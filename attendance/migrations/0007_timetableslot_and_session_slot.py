# Timetable integration: TimetableSlot (weekly recurrence) + optional session.slot

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_rename_attendance_a_status_9d4f1e_idx_attendance__status_741eb8_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TimetableSlot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'), (6, 'Saturday'), (7, 'Sunday')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_slots', to='attendance.course')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timetable_slots', to='attendance.location')),
                ('professor', models.ForeignKey(limit_choices_to={'role': 'professor'}, on_delete=django.db.models.deletion.CASCADE, related_name='timetable_slots', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['day_of_week', 'start_time'],
                'unique_together': {('location', 'day_of_week', 'start_time')},
            },
        ),
        migrations.AddIndex(
            model_name='timetableslot',
            index=models.Index(fields=['professor', 'day_of_week'], name='attendance_t_profess_8a0b2a_idx'),
        ),
        migrations.AddIndex(
            model_name='timetableslot',
            index=models.Index(fields=['location', 'day_of_week'], name='attendance_t_locatio_9c1d4e_idx'),
        ),
        migrations.AddField(
            model_name='attendancesession',
            name='slot',
            field=models.ForeignKey(blank=True, help_text='Set when session is started from timetable (for auto-end).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions', to='attendance.timetableslot'),
        ),
    ]
