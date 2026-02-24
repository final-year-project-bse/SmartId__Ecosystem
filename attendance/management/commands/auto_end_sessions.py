"""
Auto-end attendance sessions when current time is past the slot's end_time.
Also detect "ghost sessions" (timetable slot had no session started) and notify admins.

Usage: python manage.py auto_end_sessions
Schedule via cron / Task Scheduler (e.g. every 5–15 minutes).
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from attendance.models import AttendanceSession, TimetableSlot
from notifications.utils import notify_admins


class Command(BaseCommand):
    help = 'End sessions past their slot end_time; alert admins for ghost slots (no session started).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ghost-only',
            action='store_true',
            help='Only check ghost sessions, do not auto-end.',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        today = now.date()
        current_time = now.time()
        day_of_week = now.weekday() + 1  # 1=Monday .. 7=Sunday
        ended_count = 0
        ghost_count = 0

        if not options['ghost_only']:
            # 1) Auto-end: sessions with a slot whose end_time has passed
            active = AttendanceSession.objects.filter(
                ended_at__isnull=True, slot__isnull=False,
            ).select_related('slot')
            for session in active:
                if session.slot.day_of_week == day_of_week and session.started_at.date() == today:
                    if current_time > session.slot.end_time:
                        session.ended_at = now
                        session.save(update_fields=['ended_at'])
                        ended_count += 1
                        self.stdout.write(self.style.WARNING(
                            f'Auto-ended session {session.pk} ({session.course.code if session.course else session.location.name})'
                        ))

            # Sessions without slot: try to match by (location, course, today)
            active_no_slot = AttendanceSession.objects.filter(
                ended_at__isnull=True, slot__isnull=True,
            ).select_related('location', 'course')
            for session in active_no_slot:
                if session.started_at.date() != today or not session.course_id:
                    continue
                slot = TimetableSlot.objects.filter(
                    location=session.location, course=session.course, day_of_week=day_of_week,
                ).first()
                if slot and current_time > slot.end_time:
                    session.ended_at = now
                    session.save(update_fields=['ended_at'])
                    ended_count += 1
                    self.stdout.write(self.style.WARNING(
                        f'Auto-ended session {session.pk} (no slot link) {session.course.code}'
                    ))

        # 2) Ghost sessions: slots that ended today but had no session started
        # Consider slots where end_time < current_time (already ended)
        past_slots = TimetableSlot.objects.filter(
            day_of_week=day_of_week, end_time__lt=current_time,
        ).select_related('course', 'location', 'professor')
        for slot in past_slots:
            # Was there any session for this slot today? (by slot_id or by location+course+date)
            had_session = AttendanceSession.objects.filter(
                Q(slot=slot) | Q(location=slot.location, course=slot.course, started_at__date=today),
            ).exists()
            if not had_session:
                notify_admins(
                    'Ghost Session: No class started',
                    f'Timetable slot {slot.course.code} at {slot.location.name} '
                    f'({slot.get_day_of_week_display()} {slot.start_time}-{slot.end_time}) had no attendance session started.',
                    notification_type='system',
                )
                ghost_count += 1
                self.stdout.write(self.style.WARNING(
                    f'Ghost: {slot.course.code} @ {slot.location.name} — no session started'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Done. Auto-ended {ended_count} session(s), {ghost_count} ghost alert(s) sent.'
        ))
