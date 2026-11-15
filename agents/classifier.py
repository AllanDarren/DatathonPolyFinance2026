"""Headline classifier: title (+ excerpt) -> category and controversy (rules/taxonomy.yaml).

- The model only picks a category id and a controversy flag; `horizon_relevance`
  comes from the taxonomy, never from the model.
- Headlines are untrusted: delimited, stripped of markup, truncated; output is a
  schema-validated JSON object with an enum of category ids, so an injected
  instruction cannot produce anything outside the taxonomy.
- Cache by (news_id, prompt_version).
- Offline (`MockClient`): deterministic keyword classifier, labeled `mock-keywords`.
"""

from __future__ import annotations

import re
from typing import Any

from agents.llm import LLMClient, LLMUnavailableError, Message, MockClient
from agents.prompts import load_prompt, render_prompt
from core.rules_models import Taxonomy

MAX_HEADLINE = 300
MOCK_MODEL_ID = "mock-keywords"

# Keyword heuristics for offline mode, by reference category id (contracts/rules/examples).
# Ordered: first match wins. Unknown ids (if role D renames categories) are skipped.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("controversy", ("spill", "leak", "recall", "scandal", "boycott", "accused", "fraud", "fined", "pollution",
                     "controvers", "whistleblow", "fuite", "rappel", "critiques d'actionnaires", "eliminates climate",
                     "esg roles", "class action", "data breach", "discriminat")),
    ("mergers_acquisitions", ("acquire", "acquisition", "merger", "takeover", "buyout", "to buy", "agrees to buy",
                              "stake in", "spin-off", "spinoff", "divest", "rachat", "fusion")),
    ("management_change", ("ceo", "cfo", "chief executive", "steps down", "resigns", "resign", "appoints",
                           "names new", "succession", "pdg", "démission", "nomme")),
    ("earnings_results", ("earnings", "quarterly results", "q1", "q2", "q3", "q4", "revenue", "profit", "eps",
                          "beats estimates", "misses estimates", "résultats", "bénéfice", "trimestriel")),
    ("dividend", ("dividend", "distribution", "payout", "dividende", "buyback")),
    ("macro_rates", ("interest rate", "rate cut", "rate hike", "central bank", "bank of canada", "federal reserve",
                     "the fed", "fed ", "fomc", "inflation", "cpi", "jobs report", "unemployment", "gdp", "recession",
                     "taux directeur", "banque du canada", "chômage", "treasury yield", "bond yield", "10-year")),
    ("regulation_legal", ("sec", "regulator", "antitrust", "lawsuit", "court", "ruling", "investigation",
                          "approves", "approval", "tariff", "sanction", "export curb", "réglement", "poursuite")),
    ("guidance_strategy", ("guidance", "outlook", "forecast", "strategy", "investment plan", "capex", "expansion",
                           "layoffs", "job cuts", "restructur", "reorganiz", "prévisions", "stratégie")),
    ("analyst_rating", ("analyst", "price target", "upgrade", "downgrade", "rating", "overweight", "underweight",
                        "outperform", "cible de cours")),
    ("product", ("launch", "unveil", "new product", "rolls out", "introduces", "chip", "ai features", "dévoile",
                 "lance", "nouveaux outils")),
    ("rumor_hype", ("rumor", "rumour", "reportedly", "speculat", "soars", "skyrocket", "meme", "frenzy",
                    "social media", "to the moon", "rumeur", "s'enflamment")),
    ("price_commentary", ("shares", "stock", "falls", "rises", "jumps", "slides", "drops", "gains", "rally",
                          "record high", "sell-off", "session", "recule", "séance", "sommet", "bondit")),
]
_PATTERNS = {cat: re.compile(r"\b(?:" + "|".join(re.escape(w.strip()) for w in words) + ")", re.IGNORECASE)
             for cat, words in KEYWORDS}


