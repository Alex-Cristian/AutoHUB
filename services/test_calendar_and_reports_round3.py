import csv
import io
from datetime import datetime, time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from autohub_testutils.factories import (
    make_booking,
    make_client_user,
    make_garage,
    make_mechanic,
    make_service_center,
    make_service_item,
    make_service_user,
)
from bookings.models import Booking, BookingActivityLog
from services.models import ServiceAvailabilityBlock


class ServiceCalendarEventsTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="calendar-owner-r3")
        self.foreign_user = make_client_user(username="calendar-foreign-r3")
        self.center = make_service_center(owner=self.owner, name="Calendar Round Three")
        self.garage = make_garage(center=self.center, slot_minutes=60)
        self.mechanic = make_mechanic(center=self.center, garage=self.garage, name="Mecanic Calendar")
        self.service_item = make_service_item(center=self.center, name="Diagnoza calendar", duration_minutes=90)
        self.booking = make_booking(
            center=self.center,
            user=make_client_user(username="calendar-client-r3"),
            garage=self.garage,
            mechanic=self.mechanic,
            service_item=self.service_item,
            status=Booking.STATUS_CONFIRMED,
            booking_date=timezone.localdate() + timezone.timedelta(days=3),
            booking_time_value=time(9, 30),
            duration_minutes=90,
        )
        aware_start = timezone.make_aware(
            datetime.combine(self.booking.booking_date, time(12, 0)),
            timezone.get_current_timezone(),
        )
        aware_end = timezone.make_aware(
            datetime.combine(self.booking.booking_date, time(13, 0)),
            timezone.get_current_timezone(),
        )
        self.block = ServiceAvailabilityBlock.objects.create(
            center=self.center,
            garage=self.garage,
            mechanic=self.mechanic,
            block_type=ServiceAvailabilityBlock.BLOCK_BREAK,
            title="Pauza test",
            starts_at=aware_start,
            ends_at=aware_end,
            created_by=self.owner,
        )

    def test_calendar_events_return_booking_and_block_for_selected_filters(self):
        """Livreaza in calendar atat programarea, cat si blocajul operational atunci cand filtrele corespund."""
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("services:calendar_events"),
            {
                "start": f"{self.booking.booking_date.isoformat()}T00:00:00Z",
                "end": f"{(self.booking.booking_date + timezone.timedelta(days=1)).isoformat()}T00:00:00Z",
                "status": Booking.STATUS_CONFIRMED,
                "garage": self.garage.pk,
                "mechanic": self.mechanic.pk,
                "service_item": self.service_item.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        booking_event = next(item for item in payload if item["id"] == self.booking.pk)
        block_event = next(item for item in payload if item["id"] == f"block-{self.block.pk}")
        self.assertEqual(booking_event["extendedProps"]["garage"], self.garage.name)
        self.assertEqual(booking_event["extendedProps"]["mechanic"], self.mechanic.name)
        self.assertEqual(booking_event["extendedProps"]["service"], self.service_item.name)
        self.assertEqual(block_event["extendedProps"]["status"], "availability_block")
        self.assertEqual(block_event["extendedProps"]["status_label"], self.block.get_block_type_display())

    def test_calendar_events_require_service_account(self):
        """Refuza feed-ul de evenimente din calendar pentru un utilizator fara service."""
        self.client.force_login(self.foreign_user)

        response = self.client.get(reverse("services:calendar_events"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "service_required")


class ServiceCalendarUpdateBookingTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="calendar-update-owner-r3")
        self.foreign = make_client_user(username="calendar-update-foreign-r3")
        self.center = make_service_center(owner=self.owner, name="Calendar Update Round Three")
        self.booking = make_booking(
            center=self.center,
            status=Booking.STATUS_CONFIRMED,
            booking_date=timezone.localdate() + timezone.timedelta(days=2),
            booking_time_value=time(10, 0),
            duration_minutes=60,
        )

    def test_calendar_update_booking_moves_schedule_and_logs_activity(self):
        """Mutarea din calendar actualizeaza data, ora, durata si lasa in urma o intrare de activitate."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {
                "start": f"{(self.booking.booking_date + timezone.timedelta(days=1)).isoformat()}T14:15:00",
                "end": f"{(self.booking.booking_date + timezone.timedelta(days=1)).isoformat()}T15:45:00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.booking_date, timezone.localdate() + timezone.timedelta(days=3))
        self.assertEqual(self.booking.booking_time.strftime("%H:%M"), "14:15")
        self.assertEqual(self.booking.duration_minutes, 90)
        self.assertTrue(
            BookingActivityLog.objects.filter(
                booking=self.booking,
                event_type="schedule_changed",
            ).exists()
        )

    def test_calendar_update_booking_rejects_locked_short_or_foreign_requests(self):
        """Blocheaza mutarea pentru bookinguri inchise, durate prea scurte sau proprietari gresiti."""
        self.client.force_login(self.owner)
        self.booking.status = Booking.STATUS_DONE
        self.booking.save(update_fields=["status", "updated_at"])

        locked_response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {
                "start": f"{self.booking.booking_date.isoformat()}T09:00:00",
                "end": f"{self.booking.booking_date.isoformat()}T10:00:00",
            },
        )
        self.assertEqual(locked_response.status_code, 400)
        self.assertEqual(locked_response.json()["detail"], "locked")

        self.booking.status = Booking.STATUS_CONFIRMED
        self.booking.save(update_fields=["status", "updated_at"])
        short_response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {
                "start": f"{self.booking.booking_date.isoformat()}T09:00:00",
                "end": f"{self.booking.booking_date.isoformat()}T09:20:00",
            },
        )
        self.assertEqual(short_response.status_code, 400)
        self.assertIn("Durata minima", short_response.json()["message"])

        self.client.force_login(self.foreign)
        foreign_response = self.client.post(
            reverse("services:calendar_update_booking", args=[self.booking.pk]),
            {
                "start": f"{self.booking.booking_date.isoformat()}T09:00:00",
                "end": f"{self.booking.booking_date.isoformat()}T10:00:00",
            },
        )
        self.assertEqual(foreign_response.status_code, 403)
        self.assertEqual(foreign_response.json()["detail"], "forbidden")


class ServiceReportsRoundThreeTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="reports-owner-r3")
        self.center = make_service_center(owner=self.owner, name="Reports Round Three")
        make_booking(center=self.center, status=Booking.STATUS_PENDING, booking_date=timezone.localdate())
        make_booking(center=self.center, status=Booking.STATUS_DONE, booking_date=timezone.localdate())

    def test_reports_page_renders_requested_report_and_chart_payload(self):
        """Livreaza raportul cerut si serializarea pentru grafic atunci cand filtrul este valid."""
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("services:reports"),
            {"report_type": "appointments", "preset_period": "today"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["report"]["report_type"], "appointments")
        self.assertIn('"label": "Program\\u0103ri"', response.context["report_chart_json"])
        self.assertContains(response, "Raport program")

    def test_export_report_csv_contains_expected_headers_and_values(self):
        """Exportul CSV include antetul, perioada si randurile relevante pentru raportul de statusuri."""
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("services:export_report_csv"),
            {"report_type": "appointment_status", "preset_period": "today"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("raport_appointment_status_", response["Content-Disposition"])
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0][0], "Raport status programări")
        self.assertEqual(rows[3], ["Status", "Număr", "Procent", "Observații"])
        flattened = " ".join(" ".join(row) for row in rows)
        self.assertIn("În așteptare", flattened)
        self.assertIn("Finalizată", flattened)
