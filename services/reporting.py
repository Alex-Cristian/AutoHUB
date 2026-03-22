from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Count, F, Min, Q, Sum, Value, DecimalField
from django.db.models.functions import Coalesce, TruncDay, TruncMonth
from django.utils import timezone

from bookings.models import Booking
from invoices.models import Invoice, InvoiceLine
from services.models import ServicePart

REPORT_CHOICES = [
    ('revenue', 'Raport venituri'),
    ('appointments', 'Raport programări'),
    ('completed_jobs', 'Raport lucrări finalizate'),
    ('new_clients', 'Raport clienți noi'),
    ('parts_usage', 'Raport piese utilizate / consum stoc'),
    ('appointment_status', 'Raport status programări'),
    ('performance', 'Raport performanță generală service'),
]

PRESET_CHOICES = [
    ('today', 'Azi'),
    ('this_week', 'Săptămâna aceasta'),
    ('this_month', 'Luna aceasta'),
    ('this_year', 'Anul acesta'),
    ('custom', 'Interval personalizat'),
]

MONTH_CHOICES = [(i, label) for i, label in enumerate([
    '', 'Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
    'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie'
]) if i]

STATUS_LABELS = dict(Booking.STATUS_CHOICES)


@dataclass
class Period:
    start: date
    end: date
    label: str
    comparison_start: date
    comparison_end: date
    group_by: str


def build_period(cleaned_data: dict) -> Period:
    today = timezone.localdate()
    preset = cleaned_data.get('preset_period') or 'this_month'

    if preset == 'today':
        start = end = today
        label = 'Azi'
    elif preset == 'this_week':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        label = 'Săptămâna aceasta'
    elif preset == 'this_year':
        year = cleaned_data.get('year') or today.year
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        label = f'Anul {year}'
    elif preset == 'custom':
        if cleaned_data.get('specific_day'):
            start = end = cleaned_data['specific_day']
            label = start.strftime('%d.%m.%Y')
        elif cleaned_data.get('start_date') and cleaned_data.get('end_date'):
            start = cleaned_data['start_date']
            end = cleaned_data['end_date']
            label = f"{start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"
        elif cleaned_data.get('month') and cleaned_data.get('year'):
            year = cleaned_data['year']
            month = cleaned_data['month']
            start = date(year, month, 1)
            end = (date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1))
            label = f"{dict(MONTH_CHOICES)[month]} {year}"
        elif cleaned_data.get('year'):
            year = cleaned_data['year']
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            label = f'Anul {year}'
        else:
            start = today.replace(day=1)
            end = today
            label = 'Luna curentă'
    else:
        year = cleaned_data.get('year') or today.year
        month = cleaned_data.get('month') or today.month
        start = date(year, month, 1)
        end = (date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1))
        label = f"{dict(MONTH_CHOICES)[month]} {year}"

    days = max((end - start).days + 1, 1)
    comparison_end = start - timedelta(days=1)
    comparison_start = comparison_end - timedelta(days=days - 1)
    group_by = 'day' if days <= 31 else 'month'
    return Period(start, end, label, comparison_start, comparison_end, group_by)


def _currency(value) -> str:
    value = Decimal(str(value or 0))
    return f"{value:,.2f} RON".replace(',', 'X').replace('.', ',').replace('X', '.')


def _serialize_period(dt, group_by: str) -> str:
    if not dt:
        return ''
    if isinstance(dt, datetime):
        dt = dt.date()
    return dt.strftime('%d %b') if group_by == 'day' else dt.strftime('%b %Y')


def _comparison_payload(current, previous):
    current = Decimal(str(current or 0))
    previous = Decimal(str(previous or 0))
    if previous == 0:
        delta = Decimal('100.0') if current > 0 else Decimal('0.0')
    else:
        delta = ((current - previous) / previous) * Decimal('100.0')
    return ('+' if delta >= 0 else '') + f'{delta:.1f}%'


