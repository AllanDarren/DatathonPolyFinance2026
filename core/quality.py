"""Data-quality gate (pure functions, no network).

Every price series used for a number goes through `asset_quality` first: the starter
dataset and assets downloaded on demand alike. Status:
- ok: nothing to report;
- warning: usable, the warnings are shown next to the numbers;
- blocking: no verdict is computed on this data (INSUFFICIENT_DATA).
Thresholds: rules/data_quality.yaml. There is no official exchange calendar in the
project: expected trading days come from a reference series (SPY for USD listings,
XIU.TO for CAD listings); crypto is expected every calendar day. This is documented
in every report.
"""

from __future__ import annotations

from functools import cache
from typing import Any

import pandas as pd

from core import data
from core.evidence import format_pct, make_evidence

SOURCE_STARTER = "data/prices_daily.csv"


def _thresholds() -> Any:
    from core.rules_engine import load_rules

    return load_rules().data_quality


def _reference_days(price_currency: str, asset_class: str, start: pd.Timestamp, end: pd.Timestamp,
                    ref_ticker: str | None) -> pd.DatetimeIndex:
    if asset_class == "crypto":
        return pd.date_range(start, end, freq="D")
    if ref_ticker and ref_ticker in data.starter_tickers():
        idx = data.price_series(ref_ticker, "close").index
        return idx[(idx >= start) & (idx <= end)]
    return pd.bdate_range(start, end)


@cache
def _market_moves_cached(ref_ticker: str) -> dict[str, float]:
    r = data.price_series(ref_ticker, "adj_close").pct_change().dropna()
    return {f"{d:%Y-%m-%d}": float(v) for d, v in r[r.abs() >= 0.05].items()}


def _market_moves(ref_ticker: str | None, asset_class: str) -> dict[str, float]:
    """Days when the reference market series moved by 5 % or more (crypto: none)."""
    if asset_class == "crypto" or not ref_ticker or ref_ticker not in data.starter_tickers():
        return {}
    return _market_moves_cached(ref_ticker)


def _runs(values: pd.Series, min_len: int) -> list[dict[str, Any]]:
    """Runs of identical consecutive closes of length >= min_len."""
    out: list[dict[str, Any]] = []
    if values.empty:
        return out
    same = values.eq(values.shift())
    run_start, length = values.index[0], 1
    for date, eq in zip(values.index[1:], same.iloc[1:], strict=True):
        if eq:
            length += 1
        else:
            if length >= min_len:
                out.append({"start": f"{run_start:%Y-%m-%d}", "days": int(length)})
            run_start, length = date, 1
    if length >= min_len:
        out.append({"start": f"{run_start:%Y-%m-%d}", "days": int(length)})
    return out


def _explain_odd_split(df: pd.DataFrame, date: pd.Timestamp, factor: float, dividends: pd.DataFrame | None) -> str | None:
    """If a dividend paid the same day explains the factor (P / (P - D) = factor) and adj_close counts it
    exactly once, return an explanation; otherwise None."""
    if dividends is None or dividends.empty or date not in df.index:
        return None
    pos = df.index.get_loc(date)
    if pos == 0:
        return None
    prev_close, close = float(df["close"].iloc[pos - 1]), float(df["close"].iloc[pos])
    for d in dividends.loc[dividends["ex_date"] == date, "value"].astype(float):
        if prev_close <= d or abs(prev_close / (prev_close - d) - factor) > 0.002:
            continue
        total = (close + d) / prev_close - 1
        adj = float(df["adj_close"].iloc[pos] / df["adj_close"].iloc[pos - 1] - 1)
        if abs(total - adj) < 0.002:
            return (f"le facteur {factor:g} du {date:%Y-%m-%d} correspond au dividende de {d:g} versé le même jour "
                    f"({prev_close:.2f} / ({prev_close:.2f} − {d:g})) : probablement une distribution spéciale enregistrée "
                    f"comme fractionnement. Vérifié : adj_close la compte une seule fois, les rendements ne sont pas faussés.")
    return None


