from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Count
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.models import PublicDeepfakeArchive, ForumThread, ForumReply, ForumTopic, ForumTag
from app.controllers.ResponseCodesController import get_response_code
from app.controllers.CommunityForumController import CommunityForumController
from app.models import UserData


# Initialize the forum controller
forum_controller = CommunityForumController()


class ModeratorPermission:
    """Custom permission class for moderators"""

    def has_permission(self, request, view):
        try:
            user_data = UserData.objects.get(user=request.user)
            return user_data.is_moderator() or user_data.is_admin()
        except UserData.DoesNotExist:
            return False


@staff_member_required
def approve_submission(request, submission_id):
    """Admin view to approve a submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=submission_id)
    submission.is_approved = True
    submission.save()
    return HttpResponseRedirect(reverse("admin:api_publicdeepfakearchive_changelist"))


@staff_member_required
def reject_submission(request, submission_id):
    """Admin view to reject (delete) a submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=submission_id)
    submission.delete()
    return HttpResponseRedirect(reverse("admin:api_publicdeepfakearchive_changelist"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_submissions(request):
    """API endpoint to get pending submissions for moderators"""
    try:
        user_data = UserData.objects.get(user=request.user)
        if not (user_data.is_moderator() or request.user.is_staff):
            return JsonResponse(
                {**get_response_code("ACCESS_DENIED"), "error": "Moderator privileges required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        pending = PublicDeepfakeArchive.objects.filter(is_approved=False).order_by("-submission_date")

        results = []
        for submission in pending:
            results.append(
                {
                    "id": submission.id,
                    "title": submission.title,
                    "category": submission.category,
                    "submission_identifier": submission.submission_identifier,
                    "submission_date": submission.submission_date,
                    "description": submission.description,
                    "file_type": submission.file_type,
                }
            )

        return JsonResponse(
            {**get_response_code("SUCCESS"), "data": results}, status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def moderate_submission(request, submission_id):
    """API endpoint to approve or reject a submission"""
    try:
        user_data = UserData.objects.get(user=request.user)
        if not (user_data.is_moderator() or request.user.is_staff):
            return JsonResponse(
                {**get_response_code("ACCESS_DENIED"), "error": "Moderator privileges required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        action = request.data.get("action")
        if action not in ["approve", "reject"]:
            return JsonResponse(
                {
                    **get_response_code("INVALID_REQUEST"),
                    "error": "Invalid action. Use 'approve' or 'reject'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = get_object_or_404(PublicDeepfakeArchive, id=submission_id)

        if action == "approve":
            submission.is_approved = True
            submission.save()
            message = "Submission approved successfully"
        else:
            submission.delete()
            message = "Submission rejected successfully"

        return JsonResponse(
            {**get_response_code("SUCCESS"), "message": message}, status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@login_required
def moderation_dashboard(request):
    """Modern dashboard view for all moderation activities"""
    try:
        user_data = UserData.objects.get(user=request.user)

        # Check if user is moderator or staff
        if not (user_data.is_moderator() or request.user.is_staff):
            return redirect("admin:login")

        # Fetch stats
        pda_pending_count = PublicDeepfakeArchive.objects.filter(review_date__isnull=True).count()
        forum_pending_count = ForumThread.objects.filter(approval_status="pending").count()

        # Recent activities
        recent_pda = PublicDeepfakeArchive.objects.order_by("-submission_date")[:10]
        recent_threads = ForumThread.objects.filter(is_deleted=False).order_by("-created_at")[:10]

        # Get most active topics
        active_topics = (
            ForumTopic.objects.annotate(
                thread_count=Count(
                    "forumthread",
                    filter=Q(forumthread__created_at__gte=timezone.now() - timezone.timedelta(days=7)),
                )
            )
            .filter(thread_count__gt=0)
            .order_by("-thread_count")[:5]
        )

        # Context for the template
        context = {
            "page_title": "Moderation Dashboard",
            "user": request.user,
            "pda_pending_count": pda_pending_count,
            "forum_pending_count": forum_pending_count,
            "recent_pda": recent_pda,
            "recent_threads": recent_threads,
            "active_topics": active_topics,
        }

        return render(request, "app/moderation/dashboard.html", context)

    except Exception as e:
        # If there's an error, redirect to admin
        return redirect("admin:index")


@login_required
def forum_moderation_view(request):
    """Modern view for forum thread moderation"""
    try:
        user_data = UserData.objects.get(user=request.user)

        # Check if user is moderator or staff
        if not (user_data.is_moderator() or request.user.is_staff):
            return redirect("admin:login")

        # Get pending threads with annotations
        pending_threads = (
            ForumThread.objects.filter(approval_status="pending")
            .select_related("author__user", "topic")
            .prefetch_related("tags")
            .annotate(
                reply_count=Count("replies", filter=Q(replies__is_deleted=False)),
                like_count=Count("likes"),
            )
            .order_by("-created_at")
        )

        # Handle form submissions (approve/reject)
        if request.method == "POST":
            thread_id = request.POST.get("thread_id")
            action = request.POST.get("action")

            if thread_id and action in ["approve", "reject"]:
                try:
                    # Use the controller to moderate the thread
                    result = forum_controller.moderate_thread(
                        thread_id=int(thread_id),
                        approval_status=action + "d",  # "approved" or "rejected"
                        moderator=request.user,
                    )

                    # Show success message through template context
                    if result["success"]:
                        thread = ForumThread.objects.get(id=thread_id)
                        action_message = f"Thread '{thread.title}' has been {action}d successfully."
                    else:
                        action_message = f"Error: {result['error']}"

                except Exception as e:
                    action_message = f"Error processing action: {str(e)}"
            else:
                action_message = None
        else:
            action_message = None

        # Context for the template
        context = {
            "page_title": "Forum Moderation",
            "user": request.user,
            "pending_threads": pending_threads,
            "action_message": action_message,
            "pending_count": pending_threads.count(),
        }

        return render(request, "app/moderation/forum_moderation.html", context)

    except Exception as e:
        # If there's an error, redirect to admin
        return redirect("admin:index")
