import json
import logging
from datetime import datetime, timedelta
import os
import uuid
import time

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from api.models import (
    ForumThread,
    ForumReply,
    ForumTopic,
    PublicDeepfakeArchive,
)
from app.models import UserData, ModeratorAction
from app.controllers.KnowledgeBaseController import KnowledgeBaseController
from app.controllers.HelpersController import URLHelper
from api.models import KnowledgeBaseArticle, KnowledgeBaseTopic, UserData

logger = logging.getLogger(__name__)
kb_controller = KnowledgeBaseController()

# Setup logger
logger = logging.getLogger(__name__)


# Helper functions
def is_admin(user):
    """Check if user is admin"""
    return user.is_superuser or user.is_staff


def custom_admin_required(view_func):
    """Decorator for views that checks if the user is admin, redirecting to login if not."""
    decorated_view = login_required(user_passes_test(is_admin, login_url="custom_admin_login")(view_func))
    return decorated_view


# Login / Logout Views
def custom_admin_login_view(request):
    """Login view for custom admin panel"""
    # If already logged in and is admin, redirect to dashboard
    if request.user.is_authenticated and is_admin(request.user):
        return redirect("custom_admin_dashboard")

    error_message = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if is_admin(user):
                login(request, user)
                return redirect("custom_admin_dashboard")
            else:
                error_message = "You do not have admin privileges."
        else:
            error_message = "Invalid username or password."

    return render(request, "custom_admin/login.html", {"error_message": error_message})


@login_required
def custom_admin_logout_view(request):
    """Logout view for custom admin panel"""
    logout(request)
    return redirect("custom_admin_login")


# Dashboard View
@custom_admin_required
def custom_admin_dashboard_view(request):
    """Main dashboard view for custom admin panel"""
    # Get statistics for the dashboard

    # User stats
    total_users = User.objects.count()
    month_ago = timezone.now() - timedelta(days=30)
    new_users = User.objects.filter(date_joined__gte=month_ago).count()
    new_users_percent = round((new_users / total_users) * 100) if total_users > 0 else 0

    # PDA stats
    total_pda = PublicDeepfakeArchive.objects.count()
    new_pda = PublicDeepfakeArchive.objects.filter(submission_date__gte=month_ago).count()
    new_pda_percent = round((new_pda / total_pda) * 100) if total_pda > 0 else 0

    # Forum stats
    total_threads = ForumThread.objects.filter(is_deleted=False).count()
    new_threads = ForumThread.objects.filter(is_deleted=False, created_at__gte=month_ago).count()
    new_threads_percent = round((new_threads / total_threads) * 100) if total_threads > 0 else 0

    # Pending items
    pending_pda = PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=True).count()
    pending_threads = ForumThread.objects.filter(approval_status="pending").count()
    pending_total = pending_pda + pending_threads

    # Get recent activities (admin actions)
    recent_activities = []

    # Get sample admin actions
    admin_actions = ModeratorAction.objects.filter(moderator__is_staff=True).order_by("-timestamp")[:5]

    for action in admin_actions:
        activity = {
            "title": action.content_identifier,
            "timestamp": action.timestamp,
            "action_type": action.action_type,
            "content_type": action.content_type,
            "user": action.moderator.username,
        }
        recent_activities.append(activity)

    # Get pending items for approval
    pending_items = []

    # Get pending PDA submissions
    pda_pending = PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=True).order_by("-submission_date")[:3]

    for pda in pda_pending:
        item = {
            "title": pda.title,
            "submission_date": pda.submission_date,
            "type": "PDA Submission",
            "author": pda.user.user.username,
            "url": reverse("custom_admin_pda_detail", args=[pda.id]),
            "approve_url": reverse("custom_admin_pda_approve", args=[pda.id]),
            "reject_url": reverse("custom_admin_pda_reject", args=[pda.id]),
        }
        pending_items.append(item)

    # Get pending forum threads
    forum_pending = ForumThread.objects.filter(approval_status="pending").order_by("-created_at")[:3]

    for thread in forum_pending:
        item = {
            "title": thread.title,
            "submission_date": thread.created_at,
            "type": "Forum Thread",
            "author": thread.author.user.username,
            "url": reverse("custom_admin_forum_thread", args=[thread.id]),
            "approve_url": reverse("custom_admin_forum_approve", args=[thread.id]),
            "reject_url": reverse("custom_admin_forum_reject", args=[thread.id]),
        }
        pending_items.append(item)

    # Sort pending items by date
    pending_items = sorted(pending_items, key=lambda x: x["submission_date"], reverse=True)[:5]

    # Generate data for charts
    days = 7
    days_labels = []
    users_data = []
    pda_data = []
    threads_data = []

    for i in range(days):
        day = timezone.now() - timedelta(days=days - i - 1)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Format date as string
        days_labels.append(day_start.strftime("%Y-%m-%d"))

        # Count items for each day
        day_users = User.objects.filter(date_joined__range=(day_start, day_end)).count()
        day_pda = PublicDeepfakeArchive.objects.filter(submission_date__range=(day_start, day_end)).count()
        day_threads = ForumThread.objects.filter(created_at__range=(day_start, day_end)).count()

        users_data.append(day_users)
        pda_data.append(day_pda)
        threads_data.append(day_threads)

    context = {
        "active_page": "dashboard",
        "total_users": total_users,
        "new_users_percent": new_users_percent,
        "total_pda": total_pda,
        "new_pda_percent": new_pda_percent,
        "total_threads": total_threads,
        "new_threads_percent": new_threads_percent,
        "pending_total": pending_total,
        "recent_activities": recent_activities,
        "pending_items": pending_items,
        "days_labels": json.dumps(days_labels),
        "users_data": json.dumps(users_data),
        "pda_data": json.dumps(pda_data),
        "threads_data": json.dumps(threads_data),
    }

    return render(request, "custom_admin/dashboard.html", context)


