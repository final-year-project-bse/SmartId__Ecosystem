"""
Admin Dashboard, Reporting, Analytics, and Full User CRUD
(UC-4, UC-6, UC-7, FR-6, FR-9, FR-10, FR-11, FR-13).
"""
import csv
import json
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Prefetch
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import timedelta, datetime, time as dt_time

from users.models import User, ConsentRecord, UserAuthMethod, AuthMethod, RFIDCredential, FailedLoginAttempt
from users.decorators import admin_required, staff_required
from users.forms import AdminUserCreateForm, AdminUserEditForm, RFIDEnrollForm
from attendance.models import AttendanceRecord, AttendanceSession, Location, AccessLog, Course, CourseEnrollment, TimetableSlot
from notifications.utils import notify, notify_admins
from .models import SystemDevice, SystemSetting, AlertRule


# ---------------------------------------------------------------------------
# Role-based home (dashboard entry)
# ---------------------------------------------------------------------------

@login_required
def home(request):
    """Role-based home: student -> own records; prof/admin -> dashboard; parent -> basic."""
    user = request.user
    if user.role == User.Role.STUDENT:
        records = (
            AttendanceRecord.objects
            .filter(user=user)
            .select_related('session', 'location')[:20]
        )
        return render(request, 'dashboard/student_home.html', {'records': records})
    if user.role in (User.Role.PROFESSOR, User.Role.ADMIN):
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        total_users = User.objects.filter(is_active=True).count()
        total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
        ctx = {
            'total_users': total_users,
            'total_students': total_students,
            'total_professors': User.objects.filter(role=User.Role.PROFESSOR, is_active=True).count(),
            'active_sessions': AttendanceSession.objects.filter(ended_at__isnull=True).count(),
            'weekly_attendance': AttendanceRecord.objects.filter(marked_at__date__gte=week_ago).count(),
            'today_attendance': AttendanceRecord.objects.filter(marked_at__date=today).count(),
            'student_pct': round(total_students / total_users * 100) if total_users else 0,
        }
        return render(request, 'dashboard/staff_home.html', ctx)
    if user.role == User.Role.PARENT:
        from users.models import ParentStudentLink
        from attendance.models import CourseEnrollment, LeaveRequest
        links = ParentStudentLink.objects.filter(parent=user).select_related('student')
        children = []
        for link in links:
            stu = link.student
            enrolled = CourseEnrollment.objects.filter(student=stu).count()
            total_att = AttendanceRecord.objects.filter(user=stu).count()
            pending = LeaveRequest.objects.filter(student=stu, status='pending').count()
            children.append({
                'student': stu,
                'enrolled_courses': enrolled,
                'total_attendance': total_att,
                'pending_leaves': pending,
            })
        return render(request, 'dashboard/parent_home.html', {'children': children})
    return render(request, 'dashboard/home.html')


# ---------------------------------------------------------------------------
# Reports (UC-4, FR-6)
# ---------------------------------------------------------------------------

