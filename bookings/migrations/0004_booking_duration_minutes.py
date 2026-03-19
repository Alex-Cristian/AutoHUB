from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0003_booking_garage_bookingattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='duration_minutes',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Durată blocare garaj (minute)'),
        ),
    ]
