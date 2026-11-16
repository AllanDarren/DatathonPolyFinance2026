"""Per-user routes (/me...): identity from the token only, isolation, persistence, DynamoDB + S3 backend.

Offline: LocalUserStore on a temp dir, and AwsUserStore against moto (no real AWS).
"""

from __future__ import annotations

import json
import os

os.environ["LLM_PROVIDER"] = "mock"
os.environ.pop("DATA_BUCKET", None)

import pytest  # noqa: E402

from api import users  # noqa: E402
from api.routes import dispatch, route_key  # noqa: E402

CSV = "ticker,montant\nXBB.TO,40000\nRY.TO,15000\nFTS.TO,12000\n"


@pytest.fixture(autouse=True)
def local_store(tmp_path):
    users.set_store(users.LocalUserStore(tmp_path))
    yield
    users.set_store(None)


@pytest.fixture(scope="module")
def robert() -> dict:
    personas = dispatch("GET", "/personas", None, None).body
    return next(p for p in personas if p["id"] == "robert")


def _flow(user: str, robert: dict) -> dict:
    r = dispatch("PUT", "/me/profile", None, json.dumps({"profile": robert["profile"], "persona_id": "robert"}), user_id=user)
    assert r.status == 200, r.body
    r = dispatch("PUT", "/me/portfolio", None, json.dumps({"csv": CSV}), user_id=user)
    assert r.status == 200, r.body
    feed = dispatch("POST", "/feed", None, json.dumps({"profile": robert["profile"], "portfolio": r.body["portfolio"]})).body
    r = dispatch("POST", "/me/briefs", None, json.dumps({"feed": feed}), user_id=user)
    assert r.status == 201, r.body
    return r.body


def test_me_requires_identity() -> None:
    for method, path in [("GET", "/me"), ("PUT", "/me/profile"), ("PUT", "/me/portfolio"),
                         ("POST", "/me/briefs"), ("GET", "/me/briefs/20261115T000000000Z"), ("DELETE", "/me")]:
        r = dispatch(method, path, None, "{}")
        assert r.status == 401 and r.body["error"]["code"] == "UNAUTHORIZED", (method, path)


def test_empty_account() -> None:
    r = dispatch("GET", "/me", None, None, user_id="u-new")
    assert r.status == 200
    assert r.body["profile"] is None and r.body["portfolio"] is None and r.body["briefs"] == []


def test_data_survives_reconnection(robert: dict) -> None:
    meta = _flow("u-1", robert)
    me = dispatch("GET", "/me", None, None, user_id="u-1").body  # a later session, same identity
    assert me["profile"] == robert["profile"] and me["persona_id"] == "robert"
    assert me["portfolio_csv"] == CSV
    assert [p["ticker"] for p in me["portfolio"]["positions"]][:1] == ["XBB.TO"]
    assert me["briefs"][0]["brief_id"] == meta["brief_id"] and me["briefs"][0]["shown"] >= 1
    brief = dispatch("GET", f"/me/briefs/{meta['brief_id']}", None, None, user_id="u-1")
    assert brief.status == 200 and brief.body["profile"]["profile_id"] == "robert"


def test_users_are_isolated(robert: dict) -> None:
    meta = _flow("u-a", robert)
    other = dispatch("GET", "/me", None, None, user_id="u-b").body
    assert other["profile"] is None and other["briefs"] == []
    r = dispatch("GET", f"/me/briefs/{meta['brief_id']}", None, None, user_id="u-b")
    assert r.status == 404


def test_identity_in_body_is_ignored(robert: dict) -> None:
    body = {"profile": robert["profile"], "user_id": "u-victim"}
    r = dispatch("PUT", "/me/profile", None, json.dumps(body), user_id="u-attacker")
    assert r.status == 200
    assert dispatch("GET", "/me", None, None, user_id="u-victim").body["profile"] is None


def test_validation_errors() -> None:
    r = dispatch("PUT", "/me/profile", None, json.dumps({"profile": {"x": 1}}), user_id="u")
    assert r.status == 400 and r.body["error"]["code"] == "INVALID_REQUEST"
    r = dispatch("PUT", "/me/portfolio", None, json.dumps({"csv": "pas,un,csv"}), user_id="u")
    assert r.status == 400
    r = dispatch("POST", "/me/briefs", None, json.dumps({"feed": {}}), user_id="u")
    assert r.status == 400
    r = dispatch("GET", "/me/briefs/../../etc", None, None, user_id="u")
    assert r.status == 404


