"""
Attendance recording (UC-3), terminal auth (UC-2), session management,
student portal, and teacher portal.
"""
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.core.paginator import Paginator
from datetime import timedelta, time as dt_time

from users.models import User
from users.decorators import staff_required, role_required
from notifications.utils import notify, notify_admins
from .models import (
    Location, AttendanceSession, AttendanceRecord, AccessLog,
    Course, CourseEnrollment, LeaveRequest, TimetableSlot,
)


# ===========================================================================
# Terminal / RFID authentication (UC-2)
# ===========================================================================

def terminal_login(request):
    """RFID/terminal-style authentication for kiosk or terminal."""
    from users.models import RFIDCredential
    if request.method == 'POST':
        rfid_tag = request.POST.get('rfid_tag', '').strip()
        location_id = request.POST.get('location_id')
        if not rfid_tag or not location_id:
            messages.error(request, 'RFID tag and location are required.')
            return render(request, 'attendance/terminal_login.html', {'locations': Location.objects.all()})
        location = get_object_or_404(Location, pk=location_id)
        user = None
        for cred in RFIDCredential.objects.select_related('user').filter(user__is_active=True):
            if cred.check_tag(rfid_tag):
                user = cred.user
                break
        if user:
            with transaction.atomic():
                AccessLog.objects.create(user=user, location=location, success=True, auth_method='rfid')
                session = _get_or_create_session(location)
                AttendanceRecord.objects.get_or_create(
                    user=user, session=session, defaults={'location': location}
                )
            request.session['terminal_user_id'] = user.pk
            messages.success(request, f'Welcome, {user.get_full_name()}. Attendance recorded.')
            return redirect('attendance:terminal_success')
        try:
            AccessLog.objects.create(location=location, success=False, auth_method='rfid')
        except Exception:
            pass
        notify_admins(
            'Failed RFID Authentication',
            f'An unrecognized RFID tag was scanned at {location.name}.',
            notification_type='failed_auth',
        )
        messages.error(request, 'RFID not recognized. Please try again or use web login.')
    return render(request, 'attendance/terminal_login.html', {'locations': Location.objects.all()})


def terminal_success(request):
    return render(request, 'attendance/terminal_success.html')


# ===========================================================================
# Web attendance (for logged-in users)
# ===========================================================================

@login_required
def attendance_page(request):
    """Web-based attendance: pick a location, mark attendance. Students must use terminal (RFID/face/fingerprint) or ask teacher."""
    if request.user.role == User.Role.STUDENT:
        messages.info(
            request,
            'Student attendance is recorded only at the terminal (RFID, face, or fingerprint) or by your teacher. '
            'If you have issues with the portal or device, ask your teacher to mark you present.',
        )
        return redirect('dashboard:home')
    locations = Location.objects.all().order_by('name')
    if request.method == 'POST':
        location_id = request.POST.get('location_id')
        if not location_id:
            messages.error(request, 'Please select a location.')
        else:
            location = get_object_or_404(Location, pk=location_id)
            session = _get_or_create_session(location)
            record, created = AttendanceRecord.objects.get_or_create(
                user=request.user, session=session, defaults={'location': location}
            )
            AccessLog.objects.create(
                user=request.user, location=location, success=True, auth_method='web'
            )
            if created:
                messages.success(request, f'Attendance marked at {location.name}.')
            else:
                messages.info(request, 'Attendance already recorded for this session.')
            return redirect('dashboard:home')
    return render(request, 'attendance/attendance_page.html', {'locations': locations})


@login_required
def mark_attendance(request, location_id):
    """Quick mark attendance at a specific location. Not available to students (use terminal or teacher)."""
    if request.user.role == User.Role.STUDENT:
        messages.info(request, 'Students must use the terminal (RFID/face/fingerprint) or ask the teacher to mark attendance.')
        return redirect('dashboard:home')
    location = get_object_or_404(Location, pk=location_id)
    session = _get_or_create_session(location)
    record, created = AttendanceRecord.objects.get_or_create(
        user=request.user, session=session, defaults={'location': location}
    )
    AccessLog.objects.create(user=request.user, location=location, success=True, auth_method='web')
    if created:
        messages.success(request, 'Attendance marked successfully.')
    else:
        messages.info(request, 'Attendance already recorded for this session.')
    return redirect('dashboard:home')


