from decimal import Decimal

from django.db import models
from django.utils import timezone

from bookings.models import Booking
from services.models import ServiceCenter


class Invoice(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_FINAL = 'final'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_FINAL, 'Emisa'),
        (STATUS_PAID, 'Achitata'),
        (STATUS_CANCELLED, 'Anulata'),
    ]

    center = models.ForeignKey(
        ServiceCenter, on_delete=models.CASCADE, related_name='invoices', verbose_name='Service'
    )
    booking = models.ForeignKey(
        Booking, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='invoices', verbose_name='Programare'
    )
    invoice_no = models.PositiveIntegerField(null=True, blank=True, verbose_name='Numar')

    issue_date = models.DateField(default=timezone.now, verbose_name='Data emiterii')
    due_date = models.DateField(null=True, blank=True, verbose_name='Scadenta')

    company_name = models.CharField(max_length=255, verbose_name='Denumire firma')
    company_address = models.CharField(max_length=300, verbose_name='Adresa')
    company_city = models.CharField(max_length=100, blank=True, verbose_name='Oras')
    company_phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon')
    company_email = models.EmailField(blank=True, verbose_name='Email')
    company_fiscal_code = models.CharField(max_length=50, blank=True, verbose_name='CIF')
    company_trade_register_no = models.CharField(max_length=50, blank=True, verbose_name='Nr. RC')

    client_name = models.CharField(max_length=200, verbose_name='Client')
    client_email = models.EmailField(blank=True, verbose_name='Email client')
    client_phone = models.CharField(max_length=30, blank=True, verbose_name='Telefon client')
    client_address = models.CharField(max_length=300, blank=True, verbose_name='Adresa client')
    client_fiscal_code = models.CharField(max_length=50, blank=True, verbose_name='CIF client')

    notes = models.TextField(blank=True, verbose_name='Note')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturi'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['center', 'invoice_no'], name='uniq_invoice_no_per_center')
        ]

    def __str__(self):
        if self.invoice_no:
            return f"Factura #{self.invoice_no} - {self.center.name}"
        return f"Factura draft ({self.center.name})"

    def assign_next_number_if_needed(self):
        if self.invoice_no:
            return
        last = Invoice.objects.filter(center=self.center, invoice_no__isnull=False).order_by('-invoice_no').first()
        self.invoice_no = (last.invoice_no + 1) if last else 1

    def recalc_totals(self, save=True):
        subtotal = Decimal('0.00')
        for line in self.lines.all():
            subtotal += line.line_total
        self.subtotal = subtotal
        self.total = subtotal
        if save:
            self.save(update_fields=['subtotal', 'total', 'updated_at'])


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=300, verbose_name='Descriere')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('1.00'), verbose_name='Cantitate')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Pret unitar')
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Total linie')

    class Meta:
        verbose_name = 'Linie factura'
        verbose_name_plural = 'Linii factura'

    def __str__(self):
        return f"{self.description} ({self.quantity} x {self.unit_price})"

    def save(self, *args, **kwargs):
        self.line_total = (self.quantity or Decimal('0')) * (self.unit_price or Decimal('0'))
        super().save(*args, **kwargs)
