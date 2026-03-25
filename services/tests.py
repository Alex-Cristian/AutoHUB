import json
from datetime import datetime, time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import LegalAcceptance
from bookings.models import Booking, BookingActivityLog
from services.forms import AvailabilityBlockForm
from services.models import (
    JobCard,
    JobOperation,
    JobPartUsage,
    ServiceAvailabilityBlock,
    ServiceCategory,
    ServiceCenter,
    ServiceGarage,
    ServiceItem,
    ServicePart,
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

    def test_booking_print_fills_services_from_selected_service_and_problem(self):
        self.client.force_login(self.owner)
        self.booking.service_item = ServiceItem.objects.create(
            center=self.center,
            name='Schimb ulei si filtre',
            description='Revizie periodica',
            price_from='250.00',
            duration_minutes=90,
        )
        self.booking.problem_description = 'Revizie de primavara'
        self.booking.save(update_fields=['service_item', 'problem_description', 'updated_at'])

        response = self.client.get(reverse('services:booking_print', args=[self.booking.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Servicii de efectuat / piese folosite')
        self.assertContains(response, 'Schimb ulei si filtre')
        self.assertContains(response, 'Solicitare client: Revizie de primavara')

    def test_booking_print_fills_services_from_job_card_operations_and_parts(self):
        self.client.force_login(self.owner)
        job_card = JobCard.objects.create(
            booking=self.booking,
            center=self.center,
            status=JobCard.STATUS_IN_PROGRESS,
        )
        JobOperation.objects.create(
            job_card=job_card,
            title='Diagnoza electronica',
            description='Citire erori si verificare parametri',
            position=1,
        )
        JobPartUsage.objects.create(
            job_card=job_card,
            description='Filtru aer',
            quantity=1,
            unit_label='buc',
            status=JobPartUsage.STATUS_CONSUMED,
            notes='inlocuire recomandata',
        )

        response = self.client.get(reverse('services:booking_print', args=[self.booking.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Diagnoza electronica - Citire erori si verificare parametri')
        self.assertContains(response, 'Filtru aer (1 buc) - inlocuire recomandata')


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

    def test_calendar_sidebar_shows_latest_created_blocks_first(self):
        self.client.force_login(self.owner)
        base_day = timezone.localdate() + timezone.timedelta(days=5)
        for index in range(9):
            starts_at = timezone.make_aware(datetime.combine(base_day + timezone.timedelta(days=index), time(9, 0)))
            ends_at = timezone.make_aware(datetime.combine(base_day + timezone.timedelta(days=index), time(10, 0)))
            ServiceAvailabilityBlock.objects.create(
                center=self.center,
                garage=self.booking.garage,
                title=f'Bloc test {index}',
                block_type=ServiceAvailabilityBlock.BLOCK_BREAK,
                starts_at=starts_at,
                ends_at=ends_at,
                created_by=self.owner,
            )

        response = self.client.get(reverse('services:calendar'))

        self.assertEqual(response.status_code, 200)
        recent_titles = [block.title for block in response.context['recent_blocks']]
        self.assertEqual(len(recent_titles), 8)
        self.assertEqual(recent_titles[0], 'Bloc test 8')
        self.assertNotIn('Bloc test 0', recent_titles)


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
        self.assertContains(response, 'Planul de azi')
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


class ServiceReportsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner-reports', password='pass12345')
        grant_legal_acceptance(self.owner)
        self.center = create_center(self.owner, 'Reports Service')
        self.booking = create_booking(self.center, status=Booking.STATUS_DONE, suffix='9')

    def test_reports_page_renders(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('services:reports'), {'report_type': 'performance', 'preset_period': 'this_month'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rapoarte service')
        self.assertContains(response, 'Generează raport')

    def test_reports_csv_export(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('services:export_report_csv'), {'report_type': 'appointments', 'preset_period': 'this_month'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'].split(';')[0], 'text/csv')
        self.assertIn('raport_appointments', response['Content-Disposition'])


class AvailabilityBlockFormTests(TestCase):
    def test_form_accepts_garage_from_selected_center(self):
        owner = User.objects.create_user(username='owner-block-form', password='pass12345')
        grant_legal_acceptance(owner)
        center = create_center(owner, 'Block Form Service')
        garage = ServiceGarage.objects.create(
            center=center,
            name='Post form',
            category=center.category,
            open_time=time(8, 0),
            close_time=time(18, 0),
            slot_minutes=60,
        )
        start = (timezone.localtime() + timezone.timedelta(days=2)).replace(hour=12, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M')
        end = (timezone.localtime() + timezone.timedelta(days=2)).replace(hour=13, minute=0, second=0, microsecond=0).strftime('%Y-%m-%dT%H:%M')

        form = AvailabilityBlockForm(
            {
                'garage': str(garage.pk),
                'mechanic': '',
                'block_type': ServiceAvailabilityBlock.BLOCK_BREAK,
                'title': 'Bloc valid',
                'notes': '',
                'starts_at': start,
                'ends_at': end,
            },
            center=center,
        )

        self.assertTrue(form.is_valid(), form.errors)