def _booking_queryset(centers, period: Period):
    return Booking.objects.filter(center__in=centers, booking_date__range=(period.start, period.end)).select_related(
        'center', 'service_item', 'garage', 'mechanic'
    )


def _invoice_queryset(centers, period: Period):
    return Invoice.objects.filter(center__in=centers, issue_date__range=(period.start, period.end)).select_related(
        'center', 'booking'
    )


def build_dashboard_metrics(centers):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    bookings = Booking.objects.filter(center__in=centers)
    invoices = Invoice.objects.filter(center__in=centers)
    parts = ServicePart.objects.filter(center__in=centers)

    kpis = {
        'appointments_today': bookings.filter(booking_date=today).count(),
        'appointments_pending': bookings.filter(status=Booking.STATUS_PENDING).count(),
        'cars_in_work': bookings.filter(status=Booking.STATUS_IN_PROGRESS).count(),
        'completed_this_month': bookings.filter(status=Booking.STATUS_DONE, booking_date__range=(month_start, today)).count(),
        'revenue_this_month': invoices.filter(status=Invoice.STATUS_FINAL, issue_date__range=(month_start, today)).aggregate(
            total=Coalesce(Sum('total'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2))
        )['total'],
        'low_stock_count': parts.filter(stock__lte=F('minimum_stock')).count(),
    }

    today_bookings = list(
        bookings.filter(booking_date=today)
        .select_related('service_item', 'garage', 'mechanic', 'center')
        .order_by('booking_time', 'created_at')[:8]
    )

    attention = []
    for booking in bookings.filter(status=Booking.STATUS_PENDING).order_by('-created_at')[:3]:
        attention.append({
            'title': 'Programare nouă neconfirmată',
            'description': f'{booking.client_name} · {booking.car_brand} {booking.car_model}',
            'meta': booking.booking_date.strftime('%d.%m.%Y'),
            'badge': 'warning text-dark',
            'icon': 'bi-hourglass-split',
            'url': f'/services/dashboard/programari/{booking.pk}/',
        })
    overdue_qs = bookings.filter(
        booking_date__lte=today,
        status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_IN_PROGRESS],
    ).order_by('booking_date', 'booking_time')
    for booking in overdue_qs[:3]:
        attention.append({
            'title': 'Lucrare întârziată sau nerezolvată',
            'description': f'{booking.client_name} · {booking.car_brand} {booking.car_model}',
            'meta': booking.booking_date.strftime('%d.%m.%Y'),
            'badge': 'danger',
            'icon': 'bi-exclamation-triangle',
            'url': f'/services/dashboard/programari/{booking.pk}/',
        })
    for part in parts.filter(stock__lte=F('minimum_stock')).order_by('stock', 'name')[:3]:
        attention.append({
            'title': 'Stoc critic piese',
            'description': f'{part.name} · {part.stock} {part.unit} disponibile',
            'meta': part.center.name,
            'badge': 'warning text-dark' if part.stock > 0 else 'danger',
            'icon': 'bi-box-seam',
            'url': '/services/dashboard/piese/',
        })
    uninvoiced_done = bookings.filter(status=Booking.STATUS_DONE, invoices__isnull=True).order_by('-booking_date')[:3]
    for booking in uninvoiced_done:
        attention.append({
            'title': 'Lucrare finalizată fără factură',
            'description': f'{booking.client_name} · {booking.car_brand} {booking.car_model}',
            'meta': booking.booking_date.strftime('%d.%m.%Y'),
            'badge': 'info text-dark',
            'icon': 'bi-receipt',
            'url': f'/invoices/creare/?booking={booking.pk}',
        })

    quick_actions = [
        {'title': 'Adaugă programare', 'icon': 'bi-calendar-plus', 'url': f'/services/dashboard/service/{centers.first().pk}/programare-noua/' if centers else '#'},
        {'title': 'Vezi toate programările', 'icon': 'bi-calendar3', 'url': '/services/dashboard/programari/'},
        {'title': 'Adaugă lucrare', 'icon': 'bi-tools', 'url': '/services/dashboard/programari/'},
        {'title': 'Vezi clienți', 'icon': 'bi-people', 'url': '/invoices/clienti/'},
        {'title': 'Vezi mașini', 'icon': 'bi-car-front', 'url': '/services/dashboard/istoric-masini/'},
        {'title': 'Vezi stoc', 'icon': 'bi-box-seam', 'url': '/services/dashboard/piese/'},
        {'title': 'Generează raport', 'icon': 'bi-bar-chart', 'url': '/services/dashboard/rapoarte/'},
        {'title': 'Emite factură', 'icon': 'bi-receipt-cutoff', 'url': '/invoices/creare/'},
    ]

    categories = [
        {'title': 'Programări', 'description': 'Calendar, listă completă și management statusuri.', 'icon': 'bi-calendar-check', 'url': '/services/dashboard/programari/', 'count': bookings.exclude(status=Booking.STATUS_CANCELLED).count()},
        {'title': 'Clienți', 'description': 'Acces rapid la istoricul clienților și contact.', 'icon': 'bi-people', 'url': '/invoices/clienti/', 'count': bookings.values('client_email').exclude(client_email='').distinct().count()},
        {'title': 'Mașini', 'description': 'Istoric mașini și intervenții efectuate.', 'icon': 'bi-car-front', 'url': '/services/dashboard/istoric-masini/', 'count': bookings.values('car_plate').distinct().count()},
        {'title': 'Lucrări / Reparații', 'description': 'Urmărește lucrările în curs și finalizate.', 'icon': 'bi-tools', 'url': '/services/dashboard/programari/?status=in_progress', 'count': bookings.filter(status__in=[Booking.STATUS_IN_PROGRESS, Booking.STATUS_DONE]).count()},
        {'title': 'Piese / Stoc', 'description': 'Situația stocului și alertele critice.', 'icon': 'bi-box-seam', 'url': '/services/dashboard/piese/', 'count': parts.count()},
        {'title': 'Facturi / Documente', 'description': 'Facturi draft, finalizate și emitere rapidă.', 'icon': 'bi-receipt', 'url': '/invoices/creare/', 'count': invoices.count()},
        {'title': 'Rapoarte', 'description': 'Indicatori financiari și operaționali pentru service.', 'icon': 'bi-graph-up-arrow', 'url': '/services/dashboard/rapoarte/', 'count': None},
        {'title': 'Setări service', 'description': 'Date service, profil, galerii și configurări.', 'icon': 'bi-gear', 'url': f'/services/dashboard/service/{centers.first().pk}/' if centers else '#', 'count': centers.count()},
    ]

    return {
        'kpis': kpis,
        'today_bookings': today_bookings,
        'attention_items': attention[:6],
        'quick_actions': quick_actions,
        'categories': categories,
    }


