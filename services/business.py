from collections import defaultdict
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min, Sum
from django.utils import timezone

from bookings.activity import log_booking_activity
from bookings.models import Booking
from services.models import JobCard, JobPartUsage, StockMovement


JOB_TO_BOOKING_STATUS = {
    JobCard.STATUS_APPROVED: Booking.STATUS_CONFIRMED,
    JobCard.STATUS_IN_PROGRESS: Booking.STATUS_IN_PROGRESS,
    JobCard.STATUS_WAITING_PARTS: Booking.STATUS_WAITING_PARTS,
    JobCard.STATUS_WAITING_CUSTOMER: Booking.STATUS_CONFIRMED,
    JobCard.STATUS_COMPLETED: Booking.STATUS_DONE,
    JobCard.STATUS_INVOICED: Booking.STATUS_DONE,
    JobCard.STATUS_CLOSED: Booking.STATUS_DONE,
}


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


def sync_booking_from_job_card(job_card, actor=None):
    booking = job_card.booking
    target_status = JOB_TO_BOOKING_STATUS.get(job_card.status)
    if not target_status:
        return booking

    changed_fields = []
    if booking.status != target_status:
        old_status = booking.status
        booking.status = target_status
        changed_fields.append('status')
    else:
        old_status = None

    tags = list(booking.operational_tags or [])
    waiting_tag_present = Booking.TAG_WAITING_PART in tags
    if job_card.status == JobCard.STATUS_WAITING_PARTS and not waiting_tag_present:
        tags.append(Booking.TAG_WAITING_PART)
    if job_card.status != JobCard.STATUS_WAITING_PARTS and waiting_tag_present:
        tags = [tag for tag in tags if tag != Booking.TAG_WAITING_PART]
    if tags != (booking.operational_tags or []):
        booking.operational_tags = tags
        changed_fields.append('operational_tags')

    if changed_fields:
        booking.save(update_fields=[*changed_fields, 'updated_at'])
        if old_status:
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
            operations_count += job_card.operations.count()
            parts_count += job_card.part_usages.exclude(status=JobPartUsage.STATUS_RETURNED).count()
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
