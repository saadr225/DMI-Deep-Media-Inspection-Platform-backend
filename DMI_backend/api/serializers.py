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
        fields = [
            "id",
            "amount",
            "currency",
            "status",
            "created_at",
            "updated_at",
            "donor_name",
            "donor_email",
            "is_anonymous",
            "message",
            "donor_username",
            "donation_type",
            "project_allocation",
            "is_gift",
            "gift_recipient_name",
            "gift_recipient_email",
            "gift_message",
            "donor_address",
            "donor_phone",
            "donor_country",
            "payment_method_type",
            "card_number_last4",
            "card_expiry_month",
            "card_expiry_year",
            "card_type",
            "billing_city",
            "billing_postal_code",
            "notes",
            "refund_id",
            "refunded_at",
            "refund_reason",
            "refunded_amount",
        ]
        read_only_fields = ["id", "payment_id", "session_id", "status", "created_at", "updated_at", "refund_id", "refunded_at"]

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

    # New fields
    donation_type = serializers.ChoiceField(choices=Donation.DonationType.choices, default=Donation.DonationType.ONE_TIME)
    project_allocation = serializers.CharField(required=False, allow_blank=True)
    is_gift = serializers.BooleanField(default=False)
    gift_recipient_name = serializers.CharField(required=False, allow_blank=True)
    gift_recipient_email = serializers.EmailField(required=False, allow_blank=True)
    gift_message = serializers.CharField(required=False, allow_blank=True)
    donor_address = serializers.CharField(required=False, allow_blank=True)
    donor_phone = serializers.CharField(required=False, allow_blank=True)
    donor_country = serializers.CharField(required=False, allow_blank=True)

    # Credit card fields
    card_number = serializers.CharField(required=False, write_only=True, allow_blank=True)  # Full number - write only, not stored
    card_expiry_month = serializers.CharField(required=False, allow_blank=True)
    card_expiry_year = serializers.CharField(required=False, allow_blank=True)
    card_cvc = serializers.CharField(required=False, write_only=True, allow_blank=True)  # Write only, not stored
    card_type = serializers.CharField(required=False, allow_blank=True)
    billing_city = serializers.CharField(required=False, allow_blank=True)
    billing_postal_code = serializers.CharField(required=False, allow_blank=True)

    payment_method_type = serializers.CharField(required=False, default="credit_card", allow_blank=True)

    class Meta:
        model = Donation
        fields = [
            "amount",
            "currency",
            "donor_name",
            "donor_email",
            "is_anonymous",
            "message",
            "donation_type",
            "project_allocation",
            "is_gift",
            "gift_recipient_name",
            "gift_recipient_email",
            "gift_message",
            "donor_address",
            "donor_phone",
            "donor_country",
            "payment_method_type",
            "card_number",
            "card_expiry_month",
            "card_expiry_year",
            "card_cvc",
            "card_type",
            "billing_city",
            "billing_postal_code",
        ]

    def validate(self, data):
        # If anonymous but no donor information, raise an error
        if data.get("is_anonymous") and not self.context.get("request").user.is_authenticated:
            if not data.get("donor_name") and not data.get("donor_email"):
                raise serializers.ValidationError("Anonymous donations must provide either a name or email.")

        # If this is a gift, both recipient name and email are required
        if data.get("is_gift"):
            if not data.get("gift_recipient_name") or not data.get("gift_recipient_email"):
                raise serializers.ValidationError("Gift donations require recipient name and email.")

        # Validate credit card details if payment_method_type is credit_card
        if data.get("payment_method_type") == "credit_card":
            # Check cardholder name (using donor_name)
            if not data.get("donor_name"):
                raise serializers.ValidationError({"donor_name": "Cardholder name is required for credit card payments."})

            card_number = data.get("card_number", "")
            if not card_number:
                raise serializers.ValidationError({"card_number": "Card number is required for credit card payments."})

            # Simple validation - in real app this would be more robust
            if not card_number.isdigit() or not (12 <= len(card_number) <= 19):
                raise serializers.ValidationError({"card_number": "Invalid card number format."})

            # Test cards validation - allow the test card number
            # For demo purposes, accept 4111 1111 1111 1111 as valid
            test_card = "4111111111111111"
            if card_number != test_card and not self._is_valid_card_number(card_number):
                raise serializers.ValidationError({"card_number": "Invalid card number. For testing, use 4111 1111 1111 1111."})

            # Check expiry date
            if not data.get("card_expiry_month"):
                raise serializers.ValidationError({"card_expiry_month": "Expiry month is required."})

            if not data.get("card_expiry_year"):
                raise serializers.ValidationError({"card_expiry_year": "Expiry year is required."})

            # Validate expiry month format (01-12)
            try:
                month = int(data.get("card_expiry_month", "0"))
                if not (1 <= month <= 12):
                    raise serializers.ValidationError({"card_expiry_month": "Expiry month must be between 01 and 12."})
            except ValueError:
                raise serializers.ValidationError({"card_expiry_month": "Expiry month must be a number."})

            # Check CVC
            if not data.get("card_cvc"):
                raise serializers.ValidationError({"card_cvc": "Security code (CVC) is required."})

            # Validate CVC format (3-4 digits)
            cvc = data.get("card_cvc", "")
            if not cvc.isdigit() or not (3 <= len(cvc) <= 4):
                raise serializers.ValidationError({"card_cvc": "Security code (CVC) must be 3-4 digits."})

            # Check required billing information
            if not data.get("donor_address"):
                raise serializers.ValidationError({"donor_address": "Billing address is required for credit card payments."})

            if not data.get("billing_city"):
                raise serializers.ValidationError({"billing_city": "Billing city is required for credit card payments."})

            if not data.get("billing_postal_code"):
                raise serializers.ValidationError({"billing_postal_code": "Postal/zip code is required for credit card payments."})

            if not data.get("donor_country"):
                raise serializers.ValidationError({"donor_country": "Country is required for credit card payments."})

            # Determine card type (simplified logic)
            if not data.get("card_type"):
                if card_number.startswith("4"):
                    data["card_type"] = "Visa"
                elif card_number.startswith(("51", "52", "53", "54", "55")):
                    data["card_type"] = "MasterCard"
                elif card_number.startswith("34") or card_number.startswith("37"):
                    data["card_type"] = "American Express"
                else:
                    data["card_type"] = "Unknown"

        return data

    def _is_valid_card_number(self, card_number):

        return True
