from django.http import JsonResponse
from api.models import APIKey
from app.controllers.ResponseCodesController import get_response_code


class APIKeyAuthMiddleware:
    """
    Middleware to authenticate API requests using API keys
    This middleware only applies to public API endpoints
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply to public API endpoints
        if request.path.startswith("/api/public-api/"):
            api_key_header = request.META.get("HTTP_X_API_KEY")

            # If no API key is provided, return 403
            if not api_key_header:
                return JsonResponse(
                    {"success": False, "code": "AUT001", "message": "Missing API key. Please provide your API key in the X-API-Key header."}, status=403
                )

            try:
                # Try to get the API key from the database
                api_key = APIKey.objects.get(key=api_key_header)

                # Check if the key is valid
                if not api_key.is_valid():
                    return JsonResponse({"success": False, "code": "AUT001", "message": "Invalid API key. The key is inactive or expired."}, status=403)

                # Set the api_key in request for use in views
                request.api_key = api_key

            except APIKey.DoesNotExist:
                return JsonResponse({"success": False, "code": "AUT001", "message": "Invalid API key. Please check your API key and try again."}, status=403)

        # Continue processing the request
        response = self.get_response(request)
        return response
