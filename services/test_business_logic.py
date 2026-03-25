from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking
from invoices.models import Invoice
from services.business import (
    build_clients_snapshot,
    build_vehicle_dossier,
    create_job_part_usage,
    ensure_job_card,
    finalize_invoice,
    rollback_job_part_usage,
    sync_booking_from_job_card,
    transition_booking_status,
)
from services.models import JobCard, JobPartUsage, JobRecommendation
from services.reporting import build_dashboard_metrics, build_period
from autohub_testutils.factories import make_booking, make_invoice, make_mechanic, make_part, make_service_center


class ServiceBusinessLogicTests(TestCase):
    def test_ensure_job_card_copies_center_mechanic_and_estimated_cost(self):
        """Creeaza sau completeaza fisa lucrarii folosind datele esentiale din programare."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED, estimated_price=Decimal("350.00"))
        mechanic = make_mechanic(center=booking.center, garage=booking.garage)
        booking.mechanic = mechanic
        booking.save(update_fields=["mechanic", "updated_at"])

        job_card, created = ensure_job_card(booking, actor=booking.center.owner)

        self.assertTrue(created)
        self.assertEqual(job_card.center, booking.center)
        self.assertEqual(job_card.mechanic, mechanic)
        self.assertEqual(job_card.estimated_cost, Decimal("350.00"))

    def test_sync_booking_from_job_card_updates_status_and_waiting_part_tag(self):
        """Sincronizeaza bookingul din fisa lucrarii si gestioneaza automat tagul de asteptare piese."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        job_card.status = JobCard.STATUS_WAITING_PARTS
        job_card.save(update_fields=["status", "updated_at"])

        sync_booking_from_job_card(job_card, actor=booking.center.owner)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_WAITING_PARTS)
        self.assertIn(Booking.TAG_WAITING_PART, booking.operational_tags)

        job_card.status = JobCard.STATUS_COMPLETED
        job_card.save(update_fields=["status", "updated_at"])
        sync_booking_from_job_card(job_card, actor=booking.center.owner)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_DONE)
        self.assertNotIn(Booking.TAG_WAITING_PART, booking.operational_tags)

    def test_sync_booking_from_waiting_customer_job_card_keeps_quote_state(self):
        """Statusul waiting_customer din fisa trebuie sa ramana aliniat cu bookingul ofertat, nu confirmat."""
        booking = make_booking(status=Booking.STATUS_PENDING)
        transition_booking_status(booking, Booking.STATUS_QUOTED, actor=booking.center.owner)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        job_card.status = JobCard.STATUS_WAITING_CUSTOMER
        job_card.save(update_fields=["status", "updated_at"])

        sync_booking_from_job_card(job_card, actor=booking.center.owner)
        booking.refresh_from_db()

        self.assertEqual(booking.status, Booking.STATUS_QUOTED)

    def test_finalize_invoice_requires_completed_booking(self):
        """Nu permite emiterea finala a unei facturi cat timp programarea este inca activa."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        invoice = make_invoice(center=booking.center, booking=booking, with_line=False)

        with self.assertRaisesMessage(ValidationError, "programarea este marcata ca finalizata"):
            finalize_invoice(invoice, actor=booking.center.owner)

    def test_create_job_part_usage_and_rollback_keep_stock_consistent(self):
        """Consumul si rollback-ul piesei pastreaza stocul si trasabilitatea miscarilor in stare corecta."""
        booking = make_booking(status=Booking.STATUS_CONFIRMED)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        part = make_part(center=booking.center, stock=7)

        usage = create_job_part_usage(
            job_card,
            part=part,
            quantity=2,
            status=JobPartUsage.STATUS_CONSUMED,
            actor=booking.center.owner,
            note="Consum in test",
        )

        part.refresh_from_db()
        self.assertEqual(part.stock, 5)
        self.assertEqual(usage.line_total, Decimal("90.00"))

        rollback_job_part_usage(usage, actor=booking.center.owner)
        part.refresh_from_db()
        self.assertEqual(part.stock, 7)
        self.assertFalse(job_card.part_usages.exists())

    def test_build_vehicle_dossier_returns_summary_history_and_open_recommendations(self):
        """Construieste dosarul auto cu sumarul financiar si recomandarile tehnice deschise."""
        booking = make_booking(status=Booking.STATUS_DONE)
        job_card = ensure_job_card(booking, actor=booking.center.owner)[0]
        job_card.final_cost = Decimal("480.00")
        job_card.next_service_date = timezone.localdate() + timezone.timedelta(days=120)
        job_card.save(update_fields=["final_cost", "next_service_date", "updated_at"])
        JobRecommendation.objects.create(
            job_card=job_card,
            title="Schimb placute spate",
            details="Uzura aproape de limita.",
            is_visible_to_customer=True,
            is_resolved=False,
        )

        dossier = build_vehicle_dossier(vin=booking.car_vin, plate=booking.car_plate)

        self.assertEqual(dossier["summary"]["interventions_count"], 1)
        self.assertEqual(dossier["summary"]["total_cost"], Decimal("480.00"))
        self.assertEqual(dossier["summary"]["open_recommendations_count"], 1)
        self.assertEqual(dossier["history"][0], booking)

    def test_build_clients_snapshot_groups_bookings_for_the_same_customer(self):
        """Grupeaza programarile aceluiasi client dupa email si retine sumarul relevant pentru CRM-ul service-ului."""
        first = make_booking(status=Booking.STATUS_DONE)
        second = make_booking(center=first.center, user=first.user, status=Booking.STATUS_CONFIRMED)
        second.client_email = first.client_email
        second.client_phone = first.client_phone
        second.client_name = first.client_name
        second.save(update_fields=["client_email", "client_phone", "client_name", "updated_at"])

        snapshot = build_clients_snapshot(Booking.objects.filter(center=first.center).order_by("-created_at"))

        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot[0]["booking_count"], 2)
        self.assertEqual(snapshot[0]["email"], first.client_email)

    def test_reporting_period_builder_handles_custom_month(self):
        """Construieste corect intervalul raportului pentru o luna selectata explicit."""
        period = build_period({"preset_period": "custom", "month": 3, "year": 2026})
        self.assertEqual(str(period.start), "2026-03-01")
        self.assertEqual(str(period.end), "2026-03-31")
        self.assertEqual(period.group_by, "day")

    def test_dashboard_metrics_include_estimated_revenue_overdue_and_low_stock(self):
        """Calculeaza KPI-urile esentiale din dashboard: venit estimat, restante si stoc critic."""
        center = make_service_center(name="Metrics Service")
        make_part(center=center, stock=1, minimum_stock=2)
        overdue_booking = make_booking(
            center=center,
            status=Booking.STATUS_CONFIRMED,
            booking_date=timezone.localdate() - timezone.timedelta(days=2),
            estimated_price=Decimal("200.00"),
        )
        make_booking(
            center=center,
            status=Booking.STATUS_WAITING_PARTS,
            booking_date=timezone.localdate(),
            estimated_price=Decimal("300.00"),
        )
        invoice = make_invoice(center=center, booking=overdue_booking, status=Invoice.STATUS_FINAL)
        invoice.total = Decimal("100.00")
        invoice.subtotal = Decimal("100.00")
        invoice.save(update_fields=["subtotal", "total", "updated_at"])

        dashboard = build_dashboard_metrics(center.__class__.objects.filter(pk=center.pk))

        self.assertEqual(dashboard["kpis"]["overdue_bookings"], 1)
        self.assertEqual(dashboard["kpis"]["low_stock_count"], 1)
        self.assertEqual(dashboard["kpis"]["estimated_revenue"], Decimal("500"))
        self.assertEqual(dashboard["kpis"]["revenue_this_month"], Decimal("100"))
