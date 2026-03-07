"""
Management command to set a user's role (and optionally staff status) by email.
Use this to fix an admin account that has role=student, e.g.:
  python manage.py set_user_role finalyearp052@gmail.com admin
"""
from django.core.management.base import BaseCommand
from users.models import User


class Command(BaseCommand):
    help = "Set a user's role by email. Use: set_user_role <email> <role> [--staff]"

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email')
        parser.add_argument(
            'role',
            type=str,
            choices=[r.value for r in User.Role],
            help='Role: student, professor, admin, parent',
        )
        parser.add_argument(
            '--staff',
            action='store_true',
            help='Set is_staff=True (recommended for admin role)',
        )

    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        role = options['role']
        set_staff = options['staff']

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'User with email "{email}" not found.'))
            return

        old_role = user.role
        user.role = role
        if set_staff or role == User.Role.ADMIN:
            user.is_staff = True
        user.save(update_fields=['role', 'is_staff'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Updated {user.email}: role {old_role} -> {role}, is_staff={user.is_staff}'
            )
        )
        if role == User.Role.ADMIN:
            self.stdout.write(
                'Use the admin login page at /login/admin/ to access the admin dashboard.'
            )
