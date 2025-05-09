from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User, Group
from django.contrib.admin.sites import AdminSite
from api.models import (
    PublicDeepfakeArchive,
    UserData,
    DeepfakeDetectionResult,
    ForumThread,
    ForumReply,
    ForumTopic,
    ForumTag,
    ForumAnalytics,
    ForumReaction,
)
from app.controllers.HelpersController import URLHelper
from app.controllers import CommunityForumController
from datetime import datetime, timedelta
from django.db.models import Q, Count, Sum
from django.urls import path, reverse
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render, redirect
from django.template.response import TemplateResponse


# Custom AdminSite for better dashboard and organization
class PDAAdminSite(AdminSite):
    site_header = "Deepfake Archive Administration"
    site_title = "PDA Admin/Moderation Portal"
    index_title = "Welcome to PDA Admin/Moderation Portal"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "forum-analytics/",
                self.admin_view(ForumAnalyticsDashboardView.as_view()),
                name="forum-analytics",
            ),
            path(
                "make-moderator/<int:user_id>/",
                self.admin_view(self.make_moderator_view),
                name="make-moderator",
            ),
            path(
                "remove-moderator/<int:user_id>/",
                self.admin_view(self.remove_moderator_view),
                name="remove-moderator",
            ),
        ]
        return custom_urls + urls

    def make_moderator_view(self, request, user_id):
        user = User.objects.get(id=user_id)
        moderator_group, created = Group.objects.get_or_create(name="PDA_Moderator")
        if not user.groups.filter(name="PDA_Moderator").exists():
            user.groups.add(moderator_group)
            self.message_user(request, f"User {user.username} was successfully made a moderator.")
        return redirect("admin:auth_user_change", user_id)

    def remove_moderator_view(self, request, user_id):
        user = User.objects.get(id=user_id)
        moderator_group = Group.objects.get(name="PDA_Moderator")
        if user.groups.filter(name="PDA_Moderator").exists():
            user.groups.remove(moderator_group)
            self.message_user(request, f"Moderator status removed from {user.username}.")
        return redirect("admin:auth_user_change", user_id)

    def index(self, request, extra_context=None):
        # Get overall stats
        pda_pending_count = PublicDeepfakeArchive.objects.filter(review_date__isnull=True).count()
        forum_pending_count = ForumThread.objects.filter(approval_status="pending").count()
        user_count = UserData.objects.count()
        verified_user_count = UserData.objects.filter(is_verified=True).count()

        # Recent activity
        recent_pda_submissions = PublicDeepfakeArchive.objects.order_by("-submission_date")[:5]
        recent_forum_threads = ForumThread.objects.filter(is_deleted=False).order_by("-created_at")[:5]

        # Most active users (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        active_users = (
            UserData.objects.annotate(
                activity_count=Count(
                    "forumthread", filter=Q(forumthread__created_at__gte=seven_days_ago)
                )
                + Count("forumreply", filter=Q(forumreply__created_at__gte=seven_days_ago))
            )
            .filter(activity_count__gt=0)
            .order_by("-activity_count")[:5]
        )

        extra_context = extra_context or {}
        extra_context.update(
            {
                "pda_pending_count": pda_pending_count,
                "forum_pending_count": forum_pending_count,
                "user_count": user_count,
                "verified_user_count": verified_user_count,
                "recent_pda_submissions": recent_pda_submissions,
                "recent_forum_threads": recent_forum_threads,
                "active_users": active_users,
            }
        )

        return super().index(request, extra_context=extra_context)


# Create an instance of our custom admin site
pda_admin_site = PDAAdminSite(name="pda_admin")

# Replace the default admin site
admin.site = pda_admin_site


