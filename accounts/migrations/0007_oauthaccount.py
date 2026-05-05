from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_emailverificationtoken_carexpiryreminderlog'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OAuthAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('google', 'Google'), ('credentials', 'Email si parola')], max_length=20, verbose_name='Provider')),
                ('provider_user_id', models.CharField(max_length=255, verbose_name='ID utilizator provider')),
                ('provider_email', models.EmailField(blank=True, max_length=254, verbose_name='Email provider')),
                ('email_verified', models.BooleanField(default=False, verbose_name='Email verificat de provider')),
                ('name', models.CharField(blank=True, max_length=255, verbose_name='Nume provider')),
                ('avatar_url', models.URLField(blank=True, verbose_name='Avatar provider')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='oauth_accounts', to=settings.AUTH_USER_MODEL, verbose_name='Utilizator')),
            ],
            options={
                'verbose_name': 'Cont autentificare externa',
                'verbose_name_plural': 'Conturi autentificare externa',
                'unique_together': {('provider', 'provider_user_id')},
            },
        ),
        migrations.AddIndex(
            model_name='oauthaccount',
            index=models.Index(fields=['provider', 'provider_email'], name='accounts_oa_provide_78c1a3_idx'),
        ),
    ]
