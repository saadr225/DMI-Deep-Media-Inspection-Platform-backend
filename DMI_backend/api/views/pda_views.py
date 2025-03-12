import os
import time
import uuid
import shutil
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import JsonResponse
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser

from app.contollers.DeepfakeDetectionController import DeepfakeDetectionPipeline
from app.contollers.MetadataAnalysisController import MetadataAnalysisPipeline
from app.contollers.ResponseCodesController import get_response_code
from app.contollers.HelpersController import URLHelper

from api.models import (
    UserData,
    DeepfakeDetectionResult,
    MediaUploadMetadata,
    MediaUpload,
    PublicDeepfakeArchive,
    DEEPFAKE_CATEGORIES,
)
from api.serializers import FileUploadSerializer

# This should be initialized alongside other controllers in semantic_views.py
# and imported here to avoid duplication
from api.views.semantic_views import deepfake_detection_pipeline, metadata_analysis_pipeline


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, FileUploadParser])
def submit_to_pda(request):
    """
    Submit a deepfake to the Public Deepfake Archive
    """
    file_upload_serializer = FileUploadSerializer(data=request.data)

    if file_upload_serializer.is_valid():
        try:
            # Extract form data
            media_file = file_upload_serializer.validated_data["file"]
            title = request.data.get("title", "Untitled Submission")
            category = request.data.get("category")
            description = request.data.get("description", "")
            context = request.data.get("context", "")
            source_url = request.data.get("source_url", "")

            # Validate category
            valid_categories = [choice[0] for choice in DEEPFAKE_CATEGORIES]
            if category not in valid_categories:
                return JsonResponse(
                    {**get_response_code("INVALID_CATEGORY"), "error": "Invalid category selected."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get user data
            user = request.user
            user_data = UserData.objects.get(user=user)

            # Save file
            fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/pda_submissions/")
            original_filename = media_file.name
            submission_identifier = f"pda-{uuid.uuid4().hex[:8]}-{int(time.time())}"
            filename = fs.save(
                f"{submission_identifier}-{original_filename}",
                media_file,
            )
            file_path = os.path.join(f"{settings.MEDIA_ROOT}/pda_submissions/", filename)

            # Check file type
            file_type = deepfake_detection_pipeline.media_processor.check_media_type(file_path)
            if file_type not in ["Image", "Video"]:
                os.remove(file_path)
                return JsonResponse(
                    {
                        **get_response_code("UNSUPPORTED_FILE_TYPE"),
                        "error": f"File type '{file_type}' not supported.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create PDA submission directly instead of using controller
            pda_submission = PublicDeepfakeArchive.objects.create(
                user=user_data,
                file=file_path,
                title=title,
                category=category,
                description=description,
                context=context,
                source_url=source_url,
                original_filename=original_filename,
                file_type=file_type,
                submission_identifier=submission_identifier,
                is_approved=False,  # Requires moderation by default
            )

            # Extract metadata and analyze for deepfakes
            metadata = metadata_analysis_pipeline.extract_metadata(file_path)

            # Run deepfake detection
            deepfake_results = deepfake_detection_pipeline.process_media(
                media_path=file_path,
                frame_rate=2,
            )

            # Generate file identifier
            file_identifier = deepfake_detection_pipeline.media_processor.generate_combined_hash(
                file_path
            )

            if deepfake_results is not False:
                # Create deepfake detection result
                detection_result = DeepfakeDetectionResult.objects.create(
                    media_upload=None,  # Not linked to regular media upload
                    is_deepfake=deepfake_results["statistics"]["is_deepfake"],
                    confidence_score=deepfake_results["statistics"]["confidence"],
                    frames_analyzed=deepfake_results["statistics"]["total_frames"],
                    fake_frames=deepfake_results["statistics"]["fake_frames"],
                    analysis_report=deepfake_results,
                )

                # Attach detection result to PDA submission directly
                pda_submission.detection_result = detection_result
                pda_submission.save()

                # Create metadata entry for the submission
                MediaUploadMetadata.objects.create(media_upload=None, metadata=metadata)

                status_code = "SUCCESS"
            else:
                # No faces detected
                detection_result = DeepfakeDetectionResult.objects.create(
                    media_upload=None,
                    is_deepfake=False,
                    confidence_score=0.0,
                    frames_analyzed=0,
                    fake_frames=0,
                    analysis_report={
                        "final_verdict": "MEDIA_CONTAINS_NO_FACES",
                        "file_identifier": file_identifier,
                    },
                )

                # Attach detection result directly
                pda_submission.detection_result = detection_result
                pda_submission.save()

                status_code = "MEDIA_CONTAINS_NO_FACES"

            # Return response
            return JsonResponse(
                {
                    **get_response_code(status_code),
                    "data": {
                        "submission_id": pda_submission.id,
                        "submission_identifier": pda_submission.submission_identifier,
                        "status": "Under review" if not pda_submission.is_approved else "Approved",
                    },
                },
                status=status.HTTP_200_OK,
            )

        except UserData.DoesNotExist:
            return JsonResponse(
                {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return JsonResponse(
                {**get_response_code("MEDIA_PROCESSING_ERROR"), "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    else:
        return JsonResponse(
            {**get_response_code("FILE_UPLOAD_ERROR"), "error": file_upload_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_existing_to_pda(request):
    """
    Submit an existing analyzed file to the Public Deepfake Archive
    """
    try:
        # Extract form data
        submission_identifier = request.data.get("submission_identifier")
        title = request.data.get("title", "Untitled Submission")
        category = request.data.get("category")
        description = request.data.get("description", "")
        context = request.data.get("context", "")
        source_url = request.data.get("source_url", "")

        if not submission_identifier:
            return JsonResponse(
                {**get_response_code("INVALID_REQUEST"), "error": "Submission identifier is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate category
        valid_categories_expanded = [
            {"code": choice[0], "name": choice[1]} for choice in DEEPFAKE_CATEGORIES
        ]
        valid_categories = [choice[0] for choice in DEEPFAKE_CATEGORIES]
        if category not in valid_categories:
            return JsonResponse(
                {
                    **get_response_code("INVALID_CATEGORY"),
                    "error": f"Invalid category selected ({category}).",
                    "categories": valid_categories_expanded,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get user data
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Find the existing media upload
        try:
            media_upload = MediaUpload.objects.get(submission_identifier=submission_identifier)

            # Verify this user owns the submission
            if media_upload.user.id != user_data.id:
                return JsonResponse(
                    {**get_response_code("ACCESS_DENIED"), "error": "You don't own this submission."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Find the deepfake detection result
            try:
                detection_result = DeepfakeDetectionResult.objects.get(media_upload=media_upload)
            except DeepfakeDetectionResult.DoesNotExist:
                return JsonResponse(
                    {
                        **get_response_code("INVALID_SUBMISSION"),
                        "error": "No deepfake analysis found for this submission.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get metadata if available
            try:
                metadata = MediaUploadMetadata.objects.get(media_upload=media_upload).metadata
            except MediaUploadMetadata.DoesNotExist:
                metadata = {}

            # Check if already submitted to PDA
            existing_pda = PublicDeepfakeArchive.objects.filter(
                submission_identifier=f"pda-{submission_identifier}"
            ).first()

            if existing_pda:
                return JsonResponse(
                    {
                        **get_response_code("DUPLICATE_SUBMISSION"),
                        "error": "This media has already been submitted to the PDA.",
                        "data": {
                            "submission_identifier": submission_identifier,
                            "pda_submission_identifier": existing_pda.submission_identifier,
                        },
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create a copy of the file for PDA
            pda_submission_identifier = f"pda-{submission_identifier}"
            original_file_path = media_upload.file.path
            original_filename = media_upload.original_filename
            file_type = media_upload.file_type

            # Create directory if it doesn't exist
            pda_dir = os.path.join(settings.MEDIA_ROOT, "pda_submissions")
            os.makedirs(pda_dir, exist_ok=True)

            # Create a new path for the PDA copy
            pda_file_path = os.path.join(pda_dir, f"{pda_submission_identifier}-{original_filename}")

            # Copy the file
            shutil.copy2(original_file_path, pda_file_path)

            # Create the PDA submission directly
            pda_submission = PublicDeepfakeArchive.objects.create(
                user=user_data,
                file=pda_file_path,
                title=title,
                category=category,
                description=description,
                context=context,
                source_url=source_url,
                original_filename=original_filename,
                file_type=file_type,
                submission_identifier=pda_submission_identifier,
                detection_result=detection_result,
                is_approved=False,  # Requires moderation by default
            )

            pda_submission.save()

            # Return success response
            return JsonResponse(
                {
                    **get_response_code("SUCCESS"),
                    "data": {
                        "submission_identifier": submission_identifier,
                        "pda_submission_identifier": pda_submission.submission_identifier,
                        "status": "Under review" if not pda_submission.is_approved else "Approved",
                    },
                },
                status=status.HTTP_200_OK,
            )

        except MediaUpload.DoesNotExist:
            return JsonResponse(
                {
                    **get_response_code("SUBMISSION_NOT_FOUND"),
                    "error": "The specified submission was not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def browse_pda(request):
    """
    Browse, search and filter PDA submissions
    """
    try:
        query = request.GET.get("q", None)
        category = request.GET.get("category", None)
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))

        # Search PDA submissions directly instead of using controller
        submissions = PublicDeepfakeArchive.objects.filter(is_approved=True)

        if query:
            submissions = submissions.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(context__icontains=query)
            )
        print(category)
        if category:
            submissions = submissions.filter(category=category)

        submissions = submissions.order_by("-submission_date")

        # Simple pagination
        start_index = (page - 1) * limit
        end_index = start_index + limit
        paginated_submissions = submissions[start_index:end_index]

        # Format the response
        results = []
        for submission in paginated_submissions:
            detection_result = submission.detection_result

            result_data = {
                "title": submission.title,
                "category": submission.category,
                "category_display": submission.get_category_display(),
                "submission_identifier": submission.submission_identifier.replace("pda-", ""),
                "pda_submission_identifier": submission.submission_identifier,
                "description": submission.description,
                "context": submission.context,
                "source_url": submission.source_url,
                "file_type": submission.file_type,
                "submission_date": submission.submission_date,
                "file_url": URLHelper.convert_to_public_url(file_path=submission.file.path),
                "detection_result": (
                    {
                        "is_deepfake": detection_result.is_deepfake,
                        "confidence_score": detection_result.confidence_score,
                        "frames_analyzed": detection_result.frames_analyzed,
                        "fake_frames": detection_result.fake_frames,
                    }
                    if detection_result
                    else None
                ),
            }
            results.append(result_data)

        return JsonResponse(
            {
                **get_response_code("SUCCESS"),
                "data": {
                    "results": results,
                    "total": submissions.count(),
                    "page": page,
                    "limit": limit,
                    "categories": [
                        {"code": category[0], "name": category[1]} for category in DEEPFAKE_CATEGORIES
                    ],
                },
            },
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_pda_submission_detail(request, submission_identifier):
    """
    Get detailed information about a specific PDA submission
    """
    try:
        # Get submission directly instead of using controller
        try:
            submission = PublicDeepfakeArchive.objects.get(submission_identifier=submission_identifier)
        except PublicDeepfakeArchive.DoesNotExist:
            return JsonResponse(
                {**get_response_code("NOT_FOUND"), "error": "Submission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not submission.is_approved:
            return JsonResponse(
                {**get_response_code("ACCESS_DENIED"), "error": "This submission is under review."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if this was submitted from an existing MediaUpload
        original_submission_identifier = None
        if submission.submission_identifier.startswith("pda-"):
            # Extract the original submission identifier by removing the "pda-" prefix
            original_submission_identifier = submission.submission_identifier[4:]

        result_data = {
            "id": submission.id,
            "title": submission.title,
            "category": submission.category,
            "category_display": submission.get_category_display(),
            "submission_identifier": submission.submission_identifier,
            "original_submission_identifier": original_submission_identifier,
            "description": submission.description,
            "context": submission.context,
            "source_url": submission.source_url,
            "file_type": submission.file_type,
            "submission_date": submission.submission_date,
            "file_url": URLHelper.convert_to_public_url(file_path=submission.file.path),
        }

        return JsonResponse(
            {**get_response_code("SUCCESS"), "data": result_data},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
