from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CarExpiryCalendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('itp_expiry', models.DateField(blank=True, null=True, verbose_name='Expirare ITP')),
                ('rca_expiry', models.DateField(blank=True, null=True, verbose_name='Expirare RCA')),
                ('rovinieta_expiry', models.DateField(blank=True, null=True, verbose_name='Expirare rovinietă')),
                ('trusa_expiry', models.DateField(blank=True, null=True, verbose_name='Expirare trusă auto')),
                ('extinctor_expiry', models.DateField(blank=True, null=True, verbose_name='Expirare extinctor')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('car', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='expiry_calendar', to='accounts.car', verbose_name='Mașină')),
            ],
            options={
                'verbose_name': 'Calendar expirări mașină',
                'verbose_name_plural': 'Calendare expirări mașini',
            },
        ),
    ]
