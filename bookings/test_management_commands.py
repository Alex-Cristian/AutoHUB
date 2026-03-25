from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking, BookingNotification
from autohub_testutils.factories import make_booking, make_service_center


class BookingReminderCommandTests(TestCase):
    @patch("bookings.management.commands.send_booking_reminders.send_booking_reminder_sms", return_value=True)
    def test_send_booking_reminders_marks_only_eligible_bookings(self, mocked_send_sms):
        """Trimite reminder doar pentru programarile eligibile de maine si le marcheaza ca notificate."""
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)
        eligible = make_booking(status=Booking.STATUS_CONFIRMED, booking_date=tomorrow)
        in_progress = make_booking(status=Booking.STATUS_IN_PROGRESS, booking_date=tomorrow)
        pending = make_booking(status=Booking.STATUS_PENDING, booking_date=tomorrow)
        already_sent = make_booking(status=Booking.STATUS_CONFIRMED, booking_date=tomorrow)
        already_sent.reminder_sent_1d = True
        already_sent.save(update_fields=["reminder_sent_1d"])

        out = StringIO()
        call_command("send_booking_reminders", stdout=out)

        eligible.refresh_from_db()
        in_progress.refresh_from_db()
        pending.refresh_from_db()
        already_sent.refresh_from_db()
        self.assertTrue(eligible.reminder_sent_1d)
        self.assertTrue(in_progress.reminder_sent_1d)
        self.assertFalse(pending.reminder_sent_1d)
        self.assertTrue(already_sent.reminder_sent_1d)
        self.assertEqual(mocked_send_sms.call_count, 2)
        self.assertIn("Reminders trimise: 2", out.getvalue())

    @patch("bookings.management.commands.send_booking_reminders.send_booking_reminder_sms", return_value=False)
    def test_send_booking_reminders_keeps_flag_false_when_sms_fails(self, mocked_send_sms):
        """Nu marcheaza reminderul ca trimis daca furnizorul SMS esueaza."""
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)
        booking = make_booking(status=Booking.STATUS_CONFIRMED, booking_date=tomorrow)

        call_command("send_booking_reminders", stdout=StringIO())

        booking.refresh_from_db()
        self.assertFalse(booking.reminder_sent_1d)
        mocked_send_sms.assert_called_once_with(booking)


class StalePendingNotificationCommandTests(TestCase):
    def test_notify_stale_pending_bookings_creates_one_notification_per_old_booking(self):
        """Creeaza notificari pentru bookingurile pending vechi si evita dublurile din aceeasi zi."""
        center = make_service_center()
        old_booking = make_booking(center=center, status=Booking.STATUS_PENDING)
        old_booking.created_at = timezone.now() - timezone.timedelta(hours=30)
        old_booking.save(update_fields=["created_at"])

        fresh_booking = make_booking(center=center, status=Booking.STATUS_PENDING)
        fresh_booking.created_at = timezone.now() - timezone.timedelta(hours=3)
        fresh_booking.save(update_fields=["created_at"])

        duplicate = make_booking(center=center, status=Booking.STATUS_PENDING)
        duplicate.created_at = timezone.now() - timezone.timedelta(hours=30)
        duplicate.save(update_fields=["created_at"])
        BookingNotification.objects.create(
            recipient=center.owner,
            booking=duplicate,
            kind=BookingNotification.KIND_STATUS_UPDATE,
            title=f"Programarea #{duplicate.pk} sta prea mult in pending",
            message="Exista deja notificarea de azi.",
        )

        out = StringIO()
        call_command("notify_stale_pending_bookings", stdout=out)

        notifications = BookingNotification.objects.filter(recipient=center.owner, title__icontains="pending")
        self.assertTrue(notifications.filter(booking=old_booking).exists())
        self.assertFalse(notifications.filter(booking=fresh_booking).exists())
        self.assertEqual(notifications.filter(booking=duplicate).count(), 1)
        self.assertIn("S-au creat 1 notificari", out.getvalue())

