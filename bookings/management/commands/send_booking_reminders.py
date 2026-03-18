from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Booking
from core.services.sms_service import send_booking_reminder_sms


class Command(BaseCommand):
    help = 'Trimite reminder SMS pentru programările de mâine.'

    def handle(self, *args, **options):
        tomorrow = timezone.localdate() + timedelta(days=1)
        bookings = Booking.objects.select_related('center').filter(
            booking_date=tomorrow,
            status__in=[Booking.STATUS_CONFIRMED, Booking.STATUS_IN_PROGRESS],
            reminder_sent_1d=False,
        )

        sent_count = 0
        skipped_count = 0

        for booking in bookings:
            if send_booking_reminder_sms(booking):
                booking.reminder_sent_1d = True
                booking.save(update_fields=['reminder_sent_1d'])
                sent_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Reminders trimise: {sent_count}. Programări sărite: {skipped_count}.'
        ))
