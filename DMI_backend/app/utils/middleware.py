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
        current_url = resolve(request.path_info).url_name
        if current_url and current_url.startswith('moderation_') or current_url in [
            'pda_moderation', 'user_management', 'forum_moderation', 
            'analytics_dashboard', 'moderation_settings', 'thread_detail'
        ]:
            # Check if user has access to moderation panel
            if not (request.is_moderator or request.is_admin):
                messages.error(request, "You do not have permission to access the moderation panel.")
                return redirect('home')

        response = self.get_response(request)
        return response 