def assess(ticker: str, prices: pd.DataFrame, *, asset_class: str, price_currency: str,
           splits: pd.DataFrame | None = None, dividends: pd.DataFrame | None = None,
           as_of: str | None = None, origin: str = "starter_dataset",
           source: str = SOURCE_STARTER, retrieved_at: str | None = None) -> dict[str, Any]:
    """QualityReport contract dict for one asset. `prices`: rows of one ticker with
    date, open, high, low, close, adj_close, volume (any order)."""
    th = _thresholds()
    df = prices.sort_values("date").set_index("date")
    warnings: list[str] = []
    blocking: list[str] = []
    notes: list[str] = []  # informative, does not change the status
    n = int(len(df))
    if n < 2:
        report = {"ticker": ticker, "status": "blocking", "origin": origin, "source": source,
                  "retrieved_at": retrieved_at, "first_date": None, "last_date": None, "n_obs": n,
                  "years": 0.0, "missing_days": 0, "missing_share": 0.0, "stale_runs": [], "outliers": [],
                  "ohlc_issues": 0, "zero_volume_days": 0, "fx_filled_days": 0, "odd_splits": [],
                  "warnings_fr": ["Moins de deux cotations : aucune analyse possible."], "notes_fr": [],
                  "reference_calendar": None}
        return _with_evidence(report, as_of)
    first, last = df.index[0], df.index[-1]
    years = (last - first).days / 365.25
    if years < th.min_years:
        blocking.append(f"Seulement {years:.1f} an(s) d'historique (minimum {th.min_years:g}).")

    ref_ticker = th.reference_calendars.get(price_currency)
    expected = _reference_days(price_currency, asset_class, first, last, ref_ticker)
    missing = expected.difference(df.index)
    missing_share = float(len(missing) / len(expected)) if len(expected) else 0.0
    if missing_share > th.max_missing_share:
        blocking.append(f"{format_pct(missing_share)} des jours de cotation attendus sont absents.")
    elif missing_share > th.warn_missing_share:
        warnings.append(f"{len(missing)} jour(s) de cotation attendus absents ({format_pct(missing_share)}).")

    stale = _runs(df["close"], th.stale_run_days)
    if any(r["days"] >= th.blocking_stale_run_days for r in stale):
        blocking.append(f"Prix figé pendant {max(r['days'] for r in stale)} jours d'affilée.")
    elif stale:
        warnings.append(f"{len(stale)} période(s) de prix inchangé (≥ {th.stale_run_days} jours).")

    r = df["adj_close"].pct_change().dropna()
    sigma = float(r.std(ddof=1)) if len(r) > 2 else 0.0
    mask = (r.abs() > th.outlier_abs_return) | ((r.abs() > th.outlier_sigma * sigma) if sigma > 0 else False)
    outliers = [{"date": f"{d:%Y-%m-%d}", "return": round(float(v), 6)} for d, v in r[mask].items()]
    # A move shared by the market the same day (reference series moved >= 5 % the same way) is
    # a market event, not a data error: it becomes a note.
    market = _market_moves(ref_ticker, asset_class)
    isolated = [o for o in outliers if not (o["date"] in market and market[o["date"]] * o["return"] > 0)]
    shared = [o for o in outliers if o not in isolated]
    if isolated:
        warnings.append(f"{len(isolated)} mouvement(s) quotidien(s) inhabituel(s) propre(s) à ce titre, à vérifier "
                        f"(ex. {isolated[0]['date']} : {format_pct(isolated[0]['return'])}).")
    if shared:
        notes.append(f"{len(shared)} forte(s) variation(s) partagée(s) par tout le marché le même jour "
                     f"(ex. {shared[0]['date']}) : événement de marché, pas une erreur de données.")

    ohlc = df[["open", "high", "low", "close"]].astype(float)
    bad = ((ohlc["low"] > ohlc[["open", "close"]].min(axis=1) + 1e-9)
           | (ohlc["high"] < ohlc[["open", "close"]].max(axis=1) - 1e-9))
    ohlc_issues = int(bad.sum())
    if ohlc_issues:
        warnings.append(f"{ohlc_issues} jour(s) où le haut/bas ne contient pas l'ouverture ou la clôture.")
    zero_volume = int((df["volume"].fillna(0) <= 0).sum()) if "volume" in df and asset_class != "crypto" else 0
    if zero_volume:
        warnings.append(f"{zero_volume} jour(s) sans volume échangé.")

    fx_filled = 0
    if price_currency == "USD":
        fx = data.load_fx()
        idx = df.index[(df.index >= fx.index[0])]
        fx_filled = int((~idx.isin(fx.index)).sum())
        if fx_filled:
            notes.append(f"{fx_filled} jour(s) convertis en CAD avec le dernier taux USD/CAD publié "
                         "(jours fériés canadiens, fins de semaine).")

    odd: list[dict[str, Any]] = []
    if splits is not None and not splits.empty:
        for _, s in splits.iterrows():
            f = float(s["value"])
            if abs(f - round(f)) > 1e-6 and abs(1 / f - round(1 / f)) > 1e-6:
                when = pd.Timestamp(s["ex_date"])
                why = _explain_odd_split(df, when, f, dividends)
                odd.append({"date": f"{when:%Y-%m-%d}", "factor": f, "explained": why is not None})
                if why:
                    notes.append("Fractionnement non entier expliqué : " + why)
                else:
                    warnings.append(f"Fractionnement non entier à vérifier : {f:g} le {when:%Y-%m-%d} "
                                    "(aucun dividende du même jour ne l'explique).")

    ref_date = pd.Timestamp(as_of or data.data_as_of())
    lag = (ref_date - last).days
    if lag > th.max_stale_last_days:
        warnings.append(f"Dernière cotation il y a {lag} jours ({last:%Y-%m-%d}).")

    status = "blocking" if blocking else "warning" if warnings else "ok"
    calendar = ("tous les jours (cryptoactif)" if asset_class == "crypto"
                else f"jours de cotation de {ref_ticker} (pas de calendrier officiel)" if ref_ticker
                else "jours ouvrables (approximation)")
    report = {
        "ticker": ticker, "status": status, "origin": origin, "source": source, "retrieved_at": retrieved_at,
        "first_date": f"{first:%Y-%m-%d}", "last_date": f"{last:%Y-%m-%d}", "n_obs": n,
        "years": round(years, 2), "missing_days": int(len(missing)), "missing_share": round(missing_share, 6),
        "stale_runs": stale, "outliers": outliers[:10], "ohlc_issues": ohlc_issues,
        "zero_volume_days": zero_volume, "fx_filled_days": fx_filled, "odd_splits": odd,
        "warnings_fr": blocking + warnings, "notes_fr": notes, "reference_calendar": calendar,
    }
    return _with_evidence(report, as_of)


