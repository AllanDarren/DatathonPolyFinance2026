"""Market data on demand for any listed asset (yfinance), behind the data-quality gate.

Decision (docs/DECISIONS.md, 2026-11-15): the online path may call the network ONLY here,
and only for a ticker outside the 31-asset starter dataset that the investor asks about.
Every download:
1. is mapped to a contract asset class by rules/on_demand_assets.yaml, or refused clearly;
2. covers the same window as the starter dataset (no look-ahead past its last date);
3. goes through core/quality.assess before any number is computed;
4. is registered in core/data (in-memory) with its source and retrieval date, and cached on
   disk (MARKET_CACHE_DIR) so the same request is reproducible and fast.
Nothing about the investor is sent: only the ticker symbol.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

import pandas as pd

from core import data, quality
from core.errors import AlphaForgeError

USER_AGENT = "Mozilla/5.0 (AlphaForge datathon prototype)"
YAHOO_QUOTE_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount={n}&newsCount=0"
TIMEOUT_S = 8
SOURCE = "yfinance (Yahoo Finance), données non certifiées par la bourse"


def _rules() -> Any:
    from core.rules_engine import load_rules

    return load_rules().on_demand


def cache_dir() -> Path:
    d = Path(os.environ.get("MARKET_CACHE_DIR", Path(tempfile.gettempdir()) / "alphaforge_market"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _refuse(code_key: str, ticker: str, extra: str = "") -> AlphaForgeError:
    msg = _rules().unsupported_fr.get(code_key, "Actif non pris en charge.")
    return AlphaForgeError("UNSUPPORTED_ASSET" if code_key != "NOT_FOUND" else "UNKNOWN_TICKER",
                           f"{ticker} : {msg}{extra}", details={"ticker": ticker, "reason": code_key})


def classify(ticker: str, quote_type: str | None, currency: str | None, category: str | None,
             name: str | None) -> str:
    """Contract asset class from Yahoo metadata, by rules (raises UNSUPPORTED_ASSET)."""
    r = _rules()
    qt = (quote_type or "").upper()
    if qt in ("", "NONE"):
        raise _refuse("NOT_FOUND", ticker)
    if qt == "CRYPTOCURRENCY":
        if currency != "USD":
            raise _refuse("CURRENCY_NOT_SUPPORTED", ticker)
        return r.crypto
    if currency not in r.supported_currencies:
        raise _refuse("CURRENCY_NOT_SUPPORTED", ticker, f" (devise : {currency})")
    if qt == "EQUITY":
        return r.equity_by_currency[currency]
    if qt == "ETF":
        text = f" {(category or '').lower()} {(name or '').lower()} "
        if any(m in text for m in r.etf.bond_markers):
            return "bond_etf"
        if any(m in text for m in r.etf.gold_markers):
            return "gold_etf"
        if "commodit" in text and not r.etf.other_commodity_supported:
            raise _refuse("COMMODITY_ETF", ticker)
        return r.etf.default
    raise _refuse(qt if qt in r.unsupported_fr else "NOT_FOUND", ticker)


def _download(ticker: str, start: str, end: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """yfinance call (isolated so tests can replace it). Returns (prices, info)."""
    import yfinance as yf

    yf.set_tz_cache_location(str(cache_dir()))  # Lambda: only /tmp is writable
    tk = yf.Ticker(ticker)
    hist = tk.history(start=start, end=end, auto_adjust=False, actions=True, timeout=TIMEOUT_S)
    md = tk.history_metadata or {}
    try:
        info = tk.info or {}
    except Exception:  # noqa: BLE001 - info is optional (name, sector, category)
        info = {}
    meta = {"quote_type": info.get("quoteType") or md.get("instrumentType"),
            "currency": md.get("currency") or info.get("currency"),
            "name": info.get("longName") or info.get("shortName") or md.get("longName") or ticker,
            "sector": info.get("sector") or "", "category": info.get("category") or "",
            "market": md.get("exchangeName") or info.get("exchange") or ""}
    if hist.empty:
        return pd.DataFrame(), meta
    idx = pd.DatetimeIndex(hist.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df = pd.DataFrame({
        "date": idx.normalize(), "open": hist["Open"].to_numpy(), "high": hist["High"].to_numpy(),
        "low": hist["Low"].to_numpy(), "close": hist["Close"].to_numpy(), "adj_close": hist["Adj Close"].to_numpy(),
        "volume": hist["Volume"].to_numpy(),
        "dividend": hist["Dividends"].to_numpy() if "Dividends" in hist else 0.0,
        "split": hist["Stock Splits"].to_numpy() if "Stock Splits" in hist else 0.0,
    })
    return df.drop_duplicates("date", keep="last"), meta


def _cache_paths(ticker: str, day: str) -> tuple[Path, Path]:
    safe = ticker.replace("/", "_").replace("^", "_")
    return cache_dir() / f"{safe}_{day}.csv", cache_dir() / f"{safe}_{day}.json"


def ensure_asset(ticker: str) -> dict[str, Any]:
    """Make `ticker` usable by core/ (starter asset or on-demand download). Returns its quality report.

    Raises UNKNOWN_TICKER / UNSUPPORTED_ASSET / MARKET_DATA_UNAVAILABLE with a clear message.
    """
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 15 or any(c.isspace() for c in ticker):
        raise AlphaForgeError("UNKNOWN_TICKER", "Symbole de titre invalide.", details={"ticker": ticker})
    if data.is_starter(ticker):
        return quality.asset_quality(ticker)
    if data.extra_asset(ticker) is not None:
        return quality.asset_quality(ticker)

    start = _rules().history_start
    end = (pd.Timestamp(data.data_as_of()) + timedelta(days=1)).strftime("%Y-%m-%d")  # same window as the dataset
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    csv_path, meta_path = _cache_paths(ticker, day)
    if csv_path.exists() and meta_path.exists():
        df = pd.read_csv(csv_path, parse_dates=["date"])
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        t0 = time.perf_counter()
        try:
            df, meta = _download(ticker, start, end)
        except AlphaForgeError:
            raise
        except Exception as exc:  # noqa: BLE001 - network or provider failure
            raise AlphaForgeError("MARKET_DATA_UNAVAILABLE",
                                  f"Impossible de récupérer les données de {ticker} pour l'instant ({type(exc).__name__}).",
                                  status=503, details={"ticker": ticker}) from exc
        meta["retrieved_at"] = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        meta["download_ms"] = int((time.perf_counter() - t0) * 1000)
        if not df.empty:
            df.to_csv(csv_path, index=False)
            meta_path.write_text(json.dumps(meta), encoding="utf-8")
    if df.empty:
        raise _refuse("NOT_FOUND", ticker)
    asset_class = classify(ticker, meta.get("quote_type"), meta.get("currency"), meta.get("category"), meta.get("name"))
    df = df[df["date"] <= pd.Timestamp(data.data_as_of())]
    source = f"{SOURCE}, téléchargé le {str(meta.get('retrieved_at', day))[:10]}"
    splits = df.loc[df["split"].fillna(0) > 0, ["date", "split"]].rename(columns={"date": "ex_date", "split": "value"})
    dividends = df.loc[df["dividend"].fillna(0) > 0, ["date", "dividend"]].rename(
        columns={"date": "ex_date", "dividend": "value"})
    q = quality.assess(ticker, df, asset_class=asset_class, price_currency=meta["currency"], splits=splits,
                       dividends=dividends, origin="on_demand", source=source, retrieved_at=meta.get("retrieved_at"))
    data.register_extra_asset(
        ticker,
        {"name": meta.get("name", ticker), "sector": meta.get("sector", ""), "market": meta.get("market", ""),
         "asset_class": asset_class, "price_currency": meta["currency"], "source": source,
         "retrieved_at": meta.get("retrieved_at"), "category": meta.get("category", "")},
        df.assign(ticker=ticker, currency=meta["currency"]),
        q,
        dividends=dividends.assign(ticker=ticker, action="dividend", unit=f"{meta['currency']} per share"),
    )
    return q


def search_assets(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Yahoo quote search -> AssetSearchResult list (starter assets first, flagged)."""
    q = query.strip()
    if not q:
        return []
    uni = data.load_universe()
    starter = [{"ticker": t, "name": str(uni.loc[t, "name"]), "exchange": str(uni.loc[t].get("market", "")),
                "quote_type": "STARTER", "supported": True, "in_starter_dataset": True}
               for t in data.starter_tickers()
               if q.upper() in t or q.lower() in str(uni.loc[t, "name"]).lower()]
    try:
        req = Request(YAHOO_QUOTE_SEARCH.format(q=quote(q), n=limit), headers={"User-Agent": USER_AGENT})
        payload = json.loads(urlopen(req, timeout=TIMEOUT_S).read())  # noqa: S310 - fixed https host
    except Exception:  # noqa: BLE001 - search is a convenience: degrade to the starter list
        payload = {"quotes": []}
    r = _rules()
    found = []
    for item in payload.get("quotes", []):
        t = str(item.get("symbol", "")).upper()
        if not t or data.is_starter(t):
            continue
        qt = str(item.get("quoteType", "")).upper()
        found.append({"ticker": t, "name": item.get("longname") or item.get("shortname") or t,
                      "exchange": item.get("exchDisp") or item.get("exchange") or "", "quote_type": qt,
                      "supported": qt in ("EQUITY", "ETF", "CRYPTOCURRENCY") and qt not in r.unsupported_fr,
                      "in_starter_dataset": False})
    return (starter + found)[: max(limit, len(starter))]
