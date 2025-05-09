from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.core.paginator import Paginator
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from datetime import timedelta

from api.models import PublicDeepfakeArchive, ForumThread, ForumReply, ForumTopic, ForumTag
from app.controllers.ResponseCodesController import get_response_code
from app.controllers.CommunityForumController import CommunityForumController
from app.models import UserData
from app.utils.decorators import moderator_required


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


@moderator_required
def pda_moderation_view(request):
    """View for PDA submissions moderation"""
    try:
        # Get pending submissions
        pending_submissions = PublicDeepfakeArchive.objects.filter(review_date__isnull=True).order_by(
            "-submission_date"
        )

        # Paginate results
        paginator = Paginator(pending_submissions, 5)  # 5 submissions per page
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        # Handle form submissions (approve/reject)
        if request.method == "POST":
            submission_id = request.POST.get("submission_id")
            action = request.POST.get("action")
            review_notes = request.POST.get("review_notes", "")

            if submission_id and action in ["approve", "reject"]:
                try:
                    submission = PublicDeepfakeArchive.objects.get(id=submission_id)

                    if action == "approve":
                        submission.is_approved = True
                        submission.review_date = timezone.now()
                        submission.review_notes = review_notes
                        submission.reviewer = request.user
                        submission.save()
                        action_message = f"Submission '{submission.title}' has been approved."
                    else:
                        submission.is_approved = False
                        submission.review_date = timezone.now()
                        submission.review_notes = review_notes
                        submission.reviewer = request.user
                        submission.save()
                        action_message = f"Submission '{submission.title}' has been rejected."

                except Exception as e:
                    action_message = f"Error processing action: {str(e)}"
            else:
                action_message = None
        else:
            action_message = None

        context = {
            "page_title": "PDA Moderation",
            "pending_submissions": page_obj,
            "pending_count": pending_submissions.count(),
            "action_message": action_message,
        }

        return render(request, "moderation/pda_moderation.html", context)

    except Exception as e:
        # Log the error and redirect to dashboard
        print(f"Error in PDA moderation view: {str(e)}")
        return redirect("moderation_dashboard")


