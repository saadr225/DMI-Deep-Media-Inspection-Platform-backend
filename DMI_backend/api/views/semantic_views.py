import os
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
from app.contollers.HelpersController import URLHelper
from api.models import UserData, MediaUpload, DeepfakeDetectionResult, AIGeneratedMediaResult
from api.serializers import FileUploadSerializer

# Initialize DeepfakeDetectionPipeline
print("Initializing DeepfakeDetectionPipeline...")
deepfake_detection_pipeline = DeepfakeDetectionPipeline(
    frame_model_path=f"{settings.ML_MODELS_DIR}/acc99.76_test-2.1_FRAMES_deepfake_detector_resnext50.pth",
    crop_model_path=f"{settings.ML_MODELS_DIR}/acc99.53_test-2.1_CROPS_deepfake_detector_resnext50.pth",
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
    model_path=f"{settings.ML_MODELS_DIR}/acc98.30_test-2.1_AI_image_detector_resnext101_32x8d.pth",
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
                file_identifier=filename,
                file_type=deepfake_detection_pipeline.media_processor.check_media_type(file_path),
            )
            print(f"file path: {file_path}")
            metatdata = metadata_analysis_pipeline.extract_metadata(file_path)
            # Process media
            results = deepfake_detection_pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
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
                    analysis_report={"final_verdict": "Media contains no person."},
                )
                satus_code = "MEDIA_CONTAINS_NO_FACES"

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
                file_identifier=filename,
                file_type="image",  # AI generated media only supports images
            )
            metatdata = metadata_analysis_pipeline.extract_metadata(file_path)
            # Process media
            results = ai_generated_media_detection_pipeline.process_image(file_path)

            is_generated = results["prediction"] == "fake"

            ai_generated_result = AIGeneratedMediaResult.objects.create(
                media_upload=media_upload,
                is_generated=is_generated,
                confidence_score=results["confidence"],
                analysis_report={
                    "file_id": results["file_id"],
                    "media_path": results["media_path"],
                    "gradcam_path": results["gradcam_path"],
                    "prediction": results["prediction"],
                    "confidence": results["confidence"],
                },
            )

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
    file_identfier = request.data.get("file_identifier")
    if not file_identfier:
        return JsonResponse(
            {**get_response_code("FILE_IDENTIFIER_REQUIRED"), "error": "File identifier is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Direct path construction instead of searching through all files
        file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", file_identfier)

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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_submissions_history(request):
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)
        user_submissions = MediaUpload.objects.filter(user=user_data)

        # Organize submissions by type
        categorized_history = {
            "deepfake_analysis": [],
            "ai_generated_analysis": [],
            "dual_analysis": [],  # Files analyzed by both methods
            "incomplete_analysis": [],  # Files with no analysis results
        }

        for submission in user_submissions:
            base_entry = {
                "id": submission.id,
                "file": URLHelper.convert_to_public_url(file_path=submission.file.path),
                "original_filename": submission.original_filename,
                "file_type": submission.file_type,
                "upload_date": submission.upload_date,
            }

            df_entry = DeepfakeDetectionResult.objects.filter(media_upload_id=submission.id)
            ai_entry = AIGeneratedMediaResult.objects.filter(media_upload_id=submission.id)

            has_df = df_entry.exists()
            has_ai = ai_entry.exists()

            if has_df:
                base_entry["deepfake_detection"] = {
                    "is_deepfake": df_entry[0].is_deepfake,
                    "confidence_score": df_entry[0].confidence_score,
                    "frames_analyzed": df_entry[0].frames_analyzed,
                    "fake_frames": df_entry[0].fake_frames,
                    "analysis_report": df_entry[0].analysis_report,
                }

            if has_ai:
                base_entry["ai_generated_media"] = {
                    "is_generated": ai_entry[0].is_generated,
                    "confidence_score": ai_entry[0].confidence_score,
                    "analysis_report": ai_entry[0].analysis_report,
                }

            # Categorize based on analysis type
            if has_df and has_ai:
                categorized_history["dual_analysis"].append(base_entry)
            elif has_df:
                categorized_history["deepfake_analysis"].append(base_entry)
            elif has_ai:
                categorized_history["ai_generated_analysis"].append(base_entry)
            else:
                categorized_history["incomplete_analysis"].append(base_entry)

        # Add summary statistics
        summary = {
            "total_submissions": len(user_submissions),
            "deepfake_only_count": len(categorized_history["deepfake_analysis"]),
            "ai_generated_only_count": len(categorized_history["ai_generated_analysis"]),
            "dual_analysis_count": len(categorized_history["dual_analysis"]),
            "incomplete_analysis_count": len(categorized_history["incomplete_analysis"]),
        }

        return JsonResponse(
            {**get_response_code("SUCCESS"), "summary": summary, "data": categorized_history},
            status=status.HTTP_200_OK,
        )
    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("HISTORY_FETCH_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
