"""News targeting (pure code, no LLM): source reliability, ticker mention, event clusters.

- source_tier: rules/source_tiers.yaml (primary / established press / aggregator).
- mention: does the headline actually name the company? Google News often tags a
  ticker on articles that only cite it in passing.
- cluster: the same event is often reported by many outlets; we show one card per
  event ("N sources en parlent") instead of N near-identical cards.
These signals feed the relevance rules (role D's relevance_rules.yaml); nothing here
decides alone.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any

from core import data

CLUSTER_WINDOW_HOURS = 48
CLUSTER_MIN_JACCARD = 0.5
TIER_RANK = {"primary": 0, "established": 1, "unknown": 2, "aggregator": 3}

# Extra names used in headlines (the universe `name` column is used too).
ALIASES: dict[str, list[str]] = {
    "RY.TO": ["royal bank", "rbc"], "TD.TO": ["td bank", "toronto-dominion", "td securities"],
    "MFC.TO": ["manulife", "john hancock"], "ENB.TO": ["enbridge"], "CNQ.TO": ["canadian natural", "cnrl"],
    "CNR.TO": ["canadian national", "cn rail", "cn railway"], "FTS.TO": ["fortis"],
    "ATD.TO": ["couche-tard", "couche tard", "circle k"], "SHOP.TO": ["shopify"], "CSU.TO": ["constellation software"],
    "AAPL": ["apple", "iphone"], "MSFT": ["microsoft", "azure", "copilot"], "NVDA": ["nvidia"],
    "GOOGL": ["alphabet", "google", "youtube", "waymo", "gemini"], "AMZN": ["amazon", "aws"],
    "TSLA": ["tesla", "musk"], "JPM": ["jpmorgan", "jp morgan", "dimon"], "JNJ": ["johnson & johnson", "j&j"],
    "PG": ["procter", "p&g"], "XOM": ["exxon"], "BTC-USD": ["bitcoin", "btc"], "ETH-USD": ["ether", "ethereum"],
}
STOP = {"the", "and", "for", "with", "from", "that", "this", "its", "are", "has", "have", "will", "after", "over",
        "into", "about", "what", "why", "how", "les", "des", "une", "pour", "dans", "sur", "par", "est", "aux",
        "stock", "stocks", "shares", "says", "said", "new", "news", "inc", "corp", "ltd"}


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in t if not unicodedata.combining(ch))


def source_tier(source: str, cfg: Any) -> dict[str, Any]:
    """{id, label_fr, text_fr} of the first tier whose pattern is in the source name."""
    s = _fold(source or "")
    if cfg is not None:
        for tier in cfg.tiers:
            if any(_fold(p) in s for p in tier.patterns):
                return {"id": tier.id, "label_fr": tier.label_fr, "text_fr": tier.text_fr}
        u = cfg.unknown
        return {"id": "unknown", "label_fr": u.label_fr, "text_fr": u.text_fr}
    return {"id": "unknown", "label_fr": "Source non répertoriée", "text_fr": ""}


def _names(ticker: str) -> list[str]:
    uni = data.load_universe()
    base = ticker.split(".")[0].split("-")[0].lower()
    names = [f"({base})", f"{base}:", f" {base} ", f"${base}"] + ALIASES.get(ticker, [])
    if ticker in uni.index:
        first = re.split(r"[ (,]", str(uni.loc[ticker, "name"]).lower())[0]
        if len(first) > 3:
            names.append(first)
    return names


def mention(rec: dict[str, Any], ticker: str) -> str:
    """'title' | 'snippet' | 'none' | 'not_applicable' (funds: no company name to look for)."""
    uni = data.load_universe()
    if ticker in uni.index and uni.loc[ticker, "asset_class"] in ("equity_etf", "bond_etf", "gold_etf"):
        return "not_applicable"
    names = _names(ticker)
    title = f" {_fold(rec.get('title', ''))} "
    if any(_fold(n) in title for n in names):
        return "title"
    if any(_fold(n) in f" {_fold(rec.get('snippet') or '')} " for n in names):
        return "snippet"
    return "none"


RATES_TERMS = ("rate", "yield", "treasur", "inflation", "cpi", "fed ", "federal reserve", "fomc", "powell",
               "bank of canada", "banque du canada", "macklem", "bond", "taux", "obligat", "ipc ")


def is_rates_related(rec: dict[str, Any]) -> bool:
    """True if the headline (or snippet) is about interest rates, yields, inflation or bonds."""
    text = f" {_fold(rec.get('title', ''))} {_fold(rec.get('snippet') or '')} "
    return any(t in text for t in RATES_TERMS)


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _fold(title)) if len(w) > 2 and w not in STOP}


def _ts(iso: str) -> float:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def cluster(records: list[dict[str, Any]], tier_of: dict[str, str]) -> list[dict[str, Any]]:
    """Group near-duplicate headlines (shared ticker, within 48 h, Jaccard >= 0.5 on title words).

    Returns one representative per cluster (best source tier, then earliest), with
    `_cluster` = {size, sources, news_ids}. Deterministic: input order does not matter.
    """
    recs = sorted(records, key=lambda r: (r["published_at"], r["id"]))
    toks = {r["id"]: _tokens(r["title"]) for r in recs}
    groups: list[list[dict[str, Any]]] = []
    for r in recs:
        placed = False
        for g in groups:
            head = g[0]
            if not set(r["tickers"]) & set(head["tickers"]) and (r["tickers"] or head["tickers"]):
                continue
            if abs(_ts(r["published_at"]) - _ts(head["published_at"])) > CLUSTER_WINDOW_HOURS * 3600:
                continue
            a, b = toks[r["id"]], toks[head["id"]]
            if a and b and len(a & b) / len(a | b) >= CLUSTER_MIN_JACCARD:
                g.append(r)
                placed = True
                break
        if not placed:
            groups.append([r])
    out = []
    for g in groups:
        rep = min(g, key=lambda r: (TIER_RANK.get(tier_of.get(r["id"], "unknown"), 2), r["published_at"], r["id"]))
        rep = dict(rep)
        rep["_cluster"] = {"size": len(g), "sources": sorted({x["source"] for x in g}),
                           "news_ids": [x["id"] for x in g]}
        out.append(rep)
    return out
