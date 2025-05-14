"""
Public API views for external API access
"""

import time
import os
from django.conf import settings
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
    parser_classes,
    throttle_classes,
)
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError

# Import controllers
from app.controllers.PublicAPIController import APIKeyAuthentication, HasAPIAccess, APIRateLimitThrottle, APIKeyController
from app.controllers.ResponseCodesController import get_response_code
from app.controllers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from app.controllers.AIGeneratedTextDetectionController import TextDetectionPipeline
from app.controllers.AIGeneratedMediaDetectionController import AIGeneratedMediaDetectionPipeline
from app.controllers.MetadataAnalysisController import MetadataAnalysisPipeline
from app.controllers.HelpersController import URLHelper

# Import models
from api.models import MediaUpload, TextSubmission, DeepfakeDetectionResult, AIGeneratedMediaResult, AIGeneratedTextResult, MediaUploadMetadata, UserData
from api.models import APIKey, APIUsageLog
from api.serializers import FileUploadSerializer, APIKeySerializer, APIKeyCreateSerializer

# Initialize controllers (this assumes they're already initialized in semantic_views.py)
from api.views.semantic_views import deepfake_detection_pipeline, text_detection_pipeline, ai_generated_media_detection_pipeline, metadata_analysis_pipeline


def log_api_request(api_key, endpoint, start_time, status_code, request=None):
    """Helper function to log API usage"""
    end_time = time.time()
    response_time = end_time - start_time

    # Get IP address and user agent if request is available
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT")

    # Create log entry
    APIUsageLog.objects.create(
        api_key=api_key,
        endpoint=endpoint,
        method=request.method if request else "UNKNOWN",
        status_code=status_code,
        response_time=response_time,
        ip_address=ip_address,
        user_agent=user_agent,
    )


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
@permission_classes([HasAPIAccess])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def deepfake_detection_api(request):
    """
    API endpoint for deepfake detection

    Accepts a media file (image or video) and returns detection results.
    """
    start_time = time.time()

    # Check permissions for this specific endpoint
    if not request.auth.can_use_deepfake_detection:
        return JsonResponse(
            {"success": False, "error": "Your API key does not have access to the Deepfake Detection API", "code": "API_PERMISSION_DENIED"},
            status=status.HTTP_403_FORBIDDEN,
        )

    file_upload_serializer = FileUploadSerializer(data=request.FILES)
    if file_upload_serializer.is_valid():
        try:
            # Extract the uploaded file
            media_file = file_upload_serializer.validated_data["file"]

            # Save file to temporary location
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = fs.save(f"api_uploads/{media_file.name}", media_file)
            file_path = fs.path(filename)

            # Check media type
            file_type = deepfake_detection_pipeline.media_processor.check_media_type(file_path)
            if file_type not in ["Image", "Video"]:
                return JsonResponse(
                    {"success": False, "error": f"Unsupported file type: {file_type}", "code": "UNSUPPORTED_MEDIA_TYPE"},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )

            # Process metadata
            metadata = metadata_analysis_pipeline.extract_metadata(file_path)

            # Run deepfake detection
            results = deepfake_detection_pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
            )

            if results is False:
                # No faces detected
                response_data = {
                    "success": True,
                    "code": "MEDIA_CONTAINS_NO_FACES",
                    "result": {
                        "is_deepfake": False,
                        "confidence_score": 0.0,
                        "frames_analyzed": 0,
                        "fake_frames": 0,
                        "file_type": file_type,
                    },
                    "metadata": metadata,
                }
                status_code = status.HTTP_200_OK
            else:
                # Successful detection with faces
                response_data = {
                    "success": True,
                    "code": "SUCCESS",
                    "result": {
                        "is_deepfake": results["statistics"]["is_deepfake"],
                        "confidence_score": results["statistics"]["confidence"],
                        "frames_analyzed": results["statistics"]["total_frames"],
                        "fake_frames": results["statistics"]["fake_frames"],
                        "fake_frames_percentage": results["statistics"]["fake_frames_percentage"],
                        "file_type": file_type,
                    },
                    "metadata": metadata,
                }
                status_code = status.HTTP_200_OK

            # Log the API request
            log_api_request(request.auth, "deepfake_detection_api", start_time, status_code, request)

            return JsonResponse(response_data, status=status_code)

        except Exception as e:
            # Log the API request with error status
            log_api_request(request.auth, "deepfake_detection_api", start_time, status.HTTP_500_INTERNAL_SERVER_ERROR, request)

            return JsonResponse({"success": False, "error": str(e), "code": "MEDIA_PROCESSING_ERROR"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        # Log the API request with error status
        log_api_request(request.auth, "deepfake_detection_api", start_time, status.HTTP_400_BAD_REQUEST, request)

        return JsonResponse({"success": False, "error": file_upload_serializer.errors, "code": "FILE_UPLOAD_ERROR"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
@permission_classes([HasAPIAccess])
@parser_classes([JSONParser])
def ai_text_detection_api(request):
    """
    API endpoint for AI-generated text detection

    Accepts text content and returns detection results.
    """
    start_time = time.time()

    # Check permissions for this specific endpoint
    if not request.auth.can_use_ai_text_detection:
        return JsonResponse(
            {"success": False, "error": "Your API key does not have access to the AI Text Detection API", "code": "API_PERMISSION_DENIED"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Validate input
    if not request.data or "text" not in request.data:
        # Log the API request with error status
        log_api_request(request.auth, "ai_text_detection_api", start_time, status.HTTP_400_BAD_REQUEST, request)

        return JsonResponse({"success": False, "error": "Text parameter missing", "code": "TEXT_MISSING"}, status=status.HTTP_400_BAD_REQUEST)

    text = request.data["text"]
    highlight = request.data.get("highlight", False)

    if len(text.strip()) < 50:  # Minimum text length for reliable analysis : 50 characters
        # Log the API request with error status
        log_api_request(request.auth, "ai_text_detection_api", start_time, status.HTTP_400_BAD_REQUEST, request)

        return JsonResponse(
            {"success": False, "error": "Text is too short for reliable analysis (minimum 50 characters)", "code": "TEXT_TOO_SHORT"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Process the text
        results = text_detection_pipeline.process_text(text, highlight=highlight)

        # Prepare response
        response_data = {
            "success": True,
            "code": "SUCCESS",
            "result": {
                "is_ai_generated": results["prediction"] != "Human",
                "source_prediction": results["prediction"],
                "confidence_scores": results["confidence"],
            },
        }

        # Add highlighted text if requested
        if highlight and "highlighted_text" in results:
            response_data["result"]["highlighted_text"] = results["highlighted_text"]

        # Log the API request
        log_api_request(request.auth, "ai_text_detection_api", start_time, status.HTTP_200_OK, request)

        return JsonResponse(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        # Log the API request with error status
        log_api_request(request.auth, "ai_text_detection_api", start_time, status.HTTP_500_INTERNAL_SERVER_ERROR, request)

        return JsonResponse({"success": False, "error": str(e), "code": "TEXT_PROCESSING_ERROR"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@authentication_classes([APIKeyAuthentication])
@permission_classes([HasAPIAccess])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def ai_media_detection_api(request):
    """
    API endpoint for AI-generated media detection

    Accepts an image file and returns detection results.
    """
    start_time = time.time()

    # Check permissions for this specific endpoint
    if not request.auth.can_use_ai_media_detection:
        return JsonResponse(
            {"success": False, "error": "Your API key does not have access to the AI Media Detection API", "code": "API_PERMISSION_DENIED"},
            status=status.HTTP_403_FORBIDDEN,
        )

    file_upload_serializer = FileUploadSerializer(data=request.FILES)
    if file_upload_serializer.is_valid():
        try:
            # Extract the uploaded file
            media_file = file_upload_serializer.validated_data["file"]

            # Save file to temporary location
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = fs.save(f"api_uploads/{media_file.name}", media_file)
            file_path = fs.path(filename)

            # Check media type - only image is supported for AI media detection
            file_type = deepfake_detection_pipeline.media_processor.check_media_type(file_path)
            if file_type != "Image":
                return JsonResponse(
                    {"success": False, "error": "Only image files are supported for AI media detection", "code": "UNSUPPORTED_MEDIA_TYPE"},
                    status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )

            # Process metadata
            metadata = metadata_analysis_pipeline.extract_metadata(file_path)

            # Run AI media detection
            results = ai_generated_media_detection_pipeline.process_media(file_path)

            response_data = {
                "success": True,
                "code": "SUCCESS",
                "result": {
                    "is_ai_generated": results["prediction"] == "fake",
                    "prediction": results["prediction"],
                    "confidence_scores": {"ai_generated": results["fake_probability"], "real": results["real_probability"]},
                },
                "metadata": metadata,
            }

            # Log the API request
            log_api_request(request.auth, "ai_media_detection_api", start_time, status.HTTP_200_OK, request)

            return JsonResponse(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # Log the API request with error status
            log_api_request(request.auth, "ai_media_detection_api", start_time, status.HTTP_500_INTERNAL_SERVER_ERROR, request)

            return JsonResponse({"success": False, "error": str(e), "code": "MEDIA_PROCESSING_ERROR"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        # Log the API request with error status
        log_api_request(request.auth, "ai_media_detection_api", start_time, status.HTTP_400_BAD_REQUEST, request)

        return JsonResponse({"success": False, "error": file_upload_serializer.errors, "code": "FILE_UPLOAD_ERROR"}, status=status.HTTP_400_BAD_REQUEST)


###########################################
# API Key Management Views
###########################################


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def api_key_management(request):
    """
    GET: List all API keys for the authenticated user
    POST: Create a new API key for the authenticated user
    """
    try:
        # Get user data
        user_data = UserData.objects.get(user=request.user)

        if request.method == "GET":
            # Get all API keys for this user
            api_keys = APIKey.objects.filter(user=user_data)
            serializer = APIKeySerializer(api_keys, many=True)

            return JsonResponse({**get_response_code("SUCCESS"), "data": serializer.data}, status=status.HTTP_200_OK)

        elif request.method == "POST":
            # Create a new API key
            serializer = APIKeyCreateSerializer(data=request.data)
            if serializer.is_valid():
                # Use controller to create the key
                validated_data = serializer.validated_data
                api_key = APIKeyController.create_key(
                    user_data=user_data,
                    name=validated_data.get("name"),
                    expires_days=None if not validated_data.get("expires_at") else (validated_data.get("expires_at").date() - timezone.now().date()).days,
                    daily_limit=validated_data.get("daily_limit", 1000),
                    can_use_deepfake_detection=validated_data.get("can_use_deepfake_detection", True),
                    can_use_ai_text_detection=validated_data.get("can_use_ai_text_detection", True),
                    can_use_ai_media_detection=validated_data.get("can_use_ai_media_detection", True),
                )

                # Return the created key
                response_serializer = APIKeySerializer(api_key)
                return JsonResponse({**get_response_code("SUCCESS"), "data": response_serializer.data}, status=status.HTTP_201_CREATED)
            else:
                return JsonResponse({**get_response_code("GENERAL_ERROR"), "error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
    except UserData.DoesNotExist:
        return JsonResponse(get_response_code("USER_DATA_NOT_FOUND"), status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JsonResponse({**get_response_code("GENERAL_ERROR"), "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def api_key_detail(request, key_id):
    """
    GET: Get details of a specific API key
    DELETE: Revoke (deactivate) a specific API key
    """
    try:
        # Get user data
        user_data = UserData.objects.get(user=request.user)

        # Get the API key and ensure it belongs to this user
        try:
            api_key = APIKey.objects.get(pk=key_id, user=user_data)
        except APIKey.DoesNotExist:
            return JsonResponse({**get_response_code("NOT_FOUND"), "error": "API key not found or does not belong to you."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            # Return the API key details
            serializer = APIKeySerializer(api_key)
            return JsonResponse({**get_response_code("SUCCESS"), "data": serializer.data}, status=status.HTTP_200_OK)

        elif request.method == "DELETE":
            # Revoke the API key
            success = APIKeyController.revoke_key(key_id)
            if success:
                return JsonResponse({**get_response_code("SUCCESS"), "message": "API key revoked successfully."}, status=status.HTTP_200_OK)
            else:
                return JsonResponse({**get_response_code("GENERAL_ERROR"), "error": "Failed to revoke API key."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except UserData.DoesNotExist:
        return JsonResponse(get_response_code("USER_DATA_NOT_FOUND"), status=status.HTTP_404_NOT_FOUND)
