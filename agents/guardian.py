"""Explanation guardian (CLAUDE.md section 9).

Two passes per claim:
1. deterministic: cited evidence exists, every {{ev_id}} marker is cited, label is
   valid, no number absent from the cited evidence (the model must not type numbers),
   no advice vocabulary. A claim failing this pass is REMOVED and flagged.
2. model: is the text supported by its cited evidence statements? Unsupported
   claims are kept but marked `unsupported` (UI shows ⚠). If the model is
   unavailable, LLM-written claims stay `not_checked` and the guardian is flagged.
Template claims (evidence statements written by code) skip pass 2: they are the evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agents.llm import LLMClient, LLMUnavailableError, MockClient
from agents.prompts import load_prompt
from core.evidence import EvidenceRegistry, format_value, render_template

LABELS = {"fact", "hypothesis", "scenario"}
ADVICE = re.compile(
    r"\b(achète|achètes|achetez|vends|vendez|tu devrais|vous devriez|il faut que tu|il faudrait que tu|"
    r"je te conseille|je vous conseille|je recommande|nous recommandons|on recommande|"
    r"buy now|you should|sell now)\b",
    re.IGNORECASE,
)
NUMBER = re.compile(r"\d+(?:[.,   ]\d+)*")


@dataclass
class Draft:
    """A claim before checks: `template` may contain {{ev_id}} markers."""

    template: str
    label: str
    evidence_ids: list[str]
    origin: str = "llm"  # "llm" | "template"


@dataclass
class Review:
    claims: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def guardian(self) -> dict[str, Any]:
        return {"status": "flagged" if self.flags else "passed", "flags": list(self.flags)}


def _norm(s: str) -> str:
    return s.replace(" ", " ").replace(" ", " ").replace("−", "-")


def unsourced_numbers(text: str, evidence: list[dict[str, Any]]) -> list[str]:
    """Numbers in `text` that appear in none of the cited evidence (rendered values removed first)."""
    t = _norm(text)
    for ev in evidence:
        t = t.replace(_norm(format_value(ev)), " ")
    haystack = " ".join(_norm(ev.get("statement", "")) + " " + _norm(str(ev.get("inputs", ""))) for ev in evidence)
    return [n for n in NUMBER.findall(t) if n.strip() and n not in haystack]


def deterministic_check(draft: Draft, registry: EvidenceRegistry) -> tuple[str, list[str], list[str]]:
    """Return (rendered text, final evidence ids, problems)."""
    text, cited, unknown = render_template(draft.template, registry)
    ids = list(dict.fromkeys([*draft.evidence_ids, *cited]))
    problems: list[str] = []
    if unknown:
        problems.append(f"repère(s) sans preuve: {', '.join(unknown)}")
    missing = [i for i in ids if i not in registry]
    if missing:
        problems.append(f"preuve(s) inexistante(s): {', '.join(missing)}")
    if not ids:
        problems.append("aucune preuve citée")
    if draft.label not in LABELS:
        problems.append(f"étiquette invalide: {draft.label!r}")
    if ADVICE.search(text):
        problems.append("formulation de conseil")
    evs = [e for e in (registry.get(i) for i in ids) if e]
    stray = unsourced_numbers(text, evs)
    if stray:
        problems.append(f"chiffre(s) non sourcé(s): {', '.join(stray)}")
    return text, ids, problems


def _model_schema(n: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"verdicts": {"type": "array", "items": {
            "type": "object",
            "properties": {"index": {"type": "integer", "minimum": 0, "maximum": max(n - 1, 0)},
                           "supported": {"type": "boolean"}, "reason": {"type": "string"}},
            "required": ["index", "supported", "reason"], "additionalProperties": False}}},
        "required": ["verdicts"], "additionalProperties": False,
    }


def model_check(claims: list[dict[str, Any]], registry: EvidenceRegistry, client: LLMClient) -> dict[int, tuple[bool, str]]:
    system, _ = load_prompt("guardian")
    lines = []
    for i, c in enumerate(claims):
        evs = "; ".join(f"[{e}] {registry.get(e)['statement']}" for e in c["evidence_ids"] if registry.get(e))
        lines.append(f"CLAIM {i} ({c['label']}): {c['text']}\nEVIDENCE: {evs}")
    out = client.complete(system, [{"role": "user", "content": "\n\n".join(lines)}], _model_schema(len(claims)))
    return {v["index"]: (v["supported"], v["reason"]) for v in out["verdicts"]}


def review(drafts: list[Draft], registry: EvidenceRegistry, client: LLMClient | None = None) -> Review:
    rev = Review()
    for d in drafts:
        text, ids, problems = deterministic_check(d, registry)
        if problems:
            rev.flags.append(f"Affirmation retirée ({'; '.join(problems)}).")
            continue
        rev.claims.append({"text": text, "label": d.label, "evidence_ids": ids,
                           "verified": "supported" if d.origin == "template" else "not_checked"})
    to_check = [i for i, c in enumerate(rev.claims) if c["verified"] == "not_checked"]
    if to_check:
        offline = client is None or (isinstance(client, MockClient) and client.responder is None)
        try:
            if offline:
                raise LLMUnavailableError("pas de modèle")
            subset = [rev.claims[i] for i in to_check]
            verdicts = model_check(subset, registry, client)  # type: ignore[arg-type]
            for j, i in enumerate(to_check):
                ok, reason = verdicts.get(j, (False, "pas de verdict"))
                rev.claims[i]["verified"] = "supported" if ok else "unsupported"
                if not ok:
                    rev.flags.append(f"Affirmation non soutenue par ses preuves: « {rev.claims[i]['text']} » ({reason}).")
        except LLMUnavailableError:
            rev.flags.append("Contrôle par modèle indisponible: affirmations non vérifiées sur le fond.")
    return rev
