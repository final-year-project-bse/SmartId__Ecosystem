"""
Authentication backend: allow login with email OR registration number (institutional_id).
Enforces account lockout after max_failed_attempts consecutive failures (SEC-4).
"""
from django.contrib.auth.backends import ModelBackend
from .models import User, FailedLoginAttempt


def _is_locked_out(identifier: str, is_admin: bool) -> bool:
    """Return True if identifier has too many recent failed attempts."""
    try:
        from dashboard.models import SystemSetting
        max_attempts = SystemSetting.load().max_failed_attempts
    except Exception:
        max_attempts = 3

    from django.utils import timezone
    from datetime import timedelta
    window = timezone.now() - timedelta(minutes=15)
    count = FailedLoginAttempt.objects.filter(
        identifier__iexact=identifier,
        is_admin_attempt=is_admin,
        created_at__gte=window,
    ).count()
    return count >= max_attempts


class EmailOrRegistrationBackend(ModelBackend):
    """
    Authenticate with username (email or registration number) and password.
    Registration numbers are normalized to uppercase for lookup.
    Locks out an identifier after max_failed_attempts failures within 15 minutes.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        username = (username or '').strip()
        if not username:
            return None

        is_admin_path = getattr(request, 'path', '').startswith('/login/admin')

        if _is_locked_out(username, is_admin_path):
            return None

        # Try by email first (case-insensitive)
        user = User.objects.filter(email__iexact=username).first()
        if not user:
            user = User.objects.filter(institutional_id=username.upper()).first()

        if user and user.check_password(password):
            return user
        return None
