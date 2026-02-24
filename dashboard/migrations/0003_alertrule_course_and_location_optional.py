# Course-based alert rules; location optional when course is set

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
        ('dashboard', '0002_systemdevice_api_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertrule',
            name='course',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional: when set, alert is based on this class/course attendance % instead of location.',
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='alert_rules',
                to='attendance.course',
            ),
        ),
        migrations.AlterField(
            model_name='alertrule',
            name='location',
            field=models.ForeignKey(
                blank=True,
                help_text='Required for location-based rules. Leave blank when using a specific course.',
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name='alert_rules',
                to='attendance.location',
            ),
        ),
    ]
