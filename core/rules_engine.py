"""Rules engine (A3): profile scoring, news relevance, purchase coherence.

Reads role D's files in `rules/` (or `RULES_DIR`), validated against
core/rules_models.py. A missing file falls back to the reference example in
contracts/rules/examples/ and is reported by `rules_status()`.

No LLM call here. Same inputs, same outputs. Every RuleHit carries its rule_id,
its French text and the observed values; coherence also returns Evidence.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from core import data, metrics
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry, format_num, format_pct, make_evidence
from core.models import Profile
from core.rules_models import (
    RULE_FILES,
    CoherenceRules,
    Condition,
    Glossary,
    LimitsTexts,
    ProfileRules,
    Questionnaire,
    RelevanceRules,
    Taxonomy,
)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_RULES_DIR = ROOT / "contracts" / "rules" / "examples"
PERSONA_IDS = ("robert", "amira", "mateo")

# Metrics usable in coherence rules -> unit used to format {observed}/{limit}.
COHERENCE_METRICS: dict[str, str] = {
    "position_weight_after": "fraction",
    "annualized_vol": "fraction",
    "max_drawdown": "fraction",
    "max_drawdown_abs": "fraction",
    "worst_calendar_year_return": "fraction",
    "worst_calendar_year_loss_abs": "fraction",
    "return_5y": "fraction",
    "dividend_yield_ttm": "fraction",
    "recovery_days": "days",
    "recovery_years": "years",
    "is_high_vol": "bool",
    "asset_class": "text",
    "high_vol_share_after": "fraction",
    "top3_concentration_after": "fraction",
    "crypto_share_after": "fraction",
    "corr_to_portfolio": "correlation",
}
# Paths a relevance condition may read (besides profile.*).
RELEVANCE_FIELDS = {
    "item.category", "item.horizon_relevance", "item.controversy", "item.controversy_type", "item.tickers",
    "position.ticker", "position.weight", "position.asset_class", "position.sector", "position.is_high_vol",
    "position.annualized_vol", "position.held",
}
PROFILE_FIELDS = set(Profile.model_fields) | {
    "preferences.avoid_controversies", "preferences.excluded_sectors", "preferences.interests",
    "limits.max_single_position", "limits.max_high_vol_share",
}


# --- loading ------------------------------------------------------------------------


def rules_dir() -> Path:
    return Path(os.environ.get("RULES_DIR", ROOT / "rules"))


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AlphaForgeError("RULES_INVALID", f"{path.name}: YAML illisible ({exc}).", status=500) from exc


def _resolve_file(name: str) -> tuple[Path, bool]:
    """Return (path, is_example_fallback)."""
    own = rules_dir() / name
    if own.exists():
        return own, False
    example = EXAMPLE_RULES_DIR / name
    if example.exists():
        return example, True
    raise AlphaForgeError("RULES_UNAVAILABLE", f"Fichier de règles absent: {name}.", status=500)


@dataclass(frozen=True)
class RuleSet:
    questionnaire: Questionnaire
    profile_rules: ProfileRules
    taxonomy: Taxonomy
    relevance: RelevanceRules
    coherence: CoherenceRules
    glossary: Glossary
    limits_texts: LimitsTexts
    raw_questionnaire: dict[str, Any]
    fallbacks: tuple[str, ...] = field(default_factory=tuple)

    def category(self, cat_id: str) -> Any:
        return next((c for c in self.taxonomy.categories if c.id == cat_id), None)


def _load_model(name: str) -> tuple[BaseModel, Any, bool]:
    path, fallback = _resolve_file(name)
    raw = _read_yaml(path)
    try:
        return RULE_FILES[name].model_validate(raw), raw, fallback
    except ValidationError as exc:
        raise AlphaForgeError("RULES_INVALID", f"{name} ne respecte pas son schéma (lance make validate-rules).",
                              status=500, details={"errors": exc.errors(include_url=False)[:5]}) from exc


@cache
def load_rules() -> RuleSet:
    loaded = {name: _load_model(name) for name in RULE_FILES}
    return RuleSet(
        questionnaire=loaded["questionnaire.yaml"][0],  # type: ignore[arg-type]
        profile_rules=loaded["profile_rules.yaml"][0],  # type: ignore[arg-type]
        taxonomy=loaded["taxonomy.yaml"][0],  # type: ignore[arg-type]
        relevance=loaded["relevance_rules.yaml"][0],  # type: ignore[arg-type]
        coherence=loaded["coherence_rules.yaml"][0],  # type: ignore[arg-type]
        glossary=loaded["glossary.yaml"][0],  # type: ignore[arg-type]
        limits_texts=loaded["limits_texts.yaml"][0],  # type: ignore[arg-type]
        raw_questionnaire=loaded["questionnaire.yaml"][1],
        fallbacks=tuple(name for name, (_, _, fb) in loaded.items() if fb),
    )


def rules_status() -> dict[str, Any]:
    rs = load_rules()
    return {"rules_dir": str(rules_dir()), "example_fallbacks": list(rs.fallbacks)}


def clear_cache() -> None:
    load_rules.cache_clear()


def load_personas() -> list[dict[str, Any]]:
    """Persona contracts from rules/personas/{id}.yaml + {id}_portfolio.csv (example fallback)."""
    out = []
    for pid in PERSONA_IDS:
        prof_path, _ = _resolve_file(f"personas/{pid}.yaml")
        csv_path, _ = _resolve_file(f"personas/{pid}_portfolio.csv")
        try:
            profile = dump_profile(Profile.model_validate(_read_yaml(prof_path)))
        except ValidationError as exc:
            raise AlphaForgeError("RULES_INVALID", f"personas/{pid}.yaml n'est pas un Profile valide.", status=500,
                                  details={"errors": exc.errors(include_url=False)[:5]}) from exc
        out.append({"id": pid, "label": profile["label"], "profile": profile,
                    "sample_portfolio_csv": csv_path.read_text(encoding="utf-8")})
    return out


def dump_profile(profile: Profile) -> dict[str, Any]:
    """Profile -> contract dict: optional `age` omitted when unknown, nullable fields kept."""
    out = profile.model_dump(mode="json")
    if out.get("age") is None:
        out.pop("age", None)
    return out


# --- conditions ---------------------------------------------------------------------

_MISSING = object()


def resolve_path(ctx: dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def _compare(left: Any, op: str, right: Any) -> bool:
    if left is _MISSING or right is _MISSING or left is None:
        return False
    try:
        if op == "==":
            return bool(left == right)
        if op == "!=":
            return bool(left != right)
        if op == "<":
            return bool(left < right)
        if op == "<=":
            return bool(left <= right)
        if op == ">":
            return bool(left > right)
        if op == ">=":
            return bool(left >= right)
        if op == "in":
            return left in (right or [])
        if op == "not_in":
            return left not in (right or [])
        if op == "contains":
            return right in (left or [])
        if op == "not_contains":
            return right not in (left or [])
    except TypeError:
        return False
    raise ValueError(f"unknown op {op}")


@dataclass
class CondResult:
    ok: bool
    observed: Any = None
    limit: Any = None


def evaluate(conds: list[Condition], ctx: dict[str, Any], metric_values: dict[str, Any] | None = None) -> CondResult:
    """AND of all conditions. `observed`/`limit` come from the last numeric comparison."""
    observed = limit = None
    for c in conds:
        if c.metric is not None:
            left = (metric_values or {}).get(c.metric, _MISSING)
        else:
            left = resolve_path(ctx, c.field or "")
        right = resolve_path(ctx, c.right_path) if c.right_path else c.value
        if not _compare(left, c.op, right):
            return CondResult(False)
        if isinstance(left, int | float) and not isinstance(left, bool) and isinstance(right, int | float):
            observed, limit = left, right
    return CondResult(True, observed, limit)


def _fmt(value: Any, unit: str) -> str:
    if value is None:
        return "n.d."
    if unit == "fraction":
        return format_pct(float(value), 0 if abs(float(value) * 100 - round(float(value) * 100)) < 1e-9 else 1)
    if unit == "days":
        return f"{int(value)} jours"
    if unit == "years":
        return f"{format_num(float(value), 1)} ans"
    if unit == "correlation":
        return format_num(float(value))
    return str(value)


def _render(text: str, **values: str) -> str:
    out = text
    for k, v in values.items():
        out = out.replace("{" + k + "}", v)
    return out


# --- profile ------------------------------------------------------------------------


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = target
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def horizon_bucket(years: float, rules: ProfileRules) -> str:
    for b in sorted(rules.horizon_buckets, key=lambda b: b.max_years):
        if years <= b.max_years:
            return b.id
    return sorted(rules.horizon_buckets, key=lambda b: b.max_years)[-1].id


def risk_from_points(points: float, rules: ProfileRules) -> str:
    for tier in sorted(rules.risk_from_points, key=lambda t: t.max_points):
        if points <= tier.max_points:
            return tier.value
    return sorted(rules.risk_from_points, key=lambda t: t.max_points)[-1].value


def score_profile(answers: dict[str, str], rules: RuleSet | None = None) -> dict[str, Any]:
    """Questionnaire answers -> Profile contract dict (with inconsistencies)."""
    rs = rules or load_rules()
    if not isinstance(answers, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in answers.items()):
        raise AlphaForgeError("INVALID_ANSWERS", "Les réponses doivent être un objet {question_id: option_id}.")
    questions = {q.id: q for q in rs.questionnaire.questions}
    unknown = sorted(set(answers) - set(questions))
    if unknown:
        raise AlphaForgeError("INVALID_ANSWERS", f"Question(s) inconnue(s): {', '.join(unknown)}.",
                              details={"unknown_questions": unknown})
    missing = [q.id for q in rs.questionnaire.questions if not q.optional and q.id not in answers]
    if missing:
        raise AlphaForgeError("INVALID_ANSWERS", f"Question(s) sans réponse: {', '.join(missing)}.",
                              details={"missing_questions": missing})

    prof: dict[str, Any] = {}
    for path, value in rs.profile_rules.defaults.items():
        _set_path(prof, path, value)
    points: dict[str, float] = {}
    for qid, oid in answers.items():
        opt = next((o for o in questions[qid].options if o.id == oid), None)
        if opt is None:
            raise AlphaForgeError("INVALID_ANSWERS", f"Option « {oid} » inconnue pour la question {qid}.",
                                  details={"question": qid, "option": oid})
        for path, value in opt.sets.items():
            _set_path(prof, path, value)
        for key, pts in opt.points.items():
            points[key] = points.get(key, 0.0) + pts

    pr = rs.profile_rules
    if "risk_tolerance" not in prof:
        prof["risk_tolerance"] = risk_from_points(points.get("risk", 0.0), pr)
    if "horizon_years" not in prof:
        raise AlphaForgeError("PROFILE_INCOMPLETE", "Impossible de déterminer l'horizon (horizon_years).", status=500)
    prof["horizon_bucket"] = horizon_bucket(float(prof["horizon_years"]), pr)
    lim = pr.limits_by_risk.get(prof["risk_tolerance"])  # type: ignore[call-overload]
    if lim is None:
        raise AlphaForgeError("RULES_INVALID", f"Aucune limite pour le niveau {prof['risk_tolerance']}.", status=500)
    prof["limits"] = lim.model_dump()
    prefs = prof.setdefault("preferences", {})
    prefs.setdefault("avoid_controversies", False)
    prefs.setdefault("excluded_sectors", [])
    prefs.setdefault("interests", [])
    prof.setdefault("monthly_expenses_cad", None)
    prof.update({"profile_id": "custom", "label": "Mon profil", "source": "questionnaire", "base_currency": "CAD"})
    prof["inconsistencies"] = [c.text_fr for c in pr.inconsistency_checks if evaluate(c.when, prof).ok]
    try:
        return dump_profile(Profile.model_validate(prof))
    except ValidationError as exc:
        missing_fields = sorted({str(e["loc"][0]) for e in exc.errors() if e["type"] == "missing"})
        raise AlphaForgeError("PROFILE_INCOMPLETE",
                              "Le profil calculé est incomplet: " + (", ".join(missing_fields) or "valeurs invalides")
                              + ". Vérifie les « defaults » de profile_rules.yaml.", status=500,
                              details={"errors": exc.errors(include_url=False)[:5]}) from exc


# --- relevance ----------------------------------------------------------------------


def position_context(portfolio: dict[str, Any] | None, tickers: list[str], high_vol_threshold: float) -> dict[str, Any]:
    """Context of the most-weighted held position among `tickers` ({} if none held)."""
    held = [p for p in (portfolio or {}).get("positions", []) if p["ticker"] in tickers and p.get("in_universe", True)]
    if not held:
        return {"held": False, "weight": 0.0}
    pos = max(held, key=lambda p: p["weight"])
    t = pos["ticker"]
    vol = metrics.annualized_vol(t).value
    return {"held": True, "ticker": t, "weight": float(pos["weight"]), "asset_class": pos["asset_class"],
            "sector": str(data.load_universe().loc[t, "sector"]), "annualized_vol": vol,
            "is_high_vol": vol > high_vol_threshold}


def score_relevance(profile: dict[str, Any], classification: dict[str, Any], position: dict[str, Any] | None = None,
                    rules: RuleSet | None = None) -> dict[str, Any]:
    """Profile x classification x position -> {score, level, shown, position_weight, rule_hits, hidden_reason}."""
    rs = rules or load_rules()
    rr = rs.relevance
    pos = position or {"held": False, "weight": 0.0}
    bucket = profile["horizon_bucket"]
    cat_id = classification["category"]
    cat = rs.category(cat_id)
    label = cat.label_fr if cat else cat_id
    base = rr.base_weights.get(bucket, {}).get(cat_id, 0.0)
    hits: list[dict[str, Any]] = [{
        "rule_id": f"R_BASE_{cat_id.upper()}",
        "text": _render(rr.base_rule_text_fr, category=label, weight=format_num(base), horizon_bucket=bucket),
        "delta": base,
    }]
    score = base
    weight = float(pos.get("weight", 0.0))
    for tier in sorted(rr.position_weight_bonus, key=lambda t: -t.min_weight):
        if weight >= tier.min_weight:
            text = tier.text_fr or f"Cette position pèse au moins {format_pct(tier.min_weight, 0)} de ton portefeuille."
            hits.append({"rule_id": f"R_POS_WEIGHT_{round(tier.min_weight * 100)}", "text": text, "delta": tier.add,
                         "observed": round(weight, 6), "limit": tier.min_weight})
            score += tier.add
            break
    ctx = {"profile": profile, "item": classification, "position": pos}
    for mod in rr.modifiers:
        res = evaluate(mod.when, ctx)
        if res.ok:
            hit: dict[str, Any] = {"rule_id": mod.id, "text": mod.text_fr, "delta": mod.add}
            if res.observed is not None:
                hit.update(observed=res.observed, limit=res.limit)
            hits.append(hit)
            score += mod.add
    score = round(min(max(score, 0.0), 1.0), 4)
    th = rr.thresholds
    shown = score >= th.show
    level = "high" if score >= th.high else "medium" if score >= (th.medium if th.medium is not None else th.show) \
        else "low"
    hidden_reason = None
    if not shown:
        key = "short_term_noise" if classification.get("horizon_relevance") == "short_term_noise" else "low_relevance"
        default = {"short_term_noise": "Bruit de court terme pour ton horizon",
                   "low_relevance": "Pertinence trop faible pour ton profil"}[key]
        hidden_reason = rr.hidden_reasons_fr.get(key, default)
    return {"score": score, "level": level, "shown": shown, "position_weight": round(weight, 6), "rule_hits": hits,
            "hidden_reason": hidden_reason}


# --- coherence ----------------------------------------------------------------------


def portfolio_after(portfolio: dict[str, Any], ticker: str, intended_weight: float) -> dict[str, Any]:
    """Analyzed positions after reaching `intended_weight` on `ticker` (other amounts unchanged)."""
    positions = [dict(p) for p in portfolio.get("positions", []) if p.get("in_universe", True)]
    total = math.fsum(p["amount"] for p in positions)
    held = next((p for p in positions if p["ticker"] == ticker), None)
    a = held["amount"] if held else 0.0
    if total <= 0:
        raise AlphaForgeError("EMPTY_PORTFOLIO", "Le portefeuille analysé est vide.")
    others = total - a
    if others <= 0:
        new_amount, new_total = a, total  # single-position portfolio: weight stays 100 %
    else:
        new_amount = intended_weight * others / (1 - intended_weight)
        new_total = others + new_amount
    uni = data.load_universe()
    if held:
        held["amount"] = new_amount
    else:
        positions.append({"ticker": ticker, "amount": new_amount, "weight": 0.0,
                          "asset_class": str(uni.loc[ticker, "asset_class"]),
                          "price_currency": str(uni.loc[ticker, "price_currency"]), "in_universe": True})
    for p in positions:
        p["weight"] = p["amount"] / new_total
    return {"base_currency": "CAD", "total_amount": new_total, "positions": positions,
            "unanalyzed": {"tickers": [], "weight": 0.0}, "warnings": []}


def coherence_metrics(profile: dict[str, Any], portfolio: dict[str, Any], ticker: str, intended_weight: float,
                      registry: EvidenceRegistry, high_vol_threshold: float) -> tuple[dict[str, Any], dict[str, str]]:
    """Compute every coherence metric with its evidence. Returns (values, metric -> evidence id)."""
    vals: dict[str, Any] = {}
    ev: dict[str, str] = {}

    def put(name: str, res: metrics.MetricResult) -> None:
        vals[name] = res.value
        ev[name] = registry.add(res)

    put("annualized_vol", metrics.annualized_vol(ticker))
    put("max_drawdown", metrics.max_drawdown(ticker))
    put("max_drawdown_abs", metrics.max_drawdown_abs(ticker))
    put("worst_calendar_year_return", metrics.worst_calendar_year_return(ticker))
    vals["worst_calendar_year_loss_abs"] = max(0.0, -vals["worst_calendar_year_return"])
    ev["worst_calendar_year_loss_abs"] = ev["worst_calendar_year_return"]
    put("return_5y", metrics.return_5y(ticker))
    put("dividend_yield_ttm", metrics.dividend_yield_ttm(ticker))
    put("recovery_days", metrics.recovery_days(ticker))
    vals["recovery_years"] = None if vals["recovery_days"] is None else vals["recovery_days"] / 365.25
    ev["recovery_years"] = ev["recovery_days"]
    put("is_high_vol", metrics.is_high_vol(ticker, high_vol_threshold))
    put("asset_class", metrics.asset_class(ticker))
    put("position_weight_after", metrics.position_weight_after(portfolio, ticker, intended_weight))

    after = portfolio_after(portfolio, ticker, intended_weight)
    hv = metrics.high_vol_share(after, high_vol_threshold)
    top3 = metrics.top3_concentration(after)
    crypto = math.fsum(p["weight"] for p in after["positions"] if p["asset_class"] == "crypto")
    for name, value, res, stmt in (
        ("high_vol_share_after", hv.value, hv,
         f"Après l'ajout envisagé, la part des positions très volatiles serait de {format_pct(hv.value)}."),
        ("top3_concentration_after", top3.value, top3,
         f"Après l'ajout envisagé, les trois plus grosses positions pèseraient {format_pct(top3.value)}."),
        ("crypto_share_after", crypto, None,
         f"Après l'ajout envisagé, la part des cryptomonnaies serait de {format_pct(crypto)}."),
    ):
        inputs = {"ticker": ticker, "intended_weight": intended_weight,
                  "positions_after": {p["ticker"]: round(p["weight"], 6) for p in after["positions"]}}
        if res is not None:
            inputs["detail"] = res.evidence["inputs"]
        e = make_evidence(kind="portfolio_calc", statement=stmt, value=value, unit="fraction",
                          as_of=data.data_as_of(), inputs=inputs, source="portefeuille fourni, data/prices_daily.csv",
                          computed_by=f"core.rules_engine.{name}")
        vals[name] = value
        ev[name] = registry.add(e)
    if any(p["ticker"] != ticker for p in portfolio.get("positions", [])):
        put("corr_to_portfolio", metrics.corr_to_portfolio(portfolio, ticker))
    return vals, ev


def check_coherence(profile: dict[str, Any], portfolio: dict[str, Any], consideration: dict[str, Any],
                    registry: EvidenceRegistry | None = None, rules: RuleSet | None = None) -> dict[str, Any]:
    """Profile x portfolio x consideration -> verdict, rule_hits, metrics and evidence ids (no explanation)."""
    rs = rules or load_rules()
    reg = registry if registry is not None else EvidenceRegistry()
    ticker = str(consideration.get("ticker", "")).strip().upper()
    w = consideration.get("intended_weight")
    if ticker not in data.load_universe().index:
        raise AlphaForgeError("UNKNOWN_TICKER", f"{ticker or '(vide)'} ne fait pas partie des 31 actifs analysés.",
                              details={"ticker": ticker})
    if not isinstance(w, int | float) or not 0 < w < 1:
        raise AlphaForgeError("INVALID_CONSIDERATION", "Le poids visé doit être strictement entre 0 % et 100 %.",
                              details={"intended_weight": w})
    thr = rs.profile_rules.high_vol_threshold
    vals, ev_ids = coherence_metrics(profile, portfolio, ticker, float(w), reg, thr)
    ctx = {"profile": profile, "consideration": {"ticker": ticker, "intended_weight": w}}
    hits: list[dict[str, Any]] = []
    hit_ev: dict[str, list[str]] = {}
    for rule in rs.coherence.rules:
        res = evaluate(rule.when, ctx, vals)
        if not res.ok:
            continue
        metric_names = [c.metric for c in rule.when if c.metric]
        unit = COHERENCE_METRICS.get(next((m for m in reversed(metric_names)
                                           if COHERENCE_METRICS.get(m) not in ("bool", "text")), ""), "fraction")
        limit_unit = "years" if unit == "years" else unit
        text = _render(rule.text_fr, observed=_fmt(res.observed, unit), limit=_fmt(res.limit, limit_unit),
                       ticker=ticker)
        hit: dict[str, Any] = {"rule_id": rule.id, "text": text, "severity": rule.severity}
        if res.observed is not None:
            hit["observed"] = round(float(res.observed), 6)
            hit["limit"] = round(float(res.limit), 6)
        hits.append(hit)
        cited = sorted({ev_ids[m] for m in metric_names if m in ev_ids})
        rule_ev = make_evidence(kind="rule_hit", statement=f"Règle {rule.id} déclenchée: {text}",
                                value=hit.get("observed"), unit=unit if unit in ("fraction", "days") else None,
                                as_of=data.data_as_of(),
                                inputs={"rule_id": rule.id, "severity": rule.severity, "observed": hit.get("observed"),
                                        "limit": hit.get("limit"), "metric_evidence": cited},
                                source="rules/coherence_rules.yaml", computed_by="core.rules_engine.check_coherence")
        hit_ev[rule.id] = [reg.add(rule_ev), *cited]
    n_high = sum(h["severity"] == "high" for h in hits)
    n_med = sum(h["severity"] in ("medium", "high") for h in hits)
    v = rs.coherence.verdict
    verdict = ("incoherent" if n_high >= v.incoherent_if_high_at_least
               else "tension" if n_med >= v.tension_if_medium_at_least else "coherent")
    return {
        "verdict": verdict,
        "rule_hits": hits,
        "metrics": {"annualized_vol": vals["annualized_vol"], "max_drawdown": vals["max_drawdown"],
                    "worst_calendar_year_return": vals["worst_calendar_year_return"],
                    "position_weight_after": vals["position_weight_after"]},
        "metric_values": vals,
        "metric_evidence": ev_ids,
        "rule_evidence": hit_ev,
    }