# User Management Views
@custom_admin_required
def custom_admin_users_view(request):
    """View to list and manage users"""
    # Get all users
    users = User.objects.all().order_by("-date_joined")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) | Q(email__icontains=search_query) | Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(users, 20)  # 20 users per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "active_page": "users",
        "users": page_obj,
        "search_query": search_query,
        "total_users": User.objects.count(),
        "total_moderators": User.objects.filter(groups__name="PDA_Moderator").count(),
        "total_admins": User.objects.filter(is_staff=True).count(),
    }

    return render(request, "custom_admin/users.html", context)


@custom_admin_required
def custom_admin_user_detail_view(request, user_id):
    """View to see and edit user details"""
    user = get_object_or_404(User, id=user_id)

    try:
        user_data = UserData.objects.get(user=user)
    except UserData.DoesNotExist:
        user_data = None

    # Get user activity
    forum_threads = ForumThread.objects.filter(author__user=user, is_deleted=False).count()
    forum_replies = ForumReply.objects.filter(author__user=user, is_deleted=False).count()
    pda_submissions = PublicDeepfakeArchive.objects.filter(user__user=user).count()

    # Process form submission to update user
    if request.method == "POST":
        # Process user update
        user.username = request.POST.get("username", user.username)
        user.email = request.POST.get("email", user.email)
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)

        # Handle status changes
        is_active = request.POST.get("is_active") == "on"
        is_staff = request.POST.get("is_staff") == "on"
        is_superuser = request.POST.get("is_superuser") == "on"

        user.is_active = is_active
        user.is_staff = is_staff
        user.is_superuser = is_superuser

        # Save changes
        user.save()

        # Update UserData if it exists
        if user_data:
            user_data.is_verified = request.POST.get("is_verified") == "on"
            user_data.save()

        messages.success(request, f"User {user.username} updated successfully")
        return redirect("custom_admin_user_detail", user_id=user.id)

    context = {
        "active_page": "users",
        "user_obj": user,
        "user_data": user_data,
        "forum_threads": forum_threads,
        "forum_replies": forum_replies,
        "pda_submissions": pda_submissions,
        "is_moderator": user.groups.filter(name="PDA_Moderator").exists(),
    }

    return render(request, "custom_admin/user_detail.html", context)


@custom_admin_required
def custom_admin_user_add_view(request):
    """View to add a new user"""
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        first_name = request.POST.get("first_name", "")
        last_name = request.POST.get("last_name", "")

        # Validate input
        if not (username and email and password):
            messages.error(request, "Username, email, and password are required.")
            return render(request, "custom_admin/user_add.html", {"active_page": "users"})

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return render(request, "custom_admin/user_add.html", {"active_page": "users"})

        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f"Email '{email}' is already in use.")
            return render(request, "custom_admin/user_add.html", {"active_page": "users"})

        # Create user
        try:
            user = User.objects.create_user(username=username, email=email, password=password, first_name=first_name, last_name=last_name)

            # Create UserData for the user
            UserData.objects.create(user=user)

            # Set user roles
            is_moderator = request.POST.get("is_moderator") == "on"
            is_staff = request.POST.get("is_staff") == "on"
            is_superuser = request.POST.get("is_superuser") == "on"

            if is_moderator:
                moderator_group = Group.objects.get(name="PDA_Moderator")
                user.groups.add(moderator_group)

            if is_staff:
                user.is_staff = True
                user.save()

            if is_superuser:
                user.is_superuser = True
                user.save()

            messages.success(request, f"User '{username}' created successfully!")
            return redirect("custom_admin_user_detail", user_id=user.id)

        except Exception as e:
            messages.error(request, f"Error creating user: {str(e)}")

    return render(request, "custom_admin/user_add.html", {"active_page": "users"})


