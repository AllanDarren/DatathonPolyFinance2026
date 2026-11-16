"""Per-user storage: investor profile, uploaded portfolio (CSV) and latest briefs.

Identity comes ONLY from the verified token (API Gateway JWT authorizer -> Cognito `sub`),
never from the request body. Two backends, same interface:

- `AwsUserStore` (Lambda): DynamoDB table `USER_TABLE` + S3 bucket `USER_BUCKET`.
    DynamoDB  pk=user_id  sk=PROFILE    -> {profile, persona_id, updated_at}
              pk=user_id  sk=PORTFOLIO  -> {portfolio (parsed), csv_key, updated_at}
              pk=user_id  sk=BRIEF#<ts> -> {brief_id, generated_at, saved_at, shown, hidden, s3_key}
    S3        users/<user_id>/portfolio.csv
              users/<user_id>/briefs/<brief_id>.json
- `LocalUserStore` (make dev, tests): the same layout as JSON files under a local directory.

Only what the user types or uploads is stored (simulation, no bank data). Nothing here is logged.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

MAX_BRIEFS = 10
_BRIEF_ID = re.compile(r"^[0-9]{8}T[0-9]{6}[0-9]{3}Z$")
_USER_ID = re.compile(r"^[A-Za-z0-9._@+-]{1,128}$")


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_brief_id() -> str:
    d = datetime.now(UTC)
    return d.strftime("%Y%m%dT%H%M%S") + f"{d.microsecond // 1000:03d}Z"


def valid_brief_id(brief_id: str) -> bool:
    return bool(_BRIEF_ID.match(brief_id))


def check_user_id(user_id: str) -> str:
    if not _USER_ID.match(user_id or ""):
        raise ValueError("invalid user id")
    return user_id


class UserStore(Protocol):
    def get_profile(self, user_id: str) -> dict[str, Any] | None: ...
    def put_profile(self, user_id: str, record: dict[str, Any]) -> None: ...
    def get_portfolio(self, user_id: str) -> dict[str, Any] | None: ...
    def put_portfolio(self, user_id: str, csv_text: str, record: dict[str, Any]) -> None: ...
    def get_portfolio_csv(self, user_id: str) -> str | None: ...
    def list_briefs(self, user_id: str) -> list[dict[str, Any]]: ...
    def put_brief(self, user_id: str, meta: dict[str, Any], brief: dict[str, Any]) -> None: ...
    def get_brief(self, user_id: str, brief_id: str) -> dict[str, Any] | None: ...
    def delete_user(self, user_id: str) -> None: ...


# ---------------------------------------------------------------- local (files)

class LocalUserStore:
    """Files under `root/<user_id>/`. For `make dev` and tests only."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _dir(self, user_id: str) -> Path:
        d = self.root / check_user_id(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _read(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _write(self, path: Path, obj: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        return self._read(self._dir(user_id) / "profile.json")

    def put_profile(self, user_id: str, record: dict[str, Any]) -> None:
        self._write(self._dir(user_id) / "profile.json", record)

    def get_portfolio(self, user_id: str) -> dict[str, Any] | None:
        return self._read(self._dir(user_id) / "portfolio.json")

    def put_portfolio(self, user_id: str, csv_text: str, record: dict[str, Any]) -> None:
        d = self._dir(user_id)
        (d / "portfolio.csv").write_text(csv_text, encoding="utf-8")
        self._write(d / "portfolio.json", record)

    def get_portfolio_csv(self, user_id: str) -> str | None:
        p = self._dir(user_id) / "portfolio.csv"
        return p.read_text(encoding="utf-8") if p.exists() else None

    def list_briefs(self, user_id: str) -> list[dict[str, Any]]:
        return self._read(self._dir(user_id) / "briefs.json") or []

    def put_brief(self, user_id: str, meta: dict[str, Any], brief: dict[str, Any]) -> None:
        d = self._dir(user_id)
        self._write(d / "briefs" / f"{meta['brief_id']}.json", brief)
        metas = [meta, *self.list_briefs(user_id)]
        for old in metas[MAX_BRIEFS:]:
            (d / "briefs" / f"{old['brief_id']}.json").unlink(missing_ok=True)
        self._write(d / "briefs.json", metas[:MAX_BRIEFS])

    def get_brief(self, user_id: str, brief_id: str) -> dict[str, Any] | None:
        return self._read(self._dir(user_id) / "briefs" / f"{brief_id}.json")

    def delete_user(self, user_id: str) -> None:
        shutil.rmtree(self.root / check_user_id(user_id), ignore_errors=True)


# ---------------------------------------------------------------- AWS (DynamoDB + S3)

class AwsUserStore:
    def __init__(self, table: str, bucket: str) -> None:
        import boto3

        self.table = boto3.resource("dynamodb").Table(table)
        self.s3 = boto3.client("s3")
        self.bucket = bucket

    @staticmethod
    def _prefix(user_id: str) -> str:
        return f"users/{check_user_id(user_id)}/"

    def _get(self, user_id: str, sk: str) -> dict[str, Any] | None:
        item = self.table.get_item(Key={"user_id": check_user_id(user_id), "sk": sk}).get("Item")
        return json.loads(item["data"]) if item else None

    def _put(self, user_id: str, sk: str, record: dict[str, Any]) -> None:
        # Stored as a JSON string: no float -> Decimal conversion, exact round trip.
        self.table.put_item(Item={"user_id": check_user_id(user_id), "sk": sk,
                                  "data": json.dumps(record, ensure_ascii=False)})

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        return self._get(user_id, "PROFILE")

    def put_profile(self, user_id: str, record: dict[str, Any]) -> None:
        self._put(user_id, "PROFILE", record)

    def get_portfolio(self, user_id: str) -> dict[str, Any] | None:
        return self._get(user_id, "PORTFOLIO")

    def put_portfolio(self, user_id: str, csv_text: str, record: dict[str, Any]) -> None:
        key = self._prefix(user_id) + "portfolio.csv"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=csv_text.encode("utf-8"),
                           ContentType="text/csv; charset=utf-8")
        self._put(user_id, "PORTFOLIO", {**record, "csv_key": key})

    def get_portfolio_csv(self, user_id: str) -> str | None:
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self._prefix(user_id) + "portfolio.csv")
        except self.s3.exceptions.NoSuchKey:
            return None
        return obj["Body"].read().decode("utf-8")

    def list_briefs(self, user_id: str) -> list[dict[str, Any]]:
        from boto3.dynamodb.conditions import Key

        res = self.table.query(
            KeyConditionExpression=Key("user_id").eq(check_user_id(user_id)) & Key("sk").begins_with("BRIEF#"),
            ScanIndexForward=False, Limit=MAX_BRIEFS)
        return [json.loads(i["data"]) for i in res.get("Items", [])]

    def put_brief(self, user_id: str, meta: dict[str, Any], brief: dict[str, Any]) -> None:
        key = self._prefix(user_id) + f"briefs/{meta['brief_id']}.json"
        self.s3.put_object(Bucket=self.bucket, Key=key, ContentType="application/json",
                           Body=json.dumps(brief, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        self._put(user_id, f"BRIEF#{meta['brief_id']}", {**meta, "s3_key": key})
        # Keep the latest MAX_BRIEFS only.
        from boto3.dynamodb.conditions import Key

        res = self.table.query(
            KeyConditionExpression=Key("user_id").eq(user_id) & Key("sk").begins_with("BRIEF#"),
            ScanIndexForward=False, ProjectionExpression="sk")
        for item in res.get("Items", [])[MAX_BRIEFS:]:
            old_id = item["sk"].removeprefix("BRIEF#")
            self.s3.delete_object(Bucket=self.bucket, Key=self._prefix(user_id) + f"briefs/{old_id}.json")
            self.table.delete_item(Key={"user_id": user_id, "sk": item["sk"]})

    def get_brief(self, user_id: str, brief_id: str) -> dict[str, Any] | None:
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=self._prefix(user_id) + f"briefs/{brief_id}.json")
        except self.s3.exceptions.NoSuchKey:
            return None
        return json.loads(obj["Body"].read())

    def delete_user(self, user_id: str) -> None:
        from boto3.dynamodb.conditions import Key

        prefix = self._prefix(user_id)
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objs})
        res = self.table.query(KeyConditionExpression=Key("user_id").eq(user_id), ProjectionExpression="sk")
        with self.table.batch_writer() as batch:
            for item in res.get("Items", []):
                batch.delete_item(Key={"user_id": user_id, "sk": item["sk"]})


_STORE: UserStore | None = None


def store() -> UserStore:
    """AWS store when USER_TABLE and USER_BUCKET are set (Lambda), local files otherwise."""
    global _STORE
    if _STORE is None:
        table, bucket = os.environ.get("USER_TABLE", ""), os.environ.get("USER_BUCKET", "")
        if table and bucket:
            _STORE = AwsUserStore(table, bucket)
        else:
            root = Path(os.environ.get("USER_STORE_DIR", Path(__file__).resolve().parent.parent / ".build" / "local_users"))
            _STORE = LocalUserStore(root)
    return _STORE


def set_store(s: UserStore | None) -> None:
    """Tests: inject a store (None = re-read the environment)."""
    global _STORE
    _STORE = s
