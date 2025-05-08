import os
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q, Count, F
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from api.models import (
    ForumThread,
    ForumReply,
    ForumTopic,
    ForumTag,
    ForumLike,
    ForumAnalytics,
)
from app.models import UserData

# Initialize logger
logger = logging.getLogger(__name__)



class CommunityForumController:
    def __init__(self):
        """Initialize the Community Forum Controller"""
        # Ensure analytics exists
        self.analytics, created = ForumAnalytics.objects.get_or_create(id=1)
        if created:
            logger.info("Created new forum analytics record")

    def create_thread(self, title, content, user_data, topic_id, tags=None):
        """
        Create a new forum thread

        Args:
            title (str): Thread title
            content (str): Thread content
            user_data (UserData): Author user data
            topic_id (int): ID of the topic
            tags (list, optional): List of tag IDs

        Returns:
            dict: Response with thread details or error
        """
        try:
            # Validate fields
            if not title or not content or not topic_id:
                return {
                    "success": False,
                    "error": "Missing required fields",
                    "code": "FORUM_MISSING_FIELDS",
                }

            # Get topic
            try:
                topic = ForumTopic.objects.get(id=topic_id)
            except ForumTopic.DoesNotExist:
                return {"success": False, "error": "Topic not found", "code": "FORUM_TOPIC_NOT_FOUND"}

            # Create thread
            thread = ForumThread.objects.create(
                title=title, content=content, author=user_data, topic=topic
            )

            # Add tags
            if tags:
                thread.tags.set(tags)

            # Update analytics
            self.analytics.total_threads += 1
            self.analytics.save()

            return {
                "success": True,
                "thread_id": thread.id,
                "approval_status": thread.approval_status,
                "code": "FORUM_THREAD_CREATED",
            }

        except Exception as e:
            logger.error(f"Error creating thread: {str(e)}")
            return {
                "success": False,
                "error": f"Error creating thread: {str(e)}",
                "code": "FORUM_CREATE_ERROR",
            }

    def moderate_thread(self, thread_id, approval_status, moderator):
        """
        Moderate (approve/reject) a forum thread

        Args:
            thread_id (int): ID of the thread to moderate
            approval_status (str): 'approved' or 'rejected'
            moderator (User): Moderator user object

        Returns:
            dict: Response with status
        """
        try:
            # Check if user is moderator/staff
            user_data = UserData.objects.get(user=moderator)
            if not (user_data.is_moderator() or moderator.is_staff):
                return {
                    "success": False,
                    "error": "Permission denied. Only moderators can perform this action.",
                    "code": "FORUM_PERMISSION_DENIED",
                }

            # Get thread
            try:
                thread = ForumThread.objects.get(id=thread_id)
            except ForumThread.DoesNotExist:
                return {"success": False, "error": "Thread not found", "code": "FORUM_THREAD_NOT_FOUND"}

            # Update approval status
            if approval_status not in ["approved", "rejected"]:
                return {
                    "success": False,
                    "error": "Invalid approval status. Use 'approved' or 'rejected'.",
                    "code": "FORUM_INVALID_STATUS",
                }

            thread.approval_status = approval_status
            thread.save()

            # Send email notification to author
            try:
                author_email = thread.author.user.email
                if author_email:
                    status_text = "approved" if approval_status == "approved" else "rejected"
                    send_mail(
                        subject=f"Your forum thread has been {status_text}",
                        message=f"Hello {thread.author.user.username},\n\nYour forum thread '{thread.title}' has been {status_text} by our moderators.\n\n"
                        + (
                            f"You can view it in the community forum."
                            if approval_status == "approved"
                            else "If you believe this is a mistake, please contact our support team."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[author_email],
                        fail_silently=True,
                    )
            except Exception as email_err:
                logger.error(f"Failed to send thread moderation email: {str(email_err)}")
                # Continue even if email fails

            return {
                "success": True,
                "thread_id": thread.id,
                "approval_status": thread.approval_status,
                "code": f"FORUM_THREAD_{approval_status.upper()}",
            }

        except Exception as e:
            logger.error(f"Error moderating thread: {str(e)}")
            return {
                "success": False,
                "error": f"Error moderating thread: {str(e)}",
                "code": "FORUM_MODERATE_ERROR",
            }

    def add_reply(self, thread_id, content, user_data, parent_reply_id=None, media_file=None):
        """
        Add a reply to a thread or another reply

        Args:
            thread_id (int): ID of the thread
            content (str): Reply content
            user_data (UserData): User data of the replier
            parent_reply_id (int, optional): ID of parent reply if this is a nested reply
            media_file (File, optional): Media file attachment

        Returns:
            dict: Response with reply details or error
        """
        try:
            # Validate fields
            if not content:
                return {
                    "success": False,
                    "error": "Reply content is required",
                    "code": "FORUM_MISSING_CONTENT",
                }

            # Get thread
            try:
                thread = ForumThread.objects.get(
                    id=thread_id, approval_status="approved", is_deleted=False
                )
            except ForumThread.DoesNotExist:
                return {
                    "success": False,
                    "error": "Thread not found or not approved",
                    "code": "FORUM_THREAD_NOT_FOUND",
                }

            # Check parent reply if provided
            parent_reply = None
            if parent_reply_id:
                try:
                    parent_reply = ForumReply.objects.get(id=parent_reply_id, is_deleted=False)
                    if parent_reply.thread.id != thread.id:
                        return {
                            "success": False,
                            "error": "Parent reply does not belong to this thread",
                            "code": "FORUM_INVALID_PARENT",
                        }
                except ForumReply.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Parent reply not found",
                        "code": "FORUM_REPLY_NOT_FOUND",
                    }

            # Create reply
            reply = ForumReply.objects.create(
                content=content, author=user_data, thread=thread, parent_reply=parent_reply
            )

            # Handle media file if provided
            media_url = None
            if media_file:
                fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/forum/")
                filename = fs.save(f"reply_{reply.id}_{media_file.name}", media_file)
                media_url = fs.url(filename)

                # TODO: Store media URL in reply or related model

            # Update thread last activity time
            thread.last_active = timezone.now()
            thread.save()

            # Update analytics
            self.analytics.total_replies += 1
            self.analytics.save()

            # Send notification email to thread author if not the same as reply author
            if thread.author.id != user_data.id:
                try:
                    author_email = thread.author.user.email
                    if author_email:
                        send_mail(
                            subject=f"New reply on your thread: {thread.title}",
                            message=f"Hello {thread.author.user.username},\n\n{user_data.user.username} has replied to your thread '{thread.title}'.\n\nView the reply in the community forum.",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[author_email],
                            fail_silently=True,
                        )
                except Exception as email_err:
                    logger.error(f"Failed to send reply notification email: {str(email_err)}")

            # Send notification to parent reply author if applicable
            if parent_reply and parent_reply.author.id != user_data.id:
                try:
                    parent_author_email = parent_reply.author.user.email
                    if parent_author_email:
                        send_mail(
                            subject=f"New reply to your comment",
                            message=f"Hello {parent_reply.author.user.username},\n\n{user_data.user.username} has replied to your comment in the thread '{thread.title}'.\n\nView the reply in the community forum.",
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[parent_author_email],
                            fail_silently=True,
                        )
                except Exception as email_err:
                    logger.error(f"Failed to send reply notification email: {str(email_err)}")

            return {
                "success": True,
                "reply_id": reply.id,
                "media_url": media_url,
                "code": "FORUM_REPLY_CREATED",
            }

        except Exception as e:
            logger.error(f"Error adding reply: {str(e)}")
            return {
                "success": False,
                "error": f"Error adding reply: {str(e)}",
                "code": "FORUM_REPLY_ERROR",
            }

    def toggle_like(self, user_data, thread_id=None, reply_id=None):
        """
        Toggle like/upvote on a thread or reply

        Args:
            user_data (UserData): User data of the liker
            thread_id (int, optional): ID of thread to like
            reply_id (int, optional): ID of reply to like

        Returns:
            dict: Response with like status
        """
        try:
            # Check if either thread_id or reply_id is provided
            if (thread_id is None and reply_id is None) or (thread_id and reply_id):
                return {
                    "success": False,
                    "error": "Must provide either thread_id or reply_id, not both",
                    "code": "FORUM_INVALID_LIKE_TARGET",
                }

            # Find the target object
            target = None
            if thread_id:
                try:
                    target = ForumThread.objects.get(
                        id=thread_id, approval_status="approved", is_deleted=False
                    )
                    existing_like = ForumLike.objects.filter(
                        user=user_data, thread=target, reply=None
                    ).first()
                except ForumThread.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Thread not found or not approved",
                        "code": "FORUM_THREAD_NOT_FOUND",
                    }
            else:
                try:
                    target = ForumReply.objects.get(id=reply_id, is_deleted=False)
                    existing_like = ForumLike.objects.filter(
                        user=user_data, reply=target, thread=None
                    ).first()
                except ForumReply.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Reply not found",
                        "code": "FORUM_REPLY_NOT_FOUND",
                    }

            # Toggle like status
            if existing_like:
                existing_like.delete()
                action = "removed"
                # Update analytics
                self.analytics.total_likes -= 1
                self.analytics.save()
            else:
                # Create new like
                if thread_id:
                    ForumLike.objects.create(user=user_data, thread=target)
                else:
                    ForumLike.objects.create(user=user_data, reply=target)
                action = "added"
                # Update analytics
                self.analytics.total_likes += 1
                self.analytics.save()

            # Get updated like count
            if thread_id:
                like_count = ForumLike.objects.filter(thread=target).count()
            else:
                like_count = ForumLike.objects.filter(reply=target).count()

            return {
                "success": True,
                "action": action,
                "like_count": like_count,
                "code": f"FORUM_LIKE_{action.upper()}",
            }

        except Exception as e:
            logger.error(f"Error toggling like: {str(e)}")
            return {
                "success": False,
                "error": f"Error toggling like: {str(e)}",
                "code": "FORUM_LIKE_ERROR",
            }

    def edit_thread(self, thread_id, user_data, title=None, content=None, tags=None):
        """
        Edit an existing thread

        Args:
            thread_id (int): ID of the thread to edit
            user_data (UserData): User data of the editor
            title (str, optional): New title
            content (str, optional): New content
            tags (list, optional): New list of tag IDs

        Returns:
            dict: Response with status
        """
        try:
            # Get thread
            try:
                thread = ForumThread.objects.get(id=thread_id, is_deleted=False)
            except ForumThread.DoesNotExist:
                return {"success": False, "error": "Thread not found", "code": "FORUM_THREAD_NOT_FOUND"}

            # Check ownership or moderator status
            if thread.author.id != user_data.id and not (
                user_data.is_moderator() or user_data.user.is_staff
            ):
                return {
                    "success": False,
                    "error": "Permission denied. You can only edit your own threads.",
                    "code": "FORUM_PERMISSION_DENIED",
                }

            # Update fields
            if title:
                thread.title = title

            if content:
                thread.content = content

            if tags is not None:
                thread.tags.set(tags)

            thread.save()

            return {"success": True, "thread_id": thread.id, "code": "FORUM_THREAD_UPDATED"}

        except Exception as e:
            logger.error(f"Error editing thread: {str(e)}")
            return {
                "success": False,
                "error": f"Error editing thread: {str(e)}",
                "code": "FORUM_THREAD_EDIT_ERROR",
            }

    def delete_thread(self, thread_id, user_data):
        """
        Delete/soft-delete a thread

        Args:
            thread_id (int): ID of the thread to delete
            user_data (UserData): User data of the deleter

        Returns:
            dict: Response with status
        """
        try:
            # Get thread
            try:
                thread = ForumThread.objects.get(id=thread_id, is_deleted=False)
            except ForumThread.DoesNotExist:
                return {"success": False, "error": "Thread not found", "code": "FORUM_THREAD_NOT_FOUND"}

            # Check ownership or moderator status
            if thread.author.id != user_data.id and not (
                user_data.is_moderator() or user_data.user.is_staff
            ):
                return {
                    "success": False,
                    "error": "Permission denied. You can only delete your own threads.",
                    "code": "FORUM_PERMISSION_DENIED",
                }

            # Soft delete the thread
            thread.is_deleted = True
            thread.save()

            return {"success": True, "code": "FORUM_THREAD_DELETED"}

        except Exception as e:
            logger.error(f"Error deleting thread: {str(e)}")
            return {
                "success": False,
                "error": f"Error deleting thread: {str(e)}",
                "code": "FORUM_THREAD_DELETE_ERROR",
            }

    def edit_reply(self, reply_id, user_data, content):
        """
        Edit an existing reply

        Args:
            reply_id (int): ID of the reply to edit
            user_data (UserData): User data of the editor
            content (str): New content

        Returns:
            dict: Response with status
        """
        try:
            # Get reply
            try:
                reply = ForumReply.objects.get(id=reply_id, is_deleted=False)
            except ForumReply.DoesNotExist:
                return {"success": False, "error": "Reply not found", "code": "FORUM_REPLY_NOT_FOUND"}

            # Check ownership or moderator status
            if reply.author.id != user_data.id and not (
                user_data.is_moderator() or user_data.user.is_staff
            ):
                return {
                    "success": False,
                    "error": "Permission denied. You can only edit your own replies.",
                    "code": "FORUM_PERMISSION_DENIED",
                }

            # Update content
            reply.content = content
            reply.save()

            return {"success": True, "reply_id": reply.id, "code": "FORUM_REPLY_UPDATED"}

        except Exception as e:
            logger.error(f"Error editing reply: {str(e)}")
            return {
                "success": False,
                "error": f"Error editing reply: {str(e)}",
                "code": "FORUM_REPLY_EDIT_ERROR",
            }

    def delete_reply(self, reply_id, user_data):
        """
        Delete/soft-delete a reply

        Args:
            reply_id (int): ID of the reply to delete
            user_data (UserData): User data of the deleter

        Returns:
            dict: Response with status
        """
        try:
            # Get reply
            try:
                reply = ForumReply.objects.get(id=reply_id, is_deleted=False)
            except ForumReply.DoesNotExist:
                return {"success": False, "error": "Reply not found", "code": "FORUM_REPLY_NOT_FOUND"}

            # Check ownership or moderator status
            if reply.author.id != user_data.id and not (
                user_data.is_moderator() or user_data.user.is_staff
            ):
                return {
                    "success": False,
                    "error": "Permission denied. You can only delete your own replies.",
                    "code": "FORUM_PERMISSION_DENIED",
                }

            # Soft delete the reply
            reply.is_deleted = True
            reply.save()

            return {"success": True, "code": "FORUM_REPLY_DELETED"}

        except Exception as e:
            logger.error(f"Error deleting reply: {str(e)}")
            return {
                "success": False,
                "error": f"Error deleting reply: {str(e)}",
                "code": "FORUM_REPLY_DELETE_ERROR",
            }

    def get_threads(self, topic_id=None, tag_id=None, page=1, items_per_page=20, user_data=None):
        """
        Get threads with pagination

        Args:
            topic_id (int, optional): Filter by topic ID
            tag_id (int, optional): Filter by tag ID
            page (int): Page number
            items_per_page (int): Items per page
            user_data (UserData, optional): If provided, filter by user's threads

        Returns:
            dict: Response with thread list
        """
        try:
            # Base query - only approved threads unless filtering by user
            base_query = Q(is_deleted=False)

            if user_data:
                # If viewing own threads, show all statuses
                if topic_id:
                    base_query &= Q(topic_id=topic_id)
                threads = ForumThread.objects.filter(base_query & Q(author=user_data))
            else:
                # Otherwise only show approved threads
                base_query &= Q(approval_status="approved")
                if topic_id:
                    base_query &= Q(topic_id=topic_id)
                threads = ForumThread.objects.filter(base_query)

            # Additional filtering
            if tag_id:
                threads = threads.filter(tags__id=tag_id)

            # Annotate with counts
            threads = threads.annotate(
                reply_count=Count("replies", filter=Q(replies__is_deleted=False)),
                like_count=Count("likes"),
            )

            # Order by last activity
            threads = threads.order_by("-last_active")

            # Paginate results
            paginator = Paginator(threads, items_per_page)
            try:
                paginated_threads = paginator.page(page)
            except PageNotAnInteger:
                paginated_threads = paginator.page(1)
            except EmptyPage:
                paginated_threads = paginator.page(paginator.num_pages)

            # Format response
            result_threads = []
            for thread in paginated_threads:
                author_username = thread.author.user.username

                result_threads.append(
                    {
                        "id": thread.id,
                        "title": thread.title,
                        "author": author_username,
                        "created_at": thread.created_at,
                        "last_active": thread.last_active,
                        "reply_count": thread.reply_count,
                        "like_count": thread.like_count,
                        "topic": {"id": thread.topic.id, "name": thread.topic.name},
                        "tags": [{"id": tag.id, "name": tag.name} for tag in thread.tags.all()],
                        "approval_status": thread.approval_status,
                        "view_count": thread.view_count,
                    }
                )

            return {
                "success": True,
                "threads": result_threads,
                "page": page,
                "pages": paginator.num_pages,
                "total": paginator.count,
                "code": "FORUM_THREADS_FETCHED",
            }

        except Exception as e:
            logger.error(f"Error fetching threads: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching threads: {str(e)}",
                "code": "FORUM_THREAD_FETCH_ERROR",
            }

    def get_thread_detail(self, thread_id, user_data=None):
        """
        Get detailed information about a thread

        Args:
            thread_id (int): ID of the thread
            user_data (UserData, optional): Current user data to check permissions

        Returns:
            dict: Response with thread details
        """
        try:
            # Get thread
            try:
                thread = ForumThread.objects.get(id=thread_id)

                # Check if thread is deleted
                if thread.is_deleted:
                    return {
                        "success": False,
                        "error": "Thread has been deleted",
                        "code": "FORUM_THREAD_DELETED",
                    }

                # Check if thread is approved or user is author/moderator
                if thread.approval_status != "approved":
                    if not user_data or (
                        user_data.id != thread.author.id
                        and not user_data.is_moderator()
                        and not user_data.user.is_staff
                    ):
                        return {
                            "success": False,
                            "error": "Thread is not approved",
                            "code": "FORUM_THREAD_NOT_APPROVED",
                        }

            except ForumThread.DoesNotExist:
                return {"success": False, "error": "Thread not found", "code": "FORUM_THREAD_NOT_FOUND"}

            # Increment view count
            thread.view_count += 1
            thread.save()

            # Get replies
            replies = ForumReply.objects.filter(
                thread=thread, is_deleted=False, parent_reply=None
            ).select_related("author__user")

            # Format replies
            formatted_replies = []
            for reply in replies:
                # Get child replies (nested comments)
                child_replies = ForumReply.objects.filter(
                    parent_reply=reply, is_deleted=False
                ).select_related("author__user")

                formatted_child_replies = []
                for child in child_replies:
                    like_count = ForumLike.objects.filter(reply=child).count()
                    user_liked = False
                    if user_data:
                        user_liked = ForumLike.objects.filter(user=user_data, reply=child).exists()

                    formatted_child_replies.append(
                        {
                            "id": child.id,
                            "content": child.content,
                            "author": child.author.user.username,
                            "created_at": child.created_at,
                            "like_count": like_count,
                            "user_liked": user_liked,
                        }
                    )

                # Get like info for parent reply
                like_count = ForumLike.objects.filter(reply=reply).count()
                user_liked = False
                if user_data:
                    user_liked = ForumLike.objects.filter(user=user_data, reply=reply).exists()

                formatted_replies.append(
                    {
                        "id": reply.id,
                        "content": reply.content,
                        "author": reply.author.user.username,
                        "created_at": reply.created_at,
                        "replies": formatted_child_replies,
                        "like_count": like_count,
                        "user_liked": user_liked,
                    }
                )

            # Check if user has liked the thread
            user_liked_thread = False
            if user_data:
                user_liked_thread = ForumLike.objects.filter(user=user_data, thread=thread).exists()

            # Get like count for thread
            thread_like_count = ForumLike.objects.filter(thread=thread).count()

            # Format response
            thread_detail = {
                "id": thread.id,
                "title": thread.title,
                "content": thread.content,
                "author": thread.author.user.username,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
                "last_active": thread.last_active,
                "approval_status": thread.approval_status,
                "view_count": thread.view_count,
                "topic": {
                    "id": thread.topic.id,
                    "name": thread.topic.name,
                    "description": thread.topic.description,
                },
                "tags": [{"id": tag.id, "name": tag.name} for tag in thread.tags.all()],
                "replies": formatted_replies,
                "reply_count": len(formatted_replies),
                "like_count": thread_like_count,
                "user_liked": user_liked_thread,
            }

            return {"success": True, "thread": thread_detail, "code": "FORUM_THREAD_FETCHED"}

        except Exception as e:
            logger.error(f"Error fetching thread detail: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching thread detail: {str(e)}",
                "code": "FORUM_THREAD_DETAIL_ERROR",
            }

    def get_topics(self):
        """
        Get all forum topics

        Returns:
            dict: Response with list of topics
        """
        try:
            topics = ForumTopic.objects.all()

            # Count threads per topic
            topic_data = []
            for topic in topics:
                thread_count = ForumThread.objects.filter(
                    topic=topic, approval_status="approved", is_deleted=False
                ).count()

                topic_data.append(
                    {
                        "id": topic.id,
                        "name": topic.name,
                        "description": topic.description,
                        "thread_count": thread_count,
                    }
                )

            return {"success": True, "topics": topic_data, "code": "FORUM_TOPICS_FETCHED"}

        except Exception as e:
            logger.error(f"Error fetching topics: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching topics: {str(e)}",
                "code": "FORUM_TOPICS_ERROR",
            }

    def get_tags(self):
        """
        Get all forum tags

        Returns:
            dict: Response with list of tags
        """
        try:
            tags = ForumTag.objects.all()

            # Count threads per tag
            tag_data = []
            for tag in tags:
                thread_count = ForumThread.objects.filter(
                    tags=tag, approval_status="approved", is_deleted=False
                ).count()

                tag_data.append({"id": tag.id, "name": tag.name, "thread_count": thread_count})

            return {"success": True, "tags": tag_data, "code": "FORUM_TAGS_FETCHED"}

        except Exception as e:
            logger.error(f"Error fetching tags: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching tags: {str(e)}",
                "code": "FORUM_TAGS_ERROR",
            }

    def search_threads(self, query, page=1, items_per_page=20):
        """
        Search threads by keywords or phrases

        Args:
            query (str): Search query
            page (int): Page number
            items_per_page (int): Items per page

        Returns:
            dict: Response with search results
        """
        try:
            if not query or len(query.strip()) < 3:
                return {
                    "success": False,
                    "error": "Search query must be at least 3 characters",
                    "code": "FORUM_SEARCH_TOO_SHORT",
                }

            # Search in title, content and tags
            threads = ForumThread.objects.filter(
                Q(title__icontains=query)
                | Q(content__icontains=query)
                | Q(tags__name__icontains=query),
                approval_status="approved",
                is_deleted=False,
            ).distinct()

            # Annotate with counts
            threads = threads.annotate(
                reply_count=Count("replies", filter=Q(replies__is_deleted=False)),
                like_count=Count("likes"),
            )

            # Order by relevance (title match first, then content)
            threads = threads.order_by(
                # Title exact match gets highest priority
                ~Q(title__iexact=query),
                # Then title contains
                ~Q(title__icontains=query),
                # Then content contains
                ~Q(content__icontains=query),
                # Finally by last activity
                "-last_active",
            )

            # Paginate results
            paginator = Paginator(threads, items_per_page)
            try:
                paginated_threads = paginator.page(page)
            except PageNotAnInteger:
                paginated_threads = paginator.page(1)
            except EmptyPage:
                paginated_threads = paginator.page(paginator.num_pages)

            # Format response
            result_threads = []
            for thread in paginated_threads:
                result_threads.append(
                    {
                        "id": thread.id,
                        "title": thread.title,
                        "author": thread.author.user.username,
                        "created_at": thread.created_at,
                        "last_active": thread.last_active,
                        "reply_count": thread.reply_count,
                        "like_count": thread.like_count,
                        "topic": {"id": thread.topic.id, "name": thread.topic.name},
                        "tags": [{"id": tag.id, "name": tag.name} for tag in thread.tags.all()],
                        # Include a small content preview
                        "preview": thread.content[:150] + ("..." if len(thread.content) > 150 else ""),
                    }
                )

            return {
                "success": True,
                "threads": result_threads,
                "page": page,
                "pages": paginator.num_pages,
                "total": paginator.count,
                "query": query,
                "code": "FORUM_SEARCH_RESULTS",
            }

        except Exception as e:
            logger.error(f"Error searching threads: {str(e)}")
            return {
                "success": False,
                "error": f"Error searching threads: {str(e)}",
                "code": "FORUM_SEARCH_ERROR",
            }



