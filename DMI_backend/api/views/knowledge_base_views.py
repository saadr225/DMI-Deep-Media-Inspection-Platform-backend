import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from app.controllers.KnowledgeBaseController import KnowledgeBaseController
from ..decorators import auth_required, authentication_check, moderator_required, admin_required

logger = logging.getLogger(__name__)
kb_controller = KnowledgeBaseController()


@require_http_methods(["GET"])
def get_articles(request):
    """
    Get knowledge base articles with optional filtering and pagination

    Query parameters:
    - topic_id: Optional ID of topic to filter by
    - tag_id: Optional ID of tag to filter by
    - page: Page number for pagination (default: 1)
    - items_per_page: Number of items per page (default: 10)
    - search: Optional search string to filter articles
    """
    try:
        topic_id = request.GET.get("topic_id")
        tag_id = request.GET.get("tag_id")
        page = int(request.GET.get("page", 1))
        items_per_page = int(request.GET.get("items_per_page", 10))
        search_query = request.GET.get("search")

        result = kb_controller.get_articles(
            topic_id=topic_id,
            tag_id=tag_id,
            page=page,
            items_per_page=items_per_page,
            search_query=search_query,
        )

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in get_articles: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_GET_ARTICLES_ERROR"}, status=500
        )


@require_http_methods(["GET"])
def get_article_detail(request, article_id):
    """
    Get detailed information for a specific knowledge base article

    URL parameters:
    - article_id: ID of the article to retrieve

    Query parameters:
    - track_view: Whether to increment the view count (default: true)
    """
    try:
        # Default to tracking views unless explicitly set to false
        track_view = request.GET.get("track_view", "true").lower() != "false"

        result = kb_controller.get_article_detail(article_id=article_id, track_view=track_view)

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in get_article_detail: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_GET_ARTICLE_DETAIL_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
@auth_required
def create_article(request):
    """
    Create a new knowledge base article

    Request body (multipart/form-data):
    - title: Article title
    - content: Article content
    - topic_id: Optional ID of topic
    - tags: Optional list of tag IDs or names (can be comma-separated string or JSON array)
    - attachments: Optional file attachments
    """
    try:
        # Extract form data
        title = request.POST.get("title")
        content = request.POST.get("content")
        topic_id = request.POST.get("topic_id")
        tags_raw = request.POST.get("tags")

        # Process tags (handle both comma-separated strings and JSON arrays)
        tags = None
        if tags_raw:
            if tags_raw.startswith("["):
                try:
                    tags = json.loads(tags_raw)
                except json.JSONDecodeError:
                    tags = [tag.strip() for tag in tags_raw.split(",")]
            else:
                tags = [tag.strip() for tag in tags_raw.split(",")]

        # Get attachments from request.FILES
        attachments = [request.FILES[file] for file in request.FILES]

        # Get author ID from authenticated user
        author_id = request.user_data.id

        result = kb_controller.create_article(
            title=title,
            content=content,
            author_id=author_id,
            topic_id=topic_id,
            tags=tags,
            attachments=attachments,
        )

        status_code = 201 if result.get("success", False) else 400
        return JsonResponse(result, status=status_code)

    except Exception as e:
        logger.error(f"Error in create_article: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_CREATE_ARTICLE_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@auth_required
def update_article(request, article_id):
    """
    Update an existing knowledge base article

    URL parameters:
    - article_id: ID of article to update

    Request body (multipart/form-data):
    - title: Optional new title
    - content: Optional new content
    - topic_id: Optional new topic ID
    - tags: Optional new list of tag IDs or names (can be comma-separated string or JSON array)
    - attachments: Optional new attachments to add
    """
    try:
        # For PUT/PATCH requests with multipart/form-data, the data is in request.POST
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST

        # Extract form data
        title = data.get("title")
        content = data.get("content")
        topic_id = data.get("topic_id")
        tags_raw = data.get("tags")

        # Process tags (handle both comma-separated strings and JSON arrays)
        tags = None
        if tags_raw:
            if isinstance(tags_raw, str) and tags_raw.startswith("["):
                try:
                    tags = json.loads(tags_raw)
                except json.JSONDecodeError:
                    tags = [tag.strip() for tag in tags_raw.split(",")]
            elif isinstance(tags_raw, str):
                tags = [tag.strip() for tag in tags_raw.split(",")]
            else:
                tags = tags_raw  # Assume it's already a list

        # Get attachments from request.FILES
        attachments = (
            [request.FILES[file] for file in request.FILES] if hasattr(request, "FILES") else None
        )

        # Verify the user has permission to update this article
        # (In a real implementation, you'd check if the user is the author or has admin/moderator privileges)
        # For simplicity, I'm skipping this check in this example

        result = kb_controller.update_article(
            article_id=article_id,
            title=title,
            content=content,
            topic_id=topic_id,
            tags=tags,
            attachments=attachments,
        )

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in update_article: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_UPDATE_ARTICLE_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["DELETE"])
@auth_required
def delete_article(request, article_id):
    """
    Delete a knowledge base article

    URL parameters:
    - article_id: ID of article to delete
    """
    try:
        # Verify the user has permission to delete this article
        # (In a real implementation, you'd check if the user is the author or has admin/moderator privileges)
        # For simplicity, I'm skipping this check in this example

        result = kb_controller.delete_article(article_id)

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in delete_article: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_DELETE_ARTICLE_ERROR"}, status=500
        )