def _revenue_report(centers, period: Period):
    invoices = _invoice_queryset(centers, period).filter(status=Invoice.STATUS_FINAL)
    previous_invoices = Invoice.objects.filter(center__in=centers, status=Invoice.STATUS_FINAL, issue_date__range=(period.comparison_start, period.comparison_end))
    total = invoices.aggregate(total=Coalesce(Sum('total'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2)))['total']
    count = invoices.count()
    average = (total / count) if count else Decimal('0.00')
    grouped = invoices.annotate(period_value=TruncDay('issue_date') if period.group_by == 'day' else TruncMonth('issue_date')).values('period_value').annotate(total=Sum('total')).order_by('period_value')
    detail_rows = [
        {'col1': inv.issue_date.strftime('%d.%m.%Y'), 'col2': inv.client_name, 'col3': inv.center.name, 'col4': _currency(inv.total)}
        for inv in invoices.order_by('-issue_date', '-created_at')[:50]
    ]
    return {
        'title': 'Raport venituri',
        'summary': [
            {'label': 'Venit total', 'value': _currency(total), 'icon': 'bi-cash-stack'},
            {'label': 'Facturi finalizate', 'value': count, 'icon': 'bi-receipt'},
            {'label': 'Valoare medie / factură', 'value': _currency(average), 'icon': 'bi-calculator'},
            {'label': 'Vs. perioada anterioară', 'value': _comparison_payload(total, previous_invoices.aggregate(total=Coalesce(Sum('total'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2)))['total']), 'icon': 'bi-arrow-left-right'},
        ],
        'chart': {
            'type': 'bar',
            'labels': [_serialize_period(item['period_value'], period.group_by) for item in grouped],
            'values': [float(item['total'] or 0) for item in grouped],
            'label': 'Venit (RON)',
        },
        'table_headers': ['Data', 'Client', 'Service', 'Total'],
        'table_rows': detail_rows,
        'export_headers': ['Data', 'Client', 'Service', 'Total'],
        'export_rows': [[row['col1'], row['col2'], row['col3'], row['col4']] for row in detail_rows],
    }


