import json
import logging
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
from app.controllers.CommunityForumController import CommunityForumController

# Setup logger
logger = logging.getLogger(__name__)

# Initialize forum controller
forum_controller = CommunityForumController()

# Helper functions
def is_moderator(user):
    """Check if user is moderator or admin"""
    if user.is_superuser or user.is_staff:
        return True
    
    try:
        user_data = UserData.objects.get(user=user)
        return user_data.is_moderator()
    except UserData.DoesNotExist:
        return False

def moderator_required(view_func):
    """Decorator for views that require moderator privileges"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('moderation_login')
        
        if not is_moderator(request.user):
            messages.error(request, "You do not have moderator privileges to access this page.")
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def log_moderation_action(moderator, action_type, content_type, content_object=None, content_identifier="", notes=None):
    """Log a moderation action for auditing purposes"""
    try:
        action = ModeratorAction(
            moderator=moderator,
            action_type=action_type,
            content_type=content_type,
            content_identifier=content_identifier,
            notes=notes
        )
        
        # If content_object is provided, link it using Generic Foreign Key
        if content_object:
            from django.contrib.contenttypes.models import ContentType
            content_type_obj = ContentType.objects.get_for_model(content_object.__class__)
            action.content_object_type = content_type_obj
            action.content_object_id = content_object.id
        
        action.save()
        return action
    except Exception as e:
        logger.error(f"Error logging moderation action: {str(e)}")
        return None

# Login / Logout Views
def moderation_login_view(request):
    """Login view for moderation panel"""
    # If already logged in and is moderator, redirect to dashboard
    if request.user.is_authenticated and is_moderator(request.user):
        return redirect('moderation_dashboard')
    
    error_message = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if is_moderator(user):
                login(request, user)
                return redirect('moderation_dashboard')
            else:
                error_message = "You do not have moderator privileges."
        else:
            error_message = "Invalid username or password."
    
    return render(request, 'custom_moderation/login.html', {'error_message': error_message})

@login_required
def moderation_logout_view(request):
    """Logout view for moderation panel"""
    logout(request)
    return redirect('moderation_login')

# Dashboard View
@moderator_required
def moderation_dashboard_view(request):
    """Main dashboard view for moderation panel"""
    # Get counts for the dashboard
    pda_pending_count = PublicDeepfakeArchive.objects.filter(
        is_approved=False, 
        review_date__isnull=True
    ).count()
    
    forum_pending_count = ForumThread.objects.filter(
        approval_status='pending'
    ).count()
    
    # For now, there's no reported content system, so use 0
    # In the future, implement reported content functionality
    reported_count = 0
    
    # Get moderator's recent actions
    moderator_actions = ModeratorAction.objects.filter(
        moderator=request.user
    ).order_by('-timestamp')[:10]
    
    moderator_actions_count = ModeratorAction.objects.filter(
        moderator=request.user,
        timestamp__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    # Get recent items that need moderation
    recent_moderation_items = []
    
    # Get pending PDA submissions
    pda_pending = PublicDeepfakeArchive.objects.filter(
        is_approved=False, 
        review_date__isnull=True
    ).order_by('-submission_date')[:5]
    
    for pda in pda_pending:
        item = {
            'title': pda.title,
            'submission_date': pda.submission_date,
            'type': 'PDA Submission',
            'author': pda.user.user.username,
            'url': reverse('pda_detail', args=[pda.id]),
            'approve_url': reverse('pda_approve', args=[pda.id]),
            'reject_url': reverse('pda_reject', args=[pda.id])
        }
        recent_moderation_items.append(item)
    
    # Get pending forum threads
    forum_pending = ForumThread.objects.filter(
        approval_status='pending'
    ).order_by('-created_at')[:5]
    
    for thread in forum_pending:
        item = {
            'title': thread.title,
            'submission_date': thread.created_at,
            'type': 'Forum Thread',
            'author': thread.author.user.username,
            'url': reverse('thread_detail', args=[thread.id]),
            'approve_url': reverse('thread_approve', args=[thread.id]),
            'reject_url': reverse('thread_reject', args=[thread.id])
        }
        recent_moderation_items.append(item)
    
    # Sort moderation items by date
    recent_moderation_items = sorted(recent_moderation_items, key=lambda x: x['submission_date'], reverse=True)[:5]
    
    # Generate data for charts
    days = 7
    days_labels = []
    pda_data = []
    threads_data = []
    approved_data = []
    
    for i in range(days):
        day = timezone.now() - timedelta(days=days-i-1)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Format date as string
        days_labels.append(day_start.strftime('%Y-%m-%d'))
        
        # Count items for each day
        day_pda = PublicDeepfakeArchive.objects.filter(submission_date__range=(day_start, day_end)).count()
        day_threads = ForumThread.objects.filter(created_at__range=(day_start, day_end)).count()
        
        # Count approved items
        day_approved = (
            PublicDeepfakeArchive.objects.filter(
                is_approved=True, 
                review_date__range=(day_start, day_end)
            ).count() +
            ForumThread.objects.filter(
                approval_status='approved',
                review_date__range=(day_start, day_end)
            ).count()
        )
        
        pda_data.append(day_pda)
        threads_data.append(day_threads)
        approved_data.append(day_approved)
    
    context = {
        'active_page': 'dashboard',
        'pda_pending_count': pda_pending_count,
        'forum_pending_count': forum_pending_count,
        'reported_count': reported_count,
        'pending_count': pda_pending_count + forum_pending_count + reported_count,
        'moderator_actions': moderator_actions,
        'moderator_actions_count': moderator_actions_count,
        'recent_moderation_items': recent_moderation_items,
        'days_labels': json.dumps(days_labels),
        'pda_data': json.dumps(pda_data),
        'threads_data': json.dumps(threads_data),
        'approved_data': json.dumps(approved_data)
    }
    
    return render(request, 'custom_moderation/dashboard.html', context)

# PDA Moderation Views
@moderator_required
def pda_moderation_view(request):
    """View for moderating PDA submissions"""
    # Get all pending submissions
    pending_submissions = PublicDeepfakeArchive.objects.filter(
        review_date__isnull=True
    ).order_by('-submission_date')
    
    # Pagination
    paginator = Paginator(pending_submissions, 10)  # 10 submissions per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'active_page': 'pda_moderation',
        'pending_submissions': page_obj,
        'pending_count': pending_submissions.count(),
    }
    
    return render(request, 'custom_moderation/pda_moderation.html', context)

@moderator_required
def pda_detail_view(request, pda_id):
    """View to see PDA submission details and moderate it"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=pda_id)
    
    context = {
        'active_page': 'pda_moderation',
        'submission': submission,
    }
    
    return render(request, 'custom_moderation/pda_detail.html', context)

