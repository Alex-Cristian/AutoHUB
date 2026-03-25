from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from bookings.models import Booking
from services.business import (
    build_clients_snapshot,
    build_vehicle_dossier,
    build_invoice_line_drafts_for_booking,
    finalize_invoice,
)
from services.models import ServiceCenter

from .forms import InvoiceForm, InvoiceLineForm, InvoiceLineFormSet
from .models import Invoice, InvoiceLine
from core.pdf_utils import build_invoice_pdf


def _owned_centers(user):
    if user.is_staff:
        return ServiceCenter.objects.all()
    return ServiceCenter.objects.filter(owner=user)


def _require_owned_centers(request):
    centers = _owned_centers(request.user)
    if not centers.exists() and not request.user.is_staff:
        messages.info(request, 'Nu ai inca un service inregistrat.')
        return None
    return centers


def _booking_for_invoice_owner_or_404(request, booking_id, centers):
    queryset = Booking.objects.select_related('center', 'service_item').prefetch_related(
        'job_card__operations',
        'job_card__part_usages',
    )
    if request.user.is_staff:
        return get_object_or_404(queryset, pk=booking_id)
    return get_object_or_404(queryset, pk=booking_id, center__in=centers)


def _invoice_for_user_or_404(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related('center', 'booking', 'booking__center'),
        pk=pk,
    )
    if request.user.is_staff or invoice.center.owner_id == request.user.id:
        return invoice
    return None


@login_required
def _legacy_clients_list_unused(request):
    centers = _owned_centers(request.user)
    if centers is None:
        messages.info(request, 'Nu ai încă un service înregistrat.')
        return redirect('services:register_service')

    bookings = (
        Booking.objects
        .filter(center__in=centers)
        .exclude(status=Booking.STATUS_CANCELLED)
        .order_by('-created_at')
    )

    clients = OrderedDict()
    for booking in bookings:
        key = (booking.client_email or '').strip().lower() or (booking.client_phone or '').strip()
        if not key:
            key = f'booking-{booking.pk}'

        if key not in clients:
            clients[key] = {
                'name': booking.client_name,
                'email': booking.client_email,
                'phone': booking.client_phone,
                'last_booking': booking,
                'center': booking.center,
                'count': 1,
            }
        else:
            clients[key]['count'] += 1

    clients_list_data = list(clients.values())
    page_obj = Paginator(clients_list_data, 20).get_page(request.GET.get('page'))

    return render(request, 'invoices/clients_list.html', {
        'clients': page_obj.object_list,
        'page_obj': page_obj,
        'total_clients': len(clients_list_data),
        'total_bookings': bookings.count(),
    })


def _prefill_company(invoice: Invoice, center: ServiceCenter):
    invoice.company_name = center.legal_name or center.name
    invoice.company_address = center.headquarters or center.address
    invoice.company_city = center.get_city_display() if hasattr(center, 'get_city_display') else center.city
    invoice.company_phone = center.phone
    invoice.company_email = center.email or ''
    invoice.company_fiscal_code = center.fiscal_code or ''
    invoice.company_trade_register_no = center.trade_register_no or ''


def _invoice_line_initial_for_booking(booking):
    if not booking:
        return []
    return build_invoice_line_drafts_for_booking(booking)


def _formset_has_meaningful_lines(formset):
    for form in formset.forms:
        cleaned = getattr(form, 'cleaned_data', None) or {}
        if cleaned.get('DELETE'):
            continue
        description = (cleaned.get('description') or '').strip()
        quantity = cleaned.get('quantity')
        unit_price = cleaned.get('unit_price')
        if description or quantity or unit_price:
            return True
    return False


def _create_auto_invoice_lines(invoice, booking):
    created = 0
    for line in _invoice_line_initial_for_booking(booking):
        InvoiceLine.objects.create(invoice=invoice, **line)
        created += 1
    return created


def _invoice_line_formset_class(extra_forms=1):
    return inlineformset_factory(
        Invoice,
        InvoiceLine,
        form=InvoiceLineForm,
        extra=max(1, extra_forms),
        can_delete=True,
    )


def _request_has_meaningful_line_inputs(post_data):
    for key, value in post_data.items():
        if not key.startswith('lines-'):
            continue
        if key.endswith(('-description', '-quantity', '-unit_price')) and str(value).strip():
            return True
    return False


