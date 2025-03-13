from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User, Group
from api.models import PublicDeepfakeArchive, UserData, DeepfakeDetectionResult
from app.contollers.HelpersController import URLHelper
from datetime import datetime
from django.db.models import Q
# Customize the admin site
admin.site.site_header = "Deepfake Archive Administration"
admin.site.site_title = "PDA Admin/Moderation Portal"
admin.site.index_title = "Welcome to PDA Admin/Morderator Portal"


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
                Q(reviewed_by__isnull=True) |  # Not reviewed yet
                Q(reviewed_by=request.user)     # Or reviewed by current user
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

    def is_moderator(self, obj):
        return obj.groups.filter(name="PDA_Moderator").exists()

    is_moderator.boolean = True
    is_moderator.short_description = "Moderator"

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


# Unregister the default UserAdmin
admin.site.unregister(User)
# Register our CustomUserAdmin
admin.site.register(User, CustomUserAdmin)
admin.site.register(UserData, UserDataAdmin)
admin.site.register(PublicDeepfakeArchive, PublicDeepfakeArchiveAdmin)
