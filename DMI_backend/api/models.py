from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from app.models import UserData
from django.utils import timezone


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


class TextSubmission(models.Model):
    """Model for text submissions that need to be analyzed for AI generation"""

    user = models.ForeignKey(UserData, on_delete=models.CASCADE)
    text_content = models.TextField(blank=False)
    submission_identifier = models.CharField(max_length=128, blank=False)
    purpose = models.CharField(max_length=32, default="AI-Text-Analysis", blank=False)
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.user.username} - Text Submission ({len(self.text_content)} chars) - {self.upload_date}"


class AIGeneratedTextResult(models.Model):
    """Model to store results of AI-generated text detection"""

    text_submission = models.ForeignKey(TextSubmission, on_delete=models.CASCADE)
    is_ai_generated = models.BooleanField(blank=False)  # True if text is AI generated
    source_prediction = models.CharField(max_length=32, blank=False)  # "Human", "GPT-3", "Claude"
    confidence_scores = models.JSONField(blank=False)  # Store confidence for each class
    highlighted_text = models.TextField(blank=True)  # Text with AI parts highlighted
    html_text = models.TextField(blank=True)  # HTML version with highlighting
    analysis_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.text_submission.user.user.username} - {self.source_prediction} - {self.analysis_date}"


DEEPFAKE_CATEGORIES = [
    ("POL", "Politician"),
    ("CEL", "Celebrity"),
    ("INF", "Influencer"),
    ("PUB", "Public Figure"),
    ("OTH", "Other"),
]


class PublicDeepfakeArchive(models.Model):
    user = models.ForeignKey(UserData, on_delete=models.CASCADE)
    file = models.FileField(upload_to="pda_submissions/", max_length=512)
    original_filename = models.CharField(max_length=256)
    submission_identifier = models.CharField(max_length=256, unique=True)
    file_type = models.CharField(max_length=50)  # Image or Video
    title = models.CharField(max_length=256)
    description = models.TextField(blank=True, null=True, max_length=1024)
    category = models.CharField(max_length=3, choices=DEEPFAKE_CATEGORIES)
    context = models.TextField(blank=True, null=True, max_length=256)
    source_url = models.URLField(blank=True, null=True)
    detection_result = models.OneToOneField(
        DeepfakeDetectionResult, on_delete=models.CASCADE, null=False, related_name="archive_submission"
    )
    is_approved = models.BooleanField(default=False)  # For moderation purposes
    submission_date = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_submissions"
    )
    review_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        if self.is_approved and not self.review_date:
            self.review_date = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.submission_date}"


class FacialWatchRegistration(models.Model):
    user = models.ForeignKey(UserData, on_delete=models.CASCADE)
    face_embedding = models.JSONField()  # Store face embedding vectors as JSON
    registration_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]


class FacialWatchMatch(models.Model):
    user = models.ForeignKey(UserData, on_delete=models.CASCADE)
    pda_submission = models.ForeignKey(PublicDeepfakeArchive, on_delete=models.SET_NULL, null=True)
    pda_submission_identifier = models.CharField(max_length=256, blank=False)
    match_confidence = models.FloatField()
    face_location = models.JSONField(null=True)  # Store bounding box coordinates
    match_date = models.DateTimeField(auto_now_add=True)
    notification_sent = models.BooleanField(default=False)


class PDASubmissionProfiledFace(models.Model):
    pda_submission = models.ForeignKey(
        PublicDeepfakeArchive, on_delete=models.CASCADE, related_name="detected_faces"
    )
    face_embedding = models.JSONField()  # Store face embedding vectors as JSON
    face_location = models.JSONField()  # Store bounding box coordinates
    frame_id = models.CharField(max_length=100, null=True)  # For videos, store frame ID
    detection_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["pda_submission"]),
        ]


# class CommunityFeedback(models.Model):
#     media = models.ForeignKey(MediaUpload, on_delete=models.CASCADE)
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     feedback = models.TextField()
#     feedback_date = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.user.username} - {self.media.file.name}"
