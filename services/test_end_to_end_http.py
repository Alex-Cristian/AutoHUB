from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, BookingNotification
from services.models import JobCard
from autohub_testutils.factories import make_car, make_client_user, make_garage, make_mechanic, make_service_center, make_service_item, make_service_user


class EndToEndHttpFlowTests(TestCase):
    def setUp(self):
        self.service_owner = make_service_user(username="e2e-service")
        self.client_user = make_client_user(username="e2e-client")
        self.center = make_service_center(owner=self.service_owner, name="Flux E2E Service")
        self.garage = make_garage(center=self.center)
        self.mechanic = make_mechanic(center=self.center, garage=self.garage)
        self.service_item = make_service_item(center=self.center, name="Revizie completa", duration_minutes=60)
        self.car = make_car(owner=self.client_user)

    @patch("bookings.signals.send_booking_request_to_service_email", return_value=True)
    @patch("services.views.send_booking_completed_email", return_value=True)
    @patch("services.views.send_booking_completed_sms", return_value=False)
    def test_client_service_client_http_flow_covers_booking_processing_and_history(
        self,
        mocked_sms,
        mocked_completed_email,
        mocked_new_booking_email,
    ):
        """Parcurge cap-coada fluxul principal HTTP: clientul creeaza booking, service-ul il proceseaza, clientul vede rezultatul."""
        self.client.force_login(self.client_user)
        with self.captureOnCommitCallbacks(execute=True):
            create_response = self.client.post(
                reverse("bookings:create", args=[self.center.slug]),
                {
                    "saved_car": self.car.pk,
                    "client_name": "Client E2E",
                    "client_phone": "0722333444",
                    "client_email": "e2eclient@example.com",
                    "car_brand": self.car.make,
                    "car_model": self.car.model,
                    "car_year": self.car.year,
                    "car_fuel": self.car.fuel,
                    "car_plate": self.car.plate_number,
                    "car_vin": self.car.vin,
                    "service_item": self.service_item.pk,
                    "garage": self.garage.pk,
                    "problem_description": "Revizie completa si schimb filtre",
                    "booking_date": (timezone.localdate() + timezone.timedelta(days=2)).isoformat(),
                    "booking_time": "10:00",
                    "save_car": "1",
                },
            )
        booking = Booking.objects.get(center=self.center, user=self.client_user)
        self.assertRedirects(create_response, reverse("bookings:success", args=[booking.pk]))
        mocked_new_booking_email.assert_called_once()

        self.client.force_login(self.service_owner)
        update_response = self.client.post(
            reverse("services:booking_detail", args=[booking.pk]),
            {
                "action": "save_job_card",
                "status": JobCard.STATUS_COMPLETED,
                "mechanic": self.mechanic.pk,
                "mileage": 153000,
                "estimated_hours": "2.00",
                "actual_hours": "2.25",
                "estimated_cost": "350.00",
                "final_cost": "420.00",
                "diagnostic_summary": "Consumabile schimbate.",
                "work_performed": "Revizie completa",
                "customer_notes": "Masina este gata de ridicare.",
                "internal_notes": "Test e2e",
                "next_service_date": "",
                "next_service_km": "",
            },
        )
        self.assertRedirects(update_response, reverse("services:booking_detail", args=[booking.pk]))

        status_response = self.client.post(
            reverse("services:booking_detail", args=[booking.pk]),
            {"action": "update_status", "status": Booking.STATUS_DONE},
        )
        self.assertRedirects(status_response, reverse("services:booking_detail", args=[booking.pk]))

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_DONE)
        self.assertTrue(BookingNotification.objects.filter(booking=booking).exists())

        self.client.force_login(self.client_user)
        my_bookings_response = self.client.get(reverse("bookings:my_bookings"))
        car_history_response = self.client.get(reverse("accounts:car_history", args=[self.car.pk]))

        self.assertEqual(my_bookings_response.status_code, 200)
        self.assertContains(my_bookings_response, booking.center.name)
        self.assertEqual(car_history_response.status_code, 200)
        self.assertContains(car_history_response, booking.car_model)
        mocked_completed_email.assert_not_called()
        mocked_sms.assert_not_called()
