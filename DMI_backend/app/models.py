from django.db import models
from django.contrib.auth.models import User, Group
from django.contrib import admin


class UserData(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)

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


class PasswordResetToken(models.Model):
    user_data = models.OneToOneField(UserData, on_delete=models.CASCADE)
    reset_token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_data.user.username} - {self.reset_token}"
