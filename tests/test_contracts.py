"""A0 acceptance: examples validate against the JSON Schemas; facade returns contract shapes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import services
from agents.llm import MockClient
from core import models
from tools import export_schemas

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = json.loads((ROOT / "contracts" / "alphaforge.schema.json").read_text(encoding="utf-8"))
EXAMPLES = ROOT / "contracts" / "examples"
FEEDS = ["feed_robert.json", "feed_amira.json", "feed_mateo.json"]


def validator(name: str) -> Draft202012Validator:
    schema = {**BUNDLE, "anyOf": None, "$ref": f"#/$defs/{name}"}
    del schema["anyOf"]
    return Draft202012Validator(schema)


def assert_valid(name: str, instance: Any) -> None:
    errors = sorted(validator(name).iter_errors(instance), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:5])


def load(name: str) -> Any:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_schema_bundle_is_up_to_date() -> None:
    assert (ROOT / "contracts" / "alphaforge.schema.json").read_text(encoding="utf-8") == export_schemas.render()


def test_bundle_is_a_valid_schema() -> None:
    Draft202012Validator.check_schema(BUNDLE)
    for model in models.TOP_LEVEL:
        assert model.__name__ in BUNDLE["$defs"]


@pytest.mark.parametrize("name", FEEDS)
def test_feed_example_validates(name: str) -> None:
    feed = load(name)
    assert_valid("FeedResponse", feed)
    models.FeedResponse.model_validate(feed)
    assert len(feed["items"]) >= 5


@pytest.mark.parametrize("name", FEEDS)
def test_every_cited_evidence_exists(name: str) -> None:
    feed = load(name)
    ev = feed["evidence"]
    for key, value in ev.items():
        assert value["id"] == key
    explanations = [i["explanation"] for i in feed["items"]]
    if feed["coherence"]:
        explanations.append(feed["coherence"]["explanation"])
    for expl in explanations:
        for claim in expl["claims"]:
            assert claim["evidence_ids"], claim["text"]
            for ev_id in claim["evidence_ids"]:
                assert ev_id in ev
            assert not re.search(r"\{\{ev_\w+\}\}", claim["text"]), "unrendered marker"
    for item in feed["items"]:
        if item["historical_context"]:
            assert item["historical_context"]["evidence_id"] in ev


def test_robert_has_incoherent_nvda_20() -> None:
    coherence = load("feed_robert.json")["coherence"]
    assert coherence["verdict"] == "incoherent"
    assert coherence["metrics"]["position_weight_after"] == pytest.approx(0.20)
    assert len(coherence["rule_hits"]) >= 2


def test_example_news_match_the_snapshot() -> None:
    from core import snapshots

    by_id = {r["id"]: r for r in snapshots.records("classified_news")}
    for name in FEEDS:
        for item in load(name)["items"]:
            src = by_id[item["news_id"]]
            assert item["is_synthetic"] == src["is_synthetic"] and item["url"] == src["url"]


def test_no_advice_vocabulary_in_our_texts() -> None:
    banned = re.compile(r"\b(achète|achetez|vends|vendez|tu devrais|vous devriez)\b", re.IGNORECASE)
    for name in FEEDS:
        feed = load(name)
        expls = [i["explanation"] for i in feed["items"]] + ([feed["coherence"]["explanation"]] if feed["coherence"] else [])
        for e in expls:
            assert not banned.search(e["summary"])
            for c in e["claims"]:
                assert not banned.search(c["text"]), c["text"]
        for h in (feed["coherence"] or {}).get("rule_hits", []):
            assert not banned.search(h["text"])


def test_personas_validate() -> None:
    personas = services.get_personas()
    assert {p["id"] for p in personas} == {"robert", "amira", "mateo"}
    for p in personas:
        assert_valid("Persona", p)


def test_facade_shapes() -> None:
    assert_valid("Health", services.health())
    answers = {q["id"]: q["options"][0]["id"] for q in services.get_questionnaire()["questions"]}
    profile = services.score_profile(answers)
    assert_valid("Profile", profile)
    portfolio = services.parse_portfolio("ticker,montant\nSPY,1000\n")
    assert_valid("Portfolio", portfolio)
    feed = services.build_feed(load("feed_robert.json")["profile"], portfolio, {"ticker": "NVDA", "intended_weight": 0.2})
    assert_valid("FeedResponse", feed)
    assert feed["coherence"] is not None
    assert services.build_feed(profile, portfolio)["coherence"] is None
    for event in services.get_events(["NVDA"]):
        assert_valid("Event", event)
    assert isinstance(services.get_questionnaire(), dict)


def test_facade_errors_follow_error_contract() -> None:
    with pytest.raises(services.ServiceError) as exc:
        services.parse_portfolio("   ")
    assert exc.value.code == "INVALID_CSV"
    assert_valid("ErrorResponse", exc.value.to_dict())


def test_mock_client_is_deterministic() -> None:
    schema = {"type": "object", "properties": {"category": {"enum": ["a", "b"]}, "confidence": {"type": "number"}},
              "required": ["category", "confidence"]}
    a, b = MockClient(), MockClient()
    out_a = a.complete("sys", [{"role": "user", "content": "x"}], schema)
    out_b = b.complete("sys", [{"role": "user", "content": "x"}], schema)
    assert out_a == out_b == {"category": "a", "confidence": 0}
    assert a.calls[0]["digest"] == b.calls[0]["digest"]
