from django.contrib import admin

from .models import Invoice, InvoiceLine


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'center', 'invoice_no', 'status', 'client_name', 'issue_date', 'total')
    list_filter = ('status', 'center')
    search_fields = ('client_name', 'client_email', 'company_name')
    inlines = [InvoiceLineInline]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'description', 'quantity', 'unit_price', 'line_total')
