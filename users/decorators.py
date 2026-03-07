"""
Reusable role-based authorization decorators (SEC-3, FR-13).
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def role_required(*allowed_roles):
    """Decorator that enforces login + role membership. Staff/superuser always have access."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if (
                user.role in allowed_roles
                or getattr(user, 'is_superuser', False)
                or getattr(user, 'is_staff', False)
            ):
                return view_func(request, *args, **kwargs)
            messages.warning(request, 'You do not have permission to access that page.')
            return redirect('dashboard:home')
        return _wrapped
    return decorator


def admin_required(view_func):
    """Shortcut: only admin role or superuser."""
    from users.models import User
    return role_required(User.Role.ADMIN)(view_func)


def staff_required(view_func):
    """Professor or admin."""
    from users.models import User
    return role_required(User.Role.PROFESSOR, User.Role.ADMIN)(view_func)
