from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from app.models import UserData


class MediaUpload(models.Model):
    user = models.ForeignKey(UserData, on_delete=models.CASCADE)
    # file = models.FileField(upload_to=f"{settings.MEDIA_ROOT}/submissions", max_length=512)
    file = models.FileField(upload_to=f"submissions/", max_length=512)
    original_filename = models.CharField(max_length=256, blank=False)
    submission_identifier = models.CharField(max_length=128, blank=False)
    file_identifier = models.CharField(max_length=128, blank=False)
    file_type = models.CharField(max_length=32, default="Video")
    purpose = models.CharField(max_length=32, default="Deepfake-Analaysis", blank=False)
    upload_date = models.DateTimeField(auto_now_add=True)
    # description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.file.name} - {self.upload_date}"


class MediaUploadMetadata(models.Model):
    media_upload = models.ForeignKey(MediaUpload, on_delete=models.CASCADE)
    metadata = models.JSONField()
    analysis_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.media.file.name} - {self.analysis_date}"


class DeepfakeDetectionResult(models.Model):
    media_upload = models.ForeignKey(MediaUpload, on_delete=models.CASCADE)
    is_deepfake = models.BooleanField(blank=True)
    confidence_score = models.FloatField(blank=True)
    frames_analyzed = models.IntegerField(blank=True)
    fake_frames = models.IntegerField(blank=True)
    analysis_date = models.DateTimeField(auto_now_add=True)
    analysis_report = models.JSONField(blank=True)

    def __str__(self):
        return f"{self.media.file.name} - {self.analysis_date}"


class AIGeneratedMediaResult(models.Model):
    media_upload = models.ForeignKey(MediaUpload, on_delete=models.CASCADE)
    is_generated = models.BooleanField()
    confidence_score = models.FloatField()
    analysis_report = models.JSONField()
    analysis_date = models.DateTimeField(auto_now_add=True)


# class CommunityFeedback(models.Model):
#     media = models.ForeignKey(MediaUpload, on_delete=models.CASCADE)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     feedback = models.TextField()
#     feedback_date = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user.username} - {self.media.file.name}"