# ===========================================================================
# Session management (professor/admin)
# ===========================================================================

def _current_timetable_slot_for_professor(user):
    """If professor has a TimetableSlot right now (or within 10 min of start), return it."""
    from datetime import datetime, timedelta
    now = timezone.now()
    # Python Monday=0 .. Sunday=6; our day_of_week 1=Monday .. 7=Sunday
    day_of_week = now.weekday() + 1  # 1-7
    current_time = now.time()
    slots = TimetableSlot.objects.filter(
        professor=user, day_of_week=day_of_week,
    ).select_related('course', 'location')
    for slot in slots:
        # In class: between start and end
        if slot.start_time <= current_time <= slot.end_time:
            return slot
        # Within 10 min before start (grace to click Start)
        start_naive = datetime.combine(now.date(), slot.start_time)
        start_aware = timezone.make_aware(start_naive) if timezone.is_naive(start_naive) else start_naive
        if start_aware - timedelta(minutes=10) <= now <= start_aware:
            return slot
    return None


@staff_required
def manage_sessions(request):
    """View and manage attendance sessions."""
    user = request.user
    active_sessions = AttendanceSession.objects.filter(ended_at__isnull=True).select_related('location', 'created_by', 'course')
    recent_sessions_qs = AttendanceSession.objects.filter(ended_at__isnull=False).select_related('location', 'created_by', 'course')

    # Professors see only their own sessions (apply all filters before any slice)
    if user.role == User.Role.PROFESSOR:
        active_sessions = active_sessions.filter(
            Q(created_by=user) | Q(course__professor=user)
        )
        recent_sessions_qs = recent_sessions_qs.filter(
            Q(created_by=user) | Q(course__professor=user)
        )

    # Slice only after all filters to avoid "Cannot filter a query once a slice has been taken"
    recent_sessions = list(recent_sessions_qs[:20])

    locations = Location.objects.all().order_by('name')
    courses = Course.objects.filter(professor=user, is_active=True) if user.role == User.Role.PROFESSOR else Course.objects.filter(is_active=True)

    # Pre-fill: if professor, suggest current timetable slot so they can one-click Start
    suggested_slot = _current_timetable_slot_for_professor(user) if user.role == User.Role.PROFESSOR else None

    return render(request, 'attendance/manage_sessions.html', {
        'active_sessions': active_sessions,
        'recent_sessions': recent_sessions,
        'locations': locations,
        'courses': courses,
        'suggested_slot': suggested_slot,
    })


@staff_required
def start_session(request):
    """Start a new attendance session for a location, optionally linked to a course/slot."""
    if request.method == 'POST':
        slot_id = request.POST.get('slot_id') or None
        location_id = request.POST.get('location_id')
        course_id = request.POST.get('course_id') or None
        # If the form was pre-filled from a suggested timetable slot, it includes a hidden slot_id.
        # But if the user manually changed Location/Course, we must NOT force the suggested slot.
        if slot_id:
            slot = (
                TimetableSlot.objects
                .filter(pk=slot_id)
                .select_related('location', 'course')
                .first()
            )
            slot_allowed = bool(slot) and (request.user.role == User.Role.ADMIN or slot.professor_id == request.user.id)
            manual_override = False
            if slot_allowed:
                if location_id and str(slot.location_id) != str(location_id):
                    manual_override = True
                if course_id and str(slot.course_id) != str(course_id):
                    manual_override = True
            if slot_allowed and not manual_override:
                location = slot.location
                course = slot.course
                existing = AttendanceSession.objects.filter(location=location, ended_at__isnull=True).first()
                if existing:
                    existing_label = existing.course.code if existing.course else 'No course'
                    messages.warning(request, f'An active session already exists for {location.name} ({existing_label}).')
                else:
                    AttendanceSession.objects.create(
                        location=location, course=course, slot=slot, created_by=request.user,
                    )
                    messages.success(request, f'Session started for {course.code} at {location.name}.')
                return redirect('attendance:manage_sessions')
        if location_id:
            location = get_object_or_404(Location, pk=location_id)
            existing = AttendanceSession.objects.filter(location=location, ended_at__isnull=True).first()
            if existing:
                existing_label = existing.course.code if existing.course else 'No course'
                messages.warning(request, f'An active session already exists for {location.name} ({existing_label}).')
            else:
                course = Course.objects.filter(pk=course_id).first() if course_id else None
                AttendanceSession.objects.create(
                    location=location, course=course, created_by=request.user,
                )
                label = f"{course.code} at {location.name}" if course else location.name
                messages.success(request, f'Session started for {label}.')
    return redirect('attendance:manage_sessions')


