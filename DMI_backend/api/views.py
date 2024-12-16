import time
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.models import User

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, TokenError
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from app.contollers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from .serializers import FileUploadSerializer, UserSerializer, LoginSerializer

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

# Views


@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        try:
            serializer.save()
            return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token
        return JsonResponse(
            {
                "refresh": str(refresh),
                "access": str(access),
            },
            status=status.HTTP_200_OK,
        )
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return JsonResponse(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = RefreshToken(refresh_token)
        token.blacklist()
        return JsonResponse(
            {"message": "Successfully logged out."},
            status=status.HTTP_205_RESET_CONTENT,
        )

    except TokenError as e:
        return JsonResponse(
            {"error": "Token is invalid or expired."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def process_deepfake_media(request):
    serializer = FileUploadSerializer(data=request.data)

    if serializer.is_valid():
        try:
            validated_data = serializer.validated_data
            media_file = validated_data["file"]
            user = request.user

            # Save file
            fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/submissions/")
            filename = fs.save(
                f"uid{user.id}-{time.strftime('%Y-%m-%d_%H-%M-%S')}-{int(time.time() * 1000) % 1000}-{media_file.name}",
                media_file,
            )
            file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", filename)

            # Process media
            results = pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
            )

            return JsonResponse(results, status=status.HTTP_200_OK)

        except TokenError as e:
            return JsonResponse(
                {"error": "Token is invalid or expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except Exception as e:
            return JsonResponse(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh_token(request):
    try:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return JsonResponse(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token = RefreshToken(refresh_token)
        access_token = token.access_token
        return JsonResponse(
            {"access": str(access_token)},
            status=status.HTTP_200_OK,
        )
    except TokenError as e:
        return JsonResponse(
            {"error": "Token is invalid or expired."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
