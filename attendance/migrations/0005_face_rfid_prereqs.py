# Face + RFID attendance prerequisites

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('attendance', '0004_course_courseenrollment_leaverequest_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='status',
            field=models.CharField(
                choices=[('on_time', 'On time'), ('late', 'Late')],
                default='on_time',
                help_text='On time (within 20 min of session start) or late',
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name='PendingRFIDScan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_id', models.PositiveIntegerField(help_text='SystemDevice.pk that received the scan')),
                ('scanned_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_rfid_scans', to='attendance.attendancesession')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_rfid_scans', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Pending RFID scan',
                'verbose_name_plural': 'Pending RFID scans',
                'ordering': ['scanned_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pendingrfidscan',
            index=models.Index(fields=['session', 'device_id'], name='attendance_p_session_6a0b0d_idx'),
        ),
        migrations.AddIndex(
            model_name='pendingrfidscan',
            index=models.Index(fields=['scanned_at'], name='attendance_p_scanned_8c1e2a_idx'),
        ),
        migrations.AddIndex(
            model_name='attendancerecord',
            index=models.Index(fields=['status'], name='attendance_a_status_9d4f1e_idx'),
        ),
    ]
