from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_carexpiryprofile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LegalAcceptance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_set', models.CharField(default='platform', max_length=30, verbose_name='Set documente')),
                ('terms_version', models.CharField(max_length=30, verbose_name='Versiune termeni')),
                ('privacy_version', models.CharField(max_length=30, verbose_name='Versiune confidențialitate')),
                ('cookies_version', models.CharField(max_length=30, verbose_name='Versiune cookie')),
                ('accepted_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Acceptat la')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='Adresă IP')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='legal_acceptance', to=settings.AUTH_USER_MODEL, verbose_name='Utilizator')),
            ],
            options={
                'verbose_name': 'Acceptare documente legale',
                'verbose_name_plural': 'Acceptări documente legale',
            },
        ),
    ]
