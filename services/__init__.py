"""Public facade called by the API (api/handler.py, role B).

A0: every function returns the contract examples from contracts/examples/ so B can
wire the API and C can render real shapes. Later deliverables swap in the real
pipeline one capability at a time, without changing the output shapes.

All functions return plain JSON-serializable dicts/lists matching the contracts.
"""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

from core import data as _data
from core import portfolio as _portfolio
from core import rules_engine as _rules
from core import snapshots as _snapshots
from core.errors import AlphaForgeError
from core.models import CONTRACT_VERSION

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "contracts" / "examples"

__all__ = [
    "ServiceError",
    "health",
    "get_questionnaire",
    "get_personas",
    "score_profile",
    "parse_portfolio",
    "build_feed",
    "get_events",
]


# Business errors: the API maps them to `{error: {code, message, details?}}` with `.status`.
ServiceError = AlphaForgeError


@cache
def _example(name: str) -> Any:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _copy(obj: Any) -> Any:
    return json.loads(json.dumps(obj))


def health() -> dict[str, Any]:
    return {"status": "ok", "version": CONTRACT_VERSION, "llm_provider": os.environ.get("LLM_PROVIDER", "mock")}


def get_questionnaire() -> dict[str, Any]:
    """Content of rules/questionnaire.yaml as JSON (reference example until role D ships it)."""
    return _copy(_rules.load_rules().raw_questionnaire)


def get_personas() -> list[dict[str, Any]]:
    """Personas from rules/personas/ (reference examples until role D ships them)."""
    return _rules.load_personas()


def score_profile(answers: dict[str, str]) -> dict[str, Any]:
    """Questionnaire answers -> Profile, computed by rules (never by the LLM)."""
    return _rules.score_profile(answers)


def parse_portfolio(csv_text: str) -> dict[str, Any]:
    """CSV `ticker,montant` (CAD) -> Portfolio. Raises ServiceError (INVALID_CSV, UNKNOWN_TICKER)."""
    if not isinstance(csv_text, str):
        raise ServiceError("INVALID_CSV", "Le contenu CSV doit être du texte.")
    return _portfolio.parse_portfolio(csv_text)


def build_feed(profile: dict[str, Any], portfolio: dict[str, Any],
               consideration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Profile x portfolio (x consideration) -> FeedResponse (real pipeline)."""
    from services.feed import build_feed as _build_feed

    return _build_feed(profile, portfolio, consideration)


def get_events(tickers: list[str] | None = None) -> list[dict[str, Any]]:
    """Events from the latest snapshot: macro events always, ticker events filtered by `tickers`.

    Without a snapshot, falls back to the A0 example events.
    """
    events = _snapshots.records("events", required=False) or _copy(_example("feed_robert.json")["events"])
    if tickers:
        wanted = {t.strip().upper() for t in tickers}
        unknown = sorted(wanted - set(_data.universe_tickers()))
        if unknown:
            raise ServiceError("UNKNOWN_TICKER", f"Ticker(s) hors des 31 actifs: {', '.join(unknown)}.",
                               details={"tickers": unknown})
        events = [e for e in events if e["scope"] == "macro" or wanted & set(e["tickers"])]
    return _copy(events)