def sanitize(text: str | None, limit: int = MAX_HEADLINE) -> str:
    """Untrusted text -> plain single line, no markup, bounded length."""
    if not text:
        return ""
    text = re.sub(r"<[^>]*>", " ", text).replace("<", " ").replace(">", " ")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def output_schema(taxonomy: Taxonomy) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [c.id for c in taxonomy.categories]},
            "controversy": {"type": "boolean"},
            "controversy_type": {"anyOf": [{"type": "string", "enum": list(taxonomy.controversy_types)},
                                           {"type": "null"}]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["category", "controversy", "controversy_type", "confidence"],
        "additionalProperties": False,
    }


def system_prompt(taxonomy: Taxonomy) -> tuple[str, str]:
    text, version = load_prompt("classifier")
    cats = "\n".join(f"- {c.id}: {c.definition} Examples: " + " | ".join(c.examples) for c in taxonomy.categories)
    return render_prompt(text, categories=cats, controversy_types=", ".join(taxonomy.controversy_types)), version


def user_message(record: dict[str, Any]) -> list[Message]:
    title = sanitize(record.get("title"))
    excerpt = sanitize(record.get("snippet"))
    body = f"<headline>\n{title}" + (f"\nExcerpt: {excerpt}" if excerpt else "") + "\n</headline>"
    return [{"role": "user", "content": body}]


def keyword_classify(record: dict[str, Any], taxonomy: Taxonomy) -> dict[str, Any]:
    """Deterministic offline classification (mock mode)."""
    ids = {c.id for c in taxonomy.categories}
    text = sanitize(record.get("title")).lower()
    category, matched = None, False
    for cat_id, _ in KEYWORDS:
        if cat_id in ids and _PATTERNS[cat_id].search(text):
            category, matched = cat_id, True
            break
    if category is None:  # unmatched: generic market commentary (short-term noise), low confidence
        noise = [c.id for c in taxonomy.categories if c.horizon_relevance == "short_term_noise"]
        category = "price_commentary" if "price_commentary" in noise else (noise[0] if noise else
                                                                            taxonomy.categories[0].id)
    controversy = category == "controversy"
    ctype = None
    if controversy:
        if any(w in text for w in ("spill", "leak", "pollution", "climate", "fuite", "environment")):
            ctype = "environmental"
        elif any(w in text for w in ("recall", "safety", "rappel", "crash")):
            ctype = "safety"
        elif any(w in text for w in ("ceo pay", "shareholder", "actionnaires", "governance", "board")):
            ctype = "governance"
        else:
            ctype = "other"
        if ctype not in taxonomy.controversy_types:
            ctype = taxonomy.controversy_types[-1]
    return {"category": category, "controversy": controversy, "controversy_type": ctype,
            "confidence": 0.6 if matched else 0.3}


class Classifier:
    """Classifies NewsRecords; caches by (news_id, prompt_version)."""

    def __init__(self, client: LLMClient, taxonomy: Taxonomy, cache: dict[tuple[str, str], dict[str, Any]] | None = None):
        self.client = client
        self.taxonomy = taxonomy
        self.cache = cache if cache is not None else {}
        self.system, self.prompt_version = system_prompt(taxonomy)
        self.schema = output_schema(taxonomy)
        self.mock = isinstance(client, MockClient) and client.responder is None

    @property
    def model_id(self) -> str:
        return MOCK_MODEL_ID if self.mock else self.client.model_id

    def classify(self, record: dict[str, Any]) -> dict[str, Any]:
        """NewsRecord -> classification dict (contract NewsClassification). Raises LLMUnavailableError."""
        key = (record["id"], self.prompt_version)
        if key in self.cache:
            return dict(self.cache[key])
        if self.mock:
            raw = keyword_classify(record, self.taxonomy)
        else:
            raw = self.client.complete(self.system, user_message(record), self.schema)
        cat = next((c for c in self.taxonomy.categories if c.id == raw["category"]), None)
        if cat is None:  # cannot happen with schema validation; defensive
            raise LLMUnavailableError(f"catégorie hors taxonomie: {raw['category']!r}")
        controversy = bool(raw["controversy"])
        out = {
            "category": cat.id,
            "horizon_relevance": cat.horizon_relevance,
            "controversy": controversy,
            "controversy_type": raw.get("controversy_type") if controversy else None,
            "confidence": round(float(raw["confidence"]), 3),
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
        }
        self.cache[key] = out
        return dict(out)
