from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

# Import API key serializers
from api.models import APIKey
from app.models import Donation, UserData


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


class DonationSerializer(serializers.ModelSerializer):
    donor_username = serializers.SerializerMethodField()
    donor_email = serializers.EmailField(required=False)

    class Meta:
        model = Donation
        fields = ["id", "amount", "currency", "status", "created_at", "updated_at", "donor_name", "donor_email", "is_anonymous", "message", "donor_username"]
        read_only_fields = ["id", "stripe_payment_id", "stripe_checkout_id", "status", "created_at", "updated_at"]

    def get_donor_username(self, obj):
        if obj.user and not obj.is_anonymous:
            return obj.user.user.username
        return None


class DonationCreateSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    message = serializers.CharField(required=False, allow_blank=True)
    donor_name = serializers.CharField(required=False, allow_blank=True)
    donor_email = serializers.EmailField(required=False, allow_blank=True)
    is_anonymous = serializers.BooleanField(default=False)

    class Meta:
        model = Donation
        fields = ["amount", "currency", "donor_name", "donor_email", "is_anonymous", "message"]

    def validate(self, data):
        # If anonymous but no donor information, raise an error
        if data.get("is_anonymous") and not self.context.get("request").user.is_authenticated:
            if not data.get("donor_name") and not data.get("donor_email"):
                raise serializers.ValidationError("Anonymous donations must provide either a name or email.")
        return data
