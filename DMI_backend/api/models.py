from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from app.models import UserData


class MediaUpload(models.Model):
    user = models.ForeignKey(UserData, on_delete=models.CASCADE)
    # file = models.FileField(upload_to=f"{settings.MEDIA_ROOT}/submissions", max_length=512)
    file = models.FileField(upload_to=f"submissions/", max_length=512)

    file_type = models.CharField(max_length=32, default="Video")
    upload_date = models.DateTimeField(auto_now_add=True)
    # description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.file.name} - {self.upload_date}"


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


# class CommunityFeedback(models.Model):
#     media = models.ForeignKey(MediaUpload, on_delete=models.CASCADE)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     feedback = models.TextField()
#     feedback_date = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user.username} - {self.media.file.name}"