@staff_required
def end_session(request, session_id):
    """End an active attendance session."""
    if request.method == 'POST':
        session = get_object_or_404(AttendanceSession, pk=session_id, ended_at__isnull=True)
        session.ended_at = timezone.now()
        session.save(update_fields=['ended_at'])
        messages.success(request, f'Session at {session.location.name} ended.')
    return redirect('attendance:manage_sessions')


# ===========================================================================
# STUDENT PORTAL
# ===========================================================================

@role_required(User.Role.STUDENT)
def student_attendance_history(request):
    """Student views full attendance history with filters and pagination."""
    records = (
        AttendanceRecord.objects.filter(user=request.user)
        .select_related('session', 'session__course', 'location')
    )
    # Filters
    course_id = request.GET.get('course')
    location_id = request.GET.get('location')
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    status_filter = request.GET.get('status')  # '', 'on_time', 'late'

    if course_id:
        records = records.filter(session__course_id=course_id)
    if location_id:
        records = records.filter(location_id=location_id)
    if date_from:
        records = records.filter(marked_at__date__gte=date_from)
    if date_to:
        records = records.filter(marked_at__date__lte=date_to)
    if status_filter in (AttendanceRecord.Status.ON_TIME, AttendanceRecord.Status.LATE):
        records = records.filter(status=status_filter)

    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user, is_active=True
    )
    locations = Location.objects.all().order_by('name')

    # Pagination
    paginator = Paginator(records, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'attendance/student_history.html', {
        'records': page_obj,
        'page_obj': page_obj,
        'courses': enrolled_courses,
        'locations': locations,
        'filters': {'course': course_id, 'location': location_id, 'from': date_from, 'to': date_to, 'status': status_filter},
    })


@role_required(User.Role.STUDENT)
def student_attendance_stats(request):
    """Attendance statistics per course for the student."""
    enrollments = CourseEnrollment.objects.filter(
        student=request.user
    ).select_related('course', 'course__professor', 'course__location')

    stats = []
    for enrollment in enrollments:
        course = enrollment.course
        total_sessions = AttendanceSession.objects.filter(course=course, ended_at__isnull=False).count()
        attended = AttendanceRecord.objects.filter(
            user=request.user, session__course=course,
        ).count()
        pct = round(attended / total_sessions * 100) if total_sessions else 0
        stats.append({
            'course': course,
            'total_sessions': total_sessions,
            'attended': attended,
            'missed': total_sessions - attended,
            'percentage': pct,
            'status': 'danger' if pct < 75 else ('warning' if pct < 85 else 'success'),
        })

    return render(request, 'attendance/student_stats.html', {'stats': stats})


def _schedule_items_for_student(student):
    """
    Build a list of schedule items (day, start_time, end_time, course, professor, location)
    from TimetableSlot for enrolled courses, with fallback to Course schedule fields.
    """
    DAY_STR_TO_INT = {
        'monday': 1, 'tuesday': 2, 'wednesday': 3,
        'thursday': 4, 'friday': 5, 'saturday': 6,
    }
    enrolled_course_ids = CourseEnrollment.objects.filter(
        student=student
    ).values_list('course_id', flat=True)
    items = []
    # Prefer TimetableSlot (multiple slots per course per week)
    slots = TimetableSlot.objects.filter(
        course_id__in=enrolled_course_ids
    ).select_related('course', 'professor', 'location').order_by('day_of_week', 'start_time')
    for slot in slots:
        items.append({
            'day': slot.day_of_week,
            'start_time': slot.start_time,
            'end_time': slot.end_time,
            'course': slot.course,
            'professor': slot.professor,
            'location': slot.location,
        })
    # If no slots, fall back to Course schedule (one slot per course)
    if not items:
        courses = Course.objects.filter(
            id__in=enrolled_course_ids, is_active=True,
            day_of_week__in=DAY_STR_TO_INT.keys(),
        ).exclude(start_time__isnull=True).exclude(end_time__isnull=True)
        for c in courses.select_related('professor', 'location'):
            items.append({
                'day': DAY_STR_TO_INT[c.day_of_week],
                'start_time': c.start_time,
                'end_time': c.end_time,
                'course': c,
                'professor': c.professor,
                'location': c.location,
            })
    return items


