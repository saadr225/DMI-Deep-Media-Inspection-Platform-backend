import hashlib
import os
import shutil
import sys
import time
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from rest_framework_simplejwt.exceptions import TokenError

from app.controllers.FacialWatchAndRecognitionController import FacialWatchAndRecognitionPipleine
from app.controllers.AIGeneratedTextDetectionController import TextDetectionPipeline
from app.controllers.ResponseCodesController import get_response_code
from app.controllers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from app.controllers.AIGeneratedMediaDetectionController import AIGeneratedMediaDetectionPipeline
from app.controllers.MetadataAnalysisController import MetadataAnalysisPipeline
from app.controllers.HelpersController import URLHelper, HuggingFaceHelper

from api.models import (
    AIGeneratedTextResult,
    MediaUploadMetadata,
    TextSubmission,
    UserData,
    MediaUpload,
    DeepfakeDetectionResult,
    AIGeneratedMediaResult,
)
from api.serializers import FileUploadSerializer


# # Add the project root directory to Python path
# project_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
# if project_root not in sys.path:
#     sys.path.append(project_root)

# import the helper
# from Hugging_face_helper.helper.main import HuggingFaceHelper
# Try absolute import

# Initialize HuggingFace Helper
print("Initializing HuggingFace Helper...")
hf_helper = HuggingFaceHelper(
    token=os.environ.get("HF_TOKEN"),
    repo_name="spectrewolf8/DMI_FYP_Models_Repo",
    repo_local_dir=f"../../hf_helper_files/repo/",
    cache_dir=f"../../hf_helper/cache/",
    offline_mode=os.environ.get("HF_OFFLINE_MODE", "False").lower() == "true",
    check_updates_interval=24 * 3600,  # Check for updates once per day
)

# Get model files if they don't exist locally
MODEL_FILES = {
    "deepfake_frames_detection_model": "V3_FRAMES_deepfake_detector_resnext101_64x4d_acc99.33_epochs25.pth",
    "deepfake_crops_detection_model": "V3_CROPS_deepfake_detector_resnext101_32x8d_acc98.71_epochs25.pth",
    "ai_gen_media_detection_model": "V3_AI_image_detector_resnext101_32x8d_acc98.30_epochs25.pth",
    "ai_gen_text_detection_model": "AIGT_bert_epoch3.ipynb.pth",
}

facial_watch_system = FacialWatchAndRecognitionPipleine(recognition_threshold=0.3, log_level=1)

# Download models if they don't exist
for model_name, filename in MODEL_FILES.items():
    local_path = os.path.join(settings.ML_MODELS_DIR, filename)
    if not os.path.exists(local_path):
        print(f"Downloading {model_name}...")
        downloaded_path = hf_helper.download_model(filename)
        # Create ML_MODELS_DIR if it doesn't exist
        os.makedirs(settings.ML_MODELS_DIR, exist_ok=True)
        print(f"Moving {filename} to {local_path}")
        # Copy from cache to models directory
        shutil.copy2(downloaded_path, local_path)
        print(f"{model_name} downloaded successfully")
    else:
        print(f"{model_name} already exists locally")

# Initialize DeepfakeDetectionPipeline
print("Initializing DeepfakeDetectionPipeline...")
deepfake_detection_pipeline = DeepfakeDetectionPipeline(
    frame_model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['deepfake_frames_detection_model']}",
    crop_model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['deepfake_crops_detection_model']}",
    frames_dir=f"{settings.MEDIA_ROOT}/temp/temp_frames/",
    crops_dir=f"{settings.MEDIA_ROOT}/temp/temp_crops/",
    threshold=0.4,
    log_level=0,
    FRAMES_FILE_FORMAT="png",
)
print("DeepfakeDetectionPipeline initialized")

# Initialize AIGeneratedMediaDetection
print("Initializing AIGeneratedMediaDetection...")
ai_generated_media_detection_pipeline = AIGeneratedMediaDetectionPipeline(
    model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['ai_gen_media_detection_model']}",
    synthetic_media_dir=f"{settings.MEDIA_ROOT}/temp/temp_synthetic_media/",
    threshold=0.5,
    log_level=0,
    FRAMES_FILE_FORMAT="png",
)
print("AIGeneratedMediaDetection initialized")

# Initialize MetadataAnalysisPipeline
print("Initializing MetadataAnalysisPipeline...")
metadata_analysis_pipeline = MetadataAnalysisPipeline()
print("MetadataAnalysisPipeline initialized")

