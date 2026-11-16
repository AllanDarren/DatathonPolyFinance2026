"""A2 golden tests. Reference values from the team's exploration (docs/VALIDATION.md), revalidated by an
independent computation (2026-11-14). Tolerances: 0.5 pt for returns/vol, 0.02 for
correlations. Volatility: daily returns x sqrt(252), or sqrt(365) for crypto (team
decision 2026-11-14); the context's vol references came from monthly returns.
"""

from __future__ import annotations

import pytest

from core import metrics as m
from core.errors import AlphaForgeError
from core.models import Evidence
from core.portfolio import parse_portfolio

RET = 0.005
CORR = 0.02
# References given to the point only (e.g. "BTC -64 %"): tolerance widened to 1 pt.
ROUNDED_TO_POINT = {"BTC-USD", "ETH-USD", "NVDA", "XOM", "TSLA", "AGG", "TLT"}


def tol(ticker: str) -> float:
    return 0.01 if ticker in ROUNDED_TO_POINT else RET


@pytest.mark.parametrize(("ticker", "expected"), [
    ("SPY", -0.182), ("QQQ", -0.326), ("AGG", -0.130), ("XBB.TO", -0.117), ("TLT", -0.312),
    ("GLD", -0.008), ("BTC-USD", -0.64), ("ETH-USD", -0.67), ("NVDA", -0.50), ("XOM", 0.87),
])
def test_calendar_year_2022(ticker: str, expected: float) -> None:
    assert m.calendar_year_return(ticker, 2022).value == pytest.approx(expected, abs=tol(ticker))


@pytest.mark.parametrize(("ticker", "expected"), [
    ("NVDA", -0.66), ("TSLA", -0.73), ("BTC-USD", -0.76), ("ETH-USD", -0.79), ("SPY", -0.245),
    ("AGG", -0.17), ("XBB.TO", -0.155), ("TLT", -0.44), ("ZST.TO", -0.004),
])
def test_max_drawdown(ticker: str, expected: float) -> None:
    assert m.max_drawdown(ticker).value == pytest.approx(expected, abs=tol(ticker))
    assert m.max_drawdown_abs(ticker).value == pytest.approx(-m.max_drawdown(ticker).value)


@pytest.mark.parametrize(("ticker", "expected", "days"), [
    ("BTC-USD", 0.508, 365), ("NVDA", 0.519, 252), ("SPY", 0.173, 252),
])
def test_annualized_vol(ticker: str, expected: float, days: int) -> None:
    res = m.annualized_vol(ticker)
    assert res.value == pytest.approx(expected, abs=RET)
    assert res.evidence["inputs"]["days_per_year"] == days


@pytest.mark.parametrize(("a", "b", "expected"), [
    ("QQQ", "SPY", 0.91), ("ESGV", "SPY", 0.99), ("BTC-USD", "ETH-USD", 0.83), ("BTC-USD", "QQQ", 0.49),
])
def test_monthly_correlation(a: str, b: str, expected: float) -> None:
    assert m.monthly_correlation(a, b).value == pytest.approx(expected, abs=CORR)


@pytest.mark.parametrize(("ticker", "currency", "expected"), [
    ("SPY", "native", 0.732), ("SPY", "CAD", 0.965), ("QQQ", "native", 0.796), ("ESGV", "native", 0.614),
])
def test_return_5y(ticker: str, currency: str, expected: float) -> None:
    assert m.return_5y(ticker, currency).value == pytest.approx(expected, abs=RET)


def test_cumulative_inflation_ca() -> None:
    assert m.cumulative_inflation_ca().value == pytest.approx(0.19, abs=0.01)


def test_worst_year_uses_complete_years_only() -> None:
    res = m.worst_calendar_year_return("NVDA")
    assert res.evidence["inputs"]["years"] == [2022, 2023, 2024, 2025]
    assert res.evidence["inputs"]["worst_year"] == 2022
    with pytest.raises(AlphaForgeError):
        m.calendar_year_return("NVDA", 2026)  # partial year
    with pytest.raises(AlphaForgeError):
        m.calendar_year_return("NVDA", 2021)  # no previous year-end


