"""A7: build_feed real pipeline (mock LLM, committed snapshots)."""

from __future__ import annotations

import time
from typing import Any

import pytest

import services
from agents.llm import MockClient
from core import rules_engine as engine
from core import snapshots
from core.errors import AlphaForgeError
from core.portfolio import parse_portfolio
from services.feed import MAX_ITEMS, MAX_PER_TOPIC, build_feed
from tests.test_contracts import assert_valid


@pytest.fixture(autouse=True)
def _rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.EXAMPLE_RULES_DIR))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    engine.clear_cache()


@pytest.fixture
def personas() -> dict[str, dict[str, Any]]:
    return {p["id"]: {**p, "portfolio": parse_portfolio(p["sample_portfolio_csv"])} for p in services.get_personas()}


def feed_for(p: dict[str, Any], consideration: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_feed(p["profile"], p["portfolio"], consideration, generated_at="2026-11-15T00:00:00Z")


def test_feed_contract_and_ordering(personas: dict) -> None:
    f = feed_for(personas["robert"], {"ticker": "NVDA", "intended_weight": 0.2})
    assert_valid("FeedResponse", f)
    scores = [i["relevance"]["score"] for i in f["items"]]
    assert scores == sorted(scores, reverse=True)
    assert 5 <= len(f["items"]) <= MAX_ITEMS
    assert all(i["relevance"]["shown"] for i in f["items"])
    assert f["hidden"]["count"] == sum(r["count"] for r in f["hidden"]["by_reason"])
    assert f["coherence"]["verdict"] == "incoherent" and f["coherence"]["agent_trace"]
    assert f["data_as_of"] == "2026-11-12" and f["news_as_of"].startswith("2026-11-15")


def test_every_cited_evidence_is_returned(personas: dict) -> None:
    f = feed_for(personas["mateo"])
    ev = f["evidence"]
    for i in f["items"]:
        for c in i["explanation"]["claims"]:
            assert set(c["evidence_ids"]) <= set(ev)
        if i["historical_context"]:
            assert i["historical_context"]["evidence_id"] in ev
            assert i["historical_context"]["caveats"]


def test_topic_cap(personas: dict) -> None:
    f = feed_for(personas["amira"])
    topics: dict[tuple[str, str], int] = {}
    for i in f["items"]:
        key = (str(sorted(i["tickers"])), i["category"])
        topics[key] = topics.get(key, 0) + 1
    held = {p["ticker"] for p in personas["amira"]["portfolio"]["positions"]}
    for i in f["items"]:
        assert held & set(i["tickers"]) or i["horizon_relevance"] == "macro_context"
    assert max(topics.values()) <= MAX_PER_TOPIC * 3  # several ticker combos may share a primary ticker


def test_robert_and_amira_feeds_differ(personas: dict) -> None:
    rob, ami = feed_for(personas["robert"]), feed_for(personas["amira"])
    assert {i["news_id"] for i in rob["items"]} != {i["news_id"] for i in ami["items"]}
    assert rob["profile"]["horizon_bucket"] != ami["profile"]["horizon_bucket"]


def test_mateo_sees_controversy_with_preference_rule(personas: dict) -> None:
    f = feed_for(personas["mateo"])
    contro = [i for i in f["items"] if i["category"] == "controversy"]
    for i in contro:
        assert "R_PREF_CONTROVERSY" in [h["rule_id"] for h in i["relevance"]["rule_hits"]]


def test_deterministic(personas: dict) -> None:
    assert feed_for(personas["robert"]) == feed_for(personas["robert"])


def test_online_path_is_fast(personas: dict) -> None:
    start = time.perf_counter()
    feed_for(personas["amira"], {"ticker": "BTC-USD", "intended_weight": 0.1})
    assert time.perf_counter() - start < 10


def test_mock_mode_is_disclosed_in_limits(personas: dict) -> None:
    f = feed_for(personas["robert"])
    assert any("mots-clés" in lim for lim in f["limits"])
    assert f["disclaimers"]


def test_portfolio_with_unanalyzed_positions(personas: dict) -> None:
    port = parse_portfolio("ticker,montant\nSPY,5000\nBRK-B,5000\n")
    f = build_feed(personas["robert"]["profile"], port)
    assert any("BRK-B" in lim for lim in f["limits"])


@pytest.mark.parametrize(("profile_patch", "portfolio", "cons", "code"), [
    ({"horizon_bucket": "forever"}, None, None, "INVALID_PROFILE"),
    ({}, {"base_currency": "CAD"}, None, "INVALID_PORTFOLIO"),
    ({}, None, {"ticker": "NVDA", "intended_weight": 2}, "INVALID_CONSIDERATION"),
    ({}, None, {"ticker": "FOO", "intended_weight": 0.1}, "UNKNOWN_TICKER"),
])
def test_invalid_inputs(personas: dict, profile_patch: dict, portfolio: Any, cons: Any, code: str) -> None:
    profile = {**personas["robert"]["profile"], **profile_patch}
    with pytest.raises(AlphaForgeError) as exc:
        build_feed(profile, portfolio or personas["robert"]["portfolio"], cons)
    assert exc.value.code == code
    assert_valid("ErrorResponse", exc.value.to_dict())


def test_empty_portfolio(personas: dict) -> None:
    empty = {"base_currency": "CAD", "total_amount": 0, "positions": [], "unanalyzed": {"tickers": [], "weight": 0},
             "warnings": []}
    with pytest.raises(AlphaForgeError) as exc:
        build_feed(personas["robert"]["profile"], empty)
    assert exc.value.code == "EMPTY_PORTFOLIO"


def test_missing_snapshot_gives_empty_feed(personas: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    real = snapshots.load_snapshot

    def no_news(kind: str, required: bool = True) -> Any:
        return None if kind == "classified_news" else real(kind, required)

    monkeypatch.setattr(snapshots, "load_snapshot", no_news)
    f = build_feed(personas["robert"]["profile"], personas["robert"]["portfolio"])
    assert f["items"] == [] and any("Aucun instantané" in lim for lim in f["limits"])
    assert_valid("FeedResponse", f)


def test_llm_explanations_for_top_items(personas: dict) -> None:
    def writer(system: str, messages: Any, schema: dict[str, Any]) -> dict[str, Any]:
        if "fact-checker" in system:
            n = messages[0]["content"].count("CLAIM ")
            return {"verdicts": [{"index": i, "supported": True, "reason": "ok"} for i in range(n)]}
        ids = schema["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"]
        return {"summary": "Nouvelle importante pour ton profil.",
                "claims": [{"text": "Pertinence: {{" + ids[0] + "}}.", "label": "fact", "evidence_ids": [ids[0]]}]}

    f = build_feed(personas["robert"]["profile"], personas["robert"]["portfolio"],
                   client=MockClient(responder=writer, model_id="m"))
    gen = [i["explanation"]["generated_by"] for i in f["items"]]
    assert gen[:6] == ["bedrock"] * 6 and set(gen[6:]) == {"template"}
    assert_valid("FeedResponse", f)
