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


# THREAD MANAGEMENT VIEWS


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def create_thread(request):
    """
    Create a new thread in the community forum

    Required fields:
    - title: Thread title
    - content: Thread content
    - topic_id: ID of the topic

    Optional fields:
    - tags: List of tag IDs
    - is_pinned: Whether the thread should be pinned (moderators only)
    - media_file: Media file attachment
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get required fields
        title = request.data.get("title")
        content = request.data.get("content")
        topic_id = request.data.get("topic_id")
        tags = request.data.get("tags", [])
        is_pinned = request.data.get("is_pinned", False)
        media_file = request.FILES.get("media_file")
        
        # Convert string 'true'/'false' to boolean if needed
        if isinstance(is_pinned, str):
            is_pinned = is_pinned.lower() == 'true'

        result = forum_controller.create_thread(
            title=title, 
            content=content, 
            user_data=user_data, 
            topic_id=topic_id, 
            tags=tags,
            is_pinned=is_pinned,
            media_file=media_file
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_THREAD_CREATED"), **result}, status=status.HTTP_201_CREATED
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
    - is_pinned: Whether the thread should be pinned (moderators only)
    - is_locked: Whether the thread should be locked (moderators only)
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        title = request.data.get("title")
        content = request.data.get("content")
        tags = request.data.get("tags") if "tags" in request.data else None
        is_pinned = request.data.get("is_pinned") if "is_pinned" in request.data else None
        is_locked = request.data.get("is_locked") if "is_locked" in request.data else None

        # Check if at least one field is provided
        if title is None and content is None and tags is None and is_pinned is None and is_locked is None:
            return JsonResponse(
                {
                    **get_response_code("FORUM_MISSING_FIELDS"),
                    "error": "At least one field to update must be provided.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = forum_controller.edit_thread(
            thread_id=thread_id, 
            user_data=user_data, 
            title=title, 
            content=content, 
            tags=tags,
            is_pinned=is_pinned,
            is_locked=is_locked
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_THREAD_UPDATED"), **result}, status=status.HTTP_200_OK
            )
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
            return JsonResponse(
                {**get_response_code("FORUM_THREAD_DELETED"), **result}, status=status.HTTP_200_OK
            )
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


# REPLY MANAGEMENT VIEWS


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
    - is_solution: Whether this reply should be marked as solution (thread author or moderator only)
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        content = request.data.get("content")
        parent_reply_id = request.data.get("parent_reply_id")
        media_file = request.FILES.get("media_file")
        is_solution = request.data.get("is_solution", False)
        
        # Convert string 'true'/'false' to boolean if needed
        if isinstance(is_solution, str):
            is_solution = is_solution.lower() == 'true'

        result = forum_controller.add_reply(
            thread_id=thread_id,
            content=content,
            user_data=user_data,
            parent_reply_id=parent_reply_id,
            media_file=media_file,
            is_solution=is_solution
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_REPLY_CREATED"), **result}, status=status.HTTP_201_CREATED
            )
        else:
            if result["code"] == "FORUM_THREAD_NOT_FOUND":
                return JsonResponse(
                    {**get_response_code(result["code"]), "error": result["error"]},
                    status=status.HTTP_404_NOT_FOUND,
                )
            elif result["code"] == "FORUM_THREAD_LOCKED":
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
        logger.error(f"Error in add_reply: {str(e)}")
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
            return JsonResponse(
                {**get_response_code("FORUM_REPLY_UPDATED"), **result}, status=status.HTTP_200_OK
            )
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
            return JsonResponse(
                {**get_response_code("FORUM_REPLY_DELETED"), **result}, status=status.HTTP_200_OK
            )
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


# REACTION AND LIKE VIEWS


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
            user_data=user_data, thread_id=thread_id, reply_id=reply_id, like_type="like"
        )

        if result["success"]:
            # Use the specific response code returned by the controller
            response_code = result["code"]
            return JsonResponse(
                {**get_response_code(response_code), **result}, status=status.HTTP_200_OK
            )
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def toggle_dislike(request):
    """
    Toggle dislike/downvote on a thread or reply

    Required fields (one of):
    - thread_id: ID of thread to dislike
    - reply_id: ID of reply to dislike
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        thread_id = request.data.get("thread_id")
        reply_id = request.data.get("reply_id")

        result = forum_controller.toggle_like(
            user_data=user_data, thread_id=thread_id, reply_id=reply_id, like_type="dislike"
        )

        if result["success"]:
            # Use the specific response code returned by the controller
            response_code = result["code"]
            return JsonResponse(
                {**get_response_code(response_code), **result}, status=status.HTTP_200_OK
            )
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
        logger.error(f"Error in toggle_dislike: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def add_reaction(request):
    """
    Add emoji reaction to a thread or reply

    Required fields:
    - reaction_type: Type of reaction (emoji code)
    - thread_id OR reply_id: Target to react to
    """
    try:
        user = request.user
        user_data = UserData.objects.get(user=user)

        # Get fields
        reaction_type = request.data.get("reaction_type")
        thread_id = request.data.get("thread_id")
        reply_id = request.data.get("reply_id")

        # Use controller method to add reaction
        result = forum_controller.add_reaction(
            user_data=user_data, reaction_type=reaction_type, thread_id=thread_id, reply_id=reply_id
        )

        if result["success"]:
            # Use the specific response code returned by the controller
            response_code = result["code"]
            return JsonResponse(
                {**get_response_code(response_code), **result}, status=status.HTTP_200_OK
            )
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
        logger.error(f"Error in add_reaction: {str(e)}")
        return JsonResponse(
            {**get_response_code("FORUM_REACTION_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_reaction_counts(request, thread_id=None, reply_id=None):
    """
    Get reaction counts for a thread or reply

    URL parameters (one of):
    - thread_id: ID of thread
    - reply_id: ID of reply
    """
    try:
        # Use controller method to get reaction counts
        if thread_id:
            reaction_counts = forum_controller.get_reaction_counts(thread_id=thread_id)
        elif reply_id:
            reaction_counts = forum_controller.get_reaction_counts(reply_id=reply_id)
        else:
            return JsonResponse(
                {
                    **get_response_code("FORUM_INVALID_REACTION_TARGET"),
                    "error": "Must provide either thread_id or reply_id",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return JsonResponse(
            {**get_response_code("SUCCESS"), "reaction_counts": reaction_counts},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error(f"Error in get_reaction_counts: {str(e)}")
        return JsonResponse(
            {**get_response_code("FORUM_REACTION_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# NAVIGATION AND SEARCH VIEWS


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
            else:
                # Even if not filtering by user threads, still pass user_data 
                # for checking likes/dislikes
                user_data = UserData.objects.get(user=request.user)

        result = forum_controller.get_threads(
            topic_id=topic_id,
            tag_id=tag_id,
            page=page,
            items_per_page=items_per_page,
            user_data=user_data,
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_THREADS_FETCHED"), **result}, status=status.HTTP_200_OK
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
        logger.error(f"Error in get_threads: {str(e)}")
        return JsonResponse(
            {**get_response_code("SERVER_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_thread_detail(request, thread_id):
    """
    Get detailed information about a thread.
    Returns all thread details including author info, reactions, tags, etc.
    """
    try:
        # Check if user is authenticated
        user_data = None
        if request.user.is_authenticated:
            user_data = UserData.objects.get(user=request.user)

        result = forum_controller.get_thread_detail(thread_id=thread_id, user_data=user_data)

        if result["success"]:
            response_data = {
                "status": "success",
                "code": "FORUM_THREAD_FETCHED",
                "message": "Thread details retrieved successfully",
                "data": result["thread"]
            }
            return JsonResponse(response_data, status=status.HTTP_200_OK)
        else:
            error_code = result["code"]
            
            if error_code in ["FORUM_THREAD_NOT_FOUND", "FORUM_THREAD_DELETED"]:
                response_data = {
                    "status": "error",
                    "code": error_code,
                    "message": result["error"]
                }
                return JsonResponse(response_data, status=status.HTTP_404_NOT_FOUND)
            elif error_code == "FORUM_THREAD_NOT_APPROVED":
                response_data = {
                    "status": "error",
                    "code": error_code,
                    "message": result["error"]
                }
                return JsonResponse(response_data, status=status.HTTP_403_FORBIDDEN)
            else:
                response_data = {
                    "status": "error",
                    "code": error_code,
                    "message": result["error"]
                }
                return JsonResponse(response_data, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error in get_thread_detail: {str(e)}")
        response_data = {
            "status": "error",
            "code": "FORUM_THREAD_DETAIL_ERROR",
            "message": str(e)
        }
        return JsonResponse(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([AllowAny])
def get_topics(request):
    """Get all forum topics"""
    try:
        result = forum_controller.get_topics()

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_TOPICS_FETCHED"), **result}, status=status.HTTP_200_OK
            )
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
    except Exception as e:
        logger.error(f"Error in get_topics: {str(e)}")
        return JsonResponse(
            {**get_response_code("FORUM_TOPICS_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_tags(request):
    """Get all forum tags"""
    try:
        result = forum_controller.get_tags()

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_TAGS_FETCHED"), **result}, status=status.HTTP_200_OK
            )
        else:
            return JsonResponse(
                {**get_response_code(result["code"]), "error": result["error"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Exception as e:
        logger.error(f"Error in get_tags: {str(e)}")
        return JsonResponse(
            {**get_response_code("FORUM_TAGS_ERROR"), "error": str(e)},
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
        
        # Check if user is authenticated
        user_data = None
        if request.user.is_authenticated:
            user_data = UserData.objects.get(user=request.user)

        result = forum_controller.search_threads(
            query=query, 
            page=page, 
            items_per_page=items_per_page,
            user_data=user_data
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_SEARCH_RESULTS"), **result}, status=status.HTTP_200_OK
            )
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
            {**get_response_code("FORUM_SEARCH_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_thread_replies(request, thread_id):
    """
    Get replies for a specific thread

    URL parameters:
    - thread_id: ID of the thread

    Query parameters:
    - page: Page number (default: 1)
    - items: Items per page (default: 20)
    """
    try:
        # Check if user is authenticated
        user_data = None
        if request.user.is_authenticated:
            user_data = UserData.objects.get(user=request.user)

        # Get query parameters
        page = int(request.query_params.get("page", 1))
        items_per_page = int(request.query_params.get("items", 20))
        
        # Limit items per page to prevent overload
        items_per_page = min(items_per_page, 50)

        result = forum_controller.get_thread_replies(
            thread_id=thread_id, 
            user_data=user_data, 
            page=page, 
            items_per_page=items_per_page
        )

        if result["success"]:
            return JsonResponse(
                {**get_response_code("FORUM_REPLIES_FETCHED"), **result}, status=status.HTTP_200_OK
            )
        else:
            if result["code"] == "FORUM_THREAD_NOT_FOUND":
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

    except ValueError:
        return JsonResponse(
            {**get_response_code("INVALID_REQUEST"), "error": "Invalid page or items parameter"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error(f"Error in get_thread_replies: {str(e)}")
        return JsonResponse(
            {**get_response_code("FORUM_REPLIES_ERROR"), "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
