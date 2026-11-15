"""Cold-start setup for the Lambda: fetch the data from S3 once, keep it in memory.

The data bucket is the source of truth on AWS:
  s3://$DATA_BUCKET/starter/*.csv           -> /tmp/data/*.csv
  s3://$DATA_BUCKET/$SNAPSHOT_PREFIX*.json  -> /tmp/data/snapshots/*.json
Then DATA_DIR points to /tmp/data, which is what core/ reads. Refreshing the
snapshots (make upload-data) does not need a redeploy: new execution environments
pick them up, and `make deploy` forces a refresh of all of them.

Locally (no DATA_BUCKET), nothing happens and DATA_DIR keeps its value.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

STARTER_PREFIX = "starter/"
LOCAL_DIR = Path("/tmp/data")  # noqa: S108 - Lambda's only writable directory


def sync_data_from_s3() -> dict[str, Any]:
    """Download starter data and snapshots. Returns a small report for the logs."""
    bucket = os.environ.get("DATA_BUCKET", "")
    if not bucket:
        return {"data_source": "local", "data_dir": os.environ.get("DATA_DIR", "data")}

    import boto3

    snapshot_prefix = os.environ.get("SNAPSHOT_PREFIX", "snapshots/")
    s3 = boto3.client("s3")
    t0 = time.perf_counter()
    count = 0
    for prefix, target in ((STARTER_PREFIX, LOCAL_DIR), (snapshot_prefix, LOCAL_DIR / "snapshots")):
        target.mkdir(parents=True, exist_ok=True)
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                name = key[len(prefix):]
                if not name or "/" in name:  # flat layout only
                    continue
                s3.download_file(bucket, key, str(target / name))
                count += 1
    os.environ["DATA_DIR"] = str(LOCAL_DIR)
    return {"data_source": f"s3://{bucket}", "files": count, "sync_ms": int((time.perf_counter() - t0) * 1000)}