@staff_required
def reports(request):
    """Attendance reports -- daily, weekly, monthly with CSV export; filter by location and optional date range."""
    period = request.GET.get('period', 'monthly')  # default monthly so reports show data more reliably
    today = timezone.localtime(timezone.now()).date()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start > end:
                start, end = end, start
        except ValueError:
            start = today
            end = today
    else:
        if period == 'weekly':
            start = today - timedelta(days=7)
        elif period == 'monthly':
            start = today - timedelta(days=30)
        else:
            start = today  # daily
        end = today

    # Use timezone-aware datetime range so records from "today" in local time are included
    # (make_aware works with ZoneInfo; .localize() is pytz-only and would raise on ZoneInfo)
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start, dt_time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end, dt_time.max), tz)

    records = (
        AttendanceRecord.objects
        .filter(marked_at__gte=start_dt, marked_at__lte=end_dt)
        .select_related('user', 'session', 'location')
    )
    status_filter = request.GET.get('status', '')
    if status_filter in (AttendanceRecord.Status.ON_TIME, AttendanceRecord.Status.LATE):
        records = records.filter(status=status_filter)
    location_id = request.GET.get('location')
    if location_id:
        records = records.filter(location_id=location_id)

    by_user = (
        records
        .values('user__institutional_id', 'user__first_name', 'user__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    by_location = (
        records
        .values('location__name', 'location__code')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    locations = Location.objects.all().order_by('name')

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = f"attendance_{start}_{end}.csv" if (start_date and end_date) else f"attendance_{period}_{today}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow(['Institutional ID', 'First Name', 'Last Name', 'Location', 'Location Code', 'Date/Time', 'Status'])
        for r in records[:5000]:
            writer.writerow([
                r.user.institutional_id, r.user.first_name, r.user.last_name,
                r.location.name, r.location.code,
                r.marked_at.strftime('%Y-%m-%d %H:%M:%S'),
                r.get_status_display(),
            ])
        return response

    return render(request, 'dashboard/reports.html', {
        'records': records[:100],
        'by_user': by_user,
        'by_location': by_location,
        'period': period,
        'status_filter': status_filter,
        'location_id': location_id,
        'locations': locations,
        'start_date': start_date,
        'end_date': end_date,
        'report_start': start,
        'report_end': end,
    })


# ---------------------------------------------------------------------------
# Analytics (UC-7)
# ---------------------------------------------------------------------------

@admin_required
def analytics(request):
    """Analytics dashboard for admin with Chart.js visualizations."""
    today = timezone.localtime(timezone.now()).date()
    window_days = 30
    window_start_date = today - timedelta(days=window_days)
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(window_start_date, dt_time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(today, dt_time.max), tz)

    total_users = User.objects.filter(is_active=True).count()
    total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
    total_professors = User.objects.filter(role=User.Role.PROFESSOR, is_active=True).count()
    attendance_count = AttendanceRecord.objects.filter(marked_at__gte=start_dt, marked_at__lte=end_dt).count()
    access_logs = AccessLog.objects.filter(accessed_at__gte=start_dt, accessed_at__lte=end_dt).select_related('user', 'location')
    failed_web_logins = FailedLoginAttempt.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt).count()
    failed_terminal_logins = access_logs.filter(success=False).count()
    failed_logins = failed_web_logins + failed_terminal_logins
    successful_logins = access_logs.filter(success=True).count()

    # ── Chart Data: attendance trend (last 7 days, per calendar day in local tz) ──
    daily_labels = []
    daily_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        daily_labels.append(d.strftime('%a'))
        day_start = timezone.make_aware(datetime.combine(d, dt_time.min), tz)
        day_end = timezone.make_aware(datetime.combine(d, dt_time.max), tz)
        daily_data.append(
            AttendanceRecord.objects.filter(marked_at__gte=day_start, marked_at__lte=day_end).count()
        )

    # ── Chart Data: Attendance by location ──
    from attendance.models import Location
    locations = Location.objects.all()[:6]
    location_labels = [loc.name for loc in locations]
    location_data = [
        AttendanceRecord.objects.filter(location=loc, marked_at__gte=start_dt, marked_at__lte=end_dt).count()
        for loc in locations
    ]

    # Pass chart data as JSON so template outputs valid JavaScript (no HTML escaping issues)
    return render(request, 'dashboard/analytics.html', {
        'total_users': total_users,
        'total_students': total_students,
        'total_professors': total_professors,
        'attendance_count': attendance_count,
        'failed_logins': failed_logins,
        'successful_logins': successful_logins,
        'access_logs': access_logs[:50],
        'daily_labels': json.dumps(daily_labels),
        'daily_data': json.dumps(daily_data),
        'location_labels': json.dumps(location_labels),
        'location_data': json.dumps(location_data),
    })


# ---------------------------------------------------------------------------
# Manage Users -- full in-app CRUD (UC-6)
# ---------------------------------------------------------------------------

@admin_required
def manage_users(request):
    """List all users with search/filter and pagination."""
    q = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', '').strip()
    status_filter = request.GET.get('status', '').strip()

    users = User.objects.all().order_by('-date_joined')
    if q:
        users = users.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
            | Q(email__icontains=q) | Q(institutional_id__icontains=q)
        )
    if role_filter:
        users = users.filter(role=role_filter)
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)

    # Pagination
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'dashboard/manage_users.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'q': q,
        'role_filter': role_filter,
        'status_filter': status_filter,
        'role_choices': User.Role.choices,
    })


