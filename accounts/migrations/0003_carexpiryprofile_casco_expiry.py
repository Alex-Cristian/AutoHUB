from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_carexpiryprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="carexpiryprofile",
            name="casco_expiry",
            field=models.DateField(blank=True, null=True, verbose_name="Expirare CASCO"),
        ),
    ]
