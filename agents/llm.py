"""LLM clients.

`LLMClient.complete(system, messages, json_schema) -> dict` always returns a JSON
object validated against `json_schema` (structured output via a forced tool call).
`LLMClient.converse(system, messages, tools)` runs one Converse turn with tools
(used by the orchestrator agent).

The LLM never computes numbers nor decides verdicts: it classifies headlines and
drafts text from evidence.

Providers (env `LLM_PROVIDER`): `mock` (default, deterministic, no network) or
`bedrock` (model and region from `BEDROCK_MODEL_ID` and `BEDROCK_REGION`; never guessed).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from typing import Any, Protocol

import jsonschema

Message = dict[str, str]  # {"role": "user" | "assistant", "content": "..."}
ConverseMessage = dict[str, Any]  # Bedrock Converse format


class LLMUnavailableError(RuntimeError):
    """The model cannot be reached or returned invalid output."""

    code = "LLM_UNAVAILABLE"


class LLMClient(Protocol):
    model_id: str

    def complete(self, system: str, messages: list[Message], json_schema: dict[str, Any]) -> dict[str, Any]:
        ...

    def converse(self, system: str, messages: list[ConverseMessage], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Return {"message": <assistant ConverseMessage>, "stop_reason": str}."""
        ...


Responder = Callable[[str, list[Message], dict[str, Any]], dict[str, Any]]
Planner = Callable[[str, list[ConverseMessage], list[dict[str, Any]]], dict[str, Any]]


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


def _to_converse(messages: list[Message]) -> list[ConverseMessage]:
    return [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages]


class MockClient:
    """Deterministic offline client for tests and local development.

    `responder` scripts `complete`; `planner` scripts `converse`. Without them,
    `complete` returns the minimal object satisfying the schema and `converse`
    ends the turn. Every call is recorded in `calls`.
    """

    model_id = "mock"

    def __init__(self, responder: Responder | None = None, planner: Planner | None = None,
                 model_id: str | None = None) -> None:
        self.responder = responder
        self.planner = planner
        if model_id:
            self.model_id = model_id
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: str, messages: list[Message], json_schema: dict[str, Any]) -> dict[str, Any]:
        digest = hashlib.sha256(json.dumps([system, messages], sort_keys=True).encode()).hexdigest()[:12]
        self.calls.append({"kind": "complete", "system": system, "messages": messages, "schema": json_schema,
                           "digest": digest})
        out = self.responder(system, messages, json_schema) if self.responder else _default_for(json_schema)
        jsonschema.validate(out, json_schema)
        return out

    def converse(self, system: str, messages: list[ConverseMessage], tools: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls.append({"kind": "converse", "system": system, "messages": messages, "tools": tools})
        if self.planner:
            return self.planner(system, messages, tools)
        return {"message": {"role": "assistant", "content": [{"text": "done"}]}, "stop_reason": "end_turn"}


class BedrockClient:
    """Amazon Bedrock Converse API client (temperature 0, limited retries, timeout)."""

    def __init__(self, model_id: str | None = None, region: str | None = None, *, timeout: float = 25,
                 max_attempts: int = 2, max_tokens: int = 1024, client: Any = None) -> None:
        self.model_id = model_id or os.environ.get("BEDROCK_MODEL_ID", "")
        self.region = region or os.environ.get("BEDROCK_REGION", "")
        if not self.model_id or not self.region:
            raise LLMUnavailableError("BEDROCK_MODEL_ID et BEDROCK_REGION doivent être définis (voir docs/AWS_STATUS.md).")
        self.max_attempts = max_attempts
        self.max_tokens = max_tokens
        self.use_temperature = True  # temperature 0 when the model accepts it (reproducibility)
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client("bedrock-runtime", region_name=self.region,
                                  config=Config(read_timeout=timeout, connect_timeout=5,
                                                retries={"max_attempts": 1, "mode": "standard"}))
        self._client = client

    def _call(self, **kwargs: Any) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(self.max_attempts):
            inference: dict[str, Any] = {"maxTokens": self.max_tokens}
            if self.use_temperature:
                inference["temperature"] = 0
            try:
                return dict(self._client.converse(modelId=self.model_id, inferenceConfig=inference, **kwargs))
            except Exception as exc:  # noqa: BLE001 - botocore errors vary; all mean "unavailable"
                last = exc
                err = getattr(exc, "response", {}).get("Error", {})
                code, message = err.get("Code", ""), str(err.get("Message", "")).lower()
                if code == "ValidationException" and "temperature" in message and self.use_temperature:
                    # Some models reject `temperature` (e.g. claude-haiku-5-5): retry once without it.
                    self.use_temperature = False
                    continue
                if code in ("ValidationException", "AccessDeniedException", "ResourceNotFoundException"):
                    break  # not transient
                time.sleep(0.5 * (attempt + 1))
        raise LLMUnavailableError(f"Bedrock indisponible: {type(last).__name__}: {last}") from last

    def complete(self, system: str, messages: list[Message], json_schema: dict[str, Any]) -> dict[str, Any]:
        tool = {"toolSpec": {"name": "respond", "description": "Return the answer as structured JSON.",
                             "inputSchema": {"json": json_schema}}}
        try:
            resp = self._call(system=[{"text": system}], messages=_to_converse(messages),
                              toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": "respond"}}})
        except LLMUnavailableError:
            # Some models do not support a forced tool choice: retry with "any".
            resp = self._call(system=[{"text": system}], messages=_to_converse(messages),
                              toolConfig={"tools": [tool], "toolChoice": {"any": {}}})
        content = resp.get("output", {}).get("message", {}).get("content", [])
        payload = next((c["toolUse"]["input"] for c in content if "toolUse" in c), None)
        if payload is None:
            text = "".join(c.get("text", "") for c in content).strip()
            try:
                payload = json.loads(text[text.find("{"): text.rfind("}") + 1])
            except ValueError as exc:
                raise LLMUnavailableError("Réponse du modèle sans JSON exploitable.") from exc
        try:
            jsonschema.validate(payload, json_schema)
        except jsonschema.ValidationError as exc:
            raise LLMUnavailableError(f"Réponse du modèle hors schéma: {exc.message}") from exc
        return dict(payload)

    def converse(self, system: str, messages: list[ConverseMessage], tools: list[dict[str, Any]]) -> dict[str, Any]:
        resp = self._call(system=[{"text": system}], messages=messages, toolConfig={"tools": tools})
        return {"message": resp["output"]["message"], "stop_reason": resp.get("stopReason", "")}


def get_client() -> LLMClient:
    """Build the client selected by `LLM_PROVIDER` (default: mock)."""
    provider = os.environ.get("LLM_PROVIDER", "mock")
    if provider == "mock":
        return MockClient()
    if provider == "bedrock":
        return BedrockClient()
    raise ValueError(f"unknown LLM_PROVIDER: {provider!r}")