@admin_required
def create_user(request):
    """
    Admin enrolls a new user (UC-1, UC-6, FR-1, FR-2).
    Creates the user, consent record, auth method, and optionally
    redirects to RFID enrollment if RFID is the chosen method.
    """
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            # ── Create Digital Consent Record (FR-2) ──
            ConsentRecord.objects.create(
                user=user,
                biometric_consent=form.cleaned_data.get('consent_biometric', False),
                rfid_consent=form.cleaned_data.get('consent_rfid', False),
                data_retention_ack=form.cleaned_data.get('data_retention', False),
                ip_address=_get_client_ip(request),
            )
            # ── Set authentication method ──
            method = form.cleaned_data['auth_method']
            UserAuthMethod.objects.create(user=user, method=method)
            notify_admins(
                'New User Enrolled',
                f'User {user.get_full_name()} ({user.institutional_id}) was enrolled by '
                f'{request.user.get_full_name()} with {dict(AuthMethod.choices).get(method, method)} auth.',
                notification_type='system',
            )
            # ── RFID: register tag if provided in wizard, else redirect to enroll page ──
            if method == AuthMethod.RFID:
                rfid_tag = form.cleaned_data.get('rfid_tag', '').strip()
                if rfid_tag:
                    from users.models import RFIDCredential
                    cred, _ = RFIDCredential.objects.get_or_create(user=user)
                    cred.set_tag(rfid_tag)
                    messages.success(request, f'User {user.get_full_name()} enrolled with RFID card registered.')
                else:
                    messages.success(request, f'User {user.get_full_name()} created. Register their RFID card from User Management.')
                    return redirect('dashboard:enroll_rfid', user_id=user.pk)
            else:
                messages.success(request, f'User {user.get_full_name()} enrolled successfully.')
            return redirect('dashboard:manage_users')
    else:
        form = AdminUserCreateForm()
    return render(request, 'dashboard/user_form.html', {
        'form': form,
        'form_title': 'Enroll New User',
        'submit_label': 'Enroll User',
    })


def _get_client_ip(request):
    """Extract client IP from request headers."""
    x = request.META.get('HTTP_X_FORWARDED_FOR')
    return x.split(',')[0].strip() if x else request.META.get('REMOTE_ADDR')


@admin_required
def enroll_rfid(request, user_id):
    """Admin registers an RFID card for a newly enrolled user."""
    target = get_object_or_404(User, pk=user_id)
    if getattr(target, 'rfid_credential', None):
        messages.info(request, f'{target.get_full_name()} already has an RFID card registered.')
        return redirect('dashboard:manage_users')
    if request.method == 'POST':
        form = RFIDEnrollForm(request.POST)
        if form.is_valid():
            cred, _ = RFIDCredential.objects.get_or_create(user=target)
            cred.set_tag(form.cleaned_data['rfid_tag'])
            messages.success(request, f'RFID card registered for {target.get_full_name()}.')
            return redirect('dashboard:manage_users')
    else:
        form = RFIDEnrollForm()
    return render(request, 'dashboard/enroll_rfid.html', {
        'form': form,
        'target_user': target,
    })


@admin_required
def edit_user(request, user_id):
    """Admin edits a user."""
    target = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {target.get_full_name()} updated.')
            return redirect('dashboard:manage_users')
    else:
        form = AdminUserEditForm(instance=target)
    return render(request, 'dashboard/user_form.html', {
        'form': form,
        'form_title': f'Edit User: {target.get_full_name()}',
        'submit_label': 'Save Changes',
        'target_user': target,
    })


@admin_required
def toggle_user_active(request, user_id):
    """Activate or deactivate a user account."""
    if request.method != 'POST':
        return redirect('dashboard:manage_users')
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('dashboard:manage_users')
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    action = 'activated' if target.is_active else 'deactivated'
    notify_admins(
        f'User Account {action.title()}',
        f'{target.get_full_name()} ({target.institutional_id}) was {action} by {request.user.get_full_name()}.',
        notification_type='system',
    )
    messages.success(request, f'{target.get_full_name()} has been {action}.')
    return redirect('dashboard:manage_users')


