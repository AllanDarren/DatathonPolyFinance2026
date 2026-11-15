"""Historical context of structured events (A6). Never a forecast.

For an event type and an asset: return from the close of the trading day *before*
the event to the close 5 trading days after the first trading day on or after the
event (window t-1 -> t+5, in the asset's own trading days; crypto trades 7/7).
This covers both pre-market and after-close announcements.

Refuses to produce a result under MIN_EVENTS events ("données insuffisantes").
Mandatory caveats are always attached.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core import data, snapshots
from core.errors import AlphaForgeError
from core.evidence import MetricResult, format_pct, make_evidence

MIN_EVENTS = 8
HORIZON_DAYS = 5
WINDOW_LABEL = "veille de l'événement à +5 jours de bourse"
EVENT_LABELS_FR = {
    "earnings": "publications de résultats",
    "dividend_ex_date": "dates ex-dividende",
    "rate_decision": "décisions de taux",
    "cpi_release": "publications d'inflation",
    "other": "événements",
}
MACRO_TYPES = {"rate_decision", "cpi_release"}


def event_dates(event_type: str, asset: str, macro_source: str | None = None) -> list[pd.Timestamp]:
    """Past event dates from the latest events snapshot.

    Ticker events are filtered on `asset`; macro events (rate decisions) can be
    narrowed with `macro_source` (e.g. 'federalreserve' or 'bankofcanada').
    """
    out = []
    for e in snapshots.records("events", required=False):
        if e["type"] != event_type:
            continue
        if event_type in MACRO_TYPES:
            if e["scope"] != "macro" or (macro_source and macro_source not in e["source"]):
                continue
        elif asset not in e["tickers"]:
            continue
        out.append(pd.Timestamp(e["date"]))
    return sorted(set(out))


def window_returns(prices: pd.Series, dates: list[pd.Timestamp], horizon: int = HORIZON_DAYS) -> list[dict[str, Any]]:
    """t-1 -> t+horizon returns for each event date that has a full window in `prices`."""
    s = prices.dropna().sort_index()
    idx = s.index
    out = []
    for d in dates:
        pos = int(idx.searchsorted(d))  # first trading day >= d
        if pos < 1 or pos + horizon >= len(idx):
            continue
        before, after = float(s.iloc[pos - 1]), float(s.iloc[pos + horizon])
        out.append({"date": d.strftime("%Y-%m-%d"), "return": after / before - 1,
                    "start": idx[pos - 1].strftime("%Y-%m-%d"), "end": idx[pos + horizon].strftime("%Y-%m-%d")})
    return out


def _overlaps(windows: list[dict[str, Any]]) -> int:
    ordered = sorted(windows, key=lambda w: w["start"])
    return sum(1 for a, b in zip(ordered, ordered[1:], strict=False) if b["start"] <= a["end"])


def historical_context(event_type: str, asset: str, *, dates: list[pd.Timestamp] | None = None,
                       prices: pd.Series | None = None, macro_source: str | None = None,
                       source: str | None = None) -> tuple[dict[str, Any], MetricResult]:
    """Return (HistoricalContext dict, MetricResult with the event_study evidence)."""
    if event_type not in EVENT_LABELS_FR:
        raise AlphaForgeError("INVALID_EVENT_TYPE", f"Type d'événement inconnu: {event_type}.")
    if prices is None:
        if asset not in data.load_universe().index:
            raise AlphaForgeError("UNKNOWN_TICKER", f"{asset} ne fait pas partie des 31 actifs analysés.")
        prices = data.price_series(asset)
    if dates is None:
        dates = event_dates(event_type, asset, macro_source)
    windows = window_returns(prices, dates)
    label = EVENT_LABELS_FR[event_type]
    if len(windows) < MIN_EVENTS:
        raise AlphaForgeError("INSUFFICIENT_DATA",
                              f"Données insuffisantes: {len(windows)} {label} pour {asset} (minimum {MIN_EVENTS}).",
                              details={"n_events": len(windows), "min_events": MIN_EVENTS})
    rets = np.array([w["return"] for w in windows])
    median, p10, p90 = (float(np.percentile(rets, q)) for q in (50, 10, 90))
    share_pos = float((rets > 0).mean())
    overlaps = _overlaps(windows)
    caveats = [
        f"Échantillon limité: {len(windows)} {label} sur une seule période de 5 ans.",
        "Les fenêtres peuvent chevaucher d'autres nouvelles ou événements; "
        + (f"{overlaps} fenêtre(s) se chevauchent entre elles." if overlaps else "aucune ne se chevauche entre elles."),
        "Biais du survivant: actif choisi en 2026 parmi des titres qui ont réussi.",
        "Ce n'est pas une prévision: dans des situations comparables, on a observé ces mouvements.",
    ]
    if event_type == "dividend_ex_date":
        caveats.append("Prix ajustés des dividendes: la baisse mécanique du jour ex-dividende est neutralisée.")
    first, last = windows[0]["date"], windows[-1]["date"]
    inputs = {"event_type": event_type, "asset": asset, "window": "t-1 -> t+5 trading days", "n_events": len(windows),
              "from": first, "to": last, "macro_source": macro_source, "prices": "adj_close (listing currency)"}
    statement = (f"Sur {len(windows)} {label} ({first} au {last}), le mouvement médian de {asset} de la veille à "
                 f"+5 jours de bourse a été de {format_pct(median, 2)} (p10 {format_pct(p10, 1)}, p90 "
                 f"{format_pct(p90, 1)}, {format_pct(share_pos, 0)} de cas positifs).")
    ev = make_evidence(kind="event_study", statement=statement, value=median, unit="fraction",
                       as_of=data.data_as_of(), inputs=inputs,
                       source=source or "data/prices_daily.csv, data/snapshots/events_*.json",
                       computed_by="core.event_study.historical_context")
    ctx = {
        "event_type": event_type, "asset": asset, "window": WINDOW_LABEL, "n_events": len(windows),
        "median_return": round(median, 6), "p10": round(p10, 6), "p90": round(p90, 6),
        "share_positive": round(share_pos, 4),
        "events": [{"date": w["date"], "return": round(w["return"], 6)} for w in windows],
        "caveats": caveats, "evidence_id": ev["id"],
    }
    return ctx, MetricResult(median, ev)
