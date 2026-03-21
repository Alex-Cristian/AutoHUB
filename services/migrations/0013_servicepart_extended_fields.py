from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0012_alter_mechanicphoto_photo_type_servicepart'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicepart',
            name='brand',
            field=models.CharField(blank=True, max_length=80, verbose_name='Brand / producator'),
        ),
        migrations.AddField(
            model_name='servicepart',
            name='category',
            field=models.CharField(
                choices=[
                    ('motor', 'Motor'),
                    ('consumabile', 'Consumabile'),
                    ('franare', 'Franare'),
                    ('electric', 'Electric'),
                    ('caroserie', 'Caroserie'),
                    ('suspensie', 'Suspensie'),
                    ('anvelope', 'Anvelope'),
                    ('altele', 'Altele'),
                ],
                default='altele',
                max_length=30,
                verbose_name='Categorie',
            ),
        ),
        migrations.AddField(
            model_name='servicepart',
            name='price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Pret unitar estimat'),
        ),
        migrations.AddField(
            model_name='servicepart',
            name='supplier',
            field=models.CharField(blank=True, max_length=120, verbose_name='Furnizor'),
        ),
    ]
