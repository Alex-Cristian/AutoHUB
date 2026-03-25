from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.models import Invoice
from services.business import create_job_part_usage, ensure_job_card
from services.models import JobOperation, JobPartUsage
from autohub_testutils.factories import (
    make_booking,
    make_client_user,
    make_part,
    make_service_center,
    make_service_user,
)


class InvoiceCreateAndFinalizeFlowTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="invoice-flow-owner")
        self.center = make_service_center(owner=self.owner, name="Invoice Flow Service")
        self.booking = make_booking(center=self.center, status="done")

    def _prepare_job_card_with_billable_items(self):
        job_card, _ = ensure_job_card(self.booking, actor=self.owner)
        JobOperation.objects.create(
            job_card=job_card,
            title="Schimb ulei și filtru",
            description="Manoperă revizie periodică",
            final_cost=Decimal("220.00"),
            position=1,
        )
        part = make_part(center=self.center, name="Filtru ulei", stock=8, sale_price=Decimal("45.00"))
        create_job_part_usage(
            job_card,
            part=part,
            quantity=2,
            status=JobPartUsage.STATUS_CONSUMED,
            actor=self.owner,
            note="Consum la revizie",
        )
        return job_card

    def test_invoice_create_prefills_client_from_booking(self):
        """Prefill-uieste formularul de factura cu datele clientului cand vine dintr-un booking."""
        self.client.force_login(self.owner)

        response = self.client.get(reverse("invoices:create"), {"booking": self.booking.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["booking"], self.booking)
        self.assertContains(response, self.booking.client_name)

    def test_invoice_create_prefills_issue_date_for_new_invoice(self):
        """Afiseaza data emiterii implicit in formular, astfel incat finalizarea din UI sa nu esueze pe camp gol."""
        self.client.force_login(self.owner)

        response = self.client.get(reverse("invoices:create"), {"booking": self.booking.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, timezone.localdate().isoformat())

    def test_invoice_create_extra_line_starts_empty_for_browser_flow(self):
        """Liniile extra din formular pornesc goale, ca submit-ul din UI sa nu pice pe randuri necompletate."""
        self.client.force_login(self.owner)
        self.booking.service_item = None
        self.booking.save(update_fields=["service_item"])

        response = self.client.get(reverse("invoices:create"), {"booking": self.booking.pk})

        self.assertEqual(response.status_code, 200)
        formset = response.context["formset"]
        self.assertEqual(len(formset.forms), 1)
        self.assertEqual(formset.forms[0]["quantity"].value(), "")
        self.assertEqual(formset.forms[0]["unit_price"].value(), "")

    def test_invoice_create_finalize_action_persists_invoice_and_number(self):
        """Creeaza factura, liniile si o finalizeaza dintr-un singur pas."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("invoices:create") + f"?booking={self.booking.pk}",
            {
                "issue_date": "2026-03-23",
                "due_date": "",
                "client_name": self.booking.client_name,
                "client_email": self.booking.client_email,
                "client_phone": self.booking.client_phone,
                "client_address": "",
                "client_fiscal_code": "",
                "notes": "Factura test",
                "action": "finalize",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-description": "Manopera revizie",
                "lines-0-quantity": "1",
                "lines-0-unit_price": "150.00",
            },
        )

        invoice = Invoice.objects.get(booking=self.booking)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(invoice.status, Invoice.STATUS_FINAL)
        self.assertEqual(invoice.invoice_no, 1)
        self.assertEqual(str(invoice.total), "150.00")

    def test_invoice_create_prefills_lines_from_job_card_operations_and_parts(self):
        """Formularul de factură preia automat operațiunile și piesele din fișa lucrării."""
        self.client.force_login(self.owner)
        self._prepare_job_card_with_billable_items()

        response = self.client.get(reverse("invoices:create"), {"booking": self.booking.pk})

        self.assertEqual(response.status_code, 200)
        formset = response.context["formset"]
        descriptions = [form["description"].value() for form in formset.forms if form["description"].value()]
        self.assertIn("Schimb ulei și filtru - Manoperă revizie periodică", descriptions)
        self.assertIn("Filtru ulei - Consum la revizie", descriptions)
        self.assertContains(response, "Am preluat automat")

    def test_invoice_create_uses_auto_lines_when_submitted_without_manual_rows(self):
        """Dacă nu sunt introduse linii manual, factura salvează automat operațiunile și piesele existente."""
        self.client.force_login(self.owner)
        self._prepare_job_card_with_billable_items()

        response = self.client.post(
            reverse("invoices:create") + f"?booking={self.booking.pk}",
            {
                "issue_date": "2026-03-23",
                "due_date": "",
                "client_name": self.booking.client_name,
                "client_email": self.booking.client_email,
                "client_phone": self.booking.client_phone,
                "client_address": "",
                "client_fiscal_code": "",
                "notes": "Preluare automată",
                "action": "save",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-description": "",
                "lines-0-quantity": "",
                "lines-0-unit_price": "",
            },
        )

        invoice = Invoice.objects.get(booking=self.booking)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(invoice.lines.count(), 2)
        self.assertEqual(str(invoice.total), "310.00")

    def test_invoice_create_finalize_keeps_draft_when_booking_is_not_completed(self):
        """Nu emite factura finala pentru o programare care nu este inca marcata ca finalizata."""
        self.client.force_login(self.owner)
        self.booking.status = "confirmed"
        self.booking.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("invoices:create") + f"?booking={self.booking.pk}",
            {
                "issue_date": "2026-03-23",
                "due_date": "",
                "client_name": self.booking.client_name,
                "client_email": self.booking.client_email,
                "client_phone": self.booking.client_phone,
                "client_address": "",
                "client_fiscal_code": "",
                "notes": "Factura draft fortat",
                "action": "finalize",
                "lines-TOTAL_FORMS": "1",
                "lines-INITIAL_FORMS": "0",
                "lines-MIN_NUM_FORMS": "0",
                "lines-MAX_NUM_FORMS": "1000",
                "lines-0-description": "Diagnoza",
                "lines-0-quantity": "1",
                "lines-0-unit_price": "100.00",
            },
        )

        invoice = Invoice.objects.get(booking=self.booking)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(invoice.status, Invoice.STATUS_DRAFT)
        self.assertIsNone(invoice.invoice_no)

    def test_invoice_finalize_view_is_idempotent_for_final_invoice(self):
        """Nu renumeroteaza si nu strica factura atunci cand finalizezi a doua oara un document deja emis."""
        self.client.force_login(self.owner)
        invoice = Invoice.objects.create(
            center=self.center,
            booking=self.booking,
            company_name=self.center.name,
            company_address=self.center.address,
            company_city=self.center.get_city_display(),
            company_phone=self.center.phone,
            company_email=self.center.email,
            client_name=self.booking.client_name,
            client_email=self.booking.client_email,
            client_phone=self.booking.client_phone,
            status=Invoice.STATUS_FINAL,
            invoice_no=7,
        )

        response = self.client.post(reverse("invoices:finalize", args=[invoice.pk]))

        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_no, 7)

    def test_invoice_create_is_not_available_to_foreign_user(self):
        """Blocheaza accesul la formularul de facturare pentru un utilizator fara drepturi pe service."""
        foreign = make_client_user(username="invoice-foreign")
        self.client.force_login(foreign)

        response = self.client.get(reverse("invoices:create"))

        self.assertEqual(response.status_code, 302)
