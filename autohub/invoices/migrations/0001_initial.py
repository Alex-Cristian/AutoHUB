# Generated manually
from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('services', '0003_servicecenter_verification'),
        ('bookings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Invoice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('invoice_no', models.PositiveIntegerField(blank=True, null=True, verbose_name='Număr')),
                ('issue_date', models.DateField(default=django.utils.timezone.now, verbose_name='Data emiterii')),
                ('due_date', models.DateField(blank=True, null=True, verbose_name='Scadență (opțional)')),
                ('company_name', models.CharField(max_length=255, verbose_name='Denumire firmă')),
                ('company_address', models.CharField(max_length=300, verbose_name='Adresă')),
                ('company_city', models.CharField(blank=True, max_length=100, verbose_name='Oraș')),
                ('company_phone', models.CharField(blank=True, max_length=30, verbose_name='Telefon')),
                ('company_email', models.EmailField(blank=True, max_length=254, verbose_name='Email')),
                ('company_fiscal_code', models.CharField(blank=True, max_length=50, verbose_name='CIF')),
                ('company_trade_register_no', models.CharField(blank=True, max_length=50, verbose_name='Nr. RC')),
                ('client_name', models.CharField(max_length=200, verbose_name='Client')),
                ('client_email', models.EmailField(blank=True, max_length=254, verbose_name='Email client')),
                ('client_phone', models.CharField(blank=True, max_length=30, verbose_name='Telefon client')),
                ('client_address', models.CharField(blank=True, max_length=300, verbose_name='Adresă client')),
                ('client_fiscal_code', models.CharField(blank=True, max_length=50, verbose_name='CIF client (dacă e firmă)')),
                ('notes', models.TextField(blank=True, verbose_name='Note')),
                ('subtotal', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('final', 'Finalizată')], default='draft', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='bookings.booking', verbose_name='Programare')),
                ('center', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='services.servicecenter', verbose_name='Service')),
            ],
            options={
                'verbose_name': 'Factură',
                'verbose_name_plural': 'Facturi',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InvoiceLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=300, verbose_name='Descriere')),
                ('quantity', models.DecimalField(decimal_places=2, default=Decimal('1.00'), max_digits=10, verbose_name='Cantitate')),
                ('unit_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Preț unitar')),
                ('line_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Total linie')),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='invoices.invoice')),
            ],
            options={
                'verbose_name': 'Linie factură',
                'verbose_name_plural': 'Linii factură',
            },
        ),
        migrations.AddConstraint(
            model_name='invoice',
            constraint=models.UniqueConstraint(fields=('center', 'invoice_no'), name='uniq_invoice_no_per_center'),
        ),
    ]
