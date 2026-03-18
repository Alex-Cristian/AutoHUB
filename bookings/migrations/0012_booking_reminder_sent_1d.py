from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0011_booking_estimated_price_and_quoted'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='reminder_sent_1d',
            field=models.BooleanField(default=False, verbose_name='Reminder SMS trimis cu o zi înainte'),
        ),
    ]
