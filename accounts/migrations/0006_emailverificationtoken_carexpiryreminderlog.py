from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import secrets


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_merge_0003_legalacceptance_0004_alter_car_vin'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerificationToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=secrets.token_urlsafe, max_length=64, unique=True, verbose_name='Token')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True, verbose_name='Verificat la')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='email_verification_token', to=settings.AUTH_USER_MODEL, verbose_name='Utilizator')),
            ],
            options={
                'verbose_name': 'Token verificare email',
                'verbose_name_plural': 'Token-uri verificare email',
            },
        ),
        migrations.CreateModel(
            name='CarExpiryReminderLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_type', models.CharField(max_length=30, verbose_name='Tip document')),
                ('expiry_date', models.DateField(verbose_name='Data expirării')),
                ('sent_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Trimis la')),
                ('car', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expiry_email_logs', to='accounts.car', verbose_name='Mașină')),
            ],
            options={
                'verbose_name': 'Istoric reminder expirare email',
                'verbose_name_plural': 'Istoric remindere expirare email',
                'ordering': ['-sent_at'],
                'unique_together': {('car', 'document_type', 'expiry_date')},
            },
        ),
    ]
