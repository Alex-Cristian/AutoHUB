import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _format_price(price) -> str | None:
    if price in (None, ""):
        return None
    try:
        amount = Decimal(price)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return f"{amount:.2f} RON"


def _date_text(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "Data necunoscuta"


def _time_text(value) -> str:
    return value.strftime("%H:%M") if value else "Ora necunoscuta"


def _site_url(path: str = "/") -> str:
    domain = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{domain}{path}" if domain else path


def _user_display_name(user) -> str:
    if not user:
        return "Salut"
    return getattr(user, "first_name", "") or getattr(user, "username", "") or "Salut"


def _service_owner_email(booking) -> str:
    owner = getattr(getattr(booking, "center", None), "owner", None)
    return getattr(owner, "email", "") or ""


def _booking_context(booking) -> dict:
    return {
        "booking": booking,
        "client_name": booking.client_name,
        "service_name": getattr(booking.center, "name", "AutoEMG"),
        "service_owner_name": _user_display_name(getattr(booking.center, "owner", None)),
        "booking_date_text": _date_text(booking.booking_date),
        "booking_time_text": _time_text(booking.booking_time),
        "duration_text": booking.get_duration_display(),
        "estimated_price_text": _format_price(getattr(booking, "estimated_price", None)) or "Nespecificat",
        "garage_name": getattr(getattr(booking, "garage", None), "name", "") or "Service",
        "car_summary": f"{booking.car_brand} {booking.car_model} ({booking.car_plate})",
        "client_phone": booking.client_phone,
        "client_email": booking.client_email,
        "problem_description": booking.problem_description,
        "booking_detail_url": _site_url(reverse("services:booking_detail", args=[booking.pk])),
        "my_bookings_url": _site_url(reverse("bookings:my_bookings")),
        "service_dashboard_url": _site_url(reverse("services:dashboard")),
    }


def _render_plain_text(template_name: str, context: dict) -> str:
    rendered = render_to_string(template_name, context).strip()
    return rendered or strip_tags(render_to_string("emails/base.txt", context)).strip()


def send_transactional_email(
    *,
    to_email: str,
    subject: str,
    html_template: str,
    text_template: str,
    context: dict,
) -> bool:
    if getattr(settings, "DISABLE_TRANSACTIONAL_EMAILS", False):
        logger.info("Email dezactivat prin setare pentru subiectul '%s'.", subject)
        return False

    if not to_email:
        logger.warning("Email netrimis: lipseste destinatarul pentru subiectul '%s'.", subject)
        return False

    payload = {
        "brand_name": "AutoEMG",
        "brand_tagline": "Marketplace service auto",
        "site_url": _site_url("/"),
        "support_email": getattr(settings, "DEFAULT_FROM_EMAIL", ""),
        **context,
    }

    try:
        text_body = _render_plain_text(text_template, payload)
        html_body = render_to_string(html_template, payload)
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or None,
            to=[to_email],
        )
        message.attach_alternative(html_body, "text/html")
        message.send(fail_silently=False)
        logger.info("Email trimis cu succes catre %s: %s", to_email, subject)
        return True
    except Exception:
        logger.exception("Nu am putut trimite emailul '%s' catre %s.", subject, to_email)
        return False


def send_verification_email(user, token) -> bool:
    verify_url = _site_url(reverse("accounts:verify_email", args=[token.token]))
    return send_transactional_email(
        to_email=user.email,
        subject="AutoEMG - confirma adresa de email",
        html_template="emails/account_verification.html",
        text_template="emails/account_verification.txt",
        context={
            "preview_text": "Activeaza-ti contul si confirma adresa de email.",
            "headline": "Confirma adresa de email",
            "greeting_name": _user_display_name(user),
            "verification_url": verify_url,
            "cta_label": "Confirma emailul",
            "expiry_hours": getattr(settings, "ACCOUNT_VERIFICATION_EXPIRY_HOURS", 24),
        },
    )


