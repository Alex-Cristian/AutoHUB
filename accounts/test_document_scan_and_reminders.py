import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CarExpiryProfile, CarExpiryReminderLog
from autohub_testutils.factories import make_car, make_client_user


class CarScanApiTests(TestCase):
    def setUp(self):
        self.user = make_client_user(username="scan-user")
        self.other_user = make_client_user(username="scan-other")
        self.car = make_car(owner=self.user)

    def test_document_scan_api_requires_payload(self):
        """Respinge cererea de scanare generica atunci cand nu exista nici fisier, nici imagine."""
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:document_scan_api"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("Încarcă".lower().replace("ă", "a"), response.json()["error"].lower().replace("ă", "a"))

    @patch("accounts.views._call_openai_document_scan")
    def test_car_scan_api_returns_normalized_data_for_owned_car(self, mocked_scan):
        """Ruleaza scanarea doar pentru masina proprie si intoarce datele normalizate catre UI."""
        mocked_scan.return_value = ({"tip_document": "ITP", "expiry_date": "2026-05-30"}, ["Camp cu incredere scazuta."])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:car_scan_api", args=[self.car.pk]),
            data=json.dumps({"hint_type": "ITP", "image": "data:image/png;base64,AAAA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["tip_document"], "ITP")
        self.assertIn("warning", payload)

    def test_car_scan_api_blocks_foreign_car(self):
        """Ascunde endpointul de scanare pentru masina altui utilizator."""
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("accounts:car_scan_api", args=[self.car.pk]),
            {"image": "data:image/png;base64,AAAA"},
        )

        self.assertEqual(response.status_code, 404)

    def test_car_scan_save_persists_manual_confirmation_into_car_and_expiry_profile(self):
        """Salveaza in masina si in profilul de expirari doar dupa confirmarea explicita a datelor scanate."""
        self.car.make = ""
        self.car.model = ""
        self.car.year = None
        self.car.fuel = ""
        self.car.save(update_fields=["make", "model", "year", "fuel"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:car_scan_save", args=[self.car.pk]),
            data=json.dumps({
                "target_document": "ITP",
                "tip_document": "ITP",
                "expiry_date": "2026-06-15",
                "make": "Volkswagen",
                "model": "Golf",
                "manufacture_year": 2019,
                "fuel": "benzina",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.car.refresh_from_db()
        expiry_profile = self.car.expiry_profile
        self.assertEqual(self.car.make, "Volkswagen")
        self.assertEqual(self.car.model, "Golf")
        self.assertEqual(self.car.year, 2019)
        self.assertEqual(expiry_profile.itp_expiry.isoformat(), "2026-06-15")


class ExpiryReminderCommandTests(TestCase):
    @patch("accounts.management.commands.send_expiry_email_reminders.send_expiry_reminder_email", return_value=True)
    def test_send_expiry_email_reminders_creates_log_only_for_due_documents(self, mocked_send):
        """Trimite remindere doar pentru documentele aflate in fereastra de 28-31 zile si memoreaza logul."""
        user = make_client_user(username="expiry-user")
        car = make_car(owner=user)
        profile = CarExpiryProfile.objects.create(
            car=car,
            itp_expiry=timezone.localdate() + timezone.timedelta(days=30),
            rca_expiry=timezone.localdate() + timezone.timedelta(days=10),
        )

        out = StringIO()
        call_command("send_expiry_email_reminders", stdout=out)

        self.assertTrue(
            CarExpiryReminderLog.objects.filter(
                car=car,
                document_type="itp_expiry",
                expiry_date=profile.itp_expiry,
            ).exists()
        )
        self.assertFalse(
            CarExpiryReminderLog.objects.filter(
                car=car,
                document_type="rca_expiry",
                expiry_date=profile.rca_expiry,
            ).exists()
        )
        mocked_send.assert_called_once()
        self.assertIn("Emailuri trimise: 1", out.getvalue())

    @patch("accounts.management.commands.send_expiry_email_reminders.send_expiry_reminder_email", return_value=True)
    def test_send_expiry_email_reminders_skips_existing_log(self, mocked_send):
        """Nu retrimite reminderul daca exista deja log pentru acel document si aceeasi data."""
        user = make_client_user(username="expiry-log-user")
        car = make_car(owner=user)
        expiry_date = timezone.localdate() + timezone.timedelta(days=29)
        CarExpiryProfile.objects.create(car=car, itp_expiry=expiry_date)
        CarExpiryReminderLog.objects.create(car=car, document_type="itp_expiry", expiry_date=expiry_date)

        call_command("send_expiry_email_reminders", stdout=StringIO())

        mocked_send.assert_not_called()
