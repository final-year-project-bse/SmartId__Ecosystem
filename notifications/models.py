"""
Student & Staff Notifications (FR-9, FR-10, UC-5).
"""
from django.db import models
from django.conf import settings


class Notification(models.Model):
    """In-app and optionally email notifications."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, choices=[
        ('missed_class', 'Missed class'),
        ('failed_auth', 'Failed authentication'),
        ('access_alert', 'Access alert'),
        ('system', 'System'),
    ], default='system')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} for {self.user}"
