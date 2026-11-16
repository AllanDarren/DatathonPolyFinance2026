"""Multi-agent validation layer: diversification analyst, risk analyst (instrument risks),
governance agent, "what would change the answer", and the guardian's past-performance /
forecast checks. All offline (mock), deterministic, against role D's real rules."""

from __future__ import annotations

from typing import Any

import pytest

from agents import guardian, orchestrator
from core import rules_engine as engine
from core.diversification import diversification_impact
from core.evidence import EvidenceRegistry, make_evidence
from core.instruments import instrument_risks
from core.models import CoherenceResult
from core.portfolio import parse_portfolio
from core.sensitivity import weight_grid, what_would_change


@pytest.fixture(autouse=True)
def _real_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.ROOT / "rules"))
    engine.clear_cache()


def persona(pid: str) -> tuple[dict[str, Any], dict[str, Any]]:
    p = next(x for x in engine.load_personas() if x["id"] == pid)
    return p["profile"], parse_portfolio(p["sample_portfolio_csv"])


# --- diversification analyst -------------------------------------------------------


def test_qqq_next_to_spy_is_an_overlap() -> None:
    _, pf = persona("robert")  # holds SPY
    d = diversification_impact(pf, "QQQ", 0.10, EvidenceRegistry())
    assert d["verdict"] == "overlap"
    assert d["correlations"][0]["ticker"] == "SPY"
    assert d["correlations"][0]["correlation"] == pytest.approx(0.91, abs=0.02)  # team reference value


def test_new_asset_class_correlated_is_only_partial() -> None:
    _, pf = persona("robert")
    d = diversification_impact(pf, "NVDA", 0.10, EvidenceRegistry())
    assert d["verdict"] in ("partial", "overlap")  # a new class that moves with SPY is not "new exposure"
    assert d["asset_class_after"]["equity_us"] > 0
    assert sum(d["asset_class_after"].values()) == pytest.approx(1.0, abs=1e-6)


def test_diversification_numbers_are_evidence() -> None:
    _, pf = persona("robert")
    reg = EvidenceRegistry()
    d = diversification_impact(pf, "GLD", 0.10, reg)
    assert all(i in reg for i in d["evidence_ids"])
    assert all(c["evidence_id"] in reg for c in d["correlations"])


# --- risk analyst --------------------------------------------------------------------


@pytest.mark.parametrize("ticker,cls", [("NVDA", "equity_us"), ("XBB.TO", "bond_etf"), ("BTC-USD", "crypto"),
                                        ("GLD", "gold_etf"), ("RY.TO", "equity_ca"), ("SPY", "equity_etf")])
def test_instrument_risks_by_class(ticker: str, cls: str) -> None:
    r = instrument_risks(ticker)
    assert r["asset_class"] == cls and r["risks"]
    if r["price_currency"] == "USD":
        assert any(x["risk"] == "currency" for x in r["risks"])


def test_bond_etf_highlights_rate_risk() -> None:
    r = instrument_risks("TLT")
    assert any(x["risk"] == "rates_inflation" and x["level"] == "high" for x in r["risks"])


# --- what would change the answer --------------------------------------------------


def test_robert_nvda_20_what_would_change() -> None:
    prof, pf = persona("robert")
    reg = EvidenceRegistry()
    res = engine.check_coherence(prof, pf, {"ticker": "NVDA", "intended_weight": 0.2})
    changes, grid = what_would_change(prof, pf, "NVDA", 0.2, [h["rule_id"] for h in res["rule_hits"]], reg)
    by_rule = {c["rule_id"]: c for c in changes}
    limit = prof["limits"]["max_single_position"]
    assert by_rule["C_MAX_SINGLE"]["kind"] == "weight"
    assert by_rule["C_MAX_SINGLE"]["max_weight"] == pytest.approx(limit)  # rule is "> limit"
    assert by_rule["C_DRAWDOWN_VS_LOSS"]["kind"] == "profile"  # depends on the asset, not the amount
    assert all(c["evidence_id"] in reg for c in changes)
    assert any(g["weight"] == 0.2 and g["verdict"] == "incoherent" for g in grid)


