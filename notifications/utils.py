"""
Notification helper functions for programmatic event-driven notifications (FR-9, FR-10).
In-app notifications are always created; email is sent when NOTIFICATIONS_SEND_EMAIL is True.
"""
from django.conf import settings
from django.core.mail import send_mail

from .models import Notification


def _send_notification_email(emails, title, message, fail_silently=True):
    """Send notification by email to the given list of addresses."""
    if not getattr(settings, 'NOTIFICATIONS_SEND_EMAIL', False):
        return
    if not emails:
        return
    subject = f"[SmartID] {title}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'smartid@campus.edu')
    try:
        send_mail(
            subject,
            message,
            from_email,
            list(emails),
            fail_silently=fail_silently,
        )
    except Exception:
        if not fail_silently:
            raise


def notify(user, title, message, notification_type='system'):
    """Create a single in-app notification for a user; optionally send email."""
    n = Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
    )
    if getattr(user, 'email', None):
        _send_notification_email([user.email], title, message)
    return n


def notify_admins(title, message, notification_type='system'):
    """Send a notification to all active admin users (FR-10); optionally email them."""
    from users.models import User
    admins = User.objects.filter(role=User.Role.ADMIN, is_active=True)
    notifications = []
    admin_emails = []
    for admin in admins:
        notifications.append(Notification(
            user=admin,
            title=title,
            message=message,
            notification_type=notification_type,
        ))
        if getattr(admin, 'email', None):
            admin_emails.append(admin.email)
    Notification.objects.bulk_create(notifications)
    _send_notification_email(admin_emails, title, message)
    return notifications
