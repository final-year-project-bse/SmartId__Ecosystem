"""
Management command: evaluate all active AlertRules and fire notifications.
Usage: python manage.py check_alerts
Schedule via cron / Windows Task Scheduler for automated monitoring.
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import User
from attendance.models import AttendanceRecord, AttendanceSession
from attendance.models import CourseEnrollment
from dashboard.models import AlertRule
from notifications.utils import notify_admins


def evaluate_rule(rule, start, today):
    """Return (pct, scope_label) for course-based or location-based rule."""
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


class Command(BaseCommand):
    help = 'Evaluate active alert rules and send notifications for breached thresholds.'

    def handle(self, *args, **options):
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

            pct, scope_label = evaluate_rule(rule, start, today)

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
                self.stdout.write(self.style.WARNING(
                    f'TRIGGERED: {rule.name} — {scope_label} {pct}% < {rule.threshold_pct}%'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Done. Checked {AlertRule.objects.filter(is_active=True).count()} rules, {triggered} triggered.'
        ))
