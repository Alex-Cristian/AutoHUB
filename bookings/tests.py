from datetime import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Car, LegalAcceptance
from bookings.forms import BookingForm
from bookings.files import build_attachment_summary, sanitize_uploaded_filename
from bookings.models import Booking, BookingActivityLog, BookingNotification
from invoices.models import Invoice, InvoiceLine
from services.business import ensure_job_card
from services.models import (
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
