# Generated migration to add encrypted_password and api_token
from django.db import migrations, models
import secrets


def populate_api_tokens(apps, schema_editor):
    DeviceInstance = apps.get_model('core', 'DeviceInstance')
    for d in DeviceInstance.objects.all():
        if not d.api_token:
            d.api_token = secrets.token_hex(32)
            d.save(update_fields=['api_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_deviceinstance_telemetry'),
    ]

    operations = [
        migrations.AddField(
            model_name='deviceconfig',
            name='encrypted_password',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='deviceinstance',
            name='api_token',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.RunPython(populate_api_tokens),
        migrations.AlterField(
            model_name='deviceinstance',
            name='api_token',
            field=models.CharField(max_length=64, unique=True),
        ),
    ]
