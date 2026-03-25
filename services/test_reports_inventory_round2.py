import csv
import io
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from autohub_testutils.factories import (
    make_booking,
    make_client_user,
    make_invoice,
    make_part,
    make_service_center,
    make_service_user,
)
from bookings.models import Booking
from invoices.models import Invoice, InvoiceLine
from services.business import apply_stock_movement
from services.models import ServiceCenter, StockMovement
from services.reporting import build_report


class ServiceReportsRoundTwoTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="reports-owner-r2")
        self.client_user = make_client_user(username="reports-client-r2")
        self.center = make_service_center(owner=self.owner, name="Reports Round Two")

    def test_reports_page_falls_back_to_default_report_for_invalid_custom_interval(self):
        """Revine la raportul implicit cand filtrul de interval personalizat este invalid."""
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("services:reports"),
            {
                "report_type": "appointments",
                "preset_period": "custom",
                "start_date": "2026-03-21",
                "end_date": "2026-03-01",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["report"]["report_type"], "performance")

    def test_export_report_csv_falls_back_to_default_payload_when_filter_is_invalid(self):
        """Exportul CSV foloseste payload-ul implicit daca filtrul trimis in querystring este invalid."""
        self.client.force_login(self.owner)
        expected = build_report(
            ServiceCenter.objects.filter(pk=self.center.pk),
            {"report_type": "performance", "preset_period": "this_month"},
        )

        response = self.client.get(
            reverse("services:export_report_csv"),
            {
                "report_type": "parts_usage",
                "preset_period": "custom",
                "start_date": "2026-03-22",
                "end_date": "2026-03-10",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('raport_performance_', response["Content-Disposition"])

        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        self.assertEqual(rows[0][0], expected["title"])
        self.assertEqual(rows[3], expected["export_headers"])

    def test_build_parts_usage_report_matches_consumed_parts_from_invoice_lines(self):
        """Identifica piesele consumate in raport pe baza liniilor de factura care contin numele si codul piesei."""
        booking = make_booking(
            user=self.client_user,
            center=self.center,
            status=Booking.STATUS_DONE,
            booking_date=timezone.localdate(),
        )
        part = make_part(center=self.center, name="Filtru ulei premium", stock=3, minimum_stock=5)
        invoice = make_invoice(center=self.center, booking=booking, status=Invoice.STATUS_FINAL, with_line=False)
        invoice.issue_date = timezone.localdate()
        invoice.save(update_fields=["issue_date"])
        InvoiceLine.objects.create(
            invoice=invoice,
            description=f"{part.name} {part.part_number}",
            quantity=Decimal("2.00"),
            unit_price=Decimal("89.90"),
        )
        InvoiceLine.objects.create(
            invoice=invoice,
            description="Manopera revizie",
            quantity=Decimal("1.00"),
            unit_price=Decimal("150.00"),
        )
        invoice.recalc_totals(save=True)

        report = build_report(
            ServiceCenter.objects.filter(pk=self.center.pk),
            {"report_type": "parts_usage", "preset_period": "this_month"},
        )

        self.assertEqual(report["report_type"], "parts_usage")
        self.assertEqual(report["table_rows"][0]["col1"], part.name)
        self.assertIn("2", report["table_rows"][0]["col2"])
        self.assertEqual(report["summary"][2]["value"], 1)
        self.assertEqual(report["summary"][3]["value"], part.name)

    def test_build_appointment_status_report_counts_each_status_bucket(self):
        """Numara corect programarile pe fiecare status in raportul de distributie."""
        make_booking(center=self.center, user=self.client_user, status=Booking.STATUS_PENDING)
        make_booking(center=self.center, user=self.client_user, status=Booking.STATUS_CONFIRMED)
        make_booking(center=self.center, user=self.client_user, status=Booking.STATUS_DONE)
        make_booking(center=self.center, user=self.client_user, status=Booking.STATUS_CANCELLED)

        report = build_report(
            ServiceCenter.objects.filter(pk=self.center.pk),
            {"report_type": "appointment_status", "preset_period": "this_month"},
        )

        rows = {row["col1"]: row["col2"] for row in report["table_rows"]}
        labels = dict(Booking.STATUS_CHOICES)
        self.assertEqual(rows[labels[Booking.STATUS_PENDING]], 1)
        self.assertEqual(rows[labels[Booking.STATUS_CONFIRMED]], 1)
        self.assertEqual(rows[labels[Booking.STATUS_DONE]], 1)
        self.assertEqual(rows[labels[Booking.STATUS_CANCELLED]], 1)
        self.assertEqual(sum(report["chart"]["values"]), 4)


class ServiceInventoryRoundTwoTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="inventory-owner-r2")
        self.other_owner = make_service_user(username="inventory-other-r2")
        self.center = make_service_center(owner=self.owner, name="Inventory Round Two")
        self.other_center = make_service_center(owner=self.other_owner, name="Foreign Inventory")
        self.part = make_part(center=self.center, name="Placute frana", stock=4, minimum_stock=1)
        self.other_part = make_part(center=self.other_center, name="Alternator", stock=8, minimum_stock=2)

    def test_record_movement_adds_stock_and_persists_traceability(self):
        """Inregistreaza o intrare in stoc si salveaza miscarea cu observatia introdusa din UI."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:parts_inventory"),
            {
                "action": "record_movement",
                "center_id": self.center.pk,
                "part_id": self.part.pk,
                "movement_type": StockMovement.TYPE_IN,
                "quantity": 5,
                "note": "Livrare furnizor saptamanala",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock, 9)
        movement = StockMovement.objects.get(part=self.part, movement_type=StockMovement.TYPE_IN)
        self.assertEqual(movement.quantity_delta, 5)
        self.assertEqual(movement.note, "Livrare furnizor saptamanala")
        self.assertEqual(movement.actor, self.owner)

    def test_record_movement_prevents_negative_stock_and_keeps_previous_value(self):
        """Blocheaza iesirea peste stocul disponibil si nu creeaza miscari partiale."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:parts_inventory"),
            {
                "action": "record_movement",
                "center_id": self.center.pk,
                "part_id": self.part.pk,
                "movement_type": StockMovement.TYPE_OUT,
                "quantity": 10,
                "note": "Consum gresit",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock, 4)
        self.assertFalse(
            StockMovement.objects.filter(part=self.part, note="Consum gresit").exists()
        )
        self.assertContains(response, "Stoc insuficient")

    def test_parts_inventory_search_and_sort_are_scoped_to_selected_center(self):
        """Aplica filtrele si ordonarea doar in centrul selectat, fara a amesteca piesele altui service."""
        second_local = make_part(center=self.center, name="Filtru aer", stock=7, minimum_stock=1)
        second_local.part_number = "FIL-777"
        second_local.supplier = "Unix Auto"
        second_local.save(update_fields=["part_number", "supplier"])

        self.part.part_number = "FIL-111"
        self.part.supplier = "Unix Auto"
        self.part.save(update_fields=["part_number", "supplier"])

        self.other_part.part_number = "FIL-999"
        self.other_part.supplier = "Unix Auto"
        self.other_part.save(update_fields=["part_number", "supplier"])

        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("services:parts_inventory"),
            {
                "center": self.center.pk,
                "q": "FIL",
                "sort": "stock_desc",
            },
        )

        self.assertEqual(response.status_code, 200)
        names = [part.name for part in response.context["parts"]]
        self.assertEqual(names, ["Filtru aer", "Placute frana"])
        self.assertNotIn("Alternator", names)

    def test_foreign_service_owner_cannot_mutate_another_services_part(self):
        """Refuza modificarile de stoc atunci cand piesa apartine altui service."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:parts_inventory"),
            {
                "action": "update_stock",
                "center_id": self.center.pk,
                "part_id": self.other_part.pk,
                "stock": 99,
                "minimum_stock": 3,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.other_part.refresh_from_db()
        self.assertEqual(self.other_part.stock, 8)

    def test_manual_stock_helper_rejects_negative_adjustment_below_zero(self):
        """Helperul de stoc continua sa protejeze integritatea chiar si la apel direct de business logic."""
        with self.assertRaisesMessage(ValidationError, "Stoc insuficient"):
            apply_stock_movement(
                self.part,
                -50,
                StockMovement.TYPE_ADJUSTMENT,
                actor=self.owner,
                note="Ajustare invalida",
            )
