from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

from app.models import UserData


def role_required(required_roles=None):
    """
    Decorator to check if user has the required role(s)
    required_roles can be a single role or a list of roles
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"/login/?next={request.path}")

            try:
                user_data = UserData.objects.get(user=request.user)
            except UserData.DoesNotExist:
                return HttpResponseForbidden("Access denied")

            user_role = user_data.get_role()

            # If no specific role is required, just check authentication
            if required_roles is None:
                return view_func(request, *args, **kwargs)

            # Convert required_roles to a list if it's not already
            roles = required_roles if isinstance(required_roles, list) else [required_roles]

            # Check if user has any of the required roles
            if user_role in roles:
                return view_func(request, *args, **kwargs)
            else:
                return HttpResponseForbidden("You don't have permission to access this page")

        return wrapper

    return decorator


def moderator_required(view_func):
    """
    Decorator to restrict view access to moderators only.
    This combines login_required with a check for moderator status.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Ensure the user is logged in
        if not request.user.is_authenticated:
            return redirect("login")

        try:
            # Check if user is a moderator or admin
            user_data = UserData.objects.get(user=request.user)
            if user_data.is_moderator() or request.user.is_staff:
                return view_func(request, *args, **kwargs)
            else:
                # User is logged in but not a moderator
                messages.error(request, "You do not have moderator privileges to access this page.")
                return redirect("home")  # Redirect to home or appropriate page

        except UserData.DoesNotExist:
            # User exists but UserData does not
            messages.error(request, "User profile not found. Please contact support.")
            return redirect("home")

    return _wrapped_view


def admin_required(view_func):
    """
    Decorator to restrict view access to administrators only.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Ensure the user is logged in
        if not request.user.is_authenticated:
            return redirect("login")

        # Check if user is staff/admin
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        else:
            # User is logged in but not an admin
            messages.error(request, "Administrator privileges required to access this page.")
            return redirect("home")  # Redirect to home or appropriate page

    return _wrapped_view


def verified_required(view_func):
    """Decorator to check if user is verified"""
    return role_required(["verified", "moderator", "staff", "admin"])(view_func)
