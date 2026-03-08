from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Booking, BookingNotification


def _safe_send_mail(subject: str, message: str, to_email: str) -> None:
    """Send email only if email backend is configured; never crash on deploy."""
    if not to_email:
        return
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
        send_mail(subject, message, from_email, [to_email], fail_silently=True)
    except Exception:
        # Email is optional in this project
        return


@receiver(post_save, sender=Booking)
def create_notification_on_new_booking(sender, instance: Booking, created: bool, **kwargs):
    """When a booking is created, notify the service owner."""
    if not created:
        return

    owner = getattr(instance.center, 'owner', None)
    if owner:
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

        # Optional email notification to the owner
        _safe_send_mail(
            subject=f"[AutoHub] Programare nouă #{instance.pk}",
            message=(
                f"Ai o programare nouă pentru {instance.center.name}.\n\n"
                f"Client: {instance.client_name}\n"
                f"Data/Ora: {instance.booking_date} {instance.booking_time}\n"
                f"Mașină: {instance.car_brand} {instance.car_model} ({instance.car_plate})\n"
                f"Telefon: {instance.client_phone}\n"
                f"Email: {instance.client_email}\n\n"
                f"Intră în dashboard-ul service-ului ca să accepți/respingeți programarea."
            ),
            to_email=owner.email,
        )
