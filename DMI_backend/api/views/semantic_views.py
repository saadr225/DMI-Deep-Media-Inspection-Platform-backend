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

from app.contollers.ResponseCodesController import get_response_code
from app.contollers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from app.contollers.AIGeneratedMediaDetectionController import AIGeneratedMediaDetectionPipeline
from app.contollers.MetadataAnalysisController import MetadataAnalysisPipeline
from app.contollers.HelpersController import URLHelper, HuggingFaceHelper

from api.models import (
    MediaUploadMetadata,
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
)

# Get model files if they don't exist locally
MODEL_FILES = {
    "frames_model": "V3_FRAMES_deepfake_detector_resnext101_64x4d_acc99.33_epochs25.pth",
    "crops_model": "V3_CROPS_deepfake_detector_resnext101_32x8d_acc98.71_epochs25.pth",
    "ai_gen_model": "V3_AI_image_detector_resnext101_32x8d_acc98.30_epochs25.pth",
}

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
    frame_model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['frames_model']}",
    crop_model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['crops_model']}",
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
    model_path=f"{settings.ML_MODELS_DIR}/{MODEL_FILES['ai_gen_model']}",
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
