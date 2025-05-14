from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

# Import API key serializers
from api.models import APIKey


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "password")
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("This username is already in use.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(required=True)
    is_email = serializers.BooleanField(required=True)

    def validate(self, data):
        email = data.get("email")
        username = data.get("username")
        password = data.get("password")
        is_email = data.get("is_email")

        if is_email is None:
            data["error"] = "The 'is_email' flag is required."
        elif is_email and not email:
            data["error"] = "Email is required when is_email is True."
        elif not is_email and not username:
            data["error"] = "Username is required when is_email is False."
        elif not password:
            data["error"] = "Password is required."

        return data


class ChangeEmailSerializer(serializers.Serializer):
    new_email = serializers.EmailField(required=True)

    def validate_new_email(self, data):
        return data


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    new_password_repeat = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        return data


class APIKeySerializer(serializers.ModelSerializer):
    """
    Serializer for API keys
    """

    class Meta:
        model = APIKey
        fields = [
            "id",
            "name",
            "key",
            "is_active",
            "created_at",
            "expires_at",
            "last_used_at",
            "daily_limit",
            "daily_usage",
            "last_usage_date",
            "can_use_deepfake_detection",
            "can_use_ai_text_detection",
            "can_use_ai_media_detection",
        ]
        read_only_fields = ["id", "key", "created_at", "last_used_at", "daily_usage", "last_usage_date"]


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating API keys
    """

    class Meta:
        model = APIKey
        fields = ["name", "daily_limit", "expires_at", "can_use_deepfake_detection", "can_use_ai_text_detection", "can_use_ai_media_detection"]
