"""What would change the answer? (pure code, no LLM)

Credible explanations say which conditions would change the conclusion (BN workshop,
slide 12). We re-apply the same coherence rules on a grid of intended weights:
- a rule that clears at a lower weight -> "at X % or less, this rule is no longer triggered";
- a rule triggered at every weight depends on the asset and the profile, not the amount
  -> we name the profile fields it reads (horizon, acceptable loss, risk tolerance).
Nothing here is a recommendation: it describes the rules' thresholds.
"""

from __future__ import annotations

from typing import Any

from core import data
from core.evidence import EvidenceRegistry, format_pct, make_evidence

GRID_STEP = 0.01
GRID_MAX = 0.30
PROFILE_FIELDS_FR = {
    "profile.max_acceptable_loss_pct": "la perte annuelle que tu dis pouvoir accepter",
    "profile.horizon_years": "ton horizon de placement",
    "profile.risk_tolerance": "ta tolérance au risque",
    "profile.limits.max_single_position": "la limite par titre de ton profil",
    "profile.limits.max_high_vol_share": "la part très volatile permise par ton profil",
}
VERDICT_RANK = {"coherent": 0, "tension": 1, "incoherent": 2}


def weight_grid(profile: dict[str, Any], portfolio: dict[str, Any], ticker: str,
                weights: list[float] | None = None) -> list[dict[str, Any]]:
    """[{weight, verdict, rule_ids}] for each weight (same rules as check_coherence)."""
    from core.rules_engine import check_coherence

    ws = weights or [round(GRID_STEP * i, 4) for i in range(1, int(round(GRID_MAX / GRID_STEP)) + 1)]
    out = []
    for w in ws:
        res = check_coherence(profile, portfolio, {"ticker": ticker, "intended_weight": w}, EvidenceRegistry())
        out.append({"weight": w, "verdict": res["verdict"], "rule_ids": [h["rule_id"] for h in res["rule_hits"]]})
    return out


def _profile_fields(rule_id: str) -> list[str]:
    from core.rules_engine import load_rules

    rule = next((r for r in load_rules().coherence.rules if r.id == rule_id), None)
    if rule is None:
        return []
    paths = [p for c in rule.when for p in (c.field, c.right_path) if p and p.startswith("profile.")]
    return list(dict.fromkeys(paths))


def what_would_change(profile: dict[str, Any], portfolio: dict[str, Any], ticker: str, intended_weight: float,
                      triggered: list[str], registry: EvidenceRegistry) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(changes, grid). Each change: {rule_id, kind: weight|profile, text_fr, max_weight?, evidence_id}."""
    top = max(GRID_MAX, intended_weight)
    steps = {round(GRID_STEP * i, 4) for i in range(1, int(round(top / GRID_STEP)) + 1)}
    weights = sorted(steps | {round(intended_weight, 4)})
    grid = weight_grid(profile, portfolio, ticker, weights)
    below = [g for g in grid if g["weight"] <= intended_weight + 1e-9]
    changes: list[dict[str, Any]] = []
    for rule_id in triggered:
        clear = [g["weight"] for g in below if rule_id not in g["rule_ids"]]
        if clear:
            w = max(clear)
            text = (f"Avec un poids visé de {format_pct(w, 0)} ou moins (au lieu de {format_pct(intended_weight, 0)}), "
                    f"la règle {rule_id} ne serait plus déclenchée.")
            change: dict[str, Any] = {"rule_id": rule_id, "kind": "weight", "text_fr": text, "max_weight": w}
        else:
            fields = [PROFILE_FIELDS_FR.get(f, f) for f in _profile_fields(rule_id)]
            what = " et ".join(fields) if fields else "les caractéristiques de l'actif"
            text = (f"La règle {rule_id} reste déclenchée même à {format_pct(below[0]['weight'], 0)}: elle ne dépend "
                    f"pas du montant, mais de l'actif et de {what}.")
            change = {"rule_id": rule_id, "kind": "profile", "text_fr": text, "max_weight": None}
        ev = make_evidence(kind="portfolio_calc", statement=text, value=change["max_weight"],
                           unit="fraction" if change["max_weight"] is not None else None, as_of=data.data_as_of(),
                           inputs={"ticker": ticker, "intended_weight": intended_weight, "rule_id": rule_id,
                                   "grid_step": GRID_STEP, "weights_tested": [g["weight"] for g in below]},
                           source="rules/coherence_rules.yaml, portefeuille fourni",
                           computed_by="core.sensitivity.what_would_change")
        change["evidence_id"] = registry.add(ev)
        changes.append(change)
    # Overall: largest tested weight with a better verdict than the current one.
    current = next(g for g in grid if abs(g["weight"] - intended_weight) < 1e-9)["verdict"]
    better = [g for g in below if VERDICT_RANK[g["verdict"]] < VERDICT_RANK[current]]
    if better:
        best = max(better, key=lambda g: g["weight"])
        label = {"coherent": "cohérent", "tension": "en tension"}[best["verdict"]]
        text = f"Jusqu'à {format_pct(best['weight'], 0)} de {ticker}, le verdict serait « {label} » selon les mêmes règles."
        ev = make_evidence(kind="portfolio_calc", statement=text, value=best["weight"], unit="fraction",
                           as_of=data.data_as_of(),
                           inputs={"ticker": ticker, "intended_weight": intended_weight, "verdict_at_weight": best["verdict"],
                                   "grid_step": GRID_STEP},
                           source="rules/coherence_rules.yaml, portefeuille fourni",
                           computed_by="core.sensitivity.what_would_change")
        changes.insert(0, {"rule_id": None, "kind": "weight", "text_fr": text, "max_weight": best["weight"],
                           "evidence_id": registry.add(ev)})
    return changes, grid
