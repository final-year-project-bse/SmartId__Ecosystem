"""
Authentication backend: allow login with email OR registration number (institutional_id).
"""
from django.contrib.auth.backends import ModelBackend
from .models import User


class EmailOrRegistrationBackend(ModelBackend):
    """
    Authenticate with username (email or registration number) and password.
    Registration numbers are normalized to uppercase for lookup.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        username = (username or '').strip()
        if not username:
            return None

        # Try by email first (case-insensitive for email)
        user = User.objects.filter(email__iexact=username).first()
        if not user:
            # Try by registration number (normalize to uppercase)
            reg = username.upper()
            user = User.objects.filter(institutional_id=reg).first()
        if user and user.check_password(password):
            return user
        return None
