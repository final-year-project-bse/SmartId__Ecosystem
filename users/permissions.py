"""
Role-based access helpers — thin wrappers around users.decorators.
Import from users.decorators directly; this file exists for backwards compatibility.
"""
from users.decorators import role_required, admin_required, staff_required  # noqa: F401
from .models import User


def is_admin_user(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return (
        getattr(user, 'role', None) == User.Role.ADMIN
        or getattr(user, 'is_staff', False)
        or getattr(user, 'is_superuser', False)
    )


def is_professor_or_admin(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    return (
        getattr(user, 'role', None) in (User.Role.PROFESSOR, User.Role.ADMIN)
        or getattr(user, 'is_staff', False)
        or getattr(user, 'is_superuser', False)
    )


professor_or_admin_required = staff_required
