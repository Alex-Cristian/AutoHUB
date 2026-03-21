from datetime import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import LegalAcceptance
from bookings.forms import BookingForm
from bookings.models import Booking, BookingNotification
from services.models import ServiceCategory, ServiceCenter, ServiceGarage, ServiceMechanic


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
        self.client.force_login(self.client_user)

        response = self.client.post(reverse('bookings:reject_quote', args=[self.booking.pk]))

        self.assertRedirects(response, reverse('bookings:my_bookings'))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.STATUS_CANCELLED)


class BookingFormValidationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='ownerform', password='pass12345')
        self.center, self.garage = create_center_with_garage(self.owner)

    def test_booking_form_rejects_invalid_vin(self):
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
