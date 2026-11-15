"""HTTP routing shared by the Lambda handler and the local server (same contract everywhere).

Thin layer only: parse the request, validate the body against the JSON Schemas of
contracts/, call `services`, map errors to `{error: {code, message, details?}}`.
No business logic here.
"""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = ROOT / "contracts" / "alphaforge.schema.json"
MAX_BODY_BYTES = 512 * 1024  # a portfolio CSV or a feed request is a few KB


@dataclass
class Response:
    status: int
    body: Any
    # Names of the agent tools called while serving the request (for logs; never their params).
    tools: list[str] = field(default_factory=list)
    error_code: str | None = None
    # For unexpected errors only: stack frames (file:line function), never the message or locals.
    frames: list[str] = field(default_factory=list)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            err["details"] = self.details
        return {"error": err}


@cache
def _schema_doc() -> dict[str, Any]:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


@cache
def _validator(name: str) -> jsonschema.protocols.Validator:
    doc = _schema_doc()
    schema = {"$schema": doc.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
              "$defs": doc["$defs"], "$ref": f"#/$defs/{name}"}
    cls = jsonschema.validators.validator_for(schema)
    return cls(schema)


def validate(name: str, payload: Any) -> None:
    """Raise ApiError(400, INVALID_REQUEST) if `payload` does not match contract `name`."""
    errors = sorted(_validator(name).iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        where = "/".join(str(p) for p in first.absolute_path) or "(racine)"
        raise ApiError(400, "INVALID_REQUEST", f"Requête invalide ({name}) au champ « {where} ».",
                       {"field": where, "reason": first.message[:300], "errors": len(errors)})


def _parse_json(body: str | None) -> Any:
    if body is None or body.strip() == "":
        raise ApiError(400, "INVALID_JSON", "Corps de requête vide: un objet JSON est attendu.")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", f"Requête trop volumineuse (maximum {MAX_BODY_BYTES // 1024} Ko).")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ApiError(400, "INVALID_JSON", "Le corps de la requête n'est pas du JSON valide.",
                       {"line": exc.lineno, "column": exc.colno}) from None


# --- handlers --------------------------------------------------------------

def _services():  # imported lazily so the Lambda can set DATA_DIR before core/ loads
    import services

    return services


def _health(_q: dict[str, str], _b: Any) -> Response:
    return Response(200, _services().health())


def _questionnaire(_q: dict[str, str], _b: Any) -> Response:
    return Response(200, _services().get_questionnaire())


def _personas(_q: dict[str, str], _b: Any) -> Response:
    return Response(200, _services().get_personas())


def _profile(_q: dict[str, str], body: Any) -> Response:
    validate("ProfileRequest", body)
    return Response(200, _services().score_profile(body["answers"], body.get("confirmed_preferences")))


def _preferences(_q: dict[str, str], body: Any) -> Response:
    validate("PreferenceExtractRequest", body)
    return Response(200, _services().extract_preferences(body["text"]))


def _portfolio(_q: dict[str, str], body: Any) -> Response:
    validate("PortfolioParseRequest", body)
    return Response(200, _services().parse_portfolio(body["csv"]))


def _feed(_q: dict[str, str], body: Any) -> Response:
    validate("FeedRequest", body)
    out = _services().build_feed(body["profile"], body["portfolio"], body.get("consideration"))
    trace = ((out or {}).get("coherence") or {}).get("agent_trace") or []
    return Response(200, out, tools=[str(t.get("tool")) for t in trace if isinstance(t, dict)])


def _events(query: dict[str, str], _b: Any) -> Response:
    raw = query.get("tickers", "")
    tickers = [t.strip() for t in raw.split(",") if t.strip()] or None
    return Response(200, _services().get_events(tickers))


Handler = Callable[[dict[str, str], Any], Response]

# (method, path) -> (handler, has_json_body)
ROUTES: dict[tuple[str, str], tuple[Handler, bool]] = {
    ("GET", "/health"): (_health, False),
    ("GET", "/questionnaire"): (_questionnaire, False),
    ("GET", "/personas"): (_personas, False),
    ("POST", "/profile"): (_profile, True),
    ("POST", "/portfolio/parse"): (_portfolio, True),
    ("POST", "/feed"): (_feed, True),
    ("POST", "/preferences/extract"): (_preferences, True),
    ("GET", "/events"): (_events, False),
}
PATHS = {p for _, p in ROUTES}


def route_key(method: str, path: str) -> str:
    """Stable label for logs and metrics (never contains user data)."""
    path = "/" + path.strip("/")
    return f"{method.upper()} {path}" if path in PATHS else "UNMATCHED"


def dispatch(method: str, path: str, query: dict[str, str] | None, body: str | None) -> Response:
    """Serve one request. Never raises: every failure becomes a contract error body."""
    method = method.upper()
    path = "/" + (path or "").strip("/")
    try:
        if method == "OPTIONS":  # CORS preflight is answered by API Gateway / middleware; be lenient
            return Response(204, None)
        entry = ROUTES.get((method, path))
        if entry is None:
            if path in PATHS:
                allowed = sorted(m for m, p in ROUTES if p == path)
                raise ApiError(405, "METHOD_NOT_ALLOWED", f"Méthode {method} non permise sur {path}.", {"allowed": allowed})
            raise ApiError(404, "NOT_FOUND", f"Route inconnue: {path}.")
        handler, has_body = entry
        payload = _parse_json(body) if has_body else None
        return handler(query or {}, payload)
    except ApiError as exc:
        return Response(exc.status, exc.body(), error_code=exc.code)
    except Exception as exc:  # noqa: BLE001 - mapped to the error contract below
        return _map_exception(exc)


def _map_exception(exc: Exception) -> Response:
    from core.errors import AlphaForgeError

    if isinstance(exc, AlphaForgeError):
        return Response(exc.status, exc.to_dict(), error_code=exc.code)
    try:
        from agents.llm import LLMUnavailableError

        if isinstance(exc, LLMUnavailableError):
            return Response(503, {"error": {"code": "LLM_UNAVAILABLE",
                                            "message": "Le modèle de langage est indisponible. Réessaie dans un instant."}},
                            error_code="LLM_UNAVAILABLE")
    except ImportError:
        pass
    # Unexpected: the message may contain user data, so it is neither returned nor logged.
    frames = [f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in traceback.extract_tb(exc.__traceback__)][-10:]
    return Response(500, {"error": {"code": "INTERNAL_ERROR", "message": "Erreur interne du serveur.",
                                    "details": {"type": type(exc).__name__}}},
                    error_code="INTERNAL_ERROR", frames=frames)
