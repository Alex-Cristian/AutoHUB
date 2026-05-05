from datetime import datetime, timedelta

from django.utils import timezone

from .models import Booking


ACTIVE_CALENDAR_STATUSES = {
    Booking.STATUS_CONFIRMED,
    Booking.STATUS_IN_PROGRESS,
    Booking.STATUS_WAITING_PARTS,
}


def booking_interval_overlaps(service_id, start_time, duration, appointment_id=None):
    if not service_id or not start_time:
        return False

    duration_minutes = max(int(duration or 0), 30)
    requested_start = start_time
    if timezone.is_aware(requested_start):
        requested_start = timezone.localtime(requested_start).replace(tzinfo=None)
    requested_end = requested_start + timedelta(minutes=duration_minutes)

    qs = Booking.objects.filter(
        center_id=service_id,
        status__in=ACTIVE_CALENDAR_STATUSES,
        booking_date=requested_start.date(),
    ).select_related("service_item", "garage")
    if appointment_id:
        qs = qs.exclude(pk=appointment_id)

    for booking in qs:
        existing_start = datetime.combine(booking.booking_date, booking.booking_time)
        existing_duration = booking.duration_minutes
        if not existing_duration and booking.service_item_id:
            existing_duration = getattr(booking.service_item, "duration_minutes", None)
        if not existing_duration and booking.garage_id:
            existing_duration = getattr(booking.garage, "slot_minutes", None)
        existing_end = existing_start + timedelta(minutes=max(existing_duration or 60, 30))
        if requested_start < existing_end and requested_end > existing_start:
            return True
    return False


def booking_slot_is_available(booking, booking_date, booking_time, duration_minutes):
    if not booking_date or not booking_time:
        return False

    start_time = datetime.combine(booking_date, booking_time)
    if booking_interval_overlaps(
        booking.center_id,
        start_time,
        duration_minutes,
        appointment_id=booking.pk,
    ):
        return False

    if booking.garage_id and not booking.garage.is_time_available(
        booking_date,
        booking_time,
        duration_minutes=duration_minutes,
        exclude_booking_id=booking.pk,
        booking_status=booking.status,
    ):
        return False

    if booking.mechanic_id and not booking.mechanic.is_time_available(
        booking_date,
        booking_time,
        duration_minutes=duration_minutes,
        exclude_booking_id=booking.pk,
    ):
        return False

    return True
