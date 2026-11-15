"""Fetch structured events -> Event list (past and upcoming).

- earnings: Yahoo Finance earnings dates via yfinance (past and next, stocks only);
- dividend_ex_date: past ex-dates from data/corporate_actions.csv, next from yfinance;
- rate_decision: Bank of Canada (key interest rate page: past decisions incl. holds,
  and the yearly schedule) and Federal Reserve (FOMC calendar: decision = last day).
- cpi_release: not collected (BLS blocks automated access; no reliable public
  calendar found) - documented as a limit.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from core.data import load_corporate_actions, load_universe
from ingest.common import http_get, now_iso, stable_id, strip_html

BOC_URL = "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
WINDOW_START = date(2021, 11, 1)
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                       "September", "October", "November", "December"], start=1)}
SHORT_MONTHS = {m[:3]: i for m, i in MONTHS.items()}

Fetcher = Callable[[str], bytes]


def _event(*, type_: str, scope: str, tickers: list[str], day: date, title: str, is_estimated: bool, source: str,
           retrieved_at: str) -> dict[str, Any]:
    return {
        "id": stable_id("evt_", type_, ",".join(sorted(tickers)) or scope, day.isoformat(), title if scope == "macro" else ""),
        "type": type_, "scope": scope, "tickers": sorted(tickers), "date": day.isoformat(), "title": title,
        "is_estimated": is_estimated, "source": source, "retrieved_at": retrieved_at,
    }


# --- central banks --------------------------------------------------------------------


def parse_boc(html: str, retrieved_at: str, today: date) -> list[dict[str, Any]]:
    """Past decisions (`<th data-date>` rows, with target and change) + yearly schedule tables."""
    out: list[dict[str, Any]] = []
    seen: set[date] = set()
    for m in re.finditer(r'<th data-date="(\d{4}-\d{2}-\d{2})">[^<]*</th>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>', html):
        d = date.fromisoformat(m.group(1))
        target, change = strip_html(m.group(2)), strip_html(m.group(3))
        what = "maintien" if change in ("---", "0", "0.00", "") else f"variation de {change} pt"
        out.append(_event(type_="rate_decision", scope="macro", tickers=[], day=d,
                          title=f"Banque du Canada: décision de taux ({what}, taux cible {target} %)",
                          is_estimated=False, source=BOC_URL, retrieved_at=retrieved_at))
        seen.add(d)
    for cap in re.finditer(r"<caption>\s*Schedule for (\d{4})\s*</caption>(.*?)</table>", html, re.S):
        year = int(cap.group(1))
        for row in re.findall(r"<tr>(.*?)</tr>", cap.group(2), re.S):
            cells = [strip_html(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
            if len(cells) < 2 or "interest rate announcement" not in cells[1].lower():
                continue
            mm = re.match(r"([A-Z][a-z]+)\s+(\d{1,2})", cells[0].replace("\xa0", " "))
            if not mm or mm.group(1) not in MONTHS:
                continue
            d = date(year, MONTHS[mm.group(1)], int(mm.group(2)))
            if d in seen or d <= today:
                continue
            out.append(_event(type_="rate_decision", scope="macro", tickers=[], day=d,
                              title="Banque du Canada: annonce de taux prévue", is_estimated=False, source=BOC_URL,
                              retrieved_at=retrieved_at))
            seen.add(d)
    return [e for e in out if date.fromisoformat(e["date"]) >= WINDOW_START]


def _fomc_last_day(year: int, month_label: str, days_label: str) -> date | None:
    days_label = days_label.replace("*", "").strip()
    if "notation vote" in days_label or not re.match(r"^\d{1,2}(-\d{1,2})?$", days_label):
        return None
    parts = [int(x) for x in days_label.split("-")]
    last_day = parts[-1]
    if "/" in month_label:  # e.g. "Apr/May 30-1": the day number wraps, decision in the second month
        first, second = month_label.split("/")
        month = SHORT_MONTHS.get((second if last_day < parts[0] else first)[:3])
    else:
        month = MONTHS.get(month_label)
    return date(year, month, last_day) if month else None


def parse_fomc(html: str, retrieved_at: str, today: date) -> list[dict[str, Any]]:
    """FOMC meetings by year; the decision is announced on the last day of the meeting."""
    out: list[dict[str, Any]] = []
    heads = list(re.finditer(r'<h4><a id="\d+">(\d{4}) FOMC Meetings', html))
    for i, h in enumerate(heads):
        year = int(h.group(1))
        seg = html[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(html)]
        pairs = re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<',
                           seg, re.S)
        for month_label, days_label in pairs:
            d = _fomc_last_day(year, month_label.strip(), days_label)
            if d is None or d < WINDOW_START:
                continue
            out.append(_event(type_="rate_decision", scope="macro", tickers=[], day=d,
                              title="Réserve fédérale (FOMC): décision de taux", is_estimated=False, source=FOMC_URL,
                              retrieved_at=retrieved_at))
    return sorted({e["id"]: e for e in out}.values(), key=lambda e: e["date"])


# --- tickers ------------------------------------------------------------------------


def dividends_from_starter(retrieved_at: str) -> list[dict[str, Any]]:
    ca = load_corporate_actions()
    out = []
    for row in ca[ca.action == "dividend"].itertuples():
        out.append(_event(type_="dividend_ex_date", scope="ticker", tickers=[row.ticker], day=row.ex_date.date(),
                          title=f"{row.ticker}: date ex-dividende ({row.value} {row.unit})", is_estimated=False,
                          source="data/corporate_actions.csv (Yahoo Finance, jeu de départ)",
                          retrieved_at=retrieved_at))
    return out


def fetch_ticker_events(tickers: list[str], retrieved_at: str, today: date) -> tuple[list[dict[str, Any]], list[str]]:
    """Earnings dates (past + next) and next ex-dividend date from yfinance."""
    import yfinance as yf  # offline ingestion only

    out: list[dict[str, Any]] = []
    errors: list[str] = []
    uni = load_universe()
    for t in tickers:
        if uni.loc[t, "asset_class"] not in ("equity_ca", "equity_us"):
            continue
        tk = yf.Ticker(t)
        try:
            ed = tk.get_earnings_dates(limit=28)
            for ts in (ed.index if ed is not None else []):
                d = ts.date()
                if d < WINDOW_START:
                    continue
                future = d > today
                out.append(_event(type_="earnings", scope="ticker", tickers=[t], day=d,
                                  title=f"{t}: publication des résultats" + (" (date prévue)" if future else ""),
                                  is_estimated=future, source="Yahoo Finance (yfinance)",
                                  retrieved_at=retrieved_at))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"earnings {t}: {exc}")
        try:
            cal = tk.calendar or {}
            ex = cal.get("Ex-Dividend Date")
            if isinstance(ex, date) and ex > today:
                out.append(_event(type_="dividend_ex_date", scope="ticker", tickers=[t], day=ex,
                                  title=f"{t}: prochaine date ex-dividende", is_estimated=True,
                                  source="Yahoo Finance (yfinance)", retrieved_at=retrieved_at))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"calendar {t}: {exc}")
    return out, errors


def fetch_events(tickers: list[str] | None = None, *, fetch: Fetcher = http_get,
                 with_tickers: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    retrieved_at = now_iso()
    today = datetime.now().date()
    tickers = tickers or list(load_universe().index)
    events: list[dict[str, Any]] = []
    report: dict[str, Any] = {"retrieved_at": retrieved_at, "errors": []}
    for label, url, parser in (("boc", BOC_URL, parse_boc), ("fomc", FOMC_URL, parse_fomc)):
        try:
            events += parser(fetch(url).decode("utf-8", errors="ignore"), retrieved_at, today)
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"{label}: {exc}")
    events += [e for e in dividends_from_starter(retrieved_at) if e["tickers"][0] in tickers]
    if with_tickers:
        got, errs = fetch_ticker_events(tickers, retrieved_at, today)
        events += got
        report["errors"] += errs
    events = sorted({e["id"]: e for e in events}.values(), key=lambda e: (e["date"], e["id"]))
    counts: dict[str, dict[str, int]] = {}
    for e in events:
        key = ",".join(e["tickers"]) or "macro"
        counts.setdefault(key, {}).setdefault(e["type"], 0)
        counts[key][e["type"]] += 1
    report.update({"n_events": len(events), "per_ticker": counts,
                   "upcoming": sum(e["date"] > today.isoformat() for e in events)})
    return events, report
