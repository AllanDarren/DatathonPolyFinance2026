"""Named metrics v0 (CLAUDE.md section 10). See core/METRICS.md.

Every public function returns a `MetricResult(value, evidence)`. Pure and
deterministic: same data, same output. Returns use `adj_close` in the listing
currency unless `currency="CAD"` is given. Fractions are between 0 and 1
(drawdowns are negative).
"""

from __future__ import annotations

import functools
import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd

from core import data
from core.errors import AlphaForgeError
from core.evidence import MetricResult, format_cad, format_num, format_pct, make_evidence

PRICES_SRC = "data/prices_daily.csv"
HIGH_VOL_THRESHOLD = 0.30  # default; the rules files may override it
TRADING_DAYS = {"crypto": 365}  # every other asset class: 252
DEFAULT_TRADING_DAYS = 252


_MEMO: dict[tuple[Any, ...], Any] = {}
_MEMO_MAX = 4096


def _memo(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Memoize a pure metric on (args, data version): same data, same result, computed once.

    Portfolio arguments are keyed on their (ticker, weight, amount) tuples."""

    def key_of(v: Any) -> Any:
        if isinstance(v, dict) and "positions" in v:
            return tuple((p["ticker"], round(float(p["weight"]), 9), round(float(p["amount"]), 4),
                          p.get("in_universe", True)) for p in v["positions"])
        return v

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = (fn.__name__, data.version(), tuple(key_of(a) for a in args),
               tuple(sorted((k, key_of(v)) for k, v in kwargs.items())))
        if key not in _MEMO:
            if len(_MEMO) >= _MEMO_MAX:
                _MEMO.clear()
            _MEMO[key] = fn(*args, **kwargs)
        return _MEMO[key]

    return wrapper


def _check_ticker(ticker: str) -> None:
    if ticker not in data.load_universe().index:
        raise AlphaForgeError("UNKNOWN_TICKER", f"{ticker} ne fait pas partie des 31 actifs analysés.",
                              details={"ticker": ticker})


def _window(s: pd.Series) -> str:
    return f"{s.index[0]:%Y-%m-%d}/{s.index[-1]:%Y-%m-%d}"


def _series(ticker: str, currency: str) -> pd.Series:
    _check_ticker(ticker)
    return data.price_series(ticker, "adj_close", currency)


def _ccy_label(ticker: str, currency: str) -> str:
    if currency == "CAD":
        return "CAD"
    return str(data.load_universe().loc[ticker, "price_currency"])


def trading_days_per_year(ticker: str) -> int:
    return TRADING_DAYS.get(str(data.load_universe().loc[ticker, "asset_class"]), DEFAULT_TRADING_DAYS)


def _ev(kind: str, statement: str, value: Any, unit: str | None, inputs: dict[str, Any], fn: str,
        source: str = PRICES_SRC) -> dict[str, Any]:
    return make_evidence(kind=kind, statement=statement, value=value, unit=unit, as_of=data.data_as_of(),
                         inputs=inputs, source=source, computed_by=f"core.metrics.{fn}")


# --- single-asset metrics -------------------------------------------------------


@_memo
def annualized_vol(ticker: str, currency: str = "native") -> MetricResult:
    """Std-dev of daily adj_close returns x sqrt(days per year): 252, or 365 for crypto (7/7)."""
    s = _series(ticker, currency)
    r = s.pct_change().dropna()
    days = trading_days_per_year(ticker)
    vol = float(r.std(ddof=1) * math.sqrt(days))
    inputs = {"ticker": ticker, "window": _window(s), "returns": "daily adj_close", "days_per_year": days,
              "currency": _ccy_label(ticker, currency), "n_returns": int(len(r))}
    statement = f"Volatilité annualisée de {ticker}: {format_pct(vol)}."
    if days != DEFAULT_TRADING_DAYS:  # crypto trades 7/7: 365 shown, 252 kept as a sensitivity check
        alt = float(r.std(ddof=1) * math.sqrt(DEFAULT_TRADING_DAYS))
        inputs["sensitivity_252"] = round(alt, 6)
        statement = (f"Volatilité annualisée de {ticker}: {format_pct(vol)} sur {days} jours "
                     f"(cotation 7 jours sur 7; {format_pct(alt)} avec la convention de 252 jours).")
    return MetricResult(vol, _ev("metric", statement, vol, "fraction", inputs, "annualized_vol"))


def _drawdown_path(s: pd.Series) -> tuple[float, pd.Timestamp, pd.Timestamp, pd.Timestamp | None]:
    peak = s.cummax()
    dd = s / peak - 1
    trough = dd.idxmin()
    peak_date = s.loc[:trough].idxmax()
    after = s.loc[trough:]
    recovered = after[after >= s.loc[peak_date]]
    recovery = recovered.index[0] if len(recovered) else None
    return float(dd.min()), peak_date, trough, recovery


@_memo
def max_drawdown(ticker: str, currency: str = "native") -> MetricResult:
    """Worst peak-to-trough fall over the window (negative fraction)."""
    s = _series(ticker, currency)
    mdd, peak, trough, _ = _drawdown_path(s)
    inputs = {"ticker": ticker, "window": _window(s), "peak_date": peak, "trough_date": trough,
              "currency": _ccy_label(ticker, currency)}
    return MetricResult(mdd, _ev("metric", f"Perte maximale de {ticker} sur la période: {format_pct(mdd)} "
                                 f"(sommet {peak:%Y-%m-%d}, creux {trough:%Y-%m-%d}).", mdd, "fraction", inputs,
                                 "max_drawdown"))


def max_drawdown_abs(ticker: str, currency: str = "native") -> MetricResult:
    """|max_drawdown|, convenient to compare with a limit."""
    base = max_drawdown(ticker, currency)
    v = abs(base.value)
    inputs = {**base.evidence["inputs"], "from": base.evidence_id}
    return MetricResult(v, _ev("metric", f"Ampleur de la pire chute de {ticker}: {format_pct(v)}.", v, "fraction",
                               inputs, "max_drawdown_abs"))


@_memo
def recovery_days(ticker: str, currency: str = "native") -> MetricResult:
    """Calendar days from the max-drawdown trough back to the previous peak; None if never recovered."""
    s = _series(ticker, currency)
    _, peak, trough, recovery = _drawdown_path(s)
    days = None if recovery is None else int((recovery - trough).days)
    inputs = {"ticker": ticker, "window": _window(s), "peak_date": peak, "trough_date": trough,
              "recovery_date": recovery, "currency": _ccy_label(ticker, currency)}
    if days is None:
        stmt = f"{ticker} n'a pas retrouvé son sommet du {peak:%Y-%m-%d} à la fin de la période."
    else:
        stmt = f"{ticker} a mis {days} jours après son creux du {trough:%Y-%m-%d} pour retrouver son sommet précédent."
    return MetricResult(days, _ev("metric", stmt, days, "days", inputs, "recovery_days"))


def _year_end_prices(s: pd.Series) -> pd.Series:
    return s.groupby(s.index.year).last()


@_memo
def calendar_year_return(ticker: str, year: int, currency: str = "native") -> MetricResult:
    """Return of a calendar year: last price of `year` / last price of `year - 1` - 1."""
    s = _series(ticker, currency)
    ye = _year_end_prices(s)
    if year not in ye.index or (year - 1) not in ye.index or year >= s.index[-1].year:
        raise AlphaForgeError("INSUFFICIENT_DATA", f"Année {year} incomplète ou absente pour {ticker}.",
                              details={"ticker": ticker, "year": year})
    v = float(ye.loc[year] / ye.loc[year - 1] - 1)
    inputs = {"ticker": ticker, "year": year, "currency": _ccy_label(ticker, currency)}
    return MetricResult(v, _ev("metric", f"Rendement de {ticker} en {year}: {format_pct(v)}.", v, "fraction",
                               inputs, "calendar_year_return"))


def complete_years(ticker: str) -> list[int]:
    """Calendar years fully covered by the window (previous year-end exists, year finished)."""
    s = _series(ticker, "native")
    first, last = s.index[0].year, s.index[-1].year
    return [y for y in range(first + 1, last)]


@_memo
def worst_calendar_year_return(ticker: str, currency: str = "native") -> MetricResult:
    """Worst complete calendar-year return in the window."""
    years = complete_years(ticker)
    results = {y: calendar_year_return(ticker, y, currency).value for y in years}
    worst_year = min(results, key=lambda y: results[y])
    v = results[worst_year]
    inputs = {"ticker": ticker, "years": years, "worst_year": worst_year, "currency": _ccy_label(ticker, currency)}
    return MetricResult(v, _ev("metric", f"Pire année civile de {ticker}: {worst_year} ({format_pct(v)}).", v,
                               "fraction", inputs, "worst_calendar_year_return"))


@_memo
def return_5y(ticker: str, currency: str = "native") -> MetricResult:
    """Total adj_close return over the full window."""
    s = _series(ticker, currency)
    v = float(s.iloc[-1] / s.iloc[0] - 1)
    inputs = {"ticker": ticker, "window": _window(s), "currency": _ccy_label(ticker, currency)}
    return MetricResult(v, _ev("metric", f"Rendement total de {ticker} sur la période: {format_pct(v)}.", v,
                               "fraction", inputs, "return_5y"))


@_memo
def dividend_yield_ttm(ticker: str) -> MetricResult:
    """Dividends with ex-date in the last 365 days / last close (same currency)."""
    _check_ticker(ticker)
    close = data.price_series(ticker, "close")
    end = close.index[-1]
    ca = data.load_corporate_actions()
    divs = ca[(ca.ticker == ticker) & (ca.action == "dividend") & (ca.ex_date > end - pd.Timedelta(days=365))
              & (ca.ex_date <= end)]
    total = float(divs["value"].sum())
    v = total / float(close.iloc[-1])
    inputs = {"ticker": ticker, "from": end - pd.Timedelta(days=365), "to": end, "n_dividends": int(len(divs)),
              "dividends_sum": round(total, 6), "last_close": float(close.iloc[-1])}
    stmt = f"Rendement en dividendes de {ticker} sur 12 mois: {format_pct(v)} ({len(divs)} versement(s))."
    if ticker in ("XIU.TO", "SPY", "QQQ", "ESGV", "XBB.TO", "ZST.TO", "AGG", "TLT", "GLD"):
        stmt += " Les distributions des FNB peuvent être incomplètes."
    return MetricResult(v, _ev("metric", stmt, v, "fraction", inputs, "dividend_yield_ttm",
                               source="data/corporate_actions.csv, data/prices_daily.csv"))


def asset_class(ticker: str) -> MetricResult:
    _check_ticker(ticker)
    v = str(data.load_universe().loc[ticker, "asset_class"])
    return MetricResult(v, _ev("metric", f"Classe d'actif de {ticker}: {v}.", v, None, {"ticker": ticker},
                               "asset_class", source="data/assets_universe.csv"))


def is_high_vol(ticker: str, threshold: float = HIGH_VOL_THRESHOLD) -> MetricResult:
    vol = annualized_vol(ticker)
    flag = vol.value > threshold
    stmt = (f"{ticker} est {'un actif très volatil' if flag else 'sous le seuil de forte volatilité'} "
            f"(volatilité {format_pct(vol.value)}, seuil {format_pct(threshold, 0)}).")
    inputs = {"ticker": ticker, "threshold": threshold, "annualized_vol": vol.value, "from": vol.evidence_id}
    return MetricResult(flag, _ev("metric", stmt, "true" if flag else "false", None, inputs, "is_high_vol"))


# --- portfolio metrics ----------------------------------------------------------


def _positions(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    return [p for p in portfolio.get("positions", []) if p.get("in_universe", True)]


def position_weight(portfolio: dict[str, Any], ticker: str) -> MetricResult:
    """Weight of `ticker` in the analyzed portfolio (0 if not held)."""
    pos = next((p for p in _positions(portfolio) if p["ticker"] == ticker), None)
    v = float(pos["weight"]) if pos else 0.0
    total = float(sum(p["amount"] for p in _positions(portfolio)))
    inputs = {"ticker": ticker, "amount": pos["amount"] if pos else 0.0, "analyzed_total": total}
    return MetricResult(v, _ev("portfolio_calc", f"{ticker} représente {format_pct(v)} du portefeuille analysé.", v,
                               "fraction", inputs, "position_weight", source="portefeuille fourni"))


def position_weight_after(portfolio: dict[str, Any], ticker: str, intended_weight: float) -> MetricResult:
    """Target weight after a hypothetical addition, with the implied CAD amount to add.

    With current amount a, analyzed total T and target w: added = (w*T - a) / (1 - w).
    """
    if not 0 < intended_weight < 1:
        raise AlphaForgeError("INVALID_CONSIDERATION", "Le poids visé doit être strictement entre 0 % et 100 %.",
                              details={"intended_weight": intended_weight})
    _check_ticker(ticker)
    current = position_weight(portfolio, ticker)
    total = current.evidence["inputs"]["analyzed_total"]
    held = current.evidence["inputs"]["amount"]
    added = (intended_weight * total - held) / (1 - intended_weight)
    inputs = {"ticker": ticker, "intended_weight": intended_weight, "current_weight": current.value,
              "current_amount": held, "analyzed_total": total, "implied_added_amount_cad": round(added, 2)}
    stmt = f"Poids de {ticker} après l'ajout envisagé: {format_pct(intended_weight)}"
    stmt += f" (environ {format_cad(added)} ajoutés)." if added > 0 else " (inférieur ou égal au poids actuel)."
    return MetricResult(float(intended_weight), _ev("portfolio_calc", stmt, intended_weight,
                                                    "fraction", inputs, "position_weight_after",
                                                    source="portefeuille fourni"))


def high_vol_share(portfolio: dict[str, Any], threshold: float = HIGH_VOL_THRESHOLD) -> MetricResult:
    """Sum of the weights of very volatile positions."""
    flagged = [p for p in _positions(portfolio) if annualized_vol(p["ticker"]).value > threshold]
    v = float(sum(p["weight"] for p in flagged))
    inputs = {"threshold": threshold, "tickers": [p["ticker"] for p in flagged]}
    return MetricResult(v, _ev("portfolio_calc", f"Part des positions très volatiles (volatilité > "
                               f"{format_pct(threshold, 0)}): {format_pct(v)}.", v, "fraction", inputs,
                               "high_vol_share", source="portefeuille fourni, data/prices_daily.csv"))


def top3_concentration(portfolio: dict[str, Any]) -> MetricResult:
    top = sorted(_positions(portfolio), key=lambda p: -p["weight"])[:3]
    v = float(sum(p["weight"] for p in top))
    inputs = {"tickers": [p["ticker"] for p in top]}
    return MetricResult(v, _ev("portfolio_calc", f"Les trois plus grosses positions pèsent {format_pct(v)} du "
                               "portefeuille.", v, "fraction", inputs, "top3_concentration",
                               source="portefeuille fourni"))


@_memo
def _monthly_returns_cad(ticker: str) -> pd.Series:
    s = data.price_series(ticker, "adj_close", "CAD")
    return s.resample("ME").last().pct_change().dropna()


@_memo
def corr_to_portfolio(portfolio: dict[str, Any], ticker: str) -> MetricResult:
    """Correlation of monthly CAD returns of `ticker` with the rest of the portfolio (weights rescaled)."""
    _check_ticker(ticker)
    rest = [p for p in _positions(portfolio) if p["ticker"] != ticker]
    if not rest:
        raise AlphaForgeError("INSUFFICIENT_DATA", "Il faut au moins une autre position pour calculer une corrélation.")
    w = np.array([p["weight"] for p in rest], dtype=float)
    w = w / w.sum()
    rets = pd.concat([_monthly_returns_cad(p["ticker"]) for p in rest], axis=1).dropna()
    rest_ret = rets.to_numpy() @ w
    rest_s = pd.Series(rest_ret, index=rets.index)
    joined = pd.concat([_monthly_returns_cad(ticker), rest_s], axis=1).dropna()
    v = float(joined.corr().iloc[0, 1])
    inputs = {"ticker": ticker, "rest": [p["ticker"] for p in rest], "frequency": "monthly", "currency": "CAD",
              "n_months": int(len(joined))}
    return MetricResult(v, _ev("metric", f"Corrélation mensuelle de {ticker} avec le reste du portefeuille: "
                               f"{format_num(v)}.", v, "correlation", inputs, "corr_to_portfolio",
                               source="portefeuille fourni, data/prices_daily.csv"))


@_memo
def monthly_correlation(a: str, b: str) -> MetricResult:
    """Correlation of monthly returns (listing currency) between two assets."""
    _check_ticker(a)
    _check_ticker(b)

    def m(t: str) -> pd.Series:
        return data.price_series(t).resample("ME").last().pct_change().dropna()

    joined = pd.concat([m(a), m(b)], axis=1).dropna()
    v = float(joined.corr().iloc[0, 1])
    inputs = {"a": a, "b": b, "frequency": "monthly", "n_months": int(len(joined))}
    return MetricResult(v, _ev("metric", f"Corrélation mensuelle {a}–{b}: {format_num(v)}.", v,
                               "correlation", inputs, "monthly_correlation"))


# --- macro ------------------------------------------------------------------------


def cumulative_inflation_ca(end_year: int = 2026, month: int = 9, years: int = 5) -> MetricResult:
    """Canadian cumulative inflation by compounding the y/y CPI change (STATIC_TOTALCPICHANGE).

    Monthly series dated to the reference month (not the release date). Approximation:
    product of `years` y/y changes for the same month.
    """
    macro = data.load_macro()
    cpi = macro[macro.series_id == "STATIC_TOTALCPICHANGE"].set_index("date")["value"]
    points = []
    for y in range(end_year - years + 1, end_year + 1):
        d = pd.Timestamp(year=y, month=month, day=1)
        if d not in cpi.index:
            raise AlphaForgeError("INSUFFICIENT_DATA", f"Inflation de {d:%Y-%m} absente.", details={"month": f"{d:%Y-%m}"})
        points.append(float(cpi.loc[d]))
    v = float(np.prod([1 + x / 100 for x in points]) - 1)
    start = f"{end_year - years}-{month:02d}"
    inputs = {"series_id": "STATIC_TOTALCPICHANGE", "yoy_pct": points, "from": start, "to": f"{end_year}-{month:02d}"}
    return MetricResult(v, _ev("metric", f"Inflation canadienne cumulée de {start} à {end_year}-{month:02d}: "
                               f"environ {format_pct(v)}.", v, "fraction", inputs, "cumulative_inflation_ca",
                               source="data/macro_rates.csv (Banque du Canada)"))