@login_required
def invoice_create(request):
    centers = _require_owned_centers(request)
    if centers is None:
        messages.info(request, 'Nu ai încă un service înregistrat.')
        return redirect('services:register_service')

    booking_id = request.GET.get('booking')
    booking = None
    center = None

    if booking_id:
        booking = _booking_for_invoice_owner_or_404(request, booking_id, centers)
        center = booking.center
    else:
        center = centers.first()

    if center is None:
        messages.error(request, 'Nu am putut identifica service-ul pentru emiterea facturii.')
        return redirect('services:dashboard')

    if request.method == 'POST':
        invoice = Invoice(center=center, booking=booking, issue_date=timezone.localdate())
        _prefill_company(invoice, center)

        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice, prefix='lines')
        action = request.POST.get('action', 'save')
        has_manual_line_inputs = _request_has_meaningful_line_inputs(request.POST)
        form_is_valid = form.is_valid()
        formset_is_valid = formset.is_valid() if has_manual_line_inputs else True

        if form_is_valid and formset_is_valid:
            invoice = form.save(commit=False)
            invoice.center = center
            invoice.booking = booking
            _prefill_company(invoice, center)
            invoice.save()

            auto_lines_created = 0
            if has_manual_line_inputs:
                formset.instance = invoice
                formset.save()
            if booking and not invoice.lines.exists():
                auto_lines_created = _create_auto_invoice_lines(invoice, booking)

            invoice.recalc_totals(save=True)

            if action == 'finalize':
                try:
                    finalize_invoice(invoice, actor=request.user)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                    return redirect('invoices:detail', pk=invoice.pk)
                if auto_lines_created:
                    messages.success(request, 'Factura a fost finalizată și am preluat automat operațiunile și piesele din fișa lucrării.')
                else:
                    messages.success(request, 'Factura a fost finalizată. O poți tipări imediat.')
                return redirect('invoices:detail', pk=invoice.pk)

            if auto_lines_created:
                messages.success(request, 'Factura a fost salvată ca draft și am preluat automat operațiunile și piesele din fișa lucrării.')
            else:
                messages.success(request, 'Factura a fost salvată ca draft.')
            return redirect('invoices:detail', pk=invoice.pk)
    else:
        invoice = Invoice(center=center, booking=booking, issue_date=timezone.localdate())
        _prefill_company(invoice, center)

        if booking:
            invoice.client_name = booking.client_name
            invoice.client_email = booking.client_email
            invoice.client_phone = booking.client_phone

        line_initial = _invoice_line_initial_for_booking(booking)
        form = InvoiceForm(instance=invoice)
        formset = _invoice_line_formset_class(len(line_initial))(instance=invoice, prefix='lines', initial=line_initial)

    return render(request, 'invoices/invoice_form.html', {
        'form': form,
        'formset': formset,
        'booking': booking,
        'center': center,
        'centers': centers,
        'auto_line_count': len(_invoice_line_initial_for_booking(booking)) if booking else 0,
    })


@login_required
def invoice_detail(request, pk):
    invoice = _invoice_for_user_or_404(request, pk)
    if invoice is None:
        return redirect('services:dashboard')

    centers = _owned_centers(request.user)
    return render(request, 'invoices/invoice_detail.html', {
        'invoice': invoice,
        'centers': centers,
    })


@login_required
def invoice_finalize(request, pk):
    invoice = _invoice_for_user_or_404(request, pk)
    if invoice is None:
        return redirect('services:dashboard')

    if request.method == 'POST':
        if invoice.status == Invoice.STATUS_FINAL:
            messages.info(request, 'Factura este deja finalizată.')
            return redirect('invoices:detail', pk=invoice.pk)

        try:
            finalize_invoice(invoice, actor=request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
            return redirect('invoices:detail', pk=invoice.pk)
        messages.success(request, 'Factura a fost finalizată.')

    return redirect('invoices:detail', pk=invoice.pk)


@login_required
def invoice_pdf(request, pk):
    invoice = _invoice_for_user_or_404(request, pk)
    if invoice is None:
        return redirect('services:dashboard')

    pdf_bytes = build_invoice_pdf(invoice)
    filename = f'factura-{invoice.invoice_no or invoice.pk}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
def clients_list(request):
    centers = _require_owned_centers(request)
    if centers is None:
        return redirect('services:register_service')

    query = (request.GET.get('q') or '').strip()
    bookings = (
        Booking.objects
        .filter(center__in=centers)
        .exclude(status=Booking.STATUS_CANCELLED)
        .select_related('center')
        .order_by('-created_at')
    )
    if query:
        bookings = bookings.filter(booking_search_q(query))

    clients_data = build_clients_snapshot(bookings)
    for item in clients_data:
        last_booking = item['last_booking']
        item['count'] = item['booking_count']
        item['center'] = last_booking.center if last_booking else None
        dossier = build_vehicle_dossier(
            vin=next(iter(item.get('vin_values') or []), ''),
            plate=next(iter(item.get('plate_values') or []), ''),
        )
        item['dossier'] = dossier
        item['dossier_summary'] = dossier['summary']
        item['open_recommendations'] = dossier['open_recommendations'][:3]

    page_obj = Paginator(clients_data, 20).get_page(request.GET.get('page'))
    return render(request, 'invoices/clients_list.html', {
        'clients': page_obj.object_list,
        'page_obj': page_obj,
        'total_clients': len(clients_data),
        'total_bookings': bookings.count(),
        'search_query': query,
        'centers': centers,
    })


def booking_search_q(query):
    from django.db.models import Q

    return (
        Q(client_name__icontains=query)
        | Q(client_phone__icontains=query)
        | Q(client_email__icontains=query)
        | Q(car_plate__icontains=query)
        | Q(car_vin__icontains=query)
    )
