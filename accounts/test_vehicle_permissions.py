from django.test import TestCase
from django.urls import reverse

from autohub_testutils.factories import make_booking, make_car, make_client_user


class AccountVehiclePermissionTests(TestCase):
    def setUp(self):
        self.owner = make_client_user(username="car-owner")
        self.other_user = make_client_user(username="other-owner")
        self.car = make_car(owner=self.owner)

    def test_user_cannot_edit_car_owned_by_another_account(self):
        """Ascunde masina altui utilizator la editare si raspunde cu 404."""
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("accounts:car_update", args=[self.car.pk]))

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_open_service_history_for_foreign_car(self):
        """Restrictioneaza istoricul unei masini straine chiar daca utilizatorul este autentificat."""
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("accounts:car_history", args=[self.car.pk]))

        self.assertEqual(response.status_code, 404)

    def test_car_history_uses_only_bookings_for_the_current_users_vehicle(self):
        """Afiseaza in dosarul masinii doar interventiile care apartin VIN-ului si numarului acelui vehicul."""
        matching_booking = make_booking(
            user=self.owner,
            status="done",
            suffix="101",
        )
        matching_booking.car_plate = self.car.plate_number
        matching_booking.car_vin = self.car.vin
        matching_booking.save(update_fields=["car_plate", "car_vin", "updated_at"])

        foreign_booking = make_booking(
            user=self.other_user,
            status="done",
            suffix="102",
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse("accounts:car_history", args=[self.car.pk]))

        self.assertEqual(response.status_code, 200)
        history = list(response.context["history"])
        self.assertIn(matching_booking, history)
        self.assertNotIn(foreign_booking, history)
