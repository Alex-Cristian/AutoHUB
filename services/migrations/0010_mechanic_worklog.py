from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0009_servicemechanic'),
        ('bookings', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicemechanic',
            name='specialization',
            field=models.CharField(blank=True, max_length=200, verbose_name='Specializare'),
        ),
        migrations.AddField(
            model_name='servicemechanic',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='mechanic_photos/', verbose_name='Fotografie'),
        ),
        migrations.AddField(
            model_name='servicemechanic',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='Activ'),
        ),
        migrations.CreateModel(
            name='MechanicWorkLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('repair_description', models.TextField(blank=True, verbose_name='Descriere reparatie')),
                ('parts_used', models.TextField(blank=True, verbose_name='Piese folosite')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='Inceput lucru')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='Terminat lucru')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='work_log', to='bookings.booking', verbose_name='Programare')),
                ('mechanic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_logs', to='services.servicemechanic', verbose_name='Mecanic')),
            ],
            options={
                'verbose_name': 'Fisa lucru mecanic',
                'verbose_name_plural': 'Fise lucru mecanici',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MechanicPhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', models.ImageField(upload_to='mechanic_work_photos/', verbose_name='Fotografie')),
                ('photo_type', models.CharField(choices=[('before', 'Inainte de reparatie'), ('after', 'Dupa reparatie')], default='before', max_length=10, verbose_name='Tip fotografie')),
                ('caption', models.CharField(blank=True, max_length=200, verbose_name='Descriere')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('work_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='services.mechanicworklog', verbose_name='Fisa lucru')),
            ],
            options={
                'verbose_name': 'Fotografie lucru',
                'verbose_name_plural': 'Fotografii lucru',
                'ordering': ['photo_type', 'uploaded_at'],
            },
        ),
    ]