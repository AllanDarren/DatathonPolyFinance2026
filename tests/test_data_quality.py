"""Data-quality gate: every check triggered on synthetic series, the starter dataset passes,
CNQ.TO's 1.021 factor is explained by a same-day dividend, blocking data never yields a verdict."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from agents import orchestrator
from core import data, metrics, quality
from core import rules_engine as engine
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry
from core.models import FeedResponse, QualityReport
from core.portfolio import parse_portfolio


@pytest.fixture(autouse=True)
def _real_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.ROOT / "rules"))
    engine.clear_cache()


def synthetic(n_days: int = 1000, start: str = "2021-11-12", drop: list[int] | None = None, seed: int = 1) -> pd.DataFrame:
    """Business-day series that follows SPY's calendar (USD listing), random walk."""
    days = data.price_series("SPY", "close").index
    days = days[days >= pd.Timestamp(start)][:n_days]
    rng = np.random.default_rng(seed)
    px = 100 * np.cumprod(1 + rng.normal(0, 0.01, len(days)))
    df = pd.DataFrame({"date": days, "open": px, "high": px * 1.01, "low": px * 0.99, "close": px, "adj_close": px,
                       "volume": 1000})
    if drop:
        df = df.drop(index=drop).reset_index(drop=True)
    return df


def assess(df: pd.DataFrame, **kw: Any) -> dict[str, Any]:
    return quality.assess("TEST", df, asset_class="equity_us", price_currency="USD", **kw)


def test_clean_series_is_ok_and_matches_contract() -> None:
    q = assess(synthetic(5000))  # whole window, up to the dataset's last date
    assert q["status"] == "ok" and not q["warnings_fr"]
    QualityReport.model_validate(quality.public(q))
    assert q["notes_fr"]  # USD listing: FX carried forward on Canadian holidays is disclosed


def test_short_history_is_blocking() -> None:
    q = assess(synthetic(200))
    assert q["status"] == "blocking" and "historique" in q["warnings_fr"][0]


def test_missing_days_blocking() -> None:
    df = synthetic(1240, drop=list(range(100, 300)))  # ~16 % of expected days missing
    q = assess(df)
    assert q["status"] == "blocking" and q["missing_days"] == 200


def test_stale_price_and_outlier_and_ohlc() -> None:
    df = synthetic(1240)
    df.loc[500:507, ["open", "high", "low", "close", "adj_close"]] = df.loc[499, "close"]  # 9 identical closes
    df.loc[800, ["close", "adj_close", "high"]] = df.loc[799, "close"] * 1.6  # +60 % in a day
    df.loc[900, "low"] = df.loc[900, "close"] * 1.2  # low above close
    q = assess(df)
    assert q["status"] == "warning"
    assert q["stale_runs"] and q["outliers"] and q["ohlc_issues"] == 1


def test_unexplained_fractional_split_is_a_warning() -> None:
    df = synthetic(1240)
    splits = pd.DataFrame({"ex_date": [df["date"].iloc[600]], "value": [1.021]})
    q = assess(df, splits=splits)
    assert q["odd_splits"][0]["explained"] is False and q["status"] == "warning"


def test_starter_dataset_has_no_blocking_asset() -> None:
    for t in data.starter_tickers():
        assert quality.asset_quality(t)["status"] != "blocking", t


def test_cnq_special_distribution_is_explained() -> None:
    q = quality.asset_quality("CNQ.TO")
    assert q["odd_splits"] == [{"date": "2022-08-22", "factor": 1.021, "explained": True}]
    assert any("une seule fois" in n for n in q["notes_fr"])


def test_crypto_vol_365_with_252_sensitivity() -> None:
    r = metrics.annualized_vol("BTC-USD")
    assert r.value == pytest.approx(0.508, abs=0.01)
    assert r.evidence["inputs"]["days_per_year"] == 365
    assert r.evidence["inputs"]["sensitivity_252"] == pytest.approx(0.4217, abs=0.01)


def test_blocking_on_demand_asset_never_gets_a_verdict() -> None:
    df = synthetic(200)  # < 2 years
    q = quality.assess("ZZZ", df, asset_class="equity_us", price_currency="USD", origin="on_demand", source="test")
    data.register_extra_asset("ZZZ", {"name": "Test", "sector": "Technology", "asset_class": "equity_us",
                                      "price_currency": "USD"}, df.assign(ticker="ZZZ"), q)
    try:
        p = next(x for x in engine.load_personas() if x["id"] == "robert")
        with pytest.raises(AlphaForgeError) as exc:
            orchestrator.consider(p["profile"], parse_portfolio(p["sample_portfolio_csv"]),
                                  {"ticker": "ZZZ", "intended_weight": 0.05}, EvidenceRegistry(), None)
        assert exc.value.code == "INSUFFICIENT_DATA" and exc.value.status == 422
    finally:
        data.clear_caches()


def test_feed_reports_quality_of_each_position() -> None:
    from services.feed import build_feed

    p = next(x for x in engine.load_personas() if x["id"] == "robert")
    f = build_feed(p["profile"], parse_portfolio(p["sample_portfolio_csv"]), {"ticker": "NVDA", "intended_weight": 0.1})
    FeedResponse.model_validate(f)
    assert {q["ticker"] for q in f["data_quality"]} == {x["ticker"] for x in parse_portfolio(p["sample_portfolio_csv"])["positions"]}
    assert all(q["evidence_id"] in f["evidence"] for q in f["data_quality"])
    controls = {c["id"]: c for c in f["coherence"]["governance"]["controls"]}
    assert controls["G_DATA_QUALITY"]["status"] in ("ok", "warning")
    assert f["coherence"]["asset_origin"] == "starter_dataset"
