from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Booking, BookingNotification


class Command(BaseCommand):
    help = 'Notifica service-urile despre booking-urile care stau prea mult in pending.'

    def handle(self, *args, **options):
        threshold = timezone.now() - timezone.timedelta(hours=24)
        today = timezone.localdate()
        queryset = Booking.objects.filter(
            status=Booking.STATUS_PENDING,
            created_at__lte=threshold,
            center__owner__isnull=False,
        ).select_related('center__owner')

        created = 0
        for booking in queryset:
            if BookingNotification.objects.filter(
                recipient=booking.center.owner,
                booking=booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
                title__icontains='pending',
                created_at__date=today,
            ).exists():
                continue

            BookingNotification.objects.create(
                recipient=booking.center.owner,
                booking=booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
                title=f'Programarea #{booking.pk} sta prea mult in pending',
                message='Verifica cererea si trimite oferta sau o decizie cat mai curand pentru a evita pierderea booking-ului.',
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(f'S-au creat {created} notificari pentru booking-uri pending vechi.'))
