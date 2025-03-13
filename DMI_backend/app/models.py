from django.db import models
from django.contrib.auth.models import User
from django.contrib import admin


class UserData(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)


class PasswordResetToken(models.Model):
    user_data = models.OneToOneField(UserData, on_delete=models.CASCADE)
    reset_token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.reset_token}"
