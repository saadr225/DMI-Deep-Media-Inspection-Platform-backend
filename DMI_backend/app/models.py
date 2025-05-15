from django.db import models
from django.contrib.auth.models import User, Group
from django.contrib import admin
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils.translation import gettext_lazy as _


class UserData(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)
    profile_image_url = models.CharField(max_length=255, blank=True, null=True, default="/images/avatars/default.png")
    metadata = models.JSONField(default=dict, blank=True, null=True)

    def is_moderator(self):
        """Check if user is a moderator"""
        return self.user.groups.filter(name="PDA_Moderator").exists()

    def is_admin(self):
        """Check if user is an admin"""
        return self.user.is_staff or self.user.is_superuser

    def get_role(self):
        """Get the user's highest role"""
        if self.user.is_superuser:
            return "admin"
        elif self.user.is_staff:
            return "staff"
        elif self.is_moderator():
            return "moderator"
        elif self.is_verified:
            return "verified"
        else:
            return "user"

    def __str__(self):
        return f"{self.user.username}'s profile"


class PasswordResetToken(models.Model):
    user_data = models.OneToOneField(UserData, on_delete=models.CASCADE)
    reset_token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_data.user.username} - {self.reset_token}"


class ModeratorAction(models.Model):
    """
    Tracks all actions taken by moderators for auditing purposes
    """

    ACTION_TYPES = (
        ("approve", "Approve Content"),
        ("reject", "Reject Content"),
        ("delete", "Delete Content"),
        ("restore", "Restore Content"),
        ("edit", "Edit Content"),
        ("verify", "Verify User"),
        ("unverify", "Unverify User"),
        ("promote", "Promote User"),
        ("demote", "Demote User"),
        ("suspend", "Suspend User"),
        ("unsuspend", "Unsuspend User"),
        ("other", "Other Action"),
    )

    CONTENT_TYPES = (
        ("pda", "PDA Submission"),
        ("thread", "Forum Thread"),
        ("reply", "Forum Reply"),
        ("user", "User Account"),
        ("topic", "Forum Topic"),
        ("tag", "Forum Tag"),
        ("other", "Other Content"),
        ("donation", "Donation"),
    )

    moderator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="moderator_actions")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)

    # Generic foreign key to link to moderated content
    content_object_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    content_object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey("content_object_type", "content_object_id")

    content_identifier = models.CharField(max_length=255, help_text="Identifying information about the content")
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.moderator.username} {self.get_action_type_display()} on {self.content_identifier}"


class Donation(models.Model):
    """
    Model to track donations (demo implementation)
    """

    class DonationStatus(models.TextChoices):
        PENDING = "pending", _("Pending")
        COMPLETED = "completed", _("Completed")
        FAILED = "failed", _("Failed")
        REFUNDED = "refunded", _("Refunded")

    class DonationType(models.TextChoices):
        ONE_TIME = "one_time", _("One Time")
        MONTHLY = "monthly", _("Monthly")
        ANNUALLY = "annually", _("Annually")

    user = models.ForeignKey(UserData, on_delete=models.SET_NULL, null=True, blank=True, related_name="donations")
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in USD")
    currency = models.CharField(max_length=3, default="USD")
    payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    session_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=DonationStatus.choices, default=DonationStatus.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    donor_name = models.CharField(max_length=255, blank=True, null=True)
    donor_email = models.EmailField(blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)
    message = models.TextField(blank=True, null=True)

    # Additional fields for more complete donation data
    donation_type = models.CharField(max_length=20, choices=DonationType.choices, default=DonationType.ONE_TIME)
    project_allocation = models.CharField(max_length=100, blank=True, null=True, help_text="Specific project the donation is for")
    is_gift = models.BooleanField(default=False)
    gift_recipient_name = models.CharField(max_length=255, blank=True, null=True)
    gift_recipient_email = models.EmailField(blank=True, null=True)
    gift_message = models.TextField(blank=True, null=True)
    donor_address = models.TextField(blank=True, null=True)
    donor_phone = models.CharField(max_length=20, blank=True, null=True)
    donor_country = models.CharField(max_length=100, blank=True, null=True)
    payment_method_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of payment method used")

    # Credit card related fields (for demo purposes, following PCI compliance guidelines)
    card_number_last4 = models.CharField(max_length=4, blank=True, null=True, help_text="Last 4 digits of card number")
    card_expiry_month = models.CharField(max_length=2, blank=True, null=True, help_text="Card expiry month (MM)")
    card_expiry_year = models.CharField(max_length=4, blank=True, null=True, help_text="Card expiry year (YYYY)")
    card_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of card (Visa, Mastercard, etc.)")
    billing_city = models.CharField(max_length=100, blank=True, null=True, help_text="Billing address city")
    billing_postal_code = models.CharField(max_length=20, blank=True, null=True, help_text="Billing address postal/zip code")

    notes = models.TextField(blank=True, null=True, help_text="Administrative notes about this donation")

    # Fields for refunds
    refund_id = models.CharField(max_length=100, blank=True, null=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    refund_reason = models.TextField(blank=True, null=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.is_anonymous:
            return f"Anonymous donation of {self.amount} {self.currency} on {self.created_at.strftime('%Y-%m-%d')}"
        elif self.user:
            return f"Donation of {self.amount} {self.currency} by {self.user.user.username} on {self.created_at.strftime('%Y-%m-%d')}"
        else:
            return f"Donation of {self.amount} {self.currency} by {self.donor_name or 'unknown'} on {self.created_at.strftime('%Y-%m-%d')}"
