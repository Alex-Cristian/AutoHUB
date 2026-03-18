import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings

try:
    from twilio.base.exceptions import TwilioRestException
    from twilio.rest import Client
except Exception:  # pragma: no cover
    Client = None
    TwilioRestException = Exception

logger = logging.getLogger(__name__)


def _normalize_phone_number(phone: str) -> str:
    raw = ''.join(ch for ch in str(phone or '').strip() if ch.isdigit() or ch == '+')
    if not raw:
        return ''
    if raw.startswith('+'):
        return raw
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if digits.startswith('00'):
        return f'+{digits[2:]}'
    if digits.startswith('0') and len(digits) == 10:
        return f'+4{digits}'
    if digits.startswith('40') and len(digits) == 11:
        return f'+{digits}'
    return f'+{digits}' if digits else ''


def _format_price(price) -> str | None:
    if price in (None, ''):
        return None
    try:
        amount = Decimal(price)
    except (InvalidOperation, TypeError, ValueError):
        return None
    return f'{amount:.2f} RON'


def _booking_date_text(booking) -> str:
    return booking.booking_date.strftime('%d.%m.%Y') if booking.booking_date else 'data necunoscută'


def _booking_time_text(booking) -> str:
    return booking.booking_time.strftime('%H:%M') if booking.booking_time else 'ora necunoscută'


def _booking_service_name(booking) -> str:
    return getattr(getattr(booking, 'center', None), 'name', 'service-ul')


def _booking_base_parts(booking) -> list[str]:
    parts = [
        f'Data: {_booking_date_text(booking)}',
        f'Ora: {_booking_time_text(booking)}',
    ]
    if getattr(booking, 'estimated_price', None):
        formatted_price = _format_price(booking.estimated_price)
        if formatted_price:
            parts.append(f'Cost estimativ: {formatted_price}')
    return parts


def build_booking_confirmation_message(booking) -> str:
    service_name = _booking_service_name(booking)
    parts = [f'AutoHub: Programarea ta a fost confirmată de {service_name}.']
    parts.extend(_booking_base_parts(booking))
    return ' | '.join(parts)


def build_booking_reminder_message(booking) -> str:
    service_name = _booking_service_name(booking)
    parts = [f'AutoHub: Reminder - mâine ai programare la {service_name}.']
    parts.extend(_booking_base_parts(booking))
    return ' | '.join(parts)


def build_booking_started_message(booking) -> str:
    service_name = _booking_service_name(booking)
    parts = [f'AutoHub: Mecanicul a început lucrul la programarea ta la {service_name}.']
    parts.extend(_booking_base_parts(booking))
    return ' | '.join(parts)


def build_booking_completed_message(booking) -> str:
    service_name = _booking_service_name(booking)
    parts = [f'AutoHub: Programarea ta la {service_name} a fost finalizată.']
    parts.extend(_booking_base_parts(booking))
    return ' | '.join(parts)


def send_sms(phone: str, message: str) -> bool:
    normalized_phone = _normalize_phone_number(phone)
    if not normalized_phone or not message:
        logger.warning('SMS not sent: missing phone or message.')
        return False

    if not getattr(settings, 'TWILIO_SMS_ENABLED', False):
        logger.info('SMS disabled. Skipping SMS to %s.', normalized_phone)
        return False

    account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    from_number = getattr(settings, 'TWILIO_PHONE_NUMBER', '')

    if not all([account_sid, auth_token, from_number]):
        logger.warning('SMS not sent: missing Twilio credentials.')
        return False

    if Client is None:
        logger.warning('SMS not sent: Twilio client is unavailable.')
        return False

    try:
        client = Client(account_sid, auth_token)
        client.messages.create(body=message, from_=from_number, to=normalized_phone)
        logger.info('SMS sent to %s.', normalized_phone)
        return True
    except TwilioRestException:
        logger.exception('Twilio API error while sending SMS to %s.', normalized_phone)
    except Exception:
        logger.exception('Unexpected error while sending SMS to %s.', normalized_phone)
    return False


def send_booking_confirmation_sms(booking) -> bool:
    phone = getattr(booking, 'client_phone', '')
    message = build_booking_confirmation_message(booking)
    return send_sms(phone, message)


def send_booking_reminder_sms(booking) -> bool:
    phone = getattr(booking, 'client_phone', '')
    message = build_booking_reminder_message(booking)
    return send_sms(phone, message)


def send_booking_started_sms(booking) -> bool:
    phone = getattr(booking, 'client_phone', '')
    message = build_booking_started_message(booking)
    return send_sms(phone, message)


def send_booking_completed_sms(booking) -> bool:
    phone = getattr(booking, 'client_phone', '')
    message = build_booking_completed_message(booking)
    return send_sms(phone, message)
