"""
Role-based access helpers for SmartID.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import User


def is_admin_user(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return (
        getattr(user, "role", None) == User.Role.ADMIN
        or getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
    )


def is_professor_or_admin(user):
    if not getattr(user, "is_authenticated", False):
        return False
    return (
        getattr(user, "role", None) in (User.Role.PROFESSOR, User.Role.ADMIN)
        or getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
    )


def role_required(role_check, denied_message="You do not have permission to access this page."):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if role_check(request.user):
                return view_func(request, *args, **kwargs)
            messages.error(request, denied_message)
            return redirect("dashboard:home")

        return _wrapped

    return decorator


admin_required = role_required(
    is_admin_user, denied_message="Administrator access is required for this action."
)
professor_or_admin_required = role_required(
    is_professor_or_admin,
    denied_message="Professor or administrator access is required for this page.",
)