def _appointments_report(centers, period: Period):
    bookings = _booking_queryset(centers, period)
    total = bookings.count()
    confirmed = bookings.filter(status=Booking.STATUS_CONFIRMED).count()
    done = bookings.filter(status=Booking.STATUS_DONE).count()
    cancelled = bookings.filter(status=Booking.STATUS_CANCELLED).count()
    pending = bookings.filter(status=Booking.STATUS_PENDING).count()
    completion_rate = (done / total * 100) if total else 0
    grouped = bookings.annotate(period_value=TruncDay('booking_date') if period.group_by == 'day' else TruncMonth('booking_date')).values('period_value').annotate(total=Count('id')).order_by('period_value')
    busiest = bookings.values('booking_date').annotate(total=Count('id')).order_by('-total', 'booking_date')[:5]
    rows = [
        {'col1': b.booking_date.strftime('%d.%m.%Y'), 'col2': b.client_name, 'col3': f'{b.car_brand} {b.car_model}', 'col4': STATUS_LABELS.get(b.status, b.status)}
        for b in bookings.order_by('-booking_date', '-booking_time')[:50]
    ]
    return {
        'title': 'Raport programări',
        'summary': [
            {'label': 'Programări totale', 'value': total, 'icon': 'bi-calendar-check'},
            {'label': 'Confirmate', 'value': confirmed, 'icon': 'bi-patch-check'},
            {'label': 'Finalizate', 'value': done, 'icon': 'bi-flag'},
            {'label': 'Rată finalizare', 'value': f'{completion_rate:.1f}%', 'icon': 'bi-speedometer2'},
        ],
        'chart': {
            'type': 'line',
            'labels': [_serialize_period(item['period_value'], period.group_by) for item in grouped],
            'values': [item['total'] for item in grouped],
            'label': 'Programări',
        },
        'highlights': [f"{item['booking_date'].strftime('%d.%m.%Y')}: {item['total']} programări" for item in busiest],
        'table_headers': ['Data', 'Client', 'Mașină', 'Status'],
        'table_rows': rows,
        'export_headers': ['Data', 'Client', 'Mașină', 'Status'],
        'export_rows': [[row['col1'], row['col2'], row['col3'], row['col4']] for row in rows],
    }


