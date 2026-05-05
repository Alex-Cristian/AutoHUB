from datetime import datetime, time
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Car, LegalAcceptance
from bookings.forms import BookingForm, service_open_weekdays
from bookings.ai import heuristic_duration_estimate
from bookings.availability import booking_interval_overlaps
from bookings.files import build_attachment_summary, sanitize_uploaded_filename
from bookings.models import Booking, BookingActivityLog, BookingNotification
from invoices.models import Invoice, InvoiceLine
from services.business import ensure_job_card
from services.models import (
    JobCard,
    JobPartUsage,
    JobRecommendation,
    ServiceCategory,
    ServiceCenter,
    ServiceGarage,
    ServiceMechanic,
    ServicePart,
    StockMovement,
)


User = get_user_model()


def grant_legal_acceptance(user):
    LegalAcceptance.objects.create(
        user=user,
        document_set='platform',
        terms_version=settings.LEGAL_DOCUMENTS_VERSION,
        privacy_version=settings.LEGAL_DOCUMENTS_VERSION,
        cookies_version=settings.LEGAL_DOCUMENTS_VERSION,
    )


def create_center_with_garage(owner):
    category = ServiceCategory.objects.create(name='Diagnoza', slug='diagnoza')
    center = ServiceCenter.objects.create(
        owner=owner,
        name='Service Booking',
        category=category,
        description='Descriere',
        address='Str. Test 11',
        city='bucuresti',
        phone='0700000001',
        email='servicebooking@example.com',
    )
    center.categories.add(category)
    garage = ServiceGarage.objects.create(
        center=center,
        name='Garaj principal',
        category=category,
        open_time=time(8, 0),
        close_time=time(18, 0),
        slot_minutes=60,
    )
    return center, garage


class BookingQuoteFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='serviceowner', password='pass12345')
        self.client_user = User.objects.create_user(username='clientflow', password='pass12345')
        grant_legal_acceptance(self.owner)
        grant_legal_acceptance(self.client_user)
        self.center, self.garage = create_center_with_garage(self.owner)
        self.booking = Booking.objects.create(
            user=self.client_user,
            center=self.center,
            garage=self.garage,
            client_name='Client Flow',
            client_phone='0722222222',
            client_email='clientflow@example.com',
            car_brand='VW',
            car_model='Golf',
            car_year=2021,
            car_fuel='benzina',
            car_plate='B22FLOW',
            car_vin='WVWZZZ1KZAW000001',
            problem_description='Revizie si verificare frane',
            booking_date=timezone.localdate() + timezone.timedelta(days=2),
            booking_time=time(11, 0),
            duration_minutes=60,
            status=Booking.STATUS_QUOTED,
            estimated_price=250,
        )

    def test_client_can_accept_quote(self):
        """Verifica faptul ca un client poate accepta o oferta si service-ul primeste notificare."""
        self.client.force_login(self.client_user)

        response = self.client.post(reverse('bookings:accept_quote', args=[self.booking.pk]))

        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_CONFIRMED)
        self.assertTrue(
            BookingNotification.objects.filter(
                recipient=self.owner,
                booking=self.booking,
                kind=BookingNotification.KIND_STATUS_UPDATE,
            ).exists()
        )

    def test_client_can_reject_quote(self):
        """Verifica faptul ca un client poate refuza o oferta si programarea devine anulata."""
        self.client.force_login(self.client_user)

        response = self.client.post(reverse('bookings:reject_quote', args=[self.booking.pk]))

        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_CANCELLED)

    def _make_pending_booking(self, *, booking_time_value=time(11, 0), duration_minutes=60):
        return Booking.objects.create(
            user=self.client_user,
            center=self.center,
            garage=self.garage,
            client_name='Client Pending',
            client_phone='0733333333',
            client_email='pending@example.com',
            car_brand='VW',
            car_model='Golf',
            car_year=2021,
            car_fuel='benzina',
            car_plate='B33PEND',
            car_vin='WVWZZZ1KZAW000033',
            problem_description='Diagnoza zgomot',
            booking_date=timezone.localdate() + timezone.timedelta(days=4),
            booking_time=booking_time_value,
            duration_minutes=duration_minutes,
            status=Booking.STATUS_PENDING,
        )

    def _make_confirmed_booking(self, *, booking_date, booking_time_value=time(12, 0), duration_minutes=60):
        return Booking.objects.create(
            user=self.client_user,
            center=self.center,
            garage=self.garage,
            client_name='Client Confirmed',
            client_phone='0744444444',
            client_email='confirmed@example.com',
            car_brand='Skoda',
            car_model='Octavia',
            car_year=2020,
            car_fuel='benzina',
            car_plate='B44CONF',
            car_vin='TMBZZZ1KZAW000044',
            problem_description='Revizie',
            booking_date=booking_date,
            booking_time=booking_time_value,
            duration_minutes=duration_minutes,
            status=Booking.STATUS_CONFIRMED,
        )

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_real_duration_lte_ai_keeps_quote_flow_unchanged(self, *_mocked):
        booking = self._make_pending_booking(duration_minutes=60)
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:booking_accept', args=[booking.pk]), {
            'duration_minutes': '60',
            'estimated_price': '300',
        })

        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_QUOTED)
        self.assertFalse(booking.needs_client_reschedule)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_real_duration_gt_ai_without_overlap_keeps_quote_flow_unchanged(self, *_mocked):
        booking = self._make_pending_booking(duration_minutes=60)
        self._make_confirmed_booking(booking_date=booking.booking_date, booking_time_value=time(15, 0))
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:booking_accept', args=[booking.pk]), {
            'duration_minutes': '120',
            'estimated_price': '450',
        })

        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_QUOTED)
        self.assertFalse(booking.needs_client_reschedule)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_real_duration_gt_ai_with_overlap_requires_client_reschedule(self, *_mocked):
        booking = self._make_pending_booking(duration_minutes=60)
        self._make_confirmed_booking(booking_date=booking.booking_date, booking_time_value=time(12, 0))
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:booking_accept', args=[booking.pk]), {
            'duration_minutes': '120',
            'estimated_price': '450',
        })

        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_QUOTED)
        self.assertTrue(booking.needs_client_reschedule)

    def test_client_cannot_accept_quote_before_required_reschedule(self):
        self.booking.needs_client_reschedule = True
        self.booking.save(update_fields=['needs_client_reschedule'])
        self.client.force_login(self.client_user)

        response = self.client.post(reverse('bookings:accept_quote', args=[self.booking.pk]))

        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_QUOTED)
        self.assertTrue(self.booking.needs_client_reschedule)

    def test_client_reschedules_to_available_slot_then_can_accept_quote(self):
        self.booking.needs_client_reschedule = True
        self.booking.duration_minutes = 120
        self.booking.save(update_fields=['needs_client_reschedule', 'duration_minutes'])
        new_date = self.booking.booking_date + timezone.timedelta(days=1)
        self.client.force_login(self.client_user)

        response = self.client.post(reverse('bookings:reschedule_quote', args=[self.booking.pk]), {
            'booking_date': new_date.isoformat(),
            'booking_time': '09:00',
        })

        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertFalse(self.booking.needs_client_reschedule)
        self.assertEqual(self.booking.booking_date, new_date)
        self.assertEqual(self.booking.booking_time, time(9, 0))

        response = self.client.post(reverse('bookings:accept_quote', args=[self.booking.pk]))
        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_CONFIRMED)

    def test_client_reschedule_rejects_slot_that_became_unavailable(self):
        self.booking.needs_client_reschedule = True
        self.booking.duration_minutes = 120
        self.booking.save(update_fields=['needs_client_reschedule', 'duration_minutes'])
        self._make_confirmed_booking(booking_date=self.booking.booking_date, booking_time_value=time(9, 30))
        self.client.force_login(self.client_user)

        response = self.client.post(reverse('bookings:reschedule_quote', args=[self.booking.pk]), {
            'booking_date': self.booking.booking_date.isoformat(),
            'booking_time': '09:00',
        })

        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertTrue(self.booking.needs_client_reschedule)
        self.assertNotEqual(self.booking.booking_time, time(9, 0))


class BookingRescheduleOfferFlowVerboseTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='verboseowner', password='pass12345')
        self.client_user = User.objects.create_user(username='verboseclient', password='pass12345')
        grant_legal_acceptance(self.owner)
        grant_legal_acceptance(self.client_user)
        self.center, self.garage = create_center_with_garage(self.owner)
        self.service_offer_url_name = 'services:booking_accept'

    def _log(self, test_name, setup, action, expected, result, passed=True):
        print(f'\n[TEST] {test_name}')
        print(f'[SETUP] {setup}')
        print(f'[ACTION] {action}')
        print(f'[EXPECTED] {expected}')
        print(f'[RESULT] {result}')
        print('[PASS]' if passed else '[FAIL]')

    def _make_booking(
        self,
        *,
        status=Booking.STATUS_PENDING,
        booking_date=None,
        booking_time_value=time(10, 0),
        duration_minutes=60,
        plate='B00FLOW',
        vin='WVWZZZ1KZAW100000',
        user=None,
    ):
        return Booking.objects.create(
            user=user if user is not None else self.client_user,
            center=self.center,
            garage=self.garage,
            client_name='Client Flow Verbose',
            client_phone='0722000000',
            client_email='flow.verbose@example.com',
            car_brand='VW',
            car_model='Golf',
            car_year=2021,
            car_fuel='benzina',
            car_plate=plate,
            car_vin=vin,
            problem_description='Zgomot la franare si cerere oferta.',
            booking_date=booking_date or timezone.localdate() + timezone.timedelta(days=5),
            booking_time=booking_time_value,
            duration_minutes=duration_minutes,
            status=status,
            estimated_price=250 if status == Booking.STATUS_QUOTED else None,
        )

    def _send_offer(self, booking, service_duration, price='450'):
        self.client.force_login(self.owner)
        return self.client.post(reverse(self.service_offer_url_name, args=[booking.pk]), {
            'duration_minutes': str(service_duration),
            'estimated_price': price,
        })

    def _accept_offer(self, booking):
        self.client.force_login(self.client_user)
        return self.client.post(reverse('bookings:accept_quote', args=[booking.pk]), follow=True)

    def _reschedule_offer(self, booking, new_date, new_time):
        self.client.force_login(self.client_user)
        return self.client.post(reverse('bookings:reschedule_quote', args=[booking.pk]), {
            'booking_date': new_date.isoformat(),
            'booking_time': new_time.strftime('%H:%M'),
        }, follow=True)

    def _message_text(self, response):
        return ' '.join(str(message) for message in response.context['messages'])

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_01_real_duration_equal_to_ai_allows_direct_accept(self, *_mocked):
        booking = self._make_booking(duration_minutes=60, booking_time_value=time(10, 0), plate='B01EQL', vin='WVWZZZ1KZAW100001')

        self._send_offer(booking, 60)
        booking.refresh_from_db()
        accept_response = self._accept_offer(booking)
        booking.refresh_from_db()

        passed = (
            booking.needs_client_reschedule is False
            and booking.status == Booking.STATUS_CONFIRMED
            and accept_response.status_code == 200
        )
        self._log(
            'Durata reala = durata AI -> acceptare directa',
            'AI duration: 60 min, service duration: 60 min, selected slot: 10:00-11:00, no active conflict',
            'Service sends offer, client accepts offer',
            'needs_client_reschedule = false, status becomes confirmed',
            f'needs_client_reschedule = {booking.needs_client_reschedule}, status = {booking.status}',
            passed,
        )
        self.assertTrue(passed)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_02_real_duration_lower_than_ai_keeps_old_flow(self, *_mocked):
        booking = self._make_booking(duration_minutes=90, booking_time_value=time(10, 0), plate='B02LOW', vin='WVWZZZ1KZAW100002')

        self._send_offer(booking, 60)
        booking.refresh_from_db()
        accept_response = self._accept_offer(booking)
        booking.refresh_from_db()

        passed = (
            booking.needs_client_reschedule is False
            and booking.duration_minutes == 60
            and booking.status == Booking.STATUS_CONFIRMED
            and accept_response.status_code == 200
        )
        self._log(
            'Durata reala < durata AI -> flow vechi',
            'AI duration: 90 min, service duration: 60 min, selected slot: 10:00-11:30, no active conflict',
            'Service sends shorter offer, client accepts offer',
            'No reschedule, duration is updated to 60 min, status becomes confirmed',
            f'needs_client_reschedule = {booking.needs_client_reschedule}, duration = {booking.duration_minutes}, status = {booking.status}',
            passed,
        )
        self.assertTrue(passed)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_03_real_duration_greater_without_overlap_allows_direct_accept(self, *_mocked):
        booking = self._make_booking(duration_minutes=60, booking_time_value=time(10, 0), plate='B03NOO', vin='WVWZZZ1KZAW100003')

        self._send_offer(booking, 90)
        booking.refresh_from_db()
        end_time = booking.get_end_datetime().time()
        accept_response = self._accept_offer(booking)
        booking.refresh_from_db()

        passed = (
            booking.needs_client_reschedule is False
            and booking.duration_minutes == 90
            and end_time == time(11, 30)
            and booking.status == Booking.STATUS_CONFIRMED
            and accept_response.status_code == 200
        )
        self._log(
            'Durata reala > durata AI fara overlap -> acceptare directa',
            'AI duration: 60 min, service duration: 90 min, selected slot: 10:00-11:00, no appointment between 11:00 and 11:30',
            'Service sends offer, client accepts offer',
            'No reschedule, booking interval becomes 10:00-11:30, status becomes confirmed',
            f'needs_client_reschedule = {booking.needs_client_reschedule}, interval_end = {end_time.strftime("%H:%M")}, status = {booking.status}',
            passed,
        )
        self.assertTrue(passed)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_04_real_duration_greater_with_future_overlap_requires_reschedule(self, *_mocked):
        booking = self._make_booking(duration_minutes=60, booking_time_value=time(10, 0), plate='B04OVR', vin='WVWZZZ1KZAW100004')
        self._make_booking(
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking.booking_date,
            booking_time_value=time(11, 0),
            duration_minutes=60,
            plate='B04ACT',
            vin='WVWZZZ1KZAW100014',
        )

        self._send_offer(booking, 90)
        booking.refresh_from_db()
        accept_response = self._accept_offer(booking)
        booking.refresh_from_db()

        passed = (
            booking.needs_client_reschedule is True
            and booking.status == Booking.STATUS_QUOTED
            and 'Alege un nou interval disponibil' in self._message_text(accept_response)
        )
        self._log(
            'Durata reala > durata AI + overlap -> necesita reprogramare',
            'AI duration: 60 min, service duration: 90 min, selected slot: 10:00-11:00, existing active appointment: 11:00-12:00',
            'Service sends offer, client tries direct accept',
            'needs_client_reschedule = true, direct accept is blocked, status remains quoted',
            f'needs_client_reschedule = {booking.needs_client_reschedule}, status = {booking.status}, accept_blocked = {"Alege un nou interval disponibil" in self._message_text(accept_response)}',
            passed,
        )
        self.assertTrue(passed)

    def test_05_server_refuses_accept_without_reschedule(self):
        booking = self._make_booking(status=Booking.STATUS_QUOTED, duration_minutes=90, plate='B05BLK', vin='WVWZZZ1KZAW100005')
        booking.needs_client_reschedule = True
        booking.save(update_fields=['needs_client_reschedule'])

        accept_response = self._accept_offer(booking)
        booking.refresh_from_db()

        passed = (
            booking.status == Booking.STATUS_QUOTED
            and booking.needs_client_reschedule is True
            and 'Alege un nou interval disponibil' in self._message_text(accept_response)
        )
        self._log(
            'Acceptare fara reprogramare -> refuz server-side',
            'Offer status: quoted, needs_client_reschedule: true, service duration: 90 min',
            'Client posts accept_quote without selecting a new slot',
            'Server rejects accept, clear message is returned, status does not become confirmed',
            f'status = {booking.status}, needs_client_reschedule = {booking.needs_client_reschedule}, message_present = {"Alege un nou interval disponibil" in self._message_text(accept_response)}',
            passed,
        )
        self.assertTrue(passed)

    def test_06_client_reschedules_to_available_slot_using_real_duration_then_accepts(self):
        booking = self._make_booking(status=Booking.STATUS_QUOTED, duration_minutes=90, plate='B06AVL', vin='WVWZZZ1KZAW100006')
        booking.needs_client_reschedule = True
        booking.save(update_fields=['needs_client_reschedule'])
        new_date = booking.booking_date + timezone.timedelta(days=1)

        reschedule_response = self._reschedule_offer(booking, new_date, time(13, 0))
        booking.refresh_from_db()
        overlap_after_reschedule = booking_interval_overlaps(
            booking.center_id,
            datetime.combine(booking.booking_date, booking.booking_time),
            booking.duration_minutes,
            appointment_id=booking.pk,
        )
        accept_response = self._accept_offer(booking)
        booking.refresh_from_db()

        passed = (
            booking.booking_date == new_date
            and booking.booking_time == time(13, 0)
            and booking.duration_minutes == 90
            and booking.needs_client_reschedule is False
            and overlap_after_reschedule is False
            and booking.status == Booking.STATUS_CONFIRMED
            and reschedule_response.status_code == 200
            and accept_response.status_code == 200
        )
        self._log(
            'Reprogramare pe slot liber cu durata reala -> acceptare posibila',
            'Offer requires reschedule, service duration: 90 min, new selected slot: 13:00-14:30, no conflict',
            'Client saves new slot, then accepts quote',
            'Slot is saved, reschedule flag false, no overlap is created, status becomes confirmed',
            f'new_time = {booking.booking_time.strftime("%H:%M")}, duration = {booking.duration_minutes}, needs_client_reschedule = {booking.needs_client_reschedule}, overlap = {overlap_after_reschedule}, status = {booking.status}',
            passed,
        )
        self.assertTrue(passed)

    def test_07_client_reschedule_rejects_slot_without_enough_real_duration_room(self):
        booking = self._make_booking(status=Booking.STATUS_QUOTED, duration_minutes=90, plate='B07FUL', vin='WVWZZZ1KZAW100007')
        booking.needs_client_reschedule = True
        booking.save(update_fields=['needs_client_reschedule'])
        self._make_booking(
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking.booking_date,
            booking_time_value=time(14, 0),
            duration_minutes=60,
            plate='B07ACT',
            vin='WVWZZZ1KZAW100017',
        )

        response = self._reschedule_offer(booking, booking.booking_date, time(13, 0))
        booking.refresh_from_db()

        passed = (
            booking.needs_client_reschedule is True
            and booking.booking_time != time(13, 0)
            and 'Intervalul ales nu mai este disponibil' in self._message_text(response)
        )
        self._log(
            'Reprogramare pe slot prea scurt -> refuz server-side',
            'Offer requires reschedule, service duration: 90 min, requested slot: 13:00-14:30, existing active appointment: 14:00-15:00',
            'Client posts reschedule_quote for 13:00',
            'Server rejects slot, client must choose another slot, booking remains in reschedule state',
            f'needs_client_reschedule = {booking.needs_client_reschedule}, saved_time = {booking.booking_time.strftime("%H:%M")}, message_present = {"Intervalul ales nu mai este disponibil" in self._message_text(response)}',
            passed,
        )
        self.assertTrue(passed)

    def test_08_slot_available_in_ui_becomes_unavailable_before_save(self):
        booking = self._make_booking(status=Booking.STATUS_QUOTED, duration_minutes=90, plate='B08RCE', vin='WVWZZZ1KZAW100008')
        booking.needs_client_reschedule = True
        booking.save(update_fields=['needs_client_reschedule'])
        self.client.force_login(self.client_user)
        slots_response = self.client.get(reverse('bookings:garage_slots', args=[self.center.slug]), {
            'garage': self.garage.pk,
            'date': booking.booking_date.isoformat(),
            'duration': '90',
        })
        ui_slots = slots_response.json()['slots']
        self.assertIn('13:00', ui_slots)
        self._make_booking(
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking.booking_date,
            booking_time_value=time(14, 0),
            duration_minutes=60,
            plate='B08NEW',
            vin='WVWZZZ1KZAW100018',
        )

        response = self._reschedule_offer(booking, booking.booking_date, time(13, 0))
        booking.refresh_from_db()
        conflict_count = Booking.objects.filter(
            center=self.center,
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking.booking_date,
            booking_time=time(13, 0),
        ).count()

        passed = (
            booking.needs_client_reschedule is True
            and booking.booking_time != time(13, 0)
            and conflict_count == 0
            and 'Intervalul ales nu mai este disponibil' in self._message_text(response)
        )
        self._log(
            'Race condition: slot din UI devine indisponibil inainte de salvare',
            'UI loaded 13:00 as available for 90 min; before save, another active appointment appears at 14:00-15:00',
            'Client posts reschedule_quote for stale 13:00 slot',
            'Server rechecks availability, rejects save, asks for another slot, no overlapping confirmed booking is created',
            f'ui_had_13 = {"13:00" in ui_slots}, saved_time = {booking.booking_time.strftime("%H:%M")}, needs_client_reschedule = {booking.needs_client_reschedule}, overlapping_confirmed_at_13 = {conflict_count}',
            passed,
        )
        self.assertTrue(passed)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_09_current_booking_is_excluded_from_overlap_check(self, *_mocked):
        booking = self._make_booking(duration_minutes=60, booking_time_value=time(10, 0), plate='B09SELF', vin='WVWZZZ1KZAW100009')

        self._send_offer(booking, 90)
        booking.refresh_from_db()

        passed = (
            booking.status == Booking.STATUS_QUOTED
            and booking.duration_minutes == 90
            and booking.needs_client_reschedule is False
        )
        self._log(
            'Programarea curenta este exclusa din overlap',
            'AI duration: 60 min, service duration: 90 min, selected slot: 10:00-11:00, no other appointments',
            'Service sends offer; overlap helper excludes current booking id',
            'No reschedule is required only because the booking overlaps its own original slot',
            f'status = {booking.status}, duration = {booking.duration_minutes}, needs_client_reschedule = {booking.needs_client_reschedule}',
            passed,
        )
        self.assertTrue(passed)

    @patch('services.views.send_booking_confirmation_sms', return_value=False)
    @patch('services.views.send_booking_quote_email', return_value=True)
    def test_10_cancelled_bookings_do_not_block_real_duration(self, *_mocked):
        booking = self._make_booking(duration_minutes=60, booking_time_value=time(10, 0), plate='B10CAN', vin='WVWZZZ1KZAW100010')
        self._make_booking(
            status=Booking.STATUS_CANCELLED,
            booking_date=booking.booking_date,
            booking_time_value=time(11, 0),
            duration_minutes=60,
            plate='B10OLD',
            vin='WVWZZZ1KZAW100020',
        )

        self._send_offer(booking, 90)
        booking.refresh_from_db()

        passed = (
            booking.status == Booking.STATUS_QUOTED
            and booking.needs_client_reschedule is False
            and booking.duration_minutes == 90
        )
        self._log(
            'Programarile anulate/respinse nu blocheaza disponibilitatea',
            'AI duration: 60 min, service duration: 90 min, selected slot: 10:00-11:00, cancelled appointment: 11:00-12:00',
            'Service sends offer',
            'Cancelled appointment is ignored, no reschedule required',
            f'cancelled_conflict_ignored = {not booking.needs_client_reschedule}, status = {booking.status}, duration = {booking.duration_minutes}',
            passed,
        )
        self.assertTrue(passed)

    def test_11_ui_hides_accept_button_and_shows_reschedule_calendar(self):
        booking = self._make_booking(status=Booking.STATUS_QUOTED, duration_minutes=90, plate='B11UIR', vin='WVWZZZ1KZAW100011')
        booking.needs_client_reschedule = True
        booking.save(update_fields=['needs_client_reschedule'])
        self.client.force_login(self.client_user)

        response = self.client.get(reverse('bookings:my_bookings'))
        html = response.content.decode('utf-8')

        passed = (
            'client-reschedule-required-message' in html
            and 'client-reschedule-form' in html
            and 'client-accept-quote-button' not in html
            and f'data-duration="{booking.duration_minutes}"' in html
        )
        self._log(
            'UI: acceptarea este ascunsa cand reprogramarea este obligatorie',
            'Client has quoted offer with needs_client_reschedule = true and service duration = 90 min',
            'Client opens /bookings/programarile-mele/',
            'Reschedule message and calendar are visible, accept button is not available',
            f'message_visible = {"client-reschedule-required-message" in html}, calendar_visible = {"client-reschedule-form" in html}, accept_button_present = {"client-accept-quote-button" in html}, data_duration = {booking.duration_minutes}',
            passed,
        )
        self.assertTrue(passed)

    def test_12_reschedule_calendar_and_server_use_real_service_duration(self):
        booking = self._make_booking(status=Booking.STATUS_QUOTED, duration_minutes=120, plate='B12DUR', vin='WVWZZZ1KZAW100012')
        booking.needs_client_reschedule = True
        booking.save(update_fields=['needs_client_reschedule'])
        self._make_booking(
            status=Booking.STATUS_CONFIRMED,
            booking_date=booking.booking_date,
            booking_time_value=time(14, 0),
            duration_minutes=60,
            plate='B12ACT',
            vin='WVWZZZ1KZAW100022',
        )
        self.client.force_login(self.client_user)

        slots_response = self.client.get(reverse('bookings:garage_slots', args=[self.center.slug]), {
            'garage': self.garage.pk,
            'date': booking.booking_date.isoformat(),
            'duration': str(booking.duration_minutes),
        })
        real_duration_slots = slots_response.json()['slots']
        response = self._reschedule_offer(booking, booking.booking_date, time(13, 0))
        booking.refresh_from_db()

        passed = (
            '13:00' not in real_duration_slots
            and booking.needs_client_reschedule is True
            and booking.booking_time != time(13, 0)
            and 'Intervalul ales nu mai este disponibil' in self._message_text(response)
        )
        self._log(
            'Calendarul de reprogramare foloseste durata reala a service-ului',
            'AI duration: 60 min, service duration: 120 min, candidate slot: 13:00, existing active appointment: 14:00-15:00',
            'Client loads garage slots with duration=120, then server-side save is attempted for 13:00',
            '13:00 is not returned for 120 min and is rejected server-side; a 60-min-only gap is not accepted',
            f'13_in_slots_for_120 = {"13:00" in real_duration_slots}, saved_time = {booking.booking_time.strftime("%H:%M")}, needs_client_reschedule = {booking.needs_client_reschedule}, message_present = {"Intervalul ales nu mai este disponibil" in self._message_text(response)}',
            passed,
        )
        self.assertTrue(passed)


