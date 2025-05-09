from django.db import models
from django.contrib.auth.models import User, Group
from django.contrib import admin
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class UserData(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)
    profile_image_url = models.CharField(max_length=255, blank=True, null=True, default="/images/avatars/default.png")

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
        ('approve', 'Approve Content'),
        ('reject', 'Reject Content'),
        ('delete', 'Delete Content'),
        ('restore', 'Restore Content'),
        ('edit', 'Edit Content'),
        ('verify', 'Verify User'),
        ('unverify', 'Unverify User'),
        ('promote', 'Promote User'),
        ('demote', 'Demote User'),
        ('suspend', 'Suspend User'),
        ('unsuspend', 'Unsuspend User'),
        ('other', 'Other Action'),
    )
    
    CONTENT_TYPES = (
        ('pda', 'PDA Submission'),
        ('thread', 'Forum Thread'),
        ('reply', 'Forum Reply'),
        ('user', 'User Account'),
        ('topic', 'Forum Topic'),
        ('tag', 'Forum Tag'),
        ('other', 'Other Content'),
    )
    
    moderator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='moderator_actions')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    
    # Generic foreign key to link to moderated content
    content_object_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    content_object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_object_type', 'content_object_id')
    
    content_identifier = models.CharField(max_length=255, help_text="Identifying information about the content")
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.moderator.username} {self.get_action_type_display()} on {self.content_identifier}"
