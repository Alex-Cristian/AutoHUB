from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0010_remove_booking_block_end_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='estimated_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preț aproximativ (RON)'),
        ),
        migrations.AlterField(
            model_name='booking',
            name='status',
            field=models.CharField(choices=[('pending', 'În așteptare'), ('quoted', 'În așteptarea clientului'), ('confirmed', 'Confirmată'), ('in_progress', 'În lucru'), ('done', 'Finalizată'), ('cancelled', 'Anulată')], default='pending', max_length=20, verbose_name='Status'),
        ),
    ]
