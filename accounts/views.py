from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.db import models
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

import json
import secrets
import re
import requests as http_requests

from services.models import Favorite
from core.services.email_service import send_verification_email
from .forms import RegisterForm, LoginForm, CarForm, CarExpiryProfileForm
from .models import Car, CarExpiryProfile, LegalAcceptance, EmailVerificationToken


STAR_POSITIONS = [
    {'key': 'itp', 'top': '14%', 'left': '50%'},
    {'key': 'rca', 'top': '33%', 'left': '77%'},
    {'key': 'rovinieta', 'top': '76%', 'left': '65%'},
    {'key': 'casco', 'top': '76%', 'left': '35%'},
    {'key': 'siguranta_auto', 'top': '33%', 'left': '23%'},
]

ALLOWED_DOCUMENT_TYPES = {'ITP', 'RCA', 'ROVINIETA', 'CASCO', 'TRUSA', 'EXTINCTOR', 'TALON', 'NECUNOSCUT'}
ALLOWED_CONFIDENCE = {'high', 'medium', 'low'}


def _client_ip(request):
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return forwarded or request.META.get('REMOTE_ADDR')


def _record_legal_acceptance(user, request):
    LegalAcceptance.objects.update_or_create(
        user=user,
        defaults={
            'document_set': 'platform',
            'terms_version': settings.LEGAL_DOCUMENTS_VERSION,
            'privacy_version': settings.LEGAL_DOCUMENTS_VERSION,
            'cookies_version': settings.LEGAL_DOCUMENTS_VERSION,
            'accepted_at': timezone.now(),
            'ip_address': _client_ip(request),
        },
    )


def _has_current_legal_acceptance(user):
    acceptance = getattr(user, 'legal_acceptance', None)
    if not acceptance:
        return False
    current = settings.LEGAL_DOCUMENTS_VERSION
    return all([
        acceptance.terms_version == current,
        acceptance.privacy_version == current,
        acceptance.cookies_version == current,
    ])




def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = (user.email or '').strip().lower()
            user.is_active = False
            user.save()
            _record_legal_acceptance(user, request)
            token, _ = EmailVerificationToken.objects.update_or_create(
                user=user,
                defaults={'token': secrets.token_urlsafe(32), 'verified_at': None},
            )
            sent = send_verification_email(user, token)
            if sent:
                messages.success(request, 'Contul a fost creat. Ți-am trimis un email de confirmare. Verifică inbox-ul înainte să te autentifici.')
            else:
                messages.warning(request, 'Contul a fost creat, dar emailul de confirmare nu a putut fi trimis. Verifică setările SMTP și încearcă din nou.')
            return redirect('accounts:login')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        attempted_username = (request.POST.get('username') or '').strip()
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if not _has_current_legal_acceptance(user):
                messages.warning(request, 'Pentru a continua, trebuie să accepți documentele legale actualizate.')
                return redirect('accounts:accept_legal')
            messages.success(request, f'Bun venit înapoi, {user.first_name or user.username}!')
            next_url = request.GET.get('next')
            return redirect(next_url or 'core:home')
        if attempted_username:
            inactive_user = User.objects.filter(username__iexact=attempted_username, is_active=False).first()
            if inactive_user:
                messages.error(request, 'Contul tău nu este încă verificat pe email. Deschide linkul primit în inbox înainte să te autentifici.')
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Ai fost deconectat.')
    return redirect('core:home')


@login_required
def accept_legal_view(request):
    if request.method == 'POST':
        accepted = request.POST.get('accept_terms') == 'on'
        if accepted:
            _record_legal_acceptance(request.user, request)
            messages.success(request, 'Documentele legale au fost acceptate cu succes.')
            next_url = request.GET.get('next') or request.POST.get('next')
            return redirect(next_url or 'core:home')
        messages.error(request, 'Trebuie să bifezi acceptarea pentru a continua.')

    return render(request, 'accounts/accept_legal.html', {
        'legal_version': settings.LEGAL_DOCUMENTS_VERSION,
        'next_url': request.GET.get('next', ''),
    })