# Rest of your admin classes...
class PublicDeepfakeArchiveAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "submission_date",
        "is_approved",
        "approval_status",
        "preview",
        "deepfake_status",
    )
    list_filter = ("is_approved", "category", "submission_date", "reviewed_by")
    search_fields = ("title", "description", "submission_identifier")
    readonly_fields = (
        "submission_identifier",
        "submission_date",
        "file_preview",
        "original_filename",
        "file_type",
        "detection_result_display",
        "title",
        "category",
        "description",
        "context",
        "source_url",
        "reviewed_by",
        "review_date",
    )

    fieldsets = (
        (
            "Review Decision",
            {"fields": ("is_approved", "review_notes"), "classes": ("wide",)},
        ),
        (
            "Submission Details",
            {
                "fields": (
                    "title",
                    "category",
                    "description",
                    "context",
                    "source_url",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "File Information",
            {
                "fields": (
                    "submission_identifier",
                    "original_filename",
                    "file_type",
                    "submission_date",
                    "file_preview",
                ),
                "classes": ("collapse",),
            },
        ),
        ("Detection Results", {"fields": ("detection_result_display",), "classes": ("collapse",)}),
        (
            "Review Information",
            {
                "fields": ("reviewed_by", "review_date"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Override save_model to automatically set reviewer information"""
        if change:  # Only when editing existing objects
            obj.reviewed_by = request.user
            obj.review_date = datetime.now()
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Ensure certain fields are always readonly"""
        return self.readonly_fields

    def has_add_permission(self, request):
        """Disable ability to add new submissions through admin"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable ability to delete submissions"""
        return False

    def get_queryset(self, request):
        """Only show submissions that haven't been reviewed yet or were reviewed by the current user"""
        qs = super().get_queryset(request)
        if not request.user.is_superuser:  # For moderators
            return qs.filter(
                Q(reviewed_by__isnull=True)  # Not reviewed yet
                | Q(reviewed_by=request.user)  # Or reviewed by current user
            )
        return qs  # Superusers can see all

    def approval_status(self, obj):
        """Display approval status with colored formatting"""
        if obj.is_approved:
            return format_html('<span style="color: green; font-weight: bold;">Approved</span>')
        elif obj.review_date:  # If reviewed but not approved, it was rejected
            return format_html('<span style="color: red; font-weight: bold;">Rejected</span>')
        return format_html('<span style="color: orange; font-weight: bold;">Pending</span>')

    approval_status.short_description = "Status"

    def preview(self, obj):
        """Display a small thumbnail preview in the list view"""
        if obj.file:
            file_url = URLHelper.convert_to_public_url(file_path=obj.file.path)
            if obj.file_type == "Image":
                return format_html('<img src="{}" width="50" height="auto" />', file_url)
            elif obj.file_type == "Video":
                return format_html(
                    '<video width="50" height="auto" controls><source src="{}"></video>', file_url
                )
        return "No preview"

    preview.short_description = "Preview"

    def file_preview(self, obj):
        """Display a larger preview in the detail view"""
        if obj.file:
            file_url = URLHelper.convert_to_public_url(file_path=obj.file.path)
            if obj.file_type == "Image":
                return format_html('<img src="{}" width="400" height="auto" />', file_url)
            elif obj.file_type == "Video":
                return format_html(
                    '<video width="400" height="auto" controls><source src="{}"></video>', file_url
                )
        return "No preview available"

    file_preview.short_description = "File Preview"

    def approve_submissions(self, request, queryset):
        """Approve selected submissions"""
        count = 0
        for submission in queryset:
            submission.is_approved = True
            submission.reviewed_by = request.user
            submission.review_date = datetime.now()
            submission.save()
            count += 1

        if count == 1:
            message = "1 submission was"
        else:
            message = f"{count} submissions were"
        self.message_user(request, f"{message} successfully approved.")

    approve_submissions.short_description = "Approve selected submissions"

    def reject_submissions(self, request, queryset):
        """Reject selected submissions"""
        count = 0
        for submission in queryset:
            submission.is_approved = False
            submission.reviewed_by = request.user
            submission.review_date = datetime.now()
            submission.save()
            count += 1

        if count == 1:
            message = "1 submission was"
        else:
            message = f"{count} submissions were"
        self.message_user(request, f"{message} rejected.")

    reject_submissions.short_description = "Reject selected submissions"

    def deepfake_status(self, obj):
        """Display deepfake detection status with colored formatting"""
        if obj.detection_result:
            if obj.detection_result.is_deepfake:
                return format_html('<span style="color: red; font-weight: bold;">Deepfake</span>')
            return format_html('<span style="color: green; font-weight: bold;">Real</span>')
        return format_html('<span style="color: gray;">No Results</span>')

    deepfake_status.short_description = "Deepfake Status"

    def detection_result_display(self, obj):
        """Display detailed detection results with visualizations"""
        if not obj.detection_result:
            return "No detection results available"

        result = obj.detection_result

        # Create base info
        html = format_html(
            '<div style="padding: 10px; background-color: #f8f9fa; border-radius: 5px;">'
            '<h3 style="margin-top: 0;">Detection Summary</h3>'
            '<p><strong>Is Deepfake:</strong> <span style="color: {}; font-weight: bold;">{}</span></p>'
            "<p><strong>Confidence Score:</strong> {:.2f}%</p>"
            "<p><strong>Frames Analyzed:</strong> {}</p>"
            "<p><strong>Fake Frames:</strong> {} ({:.1f}%)</p>"
            "<p><strong>Analysis Date:</strong> {}</p>",
            "red" if result.is_deepfake else "green",
            "Yes" if result.is_deepfake else "No",
            result.confidence_score * 100,
            result.frames_analyzed,
            result.fake_frames,
            (result.fake_frames / result.frames_analyzed * 100) if result.frames_analyzed > 0 else 0,
            result.analysis_date.strftime("%B %d, %Y, %H:%M:%S"),
        )

        # Add visualization links if available in the JSON report
        if result.analysis_report and isinstance(result.analysis_report, dict):
            # Check if we have frame results to display
            if "frame_results" in result.analysis_report and result.analysis_report["frame_results"]:
                html += format_html(
                    '<h3>Frame Analysis</h3><div style="display: flex; flex-wrap: wrap; gap: 10px;">'
                )

                # Show only first 5 frames to avoid cluttering
                max_frames = min(5, len(result.analysis_report["frame_results"]))

                for i in range(max_frames):
                    frame = result.analysis_report["frame_results"][i]
                    if "frame_path" in frame and "gradcam_path" in frame:
                        frame_path = frame["frame_path"]
                        gradcam_path = frame["gradcam_path"]

                        html += format_html(
                            '<div style="text-align: center; margin-right: 10px;">'
                            "<p>Frame {}</p>"
                            '<div style="display: flex;">'
                            '<div style="margin-right: 5px;"><img src="{}" width="150" height="auto" /><br>Original</div>'
                            '<div><img src="{}" width="150" height="auto" /><br>GradCAM</div>'
                            "</div>"
                            '<p>Verdict: <span style="color: {}; font-weight: bold;">{}</span></p>'
                            "</div>",
                            i,
                            frame_path,
                            gradcam_path,
                            "red" if frame.get("final_verdict") == "fake" else "green",
                            frame.get("final_verdict", "unknown"),
                        )

                html += format_html("</div>")

                if len(result.analysis_report["frame_results"]) > max_frames:
                    html += format_html(
                        "<p>Showing first {} of {} frames...</p>",
                        max_frames,
                        len(result.analysis_report["frame_results"]),
                    )

        html += format_html("</div>")
        return html

    detection_result_display.short_description = "Detection Results"


class UserDataAdmin(admin.ModelAdmin):
    list_display = ("user", "is_verified")
    search_fields = ("user__username", "user__email")


class CustomUserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_moderator")
    list_filter = ("is_staff", "is_superuser", "groups")
    actions = ["make_moderator", "remove_moderator"]

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Moderation",
            {
                "fields": ("moderator_actions",),
            },
        ),
    )
    readonly_fields = ("moderator_actions",)

    def is_moderator(self, obj):
        return obj.groups.filter(name="PDA_Moderator").exists()

    is_moderator.boolean = True
    is_moderator.short_description = "Moderator"

    def moderator_actions(self, obj):
        if obj.pk:
            is_mod = obj.groups.filter(name="PDA_Moderator").exists()
            if is_mod:
                return format_html(
                    '<a class="button" href="{}">Remove Moderator Status</a>',
                    reverse("admin:remove-moderator", args=[obj.pk]),
                )
            else:
                return format_html(
                    '<a class="button default" style="background:#417690;color:white" href="{}">Make Moderator</a>',
                    reverse("admin:make-moderator", args=[obj.pk]),
                )
        return "Save the user first to manage moderator status"

    def make_moderator(self, request, queryset):
        moderator_group, created = Group.objects.get_or_create(name="PDA_Moderator")
        count = 0
        for user in queryset:
            if not user.groups.filter(name="PDA_Moderator").exists():
                user.groups.add(moderator_group)
                count += 1
        if count == 1:
            message = "1 user was"
        else:
            message = f"{count} users were"
        self.message_user(request, f"{message} successfully made moderators.")

    make_moderator.short_description = "Make selected users moderators"

    def remove_moderator(self, request, queryset):
        moderator_group = Group.objects.get(name="PDA_Moderator")
        count = 0
        for user in queryset:
            if user.groups.filter(name="PDA_Moderator").exists():
                user.groups.remove(moderator_group)
                count += 1
        if count == 1:
            message = "1 user was"
        else:
            message = f"{count} users were"
        self.message_user(request, f"Moderator status removed from {message}.")

    remove_moderator.short_description = "Remove moderator status from selected users"


# Forum-related admin classes
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "topic",
        "created_at",
        "approval_status",
        "is_deleted",
        "view_count",
        "reply_count",
        "like_count",
    )
    list_filter = ("approval_status", "topic", "is_deleted", "created_at")
    search_fields = ("title", "content", "author__user__username")
    actions = ["approve_threads", "reject_threads", "delete_threads"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            reply_count=Count("replies", filter=Q(replies__is_deleted=False)), like_count=Count("likes")
        )
        return qs

    def reply_count(self, obj):
        return obj.reply_count

    def like_count(self, obj):
        return obj.like_count

    reply_count.admin_order_field = "reply_count"
    like_count.admin_order_field = "like_count"

    def approve_threads(self, request, queryset):
        count = 0
        for thread in queryset.filter(approval_status="pending"):
            thread.approval_status = "approved"
            thread.save()
            count += 1

            # Send email notification
            try:
                send_mail(
                    subject="Your forum thread has been approved",
                    message=f"Hello {thread.author.user.username},\n\n"
                    f"Your thread '{thread.title}' has been approved and is now visible on the forum.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[thread.author.user.email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log the error but continue processing
                print(f"Failed to send approval email: {e}")

        if count == 1:
            message = "1 thread was"
        else:
            message = f"{count} threads were"
        self.message_user(request, f"{message} successfully approved.")

    approve_threads.short_description = "Approve selected threads"

    def reject_threads(self, request, queryset):
        count = 0
        for thread in queryset.filter(approval_status="pending"):
            thread.approval_status = "rejected"
            thread.save()
            count += 1

            # Send email notification
            try:
                send_mail(
                    subject="Your forum thread was not approved",
                    message=f"Hello {thread.author.user.username},\n\n"
                    f"We regret to inform you that your thread '{thread.title}' "
                    f"was not approved. Please review our community guidelines.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[thread.author.user.email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log the error but continue processing
                print(f"Failed to send rejection email: {e}")

        if count == 1:
            message = "1 thread was"
        else:
            message = f"{count} threads were"
        self.message_user(request, f"{message} rejected.")

    reject_threads.short_description = "Reject selected threads"

    def delete_threads(self, request, queryset):
        count = 0
        for thread in queryset:
            thread.is_deleted = True
            thread.save()
            count += 1

        if count == 1:
            message = "1 thread was"
        else:
            message = f"{count} threads were"
        self.message_user(request, f"{message} marked as deleted.")

    delete_threads.short_description = "Mark selected threads as deleted"


class ForumReplyAdmin(admin.ModelAdmin):
    list_display = ("get_content_preview", "author", "thread", "created_at", "is_deleted")
    list_filter = ("is_deleted", "created_at")
    search_fields = ("content", "author__user__username", "thread__title")
    actions = ["delete_replies", "restore_replies"]

    def get_content_preview(self, obj):
        if len(obj.content) > 50:
            return f"{obj.content[:50]}..."
        return obj.content

    get_content_preview.short_description = "Content"

    def delete_replies(self, request, queryset):
        count = queryset.update(is_deleted=True)
        if count == 1:
            message = "1 reply was"
        else:
            message = f"{count} replies were"
        self.message_user(request, f"{message} marked as deleted.")

    delete_replies.short_description = "Mark selected replies as deleted"

    def restore_replies(self, request, queryset):
        count = queryset.update(is_deleted=False)
        if count == 1:
            message = "1 reply was"
        else:
            message = f"{count} replies were"
        self.message_user(request, f"{message} restored.")

    restore_replies.short_description = "Restore selected replies"


class ForumTopicAdmin(admin.ModelAdmin):
    list_display = ("name", "thread_count", "created_at")
    search_fields = ("name", "description")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(thread_count=Count("forumthread", filter=Q(forumthread__is_deleted=False)))
        return qs

    def thread_count(self, obj):
        return obj.thread_count

    thread_count.admin_order_field = "thread_count"
    thread_count.short_description = "Thread Count"


class ForumTagAdmin(admin.ModelAdmin):
    list_display = ("name", "thread_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(thread_count=Count("forumthread", filter=Q(forumthread__is_deleted=False)))
        return qs

    def thread_count(self, obj):
        return obj.thread_count

    thread_count.admin_order_field = "thread_count"
    thread_count.short_description = "Thread Count"


class ForumAnalyticsAdmin(admin.ModelAdmin):
    list_display = ("total_threads", "total_replies", "total_likes", "last_updated")
    readonly_fields = (
        "total_threads",
        "total_replies",
        "total_likes",
        "last_updated",
        "get_analytics_dashboard",
    )

    def has_add_permission(self, request):
        # Only one analytics record should exist
        return ForumAnalytics.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of analytics record
        return False

    def get_analytics_dashboard(self, obj):
        """Display comprehensive analytics dashboard"""
        # Get recent activity (last 30 days)
        today = timezone.now()
        thirty_days_ago = today - timedelta(days=30)

        # Count recent threads and replies
        recent_threads = ForumThread.objects.filter(
            created_at__gte=thirty_days_ago, is_deleted=False
        ).count()

        recent_replies = ForumReply.objects.filter(
            created_at__gte=thirty_days_ago, is_deleted=False
        ).count()

        # Most active users
        active_users = (
            UserData.objects.annotate(
                total_activity=Count(
                    "forumthread", filter=Q(forumthread__created_at__gte=thirty_days_ago)
                )
                + Count("forumreply", filter=Q(forumreply__created_at__gte=thirty_days_ago))
            )
            .filter(total_activity__gt=0)
            .order_by("-total_activity")[:5]
        )

        # Popular topics
        popular_topics = (
            ForumTopic.objects.annotate(
                recent_threads=Count(
                    "forumthread",
                    filter=Q(
                        forumthread__created_at__gte=thirty_days_ago, forumthread__is_deleted=False
                    ),
                )
            )
            .filter(recent_threads__gt=0)
            .order_by("-recent_threads")[:5]
        )

        # Create HTML dashboard
        html = format_html(
            '<div style="padding: 15px; background-color: #f5f5f5; border-radius: 5px;">'
        )

        # Summary section
        html += format_html(
            "<h2>Forum Analytics Dashboard</h2>"
            '<div style="display: flex; justify-content: space-between; margin-bottom: 20px;">'
            '<div style="background-color: #dff0d8; padding: 15px; border-radius: 5px; width: 30%;">'
            "<h3>Total Threads</h3>"
            '<p style="font-size: 24px; font-weight: bold;">{}</p>'
            "<p>Last 30 days: {}</p>"
            "</div>"
            '<div style="background-color: #d9edf7; padding: 15px; border-radius: 5px; width: 30%;">'
            "<h3>Total Replies</h3>"
            '<p style="font-size: 24px; font-weight: bold;">{}</p>'
            "<p>Last 30 days: {}</p>"
            "</div>"
            '<div style="background-color: #fcf8e3; padding: 15px; border-radius: 5px; width: 30%;">'
            "<h3>Total Likes</h3>"
            '<p style="font-size: 24px; font-weight: bold;">{}</p>'
            "</div>"
            "</div>",
            obj.total_threads,
            recent_threads,
            obj.total_replies,
            recent_replies,
            obj.total_likes,
        )

        # Most active users
        html += format_html(
            '<h3>Most Active Users (Last 30 days)</h3><ul style="list-style-type: none; padding: 0;">'
        )
        for user in active_users:
            html += format_html(
                '<li style="padding: 8px; margin-bottom: 5px; background-color: #fff; border-radius: 3px;">'
                "<strong>{}</strong>: {} activities"
                "</li>",
                user.user.username,
                user.total_activity,
            )
        html += format_html("</ul>")

        # Popular topics
        html += format_html(
            '<h3>Popular Topics (Last 30 days)</h3><ul style="list-style-type: none; padding: 0;">'
        )
        for topic in popular_topics:
            html += format_html(
                '<li style="padding: 8px; margin-bottom: 5px; background-color: #fff; border-radius: 3px;">'
                "<strong>{}</strong>: {} new threads"
                "</li>",
                topic.name,
                topic.recent_threads,
            )
        html += format_html("</ul>")

        html += format_html("</div>")
        return html

    get_analytics_dashboard.short_description = "Analytics Dashboard"


# Enhanced user management
class EnhancedUserDataAdmin(UserDataAdmin):
    list_display = (
        "user",
        "is_verified",
        "is_moderator",
        "thread_count",
        "reply_count",
        "last_activity",
    )
    list_filter = ("is_verified", "user__is_staff", "user__is_active", "user__groups")
    readonly_fields = ("thread_count", "reply_count", "last_activity", "user_activity_summary")
    actions = ["verify_users", "unverify_users", "suspend_users", "activate_users"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            thread_count=Count("forumthread", filter=Q(forumthread__is_deleted=False)),
            reply_count=Count("forumreply", filter=Q(forumreply__is_deleted=False)),
            last_post=Count("forumthread", filter=Q(forumthread__is_deleted=False)),
        )
        return qs

    def is_moderator(self, obj):
        return obj.user.groups.filter(name="PDA_Moderator").exists() or obj.user.is_staff

    is_moderator.boolean = True
    is_moderator.short_description = "Moderator"

    def thread_count(self, obj):
        return obj.thread_count

    thread_count.admin_order_field = "thread_count"

    def reply_count(self, obj):
        return obj.reply_count

    reply_count.admin_order_field = "reply_count"

    def last_activity(self, obj):
        last_thread = ForumThread.objects.filter(author=obj).order_by("-created_at").first()
        last_reply = ForumReply.objects.filter(author=obj).order_by("-created_at").first()

        last_thread_date = last_thread.created_at if last_thread else None
        last_reply_date = last_reply.created_at if last_reply else None

        if last_thread_date and last_reply_date:
            return max(last_thread_date, last_reply_date)
        elif last_thread_date:
            return last_thread_date
        elif last_reply_date:
            return last_reply_date
        else:
            return None

    def user_activity_summary(self, obj):
        """Display detailed user activity summary"""
        # Get recent threads
        recent_threads = ForumThread.objects.filter(author=obj, is_deleted=False).order_by(
            "-created_at"
        )[:5]

        # Get recent replies
        recent_replies = ForumReply.objects.filter(author=obj, is_deleted=False).order_by(
            "-created_at"
        )[:5]

        # Create HTML summary
        html = format_html(
            '<div style="padding: 15px; background-color: #f5f5f5; border-radius: 5px;">'
        )

        # User info
        html += format_html(
            "<h2>User Activity: {}</h2>"
            "<p><strong>Email:</strong> {}</p>"
            "<p><strong>Date Joined:</strong> {}</p>"
            "<p><strong>Status:</strong> {} | <strong>Verified:</strong> {}</p>",
            obj.user.username,
            obj.user.email,
            obj.user.date_joined.strftime("%Y-%m-%d %H:%M"),
            "Active" if obj.user.is_active else "Suspended",
            "Yes" if obj.is_verified else "No",
        )

        # Recent threads
        html += format_html("<h3>Recent Threads</h3>")
        if recent_threads:
            html += format_html("<ul>")
            for thread in recent_threads:
                html += format_html(
                    '<li><a href="{}">{}</a> - {}</li>',
                    reverse("admin:api_forumthread_change", args=[thread.id]),
                    thread.title,
                    thread.created_at.strftime("%Y-%m-%d %H:%M"),
                )
            html += format_html("</ul>")
        else:
            html += format_html("<p>No recent threads.</p>")

        # Recent replies
        html += format_html("<h3>Recent Replies</h3>")
        if recent_replies:
            html += format_html("<ul>")
            for reply in recent_replies:
                html += format_html(
                    '<li><a href="{}">Reply to: {}</a> - {}</li>',
                    reverse("admin:api_forumreply_change", args=[reply.id]),
                    reply.thread.title[:30] + ("..." if len(reply.thread.title) > 30 else ""),
                    reply.created_at.strftime("%Y-%m-%d %H:%M"),
                )
            html += format_html("</ul>")
        else:
            html += format_html("<p>No recent replies.</p>")

        html += format_html("</div>")
        return html

    user_activity_summary.short_description = "User Activity Summary"

    def verify_users(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f"{count} users were verified successfully.")

    verify_users.short_description = "Verify selected users"

    def unverify_users(self, request, queryset):
        count = queryset.update(is_verified=False)
        self.message_user(request, f"{count} users were unverified successfully.")

    unverify_users.short_description = "Unverify selected users"

    def suspend_users(self, request, queryset):
        for user_data in queryset:
            user = user_data.user
            user.is_active = False
            user.save()

            # Send notification email
            try:
                send_mail(
                    subject="Your account has been suspended",
                    message=f"Hello {user.username},\n\n"
                    f"Your account has been suspended. Please contact the "
                    f"administration for more information.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception as e:
                # Log the error but continue processing
                print(f"Failed to send suspension email: {e}")

        self.message_user(request, f"{queryset.count()} users were suspended successfully.")

    suspend_users.short_description = "Suspend selected users"

    def activate_users(self, request, queryset):
        count = 0
        for user_data in queryset:
            if not user_data.user.is_active:
                user = user_data.user
                user.is_active = True
                user.save()
                count += 1

                # Send notification email
                try:
                    send_mail(
                        subject="Your account has been reactivated",
                        message=f"Hello {user.username},\n\n"
                        f"Your account has been reactivated and you can now log in again.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    # Log the error but continue processing
                    print(f"Failed to send reactivation email: {e}")

        self.message_user(request, f"{count} users were activated successfully.")

    activate_users.short_description = "Activate suspended users"


# Add to the existing imports
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView


# Add this class to create a custom admin view for analytics
class ForumAnalyticsDashboardView(TemplateView):
    template_name = "admin/forum/analytics_dashboard.html"

    @method_decorator(staff_member_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date range from request or default to last 30 days
        days = int(self.request.GET.get("days", 30))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Thread stats
        total_threads = ForumThread.objects.filter(is_deleted=False).count()
        new_threads = ForumThread.objects.filter(created_at__gte=start_date, is_deleted=False).count()

        # Reply stats
        total_replies = ForumReply.objects.filter(is_deleted=False).count()
        new_replies = ForumReply.objects.filter(created_at__gte=start_date, is_deleted=False).count()

        # Most active users
        most_active_users = (
            UserData.objects.annotate(
                thread_count=Count(
                    "forumthread",
                    filter=Q(forumthread__created_at__gte=start_date, forumthread__is_deleted=False),
                ),
                reply_count=Count(
                    "forumreply",
                    filter=Q(forumreply__created_at__gte=start_date, forumreply__is_deleted=False),
                ),
                total_activity=Count(
                    "forumthread",
                    filter=Q(forumthread__created_at__gte=start_date, forumthread__is_deleted=False),
                )
                + Count(
                    "forumreply",
                    filter=Q(forumreply__created_at__gte=start_date, forumreply__is_deleted=False),
                ),
            )
            .filter(total_activity__gt=0)
            .order_by("-total_activity")[:10]
        )

        # Popular topics
        popular_topics = (
            ForumTopic.objects.annotate(
                thread_count=Count(
                    "forumthread",
                    filter=Q(
                        forumthread__created_at__gte=start_date,
                        forumthread__is_deleted=False,
                        forumthread__approval_status="approved",
                    ),
                )
            )
            .filter(thread_count__gt=0)
            .order_by("-thread_count")[:5]
        )

        # Daily activity for charts (last 30 days)
        daily_data = []
        for i in range(days):
            day = end_date - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            threads = ForumThread.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end, is_deleted=False
            ).count()

            replies = ForumReply.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end, is_deleted=False
            ).count()

            daily_data.append(
                {
                    "date": day_start.strftime("%Y-%m-%d"),
                    "threads": threads,
                    "replies": replies,
                    "total": threads + replies,
                }
            )

        # Reverse for chronological order
        daily_data.reverse()

        context.update(
            {
                "title": "Forum Analytics Dashboard",
                "total_threads": total_threads,
                "new_threads": new_threads,
                "total_replies": total_replies,
                "new_replies": new_replies,
                "most_active_users": most_active_users,
                "popular_topics": popular_topics,
                "daily_data": daily_data,
                "days": days,
                "start_date": start_date,
                "end_date": end_date,
            }
        )

        return context


# Register user & auth models
pda_admin_site.register(User, CustomUserAdmin)
pda_admin_site.register(Group)

# Register PDA models with app groups
pda_admin_site.register(UserData, EnhancedUserDataAdmin)
pda_admin_site.register(PublicDeepfakeArchive, PublicDeepfakeArchiveAdmin)

# Register forum models with app groups
pda_admin_site.register(ForumThread, ForumThreadAdmin)
pda_admin_site.register(ForumReply, ForumReplyAdmin)
pda_admin_site.register(ForumTopic, ForumTopicAdmin)
pda_admin_site.register(ForumTag, ForumTagAdmin)
pda_admin_site.register(ForumAnalytics, ForumAnalyticsAdmin)
