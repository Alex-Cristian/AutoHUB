from datetime import time
from decimal import Decimal
from itertools import count

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Car, EmailVerificationToken, LegalAcceptance
from bookings.models import Booking, BookingNotification
from invoices.models import Invoice, InvoiceLine
from services.business import ensure_job_card
from services.models import (
    Favorite,
    Review,
    ServiceCategory,
    ServiceCenter,
    ServiceGarage,
    ServiceItem,
    ServiceMechanic,
    ServicePart,
)


User = get_user_model()
_seq = count(1)


def _next(prefix="item"):
    return f"{prefix}{next(_seq)}"


def accept_legal(user):
    return LegalAcceptance.objects.update_or_create(
        user=user,
        defaults={
            "document_set": "platform",
            "terms_version": settings.LEGAL_DOCUMENTS_VERSION,
            "privacy_version": settings.LEGAL_DOCUMENTS_VERSION,
            "cookies_version": settings.LEGAL_DOCUMENTS_VERSION,
        },
    )[0]


def make_user(*, username=None, email=None, password="pass12345", is_staff=False, is_superuser=False, active=True):
    username = username or _next("user")
    email = email or f"{username}@example.com"
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_staff=is_staff,
        is_superuser=is_superuser,
        is_active=active,
    )
    if active:
        accept_legal(user)
    return user


def make_service_user(**kwargs):
    return make_user(username=kwargs.pop("username", _next("service")), **kwargs)


def make_client_user(**kwargs):
    return make_user(username=kwargs.pop("username", _next("client")), **kwargs)


def make_admin_user(**kwargs):
    return make_user(
        username=kwargs.pop("username", _next("admin")),
        is_staff=True,
        is_superuser=True,
        **kwargs,
    )


def make_email_verification(user, *, verified=False, created_at=None):
    token = EmailVerificationToken.objects.create(user=user, token=_next("verify-token-"))
    if created_at:
        token.created_at = created_at
    if verified:
        token.verified_at = timezone.now()
    token.save(update_fields=["token", "created_at", "verified_at"])
    return token


def make_category(*, name=None, slug=None):
    name = name or f"Categorie {_next('cat')}"
    slug = slug or name.lower().replace(" ", "-")
    return ServiceCategory.objects.create(name=name, slug=slug)


def make_service_center(*, owner=None, category=None, name=None, city="bucuresti", is_active=True, is_featured=False):
    owner = owner or make_service_user()
    category = category or make_category()
    name = name or f"Service {_next('center')}"
    center = ServiceCenter.objects.create(
        owner=owner,
        name=name,
        category=category,
        description="Descriere test service",
        address="Str. Test 1",
        city=city,
        phone="0711111111",
        email=f"{name.lower().replace(' ', '')}@example.com",
        is_active=is_active,
        is_featured=is_featured,
    )
    center.categories.add(category)
    return center


def make_garage(*, center=None, category=None, name=None, open_time_value=None, close_time_value=None, slot_minutes=60):
    center = center or make_service_center()
    category = category or center.category
    return ServiceGarage.objects.create(
        center=center,
        category=category,
        name=name or f"Garaj {_next('garage')}",
        open_time=open_time_value or time(8, 0),
        close_time=close_time_value or time(18, 0),
        slot_minutes=slot_minutes,
    )


def make_mechanic(*, center=None, garage=None, name=None):
    center = center or make_service_center()
    return ServiceMechanic.objects.create(
        center=center,
        garage=garage,
        name=name or f"Mecanic {_next('mech')}",
        specialization="Mecanica generala",
    )


def make_service_item(*, center=None, name=None, duration_minutes=60, price_from=Decimal("100.00"), price_to=Decimal("150.00")):
    center = center or make_service_center()
    return ServiceItem.objects.create(
        center=center,
        name=name or f"Serviciu {_next('svc')}",
        description="Serviciu test",
        duration_minutes=duration_minutes,
        price_from=price_from,
        price_to=price_to,
    )


def make_car(*, owner=None, plate_number=None, vin=None):
    owner = owner or make_client_user()
    idx = next(_seq)
    return Car.objects.create(
        owner=owner,
        make="Dacia",
        model="Logan",
        year=2020,
        fuel="benzina",
        plate_number=plate_number or f"B{idx:06d}",
        vin=vin or f"WVWZZZ1KZAW{idx:06d}",
    )


