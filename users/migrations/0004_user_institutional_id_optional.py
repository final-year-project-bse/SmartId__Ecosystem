# Optional institutional_id for professor and parent (students still use registration number)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_parentstudentlink'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='institutional_id',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
    ]
