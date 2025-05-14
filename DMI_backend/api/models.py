import secrets
from django.db import models
from django.utils import timezone
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
    detection_result = models.OneToOneField(DeepfakeDetectionResult, on_delete=models.CASCADE, null=False, related_name="archive_submission")
    is_approved = models.BooleanField(default=False)  # For moderation purposes
    submission_date = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_submissions")
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
    pda_submission = models.ForeignKey(PublicDeepfakeArchive, on_delete=models.CASCADE, related_name="detected_faces")
    face_embedding = models.JSONField()  # Store face embedding vectors as JSON
    face_location = models.JSONField()  # Store bounding box coordinates
    frame_id = models.CharField(max_length=100, null=True)  # For videos, store frame ID
    detection_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["pda_submission"]),
        ]


class ForumTopic(models.Model):
    """Pre-defined topics for forum threads"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True)  # For displaying topic icon
    is_active = models.BooleanField(default=True)  # For disabling topics without deleting
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class ForumTag(models.Model):
    """Tags for forum threads"""

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=20, blank=True, null=True)  # For styling tags with colors
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ForumThread(models.Model):
    """Main forum discussion threads"""

    APPROVAL_STATUS = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="forum_threads")
    topic = models.ForeignKey(ForumTopic, on_delete=models.CASCADE, related_name="threads")
    tags = models.ManyToManyField(ForumTag, blank=True, related_name="threads")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(default=timezone.now)

    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS, default="pending")
    is_deleted = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)  # For pinning important threads
    is_locked = models.BooleanField(default=False)  # For preventing new replies

    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_threads")
    review_date = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, null=True)

    view_count = models.IntegerField(default=0)

    # Media attachment for thread
    media_url = models.CharField(max_length=255, blank=True, null=True)
    media_type = models.CharField(max_length=50, blank=True, null=True)  # image, video, document

    class Meta:
        ordering = ["-last_active"]
        indexes = [
            models.Index(fields=["approval_status", "is_deleted"]),
            models.Index(fields=["author"]),
            models.Index(fields=["topic"]),
            models.Index(fields=["is_pinned"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # If thread is being approved or rejected and has no review date, set it
        if self.approval_status in ["approved", "rejected"] and not self.review_date:
            self.review_date = timezone.now()
        super().save(*args, **kwargs)


class ForumReply(models.Model):
    """Replies to forum threads or other replies"""

    content = models.TextField()
    author = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="forum_replies")
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name="replies")
    parent_reply = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="child_replies")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_deleted = models.BooleanField(default=False)
    is_solution = models.BooleanField(default=False)  # Mark as solution to thread question

    # Media attachment for reply
    media_url = models.CharField(max_length=255, blank=True, null=True)
    media_type = models.CharField(max_length=50, blank=True, null=True)  # image, video, document

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "is_deleted"]),
            models.Index(fields=["parent_reply"]),
            models.Index(fields=["author"]),
            models.Index(fields=["is_solution"]),
        ]
        verbose_name_plural = "Forum replies"

    def __str__(self):
        return f"Reply by {self.author.user.username} on {self.created_at.strftime('%Y-%m-%d')}"


class ForumLike(models.Model):
    """Likes/upvotes/downvotes for threads and replies"""

    LIKE_TYPES = [
        ("like", "Like"),
        ("dislike", "Dislike"),
    ]

    user = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="forum_likes")
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, null=True, blank=True, related_name="likes")
    reply = models.ForeignKey(ForumReply, on_delete=models.CASCADE, null=True, blank=True, related_name="likes")
    like_type = models.CharField(max_length=10, choices=LIKE_TYPES, default="like")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(thread__isnull=False, reply__isnull=True) | models.Q(thread__isnull=True, reply__isnull=False)),
                name="like_either_thread_or_reply",
            ),
            models.UniqueConstraint(
                fields=["user", "thread", "like_type"],
                name="unique_thread_like_per_user",
                condition=models.Q(thread__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "reply", "like_type"],
                name="unique_reply_like_per_user",
                condition=models.Q(reply__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["thread", "like_type"]),
            models.Index(fields=["reply", "like_type"]),
        ]

    def __str__(self):
        action = "Dislike" if self.like_type == "dislike" else "Like"
        if self.thread:
            return f"{action} on thread by {self.user.user.username}"
        return f"{action} on reply by {self.user.user.username}"


class ForumReaction(models.Model):
    """Emoji reactions for threads and replies"""

    REACTION_TYPES = [
        ("👍", "Thumbs Up"),
        ("❤️", "Heart"),
        ("😂", "Laugh"),
        ("😮", "Wow"),
        ("😢", "Sad"),
        ("😡", "Angry"),
        ("🔥", "Fire"),
        ("👏", "Clap"),
        ("🧠", "Brain"),
    ]

    user = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="forum_reactions")
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, null=True, blank=True, related_name="reactions")
    reply = models.ForeignKey(ForumReply, on_delete=models.CASCADE, null=True, blank=True, related_name="reactions")
    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(models.Q(thread__isnull=False, reply__isnull=True) | models.Q(thread__isnull=True, reply__isnull=False)),
                name="reaction_either_thread_or_reply",
            ),
            models.UniqueConstraint(
                fields=["user", "thread", "reaction_type"],
                name="unique_thread_reaction_per_user",
                condition=models.Q(thread__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "reply", "reaction_type"],
                name="unique_reply_reaction_per_user",
                condition=models.Q(reply__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["thread", "reaction_type"]),
            models.Index(fields=["reply", "reaction_type"]),
        ]

    def __str__(self):
        target = f"thread {self.thread.id}" if self.thread else f"reply {self.reply.id}"
        return f"{self.user.user.username} - {self.reaction_type} on {target}"


class ForumAnalytics(models.Model):
    """Analytics for the forum"""

    total_threads = models.IntegerField(default=0)
    total_replies = models.IntegerField(default=0)
    total_likes = models.IntegerField(default=0)
    total_reactions = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)

    # Daily stats
    threads_today = models.IntegerField(default=0)
    replies_today = models.IntegerField(default=0)

    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Forum analytics"

    def __str__(self):
        return f"Forum Analytics - Last updated: {self.last_updated.strftime('%Y-%m-%d %H:%M')}"


class ForumNotification(models.Model):
    """Notifications for forum activities"""

    NOTIFICATION_TYPES = [
        ("reply", "New Reply"),
        ("like", "New Like"),
        ("reaction", "New Reaction"),
        ("mention", "Mention"),
        ("solution", "Solution Marked"),
    ]

    user = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="forum_notifications")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    content = models.TextField()

    # References to related content
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, null=True, blank=True)
    reply = models.ForeignKey(ForumReply, on_delete=models.CASCADE, null=True, blank=True)
    from_user = models.ForeignKey(UserData, on_delete=models.SET_NULL, null=True, related_name="sent_notifications")

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Notification for {self.user.user.username} - {self.notification_type}"


class KnowledgeBaseTopic(models.Model):
    """Topics for organizing knowledge base articles"""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, null=True)  # For displaying topic icon
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class KnowledgeBaseArticle(models.Model):
    """Main knowledge base article model"""

    title = models.CharField(max_length=200)
    content = models.TextField()
    banner_image = models.CharField(max_length=255, null=True, blank=True)
    author = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="knowledge_articles")
    topic = models.ForeignKey(KnowledgeBaseTopic, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_published = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class KnowledgeBaseAttachment(models.Model):
    """Files attached to knowledge base articles"""

    article = models.ForeignKey(KnowledgeBaseArticle, on_delete=models.CASCADE, related_name="attachments")
    filename = models.CharField(max_length=255)
    file_url = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # image, video, audio, pdf, document
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.file_type})"


class KnowledgeBaseStatistics(models.Model):
    """Statistics for knowledge base articles"""

    article = models.OneToOneField(KnowledgeBaseArticle, on_delete=models.CASCADE, related_name="statistics")
    view_count = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stats for {self.article.title}"


class APIKey(models.Model):
    """
    API Key model for authenticating external API users
    """

    # Key management fields
    key = models.CharField(max_length=64, unique=True, editable=False)
    user = models.ForeignKey(UserData, on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=100, help_text="A name to help you identify this API key")

    # Status fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    # Rate limiting and quota
    daily_limit = models.IntegerField(default=1000, help_text="Maximum number of requests per day")
    daily_usage = models.IntegerField(default=0, help_text="Current usage count for the day")
    last_usage_date = models.DateField(default=timezone.now)

    # Permission fields - What API services this key can access
    can_use_deepfake_detection = models.BooleanField(default=True)
    can_use_ai_text_detection = models.BooleanField(default=True)
    can_use_ai_media_detection = models.BooleanField(default=True)

    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self):
        return f"{self.name} ({self.user.user.username})"

    def save(self, *args, **kwargs):
        # Generate a new API key if it doesn't exist
        if not self.key:
            self.key = self.generate_key()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_key():
        """Generate a secure random API key"""
        return secrets.token_hex(32)

    def is_valid(self):
        """Check if the API key is valid and not expired"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def update_usage(self):
        """Update the usage counter for this API key"""
        today = timezone.now().date()

        # Reset counter if it's a new day
        if self.last_usage_date != today:
            self.daily_usage = 0
            self.last_usage_date = today

        # Increment usage counter
        self.daily_usage += 1
        self.last_used_at = timezone.now()
        self.save(update_fields=["daily_usage", "last_used_at", "last_usage_date"])

        # Check if limit has been exceeded
        return self.daily_usage <= self.daily_limit


class APIUsageLog(models.Model):
    """
    Log of API usage for analytics and monitoring
    """

    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name="usage_logs")
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)  # GET, POST, etc.
    status_code = models.IntegerField()
    response_time = models.FloatField(help_text="Response time in seconds")
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "API Usage Log"
        verbose_name_plural = "API Usage Logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.api_key} - {self.endpoint} ({self.status_code})"
