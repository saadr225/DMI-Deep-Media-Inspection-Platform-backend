from django.http import JsonResponse

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.models import AIGeneratedMediaResult, DeepfakeDetectionResult, MediaUpload
from app.contollers.HelpersController import URLHelper
from app.contollers.ResponseCodesController import get_response_code
from app.models import UserData
from api.serializers import UserSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_submissions_history(request):
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)
        user_submissions = MediaUpload.objects.filter(user=user_data)

        # Organize submissions by type
        categorized_history = {
            "deepfake_analysis": [],
            "ai_generated_analysis": [],
            "dual_analysis": [],  # Files analyzed by both methods
            "incomplete_analysis": [],  # Files with no analysis results
        }

        for submission in user_submissions:
            base_entry = {
                "id": submission.id,
                "file": URLHelper.convert_to_public_url(file_path=submission.file.path),
                "original_filename": submission.original_filename,
                "file_type": submission.file_type,
                "upload_date": submission.upload_date,
            }

            df_entry = DeepfakeDetectionResult.objects.filter(media_upload_id=submission.id)
            ai_entry = AIGeneratedMediaResult.objects.filter(media_upload_id=submission.id)

            has_df = df_entry.exists()
            has_ai = ai_entry.exists()

            if has_df:
                base_entry["deepfake_detection"] = {
                    "is_deepfake": df_entry[0].is_deepfake,
                    "confidence_score": df_entry[0].confidence_score,
                    "frames_analyzed": df_entry[0].frames_analyzed,
                    "fake_frames": df_entry[0].fake_frames,
                    "analysis_report": df_entry[0].analysis_report,
                }

            if has_ai:
                base_entry["ai_generated_media"] = {
                    "is_generated": ai_entry[0].is_generated,
                    "confidence_score": ai_entry[0].confidence_score,
                    "analysis_report": ai_entry[0].analysis_report,
                }

            # Categorize based on analysis type
            if has_df and has_ai:
                categorized_history["dual_analysis"].append(base_entry)
            elif has_df:
                categorized_history["deepfake_analysis"].append(base_entry)
            elif has_ai:
                categorized_history["ai_generated_analysis"].append(base_entry)
            else:
                categorized_history["incomplete_analysis"].append(base_entry)

        # Add summary statistics
        summary = {
            "total_submissions": len(user_submissions),
            "deepfake_only_count": len(categorized_history["deepfake_analysis"]),
            "ai_generated_only_count": len(categorized_history["ai_generated_analysis"]),
            "dual_analysis_count": len(categorized_history["dual_analysis"]),
            "incomplete_analysis_count": len(categorized_history["incomplete_analysis"]),
        }

        return JsonResponse(
            {**get_response_code("SUCCESS"), "summary": summary, "data": categorized_history},
            status=status.HTTP_200_OK,
        )
    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("HISTORY_FETCH_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    user = request.user
    user_data = UserData.objects.get(user=user)
    user_response = UserSerializer(user).data
    user_data_response = {
        "user": user_response,
        "user_data": {
            "is_verified": user_data.is_verified,
        },
    }

    return JsonResponse(
        {
            **get_response_code("SUCCESS"),
            "data": user_data_response,
        },
        status=status.HTTP_200_OK,
    )
