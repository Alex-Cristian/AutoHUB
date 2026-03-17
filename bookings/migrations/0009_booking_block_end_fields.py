from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0008_booking_ai_duration_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="block_end_date",
            field=models.DateField(blank=True, null=True, verbose_name="Blocare până la data"),
        ),
        migrations.AddField(
            model_name="booking",
            name="block_end_time",
            field=models.TimeField(blank=True, null=True, verbose_name="Blocare până la ora"),
        ),
    ]
