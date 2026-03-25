from datetime import datetime, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from autohub_testutils.factories import (
    make_booking,
    make_mechanic,
    make_part,
    make_service_center,
    make_service_user,
)
from bookings.models import Booking
from services.business import (
    apply_stock_movement,
    create_job_part_usage,
    ensure_job_card,
    rollback_job_part_usage,
)
from services.models import JobPartUsage, ServiceAvailabilityBlock, StockMovement


class ServiceStockEdgeCaseTests(TestCase):
    def test_apply_stock_movement_allows_exact_depletion_to_zero_and_records_metadata(self):
        """Permite consumul exact pana la zero si pastreaza trasabilitatea miscarii de stoc."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        part = make_part(center=booking.center, stock=2, sale_price=Decimal("50.00"))

        movement = apply_stock_movement(
            part,
            -2,
            StockMovement.TYPE_OUT,
            actor=booking.center.owner,
            job_card=job_card,
            booking=booking,
            note="Consum total din test",
        )

        part.refresh_from_db()
        self.assertEqual(part.stock, 0)
        self.assertEqual(movement.previous_stock, 2)
        self.assertEqual(movement.new_stock, 0)
        self.assertEqual(movement.actor, booking.center.owner)
        self.assertEqual(movement.job_card, job_card)
        self.assertEqual(movement.booking, booking)

    def test_create_job_part_usage_rejects_invalid_status(self):
        """Blocheaza orice status de piesa care nu face parte din fluxul acceptat."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        part = make_part(center=booking.center, stock=4)

        with self.assertRaisesMessage(ValidationError, "Statusul piesei din lucrare nu este valid."):
            create_job_part_usage(
                job_card,
                part=part,
                quantity=1,
                status="broken-status",
                actor=booking.center.owner,
            )

    def test_reserved_usage_rollback_restores_stock_and_creates_release_movement(self):
        """O rezervare urmata de rollback readuce stocul si lasa miscarea inversa corecta."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        part = make_part(center=booking.center, stock=5)

        usage = create_job_part_usage(
            job_card,
            part=part,
            quantity=2,
            status=JobPartUsage.STATUS_RESERVED,
            actor=booking.center.owner,
            note="Rezervare test",
        )
        rollback_job_part_usage(usage, actor=booking.center.owner)

        part.refresh_from_db()
        self.assertEqual(part.stock, 5)
        movement_types = list(
            part.stock_movements.order_by("created_at", "pk").values_list("movement_type", flat=True)
        )
        self.assertEqual(movement_types, [StockMovement.TYPE_RESERVE, StockMovement.TYPE_RELEASE])

    def test_returned_usage_rollback_consumes_extra_stock_back_to_original(self):
        """Rollback pentru o piesa marcata returnata inverseaza cresterea de stoc facuta la retur."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        part = make_part(center=booking.center, stock=3)

        usage = create_job_part_usage(
            job_card,
            part=part,
            quantity=1,
            status=JobPartUsage.STATUS_RETURNED,
            actor=booking.center.owner,
            note="Retur test",
        )
        part.refresh_from_db()
        self.assertEqual(part.stock, 4)

        rollback_job_part_usage(usage, actor=booking.center.owner)
        part.refresh_from_db()
        self.assertEqual(part.stock, 3)
        movement_types = list(
            part.stock_movements.order_by("created_at", "pk").values_list("movement_type", flat=True)
        )
        self.assertEqual(movement_types, [StockMovement.TYPE_RELEASE, StockMovement.TYPE_RESERVE])


class ServiceAvailabilityEdgeCaseTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="edge-owner-r6")
        self.center = make_service_center(owner=self.owner, name="Edge Calendar Service")
        self.booking = make_booking(
            center=self.center,
            status=Booking.STATUS_CONFIRMED,
            booking_date=timezone.localdate() + timezone.timedelta(days=4),
            booking_time_value=time(10, 0),
            duration_minutes=60,
        )
        self.garage = self.booking.garage
        self.mechanic = make_mechanic(center=self.center, garage=self.garage, name="Edge Mechanic")
        self.booking.mechanic = self.mechanic
        self.booking.save(update_fields=["mechanic", "updated_at"])
        self.client.force_login(self.owner)

    def test_available_slots_include_slot_that_ends_exactly_at_closing_time(self):
        """Pastreaza sloturile care se termina fix la ora de inchidere a garajului."""
        self.garage.open_time = time(8, 0)
        self.garage.close_time = time(10, 0)
        self.garage.slot_minutes = 60
        self.garage.save(update_fields=["open_time", "close_time", "slot_minutes"])

        slots = self.garage.available_slots_for_date(
            timezone.localdate() + timezone.timedelta(days=6),
            duration_minutes=60,
        )

        self.assertIn("09:00", slots)

    def test_garage_time_availability_rejects_partial_overlap_with_block(self):
        """Refuza un interval care se intersecteaza chiar partial cu un bloc operational."""
        booking_date = timezone.localdate() + timezone.timedelta(days=7)
        ServiceAvailabilityBlock.objects.create(
            center=self.center,
            garage=self.garage,
            block_type=ServiceAvailabilityBlock.BLOCK_BREAK,
            title="Pauza partiala",
            starts_at=timezone.make_aware(datetime.combine(booking_date, time(9, 15))),
            ends_at=timezone.make_aware(datetime.combine(booking_date, time(9, 45))),
            created_by=self.owner,
        )

        is_available = self.garage.is_time_available(
            booking_date,
            time(9, 0),
            duration_minutes=60,
        )

        self.assertFalse(is_available)

    def test_mechanic_time_availability_allows_same_booking_when_excluded(self):
        """Nu blocheaza propria programare cand verificarea este facuta pentru acelasi booking."""
        is_available = self.mechanic.is_time_available(
            self.booking.booking_date,
            self.booking.booking_time,
            duration_minutes=self.booking.duration_minutes,
            exclude_booking_id=self.booking.pk,
        )

        self.assertTrue(is_available)

    def test_calendar_update_rejects_missing_bounds(self):
        """Returneaza eroare clara cand lipseste startul sau finalul mutarii din calendar."""
        response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {"start": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Lipsesc data de inceput", response.json()["message"])

    def test_calendar_update_rejects_invalid_datetime_format(self):
        """Refuza payload-urile cu data invalida trimise de un client buggy."""
        response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {"start": "nu-e-data", "end": "nici-asta"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Intervalul trimis nu este valid", response.json()["message"])

    def test_calendar_update_rejects_move_into_blocked_interval(self):
        """Nu permite mutarea booking-ului peste un interval blocat pe acelasi garaj."""
        ServiceAvailabilityBlock.objects.create(
            center=self.center,
            garage=self.garage,
            block_type=ServiceAvailabilityBlock.BLOCK_BREAK,
            title="Pauza calendar",
            starts_at=timezone.make_aware(datetime.combine(self.booking.booking_date, time(12, 0))),
            ends_at=timezone.make_aware(datetime.combine(self.booking.booking_date, time(13, 0))),
            created_by=self.owner,
        )

        response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {
                "start": f"{self.booking.booking_date.isoformat()}T12:00:00",
                "end": f"{self.booking.booking_date.isoformat()}T13:00:00",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nu mai este disponibil", response.json()["message"])