@custom_admin_required
def custom_admin_pda_list_view(request):
    """View to list PDA submissions"""
    # Get filter parameter
    filter_type = request.GET.get("filter", "all")

    # Apply filter
    if filter_type == "pending":
        submissions = PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=True).order_by("-submission_date")
    elif filter_type == "approved":
        submissions = PublicDeepfakeArchive.objects.filter(is_approved=True).order_by("-submission_date")
    elif filter_type == "rejected":
        submissions = PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=False).order_by("-submission_date")
    else:
        submissions = PublicDeepfakeArchive.objects.all().order_by("-submission_date")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        submissions = submissions.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query) | Q(user__user__username__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(submissions, 10)  # 10 submissions per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "active_page": "pda_submissions",
        "submissions": page_obj,
        "filter_type": filter_type,
        "search_query": search_query,
        "pending_count": PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=True).count(),
        "approved_count": PublicDeepfakeArchive.objects.filter(is_approved=True).count(),
        "rejected_count": PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=False).count(),
        "total_count": PublicDeepfakeArchive.objects.count(),
        "page_range": range(1, paginator.num_pages + 1),
    }

    return render(request, "custom_admin/pda_list.html", context)


@custom_admin_required
def custom_admin_pda_detail_view(request, pda_id):
    """View to see PDA submission details"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=pda_id)

    context = {
        "active_page": "pda_submissions",
        "submission": submission,
    }

    return render(request, "custom_admin/pda_detail.html", context)


@custom_admin_required
def custom_admin_pda_approve_view(request, pda_id):
    """View to approve a PDA submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=pda_id)

    # Update submission
    submission.is_approved = True
    submission.review_date = timezone.now()
    submission.reviewed_by = request.user

    if request.method == "POST":
        # If additional notes were submitted
        submission.review_notes = request.POST.get("review_notes", "")

    submission.save()

    # Log the action
    moderator_action = ModeratorAction(
        moderator=request.user, action_type="approve", content_type="pda", content_identifier=f"PDA: {submission.title}", notes=submission.review_notes
    )
    moderator_action.save()

    messages.success(request, f"PDA submission '{submission.title}' has been approved.")
    return redirect("custom_admin_pda_list")


