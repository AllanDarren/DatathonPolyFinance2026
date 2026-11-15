"""API layer tests (role B): routing, contract validation, error format, Lambda event, local server.

Run offline with LLM_PROVIDER=mock (set below). No AWS.
"""

from __future__ import annotations

import json
import os

os.environ["LLM_PROVIDER"] = "mock"
os.environ.pop("DATA_BUCKET", None)

import pytest  # noqa: E402

from api import routes  # noqa: E402
from api.routes import dispatch, validate  # noqa: E402


def _ok(name: str, payload: object) -> None:
    validate(name, payload)  # raises ApiError if the response drifts from the contract


@pytest.fixture(scope="module")
def personas() -> list[dict]:
    r = dispatch("GET", "/personas", None, None)
    assert r.status == 200
    return r.body


def _persona(personas: list[dict], pid: str) -> dict:
    return next(p for p in personas if p["id"] == pid)


def _parse(csv: str) -> routes.Response:
    return dispatch("POST", "/portfolio/parse", None, json.dumps({"csv": csv}))


def test_health() -> None:
    r = dispatch("GET", "/health", None, None)
    assert r.status == 200
    _ok("Health", r.body)
    assert r.body["llm_provider"] == "mock"


def test_questionnaire_and_profile() -> None:
    q = dispatch("GET", "/questionnaire", None, None)
    assert q.status == 200 and q.body["questions"]
    answers = {question["id"]: question["options"][-1]["id"] for question in q.body["questions"]}
    r = dispatch("POST", "/profile", None, json.dumps({"answers": answers}))
    assert r.status == 200, r.body
    _ok("Profile", r.body)
    assert r.body["source"] == "questionnaire"


def test_personas_match_contract(personas: list[dict]) -> None:
    assert {p["id"] for p in personas} >= {"amira", "mateo", "robert"}
    for p in personas:
        _ok("Persona", p)


def test_portfolio_parse_valid(personas: list[dict]) -> None:
    r = _parse(_persona(personas, "robert")["sample_portfolio_csv"])
    assert r.status == 200
    _ok("Portfolio", r.body)
    assert abs(sum(p["weight"] for p in r.body["positions"] if p["in_universe"]) - 1) < 1e-6


@pytest.mark.parametrize("csv", ["", "ticker;montant\nSPY;100", "ticker,montant\nSPY,-5"])
def test_portfolio_parse_errors_use_error_contract(csv: str) -> None:
    r = _parse(csv)
    assert 400 <= r.status < 500
    _ok("ErrorResponse", r.body)
    assert r.error_code == r.body["error"]["code"]


def test_feed_robert_with_consideration(personas: list[dict]) -> None:
    robert = _persona(personas, "robert")
    portfolio = _parse(robert["sample_portfolio_csv"]).body
    body = {"profile": robert["profile"], "portfolio": portfolio,
            "consideration": {"ticker": "NVDA", "intended_weight": 0.20}}
    r = dispatch("POST", "/feed", None, json.dumps(body))
    assert r.status == 200, r.body
    _ok("FeedResponse", r.body)
    assert r.body["coherence"]["verdict"] in ("tension", "incoherent")
    assert r.body["items"]
    if r.body["coherence"].get("agent_trace"):
        assert r.tools  # tool names surface for the logs


def test_feed_without_consideration(personas: list[dict]) -> None:
    amira = _persona(personas, "amira")
    portfolio = _parse(amira["sample_portfolio_csv"]).body
    r = dispatch("POST", "/feed", None, json.dumps({"profile": amira["profile"], "portfolio": portfolio}))
    assert r.status == 200
    assert r.body["coherence"] is None


def test_feed_rejects_body_not_matching_contract() -> None:
    r = dispatch("POST", "/feed", None, json.dumps({"profile": {}, "portfolio": {}}))
    assert r.status == 400 and r.body["error"]["code"] == "INVALID_REQUEST"
    _ok("ErrorResponse", r.body)


