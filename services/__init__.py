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

from core.models import CONTRACT_VERSION

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "contracts" / "examples"
RULES = ROOT / "rules"

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


class ServiceError(Exception):
    """Business error; the API maps it to `{error: {code, message, details?}}`."""

    def __init__(self, code: str, message: str, status: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details

    def to_dict(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            err["details"] = self.details
        return {"error": err}


@cache
def _example(name: str) -> Any:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _copy(obj: Any) -> Any:
    return json.loads(json.dumps(obj))


def health() -> dict[str, Any]:
    return {"status": "ok", "version": CONTRACT_VERSION, "llm_provider": os.environ.get("LLM_PROVIDER", "mock")}


def get_questionnaire() -> dict[str, Any]:
    """Content of rules/questionnaire.yaml as JSON (empty placeholder until role D ships it)."""
    path = RULES / "questionnaire.yaml"
    if path.exists():
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return {"version": 1, "questions": []}


def get_personas() -> list[dict[str, Any]]:
    return _copy(_example("personas.json"))


def score_profile(answers: dict[str, str]) -> dict[str, Any]:
    """A0 stub: returns the Mateo example profile tagged as a questionnaire result."""
    if not isinstance(answers, dict):
        raise ServiceError("INVALID_ANSWERS", "Les réponses doivent être un objet {question_id: option_id}.")
    profile = _copy(_example("feed_mateo.json")["profile"])
    profile.update({"profile_id": "custom", "label": "Mon profil", "source": "questionnaire"})
    return profile


def parse_portfolio(csv_text: str) -> dict[str, Any]:
    """A0 stub: returns Robert's example portfolio, shaped as a Portfolio."""
    if not csv_text or not csv_text.strip():
        raise ServiceError("INVALID_CSV", "Le fichier CSV est vide.")
    summary = _example("feed_robert.json")["portfolio_summary"]
    positions = _copy(summary["top_positions"])
    return {
        "base_currency": "CAD",
        "total_amount": sum(p["amount"] for p in positions),
        "positions": positions,
        "unanalyzed": {"tickers": [], "weight": 0.0},
        "warnings": ["Réponse d'exemple (A0): le vrai analyseur CSV arrive en A1."],
    }


def build_feed(
    profile: dict[str, Any], portfolio: dict[str, Any], consideration: dict[str, Any] | None = None
) -> dict[str, Any]:
    """A0 stub: returns the example feed of the matching persona (Mateo by default)."""
    pid = profile.get("profile_id") if isinstance(profile, dict) else None
    name = f"feed_{pid}.json" if pid in ("robert", "amira", "mateo") else "feed_mateo.json"
    feed = _copy(_example(name))
    if consideration is None:
        feed["coherence"] = None
    return feed


def get_events(tickers: list[str] | None = None) -> list[dict[str, Any]]:
    events = _copy(_example("feed_robert.json")["events"])
    if tickers:
        wanted = set(tickers)
        events = [e for e in events if e["scope"] == "macro" or wanted & set(e["tickers"])]
    return events
