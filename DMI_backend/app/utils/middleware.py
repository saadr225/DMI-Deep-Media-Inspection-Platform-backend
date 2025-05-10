from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve, reverse
from app.models import UserData

class RoleMiddleware:
    """
    Middleware to inject user role into request and handle role-based access
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach user role to request
        if request.user.is_authenticated:
            try:
                user_data = UserData.objects.get(user=request.user)
                request.user_role = user_data.get_role()
                request.is_moderator = user_data.is_moderator()
                request.is_admin = user_data.is_admin()
            except UserData.DoesNotExist:
                request.user_role = "anonymous"
                request.is_moderator = False
                request.is_admin = False
        else:
            request.user_role = "anonymous"
            request.is_moderator = False
            request.is_admin = False

        # Check if this is a moderation panel URL
        try:
            current_url = resolve(request.path_info).url_name
            
            # Skip login check for login pages
            if current_url in ['moderation_login', 'custom_admin_login']:
                return self.get_response(request)
                
            # Moderation panel URLs
            if current_url and (current_url.startswith('moderation_') or current_url in [
                'pda_moderation', 'pda_detail', 'pda_approve', 'pda_reject',
                'forum_moderation', 'thread_detail', 'thread_approve', 'thread_reject',
                'analytics_dashboard', 'moderation_settings', 'reported_content'
            ]):
                # Check if user is authenticated
                if not request.user.is_authenticated:
                    messages.info(request, "Please log in to access the moderation panel.")
                    return redirect('moderation_login')
                    
                # Check if user has access to moderation panel
                if not (request.is_moderator or request.is_admin):
                    messages.error(request, "You do not have permission to access the moderation panel.")
                    return redirect('moderation_login')
                    
            # Admin panel URLs
            if current_url and (current_url.startswith('custom_admin_') or current_url == 'custom_admin_dashboard'):
                # Check if user is authenticated
                if not request.user.is_authenticated:
                    messages.info(request, "Please log in to access the admin panel.")
                    return redirect('custom_admin_login')
                    
                # Check if user has admin access
                if not request.is_admin:
                    messages.error(request, "You do not have permission to access the admin panel.")
                    return redirect('custom_admin_login')
        except:
            # If URL resolution fails, just continue
            pass

        response = self.get_response(request)
        return response 