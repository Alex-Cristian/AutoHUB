import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from autohub_testutils.factories import make_car, make_client_user


class DocumentScanRoundThreeTests(TestCase):
    def setUp(self):
        self.user = make_client_user(username="scan-r3-user")
        self.car = make_car(owner=self.user)

    @patch("accounts.views._call_openai_document_scan", side_effect=RuntimeError("Serviciul AI nu este disponibil."))
    def test_generic_document_scan_api_surfaces_provider_errors_cleanly(self, mocked_scan):
        """Returneaza un mesaj clar catre UI cand providerul de scanare esueaza controlat."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:document_scan_api"),
            data=json.dumps({"hint_type": "ITP", "image": "data:image/png;base64,AAAA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "Serviciul AI nu este disponibil.")
        mocked_scan.assert_called_once()

    def test_car_scan_save_preserves_existing_vehicle_identity_fields(self):
        """Nu suprascrie datele deja confirmate manual pe masina, dar poate completa expirarea documentului."""
        self.client.force_login(self.user)
        original_make = self.car.make
        original_model = self.car.model
        original_year = self.car.year

        response = self.client.post(
            reverse("accounts:car_scan_save", args=[self.car.pk]),
            data=json.dumps({
                "target_document": "RCA",
                "tip_document": "RCA",
                "expiry_date": "2026-09-10",
                "make": "Volkswagen",
                "model": "Passat",
                "manufacture_year": 2017,
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.car.refresh_from_db()
        self.assertEqual(self.car.make, original_make)
        self.assertEqual(self.car.model, original_model)
        self.assertEqual(self.car.year, original_year)
        self.assertEqual(self.car.expiry_profile.rca_expiry.isoformat(), "2026-09-10")
        self.assertEqual(payload["fields_updated"], ["rca_expiry"])

    def test_car_scan_save_returns_normalized_warning_message_when_data_is_partial(self):
        """Include avertismentele de validare in mesajul final atunci cand scanarea are incredere scazuta."""
        self.client.force_login(self.user)

        with patch(
            "accounts.views._validate_and_normalize_ai_data",
            return_value=(
                {
                    "tip_document": "ITP",
                    "expiry_date": "2026-12-01",
                    "make": "",
                    "model": "",
                    "vin": "",
                    "plate_number": "",
                    "fuel": "",
                    "manufacture_year": None,
                    "confidence": "low",
                },
                ["Completeaza manual campurile lipsa."],
            ),
        ):
            response = self.client.post(
                reverse("accounts:car_scan_save", args=[self.car.pk]),
                data=json.dumps({"target_document": "ITP", "tip_document": "ITP", "expiry_date": "2026-12-01"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("Verificări automate".replace("ă", "a"), payload["message"].replace("ă", "a"))
        self.assertIn("Completeaza manual", payload["message"])
