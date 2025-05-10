from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from app.models import UserData

def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser

def is_moderator(user):
    """Check if user is moderator or admin"""
    if user.is_superuser or user.is_staff:
        return True
    
    try:
        user_data = UserData.objects.get(user=user)
        return user_data.is_moderator()
    except UserData.DoesNotExist:
        return False

# Create your views here.
def home(request):
    """Portal page that redirects to admin or moderation panel based on role"""
    if request.user.is_authenticated:
        # Check user roles
        is_user_admin = is_admin(request.user)
        is_user_moderator = is_moderator(request.user)
        
        context = {
            'is_admin': is_user_admin,
            'is_moderator': is_user_moderator,
            'username': request.user.username
        }
        
        # If user has any role, show portal page
        if is_user_admin or is_user_moderator:
            return render(request, 'portal.html', context)
        else:
            messages.info(request, "You don't have access to the admin or moderation panels.")
            return render(request, 'access_denied.html')
    else:
        # For non-authenticated users, show login options
        return render(request, 'portal_login.html')
