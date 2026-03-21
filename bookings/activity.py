from bookings.models import BookingActivityLog


def log_booking_activity(booking, event_type, message, *, actor=None, metadata=None):
    return BookingActivityLog.objects.create(
        booking=booking,
        actor=actor,
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    )
