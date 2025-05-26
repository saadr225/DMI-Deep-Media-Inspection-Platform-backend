from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth.models import User
from api.models import PublicDeepfakeArchive
from app.models import UserData


@receiver(post_save, sender=User)
def create_user_data(sender, instance, created, **kwargs):
    """Automatically create UserData for any new User"""
    if created:
        UserData.objects.get_or_create(user=instance)


@receiver(post_save, sender=PublicDeepfakeArchive)
def send_approval_email(sender, instance, **kwargs):
    if instance.is_approved and instance.reviewed_by:
        # Send email to the user
        send_mail(
            subject="Your submission has been approved",
            message=f'Hello {instance.user.user.username},\n\nYour submission "{instance.title}" has been approved.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.user.user.email],
            fail_silently=False,
        )
        print(f"Approval email sent to {instance.user.user.username} at {instance.user.user.email}")
    elif not instance.is_approved and instance.reviewed_by:
        # Send email to the user
        send_mail(
            subject="Your submission has been rejected",
            message=f'Hello {instance.user.user.username},\n\nYour submission "{instance.title}" has been rejected.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.user.user.email],
            fail_silently=False,
        )
        print(f"Rejection email sent to {instance.user.user.username} at {instance.user.user.email}")