def test_recovery_days() -> None:
    spy = m.recovery_days("SPY")
    assert spy.value is not None and spy.value > 0
    inputs = spy.evidence["inputs"]
    assert inputs["peak_date"] < inputs["trough_date"] < inputs["recovery_date"]


def test_dividend_yield_ttm() -> None:
    ry = m.dividend_yield_ttm("RY.TO")
    assert ry.evidence["inputs"]["n_dividends"] == 4
    assert 0.01 < ry.value < 0.06
    assert m.dividend_yield_ttm("BTC-USD").value == 0


def test_is_high_vol_and_asset_class() -> None:
    assert m.is_high_vol("NVDA").value is True
    assert m.is_high_vol("XBB.TO").value is False
    assert m.asset_class("BTC-USD").value == "crypto"


@pytest.fixture
def portfolio() -> dict:
    return parse_portfolio("ticker,montant\nSPY,5000\nNVDA,2000\nXBB.TO,2000\nBTC-USD,1000\n")


def test_portfolio_metrics(portfolio: dict) -> None:
    assert m.position_weight(portfolio, "NVDA").value == pytest.approx(0.2)
    assert m.position_weight(portfolio, "TSLA").value == 0
    assert m.top3_concentration(portfolio).value == pytest.approx(0.9)
    hv = m.high_vol_share(portfolio)
    assert hv.value == pytest.approx(0.3)
    assert set(hv.evidence["inputs"]["tickers"]) == {"NVDA", "BTC-USD"}
    c = m.corr_to_portfolio(portfolio, "BTC-USD")
    assert -1 <= c.value <= 1 and c.evidence["inputs"]["n_months"] > 50


def test_position_weight_after(portfolio: dict) -> None:
    res = m.position_weight_after(portfolio, "TSLA", 0.2)
    assert res.value == 0.2
    # (0.2 * 10000 - 0) / 0.8 = 2500 CAD
    assert res.evidence["inputs"]["implied_added_amount_cad"] == pytest.approx(2500)
    assert "2 500 $" in res.evidence["statement"]
    with pytest.raises(AlphaForgeError) as exc:
        m.position_weight_after(portfolio, "TSLA", 1.2)
    assert exc.value.code == "INVALID_CONSIDERATION"


def test_unknown_ticker() -> None:
    with pytest.raises(AlphaForgeError) as exc:
        m.annualized_vol("FOO")
    assert exc.value.code == "UNKNOWN_TICKER"


def test_every_metric_returns_valid_deterministic_evidence(portfolio: dict) -> None:
    results = [
        m.annualized_vol("NVDA"), m.max_drawdown("NVDA"), m.max_drawdown_abs("NVDA"), m.recovery_days("NVDA"),
        m.calendar_year_return("NVDA", 2022), m.worst_calendar_year_return("NVDA"), m.return_5y("NVDA"),
        m.dividend_yield_ttm("NVDA"), m.asset_class("NVDA"), m.is_high_vol("NVDA"),
        m.position_weight(portfolio, "NVDA"), m.position_weight_after(portfolio, "NVDA", 0.3),
        m.high_vol_share(portfolio), m.top3_concentration(portfolio), m.corr_to_portfolio(portfolio, "NVDA"),
        m.cumulative_inflation_ca(), m.annualized_vol("NVDA", currency="CAD"),
    ]
    ids = set()
    for r in results:
        Evidence.model_validate(r.evidence)
        assert r.evidence["computed_by"].startswith("core.metrics.")
        ids.add(r.evidence_id)
    assert len(ids) == len(results)  # distinct computations, distinct ids
    assert m.annualized_vol("NVDA").evidence == results[0].evidence  # deterministic
