from rest_framework import serializers
from django.contrib.auth.models import User


# from django.contrib.auth import authenticate


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "password")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            # first_name=validated_data.get("first_name", ""), first_name and last_name are ignored for now
            # last_name=validated_data.get("last_name", ""),
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
            raise serializers.ValidationError("The 'is_email' flag is required.")

        if is_email and not email:
            raise serializers.ValidationError(
                "Email is required when is_email is True."
            )
        if not is_email and not username:
            raise serializers.ValidationError(
                "Username is required when is_email is False."
            )
        if not password:
            raise serializers.ValidationError("Password is required.")

        return data
