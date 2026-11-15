"""Preferences confirmed from the investor's free-text note (pure code, no LLM).

Closed lists come from role D's rules: interests from questionnaire.yaml, excluded
sectors from instrument_risks.yaml. Used by the rules engine (score_profile) and by
the preference extraction agent (agents/preferences.py).
"""

from __future__ import annotations

from typing import Any

from core.errors import AlphaForgeError

INTEREST_FR = {"ai": "intelligence artificielle", "emerging_technology": "technologies émergentes",
               "crypto": "cryptoactifs", "esg": "critères ESG", "income": "revenus et dividendes"}


def allowed_values() -> dict[str, list[Any]]:
    """Closed lists from role D's rules (no free value can reach the profile)."""
    from core.rules_engine import load_rules

    rs = load_rules()
    interests: list[str] = []
    for q in rs.questionnaire.questions:
        for o in q.options:
            for v in o.sets.get("preferences.interests", []) or []:
                if v not in interests:
                    interests.append(v)
    sectors = list(rs.instrument_risks.sector_exclusions) if rs.instrument_risks else []
    return {"excluded_sectors": sectors, "interests": interests, "avoid_controversies": [True]}


def label(field: str, value: Any) -> str:
    if field == "excluded_sectors":
        from core.rules_engine import load_rules

        ex = load_rules().instrument_risks
        lab = ex.sector_exclusions[value].label_fr if ex and value in ex.sector_exclusions else value
        return f"Exclure le secteur : {lab}"
    if field == "interests":
        return f"Intérêt : {INTEREST_FR.get(value, value)}"
    return "Faire ressortir les controverses (préférence ESG)"


def describe_confirmed(confirmed: dict[str, Any]) -> list[str]:
    """French labels of the confirmed preferences (shown on the profile screen)."""
    out = [label("excluded_sectors", v) for v in confirmed.get("excluded_sectors") or []]
    out += [label("interests", v) for v in confirmed.get("interests") or []]
    if confirmed.get("avoid_controversies") is True:
        out.append(label("avoid_controversies", True))
    return out


def apply_confirmed(profile_inputs: dict[str, Any], confirmed: dict[str, Any] | None) -> dict[str, Any]:
    """Merge confirmed preferences into a profile dict (validated against the closed lists)."""
    if not confirmed:
        return profile_inputs
    allowed = allowed_values()
    prefs = profile_inputs.setdefault("preferences", {"avoid_controversies": False, "excluded_sectors": [],
                                                      "interests": []})
    for field in ("excluded_sectors", "interests"):
        for v in confirmed.get(field) or []:
            if v not in allowed[field]:
                raise AlphaForgeError("INVALID_PREFERENCES", f"Préférence inconnue: {field}={v}.",
                                      details={"field": field, "value": v, "allowed": allowed[field]})
            if v not in prefs[field]:
                prefs[field] = [*prefs[field], v]
    if confirmed.get("avoid_controversies") is True:
        prefs["avoid_controversies"] = True
    return profile_inputs