# Initialize TextDetectionPipeline
print("Initializing TextDetectionPipeline...")
text_detection_pipeline = TextDetectionPipeline(
    model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['ai_gen_text_detection_model']}",
    threshold=0.4,
    log_level=0,
)
print("TextDetectionPipeline initialized")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def process_deepfake_media(request):
    file_upload_serializer = FileUploadSerializer(data=request.data)

    if file_upload_serializer.is_valid():
        try:
            validated_data = file_upload_serializer.validated_data
            media_file = validated_data["file"]
            user = request.user
            original_filename = media_file.name

            # Save file
            fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/submissions/")
            filename = fs.save(
                f"uid{user.id}-{time.strftime('%Y-%m-%d_%H-%M-%S')}-{int(time.time() * 1000) % 1000}-{media_file.name}",
                media_file,
            )
            file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", filename)

            media_upload = MediaUpload.objects.create(
                user=UserData.objects.get(user=user),
                file=file_path,
                original_filename=original_filename,
                submission_identifier=filename,  # filename becomes the submission identifier
                file_type=deepfake_detection_pipeline.media_processor.check_media_type(file_path),
                purpose="Deepfake-Analysis",
            )
            
            metatdata = metadata_analysis_pipeline.extract_metadata(file_path)
            # Save metadata
            MediaUploadMetadata.objects.create(media_upload=media_upload, metadata=metatdata)

            # Process media
            results = deepfake_detection_pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
            )

            # Generate file identifier using media processor
            file_identifier = deepfake_detection_pipeline.media_processor.generate_combined_hash(
                file_path
            )

            if results is not False:
                deepfake_result = DeepfakeDetectionResult.objects.create(
                    media_upload=media_upload,
                    is_deepfake=results["statistics"]["is_deepfake"],
                    confidence_score=results["statistics"]["confidence"],
                    frames_analyzed=results["statistics"]["total_frames"],
                    fake_frames=results["statistics"]["fake_frames"],
                    analysis_report=results,
                )
                satus_code = "SUCCESS"
            else:
                deepfake_result = DeepfakeDetectionResult.objects.create(
                    media_upload=media_upload,
                    is_deepfake=False,
                    confidence_score=0.0,
                    frames_analyzed=0,
                    fake_frames=0,
                    analysis_report={
                        "final_verdict": "MEDIA_CONTAINS_NO_FACES",
                        "file_identifier": file_identifier,
                    },
                )
                satus_code = "MEDIA_CONTAINS_NO_FACES"

            # Add the file identifier to the media upload
            media_upload.file_identifier = file_identifier
            media_upload.save()

            result_data = {
                "id": deepfake_result.id,
                "submission_identifier": media_upload.submission_identifier,
                "media_upload": deepfake_result.media_upload.id,
                "is_deepfake": deepfake_result.is_deepfake,
                "confidence_score": deepfake_result.confidence_score,
                "frames_analyzed": deepfake_result.frames_analyzed,
                "fake_frames": deepfake_result.fake_frames,
                "analysis_report": deepfake_result.analysis_report,
                "metadata": metatdata,
            }

            return JsonResponse(
                {**get_response_code(satus_code), "data": result_data},
                status=status.HTTP_200_OK,
            )

        except TokenError as e:
            return JsonResponse(
                get_response_code("TOKEN_INVALID_OR_EXPIRED"),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return JsonResponse(
                {**get_response_code("MEDIA_PROCESSING_ERROR"), "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    else:
        return JsonResponse(
            {
                **get_response_code("FILE_UPLOAD_ERROR"),
                "error": file_upload_serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def process_ai_generated_media(request):
    file_upload_serializer = FileUploadSerializer(data=request.data)

    if file_upload_serializer.is_valid():
        try:
            validated_data = file_upload_serializer.validated_data
            media_file = validated_data["file"]
            user = request.user
            original_filename = media_file.name

            # Save file
            fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/submissions/")
            filename = fs.save(
                f"uid{user.id}-{time.strftime('%Y-%m-%d_%H-%M-%S')}-{int(time.time() * 1000) % 1000}-{media_file.name}",
                media_file,
            )
            file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", filename)

            media_upload = MediaUpload.objects.create(
                user=UserData.objects.get(user=user),
                file=file_path,
                original_filename=original_filename,
                submission_identifier=filename,  # filename becomes the submission identifier
                file_type="image",  # AI generated media only supports images
                purpose="AI-Generated-Media-Analysis",
            )
            metatdata = metadata_analysis_pipeline.extract_metadata(file_path)
            # Save metadata
            MediaUploadMetadata.objects.create(media_upload=media_upload, metadata=metatdata)

            # Process media
            results = ai_generated_media_detection_pipeline.process_image(file_path)

            is_generated = results["prediction"] == "fake"

            ai_generated_result = AIGeneratedMediaResult.objects.create(
                media_upload=media_upload,
                is_generated=is_generated,
                confidence_score=results["confidence"],
                analysis_report={
                    "file_identifier": results["file_identifier"],
                    "media_path": results["media_path"],
                    "gradcam_path": results["gradcam_path"],
                    "prediction": results["prediction"],
                    "confidence": results["confidence"],
                },
            )

            # Add the file identifier to the media upload
            media_upload.file_identifier = results["file_identifier"]
            media_upload.save()

            result_data = {
                "id": ai_generated_result.id,
                "media_upload": ai_generated_result.media_upload.id,
                "is_generated": ai_generated_result.is_generated,
                "confidence_score": ai_generated_result.confidence_score,
                "analysis_report": ai_generated_result.analysis_report,
                "metadata": metatdata,
            }

            return JsonResponse(
                {**get_response_code("SUCCESS"), "data": result_data},
                status=status.HTTP_200_OK,
            )

        except TokenError as e:
            return JsonResponse(
                get_response_code("TOKEN_INVALID_OR_EXPIRED"),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return JsonResponse(
                {**get_response_code("MEDIA_PROCESSING_ERROR"), "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    else:
        return JsonResponse(
            {
                **get_response_code("FILE_UPLOAD_ERROR"),
                "error": file_upload_serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def process_metadata(request):
    submission_identifier = request.data.get("submission_identifier")
    if not submission_identifier:
        return JsonResponse(
            {**get_response_code("FILE_IDENTIFIER_REQUIRED"), "error": "File identifier is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Direct path construction instead of searching through all files
        file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", submission_identifier)

        if not os.path.exists(file_path):
            return JsonResponse(
                get_response_code("FILE_NOT_FOUND"),
                status=status.HTTP_404_NOT_FOUND,
            )

        results = metadata_analysis_pipeline.extract_metadata(file_path)
        return JsonResponse(
            {**get_response_code("SUCCESS"), "metadata": results},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return JsonResponse(
            {**get_response_code("METADATA_ANALYSIS_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def process_ai_generated_text(request):
    """
    API endpoint to detect if text is human or AI-generated
    """
    try:
        # Validate input
        if not request.data or "text" not in request.data:
            return JsonResponse(
                {**get_response_code("TEXT_MISSING"), "error": "Text parameter missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "highlight" not in request.data:
            return JsonResponse(
                {**get_response_code("HIGHLIGHT_MISSING"), "error": "Highlight parameter missing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        text = request.data["text"]
        highlight = request.data.get("highlight")
        user = request.user

        if len(text.strip()) < 50:  # Minimum text length for reliable analysis : 50 characters
            return JsonResponse(
                {
                    **get_response_code("TEXT_TOO_SHORT"),
                    "error": "Text is too short for reliable analysis",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate a submission identifier
        text_hash = hashlib.md5(text.encode()).hexdigest()[:16]
        submission_identifier = f"uid{user.id}-{time.strftime('%Y-%m-%d_%H-%M-%S')}-{text_hash}"

        # Save text submission
        text_submission = TextSubmission.objects.create(
            user=UserData.objects.get(user=user),
            text_content=text,
            submission_identifier=submission_identifier,
            purpose="AI-Text-Analysis",
        )

        print(highlight)
        # Process the text
        results = text_detection_pipeline.process_text(text, highlight=highlight)

        # Determine if it's AI-generated (anything not classified as "Human")
        is_ai_generated = results["prediction"] != "Human"

        # Save detection results
        text_detection_result = AIGeneratedTextResult.objects.create(
            text_submission=text_submission,
            is_ai_generated=is_ai_generated,
            source_prediction=results["prediction"],
            confidence_scores=results["confidence"],
            highlighted_text=results.get("highlighted_text", ""),
            html_text=results.get("html_text", ""),
        )

        # Prepare response data
        result_data = {
            "submission_identifier": submission_identifier,
            "is_ai_generated": text_detection_result.is_ai_generated,
            "source_prediction": text_detection_result.source_prediction,
            "confidence_scores": text_detection_result.confidence_scores,
            "highlighted_text": text_detection_result.highlighted_text if highlight else None,
            "html_text": text_detection_result.html_text if highlight else None,
        }

        # Return the analysis results
        return JsonResponse(
            {**get_response_code("SUCCESS"), "data": result_data}, status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {**get_response_code("TEXT_PROCESSING_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