def _with_evidence(report: dict[str, Any], as_of: str | None) -> dict[str, Any]:
    labels = {"ok": "aucune anomalie détectée", "warning": "utilisables, avec avertissements",
              "blocking": "insuffisantes pour un verdict"}
    statement = f"Qualité des données de {report['ticker']} : {labels[report['status']]}"
    if report["n_obs"]:
        statement += f" ({report['n_obs']} cotations, {report['first_date']} à {report['last_date']})"
    ev = make_evidence(kind="metric", statement=statement + ".", value=report["status"], unit=None,
                       as_of=as_of or data.data_as_of(),
                       inputs={k: report[k] for k in ("ticker", "origin", "n_obs", "missing_days", "fx_filled_days",
                                                       "reference_calendar")} | {"warnings": report["warnings_fr"]},
                       source=report["source"], computed_by="core.quality.asset_quality")
    report["evidence"] = ev
    return report


@cache
def _starter_quality(ticker: str) -> dict[str, Any]:
    uni = data.load_universe()
    prices = data.load_prices()
    rows = prices[prices["ticker"] == ticker]
    ca = data.load_corporate_actions()
    splits = ca[(ca["ticker"] == ticker) & (ca["action"] == "split")]
    dividends = ca[(ca["ticker"] == ticker) & (ca["action"] == "dividend")]
    return assess(ticker, rows, asset_class=str(uni.loc[ticker, "asset_class"]),
                  price_currency=str(uni.loc[ticker, "price_currency"]), splits=splits, dividends=dividends)


def asset_quality(ticker: str) -> dict[str, Any]:
    """Quality report of any loaded asset (starter dataset or downloaded on demand)."""
    extra = data.extra_asset(ticker)
    if extra is not None:
        return extra["quality"]
    return _starter_quality(ticker)


def public(report: dict[str, Any]) -> dict[str, Any]:
    """Contract view (QualityReport) with the evidence id instead of the evidence object."""
    out = {k: v for k, v in report.items() if k != "evidence"}
    out["evidence_id"] = report["evidence"]["id"]
    return out


def clear_cache() -> None:
    _starter_quality.cache_clear()
    _market_moves_cached.cache_clear()


__all__ = ["assess", "asset_quality", "public", "clear_cache"]
