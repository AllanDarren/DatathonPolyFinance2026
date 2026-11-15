"""Rebuild contracts/examples/ with the real pipeline (python -m tools.build_examples).

feed_robert.json (with "J'envisage d'acheter NVDA à 20 %"), feed_amira.json,
feed_mateo.json and personas.json, produced by services.build_feed in the current
LLM_PROVIDER mode (mock by default: keyword classification, template explanations).
"""

from __future__ import annotations

import json
from pathlib import Path

import services
from core.models import FeedResponse, Persona
from core.portfolio import parse_portfolio

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "contracts" / "examples"
GENERATED_AT = "2026-11-15T00:00:00Z"
CONSIDERATIONS = {"robert": {"ticker": "NVDA", "intended_weight": 0.20}}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    personas = services.get_personas()
    for p in personas:
        Persona.model_validate(p)
        portfolio = parse_portfolio(p["sample_portfolio_csv"])
        from services.feed import build_feed

        feed = build_feed(p["profile"], portfolio, CONSIDERATIONS.get(p["id"]), generated_at=GENERATED_AT)
        FeedResponse.model_validate(feed)
        (OUT / f"feed_{p['id']}.json").write_text(json.dumps(feed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"feed_{p['id']}.json: {len(feed['items'])} items, {feed['hidden']['count']} hidden, "
              f"{len(feed['evidence'])} evidence, coherence={feed['coherence'] and feed['coherence']['verdict']}")
    (OUT / "personas.json").write_text(json.dumps(personas, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
