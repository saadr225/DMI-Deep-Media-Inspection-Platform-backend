import os
import logging
import time
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q, Count, F
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.models import Group, User

from api.models import (
    ForumThread,
    ForumReply,
    ForumTopic,
    ForumTag,
    ForumLike,
    ForumAnalytics,
    ForumReaction,
    ForumNotification,
)
from app.models import UserData

# Initialize logger
logger = logging.getLogger(__name__)


class CommunityForumController:
    def __init__(self):
        """Initialize the Community Forum Controller"""
        self.analytics = None  # Initialize as None

    def _ensure_analytics(self):
        if self.analytics is None:
            self.analytics, _ = ForumAnalytics.objects.get_or_create(id=1)
        return self.analytics

    def create_thread(self, title, content, user_data, topic_id, tags=None, is_pinned=False):
        """
        Create a new forum thread

        Args:
            title (str): Thread title
            content (str): Thread content
            user_data (UserData): Author user data
            topic_id (int): ID of the topic
            tags (list, optional): List of tag IDs
            is_pinned (bool, optional): Whether thread should be pinned

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
                topic = ForumTopic.objects.get(id=topic_id, is_active=True)
            except ForumTopic.DoesNotExist:
                return {"success": False, "error": "Topic not found or inactive", "code": "FORUM_TOPIC_NOT_FOUND"}

            # Check for auto-approval
            auto_approve = user_data.is_verified or user_data.is_moderator() or user_data.user.is_staff
            approval_status = "approved" if auto_approve else "pending"

            # Create thread
            thread = ForumThread.objects.create(
                title=title, 
                content=content, 
                author=user_data, 
                topic=topic,
                approval_status=approval_status,
                is_pinned=is_pinned if user_data.is_moderator() or user_data.user.is_staff else False
            )

            # Add tags
            if tags:
                thread.tags.set(tags)

            # Update analytics
            analytics = self._ensure_analytics()
            analytics.total_threads += 1
            analytics.threads_today += 1
            analytics.save()
            
            # Create notification for moderators if needs approval
            if not auto_approve:
                try:
                    # Get all moderators
                    moderator_group = Group.objects.get(name="PDA_Moderator")
                    moderators = UserData.objects.filter(user__groups=moderator_group)
                    
                    # Notify moderators about new thread needing approval
                    for moderator in moderators:
                        notification_content = f"New thread '{title}' by {user_data.user.username} needs approval"
                        ForumNotification.objects.create(
                            user=moderator,
                            notification_type='thread_approval',
                            content=notification_content,
                            thread=thread,
                            from_user=user_data
                        )
                except Exception as notif_error:
                    logger.error(f"Error creating moderator notifications: {str(notif_error)}")

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

    def add_reply(self, thread_id, content, user_data, parent_reply_id=None, media_file=None, is_solution=False):
        """
        Add a reply to a thread or another reply

        Args:
            thread_id (int): ID of the thread
            content (str): Reply content
            user_data (UserData): User data of the replier
            parent_reply_id (int, optional): ID of parent reply if this is a nested reply
            media_file (File, optional): Media file attachment
            is_solution (bool, optional): Whether this reply is marked as a solution

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
                
                # Check if thread is locked
                if thread.is_locked:
                    return {
                        "success": False,
                        "error": "Thread is locked and cannot accept new replies",
                        "code": "FORUM_THREAD_LOCKED",
                    }
                
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

            # Handle media file if provided
            media_url = None
            media_type = None
            if media_file:
                fs = FileSystemStorage(location=f"{settings.MEDIA_ROOT}/forum/")
                filename = fs.save(f"reply_{user_data.id}_{int(time.time())}_{media_file.name}", media_file)
                media_url = fs.url(filename)
                
                # Determine media type based on file extension
                file_extension = os.path.splitext(media_file.name)[1].lower()
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                    media_type = 'image'
                elif file_extension in ['.mp4', '.webm', '.avi', '.mov', '.wmv']:
                    media_type = 'video'
                elif file_extension in ['.mp3', '.wav', '.ogg']:
                    media_type = 'audio'
                else:
                    media_type = 'document'

            # Only allow marking as solution if user is thread author or moderator
            can_mark_solution = user_data.id == thread.author.id or user_data.is_moderator() or user_data.user.is_staff
            is_solution = is_solution and can_mark_solution
            
            # Create reply
            reply = ForumReply.objects.create(
                content=content, 
                author=user_data, 
                thread=thread, 
                parent_reply=parent_reply,
                media_url=media_url,
                media_type=media_type,
                is_solution=is_solution
            )

            # Update thread last activity time
            thread.last_active = timezone.now()
            thread.save()

            # Update analytics
            analytics = self._ensure_analytics()
            analytics.total_replies += 1
            analytics.replies_today += 1
            analytics.save()

            # Create notification for thread author if not the same as reply author
            if thread.author.id != user_data.id:
                try:
                    notification_content = f"{user_data.user.username} replied to your thread '{thread.title}'"
                    ForumNotification.objects.create(
                        user=thread.author,
                        notification_type='reply',
                        content=notification_content,
                        thread=thread,
                        reply=reply,
                        from_user=user_data
                    )
                except Exception as notif_error:
                    logger.error(f"Failed to create thread reply notification: {str(notif_error)}")

            # Create notification for parent reply author if not the same as reply author
            if parent_reply and parent_reply.author.id != user_data.id:
                try:
                    notification_content = f"{user_data.user.username} replied to your comment in '{thread.title}'"
                    ForumNotification.objects.create(
                        user=parent_reply.author,
                        notification_type='reply',
                        content=notification_content,
                        thread=thread,
                        reply=reply,
                        from_user=user_data
                    )
                except Exception as notif_error:
                    logger.error(f"Failed to create parent reply notification: {str(notif_error)}")
                
            # Check for @mentions in content and create notifications
            self._process_mentions(content, user_data, thread, reply)

            return {
                "success": True,
                "reply_id": reply.id,
                "media_url": media_url,
                "media_type": media_type,
                "is_solution": reply.is_solution,
                "code": "FORUM_REPLY_CREATED",
            }

        except Exception as e:
            logger.error(f"Error adding reply: {str(e)}")
            return {
                "success": False,
                "error": f"Error adding reply: {str(e)}",
                "code": "FORUM_REPLY_ERROR",
            }
            
    def _process_mentions(self, content, from_user, thread, reply):
        """Process @mentions in content and create notifications"""
        import re
        
        # Find all @username mentions
        mentions = re.findall(r'@(\w+)', content)
        
        if not mentions:
            return
            
        # Create notifications for mentioned users
        for username in set(mentions):  # Use set to avoid duplicate notifications
            try:
                # Find the mentioned user
                mentioned_user = User.objects.filter(username=username).first()
                
                if mentioned_user and mentioned_user.id != from_user.user.id:
                    user_data = UserData.objects.get(user=mentioned_user)
                    
                    notification_content = f"{from_user.user.username} mentioned you in a comment"
                    ForumNotification.objects.create(
                        user=user_data,
                        notification_type='mention',
                        content=notification_content,
                        thread=thread,
                        reply=reply,
                        from_user=from_user
                    )
            except Exception as e:
                logger.error(f"Error processing mention for {username}: {str(e)}")
                # Continue processing other mentions even if one fails

    def toggle_like(self, user_data, thread_id=None, reply_id=None, like_type="like"):
        """
        Toggle like/dislike on a thread or reply

        Args:
            user_data (UserData): User data of the liker
            thread_id (int, optional): ID of thread to like/dislike
            reply_id (int, optional): ID of reply to like/dislike
            like_type (str, optional): Type of vote ('like' or 'dislike')

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

            # Validate like_type
            if like_type not in ["like", "dislike"]:
                return {
                    "success": False,
                    "error": "Invalid like type. Must be 'like' or 'dislike'",
                    "code": "FORUM_INVALID_LIKE_TYPE",
                }

            # Find the target object and check for existing likes/dislikes
            if thread_id:
                try:
                    target = ForumThread.objects.get(
                        id=thread_id, approval_status="approved", is_deleted=False
                    )
                    # Check for any existing like/dislike of any type
                    existing_like = ForumLike.objects.filter(user=user_data, thread=target).first()
                except ForumThread.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Thread not found or not approved",
                        "code": "FORUM_THREAD_NOT_FOUND",
                    }
            else:
                try:
                    target = ForumReply.objects.get(id=reply_id, is_deleted=False)
                    existing_like = ForumLike.objects.filter(user=user_data, reply=target).first()
                except ForumReply.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Reply not found",
                        "code": "FORUM_REPLY_NOT_FOUND",
                    }

            # Toggle like status
            if existing_like:
                if existing_like.like_type == like_type:
                    # If same type, remove it (toggle off)
                    existing_like.delete()
                    action = "removed"
                    # Update analytics
                    self.analytics.total_likes -= 1
                    self.analytics.save()
                else:
                    # If different type, change the type (switch from like to dislike or vice versa)
                    existing_like.like_type = like_type
                    existing_like.save()
                    action = "changed"
            else:
                # Create new like/dislike
                if thread_id:
                    ForumLike.objects.create(user=user_data, thread=target, like_type=like_type)
                else:
                    ForumLike.objects.create(user=user_data, reply=target, like_type=like_type)
                action = "added"
                # Update analytics
                self.analytics.total_likes += 1
                self.analytics.save()

            # Get updated counts
            if thread_id:
                like_count = ForumLike.objects.filter(thread=target, like_type="like").count()
                dislike_count = ForumLike.objects.filter(thread=target, like_type="dislike").count()
            else:
                like_count = ForumLike.objects.filter(reply=target, like_type="like").count()
                dislike_count = ForumLike.objects.filter(reply=target, like_type="dislike").count()

            return {
                "success": True,
                "action": action,
                "like_type": like_type,
                "like_count": like_count,
                "dislike_count": dislike_count,
                "code": f"FORUM_LIKE_{action.upper()}",
            }

        except Exception as e:
            logger.error(f"Error toggling like: {str(e)}")
            return {
                "success": False,
                "error": f"Error toggling like: {str(e)}",
                "code": "FORUM_LIKE_ERROR",
            }

    def edit_thread(self, thread_id, user_data, title=None, content=None, tags=None, is_pinned=None, is_locked=None):
        """
        Edit an existing thread

        Args:
            thread_id (int): ID of the thread to edit
            user_data (UserData): User data of the editor
            title (str, optional): New title
            content (str, optional): New content
            tags (list, optional): New list of tag IDs
            is_pinned (bool, optional): Whether the thread should be pinned
            is_locked (bool, optional): Whether the thread should be locked

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
            is_moderator = user_data.is_moderator() or user_data.user.is_staff
            if thread.author.id != user_data.id and not is_moderator:
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
                
            # Only moderators can pin/unlock threads
            if is_moderator:
                if is_pinned is not None:
                    thread.is_pinned = is_pinned
                    
                if is_locked is not None:
                    thread.is_locked = is_locked
                    
                    # Create notification for thread author about thread lock status
                    if is_locked != thread.is_locked and thread.author.id != user_data.id:
                        try:
                            status_text = "locked" if is_locked else "unlocked"
                            notification_content = f"Your thread '{thread.title}' has been {status_text} by a moderator"
                            ForumNotification.objects.create(
                                user=thread.author,
                                notification_type='thread_status',
                                content=notification_content,
                                thread=thread,
                                from_user=user_data
                            )
                        except Exception as notif_error:
                            logger.error(f"Failed to create thread lock notification: {str(notif_error)}")

            thread.save()

            return {
                "success": True, 
                "thread_id": thread.id, 
                "is_pinned": thread.is_pinned,
                "is_locked": thread.is_locked,
                "code": "FORUM_THREAD_UPDATED"
            }

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
            
            # Update analytics
            analytics = self._ensure_analytics()
            analytics.total_views += 1
            analytics.save()

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
                    # Get likes for child reply
                    like_count = ForumLike.objects.filter(reply=child, like_type="like").count()
                    dislike_count = ForumLike.objects.filter(reply=child, like_type="dislike").count()
                    
                    # Check if user has liked the child reply
                    user_liked = False
                    user_disliked = False
                    if user_data:
                        user_liked = ForumLike.objects.filter(user=user_data, reply=child, like_type="like").exists()
                        user_disliked = ForumLike.objects.filter(user=user_data, reply=child, like_type="dislike").exists()
                    
                    # Get reactions for child reply
                    child_reactions = self.get_reaction_counts(reply_id=child.id)
                    
                    # Calculate time ago
                    time_ago = self._calculate_time_ago(child.created_at)
                    
                    # Get child author details
                    child_author = {
                        "username": child.author.user.username,
                        "avatar": child.author.profile_image_url,
                        "joinDate": child.author.user.date_joined.strftime("%B %Y"),
                        "isVerified": child.author.is_verified or child.author.user.is_staff
                    }

                    formatted_child_replies.append({
                        "id": child.id,
                        "content": child.content,
                        "author": child_author,
                        "created_at": child.created_at,
                        "timeAgo": time_ago,
                        "likes": like_count,
                        "dislikes": dislike_count,
                        "reactions": child_reactions,
                        "user_liked": user_liked,
                        "user_disliked": user_disliked,
                        "media_url": child.media_url,
                        "media_type": child.media_type,
                        "is_solution": child.is_solution,
                    })

                # Get like info for parent reply
                like_count = ForumLike.objects.filter(reply=reply, like_type="like").count()
                dislike_count = ForumLike.objects.filter(reply=reply, like_type="dislike").count()
                
                # Check if user has liked/disliked the parent reply
                user_liked = False
                user_disliked = False
                if user_data:
                    user_liked = ForumLike.objects.filter(user=user_data, reply=reply, like_type="like").exists()
                    user_disliked = ForumLike.objects.filter(user=user_data, reply=reply, like_type="dislike").exists()
                
                # Get reactions for parent reply
                reply_reactions = self.get_reaction_counts(reply_id=reply.id)
                
                # Calculate time ago for parent reply
                time_ago = self._calculate_time_ago(reply.created_at)
                
                # Get parent reply author details
                reply_author = {
                    "username": reply.author.user.username,
                    "avatar": reply.author.profile_image_url,
                    "joinDate": reply.author.user.date_joined.strftime("%B %Y"),
                    "postCount": self._get_user_post_count(reply.author),
                    "isVerified": reply.author.is_verified or reply.author.user.is_staff
                }

                formatted_replies.append({
                    "id": reply.id,
                    "content": reply.content,
                    "author": reply_author,
                    "created_at": reply.created_at,
                    "updated_at": reply.updated_at,
                    "timeAgo": time_ago,
                    "replies": formatted_child_replies,
                    "likes": like_count,
                    "dislikes": dislike_count,
                    "reactions": reply_reactions,
                    "user_liked": user_liked,
                    "user_disliked": user_disliked,
                    "media_url": reply.media_url,
                    "media_type": reply.media_type,
                    "is_solution": reply.is_solution,
                })

            # Check if user has liked or disliked the thread
            user_liked_thread = False
            user_disliked_thread = False
            if user_data:
                user_liked_thread = ForumLike.objects.filter(
                    user=user_data, thread=thread, like_type="like"
                ).exists()
                user_disliked_thread = ForumLike.objects.filter(
                    user=user_data, thread=thread, like_type="dislike"
                ).exists()

            # Get like and dislike counts for thread
            thread_like_count = ForumLike.objects.filter(thread=thread, like_type="like").count()
            thread_dislike_count = ForumLike.objects.filter(thread=thread, like_type="dislike").count()
            
            # Get reactions for thread
            reactions = self.get_reaction_counts(thread_id=thread_id)
            
            # Format date strings
            created_date = thread.created_at.strftime("%B %d, %Y")
            time_ago = self._calculate_time_ago(thread.created_at)
            
            # Get author details including post count and join date
            author = thread.author
            author_details = {
                "username": author.user.username,
                "avatar": author.profile_image_url,
                "joinDate": author.user.date_joined.strftime("%B %Y"),
                "postCount": self._get_user_post_count(author),
                "isVerified": author.is_verified or author.user.is_staff
            }
            
            # Set thread status based on approval status and locked state
            thread_status = "open"
            if thread.approval_status == "pending":
                thread_status = "pending"
            elif thread.approval_status == "rejected":
                thread_status = "closed"
            elif thread.is_locked:
                thread_status = "locked"
            
            # Get tag names
            tags = [tag.name for tag in thread.tags.all()]

            # Format response
            thread_detail = {
                "id": thread.id,
                "title": thread.title,
                "content": thread.content,
                "author": author_details,
                "date": created_date,
                "timeAgo": time_ago,
                "views": thread.view_count,
                "likes": thread_like_count,
                "upvotes": thread_like_count,
                "downvotes": thread_dislike_count,
                "tags": tags,
                "status": thread_status,
                "reactions": reactions,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
                "last_active": thread.last_active,
                "approval_status": thread.approval_status,
                "is_pinned": thread.is_pinned,
                "is_locked": thread.is_locked,
                "topic": {
                    "id": thread.topic.id,
                    "name": thread.topic.name,
                    "description": thread.topic.description,
                    "icon": thread.topic.icon,
                },
                "replies": formatted_replies,
                "reply_count": len(formatted_replies),
                "user_liked": user_liked_thread if user_data else False,
                "user_disliked": user_disliked_thread if user_data else False,
            }

            return {"success": True, "thread": thread_detail, "code": "FORUM_THREAD_FETCHED"}

        except Exception as e:
            logger.error(f"Error fetching thread detail: {str(e)}")
            return {
                "success": False,
                "error": f"Error fetching thread detail: {str(e)}",
                "code": "FORUM_THREAD_DETAIL_ERROR",
            }

    def _calculate_time_ago(self, timestamp):
        """Helper method to calculate time ago string from timestamp"""
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - timestamp
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60
        
        if days > 365:
            years = days // 365
            return f"{years} {'year' if years == 1 else 'years'} ago"
        elif days > 30:
            months = days // 30
            return f"{months} {'month' if months == 1 else 'months'} ago"
        elif days > 0:
            return f"{days} {'day' if days == 1 else 'days'} ago"
        elif hours > 0:
            return f"{hours} {'hour' if hours == 1 else 'hours'} ago"
        elif minutes > 0:
            return f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"
        else:
            return "just now"
    
    def _get_user_post_count(self, user_data):
        """Helper method to get total post count for a user"""
        thread_count = ForumThread.objects.filter(author=user_data, is_deleted=False).count()
        reply_count = ForumReply.objects.filter(author=user_data, is_deleted=False).count()
        return thread_count + reply_count

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

    def get_reaction_counts(self, thread_id=None, reply_id=None):
        """
        Get reaction counts for a thread or reply

        Args:
            thread_id (int, optional): ID of thread
            reply_id (int, optional): ID of reply

        Returns:
            list: List of reactions with counts and user lists
        """
        try:
            if thread_id:
                reactions = ForumReaction.objects.filter(thread_id=thread_id)
            elif reply_id:
                reactions = ForumReaction.objects.filter(reply_id=reply_id)
            else:
                return []
            
            # Group by reaction type and count
            result = {}
            for reaction in reactions:
                reaction_type = reaction.reaction_type
                if reaction_type not in result:
                    result[reaction_type] = {
                        "emoji": reaction_type,
                        "count": 0,
                        "users": []
                    }
                
                result[reaction_type]["count"] += 1
                # Add username to users list
                result[reaction_type]["users"].append(reaction.user.user.username)
            
            return list(result.values())
        
        except Exception as e:
            logger.error(f"Error getting reaction counts: {str(e)}")
            return []

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

            # Validate reaction type (ensure it's one of the allowed emojis)
            valid_reaction_types = dict(ForumReaction.REACTION_TYPES).keys()
            if reaction_type not in valid_reaction_types:
                return {
                    "success": False,
                    "error": f"Invalid reaction type. Must be one of: {', '.join(valid_reaction_types)}",
                    "code": "FORUM_INVALID_REACTION_TYPE",
                }

            # Find the target object
            if thread_id:
                try:
                    target = ForumThread.objects.get(
                        id=thread_id, approval_status="approved", is_deleted=False
                    )
                except ForumThread.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Thread not found or not approved",
                        "code": "FORUM_THREAD_NOT_FOUND",
                    }
            else:
                try:
                    target = ForumReply.objects.get(id=reply_id, is_deleted=False)
                except ForumReply.DoesNotExist:
                    return {
                        "success": False,
                        "error": "Reply not found",
                        "code": "FORUM_REPLY_NOT_FOUND",
                    }

            # Check for existing reaction of the same type
            if thread_id:
                existing_reaction = ForumReaction.objects.filter(
                    user=user_data, thread=target, reaction_type=reaction_type
                ).first()
            else:
                existing_reaction = ForumReaction.objects.filter(
                    user=user_data, reply=target, reaction_type=reaction_type
                ).first()

            # Toggle reaction
            if existing_reaction:
                # Remove the reaction (toggle off)
                existing_reaction.delete()
                action = "removed"
                
                # Update analytics
                analytics = self._ensure_analytics()
                analytics.total_reactions = max(0, analytics.total_reactions - 1)
                analytics.save()
            else:
                # Create new reaction
                if thread_id:
                    ForumReaction.objects.create(
                        user=user_data, thread=target, reaction_type=reaction_type
                    )
                else:
                    ForumReaction.objects.create(
                        user=user_data, reply=target, reaction_type=reaction_type
                    )
                action = "added"
                
                # Update analytics
                analytics = self._ensure_analytics()
                analytics.total_reactions += 1
                analytics.save()
                
                # Create notification for the content author (if not the same as reactor)
                content_author = target.author if thread_id else target.author
                thread_ref = target if thread_id else target.thread
                
                if content_author.id != user_data.id:
                    try:
                        notification_content = f"{user_data.user.username} reacted with {reaction_type} to your {'thread' if thread_id else 'reply'}"
                        ForumNotification.objects.create(
                            user=content_author,
                            notification_type='reaction',
                            content=notification_content,
                            thread=thread_ref,
                            reply=None if thread_id else target,
                            from_user=user_data
                        )
                    except Exception as notif_error:
                        logger.error(f"Error creating reaction notification: {str(notif_error)}")

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
            logger.error(f"Error adding reaction: {str(e)}")
            return {
                "success": False,
                "error": f"Error adding reaction: {str(e)}",
                "code": "FORUM_REACTION_ERROR",
            }
