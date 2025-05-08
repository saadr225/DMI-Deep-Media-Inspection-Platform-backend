from itertools import count
import os
import logging
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, FileUploadParser, JSONParser

from app.controllers.CommunityForumController import CommunityForumController
from app.controllers.ResponseCodesController import get_response_code
from app.models import UserData
from api.models import (
    ForumReaction,
    ForumThread,
    ForumReply,
    ForumAnalytics,
    ForumLike,
    ForumTag,
    ForumTopic,
)

logger = logging.getLogger(__name__)

# Initialize the controller
forum_controller = CommunityForumController()


# Thread Management Views
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def create_thread(request):
    """
    Create a new thread in the community forum

    Required fields:
    - title: Thread title
    - content: Thread content
    - topic_id: ID of the topic

    Optional fields:
    - tags: List of tag IDs
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get required fields
        title = request.data.get("title")
        content = request.data.get("content")
        topic_id = request.data.get("topic_id")
        tags = request.data.get("tags", [])

        result = forum_controller.create_thread(
            title=title, content=content, user_data=user_data, topic_id=topic_id, tags=tags
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("SUCCESS"), **result}, status=status.HTTP_201_CREATED
            )
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in create_thread: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def add_reply(request, thread_id):
    """
    Add a reply to a thread or another reply

    Required fields:
    - content: Reply content

    Optional fields:
    - parent_reply_id: ID of parent reply if this is a nested reply
    - media_file: Media file attachment
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        content = request.data.get("content")
        parent_reply_id = request.data.get("parent_reply_id")
        media_file = request.FILES.get("media_file")

        result = forum_controller.add_reply(
            thread_id=thread_id,
            content=content,
            user_data=user_data,
            parent_reply_id=parent_reply_id,
            media_file=media_file,
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("SUCCESS"), **result}, status=status.HTTP_201_CREATED
            )
        else:
            if result["code"] == "FORUM_THREAD_NOT_FOUND":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in add_reply: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def toggle_like(request):
    """
    Toggle like/upvote on a thread or reply

    Required fields (one of):
    - thread_id: ID of thread to like
    - reply_id: ID of reply to like
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        thread_id = request.data.get("thread_id")
        reply_id = request.data.get("reply_id")

        result = forum_controller.toggle_like(
            user_data=user_data, thread_id=thread_id, reply_id=reply_id
        )

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if "NOT_FOUND" in result["code"]:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in toggle_like: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def edit_thread(request, thread_id):
    """
    Edit an existing thread

    Optional fields (at least one required):
    - title: New title
    - content: New content
    - tags: New list of tag IDs
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        title = request.data.get("title")
        content = request.data.get("content")
        tags = request.data.get("tags") if "tags" in request.data else None

        # Check if at least one field is provided
        if title is None and content is None and tags is None:
            return JsonResponse(
                {
                    **get_response_code("FORUM_MISSING_FIELDS"),
                    "error": "At least one field to update must be provided.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = forum_controller.edit_thread(
            thread_id=thread_id, user_data=user_data, title=title, content=content, tags=tags
        )

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if result["code"] == "FORUM_THREAD_NOT_FOUND":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif result["code"] == "FORUM_PERMISSION_DENIED":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in edit_thread: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_thread(request, thread_id):
    """Delete a thread"""
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        result = forum_controller.delete_thread(thread_id=thread_id, user_data=user_data)

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if result["code"] == "FORUM_THREAD_NOT_FOUND":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif result["code"] == "FORUM_PERMISSION_DENIED":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in delete_thread: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def edit_reply(request, reply_id):
    """
    Edit an existing reply

    Required fields:
    - content: New content
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get field
        content = request.data.get("content")

        if not content:
            return JsonResponse(
                {**get_response_code("FORUM_MISSING_CONTENT"), "error": "Reply content is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = forum_controller.edit_reply(reply_id=reply_id, user_data=user_data, content=content)

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if result["code"] == "FORUM_REPLY_NOT_FOUND":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif result["code"] == "FORUM_PERMISSION_DENIED":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in edit_reply: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_reply(request, reply_id):
    """Delete a reply"""
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        result = forum_controller.delete_reply(reply_id=reply_id, user_data=user_data)

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if result["code"] == "FORUM_REPLY_NOT_FOUND":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif result["code"] == "FORUM_PERMISSION_DENIED":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in delete_reply: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Navigation & Search Views
@api_view(["GET"])
@permission_classes([AllowAny])
def get_threads(request):
    """
    Get threads with pagination

    Query parameters:
    - topic_id: Filter by topic ID
    - tag_id: Filter by tag ID
    - page: Page number (default: 1)
    - items: Items per page (default: 20)
    """
    try:
        # Get query parameters
        topic_id = request.query_params.get("topic_id")
        tag_id = request.query_params.get("tag_id")
        page = int(request.query_params.get("page", 1))
        items_per_page = int(request.query_params.get("items", 20))

        # Limit items per page to prevent overload
        items_per_page = min(items_per_page, 50)

        # Check if we're filtering by user
        user_data = None
        if request.user.is_authenticated:
            if request.query_params.get("my_threads") == "true":
                user_data = UserData.objects.get(user=request.user)

        result = forum_controller.get_threads(
            topic_id=topic_id,
            tag_id=tag_id,
            page=page,
            items_per_page=items_per_page,
            user_data=user_data,
        )

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except ValueError:
        return JsonResponse(
            {**get_response_code("INVALID_REQUEST"), "error": "Invalid page or items parameter"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error(f"Error in get_threads: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_thread_detail(request, thread_id):
    """Get detailed information about a thread"""
    try:
        # Check if user is authenticated
        user_data = None
        if request.user.is_authenticated:
            user_data = UserData.objects.get(user=request.user)

        result = forum_controller.get_thread_detail(thread_id=thread_id, user_data=user_data)

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if result["code"] == "FORUM_THREAD_NOT_FOUND" or result["code"] == "FORUM_THREAD_DELETED":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif result["code"] == "FORUM_THREAD_NOT_APPROVED":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_403_FORBIDDEN,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except Exception as e:
        logger.error(f"Error in get_thread_detail: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_topics(request):
    """Get all forum topics"""
    try:
        result = forum_controller.get_topics()

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,  # filepath: /home/b450-plus/DMI_FYP_dj_primary-backend/DMI_FYP_dj_primary-backend/DMI_backend/api/views/community_forum_views.py
            )
    except Exception as e:
        logger.error(f"Error in get_topics: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# Thread Management Views
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def create_thread(request):
    """
    Create a new thread in the community forum

    Required fields:
    - title: Thread title
    - content: Thread content
    - topic_id: ID of the topic

    Optional fields:
    - tags: List of tag IDs
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get required fields
        title = request.data.get("title")
        content = request.data.get("content")
        topic_id = request.data.get("topic_id")
        tags = request.data.get("tags", [])

        result = forum_controller.create_thread(
            title=title, content=content, user_data=user_data, topic_id=topic_id, tags=tags
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("SUCCESS"), **result}, status=status.HTTP_201_CREATED
            )
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except UserData.DoesNotExist:
        return JsonResponse(
            {**get_response_code("USER_DATA_NOT_FOUND"), "error": "User data not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.error(f"Error in create_thread: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_tags(request):
    """Get all forum tags"""
    try:
        result = forum_controller.get_tags()

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Exception as e:
        logger.error(f"Error in get_tags: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def search_threads(request):
    """
    Search threads by keywords or phrases

    Query parameters:
    - query: Search query (required, must be at least 3 characters)
    - page: Page number (default: 1)
    - items: Items per page (default: 20)
    """
    try:
        # Get query parameters
        query = request.query_params.get("query", "")
        page = int(request.query_params.get("page", 1))
        items_per_page = int(request.query_params.get("items", 20))

        # Limit items per page to prevent overload
        items_per_page = min(items_per_page, 50)

        result = forum_controller.search_threads(query=query, page=page, items_per_page=items_per_page)

        if result["success"]:
            return JsonResponse({**get_response_code("SUCCESS"), **result}, status=status.HTTP_200_OK)
        else:
            if result["code"] == "FORUM_SEARCH_TOO_SHORT":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

    except ValueError:
        return JsonResponse(
            {**get_response_code("INVALID_REQUEST"), "error": "Invalid page or items parameter"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error(f"Error in search_threads: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


api_view(["POST"])


@permission_classes([IsAuthenticated])
def add_reaction(self, user_data, reaction_type, thread_id=None, reply_id=None):
    """
    Add emoji reaction to a thread or reply

    Args:
        user_data (UserData): User data of the reactor
        reaction_type (str): Type of reaction (emoji code)
        thread_id (int, optional): ID of thread to react to
        reply_id (int, optional): ID of reply to react to

    Returns:
        dict: Response with reaction status
    """
    try:
        # Check if either thread_id or reply_id is provided
        if (thread_id is None and reply_id is None) or (thread_id and reply_id):
            return {
                "success": False,
                "error": "Must provide either thread_id or reply_id, not both",
                "code": "FORUM_INVALID_REACTION_TARGET",
            }

        # Validate reaction type
        valid_reactions = ["like", "love", "laugh", "wow", "sad", "angry"]
        if reaction_type not in valid_reactions:
            return {
                "success": False,
                "error": f"Invalid reaction type. Valid types: {', '.join(valid_reactions)}",
                "code": "FORUM_INVALID_REACTION_TYPE",
            }

        # Find the target object
        target = None
        if thread_id:
            try:
                target = ForumThread.objects.get(
                    id=thread_id, approval_status="approved", is_deleted=False
                )
                # Check if user already reacted with this type
                existing_reaction = ForumReaction.objects.filter(
                    user=user_data, thread=target, reaction_type=reaction_type
                ).first()

                # Remove any previous reactions of different types
                ForumReaction.objects.filter(user=user_data, thread=target).exclude(
                    reaction_type=reaction_type
                ).delete()

            except ForumThread.DoesNotExist:
                return {
                    "success": False,
                    "error": "Thread not found or not approved",
                    "code": "FORUM_THREAD_NOT_FOUND",
                }
        else:
            try:
                target = ForumReply.objects.get(id=reply_id, is_deleted=False)
                # Check if user already reacted with this type
                existing_reaction = ForumReaction.objects.filter(
                    user=user_data, reply=target, reaction_type=reaction_type
                ).first()

                # Remove any previous reactions of different types
                ForumReaction.objects.filter(user=user_data, reply=target).exclude(
                    reaction_type=reaction_type
                ).delete()

            except ForumReply.DoesNotExist:
                return {
                    "success": False,
                    "error": "Reply not found",
                    "code": "FORUM_REPLY_NOT_FOUND",
                }

        # Toggle reaction status
        if existing_reaction:
            existing_reaction.delete()
            action = "removed"
        else:
            # Create new reaction
            if thread_id:
                ForumReaction.objects.create(user=user_data, thread=target, reaction_type=reaction_type)
            else:
                ForumReaction.objects.create(user=user_data, reply=target, reaction_type=reaction_type)
            action = "added"

        # Get updated reaction counts
        if thread_id:
            reaction_counts = self.get_reaction_counts(thread_id=thread_id)
        else:
            reaction_counts = self.get_reaction_counts(reply_id=reply_id)

        return {
            "success": True,
            "action": action,
            "reaction_type": reaction_type,
            "reaction_counts": reaction_counts,
            "code": f"FORUM_REACTION_{action.upper()}",
        }

    except Exception as e:
        logger.error(f"Error toggling reaction: {str(e)}")
        return {
            "success": False,
            "error": f"Error toggling reaction: {str(e)}",
            "code": "FORUM_REACTION_ERROR",
        }


@api_view(["GET"])
@permission_classes([AllowAny])
def get_reaction_counts(self, thread_id=None, reply_id=None):
    """
    Get reaction counts for a thread or reply

    Args:
        thread_id (int, optional): ID of thread
        reply_id (int, optional): ID of reply

    Returns:
        dict: Counts for each reaction type
    """
    reaction_counts = {}

    try:
        if thread_id:
            # Get all reactions for this thread
            reactions = (
                ForumReaction.objects.filter(thread_id=thread_id)
                .values("reaction_type")
                .annotate(count=count("id"))
            )
        elif reply_id:
            # Get all reactions for this reply
            reactions = (
                ForumReaction.objects.filter(reply_id=reply_id)
                .values("reaction_type")
                .annotate(count=count("id"))
            )
        else:
            return {}

        # Convert to dictionary format
        for reaction in reactions:
            reaction_counts[reaction["reaction_type"]] = reaction["count"]

        return reaction_counts

    except Exception as e:
        logger.error(f"Error getting reaction counts: {str(e)}")
        return {}
