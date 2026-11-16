"""Tool-using agent for "J'envisage d'acheter X" (Bedrock Converse tool use).

The model chooses which evidence to gather among four tools; the code executes them
and records every call (name, parameters, evidence ids, duration) in `agent_trace`.
The verdict always comes from `check_coherence` (rules), never from the model: if
the model does not call it, the code does (`forced: true`). Then the explainer
drafts the explanation from the gathered evidence and the guardian checks it.

Offline (MockClient), a deterministic planner makes the same kind of calls.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from agents.explainer import explain, with_diversification_claim
from agents.governance import govern
from agents.llm import LLMClient, LLMUnavailableError, MockClient
from agents.prompts import load_prompt, render_prompt
from core import data, event_study, metrics
from core import rules_engine as engine
from core.diversification import diversification_impact
from core.instruments import instrument_risks
from core.sensitivity import what_would_change
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry, format_pct

MAX_TOOL_CALLS = 7
MAX_TURNS = 5
# Tools whose output the response always needs: the code calls them if the model did not (`forced: true`).
REQUIRED_TOOLS = ("check_coherence", "get_diversification_impact", "get_instrument_risks")

TOOLS: list[dict[str, Any]] = [
    {"toolSpec": {"name": "check_coherence",
                  "description": "Apply the profile's coherence rules to the considered purchase. Returns the verdict "
                                 "and triggered rules. Call exactly once.",
                  "inputSchema": {"json": {"type": "object", "properties": {
                      "ticker": {"type": "string"}, "intended_weight": {"type": "number"}},
                      "required": ["ticker", "intended_weight"]}}}},
    {"toolSpec": {"name": "get_position_metrics",
                  "description": "Risk metrics of an asset over 5 years: annualized volatility, max drawdown, "
                                 "recovery time, worst calendar year.",
                  "inputSchema": {"json": {"type": "object", "properties": {"ticker": {"type": "string"}},
                                           "required": ["ticker"]}}}},
    {"toolSpec": {"name": "get_calendar_year_return",
                  "description": "Return of an asset for one complete calendar year (2022 to 2025).",
                  "inputSchema": {"json": {"type": "object", "properties": {
                      "ticker": {"type": "string"}, "year": {"type": "integer"}}, "required": ["ticker", "year"]}}}},
    {"toolSpec": {"name": "get_event_context",
                  "description": "Historical moves of an asset around past events (earnings, dividend_ex_date, "
                                 "rate_decision). Not a forecast.",
                  "inputSchema": {"json": {"type": "object", "properties": {
                      "ticker": {"type": "string"},
                      "event_type": {"type": "string", "enum": ["earnings", "dividend_ex_date", "rate_decision"]}},
                      "required": ["ticker", "event_type"]}}}},
    {"toolSpec": {"name": "get_diversification_impact",
                  "description": "Diversification analyst: correlation of the asset with each held position, "
                                 "asset-class and currency exposures before/after. Says whether the asset adds a new "
                                 "source of risk or duplicates one already held.",
                  "inputSchema": {"json": {"type": "object", "properties": {"ticker": {"type": "string"}},
                                           "required": ["ticker"]}}}},
    {"toolSpec": {"name": "get_instrument_risks",
                  "description": "Risk analyst: what the investor really owns with this type of instrument "
                                 "(stock, equity ETF, bond ETF, gold ETF, crypto) and the risks to understand.",
                  "inputSchema": {"json": {"type": "object", "properties": {"ticker": {"type": "string"}},
                                           "required": ["ticker"]}}}},
]


class Toolbox:
    """Executes tools, registers evidence, keeps the trace."""

    def __init__(self, profile: dict[str, Any], portfolio: dict[str, Any], consideration: dict[str, Any],
                 registry: EvidenceRegistry, planner: str) -> None:
        self.profile, self.portfolio, self.consideration = profile, portfolio, consideration
        self.registry = registry
        self.planner = planner
        self.trace: list[dict[str, Any]] = []
        self.coherence: dict[str, Any] | None = None
        self.evidence_ids: list[str] = []
        self.historical: dict[str, Any] | None = None
        self.diversification: dict[str, Any] | None = None
        self.instrument: dict[str, Any] | None = None

    def _ticker(self, params: dict[str, Any]) -> str:
        t = str(params.get("ticker", "")).strip().upper()
        if t not in data.load_universe().index:
            raise AlphaForgeError("UNKNOWN_TICKER", f"{t} hors univers")
        return t

    def _add(self, *results: metrics.MetricResult) -> list[str]:
        ids = [self.registry.add(r) for r in results]
        self.evidence_ids.extend(i for i in ids if i not in self.evidence_ids)
        return ids

    def check_coherence(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        # The user's consideration is authoritative: the model cannot change ticker or weight.
        res = engine.check_coherence(self.profile, self.portfolio, self.consideration, self.registry)
        self.coherence = res
        ids = sorted({i for v in res["rule_evidence"].values() for i in v}
                     | {res["metric_evidence"][k] for k in ("position_weight_after", "max_drawdown")})
        self.evidence_ids.extend(i for i in ids if i not in self.evidence_ids)
        return {"verdict": res["verdict"], "rules": [h["text"] for h in res["rule_hits"]]}, ids

    def get_position_metrics(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        t = self._ticker(params)
        results = [metrics.annualized_vol(t), metrics.max_drawdown(t), metrics.recovery_days(t),
                   metrics.worst_calendar_year_return(t)]
        return {"statements": [r.evidence["statement"] for r in results]}, self._add(*results)

    def get_calendar_year_return(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        t = self._ticker(params)
        r = metrics.calendar_year_return(t, int(params.get("year", 2022)))
        return {"statement": r.evidence["statement"]}, self._add(r)

    def get_event_context(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        t = self._ticker(params)
        etype = str(params.get("event_type", "earnings"))
        macro = "federalreserve" if etype == "rate_decision" else None
        ctx, res = event_study.historical_context(etype, t, macro_source=macro)
        self.historical = ctx
        return {"statement": res.evidence["statement"], "caveats": ctx["caveats"]}, self._add(res)

    def get_diversification_impact(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        # Diversification of the user's consideration (the model cannot change ticker or weight).
        cfg = engine.load_rules().instrument_risks
        thr = cfg.diversification if cfg else None
        res = diversification_impact(self.portfolio, self.consideration["ticker"],
                                     float(self.consideration["intended_weight"]), self.registry,
                                     overlap_corr=thr.overlap_corr if thr else 0.8,
                                     new_exposure_corr=thr.new_exposure_corr if thr else 0.3)
        self.diversification = res
        self.evidence_ids.extend(i for i in res["evidence_ids"][:2] if i not in self.evidence_ids)
        return {"verdict": res["verdict"], "statement": res["text_fr"]}, res["evidence_ids"]

    def get_instrument_risks(self, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        res = instrument_risks(self.consideration["ticker"])
        self.instrument = res
        return {"instrument": res["label_fr"], "risks": [f"{r['label_fr']} ({r['level']}): {r['text_fr']}"
                                                          for r in res["risks"]]}, []

    def run(self, name: str, params: dict[str, Any], *, forced: bool = False) -> dict[str, Any]:
        fn: Callable[[dict[str, Any]], tuple[dict[str, Any], list[str]]] | None = {
            "check_coherence": self.check_coherence, "get_position_metrics": self.get_position_metrics,
            "get_calendar_year_return": self.get_calendar_year_return, "get_event_context": self.get_event_context,
            "get_diversification_impact": self.get_diversification_impact,
            "get_instrument_risks": self.get_instrument_risks,
        }.get(name)
        start = time.perf_counter()
        entry: dict[str, Any] = {"step": len(self.trace) + 1, "tool": name, "params": dict(params), "evidence_ids": [],
                                 "status": "ok", "forced": forced, "planner": self.planner, "duration_ms": 0}
        try:
            if fn is None:
                raise AlphaForgeError("UNKNOWN_TOOL", f"outil inconnu: {name}")
            result, ids = fn(params)
            entry["evidence_ids"] = ids
        except AlphaForgeError as exc:
            entry.update(status="error", error=exc.message)
            result = {"error": exc.message}
        entry["duration_ms"] = int((time.perf_counter() - start) * 1000)
        self.trace.append(entry)
        return result


def _mock_plan(ticker: str, weight: float) -> list[tuple[str, dict[str, Any]]]:
    plan: list[tuple[str, dict[str, Any]]] = [
        ("check_coherence", {"ticker": ticker, "intended_weight": weight}),
        ("get_position_metrics", {"ticker": ticker}),
        ("get_calendar_year_return", {"ticker": ticker, "year": 2022}),
        ("get_diversification_impact", {"ticker": ticker}),
        ("get_instrument_risks", {"ticker": ticker}),
    ]
    if data.load_universe().loc[ticker, "asset_class"] in ("equity_ca", "equity_us"):
        plan.append(("get_event_context", {"ticker": ticker, "event_type": "earnings"}))
    return plan


def _llm_loop(client: LLMClient, box: Toolbox, ticker: str, weight: float) -> None:
    text, _ = load_prompt("orchestrator")
    p = box.profile
    system = render_prompt(text, ticker=ticker, weight=format_pct(weight, 0), horizon=p["horizon_years"],
                           risk=p["risk_tolerance"], loss=format_pct(p["max_acceptable_loss_pct"], 0))
    messages: list[dict[str, Any]] = [{"role": "user", "content": [
        {"text": f"Considered purchase: {ticker} at {format_pct(weight, 0)} of the portfolio. Gather the evidence."}]}]
    calls = 0
    for _ in range(MAX_TURNS):
        resp = client.converse(system, messages, TOOLS)
        msg = resp["message"]
        messages.append(msg)
        uses = [c["toolUse"] for c in msg.get("content", []) if "toolUse" in c]
        if not uses:
            break
        results = []
        for use in uses:
            if calls >= MAX_TOOL_CALLS:
                out: dict[str, Any] = {"error": "limite d'appels d'outils atteinte"}
            else:
                out = box.run(use["name"], use.get("input") or {})
                calls += 1
            results.append({"toolResult": {"toolUseId": use["toolUseId"], "content": [{"json": out}]}})
        messages.append({"role": "user", "content": results})
        # Nothing left to gather: skip the closing turn (the model's final text is never used,
        # and it cost several seconds on the ~29 s request budget).
        used = {t["tool"] for t in box.trace}
        if calls >= MAX_TOOL_CALLS or all(t["toolSpec"]["name"] in used for t in TOOLS):
            break


def consider(profile: dict[str, Any], portfolio: dict[str, Any], consideration: dict[str, Any],
             registry: EvidenceRegistry, client: LLMClient | None) -> dict[str, Any]:
    """CoherenceResult contract dict (with agent_trace) for a considered purchase."""
    ticker = str(consideration.get("ticker", "")).strip().upper()
    cons = {"ticker": ticker, "intended_weight": consideration.get("intended_weight")}
    from core import quality

    if ticker in data.load_universe().index:
        q = quality.asset_quality(ticker)
        if q["status"] == "blocking":
            raise AlphaForgeError("INSUFFICIENT_DATA",
                                  f"Données de {ticker} insuffisantes pour un verdict fiable : " + " ".join(q["warnings_fr"]),
                                  status=422, details={"data_quality": quality.public(q)})
    engine.check_coherence(profile, portfolio, cons, EvidenceRegistry())  # validate inputs early (raises)
    weight = float(cons["intended_weight"])  # type: ignore[arg-type]
    offline = client is None or (isinstance(client, MockClient) and client.planner is None)
    box = Toolbox(profile, portfolio, cons, registry, "mock" if offline else client.model_id)  # type: ignore[union-attr]
    if offline:
        for name, params in _mock_plan(ticker, weight):
            box.run(name, params)
    else:
        try:
            _llm_loop(client, box, ticker, weight)  # type: ignore[arg-type]
        except LLMUnavailableError:
            box.planner = "mock"
            for name, params in _mock_plan(ticker, weight):
                if name not in {t["tool"] for t in box.trace}:
                    box.run(name, params, forced=True)
    called = {t["tool"] for t in box.trace if t["status"] == "ok"}
    for name in REQUIRED_TOOLS:
        if name not in called:
            box.run(name, {"ticker": ticker, "intended_weight": weight}, forced=True)
    res = box.coherence
    assert res is not None

    # What would change the answer (code: the same rules re-applied on a grid of weights).
    changes, grid = what_would_change(profile, portfolio, ticker, weight, [h["rule_id"] for h in res["rule_hits"]],
                                      registry)
    box.trace.append(_internal_step(box, "what_would_change", [c["evidence_id"] for c in changes]))
    # Governance agent: investor constraints, simulation boundaries, missing information.
    governance = govern(profile, portfolio, cons, res, box.diversification, registry, box.trace)
    box.trace.append(_internal_step(box, "governance_review",
                                    [i for c in governance["controls"] for i in c["evidence_ids"]]))

    # Diversification is stated by code, verbatim from its evidence: the writer kept misreading
    # correlations ("nouvelle source de risque" read as less diversification).
    div_ids = set(box.diversification["evidence_ids"]) if box.diversification else set()
    explain_ids = [i for i in [*box.evidence_ids, *[c["evidence_id"] for c in changes[:1]]] if i not in div_ids]
    context = json.dumps({"task": "coherence of a considered purchase", "ticker": ticker,
                          "intended_weight": format_pct(weight, 0), "verdict": res["verdict"],
                          "note": "Do not discuss diversification or correlation: it is stated separately.",
                          "profile": {"horizon_years": profile["horizon_years"],
                                      "risk_tolerance": profile["risk_tolerance"]}}, ensure_ascii=False)
    explanation = explain(explain_ids, registry, context=context, client=client)
    if box.diversification:
        explanation = with_diversification_claim(explanation, box.diversification["evidence_ids"][0], registry)
    box.trace.append(_internal_step(box, "explain_and_guard",
                                    [i for c in explanation["claims"] for i in c["evidence_ids"]]))
    g = explanation["guardian"]
    governance["controls"].append({
        "id": "G_EXPLANATION_CHECKED", "label_fr": "Explication vérifiée par le gardien",
        "status": "ok" if g["status"] == "passed" else "warning",
        "detail_fr": ("Chaque affirmation cite ses preuves; aucun chiffre non sourcé, aucun conseil, aucune prévision."
                      if g["status"] == "passed" else " ".join(g["flags"])),
        "evidence_ids": []})
    return {
        "verdict": res["verdict"],
        "rule_hits": res["rule_hits"],
        "metrics": res["metrics"],
        "explanation": explanation,
        "agent_trace": box.trace,
        "diversification": box.diversification,
        "instrument_risks": box.instrument,
        "governance": governance,
        "what_would_change": changes,
        "weight_grid": grid,
        "data_quality": quality.public(quality.asset_quality(ticker)),
        "asset_origin": "starter_dataset" if data.is_starter(ticker) else "on_demand",
    }


def _internal_step(box: Toolbox, name: str, evidence_ids: list[str]) -> dict[str, Any]:
    """Trace entry for an agent step run by the code (not chosen by the model)."""
    return {"step": len(box.trace) + 1, "tool": name, "params": {}, "evidence_ids": list(dict.fromkeys(evidence_ids)),
            "status": "ok", "forced": False, "planner": "code", "duration_ms": 0}
