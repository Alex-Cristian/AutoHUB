from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking, BookingChecklistItem, BookingNotification
from services.models import ServicePart
from autohub_testutils.factories import make_booking, make_client_user, make_mechanic, make_notification, make_part, make_service_center, make_service_user


class ServiceNotificationsTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="notif-owner")
        self.center = make_service_center(owner=self.owner, name="Notif Service")
        self.booking = make_booking(center=self.center, status=Booking.STATUS_CONFIRMED)
        self.notif = make_notification(recipient=self.owner, booking=self.booking)

    def test_notifications_feed_returns_unread_count_and_latest_items(self):
        """Livreaza feed-ul JSON cu totalul necitit si cele mai recente notificari ale service-ului curent."""
        self.client.force_login(self.owner)

        response = self.client.get(reverse("services:notifications_feed"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["unread_count"], 1)
        self.assertEqual(payload["latest_notifications"][0]["id"], self.notif.pk)

    def test_notifications_feed_requires_service_account(self):
        """Refuza feed-ul de notificari pentru un utilizator care nu detine service."""
        plain_client = make_client_user(username="notif-client")
        self.client.force_login(plain_client)

        response = self.client.get(reverse("services:notifications_feed"))

        self.assertEqual(response.status_code, 403)

    def test_notification_mark_read_marks_only_owners_notification(self):
        """Marcheaza notificarea ca citita doar pentru destinatarul corect."""
        self.client.force_login(self.owner)

        response = self.client.get(reverse("services:notification_read", args=[self.notif.pk]))

        self.assertEqual(response.status_code, 302)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_notifications_page_lists_only_current_service_notifications(self):
        """Pagina dedicata afiseaza doar notificarile destinatarului curent si totalul lor."""
        other_owner = make_service_user(username="notif-page-other")
        make_notification(recipient=other_owner, booking=self.booking)
        self.client.force_login(self.owner)

        response = self.client.get(reverse("services:notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_notifications"], 1)
        self.assertEqual(len(response.context["notifications"]), 1)
        self.assertEqual(response.context["notifications"][0].pk, self.notif.pk)

    def test_notification_mark_read_returns_404_for_foreign_notification(self):
        """Ascunde notificarea altui utilizator chiar daca acesta este autentificat pe alt service."""
        foreign_owner = make_service_user(username="notif-foreign-owner")
        foreign_center = make_service_center(owner=foreign_owner, name="Notif Foreign")
        foreign_booking = make_booking(center=foreign_center, status=Booking.STATUS_CONFIRMED)
        foreign_notif = make_notification(recipient=foreign_owner, booking=foreign_booking)
        self.client.force_login(self.owner)

        response = self.client.get(reverse("services:notification_read", args=[foreign_notif.pk]))

        self.assertEqual(response.status_code, 404)


class ServiceBookingDetailActionTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="actions-owner")
        self.client_user = make_client_user(username="actions-client")
        self.center = make_service_center(owner=self.owner, name="Action Service")
        self.booking = make_booking(center=self.center, user=self.client_user, status=Booking.STATUS_CONFIRMED)
        self.mechanic = make_mechanic(center=self.center, garage=self.booking.garage)
        self.part = make_part(center=self.center, stock=5)

    def test_assign_mechanic_updates_booking_job_card_and_creates_client_notification(self):
        """Alocarea mecanicului sincronizeaza bookingul cu job card-ul si notifica clientul."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:booking_detail", args=[self.booking.pk]),
            {"action": "assign_mechanic", "mechanic": self.mechanic.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.mechanic, self.mechanic)
        self.assertEqual(self.booking.job_card.mechanic, self.mechanic)
        self.assertTrue(
            BookingNotification.objects.filter(
                recipient=self.client_user,
                booking=self.booking,
                title__icontains="mecanic",
            ).exists()
        )

    def test_update_tags_persists_only_valid_operational_tags(self):
        """Salveaza tagurile operationale valide si ignora valorile straine de nomenclator."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:booking_detail", args=[self.booking.pk]),
            {"action": "update_tags", "operational_tags": [Booking.TAG_PRIORITY, "hack"]},
        )

        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.operational_tags, [Booking.TAG_PRIORITY])

    def test_add_and_toggle_checklist_item_work_for_service_owner(self):
        """Permite adaugarea unui pas in checklist si bifarea lui ulterioara."""
        self.client.force_login(self.owner)
        add_response = self.client.post(
            reverse("services:booking_detail", args=[self.booking.pk]),
            {"action": "add_checklist_item", "label": "Verifica presiunea in pneuri"},
        )
        item = BookingChecklistItem.objects.get(booking=self.booking)
        toggle_response = self.client.post(
            reverse("services:booking_detail", args=[self.booking.pk]),
            {"action": "toggle_checklist_item", "item_id": item.pk},
        )

        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(toggle_response.status_code, 302)
        item.refresh_from_db()
        self.assertTrue(item.is_done)
        self.assertIsNotNone(item.completed_at)

    @patch("services.views.validate_booking_media_file", return_value=None)
    def test_add_and_delete_attachment_from_booking_detail(self, mocked_validate_file):
        """Adauga atasamente in booking detail si permite stergerea lor ulterioara."""
        self.client.force_login(self.owner)
        upload = SimpleUploadedFile("poza.png", b"image-bytes", content_type="image/png")

        add_response = self.client.post(
            reverse("services:booking_detail", args=[self.booking.pk]),
            {"action": "add_attachments", "attachments": [upload]},
        )
        attachment = self.booking.attachments.first()
        delete_response = self.client.post(
            reverse("services:booking_detail", args=[self.booking.pk]),
            {"action": "delete_attachment", "attachment_id": attachment.pk},
        )

        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(self.booking.attachments.exists())
        mocked_validate_file.assert_called()


class ServicePartsInventoryExtendedTests(TestCase):
    def setUp(self):
        self.owner = make_service_user(username="parts-extended-owner")
        self.center = make_service_center(owner=self.owner, name="Parts Extended")
        self.part = make_part(center=self.center, stock=4)

    def test_parts_inventory_update_stock_sets_explicit_values(self):
        """Actualizeaza direct stocul si pragul minim pentru o piesa."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:parts_inventory"),
            {"action": "update_stock", "center_id": self.center.pk, "part_id": self.part.pk, "stock": 11, "minimum_stock": 3},
        )

        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock, 11)
        self.assertEqual(self.part.minimum_stock, 3)

    def test_parts_inventory_delete_part_removes_item(self):
        """Sterge piesa din inventar doar pentru service-ul curent."""
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("services:parts_inventory"),
            {"action": "delete_part", "center_id": self.center.pk, "part_id": self.part.pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ServicePart.objects.filter(pk=self.part.pk).exists())
