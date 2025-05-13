import logging
import os
import time
import uuid
from datetime import datetime

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, F
from django.utils import timezone

from api.models import (
    KnowledgeBaseArticle,
    KnowledgeBaseTopic,
    KnowledgeBaseAttachment,
    KnowledgeBaseStatistics,
    UserData,
)

logger = logging.getLogger(__name__)


class KnowledgeBaseController:
    """
    Controller for managing knowledge base articles, topics, and related operations.
    Handles article creation, retrieval, search, and statistics tracking.
    """

    def get_articles(self, topic_id=None, page=1, items_per_page=10, search_query=None):
        """
        Get knowledge base articles with optional filtering and pagination.

        Args:
            topic_id: Optional ID of topic to filter by
            page: Page number for pagination
            items_per_page: Number of items per page
            search_query: Optional search string to filter articles

        Returns:
            Dictionary containing articles, pagination info, and status
        """
        try:
            # Base query for published articles
            base_query = Q(is_published=True) & Q(is_deleted=False)
            articles = KnowledgeBaseArticle.objects.filter(base_query)

            # Apply filters
            if topic_id:
                articles = articles.filter(topic_id=topic_id)

            if search_query:
                articles = articles.filter(
                    Q(title__icontains=search_query) | Q(content__icontains=search_query) | Q(author__user__username__icontains=search_query)
                ).distinct()

            # Order by most recent
            articles = articles.order_by("-created_at")

            # Annotate with view count
            articles = articles.annotate(view_count=F("statistics__view_count"))

            # Paginate results
            paginator = Paginator(articles, items_per_page)
            try:
                paginated_articles = paginator.page(page)
            except PageNotAnInteger:
                paginated_articles = paginator.page(1)
            except EmptyPage:
                paginated_articles = paginator.page(paginator.num_pages)

            # Format articles for response
            result_articles = []
            for article in paginated_articles:
                # Calculate read time (average reading speed: 200 words per minute)
                word_count = len(article.content.split())
                read_time = max(1, round(word_count / 200))

                # Format article data
                result_articles.append(
                    {
                        "id": article.id,
                        "title": article.title,
                        "author": {
                            "username": article.author.user.username,
                            "avatar": article.author.profile_image_url,
                            "is_verified": article.author.is_verified,
                        },
                        "created_at": article.created_at.strftime("%Y-%m-%d"),
                        "topic": (
                            {
                                "id": article.topic.id,
                                "name": article.topic.name,
                            }
                            if article.topic
                            else None
                        ),
                        "preview": (article.content[:200] + "..." if len(article.content) > 200 else article.content),
                        "view_count": getattr(article, "view_count", 0),
                        "has_attachments": article.attachments.exists(),
                    }
                )

            return {
                "success": True,
                "articles": result_articles,
                "page": page,
                "pages": paginator.num_pages,
                "total": paginator.count,
                "code": "KNOWLEDGE_ARTICLES_FETCHED",
            }

        except Exception as e:
            logger.error(f"Error fetching knowledge base articles: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching articles: {str(e)}",
                "code": "KNOWLEDGE_FETCH_ERROR",
            }

    def get_article_detail(self, article_id, track_view=True):
        """
        Get detailed information for a specific knowledge base article

        Args:
            article_id: ID of the article to retrieve
            track_view: Whether to increment the view count

        Returns:
            Dictionary containing article details or error information
        """
        try:
            # Get the article
            article = KnowledgeBaseArticle.objects.get(id=article_id, is_published=True, is_deleted=False)

            # Get attachments
            attachments = []
            for attachment in article.attachments.all():
                attachments.append(
                    {
                        "id": attachment.id,
                        "filename": attachment.filename,
                        "file_url": self._get_full_attachment_url(attachment.file_url),
                        "file_type": attachment.file_type,
                    }
                )

            # Calculate read time (average reading speed: 200 words per minute)
            word_count = len(article.content.split())
            read_time = max(1, round(word_count / 200))

            # Track view if requested
            if track_view:
                self._track_article_view(article)

            # Retrieve statistics
            try:
                stats = KnowledgeBaseStatistics.objects.get(article=article)
                view_count = stats.view_count
            except KnowledgeBaseStatistics.DoesNotExist:
                view_count = 0

            # Format article data for response
            article_data = {
                "id": article.id,
                "title": article.title,
                "author": {
                    "username": article.author.user.username,
                    "avatar": article.author.profile_image_url,
                    "is_verified": article.author.is_verified,
                    "join_date": article.author.user.date_joined.strftime("%B %Y"),
                },
                "created_at": article.created_at.strftime("%Y-%m-%d"),
                "updated_at": article.updated_at.strftime("%Y-%m-%d"),
                "topic": (
                    {
                        "id": article.topic.id,
                        "name": article.topic.name,
                    }
                    if article.topic
                    else None
                ),
                "content": article.content,
                "read_time": read_time,
                "view_count": view_count,
                "attachments": attachments,
                "related_articles": self._get_related_articles(article),
            }

            return {
                "success": True,
                "article": article_data,
                "code": "KNOWLEDGE_ARTICLE_FETCHED",
            }

        except KnowledgeBaseArticle.DoesNotExist:
            return {
                "success": False,
                "error": "Article not found",
                "code": "KNOWLEDGE_ARTICLE_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error fetching knowledge base article detail: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching article detail: {str(e)}",
                "code": "KNOWLEDGE_DETAIL_ERROR",
            }

    def create_article(self, title, content, author_id, topic_id=None, attachments=None):
        """
        Create a new knowledge base article

        Args:
            title: Article title
            content: Article content
            author_id: ID of the author (UserData)
            topic_id: Optional ID of topic
            attachments: Optional list of attachment files

        Returns:
            Dictionary containing new article info or error information
        """
        try:
            # Validate input
            if not title or not content:
                return {
                    "success": False,
                    "error": "Title and content are required",
                    "code": "KNOWLEDGE_VALIDATION_ERROR",
                }

            # Get author
            author = UserData.objects.get(id=author_id)

            # Get topic if provided
            topic = None
            if topic_id:
                try:
                    topic = KnowledgeBaseTopic.objects.get(id=topic_id)
                except KnowledgeBaseTopic.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Topic not found",
                        "code": "KNOWLEDGE_TOPIC_NOT_FOUND",
                    }

            # Create article
            article = KnowledgeBaseArticle.objects.create(
                title=title,
                content=content,
                author=author,
                topic=topic,
                is_published=True,  # Default to published
            )

            # Process attachments
            if attachments:
                attachment_data = self._process_attachments(article, attachments)
            else:
                attachment_data = []

            # Create statistics entry
            KnowledgeBaseStatistics.objects.create(article=article, view_count=0)

            # Calculate read time
            word_count = len(content.split())
            read_time = max(1, round(word_count / 200))

            return {
                "success": True,
                "article": {
                    "id": article.id,
                    "title": article.title,
                    "created_at": article.created_at.strftime("%Y-%m-%d"),
                    "author": {
                        "username": author.user.username,
                        "avatar": author.profile_image_url,
                    },
                    "topic": (
                        {
                            "id": topic.id,
                            "name": topic.name,
                        }
                        if topic
                        else None
                    ),
                    "read_time": read_time,
                    "attachments": attachment_data,
                },
                "code": "KNOWLEDGE_ARTICLE_CREATED",
            }

        except UserData.DoesNotExist:
            return {
                "success": False,
                "error": "Author not found",
                "code": "KNOWLEDGE_AUTHOR_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error creating knowledge base article: {str(e)}")
            return {
                "success": False,
                "error": f"Error creating article: {str(e)}",
                "code": "KNOWLEDGE_CREATE_ERROR",
            }

    def update_article(self, article_id, title=None, content=None, topic_id=None, attachments=None):
        """
        Update an existing knowledge base article

        Args:
            article_id: ID of article to update
            title: Optional new title
            content: Optional new content
            topic_id: Optional new topic ID
            attachments: Optional new attachments to add

        Returns:
            Dictionary containing updated article info or error information
        """
        try:
            # Get the article
            article = KnowledgeBaseArticle.objects.get(id=article_id, is_deleted=False)

            # Update fields if provided
            if title is not None:
                article.title = title

            if content is not None:
                article.content = content

            if topic_id is not None:
                try:
                    topic = KnowledgeBaseTopic.objects.get(id=topic_id)
                    article.topic = topic
                except KnowledgeBaseTopic.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Topic not found",
                        "code": "KNOWLEDGE_TOPIC_NOT_FOUND",
                    }

            # Save changes
            article.updated_at = timezone.now()
            article.save()

            # Process attachments if provided
            attachment_data = []
            if attachments:
                attachment_data = self._process_attachments(article, attachments)

            # Calculate read time
            word_count = len(article.content.split())
            read_time = max(1, round(word_count / 200))

            return {
                "success": True,
                "article": {
                    "id": article.id,
                    "title": article.title,
                    "updated_at": article.updated_at.strftime("%Y-%m-%d"),
                    "topic": (
                        {
                            "id": article.topic.id,
                            "name": article.topic.name,
                        }
                        if article.topic
                        else None
                    ),
                    "read_time": read_time,
                    "attachments": attachment_data,
                },
                "code": "KNOWLEDGE_ARTICLE_UPDATED",
            }

        except KnowledgeBaseArticle.DoesNotExist:
            return {
                "success": False,
                "error": "Article not found",
                "code": "KNOWLEDGE_ARTICLE_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error updating knowledge base article: {str(e)}")
            return {
                "success": False,
                "error": f"Error updating article: {str(e)}",
                "code": "KNOWLEDGE_UPDATE_ERROR",
            }

    def delete_article(self, article_id):
        """
        Soft delete a knowledge base article

        Args:
            article_id: ID of article to delete

        Returns:
            Dictionary containing status of operation
        """
        try:
            article = KnowledgeBaseArticle.objects.get(id=article_id)
            article.is_deleted = True
            article.save()

            return {
                "success": True,
                "code": "KNOWLEDGE_ARTICLE_DELETED",
            }

        except KnowledgeBaseArticle.DoesNotExist:
            return {
                "success": False,
                "error": "Article not found",
                "code": "KNOWLEDGE_ARTICLE_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error deleting knowledge base article: {str(e)}")
            return {
                "success": False,
                "error": f"Error deleting article: {str(e)}",
                "code": "KNOWLEDGE_DELETE_ERROR",
            }

    def get_topics(self):
        """
        Get all knowledge base topics

        Returns:
            Dictionary containing topics or error information
        """
        try:
            topics = KnowledgeBaseTopic.objects.filter(is_active=True)

            # Annotate with article counts
            topics = topics.annotate(
                article_count=Count(
                    "knowledgebasearticle",
                    filter=Q(knowledgebasearticle__is_published=True) & Q(knowledgebasearticle__is_deleted=False),
                )
            )

            topics_data = []
            for topic in topics:
                topics_data.append(
                    {
                        "id": topic.id,
                        "name": topic.name,
                        "description": topic.description,
                        "icon": topic.icon,
                        "article_count": topic.article_count,
                    }
                )

            return {
                "success": True,
                "topics": topics_data,
                "code": "KNOWLEDGE_TOPICS_FETCHED",
            }

        except Exception as e:
            logger.error(f"Error fetching knowledge base topics: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching topics: {str(e)}",
                "code": "KNOWLEDGE_TOPICS_ERROR",
            }

    def search_articles(self, query, page=1, items_per_page=10):
        """
        Search for knowledge base articles

        Args:
            query: Search term to look for
            page: Page number for pagination
            items_per_page: Number of items per page

        Returns:
            Dictionary containing search results or error information
        """
        # This is essentially a wrapper around get_articles with a search query
        if not query or len(query.strip()) < 3:
            return {
                "success": False,
                "error": "Search query must be at least 3 characters",
                "code": "KNOWLEDGE_SEARCH_TOO_SHORT",
            }

        return self.get_articles(search_query=query, page=page, items_per_page=items_per_page)

    def get_share_links(self, article_id):
        """
        Generate social media sharing links for an article

        Args:
            article_id: ID of article to share

        Returns:
            Dictionary containing sharing links or error information
        """
        try:
            article = KnowledgeBaseArticle.objects.get(id=article_id, is_published=True, is_deleted=False)

            # Generate base URL for article
            base_url = f"{settings.SITE_URL}/knowledge/article/{article.id}"

            # Generate sharing links
            share_links = {
                "twitter": f"https://twitter.com/intent/tweet?url={base_url}&text={article.title}",
                "facebook": f"https://www.facebook.com/sharer/sharer.php?u={base_url}",
                "linkedin": f"https://www.linkedin.com/shareArticle?mini=true&url={base_url}&title={article.title}",
                "email": f"mailto:?subject={article.title}&body=Check out this article: {base_url}",
            }

            return {
                "success": True,
                "share_links": share_links,
                "code": "KNOWLEDGE_SHARE_LINKS_GENERATED",
            }

        except KnowledgeBaseArticle.DoesNotExist:
            return {
                "success": False,
                "error": "Article not found",
                "code": "KNOWLEDGE_ARTICLE_NOT_FOUND",
            }
        except Exception as e:
            logger.error(f"Error generating share links: {str(e)}")
            return {
                "success": False,
                "error": f"Error generating share links: {str(e)}",
                "code": "KNOWLEDGE_SHARE_ERROR",
            }

    # Helper Methods

    def _track_article_view(self, article):
        """Increment view count for an article"""
        try:
            stats, created = KnowledgeBaseStatistics.objects.get_or_create(article=article, defaults={"view_count": 1})

            if not created:
                stats.view_count += 1
                stats.save()

        except Exception as e:
            logger.error(f"Error tracking article view: {str(e)}")

    def _process_attachments(self, article, attachments):
        """Process and save attachments for an article"""
        attachment_data = []

        try:
            # Create attachments directory if it doesn't exist
            attachments_dir = os.path.join(settings.MEDIA_ROOT, "knowledge_base")
            if not os.path.exists(attachments_dir):
                os.makedirs(attachments_dir, exist_ok=True)

            # Process each attachment
            for attachment_file in attachments:
                # Generate unique identifier
                attachment_identifier = f"kb-{uuid.uuid4().hex[:8]}-{int(time.time())}"
                original_filename = attachment_file.name

                # Use FileSystemStorage to save the file
                fs = FileSystemStorage(location=attachments_dir)
                filename = fs.save(f"{attachment_identifier}-{original_filename}", attachment_file)

                # Store relative path from MEDIA_ROOT
                file_url = f"knowledge_base/{filename}"

                # Determine file type
                file_extension = os.path.splitext(attachment_file.name)[1].lower()
                if file_extension in [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"]:
                    file_type = "image"
                elif file_extension in [".mp4", ".webm", ".avi", ".mov", ".wmv"]:
                    file_type = "video"
                elif file_extension in [".mp3", ".wav", ".ogg"]:
                    file_type = "audio"
                elif file_extension in [".pdf"]:
                    file_type = "pdf"
                else:
                    file_type = "document"

                # Create attachment record
                attachment = KnowledgeBaseAttachment.objects.create(article=article, filename=original_filename, file_url=file_url, file_type=file_type)

                # Add to response data
                attachment_data.append(
                    {
                        "id": attachment.id,
                        "filename": original_filename,
                        "file_url": self._get_full_attachment_url(file_url),
                        "file_type": file_type,
                    }
                )

        except Exception as e:
            logger.error(f"Error processing attachments: {str(e)}")

        return attachment_data

    def _get_full_attachment_url(self, relative_url):
        """Convert relative media URL to absolute URL"""
        if not relative_url:
            return None

        if relative_url.startswith("http"):
            return relative_url

        return f"{settings.MEDIA_URL}{relative_url}"

    def _get_related_articles(self, article, max_results=3):
        """Get related articles based on topic only (tags removed)"""
        related_by_topic = []
        if article.topic:
            related_by_topic = KnowledgeBaseArticle.objects.filter(topic=article.topic, is_published=True, is_deleted=False).exclude(id=article.id)[:max_results]

        # Combine and remove duplicates while preserving order
        seen = set()
        related_articles = []

        for related in related_by_topic:
            if related.id not in seen:
                seen.add(related.id)
                related_articles.append(related)

        # Format for response
        result = []
        for related in related_articles:
            result.append(
                {
                    "id": related.id,
                    "title": related.title,
                    "author": related.author.user.username,
                    "created_at": related.created_at.strftime("%Y-%m-%d"),
                    "topic": ({"id": related.topic.id, "name": related.topic.name} if related.topic else None),
                }
            )

        return result