def _completed_jobs_report(centers, period: Period):
    bookings = _booking_queryset(centers, period).filter(status=Booking.STATUS_DONE)
    total = bookings.count()
    total_value = bookings.aggregate(total=Coalesce(Sum('estimated_price'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2)))['total']
    avg_per_day = total / max((period.end - period.start).days + 1, 1)
    top_services = list(bookings.exclude(service_item__isnull=True).values_list('service_item__name').annotate(total=Count('id')).order_by('-total')[:5])
    top_clients = list(bookings.values('client_name').annotate(total=Count('id')).order_by('-total', 'client_name')[:5])
    rows = [
        {'col1': b.booking_date.strftime('%d.%m.%Y'), 'col2': b.client_name, 'col3': b.service_item.name if b.service_item else 'Lucrare generală', 'col4': _currency(b.estimated_price)}
        for b in bookings.order_by('-booking_date', '-booking_time')[:50]
    ]
    grouped = bookings.annotate(period_value=TruncDay('booking_date') if period.group_by == 'day' else TruncMonth('booking_date')).values('period_value').annotate(total=Count('id')).order_by('period_value')
    return {
        'title': 'Raport lucrări finalizate',
        'summary': [
            {'label': 'Lucrări finalizate', 'value': total, 'icon': 'bi-tools'},
            {'label': 'Valoare totală', 'value': _currency(total_value), 'icon': 'bi-currency-exchange'},
            {'label': 'Medie / zi', 'value': f'{avg_per_day:.1f}', 'icon': 'bi-calendar3'},
            {'label': 'Top clienți', 'value': top_clients[0]['client_name'] if top_clients else '—', 'icon': 'bi-person-star'},
        ],
        'chart': {'type': 'bar', 'labels': [_serialize_period(i['period_value'], period.group_by) for i in grouped], 'values': [i['total'] for i in grouped], 'label': 'Lucrări finalizate'},
        'highlights': [f"{name}: {count}" for name, count in top_services] + [f"{item['client_name']}: {item['total']} lucrări" for item in top_clients[:3]],
        'table_headers': ['Data', 'Client', 'Tip lucrare', 'Valoare'],
        'table_rows': rows,
        'export_headers': ['Data', 'Client', 'Tip lucrare', 'Valoare'],
        'export_rows': [[r['col1'], r['col2'], r['col3'], r['col4']] for r in rows],
    }


def _new_clients_report(centers, period: Period):
    base = Booking.objects.filter(center__in=centers).exclude(client_email='')
    first_seen = base.values('client_email').annotate(first_date=Min('booking_date'), client_name=Min('client_name')).filter(first_date__range=(period.start, period.end)).order_by('-first_date')
    new_count = first_seen.count()
    total_clients = base.values('client_email').distinct().count()
    existing_share = ((total_clients - new_count) / total_clients * 100) if total_clients else 0
    day_counts = {}
    for item in first_seen:
        key = item['first_date']
        day_counts[key] = day_counts.get(key, 0) + 1
    rows = [
        {'col1': item['first_date'].strftime('%d.%m.%Y'), 'col2': item['client_name'], 'col3': item['client_email'], 'col4': 'Client nou'}
        for item in list(first_seen[:50])
    ]
    return {
        'title': 'Raport clienți noi',
        'summary': [
            {'label': 'Clienți noi', 'value': new_count, 'icon': 'bi-person-plus'},
            {'label': 'Clienți existenți', 'value': max(total_clients - new_count, 0), 'icon': 'bi-people'},
            {'label': 'Pondere existenți', 'value': f'{existing_share:.1f}%', 'icon': 'bi-pie-chart'},
            {'label': 'Ultima înscriere', 'value': rows[0]['col1'] if rows else '—', 'icon': 'bi-clock-history'},
        ],
        'chart': {'type': 'line', 'labels': [_serialize_period(k, 'day') for k in sorted(day_counts.keys())], 'values': [day_counts[k] for k in sorted(day_counts.keys())], 'label': 'Clienți noi'},
        'table_headers': ['Prima apariție', 'Client', 'Email', 'Tip'],
        'table_rows': rows,
        'export_headers': ['Prima apariție', 'Client', 'Email', 'Tip'],
        'export_rows': [[r['col1'], r['col2'], r['col3'], r['col4']] for r in rows],
    }


