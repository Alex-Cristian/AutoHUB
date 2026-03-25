from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from bookings.activity import log_booking_activity
from bookings.models import Booking
from invoices.models import Invoice
from services.models import JobCard, JobPartUsage, StockMovement


BOOKING_STATUS_LABELS = dict(Booking.STATUS_CHOICES)
JOB_CARD_STATUS_LABELS = dict(JobCard.STATUS_CHOICES)
INVOICE_STATUS_LABELS = dict(Invoice.STATUS_CHOICES)

BOOKING_STATUS_TRANSITIONS = {
    Booking.STATUS_PENDING: {
        Booking.STATUS_QUOTED,
        Booking.STATUS_CONFIRMED,
        Booking.STATUS_IN_PROGRESS,
        Booking.STATUS_WAITING_PARTS,
        Booking.STATUS_DONE,
        Booking.STATUS_CANCELLED,
    },
    Booking.STATUS_QUOTED: {
        Booking.STATUS_PENDING,
        Booking.STATUS_CONFIRMED,
        Booking.STATUS_IN_PROGRESS,
        Booking.STATUS_WAITING_PARTS,
        Booking.STATUS_DONE,
        Booking.STATUS_CANCELLED,
    },
    Booking.STATUS_CONFIRMED: {
        Booking.STATUS_IN_PROGRESS,
        Booking.STATUS_WAITING_PARTS,
        Booking.STATUS_DONE,
        Booking.STATUS_CANCELLED,
    },
    Booking.STATUS_IN_PROGRESS: {
        Booking.STATUS_CONFIRMED,
        Booking.STATUS_WAITING_PARTS,
        Booking.STATUS_DONE,
        Booking.STATUS_CANCELLED,
    },
    Booking.STATUS_WAITING_PARTS: {
        Booking.STATUS_CONFIRMED,
        Booking.STATUS_IN_PROGRESS,
        Booking.STATUS_DONE,
        Booking.STATUS_CANCELLED,
    },
    Booking.STATUS_DONE: set(),
    Booking.STATUS_CANCELLED: set(),
}

