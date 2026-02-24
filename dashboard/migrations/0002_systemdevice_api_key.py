# Device API key for Pi authentication

import secrets
from django.db import migrations, models


def generate_api_keys(apps, schema_editor):
    SystemDevice = apps.get_model('dashboard', 'SystemDevice')
    for d in SystemDevice.objects.filter(api_key=''):
        d.api_key = secrets.token_hex(32)
        d.save(update_fields=['api_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemdevice',
            name='api_key',
            field=models.CharField(
                blank=True,
                help_text='Secret for device API auth. Generated automatically if blank.',
                max_length=64,
                unique=True,
            ),
        ),
        migrations.RunPython(generate_api_keys, migrations.RunPython.noop),
    ]