@moderator_required
def pda_approve_view(request, pda_id):
    """View to approve a PDA submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=pda_id)
    
    # Update submission
    submission.is_approved = True
    submission.review_date = timezone.now()
    submission.reviewed_by = request.user
    
    if request.method == 'POST':
        # If additional notes were submitted
        submission.review_notes = request.POST.get('review_notes', '')
    
    submission.save()
    
    # Log the action
    log_moderation_action(
        moderator=request.user,
        action_type="approve",
        content_type="pda",
        content_object=submission,
        content_identifier=f"PDA: {submission.title}",
        notes=submission.review_notes
    )
    
    messages.success(request, f"PDA submission '{submission.title}' has been approved.")
    return redirect('pda_moderation')

@moderator_required
def pda_reject_view(request, pda_id):
    """View to reject a PDA submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=pda_id)
    
    # Update submission
    submission.is_approved = False
    submission.review_date = timezone.now()
    submission.reviewed_by = request.user
    
    if request.method == 'POST':
        # If additional notes were submitted
        submission.review_notes = request.POST.get('review_notes', '')
    
    submission.save()
    
    # Log the action
    log_moderation_action(
        moderator=request.user,
        action_type="reject",
        content_type="pda",
        content_object=submission,
        content_identifier=f"PDA: {submission.title}",
        notes=submission.review_notes
    )
    
    messages.success(request, f"PDA submission '{submission.title}' has been rejected.")
    return redirect('pda_moderation')