@custom_admin_required
def custom_admin_pda_reject_view(request, pda_id):
    """View to reject a PDA submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=pda_id)

    # Update submission
    submission.is_approved = False
    submission.review_date = timezone.now()
    submission.reviewed_by = request.user

    if request.method == "POST":
        # If additional notes were submitted
        submission.review_notes = request.POST.get("review_notes", "")

    submission.save()

    # Log the action
    moderator_action = ModeratorAction(
        moderator=request.user, action_type="reject", content_type="pda", content_identifier=f"PDA: {submission.title}", notes=submission.review_notes
    )
    moderator_action.save()

    messages.success(request, f"PDA submission '{submission.title}' has been rejected.")
    return redirect("custom_admin_pda_list")


@custom_admin_required
def custom_admin_forum_view(request):
    """View to list forum threads"""
    # Get filter parameter
    filter_type = request.GET.get("filter", "all")

    # Apply filter
    if filter_type == "pending":
        threads = ForumThread.objects.filter(approval_status="pending", is_deleted=False).order_by("-created_at")
    elif filter_type == "approved":
        threads = ForumThread.objects.filter(approval_status="approved", is_deleted=False).order_by("-created_at")
    elif filter_type == "rejected":
        threads = ForumThread.objects.filter(approval_status="rejected", is_deleted=False).order_by("-created_at")
    else:
        threads = ForumThread.objects.filter(is_deleted=False).order_by("-created_at")

    # Search functionality
    search_query = request.GET.get("search", "")
    if search_query:
        threads = threads.filter(Q(title__icontains=search_query) | Q(content__icontains=search_query) | Q(author__user__username__icontains=search_query))

    # Pagination
    paginator = Paginator(threads, 15)  # 15 threads per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "active_page": "forum",
        "threads": page_obj,
        "filter_type": filter_type,
        "search_query": search_query,
        "pending_count": ForumThread.objects.filter(approval_status="pending", is_deleted=False).count(),
        "approved_count": ForumThread.objects.filter(approval_status="approved", is_deleted=False).count(),
        "rejected_count": ForumThread.objects.filter(approval_status="rejected", is_deleted=False).count(),
        "total_count": ForumThread.objects.filter(is_deleted=False).count(),
        "page_range": range(1, paginator.num_pages + 1),
    }

    return render(request, "custom_admin/forum_list.html", context)


@custom_admin_required
def custom_admin_forum_thread_view(request, thread_id):
    """View to see forum thread details"""
    thread = get_object_or_404(
        ForumThread.objects.select_related("author__user", "topic").prefetch_related("tags", "replies"),
        id=thread_id,
    )

    # Get replies for the thread
    replies = ForumReply.objects.filter(thread=thread).select_related("author__user").order_by("created_at")

    context = {
        "active_page": "forum",
        "thread": thread,
        "replies": replies,
    }

    return render(request, "custom_admin/forum_thread.html", context)


@custom_admin_required
def custom_admin_forum_approve_view(request, thread_id):
    """View to approve a forum thread"""
    thread = get_object_or_404(ForumThread, id=thread_id)

    # Update thread
    thread.approval_status = "approved"
    thread.review_date = timezone.now()
    thread.reviewed_by = request.user

    if request.method == "POST":
        # If additional notes were submitted
        thread.review_notes = request.POST.get("review_notes", "")

    thread.save()

    # Log the action
    moderator_action = ModeratorAction(
        moderator=request.user,
        action_type="approve",
        content_type="thread",
        content_identifier=f"Thread: {thread.title}",
        notes=thread.review_notes if hasattr(thread, "review_notes") else None,
    )
    moderator_action.save()

    messages.success(request, f"Forum thread '{thread.title}' has been approved.")
    return redirect("custom_admin_forum")


@custom_admin_required
def custom_admin_forum_reject_view(request, thread_id):
    """View to reject a forum thread"""
    thread = get_object_or_404(ForumThread, id=thread_id)

    # Update thread
    thread.approval_status = "rejected"
    thread.review_date = timezone.now()
    thread.reviewed_by = request.user

    if request.method == "POST":
        # If additional notes were submitted
        thread.review_notes = request.POST.get("review_notes", "")

    thread.save()

    # Log the action
    moderator_action = ModeratorAction(
        moderator=request.user,
        action_type="reject",
        content_type="thread",
        content_identifier=f"Thread: {thread.title}",
        notes=thread.review_notes if hasattr(thread, "review_notes") else None,
    )
    moderator_action.save()

    messages.success(request, f"Forum thread '{thread.title}' has been rejected.")
    return redirect("custom_admin_forum")


@custom_admin_required
def custom_admin_analytics_view(request):
    """View for analytics dashboard"""
    # Get date range
    days = int(request.GET.get("days", 30))

    # Calculate date ranges
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)

    # User statistics
    total_users = User.objects.count()
    new_users = User.objects.filter(date_joined__gte=start_date).count()

    # PDA statistics
    total_pda = PublicDeepfakeArchive.objects.count()
    new_pda = PublicDeepfakeArchive.objects.filter(submission_date__gte=start_date).count()
    approved_pda = PublicDeepfakeArchive.objects.filter(is_approved=True).count()
    rejected_pda = PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=False).count()

    # Forum statistics
    total_threads = ForumThread.objects.filter(is_deleted=False).count()
    new_threads = ForumThread.objects.filter(is_deleted=False, created_at__gte=start_date).count()
    total_replies = ForumReply.objects.filter(is_deleted=False).count()
    new_replies = ForumReply.objects.filter(is_deleted=False, created_at__gte=start_date).count()

    # Get popular topics
    popular_topics = ForumTopic.objects.annotate(thread_count=Count("threads", filter=Q(threads__is_deleted=False))).order_by("-thread_count")[:10]

    # Generate timeline data for last 'days' days
    timeline_data = []
    labels = []
    users_data = []
    pda_submissions_data = []
    forum_threads_data = []
    forum_replies_data = []

    for i in range(days):
        day = timezone.now() - timedelta(days=days - i - 1)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Format date label
        labels.append(day_start.strftime("%Y-%m-%d"))

        # Count items per day
        day_users = User.objects.filter(date_joined__range=(day_start, day_end)).count()
        day_pda = PublicDeepfakeArchive.objects.filter(submission_date__range=(day_start, day_end)).count()
        day_threads = ForumThread.objects.filter(created_at__range=(day_start, day_end)).count()
        day_replies = ForumReply.objects.filter(created_at__range=(day_start, day_end)).count()

        users_data.append(day_users)
        pda_submissions_data.append(day_pda)
        forum_threads_data.append(day_threads)
        forum_replies_data.append(day_replies)

        timeline_data.append({"date": day_start.strftime("%Y-%m-%d"), "users": day_users, "pda": day_pda, "threads": day_threads, "replies": day_replies})

    context = {
        "active_page": "analytics",
        "days": days,
        "total_users": total_users,
        "new_users": new_users,
        "total_pda": total_pda,
        "new_pda": new_pda,
        "approved_pda": approved_pda,
        "rejected_pda": rejected_pda,
        "total_threads": total_threads,
        "new_threads": new_threads,
        "total_replies": total_replies,
        "new_replies": new_replies,
        "popular_topics": popular_topics,
        "timeline_data": timeline_data,
        "chart_labels": json.dumps(labels),
        "users_data": json.dumps(users_data),
        "pda_data": json.dumps(pda_submissions_data),
        "threads_data": json.dumps(forum_threads_data),
        "replies_data": json.dumps(forum_replies_data),
    }

    return render(request, "custom_admin/analytics.html", context)


@custom_admin_required
def custom_admin_logs_view(request):
    """View for activity logs"""
    # Get all moderator actions
    actions = ModeratorAction.objects.all().order_by("-timestamp")

    # Filtering by action type
    action_type = request.GET.get("action_type", "")
    if action_type:
        actions = actions.filter(action_type=action_type)

    # Filtering by user
    user_id = request.GET.get("user_id", "")
    if user_id:
        actions = actions.filter(moderator_id=user_id)

    # Filtering by content type
    content_type = request.GET.get("content_type", "")
    if content_type:
        actions = actions.filter(content_type=content_type)

    # Pagination
    paginator = Paginator(actions, 20)  # 20 actions per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "active_page": "logs",
        "actions": page_obj,
        "action_type": action_type,
        "user_id": user_id,
        "content_type": content_type,
        "moderators": User.objects.filter(Q(is_staff=True) | Q(groups__name="PDA_Moderator")).distinct(),
    }

    return render(request, "custom_admin/logs.html", context)


@custom_admin_required
def custom_admin_settings_view(request):
    """View for admin settings"""
    # Handle form submissions
    if request.method == "POST":
        # Determine which form was submitted
        form_type = request.POST.get("form_type", "")

        if form_type == "general_settings":
            # Update general settings
            pass  # Implement as needed

        elif form_type == "moderation_settings":
            # Update moderation settings
            pass  # Implement as needed

        elif form_type == "security_settings":
            # Update security settings
            pass  # Implement as needed

        messages.success(request, "Settings updated successfully.")

    context = {
        "active_page": "settings",
    }

    return render(request, "custom_admin/settings.html", context)


@custom_admin_required
def custom_admin_profile_view(request):
    """View for admin profile"""
    user = request.user

    if request.method == "POST":
        # Update user profile
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.email = request.POST.get("email", user.email)

        # Check if password should be updated
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if current_password and new_password and confirm_password:
            if user.check_password(current_password):
                if new_password == confirm_password:
                    user.set_password(new_password)
                    messages.success(request, "Password updated successfully.")
                else:
                    messages.error(request, "New passwords do not match.")
            else:
                messages.error(request, "Current password is incorrect.")

        user.save()
        messages.success(request, "Profile updated successfully.")

    context = {"active_page": "profile", "user": user}

    return render(request, "custom_admin/profile.html", context)


@custom_admin_required
def custom_admin_moderators_view(request):
    """View to manage moderators"""
    # Get users with moderator privileges
    moderator_group = Group.objects.get(name="PDA_Moderator")
    moderators = User.objects.filter(Q(groups=moderator_group) | Q(is_staff=True)).distinct().order_by("username")

    # Handle form submissions
    if request.method == "POST":
        action = request.POST.get("action")
        user_id = request.POST.get("user_id")

        if action and user_id:
            user = get_object_or_404(User, id=user_id)

            if action == "remove_moderator":
                # Remove from moderator group
                user.groups.remove(moderator_group)
                messages.success(request, f"User '{user.username}' is no longer a moderator.")

            elif action == "add_moderator":
                # Add to moderator group
                user.groups.add(moderator_group)
                messages.success(request, f"User '{user.username}' is now a moderator.")

    # Get regular users (not moderators or admins)
    regular_users = User.objects.exclude(Q(groups=moderator_group) | Q(is_staff=True) | Q(is_superuser=True)).order_by("username")

    context = {"active_page": "moderators", "moderators": moderators, "regular_users": regular_users}

    return render(request, "custom_admin/moderators.html", context)


@custom_admin_required
def custom_admin_pending_view(request):
    """View for all pending items"""
    # Get all pending items (PDA and Forum)
    pending_pda = PublicDeepfakeArchive.objects.filter(is_approved=False, review_date__isnull=True).order_by("-submission_date")

    pending_threads = ForumThread.objects.filter(approval_status="pending").order_by("-created_at")

    # Create a unified list of pending items
    pending_items = []

    for pda in pending_pda:
        item = {
            "id": pda.id,
            "title": pda.title,
            "type": "PDA Submission",
            "author": pda.user.user.username,
            "date": pda.submission_date,
            "details_url": reverse("custom_admin_pda_detail", args=[pda.id]),
            "approve_url": reverse("custom_admin_pda_approve", args=[pda.id]),
            "reject_url": reverse("custom_admin_pda_reject", args=[pda.id]),
        }
        pending_items.append(item)

    for thread in pending_threads:
        item = {
            "id": thread.id,
            "title": thread.title,
            "type": "Forum Thread",
            "author": thread.author.user.username,
            "date": thread.created_at,
            "details_url": reverse("custom_admin_forum_thread", args=[thread.id]),
            "approve_url": reverse("custom_admin_forum_approve", args=[thread.id]),
            "reject_url": reverse("custom_admin_forum_reject", args=[thread.id]),
        }
        pending_items.append(item)

    # Sort by date (newest first)
    pending_items.sort(key=lambda x: x["date"], reverse=True)

    # Pagination
    paginator = Paginator(pending_items, 20)  # 20 items per page
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except:
        page_obj = paginator.page(1)

    context = {
        "active_page": "pending",
        "pending_items": page_obj,
        "total_pending": len(pending_items),
        "pda_pending_count": pending_pda.count(),
        "forum_pending_count": pending_threads.count(),
    }

    return render(request, "custom_admin/pending.html", context)


@login_required
def custom_admin_knowledge_base_list_view(request):
    """View for listing and managing knowledge base articles"""
    # Check if user is staff member
    if not request.user.is_staff:
        messages.error(request, "Staff privileges required to access this page.")
        return redirect("custom_admin_login")
    try:
        # Get filter parameters
        topic_id = request.GET.get("topic_id")
        search_query = request.GET.get("search")
        page = request.GET.get("page", 1)

        # Get articles using controller
        result = kb_controller.get_articles(topic_id=topic_id, page=page, items_per_page=20, search_query=search_query)  # Show more items in admin panel

        # Get topics for filter options
        topics = KnowledgeBaseTopic.objects.filter(is_active=True)
        topics = topics.annotate(article_count=Count("knowledgebasearticle"))

        # Check if any filter is applied
        is_filtered = bool(topic_id or search_query)

        # Prepare context
        context = {
            "articles": result.get("articles", []),
            "page": result.get("page", 1),
            "pages": result.get("pages", 1),
            "total": result.get("total", 0),
            "topics": topics,
            "selected_topic_id": topic_id,
            "search_query": search_query,
            "is_filtered": is_filtered,
            "title": "Knowledge Base Management",
            "section": "knowledge_base",
            "page_range": range(1, result.get("pages", 1) + 1),
        }

        return render(request, "custom_admin/knowledge_base_list.html", context)

    except Exception as e:
        logger.error(f"Error in knowledge base admin list view: {str(e)}")
        messages.error(request, f"Error loading knowledge base: {str(e)}")
        return redirect("custom_admin_dashboard")


@login_required
def custom_admin_knowledge_base_create_view(request):
    """View for creating a new knowledge base article"""
    # Check if user is staff member
    if not request.user.is_staff:
        messages.error(request, "Staff privileges required to access this page.")
        return redirect("custom_admin_login")
    try:
        if request.method == "POST":
            # Extract form data
            title = request.POST.get("title")
            content = request.POST.get("content")
            topic_id = request.POST.get("topic_id")
            banner_image = request.POST.get("banner_image")

            # Get attachments
            attachments = []
            for file_name in request.FILES:
                if file_name != "banner_image_file":  # Skip banner image if it was uploaded as a file
                    attachments.append(request.FILES[file_name])

            # Use admin user as author
            author_id = request.user.userdata.id

            # Create article
            result = kb_controller.create_article(
                title=title, content=content, author_id=author_id, topic_id=topic_id, attachments=attachments, banner_image=banner_image
            )

            if result.get("success", False):
                messages.success(request, "Knowledge base article created successfully")
                return redirect("custom_admin_knowledge_base_detail", article_id=result["article"]["id"])
            else:
                messages.error(request, result.get("error", "Unknown error creating article"))

        # Get topics for form options
        topics = KnowledgeBaseTopic.objects.filter(is_active=True)

        context = {"topics": topics, "title": "Create Knowledge Base Article", "section": "knowledge_base"}

        return render(request, "custom_admin/knowledge_base_form.html", context)

    except Exception as e:
        logger.error(f"Error in knowledge base admin create view: {str(e)}")
        messages.error(request, f"Error creating article: {str(e)}")
        return redirect("custom_admin_knowledge_base_list")


@login_required
def custom_admin_knowledge_base_detail_view(request, article_id):
    """View for viewing a knowledge base article details"""
    # Check if user is staff member
    if not request.user.is_staff:
        messages.error(request, "Staff privileges required to access this page.")
        return redirect("custom_admin_login")
    try:
        # Get article details
        result = kb_controller.get_article_detail(article_id, track_view=False)

        if not result.get("success", False):
            messages.error(request, result.get("error", "Article not found"))
            return redirect("custom_admin_knowledge_base_list")

        context = {"article": result["article"], "title": f"Article: {result['article']['title']}", "section": "knowledge_base"}

        return render(request, "custom_admin/knowledge_base_detail.html", context)

    except Exception as e:
        logger.error(f"Error in knowledge base admin detail view: {str(e)}")
        messages.error(request, f"Error viewing article: {str(e)}")
        return redirect("custom_admin_knowledge_base_list")


@login_required
def custom_admin_knowledge_base_edit_view(request, article_id):
    """View for editing a knowledge base article"""
    # Check if user is staff member
    if not request.user.is_staff:
        messages.error(request, "Staff privileges required to access this page.")
        return redirect("custom_admin_login")
    try:
        # Get article to edit
        result = kb_controller.get_article_detail(article_id, track_view=False)

        if not result.get("success", False):
            messages.error(request, result.get("error", "Article not found"))
            return redirect("custom_admin_knowledge_base_list")

        article = result["article"]

        if request.method == "POST":
            # Extract form data
            title = request.POST.get("title")
            content = request.POST.get("content")
            topic_id = request.POST.get("topic_id")
            banner_image = request.POST.get("banner_image")

            # Get attachments
            attachments = None
            if request.FILES:
                attachments = []
                for file_name in request.FILES:
                    if file_name != "banner_image_file":  # Skip banner image if it was uploaded as a file
                        attachments.append(request.FILES[file_name])

            # Update article
            update_result = kb_controller.update_article(
                article_id=article_id, title=title, content=content, topic_id=topic_id, attachments=attachments, banner_image=banner_image
            )

            if update_result.get("success", False):
                messages.success(request, "Knowledge base article updated successfully")
                return redirect("custom_admin_knowledge_base_detail", article_id=article_id)
            else:
                messages.error(request, update_result.get("error", "Unknown error updating article"))

        # Get topics for form options
        topics = KnowledgeBaseTopic.objects.filter(is_active=True)

        context = {
            "article": article,
            "topics": topics,
            "title": f"Edit Article: {article['title']}",
            "section": "knowledge_base",
            "is_edit": True,
        }

        return render(request, "custom_admin/knowledge_base_form.html", context)

    except Exception as e:
        logger.error(f"Error in knowledge base admin edit view: {str(e)}")
        messages.error(request, f"Error editing article: {str(e)}")
        return redirect("custom_admin_knowledge_base_list")


@login_required
def custom_admin_knowledge_base_delete_view(request, article_id):
    """View for deleting a knowledge base article"""
    # Check if user is admin (superuser or staff)
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Admin privileges required to access this page.")
        return redirect("custom_admin_login")
    try:
        if request.method == "POST":
            # Delete article
            result = kb_controller.delete_article(article_id)

            if result.get("success", False):
                messages.success(request, "Knowledge base article deleted successfully")
            else:
                messages.error(request, result.get("error", "Unknown error deleting article"))

            return redirect("custom_admin_knowledge_base_list")

        # Get article details for confirmation
        result = kb_controller.get_article_detail(article_id, track_view=False)

        if not result.get("success", False):
            messages.error(request, result.get("error", "Article not found"))
            return redirect("custom_admin_knowledge_base_list")

        context = {"article": result["article"], "title": f"Delete Article: {result['article']['title']}", "section": "knowledge_base"}

        return render(request, "custom_admin/knowledge_base_delete.html", context)

    except Exception as e:
        logger.error(f"Error in knowledge base admin delete view: {str(e)}")
        messages.error(request, f"Error deleting article: {str(e)}")
        return redirect("custom_admin_knowledge_base_list")


@login_required
def custom_admin_knowledge_base_topics_view(request):
    """View for managing knowledge base topics"""
    # Check if user is admin (superuser or staff)
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Admin privileges required to access this page.")
        return redirect("custom_admin_login")
    try:
        # Handle topic creation
        if request.method == "POST":
            if "create" in request.POST:
                name = request.POST.get("name")
                description = request.POST.get("description", "")
                icon = request.POST.get("icon", "")

                if name:
                    # Create topic
                    topic = KnowledgeBaseTopic.objects.create(name=name, description=description, icon=icon)
                    messages.success(request, f"Topic '{name}' created successfully")
                else:
                    messages.error(request, "Topic name is required")

            # Handle topic update
            elif "update" in request.POST:
                topic_id = request.POST.get("topic_id")
                name = request.POST.get("name")
                description = request.POST.get("description", "")
                icon = request.POST.get("icon", "")
                is_active = request.POST.get("is_active") == "on"

                if topic_id and name:
                    topic = KnowledgeBaseTopic.objects.get(id=topic_id)
                    topic.name = name
                    topic.description = description
                    topic.icon = icon
                    topic.is_active = is_active
                    topic.save()
                    messages.success(request, f"Topic '{name}' updated successfully")
                else:
                    messages.error(request, "Topic ID and name are required")

            # Handle topic deletion
            elif "delete" in request.POST:
                topic_id = request.POST.get("topic_id")

                if topic_id:
                    topic = KnowledgeBaseTopic.objects.get(id=topic_id)
                    # Check if topic has articles
                    if KnowledgeBaseArticle.objects.filter(topic=topic).exists():
                        topic.is_active = False
                        topic.save()
                        messages.warning(request, f"Topic '{topic.name}' has articles. Marked as inactive instead of deleting.")
                    else:
                        topic_name = topic.name
                        topic.delete()
                        messages.success(request, f"Topic '{topic_name}' deleted successfully")
                else:
                    messages.error(request, "Topic ID is required for deletion")

        # Get all topics with article counts
        topics = KnowledgeBaseTopic.objects.all()
        topics = topics.annotate(article_count=Count("knowledgebasearticle"))

        context = {"topics": topics, "title": "Manage Knowledge Base Topics", "section": "knowledge_base"}

        return render(request, "custom_admin/knowledge_base_topics.html", context)

    except Exception as e:
        logger.error(f"Error in knowledge base admin topics view: {str(e)}")
        messages.error(request, f"Error managing topics: {str(e)}")
        return redirect("custom_admin_knowledge_base_list")


def admin_upload_image(request):
    """
    Admin-only endpoint to upload images for knowledge base articles
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

    try:
        image_file = request.FILES.get("file")
        if not image_file:
            return JsonResponse({"success": False, "error": "No image file provided"}, status=400)

        # Determine where to store the image based on purpose
        # Default to inline images (embedded within content)
        image_purpose = request.POST.get("purpose", "inline")

        if image_purpose == "banner":
            subdir = "banners"
            prefix = "kb-banner"
        elif image_purpose == "inline":
            subdir = "inline"
            prefix = "kb-inline"
        else:
            subdir = "images"
            prefix = "kb-img"

        # Generate unique identifier with proper prefix
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        attachment_identifier = f"{prefix}-{unique_id}-{timestamp}"
        original_filename = image_file.name

        # Ensure directory exists
        upload_dir = os.path.join(settings.MEDIA_ROOT, "knowledge_base", subdir)
        os.makedirs(upload_dir, exist_ok=True)

        # Save file
        file_extension = os.path.splitext(original_filename)[1].lower()
        filename = f"{attachment_identifier}-{original_filename}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb+") as destination:
            for chunk in image_file.chunks():
                destination.write(chunk)

        # Store path relative to MEDIA_ROOT
        rel_path = f"knowledge_base/{subdir}/{filename}"

        # Convert to public URL using URLHelper
        public_url = URLHelper.convert_to_public_url(file_path)

        return JsonResponse({"success": True, "location": public_url})
    except Exception as e:
        logger.error(f"Error in admin_upload_image: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
