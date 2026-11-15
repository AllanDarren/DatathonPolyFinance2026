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

from agents.explainer import explain
from agents.llm import LLMClient, LLMUnavailableError, MockClient
from agents.prompts import load_prompt, render_prompt
from core import data, event_study, metrics
from core import rules_engine as engine
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry, format_pct

MAX_TOOL_CALLS = 5
MAX_TURNS = 4

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

    def run(self, name: str, params: dict[str, Any], *, forced: bool = False) -> dict[str, Any]:
        fn: Callable[[dict[str, Any]], tuple[dict[str, Any], list[str]]] | None = {
            "check_coherence": self.check_coherence, "get_position_metrics": self.get_position_metrics,
            "get_calendar_year_return": self.get_calendar_year_return, "get_event_context": self.get_event_context,
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


def consider(profile: dict[str, Any], portfolio: dict[str, Any], consideration: dict[str, Any],
             registry: EvidenceRegistry, client: LLMClient | None) -> dict[str, Any]:
    """CoherenceResult contract dict (with agent_trace) for a considered purchase."""
    ticker = str(consideration.get("ticker", "")).strip().upper()
    cons = {"ticker": ticker, "intended_weight": consideration.get("intended_weight")}
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
    if box.coherence is None:
        box.run("check_coherence", cons, forced=True)
    res = box.coherence
    assert res is not None
    context = json.dumps({"task": "coherence of a considered purchase", "ticker": ticker,
                          "intended_weight": format_pct(weight, 0), "verdict": res["verdict"],
                          "profile": {"horizon_years": profile["horizon_years"],
                                      "risk_tolerance": profile["risk_tolerance"]}}, ensure_ascii=False)
    explanation = explain(box.evidence_ids, registry, context=context, client=client)
    return {
        "verdict": res["verdict"],
        "rule_hits": res["rule_hits"],
        "metrics": res["metrics"],
        "explanation": explanation,
        "agent_trace": box.trace,
    }
