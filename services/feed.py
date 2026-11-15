"""build_feed: profile x portfolio (x consideration) -> FeedResponse (A7).

Deterministic pipeline on the online path: headlines are already classified
(offline batch), rules score them, code computes every number as Evidence, the
explainer drafts short explanations (model for the top items, templates for the
rest) and the guardian checks them. The orchestrator agent handles a consideration.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from agents.explainer import explain, template_explanation
from agents.llm import LLMClient, LLMUnavailableError, MockClient, get_client
from agents.orchestrator import consider
from core import data, event_study, metrics, snapshots
from core import rules_engine as engine
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry, format_num, make_evidence
from core.models import Consideration, Portfolio, Profile
from core.news_targeting import cluster, is_rates_related, mention, source_tier

MAX_ITEMS = 30
MAX_LLM_ITEMS = 6
MAX_MACRO_ITEMS = 12
MAX_PER_TOPIC = 2
LEVEL_FR = {"high": "élevée", "medium": "moyenne", "low": "faible"}
UPCOMING_DAYS = 60
STRUCTURED = {"earnings_results": "earnings", "dividend": "dividend_ex_date", "macro_rates": "rate_decision"}


def _validate(model: type, value: Any, code: str, label: str) -> dict[str, Any]:
    try:
        return model.model_validate(value).model_dump(mode="json", by_alias=True)  # type: ignore[attr-defined]
    except ValidationError as exc:
        raise AlphaForgeError(code, f"{label} invalide.", details={"errors": exc.errors(include_url=False)[:5]}) from exc


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def portfolio_summary(portfolio: dict[str, Any], registry: EvidenceRegistry, threshold: float) -> dict[str, Any]:
    positions = sorted(portfolio["positions"], key=lambda p: -p["weight"])
    weights: dict[str, float] = {}
    for p in positions:
        weights[p["asset_class"]] = weights.get(p["asset_class"], 0.0) + p["weight"]
        registry.add(metrics.position_weight(portfolio, p["ticker"]))
    hv = metrics.high_vol_share(portfolio, threshold)
    top3 = metrics.top3_concentration(portfolio)
    registry.add(hv)
    registry.add(top3)
    return {"top_positions": positions[:5], "asset_class_weights": {k: round(v, 6) for k, v in weights.items()},
            "high_vol_share": round(hv.value, 6), "top3_concentration": round(top3.value, 6)}


def _select_news(records: list[dict[str, Any]], held: set[str]) -> tuple[list[dict[str, Any]], int]:
    """Headlines about held tickers, plus the most recent market-wide (macro_context) ones."""
    selected, macro, unclassified = [], [], 0
    for r in records:
        c = r.get("classification")
        if not c:
            unclassified += held.intersection(r["tickers"]) != set()
            continue
        if held.intersection(r["tickers"]):
            selected.append(r)
        elif c["horizon_relevance"] == "macro_context":
            macro.append(r)
    macro.sort(key=lambda r: r["published_at"], reverse=True)
    return selected + macro[:MAX_MACRO_ITEMS], unclassified


class FeedBuilder:
    def __init__(self, profile: dict[str, Any], portfolio: dict[str, Any], client: LLMClient | None) -> None:
        self.profile, self.portfolio, self.client = profile, portfolio, client
        self.rules = engine.load_rules()
        self.threshold = self.rules.profile_rules.high_vol_threshold
        self.registry = EvidenceRegistry()
        self._hist_cache: dict[tuple[str, str], tuple[dict[str, Any], str] | None] = {}

    def historical(self, category: str, asset: str | None) -> tuple[dict[str, Any], str] | None:
        etype = STRUCTURED.get(category)
        if not etype or not asset:
            return None
        key = (etype, asset)
        if key not in self._hist_cache:
            macro = None
            if etype == "rate_decision":
                macro = "bankofcanada" if data.load_universe().loc[asset, "price_currency"] == "CAD" else "federalreserve"
            try:
                ctx, res = event_study.historical_context(etype, asset, macro_source=macro)
                self._hist_cache[key] = (ctx, self.registry.add(res))
            except AlphaForgeError:
                self._hist_cache[key] = None  # insufficient data: no context rather than a weak one
        return self._hist_cache[key]

    def largest_position(self) -> str | None:
        pos = max(self.portfolio["positions"], key=lambda p: p["weight"], default=None)
        return pos["ticker"] if pos else None

    def largest_bond(self) -> str | None:
        bonds = [p for p in self.portfolio["positions"] if p["asset_class"] == "bond_etf" and p.get("in_universe", True)]
        return max(bonds, key=lambda p: p["weight"])["ticker"] if bonds else None

    def score(self, rec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """-> (position context, relevance). Pure rules, no evidence yet.

        The item seen by the rules = classification + targeting signals (source tier,
        company mention, cluster size). A macro headline with no held ticker is linked
        to the largest bond ETF held, since rates move bond prices (rule R_RATES_BOND).
        """
        pos = engine.position_context(self.portfolio, rec["tickers"], self.threshold)
        bond = self.largest_bond()
        if not pos.get("held") and rec["classification"]["category"] == "macro" and bond and is_rates_related(rec):
            # linked, not held by this headline: no position-weight bonus, only R_RATES_BOND
            pos = {**engine.position_context(self.portfolio, [bond], self.threshold), "weight": 0.0}
        tier = source_tier(rec["source"], self.rules.source_tiers)
        named = mention(rec, pos["ticker"]) if pos.get("held") and pos["ticker"] in rec["tickers"] else "not_applicable"
        item = {**rec["classification"], "tickers": rec["tickers"], "source_tier": tier["id"], "mention": named,
                "cluster_size": (rec.get("_cluster") or {}).get("size", 1)}
        rec["_targeting"] = {"source_tier": tier, "mention": named}
        return pos, engine.score_relevance(self.profile, item, pos, self.rules)

    def item(self, rec: dict[str, Any], pos: dict[str, Any], rel: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """-> (FeedItem without explanation, evidence ids for the explanation). Registers evidence."""
        c = rec["classification"]
        cat = self.rules.category(c["category"])
        label = cat.label_fr if cat else c["category"]
        reg = self.registry
        date = rec["published_at"][:10]
        ev_src = reg.add(make_evidence(
            kind="news_source", statement=f"Nouvelle publiée le {date} par {rec['source']}.", value=rec["id"], unit=None,
            as_of=rec["retrieved_at"][:10], inputs={"news_id": rec["id"], "url": rec["url"], "is_synthetic": rec["is_synthetic"]},
            source=rec["url"], computed_by="ingest.news"))
        ev_cls = reg.add(make_evidence(
            kind="classification",
            statement=f"Classée « {label} » ({c['horizon_relevance']}) par {c['model_id']} (confiance "
                      f"{format_num(c['confidence'])}).",
            value=c["category"], unit=None, as_of=rec["retrieved_at"][:10],
            inputs={"news_id": rec["id"], "model_id": c["model_id"], "prompt_version": c["prompt_version"],
                    "controversy": c["controversy"], "controversy_type": c["controversy_type"]},
            source="data/snapshots/classified_news", computed_by="agents.classifier"))
        hit_texts = " ".join(h["text"] for h in rel["rule_hits"])
        ev_rel = reg.add(make_evidence(
            kind="rule_hit",
            statement=f"Pertinence {format_num(rel['score'])} ({LEVEL_FR[rel['level']]}) pour ton profil. {hit_texts}",
            value=rel["score"], unit="score", as_of=data.data_as_of(),
            inputs={"news_id": rec["id"], "rule_ids": [h["rule_id"] for h in rel["rule_hits"]],
                    "horizon_bucket": self.profile["horizon_bucket"]},
            source="rules/relevance_rules.yaml", computed_by="core.rules_engine.score_relevance"))
        ids = [ev_rel, ev_cls]
        if pos.get("held"):
            ids.append(reg.add(metrics.position_weight(self.portfolio, pos["ticker"])))
            ids.append(reg.add(metrics.annualized_vol(pos["ticker"])))
        asset = pos.get("ticker") or (self.largest_position() if c["horizon_relevance"] == "macro_context" else None)
        hist = self.historical(c["category"], asset)
        if hist:
            ids.append(hist[1])
        ids.append(ev_src)
        item = {
            "news_id": rec["id"], "title": rec["title"], "url": rec["url"], "source": rec["source"],
            "published_at": rec["published_at"], "tickers": rec["tickers"], "is_synthetic": rec["is_synthetic"],
            "category": c["category"], "horizon_relevance": c["horizon_relevance"],
            "relevance": {k: rel[k] for k in ("score", "level", "shown", "position_weight", "rule_hits")},
            "explanation": None, "historical_context": hist[0] if hist else None,
            "source_tier": rec["_targeting"]["source_tier"], "mention": rec["_targeting"]["mention"],
            "cluster": rec.get("_cluster"), "linked_ticker": pos.get("ticker") if pos.get("held") else None,
        }
        return item, ids

    def context(self, item: dict[str, Any]) -> str:
        p = self.profile
        return json.dumps({"task": "why this news matters (or not) for this investor profile",
                           "category": item["category"], "relevance_level": item["relevance"]["level"],
                           "profile": {"horizon_years": p["horizon_years"], "risk_tolerance": p["risk_tolerance"],
                                       "objective": p["objective"]}}, ensure_ascii=False)


def build_feed(profile: Any, portfolio: Any, consideration: Any = None, *, client: LLMClient | None = None,
               generated_at: str | None = None) -> dict[str, Any]:
    profile = _validate(Profile, profile, "INVALID_PROFILE", "Profil")
    portfolio = _validate(Portfolio, portfolio, "INVALID_PORTFOLIO", "Portefeuille")
    if not portfolio["positions"]:
        raise AlphaForgeError("EMPTY_PORTFOLIO", "Le portefeuille ne contient aucune position analysable.")
    if consideration is not None:
        consideration = _validate(Consideration, consideration, "INVALID_CONSIDERATION", "Demande « J'envisage d'acheter »")
    llm_note = None
    if client is None:
        try:
            client = get_client()
        except LLMUnavailableError as exc:  # misconfigured or unreachable model: degrade to templates
            client, llm_note = None, f"Modèle de langage indisponible ({exc}); explications réduites aux preuves."
    fb = FeedBuilder(profile, portfolio, client)
    before = set(fb.registry.to_dict())
    summary = portfolio_summary(portfolio, fb.registry, fb.threshold)
    summary_ids = set(fb.registry.to_dict()) - before

    snap = snapshots.load_snapshot("classified_news", required=False)
    records = snap["records"] if snap else []
    held = {p["ticker"] for p in portfolio["positions"]}
    known = {c.id for c in fb.rules.taxonomy.categories}
    stale = [r for r in records if r.get("classification") and r["classification"]["category"] not in known]
    records = [r for r in records if r not in stale]
    selected, unclassified = _select_news(records, held)
    hidden: dict[str, int] = {}
    tiers = {r["id"]: source_tier(r["source"], fb.rules.source_tiers)["id"] for r in selected}
    n_before = len(selected)
    selected = cluster(selected, tiers)  # one card per event (copies: snapshot records stay untouched)
    if n_before > len(selected):
        hidden["Même événement rapporté par plusieurs sources (regroupé en une carte)"] = n_before - len(selected)
    scored = []
    for rec in selected:
        pos, rel = fb.score(rec)
        if not rel["shown"]:
            key = rel["hidden_reason"] or "Pertinence trop faible pour ton profil"
            hidden[key] = hidden.get(key, 0) + 1
            continue
        scored.append((rec, pos, rel))
    if unclassified:
        hidden["Nouvelle non classée"] = unclassified
    n_stale = sum(1 for r in stale if held.intersection(r["tickers"]))
    if n_stale:
        hidden["Classement obsolète (taxonomie modifiée depuis le classement)"] = n_stale
    scored.sort(key=lambda x: (-x[2]["score"], _neg_date(x[0]["published_at"]), x[0]["id"]))
    kept, per_topic = [], {}
    for rec, pos, rel in scored:
        topic = (pos.get("ticker") or "macro", rec["classification"]["category"])
        per_topic[topic] = per_topic.get(topic, 0) + 1
        if per_topic[topic] > MAX_PER_TOPIC:
            hidden["Sujet déjà couvert par une nouvelle plus pertinente"] = \
                hidden.get("Sujet déjà couvert par une nouvelle plus pertinente", 0) + 1
            continue
        kept.append((rec, pos, rel))
    if len(kept) > MAX_ITEMS:
        hidden[f"Au-delà des {MAX_ITEMS} nouvelles les plus pertinentes"] = len(kept) - MAX_ITEMS
        kept = kept[:MAX_ITEMS]
    items: list[dict[str, Any]] = []
    explain_ids: dict[str, list[str]] = {}
    for rec, pos, rel in kept:
        item, ids = fb.item(rec, pos, rel)
        items.append(item)
        explain_ids[item["news_id"]] = ids

    offline = isinstance(client, MockClient) and client.responder is None
    llm_ids = set() if offline else {i["news_id"] for i in items[:MAX_LLM_ITEMS]}

    def write(item: dict[str, Any]) -> dict[str, Any]:
        ids = explain_ids[item["news_id"]]
        if item["news_id"] in llm_ids:
            return explain(ids, fb.registry, context=fb.context(item), client=client, headline=item["title"])
        return template_explanation(ids, fb.registry)

    with ThreadPoolExecutor(max_workers=max(1, min(MAX_LLM_ITEMS, len(items)))) as pool:
        for item, expl in zip(items, pool.map(write, items), strict=True):
            item["explanation"] = expl

    coherence = consider(profile, portfolio, consideration, fb.registry, client) if consideration else None

    news_as_of = (snap["report"].get("retrieved_at") if snap else None) or data.data_as_of()
    tickers = sorted(held | ({consideration["ticker"]} if consideration else set()))
    start = news_as_of[:10]
    end = (datetime.fromisoformat(start) + timedelta(days=UPCOMING_DAYS)).date().isoformat()
    events = [e for e in snapshots.records("events", required=False)
              if start <= e["date"] <= end and (e["scope"] == "macro" or set(e["tickers"]) & set(tickers))]

    lt = fb.rules.limits_texts
    limits = list(lt.limits)
    if llm_note:
        limits.append(llm_note)
    if snap and snap["report"].get("model_id") == "mock-keywords":
        limits.append("Classement des nouvelles fait hors ligne par mots-clés (mode démo sans modèle); "
                      "il peut se tromper de catégorie.")
    if fb.rules.fallbacks:
        limits.append("Règles provisoires (exemples de référence): " + ", ".join(fb.rules.fallbacks) + ".")
    if snap:
        limits.append(f"Nouvelles publiques récupérées le {news_as_of[:10]} (environ 30 jours d'historique).")
    else:
        limits.append("Aucun instantané de nouvelles classées: le fil est vide.")
    if portfolio["unanalyzed"]["tickers"]:
        limits.append("Positions hors des 31 actifs non analysées: " + ", ".join(portfolio["unanalyzed"]["tickers"]) + ".")

    return {
        "generated_at": generated_at or _now(),
        "data_as_of": data.data_as_of(),
        "news_as_of": news_as_of,
        "profile": profile,
        "portfolio_summary": summary,
        "items": items,
        "hidden": {"count": sum(hidden.values()),
                   "by_reason": [{"reason": r, "count": c} for r, c in sorted(hidden.items(), key=lambda x: -x[1])]},
        "coherence": coherence,
        "events": sorted(events, key=lambda e: (e["date"], e["id"])),
        "evidence": fb.registry.to_dict(_cited(summary_ids, items, coherence)),
        "disclaimers": list(lt.disclaimers),
        "limits": limits,
    }


def _neg_date(iso: str) -> float:
    return -datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def _cited(summary_ids: set[str], items: list[dict[str, Any]], coherence: dict[str, Any] | None) -> set[str]:
    """Evidence ids referenced anywhere in the response (summary numbers, claims, contexts, agent trace)."""
    ids = set(summary_ids)
    expls = [i["explanation"] for i in items] + ([coherence["explanation"]] if coherence else [])
    for e in expls:
        for c in e["claims"]:
            ids.update(c["evidence_ids"])
    for i in items:
        if i["historical_context"]:
            ids.add(i["historical_context"]["evidence_id"])
    if coherence:
        for t in coherence.get("agent_trace") or []:
            ids.update(t["evidence_ids"])
    return ids