class BookingDurationEstimateTests(TestCase):
    def test_detects_planetara_case_from_free_text(self):
        estimate = heuristic_duration_estimate("bataie la planetare")

        self.assertEqual(estimate["minutes"], 180)
        self.assertIn(estimate["source"], {"catalog", "openai", "category_fallback", "fallback"})
        self.assertEqual(estimate["operation_slug"], "planetara_transmisie")

    def test_detects_alternator_pulley_even_with_typo(self):
        estimate = heuristic_duration_estimate("schibare fulie alternator")

        self.assertEqual(estimate["minutes"], 120)
        self.assertEqual(estimate["operation_slug"], "alternator_fulie_accesorii")

    def test_service_category_hint_avoids_generic_sixty_minutes(self):
        estimate = heuristic_duration_estimate("", service_name="Vopsitorie bara spate")

        self.assertEqual(estimate["minutes"], 240)
        self.assertEqual(estimate["operation_slug"], "tinichigerie_vopsitorie")

    def test_history_feedback_adjusts_estimate_from_completed_jobs(self):
        owner = User.objects.create_user(username='historyowner', password='pass12345')
        center, garage = create_center_with_garage(owner)
        for idx in range(3):
            booking = Booking.objects.create(
                center=center,
                garage=garage,
                client_name=f'Client {idx}',
                client_phone=f'070000000{idx}',
                client_email=f'client{idx}@example.com',
                car_brand='VW',
                car_model='Golf',
                car_year=2020,
                car_fuel='benzina',
                car_plate=f'B00HIS{idx}',
                car_vin=f'WVWZZZ1KZAW00010{idx}',
                problem_description='schimbare fulie alternator',
                booking_date=timezone.localdate() + timezone.timedelta(days=idx + 1),
                booking_time=time(9, 0),
                duration_minutes=120,
                estimated_operation_slug='alternator_fulie_accesorii',
                estimated_operation_label='Alternator / fulie / curea accesorii',
                duration_estimate_source='catalog',
                status=Booking.STATUS_DONE,
            )
            JobCard.objects.create(
                booking=booking,
                center=center,
                status=JobCard.STATUS_COMPLETED,
                actual_hours='3.00',
            )

        estimate = heuristic_duration_estimate('schimbare fulie alternator')

        self.assertEqual(estimate["operation_slug"], "alternator_fulie_accesorii")
        self.assertEqual(estimate["history_sample_count"], 3)
        self.assertEqual(estimate["history_minutes"], 180)
        self.assertEqual(estimate["minutes"], 150)


