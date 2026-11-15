"""Evidence objects, registry and value formatting (CLAUDE.md section 9).

Every computed number shown to the user is an Evidence. Ids are content-addressed
(`ev_` + short hash of computed_by + inputs), so the same computation always gets
the same id, and the registry deduplicates naturally. The LLM never types numbers:
`render_template` replaces `{{ev_id}}` markers with `format_value(evidence)`.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

EV_MARKER = re.compile(r"\{\{\s*(ev_[0-9a-z_]+)\s*\}\}")


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"not JSON serializable: {type(obj)}")


def clean_value(value: Any) -> float | str | None:
    """Make a value contract-safe: numpy -> float, NaN/inf -> None."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    f = float(value)
    return None if math.isnan(f) or math.isinf(f) else f


def make_evidence(
    *,
    kind: str,
    statement: str,
    value: Any,
    unit: str | None,
    as_of: str,
    inputs: dict[str, Any],
    source: str,
    computed_by: str,
) -> dict[str, Any]:
    """Build an Evidence dict with a deterministic, content-addressed id."""
    inputs = json.loads(json.dumps(inputs, default=_json_default, sort_keys=True))
    key = json.dumps({"computed_by": computed_by, "inputs": inputs, "kind": kind}, sort_keys=True)
    ev_id = "ev_" + hashlib.sha1(key.encode()).hexdigest()[:10]
    return {
        "id": ev_id,
        "kind": kind,
        "statement": statement,
        "value": clean_value(value),
        "unit": unit,
        "as_of": as_of,
        "inputs": inputs,
        "source": source,
        "computed_by": computed_by,
    }


@dataclass(frozen=True)
class MetricResult:
    """A computed value and the Evidence that backs it."""

    value: Any
    evidence: dict[str, Any]

    @property
    def evidence_id(self) -> str:
        return str(self.evidence["id"])


class EvidenceRegistry:
    """Collects the evidence cited by one response."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def add(self, item: dict[str, Any] | MetricResult) -> str:
        ev = item.evidence if isinstance(item, MetricResult) else item
        self._items.setdefault(ev["id"], ev)
        return str(ev["id"])

    def get(self, ev_id: str) -> dict[str, Any] | None:
        return self._items.get(ev_id)

    def __contains__(self, ev_id: object) -> bool:
        return ev_id in self._items

    def __len__(self) -> int:
        return len(self._items)

    def to_dict(self, only: set[str] | None = None) -> dict[str, dict[str, Any]]:
        return {k: v for k, v in self._items.items() if only is None or k in only}


# --- formatting (French) -------------------------------------------------------

NBSP = " "


def _fr_number(x: float, digits: int) -> str:
    s = f"{abs(x):,.{digits}f}".replace(",", NBSP).replace(".", ",")
    return ("−" if x < 0 else "") + s


def format_pct(x: float, digits: int = 1) -> str:
    """0.1234 -> '12,3 %' (French typography, true minus sign)."""
    return f"{_fr_number(x * 100, digits)}{NBSP}%"


def format_num(x: float, digits: int = 2) -> str:
    return _fr_number(x, digits)


def format_cad(x: float) -> str:
    return f"{_fr_number(x, 0)}{NBSP}$"


def format_value(ev: dict[str, Any]) -> str:
    """Human rendering of an evidence value, driven by its unit."""
    value, unit = ev.get("value"), ev.get("unit")
    if value is None:
        return "n.d."
    if isinstance(value, str):
        return value
    if unit == "fraction":
        return format_pct(value)
    if unit == "days":
        return f"{_fr_number(value, 0)}{NBSP}jours"
    if unit == "CAD":
        return f"{_fr_number(value, 0)}{NBSP}$"
    if unit == "count":
        return _fr_number(value, 0)
    if unit == "correlation" or unit == "score":
        return _fr_number(value, 2)
    return _fr_number(value, 2) + (f"{NBSP}{unit}" if unit else "")


def render_template(template: str, registry: EvidenceRegistry) -> tuple[str, list[str], list[str]]:
    """Replace `{{ev_id}}` markers by formatted values.

    Returns (rendered text, cited evidence ids, unknown ids). Unknown markers are
    left as '[?]' so the guardian can flag the claim.
    """
    cited: list[str] = []
    unknown: list[str] = []

    def sub(m: re.Match[str]) -> str:
        ev_id = m.group(1)
        ev = registry.get(ev_id)
        if ev is None:
            unknown.append(ev_id)
            return "[?]"
        if ev_id not in cited:
            cited.append(ev_id)
        return format_value(ev)

    return EV_MARKER.sub(sub, template), cited, unknown
