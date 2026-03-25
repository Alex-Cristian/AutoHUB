from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Car, LegalAcceptance
from services.models import ServiceCategory, ServiceCenter, ServiceGarage, ServiceItem, ServiceMechanic, ServicePart


User = get_user_model()


class Command(BaseCommand):
    help = "Pregateste date stabile pentru scenariile E2E Playwright."

    @transaction.atomic
    def handle(self, *args, **options):
        service_user = self._upsert_user(
            username="service_e2e",
            email="service_e2e@example.com",
            password="service12345",
            first_name="Service",
            last_name="E2E",
        )
        client_user = self._upsert_user(
            username="client_e2e",
            email="client_e2e@example.com",
            password="client12345",
            first_name="Client",
            last_name="E2E",
        )

        self._accept_legal(service_user)
        self._accept_legal(client_user)

        service_user.owned_centers.all().delete()
        client_user.cars.all().delete()

        category, _ = ServiceCategory.objects.get_or_create(
            slug="e2e-general",
            defaults={
                "name": "Service general E2E",
                "description": "Categorie folosita pentru testele browser E2E.",
                "icon": "tools",
                "color": "#e63946",
                "order": 900,
            },
        )

        center = ServiceCenter.objects.create(
            owner=service_user,
            name="AutoHub E2E Service",
            slug="autohub-e2e-service",
            category=category,
            description="Service pregatit pentru scenariile browser E2E.",
            address="Str. Test E2E 10",
            city="bucuresti",
            phone="0711000000",
            email="service-e2e@autohub.local",
            schedule="Lun-Vin: 08:00-18:00",
            is_active=True,
        )
        center.categories.add(category)

        garage = ServiceGarage.objects.create(
            center=center,
            category=category,
            name="Post E2E 1",
            open_time="08:00",
            close_time="18:00",
            slot_minutes=60,
        )
        ServiceItem.objects.create(
            center=center,
            name="Revizie completa E2E",
            description="Serviciu folosit pentru fluxul E2E.",
            price_from="150.00",
            price_to="450.00",
            duration_minutes=60,
            is_popular=True,
        )
        ServiceMechanic.objects.create(
            center=center,
            garage=garage,
            name="Mecanic E2E",
            specialization="Mecanica generala",
            is_active=True,
        )
        ServicePart.objects.create(
            center=center,
            name="Filtru ulei E2E",
            part_number="E2E-FO-1",
            category="consumabile",
            brand="Bosch",
            supplier="Inter Cars",
            stock=5,
            minimum_stock=2,
            price="49.90",
            purchase_price="32.00",
            sale_price="49.90",
            unit="buc",
            shelf="Raft E2E",
            is_active=True,
        )

        Car.objects.create(
            owner=client_user,
            make="Dacia",
            model="Logan",
            year=2021,
            fuel="benzina",
            plate_number="B400E2E",
            vin="WVWZZZ1KZAW400001",
        )

        self.stdout.write(self.style.SUCCESS("Datele E2E au fost pregatite."))
        self.stdout.write("Client login: client_e2e / client12345")
        self.stdout.write("Service login: service_e2e / service12345")
        self.stdout.write("Service slug: autohub-e2e-service")

    def _upsert_user(self, *, username, email, password, first_name="", last_name=""):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "is_active": True,
            },
        )
        dirty_fields = []
        if user.email != email:
            user.email = email
            dirty_fields.append("email")
        if user.first_name != first_name:
            user.first_name = first_name
            dirty_fields.append("first_name")
        if user.last_name != last_name:
            user.last_name = last_name
            dirty_fields.append("last_name")
        if not user.is_active:
            user.is_active = True
            dirty_fields.append("is_active")
        user.set_password(password)
        dirty_fields.append("password")
        user.save(update_fields=dirty_fields)
        return user

    def _accept_legal(self, user):
        LegalAcceptance.objects.update_or_create(
            user=user,
            defaults={
                "document_set": "platform",
                "terms_version": settings.LEGAL_DOCUMENTS_VERSION,
                "privacy_version": settings.LEGAL_DOCUMENTS_VERSION,
                "cookies_version": settings.LEGAL_DOCUMENTS_VERSION,
            },
        )
