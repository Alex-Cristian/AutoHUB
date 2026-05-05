import json
import math
import re
import unicodedata
from typing import Optional

import requests
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError


DEFAULT_DURATION_MINUTES = 60
ALLOWED_DURATION_STEPS = [30 * step for step in range(1, 17)]

OPERATION_CATALOG = [
    {
        "slug": "diagnosticare_generala",
        "label": "Diagnosticare generala",
        "minutes": 60,
        "reason": "Diagnoza initiala si verificare de baza.",
        "keywords": ["diagnoza", "diagnostic", "tester", "eroare motor", "martor bord", "check engine"],
        "category_hints": ["diagnoza", "electrica", "mecanica"],
    },
    {
        "slug": "revizie_ulei_filtre",
        "label": "Revizie / schimb ulei si filtre",
        "minutes": 90,
        "reason": "Revizie usoara sau schimb de ulei si filtre.",
        "keywords": ["schimb ulei", "ulei", "filtru ulei", "filtre", "revizie", "revizie completa"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "franare_placute_discuri",
        "label": "Placute / discuri frana",
        "minutes": 120,
        "reason": "Interventie uzuala la sistemul de franare.",
        "keywords": ["placute", "placute frana", "frane", "frana", "discuri"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "baterie_acumulator",
        "label": "Baterie / acumulator",
        "minutes": 60,
        "reason": "Verificare sau inlocuire acumulator.",
        "keywords": ["baterie", "acumulator", "nu porneste", "curent"],
        "category_hints": ["electrica"],
    },
    {
        "slug": "alternator_fulie_accesorii",
        "label": "Alternator / fulie / curea accesorii",
        "minutes": 120,
        "reason": "Interventie pe alternator sau transmisia de accesorii, cu verificare si inlocuire piese asociate.",
        "keywords": ["alternator", "fulie alternator", "fulie de alternator", "curea accesorii", "rola alternator", "intinzator accesorii"],
        "category_hints": ["electrica", "mecanica"],
    },
    {
        "slug": "electromotor_demaror",
        "label": "Electromotor / demaror",
        "minutes": 120,
        "reason": "Verificare si posibila interventie pe sistemul de pornire.",
        "keywords": ["electromotor", "demaror", "nu invarte", "pornire grea"],
        "category_hints": ["electrica"],
    },
    {
        "slug": "planetara_transmisie",
        "label": "Planetara / cap planetara",
        "minutes": 180,
        "reason": "Verificare si posibil inlocuire elemente din transmisie planetara.",
        "keywords": ["planetara", "planetare", "cap planetara", "bataie la planetara", "trosneste la viraj"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "ambreiaj_volanta",
        "label": "Ambreiaj / volanta",
        "minutes": 360,
        "reason": "Lucrare complexa la transmisie si ambreiaj.",
        "keywords": ["ambreiaj", "kit ambreiaj", "volanta", "pedala ambreiaj", "patineaza"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "distributie",
        "label": "Curea sau lant distributie",
        "minutes": 300,
        "reason": "Lucrare complexa la distributie.",
        "keywords": ["distributie", "curea distributie", "lant distributie"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "turbina_admisie",
        "label": "Turbina / admisie",
        "minutes": 300,
        "reason": "Interventie complexa la turbina sau admisie.",
        "keywords": ["turbin", "turbina", "nu mai trage", "pierde putere"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "injectie_injectoare",
        "label": "Injectie / injectoare",
        "minutes": 240,
        "reason": "Constatare si interventie pe sistemul de injectie.",
        "keywords": ["injector", "injectoare", "injectie", "merge in 3"],
        "category_hints": ["mecanica", "electrica"],
    },
    {
        "slug": "egr_admisie",
        "label": "EGR / admisie",
        "minutes": 180,
        "reason": "Curatare sau interventie pe EGR si admisie.",
        "keywords": ["egr", "supapa egr", "admisie"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "dpf_filtru_particule",
        "label": "DPF / filtru particule",
        "minutes": 180,
        "reason": "Diagnoza si interventie pe filtrul de particule.",
        "keywords": ["dpf", "filtru particule", "regenerare", "fum excesiv"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "suspensie_directie",
        "label": "Suspensie / directie",
        "minutes": 180,
        "reason": "Lucrare medie la suspensie sau directie.",
        "keywords": ["suspensie", "amortizor", "bieleta", "bielete", "brat", "brate", "directie", "cap bara", "caseta directie", "bascula"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "cutie_viteze",
        "label": "Cutie de viteze / transmisie",
        "minutes": 360,
        "reason": "Lucrare complexa la cutia de viteze sau transmisie.",
        "keywords": ["cutie viteze", "cutie de viteze", "grup", "nu intra in viteza"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "compresor_ac_climatizare",
        "label": "Compresor AC / climatizare",
        "minutes": 180,
        "reason": "Interventie pe sistemul de climatizare si compresor AC.",
        "keywords": ["compresor ac", "climatizare", "aer conditionat", "nu baga rece", "freon"],
        "category_hints": ["electrica", "mecanica"],
    },
    {
        "slug": "racire_radiator_apa",
        "label": "Radiator / pompa apa / racire",
        "minutes": 180,
        "reason": "Interventie pe sistemul de racire, cu verificari si inlocuire componente.",
        "keywords": ["radiator", "pompa apa", "apa", "antigel", "se incalzeste", "temperatura mare", "termostat"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "evacuare",
        "label": "Evacuare / toba",
        "minutes": 120,
        "reason": "Interventie pe sistemul de evacuare.",
        "keywords": ["toba", "evacuare", "esapament", "catalizator", "sonda lambda"],
        "category_hints": ["mecanica"],
    },
    {
        "slug": "geometrie_roti",
        "label": "Geometrie / directie roti",
        "minutes": 60,
        "reason": "Reglaj de geometrie sau verificare aliniere roti.",
        "keywords": ["geometrie", "fuge volanul", "trage stanga", "trage dreapta", "aliniere roti"],
        "category_hints": ["vulcanizari", "mecanica"],
    },
    {
        "slug": "anvelope_vulcanizare",
        "label": "Anvelope / vulcanizare",
        "minutes": 60,
        "reason": "Montaj, echilibrare sau reparatie uzuala de anvelope.",
        "keywords": ["anvelope", "vulcanizare", "pana", "echilibrare", "schimb roti", "janta"],
        "category_hints": ["vulcanizari"],
    },
    {
        "slug": "detailing_cosmetica",
        "label": "Detailing / cosmetica auto",
        "minutes": 180,
        "reason": "Serviciu de detailing sau cosmetica auto.",
        "keywords": ["detailing", "polish", "polishare", "ceramic", "spalare interior", "spalare exterioara", "curatare tapiterie", "faruri matuite"],
        "category_hints": ["detailing"],
    },
    {
        "slug": "tinichigerie_vopsitorie",
        "label": "Tinichigerie / vopsitorie",
        "minutes": 240,
        "reason": "Lucrare de caroserie sau vopsitorie care necesita pregatire si finisare.",
        "keywords": ["tinichigerie", "vopsitorie", "bara", "aripa", "usa", "zgarietura", "indoitura", "lovita", "revopsit"],
        "category_hints": ["tinichigerie"],
    },
    {
        "slug": "tractare_asistenta",
        "label": "Tractare / asistenta rutiera",
        "minutes": 90,
        "reason": "Estimare operationala pentru tractare sau asistenta rutiera.",
        "keywords": ["tractare", "platforma", "asistenta rutiera", "nu porneste pe drum"],
        "category_hints": ["tractari"],
    },
]

COMMON_TEXT_NORMALIZATIONS = {
    "schibare": "schimbare",
    "shimbare": "schimbare",
    "schimat": "schimbat",
    "planetaree": "planetare",
    "alternatot": "alternator",
    "ambrej": "ambreiaj",
    "distributtie": "distributie",
}

CATEGORY_DEFAULTS = {
    "detailing": (180, "Serviciu de detailing sau cosmetica auto."),
    "vulcanizari": (60, "Interventie uzuala de vulcanizare sau anvelope."),
    "tinichigerie": (240, "Lucrare de caroserie sau vopsitorie care necesita pregatire si finisare."),
    "tractari": (90, "Estimare operationala pentru tractare sau asistenta rutiera."),
    "electrica": (90, "Lucrare electrica auto care necesita constatare si interventie."),
    "mecanica": (120, "Lucrare mecanica uzuala cu verificare si executie."),
}


def normalize_duration_minutes(value: Optional[int]) -> int:
    try:
        minutes = int(value or DEFAULT_DURATION_MINUTES)
    except (TypeError, ValueError):
        minutes = DEFAULT_DURATION_MINUTES
    minutes = max(30, minutes)
    rounded = int(math.ceil(minutes / 30.0) * 30)
    return min(rounded, ALLOWED_DURATION_STEPS[-1])


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def normalize_text(value: str) -> str:
    value = _strip_accents((value or "").lower())
    for wrong, correct in COMMON_TEXT_NORMALIZATIONS.items():
        value = value.replace(wrong, correct)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _token_set(value: str) -> set[str]:
    return {token for token in normalize_text(value).split() if token}


def _score_keyword(keyword: str, normalized_text: str, tokens: set[str]) -> int:
    keyword = normalize_text(keyword)
    if not keyword:
        return 0
    if keyword in normalized_text:
        return max(4, len(keyword.split()) * 3)
    keyword_tokens = [token for token in keyword.split() if token]
    overlap = sum(1 for token in keyword_tokens if token in tokens)
    if overlap == len(keyword_tokens) and overlap:
        return overlap * 2
    if overlap >= 2:
        return overlap
    return 0


def detect_operation(problem_description: str = "", service_name: str = "", center_name: str = "", car_data: Optional[dict] = None) -> dict:
    search_text = " ".join([
        service_name or "",
        problem_description or "",
        center_name or "",
        " ".join(str(v) for v in (car_data or {}).values() if v),
    ])
    normalized_text = normalize_text(search_text)
    tokens = _token_set(search_text)
    normalized_service = normalize_text(service_name)
    normalized_center = normalize_text(center_name)

    ranked = []
    for operation in OPERATION_CATALOG:
        score = 0
        exact_hits = 0
        for keyword in operation["keywords"]:
            keyword_score = _score_keyword(keyword, normalized_text, tokens)
            score += keyword_score
            if normalize_text(keyword) in normalized_text and keyword_score:
                exact_hits += 1
        for hint in operation.get("category_hints", []):
            hint_norm = normalize_text(hint)
            if hint_norm and (hint_norm in normalized_service or hint_norm in normalized_center):
                score += 2
        if score:
            ranked.append((score, exact_hits, operation))

    ranked.sort(key=lambda item: (item[0], item[1], item[2]["minutes"]), reverse=True)
    if ranked:
        score, _, operation = ranked[0]
        confidence = min(0.95, 0.35 + (score / 24.0))
        return {
            "slug": operation["slug"],
            "label": operation["label"],
            "minutes": normalize_duration_minutes(operation["minutes"]),
            "reason": operation["reason"],
            "confidence": round(confidence, 2),
            "source": "catalog",
            "candidates": [
                {
                    "slug": op["slug"],
                    "label": op["label"],
                    "minutes": normalize_duration_minutes(op["minutes"]),
                }
                for _, _, op in ranked[:5]
            ],
        }

    for hint, (minutes, reason) in CATEGORY_DEFAULTS.items():
        hint_norm = normalize_text(hint)
        if hint_norm and (hint_norm in normalized_service or hint_norm in normalized_center):
            return {
                "slug": f"generic_{hint_norm}",
                "label": f"Lucrare {hint}",
                "minutes": normalize_duration_minutes(minutes),
                "reason": reason,
                "confidence": 0.35,
                "source": "category_fallback",
                "candidates": [],
            }

    fallback_minutes = 90 if normalize_text(service_name) else DEFAULT_DURATION_MINUTES
    return {
        "slug": "generic_diagnostic",
        "label": "Diagnosticare / interventie generala",
        "minutes": normalize_duration_minutes(fallback_minutes),
        "reason": "Estimare implicita folosita momentan.",
        "confidence": 0.2,
        "source": "fallback",
        "candidates": [],
    }


def heuristic_duration_estimate(problem_description: str = "", service_name: str = "", car_data: Optional[dict] = None, center_name: str = "") -> dict:
    detected = detect_operation(
        problem_description=problem_description,
        service_name=service_name,
        center_name=center_name,
        car_data=car_data,
    )
    estimate = {
        "minutes": detected["minutes"],
        "source": detected["source"],
        "reason": detected["reason"],
        "operation_slug": detected["slug"],
        "operation_label": detected["label"],
        "confidence": detected["confidence"],
        "candidates": detected.get("candidates", []),
    }
    return _apply_history_feedback(estimate)


def _history_adjustment(operation_slug: str) -> dict:
    if not operation_slug or operation_slug.startswith("generic_"):
        return {"applied": False, "sample_count": 0}

    try:
        from services.models import JobCard
    except Exception:
        return {"applied": False, "sample_count": 0}

    try:
        sample_values = list(
            JobCard.objects.filter(
                booking__estimated_operation_slug=operation_slug,
                actual_hours__isnull=False,
            )
            .exclude(status=JobCard.STATUS_CREATED)
            .values_list("actual_hours", flat=True)[:12]
        )
    except (OperationalError, ProgrammingError):
        return {"applied": False, "sample_count": 0}
    if len(sample_values) < 3:
        return {"applied": False, "sample_count": len(sample_values)}

    historical_minutes = normalize_duration_minutes(
        round((sum(float(value) for value in sample_values) / len(sample_values)) * 60)
    )
    return {
        "applied": True,
        "sample_count": len(sample_values),
        "historical_minutes": historical_minutes,
    }


def _apply_history_feedback(estimate: dict) -> dict:
    adjusted = dict(estimate)
    history = _history_adjustment(adjusted.get("operation_slug", ""))
    adjusted["history_sample_count"] = history.get("sample_count", 0)
    if not history.get("applied"):
        return adjusted

    base_minutes = normalize_duration_minutes(adjusted.get("minutes"))
    historical_minutes = history["historical_minutes"]
    blended_minutes = normalize_duration_minutes(round((base_minutes * 0.6) + (historical_minutes * 0.4)))
    adjusted["minutes"] = blended_minutes
    adjusted["history_minutes"] = historical_minutes
    adjusted["source"] = f"{adjusted.get('source', 'catalog')}_history"
    adjusted["reason"] = (
        f"{adjusted.get('reason', '').strip()} Ajustat din {history['sample_count']} lucrari similare finalizate."
    ).strip()[:240]
    return adjusted


def _extract_output_text(data: dict) -> str:
    raw_text = (data.get("output_text") or "").strip()
    if raw_text:
        return raw_text
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return str(content.get("text")).strip()
    return ""


def estimate_booking_duration(problem_description: str, service_name: str = "", car_data: Optional[dict] = None, center_name: str = "") -> dict:
    description = (problem_description or "").strip()
    service_name = (service_name or "").strip()
    center_name = (center_name or "").strip()
    car_data = car_data or {}

    heuristic = heuristic_duration_estimate(
        description,
        service_name=service_name,
        car_data=car_data,
        center_name=center_name,
    )
    if not description and not service_name:
        return heuristic

    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return heuristic

    model = getattr(settings, "OPENAI_MODEL", "gpt-4.1-mini")
    candidate_lines = [
        f"- {candidate['slug']}: {candidate['label']} ({candidate['minutes']} minute)"
        for candidate in heuristic.get("candidates", [])[:5]
    ] or ["- generic_diagnostic: Diagnosticare / interventie generala (60-90 minute)"]
    prompt = (
        "Esti receptioner tehnic senior intr-un service auto din Romania si estimezi durata aproximativa a unei lucrari "
        "pornind de la limbaj real de client. Clientii descriu adesea simptome, nu operatiunea exacta. "
        "Trebuie sa deduci interventia probabila si sa estimezi durata prudenta, utila pentru filtrarea sloturilor disponibile.\n\n"
        "Reguli obligatorii:\n"
        "1. Estimeaza durata totala de ocupare a postului de lucru, nu doar timpul efectiv de manopera.\n"
        "2. Include verificare initiala, demontare, montare, reglaje, test final si manevre uzuale.\n"
        "3. Daca descrierea sugereaza diagnostic inainte de confirmarea defectului, estimeaza prudent durata unei constatari serioase.\n"
        "4. Daca exista un interval probabil, alege capatul superior rezonabil.\n"
        "5. Foloseste in primul rand catalogul intern de mai jos. Daca niciun candidat nu se potriveste, poti propune generic_diagnostic.\n"
        "6. Returneaza minute in trepte de 30 intre 30 si 480.\n\n"
        "Candidati relevanti din catalog:\n"
        + "\n".join(candidate_lines)
        + "\n\nRaspunde strict cu JSON valid conform schemei."
    )

    schema = {
        "type": "object",
        "properties": {
            "minutes": {
                "type": "integer",
                "minimum": 30,
                "maximum": 480,
                "description": "Durata totala estimata in minute."
            },
            "reason": {
                "type": "string",
                "description": "Motiv scurt pentru estimare."
            },
            "operation_slug": {
                "type": "string",
                "description": "Slug-ul operatiei probabile din catalog sau generic_diagnostic."
            }
        },
        "required": ["minutes", "reason"],
        "additionalProperties": False,
    }

    payload = {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": prompt}],
            },
            {
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": json.dumps({
                        "center_name": center_name,
                        "service_name": service_name,
                        "problem_description": description,
                        "car": {
                            "brand": car_data.get("brand", ""),
                            "model": car_data.get("model", ""),
                            "year": car_data.get("year", ""),
                            "fuel": car_data.get("fuel", ""),
                            "plate": car_data.get("plate", ""),
                            "vin": car_data.get("vin", ""),
                        },
                        "catalog_best_guess": {
                            "operation_slug": heuristic.get("operation_slug", "generic_diagnostic"),
                            "operation_label": heuristic.get("operation_label", "Diagnosticare / interventie generala"),
                            "minutes": heuristic["minutes"],
                            "confidence": heuristic.get("confidence", 0.2),
                        },
                    }, ensure_ascii=False),
                }],
            },
        ],
        "temperature": 0.1,
        "max_output_tokens": 180,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "booking_duration_estimate",
                "strict": True,
                "schema": schema,
            }
        },
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post("https://api.openai.com/v1/responses", headers=headers, json=payload, timeout=25)
        response.raise_for_status()
        data = response.json()
        raw_text = _extract_output_text(data)
        if not raw_text:
            raise ValueError("Raspuns gol de la OpenAI.")
        parsed = json.loads(raw_text)
        minutes = normalize_duration_minutes(parsed.get("minutes"))
        result = {
            "minutes": minutes,
            "source": "openai",
            "reason": (parsed.get("reason") or "").strip()[:240] or "Estimare OpenAI.",
            "model": model,
            "operation_slug": (parsed.get("operation_slug") or heuristic.get("operation_slug") or "generic_diagnostic").strip()[:80],
            "operation_label": heuristic.get("operation_label", "Diagnosticare / interventie generala"),
            "confidence": heuristic.get("confidence", 0.2),
            "candidates": heuristic.get("candidates", []),
            "history_sample_count": heuristic.get("history_sample_count", 0),
            "history_minutes": heuristic.get("history_minutes"),
        }
        return _apply_history_feedback(result)
    except Exception as exc:
        heuristic["reason"] = f"{heuristic['reason']} (fallback: {exc})"[:240]
        return heuristic