# Forum Moderation Views
@moderator_required
def forum_moderation_view(request):
    """View for moderating forum threads"""
    # Get filter parameter
    filter_type = request.GET.get("filter", "pending")
    
    # Apply filters based on selection
    if filter_type == "pending":
        threads = ForumThread.objects.filter(approval_status="pending").order_by("-created_at")
    elif filter_type == "reported":
        # For now, there's no reported content system, so use an empty queryset
        threads = ForumThread.objects.none()
    else:
        threads = ForumThread.objects.all().order_by("-created_at")
    
    # Pagination
    paginator = Paginator(threads, 10)  # 10 threads per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'active_page': 'forum_moderation',
        'threads': page_obj,
        'filter_type': filter_type,
        'pending_count': ForumThread.objects.filter(approval_status="pending").count(),
    }
    
    return render(request, 'custom_moderation/forum_moderation.html', context)

@moderator_required
def thread_detail_view(request, thread_id):
    """View to see thread details and moderate it"""
    thread = get_object_or_404(
        ForumThread.objects.select_related("author__user", "topic").prefetch_related(
            "tags", "replies"
        ),
        id=thread_id,
    )
    
    # Get replies for the thread
    replies = (
        ForumReply.objects.filter(thread=thread)
        .select_related("author__user")
        .order_by("created_at")
    )
    
    # Handle form submissions (approve/reject/delete reply)
    if request.method == "POST":
        action = request.POST.get("action")
        
        if action in ["approve", "reject"]:
            # Use the controller to moderate the thread
            result = forum_controller.moderate_thread(
                thread_id=thread.id,
                approval_status="approved" if action == "approve" else "rejected",
                moderator=request.user,
            )
            
            # Log the moderation action
            log_moderation_action(
                moderator=request.user,
                action_type=action,
                content_type="thread",
                content_object=thread,
                content_identifier=f"Thread: {thread.title}"
            )
            
            # Show success message
            if result["success"]:
                messages.success(request, f"Thread '{thread.title}' has been {action}d successfully.")
            else:
                messages.error(request, f"Error: {result['error']}")
            
            return redirect('forum_moderation')
            
        elif action == "delete_reply":
            reply_id = request.POST.get("reply_id")
            if reply_id:
                try:
                    reply = ForumReply.objects.get(id=reply_id, thread=thread)
                    reply.is_deleted = True
                    reply.save()
                    
                    # Log the action
                    log_moderation_action(
                        moderator=request.user,
                        action_type="delete",
                        content_type="reply",
                        content_object=reply,
                        content_identifier=f"Reply from {reply.author.user.username} on thread: {thread.title}"
                    )
                    
                    messages.success(request, "Reply has been deleted successfully.")
                except ForumReply.DoesNotExist:
                    messages.error(request, "Error: Reply not found.")
            else:
                messages.error(request, "Error: No reply specified for deletion.")
    
    context = {
        'active_page': 'forum_moderation',
        'thread': thread,
        'replies': replies,
    }
    
    return render(request, 'custom_moderation/thread_detail.html', context)

@moderator_required
def thread_approve_view(request, thread_id):
    """View to approve a forum thread"""
    thread = get_object_or_404(ForumThread, id=thread_id)
    
    # Use the controller to moderate the thread
    result = forum_controller.moderate_thread(
        thread_id=thread.id,
        approval_status="approved",
        moderator=request.user,
    )
    
    # Log the moderation action
    log_moderation_action(
        moderator=request.user,
        action_type="approve",
        content_type="thread",
        content_object=thread,
        content_identifier=f"Thread: {thread.title}"
    )
    
    if result["success"]:
        messages.success(request, f"Thread '{thread.title}' has been approved successfully.")
    else:
        messages.error(request, f"Error: {result['error']}")
    
    return redirect('forum_moderation')

