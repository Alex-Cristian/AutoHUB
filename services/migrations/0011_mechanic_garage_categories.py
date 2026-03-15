from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0010_mechanic_worklog'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicemechanic',
            name='garage',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='mechanics',
                to='services.servicegarage',
                verbose_name='Garaj alocat'
            ),
        ),
        migrations.AddField(
            model_name='servicemechanic',
            name='service_categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='mechanics',
                to='services.servicecategory',
                verbose_name='Categorii servicii'
            ),
        ),
    ]