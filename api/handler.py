"""AWS Lambda entry point (API Gateway HTTP API, payload format 2.0).

Thin: translate the HTTP event, call `api.routes.dispatch`, return JSON.
CORS headers are added by API Gateway (CorsConfiguration in infra/template.yaml).

Logs: one JSON line per request (request id, route, status, duration, version,
LLM provider, error code, names of the agent tools called). Never a portfolio,
a CSV, a profile or a headline. The same line carries CloudWatch Embedded Metric
Format fields, so latency and errors per route become CloudWatch metrics without
any extra service.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

from api import bootstrap
from api.routes import dispatch, route_key

APP_VERSION = os.environ.get("APP_VERSION", "dev")
METRIC_NAMESPACE = "AlphaForge/API"

_COLD = True
_INIT_REPORT: dict[str, Any] = {}
try:
    _INIT_REPORT = bootstrap.sync_data_from_s3()
except Exception as exc:  # noqa: BLE001 - the API answers DATA_UNAVAILABLE instead of crashing
    _INIT_REPORT = {"data_source": "error", "error_type": type(exc).__name__}
print(json.dumps({"event": "cold_start", "version": APP_VERSION, **_INIT_REPORT}))


def _log(record: dict[str, Any]) -> None:
    record["_aws"] = {
        "Timestamp": int(time.time() * 1000),
        "CloudWatchMetrics": [{
            "Namespace": METRIC_NAMESPACE,
            "Dimensions": [["route"]],
            "Metrics": [{"Name": "latency_ms", "Unit": "Milliseconds"},
                        {"Name": "server_error", "Unit": "Count"},
                        {"Name": "client_error", "Unit": "Count"}],
        }],
    }
    print(json.dumps(record, ensure_ascii=False))


def _verified_user(event: dict[str, Any]) -> str | None:
    """Cognito `sub` of the caller, as verified by the API Gateway JWT authorizer (signature, issuer,
    audience, expiry). Present only on /me routes, which API Gateway refuses without a valid token."""
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    sub = claims.get("sub")
    return sub if isinstance(sub, str) and sub else None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    global _COLD
    t0 = time.perf_counter()
    http = (event.get("requestContext") or {}).get("http") or {}
    method = http.get("method") or event.get("httpMethod") or "GET"
    path = event.get("rawPath") or http.get("path") or event.get("path") or "/"
    body = event.get("body")
    if body is not None and event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8", errors="replace")

    resp = dispatch(method, path, event.get("queryStringParameters") or {}, body, user_id=_verified_user(event))

    duration = int((time.perf_counter() - t0) * 1000)
    route = route_key(method, path)
    _log({
        "event": "request",
        "request_id": getattr(context, "aws_request_id", None),
        "route": route,
        "status": resp.status,
        "latency_ms": duration,
        "server_error": 1 if resp.status >= 500 else 0,
        "client_error": 1 if 400 <= resp.status < 500 else 0,
        "error_code": resp.error_code,
        "tools": resp.tools,
        "cold_start": _COLD,
        "version": APP_VERSION,
        "llm_provider": os.environ.get("LLM_PROVIDER", "mock"),
    })
    if resp.frames:
        # Stack frames only (file, line, function): no exception message, no local values.
        print(json.dumps({"event": "internal_error", "request_id": getattr(context, "aws_request_id", None),
                          "route": route, "frames": resp.frames}))
    _COLD = False

    headers = {"content-type": "application/json; charset=utf-8", "x-alphaforge-version": APP_VERSION,
               "cache-control": "no-store"}
    if resp.status == 204 or resp.body is None:
        return {"statusCode": resp.status, "headers": headers, "body": ""}
    return {"statusCode": resp.status, "headers": headers,
            "body": json.dumps(resp.body, ensure_ascii=False, separators=(",", ":"))}
