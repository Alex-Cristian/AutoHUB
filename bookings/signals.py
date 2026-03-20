from django.db.models.signals import post_save
from django.dispatch import receiver

from core.services.email_service import send_booking_request_to_service_email
from .models import Booking, BookingNotification


@receiver(post_save, sender=Booking, dispatch_uid='bookings_create_notification_on_new_booking')
def create_notification_on_new_booking(sender, instance: Booking, created: bool, **kwargs):
    """When a booking is created, notify the service owner."""
    if not created:
        return

    owner = getattr(instance.center, 'owner', None)
    if not owner:
        return

    BookingNotification.objects.create(
        recipient=owner,
        booking=instance,
        kind=BookingNotification.KIND_BOOKING_NEW,
        title=f"Programare nouă #{instance.pk} — {instance.client_name}",
        message=(
            f"Service: {instance.center.name}\n"
            f"Data/Ora: {instance.booking_date} {instance.booking_time}\n"
            f"Mașină: {instance.car_brand} {instance.car_model} ({instance.car_plate})\n"
            f"Telefon: {instance.client_phone}\n"
            f"Detalii: {instance.problem_description[:300]}"
        ),
    )

    send_booking_request_to_service_email(instance)