def _build_timetable_grid(schedule_items):
    """
    Build a weekly grid: time slots 7:00–18:00, days Mon–Sat.
    grid[time_index][day_index] = list of schedule item dicts for that cell.
    """
    if not schedule_items:
        return {'time_slots': [], 'days': [], 'grid': []}
    time_slots = [
        (i, f"{7 + i}:00") for i in range(12)
    ]  # 7:00 .. 18:00
    days = [
        (1, 'Mon'), (2, 'Tue'), (3, 'Wed'),
        (4, 'Thu'), (5, 'Fri'), (6, 'Sat'),
    ]
    grid = []
    for ti, (hour_idx, time_label) in enumerate(time_slots):
        hour_start = dt_time(7 + hour_idx, 0)
        hour_end = dt_time(7 + hour_idx + 1, 0) if hour_idx < 11 else dt_time(18, 59, 59)
        row = []
        for di, (day_num, _) in enumerate(days):
            cell = [
                it for it in schedule_items
                if it['day'] == day_num
                and it['start_time'] < hour_end
                and it['end_time'] > hour_start
            ]
            row.append(cell)
        grid.append({'time_label': time_label, 'cells': row})
    return {
        'time_slots': time_slots,
        'days': days,
        'grid': grid,
    }


@role_required(User.Role.STUDENT)
def student_timetable(request):
    """Student's class schedule based on enrolled courses (list or weekly grid)."""
    courses = Course.objects.filter(
        enrollments__student=request.user, is_active=True,
    ).select_related('professor', 'location').order_by('day_of_week', 'start_time')
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    schedule = {d: [] for d in days_order}
    for c in courses:
        if c.day_of_week:
            schedule[c.day_of_week].append(c)
    # For grid: use TimetableSlot-based items (or Course fallback)
    schedule_items = _schedule_items_for_student(request.user)
    grid_data = _build_timetable_grid(schedule_items)
    view_mode = request.GET.get('view', 'list')
    if view_mode not in ('list', 'grid'):
        view_mode = 'list'
    return render(request, 'attendance/student_timetable.html', {
        'schedule': schedule,
        'courses': courses,
        'schedule_items': schedule_items,
        'grid_data': grid_data,
        'view_mode': view_mode,
    })


@role_required(User.Role.STUDENT)
def student_leave_request(request):
    """Student submits or views leave requests."""
    enrolled_courses = Course.objects.filter(
        enrollments__student=request.user, is_active=True,
    )
    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        date = request.POST.get('date')
        reason = request.POST.get('reason', '').strip()
        if course_id and date and reason:
            course = get_object_or_404(Course, pk=course_id)
            LeaveRequest.objects.create(
                student=request.user, course=course, date=date, reason=reason,
            )
            notify(
                course.professor,
                'Leave Request',
                f'{request.user.get_full_name()} ({request.user.institutional_id}) has requested leave from {course.code} on {date}.',
                notification_type='system',
            )
            messages.success(request, 'Leave request submitted successfully.')
            return redirect('attendance:student_leaves')
        else:
            messages.error(request, 'All fields are required.')

    leaves = LeaveRequest.objects.filter(student=request.user).select_related('course', 'reviewed_by')
    return render(request, 'attendance/student_leaves.html', {
        'leaves': leaves,
        'courses': enrolled_courses,
    })


# ===========================================================================
# TEACHER PORTAL
# ===========================================================================