def _parts_usage_report(centers, period: Period):
    parts = ServicePart.objects.filter(center__in=centers)
    low_stock = parts.filter(stock__lte=F('minimum_stock')).order_by('stock', 'name')
    lines = InvoiceLine.objects.filter(invoice__center__in=centers, invoice__issue_date__range=(period.start, period.end), invoice__status=Invoice.STATUS_FINAL)
    matched_usage = []
    total_qty = Decimal('0.00')
    total_value = Decimal('0.00')
    for part in parts:
        q = lines.filter(Q(description__icontains=part.name) | Q(description__icontains=part.part_number)) if part.part_number else lines.filter(description__icontains=part.name)
        qty = q.aggregate(total=Coalesce(Sum('quantity'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2)))['total']
        if qty and qty > 0:
            value = q.aggregate(total=Coalesce(Sum('line_total'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2)))['total']
            matched_usage.append({'part': part, 'qty': qty, 'value': value})
            total_qty += qty
            total_value += value
    matched_usage.sort(key=lambda item: item['qty'], reverse=True)
    rows = [
        {'col1': item['part'].name, 'col2': f"{item['qty']} {item['part'].unit}", 'col3': item['part'].stock, 'col4': _currency(item['value'])}
        for item in matched_usage[:50]
    ] or [
        {'col1': part.name, 'col2': '0', 'col3': part.stock, 'col4': _currency((part.price or 0) * max(part.minimum_stock - part.stock, 0))}
        for part in low_stock[:20]
    ]
    return {
        'title': 'Raport piese utilizate / consum stoc',
        'summary': [
            {'label': 'Total piese identificate', 'value': f'{total_qty}', 'icon': 'bi-box2'},
            {'label': 'Valoare estimată consum', 'value': _currency(total_value), 'icon': 'bi-cash-coin'},
            {'label': 'Stoc critic', 'value': low_stock.count(), 'icon': 'bi-exclamation-diamond'},
            {'label': 'Piesa cea mai folosită', 'value': matched_usage[0]['part'].name if matched_usage else '—', 'icon': 'bi-trophy'},
        ],
        'chart': {'type': 'bar', 'labels': [item['part'].name for item in matched_usage[:8]], 'values': [float(item['qty']) for item in matched_usage[:8]], 'label': 'Cantitate utilizată'},
        'table_headers': ['Piesă', 'Cantitate', 'Stoc curent', 'Valoare estimată'],
        'table_rows': rows,
        'export_headers': ['Piesă', 'Cantitate', 'Stoc curent', 'Valoare estimată'],
        'export_rows': [[r['col1'], r['col2'], r['col3'], r['col4']] for r in rows],
    }


def _appointment_status_report(centers, period: Period):
    bookings = _booking_queryset(centers, period)
    total = bookings.count()
    rows = []
    labels = []
    values = []
    for code, label in Booking.STATUS_CHOICES:
        count = bookings.filter(status=code).count()
        percent = (count / total * 100) if total else 0
        rows.append({'col1': label, 'col2': count, 'col3': f'{percent:.1f}%', 'col4': '—'})
        labels.append(label)
        values.append(count)
    return {
        'title': 'Raport status programări',
        'summary': [
            {'label': 'Programări totale', 'value': total, 'icon': 'bi-calendar-range'},
            {'label': 'În așteptare', 'value': bookings.filter(status=Booking.STATUS_PENDING).count(), 'icon': 'bi-hourglass'},
            {'label': 'În lucru', 'value': bookings.filter(status=Booking.STATUS_IN_PROGRESS).count(), 'icon': 'bi-tools'},
            {'label': 'Anulate', 'value': bookings.filter(status=Booking.STATUS_CANCELLED).count(), 'icon': 'bi-x-circle'},
        ],
        'chart': {'type': 'doughnut', 'labels': labels, 'values': values, 'label': 'Distribuție statusuri'},
        'table_headers': ['Status', 'Număr', 'Procent', 'Observații'],
        'table_rows': rows,
        'export_headers': ['Status', 'Număr', 'Procent', 'Observații'],
        'export_rows': [[r['col1'], r['col2'], r['col3'], r['col4']] for r in rows],
    }