@moderator_required
def user_management_view(request):
    """View for user management by moderators"""
    try:
        # Only staff and admins can access this view
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect("moderation_dashboard")

        # Get all users with UserData
        users = User.objects.select_related("userdata").all()

        # Filter based on search query if provided
        search_query = request.GET.get("search", "")
        if search_query:
            users = users.filter(
                Q(username__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
            )

        # Get moderator group
        moderator_group = Group.objects.get(name="PDA_Moderator")

        # Handle form submissions for making/removing moderators
        if request.method == "POST" and request.user.is_superuser:
            user_id = request.POST.get("user_id")
            action = request.POST.get("action")

            if user_id and action in ["make_moderator", "remove_moderator"]:
                try:
                    target_user = User.objects.get(id=user_id)

                    if action == "make_moderator":
                        if not target_user.groups.filter(name="PDA_Moderator").exists():
                            target_user.groups.add(moderator_group)
                            action_message = f"User '{target_user.username}' is now a moderator."
                        else:
                            action_message = f"User '{target_user.username}' is already a moderator."
                    else:
                        if target_user.groups.filter(name="PDA_Moderator").exists():
                            target_user.groups.remove(moderator_group)
                            action_message = f"Removed moderator status from '{target_user.username}'."
                        else:
                            action_message = f"User '{target_user.username}' is not a moderator."

                except Exception as e:
                    action_message = f"Error processing action: {str(e)}"
            else:
                action_message = None
        else:
            action_message = None

        # Paginate results
        paginator = Paginator(users, 15)  # 15 users per page
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        context = {
            "page_title": "User Management",
            "users": page_obj,
            "total_users": users.count(),
            "verified_users": UserData.objects.filter(is_verified=True).count(),
            "moderator_count": User.objects.filter(groups__name="PDA_Moderator").count(),
            "search_query": search_query,
            "action_message": action_message,
            "is_superuser": request.user.is_superuser,
        }

        return render(request, "moderation/user_management.html", context)

    except Exception as e:
        # Log the error and redirect to dashboard
        print(f"Error in user management view: {str(e)}")
        return redirect("moderation_dashboard")


@moderator_required
def analytics_dashboard_view(request):
    """Analytics dashboard for moderators and staff"""
    try:
        # Date filters
        days = request.GET.get("days", "30")
        try:
            days = int(days)
        except ValueError:
            days = 30  # Default to 30 days

        start_date = timezone.now() - timedelta(days=days)

        # Thread statistics
        total_threads = ForumThread.objects.filter(is_deleted=False).count()
        new_threads = ForumThread.objects.filter(is_deleted=False, created_at__gte=start_date).count()

        threads_by_status = (
            ForumThread.objects.filter(is_deleted=False)
            .values("approval_status")
            .annotate(count=Count("id"))
        )

        # Reply statistics
        total_replies = ForumReply.objects.filter(is_deleted=False).count()
        new_replies = ForumReply.objects.filter(is_deleted=False, created_at__gte=start_date).count()

        # PDA statistics
        total_pda = PublicDeepfakeArchive.objects.count()
        new_pda = PublicDeepfakeArchive.objects.filter(submission_date__gte=start_date).count()

        approved_pda = PublicDeepfakeArchive.objects.filter(is_approved=True).count()
        rejected_pda = PublicDeepfakeArchive.objects.filter(
            is_approved=False, review_date__isnull=False
        ).count()
        pending_pda = PublicDeepfakeArchive.objects.filter(review_date__isnull=True).count()

        # Topic statistics
        popular_topics = ForumTopic.objects.annotate(
            thread_count=Count("forumthread", filter=Q(forumthread__is_deleted=False))
        ).order_by("-thread_count")[:10]

        # User statistics
        total_users = User.objects.count()
        new_users = User.objects.filter(date_joined__gte=start_date).count()
        verified_users = UserData.objects.filter(is_verified=True).count()

        # Activity timeline - threads created per day for last 30 days
        timeline_data = []
        for i in range(days):
            day = timezone.now() - timedelta(days=days - i - 1)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            count = ForumThread.objects.filter(created_at__range=(day_start, day_end)).count()

            timeline_data.append({"date": day_start.strftime("%Y-%m-%d"), "count": count})

        context = {
            "page_title": "Analytics Dashboard",
            "days": days,
            "total_threads": total_threads,
            "new_threads": new_threads,
            "threads_by_status": threads_by_status,
            "total_replies": total_replies,
            "new_replies": new_replies,
            "total_pda": total_pda,
            "new_pda": new_pda,
            "approved_pda": approved_pda,
            "rejected_pda": rejected_pda,
            "pending_pda": pending_pda,
            "popular_topics": popular_topics,
            "total_users": total_users,
            "new_users": new_users,
            "verified_users": verified_users,
            "timeline_data": timeline_data,
        }

        return render(request, "moderation/analytics_dashboard.html", context)

    except Exception as e:
        # Log the error and redirect to dashboard
        print(f"Error in analytics dashboard view: {str(e)}")
        return redirect("moderation_dashboard")


@moderator_required
def moderation_settings_view(request):
    """Settings page for moderation panel"""
    try:
        # Only staff and admins can access settings
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect("moderation_dashboard")

        # Handle form submissions
        if request.method == "POST":
            # Implement settings changes here if needed
            pass

        context = {
            "page_title": "Moderation Settings",
        }

        return render(request, "moderation/settings.html", context)

    except Exception as e:
        # Log the error and redirect to dashboard
        print(f"Error in moderation settings view: {str(e)}")
        return redirect("moderation_dashboard")


@moderator_required
def thread_detail_view(request, thread_id):
    """Detailed view of a forum thread with moderation capabilities"""
    try:
        thread = get_object_or_404(
            ForumThread.objects.select_related("author__user", "topic").prefetch_related(
                "tags", "replies"
            ),
            id=thread_id,
        )

        # Get replies for the thread
        replies = (
            ForumReply.objects.filter(thread=thread, is_deleted=False)
            .select_related("author__user")
            .order_by("created_at")
        )

        # Handle form submissions (approve/reject)
        if request.method == "POST":
            action = request.POST.get("action")

            if action in ["approve", "reject"]:
                try:
                    # Use the controller to moderate the thread
                    result = forum_controller.moderate_thread(
                        thread_id=thread.id,
                        approval_status=action + "d",  # "approved" or "rejected"
                        moderator=request.user,
                    )

                    # Show success message through template context
                    if result["success"]:
                        action_message = f"Thread '{thread.title}' has been {action}d successfully."
                    else:
                        action_message = f"Error: {result['error']}"

                except Exception as e:
                    action_message = f"Error processing action: {str(e)}"
            else:
                action_message = None
        else:
            action_message = None

        context = {
            "page_title": thread.title,
            "thread": thread,
            "replies": replies,
            "action_message": action_message,
        }

        return render(request, "moderation/thread_detail.html", context)

    except Exception as e:
        # Log the error and redirect to forum moderation
        print(f"Error in thread detail view: {str(e)}")
        return redirect("forum_moderation")


@login_required
def moderation_dashboard(request):
    """Modern dashboard view for all moderation activities"""
    try:
        user_data = UserData.objects.get(user=request.user)

        # Check if user is moderator or staff
        if not (user_data.is_moderator() or request.user.is_staff):
            return redirect("login")

        # Fetch stats
        pda_pending_count = PublicDeepfakeArchive.objects.filter(review_date__isnull=True).count()
        forum_pending_count = ForumThread.objects.filter(approval_status="pending").count()

        # Get total counts for stats
        total_threads = ForumThread.objects.filter(is_deleted=False).count()
        total_replies = ForumReply.objects.filter(is_deleted=False).count()

        # Recent activities
        recent_pda = PublicDeepfakeArchive.objects.order_by("-submission_date")[:10]
        recent_threads = ForumThread.objects.filter(is_deleted=False).order_by("-created_at")[:10]

        # Get most active topics
        active_topics = (
            ForumTopic.objects.annotate(
                thread_count=Count(
                    "forumthread",
                    filter=Q(forumthread__created_at__gte=timezone.now() - timedelta(days=7)),
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
            "total_threads": total_threads,
            "total_replies": total_replies,
        }

        return render(request, "moderation/dashboard.html", context)

    except Exception as e:
        # If there's an error, redirect to login
        print(f"Error in moderation dashboard: {str(e)}")
        return redirect("login")


@moderator_required
def forum_moderation_view(request):
    """Modern view for forum thread moderation"""
    try:
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

        # Paginate results
        paginator = Paginator(pending_threads, 10)  # 10 threads per page
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

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
            "pending_threads": page_obj,
            "action_message": action_message,
            "pending_count": pending_threads.count(),
        }

        return render(request, "moderation/forum_moderation.html", context)

    except Exception as e:
        # If there's an error, redirect to dashboard
        print(f"Error in forum moderation: {str(e)}")
        return redirect("moderation_dashboard")
