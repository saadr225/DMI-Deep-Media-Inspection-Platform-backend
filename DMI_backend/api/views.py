from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth.models import User

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser
from rest_framework_simplejwt.tokens import RefreshToken

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
        serializer.save()
        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data
        refresh = RefreshToken.for_user(user)
        return JsonResponse(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        )
    return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def logout(request):
    try:
        refresh_token = request.data["refresh"]
        token = RefreshToken(refresh_token)
        token.blacklist()
        return JsonResponse(status=status.HTTP_205_RESET_CONTENT)
    except Exception as e:
        return JsonResponse(status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def process_deepfake_media(request):
    serializer = FileUploadSerializer(data=request.data)

    if serializer.is_valid():
        try:
            validated_data = serializer.validated_data
            media_file = validated_data["file"]

            # Save file
            fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/submissions/")
            filename = fs.save(media_file.name, media_file)
            file_path = os.path.join(f"{settings.MEDIA_ROOT}/submissions/", filename)

            # Process media
            results = pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
            )

            # # Add metadata
            # results.update(
            #     {
            #         "title": validated_data.get("title", ""),
            #         "description": validated_data.get("description", ""),
            #         "file_type": validated_data.get("file_type", ""),
            #         "file_size": validated_data.get("file_size", ""),
            #         "upload_date": (
            #             validated_data.get("upload_date", "").isoformat()
            #             if validated_data.get("upload_date")
            #             else ""
            #         ),
            #     }
            # )

            return JsonResponse(results, status=status.HTTP_200_OK)

        except Exception as e:
            return JsonResponse(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    else:
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