JOB_CARD_STATUS_TRANSITIONS = {
    JobCard.STATUS_CREATED: {
        JobCard.STATUS_APPROVED,
        JobCard.STATUS_IN_PROGRESS,
        JobCard.STATUS_WAITING_PARTS,
        JobCard.STATUS_WAITING_CUSTOMER,
        JobCard.STATUS_COMPLETED,
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_APPROVED: {
        JobCard.STATUS_IN_PROGRESS,
        JobCard.STATUS_WAITING_PARTS,
        JobCard.STATUS_WAITING_CUSTOMER,
        JobCard.STATUS_COMPLETED,
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_IN_PROGRESS: {
        JobCard.STATUS_WAITING_PARTS,
        JobCard.STATUS_COMPLETED,
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_WAITING_PARTS: {
        JobCard.STATUS_APPROVED,
        JobCard.STATUS_IN_PROGRESS,
        JobCard.STATUS_COMPLETED,
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_WAITING_CUSTOMER: {
        JobCard.STATUS_APPROVED,
        JobCard.STATUS_WAITING_PARTS,
        JobCard.STATUS_COMPLETED,
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_COMPLETED: {
        JobCard.STATUS_INVOICED,
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_INVOICED: {
        JobCard.STATUS_CLOSED,
    },
    JobCard.STATUS_CLOSED: set(),
}

INVOICE_STATUS_TRANSITIONS = {
    Invoice.STATUS_DRAFT: {
        Invoice.STATUS_FINAL,
        Invoice.STATUS_CANCELLED,
    },
    Invoice.STATUS_FINAL: {
        Invoice.STATUS_PAID,
        Invoice.STATUS_CANCELLED,
    },
    Invoice.STATUS_PAID: set(),
    Invoice.STATUS_CANCELLED: set(),
}

BOOKING_TO_JOB_STATUS = {
    Booking.STATUS_PENDING: JobCard.STATUS_CREATED,
    Booking.STATUS_QUOTED: JobCard.STATUS_WAITING_CUSTOMER,
    Booking.STATUS_CONFIRMED: JobCard.STATUS_APPROVED,
    Booking.STATUS_IN_PROGRESS: JobCard.STATUS_IN_PROGRESS,
    Booking.STATUS_WAITING_PARTS: JobCard.STATUS_WAITING_PARTS,
    Booking.STATUS_DONE: JobCard.STATUS_COMPLETED,
    Booking.STATUS_CANCELLED: JobCard.STATUS_CLOSED,
}

JOB_TO_BOOKING_STATUS = {
    JobCard.STATUS_APPROVED: Booking.STATUS_CONFIRMED,
    JobCard.STATUS_IN_PROGRESS: Booking.STATUS_IN_PROGRESS,
    JobCard.STATUS_WAITING_PARTS: Booking.STATUS_WAITING_PARTS,
    JobCard.STATUS_WAITING_CUSTOMER: Booking.STATUS_QUOTED,
    JobCard.STATUS_COMPLETED: Booking.STATUS_DONE,
    JobCard.STATUS_INVOICED: Booking.STATUS_DONE,
    JobCard.STATUS_CLOSED: Booking.STATUS_DONE,
}

INVOICE_TO_JOB_STATUS = {
    Invoice.STATUS_FINAL: JobCard.STATUS_INVOICED,
    Invoice.STATUS_PAID: JobCard.STATUS_INVOICED,
    Invoice.STATUS_CANCELLED: JobCard.STATUS_COMPLETED,
}

TERMINAL_JOB_CARD_STATUSES = {
    JobCard.STATUS_COMPLETED,
    JobCard.STATUS_INVOICED,
    JobCard.STATUS_CLOSED,
}


def _validate_status_transition(current_status, new_status, transitions, labels, entity_label):
    if new_status == current_status:
        return
    if new_status not in labels:
        raise ValidationError(f'Statusul selectat pentru {entity_label} nu este valid.')
    allowed = transitions.get(current_status, set())
    if new_status not in allowed:
        current_label = labels.get(current_status, current_status)
        new_label = labels.get(new_status, new_status)
        raise ValidationError(
            f'Nu poti schimba {entity_label} din "{current_label}" in "{new_label}".'
        )


def validate_booking_status_transition(current_status, new_status):
    _validate_status_transition(
        current_status,
        new_status,
        BOOKING_STATUS_TRANSITIONS,
        BOOKING_STATUS_LABELS,
        'programare',
    )


def validate_job_card_status_transition(current_status, new_status):
    _validate_status_transition(
        current_status,
        new_status,
        JOB_CARD_STATUS_TRANSITIONS,
        JOB_CARD_STATUS_LABELS,
        'fisa lucrarii',
    )


def validate_invoice_status_transition(current_status, new_status):
    _validate_status_transition(
        current_status,
        new_status,
        INVOICE_STATUS_TRANSITIONS,
        INVOICE_STATUS_LABELS,
        'factura',
    )


def validate_job_card_status_for_booking(booking, job_card_status):
    target_booking_status = JOB_TO_BOOKING_STATUS.get(job_card_status)
    if target_booking_status:
        validate_booking_status_transition(booking.status, target_booking_status)


def normalize_booking_operational_tags(booking, *, target_status=None):
    status = target_status or booking.status
    allowed_tags = {choice[0] for choice in Booking.TAG_CHOICES}
    tags = [tag for tag in (booking.operational_tags or []) if tag in allowed_tags]
    waiting_tag_present = Booking.TAG_WAITING_PART in tags
    if status == Booking.STATUS_WAITING_PARTS and not waiting_tag_present:
        tags.append(Booking.TAG_WAITING_PART)
    if status != Booking.STATUS_WAITING_PARTS and waiting_tag_present:
        tags = [tag for tag in tags if tag != Booking.TAG_WAITING_PART]
    return tags


def booking_has_tag(booking, tag):
    return tag in (booking.operational_tags or [])


def bookings_with_tag(queryset, tag):
    return [booking for booking in queryset if booking_has_tag(booking, tag)]


def ensure_job_card(booking, actor=None):
    defaults = {
        'center': booking.center,
        'mechanic': booking.mechanic,
        'estimated_cost': booking.estimated_price,
        'created_by': actor if getattr(actor, 'is_authenticated', False) else None,
        'updated_by': actor if getattr(actor, 'is_authenticated', False) else None,
    }
    job_card, created = JobCard.objects.get_or_create(booking=booking, defaults=defaults)
    changed_fields = []
    if job_card.center_id != booking.center_id:
        job_card.center = booking.center
        changed_fields.append('center')
    if booking.mechanic_id and job_card.mechanic_id != booking.mechanic_id:
        job_card.mechanic = booking.mechanic
        changed_fields.append('mechanic')
    if booking.estimated_price is not None and job_card.estimated_cost is None:
        job_card.estimated_cost = booking.estimated_price
        changed_fields.append('estimated_cost')
    if actor and actor.is_authenticated:
        job_card.updated_by = actor
        changed_fields.append('updated_by')
    if changed_fields:
        job_card.save(update_fields=[*changed_fields, 'updated_at'])
    return job_card, created


def transition_booking_status(
    booking,
    new_status,
    *,
    actor=None,
    sync_job_card=False,
    create_job_card=False,
):
    validate_booking_status_transition(booking.status, new_status)
    old_status = booking.status
    changed_fields = []

    if old_status != new_status:
        booking.status = new_status
        changed_fields.append('status')

    normalized_tags = normalize_booking_operational_tags(booking, target_status=new_status)
    if normalized_tags != (booking.operational_tags or []):
        booking.operational_tags = normalized_tags
        changed_fields.append('operational_tags')

    if changed_fields:
        booking.save(update_fields=[*changed_fields, 'updated_at'])

    job_card = None
    if sync_job_card:
        job_card = sync_job_card_from_booking(
            booking,
            actor=actor,
            create_missing=create_job_card,
        )

    return old_status, bool(changed_fields), job_card


def transition_job_card_status(job_card, new_status, *, actor=None, sync_booking=False):
    validate_job_card_status_transition(job_card.status, new_status)
    old_status = job_card.status
    changed_fields = []

    if old_status != new_status:
        job_card.status = new_status
        changed_fields.append('status')

    if actor and getattr(actor, 'is_authenticated', False) and job_card.updated_by_id != actor.id:
        job_card.updated_by = actor
        changed_fields.append('updated_by')

    if changed_fields:
        job_card.save(update_fields=[*changed_fields, 'updated_at'])

    if sync_booking:
        sync_booking_from_job_card(job_card, actor=actor)

    return old_status, bool(changed_fields)


def sync_job_card_from_booking(booking, actor=None, create_missing=False):
    try:
        job_card = booking.job_card
    except JobCard.DoesNotExist:
        if not create_missing:
            return None
        job_card, _ = ensure_job_card(booking, actor=actor)

    changed_fields = []
    target_status = BOOKING_TO_JOB_STATUS.get(booking.status)
    if (
        target_status
        and job_card.status != target_status
        and not (
            job_card.status in TERMINAL_JOB_CARD_STATUSES
            and target_status not in TERMINAL_JOB_CARD_STATUSES
        )
    ):
        validate_job_card_status_transition(job_card.status, target_status)
        job_card.status = target_status
        changed_fields.append('status')

    if booking.mechanic_id != job_card.mechanic_id:
        job_card.mechanic = booking.mechanic
        changed_fields.append('mechanic')

    if booking.estimated_price is not None and job_card.estimated_cost is None:
        job_card.estimated_cost = booking.estimated_price
        changed_fields.append('estimated_cost')

    if actor and getattr(actor, 'is_authenticated', False) and job_card.updated_by_id != actor.id:
        job_card.updated_by = actor
        changed_fields.append('updated_by')

    if changed_fields:
        job_card.save(update_fields=[*changed_fields, 'updated_at'])
    return job_card


def sync_booking_from_job_card(job_card, actor=None):
    booking = job_card.booking
    target_status = JOB_TO_BOOKING_STATUS.get(job_card.status)
    if not target_status:
        return booking

    old_status, changed, _ = transition_booking_status(booking, target_status, actor=actor)
    if changed and old_status != booking.status:
        log_booking_activity(
            booking,
            'status_changed',
            f'Status actualizat automat din fisa lucrarii in {booking.get_status_display()}.',
            actor=actor,
            metadata={'old': old_status, 'new': booking.status, 'source': 'job_card'},
        )
    return booking


@transaction.atomic
def apply_stock_movement(part, quantity_delta, movement_type, *, actor=None, job_card=None, booking=None, note=''):
    previous_stock = part.stock
    new_stock = previous_stock + quantity_delta
    if new_stock < 0:
        raise ValidationError(f'Stoc insuficient pentru {part.name}. Mai sunt disponibile doar {part.stock} {part.unit}.')
    part.stock = new_stock
    part.save(update_fields=['stock', 'updated_at'])
    return StockMovement.objects.create(
        part=part,
        job_card=job_card,
        booking=booking,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        previous_stock=previous_stock,
        new_stock=new_stock,
        note=note,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
    )


@transaction.atomic
def create_job_part_usage(
    job_card,
    *,
    part,
    quantity,
    status,
    actor=None,
    note='',
):
    quantity = int(quantity or 0)
    if quantity <= 0:
        raise ValidationError('Cantitatea trebuie sa fie mai mare decat zero.')

    if status not in {
        JobPartUsage.STATUS_RESERVED,
        JobPartUsage.STATUS_CONSUMED,
        JobPartUsage.STATUS_RETURNED,
    }:
        raise ValidationError('Statusul piesei din lucrare nu este valid.')

    if status == JobPartUsage.STATUS_RETURNED:
        quantity_delta = quantity
        movement_type = StockMovement.TYPE_RELEASE
    elif status == JobPartUsage.STATUS_RESERVED:
        quantity_delta = -quantity
        movement_type = StockMovement.TYPE_RESERVE
    else:
        quantity_delta = -quantity
        movement_type = StockMovement.TYPE_OUT

    apply_stock_movement(
        part,
        quantity_delta,
        movement_type,
        actor=actor,
        job_card=job_card,
        booking=job_card.booking,
        note=note or f'Miscare pentru fisa lucrarii #{job_card.booking_id}',
    )
    usage = JobPartUsage.objects.create(
        job_card=job_card,
        part=part,
        description=part.name,
        quantity=quantity,
        unit_label=part.unit,
        unit_cost=part.cost_price,
        unit_price=part.client_price,
        status=status,
        notes=note,
        created_by=actor if getattr(actor, 'is_authenticated', False) else None,
    )
    job_card.updated_by = actor if getattr(actor, 'is_authenticated', False) else job_card.updated_by
    job_card.save(update_fields=['updated_by', 'updated_at'])
    return usage


@transaction.atomic
def rollback_job_part_usage(usage, actor=None):
    part = usage.part
    if part:
        if usage.status == JobPartUsage.STATUS_RETURNED:
            quantity_delta = -usage.quantity
            movement_type = StockMovement.TYPE_RESERVE
        else:
            quantity_delta = usage.quantity
            movement_type = StockMovement.TYPE_RELEASE
        apply_stock_movement(
            part,
            quantity_delta,
            movement_type,
            actor=actor,
            job_card=usage.job_card,
            booking=usage.job_card.booking,
            note=f'Revenire pentru piesa din fisa #{usage.job_card.booking_id}',
        )
    usage.delete()


def build_invoice_line_drafts_for_booking(booking):
    drafts = []
    job_card = None
    try:
        job_card = booking.job_card
    except JobCard.DoesNotExist:
        job_card = None

    if job_card:
        for operation in job_card.operations.all():
            title = (operation.title or '').strip()
            details = (operation.description or '').strip()
            description = title or 'Operațiune service'
            if details:
                description = f'{description} - {details}'
            drafts.append({
                'description': description[:300],
                'quantity': Decimal('1.00'),
                'unit_price': operation.final_cost or operation.estimated_cost or Decimal('0.00'),
            })

        for usage in job_card.part_usages.exclude(status=JobPartUsage.STATUS_RETURNED):
            description = (usage.description or '').strip() or 'Piesă utilizată'
            if usage.notes:
                description = f'{description} - {usage.notes.strip()}'
            drafts.append({
                'description': description[:300],
                'quantity': Decimal(str(usage.quantity or 1)),
                'unit_price': usage.unit_price or Decimal('0.00'),
            })

    if drafts:
        return drafts

    if booking.used_services:
        compact_description = ' '.join((booking.used_services or '').split())
        if compact_description:
            drafts.append({
                'description': compact_description[:300],
                'quantity': Decimal('1.00'),
                'unit_price': (
                    getattr(job_card, 'final_cost', None)
                    or getattr(job_card, 'estimated_cost', None)
                    or booking.estimated_price
                    or Decimal('0.00')
                ),
            })
            return drafts

    if booking.service_item_id:
        drafts.append({
            'description': booking.service_item.name[:300],
            'quantity': Decimal('1.00'),
            'unit_price': booking.estimated_price or getattr(booking.service_item, 'price_from', None) or Decimal('0.00'),
        })

    return drafts


def build_work_order_services_text(booking):
    manual_lines = [line.strip() for line in (booking.used_services or '').splitlines() if line.strip()]
    if manual_lines:
        return '\n'.join(manual_lines)

    lines = []
    job_card = None
    try:
        job_card = booking.job_card
    except JobCard.DoesNotExist:
        job_card = None

    if job_card:
        for operation in job_card.operations.all():
            title = (operation.title or '').strip()
            details = (operation.description or '').strip()
            if title and details:
                lines.append(f'{title} - {details}'[:300])
            elif title:
                lines.append(title[:300])
            elif details:
                lines.append(details[:300])

        for usage in job_card.part_usages.exclude(status=JobPartUsage.STATUS_RETURNED):
            description = (usage.description or '').strip() or 'Piesa utilizata'
            quantity = usage.quantity or 1
            unit_label = (usage.unit_label or '').strip()
            quantity_label = f'{quantity} {unit_label}'.strip() if unit_label else f'x{quantity}'
            notes = (usage.notes or '').strip()
            line = f'{description} ({quantity_label})'
            if notes:
                line = f'{line} - {notes}'
            lines.append(line[:300])

    if lines:
        return '\n'.join(lines)

    fallback_lines = []
    if booking.service_item_id:
        service_name = (booking.service_item.name or '').strip()
        if service_name:
            fallback_lines.append(service_name[:300])

    compact_problem = ' '.join((booking.problem_description or '').split())
    if compact_problem:
        fallback_lines.append(f'Solicitare client: {compact_problem}'[:300])

    return '\n'.join(fallback_lines)


@transaction.atomic
def finalize_invoice(invoice, *, actor=None):
    validate_invoice_status_transition(invoice.status, Invoice.STATUS_FINAL)

    job_card = None
    if invoice.booking_id:
        booking = invoice.booking
        if booking.status != Booking.STATUS_DONE:
            raise ValidationError('Poti finaliza factura doar dupa ce programarea este marcata ca finalizata.')
        try:
            job_card = booking.job_card
        except JobCard.DoesNotExist:
            job_card = None
        if job_card and job_card.status not in {
            JobCard.STATUS_COMPLETED,
            JobCard.STATUS_INVOICED,
            JobCard.STATUS_CLOSED,
        }:
            raise ValidationError('Finalizeaza mai intai fisa lucrarii inainte sa emiti factura.')

    invoice.assign_next_number_if_needed()
    invoice.status = Invoice.STATUS_FINAL
    invoice.save(update_fields=['invoice_no', 'status', 'updated_at'])

    if job_card:
        target_job_status = INVOICE_TO_JOB_STATUS.get(invoice.status)
        if (
            target_job_status
            and job_card.status != target_job_status
            and job_card.status != JobCard.STATUS_CLOSED
        ):
            transition_job_card_status(
                job_card,
                target_job_status,
                actor=actor,
                sync_booking=True,
            )

    return invoice


def build_vehicle_dossier(*, vin='', plate=''):
    vin = (vin or '').strip().upper()
    plate = (plate or '').strip().upper()
    if not vin and not plate:
        return {
            'summary': {
                'interventions_count': 0,
                'total_cost': Decimal('0.00'),
                'last_visit': None,
                'next_service_date': None,
                'open_recommendations_count': 0,
                'operations_count': 0,
                'parts_count': 0,
            },
            'history': [],
            'recommendations': [],
            'open_recommendations': [],
        }
    filters = models_or(vin=vin, plate=plate)
    history = Booking.objects.filter(filters).exclude(status=Booking.STATUS_CANCELLED).select_related(
        'center', 'mechanic', 'service_item'
    ).prefetch_related(
        'job_card__operations',
        'job_card__part_usages__part',
        'job_card__recommendations',
        'attachments',
        'invoices',
    ).order_by('-booking_date', '-booking_time', '-created_at')

    history_list = list(history)
    completed = [booking for booking in history_list if booking.status == Booking.STATUS_DONE]
    total_cost = Decimal('0.00')
    last_visit = completed[0] if completed else (history_list[0] if history_list else None)
    next_dates = []
    recommendations = []
    operations_count = 0
    parts_count = 0

    for booking in history_list:
        job_card = getattr(booking, 'job_card', None)
        if job_card:
            total_cost += job_card.final_cost or job_card.estimated_cost or Decimal('0.00')
            operations_count += len(job_card.operations.all())
            parts_count += len(
                [usage for usage in job_card.part_usages.all() if usage.status != JobPartUsage.STATUS_RETURNED]
            )
            if job_card.next_service_date:
                next_dates.append(job_card.next_service_date)
            recommendations.extend(job_card.recommendations.all())
        else:
            total_cost += booking.estimated_price or Decimal('0.00')

    open_recommendations = [item for item in recommendations if not item.is_resolved]
    summary = {
        'interventions_count': len(completed),
        'total_cost': total_cost,
        'last_visit': last_visit,
        'next_service_date': min(next_dates) if next_dates else None,
        'open_recommendations_count': len(open_recommendations),
        'operations_count': operations_count,
        'parts_count': parts_count,
    }
    return {
        'summary': summary,
        'history': history_list,
        'recommendations': recommendations,
        'open_recommendations': open_recommendations,
    }


def build_clients_snapshot(bookings):
    clients = defaultdict(lambda: {
        'name': '',
        'email': '',
        'phone': '',
        'booking_count': 0,
        'last_booking': None,
        'car_count': 0,
        'cars': set(),
        'vin_values': set(),
        'plate_values': set(),
    })
    for booking in bookings:
        key = (booking.client_email or '').strip().lower() or (booking.client_phone or '').strip() or f'booking-{booking.pk}'
        item = clients[key]
        item['name'] = item['name'] or booking.client_name
        item['email'] = item['email'] or booking.client_email
        item['phone'] = item['phone'] or booking.client_phone
        item['booking_count'] += 1
        item['last_booking'] = booking if item['last_booking'] is None or booking.created_at > item['last_booking'].created_at else item['last_booking']
        item['cars'].add((booking.car_brand, booking.car_model, booking.car_plate))
        if booking.car_vin:
            item['vin_values'].add(booking.car_vin.upper())
        if booking.car_plate:
            item['plate_values'].add(booking.car_plate.upper())
    output = []
    for item in clients.values():
        item['car_count'] = len(item['cars'])
        output.append(item)
    output.sort(key=lambda row: row['last_booking'].created_at if row['last_booking'] else timezone.now(), reverse=True)
    return output


def models_or(*, vin='', plate=''):
    from django.db.models import Q

    query = Q()
    if vin:
        query |= Q(car_vin__iexact=vin)
    if plate:
        query |= Q(car_plate__iexact=plate)
    return query