@moderator_required
def thread_reject_view(request, thread_id):
    """View to reject a forum thread"""
    thread = get_object_or_404(ForumThread, id=thread_id)
    
    # Use the controller to moderate the thread
    result = forum_controller.moderate_thread(
        thread_id=thread.id,
        approval_status="rejected",
        moderator=request.user,
    )
    
    # Log the moderation action
    log_moderation_action(
        moderator=request.user,
        action_type="reject",
        content_type="thread",
        content_object=thread,
        content_identifier=f"Thread: {thread.title}"
    )
    
    if result["success"]:
        messages.success(request, f"Thread '{thread.title}' has been rejected successfully.")
    else:
        messages.error(request, f"Error: {result['error']}")
    
    return redirect('forum_moderation')

# Additional views for the moderation panel can be added as needed 

@moderator_required
def reported_content_view(request):
    """View for reported content that requires moderation"""
    # This is a placeholder for future implementation of reported content
    # Currently, there is no reported content system
    
    context = {
        'active_page': 'reported_content',
        'reported_items': [],
        'reported_count': 0
    }
    
    return render(request, 'custom_moderation/reported_content.html', context)

@moderator_required
def analytics_dashboard_view(request):
    """View for analytics dashboard"""
    # Get date range
    days = int(request.GET.get('days', 30))
    
    # Calculate date ranges
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Get stats for the period
    pda_submitted = PublicDeepfakeArchive.objects.filter(
        submission_date__range=(start_date, end_date)
    ).count()
    
    pda_approved = PublicDeepfakeArchive.objects.filter(
        is_approved=True,
        review_date__range=(start_date, end_date)
    ).count()
    
    pda_rejected = PublicDeepfakeArchive.objects.filter(
        is_approved=False,
        review_date__range=(start_date, end_date)
    ).count()
    
    threads_submitted = ForumThread.objects.filter(
        created_at__range=(start_date, end_date)
    ).count()
    
    threads_approved = ForumThread.objects.filter(
        approval_status='approved',
        review_date__range=(start_date, end_date)
    ).count()
    
    threads_rejected = ForumThread.objects.filter(
        approval_status='rejected',
        review_date__range=(start_date, end_date)
    ).count()
    
    # Get moderator activity
    moderator_actions = ModeratorAction.objects.filter(
        timestamp__range=(start_date, end_date)
    ).values('moderator__username').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Generate time series data for charts
    time_period = []
    pda_series = []
    thread_series = []
    actions_series = []
    
    # For daily data (up to 90 days)
    if days <= 90:
        for i in range(days):
            day = start_date + timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Format date for display
            time_period.append(day_start.strftime('%Y-%m-%d'))
            
            # Get counts for the day
            day_pda = PublicDeepfakeArchive.objects.filter(
                submission_date__range=(day_start, day_end)
            ).count()
            
            day_threads = ForumThread.objects.filter(
                created_at__range=(day_start, day_end)
            ).count()
            
            day_actions = ModeratorAction.objects.filter(
                timestamp__range=(day_start, day_end)
            ).count()
            
            pda_series.append(day_pda)
            thread_series.append(day_threads)
            actions_series.append(day_actions)
    # For weekly data (more than 90 days)
    else:
        # Calculate number of weeks
        num_weeks = days // 7
        for i in range(num_weeks):
            week_start = start_date + timedelta(days=i*7)
            week_end = week_start + timedelta(days=6)
            
            # Format date range for display
            time_period.append(f"{week_start.strftime('%m/%d')} - {week_end.strftime('%m/%d')}")
            
            # Get counts for the week
            week_pda = PublicDeepfakeArchive.objects.filter(
                submission_date__range=(week_start, week_end)
            ).count()
            
            week_threads = ForumThread.objects.filter(
                created_at__range=(week_start, week_end)
            ).count()
            
            week_actions = ModeratorAction.objects.filter(
                timestamp__range=(week_start, week_end)
            ).count()
            
            pda_series.append(week_pda)
            thread_series.append(week_threads)
            actions_series.append(week_actions)
    
    context = {
        'active_page': 'analytics',
        'days': days,
        'pda_submitted': pda_submitted,
        'pda_approved': pda_approved,
        'pda_rejected': pda_rejected,
        'threads_submitted': threads_submitted,
        'threads_approved': threads_approved,
        'threads_rejected': threads_rejected,
        'total_moderated': pda_approved + pda_rejected + threads_approved + threads_rejected,
        'total_content': pda_submitted + threads_submitted,
        'approval_rate': round((pda_approved + threads_approved) / 
                             (pda_submitted + threads_submitted) * 100 
                             if (pda_submitted + threads_submitted) > 0 else 0, 1),
        'moderator_actions': moderator_actions,
        'time_period': json.dumps(time_period),
        'pda_series': json.dumps(pda_series),
        'thread_series': json.dumps(thread_series),
        'actions_series': json.dumps(actions_series)
    }
    
    return render(request, 'custom_moderation/analytics_dashboard.html', context)