@admin_required
def reset_user_password(request, user_id):
    """Admin resets a user password."""
    target = get_object_or_404(User, pk=user_id)
    if request.method == 'POST':
        new_pw = request.POST.get('new_password', '').strip()
        if len(new_pw) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
            return render(request, 'dashboard/reset_password.html', {'target_user': target})
        target.set_password(new_pw)
        target.save(update_fields=['password'])
        notify(target, 'Password Reset',
               'Your password was reset by an administrator. Please log in with your new credentials.',
               notification_type='system')
        messages.success(request, f'Password reset for {target.get_full_name()}.')
        return redirect('dashboard:manage_users')
    return render(request, 'dashboard/reset_password.html', {'target_user': target})


# ---------------------------------------------------------------------------
# Location management (admin)
# ---------------------------------------------------------------------------

@admin_required
def manage_locations(request):
    """List and create locations."""
    locations = Location.objects.all().order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        loc_type = request.POST.get('location_type', 'classroom')
        if name and code:
            if Location.objects.filter(code=code).exists():
                messages.error(request, f'Location code "{code}" already exists.')
            else:
                Location.objects.create(name=name, code=code, location_type=loc_type)
                messages.success(request, f'Location "{name}" created.')
                return redirect('dashboard:manage_locations')
        else:
            messages.error(request, 'Name and code are required.')
    return render(request, 'dashboard/manage_locations.html', {
        'locations': locations,
        'location_types': Location._meta.get_field('location_type').choices,
    })


@admin_required
def timetable_master(request):
    """Master timetable / room utilization: view all slots, filter by location."""
    slots = TimetableSlot.objects.select_related('course', 'location', 'professor').order_by('day_of_week', 'start_time')
    location_id = request.GET.get('location')
    if location_id:
        slots = slots.filter(location_id=location_id)
    locations = Location.objects.all().order_by('name')
    return render(request, 'dashboard/timetable_master.html', {
        'slots': slots,
        'locations': locations,
        'filter_location_id': location_id,
    })


# ---------------------------------------------------------------------------
# Parent-Student link management (admin)
# ---------------------------------------------------------------------------

@admin_required
def manage_parent_links(request, parent_id):
    """Admin links / unlinks students to a parent user."""
    from users.models import ParentStudentLink
    parent = get_object_or_404(User, pk=parent_id, role=User.Role.PARENT)
    linked = ParentStudentLink.objects.filter(parent=parent).select_related('student')
    available_students = User.objects.filter(
        role=User.Role.STUDENT, is_active=True,
    ).exclude(pk__in=linked.values_list('student_id', flat=True))

    if request.method == 'POST':
        action = request.POST.get('action')
        student_id = request.POST.get('student_id')
        if action == 'link' and student_id:
            stu = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
            ParentStudentLink.objects.get_or_create(parent=parent, student=stu)
            messages.success(request, f'{stu.get_full_name()} linked to {parent.get_full_name()}.')
        elif action == 'unlink' and student_id:
            ParentStudentLink.objects.filter(parent=parent, student_id=student_id).delete()
            messages.success(request, 'Student unlinked.')
        return redirect('dashboard:manage_parent_links', parent_id=parent.pk)

    return render(request, 'dashboard/manage_parent_links.html', {
        'parent': parent,
        'linked_students': linked,
        'available_students': available_students,
    })


# ===========================================================================
# CONTROL PLANE — System Health (Module 9, FR-7, FR-8)
# ===========================================================================

@admin_required
def system_health(request):
    """System Health dashboard: IoT device status + global auth toggles."""
    devices = SystemDevice.objects.select_related('location').all()
    settings_obj = SystemSetting.load()

    online = devices.filter(status=SystemDevice.Status.ONLINE).count()
    offline = devices.filter(status=SystemDevice.Status.OFFLINE).count()
    degraded = devices.filter(status=SystemDevice.Status.DEGRADED).count()

    locations = Location.objects.all().order_by('name')
    return render(request, 'dashboard/system_health.html', {
        'devices': devices,
        'settings': settings_obj,
        'online_count': online,
        'offline_count': offline,
        'degraded_count': degraded,
        'total_devices': devices.count(),
        'locations': locations,
    })


