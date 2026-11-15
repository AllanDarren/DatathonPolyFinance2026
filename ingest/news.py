"""Fetch public headlines for the 31 assets -> NewsRecord list (no classification).

Sources (public, no key): Yahoo Finance RSS per ticker, Yahoo Finance search API
per ticker, and optionally Google News RSS per company name. We keep title,
source, date, link and an excerpt of at most 300 characters (no full text).
Headlines are untrusted data: they are stored as is and never interpreted.
"""

from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

from core.data import load_universe
from ingest.common import http_get, normalize_title, now_iso, snippet, stable_id, strip_html

YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
YAHOO_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search?q={ticker}&newsCount={n}&quotesCount=0"
GOOGLE_NEWS = "https://news.google.com/rss/search?q={query}+when:{days}d&hl=en-CA&gl=CA&ceid=CA:en"

Fetcher = Callable[[str], bytes]


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record(*, title: str, source: str, url: str, published: datetime, tickers: Iterable[str],
            text: str | None, retrieved_at: str, origin: str) -> dict[str, Any]:
    clean_title = strip_html(title)
    return {
        "id": stable_id("n_", normalize_title(clean_title)),
        "title": clean_title,
        "source": source or origin,
        "url": url,
        "published_at": _iso(published),
        "snippet": snippet(text),
        "tickers": sorted(set(tickers)),
        "is_synthetic": False,
        "retrieved_at": retrieved_at,
    }


def parse_yahoo_rss(payload: bytes, ticker: str, retrieved_at: str) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    out = []
    for item in root.iter("item"):
        title, link, date = item.findtext("title"), item.findtext("link"), item.findtext("pubDate")
        if not (title and link and date):
            continue
        out.append(_record(title=title, source="Yahoo Finance", url=link, published=parsedate_to_datetime(date),
                           tickers=[ticker], text=item.findtext("description"), retrieved_at=retrieved_at,
                           origin="yahoo_rss"))
    return out


def parse_yahoo_search(payload: bytes, ticker: str, retrieved_at: str, universe: set[str]) -> list[dict[str, Any]]:
    data = json.loads(payload)
    out = []
    for n in data.get("news", []):
        title, link, ts = n.get("title"), n.get("link"), n.get("providerPublishTime")
        if not (title and link and ts):
            continue
        related = {t for t in n.get("relatedTickers", []) if t in universe}
        out.append(_record(title=title, source=n.get("publisher") or "Yahoo Finance", url=link,
                           published=datetime.fromtimestamp(int(ts), tz=UTC), tickers=related | {ticker},
                           text=None, retrieved_at=retrieved_at, origin="yahoo_search"))
    return out


def parse_google_news(payload: bytes, ticker: str, retrieved_at: str) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    out = []
    for item in root.iter("item"):
        title, link, date = item.findtext("title"), item.findtext("link"), item.findtext("pubDate")
        if not (title and link and date):
            continue
        source = item.findtext("source") or "Google News"
        if title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        out.append(_record(title=title, source=source, url=link, published=parsedate_to_datetime(date),
                           tickers=[ticker], text=None, retrieved_at=retrieved_at, origin="google_news"))
    return out


def merge(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by normalized title (same id); union tickers; keep the earliest date and first snippet."""
    by_id: dict[str, dict[str, Any]] = {}
    for r in records:
        cur = by_id.get(r["id"])
        if cur is None:
            by_id[r["id"]] = dict(r)
            continue
        cur["tickers"] = sorted(set(cur["tickers"]) | set(r["tickers"]))
        cur["published_at"] = min(cur["published_at"], r["published_at"])
        cur["snippet"] = cur["snippet"] or r["snippet"]
    return sorted(by_id.values(), key=lambda r: (r["published_at"], r["id"]), reverse=True)


def fetch_news(tickers: list[str] | None = None, *, google: bool = False, days: int = 30, search_count: int = 20,
               fetch: Fetcher = http_get) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch, merge and filter headlines. Returns (records, report)."""
    uni = load_universe()
    universe = set(uni.index)
    tickers = tickers or list(uni.index)
    retrieved_at = now_iso()
    raw: list[dict[str, Any]] = []
    report: dict[str, Any] = {"retrieved_at": retrieved_at, "per_source": {}, "errors": []}
    for t in tickers:
        sources: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = [
            ("yahoo_rss", lambda t=t: parse_yahoo_rss(fetch(YAHOO_RSS.format(ticker=urllib.parse.quote(t))), t,
                                                      retrieved_at)),
            ("yahoo_search", lambda t=t: parse_yahoo_search(
                fetch(YAHOO_SEARCH.format(ticker=urllib.parse.quote(t), n=search_count)), t, retrieved_at, universe)),
        ]
        if google:
            name = str(uni.loc[t, "name"])
            query = urllib.parse.quote(f'"{name}"')
            sources.append(("google_news", lambda t=t, q=query: parse_google_news(
                fetch(GOOGLE_NEWS.format(query=q, days=days)), t, retrieved_at)))
        for label, call in sources:
            try:
                got = call()
            except Exception as exc:  # noqa: BLE001 - report and keep going
                report["errors"].append(f"{label} {t}: {exc}")
                continue
            report["per_source"].setdefault(label, 0)
            report["per_source"][label] += len(got)
            raw.extend(got)
    records = merge(raw)
    if days > 0:
        since = datetime.now(UTC).timestamp() - days * 86400
        records = [r for r in records if datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")).timestamp()
                   >= since]
    per_ticker = {t: sum(t in r["tickers"] for r in records) for t in tickers}
    dates = [r["published_at"] for r in records]
    report.update({"n_records": len(records), "per_ticker": per_ticker,
                   "oldest": min(dates) if dates else None, "newest": max(dates) if dates else None})
    return records, report
