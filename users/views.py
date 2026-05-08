"""
User login, profile management, and auth method handling.
Enrollment is now admin-controlled (see dashboard.views.create_user).
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.views.generic import FormView
from django.urls import reverse_lazy

from .models import User, FailedLoginAttempt
from .forms import CustomAuthenticationForm, ProfileEditForm
from notifications.utils import notify_admins


def _get_client_ip(request):
    x = request.META.get('HTTP_X_FORWARDED_FOR')
    return (x.split(',')[0].strip() if x else request.META.get('REMOTE_ADDR')) or None


def home(request):
    """Landing: login or redirect to dashboard if authenticated."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'users/home.html')


# ---------------------------------------------------------------------------
# Authentication (UC-2)
# ---------------------------------------------------------------------------

class LoginView(FormView):
    """Credential-based login; biometric/RFID at terminal."""
    template_name = 'users/login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('dashboard:home')

    def form_valid(self, form):
        login(self.request, form.get_user())
        return redirect(self.success_url)

    def form_invalid(self, form):
        # Notify admins and record for analytics (FR-10)
        identifier = (form.data.get('username') or 'unknown').strip()[:255]
        FailedLoginAttempt.objects.create(
            identifier=identifier,
            is_admin_attempt=False,
            ip_address=_get_client_ip(self.request),
        )
        notify_admins(
            'Failed Login Attempt',
            f'A failed login attempt was made for identifier: {identifier}.',
            notification_type='failed_auth',
        )
        return super().form_invalid(form)


class AdminLoginView(FormView):
    """Admin-only login with role validation."""
    template_name = 'users/admin_login.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('dashboard:analytics')

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
        identifier = (form.data.get('username') or 'unknown').strip()[:255]
        FailedLoginAttempt.objects.create(
            identifier=identifier,
            is_admin_attempt=True,
            ip_address=_get_client_ip(self.request),
        )
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
def professor_settings(request):
    """Professor settings: view details, change password, theme."""
    user = request.user
    auth_pref = getattr(user, 'auth_method_preference', None)
    pw_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        pw_form = PasswordChangeForm(user=user, data=request.POST)
        if pw_form.is_valid():
            pw_form.save()
            update_session_auth_hash(request, pw_form.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('users:professor_settings')
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'users/professor_settings.html', {
        'auth_pref': auth_pref,
        'pw_form': pw_form,
    })


@login_required
def admin_settings(request):
    """Admin settings: view details, change password."""
    user = request.user
    auth_pref = getattr(user, 'auth_method_preference', None)
    pw_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        pw_form = PasswordChangeForm(user=user, data=request.POST)
        if pw_form.is_valid():
            pw_form.save()
            update_session_auth_hash(request, pw_form.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('users:admin_settings')
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'users/admin_settings.html', {
        'auth_pref': auth_pref,
        'pw_form': pw_form,
    })


@login_required
def student_settings(request):
    """Student settings: view all details + change password."""
    user = request.user
    auth_pref = getattr(user, 'auth_method_preference', None)
    consent = getattr(user, 'consent', None)

    pw_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        pw_form = PasswordChangeForm(user=user, data=request.POST)
        if pw_form.is_valid():
            pw_form.save()
            update_session_auth_hash(request, pw_form.user)
            messages.success(request, 'Password changed successfully.')
            return redirect('users:student_settings')
        else:
            messages.error(request, 'Please correct the errors below.')

    return render(request, 'users/student_settings.html', {
        'auth_pref': auth_pref,
        'consent': consent,
        'pw_form': pw_form,
    })


@login_required
def id_card(request):
    """Printable campus ID card: name and registration number (for differentiation)."""
    return render(request, 'users/id_card.html', {'user': request.user})
