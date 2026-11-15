"""A6: historical context on known synthetic cases + real data, mandatory caveats."""

from __future__ import annotations

import pandas as pd
import pytest

from core import event_study as es
from core.errors import AlphaForgeError
from core.models import Evidence, HistoricalContext


def synthetic_prices(n: int = 200) -> pd.Series:
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.Series(100.0, index=idx)


def test_known_synthetic_returns() -> None:
    prices = synthetic_prices()
    idx = prices.index
    dates = [idx[i] for i in range(10, 170, 16)]  # 10 events, no overlap
    for k, d in enumerate(dates):  # +1 % ... +10 % jump on the event day, flat otherwise
        pos = idx.get_loc(d)
        prices.iloc[pos:] *= 1 + (k + 1) / 100
    ctx, res = es.historical_context("earnings", "TEST", dates=dates, prices=prices, source="synthetic")
    HistoricalContext.model_validate(ctx)
    Evidence.model_validate(res.evidence)
    rets = [e["return"] for e in ctx["events"]]
    assert rets == pytest.approx([(k + 1) / 100 for k in range(10)])
    assert ctx["n_events"] == 10
    assert ctx["median_return"] == pytest.approx(0.055)
    assert ctx["share_positive"] == 1.0
    assert ctx["p10"] < ctx["median_return"] < ctx["p90"]
    assert ctx["evidence_id"] == res.evidence_id


def test_window_is_day_before_to_plus_5_trading_days() -> None:
    prices = synthetic_prices()
    d = prices.index[20]
    prices.iloc[19] = 50.0  # the day before: base of the window
    prices.iloc[25] = 60.0  # t+5: end of the window
    (w,) = es.window_returns(prices, [d])
    assert w["return"] == pytest.approx(0.2)
    assert (w["start"], w["end"]) == (prices.index[19].strftime("%Y-%m-%d"), prices.index[25].strftime("%Y-%m-%d"))


def test_weekend_event_maps_to_next_trading_day() -> None:
    prices = synthetic_prices()
    saturday = pd.Timestamp("2024-01-13")
    (w,) = es.window_returns(prices, [saturday])
    assert w["start"] == "2024-01-12"  # Friday close is the base


def test_refuses_under_8_events() -> None:
    prices = synthetic_prices()
    with pytest.raises(AlphaForgeError) as exc:
        es.historical_context("earnings", "TEST", dates=list(prices.index[10:80:10]), prices=prices)
    assert exc.value.code == "INSUFFICIENT_DATA" and "Données insuffisantes" in exc.value.message


def test_incomplete_windows_are_dropped() -> None:
    prices = synthetic_prices(30)
    assert es.window_returns(prices, [prices.index[0], prices.index[-2]]) == []


def test_caveats_are_always_present_and_overlaps_counted() -> None:
    prices = synthetic_prices()
    dates = list(prices.index[10:100:3])  # windows of 6 days every 3 days: overlaps
    ctx, _ = es.historical_context("earnings", "TEST", dates=dates, prices=prices)
    text = " ".join(ctx["caveats"])
    for word in ("Échantillon", "chevauch", "survivant", "pas une prévision"):
        assert word in text
    assert "se chevauchent" in text


@pytest.mark.parametrize(("event_type", "asset", "macro"), [
    ("earnings", "NVDA", None), ("earnings", "RY.TO", None), ("dividend_ex_date", "RY.TO", None),
    ("rate_decision", "SPY", "federalreserve"),
])
def test_real_data(event_type: str, asset: str, macro: str | None) -> None:
    ctx, res = es.historical_context(event_type, asset, macro_source=macro)
    HistoricalContext.model_validate(ctx)
    assert ctx["n_events"] >= 8
    assert -0.5 < ctx["median_return"] < 0.5
    assert res.evidence["kind"] == "event_study"
    if event_type == "dividend_ex_date":
        assert any("dividendes" in c for c in ctx["caveats"])


def test_unknown_type_and_ticker() -> None:
    with pytest.raises(AlphaForgeError):
        es.historical_context("weather", "NVDA")
    with pytest.raises(AlphaForgeError):
        es.historical_context("earnings", "FOO")