def send_expiry_reminder_email(user, car, label: str, expiry_date) -> bool:
    return send_transactional_email(
        to_email=user.email,
        subject=f"AutoEMG - {label} expira curand pentru {car.plate_number}",
        html_template="emails/expiry_reminder.html",
        text_template="emails/expiry_reminder.txt",
        context={
            "preview_text": f"Reminder pentru {label}: expira pe {_date_text(expiry_date)}.",
            "headline": f"{label} expira in curand",
            "greeting_name": _user_display_name(user),
            "document_label": label,
            "expiry_date_text": _date_text(expiry_date),
            "car_summary": f"{car.make} {car.model} ({car.plate_number})",
            "calendar_url": _site_url(reverse("accounts:car_calendar", args=[car.pk])),
            "cta_label": "Vezi calendarul de expirari",
        },
    )


def send_booking_request_to_service_email(booking) -> bool:
    owner_email = _service_owner_email(booking)
    if not owner_email:
        return False
    return send_transactional_email(
        to_email=owner_email,
        subject=f"AutoEMG - programare noua #{booking.pk}",
        html_template="emails/new_booking_service.html",
        text_template="emails/new_booking_service.txt",
        context={
            **_booking_context(booking),
            "preview_text": f"Ai primit o programare noua pentru {booking.center.name}.",
            "headline": "Ai primit o programare noua",
            "greeting_name": _user_display_name(getattr(booking.center, "owner", None)),
            "cta_label": "Deschide dashboard-ul",
        },
    )


def send_booking_quote_email(booking) -> bool:
    return send_transactional_email(
        to_email=booking.client_email,
        subject=f"AutoEMG - oferta noua pentru programarea #{booking.pk}",
        html_template="emails/service_offer_client.html",
        text_template="emails/service_offer_client.txt",
        context={
            **_booking_context(booking),
            "preview_text": f"{booking.center.name} a trimis o oferta pentru programarea ta.",
            "headline": "Oferta ta este gata",
            "greeting_name": booking.client_name,
            "cta_label": "Vezi si raspunde la oferta",
        },
    )


def send_quote_accepted_to_service_email(booking) -> bool:
    owner_email = _service_owner_email(booking)
    if not owner_email:
        return False
    return send_transactional_email(
        to_email=owner_email,
        subject=f"AutoEMG - clientul a acceptat oferta pentru programarea #{booking.pk}",
        html_template="emails/client_accepted_service.html",
        text_template="emails/client_accepted_service.txt",
        context={
            **_booking_context(booking),
            "preview_text": f"{booking.client_name} a acceptat oferta trimisa de service.",
            "headline": "Oferta a fost acceptata",
            "greeting_name": _user_display_name(getattr(booking.center, "owner", None)),
            "cta_label": "Vezi programarea",
        },
    )


def send_booking_started_email(booking) -> bool:
    return send_transactional_email(
        to_email=booking.client_email,
        subject=f"AutoEMG - lucrarea a inceput pentru programarea #{booking.pk}",
        html_template="emails/work_started_client.html",
        text_template="emails/work_started_client.txt",
        context={
            **_booking_context(booking),
            "preview_text": f"Lucrarea pentru masina ta a inceput la {booking.center.name}.",
            "headline": "Lucrarea a inceput",
            "greeting_name": booking.client_name,
            "cta_label": "Vezi programarile mele",
            "mechanic_name": getattr(getattr(booking, "mechanic", None), "name", "") or "Mecanicul alocat",
        },
    )


def send_booking_completed_email(booking) -> bool:
    return send_transactional_email(
        to_email=booking.client_email,
        subject=f"AutoEMG - lucrarea a fost finalizata pentru programarea #{booking.pk}",
        html_template="emails/work_completed_client.html",
        text_template="emails/work_completed_client.txt",
        context={
            **_booking_context(booking),
            "preview_text": f"Lucrarea pentru masina ta a fost marcata ca finalizata.",
            "headline": "Lucrarea a fost finalizata",
            "greeting_name": booking.client_name,
            "cta_label": "Vezi istoricul programarii",
            "mechanic_name": getattr(getattr(booking, "mechanic", None), "name", "") or "Mecanicul alocat",
        },
    )
