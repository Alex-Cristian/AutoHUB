from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking
from invoices.models import Invoice, InvoiceLine
from autohub_testutils.factories import make_booking, make_client_user, make_invoice, make_service_center, make_service_user


class InvoiceModelTests(TestCase):
    def test_invoice_assigns_next_number_per_service_center(self):
        """Numeroteaza facturile incremental si separat pentru fiecare service."""
        center = make_service_center(name="Factura Service")
        first = make_invoice(center=center, status=Invoice.STATUS_FINAL)
        first.assign_next_number_if_needed()
        first.save(update_fields=["invoice_no"])
        second = make_invoice(center=center, status=Invoice.STATUS_DRAFT, with_line=False)

        second.assign_next_number_if_needed()

        self.assertEqual(first.invoice_no, 1)
        self.assertEqual(second.invoice_no, 2)

    def test_invoice_line_save_and_recalc_totals_keep_financials_consistent(self):
        """Calculeaza corect totalul pe linie si totalurile agregate ale facturii."""
        invoice = make_invoice(with_line=False)
        InvoiceLine.objects.create(invoice=invoice, description="Manopera", quantity=2, unit_price=Decimal("50.00"))
        InvoiceLine.objects.create(invoice=invoice, description="Piese", quantity=1, unit_price=Decimal("25.00"))

        invoice.recalc_totals(save=True)
        invoice.refresh_from_db()

        self.assertEqual(invoice.subtotal, Decimal("125.00"))
        self.assertEqual(invoice.total, Decimal("125.00"))


class InvoiceViewPermissionAndPdfTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="invoice-owner")
        self.other_user = make_client_user(username="invoice-client")
        self.center = make_service_center(owner=self.owner, name="Invoice Secure Service")
        self.booking = make_booking(center=self.center, user=self.other_user, status=Booking.STATUS_DONE)
        self.invoice = make_invoice(center=self.center, booking=self.booking, status=Invoice.STATUS_FINAL)

    def test_non_owner_cannot_access_invoice_detail_or_pdf(self):
        """Restrange accesul la factura pentru utilizatorii fara drepturi pe service-ul emitent."""
        self.client.force_login(self.other_user)

        detail_response = self.client.get(reverse("invoices:detail", args=[self.invoice.pk]))
        pdf_response = self.client.get(reverse("invoices:pdf", args=[self.invoice.pk]))

        self.assertEqual(detail_response.status_code, 302)
        self.assertEqual(pdf_response.status_code, 302)

    def test_owner_can_open_clients_list_and_manual_invoice_create(self):
        """Rutele principale de clienti si facturare trebuie sa ramana accesibile din dashboard-ul service-ului."""
        self.client.force_login(self.owner)

        clients_response = self.client.get(reverse("invoices:clients"))
        create_response = self.client.get(reverse("invoices:create"))

        self.assertEqual(clients_response.status_code, 200)
        self.assertEqual(create_response.status_code, 200)
        self.assertContains(clients_response, "Clien")
        self.assertContains(create_response, "Creeaz")

    @patch("invoices.views.build_invoice_pdf", return_value=b"%PDF-test")
    def test_owner_can_download_invoice_pdf(self, mocked_build_pdf):
        """Genereaza raspunsul PDF pentru proprietarul service-ului si apeleaza generatorul backend."""
        self.client.force_login(self.owner)

        response = self.client.get(reverse("invoices:pdf", args=[self.invoice.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inline; filename=", response["Content-Disposition"])
        mocked_build_pdf.assert_called_once_with(self.invoice)
