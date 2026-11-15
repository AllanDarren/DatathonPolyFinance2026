"""Governance agent (case, "piste 02"): are the investor's constraints and the
simulation boundaries respected? Which information is missing? Make the controls visible.

Deterministic by design: every control is computed by code from rules, the profile,
the portfolio and frozen snapshots, and cites its evidence. The LLM never decides a
control's status. Statuses: ok | warning | fail | info.
"""

from __future__ import annotations

from typing import Any

from core import data, snapshots
from core.evidence import EvidenceRegistry, format_pct, make_evidence

CONTROVERSY_FR = {"environmental": "environnementale", "social": "sociale", "governance": "de gouvernance",
                  "legal": "juridique", "safety": "de sécurité", "other": "autre"}


def _control(cid: str, label: str, status: str, detail: str, evidence_ids: list[str] | None = None) -> dict[str, Any]:
    return {"id": cid, "label_fr": label, "status": status, "detail_fr": detail, "evidence_ids": evidence_ids or []}


def _controversies(ticker: str) -> list[dict[str, Any]]:
    recs = snapshots.records("classified_news", required=False)
    return [r for r in recs if ticker in r.get("tickers", []) and (r.get("classification") or {}).get("controversy")]


def govern(profile: dict[str, Any], portfolio: dict[str, Any], consideration: dict[str, Any],
           coherence: dict[str, Any], diversification: dict[str, Any] | None,
           registry: EvidenceRegistry, trace: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Governance contract dict: {status, controls[], missing_info[]}."""
    from core.rules_engine import load_rules

    ticker = consideration["ticker"]
    uni = data.load_universe()
    controls: list[dict[str, Any]] = [_control(
        "G_SIMULATION", "Simulation seulement", "info",
        "Aucune transaction n'est exécutée et ce verdict n'est pas un conseil personnalisé: il applique les règles "
        "du prototype à ton profil déclaré.")]

    # 0. Data quality of the considered asset (core/quality.py). Blocking data never reaches this point.
    from core import quality

    q = quality.asset_quality(ticker)
    q_id = registry.add(q["evidence"])
    origin = "téléchargées à la demande" if q["origin"] == "on_demand" else "du jeu de départ"
    detail = (f"Données {origin} ({q['source']}) : " + (" ".join(q["warnings_fr"]) if q["warnings_fr"]
                                                         else "aucune anomalie détectée.")
              + (" " + " ".join(q["notes_fr"]) if q["notes_fr"] else ""))
    controls.append(_control("G_DATA_QUALITY", "Qualité des données", "warning" if q["status"] == "warning" else "ok",
                             detail, [q_id]))

    # 1. Profile limits (coherence rules).
    hits = coherence.get("rule_hits", [])
    rule_ev = coherence.get("rule_evidence", {})
    high = [h["rule_id"] for h in hits if h.get("severity") == "high"]
    medium = [h["rule_id"] for h in hits if h.get("severity") == "medium"]
    ids = [i for h in hits for i in rule_ev.get(h["rule_id"], [])[:1]]
    if high:
        controls.append(_control("G_PROFILE_LIMITS", "Limites de ton profil", "fail",
                                 f"Règle(s) de gravité haute déclenchée(s): {', '.join(high)}.", ids))
    elif medium:
        controls.append(_control("G_PROFILE_LIMITS", "Limites de ton profil", "warning",
                                 f"Règle(s) de vigilance déclenchée(s): {', '.join(medium)}.", ids))
    else:
        controls.append(_control("G_PROFILE_LIMITS", "Limites de ton profil", "ok",
                                 "Aucune règle de cohérence déclenchée pour ce poids."))

    # 2. Profile consistency (questionnaire answers that contradict each other).
    inc = profile.get("inconsistencies") or []
    controls.append(_control("G_PROFILE_CONSISTENCY", "Cohérence de tes réponses", "warning" if inc else "ok",
                             ("Réponses à clarifier: " + " ".join(inc)) if inc else
                             "Aucune contradiction détectée entre tes réponses."))

    # 3. Excluded sectors (preferences).
    cfg = load_rules().instrument_risks
    sector = str(uni.loc[ticker, "sector"])
    excluded = []
    for ex in profile.get("preferences", {}).get("excluded_sectors", []):
        mapping = cfg.sector_exclusions.get(ex) if cfg else None
        if mapping and sector in mapping.sectors:
            excluded.append(mapping.label_fr)
    if profile.get("preferences", {}).get("excluded_sectors"):
        if excluded:
            ev = make_evidence(kind="portfolio_calc",
                               statement=f"{ticker} appartient au secteur {sector}, que tu as choisi d'exclure "
                                         f"({', '.join(excluded)}).",
                               value=sector, unit=None, as_of=data.data_as_of(),
                               inputs={"ticker": ticker, "sector": sector,
                                       "excluded_sectors": profile["preferences"]["excluded_sectors"]},
                               source="data/assets_universe.csv, rules/instrument_risks.yaml",
                               computed_by="agents.governance.excluded_sectors")
            controls.append(_control("G_EXCLUDED_SECTOR", "Secteurs exclus", "fail",
                                     f"{ticker} ({sector}) fait partie d'un secteur que tu as exclu.", [registry.add(ev)]))
        else:
            controls.append(_control("G_EXCLUDED_SECTOR", "Secteurs exclus", "ok",
                                     f"Le secteur de {ticker} ({sector}) ne fait pas partie de tes exclusions."))

    # 4. Controversies (only when the investor asked to avoid them).
    if profile.get("preferences", {}).get("avoid_controversies"):
        found = _controversies(ticker)
        if found:
            types = sorted({(r["classification"].get("controversy_type") or "other") for r in found})
            ev = make_evidence(
                kind="classification",
                statement=f"{len(found)} nouvelle(s) récente(s) sur {ticker} classée(s) comme controverse "
                          f"({', '.join(CONTROVERSY_FR.get(t, t) for t in types)}).",
                value=len(found), unit="count", as_of=snapshots.as_of("classified_news") or data.data_as_of(),
                inputs={"ticker": ticker, "news_ids": [r["id"] for r in found[:8]], "types": types},
                source="data/snapshots/classified_news (classement Bedrock)",
                computed_by="agents.governance.controversies")
            controls.append(_control("G_CONTROVERSY", "Controverses (préférence ESG)", "warning",
                                     f"Tu as demandé à éviter les controverses: {len(found)} nouvelle(s) récente(s) "
                                     f"en signale(nt) pour {ticker}.", [registry.add(ev)]))
        else:
            controls.append(_control("G_CONTROVERSY", "Controverses (préférence ESG)", "ok",
                                     f"Aucune nouvelle récente classée comme controverse pour {ticker}."))

    # 4b. Preferences that came from the investor's own note (confirmed by them in the UI).
    if profile.get("confirmed_from_note"):
        controls.append(_control("G_NOTE_PREFERENCES", "Préférences tirées de ta note", "info",
                                 "Appliquées parce que tu les as confirmées: " + "; ".join(profile["confirmed_from_note"])
                                 + ". Ta note n'a rien changé d'autre (ni risque, ni horizon, ni verdict)."))

    # 5. Diversification.
    if diversification:
        status = {"overlap": "warning", "partial": "info", "new_exposure": "ok"}[diversification["verdict"]]
        controls.append(_control("G_DIVERSIFICATION", "Diversification", status, diversification["text_fr"],
                                 diversification["evidence_ids"][:1]))

    # 6. Missing information (flag, never guess).
    missing: list[str] = []
    if profile.get("monthly_expenses_cad") in (None, 0):
        missing.append("Dépenses mensuelles inconnues: impossible de traduire une perte possible en mois de dépenses.")
    un = portfolio.get("unanalyzed") or {}
    if un.get("tickers"):
        missing.append(f"{format_pct(un.get('weight', 0), 0)} du portefeuille hors univers analysé "
                       f"({', '.join(un['tickers'])}): non pris en compte dans les calculs.")
    if any(t.get("tool") == "get_event_context" and t.get("status") == "error"
           for t in trace or []):
        missing.append("Contexte historique des événements indisponible (moins de 8 événements comparables).")
    missing.append("Autres comptes et actifs (immobilier, régime de retraite, épargne) inconnus: le portefeuille "
                   "importé n'est peut-être pas tout ton patrimoine.")
    controls.append(_control("G_MISSING_INFO", "Information manquante", "warning" if len(missing) > 1 else "info",
                             " ".join(missing)))

    worst = "fail" if any(c["status"] == "fail" for c in controls) else \
        "warning" if any(c["status"] == "warning" for c in controls) else "ok"
    return {"status": worst, "controls": controls, "missing_info": missing}
