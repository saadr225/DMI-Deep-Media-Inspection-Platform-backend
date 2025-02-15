# DMI_backend/api/views.py
import os
import time
from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FileUploadParser, FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from app.contollers.AIGeneratedMediaDetectionController import AIGeneratedMediaDetectionPipeline
from app.contollers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from app.contollers.MetadataAnalysisController import MetadataAnalysisPipeline
from app.contollers.HelpersController import URLHelper
from app.contollers.ResponseCodesController import RESPONSE_CODES, get_response_code

from app.models import PasswordResetToken, UserData
from .models import AIGeneratedMediaResult, DeepfakeDetectionResult, MediaUpload

from .serializers import (
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    FileUploadSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    UserSerializer,
)

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
                        **get_response_code("EMAIL_REQUIRED"),
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
                        **get_response_code("USERNAME_REQUIRED"),
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
            {**get_response_code("GENERAL_ERROR"), "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        validated_data = serializer.validated_data
        if validated_data["new_password"] != validated_data["new_password_repeat"]:
            return JsonResponse(
                {
                    **get_response_code("PASSWORDS_DONT_MATCH"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            {**get_response_code("PASSWORD_CHANGE_ERROR"), "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    serializer = ForgotPasswordSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return JsonResponse(
                get_response_code("USER_NOT_FOUND"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure UserData exists for the user
        user_data, created = UserData.objects.get_or_create(user=user)

        # Generate a random password reset token
        reset_token = get_random_string(length=64)

        # Save the token to the PasswordResetToken model
        PasswordResetToken.objects.update_or_create(
            user_data=user_data, defaults={"reset_token": reset_token}
        )

        # Send email with the reset token
        reset_url = f"http://{settings.FRONTEND_HOST_URL}/reset_password/{reset_token}/"

        # reset_url = f"{settings.HOST_URL}/api/user/reset_password/{reset_token}/"
        send_mail(
            f"Password Reset Request for {user.username}",
            f"Please use the following link to reset your password: {reset_url}",
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return JsonResponse(
            get_response_code("SUCCESS"),
            status=status.HTTP_200_OK,
        )
    else:
        return JsonResponse(
            {**get_response_code("FORGOT_PASSWORD_ERROR"), "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(reset_token=token)
    except PasswordResetToken.DoesNotExist:
        return JsonResponse(
            get_response_code("RESET_TOKEN_NOT_FOUND"),
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_password = request.data.get("new_password")
    if not new_password:
        return JsonResponse(
            {**get_response_code("NEW_PASSWORD_REQUIRED"), "error": "New password is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_data = reset_token.user_data
    user = user_data.user
    user.password = make_password(new_password)
    user.save()

    # Delete the used token
    reset_token.delete()

    return JsonResponse(
        {
            **get_response_code("PASSWORD_CHANGE_SUCCESS"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def change_email(request):
    serializer = ChangeEmailSerializer(data=request.data)
    if serializer.is_valid():
        user = request.user
        new_email = serializer.validated_data["new_email"]
        if User.objects.filter(email=new_email).exists():
            return JsonResponse(
                get_response_code("EMAIL_ALREADY_IN_USE"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.email = new_email
        user.save()
        return JsonResponse(
            get_response_code("EMAIL_CHANGE_SUCCESS"),
            status=status.HTTP_200_OK,
        )
    else:
        return JsonResponse(
            {**get_response_code("EMAIL_CHANGE_ERROR"), "error": serializer.errors},
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
            {**get_response_code("GENERAL_ERROR"), "error": str(e)},
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
        user_submissions_data = []
        for submission in user_submissions:
            history_entry = {
                "id": submission.id,
                "file": URLHelper.convert_to_public_url(file_path=submission.file.path),
                "original_filename": submission.original_filename,
                "file_type": submission.file_type,
                "upload_date": submission.upload_date,
            }
            df_entry = DeepfakeDetectionResult.objects.filter(media_upload_id=submission.id)
            ai_entry = AIGeneratedMediaResult.objects.filter(media_upload_id=submission.id)
            if df_entry.exists():
                history_entry["deepfake_detection"] = {
                    "is_deepfake": df_entry[0].is_deepfake,
                    "confidence_score": df_entry[0].confidence_score,
                    "frames_analyzed": df_entry[0].frames_analyzed,
                    "fake_frames": df_entry[0].fake_frames,
                    "analysis_report": df_entry[0].analysis_report,
                }
            if ai_entry.exists():
                history_entry["ai_generated_media"] = {
                    "is_generated": ai_entry[0].is_generated,
                    "confidence_score": ai_entry[0].confidence_score,
                    "analysis_report": ai_entry[0].analysis_report,
                }
            user_submissions_data.append(history_entry)

        return JsonResponse(
            {
                **get_response_code("SUCCESS"),
                "data": user_submissions_data,
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
            {**get_response_code("HISTORY_FETCH_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    user = request.user
    user_data = UserData.objects.get(user=user)
    user_response = UserSerializer(user).data
    user_data_response = {
        "user": user_response,
        "user_data": {
            "is_verified": user_data.is_verified,
        },
    }

    return JsonResponse(
        {
            **get_response_code("SUCCESS"),
            "data": user_data_response,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_response_codes(request):
    return JsonResponse(RESPONSE_CODES, status=status.HTTP_200_OK)
