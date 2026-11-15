"""Offline batch: classify the latest news snapshot (python -m agents.classify_batch).

Reads data/snapshots/news_*.json, classifies each headline (cache by news_id and
prompt_version, reusing the previous classified snapshot), and writes
data/snapshots/classified_news_<YYYYMMDD>.json. With LLM_PROVIDER=mock the
deterministic keyword classifier is used (model_id "mock-keywords").
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from agents.classifier import Classifier
from agents.llm import LLMUnavailableError, get_client
from core import rules_engine, snapshots
from core.models import NewsRecord
from ingest.common import now_iso, write_snapshot


def previous_cache() -> dict[tuple[str, str], dict[str, Any]]:
    cache = {}
    for r in snapshots.records("classified_news", required=False):
        c = r.get("classification")
        if c:
            cache[(r["id"], c["prompt_version"])] = c
    return cache


def run(limit: int | None = None, workers: int = 4) -> dict[str, Any]:
    news = snapshots.load_snapshot("news")
    assert news is not None
    records = news["records"][:limit] if limit else news["records"]
    clf = Classifier(get_client(), rules_engine.load_rules().taxonomy, previous_cache())
    errors: list[str] = []

    def one(rec: dict[str, Any]) -> dict[str, Any]:
        out = dict(rec)
        try:
            out["classification"] = clf.classify(rec)
        except LLMUnavailableError as exc:
            errors.append(f"{rec['id']}: {exc}")
        return out

    with ThreadPoolExecutor(max_workers=1 if clf.mock else workers) as pool:
        classified = list(pool.map(one, records))
    for r in classified:
        NewsRecord.model_validate(r)
    cats = Counter(r["classification"]["category"] for r in classified if r.get("classification"))
    report = {"retrieved_at": news["report"]["retrieved_at"], "classified_at": now_iso(), "model_id": clf.model_id,
              "prompt_version": clf.prompt_version, "n_records": len(classified),
              "n_classified": sum(1 for r in classified if r.get("classification")), "errors": errors[:50],
              "categories": dict(cats.most_common())}
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    write_snapshot(f"classified_news_{stamp}.json", {"kind": "classified_news", "report": report,
                                                     "records": classified})
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    rep = run(args.limit, args.workers)
    print({k: rep[k] for k in ("model_id", "prompt_version", "n_records", "n_classified", "categories")})
    if rep["errors"]:
        print(f"{len(rep['errors'])} error(s), first: {rep['errors'][0]}")


if __name__ == "__main__":
    main()
