"""Load and validate the starter dataset (data/), convert prices to CAD.

Pure reads, cached once per process (Lambda keeps them warm). `DATA_DIR` overrides
the folder. Traps handled here (CLAUDE.md section 6):
- prices are in listing currency (.TO = CAD, rest USD) -> convert with USD/CAD;
- the FX file has no rows on Canadian holidays -> carry the last rate forward
  (backward `asof` lookup, documented in `fx_rate_on`);
- no calendar alignment: each series keeps its own trading days (crypto = 7/7).
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd

from core.errors import DataError

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_SIZE = 31

# starter (asset_class, currency) -> contract asset_class
ASSET_CLASS_MAP: dict[tuple[str, str], str] = {
    ("equity", "CAD"): "equity_ca",
    ("equity", "USD"): "equity_us",
    ("etf_equity", "CAD"): "equity_etf",
    ("etf_equity", "USD"): "equity_etf",
    ("etf_bond", "CAD"): "bond_etf",
    ("etf_bond", "USD"): "bond_etf",
    ("etf_commodity", "USD"): "gold_etf",
    ("crypto", "USD"): "crypto",
}

PRICE_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "currency"]


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", ROOT / "data"))


def _read_csv(name: str, **kwargs: object) -> pd.DataFrame:
    path = data_dir() / name
    if not path.exists():
        raise DataError(f"Fichier de données absent: {name}.", {"path": str(path)})
    return pd.read_csv(path, **kwargs)  # type: ignore[arg-type]


@cache
def _load_starter_universe() -> pd.DataFrame:
    """31 assets indexed by ticker, with the contract `asset_class` and `price_currency`."""
    df = _read_csv("assets_universe.csv")
    if df["ticker"].duplicated().any():
        raise DataError("Tickers en double dans assets_universe.csv.")
    df["starter_asset_class"] = df["asset_class"]
    try:
        df["asset_class"] = [ASSET_CLASS_MAP[(a, c)] for a, c in zip(df["starter_asset_class"], df["currency"], strict=True)]
    except KeyError as exc:
        raise DataError(f"Classe d'actif inconnue: {exc}.") from exc
    df = df.rename(columns={"currency": "price_currency"}).set_index("ticker")
    return df


# --- assets downloaded on demand (ingest/market.py) ---------------------------------
# Registered in memory for the life of the process (a cache, never persisted with user data).
# Every registered asset carries its quality report: core/quality.py gates every number.
_EXTRAS: dict[str, dict[str, Any]] = {}
_VERSION = [0]  # bumped whenever the loaded data changes (memoized metrics are keyed on it)


def version() -> int:
    return _VERSION[0]
_UNIVERSE_WITH_EXTRAS: dict[int, pd.DataFrame] = {}
MAX_EXTRAS = 64


def register_extra_asset(ticker: str, meta: dict[str, Any], prices: pd.DataFrame, quality: dict[str, Any],
                         dividends: pd.DataFrame | None = None) -> None:
    """Add an asset downloaded on demand. `meta`: name, sector, market, asset_class, price_currency,
    source, retrieved_at. `prices`: same columns as prices_daily.csv (one ticker)."""
    if ticker in _load_starter_universe().index:
        raise ValueError(f"{ticker} fait déjà partie du jeu de départ")
    if len(_EXTRAS) >= MAX_EXTRAS and ticker not in _EXTRAS:
        _EXTRAS.pop(next(iter(_EXTRAS)))
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"])
    _EXTRAS[ticker] = {"meta": dict(meta), "prices": df.sort_values("date").reset_index(drop=True), "quality": quality,
                       "actions": dividends if dividends is not None else pd.DataFrame()}
    _UNIVERSE_WITH_EXTRAS.clear()
    _VERSION[0] += 1


def extra_asset(ticker: str) -> dict[str, Any] | None:
    return _EXTRAS.get(ticker)


def starter_tickers() -> list[str]:
    return list(_load_starter_universe().index)


def is_starter(ticker: str) -> bool:
    return ticker in _load_starter_universe().index


def load_universe() -> pd.DataFrame:
    """Starter universe, plus the assets registered on demand (same columns)."""
    base = _load_starter_universe()
    if not _EXTRAS:
        return base
    key = hash(tuple(_EXTRAS))
    if key not in _UNIVERSE_WITH_EXTRAS:
        rows = pd.DataFrame([{"ticker": t, "name": e["meta"].get("name", t), "sector": e["meta"].get("sector", ""),
                              "market": e["meta"].get("market", ""), "asset_class": e["meta"]["asset_class"],
                              "price_currency": e["meta"]["price_currency"], "starter_asset_class": "on_demand"}
                             for t, e in _EXTRAS.items()]).set_index("ticker")
        _UNIVERSE_WITH_EXTRAS.clear()
        _UNIVERSE_WITH_EXTRAS[key] = pd.concat([base, rows[[c for c in rows.columns if c in base.columns]]])
    return _UNIVERSE_WITH_EXTRAS[key]


def universe_tickers() -> list[str]:
    return list(load_universe().index)


@cache
def load_prices() -> pd.DataFrame:
    """Daily prices (long format), validated: columns, types, duplicates, currency."""
    df = _read_csv("prices_daily.csv")
    missing = set(PRICE_COLUMNS) - set(df.columns)
    if missing:
        raise DataError(f"Colonnes manquantes dans prices_daily.csv: {sorted(missing)}.")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    for col in ("open", "high", "low", "close", "adj_close"):
        df[col] = pd.to_numeric(df[col], errors="raise").astype(float)
    if df[["date", "ticker"]].duplicated().any():
        raise DataError("Lignes (date, ticker) en double dans prices_daily.csv.")
    if (df["adj_close"] <= 0).any():
        raise DataError("Prix ajustés nuls ou négatifs dans prices_daily.csv.")
    uni = _load_starter_universe()
    unknown = set(df["ticker"]) - set(uni.index)
    if unknown:
        raise DataError(f"Tickers hors univers dans prices_daily.csv: {sorted(unknown)}.")
    expected = df["ticker"].map(uni["price_currency"])
    if (expected != df["currency"]).any():
        raise DataError("Devise des prix incohérente avec assets_universe.csv.")
    return df.sort_values(["ticker", "date"]).reset_index(drop=True)


def _price_series(ticker: str, field: str) -> pd.Series:
    extra = _EXTRAS.get(ticker)
    if extra is not None:
        s = extra["prices"].set_index("date")[field].astype(float)
        s.name = ticker
        return s
    return _starter_price_series(ticker, field)


@cache
def _starter_price_series(ticker: str, field: str) -> pd.Series:
    df = load_prices()
    s = df.loc[df["ticker"] == ticker].set_index("date")[field]
    if s.empty:
        raise DataError(f"Aucun prix pour {ticker}.", {"ticker": ticker})
    s.name = ticker
    return s


def price_series(ticker: str, field: str = "adj_close", currency: str = "native") -> pd.Series:
    """Price series of one asset on its own trading days.

    `currency="native"` keeps the listing currency; `"CAD"` converts USD prices with the
    USD/CAD rate of the same date (last known rate carried forward).
    """
    s = _price_series(ticker, field).copy()
    if currency == "native":
        return s
    if currency != "CAD":
        raise ValueError("currency must be 'native' or 'CAD'")
    if load_universe().loc[ticker, "price_currency"] == "CAD":
        return s
    return s * fx_rates_on(s.index)


def returns(ticker: str, currency: str = "native") -> pd.Series:
    """Simple daily returns from `adj_close` (dividends and splits included)."""
    return price_series(ticker, "adj_close", currency).pct_change().dropna()


@cache
def load_fx() -> pd.Series:
    """USD->CAD rate by Bank of Canada business day."""
    df = _read_csv("fx_usdcad_daily.csv")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    if df["date"].duplicated().any():
        raise DataError("Dates en double dans fx_usdcad_daily.csv.")
    s = df.set_index("date")["usdcad"].astype(float).sort_index()
    if (s <= 0).any():
        raise DataError("Taux de change invalide dans fx_usdcad_daily.csv.")
    return s


def fx_rates_on(dates: pd.DatetimeIndex) -> pd.Series:
    """USD/CAD for each date, carrying the last published rate forward (holidays, weekends).

    Dates before the first published rate raise a DataError (no backward fill).
    """
    fx = load_fx()
    idx = pd.DatetimeIndex(dates)
    if len(idx) and idx.min() < fx.index[0]:
        raise DataError("Aucun taux de change disponible avant le début de la série.")
    values = fx.reindex(fx.index.union(idx)).ffill().reindex(idx)
    return pd.Series(values.to_numpy(), index=idx, name="usdcad")


def fx_rate_on(date: str | pd.Timestamp) -> float:
    return float(fx_rates_on(pd.DatetimeIndex([pd.Timestamp(date)])).iloc[0])


def load_corporate_actions() -> pd.DataFrame:
    """Dividends and splits of the starter dataset, plus those downloaded with on-demand assets."""
    base = _load_starter_corporate_actions()
    extra = [e["actions"] for e in _EXTRAS.values() if not e["actions"].empty]
    if not extra:
        return base
    return pd.concat([base, *extra], ignore_index=True).sort_values(["ticker", "ex_date"]).reset_index(drop=True)


@cache
def _load_starter_corporate_actions() -> pd.DataFrame:
    df = _read_csv("corporate_actions.csv")
    df["ex_date"] = pd.to_datetime(df["ex_date"], format="%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    return df.sort_values(["ticker", "ex_date"]).reset_index(drop=True)


@cache
def load_macro() -> pd.DataFrame:
    """Macro series in long format. Monthly series are dated to the reference month, not release."""
    df = _read_csv("macro_rates.csv")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["value"]).sort_values(["series_id", "date"]).reset_index(drop=True)


def data_as_of() -> str:
    """Last price date in the dataset (YYYY-MM-DD)."""
    return load_prices()["date"].max().strftime("%Y-%m-%d")


def clear_caches() -> None:
    """For tests that switch DATA_DIR."""
    for fn in (_load_starter_universe, load_prices, _starter_price_series, load_fx, _load_starter_corporate_actions,
               load_macro):
        fn.cache_clear()
    _EXTRAS.clear()
    _UNIVERSE_WITH_EXTRAS.clear()
    _VERSION[0] += 1
    from core import quality  # local import: quality depends on data

    quality.clear_cache()
