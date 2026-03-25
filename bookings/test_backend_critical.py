from datetime import datetime, time
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking, BookingNotification
from services.models import ServiceAvailabilityBlock
from autohub_testutils.factories import make_booking, make_garage, make_mechanic, make_service_center


class BookingBackendCriticalTests(TestCase):
    def test_booking_model_rejects_dates_in_the_past(self):
        """Blocheaza salvarile pentru programari plasate in trecut."""
        booking = make_booking(
            booking_date=timezone.localdate() - timezone.timedelta(days=1),
        )

        with self.assertRaisesMessage(ValidationError, "nu poate fi in trecut"):
            booking.full_clean()

    def test_new_booking_creates_owner_notification_and_sends_service_email(self):
        """Genereaza notificare interna pentru service si apeleaza emailul tranzactional la creare."""
        center = make_service_center()

        with patch("bookings.signals.send_booking_request_to_service_email", return_value=True) as mocked_send:
            with self.captureOnCommitCallbacks(execute=True):
                booking = make_booking(center=center, status=Booking.STATUS_PENDING)

        self.assertTrue(
            BookingNotification.objects.filter(
                recipient=center.owner,
                booking=booking,
                kind=BookingNotification.KIND_BOOKING_NEW,
            ).exists()
        )
        mocked_send.assert_called_once_with(booking)

    def test_garage_available_slots_exclude_confirmed_booking_and_blocks(self):
        """Scoate din sloturile disponibile intervalele deja ocupate sau blocate operational."""
        center = make_service_center()
        garage = make_garage(center=center, slot_minutes=60)
        booking_date = timezone.localdate() + timezone.timedelta(days=3)
        make_booking(
            center=center,
            garage=garage,
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking_date,
            booking_time_value=time(10, 0),
            duration_minutes=60,
        )
        ServiceAvailabilityBlock.objects.create(
            center=center,
            garage=garage,
            title="Pauza mare",
            block_type=ServiceAvailabilityBlock.BLOCK_BREAK,
            starts_at=timezone.make_aware(datetime.combine(booking_date, time(12, 0))),
            ends_at=timezone.make_aware(datetime.combine(booking_date, time(13, 0))),
        )

        slots = garage.available_slots_for_date(booking_date, duration_minutes=60)

        self.assertNotIn("10:00", slots)
        self.assertNotIn("12:00", slots)
        self.assertIn("09:00", slots)

    def test_mechanic_time_availability_rejects_overlapping_assignment(self):
        """Refuza o noua alocare peste un interval ocupat deja de acelasi mecanic."""
        center = make_service_center()
        garage = make_garage(center=center)
        mechanic = make_mechanic(center=center, garage=garage)
        booking_date = timezone.localdate() + timezone.timedelta(days=5)
        make_booking(
            center=center,
            garage=garage,
            mechanic=mechanic,
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking_date,
            booking_time_value=time(11, 0),
            duration_minutes=90,
        )

        is_available = mechanic.is_time_available(
            booking_date,
            time(11, 30),
            duration_minutes=60,
        )

        self.assertFalse(is_available)