def test_brief_history_is_capped(robert: dict) -> None:
    feed = dispatch("POST", "/feed", None, json.dumps({
        "profile": robert["profile"],
        "portfolio": dispatch("POST", "/portfolio/parse", None, json.dumps({"csv": CSV})).body})).body
    for _ in range(users.MAX_BRIEFS + 2):
        assert dispatch("POST", "/me/briefs", None, json.dumps({"feed": feed}), user_id="u-cap").status == 201
    assert len(dispatch("GET", "/me", None, None, user_id="u-cap").body["briefs"]) == users.MAX_BRIEFS


def test_delete_account_data(robert: dict) -> None:
    _flow("u-del", robert)
    assert dispatch("DELETE", "/me", None, None, user_id="u-del").status == 204
    me = dispatch("GET", "/me", None, None, user_id="u-del").body
    assert me["profile"] is None and me["briefs"] == []


def test_route_keys_never_contain_ids() -> None:
    assert route_key("GET", "/me/briefs/20261115T000000000Z") == "GET /me/briefs/{id}"
    assert route_key("PUT", "/me/portfolio") == "PUT /me/portfolio"


def test_lambda_reads_identity_from_jwt_claims(robert: dict) -> None:
    from api.handler import lambda_handler

    def event(sub: str | None) -> dict:
        ctx: dict = {"http": {"method": "GET", "path": "/me"}}
        if sub:
            ctx["authorizer"] = {"jwt": {"claims": {"sub": sub}}}
        return {"rawPath": "/me", "requestContext": ctx}

    dispatch("PUT", "/me/profile", None, json.dumps({"profile": robert["profile"]}), user_id="sub-123")
    out = lambda_handler(event("sub-123"), None)
    assert out["statusCode"] == 200 and json.loads(out["body"])["profile"]["profile_id"] == "robert"
    assert lambda_handler(event(None), None)["statusCode"] == 401


def test_aws_store_dynamodb_and_s3(robert: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    moto = pytest.importorskip("moto")
    import boto3

    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "testing")
    with moto.mock_aws():
        boto3.client("dynamodb").create_table(
            TableName="users", BillingMode="PAY_PER_REQUEST",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}, {"AttributeName": "sk", "AttributeType": "S"}])
        boto3.client("s3").create_bucket(Bucket="user-bucket")
        users.set_store(users.AwsUserStore("users", "user-bucket"))
        meta = _flow("sub-aws", robert)
        me = dispatch("GET", "/me", None, None, user_id="sub-aws").body
        assert me["profile"] == robert["profile"] and me["portfolio_csv"] == CSV
        assert me["briefs"][0]["brief_id"] == meta["brief_id"]
        keys = [o["Key"] for o in boto3.client("s3").list_objects_v2(Bucket="user-bucket")["Contents"]]
        assert "users/sub-aws/portfolio.csv" in keys and f"users/sub-aws/briefs/{meta['brief_id']}.json" in keys
        assert dispatch("DELETE", "/me", None, None, user_id="sub-aws").status == 204
        assert "Contents" not in boto3.client("s3").list_objects_v2(Bucket="user-bucket")


def test_local_server_me_routes(robert: dict) -> None:
    from fastapi.testclient import TestClient

    from api.local_server import app

    c = TestClient(app)
    assert c.get("/me").status_code == 401
    h = {"Authorization": "Bearer local.dev-user", "Origin": "http://localhost:5173"}
    assert c.put("/me/profile", json={"profile": robert["profile"]}, headers=h).status_code == 200
    r = c.get("/me", headers=h)
    assert r.status_code == 200 and r.json()["profile"]["profile_id"] == "robert"
    pre = c.options("/me/profile", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT",
                                            "Access-Control-Request-Headers": "authorization,content-type"})
    assert pre.status_code == 200 and "authorization" in pre.headers["access-control-allow-headers"].lower()
    assert c.get("/me", headers={"Authorization": "Bearer local.../bad"}).status_code == 401
