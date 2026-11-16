"""In the purchase explanation, diversification is stated by code, verbatim from its evidence."""

from __future__ import annotations

import pytest

import services
from agents.orchestrator import consider
from core import rules_engine as engine
from core.evidence import EvidenceRegistry
from core.portfolio import parse_portfolio


@pytest.fixture(autouse=True)
def _real_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.ROOT / "rules"))
    engine.clear_cache()


@pytest.mark.parametrize(("pid", "ticker"), [("amira", "NVDA"), ("mateo", "XOM"), ("robert", "NVDA")])
def test_diversification_is_stated_by_code_verbatim(pid: str, ticker: str) -> None:
    persona = next(p for p in services.get_personas() if p["id"] == pid)
    portfolio = parse_portfolio(persona["sample_portfolio_csv"])
    reg = EvidenceRegistry()
    res = consider(persona["profile"], portfolio, {"ticker": ticker, "intended_weight": 0.2}, reg, None)
    verdict_id = res["diversification"]["evidence_ids"][0]
    div_claims = [c for c in res["explanation"]["claims"] if verdict_id in c["evidence_ids"]]
    assert len(div_claims) == 1
    assert div_claims[0]["text"] == reg.get(verdict_id)["statement"]
    assert div_claims[0]["label"] == "fact" and div_claims[0]["verified"] == "supported"
