"""The purchase explanation can cite the profile (risk, horizon, loss, limits) in plain French."""

from __future__ import annotations

import pytest

from agents.orchestrator import consider
from core import rules_engine as engine
from core.evidence import EvidenceRegistry, format_value
from core.portfolio import parse_portfolio

INTERNAL_CODES = ("low_moderate", "new_exposure", "partial", "overlap", "capital_preservation")


@pytest.fixture(autouse=True)
def _real_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.ROOT / "rules"))
    engine.clear_cache()


def _persona(pid: str) -> dict:
    import services

    return next(p for p in services.get_personas() if p["id"] == pid)


def test_profile_facts_are_french_evidence() -> None:
    p = _persona("robert")["profile"]
    reg = EvidenceRegistry()
    ids = engine.profile_evidence(p, reg)
    evs = [reg.get(i) for i in ids]
    assert len(evs) == 5 and all(e["kind"] == "rule_hit" for e in evs)
    text = " ".join(e["statement"] + " " + format_value(e) for e in evs)
    assert "faible à modérée" in text and "ans" in text
    assert not any(code in text for code in INTERNAL_CODES)
    horizon = next(e for e in evs if e["inputs"]["field"] == "horizon_years")
    assert format_value(horizon) == f"{p['horizon_years']:g} ans"
    assert ".0" not in horizon["statement"]


def test_purchase_explanation_gets_profile_and_french_values() -> None:
    persona = _persona("robert")
    portfolio = parse_portfolio(persona["sample_portfolio_csv"])
    reg = EvidenceRegistry()
    res = consider(persona["profile"], portfolio, {"ticker": "NVDA", "intended_weight": 0.2}, reg, None)
    cited = {i for c in res["explanation"]["claims"] for i in c["evidence_ids"]}
    fields = {reg.get(i)["inputs"].get("field") for i in reg.to_dict()}
    assert {"risk_tolerance", "horizon_years", "limits.max_single_position"} <= fields
    assert cited  # template explanation still cites evidence offline
    rendered = " ".join(format_value(e) for e in reg.to_dict().values())
    assert not any(code in rendered.split() for code in INTERNAL_CODES)


def test_diversification_is_stated_by_code_verbatim() -> None:
    persona = _persona("amira")
    portfolio = parse_portfolio(persona["sample_portfolio_csv"])
    reg = EvidenceRegistry()
    res = consider(persona["profile"], portfolio, {"ticker": "NVDA", "intended_weight": 0.2}, reg, None)
    verdict_id = res["diversification"]["evidence_ids"][0]
    div_claims = [c for c in res["explanation"]["claims"] if verdict_id in c["evidence_ids"]]
    assert len(div_claims) == 1
    claim = div_claims[0]
    assert claim["text"] == reg.get(verdict_id)["statement"]
    assert claim["label"] == "fact" and claim["verified"] == "supported"
