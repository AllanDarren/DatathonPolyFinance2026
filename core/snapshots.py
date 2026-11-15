"""Read frozen snapshots (data/snapshots/*.json) written by ingest/ and agents/.

Latest file wins (`<kind>_<YYYYMMDD>.json`, sorted by name). Reading a snapshot is
the only I/O allowed on the online path besides the starter data.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from core.data import data_dir
from core.errors import DataError


def snapshot_path(kind: str) -> Path | None:
    files = sorted((data_dir() / "snapshots").glob(f"{kind}_*.json"))
    return files[-1] if files else None


@cache
def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_snapshot(kind: str, required: bool = True) -> dict[str, Any] | None:
    """Payload {kind, report, records} of the latest snapshot of `kind`."""
    path = snapshot_path(kind)
    if path is None:
        if required:
            raise DataError(f"Instantané « {kind} » absent de data/snapshots/.", {"kind": kind})
        return None
    return _load(str(path))


def records(kind: str, required: bool = True) -> list[dict[str, Any]]:
    snap = load_snapshot(kind, required)
    return list(snap["records"]) if snap else []


def as_of(kind: str) -> str | None:
    snap = load_snapshot(kind, required=False)
    return snap["report"].get("retrieved_at") if snap else None


def clear_cache() -> None:
    _load.cache_clear()
