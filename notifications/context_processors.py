"""
Template context processor for notification badge count.
"""
from .models import Notification


def unread_notification_count(request):
    """Inject unread notification count into every template context."""
    if request.user.is_authenticated:
        count = Notification.objects.filter(user=request.user, read=False).count()
        return {'unread_notification_count': count}
    return {'unread_notification_count': 0}
