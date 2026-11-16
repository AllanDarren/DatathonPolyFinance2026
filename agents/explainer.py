"""Explanation writer: evidence -> claims with {{ev_id}} markers -> guardian.

The model only drafts sentences around evidence markers; the code renders the
values and the guardian checks every claim. Without a model (mock mode, outage or
invalid output), the explanation shows the rules and evidence statements
themselves, without a summary (generated_by "template"). Never an invented
explanation.
"""

from __future__ import annotations

import json
from typing import Any

from agents.classifier import sanitize
from agents.guardian import Draft, review
from agents.llm import LLMClient, LLMUnavailableError, MockClient
from agents.prompts import load_prompt
from core.evidence import EvidenceRegistry, render_template

MAX_CLAIMS = 3
KIND_PRIORITY = {"rule_hit": 0, "portfolio_calc": 1, "metric": 2, "event_study": 3, "classification": 4,
                 "news_source": 5}


def output_schema(evidence_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": 240},
            "claims": {"type": "array", "maxItems": MAX_CLAIMS, "minItems": 1, "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "maxLength": 300},
                    "label": {"type": "string", "enum": ["fact", "hypothesis", "scenario"]},
                    "evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "enum": evidence_ids}},
                },
                "required": ["text", "label", "evidence_ids"], "additionalProperties": False}},
        },
        "required": ["summary", "claims"], "additionalProperties": False,
    }


def _is_offline(client: LLMClient | None) -> bool:
    return client is None or (isinstance(client, MockClient) and client.responder is None)


def template_explanation(evidence_ids: list[str], registry: EvidenceRegistry, *, max_claims: int = MAX_CLAIMS,
                         note: str | None = None) -> dict[str, Any]:
    """Rules and evidence statements as claims, no summary (fallback without a model)."""
    evs = sorted((registry.get(i) for i in dict.fromkeys(evidence_ids) if registry.get(i)),
                 key=lambda e: KIND_PRIORITY.get(e["kind"], 9))  # type: ignore[index]
    drafts = [Draft(template=e["statement"], label="fact", evidence_ids=[e["id"]], origin="template")  # type: ignore[index]
              for e in evs[:max_claims]]
    rev = review(drafts, registry, None)
    if note:
        rev.flags.append(note)
    return {"summary": "", "claims": rev.claims, "generated_by": "template", "guardian": rev.guardian}


def explain(evidence_ids: list[str], registry: EvidenceRegistry, *, context: str, client: LLMClient | None,
            headline: str | None = None) -> dict[str, Any]:
    """Explanation contract dict for the given evidence."""
    ids = [i for i in dict.fromkeys(evidence_ids) if i in registry]
    if not ids:
        return {"summary": "", "claims": [], "generated_by": "template",
                "guardian": {"status": "not_run", "flags": ["Aucune preuve disponible."]}}
    if _is_offline(client):
        return template_explanation(ids, registry)
    system, _version = load_prompt("explainer")
    payload = {
        "context": context,
        "evidence": [{"id": i, "kind": registry.get(i)["kind"], "statement": registry.get(i)["statement"]}  # type: ignore[index]
                     for i in ids],
    }
    content = ""
    if headline:
        content += f"<headline>\n{sanitize(headline)}\n</headline>\n"
    content += json.dumps(payload, ensure_ascii=False)
    try:
        out = client.complete(system, [{"role": "user", "content": content}], output_schema(ids))  # type: ignore[union-attr]
    except LLMUnavailableError as exc:
        return template_explanation(ids, registry, note=f"Modèle indisponible: explication réduite aux preuves ({exc}).")
    drafts = [Draft(template=c["text"], label=c["label"], evidence_ids=list(c["evidence_ids"])) for c in out["claims"]]
    rev = review(drafts, registry, client)
    summary, _, unknown = render_template(out["summary"], registry)
    from agents.guardian import ADVICE, policy_problems, unsourced_numbers

    evs = [registry.get(i) for i in ids]
    if unknown or ADVICE.search(summary) or unsourced_numbers(summary, evs) or policy_problems(summary, evs):  # type: ignore[arg-type]
        rev.flags.append("Résumé retiré (chiffre non sourcé ou formulation de conseil).")
        summary = ""
    if not rev.claims:
        fallback = template_explanation(ids, registry)
        fallback["guardian"]["flags"] = rev.flags + fallback["guardian"]["flags"]
        fallback["guardian"]["status"] = "flagged"
        return fallback
    return {"summary": summary, "claims": rev.claims, "generated_by": "bedrock", "guardian": rev.guardian}


def with_diversification_claim(explanation: dict[str, Any], verdict_id: str, registry: EvidenceRegistry) -> dict[str, Any]:
    """Append the diversification verdict as a code-written fact (its evidence statement, verbatim).

    Goes through the same deterministic check as template claims.
    """
    ev = registry.get(verdict_id)
    if ev is None:
        return explanation
    rev = review([Draft(template=str(ev["statement"]), label="fact", evidence_ids=[verdict_id], origin="template")],
                 registry)
    if not rev.claims:
        return explanation
    out = dict(explanation)
    out["claims"] = [*explanation["claims"], *rev.claims]
    return out
