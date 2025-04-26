from datetime import datetime, timezone

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import JsonResponse
from django.utils.crypto import get_random_string

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from app.controllers.ResponseCodesController import get_response_code
from app.models import PasswordResetToken, UserData
from api.serializers import (
    ChangeEmailSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    UserSerializer,
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
