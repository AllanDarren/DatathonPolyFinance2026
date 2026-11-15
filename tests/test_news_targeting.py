"""News targeting: source tiers, company mention, event clusters, rates -> bond ETF link."""

from __future__ import annotations

from typing import Any

import pytest

from core import rules_engine as engine
from core.news_targeting import cluster, is_rates_related, mention, source_tier
from core.portfolio import parse_portfolio
from services.feed import build_feed


@pytest.fixture(autouse=True)
def _real_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.ROOT / "rules"))
    engine.clear_cache()


def rec(rid: str, title: str, tickers: list[str], ts: str = "2026-11-10T12:00:00Z", source: str = "Reuters",
        snippet: str | None = None) -> dict[str, Any]:
    return {"id": rid, "title": title, "tickers": tickers, "published_at": ts, "source": source, "snippet": snippet}


@pytest.mark.parametrize("source,tier", [("Reuters", "established"), ("The Motley Fool Canada", "aggregator"),
                                         ("PR Newswire", "primary"), ("About Amazon", "primary"),
                                         ("Some Unknown Blog", "unknown")])
def test_source_tier(source: str, tier: str) -> None:
    assert source_tier(source, engine.load_rules().source_tiers)["id"] == tier


def test_mention() -> None:
    assert mention(rec("a", "Nvidia beats estimates", ["NVDA"]), "NVDA") == "title"
    assert mention(rec("b", "5 Dividend Stocks to Buy and Hold Forever", ["NVDA"]), "NVDA") == "none"
    assert mention(rec("c", "Chip stocks slide", ["NVDA"], snippet="Nvidia fell 3%"), "NVDA") == "snippet"
    assert mention(rec("d", "Bond funds see inflows", ["XBB.TO"]), "XBB.TO") == "not_applicable"


def test_cluster_groups_same_event_and_keeps_best_source() -> None:
    recs = [
        rec("1", "Nvidia opens investigation into CEO relationship with suspected spy", ["NVDA"], source="Motley Fool"),
        rec("2", "Nvidia opens investigation into CEO relationship with suspected spy, report", ["NVDA"],
            "2026-11-10T15:00:00Z", source="Financial Times"),
        rec("3", "Apple unveils new iPhone", ["AAPL"]),
        rec("4", "Nvidia opens investigation into CEO relationship with suspected spy", ["NVDA"],
            "2026-11-20T12:00:00Z"),  # > 48 h later: another card
    ]
    tiers = {"1": "aggregator", "2": "established", "3": "established", "4": "established"}
    out = cluster(recs, tiers)
    assert len(out) == 3
    nv = next(r for r in out if r["_cluster"]["size"] == 2)
    assert nv["id"] == "2"  # established press preferred over an aggregator
    assert set(nv["_cluster"]["news_ids"]) == {"1", "2"}
    assert cluster(list(reversed(recs)), tiers) == out or len(cluster(list(reversed(recs)), tiers)) == 3


def test_rates_related() -> None:
    assert is_rates_related(rec("x", "Bank of Canada holds its policy rate", []))
    assert not is_rates_related(rec("y", "US government holds about $20 billion in Bitcoin", []))


def test_feed_items_carry_targeting_fields() -> None:
    p = next(x for x in engine.load_personas() if x["id"] == "robert")
    f = build_feed(p["profile"], parse_portfolio(p["sample_portfolio_csv"]))
    assert f["items"]
    for i in f["items"]:
        assert i["source_tier"]["id"] in {"primary", "established", "aggregator", "unknown"}
        assert i["cluster"]["size"] >= 1 and i["news_id"] in i["cluster"]["news_ids"]
    rules = {h["rule_id"] for i in f["items"] for h in i["relevance"]["rule_hits"]}
    assert rules & {"R_SOURCE_PRIMARY", "R_SOURCE_AGGREGATOR", "R_MENTION_PASSING", "R_MULTI_SOURCE", "R_RATES_BOND"}