def _performance_report(centers, period: Period):
    bookings = _booking_queryset(centers, period)
    invoices = _invoice_queryset(centers, period).filter(status=Invoice.STATUS_FINAL)
    new_clients = Booking.objects.filter(center__in=centers).exclude(client_email='').values('client_email').annotate(first_date=Min('booking_date')).filter(first_date__range=(period.start, period.end)).count()
    total = bookings.count()
    cancelled = bookings.filter(status=Booking.STATUS_CANCELLED).count()
    done = bookings.filter(status=Booking.STATUS_DONE).count()
    revenue = invoices.aggregate(total=Coalesce(Sum('total'), Value(Decimal('0.00')), output_field=DecimalField(max_digits=12, decimal_places=2)))['total']
    low_stock = ServicePart.objects.filter(center__in=centers, stock__lte=F('minimum_stock')).count()
    cancel_rate = (cancelled / total * 100) if total else 0
    done_rate = (done / total * 100) if total else 0
    rows = [
        {'col1': 'Venit total', 'col2': _currency(revenue), 'col3': 'Perioada selectată', 'col4': ''},
        {'col1': 'Programări totale', 'col2': total, 'col3': 'Bază operațională', 'col4': ''},
        {'col1': 'Lucrări finalizate', 'col2': done, 'col3': 'Rată finalizare', 'col4': f'{done_rate:.1f}%'},
        {'col1': 'Clienți noi', 'col2': new_clients, 'col3': 'Pondere creștere', 'col4': ''},
        {'col1': 'Stoc critic', 'col2': low_stock, 'col3': 'Necesită atenție', 'col4': ''},
        {'col1': 'Rată anulare', 'col2': f'{cancel_rate:.1f}%', 'col3': 'Programări anulate', 'col4': cancelled},
    ]
    return {
        'title': 'Raport performanță generală service',
        'summary': [
            {'label': 'Venit total', 'value': _currency(revenue), 'icon': 'bi-graph-up-arrow'},
            {'label': 'Programări totale', 'value': total, 'icon': 'bi-calendar-check'},
            {'label': 'Lucrări finalizate', 'value': done, 'icon': 'bi-tools'},
            {'label': 'Clienți noi', 'value': new_clients, 'icon': 'bi-person-plus'},
        ],
        'chart': {'type': 'bar', 'labels': ['Venit', 'Programări', 'Finalizate', 'Clienți noi', 'Stoc critic'], 'values': [float(revenue), total, done, new_clients, low_stock], 'label': 'Indicatori cheie'},
        'table_headers': ['Indicator', 'Valoare', 'Context', 'Extra'],
        'table_rows': rows,
        'export_headers': ['Indicator', 'Valoare', 'Context', 'Extra'],
        'export_rows': [[r['col1'], r['col2'], r['col3'], r['col4']] for r in rows],
    }


def build_report(centers, cleaned_data: dict):
    period = build_period(cleaned_data)
    report_type = cleaned_data.get('report_type') or 'performance'
    builders = {
        'revenue': _revenue_report,
        'appointments': _appointments_report,
        'completed_jobs': _completed_jobs_report,
        'new_clients': _new_clients_report,
        'parts_usage': _parts_usage_report,
        'appointment_status': _appointment_status_report,
        'performance': _performance_report,
    }
    payload = builders.get(report_type, _performance_report)(centers, period)
    payload['period'] = period
    payload['report_type'] = report_type
    payload['report_label'] = dict(REPORT_CHOICES).get(report_type, 'Raport')
    return payload


def export_report_csv(response, report_payload):
    writer = csv.writer(response)
    writer.writerow([report_payload['title']])
    writer.writerow(['Perioadă', report_payload['period'].label])
    writer.writerow([])
    writer.writerow(report_payload['export_headers'])
    for row in report_payload['export_rows']:
        writer.writerow(row)
    return response
