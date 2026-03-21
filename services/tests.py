import json
from datetime import datetime, time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import LegalAcceptance
from bookings.models import Booking, BookingActivityLog
from services.models import ServiceCategory, ServiceCenter, ServiceGarage, ServicePart


User = get_user_model()


def grant_legal_acceptance(user):
    LegalAcceptance.objects.create(
        user=user,
        document_set='platform',
        terms_version=settings.LEGAL_DOCUMENTS_VERSION,
        privacy_version=settings.LEGAL_DOCUMENTS_VERSION,
        cookies_version=settings.LEGAL_DOCUMENTS_VERSION,
    )


def create_center(owner, name='Service Test'):
    category = ServiceCategory.objects.create(name=f'Categorie {name}', slug=f'categorie-{name.lower().replace(" ", "-")}')
    center = ServiceCenter.objects.create(
        owner=owner,
        name=name,
        category=category,
        description='Descriere',
        address='Str. Test 10',
        city='bucuresti',
        phone='0700000000',
        email=f'{name.lower().replace(" ", "")}@example.com',
    )
    center.categories.add(category)
    return center


def create_booking(center, user=None, status=Booking.STATUS_PENDING, suffix='1'):
    garage = ServiceGarage.objects.create(
        center=center,
        name=f'Garaj {suffix}',
        category=center.category,
        open_time=time(8, 0),
        close_time=time(18, 0),
        slot_minutes=60,
    )
    return Booking.objects.create(
        user=user,
        center=center,
        garage=garage,
        client_name=f'Client {suffix}',
        client_phone='0711111111',
        client_email=f'client{suffix}@example.com',
        car_brand='Dacia',
        car_model='Logan',
        car_year=2020,
        car_fuel='benzina',
        car_plate=f'B{suffix}TEST',
        car_vin=f'WVWZZZ1KZAW00000{suffix}',
        problem_description='Revizie generala',
        booking_date=timezone.localdate() + timezone.timedelta(days=1),
        booking_time=time(10, 0),
        duration_minutes=60,
        status=status,
    )


class ServiceBookingPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass12345')
        self.client_user = User.objects.create_user(username='client', password='pass12345')
        self.admin = User.objects.create_superuser(username='admin', email='admin@example.com', password='pass12345')
        for user in [self.owner, self.client_user, self.admin]:
            grant_legal_acceptance(user)
        self.center = create_center(self.owner, 'Service Owner')
        self.booking = create_booking(self.center, user=self.client_user)

    def test_service_owner_can_open_booking_detail(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:booking_detail', args=[self.booking.pk]))

        self.assertEqual(response.status_code, 200)

    def test_client_cannot_open_service_booking_detail(self):
        self.client.force_login(self.client_user)

        response = self.client.get(reverse('services:booking_detail', args=[self.booking.pk]))

        self.assertRedirects(response, reverse('core:home'), fetch_redirect_response=False)

    def test_admin_can_open_service_booking_detail(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('services:booking_detail', args=[self.booking.pk]))

        self.assertEqual(response.status_code, 200)


class ServiceCalendarTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner2', password='pass12345')
        self.other_owner = User.objects.create_user(username='owner3', password='pass12345')
        grant_legal_acceptance(self.owner)
        grant_legal_acceptance(self.other_owner)
        self.center = create_center(self.owner, 'Calendar One')
        self.other_center = create_center(self.other_owner, 'Calendar Two')
        self.booking = create_booking(self.center, status=Booking.STATUS_CONFIRMED, suffix='2')
        self.other_booking = create_booking(self.other_center, status=Booking.STATUS_DONE, suffix='3')

    def test_calendar_page_loads_for_service_owner(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:calendar'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Calendar programari')

    def test_calendar_events_only_return_owned_service_bookings(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:calendar_events'), {
            'start': (timezone.now() - timezone.timedelta(days=1)).isoformat(),
            'end': (timezone.now() + timezone.timedelta(days=10)).isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        ids = {item['id'] for item in payload}
        self.assertIn(self.booking.pk, ids)
        self.assertNotIn(self.other_booking.pk, ids)

    def test_calendar_events_requires_service_account(self):
        client_user = User.objects.create_user(username='plainclient', password='pass12345')
        grant_legal_acceptance(client_user)
        self.client.force_login(client_user)

        response = self.client.get(reverse('services:calendar_events'))

        self.assertEqual(response.status_code, 403)

    def test_calendar_update_moves_booking_and_logs_activity(self):
        self.client.force_login(self.owner)

        start = datetime.combine(self.booking.booking_date, time(13, 0)).isoformat()
        end = datetime.combine(self.booking.booking_date, time(14, 30)).isoformat()
        response = self.client.post(
            reverse('services:calendar_update_booking', args=[self.booking.pk]),
            {'start': start, 'end': end},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.booking_time, time(13, 0))
        self.assertEqual(self.booking.duration_minutes, 90)
        self.assertTrue(
            BookingActivityLog.objects.filter(
                booking=self.booking,
                event_type='schedule_changed',
            ).exists()
        )

    def test_calendar_update_rejects_invalid_overlap(self):
        self.client.force_login(self.owner)
        Booking.objects.create(
            center=self.center,
            garage=self.booking.garage,
            client_name='Client overlap',
            client_phone='0709999999',
            client_email='overlap@example.com',
            car_brand='Ford',
            car_model='Focus',
            car_year=2020,
            car_fuel='benzina',
            car_plate='B99OVL',
            car_vin='WVWZZZ1KZAW000099',
            problem_description='Conflict test',
            booking_date=self.booking.booking_date,
            booking_time=time(10, 30),
            duration_minutes=60,
            status=Booking.STATUS_CONFIRMED,
        )

        start = datetime.combine(self.booking.booking_date, time(10, 30)).isoformat()
        end = datetime.combine(self.booking.booking_date, time(11, 30)).isoformat()
        response = self.client.post(
            reverse('services:calendar_update_booking', args=[self.booking.pk]),
            {'start': start, 'end': end},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)


class ServiceDashboardAnalyticsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner4', password='pass12345')
        grant_legal_acceptance(self.owner)
        self.center = create_center(self.owner, 'Analytics Service')

    def test_dashboard_renders_with_empty_data(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Analytics service')

    def test_dashboard_surfaces_today_board_and_stock_alerts(self):
        ServicePart.objects.create(
            center=self.center,
            name='Filtru ulei',
            part_number='FO-1',
            stock=1,
            minimum_stock=2,
            category='consumabile',
        )
        create_booking(self.center, status=Booking.STATUS_CONFIRMED, suffix='7')
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Today Board')
        self.assertContains(response, 'Stoc și atenționări')
        self.assertContains(response, 'Filtru ulei')


class ServicePartsInventoryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner-parts', password='pass12345')
        grant_legal_acceptance(self.owner)
        self.center = create_center(self.owner, 'Parts Service')
        self.filter_oil = ServicePart.objects.create(
            center=self.center,
            name='Filtru ulei',
            part_number='FO-100',
            category='consumabile',
            brand='Mann',
            supplier='Inter Cars',
            stock=1,
            minimum_stock=2,
            price='45.50',
        )
        self.battery = ServicePart.objects.create(
            center=self.center,
            name='Baterie AGM',
            part_number='BAT-9',
            category='electric',
            brand='Bosch',
            stock=5,
            minimum_stock=1,
            price='510.00',
        )

    def test_parts_inventory_filters_low_stock(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('services:parts_inventory'), {
            'center': self.center.pk,
            'stock_status': 'low',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Filtru ulei')
        self.assertNotContains(response, 'Baterie AGM')

    def test_parts_inventory_adjust_stock_action(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:parts_inventory'), {
            'action': 'adjust_stock',
            'center_id': self.center.pk,
            'part_id': self.filter_oil.pk,
            'delta': 5,
        })

        self.assertEqual(response.status_code, 302)
        self.filter_oil.refresh_from_db()
        self.assertEqual(self.filter_oil.stock, 6)

    def test_parts_inventory_add_part_requires_note_when_zero_stock_and_minimum(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse('services:parts_inventory'), {
            'action': 'add_part',
            'center_id': self.center.pk,
            'name': 'Set cleme',
            'part_number': 'CL-1',
            'category': 'altele',
            'brand': '',
            'supplier': '',
            'price': '',
            'stock': 0,
            'minimum_stock': 0,
            'unit': 'buc',
            'shelf': '',
            'notes': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Adauga o observatie scurta')
