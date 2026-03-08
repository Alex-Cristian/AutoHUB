from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from bookings.models import Booking
from services.models import ServiceCenter

from .forms import InvoiceForm, InvoiceLineFormSet
from .models import Invoice


def _owned_centers(user):
    if user.is_staff:
        return ServiceCenter.objects.all()
    return ServiceCenter.objects.filter(owner=user)


@login_required
def clients_list(request):
    centers = _owned_centers(request.user)
    if not centers.exists() and not request.user.is_staff:
        messages.info(request, 'Nu ai încă un service înregistrat.')
        return redirect('services:register_service')

    # Luăm ultimele programări per client (pe baza email-ului, fallback pe telefon)
    bookings = (Booking.objects
        .filter(center__in=centers)
        .exclude(status=Booking.STATUS_CANCELLED)
        .order_by('-created_at')
    )

    clients = OrderedDict()
    for b in bookings:
        key = (b.client_email or '').strip().lower() or (b.client_phone or '').strip()
        if not key:
            key = f"booking-{b.pk}"

        if key not in clients:
            clients[key] = {
                'name': b.client_name,
                'email': b.client_email,
                'phone': b.client_phone,
                'last_booking': b,
                'center': b.center,
                'count': 1,
            }
        else:
            clients[key]['count'] += 1

    return render(request, 'invoices/clients_list.html', {
        'clients': list(clients.values()),
    })


def _prefill_company(invoice: Invoice, center: ServiceCenter):
    invoice.company_name = center.legal_name or center.name
    invoice.company_address = center.headquarters or center.address
    invoice.company_city = center.get_city_display() if hasattr(center, 'get_city_display') else center.city
    invoice.company_phone = center.phone
    invoice.company_email = center.email or ''
    invoice.company_fiscal_code = center.fiscal_code or ''
    invoice.company_trade_register_no = center.trade_register_no or ''


@login_required
def invoice_create(request):
    centers = _owned_centers(request.user)
    if not centers.exists() and not request.user.is_staff:
        messages.info(request, 'Nu ai încă un service înregistrat.')
        return redirect('services:register_service')

    booking_id = request.GET.get('booking')
    booking = None
    center = None

    if booking_id:
        booking = get_object_or_404(Booking, pk=booking_id)
        if not (request.user.is_staff or booking.center.owner_id == request.user.id):
            return redirect('services:dashboard')
        center = booking.center
    else:
        # fallback: primul center
        center = centers.first()

    if request.method == 'POST':
        # center + booking se pun pe model înainte de validare
        invoice = Invoice(center=center, booking=booking)
        _prefill_company(invoice, center)

        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice, prefix='lines')

        action = request.POST.get('action', 'save')

        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.center = center
            invoice.booking = booking
            _prefill_company(invoice, center)
            invoice.save()

            formset.instance = invoice
            formset.save()
            invoice.recalc_totals(save=True)

            if action == 'finalize':
                invoice.assign_next_number_if_needed()
                invoice.status = Invoice.STATUS_FINAL
                invoice.save(update_fields=['invoice_no', 'status', 'updated_at'])
                messages.success(request, '✅ Factura a fost finalizată. Poți printa imediat.')
                return redirect('invoices:detail', pk=invoice.pk)

            messages.success(request, '✅ Factura a fost salvată ca draft.')
            return redirect('invoices:detail', pk=invoice.pk)
    else:
        invoice = Invoice(center=center, booking=booking)
        _prefill_company(invoice, center)

        # prefill client din booking
        if booking:
            invoice.client_name = booking.client_name
            invoice.client_email = booking.client_email
            invoice.client_phone = booking.client_phone

        form = InvoiceForm(instance=invoice)
        formset = InvoiceLineFormSet(instance=invoice, prefix='lines')

        # dacă avem service_item din booking, pre-populăm o linie
        if booking and booking.service_item:
            formset.extra = 0

    return render(request, 'invoices/invoice_form.html', {
        'form': form,
        'formset': formset,
        'booking': booking,
        'center': center,
    })


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not (request.user.is_staff or invoice.center.owner_id == request.user.id):
        return redirect('services:dashboard')

    return render(request, 'invoices/invoice_detail.html', {
        'invoice': invoice,
    })


@login_required
def invoice_finalize(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not (request.user.is_staff or invoice.center.owner_id == request.user.id):
        return redirect('services:dashboard')

    if request.method == 'POST':
        if invoice.status == Invoice.STATUS_FINAL:
            messages.info(request, 'Factura este deja finalizată.')
            return redirect('invoices:detail', pk=invoice.pk)

        invoice.assign_next_number_if_needed()
        invoice.status = Invoice.STATUS_FINAL
        invoice.save(update_fields=['invoice_no', 'status', 'updated_at'])
        messages.success(request, '✅ Factura a fost finalizată.')

    return redirect('invoices:detail', pk=invoice.pk)
