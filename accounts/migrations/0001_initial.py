# Generated manually (Django migration).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Car',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('make', models.CharField(max_length=50, verbose_name='Marcă')),
                ('model', models.CharField(max_length=50, verbose_name='Model')),
                ('year', models.PositiveIntegerField(blank=True, null=True, verbose_name='An fabricație')),
                ('fuel', models.CharField(blank=True, max_length=20, verbose_name='Combustibil')),
                ('plate_number', models.CharField(max_length=15, verbose_name='Nr. înmatriculare')),
                ('vin', models.CharField(blank=True, max_length=17, verbose_name='Serie șasiu (VIN)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cars', to=settings.AUTH_USER_MODEL, verbose_name='Utilizator')),
            ],
            options={
                'verbose_name': 'Mașină',
                'verbose_name_plural': 'Mașini',
                'ordering': ['make', 'model', 'plate_number'],
                'unique_together': {('owner', 'plate_number')},
            },
        ),
    ]
