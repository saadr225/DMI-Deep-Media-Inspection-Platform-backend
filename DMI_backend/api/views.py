# DMI_backend/api/views.py

import time
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import authenticate

from django.contrib.auth.models import User
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, TokenError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from app.models import UserData
from app.contollers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from .serializers import (
    FileUploadSerializer,
    UserSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
)
from .models import MediaUpload, DeepfakeDetectionResult
from .response_codes import get_response_code, RESPONSE_CODES
from rest_framework_simplejwt.views import TokenRefreshView

from datetime import datetime, timezone
import os

# Initialize DeepfakeDetectionPipeline
pipeline = DeepfakeDetectionPipeline(
    frame_model_path=f"{settings.ML_MODELS_DIR}/acc99.76_test-2.1_FRAMES_deepfake_detector_resnext50.pth",
    crop_model_path=f"{settings.ML_MODELS_DIR}/acc99.53_test-2.1_CROPS_deepfake_detector_resnext50.pth",
    frames_dir=f"{settings.MEDIA_ROOT}/temp/temp_frames/",
    crops_dir=f"{settings.MEDIA_ROOT}/temp/temp_crops/",
    threshold=0.4,
    log_level=0,
    FRAMES_FILE_FORMAT="png",
)


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    user_serializer = UserSerializer(data=request.data)
    if user_serializer.is_valid():
        try:
            user = user_serializer.save()
            user_data = UserData.objects.create(user=user)
            user_response = user_serializer.data
            user_data_response = {
                "user": user_response,
                "user_data": {
                    "is_verified": user_data.is_verified,
                },
            }

            return JsonResponse(
                {
                    **get_response_code("USER_CREATION_SUCCESS"),
                    "data": user_data_response,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return JsonResponse(
                {**get_response_code("USER_CREATION_ERROR"), "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return JsonResponse(
        {**get_response_code("USER_CREATION_ERROR"), "error": user_serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        validated_data = serializer.validated_data
        is_email = validated_data["is_email"]
        password = validated_data["password"]

        if is_email:
            email = validated_data.get("email")
            if not email:
                return JsonResponse(
                    {
                        **get_response_code("INVALID_CREDENTIALS"),
                        "error": "Email is required when is_email is True.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                user_obj = User.objects.get(email=email)
                username = user_obj.username
            except User.DoesNotExist:
                return JsonResponse(
                    get_response_code("INVALID_CREDENTIALS"),
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            username = validated_data.get("username")
            if not username:
                return JsonResponse(
                    {
                        **get_response_code("INVALID_CREDENTIALS"),
                        "error": "Username is required when is_email is False.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user = authenticate(username=username, password=password)
        if user:
            try:
                user_data = UserData.objects.get(user=user)
                user_response = UserSerializer(user).data
                user_data_response = {
                    "user": user_response,
                    "user_data": {
                        "is_verified": user_data.is_verified,
                    },
                }

                refresh = RefreshToken.for_user(user)
                access = refresh.access_token

                # Get token expiry times
                refresh_expiry = datetime.fromtimestamp(refresh["exp"], timezone.utc)
                access_expiry = datetime.fromtimestamp(access["exp"], timezone.utc)

                return JsonResponse(
                    {
                        **get_response_code("SUCCESS"),
                        "refresh": str(refresh),
                        "access": str(access),
                        "refresh_expiry": refresh_expiry.isoformat(),
                        "access_expiry": access_expiry.isoformat(),
                        "authenticated_user": user_data_response,
                    },
                    status=status.HTTP_200_OK,
                )
            except UserData.DoesNotExist:
                return JsonResponse(
                    get_response_code("USER_DATA_NOT_FOUND"),
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return JsonResponse(
                get_response_code("INVALID_CREDENTIALS"),
                status=status.HTTP_400_BAD_REQUEST,
            )
    return JsonResponse(
        {**get_response_code("INVALID_CREDENTIALS"), "error": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return JsonResponse(
                get_response_code("REFRESH_TOKEN_REQUIRED"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = RefreshToken(refresh_token)
        token.blacklist()
        return JsonResponse(
            get_response_code("LOGOUT_SUCCESS"),
            status=status.HTTP_205_RESET_CONTENT,
        )

    except TokenError as e:
        return JsonResponse(
            get_response_code("TOKEN_INVALID_OR_EXPIRED"),
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("FILE_UPLOAD_ERROR"), "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(
        data=request.data, context={"request": request}
    )
    if serializer.is_valid():
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return JsonResponse(
                get_response_code("OLD_PASSWORD_INCORRECT"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return JsonResponse(
            get_response_code("PASSWORD_CHANGE_SUCCESS"),
            status=status.HTTP_200_OK,
        )
    else:
        return JsonResponse(
            {**get_response_code("FILE_UPLOAD_ERROR"), "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return JsonResponse(
                get_response_code("REFRESH_TOKEN_REQUIRED"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = RefreshToken(refresh_token)
        access_token = token.access_token

        # Get access token expiry time
        access_expiry = datetime.fromtimestamp(access_token["exp"], timezone.utc)

        return JsonResponse(
            {
                **get_response_code("SUCCESS"),
                "access": str(access_token),
                "access_expiry": access_expiry.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
    except TokenError as e:
        return JsonResponse(
            get_response_code("TOKEN_INVALID_OR_EXPIRED"),
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("FILE_UPLOAD_ERROR"), "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


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
                file_type=pipeline.media_processor.check_media_type(file_path),
            )

            # Process media
            results = pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
            )
            deepfake_result = DeepfakeDetectionResult.objects.create(
                media_upload=media_upload,
                is_deepfake=results["statistics"]["is_deepfake"],
                confidence_score=results["statistics"]["confidence"],
                frames_analyzed=results["statistics"]["total_frames"],
                fake_frames=results["statistics"]["fake_frames"],
                analysis_report=results,
            )

            result_data = {
                "id": deepfake_result.id,
                "media_upload": deepfake_result.media_upload.id,
                "is_deepfake": deepfake_result.is_deepfake,
                "confidence_score": deepfake_result.confidence_score,
                "frames_analyzed": deepfake_result.frames_analyzed,
                "fake_frames": deepfake_result.fake_frames,
                "analysis_report": deepfake_result.analysis_report,
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

@api_view(["GET"])
@permission_classes([AllowAny])
def get_response_codes(request):
    return JsonResponse(RESPONSE_CODES, status=status.HTTP_200_OK)