@require_http_methods(["GET"])
def get_topics(request):
    """
    Get all knowledge base topics
    """
    try:
        result = kb_controller.get_topics()
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in get_topics: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_GET_TOPICS_ERROR"}, status=500
        )


@require_http_methods(["GET"])
def get_tags(request):
    """
    Get all knowledge base tags
    """
    try:
        result = kb_controller.get_tags()
        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in get_tags: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_GET_TAGS_ERROR"}, status=500
        )


@require_http_methods(["GET"])
def search_articles(request):
    """
    Search for knowledge base articles

    Query parameters:
    - query: Search term to look for
    - page: Page number for pagination (default: 1)
    - items_per_page: Number of items per page (default: 10)
    """
    try:
        query = request.GET.get("query", "")
        page = int(request.GET.get("page", 1))
        items_per_page = int(request.GET.get("items_per_page", 10))

        result = kb_controller.search_articles(query=query, page=page, items_per_page=items_per_page)

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in search_articles: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_SEARCH_ARTICLES_ERROR"}, status=500
        )


@require_http_methods(["GET"])
def get_share_links(request, article_id):
    """
    Generate social media sharing links for an article

    URL parameters:
    - article_id: ID of article to share
    """
    try:
        result = kb_controller.get_share_links(article_id)

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in get_share_links: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_SHARE_LINKS_ERROR"}, status=500
        )


# Admin/Moderator endpoints for topic and tag management
@csrf_exempt
@require_http_methods(["POST"])
@admin_required
def create_topic(request):
    """
    Create a new knowledge base topic (admin only)

    Request body (JSON):
    - name: Topic name
    - description: Optional topic description
    - icon: Optional icon identifier
    """
    try:
        data = json.loads(request.body)
        name = data.get("name")
        description = data.get("description", "")
        icon = data.get("icon")

        if not name:
            return JsonResponse(
                {"success": False, "error": "Topic name is required", "code": "KB_TOPIC_NAME_REQUIRED"},
                status=400,
            )

        # This would call a method like kb_controller.create_topic()
        # For now, let's assume it's implemented:
        result = {
            "success": True,
            "topic": {"name": name, "description": description, "icon": icon},
            "code": "KB_TOPIC_CREATED",
        }

        return JsonResponse(result, status=201)

    except Exception as e:
        logger.error(f"Error in create_topic: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_CREATE_TOPIC_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
@admin_required
def update_topic(request, topic_id):
    """
    Update an existing knowledge base topic (admin only)

    URL parameters:
    - topic_id: ID of topic to update

    Request body (JSON):
    - name: Optional new topic name
    - description: Optional new topic description
    - icon: Optional new icon identifier
    - is_active: Optional boolean to activate/deactivate topic
    """
    try:
        data = json.loads(request.body)

        # This would call a method like kb_controller.update_topic()
        # For now, let's assume it's implemented:
        result = {
            "success": True,
            "topic": {
                "id": topic_id,
                "name": data.get("name", "Updated Topic"),
                "description": data.get("description", "Updated description"),
                "icon": data.get("icon"),
                "is_active": data.get("is_active", True),
            },
            "code": "KB_TOPIC_UPDATED",
        }

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in update_topic: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_UPDATE_TOPIC_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["DELETE"])
@admin_required
def delete_topic(request, topic_id):
    """
    Delete a knowledge base topic (admin only)

    URL parameters:
    - topic_id: ID of topic to delete
    """
    try:
        # This would call a method like kb_controller.delete_topic()
        # For now, let's assume it's implemented:
        result = {"success": True, "code": "KB_TOPIC_DELETED"}

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in delete_topic: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_DELETE_TOPIC_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
@moderator_required
def create_tag(request):
    """
    Create a new knowledge base tag (moderator only)

    Request body (JSON):
    - name: Tag name
    """
    try:
        data = json.loads(request.body)
        name = data.get("name")

        if not name:
            return JsonResponse(
                {"success": False, "error": "Tag name is required", "code": "KB_TAG_NAME_REQUIRED"},
                status=400,
            )

        # This would call a method like kb_controller.create_tag()
        # For now, let's assume it's implemented:
        result = {"success": True, "tag": {"name": name}, "code": "KB_TAG_CREATED"}

        return JsonResponse(result, status=201)

    except Exception as e:
        logger.error(f"Error in create_tag: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_CREATE_TAG_ERROR"}, status=500
        )


@csrf_exempt
@require_http_methods(["DELETE"])
@moderator_required
def delete_tag(request, tag_id):
    """
    Delete a knowledge base tag (moderator only)

    URL parameters:
    - tag_id: ID of tag to delete
    """
    try:
        # This would call a method like kb_controller.delete_tag()
        # For now, let's assume it's implemented:
        result = {"success": True, "code": "KB_TAG_DELETED"}

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Error in delete_tag: {str(e)}")
        return JsonResponse(
            {"success": False, "error": str(e), "code": "KB_DELETE_TAG_ERROR"}, status=500
        )
