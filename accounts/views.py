from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

import json
import re
import requests as http_requests

from services.models import Favorite
from .forms import RegisterForm, LoginForm, CarForm, CarExpiryProfileForm
from .models import Car, CarExpiryProfile


STAR_POSITIONS = [
    {'key': 'itp', 'top': '14%', 'left': '50%'},
    {'key': 'rca', 'top': '33%', 'left': '77%'},
    {'key': 'rovinieta', 'top': '76%', 'left': '65%'},
    {'key': 'casco', 'top': '76%', 'left': '35%'},
    {'key': 'siguranta_auto', 'top': '33%', 'left': '23%'},
]

ALLOWED_DOCUMENT_TYPES = {'ITP', 'RCA', 'ROVINIETA', 'CASCO', 'TRUSA', 'EXTINCTOR', 'NECUNOSCUT'}
ALLOWED_CONFIDENCE = {'high', 'medium', 'low'}


def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Bun venit, {user.first_name}! Contul tău a fost creat.')
            return redirect('core:home')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bun venit înapoi, {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'core:home')
            return redirect(next_url)
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Ai fost deconectat.')
    return redirect('core:home')


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


def _normalize_expiry_date(value, raw_text=''):
    candidate = _clean_text_value(value, max_length=30)
    candidates = [candidate, _extrage_data_expirare(raw_text)]
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


def _normalize_confidence(value, normalized_data):
    candidate = _clean_text_value(value, upper=True, max_length=10)
    if candidate and candidate.lower() in ALLOWED_CONFIDENCE:
        return candidate.lower()

    score = sum(bool(normalized_data.get(field)) for field in [
        'expiry_date', 'plate_number', 'vin', 'make', 'model', 'asigurator'
    ])
    if normalized_data.get('tip_document') and normalized_data['tip_document'] != 'NECUNOSCUT':
        score += 1
    if score >= 4:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'


def _build_fallback_from_text(raw_text, hint_type=None):
    parsed = _parseaza_text_ocr(raw_text or '', hint_type)
    parsed.setdefault('model', None)
    parsed.setdefault('asigurator', None)
    parsed['raw_text'] = (raw_text or '')[:1200]
    return parsed


def _validate_and_normalize_ai_data(model_data, raw_output, hint_type=None):
    raw_text = _clean_text_value(
        model_data.get('raw_text') or model_data.get('detected_text') or model_data.get('text_excerpt') or raw_output,
        max_length=1200,
    ) or ''

    normalized = {
        'tip_document': _normalize_document_type(model_data.get('tip_document'), hint_type=hint_type, raw_text=raw_text),
        'expiry_date': _normalize_expiry_date(model_data.get('expiry_date'), raw_text=raw_text),
        'plate_number': _normalize_plate_number(model_data.get('plate_number'), raw_text=raw_text),
        'vin': _normalize_vin(model_data.get('vin'), raw_text=raw_text),
        'make': _clean_text_value(model_data.get('make'), max_length=50),
        'model': _clean_text_value(model_data.get('model'), max_length=50),
        'asigurator': _clean_text_value(model_data.get('asigurator'), max_length=60),
        'raw_text': raw_text,
    }
    normalized['confidence'] = _normalize_confidence(model_data.get('confidence'), normalized)

    fallback = _build_fallback_from_text(raw_text, hint_type)
    warnings = []

    for key in ['expiry_date', 'plate_number', 'vin', 'make', 'asigurator']:
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
        'Analizează imaginea unui document auto din România. '\
        + hint_line + ' '\
        + 'Răspunde exclusiv cu un singur obiect JSON valid, fără text înainte sau după el. '\
        + 'Cheile permise sunt exact acestea: tip_document, expiry_date, plate_number, vin, make, model, asigurator, confidence, raw_text. '\
        + 'Reguli: tip_document trebuie să fie unul dintre ITP, RCA, ROVINIETA, CASCO, TRUSA, EXTINCTOR, NECUNOSCUT; '\
        + 'expiry_date trebuie să fie în format YYYY-MM-DD sau null; '\
        + 'confidence trebuie să fie high, medium sau low; '\
        + 'raw_text trebuie să conțină doar un extras relevant din document, maxim 1200 caractere; '\
        + 'dacă nu găsești o valoare, pune null; nu folosi markdown și nu explica nimic.'
    )


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
        body = json.loads(request.body)
        image_source = body.get('image', '')
        hint_type = body.get('hint_type')

        if not image_source:
            return JsonResponse({'error': 'Lipsește imaginea.'}, status=400)

        media_type = _detect_media_type(image_source)
        image_data = image_source.split(',', 1)[1] if ',' in image_source else image_source

        api_key = getattr(settings, 'OPENAI_API_KEY', '')
        if not api_key:
            return JsonResponse({'error': 'OPENAI_API_KEY lipsește. Adaugă cheia în .env sau settings.py.'}, status=500)

        data_url = f'data:{media_type};base64,{image_data}'
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
                    'content': [
                        {
                            'type': 'input_image',
                            'image_url': data_url,
                            'detail': 'high',
                        },
                        {
                            'type': 'input_text',
                            'text': _build_openai_prompt(hint_type),
                        },
                    ],
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
            return JsonResponse({
                'error': error_message or 'OpenAI API a returnat o eroare.',
                'status_code': resp.status_code,
                'details': error_data,
            }, status=500)

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
            return JsonResponse({'error': 'OpenAI nu a returnat conținut text pentru scanare.'}, status=500)

        try:
            ai_json = _extract_json_object(raw_output)
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Modelul a răspuns, dar nu cu JSON valid.',
                'raw_output': raw_output[:1200],
            }, status=500)

        normalized, warnings = _validate_and_normalize_ai_data(ai_json, raw_output, hint_type=hint_type)
        result = {'success': True, 'data': normalized}
        if warnings:
            result['warning'] = ' '.join(warnings)
        return JsonResponse(result)

    except http_requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Eroare conexiune OpenAI: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Eroare: {str(e)}'}, status=500)


@login_required
@require_POST
def car_scan_save(request, pk):
    car = get_object_or_404(Car, pk=pk, owner=request.user)

    try:
        body = json.loads(request.body)
        normalized_body, validation_warnings = _validate_and_normalize_ai_data(body, body.get('raw_text', ''), hint_type=body.get('tip_document'))
        fields_updated = []

        car_changed = False
        for field in ['make', 'model', 'vin', 'plate_number']:
            val = (normalized_body.get(field) or '').strip()
            if val and not getattr(car, field, ''):
                setattr(car, field, val)
                car_changed = True
                fields_updated.append(field)

        if car_changed:
            car.save()

        expiry_profile, _ = CarExpiryProfile.objects.get_or_create(car=car)
        tip = (normalized_body.get('tip_document') or '').upper()
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