@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_dashboard(request):
    """Teacher overview: my courses, today's sessions, quick stats."""
    user = request.user
    my_courses = Course.objects.filter(professor=user, is_active=True).select_related('location')
    today = timezone.now().date()
    today_sessions = AttendanceSession.objects.filter(
        course__professor=user, started_at__date=today,
    ).select_related('location', 'course').annotate(student_count=Count('records'))

    total_students = CourseEnrollment.objects.filter(course__professor=user).values('student').distinct().count()
    active_sessions = AttendanceSession.objects.filter(
        course__professor=user, ended_at__isnull=True,
    ).count()
    # For "Students" tile: link to roster of a course that has enrollments (so list isn't empty when possible)
    first_course_with_students = (
        my_courses.annotate(ec=Count('enrollments')).filter(ec__gt=0).order_by('-ec').first()
        or my_courses.first()
    )

    return render(request, 'attendance/teacher_dashboard.html', {
        'courses': my_courses,
        'today_sessions': today_sessions,
        'total_students': total_students,
        'active_sessions': active_sessions,
        'total_courses': my_courses.count(),
        'first_course_with_students': first_course_with_students,
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_class_attendance(request, course_id):
    """Teacher views attendance records for a specific course."""
    course = get_object_or_404(Course, pk=course_id)
    # Ensure the professor owns this course (unless admin)
    if request.user.role == User.Role.PROFESSOR and course.professor != request.user:
        messages.error(request, 'You do not have access to this course.')
        return redirect('attendance:teacher_dashboard')

    sessions = (
        AttendanceSession.objects.filter(course=course)
        .select_related('location')
        .annotate(student_count=Count('records'))
        .order_by('-started_at')[:50]
    )
    enrolled = CourseEnrollment.objects.filter(course=course).select_related('student')
    total_enrolled = enrolled.count()

    return render(request, 'attendance/teacher_class_attendance.html', {
        'course': course,
        'sessions': sessions,
        'total_enrolled': total_enrolled,
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_session_mark_students(request, session_id):
    """Teacher marks students present for a session (e.g. when student has device/portal issues)."""
    session = get_object_or_404(AttendanceSession.objects.select_related('course', 'location'), pk=session_id)
    if not session.course_id:
        messages.error(request, 'This session is not linked to a course. Cannot mark students by hand.')
        return redirect('attendance:manage_sessions')
    course = session.course
    if request.user.role == User.Role.PROFESSOR and course.professor != request.user:
        messages.error(request, 'You do not have access to this course.')
        return redirect('attendance:teacher_dashboard')

    enrolled = CourseEnrollment.objects.filter(course=course).select_related('student')
    marked_ids = set(
        AttendanceRecord.objects.filter(session=session).values_list('user_id', flat=True)
    )
    students_status = []
    for e in enrolled:
        students_status.append({
            'student': e.student,
            'marked': e.student_id in marked_ids,
        })

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        if student_id:
            student = get_object_or_404(User, pk=student_id)
            if not CourseEnrollment.objects.filter(course=course, student=student).exists():
                messages.error(request, 'Student is not enrolled in this course.')
            else:
                record, created = AttendanceRecord.objects.get_or_create(
                    user=student, session=session,
                    defaults={'location': session.location, 'status': AttendanceRecord.Status.ON_TIME},
                )
                if created:
                    messages.success(request, f'Marked {student.get_full_name()} present for this session.')
                else:
                    messages.info(request, f'{student.get_full_name()} was already marked present.')
        return redirect('attendance:teacher_session_mark_students', session_id=session.pk)

    return render(request, 'attendance/teacher_session_mark_students.html', {
        'session': session,
        'course': course,
        'students_status': students_status,
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_student_roster(request, course_id):
    """Student roster with attendance percentage per student."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user.role == User.Role.PROFESSOR and course.professor != request.user:
        messages.error(request, 'You do not have access to this course.')
        return redirect('attendance:teacher_dashboard')

    total_sessions = AttendanceSession.objects.filter(course=course, ended_at__isnull=False).count()
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('student')

    roster = []
    for e in enrollments:
        records_qs = AttendanceRecord.objects.filter(
            user=e.student, session__course=course,
        )
        attended = records_qs.count()
        on_time_count = records_qs.filter(status=AttendanceRecord.Status.ON_TIME).count()
        late_count = records_qs.filter(status=AttendanceRecord.Status.LATE).count()
        pct = round(attended / total_sessions * 100) if total_sessions else 0
        roster.append({
            'student': e.student,
            'attended': attended,
            'total': total_sessions,
            'missed': total_sessions - attended,
            'on_time_count': on_time_count,
            'late_count': late_count,
            'percentage': pct,
            'status': 'danger' if pct < 75 else ('warning' if pct < 85 else 'success'),
        })
    roster.sort(key=lambda x: x['percentage'])

    return render(request, 'attendance/teacher_roster.html', {
        'course': course,
        'roster': roster,
        'total_sessions': total_sessions,
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_export(request, course_id):
    """Export attendance data for a course to CSV."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user.role == User.Role.PROFESSOR and course.professor != request.user:
        return redirect('attendance:teacher_dashboard')

    records = (
        AttendanceRecord.objects.filter(session__course=course)
        .select_related('user', 'session', 'location')
        .order_by('-marked_at')
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{course.code}_attendance.csv"'
    writer = csv.writer(response)
    writer.writerow(['Student ID', 'Name', 'Email', 'Date/Time', 'Location', 'Session', 'Status'])
    for r in records[:5000]:
        writer.writerow([
            r.user.institutional_id,
            r.user.get_full_name(),
            r.user.email,
            r.marked_at.strftime('%Y-%m-%d %H:%M:%S'),
            r.location.name,
            r.session.started_at.strftime('%Y-%m-%d %H:%M') if r.session.started_at else '',
            r.get_status_display(),
        ])
    return response


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_send_notification(request, course_id):
    """Teacher sends a notification to all students in a course."""
    course = get_object_or_404(Course, pk=course_id)
    if request.user.role == User.Role.PROFESSOR and course.professor != request.user:
        messages.error(request, 'You do not have access to this course.')
        return redirect('attendance:teacher_dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        message_text = request.POST.get('message', '').strip()
        if title and message_text:
            students = CourseEnrollment.objects.filter(course=course).select_related('student')
            for e in students:
                notify(e.student, title, message_text, notification_type='system')
            messages.success(request, f'Notification sent to {students.count()} students in {course.code}.')
            return redirect('attendance:teacher_class_attendance', course_id=course.pk)
        else:
            messages.error(request, 'Title and message are required.')

    enrolled_count = CourseEnrollment.objects.filter(course=course).count()
    return render(request, 'attendance/teacher_send_notification.html', {
        'course': course,
        'enrolled_count': enrolled_count,
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_schedule(request):
    """Teacher's schedule view for their courses."""
    courses = Course.objects.filter(
        professor=request.user, is_active=True,
    ).select_related('location').order_by('day_of_week', 'start_time')
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    schedule = {d: [] for d in days_order}
    for c in courses:
        if c.day_of_week:
            schedule[c.day_of_week].append(c)
    return render(request, 'attendance/teacher_schedule.html', {
        'schedule': schedule,
        'courses': courses,
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_analytics(request):
    """Visual analytics for the teacher's courses."""
    user = request.user
    courses = Course.objects.filter(professor=user, is_active=True).select_related('location')
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    # Per-course stats
    course_stats = []
    daily_labels = []
    daily_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        daily_labels.append(d.strftime('%a'))
        daily_data.append(
            AttendanceRecord.objects.filter(
                session__course__professor=user, marked_at__date=d,
            ).count()
        )

    for c in courses:
        total = AttendanceSession.objects.filter(course=c, ended_at__isnull=False).count()
        enrolled = CourseEnrollment.objects.filter(course=c).count()
        avg_attendance = 0
        if total and enrolled:
            total_marks = AttendanceRecord.objects.filter(session__course=c).count()
            avg_attendance = round(total_marks / total / enrolled * 100) if total else 0
        course_stats.append({
            'course': c,
            'total_sessions': total,
            'enrolled': enrolled,
            'avg_attendance': min(avg_attendance, 100),
        })

    # Leave requests pending
    pending_leaves = LeaveRequest.objects.filter(
        course__professor=user, status=LeaveRequest.Status.PENDING,
    ).select_related('student', 'course').count()

    return render(request, 'attendance/teacher_analytics.html', {
        'course_stats': course_stats,
        'daily_labels': daily_labels,
        'daily_data': daily_data,
        'pending_leaves': pending_leaves,
        'total_courses': courses.count(),
    })


@role_required(User.Role.PROFESSOR, User.Role.ADMIN)
def teacher_leave_review(request):
    """Teacher reviews leave requests for their courses."""
    leaves = LeaveRequest.objects.filter(
        course__professor=request.user,
    ).select_related('student', 'course', 'reviewed_by').order_by('status', '-created_at')

    if request.method == 'POST':
        leave_id = request.POST.get('leave_id')
        action = request.POST.get('action')
        if leave_id and action in ('approved', 'rejected'):
            leave = get_object_or_404(LeaveRequest, pk=leave_id, course__professor=request.user)
            leave.status = action
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
            notify(
                leave.student,
                f'Leave Request {action.title()}',
                f'Your leave request for {leave.course.code} on {leave.date} has been {action}.',
                notification_type='system',
            )
            messages.success(request, f'Leave request {action}.')
            return redirect('attendance:teacher_leaves')

    return render(request, 'attendance/teacher_leaves.html', {'leaves': leaves})


# ===========================================================================
# PARENT PORTAL (read-only view of linked student's data)
# ===========================================================================

@role_required(User.Role.PARENT)
def parent_dashboard(request):
    """Parent overview: linked students with quick attendance stats."""
    from users.models import ParentStudentLink
    links = ParentStudentLink.objects.filter(parent=request.user).select_related('student')
    children = []
    for link in links:
        student = link.student
        enrolled = CourseEnrollment.objects.filter(student=student).count()
        total_records = AttendanceRecord.objects.filter(user=student).count()
        pending_leaves = LeaveRequest.objects.filter(
            student=student, status=LeaveRequest.Status.PENDING,
        ).count()
        children.append({
            'student': student,
            'enrolled_courses': enrolled,
            'total_attendance': total_records,
            'pending_leaves': pending_leaves,
        })
    return render(request, 'attendance/parent_dashboard.html', {'children': children})


@role_required(User.Role.PARENT)
def parent_student_attendance(request, student_id):
    """Parent views a linked student's attendance history."""
    from users.models import ParentStudentLink
    link = get_object_or_404(ParentStudentLink, parent=request.user, student_id=student_id)
    student = link.student
    records = (
        AttendanceRecord.objects.filter(user=student)
        .select_related('session', 'session__course', 'location')
    )
    course_id = request.GET.get('course')
    if course_id:
        records = records.filter(session__course_id=course_id)
    enrolled_courses = Course.objects.filter(enrollments__student=student, is_active=True)
    return render(request, 'attendance/parent_student_attendance.html', {
        'student': student,
        'records': records[:200],
        'courses': enrolled_courses,
        'filters': {'course': course_id},
    })


@role_required(User.Role.PARENT)
def parent_student_stats(request, student_id):
    """Parent views a linked student's attendance stats per course."""
    from users.models import ParentStudentLink
    link = get_object_or_404(ParentStudentLink, parent=request.user, student_id=student_id)
    student = link.student
    enrollments = CourseEnrollment.objects.filter(
        student=student,
    ).select_related('course', 'course__professor', 'course__location')
    stats = []
    for enrollment in enrollments:
        course = enrollment.course
        total_sessions = AttendanceSession.objects.filter(course=course, ended_at__isnull=False).count()
        attended = AttendanceRecord.objects.filter(user=student, session__course=course).count()
        pct = round(attended / total_sessions * 100) if total_sessions else 0
        stats.append({
            'course': course,
            'total_sessions': total_sessions,
            'attended': attended,
            'missed': total_sessions - attended,
            'percentage': pct,
            'status': 'danger' if pct < 75 else ('warning' if pct < 85 else 'success'),
        })
    return render(request, 'attendance/parent_student_stats.html', {
        'student': student, 'stats': stats,
    })


@role_required(User.Role.PARENT)
def parent_student_timetable(request, student_id):
    """Parent views a linked student's class schedule (list or weekly grid)."""
    from users.models import ParentStudentLink
    link = get_object_or_404(ParentStudentLink, parent=request.user, student_id=student_id)
    student = link.student
    courses = Course.objects.filter(
        enrollments__student=student, is_active=True,
    ).select_related('professor', 'location').order_by('day_of_week', 'start_time')
    days_order = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    schedule = {d: [] for d in days_order}
    for c in courses:
        if c.day_of_week:
            schedule[c.day_of_week].append(c)
    schedule_items = _schedule_items_for_student(student)
    grid_data = _build_timetable_grid(schedule_items)
    view_mode = request.GET.get('view', 'list')
    if view_mode not in ('list', 'grid'):
        view_mode = 'list'
    return render(request, 'attendance/parent_student_timetable.html', {
        'student': student, 'schedule': schedule, 'courses': courses,
        'schedule_items': schedule_items,
        'grid_data': grid_data,
        'view_mode': view_mode,
    })


@role_required(User.Role.PARENT)
def parent_student_leaves(request, student_id):
    """Parent views a linked student's leave requests (read-only)."""
    from users.models import ParentStudentLink
    link = get_object_or_404(ParentStudentLink, parent=request.user, student_id=student_id)
    student = link.student
    leaves = LeaveRequest.objects.filter(student=student).select_related('course', 'reviewed_by')
    return render(request, 'attendance/parent_student_leaves.html', {
        'student': student, 'leaves': leaves,
    })


# ===========================================================================
# Admin: Course management
# ===========================================================================

@role_required(User.Role.ADMIN)
def manage_courses(request):
    """Admin creates and manages courses."""
    courses = Course.objects.all().select_related('professor', 'location')
    professors = User.objects.filter(role=User.Role.PROFESSOR, is_active=True)
    locations = Location.objects.all().order_by('name')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip()
        professor_id = request.POST.get('professor_id')
        location_id = request.POST.get('location_id') or None
        day = request.POST.get('day_of_week', '')
        start = request.POST.get('start_time') or None
        end = request.POST.get('end_time') or None

        if name and code and professor_id:
            if Course.objects.filter(code=code).exists():
                messages.error(request, f'Course code "{code}" already exists.')
            else:
                prof = get_object_or_404(User, pk=professor_id, role=User.Role.PROFESSOR)
                loc = Location.objects.filter(pk=location_id).first() if location_id else None
                Course.objects.create(
                    name=name, code=code, professor=prof, location=loc,
                    day_of_week=day, start_time=start, end_time=end,
                )
                messages.success(request, f'Course "{code}" created.')
                return redirect('attendance:manage_courses')
        else:
            messages.error(request, 'Name, code, and professor are required.')

    return render(request, 'attendance/manage_courses.html', {
        'courses': courses,
        'professors': professors,
        'locations': locations,
    })


@role_required(User.Role.ADMIN)
def manage_course_enrollment(request, course_id):
    """Admin enrolls/removes students from a course."""
    course = get_object_or_404(Course, pk=course_id)
    enrolled = CourseEnrollment.objects.filter(course=course).select_related('student')
    students = User.objects.filter(role=User.Role.STUDENT, is_active=True).exclude(
        pk__in=enrolled.values_list('student_id', flat=True)
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        student_id = request.POST.get('student_id')
        if action == 'enroll' and student_id:
            stu = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
            CourseEnrollment.objects.get_or_create(student=stu, course=course)
            messages.success(request, f'{stu.get_full_name()} enrolled in {course.code}.')
        elif action == 'remove' and student_id:
            CourseEnrollment.objects.filter(student_id=student_id, course=course).delete()
            messages.success(request, 'Student removed from course.')
        return redirect('attendance:manage_course_enrollment', course_id=course.pk)

    return render(request, 'attendance/manage_course_enrollment.html', {
        'course': course,
        'enrolled': enrolled,
        'available_students': students,
    })


# ===========================================================================
# Helpers
# ===========================================================================

def _get_or_create_session(location):
    """Get active session or create one."""
    session = AttendanceSession.objects.filter(location=location, ended_at__isnull=True).first()
    if not session:
        session = AttendanceSession.objects.create(location=location)
    return session
