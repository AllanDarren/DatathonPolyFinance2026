"""Export the Pydantic contract models (core/models.py) to one JSON Schema bundle.

Usage: python -m tools.export_schemas [--check]

Writes `contracts/alphaforge.schema.json`: every contract type lives once under
`$defs/<Name>` (e.g. `alphaforge.schema.json#/$defs/FeedResponse`). A single bundle
keeps each type declared exactly once, which `json-schema-to-typescript` (web/) needs.
`--check` fails if the file on disk is stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic.json_schema import models_json_schema

from core.models import CONTRACT_VERSION, TOP_LEVEL
from core.rules_models import RULE_FILES

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = ROOT / "contracts"
BUNDLE = CONTRACTS_DIR / "alphaforge.schema.json"
RULES_SCHEMAS_DIR = CONTRACTS_DIR / "rules"


def _strip_property_titles(node: Any, parent_key: str | None = None) -> Any:
    """Drop per-property titles: they would generate noisy TS aliases."""
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                out[key] = {
                    k: {kk: _strip_property_titles(vv) for kk, vv in v.items() if kk != "title"}
                    for k, v in value.items()
                }
            else:
                out[key] = _strip_property_titles(value, key)
        return out
    if isinstance(node, list):
        return [_strip_property_titles(v, parent_key) for v in node]
    return node


def build_bundle() -> dict[str, Any]:
    _, raw = models_json_schema([(m, "validation") for m in TOP_LEVEL], by_alias=True)
    defs = _strip_property_titles(raw["$defs"])
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "alphaforge.schema.json",
        "title": "AlphaForgeContract",
        "description": f"AlphaForge AI contracts v{CONTRACT_VERSION}. Generated from core/models.py; do not edit by hand.",
        "x-contract-version": CONTRACT_VERSION,
        "anyOf": [{"$ref": f"#/$defs/{m.__name__}"} for m in TOP_LEVEL],
        "$defs": dict(sorted(defs.items())),
    }


def render() -> str:
    return json.dumps(build_bundle(), indent=2, ensure_ascii=False) + "\n"


def render_rules() -> dict[Path, str]:
    """One schema per rule file of role D: contracts/rules/<file>.schema.json."""
    out = {}
    for name, model in RULE_FILES.items():
        schema = model.model_json_schema(mode="validation")
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"{name}.schema.json",
                  "description": f"Format of rules/{name} (role D). Generated from core/rules_models.py.",
                  **_strip_property_titles(schema)}
        out[RULES_SCHEMAS_DIR / f"{name.removesuffix('.yaml')}.schema.json"] = (
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
    return out


def all_files() -> dict[Path, str]:
    return {BUNDLE: render(), **render_rules()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if contracts/ is out of date")
    args = parser.parse_args()
    files = all_files()
    stale = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
    if args.check:
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)} (run python -m tools.export_schemas)")
        return 1 if stale else 0
    RULES_SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    for p, text in files.items():
        p.write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} schema files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
