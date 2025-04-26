from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.models import PublicDeepfakeArchive
from app.controllers.ResponseCodesController import get_response_code
from app.models import UserData


class ModeratorPermission:
    """Custom permission class for moderators"""

    def has_permission(self, request, view):
        try:
            user_data = UserData.objects.get(user=request.user)
            return user_data.is_moderator() or user_data.is_admin()
        except UserData.DoesNotExist:
            return False


@staff_member_required
def approve_submission(request, submission_id):
    """Admin view to approve a submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=submission_id)
    submission.is_approved = True
    submission.save()
    return HttpResponseRedirect(reverse("admin:api_publicdeepfakearchive_changelist"))


@staff_member_required
def reject_submission(request, submission_id):
    """Admin view to reject (delete) a submission"""
    submission = get_object_or_404(PublicDeepfakeArchive, id=submission_id)
    submission.delete()
    return HttpResponseRedirect(reverse("admin:api_publicdeepfakearchive_changelist"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pending_submissions(request):
    """API endpoint to get pending submissions for moderators"""
    try:
        user_data = UserData.objects.get(user=request.user)
        if not (user_data.is_moderator() or request.user.is_staff):
            return JsonResponse(
                {**get_response_code("ACCESS_DENIED"), "error": "Moderator privileges required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        pending = PublicDeepfakeArchive.objects.filter(is_approved=False).order_by("-submission_date")

        results = []
        for submission in pending:
            results.append(
                {
                    "id": submission.id,
                    "title": submission.title,
                    "category": submission.category,
                    "submission_identifier": submission.submission_identifier,
                    "submission_date": submission.submission_date,
                    "description": submission.description,
                    "file_type": submission.file_type,
                }
            )

        return JsonResponse(
            {**get_response_code("SUCCESS"), "data": results}, status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def moderate_submission(request, submission_id):
    """API endpoint to approve or reject a submission"""
    try:
        user_data = UserData.objects.get(user=request.user)
        if not (user_data.is_moderator() or request.user.is_staff):
            return JsonResponse(
                {**get_response_code("ACCESS_DENIED"), "error": "Moderator privileges required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        action = request.data.get("action")
        if action not in ["approve", "reject"]:
            return JsonResponse(
                {
                    **get_response_code("INVALID_REQUEST"),
                    "error": "Invalid action. Use 'approve' or 'reject'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        submission = get_object_or_404(PublicDeepfakeArchive, id=submission_id)

        if action == "approve":
            submission.is_approved = True
            submission.save()
            message = "Submission approved successfully"
        else:
            submission.delete()
            message = "Submission rejected successfully"

        return JsonResponse(
            {**get_response_code("SUCCESS"), "message": message}, status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
