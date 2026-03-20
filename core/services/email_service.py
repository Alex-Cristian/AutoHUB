import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_email_safe(subject: str, message: str, to_email: str) -> bool:
    if not to_email:
        return False
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or None
        send_mail(subject, message, from_email, [to_email], fail_silently=False)
        return True
    except Exception:
        logger.exception('Nu am putut trimite email către %s.', to_email)
        return False


def _format_price(price) -> str | None:
    if price in (None, ''):
        return None
    try:
        amount = Decimal(price)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return f'{amount:.2f} RON'


def _date_text(value) -> str:
    return value.strftime('%d.%m.%Y') if value else 'data necunoscută'


def _time_text(value) -> str:
    return value.strftime('%H:%M') if value else 'ora necunoscută'


def _site_url(path: str = '/') -> str:
    domain = getattr(settings, 'SITE_BASE_URL', '').rstrip('/')
    if not domain:
        return path
    if not path.startswith('/'):
        path = '/' + path
    return f'{domain}{path}'


def send_verification_email(user, token) -> bool:
    verify_path = reverse('accounts:verify_email', args=[token.token])
    verify_url = _site_url(verify_path)
    subject = 'AutoEMG - confirmă adresa de email'
    message = (
        f'Salut, {user.first_name or user.username}!\n\n'
        'Contul tău AutoEMG a fost creat, dar trebuie să îți confirmi adresa de email înainte să te poți autentifica.\n\n'
        f'Link confirmare: {verify_url}\n\n'
        f'Linkul expiră în {getattr(settings, "ACCOUNT_VERIFICATION_EXPIRY_HOURS", 24)} de ore. Dacă nu ai creat tu acest cont, poți ignora acest mesaj.'
    )
    return send_email_safe(subject, message, user.email)


def send_expiry_reminder_email(user, car, label: str, expiry_date) -> bool:
    car_name = f'{car.make} {car.model} ({car.plate_number})'
    subject = f'AutoEMG - {label} expiră în curând pentru {car.plate_number}'
    message = (
        f'Salut, {user.first_name or user.username}!\n\n'
        f'{label} pentru mașina {car_name} expiră la data de {_date_text(expiry_date)}.\n'
        'Îți recomandăm să te ocupi din timp ca să eviți problemele sau amenzile.\n\n'
        f'Vezi calendarul de expirări: {_site_url(reverse("accounts:car_calendar", args=[car.pk]))}'
    )
    return send_email_safe(subject, message, user.email)


def send_booking_quote_email(booking) -> bool:
    subject = f'AutoEMG - ofertă nouă pentru programarea #{booking.pk}'
    price = _format_price(getattr(booking, 'estimated_price', None))
    message = (
        f'Salut, {booking.client_name}!\n\n'
        f'{booking.center.name} a răspuns la programarea ta.\n'
        f'Data: {_date_text(booking.booking_date)}\n'
        f'Ora: {_time_text(booking.booking_time)}\n'
        f'Durată estimată: {booking.get_duration_display()}\n'
        f'Preț aproximativ: {price or "Nespecificat"}\n\n'
        f'Poți intra în contul tău pentru a accepta sau refuza oferta: {_site_url(reverse("bookings:my_bookings"))}'
    )
    return send_email_safe(subject, message, booking.client_email)


def send_booking_started_email(booking) -> bool:
    subject = f'AutoEMG - a început lucrarea pentru programarea #{booking.pk}'
    price = _format_price(getattr(booking, 'estimated_price', None))
    parts = [
        f'Salut, {booking.client_name}!',
        '',
        f'Mecanicul a început lucrul la mașina ta în service-ul {booking.center.name}.',
        f'Data programării: {_date_text(booking.booking_date)}',
        f'Ora: {_time_text(booking.booking_time)}',
    ]
    if price:
        parts.append(f'Cost estimativ: {price}')
    return send_email_safe(subject, '\n'.join(parts), booking.client_email)


def send_booking_completed_email(booking) -> bool:
    subject = f'AutoEMG - lucrarea pentru programarea #{booking.pk} a fost finalizată'
    price = _format_price(getattr(booking, 'estimated_price', None))
    parts = [
        f'Salut, {booking.client_name}!',
        '',
        f'Lucrarea pentru mașina ta la {booking.center.name} a fost marcată ca finalizată.',
        f'Data programării: {_date_text(booking.booking_date)}',
        f'Ora: {_time_text(booking.booking_time)}',
    ]
    if price:
        parts.append(f'Cost estimativ: {price}')
    return send_email_safe(subject, '\n'.join(parts), booking.client_email)


def send_booking_request_to_service_email(booking) -> bool:
    owner = getattr(getattr(booking, 'center', None), 'owner', None)
    if not owner or not owner.email:
        return False
    subject = f'[AutoEMG] Programare nouă #{booking.pk}'
    message = (
        f'Ai o programare nouă pentru {booking.center.name}.\n\n'
        f'Client: {booking.client_name}\n'
        f'Data/Ora: {_date_text(booking.booking_date)} {_time_text(booking.booking_time)}\n'
        f'Mașină: {booking.car_brand} {booking.car_model} ({booking.car_plate})\n'
        f'Telefon: {booking.client_phone}\n'
        f'Email: {booking.client_email}\n\n'
        'Intră în dashboard-ul service-ului ca să răspunzi programării.'
    )
    return send_email_safe(subject, message, owner.email)


def send_quote_accepted_to_service_email(booking) -> bool:
    owner = getattr(getattr(booking, 'center', None), 'owner', None)
    if not owner or not owner.email:
        return False
    price = _format_price(getattr(booking, 'estimated_price', None))
    subject = f'[AutoEMG] Clientul a acceptat oferta pentru programarea #{booking.pk}'
    message = (
        f'Clientul {booking.client_name} a acceptat oferta trimisă de {booking.center.name}.\n\n'
        f'Data/Ora: {_date_text(booking.booking_date)} {_time_text(booking.booking_time)}\n'
        f'Durată estimată: {booking.get_duration_display()}\n'
        f'Preț aproximativ: {price or "Nespecificat"}\n'
        f'Mașină: {booking.car_brand} {booking.car_model} ({booking.car_plate})'
    )
    return send_email_safe(subject, message, owner.email)
