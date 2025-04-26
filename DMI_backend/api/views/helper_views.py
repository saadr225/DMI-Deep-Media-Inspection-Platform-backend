from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from app.controllers.ResponseCodesController import RESPONSE_CODES


@api_view(["GET"])
@permission_classes([AllowAny])
def get_response_codes(request):
    return JsonResponse(RESPONSE_CODES, status=status.HTTP_200_OK)
