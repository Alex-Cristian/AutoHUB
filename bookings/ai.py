import json
import math
from typing import Optional

import requests
from django.conf import settings


DEFAULT_DURATION_MINUTES = 60
ALLOWED_DURATION_STEPS = [30 * step for step in range(1, 17)]

KEYWORD_ESTIMATES = [
    (("schimb ulei", "ulei", "filtru ulei", "filtre", "revizie"), 90, 'Revizie ușoară / schimb ulei și filtre.'),
    (("diagnoză", "diagnostic", "tester", "eroare motor"), 60, 'Diagnoză inițială.'),
    (("plăcuțe", "placute", "frâne", "frana", "discuri"), 120, 'Intervenție uzuală la sistemul de frânare.'),
    (("baterie", "acumulator"), 60, 'Înlocuire / verificare acumulator.'),
    (("ambreiaj",), 360, 'Lucrare complexă la transmisie.'),
    (("distribuție", "distributie", "curea distribuție"), 300, 'Lucrare complexă la distribuție.'),
    (("turbin",), 300, 'Intervenție complexă la turbină / admisie.'),
    (("suspensie", "amortizor", "bielet", "braț", "brat"), 180, 'Lucrare medie la suspensie / direcție.'),
    (("cutie viteze",), 360, 'Lucrare complexă la cutia de viteze.'),
    (("detailing", "polish", "polishare", "ceramic", "spălare interior", "spalare interior"), 180, 'Serviciu de detailing / cosmetică.'),
]


def normalize_duration_minutes(value: Optional[int]) -> int:
    try:
        minutes = int(value or DEFAULT_DURATION_MINUTES)
    except (TypeError, ValueError):
        minutes = DEFAULT_DURATION_MINUTES
    minutes = max(30, minutes)
    rounded = int(math.ceil(minutes / 30.0) * 30)
    return min(rounded, ALLOWED_DURATION_STEPS[-1])


def heuristic_duration_estimate(problem_description: str = '', service_name: str = '', car_data: Optional[dict] = None) -> dict:
    text = ' '.join([
        (service_name or '').strip().lower(),
        (problem_description or '').strip().lower(),
        ' '.join(str(v).lower() for v in (car_data or {}).values() if v),
    ])
    for keywords, minutes, reason in KEYWORD_ESTIMATES:
        if any(keyword in text for keyword in keywords):
            return {
                'minutes': normalize_duration_minutes(minutes),
                'source': 'heuristic',
                'reason': reason,
            }
    fallback_minutes = 90 if (service_name or '').strip() else DEFAULT_DURATION_MINUTES
    return {
        'minutes': normalize_duration_minutes(fallback_minutes),
        'source': 'fallback',
        'reason': 'Estimare implicită folosită momentan.',
    }


def _extract_output_text(data: dict) -> str:
    raw_text = (data.get('output_text') or '').strip()
    if raw_text:
        return raw_text
    for item in data.get('output', []) or []:
        for content in item.get('content', []) or []:
            if content.get('type') in {'output_text', 'text'} and content.get('text'):
                return str(content.get('text')).strip()
    return ''


def estimate_booking_duration(problem_description: str, service_name: str = '', car_data: Optional[dict] = None, center_name: str = '') -> dict:
    description = (problem_description or '').strip()
    service_name = (service_name or '').strip()
    center_name = (center_name or '').strip()
    car_data = car_data or {}

    heuristic = heuristic_duration_estimate(description, service_name=service_name, car_data=car_data)

    if not description and not service_name:
        return heuristic

    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return heuristic

    model = getattr(settings, 'OPENAI_MODEL', 'gpt-4.1-mini')
    prompt = (
        'Ești consilier de service auto și estimezi prudent durata totală de lucru pentru o programare. '
        'Primești serviciul ales, descrierea problemei, datele mașinii și numele service-ului. '
        'Dacă există interval, alege capătul superior. '
        'Ține cont de complexitatea lucrării și de faptul că unele operațiuni includ demontare / montare / testare. '
        'Returnează strict JSON valid conform schemei.'
    )

    schema = {
        'type': 'object',
        'properties': {
            'minutes': {
                'type': 'integer',
                'minimum': 30,
                'maximum': 480,
                'description': 'Durata totală estimată în minute.'
            },
            'reason': {
                'type': 'string',
                'description': 'Motiv scurt pentru estimare.'
            }
        },
        'required': ['minutes', 'reason'],
        'additionalProperties': False,
    }

    payload = {
        'model': model,
        'input': [
            {
                'role': 'developer',
                'content': [{'type': 'input_text', 'text': prompt}],
            },
            {
                'role': 'user',
                'content': [{
                    'type': 'input_text',
                    'text': json.dumps({
                        'center_name': center_name,
                        'service_name': service_name,
                        'problem_description': description,
                        'car': {
                            'brand': car_data.get('brand', ''),
                            'model': car_data.get('model', ''),
                            'year': car_data.get('year', ''),
                            'fuel': car_data.get('fuel', ''),
                            'plate': car_data.get('plate', ''),
                            'vin': car_data.get('vin', ''),
                        },
                        'fallback_estimate_minutes': heuristic['minutes'],
                    }, ensure_ascii=False),
                }],
            },
        ],
        'temperature': 0.1,
        'max_output_tokens': 160,
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'booking_duration_estimate',
                'strict': True,
                'schema': schema,
            }
        },
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post('https://api.openai.com/v1/responses', headers=headers, json=payload, timeout=25)
        response.raise_for_status()
        data = response.json()
        raw_text = _extract_output_text(data)
        if not raw_text:
            raise ValueError('Răspuns gol de la OpenAI.')
        parsed = json.loads(raw_text)
        minutes = normalize_duration_minutes(parsed.get('minutes'))
        return {
            'minutes': minutes,
            'source': 'openai',
            'reason': (parsed.get('reason') or '').strip()[:240] or 'Estimare OpenAI.',
            'model': model,
        }
    except Exception as exc:
        heuristic['reason'] = f"{heuristic['reason']} (fallback: {exc})"[:240]
        return heuristic
