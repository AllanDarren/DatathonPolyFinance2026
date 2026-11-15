"""Any listed asset in « Tester un achat »: on-demand download (mocked, no network), asset-class
rules, refusals, quality gate, evidence citing the real source."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

import services
from core import data
from core import rules_engine as engine
from core.errors import AlphaForgeError
from core.models import FeedResponse
from core.portfolio import parse_portfolio
from ingest import market


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    monkeypatch.setenv("RULES_DIR", str(engine.ROOT / "rules"))
    monkeypatch.setenv("MARKET_CACHE_DIR", str(tmp_path))
    engine.clear_cache()
    yield
    data.clear_caches()


def fake_history(n: int | None = None, crypto: bool = False, seed: int = 3) -> pd.DataFrame:
    if crypto:
        days = pd.date_range("2021-11-12", data.data_as_of(), freq="D")
    else:
        days = data.price_series("SPY", "close").index
    days = days[: n or len(days)]
    rng = np.random.default_rng(seed)
    px = 50 * np.cumprod(1 + rng.normal(0.0004, 0.015, len(days)))
    return pd.DataFrame({"date": days, "open": px, "high": px * 1.01, "low": px * 0.99, "close": px, "adj_close": px,
                         "volume": 5000, "dividend": 0.0, "split": 0.0})


def mock_download(monkeypatch: pytest.MonkeyPatch, df: pd.DataFrame, **meta: Any) -> list[str]:
    calls: list[str] = []
    info = {"quote_type": "EQUITY", "currency": "USD", "name": "Test Corp", "sector": "Technology", "category": "",
            "market": "NMS"} | meta

    def fake(ticker: str, start: str, end: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        calls.append(ticker)
        return df, dict(info)

    monkeypatch.setattr(market, "_download", fake)
    return calls


def robert() -> tuple[dict[str, Any], dict[str, Any]]:
    p = next(x for x in engine.load_personas() if x["id"] == "robert")
    return p["profile"], parse_portfolio(p["sample_portfolio_csv"])


@pytest.mark.parametrize("qt,ccy,category,name,expected", [
    ("EQUITY", "USD", "", "Costco", "equity_us"),
    ("EQUITY", "CAD", "", "BCE", "equity_ca"),
    ("ETF", "USD", "Intermediate Core Bond", "Vanguard Total Bond", "bond_etf"),
    ("ETF", "USD", "Commodities Focused", "iShares Gold Trust", "gold_etf"),
    ("ETF", "USD", "Large Blend", "Total Stock Market", "equity_etf"),
    ("CRYPTOCURRENCY", "USD", "", "Solana", "crypto"),
])
def test_asset_class_rules(qt: str, ccy: str, category: str, name: str, expected: str) -> None:
    assert market.classify("X", qt, ccy, category, name) == expected


@pytest.mark.parametrize("qt,ccy,reason", [("MUTUALFUND", "USD", "MUTUALFUND"), ("EQUITY", "EUR", "CURRENCY_NOT_SUPPORTED"),
                                           ("OPTION", "USD", "OPTION"), (None, None, "NOT_FOUND")])
def test_unsupported_assets_are_refused_clearly(qt: str | None, ccy: str | None, reason: str) -> None:
    with pytest.raises(AlphaForgeError) as exc:
        market.classify("X", qt, ccy, "", "")
    assert exc.value.details["reason"] == reason and exc.value.message


def test_any_us_stock_gets_a_full_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = mock_download(monkeypatch, fake_history())
    prof, pf = robert()
    f = services.build_feed(prof, pf, {"ticker": "cost", "intended_weight": 0.1})
    FeedResponse.model_validate(f)
    c = f["coherence"]
    assert c["asset_origin"] == "on_demand" and c["data_quality"]["origin"] == "on_demand"
    assert c["instrument_risks"]["asset_class"] == "equity_us"
    assert {t["tool"] for t in c["agent_trace"]} >= {"check_coherence", "get_diversification_impact"}
    vol_ev = [e for e in f["evidence"].values() if e["computed_by"] == "core.metrics.annualized_vol"
              and e["inputs"]["ticker"] == "COST"]
    assert vol_ev and vol_ev[0]["source"].startswith("yfinance")
    services.build_feed(prof, pf, {"ticker": "COST", "intended_weight": 0.05})
    assert calls == ["COST"]  # downloaded once, then reused


def test_disk_cache_makes_the_request_reproducible(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = mock_download(monkeypatch, fake_history())
    market.ensure_asset("ABC")
    data.clear_caches()  # new process
    market.ensure_asset("ABC")
    assert calls == ["ABC"]


def test_short_history_asset_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_download(monkeypatch, fake_history(n=200))
    prof, pf = robert()
    with pytest.raises(AlphaForgeError) as exc:
        services.build_feed(prof, pf, {"ticker": "NEWIPO", "intended_weight": 0.05})
    assert exc.value.code == "INSUFFICIENT_DATA"


def test_crypto_on_demand(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_download(monkeypatch, fake_history(crypto=True), quote_type="CRYPTOCURRENCY", sector="")
    prof, pf = robert()
    c = services.build_feed(prof, pf, {"ticker": "SOL-USD", "intended_weight": 0.05})["coherence"]
    assert c["instrument_risks"]["asset_class"] == "crypto"
    assert "C_CRYPTO_LOW" in {h["rule_id"] for h in c["rule_hits"]}  # Robert's low-risk profile


def test_provider_failure_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any) -> Any:
        raise TimeoutError("slow")

    monkeypatch.setattr(market, "_download", boom)
    with pytest.raises(AlphaForgeError) as exc:
        market.ensure_asset("ZZZZ")
    assert exc.value.code == "MARKET_DATA_UNAVAILABLE" and exc.value.status == 503


def test_search_lists_verified_assets_first(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_a: Any, **_k: Any) -> Any:
        raise OSError("offline")

    monkeypatch.setattr(market, "urlopen", no_network)
    res = market.search_assets("nvid")
    assert res[0]["ticker"] == "NVDA" and res[0]["in_starter_dataset"] is True
