"""
Public API Services - Controllers
This file contains controllers for both API Key management and API authentication
"""

import time
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import permissions
from rest_framework.throttling import SimpleRateThrottle

from api.models import APIKey, APIUsageLog
from app.models import UserData


class APIKeyController:
    """
    Controller for managing API keys
    """

    @staticmethod
    def create_key(
        user_data, name, expires_days=None, daily_limit=1000, can_use_deepfake_detection=True, can_use_ai_text_detection=True, can_use_ai_media_detection=True
    ):
        """
        Create a new API key for a user
        """
        expires_at = None
        if expires_days:
            expires_at = timezone.now() + timezone.timedelta(days=expires_days)

        api_key = APIKey(
            user=user_data,
            name=name,
            expires_at=expires_at,
            daily_limit=daily_limit,
            can_use_deepfake_detection=can_use_deepfake_detection,
            can_use_ai_text_detection=can_use_ai_text_detection,
            can_use_ai_media_detection=can_use_ai_media_detection,
        )
        api_key.save()
        return api_key

    @staticmethod
    def revoke_key(key_id):
        """
        Revoke an API key
        """
        try:
            api_key = APIKey.objects.get(pk=key_id)
            api_key.is_active = False
            api_key.save(update_fields=["is_active"])
            return True
        except APIKey.DoesNotExist:
            return False

    @staticmethod
    def validate_key(key):
        """
        Check if an API key is valid and not expired
        """
        try:
            api_key = APIKey.objects.get(key=key)
            return api_key.is_valid()
        except APIKey.DoesNotExist:
            return False

    @staticmethod
    def check_rate_limit(key):
        """
        Check if the API key has exceeded its daily limit
        Returns False if limit exceeded, True otherwise
        """
        try:
            api_key = APIKey.objects.get(key=key)
            return api_key.update_usage()
        except APIKey.DoesNotExist:
            return False

    @staticmethod
    def get_keys_for_user(user_data):
        """
        Get all API keys for a user
        """
        return APIKey.objects.filter(user=user_data)

    @staticmethod
    def log_api_usage(api_key, endpoint, method, status_code, response_time, ip_address=None, user_agent=None):
        """
        Log API usage for analytics
        """
        APIUsageLog.objects.create(
            api_key=api_key, endpoint=endpoint, method=method, status_code=status_code, response_time=response_time, ip_address=ip_address, user_agent=user_agent
        )


class APIKeyAuthentication(BaseAuthentication):
    """
    Custom authentication class for API keys
    """

    def authenticate(self, request):
        # Get API key from request header
        api_key = request.META.get("HTTP_X_API_KEY") or request.query_params.get("api_key")
        if not api_key:
            return None  # Let other authentication methods handle this

        try:
            # Get the API key object
            key_obj = APIKey.objects.get(key=api_key)

            # Check if key is active and not expired
            if not key_obj.is_valid():
                raise AuthenticationFailed("API key is inactive or expired")

            # Check rate limit
            if not key_obj.update_usage():
                raise AuthenticationFailed("API rate limit exceeded")

            # Return the user and auth object
            return (key_obj.user.user, key_obj)
        except APIKey.DoesNotExist:
            return None

    def authenticate_header(self, request):
        return "X-API-Key"


class HasAPIAccess(permissions.BasePermission):
    """
    Permission class to check if API key has access to a specific endpoint
    """

    def has_permission(self, request, view):
        # Get authentication method
        if not hasattr(request, "auth") or not isinstance(request.auth, APIKey):
            # Not authenticated with API key
            return False

        api_key = request.auth
        endpoint = request.resolver_match.url_name if request.resolver_match else "unknown"

        # Check endpoint-specific permissions
        if endpoint.startswith("deepfake_detection") and not api_key.can_use_deepfake_detection:
            return False
        elif endpoint.startswith("ai_text_detection") and not api_key.can_use_ai_text_detection:
            return False
        elif endpoint.startswith("ai_media_detection") and not api_key.can_use_ai_media_detection:
            return False

        return True


class APIRateLimitThrottle(SimpleRateThrottle):
    """
    Throttle class for API rate limiting
    """

    scope = "api_key"

    def get_cache_key(self, request, view):
        if not hasattr(request, "auth") or not isinstance(request.auth, APIKey):
            return None  # No API key, no rate limiting

        return f"api_throttle_{request.auth.key}"

    def allow_request(self, request, view):
        if not hasattr(request, "auth") or not isinstance(request.auth, APIKey):
            return True  # No API key, no rate limiting

        api_key = request.auth

        # Use the API key's daily limit
        self.rate = f"{api_key.daily_limit}/day"

        return super().allow_request(request, view)
