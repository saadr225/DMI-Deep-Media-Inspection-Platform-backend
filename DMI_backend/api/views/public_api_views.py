import json
import time
import uuid
import os
from django.conf import settings
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from api.models import APIKey, UserData, MediaUpload, DeepfakeDetectionResult, AIGeneratedMediaResult, TextSubmission, AIGeneratedTextResult, MediaUploadMetadata
from app.controllers.PublicAPIController import PublicAPIController
from app.controllers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from app.controllers.AIGeneratedMediaDetectionController import AIGeneratedMediaDetectionPipeline
from app.controllers.AIGeneratedTextDetectionController import TextDetectionPipeline
from app.controllers.ResponseCodesController import get_response_code
from api.views.semantic_views import deepfake_detection_pipeline, ai_generated_media_detection_pipeline, text_detection_pipeline

# API Key Management Endpoints


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def api_key_management(request):
    """
    GET: List all API keys for the authenticated user
    POST: Create a new API key for the authenticated user
    """
    user_data = UserData.objects.get(user=request.user)

    if request.method == "GET":
        # List all API keys for the user
        api_keys = APIKey.objects.filter(user=user_data, is_active=True)
        keys_data = []

        for key in api_keys:
            keys_data.append(
                {
                    "id": key.id,
                    "name": key.name,
                    "key": key.key,
                    "created_at": key.created_at,
                    "expires_at": key.expires_at,
                    "daily_limit": key.daily_limit,
                    "daily_usage": key.daily_usage,
                    "can_use_deepfake_detection": key.can_use_deepfake_detection,
                    "can_use_ai_text_detection": key.can_use_ai_text_detection,
                    "can_use_ai_media_detection": key.can_use_ai_media_detection,
                }
            )

        return JsonResponse({"success": True, "code": get_response_code("SUCCESS")["code"], "api_keys": keys_data})

    elif request.method == "POST":
        # Create a new API key
        try:
            data = json.loads(request.body)
            name = data.get("name")

            if not name:
                return JsonResponse(
                    {"success": False, "code": get_response_code("INVALID_INPUT")["code"], "message": "API key name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get optional parameters with defaults
            expires_at = data.get("expires_at")
            daily_limit = data.get("daily_limit", 1000)
            can_use_deepfake_detection = data.get("can_use_deepfake_detection", True)
            can_use_ai_text_detection = data.get("can_use_ai_text_detection", True)
            can_use_ai_media_detection = data.get("can_use_ai_media_detection", True)

            # Create new API key
            api_key = APIKey.objects.create(
                user=user_data,
                name=name,
                expires_at=expires_at,
                daily_limit=daily_limit,
                can_use_deepfake_detection=can_use_deepfake_detection,
                can_use_ai_text_detection=can_use_ai_text_detection,
                can_use_ai_media_detection=can_use_ai_media_detection,
            )

            return JsonResponse(
                {
                    "success": True,
                    "code": get_response_code("SUCCESS")["code"],
                    "api_key": {
                        "id": api_key.id,
                        "name": api_key.name,
                        "key": api_key.key,  # Send full key only once when created
                        "created_at": api_key.created_at,
                        "expires_at": api_key.expires_at,
                        "daily_limit": api_key.daily_limit,
                        "can_use_deepfake_detection": api_key.can_use_deepfake_detection,
                        "can_use_ai_text_detection": api_key.can_use_ai_text_detection,
                        "can_use_ai_media_detection": api_key.can_use_ai_media_detection,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"success": False, "code": get_response_code("INVALID_INPUT")["code"], "message": "Invalid JSON data"}, status=status.HTTP_400_BAD_REQUEST
            )


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def api_key_detail(request, key_id):
    """
    GET: Get details of a specific API key
    DELETE: Revoke (deactivate) an API key
    """
    user_data = UserData.objects.get(user=request.user)

    try:
        api_key = APIKey.objects.get(id=key_id, user=user_data)
    except APIKey.DoesNotExist:
        return JsonResponse({"success": False, "code": get_response_code("NOT_FOUND")["code"], "message": "API key not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        # Get API key details
        return JsonResponse(
            {
                "success": True,
                "code": get_response_code("SUCCESS")["code"],
                "api_key": {
                    "id": api_key.id,
                    "name": api_key.name,
                    "key": api_key.key,
                    "created_at": api_key.created_at,
                    "expires_at": api_key.expires_at,
                    "daily_limit": api_key.daily_limit,
                    "daily_usage": api_key.daily_usage,
                    "last_used_at": api_key.last_used_at,
                    "can_use_deepfake_detection": api_key.can_use_deepfake_detection,
                    "can_use_ai_text_detection": api_key.can_use_ai_text_detection,
                    "can_use_ai_media_detection": api_key.can_use_ai_media_detection,
                },
            }
        )

    elif request.method == "DELETE":
        # Revoke the API key (deactivate it)
        api_key.is_active = False
        api_key.save()

        return JsonResponse({"success": True, "code": get_response_code("SUCCESS")["code"], "message": f'API key "{api_key.name}" has been revoked'})


# Public API Endpoints


@api_view(["POST"])
@permission_classes([])  # Empty list means no permission required
@parser_classes([MultiPartParser, FormParser])
def deepfake_detection_api(request):
    """
    API endpoint for deepfake detection
    Accepts image or video files and analyzes them for potential deepfake manipulation
    """
    start_time = time.time()

    # Get API key from header
    api_key_header = request.META.get("HTTP_X_API_KEY")

    # Authenticate API key
    authenticated, api_key, auth_error = PublicAPIController.authenticate_api_key(api_key_header)
    if not authenticated:
        return JsonResponse(auth_error, status=status.HTTP_403_FORBIDDEN)

    # Check endpoint permission
    has_permission, perm_error = PublicAPIController.check_endpoint_permission(api_key, "deepfake")
    if not has_permission:
        return JsonResponse(perm_error, status=status.HTTP_403_FORBIDDEN)

    # Get file from request
    file = request.FILES.get("file")

    # Validate file
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/bmp", "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-ms-wmv"]
    is_valid, error = PublicAPIController.validate_file(file, allowed_types)
    if not is_valid:
        # Log the failed API usage
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "deepfake-detection", "POST", status.HTTP_400_BAD_REQUEST, response_time, request)
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Generate a unique identifier for this submission
        submission_identifier = str(uuid.uuid4())

        # Determine file type (image or video)
        content_type = file.content_type
        is_video = content_type.startswith("video/")

        # Save the file to the public_api submissions directory, matching internal module structure
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "public_api/submissions"))
        filename = fs.save(submission_identifier, file)
        file_path = fs.path(filename)

        # Create a MediaUpload object
        media_upload = MediaUpload.objects.create(
            user=api_key.user,
            file=file_path,
            file_type="Video" if is_video else "Image",
            original_filename=file.name,  # Changed from file_name
            submission_identifier=submission_identifier,
            file_identifier=submission_identifier,  # Added this required field
            purpose="Deepfake-Analysis",
        )

        # Process the file for deepfake detection
        result = deepfake_detection_pipeline.process_media(
            media_path=file_path,
            frame_rate=2,
        )

        # Handle different return types from the pipeline
        if result is not False and isinstance(result, dict):
            # Regular result with statistics
            detection_result = DeepfakeDetectionResult.objects.create(
                media_upload=media_upload,
                is_deepfake=result["statistics"]["is_deepfake"],
                confidence_score=result["statistics"]["confidence"],
                frames_analyzed=result["statistics"]["total_frames"],
                fake_frames=result["statistics"]["fake_frames"],
                analysis_report=result,  # Store the entire result object instead of calculating percentage
            )
        else:
            # No faces detected or other issue
            detection_result = DeepfakeDetectionResult.objects.create(
                media_upload=media_upload,
                is_deepfake=False,
                confidence_score=0.0,
                frames_analyzed=0,
                fake_frames=0,
                analysis_report={
                    "final_verdict": "MEDIA_CONTAINS_NO_FACES",
                    "file_identifier": submission_identifier,
                },
            )

        # Format the response data
        response_data = {"is_deepfake": detection_result.is_deepfake, "confidence_score": detection_result.confidence_score, "file_type": media_upload.file_type}

        # Add video specific data if applicable
        if is_video:
            response_data.update(
                {
                    "frames_analyzed": detection_result.frames_analyzed,
                    "fake_frames": detection_result.fake_frames,
                    "fake_frames_percentage": detection_result.fake_frames_percentage,
                }
            )

        # Get metadata
        metadata = {}
        try:
            media_metadata = MediaUploadMetadata.objects.get(media_upload=media_upload)
            metadata = {
                "width": media_metadata.width,
                "height": media_metadata.height,
                "format": media_metadata.format,
                "duration": media_metadata.duration,
                "codec": media_metadata.codec,
            }
        except MediaUploadMetadata.DoesNotExist:
            # Metadata might not be available for all submissions
            pass

        # Log successful API usage
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "deepfake-detection", "POST", status.HTTP_200_OK, response_time, request)

        # Return the formatted success response
        return JsonResponse(PublicAPIController.format_success_response("SUCCESS", response_data, metadata), status=status.HTTP_200_OK)

    except Exception as e:
        # Log the error
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "deepfake-detection", "POST", status.HTTP_500_INTERNAL_SERVER_ERROR, response_time, request)

        return JsonResponse({"success": False, "code": "SYS001", "message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([])  # Empty list means no permission required
@parser_classes([MultiPartParser, FormParser, JSONParser])
def ai_text_detection_api(request):
    """
    API endpoint for AI-generated text detection
    Analyzes text to determine if it was written by AI or a human
    """
    start_time = time.time()

    # Get API key from header
    api_key_header = request.META.get("HTTP_X_API_KEY")

    # Authenticate API key
    authenticated, api_key, auth_error = PublicAPIController.authenticate_api_key(api_key_header)
    if not authenticated:
        return JsonResponse(auth_error, status=status.HTTP_403_FORBIDDEN)

    # Check endpoint permission
    has_permission, perm_error = PublicAPIController.check_endpoint_permission(api_key, "ai_text")
    if not has_permission:
        return JsonResponse(perm_error, status=status.HTTP_403_FORBIDDEN)

    # Extract data from request
    try:
        data = request.data
        text = data.get("text")
        highlight = data.get("highlight", False)
    except:
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-text-detection", "POST", status.HTTP_400_BAD_REQUEST, response_time, request)
        return JsonResponse({"success": False, "code": "SYS003", "message": "Invalid JSON data"}, status=status.HTTP_400_BAD_REQUEST)

    # Validate text input
    is_valid, error = PublicAPIController.validate_text_input(text)
    if not is_valid:
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-text-detection", "POST", status.HTTP_400_BAD_REQUEST, response_time, request)
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Generate a unique identifier for this submission
        submission_identifier = str(uuid.uuid4())

        # Create a TextSubmission object - use the owner of the API key as the user
        text_submission = TextSubmission.objects.create(
            user=api_key.user, text_content=text, submission_identifier=submission_identifier  # Make sure we're using text_content, not text
        )

        # Analyze the text
        result = text_detection_pipeline.process_text(text, highlight=highlight)

        # Normalize result structure - support both "scores" and "confidence" keys
        scores = result.get("scores", {})
        if "confidence" in result and not scores:
            scores = result["confidence"]

        # Create AIGeneratedTextResult object
        text_result = AIGeneratedTextResult.objects.create(
            text_submission=text_submission,
            is_ai_generated=result["prediction"] != "Human",
            source_prediction=result["prediction"],
            confidence_scores=json.dumps(scores),
            highlighted_text=result.get("highlighted_text", ""),
            html_text=result.get("html_text", ""),
        )

        # Format the response data
        response_data = {
            "is_ai_generated": text_result.is_ai_generated,
            "source_prediction": text_result.source_prediction,
            "confidence_scores": scores,
        }

        # Add highlighted text if requested
        if highlight:
            # Get highlighted text from result if available
            highlighted_text = result.get("highlighted_text", text)
            response_data["highlighted_text"] = highlighted_text

        # Log successful API usage
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-text-detection", "POST", status.HTTP_200_OK, response_time, request)

        # Return the formatted success response
        return JsonResponse(PublicAPIController.format_success_response("SUCCESS", response_data), status=status.HTTP_200_OK)

    except Exception as e:
        # Log the error
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-text-detection", "POST", status.HTTP_500_INTERNAL_SERVER_ERROR, response_time, request)

        return JsonResponse({"success": False, "code": "SYS001", "message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([])  # Empty list means no permission required
@parser_classes([MultiPartParser, FormParser])
def ai_media_detection_api(request):
    """
    API endpoint for AI-generated media detection
    Detects if an image was generated by AI tools (e.g., DALL-E, Midjourney)
    """
    start_time = time.time()

    # Get API key from header
    api_key_header = request.META.get("HTTP_X_API_KEY")

    # Authenticate API key
    authenticated, api_key, auth_error = PublicAPIController.authenticate_api_key(api_key_header)
    if not authenticated:
        return JsonResponse(auth_error, status=status.HTTP_403_FORBIDDEN)

    # Check endpoint permission
    has_permission, perm_error = PublicAPIController.check_endpoint_permission(api_key, "ai_media")
    if not has_permission:
        return JsonResponse(perm_error, status=status.HTTP_403_FORBIDDEN)

    # Get file from request
    file = request.FILES.get("file")

    # Validate file
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/bmp"]
    is_valid, error = PublicAPIController.validate_file(file, allowed_types)
    if not is_valid:
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-media-detection", "POST", status.HTTP_400_BAD_REQUEST, response_time, request)
        return JsonResponse(error, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Generate a unique identifier for this submission
        submission_identifier = str(uuid.uuid4())

        # Save the file to the public_api submissions directory
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "public_api/submissions"))
        filename = fs.save(submission_identifier, file)
        file_path = fs.path(filename)

        # Create a MediaUpload object
        media_upload = MediaUpload.objects.create(
            user=api_key.user,
            file=file_path,
            file_type="Image",
            original_filename=file.name,  # Changed from file_name
            submission_identifier=submission_identifier,
            file_identifier=submission_identifier,  # Added this required field
            purpose="AI-Media-Analysis",
        )

        # Process the file for AI media detection
        result = ai_generated_media_detection_pipeline.process_image(file_path)

        # Handle different return types from the pipeline
        if isinstance(result, dict):
            # Dictionary return format
            is_ai_generated = result.get("is_ai_generated", False)
            scores = result.get("scores", {})
        else:
            # Boolean return format
            is_ai_generated = bool(result)
            scores = {"fake": 1.0 if is_ai_generated else 0.0, "real": 0.0 if is_ai_generated else 1.0}

        # Create AIGeneratedMediaResult object
        ai_media_result = AIGeneratedMediaResult.objects.create(
            media_upload=media_upload,
            is_generated=is_ai_generated,  # Changed from is_ai_generated
            confidence_score=scores.get("fake", 0),  # Use the "fake" score as confidence
            analysis_report={  # Add a proper analysis report
                "file_identifier": submission_identifier,
                "prediction": "fake" if is_ai_generated else "real",
                "scores": scores,
            },
        )

        # Format the response data
        response_data = {
            "is_ai_generated": ai_media_result.is_generated,  # Changed to access is_generated
            "prediction": "fake" if ai_media_result.is_generated else "real",
            "confidence_scores": {"ai_generated": scores.get("fake", 0), "real": scores.get("real", 0)},
        }

        # Get metadata
        metadata = {}
        try:
            media_metadata = MediaUploadMetadata.objects.get(media_upload=media_upload)
            metadata = {"width": media_metadata.width, "height": media_metadata.height, "format": media_metadata.format}
        except MediaUploadMetadata.DoesNotExist:
            # Metadata might not be available for all submissions
            pass

        # Log successful API usage
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-media-detection", "POST", status.HTTP_200_OK, response_time, request)

        # Return the formatted success response
        return JsonResponse(PublicAPIController.format_success_response("SUCCESS", response_data, metadata), status=status.HTTP_200_OK)

    except Exception as e:
        # Log the error
        response_time = time.time() - start_time
        PublicAPIController.log_api_usage(api_key, "ai-media-detection", "POST", status.HTTP_500_INTERNAL_SERVER_ERROR, response_time, request)

        return JsonResponse({"success": False, "code": "SYS001", "message": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