@pytest.mark.parametrize("body,code", [(None, "INVALID_JSON"), ("{not json", "INVALID_JSON"),
                                       ("x" * (routes.MAX_BODY_BYTES + 1), "PAYLOAD_TOO_LARGE")])
def test_bad_bodies(body: str | None, code: str) -> None:
    r = dispatch("POST", "/profile", None, body)
    assert r.body["error"]["code"] == code


def test_unknown_route_and_method() -> None:
    assert dispatch("GET", "/nope", None, None).status == 404
    r = dispatch("GET", "/feed", None, None)
    assert r.status == 405 and r.body["error"]["details"]["allowed"] == ["POST"]
    assert dispatch("OPTIONS", "/feed", None, None).status == 204


def test_events_filter_and_unknown_ticker() -> None:
    r = dispatch("GET", "/events", {"tickers": "NVDA,RY.TO"}, None)
    assert r.status == 200
    for e in r.body:
        _ok("Event", e)
        assert e["scope"] == "macro" or {"NVDA", "RY.TO"} & set(e["tickers"])
    bad = dispatch("GET", "/events", {"tickers": "ZZZZ"}, None)
    assert bad.status == 400 and bad.body["error"]["code"] == "UNKNOWN_TICKER"


def test_unexpected_exception_is_contained(monkeypatch: pytest.MonkeyPatch) -> None:
    import services

    def boom() -> None:
        raise RuntimeError("secret portfolio content")

    monkeypatch.setattr(services, "get_personas", boom)
    r = dispatch("GET", "/personas", None, None)
    assert r.status == 500 and r.body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in json.dumps(r.body) and "secret" not in " ".join(r.frames)


# --- Lambda handler ---------------------------------------------------------

def _event(method: str, path: str, body: str | None = None, query: dict | None = None) -> dict:
    return {"version": "2.0", "rawPath": path, "queryStringParameters": query, "body": body,
            "isBase64Encoded": False, "requestContext": {"http": {"method": method, "path": path}}}


class _Ctx:
    aws_request_id = "test-req-1"


def test_lambda_handler_roundtrip_and_logs_have_no_portfolio(personas: list[dict],
                                                             capsys: pytest.CaptureFixture[str]) -> None:
    from api.handler import lambda_handler

    csv = "ticker,montant\nSPY,12345.67\nXBB.TO,7654.32\n"
    out = lambda_handler(_event("POST", "/portfolio/parse", json.dumps({"csv": csv})), _Ctx())
    assert out["statusCode"] == 200
    assert out["headers"]["content-type"].startswith("application/json")
    _ok("Portfolio", json.loads(out["body"]))
    logs = capsys.readouterr().out
    line = json.loads([ln for ln in logs.splitlines() if '"event": "request"' in ln][-1])
    assert line["route"] == "POST /portfolio/parse" and line["request_id"] == "test-req-1"
    assert line["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "AlphaForge/API"
    assert "12345" not in logs and "XBB" not in logs


def test_lambda_handler_base64_and_errors() -> None:
    import base64

    from api.handler import lambda_handler

    ev = _event("POST", "/profile", base64.b64encode(b"{bad").decode())
    ev["isBase64Encoded"] = True
    out = lambda_handler(ev, _Ctx())
    assert out["statusCode"] == 400 and json.loads(out["body"])["error"]["code"] == "INVALID_JSON"
    assert lambda_handler(_event("GET", "/health"), _Ctx())["statusCode"] == 200


# --- local server -----------------------------------------------------------

def test_local_server_same_contract_and_cors() -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from api.local_server import app

    client = TestClient(app)
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200 and r.json() == dispatch("GET", "/health", None, None).body
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    pre = client.options("/feed", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200
    bad = client.post("/portfolio/parse", json={"csv": ""})
    assert bad.status_code == 400 and bad.json()["error"]["code"]
    assert client.get("/nope").status_code == 404
