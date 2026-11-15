"""Preference extraction agent: an investor's free-text note -> CONFIRMABLE preferences.

The note never decides anything by itself:
1. The model (or a keyword fallback offline) maps the note to a closed list of values
   taken from role D's rules (interests from questionnaire.yaml, excluded sectors from
   instrument_risks.yaml, avoid_controversies). Output is schema-validated (enums).
2. Code check: each suggestion must quote the note verbatim; otherwise it is dropped.
3. The UI shows what was understood; the person confirms; only confirmed preferences
   are sent to POST /profile and applied by the rules engine.
Risk tolerance, horizon and amounts are never extracted: they come from the questionnaire.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agents.classifier import sanitize
from agents.llm import LLMClient, LLMUnavailableError, MockClient
from agents.prompts import load_prompt, render_prompt
from core.preferences import INTEREST_FR, allowed_values, apply_confirmed, describe_confirmed
from core.preferences import label as _label

MAX_NOTE = 300
# Offline fallback: (field, value, regex). French and English.
KEYWORDS: list[tuple[str, Any, str]] = [
    ("excluded_sectors", "fossil_fuels", r"p[ée]trol\w*|fossile\w*|oil\b|gaz naturel|charbon|pipeline\w*|sables bitumineux"),
    ("excluded_sectors", "tobacco", r"tabac\w*|tobacco|cigarette\w*"),
    ("interests", "ai", r"\bia\b|intelligence artificielle|\bai\b"),
    ("interests", "emerging_technology", r"technolog\w* [ée]mergente\w*|innovation\w*|robot\w*"),
    ("interests", "crypto", r"crypto\w*|bitcoin|ether\w*\b"),
    ("interests", "esg", r"\besg\b|environnement\w*|durable\w*|climat\w*|[ée]thique\w*"),
    ("interests", "income", r"dividende\w*|revenu\w* (r[ée]gulier|passif)\w*|income"),
    ("avoid_controversies", True, r"controvers\w*|scandale\w*|[ée]thique\w*|[ée]viter les entreprises"),
]
PROFILE_CHANGE = re.compile(r"risque|horizon|retraite|dans \d+ ans|\d+\s?(?:k|000)\s?\$|perte", re.IGNORECASE)


def output_schema(allowed: dict[str, list[Any]]) -> dict[str, Any]:
    item = {"type": "object", "properties": {
        "field": {"type": "string", "enum": ["excluded_sectors", "interests", "avoid_controversies"]},
        "value": {"anyOf": [{"type": "string", "enum": allowed["excluded_sectors"] + allowed["interests"]},
                            {"type": "boolean", "enum": [True]}]},
        "quote": {"type": "string", "maxLength": 80}},
        "required": ["field", "value", "quote"], "additionalProperties": False}
    return {"type": "object", "properties": {"suggestions": {"type": "array", "maxItems": 8, "items": item},
                                             "mentions_profile_change": {"type": "boolean"}},
            "required": ["suggestions", "mentions_profile_change"], "additionalProperties": False}


def _keyword_extract(note: str) -> dict[str, Any]:
    out = []
    for field, value, pattern in KEYWORDS:
        m = re.search(pattern, note, re.IGNORECASE)
        if m:
            out.append({"field": field, "value": value, "quote": m.group(0)})
    return {"suggestions": out, "mentions_profile_change": bool(PROFILE_CHANGE.search(note))}


def extract_preferences(text: str, client: LLMClient | None = None) -> dict[str, Any]:
    """PreferenceExtraction contract dict. Suggestions only: nothing is applied here."""
    note = sanitize(text, MAX_NOTE)
    allowed = allowed_values()
    offline = client is None or (isinstance(client, MockClient) and client.responder is None)
    generated_by = "keywords"
    raw: dict[str, Any]
    if not note:
        raw = {"suggestions": [], "mentions_profile_change": False}
    elif offline:
        raw = _keyword_extract(note)
    else:
        system, _ = load_prompt("preferences")
        system = render_prompt(system, excluded_sectors=json.dumps(allowed["excluded_sectors"]),
                               interests=json.dumps(allowed["interests"]))
        try:
            raw = client.complete(system, [{"role": "user", "content": f"<note>\n{note}\n</note>"}],  # type: ignore[union-attr]
                                  output_schema(allowed))
            generated_by = "bedrock"
        except LLMUnavailableError:
            raw = _keyword_extract(note)
    suggestions, rejected, seen = [], [], set()
    low = note.lower()
    for s in raw["suggestions"]:
        field, value, quote = s["field"], s["value"], str(s.get("quote", "")).strip()
        valid_value = (value is True) if field == "avoid_controversies" else value in allowed.get(field, [])
        if not valid_value or not quote or quote.lower() not in low:
            rejected.append(f"{field}={value} (citation absente de la note)")
            continue
        if (field, value) in seen:
            continue
        seen.add((field, value))
        suggestions.append({"field": field, "value": value, "label_fr": _label(field, value), "quote": quote})
    notice = ("Ces suggestions viennent de ta note. Rien n'est appliqué sans ta confirmation; "
              "le risque et l'horizon se règlent seulement par le questionnaire.")
    if raw.get("mentions_profile_change"):
        notice += " Ta note semble parler de risque, d'horizon ou de montants: refais les questions concernées."
    return {"note": note, "suggestions": suggestions, "rejected": rejected, "generated_by": generated_by,
            "mentions_profile_change": bool(raw.get("mentions_profile_change")), "notice_fr": notice}


__all__ = ["INTEREST_FR", "allowed_values", "apply_confirmed", "describe_confirmed", "extract_preferences"]