@admin_required
def toggle_auth_method(request):
    """POST: toggle a global authentication method on/off."""
    if request.method != 'POST':
        return redirect('dashboard:system_health')
    method = request.POST.get('method', '')
    settings_obj = SystemSetting.load()
    toggled = None
    if method == 'face':
        settings_obj.face_recognition_enabled = not settings_obj.face_recognition_enabled
        toggled = ('Facial Recognition', settings_obj.face_recognition_enabled)
    elif method == 'fingerprint':
        settings_obj.fingerprint_enabled = not settings_obj.fingerprint_enabled
        toggled = ('Fingerprint', settings_obj.fingerprint_enabled)
    elif method == 'rfid':
        settings_obj.rfid_enabled = not settings_obj.rfid_enabled
        toggled = ('RFID', settings_obj.rfid_enabled)
    if toggled:
        settings_obj.updated_by = request.user
        settings_obj.save()
        state = 'enabled' if toggled[1] else 'disabled'
        notify_admins(
            f'{toggled[0]} {state.title()}',
            f'{toggled[0]} authentication was {state} by {request.user.get_full_name()}.',
            notification_type='system',
        )
        messages.success(request, f'{toggled[0]} authentication {state}.')
    return redirect('dashboard:system_health')


@admin_required
def register_device(request):
    """POST: register a new IoT device."""
    if request.method != 'POST':
        return redirect('dashboard:system_health')
    name = request.POST.get('name', '').strip()
    device_type = request.POST.get('device_type', '')
    serial = request.POST.get('serial_number', '').strip()
    location_id = request.POST.get('location_id') or None
    ip = request.POST.get('ip_address', '').strip() or None

    if not name or not serial:
        messages.error(request, 'Device name and serial number are required.')
        return redirect('dashboard:system_health')
    if SystemDevice.objects.filter(serial_number=serial).exists():
        messages.error(request, f'Serial number "{serial}" is already registered.')
        return redirect('dashboard:system_health')

    loc = Location.objects.filter(pk=location_id).first() if location_id else None
    SystemDevice.objects.create(
        name=name, device_type=device_type, serial_number=serial,
        location=loc, ip_address=ip, status=SystemDevice.Status.OFFLINE,
    )
    messages.success(request, f'Device "{name}" registered.')
    return redirect('dashboard:system_health')


# ===========================================================================
# OVERSIGHT PLANE — Privacy Compliance (FR-2, FR-11, FR-12, FR-13)
# ===========================================================================

@admin_required
def privacy_compliance(request):
    """
    Privacy Compliance view: lists all users with their consent status.
    Flags users who have NOT signed the Digital Consent Form.
    """
    users = (
        User.objects.filter(is_active=True)
        .select_related('consent')
        .order_by('last_name', 'first_name')
    )
    total = users.count()
    consented = users.filter(consent__isnull=False).count()
    missing = total - consented

    return render(request, 'dashboard/privacy_compliance.html', {
        'users': users,
        'total_users': total,
        'consented_count': consented,
        'missing_count': missing,
        'compliance_pct': round(consented / total * 100) if total else 0,
    })


# ===========================================================================
# INTELLIGENCE PLANE — Automated Alert Configuration (FR-9, FR-10)
# ===========================================================================