def make_booking(
    *,
    user=None,
    center=None,
    garage=None,
    mechanic=None,
    service_item=None,
    status=Booking.STATUS_PENDING,
    booking_date=None,
    booking_time_value=None,
    duration_minutes=60,
    estimated_price=Decimal("120.00"),
    wants_offer=False,
    suffix=None,
):
    user = user or make_client_user()
    center = center or make_service_center()
    garage = garage or make_garage(center=center)
    service_item = service_item or make_service_item(center=center, duration_minutes=duration_minutes)
    suffix = suffix or str(next(_seq))
    booking = Booking.objects.create(
        user=user,
        center=center,
        garage=garage,
        mechanic=mechanic,
        service_item=service_item,
        client_name=f"Client {suffix}",
        client_phone="0722000000",
        client_email=f"client{suffix}@example.com",
        car_brand="Skoda",
        car_model="Octavia",
        car_year=2021,
        car_fuel="benzina",
        car_plate=f"B{int(suffix[-1]) if suffix[-1].isdigit() else 1}TEST{suffix[-1]}",
        car_vin=f"WVWZZZ1KZAW{int(next(_seq)):06d}",
        problem_description="Revizie si verificari de rutina",
        booking_date=booking_date or (timezone.localdate() + timezone.timedelta(days=2)),
        booking_time=booking_time_value or time(10, 0),
        duration_minutes=duration_minutes,
        status=status,
        estimated_price=estimated_price,
        wants_offer=wants_offer,
    )
    return booking


def make_job_card(*, booking=None, actor=None, status=None, final_cost=None):
    booking = booking or make_booking(status=Booking.STATUS_CONFIRMED)
    actor = actor or booking.center.owner
    job_card, _ = ensure_job_card(booking, actor=actor)
    if status:
        job_card.status = status
    if final_cost is not None:
        job_card.final_cost = final_cost
    job_card.save()
    return job_card


def make_part(*, center=None, name=None, stock=10, minimum_stock=2, purchase_price=Decimal("30.00"), sale_price=Decimal("45.00")):
    center = center or make_service_center()
    idx = next(_seq)
    return ServicePart.objects.create(
        center=center,
        name=name or f"Piesa {idx}",
        part_number=f"PART-{idx}",
        category="consumabile",
        brand="Bosch",
        supplier="Inter Cars",
        stock=stock,
        minimum_stock=minimum_stock,
        price=sale_price,
        purchase_price=purchase_price,
        sale_price=sale_price,
        unit="buc",
    )


def make_invoice(*, center=None, booking=None, status=Invoice.STATUS_DRAFT, with_line=True):
    booking = booking or make_booking(status=Booking.STATUS_DONE)
    center = center or booking.center
    invoice = Invoice.objects.create(
        center=center,
        booking=booking,
        status=status,
        company_name=center.legal_name or center.name,
        company_address=center.headquarters or center.address,
        company_city=center.get_city_display(),
        company_phone=center.phone,
        company_email=center.email,
        client_name=booking.client_name,
        client_email=booking.client_email,
        client_phone=booking.client_phone,
    )
    if with_line:
        InvoiceLine.objects.create(
            invoice=invoice,
            description="Lucrare test",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
        )
        invoice.recalc_totals(save=True)
    return invoice


def make_review(*, center=None, user=None, rating=5):
    center = center or make_service_center()
    user = user or make_client_user()
    Booking.objects.filter(user=user, center=center).delete()
    make_booking(user=user, center=center, status=Booking.STATUS_DONE)
    return Review.objects.create(
        center=center,
        user=user,
        rating=rating,
        title="Recenzie buna",
        body="Foarte multumit de service.",
        is_approved=True,
    )


def make_favorite(*, user=None, center=None):
    user = user or make_client_user()
    center = center or make_service_center()
    return Favorite.objects.create(user=user, center=center)


def make_notification(*, recipient=None, booking=None, kind=BookingNotification.KIND_STATUS_UPDATE):
    booking = booking or make_booking()
    recipient = recipient or booking.center.owner or make_service_user()
    return BookingNotification.objects.create(
        recipient=recipient,
        booking=booking,
        kind=kind,
        title="Notificare test",
        message="Mesaj test notificare",
    )
