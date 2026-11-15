"""HTTP and snapshot helpers for offline ingestion (never on the online path)."""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.data import data_dir

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
SNIPPET_MAX = 300


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def http_get(url: str, *, timeout: float = 20, retries: int = 2, pause: float = 1.0) -> bytes:
    """GET with a browser-like User-Agent, limited retries and a timeout."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (public URLs only)
                return bytes(resp.read())
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries + 1} attempts: {url}: {last}")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def snippet(text: str | None) -> str | None:
    """Plain-text excerpt, at most 300 characters (licence: never the full text)."""
    s = strip_html(text)
    if not s:
        return None
    return s if len(s) <= SNIPPET_MAX else s[: SNIPPET_MAX - 1].rsplit(" ", 1)[0] + "…"


def normalize_title(title: str) -> str:
    t = strip_html(title).lower()
    t = re.sub(r"\s+-\s+[^-]{2,40}$", "", t)  # Google News appends " - Source"
    return re.sub(r"[^a-z0-9à-ÿ]+", " ", t).strip()


def stable_id(prefix: str, *parts: str) -> str:
    return prefix + hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def snapshots_dir() -> Path:
    path = data_dir() / "snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_snapshot(name: str, payload: dict[str, Any]) -> Path:
    path = snapshots_dir() / name
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
