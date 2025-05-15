import os
import json
import time
import logging
from django.conf import settings
from django.http import JsonResponse
from django.core.files.storage import FileSystemStorage
from rest_framework import status

from api.models import APIKey, APIUsageLog
from app.controllers.ResponseCodesController import get_response_code

logger = logging.getLogger(__name__)


class PublicAPIController:
    """
    Controller for Public API functionality, providing authentication, rate limiting,
    request validation, and response formatting functionality for the public API.
    """

    def __init__(self):
        pass

    @staticmethod
    def authenticate_api_key(api_key_header):
        """
        Authenticates an API key and checks if it's valid

        Args:
            api_key_header (str): The API key from the X-API-Key header

        Returns:
            tuple: (authenticated, api_key_obj, error_response)
                - authenticated (bool): True if authentication successful
                - api_key_obj (APIKey): The API key object if authenticated, None otherwise
                - error_response (dict): Error response if authentication failed, None otherwise
        """
        if not api_key_header:
            error_response = {"success": False, "code": "AUT001", "message": "Missing API key. Please provide your API key in the X-API-Key header."}
            return False, None, error_response

        try:
            api_key = APIKey.objects.get(key=api_key_header)

            # Check if API key is valid (active and not expired)
            if not api_key.is_valid():
                error_response = {"success": False, "code": "AUT001", "message": "Invalid API key. The key is inactive or expired."}
                return False, None, error_response

            # Check if API key has reached its daily limit
            if not api_key.update_usage():
                error_response = {
                    "success": False,
                    "code": "AUT004",
                    "message": f"API key usage limit reached. The limit is {api_key.daily_limit} requests per day.",
                }
                return False, None, error_response

            return True, api_key, None

        except APIKey.DoesNotExist:
            error_response = {"success": False, "code": "AUT001", "message": "Invalid API key. Please check your API key and try again."}
            return False, None, error_response

    @staticmethod
    def log_api_usage(api_key, endpoint, method, status_code, response_time, request):
        """
        Logs an API request to the database for analytics and monitoring

        Args:
            api_key (APIKey): The API key object
            endpoint (str): The API endpoint that was called
            method (str): The HTTP method used
            status_code (int): The HTTP status code of the response
            response_time (float): The time taken to process the request in seconds
            request (HttpRequest): The request object

        Returns:
            None
        """
        ip_address = request.META.get("HTTP_X_FORWARDED_FOR")
        if not ip_address:
            ip_address = request.META.get("REMOTE_ADDR")

        user_agent = request.META.get("HTTP_USER_AGENT")

        APIUsageLog.objects.create(
            api_key=api_key, endpoint=endpoint, method=method, status_code=status_code, response_time=response_time, ip_address=ip_address, user_agent=user_agent
        )

    @staticmethod
    def check_endpoint_permission(api_key, endpoint_type):
        """
        Checks if the API key has permission to access a specific endpoint

        Args:
            api_key (APIKey): The API key object
            endpoint_type (str): The type of endpoint being accessed
                                ('deepfake', 'ai_text', 'ai_media')

        Returns:
            tuple: (has_permission, error_response)
                - has_permission (bool): True if access is allowed
                - error_response (dict): Error response if access is denied, None otherwise
        """
        if endpoint_type == "deepfake" and not api_key.can_use_deepfake_detection:
            error_response = {"success": False, "code": "AUT004", "message": "This API key does not have permission to access the deepfake detection endpoint."}
            return False, error_response

        elif endpoint_type == "ai_text" and not api_key.can_use_ai_text_detection:
            error_response = {"success": False, "code": "AUT004", "message": "This API key does not have permission to access the AI text detection endpoint."}
            return False, error_response

        elif endpoint_type == "ai_media" and not api_key.can_use_ai_media_detection:
            error_response = {"success": False, "code": "AUT004", "message": "This API key does not have permission to access the AI media detection endpoint."}
            return False, error_response

        return True, None

    @staticmethod
    def validate_file(file, allowed_types=None):
        """
        Validates a file upload for size and type restrictions

        Args:
            file: The uploaded file object
            allowed_types (list): List of allowed MIME types

        Returns:
            tuple: (is_valid, error_response)
                - is_valid (bool): True if file is valid
                - error_response (dict): Error response if validation failed, None otherwise
        """
        if not file:
            error_response = {"success": False, "code": "FIL001", "message": "No file was provided. Please upload a file."}
            return False, error_response

        # Check file size (max 25MB)
        if file.size > 25 * 1024 * 1024:
            error_response = {"success": False, "code": "FIL002", "message": "File too large. Maximum file size is 25MB."}
            return False, error_response

        # Check file type if specified
        if allowed_types:
            content_type = file.content_type
            if content_type not in allowed_types:
                error_response = {
                    "success": False,
                    "code": "FIL003",
                    "message": f"Unsupported file type: {content_type}. Allowed types: {', '.join(allowed_types)}",
                }
                return False, error_response

        return True, None

    @staticmethod
    def validate_text_input(text, min_length=50):
        """
        Validates text input for analysis

        Args:
            text (str): The input text
            min_length (int): Minimum required text length

        Returns:
            tuple: (is_valid, error_response)
                - is_valid (bool): True if text is valid
                - error_response (dict): Error response if validation failed, None otherwise
        """
        if not text:
            error_response = {"success": False, "code": "TXT001", "message": "No text was provided. Please provide text for analysis."}
            return False, error_response

        if len(text) < min_length:
            error_response = {
                "success": False,
                "code": "TXT002",
                "message": f"Text too short. Please provide at least {min_length} characters for reliable analysis.",
            }
            return False, error_response

        return True, None

    @staticmethod
    def format_success_response(code_key, result, metadata=None):
        """
        Formats a successful API response

        Args:
            code_key (str): The success code key
            result (dict): The result data
            metadata (dict): Optional metadata

        Returns:
            dict: The formatted success response
        """
        response = {"success": True, "code": get_response_code(code_key)["code"], "result": result}

        if metadata:
            response["metadata"] = metadata

        return response

    @staticmethod
    def format_error_response(error_code, message=None):
        """
        Formats an error API response

        Args:
            error_code (str): Error code key
            message (str): Optional custom error message

        Returns:
            dict: The formatted error response
        """
        code_info = get_response_code(error_code)

        return {"success": False, "code": code_info["code"], "message": message if message else code_info["message"]}
