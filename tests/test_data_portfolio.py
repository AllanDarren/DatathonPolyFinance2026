"""A1 acceptance: starter data loads and validates; CSV portfolio parsing."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from core import data
from core.errors import AlphaForgeError
from core.portfolio import parse_portfolio
from tests.test_contracts import assert_valid

# --- data --------------------------------------------------------------------


def test_universe_has_31_assets_with_contract_classes() -> None:
    uni = data.load_universe()
    assert len(uni) == data.UNIVERSE_SIZE
    counts = uni["asset_class"].value_counts().to_dict()
    assert counts == {"equity_ca": 10, "equity_us": 10, "equity_etf": 4, "bond_etf": 4, "gold_etf": 1, "crypto": 2}
    assert uni.loc["RY.TO", "price_currency"] == "CAD"
    assert uni.loc["NVDA", "price_currency"] == "USD"


def test_prices_cover_every_asset_without_duplicates() -> None:
    prices = data.load_prices()
    assert set(prices["ticker"]) == set(data.universe_tickers())
    assert not prices.duplicated(["date", "ticker"]).any()
    assert data.data_as_of() == "2026-11-12"
    assert len(data.price_series("BTC-USD")) > len(data.price_series("SPY"))  # crypto trades 7/7


def test_fx_carries_last_rate_forward_on_holidays() -> None:
    fx = data.load_fx()
    # 2021-11-13 is a Saturday: not in the FX file, crypto has a price that day.
    assert pd.Timestamp("2021-11-13") not in fx.index
    assert data.fx_rate_on("2021-11-13") == pytest.approx(fx.loc["2021-11-12"])
    with pytest.raises(AlphaForgeError):
        data.fx_rate_on("2020-01-01")


def test_cad_conversion() -> None:
    usd = data.price_series("SPY")
    cad = data.price_series("SPY", currency="CAD")
    d = usd.index[0]
    assert cad.loc[d] == pytest.approx(usd.loc[d] * data.fx_rate_on(d))
    # CAD-listed assets are unchanged
    assert data.price_series("RY.TO", currency="CAD").equals(data.price_series("RY.TO"))
    # BTC has weekend prices: all converted, none NaN
    assert not data.price_series("BTC-USD", currency="CAD").isna().any()


def test_spy_5y_return_in_cad_matches_reference() -> None:
    # Team reference value: SPY +73.2 % in USD, +96.5 % in CAD (tolerance 0.5 pt) - to revalidate.
    usd = data.price_series("SPY")
    cad = data.price_series("SPY", currency="CAD")
    assert usd.iloc[-1] / usd.iloc[0] - 1 == pytest.approx(0.732, abs=0.005)
    assert cad.iloc[-1] / cad.iloc[0] - 1 == pytest.approx(0.965, abs=0.005)


def test_missing_data_dir_raises_clear_error(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    data.clear_caches()
    try:
        with pytest.raises(AlphaForgeError) as exc:
            data.load_universe()
        assert exc.value.code == "DATA_UNAVAILABLE"
    finally:
        monkeypatch.delenv("DATA_DIR")
        data.clear_caches()


# --- portfolio -----------------------------------------------------------------


def test_valid_csv() -> None:
    p = parse_portfolio("ticker,montant\nSPY,6000\nXBB.TO,3000\nBTC-USD,1000\n")
    assert_valid("Portfolio", p)
    assert p["total_amount"] == 10000
    assert [x["ticker"] for x in p["positions"]] == ["SPY", "XBB.TO", "BTC-USD"]
    assert math.fsum(x["weight"] for x in p["positions"]) == pytest.approx(1.0)
    spy = p["positions"][0]
    assert spy["weight"] == pytest.approx(0.6)
    assert (spy["asset_class"], spy["price_currency"]) == ("equity_etf", "USD")
    assert p["unanalyzed"] == {"tickers": [], "weight": 0.0}
    assert p["warnings"] == []


def test_header_is_optional_and_case_insensitive() -> None:
    p = parse_portfolio("spy,500\n nvda , 500.50\n")
    assert {x["ticker"] for x in p["positions"]} == {"SPY", "NVDA"}
    assert p["total_amount"] == pytest.approx(1000.5)


def test_out_of_universe_goes_to_unanalyzed() -> None:
    p = parse_portfolio("ticker,montant\nSPY,7500\nBRK-B,2500\n")
    assert_valid("Portfolio", p)
    assert p["unanalyzed"]["tickers"] == ["BRK-B"]
    assert p["unanalyzed"]["weight"] == pytest.approx(0.25)
    assert p["positions"][0]["weight"] == pytest.approx(1.0)  # share of the analyzed total
    assert p["total_amount"] == 10000
    assert any("BRK-B" in w for w in p["warnings"])


def test_tsx_suffix_and_duplicates() -> None:
    p = parse_portfolio("ticker,montant\nRY,1000\nRY.TO,1000\nSPY,0\nAGG,2000\n")
    tickers = {x["ticker"]: x for x in p["positions"]}
    assert tickers["RY.TO"]["amount"] == 2000
    assert "SPY" not in tickers
    joined = " ".join(p["warnings"])
    assert "RY.TO" in joined and "plusieurs fois" in joined and "nul" in joined


@pytest.mark.parametrize(
    ("csv_text", "fragment"),
    [
        ("", "vide"),
        ("   \n\n", "vide"),
        ("ticker,montant\n", "aucune position"),
        ("ticker;montant\nSPY;1000\n", "point-virgule"),
        ("ticker,montant\nSPY,1000,50\n", "virgule décimale"),
        ("ticker,montant\nSPY,abc\n", "pas un nombre"),
        ("ticker,montant\nSPY,-100\n", "négatif"),
        ("ticker,montant\nSPY\n", "2 colonnes"),
        ("ticker,montant\n,100\n", "ticker manquant"),
        ("ticker,montant\nSPY,0\n", "nuls"),
    ],
)
def test_malformed_csv_is_refused(csv_text: str, fragment: str) -> None:
    with pytest.raises(AlphaForgeError) as exc:
        parse_portfolio(csv_text)
    assert exc.value.code == "INVALID_CSV"
    assert fragment in exc.value.message
    assert_valid("ErrorResponse", exc.value.to_dict())


def test_only_unknown_tickers() -> None:
    with pytest.raises(AlphaForgeError) as exc:
        parse_portfolio("ticker,montant\nFOO,100\nBAR,200\n")
    assert exc.value.code == "UNKNOWN_TICKER"
    assert exc.value.details == {"tickers": ["FOO", "BAR"]}


def test_amounts_with_dollar_sign_and_spaces() -> None:
    p = parse_portfolio("ticker,montant\nSPY,$1 000\nAGG,1000.00\n")
    assert p["total_amount"] == 2000


def test_persona_sample_portfolios_parse() -> None:
    import services

    for persona in services.get_personas():
        p = parse_portfolio(persona["sample_portfolio_csv"])
        assert p["total_amount"] == 100000
        assert p["unanalyzed"]["tickers"] == []
