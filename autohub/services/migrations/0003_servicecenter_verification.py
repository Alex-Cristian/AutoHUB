from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0002_servicecenter_legal_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicecenter',
            name='verification_status',
            field=models.CharField(
                choices=[
                    ('not_required', 'Nu necesită verificare'),
                    ('pending', 'În așteptare verificare'),
                    ('verified', 'Verificat'),
                    ('rejected', 'Respins'),
                ],
                default='not_required',
                max_length=20,
                verbose_name='Status verificare',
            ),
        ),
        migrations.AddField(
            model_name='servicecenter',
            name='verification_note',
            field=models.TextField(blank=True, verbose_name='Notă verificare (intern)'),
        ),
        migrations.AddField(
            model_name='servicecenter',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Verificat la'),
        ),
    ]
