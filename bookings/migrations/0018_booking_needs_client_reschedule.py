from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0017_booking_duration_estimate_confidence_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='needs_client_reschedule',
            field=models.BooleanField(default=False, verbose_name='Clientul trebuie sa aleaga un nou interval'),
        ),
    ]
