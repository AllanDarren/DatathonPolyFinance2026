"""LLM client interface.

`LLMClient.complete(system, messages, json_schema) -> dict` always returns a JSON
object that matches `json_schema`. The LLM never computes numbers nor decides
verdicts: it classifies headlines and drafts text from evidence.

Providers (env `LLM_PROVIDER`): `mock` (default, deterministic, no network) or
`bedrock` (implemented in A5; model and region come from `BEDROCK_MODEL_ID` and
`BEDROCK_REGION`).
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from typing import Any, Protocol

Message = dict[str, str]  # {"role": "user" | "assistant", "content": "..."}


class LLMUnavailableError(RuntimeError):
    """Raised when the model cannot be reached or returns invalid output."""

    code = "LLM_UNAVAILABLE"


class LLMClient(Protocol):
    model_id: str

    def complete(self, system: str, messages: list[Message], json_schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object matching `json_schema`."""
        ...


Responder = Callable[[str, list[Message], dict[str, Any]], dict[str, Any]]


def _default_for(schema: dict[str, Any]) -> Any:
    """Minimal deterministic value that satisfies a simple JSON Schema."""
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    if "anyOf" in schema:
        return _default_for(schema["anyOf"][0])
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "null")
    if kind == "object":
        props = schema.get("properties", {})
        return {k: _default_for(v) for k, v in props.items() if k in schema.get("required", props.keys())}
    if kind == "array":
        return []
    if kind == "string":
        return ""
    if kind in ("number", "integer"):
        return schema.get("minimum", 0)
    if kind == "boolean":
        return False
    return None


class MockClient:
    """Deterministic offline client for tests and local development.

    Pass `responder` to script answers; otherwise it returns the minimal object
    satisfying the schema. Every call is recorded in `calls`.
    """

    model_id = "mock"

    def __init__(self, responder: Responder | None = None) -> None:
        self.responder = responder
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, messages: list[Message], json_schema: dict[str, Any]) -> dict[str, Any]:
        digest = hashlib.sha256(json.dumps([system, messages], sort_keys=True).encode()).hexdigest()[:12]
        self.calls.append({"system": system, "messages": messages, "schema": json_schema, "digest": digest})
        if self.responder is not None:
            return self.responder(system, messages, json_schema)
        return _default_for(json_schema)


def get_client() -> LLMClient:
    """Build the client selected by `LLM_PROVIDER`."""
    provider = os.environ.get("LLM_PROVIDER", "mock")
    if provider == "mock":
        return MockClient()
    if provider == "bedrock":
        raise LLMUnavailableError("BedrockClient arrives in A5")
    raise ValueError(f"unknown LLM_PROVIDER: {provider!r}")
