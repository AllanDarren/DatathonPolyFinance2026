"""Build the A0 contract examples in contracts/examples/.

Usage: python -m tools.build_examples

Provisional (A0): the metrics are computed from data/ with simple inline code, the
news items are SYNTHETIC (is_synthetic: true), and personas/rules are placeholders
until role D publishes rules/. The real pipeline (A7) will regenerate these files
through services.build_feed without changing their shape.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.data import ASSET_CLASS_MAP
from core.models import FeedResponse, Persona

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "contracts" / "examples"
GENERATED_AT = "2026-11-14T00:00:00Z"
DATA_AS_OF = "2026-11-12"
NEWS_AS_OF = "2026-11-13"
RETRIEVED_AT = "2026-11-13T12:00:00Z"
HIGH_VOL = 0.30


PERSONAS: dict[str, dict[str, Any]] = {
    "robert": {
        "label": "Robert, 59 ans, proche de la retraite",
        "profile": {
            "age": 59, "horizon_years": 4, "horizon_bucket": "short", "risk_tolerance": "low_moderate",
            "max_acceptable_loss_pct": 0.10, "objective": "capital_preservation", "experience": "intermediate",
            "preferences": {"avoid_controversies": False, "excluded_sectors": [], "interests": ["dividendes"]},
            "limits": {"max_single_position": 0.10, "max_high_vol_share": 0.10},
            "monthly_expenses_cad": 5000,
        },
        "portfolio": {"ZST.TO": 20000, "XBB.TO": 25000, "XIU.TO": 15000, "SPY": 15000,
                      "FTS.TO": 8000, "RY.TO": 7000, "ENB.TO": 5000, "AGG": 5000},
        "consideration": {"ticker": "NVDA", "intended_weight": 0.20},
    },
    "amira": {
        "label": "Amira, 26 ans, ingénieure logiciel",
        "profile": {
            "age": 26, "horizon_years": 20, "horizon_bucket": "long", "risk_tolerance": "high",
            "max_acceptable_loss_pct": 0.35, "objective": "growth", "experience": "intermediate",
            "preferences": {"avoid_controversies": False, "excluded_sectors": [], "interests": ["IA", "technologie", "crypto"]},
            "limits": {"max_single_position": 0.25, "max_high_vol_share": 0.60},
            "monthly_expenses_cad": 3500,
        },
        "portfolio": {"NVDA": 20000, "QQQ": 18000, "SHOP.TO": 12000, "BTC-USD": 12000, "MSFT": 10000,
                      "XIU.TO": 8000, "TSLA": 7000, "CSU.TO": 7000, "ETH-USD": 6000},
        "consideration": None,
    },
    "mateo": {
        "label": "Mateo, 41 ans, gestionnaire des opérations",
        "profile": {
            "age": 41, "horizon_years": 10, "horizon_bucket": "medium", "risk_tolerance": "moderate",
            "max_acceptable_loss_pct": 0.20, "objective": "balanced", "experience": "intermediate",
            "preferences": {"avoid_controversies": True, "excluded_sectors": ["Energy"], "interests": ["ESG"]},
            "limits": {"max_single_position": 0.15, "max_high_vol_share": 0.25},
            "monthly_expenses_cad": 4500,
        },
        "portfolio": {"ESGV": 25000, "XBB.TO": 20000, "XIU.TO": 15000, "CNR.TO": 8000, "JNJ": 7000,
                      "PG": 7000, "GLD": 7000, "ENB.TO": 6000, "XOM": 5000},
        "consideration": None,
    },
}

# Placeholder taxonomy/relevance (role D owns the real ones in rules/).
TAXONOMY = {
    "earnings_results": ("Résultats financiers", "structural"),
    "dividend": ("Dividende", "structural"),
    "macro_rates": ("Taux et inflation", "macro_context"),
    "controversy": ("Controverse", "structural"),
    "analyst_rating": ("Avis d'analystes", "short_term_noise"),
    "price_commentary": ("Commentaire sur le prix du jour", "short_term_noise"),
    "rumor_hype": ("Rumeur ou engouement", "short_term_noise"),
    "product": ("Produit", "structural"),
}
BASE_WEIGHTS = {
    "short": {"earnings_results": 0.50, "dividend": 0.60, "macro_rates": 0.70, "controversy": 0.40,
              "analyst_rating": 0.15, "price_commentary": 0.05, "rumor_hype": 0.05, "product": 0.20},
    "medium": {"earnings_results": 0.50, "dividend": 0.40, "macro_rates": 0.45, "controversy": 0.40,
               "analyst_rating": 0.15, "price_commentary": 0.05, "rumor_hype": 0.05, "product": 0.35},
    "long": {"earnings_results": 0.45, "dividend": 0.25, "macro_rates": 0.35, "controversy": 0.35,
             "analyst_rating": 0.10, "price_commentary": 0.05, "rumor_hype": 0.05, "product": 0.45},
}
SHOW, HIGH = 0.35, 0.70

NEWS: list[dict[str, Any]] = [
    {"id": "n_syn_001", "title": "La Banque du Canada maintient son taux directeur et signale une pause prolongée",
     "tickers": [], "category": "macro_rates", "controversy": False, "date": "2026-11-10T14:00:00Z"},
    {"id": "n_syn_002", "title": "NVIDIA publie des résultats trimestriels supérieurs aux attentes, portés par les centres de données",
     "tickers": ["NVDA"], "category": "earnings_results", "controversy": False, "date": "2026-11-12T21:30:00Z"},
    {"id": "n_syn_003", "title": "Royal Bank of Canada annonce une hausse de 4 % de son dividende trimestriel",
     "tickers": ["RY.TO"], "category": "dividend", "controversy": False, "date": "2026-11-11T11:00:00Z"},
    {"id": "n_syn_004", "title": "Enbridge visée par une poursuite environnementale après une fuite sur un pipeline",
     "tickers": ["ENB.TO"], "category": "controversy", "controversy": True, "controversy_type": "environmental",
     "date": "2026-11-09T16:20:00Z"},
    {"id": "n_syn_005", "title": "Bitcoin bondit de 8 % en une journée, les réseaux sociaux s'enflamment",
     "tickers": ["BTC-USD"], "category": "rumor_hype", "controversy": False, "date": "2026-11-12T09:00:00Z"},
    {"id": "n_syn_006", "title": "Shopify dévoile de nouveaux outils d'IA pour les marchands",
     "tickers": ["SHOP.TO"], "category": "product", "controversy": False, "date": "2026-11-08T15:00:00Z"},
    {"id": "n_syn_007", "title": "Un analyste relève sa cible de cours sur Microsoft",
     "tickers": ["MSFT"], "category": "analyst_rating", "controversy": False, "date": "2026-11-12T12:00:00Z"},
    {"id": "n_syn_008", "title": "L'inflation américaine ralentit à 2,6 % sur un an en octobre",
     "tickers": [], "category": "macro_rates", "controversy": False, "date": "2026-11-12T13:30:00Z"},
    {"id": "n_syn_009", "title": "Exxon Mobil fait face à des critiques d'actionnaires sur ses objectifs climatiques",
     "tickers": ["XOM"], "category": "controversy", "controversy": True, "controversy_type": "governance",
     "date": "2026-11-07T18:00:00Z"},
    {"id": "n_syn_010", "title": "Fortis confirme ses prévisions d'investissement sur cinq ans",
     "tickers": ["FTS.TO"], "category": "earnings_results", "controversy": False, "date": "2026-11-06T12:00:00Z"},
    {"id": "n_syn_011", "title": "Le titre de Tesla recule de 3 % en séance",
     "tickers": ["TSLA"], "category": "price_commentary", "controversy": False, "date": "2026-11-12T20:00:00Z"},
    {"id": "n_syn_012", "title": "Johnson & Johnson publie ses résultats du troisième trimestre",
     "tickers": ["JNJ"], "category": "earnings_results", "controversy": False, "date": "2026-10-14T11:00:00Z"},
    {"id": "n_syn_013", "title": "Microsoft annonce de nouveaux investissements massifs dans l'infrastructure d'IA",
     "tickers": ["MSFT"], "category": "product", "controversy": False, "date": "2026-11-05T13:00:00Z"},
    {"id": "n_syn_014", "title": "Constellation Software publie ses résultats trimestriels",
     "tickers": ["CSU.TO"], "category": "earnings_results", "controversy": False, "date": "2026-11-04T21:00:00Z"},
    {"id": "n_syn_015", "title": "Tesla rappelle des véhicules en raison d'un problème de sécurité logicielle",
     "tickers": ["TSLA"], "category": "controversy", "controversy": True, "controversy_type": "safety",
     "date": "2026-11-03T15:00:00Z"},
    {"id": "n_syn_016", "title": "Le FNB SPY termine la séance à un sommet historique",
     "tickers": ["SPY"], "category": "price_commentary", "controversy": False, "date": "2026-11-12T21:00:00Z"},
    {"id": "n_syn_017", "title": "Rumeur de rachat dans le secteur bancaire canadien",
     "tickers": ["RY.TO"], "category": "rumor_hype", "controversy": False, "date": "2026-11-10T10:00:00Z"},
    {"id": "n_syn_018", "title": "L'or recule légèrement après un rebond du dollar américain",
     "tickers": ["GLD"], "category": "price_commentary", "controversy": False, "date": "2026-11-12T19:00:00Z"},
]

DISCLAIMERS = [
    "Simulation éducative: ce n'est pas un conseil financier personnalisé.",
    "Aucune transaction réelle n'est effectuée.",
]
LIMITS = [
    "Une seule fenêtre de 5 ans (2021-11-12 au 2026-11-12): hausse des taux, marché porté par la technologie.",
    "Biais du survivant: les 31 actifs ont été choisis en 2026.",
    "Un contexte historique n'est pas une prévision.",
    "Les nouvelles de cet exemple sont fictives (exemple fictif).",
]


# --- quick metrics (A0 preview; A2 replaces with core.metrics) -------------

def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices = pd.read_csv(DATA / "prices_daily.csv", parse_dates=["date"])
    universe = pd.read_csv(DATA / "assets_universe.csv")
    actions = pd.read_csv(DATA / "corporate_actions.csv", parse_dates=["ex_date"])
    return prices, universe, actions


def series(prices: pd.DataFrame, ticker: str) -> pd.Series:
    s = prices.loc[prices.ticker == ticker].set_index("date")["adj_close"].sort_index()
    return s


def metrics(s: pd.Series) -> dict[str, float]:
    r = s.pct_change().dropna()
    vol = float(r.std(ddof=1) * math.sqrt(252))
    mdd = float((s / s.cummax() - 1).min())
    yearly = s.groupby(s.index.year).last()
    first = s.iloc[0]
    rets = {}
    prev = first
    for y, v in yearly.items():
        rets[int(y)] = float(v / prev - 1)
        prev = v
    full_years = {y: v for y, v in rets.items() if 2022 <= y <= 2025}
    return {"vol": vol, "mdd": mdd, "ret_2022": rets[2022], "worst_year": min(full_years.values())}


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f} %".replace(".", ",")


class Registry:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def add(self, kind: str, statement: str, value: Any, unit: str | None, inputs: dict[str, Any],
            source: str, computed_by: str) -> str:
        ev_id = f"ev_{len(self.items) + 1:03d}"
        self.items[ev_id] = {"id": ev_id, "kind": kind, "statement": statement, "value": value, "unit": unit,
                             "as_of": DATA_AS_OF, "inputs": inputs, "source": source, "computed_by": computed_by}
        return ev_id


def explanation(claims: list[tuple[str, str, list[str]]], summary: str) -> dict[str, Any]:
    return {
        "summary": summary,
        "claims": [{"text": t, "label": lab, "evidence_ids": ids, "verified": "supported"} for t, lab, ids in claims],
        "generated_by": "template",
        "guardian": {"status": "passed", "flags": []},
    }


def event_study_dividends(prices: pd.DataFrame, actions: pd.DataFrame, ticker: str) -> dict[str, Any]:
    s = series(prices, ticker)
    dates = actions.loc[(actions.ticker == ticker) & (actions.action == "dividend"), "ex_date"].sort_values()
    events = []
    idx = s.index
    for d in dates:
        pos = idx.searchsorted(d)  # first trading day >= ex-date
        if pos < 1 or pos + 4 >= len(idx):
            continue
        before, after = s.iloc[pos - 1], s.iloc[pos + 4]
        events.append({"date": d.strftime("%Y-%m-%d"), "return": round(float(after / before - 1), 6)})
    rets = np.array([e["return"] for e in events])
    return {
        "n": len(events), "median": float(np.median(rets)), "p10": float(np.percentile(rets, 10)),
        "p90": float(np.percentile(rets, 90)), "share_positive": float((rets > 0).mean()), "events": events,
    }


def build_persona(pid: str, prices: pd.DataFrame, universe: pd.DataFrame,
                  actions: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    spec = PERSONAS[pid]
    profile = {"profile_id": pid, "label": spec["label"], "source": "persona_preset", **spec["profile"],
               "base_currency": "CAD", "inconsistencies": []}
    uni = universe.set_index("ticker")
    total = float(sum(spec["portfolio"].values()))
    positions = []
    for t, amt in sorted(spec["portfolio"].items(), key=lambda kv: -kv[1]):
        row = uni.loc[t]
        positions.append({"ticker": t, "amount": float(amt), "weight": round(amt / total, 6),
                          "asset_class": ASSET_CLASS_MAP[(row.asset_class, row.currency)],
                          "price_currency": row.currency, "in_universe": True})
    reg = Registry()
    m_cache = {t: metrics(series(prices, t)) for t in list(spec["portfolio"]) + ["NVDA"]}
    high_vol_share = sum(p["weight"] for p in positions if m_cache[p["ticker"]]["vol"] > HIGH_VOL)
    top3 = sum(p["weight"] for p in positions[:3])
    ac_weights: dict[str, float] = {}
    for p in positions:
        ac_weights[p["asset_class"]] = round(ac_weights.get(p["asset_class"], 0) + p["weight"], 6)

    weights = {p["ticker"]: p["weight"] for p in positions}
    items, hidden_reasons = [], {}
    bucket = profile["horizon_bucket"]
    for n in NEWS:
        held = [t for t in n["tickers"] if t in weights]
        if n["tickers"] and not held:
            continue
        label_fr, horizon_rel = TAXONOMY[n["category"]]
        w_pos = max((weights[t] for t in held), default=0.0)
        base = BASE_WEIGHTS[bucket][n["category"]]
        hits = [{"rule_id": f"R_BASE_{n['category'].upper()}",
                 "text": f"Catégorie {label_fr}: pertinence {base:.2f} pour un horizon {bucket}.",
                 "delta": base}]
        score = base
        if w_pos >= 0.20:
            hits.append({"rule_id": "R_POS_WEIGHT_20", "text": "Position de 20 % ou plus du portefeuille.",
                         "delta": 0.20, "observed": round(w_pos, 4), "limit": 0.20})
            score += 0.20
        elif w_pos >= 0.10:
            hits.append({"rule_id": "R_POS_WEIGHT_10", "text": "Position de 10 % ou plus du portefeuille.",
                         "delta": 0.10, "observed": round(w_pos, 4), "limit": 0.10})
            score += 0.10
        if n["controversy"] and profile["preferences"]["avoid_controversies"]:
            hits.append({"rule_id": "R_PREF_CONTROVERSY",
                         "text": "Controverse liée à un titre que tu détiens, et tu as dit vouloir les éviter.",
                         "delta": 0.40})
            score += 0.40
        if any(i.lower() in ("crypto",) for i in profile["preferences"]["interests"]) and "BTC-USD" in held:
            hits.append({"rule_id": "R_PREF_INTEREST", "text": "Sujet lié à un de tes centres d'intérêt (crypto).",
                         "delta": 0.10})
            score += 0.10
        score = round(min(score, 1.0), 4)
        shown = score >= SHOW
        if not shown:
            reason = "Bruit de court terme pour ton horizon" if horizon_rel == "short_term_noise" else "Pertinence faible pour ton profil"
            hidden_reasons[reason] = hidden_reasons.get(reason, 0) + 1
            continue
        level = "high" if score >= HIGH else "medium" if score >= 0.5 else "low"

        ev_src = reg.add("news_source", f"Nouvelle « {n['title'][:60]}… » (exemple fictif).", n["id"], None,
                         {"news_id": n["id"]}, "contracts/examples (synthetic)", "tools.build_examples")
        ev_cls = reg.add("classification", f"Classée « {label_fr} » ({horizon_rel}).", n["category"], None,
                         {"news_id": n["id"], "prompt_version": "classifier_v0"}, "synthetic", "agents.classifier (mock)")
        ev_rule = reg.add("rule_hit", f"Score de pertinence {score:.2f} ({level}).", score, "score",
                          {"rule_ids": [h["rule_id"] for h in hits]}, "rules/relevance_rules.yaml (provisoire)",
                          "core.rules_engine.score_relevance")
        claims: list[tuple[str, str, list[str]]] = [
            (f"Cette nouvelle est classée « {label_fr} ».", "fact", [ev_src, ev_cls]),
            (f"Son score de pertinence pour ton profil est {score:.2f}, niveau {level}.", "fact", [ev_rule]),
        ]
        hist = None
        if held:
            t = held[0]
            ev_w = reg.add("portfolio_calc", f"{t} représente {pct(w_pos)} du portefeuille analysé.",
                           round(w_pos, 6), "fraction", {"ticker": t, "amount": spec["portfolio"][t], "total": total},
                           "portefeuille fourni", "core.portfolio.position_weight")
            m = m_cache[t]
            ev_v = reg.add("metric", f"Volatilité annualisée de {t}: {pct(m['vol'])}.", round(m["vol"], 6),
                           "fraction", {"ticker": t, "window": "2021-11-12/2026-11-12", "days_per_year": 252},
                           "data/prices_daily.csv", "core.metrics.annualized_vol")
            claims.append((f"{t} représente {pct(w_pos)} de ton portefeuille, avec une volatilité annualisée "
                           f"de {pct(m['vol'])} sur 5 ans.", "fact", [ev_w, ev_v]))
            if n["category"] == "dividend":
                es = event_study_dividends(prices, actions, t)
                ev_es = reg.add("event_study", f"{es['n']} dates ex-dividende passées de {t}: médiane {pct(es['median'], 2)} "
                                f"de la veille à +5 jours de bourse.", round(es["median"], 6), "fraction",
                                {"ticker": t, "event_type": "dividend_ex_date", "window": "t-1 → t+5 jours de bourse"},
                                "data/corporate_actions.csv, data/prices_daily.csv", "core.event_study.historical_context")
                hist = {
                    "event_type": "dividend_ex_date", "asset": t, "window": "veille à +5 jours de bourse",
                    "n_events": es["n"], "median_return": round(es["median"], 6), "p10": round(es["p10"], 6),
                    "p90": round(es["p90"], 6), "share_positive": round(es["share_positive"], 4),
                    "events": es["events"],
                    "caveats": ["Échantillon limité.", "Les fenêtres peuvent chevaucher d'autres événements.",
                                "Biais du survivant: actif choisi en 2026.", "Ce n'est pas une prévision."],
                    "evidence_id": ev_es,
                }
                claims.append((f"Dans des situations comparables ({es['n']} dates ex-dividende), le mouvement médian "
                               f"a été de {pct(es['median'], 2)}; ce n'est pas une prévision.", "fact", [ev_es]))
        if n["controversy"]:
            claims.append(("Une controverse peut peser sur la réputation de l'entreprise sur plusieurs années.",
                           "hypothesis", [ev_cls]))
        items.append({
            "news_id": n["id"], "title": n["title"], "url": f"https://example.org/synthetic/{n['id']}",
            "source": "Exemple fictif", "published_at": n["date"], "tickers": n["tickers"], "is_synthetic": True,
            "category": n["category"], "horizon_relevance": horizon_rel,
            "relevance": {"score": score, "level": level, "shown": True, "position_weight": round(w_pos, 6),
                          "rule_hits": hits},
            "explanation": explanation(claims, f"{label_fr}: pertinence {level} pour ton profil."),
            "historical_context": hist,
        })
    items.sort(key=lambda i: -i["relevance"]["score"])

    coherence = None
    cons = spec["consideration"]
    if cons:
        t, w_after = cons["ticker"], cons["intended_weight"]
        m = m_cache[t]
        lim = profile["limits"]
        ev_v = reg.add("metric", f"Volatilité annualisée de {t}: {pct(m['vol'])}.", round(m["vol"], 6), "fraction",
                       {"ticker": t, "window": "2021-11-12/2026-11-12", "days_per_year": 252},
                       "data/prices_daily.csv", "core.metrics.annualized_vol")
        ev_d = reg.add("metric", f"Perte maximale de {t} sur 5 ans: {pct(m['mdd'])}.", round(m["mdd"], 6), "fraction",
                       {"ticker": t, "window": "2021-11-12/2026-11-12"}, "data/prices_daily.csv",
                       "core.metrics.max_drawdown")
        ev_y = reg.add("metric", f"Rendement de {t} en 2022: {pct(m['ret_2022'])}.", round(m["ret_2022"], 6),
                       "fraction", {"ticker": t, "year": 2022}, "data/prices_daily.csv",
                       "core.metrics.calendar_year_return")
        ev_w = reg.add("portfolio_calc", f"Poids de {t} après l'ajout envisagé: {pct(w_after)}.", w_after,
                       "fraction", {"ticker": t, "intended_weight": w_after}, "consideration",
                       "core.metrics.position_weight_after")
        hits = [
            {"rule_id": "C_MAX_SINGLE", "severity": "high", "observed": w_after, "limit": lim["max_single_position"],
             "text": f"Cette position dépasserait la limite de {pct(lim['max_single_position'], 0)} par titre prévue "
                     f"pour ton profil (valeur: {pct(w_after, 0)})."},
            {"rule_id": "C_DRAWDOWN_VS_LOSS", "severity": "medium", "observed": round(abs(m["mdd"]), 4),
             "limit": profile["max_acceptable_loss_pct"],
             "text": f"La pire chute historique de ce titre ({pct(abs(m['mdd']), 0)}) dépasse la perte que tu dis "
                     f"pouvoir accepter ({pct(profile['max_acceptable_loss_pct'], 0)})."},
            {"rule_id": "C_HIGH_VOL_SHARE", "severity": "high", "observed": round(high_vol_share * (1 - w_after) + w_after, 4),
             "limit": lim["max_high_vol_share"],
             "text": f"La part d'actifs très volatils dépasserait la limite de {pct(lim['max_high_vol_share'], 0)} "
                     f"prévue pour ton profil."},
        ]
        ev_r = reg.add("rule_hit", "Règles de cohérence déclenchées: C_MAX_SINGLE, C_DRAWDOWN_VS_LOSS, C_HIGH_VOL_SHARE.",
                       "incoherent", None, {"rule_ids": [h["rule_id"] for h in hits]},
                       "rules/coherence_rules.yaml (provisoire)", "core.rules_engine.check_coherence")
        coherence = {
            "verdict": "incoherent",
            "rule_hits": hits,
            "metrics": {"annualized_vol": round(m["vol"], 6), "max_drawdown": round(m["mdd"], 6),
                        "worst_calendar_year_return": round(m["worst_year"], 6), "position_weight_after": w_after},
            "explanation": explanation([
                (f"À {pct(w_after, 0)}, {t} dépasserait la limite de {pct(lim['max_single_position'], 0)} par titre "
                 f"de ton profil.", "fact", [ev_w, ev_r]),
                (f"Sur 5 ans, {t} a connu une chute maximale de {pct(m['mdd'])} et un rendement de "
                 f"{pct(m['ret_2022'])} en 2022.", "fact", [ev_d, ev_y]),
                (f"Sa volatilité annualisée ({pct(m['vol'])}) le classe parmi les actifs très volatils.", "fact", [ev_v]),
                ("Avec un horizon de 4 ans, une chute de cette ampleur pourrait ne pas être récupérée à temps.",
                 "scenario", [ev_d]),
            ], f"Demande incohérente avec ton profil: {t} à {pct(w_after, 0)}."),
        }

    feed = {
        "generated_at": GENERATED_AT, "data_as_of": DATA_AS_OF, "news_as_of": NEWS_AS_OF,
        "profile": profile,
        "portfolio_summary": {"top_positions": positions[:5], "asset_class_weights": ac_weights,
                              "high_vol_share": round(high_vol_share, 6), "top3_concentration": round(top3, 6)},
        "items": items,
        "hidden": {"count": sum(hidden_reasons.values()),
                   "by_reason": [{"reason": r, "count": c} for r, c in sorted(hidden_reasons.items())]},
        "coherence": coherence,
        "events": [
            {"id": "evt_boc_2026_12_09", "type": "rate_decision", "scope": "macro", "tickers": [], "date": "2026-12-09",
             "title": "Décision de taux de la Banque du Canada", "is_estimated": True,
             "source": "Calendrier public de la Banque du Canada (à confirmer)", "retrieved_at": RETRIEVED_AT},
        ],
        "evidence": reg.items,
        "disclaimers": DISCLAIMERS,
        "limits": LIMITS,
    }
    csv = "ticker,montant\n" + "".join(f"{t},{a}\n" for t, a in spec["portfolio"].items())
    persona = {"id": pid, "label": spec["label"], "profile": profile, "sample_portfolio_csv": csv}
    return feed, persona


def main() -> None:
    prices, universe, actions = load()
    OUT.mkdir(parents=True, exist_ok=True)
    personas = []
    for pid in PERSONAS:
        feed, persona = build_persona(pid, prices, universe, actions)
        FeedResponse.model_validate(feed)
        Persona.model_validate(persona)
        (OUT / f"feed_{pid}.json").write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        personas.append(persona)
        print(f"feed_{pid}.json: {len(feed['items'])} items, {feed['hidden']['count']} hidden, "
              f"{len(feed['evidence'])} evidence")
    (OUT / "personas.json").write_text(json.dumps(personas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
