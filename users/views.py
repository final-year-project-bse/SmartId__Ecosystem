"""
User login, profile management, and auth method handling.
Enrollment is now admin-controlled (see dashboard.views.create_user).
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import FormView
from django.urls import reverse_lazy

from .models import User
from .forms import CustomAuthenticationForm, ProfileEditForm
from notifications.utils import notify_admins


def home(request):
    """Landing: login or redirect to dashboard if authenticated."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'users/home.html')


# ---------------------------------------------------------------------------
# Authentication (UC-2)
# ---------------------------------------------------------------------------

class LoginView(FormView):
    """Credential-based login for students, professors, parents. Admins must use admin login."""
    template_name = 'users/login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('dashboard:home')

    def form_valid(self, form):
        user = form.get_user()
        if _is_admin(user):
            form.add_error(
                None,
                'This login is for students, professors, and parents. '
                'Administrator accounts must use the admin login page.',
            )
            return self.form_invalid(form)
        login(self.request, user)
        return redirect(self.success_url)

    def form_invalid(self, form):
        # Notify admins on failed login attempts (FR-10)
        identifier = form.data.get('username', 'unknown')
        notify_admins(
            'Failed Login Attempt',
            f'A failed login attempt was made for identifier: {identifier}.',
            notification_type='failed_auth',
        )
        return super().form_invalid(form)


class AdminLoginView(FormView):
    """Admin-only login with role validation. Redirects to admin dashboard (home)."""
    template_name = 'users/admin_login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('dashboard:home')  # Admin dashboard (staff_home for admin users)

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if _is_admin(request.user):
                return redirect(self.success_url)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        if not _is_admin(user):
            form.add_error(
                None,
                'Access denied. This login is for administrators only. '
                'Use the regular login for other roles.',
            )
            return self.form_invalid(form)
        login(self.request, user)
        return redirect(self.success_url)

    def form_invalid(self, form):
        identifier = form.data.get('username', 'unknown')
        notify_admins(
            'Failed Admin Login Attempt',
            f'A failed admin login attempt was made for identifier: {identifier}.',
            notification_type='failed_auth',
        )
        return super().form_invalid(form)


def _is_admin(user):
    return (
        getattr(user, 'role', None) == User.Role.ADMIN
        or user.is_staff
        or user.is_superuser
    )


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('users:login')


# ---------------------------------------------------------------------------
# Profile (post-enrollment)
# ---------------------------------------------------------------------------

@login_required
def profile(request):
    """View and edit profile + auth preferences."""
    user = request.user
    auth_pref = getattr(user, 'auth_method_preference', None)
    consent = getattr(user, 'consent', None)

    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('users:profile')
    else:
        form = ProfileEditForm(instance=user)

    return render(request, 'users/profile.html', {
        'form': form,
        'auth_pref': auth_pref,
        'consent': consent,
    })


@login_required
def id_card(request):
    """Printable campus ID card: name and registration number (for differentiation)."""
    return render(request, 'users/id_card.html', {'user': request.user})