def test_weight_grid_is_monotonic() -> None:
    prof, pf = persona("robert")
    rank = {"coherent": 0, "tension": 1, "incoherent": 2}
    grid = weight_grid(prof, pf, "NVDA", [0.02, 0.05, 0.1, 0.15, 0.2, 0.3])
    ranks = [rank[g["verdict"]] for g in grid]
    assert ranks == sorted(ranks)


# --- governance agent + full orchestration -----------------------------------------


def consider(pid: str, ticker: str, weight: float) -> dict[str, Any]:
    prof, pf = persona(pid)
    out = orchestrator.consider(prof, pf, {"ticker": ticker, "intended_weight": weight}, EvidenceRegistry(), None)
    CoherenceResult.model_validate(out)  # contract
    return out


def controls(out: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in out["governance"]["controls"]}


def test_governance_robert_nvda() -> None:
    out = consider("robert", "NVDA", 0.2)
    c = controls(out)
    assert out["verdict"] == "incoherent"
    assert c["G_PROFILE_LIMITS"]["status"] == "fail"
    assert c["G_SIMULATION"]["status"] == "info"
    assert any("Dépenses mensuelles" in m for m in out["governance"]["missing_info"])  # Robert has none declared
    assert out["governance"]["status"] == "fail"


def test_governance_mateo_excluded_sector_and_controversy() -> None:
    out = consider("mateo", "XOM", 0.05)
    c = controls(out)
    assert c["G_EXCLUDED_SECTOR"]["status"] == "fail"  # Mateo excludes fossil fuels, XOM is Energy
    assert "G_CONTROVERSY" in c  # Mateo asked to avoid controversies


def test_trace_shows_every_agent_step() -> None:
    out = consider("amira", "NVDA", 0.2)
    tools = [t["tool"] for t in out["agent_trace"]]
    for name in ("check_coherence", "get_diversification_impact", "get_instrument_risks", "what_would_change",
                 "governance_review", "explain_and_guard"):
        assert name in tools
    assert [t["step"] for t in out["agent_trace"]] == list(range(1, len(tools) + 1))


def test_verdict_still_comes_from_rules() -> None:
    prof, pf = persona("robert")
    rules_verdict = engine.check_coherence(prof, pf, {"ticker": "NVDA", "intended_weight": 0.2})["verdict"]
    assert consider("robert", "NVDA", 0.2)["verdict"] == rules_verdict


# --- guardian: the past measures risk, it never predicts ---------------------------


def _reg_with_return(value: float) -> tuple[EvidenceRegistry, str]:
    reg = EvidenceRegistry()
    ev = make_evidence(kind="metric", statement="Rendement total sur la fenêtre: x.", value=value, unit="fraction",
                       as_of="2026-11-12", inputs={"ticker": "NVDA"}, source="test",
                       computed_by="core.metrics.return_5y")
    return reg, reg.add(ev)


def test_guardian_removes_past_return_used_as_argument() -> None:
    reg, ev = _reg_with_return(2.4)
    d = guardian.Draft(template=f"NVDA a bien performé avec {{{{{ev}}}}} sur cinq ans.", label="fact",
                       evidence_ids=[ev])
    rev = guardian.review([d], reg, None)
    assert rev.claims == [] and any("rendement passé" in f for f in rev.flags)


def test_guardian_keeps_past_loss_described_as_risk() -> None:
    reg, ev = _reg_with_return(-0.5)
    d = guardian.Draft(template=f"Sur la fenêtre, le rendement total a été de {{{{{ev}}}}}.", label="fact",
                       evidence_ids=[ev], origin="template")
    assert guardian.review([d], reg, None).claims


def test_guardian_removes_forecast() -> None:
    reg, ev = _reg_with_return(-0.5)
    d = guardian.Draft(template=f"Après {{{{{ev}}}}}, le titre devrait progresser.", label="hypothesis",
                       evidence_ids=[ev])
    rev = guardian.review([d], reg, None)
    assert rev.claims == [] and any("prévision" in f for f in rev.flags)