@moderator_required
def moderation_settings_view(request):
    """View for moderation settings"""
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        try:
            # Update notification settings
            notification_settings = {
                'email_notifications': 'email_notifications' in request.POST,
                'browser_notifications': 'browser_notifications' in request.POST,
                'notify_on_new_pda': 'notify_on_new_pda' in request.POST,
                'notify_on_new_thread': 'notify_on_new_thread' in request.POST,
                'notify_on_reports': 'notify_on_reports' in request.POST,
            }
            
            # Save to user's UserData
            user_data, created = UserData.objects.get_or_create(user=request.user)
            
            # Store notification settings in the metadata field
            if not user_data.metadata:
                user_data.metadata = {}
            
            user_data.metadata['notification_settings'] = notification_settings
            user_data.save()
            
            success_message = "Settings updated successfully."
        except Exception as e:
            error_message = f"Error updating settings: {str(e)}"
    
    # Get current settings
    try:
        user_data = UserData.objects.get(user=request.user)
        notification_settings = user_data.metadata.get('notification_settings', {}) if user_data.metadata else {}
    except UserData.DoesNotExist:
        notification_settings = {}
    
    context = {
        'active_page': 'settings',
        'success_message': success_message,
        'error_message': error_message,
        'notification_settings': notification_settings
    }
    
    return render(request, 'custom_moderation/settings.html', context)

@moderator_required
def moderation_profile_view(request):
    """View for moderator profile"""
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        try:
            # Update profile information
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            
            # Update password if provided
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            # Update basic info
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            
            # Handle password update if provided
            if current_password and new_password and confirm_password:
                if not request.user.check_password(current_password):
                    error_message = "Current password is incorrect."
                elif new_password != confirm_password:
                    error_message = "New passwords do not match."
                else:
                    request.user.set_password(new_password)
                    success_message = "Profile and password updated successfully. Please log in again."
            else:
                success_message = "Profile updated successfully."
            
            request.user.save()
            
            # Redirect to login if password was changed
            if current_password and new_password and confirm_password and not error_message:
                logout(request)
                return redirect('moderation_login')
            
        except Exception as e:
            error_message = f"Error updating profile: {str(e)}"
    
    # Get moderation activity stats
    activity_stats = {
        'total_actions': ModeratorAction.objects.filter(moderator=request.user).count(),
        'pda_approved': ModeratorAction.objects.filter(
            moderator=request.user, 
            action_type='approve', 
            content_type='pda'
        ).count(),
        'pda_rejected': ModeratorAction.objects.filter(
            moderator=request.user, 
            action_type='reject', 
            content_type='pda'
        ).count(),
        'threads_approved': ModeratorAction.objects.filter(
            moderator=request.user, 
            action_type='approve', 
            content_type='forum_thread'
        ).count(),
        'threads_rejected': ModeratorAction.objects.filter(
            moderator=request.user, 
            action_type='reject', 
            content_type='forum_thread'
        ).count(),
    }
    
    # Get recent actions
    recent_actions = ModeratorAction.objects.filter(
        moderator=request.user
    ).order_by('-timestamp')[:10]
    
    context = {
        'active_page': 'profile',
        'success_message': success_message,
        'error_message': error_message,
        'activity_stats': activity_stats,
        'recent_actions': recent_actions,
        'join_date': request.user.date_joined
    }
    
    return render(request, 'custom_moderation/profile.html', context) 