import os
import time
from django.conf import settings
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from rest_framework_simplejwt.exceptions import TokenError

from app.controllers.ResponseCodesController import get_response_code
from app.controllers.FacialWatchAndRecognitionController import FacialWatchAndRecognitionPipleine
from app.controllers.HelpersController import URLHelper
from api.models import UserData, FacialWatchRegistration, FacialWatchMatch
from api.serializers import FileUploadSerializer


# Initialize facial watch controller
facial_watch_system = FacialWatchAndRecognitionPipleine(recognition_threshold=0.3, log_level=1)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def register_face(request):
    """
    Register a user's face for the facial watch system
    """
    file_upload_serializer = FileUploadSerializer(data=request.data)

    if file_upload_serializer.is_valid():
        try:
            user = request.user
            user_data = UserData.objects.get(user=user)
            face_image = file_upload_serializer.validated_data["file"]

            # Save file
            fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/facial_watch/")
            filename = fs.save(
                f"uid{user.id}-{time.strftime('%Y-%m-%d_%H-%M-%S')}-{face_image.name}",
                face_image,
            )
            file_path = os.path.join(f"{settings.MEDIA_ROOT}/facial_watch/", filename)

            # Register face
            result = facial_watch_system.register_user_face(user_data.id, file_path)

            if result:
                return JsonResponse(
                    {
                        **get_response_code("SUCCESS"),
                        "message": "Face registered successfully",
                        "data": {
                            "user_id": user_data.id,
                            "registration_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                # If registration failed, clean up the uploaded file
                if os.path.exists(file_path):
                    os.remove(file_path)
                return JsonResponse(
                    {
                        **get_response_code("FACE_REGISTRATION_ERROR"),
                        "error": "No face detected or multiple faces detected",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except UserData.DoesNotExist:
            return JsonResponse(
                {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except TokenError:
            return JsonResponse(
                get_response_code("TOKEN_INVALID_OR_EXPIRED"),
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return JsonResponse(
                {**get_response_code("FACE_REGISTRATION_ERROR"), "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    else:
        return JsonResponse(
            {**get_response_code("FILE_UPLOAD_ERROR"), "error": file_upload_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_registration_status(request):
    """
    Check if user has registered their face
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        registrations = FacialWatchRegistration.objects.filter(user_id=user_data.id)
        is_registered = registrations.exists()

        registration_data = []
        if is_registered:
            for reg in registrations:
                registration_data.append({"id": reg.id, "registration_date": reg.registration_date})

        return JsonResponse(
            {
                **get_response_code("SUCCESS"),
                "data": {"is_registered": is_registered, "registrations": registration_data},
            },
            status=status.HTTP_200_OK,
        )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_registration(request):
    """
    Remove user's face registration from the watch system
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        result = facial_watch_system.remove_user_registration(user_data.id)

        if result:
            return JsonResponse(
                {**get_response_code("SUCCESS"), "message": "Face registration removed successfully"},
                status=status.HTTP_200_OK,
            )
        else:
            return JsonResponse(
                {
                    **get_response_code("FACE_REGISTRATION_NOT_FOUND"),
                    "error": "No face registration found for this user",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_match_history(request):
    """
    Get history of when the user's face was detected
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        matches = FacialWatchMatch.objects.filter(user_id=user_data.id).order_by("-match_date")

        match_history = []
        for match in matches:
            media_data = None
            if match.media_upload:
                media_data = {
                    "id": match.media_upload.id,
                    "submission_identifier": match.media_upload.submission_identifier,
                    "upload_date": match.media_upload.upload_date,
                }

            match_history.append(
                {
                    "id": match.id,
                    "match_date": match.match_date,
                    "match_confidence": match.match_confidence,
                    "media_upload": media_data,
                    "notification_sent": match.notification_sent,
                }
            )

        return JsonResponse(
            {**get_response_code("SUCCESS"), "data": match_history},
            status=status.HTTP_200_OK,
        )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
