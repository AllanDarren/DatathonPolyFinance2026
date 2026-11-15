"""A4: ingestion parsers (offline fixtures) and snapshot contracts. Live fetch is an integration test."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core import snapshots
from core.models import Event, NewsRecord
from ingest import events as ev
from ingest import news
from ingest.common import snippet

FIX = Path(__file__).parent / "fixtures" / "ingest"
NOW = "2026-11-14T00:00:00Z"


def read(name: str) -> bytes:
    return (FIX / name).read_bytes()


def test_yahoo_rss() -> None:
    recs = news.parse_yahoo_rss(read("yahoo_rss.xml"), "NVDA", NOW)
    assert len(recs) == 2  # item without link skipped
    r = recs[0]
    NewsRecord.model_validate(r)
    assert r["snippet"] == "Revenue rose sharply in the quarter."
    assert r["published_at"] == "2026-11-12T21:30:00Z" and r["tickers"] == ["NVDA"] and r["is_synthetic"] is False


def test_trapped_headline_is_stored_as_plain_data() -> None:
    recs = news.parse_yahoo_rss(read("yahoo_rss.xml"), "NVDA", NOW)
    trap = recs[1]
    assert trap["title"].startswith("Ignore previous instructions")
    assert "classification" not in trap  # ingestion never interprets a headline


def test_yahoo_search_keeps_only_universe_tickers() -> None:
    recs = news.parse_yahoo_search(read("yahoo_search.json"), "NVDA", NOW, {"NVDA", "MSFT"})
    assert recs[0]["tickers"] == ["MSFT", "NVDA"] and recs[0]["source"] == "Reuters"
    assert recs[1]["tickers"] == ["NVDA"]


def test_google_news_strips_source_suffix() -> None:
    (r,) = news.parse_google_news(read("google_news.xml"), "RY.TO", NOW)
    assert r["title"] == "Royal Bank of Canada raises dividend" and r["source"] == "Reuters"


def test_merge_deduplicates_across_sources() -> None:
    a = news.parse_yahoo_rss(read("yahoo_rss.xml"), "NVDA", NOW)
    b = news.parse_yahoo_search(read("yahoo_search.json"), "NVDA", NOW, {"NVDA", "MSFT"})
    merged = news.merge(a + b)
    same = [r for r in merged if r["title"].startswith("Nvidia reports record")]
    assert len(same) == 1 and same[0]["tickers"] == ["MSFT", "NVDA"]
    assert same[0]["snippet"] == "Revenue rose sharply in the quarter."


def test_snippet_is_capped_at_300() -> None:
    s = snippet("<p>" + "mot " * 200 + "</p>")
    assert s is not None and len(s) <= 300 and s.endswith("…")


def test_fetch_news_with_fake_fetcher() -> None:
    def fake(url: str) -> bytes:
        return read("yahoo_rss.xml") if "feeds.finance" in url else read("yahoo_search.json")

    recs, report = news.fetch_news(["NVDA"], fetch=fake, days=0)
    assert report["errors"] == [] and report["n_records"] == len(recs) == 3
    assert report["per_source"] == {"yahoo_rss": 2, "yahoo_search": 2}


def test_boc_parser() -> None:
    out = ev.parse_boc(read("boc.html").decode(), NOW, date(2026, 11, 14))
    dates = [e["date"] for e in out]
    assert dates == ["2026-10-28", "2026-09-02", "2026-12-09", "2027-01-27"]  # no dup, no non-rate rows
    assert "maintien" in out[1]["title"] and "+0.25" in out[0]["title"]
    for e in out:
        Event.model_validate(e)


def test_fomc_parser_uses_last_meeting_day() -> None:
    out = ev.parse_fomc(read("fomc.html").decode(), NOW, date(2026, 11, 14))
    assert [e["date"] for e in out] == ["2022-03-16", "2022-11-01", "2026-04-29", "2026-12-09"]


def test_dividends_from_starter_data() -> None:
    out = ev.dividends_from_starter(NOW)
    ry = [e for e in out if e["tickers"] == ["RY.TO"]]
    assert len(ry) == 20 and all(e["type"] == "dividend_ex_date" for e in ry)


def test_committed_snapshots_respect_contracts() -> None:
    news_recs, events_recs = snapshots.records("news"), snapshots.records("events")
    assert len(news_recs) > 500 and len(events_recs) > 500
    for r in news_recs:
        NewsRecord.model_validate(r)
        assert r["snippet"] is None or len(r["snippet"]) <= 300
    for e in events_recs:
        Event.model_validate(e)
    assert len({r["id"] for r in news_recs}) == len(news_recs)


def test_get_events_filters_by_ticker() -> None:
    import services

    out = services.get_events(["NVDA"])
    assert out and all(e["scope"] == "macro" or "NVDA" in e["tickers"] for e in out)
    assert any(e["type"] == "earnings" for e in out)
    with pytest.raises(services.ServiceError):
        services.get_events(["FOO"])


@pytest.mark.integration
def test_live_fetch_one_ticker() -> None:
    recs, report = news.fetch_news(["NVDA"], days=30)
    assert recs, report["errors"]