@admin_required
def alert_rules(request):
    """List and create alert rules (location-based or course-based)."""
    rules = AlertRule.objects.select_related('location', 'course', 'created_by').all()
    locations = Location.objects.all().order_by('name')
    courses = Course.objects.filter(is_active=True).order_by('code')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        location_id = request.POST.get('location_id') or None
        course_id = request.POST.get('course_id') or None
        threshold = request.POST.get('threshold_pct', '0')
        window = request.POST.get('time_window', 'daily')

        try:
            threshold = int(threshold)
        except ValueError:
            threshold = 0

        if name and 0 < threshold <= 100 and (location_id or course_id):
            loc = get_object_or_404(Location, pk=location_id) if location_id else None
            course = get_object_or_404(Course, pk=course_id) if course_id else None
            AlertRule.objects.create(
                name=name, location=loc, course=course, threshold_pct=threshold,
                time_window=window, created_by=request.user,
            )
            scope = course.code if course else (loc.name if loc else '')
            messages.success(request, f'Alert rule "{name}" for {scope} created.')
            return redirect('dashboard:alert_rules')
        else:
            messages.error(request, 'Name, threshold (1–100), and either Location or Course are required.')

    return render(request, 'dashboard/alert_rules.html', {
        'rules': rules,
        'locations': locations,
        'courses': courses,
        'window_choices': AlertRule.TimeWindow.choices,
    })


@admin_required
def toggle_alert_rule(request, rule_id):
    """POST: enable/disable an alert rule."""
    if request.method != 'POST':
        return redirect('dashboard:alert_rules')
    rule = get_object_or_404(AlertRule, pk=rule_id)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])
    state = 'enabled' if rule.is_active else 'disabled'
    messages.success(request, f'Rule "{rule.name}" {state}.')
    return redirect('dashboard:alert_rules')


@admin_required
def delete_alert_rule(request, rule_id):
    """POST: delete an alert rule."""
    if request.method != 'POST':
        return redirect('dashboard:alert_rules')
    rule = get_object_or_404(AlertRule, pk=rule_id)
    rule.delete()
    messages.success(request, 'Alert rule deleted.')
    return redirect('dashboard:alert_rules')


def _evaluate_alert_rule(rule, start, today):
    """Return (pct, scope_label) for the rule. Scope is course or location."""
    if rule.course_id:
        enrolled = CourseEnrollment.objects.filter(course=rule.course).count()
        if not enrolled:
            return 0, rule.course.code
        sessions_in_window = AttendanceSession.objects.filter(
            course=rule.course, ended_at__isnull=False,
            started_at__date__gte=start, started_at__date__lte=today,
        ).count()
        if not sessions_in_window:
            return 0, rule.course.code
        expected_marks = enrolled * sessions_in_window
        actual_marks = AttendanceRecord.objects.filter(
            session__course=rule.course,
            marked_at__date__gte=start, marked_at__date__lte=today,
        ).count()
        pct = round(actual_marks / expected_marks * 100) if expected_marks else 0
        return pct, rule.course.code
    elif rule.location_id:
        total_students = User.objects.filter(role=User.Role.STUDENT, is_active=True).count()
        attended = (
            AttendanceRecord.objects
            .filter(location=rule.location, marked_at__date__gte=start, marked_at__date__lte=today)
            .values('user').distinct().count()
        )
        pct = round(attended / total_students * 100) if total_students else 0
        return pct, rule.location.name
    return 0, '?'


@admin_required
def check_alert_rules(request):
    """
    Manually trigger threshold evaluation for all active alert rules.
    In production this would be a periodic task (celery / cron).
    """
    today = timezone.now().date()
    triggered = 0

    for rule in AlertRule.objects.filter(is_active=True).select_related('location', 'course'):
        if not rule.location_id and not rule.course_id:
            continue
        if rule.time_window == AlertRule.TimeWindow.DAILY:
            start = today
        elif rule.time_window == AlertRule.TimeWindow.WEEKLY:
            start = today - timedelta(days=7)
        else:
            start = today - timedelta(days=30)

        pct, scope_label = _evaluate_alert_rule(rule, start, today)

        if pct < rule.threshold_pct:
            notify_admins(
                f'Low Attendance Alert: {scope_label}',
                f'Attendance for {scope_label} is {pct}% '
                f'(threshold: {rule.threshold_pct}%, window: {rule.get_time_window_display()}).',
                notification_type='access_alert',
            )
            rule.last_triggered = timezone.now()
            rule.save(update_fields=['last_triggered'])
            triggered += 1

    messages.success(request, f'Checked {AlertRule.objects.filter(is_active=True).count()} rules — {triggered} alert(s) triggered.')
    return redirect('dashboard:alert_rules')