@login_required
def profile(request):
    from bookings.models import Booking

    bookings = Booking.objects.filter(user=request.user).select_related(
        'center', 'center__category'
    ).order_by('-created_at')
    favorites = Favorite.objects.filter(user=request.user).select_related(
        'center', 'center__category'
    ).order_by('-created_at')
    cars = list(Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number'))

    for car in cars:
        expiry_profile = getattr(car, 'expiry_profile', None)
        car.expiry_badge = expiry_profile.get_dashboard_badge() if expiry_profile else {
            'label': 'Nesetat',
            'class': 'secondary',
            'icon': 'bi-dash-circle',
        }

    return render(request, 'accounts/profile.html', {
        'bookings': bookings,
        'favorites': favorites,
        'cars': cars,
    })


@login_required
def car_list(request):
    cars = list(Car.objects.filter(owner=request.user).order_by('make', 'model', 'plate_number'))
    for car in cars:
        expiry_profile = getattr(car, 'expiry_profile', None)
        car.expiry_badge = expiry_profile.get_dashboard_badge() if expiry_profile else {
            'label': 'Nesetat',
            'class': 'secondary',
            'icon': 'bi-dash-circle',
        }
    return render(request, 'accounts/car_list.html', {'cars': cars})


@login_required
def car_create(request):
    if request.method == 'POST':
        form = CarForm(request.POST)
        if form.is_valid():
            car = form.save(commit=False)
            car.owner = request.user
            car.save()
            messages.success(request, '✅ Mașina a fost adăugată în cont.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'accounts:cars')
    else:
        form = CarForm()
    return render(request, 'accounts/car_form.html', {
        'form': form,
        'mode': 'create',
    })


@login_required
def car_update(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CarForm(request.POST, instance=car)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Mașina a fost actualizată.')
            next_url = request.GET.get('next')
            return redirect(next_url or 'accounts:cars')
    else:
        form = CarForm(instance=car)
    return render(request, 'accounts/car_form.html', {
        'form': form,
        'mode': 'update',
        'car': car,
    })


@login_required
def car_delete(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    if request.method == 'POST':
        car.delete()
        messages.info(request, 'Mașina a fost ștearsă.')
        next_url = request.GET.get('next')
        return redirect(next_url or 'accounts:cars')
    return render(request, 'accounts/car_confirm_delete.html', {'car': car})



@login_required
def car_service_history(request, pk):
    from bookings.models import Booking

    car = get_object_or_404(Car, pk=pk, owner=request.user)
    history = Booking.objects.filter(
        status=Booking.STATUS_DONE,
    ).filter(
        models.Q(car_vin__iexact=car.vin) | models.Q(car_plate__iexact=car.plate_number)
    ).select_related('center', 'mechanic').order_by('-booking_date', '-booking_time', '-created_at')

    return render(request, 'accounts/car_history.html', {
        'car': car,
        'history': history,
    })

def _pick_worst_status(*items):
    priority = {
        CarExpiryProfile.STATUS_EXPIRED: 3,
        CarExpiryProfile.STATUS_SOON: 2,
        CarExpiryProfile.STATUS_MISSING: 1,
        CarExpiryProfile.STATUS_OK: 0,
    }
    valid_items = [item for item in items if item]
    if not valid_items:
        return CarExpiryProfile.STATUS_MISSING
    return max(valid_items, key=lambda item: priority[item['status']])['status']


SECTION_FIELDS = {
    'itp': ['itp_expiry'],
    'rca': ['rca_expiry'],
    'rovinieta': ['rovinieta_expiry'],
    'casco': ['casco_expiry'],
    'siguranta_auto': ['trusa_expiry', 'extinctor_expiry'],
}


@login_required
def car_expiry_calendar(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    expiry_profile, _ = CarExpiryProfile.objects.get_or_create(car=car)

    active_section = request.GET.get('section', '')

    if request.method == 'POST':
        active_section = request.POST.get('active_section', '')
        changed_fields = SECTION_FIELDS.get(active_section, [])
        form = CarExpiryProfileForm(instance=expiry_profile)

        if not changed_fields:
            messages.error(request, 'Categoria selectată nu este validă.')
        else:
            posted_values = {}
            field_errors = []

            for field_name in changed_fields:
                raw_value = (request.POST.get(field_name) or '').strip()
                if not raw_value:
                    posted_values[field_name] = None
                    continue

                parsed_value = parse_date(raw_value)
                if parsed_value is None:
                    field_label = form.fields[field_name].label or field_name
                    field_errors.append(f'{field_label}: data introdusă nu este validă.')
                else:
                    posted_values[field_name] = parsed_value

            if field_errors:
                for error in field_errors:
                    messages.error(request, error)
            else:
                for field_name, value in posted_values.items():
                    setattr(expiry_profile, field_name, value)
                if posted_values:
                    expiry_profile.save(update_fields=[*posted_values.keys(), 'updated_at'])
                messages.success(request, 'Calendarul de expirări a fost actualizat.')
                redirect_url = f"{redirect('accounts:car_calendar', pk=car.pk).url}?section={active_section or 'itp'}"
                return redirect(redirect_url)
    else:
        form = CarExpiryProfileForm(instance=expiry_profile)

    items_by_field = {item['field']: item for item in expiry_profile.get_document_items()}
    counts = expiry_profile.get_status_counts()

    node_map = {
        'itp': {
            'key': 'itp',
            'label': 'ITP',
            'icon': 'bi-shield-check',
            'status': items_by_field['itp_expiry']['status'],
            'date': items_by_field['itp_expiry']['date'],
            'days_left': items_by_field['itp_expiry']['days_left'],
            'days_overdue': items_by_field['itp_expiry']['days_overdue'],
            'description': 'Inspecția tehnică periodică a mașinii.',
        },
        'rca': {
            'key': 'rca',
            'label': 'RCA',
            'icon': 'bi-file-earmark-text',
            'status': items_by_field['rca_expiry']['status'],
            'date': items_by_field['rca_expiry']['date'],
            'days_left': items_by_field['rca_expiry']['days_left'],
            'days_overdue': items_by_field['rca_expiry']['days_overdue'],
            'description': 'Asigurarea obligatorie a vehiculului.',
        },
        'rovinieta': {
            'key': 'rovinieta',
            'label': 'Rovinietă',
            'icon': 'bi-sign-turn-right',
            'status': items_by_field['rovinieta_expiry']['status'],
            'date': items_by_field['rovinieta_expiry']['date'],
            'days_left': items_by_field['rovinieta_expiry']['days_left'],
            'days_overdue': items_by_field['rovinieta_expiry']['days_overdue'],
            'description': 'Valabilitatea rovinietei pentru drumurile naționale.',
        },
        'casco': {
            'key': 'casco',
            'label': 'CASCO',
            'icon': 'bi-shield-shaded',
            'status': items_by_field['casco_expiry']['status'],
            'date': items_by_field['casco_expiry']['date'],
            'days_left': items_by_field['casco_expiry']['days_left'],
            'days_overdue': items_by_field['casco_expiry']['days_overdue'],
            'description': 'Asigurarea facultativă a mașinii.',
        },
        'siguranta_auto': {
            'key': 'siguranta_auto',
            'label': 'Siguranță auto',
            'icon': 'bi-shield-plus',
            'status': _pick_worst_status(items_by_field['trusa_expiry'], items_by_field['extinctor_expiry']),
            'date': None,
            'days_left': None,
            'days_overdue': 0,
            'description': 'Include trusa auto și extinctorul.',
            'subitems': [items_by_field['trusa_expiry'], items_by_field['extinctor_expiry']],
        },
    }

    star_nodes = []
    for position in STAR_POSITIONS:
        node = position.copy()
        node.update(node_map[position['key']])
        star_nodes.append(node)

    if active_section not in node_map:
        active_section = ''

    return render(request, 'accounts/car_calendar.html', {
        'car': car,
        'form': form,
        'expiry_profile': expiry_profile,
        'star_nodes': star_nodes,
        'status_counts': counts,
        'active_section': active_section,
    })


def _detecteaza_tip_document(text):
    t = text.upper()
    if any(x in t for x in ['CERTIFICAT DE INMATRICULARE', 'CERTIFICATUL DE ÎNMATRICULARE', 'AUTOTURISM M1', 'NUMAR DE INMATRICULARE', 'NUMĂR DE ÎNMATRICULARE']):
        return 'TALON'
    if any(x in t for x in ['INSPECTIE TEHNICA', 'ITP', 'INSPECȚIE TEHNICĂ']):
        return 'ITP'
    if any(x in t for x in ['ASIGURARE OBLIGATORIE', 'RCA', 'RASPUNDERE CIVILA', 'RĂSPUNDERE CIVILĂ', 'POLITA', 'POLIȚĂ']):
        return 'RCA'
    if any(x in t for x in ['ROVINIETA', 'ROVINIETĂ', 'VIGNETA', 'TAXA DE DRUM']):
        return 'ROVINIETA'
    if 'CASCO' in t:
        return 'CASCO'
    if any(x in t for x in ['TRUSA', 'TRUSĂ', 'PRIM AJUTOR']):
        return 'TRUSA'
    if any(x in t for x in ['EXTINCTOR', 'FIRE EXTINGUISHER']):
        return 'EXTINCTOR'
    return 'NECUNOSCUT'


def _extrage_data_expirare(text):
    text_clean = (text or '').replace('\n', ' ')
    patterns = [
        r'valabil[ăa]?\s*p[âa]n[ăa]\s*la\s*[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'data\s*expir[ăa]rii?\s*[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'expir[ăa]\s*la\s*[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'valabilitate\s*[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'p[âa]n[ăa]\s*la\s*[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'urm[ăa]toarea\s*inspec[tț]ie\s*[:\s]*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})',
        r'\b(\d{2}[./\-]\d{2}[./\-]\d{4})\b',
        r'\b(\d{4}[./\-]\d{2}[./\-]\d{2})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text_clean, re.IGNORECASE)
        if match:
            date_str = match.group(1).replace('/', '.').replace('-', '.')
            parts = date_str.split('.')
            if len(parts) == 3:
                try:
                    if len(parts[2]) == 4:
                        return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    if len(parts[0]) == 4:
                        return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
                except Exception:
                    continue
    return None


def _extrage_numar_inmatriculare(text):
    match = re.search(r'\b([A-Z]{1,2}\s*\d{2,3}\s*[A-Z]{2,3})\b', (text or '').upper())
    return match.group(1).replace(' ', '') if match else None


def _extrage_vin(text):
    match = re.search(r'\b([A-HJ-NPR-Z0-9]{17})\b', (text or '').upper())
    return match.group(1) if match else None


def _parseaza_text_ocr(text, hint_type=None):
    result = {
        'tip_document': hint_type or _detecteaza_tip_document(text or ''),
        'expiry_date': _extrage_data_expirare(text),
        'plate_number': _extrage_numar_inmatriculare(text),
        'vin': _extrage_vin(text),
        'confidence': 'low',
    }

    marci = [
        'DACIA', 'VOLKSWAGEN', 'VW', 'RENAULT', 'FORD', 'OPEL', 'BMW',
        'MERCEDES', 'AUDI', 'SKODA', 'TOYOTA', 'HYUNDAI', 'KIA',
        'PEUGEOT', 'CITROEN', 'FIAT', 'SEAT', 'HONDA', 'NISSAN'
    ]
    for marca in marci:
        if marca in (text or '').upper():
            result['make'] = marca.capitalize()
            break

    asiguratori = [
        'ALLIANZ', 'GROUPAMA', 'OMNIASIG', 'ASIROM', 'GENERALI',
        'UNIQA', 'GRAWE', 'EUROINS', 'GOTHAER'
    ]
    for asig in asiguratori:
        if asig in (text or '').upper():
            result['asigurator'] = asig.capitalize()
            break

    filled = sum(1 for v in result.values() if v and v != 'NECUNOSCUT')
    result['confidence'] = 'high' if filled >= 3 else ('medium' if filled >= 2 else 'low')
    return result


def _detect_media_type(data_url):
    if data_url.startswith('data:image/jpeg'):
        return 'image/jpeg'
    if data_url.startswith('data:image/png'):
        return 'image/png'
    if data_url.startswith('data:image/webp'):
        return 'image/webp'
    if data_url.startswith('data:image/gif'):
        return 'image/gif'
    return 'image/png'


def _strip_code_fences(raw_text):
    text = (raw_text or '').strip()
    if text.startswith('```'):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    return text


def _extract_json_object(raw_text):
    cleaned = _strip_code_fences(raw_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def _clean_text_value(value, upper=False, max_length=120):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    value = re.sub(r'\s+', ' ', value)[:max_length]
    return value.upper() if upper else value


def _normalize_document_type(value, hint_type=None, raw_text=''):
    value = _clean_text_value(value, upper=True, max_length=20)
    hint_type = _clean_text_value(hint_type, upper=True, max_length=20)
    aliases = {
        'ROVINIETĂ': 'ROVINIETA',
        'TRUSA AUTO': 'TRUSA',
        'TRUSĂ AUTO': 'TRUSA',
        'UNKNOWN': 'NECUNOSCUT',
    }
    value = aliases.get(value, value)
    if value in ALLOWED_DOCUMENT_TYPES and value != 'NECUNOSCUT':
        return value
    if hint_type in ALLOWED_DOCUMENT_TYPES and hint_type != 'NECUNOSCUT':
        return hint_type
    return _detecteaza_tip_document(raw_text or '')


def _extract_itp_date_from_talon(text):
    text = text or ''
    if not text:
        return None

    candidates = []
    for match in re.finditer(r'\b(\d{2})[./\-](\d{2})[./\-](\d{4})\b', text):
        context = text[max(0, match.start() - 24):match.start()].upper()
        if re.search(r'(?:\bB\b|\bI\b|\bI\.1\b|\bH\b|\bL1\b|PRIMA\s+INMATRICULARE|EMITERII)', context):
            continue
        try:
            parsed = parse_date(f"{match.group(3)}-{match.group(2)}-{match.group(1)}")
        except Exception:
            parsed = None
        if parsed:
            candidates.append(parsed)

    if candidates:
        return max(candidates).isoformat()
    return None


def _extract_contextual_expiry_date(raw_text='', hint_type=None, detected_doc_type=None):
    text = raw_text or ''
    hint_type = _clean_text_value(hint_type, upper=True, max_length=20)
    detected_doc_type = _clean_text_value(detected_doc_type, upper=True, max_length=20)

    if detected_doc_type == 'TALON':
        if hint_type == 'ITP':
            return _extract_itp_date_from_talon(text)
        if hint_type in {'RCA', 'ROVINIETA', 'CASCO', 'TRUSA', 'EXTINCTOR', 'TALON'}:
            return None
        return None

    return _extrage_data_expirare(text)


def _normalize_expiry_date(value, raw_text='', hint_type=None, detected_doc_type=None):
    candidate = _clean_text_value(value, max_length=30)
    contextual = _extract_contextual_expiry_date(raw_text, hint_type=hint_type, detected_doc_type=detected_doc_type)
    candidates = [candidate, contextual]
    for item in candidates:
        if not item:
            continue
        parsed = parse_date(item)
        if parsed:
            return parsed.isoformat()
        match = re.search(r'^(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})$', item)
        if match:
            day, month, year = match.groups()
            parsed = parse_date(f'{year}-{month.zfill(2)}-{day.zfill(2)}')
            if parsed:
                return parsed.isoformat()
    return None


def _normalize_plate_number(value, raw_text=''):
    candidate = _clean_text_value(value, upper=True, max_length=20)
    if candidate:
        candidate = re.sub(r'[^A-Z0-9]', '', candidate)
        if re.fullmatch(r'[A-Z]{1,2}\d{2,3}[A-Z]{2,3}', candidate):
            return candidate
    return _extrage_numar_inmatriculare(raw_text)


def _normalize_vin(value, raw_text=''):
    candidate = _clean_text_value(value, upper=True, max_length=30)
    if candidate:
        candidate = re.sub(r'[^A-Z0-9]', '', candidate)
        if re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}', candidate):
            return candidate
    return _extrage_vin(raw_text)


def _normalize_fuel(value, raw_text=''):
    candidate = _clean_text_value(value, upper=True, max_length=30)
    mapping = {
        'BENZINA': 'benzina',
        'BENZINĂ': 'benzina',
        'PETROL': 'benzina',
        'MOTORINA': 'motorina',
        'MOTORINĂ': 'motorina',
        'DIESEL': 'motorina',
        'HIBRID': 'hibrid',
        'HYBRID': 'hibrid',
        'ELECTRIC': 'electric',
        'ELECTRICA': 'electric',
        'ELECTRICĂ': 'electric',
        'GPL': 'gpl',
        'GAZ': 'gpl',
    }

    if candidate in mapping:
        return mapping[candidate]

    text = (raw_text or '').upper()
    p3_match = re.search(r'P\.?3\s*[:\-]?\s*([A-ZĂÂÎȘȚ ]+)', text)
    if p3_match:
        p3_value = p3_match.group(1).strip()
        for key, mapped in mapping.items():
            if key in p3_value:
                return mapped

    for key, mapped in mapping.items():
        if key in text:
            return mapped
    return None


def _normalize_manufacture_year(value, raw_text=''):
    if value is not None:
        try:
            year = int(value)
            if 1950 <= year <= 2100:
                return year
        except (TypeError, ValueError):
            pass

    text = raw_text or ''
    explicit_patterns = [
        r'an(?:ul)?\s+fabrica(?:ț|t)iei\s*[:\-]?\s*(\d{4})',
        r'fabrica(?:ț|t)ie\s*[:\-]?\s*(\d{4})',
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            if 1950 <= year <= 2100:
                return year

    b_match = re.search(r'\bB\s+(\d{2})\.(\d{2})\.(\d{4})', text)
    if b_match:
        return int(b_match.group(3))
    return None


def _normalize_first_registration_date(value, raw_text=''):
    date_value = _normalize_expiry_date(value, raw_text='')
    if date_value:
        return date_value

    text = raw_text or ''
    b_match = re.search(r'\bB\s+(\d{2})\.(\d{2})\.(\d{4})', text)
    if b_match:
        return f"{b_match.group(3)}-{b_match.group(2)}-{b_match.group(1)}"
    return None


def _normalize_confidence(value, normalized_data):
    candidate = _clean_text_value(value, upper=True, max_length=10)
    if candidate and candidate.lower() in ALLOWED_CONFIDENCE:
        return candidate.lower()

    score = sum(bool(normalized_data.get(field)) for field in [
        'expiry_date', 'plate_number', 'vin', 'make', 'model', 'fuel', 'manufacture_year', 'asigurator'
    ])
    if normalized_data.get('tip_document') and normalized_data['tip_document'] != 'NECUNOSCUT':
        score += 1
    if score >= 4:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'


def _build_fallback_from_text(raw_text, hint_type=None, detected_doc_type=None):
    parsed = _parseaza_text_ocr(raw_text or '', hint_type)
    parsed.setdefault('model', None)
    parsed.setdefault('asigurator', None)
    parsed['expiry_date'] = _extract_contextual_expiry_date(raw_text or '', hint_type=hint_type, detected_doc_type=detected_doc_type or parsed.get('tip_document'))
    parsed['raw_text'] = (raw_text or '')[:1200]
    return parsed


def _validate_and_normalize_ai_data(model_data, raw_output, hint_type=None):
    raw_text = _clean_text_value(
        model_data.get('raw_text') or model_data.get('detected_text') or model_data.get('text_excerpt') or raw_output,
        max_length=1200,
    ) or ''

    normalized_tip_document = _normalize_document_type(model_data.get('tip_document'), hint_type=hint_type, raw_text=raw_text)
    normalized = {
        'tip_document': normalized_tip_document,
        'expiry_date': _normalize_expiry_date(model_data.get('expiry_date'), raw_text=raw_text, hint_type=hint_type, detected_doc_type=normalized_tip_document),
        'plate_number': _normalize_plate_number(model_data.get('plate_number'), raw_text=raw_text),
        'vin': _normalize_vin(model_data.get('vin'), raw_text=raw_text),
        'make': _clean_text_value(model_data.get('make'), max_length=50),
        'model': _clean_text_value(model_data.get('model'), max_length=50),
        'fuel': _normalize_fuel(model_data.get('fuel'), raw_text=raw_text),
        'manufacture_year': _normalize_manufacture_year(model_data.get('manufacture_year'), raw_text=raw_text),
        'first_registration_date': _normalize_first_registration_date(model_data.get('first_registration_date'), raw_text=raw_text),
        'asigurator': _clean_text_value(model_data.get('asigurator'), max_length=60),
        'raw_text': raw_text,
    }
    normalized['confidence'] = _normalize_confidence(model_data.get('confidence'), normalized)

    fallback = _build_fallback_from_text(raw_text, hint_type, detected_doc_type=normalized_tip_document)
    warnings = []

    for key in ['expiry_date', 'plate_number', 'vin', 'make', 'model', 'fuel', 'manufacture_year', 'asigurator']:
        if not normalized.get(key) and fallback.get(key):
            normalized[key] = fallback[key]
            warnings.append(f'{key} a fost completat automat din textul detectat.')

    if normalized['tip_document'] == 'NECUNOSCUT' and fallback.get('tip_document') and fallback['tip_document'] != 'NECUNOSCUT':
        normalized['tip_document'] = fallback['tip_document']
        warnings.append('Tipul documentului a fost ajustat automat pe baza conținutului detectat.')

    normalized['confidence'] = _normalize_confidence(normalized.get('confidence'), normalized)
    return normalized, warnings


def _build_openai_prompt(hint_type=None):
    hint_line = (
        f'Tip document sugerat de utilizator: {hint_type}. Respectă-l doar dacă documentul susține clar alegerea.'
        if hint_type else
        'Nu există sugestie de tip document de la utilizator.'
    )
    return (
        'Analizează un document auto din România (talon / certificat de înmatriculare, RCA, ITP, rovinietă, CASCO, trusă, extinctor). '
        + hint_line + ' '
        + 'Răspunde exclusiv cu un singur obiect JSON valid, fără text înainte sau după el. '
        + 'Cheile permise sunt exact acestea: tip_document, expiry_date, plate_number, vin, make, model, fuel, manufacture_year, first_registration_date, asigurator, confidence, raw_text. '
        + 'Reguli: '
        + 'tip_document trebuie să fie unul dintre ITP, RCA, ROVINIETA, CASCO, TRUSA, EXTINCTOR, TALON, NECUNOSCUT; '
        + 'expiry_date trebuie să fie în format YYYY-MM-DD sau null; '
        + 'first_registration_date trebuie să fie în format YYYY-MM-DD sau null; '
        + 'manufacture_year trebuie să fie număr întreg sau null; '
        + 'fuel trebuie să fie una dintre valorile: benzina, motorina, hibrid, electric, gpl sau null; '
        + 'La TALON extrage explicit combustibilul din câmpul P.3 dacă există. '
        + 'La TALON, pentru anul de fabricație: dacă există explicit, folosește acel an; dacă nu există explicit, folosește anul din câmpul B ca fallback. '
        + 'Dacă utilizatorul a sugerat ITP dar documentul este TALON, caută data ITP-ului din anexă / inspecția tehnică, nu folosi datele B, I sau I.1 ca expiry_date. '
        + 'confidence trebuie să fie high, medium sau low; '
        + 'raw_text trebuie să conțină doar un extras relevant din document, maxim 1200 caractere; '
        + 'dacă nu găsești o valoare, pune null; nu folosi markdown și nu explica nimic.'
    )


SUPPORTED_SCAN_CONTENT_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword', 'application/vnd.oasis.opendocument.text',
    'application/rtf', 'text/rtf', 'text/plain',
}


def _guess_file_content_type(uploaded_file):
    content_type = (getattr(uploaded_file, 'content_type', '') or '').strip().lower()
    if content_type:
        return content_type

    name = (getattr(uploaded_file, 'name', '') or '').lower()
    ext_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.odt': 'application/vnd.oasis.opendocument.text',
        '.rtf': 'application/rtf',
        '.txt': 'text/plain',
    }
    for ext, mime in ext_map.items():
        if name.endswith(ext):
            return mime
    return 'application/octet-stream'


def _build_scan_content_items(*, image_source=None, uploaded_file=None):
    content_items = []
    if image_source:
        media_type = _detect_media_type(image_source)
        image_data = image_source.split(',', 1)[1] if ',' in image_source else image_source
        content_items.append({
            'type': 'input_image',
            'image_url': f'data:{media_type};base64,{image_data}',
            'detail': 'high',
        })
        return content_items

    if not uploaded_file:
        raise ValueError('Nu ai trimis nici imagine, nici document.')

    content_type = _guess_file_content_type(uploaded_file)
    if content_type not in SUPPORTED_SCAN_CONTENT_TYPES:
        raise ValueError('Formatul documentului nu este acceptat. Încarcă JPG, PNG, WEBP, PDF, DOC, DOCX, ODT, RTF sau TXT.')

    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)
    if not file_bytes:
        raise ValueError('Fișierul încărcat este gol.')

    file_b64 = __import__('base64').b64encode(file_bytes).decode('ascii')
    if content_type.startswith('image/'):
        content_items.append({
            'type': 'input_image',
            'image_url': f'data:{content_type};base64,{file_b64}',
            'detail': 'high',
        })
    else:
        content_items.append({
            'type': 'input_file',
            'file_data': f'data:{content_type};base64,{file_b64}',
            'filename': getattr(uploaded_file, 'name', 'document'),
            'detail': 'high',
        })
    return content_items


def _call_openai_document_scan(*, image_source=None, uploaded_file=None, hint_type=None):
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY lipsește. Adaugă cheia în .env sau settings.py.')

    content_items = _build_scan_content_items(image_source=image_source, uploaded_file=uploaded_file)
    content_items.append({
        'type': 'input_text',
        'text': _build_openai_prompt(hint_type),
    })

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': getattr(settings, 'OPENAI_MODEL', 'gpt-4.1-mini'),
        'input': [
            {
                'role': 'developer',
                'content': [
                    {
                        'type': 'input_text',
                        'text': 'Răspunde exclusiv cu un singur obiect JSON valid, fără markdown și fără text suplimentar.',
                    }
                ],
            },
            {
                'role': 'user',
                'content': content_items,
            },
        ],
        'max_output_tokens': 900,
    }

    resp = http_requests.post('https://api.openai.com/v1/responses', headers=headers, json=payload, timeout=45)
    if resp.status_code != 200:
        try:
            error_data = resp.json()
        except Exception:
            error_data = {'raw': resp.text[:1000]}
        error_message = None
        if isinstance(error_data, dict):
            error_message = error_data.get('error', {}).get('message') or error_data.get('message')
        raise RuntimeError(error_message or 'OpenAI API a returnat o eroare.')

    response_data = resp.json()
    raw_output = (response_data.get('output_text') or '').strip()
    if not raw_output:
        output_items = response_data.get('output', []) or []
        collected = []
        for item in output_items:
            for content_item in item.get('content', []) or []:
                if content_item.get('type') == 'output_text' and content_item.get('text'):
                    collected.append(content_item.get('text', ''))
        raw_output = '\n'.join(collected).strip()
    if not raw_output:
        raise RuntimeError('OpenAI nu a returnat conținut text pentru scanare.')

    try:
        ai_json = _extract_json_object(raw_output)
    except json.JSONDecodeError:
        raise RuntimeError(f'Modelul a răspuns, dar nu cu JSON valid. Răspuns brut: {raw_output[:1200]}')

    normalized, warnings = _validate_and_normalize_ai_data(ai_json, raw_output, hint_type=hint_type)
    return normalized, warnings


def _scan_request_payload(request):
    hint_type = request.POST.get('hint_type') or None
    uploaded_file = request.FILES.get('document')
    image_source = ''
    if request.content_type and 'application/json' in request.content_type:
        body = json.loads(request.body or '{}')
        image_source = body.get('image', '')
        hint_type = body.get('hint_type') or hint_type
    return image_source, uploaded_file, hint_type


@login_required
@require_POST
def document_scan_api(request):
    try:
        image_source, uploaded_file, hint_type = _scan_request_payload(request)
        if not image_source and not uploaded_file:
            return JsonResponse({'error': 'Încarcă un document sau o imagine pentru scanare.'}, status=400)

        normalized, warnings = _call_openai_document_scan(
            image_source=image_source or None,
            uploaded_file=uploaded_file,
            hint_type=hint_type,
        )
        result = {'success': True, 'data': normalized}
        if warnings:
            result['warning'] = ' '.join(warnings)
        return JsonResponse(result)
    except http_requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Eroare conexiune OpenAI: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def car_scan_document(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)
    expiry_profile, _ = CarExpiryProfile.objects.get_or_create(car=car)
    return render(request, 'accounts/car_scan.html', {
        'car': car,
        'expiry_profile': expiry_profile,
    })


@login_required
@require_POST
def car_scan_api(request, pk):
    get_object_or_404(Car, pk=pk, owner=request.user)

    try:
        image_source, uploaded_file, hint_type = _scan_request_payload(request)
        if not image_source and not uploaded_file:
            return JsonResponse({'error': 'Încarcă un document sau o imagine pentru scanare.'}, status=400)

        normalized, warnings = _call_openai_document_scan(
            image_source=image_source or None,
            uploaded_file=uploaded_file,
            hint_type=hint_type,
        )
        result = {'success': True, 'data': normalized}
        if warnings:
            result['warning'] = ' '.join(warnings)
        return JsonResponse(result)
    except http_requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Eroare conexiune OpenAI: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def car_scan_save(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)

    try:
        body = json.loads(request.body)
        target_document = body.get('target_document') or body.get('hint_type') or body.get('tip_document')
        normalized_body, validation_warnings = _validate_and_normalize_ai_data(body, body.get('raw_text', ''), hint_type=target_document)
        fields_updated = []

        car_changed = False
        for field in ['make', 'model', 'vin', 'plate_number', 'fuel']:
            val = normalized_body.get(field)
            if isinstance(val, str):
                val = val.strip()
            if val and not getattr(car, field, ''):
                setattr(car, field, val)
                car_changed = True
                fields_updated.append(field)

        year_value = normalized_body.get('manufacture_year')
        if year_value and not car.year:
            car.year = year_value
            car_changed = True
            fields_updated.append('year')

        if car_changed:
            car.save()

        expiry_profile, _ = CarExpiryProfile.objects.get_or_create(car=car)
        tip = _clean_text_value(target_document or normalized_body.get('tip_document'), upper=True, max_length=20) or ''
        expiry_date = parse_date((normalized_body.get('expiry_date') or '').strip())

        field_map = {
            'ITP': 'itp_expiry',
            'RCA': 'rca_expiry',
            'ROVINIETA': 'rovinieta_expiry',
            'CASCO': 'casco_expiry',
            'TRUSA': 'trusa_expiry',
            'EXTINCTOR': 'extinctor_expiry',
        }

        if tip in field_map and expiry_date:
            field_name = field_map[tip]
            setattr(expiry_profile, field_name, expiry_date)
            expiry_profile.save(update_fields=[field_name, 'updated_at'])
            fields_updated.append(field_name)

        label_map = {
            'make': 'Marcă',
            'model': 'Model',
            'vin': 'VIN',
            'plate_number': 'Nr. înmatriculare',
            'fuel': 'Combustibil',
            'year': 'An fabricație',
            'itp_expiry': 'ITP',
            'rca_expiry': 'RCA',
            'rovinieta_expiry': 'Rovinietă',
            'casco_expiry': 'CASCO',
            'trusa_expiry': 'Trusă',
            'extinctor_expiry': 'Extinctor',
        }
        labels = [label_map.get(f, f) for f in fields_updated]
        message = f'Salvat: {", ".join(labels)}' if labels else 'Nimic de salvat.'
        if validation_warnings:
            message += ' Verificări automate: ' + ' '.join(validation_warnings)

        return JsonResponse({
            'success': True,
            'fields_updated': fields_updated,
            'message': message,
            'normalized_data': normalized_body,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def verify_email_view(request, token):
    verification = get_object_or_404(EmailVerificationToken.objects.select_related('user'), token=token)
    if verification.is_verified:
        messages.info(request, 'Adresa de email a fost deja confirmată. Te poți autentifica.')
        return redirect('accounts:login')
    if verification.is_expired():
        verification.token = secrets.token_urlsafe(32)
        verification.created_at = timezone.now()
        verification.save(update_fields=['token', 'created_at'])
        send_verification_email(verification.user, verification)
        messages.error(request, 'Linkul de confirmare a expirat. Ți-am trimis automat unul nou pe email.')
        return redirect('accounts:login')

    verification.verified_at = timezone.now()
    verification.save(update_fields=['verified_at'])
    user = verification.user
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=['is_active'])
    messages.success(request, 'Email confirmat cu succes. Acum te poți autentifica.')
    return redirect('accounts:login')
