"""Offline ingestion CLI: python -m ingest.run [--news] [--events] [--google] [--days 30]

Writes data/snapshots/news_<YYYYMMDD>.json (NewsRecord list without classification),
data/snapshots/events_<YYYYMMDD>.json (Event list) and REPORT_<YYYYMMDD>.md.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any

from core.data import load_universe
from core.models import Event, NewsRecord
from ingest.common import snapshots_dir, write_snapshot
from ingest.events import fetch_events
from ingest.news import fetch_news


def _report_md(stamp: str, news: tuple[list[dict[str, Any]], dict[str, Any]] | None,
               events: tuple[list[dict[str, Any]], dict[str, Any]] | None) -> str:
    uni = load_universe()
    lines = [f"# Rapport d'ingestion {stamp}", ""]
    if news:
        recs, rep = news
        lines += ["## Nouvelles", "",
                  f"- Récupérées le {rep['retrieved_at']}; {rep['n_records']} titres uniques après déduplication.",
                  f"- Par source (avant déduplication): {rep['per_source']}.",
                  f"- Profondeur: du {rep['oldest']} au {rep['newest']}.",
                  "- Licence: on garde titre, source, date, lien et au plus 300 caractères d'extrait (pas de texte "
                  "intégral). Les liens pointent vers l'éditeur ou l'agrégateur.", "",
                  "| Ticker | Classe | Titres |", "| --- | --- | --- |"]
        lines += [f"| {t} | {uni.loc[t, 'asset_class']} | {n} |" for t, n in rep["per_ticker"].items()]
        if rep["errors"]:
            lines += ["", "Erreurs:", *[f"- {e}" for e in rep["errors"][:30]]]
        lines.append("")
    if events:
        evs, rep = events
        by_type: dict[str, int] = {}
        for e in evs:
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1
        lines += ["## Événements", "", f"- {rep['n_events']} événements ({by_type}); {rep['upcoming']} à venir.",
                  "- Publications d'inflation (cpi_release): non collectées (le BLS bloque l'accès automatisé; "
                  "pas de calendrier public fiable trouvé).", "",
                  "| Ticker ou macro | Événements par type |", "| --- | --- |"]
        lines += [f"| {k} | {v} |" for k, v in sorted(rep["per_ticker"].items())]
        if rep["errors"]:
            lines += ["", "Erreurs:", *[f"- {e}" for e in rep["errors"][:30]]]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--news", action="store_true")
    parser.add_argument("--events", action="store_true")
    parser.add_argument("--google", action="store_true", help="add Google News RSS (by company name)")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--tickers", help="comma-separated subset")
    args = parser.parse_args()
    if not (args.news or args.events):
        args.news = args.events = True
    tickers = args.tickers.split(",") if args.tickers else None
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    news = events = None
    if args.news:
        news = fetch_news(tickers, google=args.google, days=args.days)
        for r in news[0]:
            NewsRecord.model_validate(r)
        write_snapshot(f"news_{stamp}.json", {"kind": "news", "report": news[1], "records": news[0]})
        print(f"news: {news[1]['n_records']} records, errors: {len(news[1]['errors'])}")
    if args.events:
        events = fetch_events(tickers)
        for e in events[0]:
            Event.model_validate(e)
        write_snapshot(f"events_{stamp}.json", {"kind": "events", "report": events[1], "records": events[0]})
        print(f"events: {events[1]['n_events']} records, errors: {len(events[1]['errors'])}")
    (snapshots_dir() / f"REPORT_{stamp}.md").write_text(_report_md(stamp, news, events), encoding="utf-8")


if __name__ == "__main__":
    main()
