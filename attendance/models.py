"""
Real-Time Attendance Logging (FR-5, FR-6), Access Logging (FR-8),
Course Management, and Leave Requests.
"""
from django.db import models
from django.conf import settings


class Location(models.Model):
    """Classroom, lab, library, gate."""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    location_type = models.CharField(max_length=50, choices=[
        ('classroom', 'Classroom'),
        ('lab', 'Lab'),
        ('library', 'Library'),
        ('gate', 'Gate'),
    ], default='classroom')

    def __str__(self):
        return f"{self.name} ({self.code})"


# ---------------------------------------------------------------------------
# Course & Enrollment
# ---------------------------------------------------------------------------

class Course(models.Model):
    """Academic course/subject linked to a professor and location."""
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='taught_courses',
        limit_choices_to={'role': 'professor'},
    )
    location = models.ForeignKey(
        Location, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='courses',
    )
    description = models.TextField(blank=True)
    # Schedule fields
    day_of_week = models.CharField(max_length=20, choices=[
        ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'), ('friday', 'Friday'), ('saturday', 'Saturday'),
    ], blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['professor', 'is_active']),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def schedule_display(self):
        if self.day_of_week and self.start_time and self.end_time:
            return f"{self.get_day_of_week_display()} {self.start_time.strftime('%I:%M %p')} – {self.end_time.strftime('%I:%M %p')}"
        return "Not scheduled"


class CourseEnrollment(models.Model):
    """Many-to-many: students enrolled in courses."""
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='course_enrollments',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['student', 'course']]
        ordering = ['-enrolled_at']
        indexes = [
            models.Index(fields=['student', 'course']),
        ]

    def __str__(self):
        return f"{self.student.institutional_id} → {self.course.code}"


# ---------------------------------------------------------------------------
# Timetable (Weekly Recurrence) — Rule-based slots for auto-fill & alerts
# ---------------------------------------------------------------------------

class TimetableSlot(models.Model):
    """
    Weekly recurrence: one row per (course, location, day, start).
    Enables pre-fill on Start Session, auto-end by slot end_time, ghost-session alerts.
    """
    DAY_CHOICES = [
        (1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'),
        (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday'),
    ]
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='timetable_slots',
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='timetable_slots',
        limit_choices_to={'role': 'professor'},
    )
    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name='timetable_slots',
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']
        unique_together = [['location', 'day_of_week', 'start_time']]
        indexes = [
            models.Index(fields=['professor', 'day_of_week']),
            models.Index(fields=['location', 'day_of_week']),
        ]

    def __str__(self):
        return f"{self.course.code} @ {self.location.name} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.db.models import Q
        if not self.start_time or not self.end_time:
            return
        if self.end_time <= self.start_time:
            raise ValidationError('end_time must be after start_time.')
        # No overlapping slot for same location on same day
        qs = TimetableSlot.objects.filter(
            location=self.location, day_of_week=self.day_of_week,
        ).exclude(pk=self.pk)
        for other in qs:
            if (self.start_time < other.end_time and self.end_time > other.start_time):
                raise ValidationError(
                    f'Location {self.location.name} is already booked at this time on {self.get_day_of_week_display()}.'
                )
        # No overlapping slot for same professor on same day
        qs2 = TimetableSlot.objects.filter(
            professor=self.professor, day_of_week=self.day_of_week,
        ).exclude(pk=self.pk)
        for other in qs2:
            if (self.start_time < other.end_time and self.end_time > other.start_time):
                raise ValidationError(
                    f'You already have a class at this time on {self.get_day_of_week_display()}.'
                )


# ---------------------------------------------------------------------------
# Attendance Sessions & Records
# ---------------------------------------------------------------------------

class AttendanceSession(models.Model):
    """Active session for a location (e.g. class period)."""
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='sessions')
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sessions',
        help_text='Optional: link this session to a course',
    )
    slot = models.ForeignKey(
        TimetableSlot, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sessions', help_text='Set when session is started from timetable (for auto-end).',
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_sessions'
    )

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['ended_at']),
            models.Index(fields=['-started_at']),
            models.Index(fields=['course', '-started_at']),
        ]

    def __str__(self):
        label = self.course.code if self.course else self.location.name
        return f"{label} @ {self.started_at.strftime('%b %d %H:%M') if self.started_at else '?'}"


class AttendanceRecord(models.Model):
    """Single attendance mark (FR-5): unique per user per session."""
    class Status(models.TextChoices):
        ON_TIME = 'on_time', 'On time'
        LATE = 'late', 'Late'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_records')
    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name='records')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='attendance_records')
    marked_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ON_TIME,
        help_text='On time (within 20 min of session start) or late',
    )

    class Meta:
        unique_together = [['user', 'session']]
        ordering = ['-marked_at']
        indexes = [
            models.Index(fields=['marked_at']),
            models.Index(fields=['user', 'marked_at']),
            models.Index(fields=['location', 'marked_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.user.institutional_id} @ {self.session}"


class AccessLog(models.Model):
    """Access events for audit (FR-8)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='access_logs', null=True, blank=True
    )
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='access_logs')
    accessed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    auth_method = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['-accessed_at']
        indexes = [
            models.Index(fields=['accessed_at', 'success']),
        ]


# ---------------------------------------------------------------------------
# Face + RFID attendance (Pi device flow)
# ---------------------------------------------------------------------------

class PendingRFIDScan(models.Model):
    """
    Queue: user scanned RFID at device/session; waiting for face match.
    TTL: entries older than e.g. 5 minutes are ignored when matching.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pending_rfid_scans',
    )
    session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE,
        related_name='pending_rfid_scans',
    )
    device_id = models.PositiveIntegerField(
        help_text='SystemDevice.pk that received the scan',
    )
    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scanned_at']
        indexes = [
            models.Index(fields=['session', 'device_id']),
            models.Index(fields=['scanned_at']),
        ]
        verbose_name = 'Pending RFID scan'
        verbose_name_plural = 'Pending RFID scans'

    def __str__(self):
        return f"{self.user.institutional_id} @ session {self.session_id} (device {self.device_id})"


# ---------------------------------------------------------------------------
# Leave Requests
# ---------------------------------------------------------------------------

class LeaveRequest(models.Model):
    """Student leave/absence request."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='leave_requests',
        limit_choices_to={'role': 'student'},
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='leave_requests',
    )
    date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_leaves',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['course', 'status']),
        ]

    def __str__(self):
        return f"{self.student.institutional_id} — {self.course.code} ({self.date})"