class BookingScheduleValidationTests(TestCase):
    def test_service_open_weekdays_defaults_to_weekdays(self):
        self.assertEqual(service_open_weekdays('Lun-Vin: 08:00-18:00'), {0, 1, 2, 3, 4})
        self.assertEqual(service_open_weekdays('Lun-Sam: 08:00-18:00'), {0, 1, 2, 3, 4, 5})
        self.assertEqual(service_open_weekdays('Non-stop 24/7'), {0, 1, 2, 3, 4, 5, 6})

    def test_form_rejects_closed_weekend_day(self):
        owner = User.objects.create_user(username='weekowner', password='pass12345')
        center, garage = create_center_with_garage(owner)
        center.schedule = 'Lun-Vin: 08:00-18:00'
        center.save(update_fields=['schedule'])

        saturday = timezone.localdate()
        while saturday.weekday() != 5:
            saturday += timezone.timedelta(days=1)

        form = BookingForm(center=center, data={
            'client_name': 'Client Weekend',
            'client_phone': '0711111111',
            'client_email': 'weekend@example.com',
            'car_brand': 'VW',
            'car_model': 'Golf',
            'car_year': 2020,
            'car_fuel': 'benzina',
            'car_plate': 'B11WKD',
            'car_vin': 'WVWZZZ1KZAW000111',
            'problem_description': 'Diagnoza generala',
            'garage': garage.pk,
            'booking_date': saturday.isoformat(),
            'booking_time': '10:00',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('booking_date', form.errors)


class BookingFormValidationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='ownerform', password='pass12345')
        self.center, self.garage = create_center_with_garage(self.owner)

    def test_booking_form_rejects_invalid_vin(self):
        """Verifica validarea VIN-ului in formularul de programare."""
        form = BookingForm(center=self.center, data={
            'client_name': 'Test Client',
            'client_phone': '0711111111',
            'client_email': 'testclient@example.com',
            'car_brand': 'Dacia',
            'car_model': 'Logan',
            'car_year': timezone.now().year,
            'car_fuel': 'benzina',
            'car_plate': 'B123AAA',
            'car_vin': 'SHORTVIN',
            'garage': self.garage.pk,
            'problem_description': 'Revizie',
            'booking_date': (timezone.localdate() + timezone.timedelta(days=1)).isoformat(),
            'booking_time': '10:00',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('car_vin', form.errors)

    def test_booking_model_rejects_mechanic_overlap(self):
        """Verifica blocarea suprapunerii de interval pentru acelasi mecanic."""
        mechanic = ServiceMechanic.objects.create(center=self.center, name='Mihai')
        second_garage = ServiceGarage.objects.create(
            center=self.center,
            name='Garaj secundar',
            category=self.center.category,
            open_time=time(8, 0),
            close_time=time(18, 0),
            slot_minutes=60,
        )
        Booking.objects.create(
            center=self.center,
            garage=self.garage,
            mechanic=mechanic,
            client_name='Client One',
            client_phone='0700000000',
            client_email='one@example.com',
            car_brand='Audi',
            car_model='A4',
            car_year=2020,
            car_fuel='benzina',
            car_plate='B11AAA',
            car_vin='WVWZZZ1KZAW000011',
            problem_description='Revizie',
            booking_date=timezone.localdate() + timezone.timedelta(days=1),
            booking_time=time(10, 0),
            duration_minutes=60,
            status=Booking.STATUS_CONFIRMED,
        )
        overlapping = Booking(
            center=self.center,
            garage=second_garage,
            mechanic=mechanic,
            client_name='Client Two',
            client_phone='0700000001',
            client_email='two@example.com',
            car_brand='BMW',
            car_model='320',
            car_year=2022,
            car_fuel='benzina',
            car_plate='B22BBB',
            car_vin='WVWZZZ1KZAW000012',
            problem_description='Diagnoza',
            booking_date=timezone.localdate() + timezone.timedelta(days=1),
            booking_time=time(10, 30),
            duration_minutes=60,
            status=Booking.STATUS_CONFIRMED,
        )

        with self.assertRaisesMessage(ValidationError, 'Mecanicul selectat este deja alocat'):
            overlapping.full_clean()


class BookingFilesTests(TestCase):
    def test_sanitize_uploaded_filename_keeps_only_basename(self):
        """Elimina calea trimisa de unele browsere sau tool-uri de upload."""
        self.assertEqual(
            sanitize_uploaded_filename(r"C:\Users\client\Pictures\WhatsApp Image 2026-03-26 at 23.08.09.jpeg"),
            "WhatsApp Image 2026-03-26 at 23.08.09.jpeg",
        )
        self.assertEqual(
            sanitize_uploaded_filename("/tmp/uploads/poza-masina.png"),
            "poza-masina.png",
        )

    def test_build_attachment_summary_uses_simple_plural_for_images(self):
        """Mesajul din istoric ramane scurt si usor de citit pentru poze multiple."""
        self.assertEqual(
            build_attachment_summary(actor_label="Clientul", count=3, image_count=3, video_count=0),
            "Clientul a adaugat 3 poze.",
        )


class BookingIntegratedPlatformTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner-int', password='pass12345')
        self.client_user = User.objects.create_user(username='client-int', password='pass12345')
        grant_legal_acceptance(self.owner)
        grant_legal_acceptance(self.client_user)
        self.center, self.garage = create_center_with_garage(self.owner)
        self.mechanic = ServiceMechanic.objects.create(
            center=self.center,
            name='Mecanic Integrat',
            specialization='Mecanica generala',
        )
        self.part = ServicePart.objects.create(
            center=self.center,
            name='Filtru ulei premium',
            part_number='FOP-1',
            category='consumabile',
            brand='Mann',
            supplier='Inter Cars',
            stock=8,
            minimum_stock=2,
            price=Decimal('45.00'),
            purchase_price=Decimal('30.00'),
            sale_price=Decimal('45.00'),
            unit='buc',
        )
        self.booking = Booking.objects.create(
            user=self.client_user,
            center=self.center,
            garage=self.garage,
            mechanic=self.mechanic,
            client_name='Client Integrat',
            client_phone='0723000000',
            client_email='client.integrat@example.com',
            car_brand='Skoda',
            car_model='Octavia',
            car_year=2020,
            car_fuel='motorina',
            car_plate='B88INT',
            car_vin='WVWZZZ1KZAW000088',
            problem_description='Revizie completa si verificare franare',
            booking_date=timezone.localdate() + timezone.timedelta(days=2),
            booking_time=time(9, 0),
            duration_minutes=90,
            estimated_price=Decimal('420.00'),
            status=Booking.STATUS_CONFIRMED,
        )
        self.car = Car.objects.create(
            owner=self.client_user,
            make='Skoda',
            model='Octavia',
            year=2020,
            fuel='motorina',
            plate_number='B88INT',
            vin='WVWZZZ1KZAW000088',
        )

    def _prepare_completed_job(self):
        job_card, _ = ensure_job_card(self.booking, actor=self.owner)
        job_card.status = 'completed'
        job_card.mechanic = self.mechanic
        job_card.estimated_cost = Decimal('420.00')
        job_card.final_cost = Decimal('515.00')
        job_card.mileage = 154000
        job_card.next_service_km = 164000
        job_card.next_service_date = timezone.localdate() + timezone.timedelta(days=120)
        job_card.customer_notes = 'Lucrarea este gata pentru ridicare.'
        job_card.save()
        JobRecommendation.objects.create(
            job_card=job_card,
            title='Schimb placute frana spate in urmatoarea luna',
            details='Uzura este aproape de limita recomandata.',
            priority='medium',
            is_visible_to_customer=True,
        )
        self.booking.status = Booking.STATUS_DONE
        self.booking.save(update_fields=['status', 'updated_at'])

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
        )
        invoice.assign_next_number_if_needed()
        invoice.save(update_fields=['invoice_no'])
        InvoiceLine.objects.create(
            invoice=invoice,
            description='Revizie completa',
            quantity=1,
            unit_price=Decimal('515.00'),
        )
        invoice.recalc_totals(save=True)
        return job_card, invoice

    def test_service_can_save_job_card_and_sync_booking_status_to_waiting_parts(self):
        """Verifica sincronizarea dintre fisa lucrarii, statusul programarii si tag-ul de asteptare piese."""
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:booking_detail', args=[self.booking.pk]), {
            'action': 'save_job_card',
            'status': 'waiting_parts',
            'mechanic': self.mechanic.pk,
            'mileage': 152340,
            'estimated_hours': '2.50',
            'actual_hours': '',
            'estimated_cost': '420.00',
            'final_cost': '',
            'diagnostic_summary': 'Lipseste o piesa din stoc.',
            'work_performed': 'Constatare si verificare initiala.',
            'customer_notes': 'Te anuntam imediat ce ajunge piesa.',
            'internal_notes': 'Rezervam intervalul dupa confirmarea livrarii.',
            'next_service_date': '',
            'next_service_km': '',
        })

        self.assertRedirects(response, reverse('services:booking_detail', args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_WAITING_PARTS)
        self.assertIn(Booking.TAG_WAITING_PART, self.booking.operational_tags)
        self.assertEqual(self.booking.job_card.status, 'waiting_parts')
        self.assertTrue(
            BookingActivityLog.objects.filter(
                booking=self.booking,
                event_type='status_changed',
            ).exists()
        )

    def test_service_can_add_part_usage_from_booking_detail_and_reduce_stock(self):
        """Verifica adaugarea unei piese din fisa lucrarii si actualizarea automata a stocului."""
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:booking_detail', args=[self.booking.pk]), {
            'action': 'add_job_part',
            'part': self.part.pk,
            'quantity': 2,
            'status': JobPartUsage.STATUS_CONSUMED,
            'note': 'Consum la revizie completa',
        })

        self.assertRedirects(response, reverse('services:booking_detail', args=[self.booking.pk]))
        self.part.refresh_from_db()
        self.assertEqual(self.part.stock, 6)
        self.assertTrue(
            self.booking.job_card.part_usages.filter(
                part=self.part,
                quantity=2,
                status=JobPartUsage.STATUS_CONSUMED,
            ).exists()
        )
        self.assertTrue(
            StockMovement.objects.filter(
                booking=self.booking,
                part=self.part,
                movement_type=StockMovement.TYPE_OUT,
                quantity_delta=-2,
            ).exists()
        )

    def test_my_bookings_page_displays_recommendations_and_document_count(self):
        """Verifica faptul ca pagina clientului afiseaza recomandari, cost si documente din fluxul integrat."""
        self._prepare_completed_job()
        self.client.force_login(self.client_user)

        response = self.client.get(reverse('bookings:my_bookings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Schimb placute frana spate in urmatoarea luna')
        self.assertContains(response, '1 facturi / documente')
        self.assertContains(response, '515,00 RON')

    def test_client_car_history_builds_vehicle_dossier_from_completed_job(self):
        """Verifica dosarul auto din contul clientului pe baza unei programari finalizate si a fisei lucrarii."""
        self._prepare_completed_job()
        self.client.force_login(self.client_user)

        response = self.client.get(reverse('accounts:car_history', args=[self.car.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dossier']['summary']['interventions_count'], 1)
        self.assertEqual(response.context['dossier']['summary']['open_recommendations_count'], 1)
        self.assertEqual(response.context['dossier']['summary']['total_cost'], Decimal('515.00'))

    def test_service_clients_page_includes_snapshot_and_vehicle_dossier_summary(self):
        """Verifica sumarul de client si dosarul masinii in lista de clienti a service-ului."""
        self._prepare_completed_job()
        self.client.force_login(self.owner)

        response = self.client.get(reverse('invoices:clients'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_clients'], 1)
        self.assertEqual(response.context['clients'][0]['booking_count'], 1)
        self.assertEqual(response.context['clients'][0]['dossier_summary']['interventions_count'], 1)

    def test_service_car_history_groups_completed_work_and_summary(self):
        """Verifica istoricul auto din dashboard-ul service-ului cu sumar pe masina si recomandari deschise."""
        self._prepare_completed_job()
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:car_history'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['vehicles']), 1)
        self.assertEqual(response.context['vehicles'][0]['summary']['interventions_count'], 1)
        self.assertEqual(response.context['vehicles'][0]['summary']['open_recommendations_count'], 1)
