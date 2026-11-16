"""Diversification analyst (pure functions, no LLM).

"Diversifier, c'est varier les expositions" (BN workshop): does the considered asset add
a new source of risk, or duplicate an exposure already held? Uses monthly correlations
over the 5-year window, asset-class and currency exposures before/after the addition.
Thresholds come from rules/instrument_risks.yaml (`diversification`).
Every number returned is backed by an Evidence registered in `registry`.
"""

from __future__ import annotations

from typing import Any

from core import data, metrics
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry, format_num, format_pct, make_evidence

ASSET_CLASS_FR = {"equity_ca": "actions canadiennes", "equity_us": "actions américaines", "equity_etf": "FNB d'actions",
                  "bond_etf": "FNB d'obligations", "gold_etf": "or", "crypto": "cryptoactifs"}
DIVERSIFICATION_FR = {"overlap": "exposition en grande partie en double", "partial": "diversification partielle",
                      "new_exposure": "nouvelle source de risque"}
SOURCE = "portefeuille fourni, data/prices_daily.csv, data/assets_universe.csv"


def _weights_by(positions: list[dict[str, Any]], key: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for p in positions:
        out[p[key]] = out.get(p[key], 0.0) + float(p["weight"])
    return {k: round(v, 6) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}


def _fmt_weights(w: dict[str, float], labels: dict[str, str] | None = None) -> str:
    return ", ".join(f"{(labels or {}).get(k, k)} {format_pct(v, 0)}" for k, v in w.items() if v > 0.0005)


def diversification_impact(portfolio: dict[str, Any], ticker: str, intended_weight: float,
                           registry: EvidenceRegistry, *, overlap_corr: float = 0.8,
                           new_exposure_corr: float = 0.3) -> dict[str, Any]:
    """Diversification impact of reaching `intended_weight` on `ticker` (DiversificationImpact contract dict)."""
    from core.rules_engine import portfolio_after  # local import: rules_engine imports metrics

    uni = data.load_universe()
    if ticker not in uni.index:
        raise AlphaForgeError("UNKNOWN_TICKER", f"{ticker} hors univers")
    before = [p for p in portfolio.get("positions", []) if p.get("in_universe", True)]
    after = portfolio_after(portfolio, ticker, intended_weight)["positions"]
    ids: list[str] = []

    # 1. Correlation with each other held position (listing currency, monthly).
    correlations: list[dict[str, Any]] = []
    for p in before:
        if p["ticker"] == ticker:
            continue
        r = metrics.monthly_correlation(ticker, p["ticker"])
        correlations.append({"ticker": p["ticker"], "weight": round(float(p["weight"]), 6),
                             "correlation": round(float(r.value), 4), "evidence_id": registry.add(r)})
    correlations.sort(key=lambda c: -c["correlation"])
    top = correlations[0] if correlations else None
    if top:
        ids.append(top["evidence_id"])

    corr_rest: float | None = None
    if correlations:
        rc = metrics.corr_to_portfolio(portfolio, ticker)
        corr_rest = round(float(rc.value), 4)
        ids.append(registry.add(rc))

    # 2. Exposures before/after.
    cls_before, cls_after = _weights_by(before, "asset_class"), _weights_by(after, "asset_class")
    ccy_before, ccy_after = _weights_by(before, "price_currency"), _weights_by(after, "price_currency")
    new_class = uni.loc[ticker, "asset_class"] not in cls_before
    already_held = any(p["ticker"] == ticker for p in before)
    exp_ev = make_evidence(
        kind="portfolio_calc",
        statement=(f"Classes d'actifs avant: {_fmt_weights(cls_before, ASSET_CLASS_FR)}; après l'ajout envisagé: "
                   f"{_fmt_weights(cls_after, ASSET_CLASS_FR)}. Devises de cotation après: {_fmt_weights(ccy_after)}."),
        value=len([v for v in cls_after.values() if v > 0]), unit="count", as_of=data.data_as_of(),
        inputs={"ticker": ticker, "intended_weight": intended_weight, "asset_class_before": cls_before,
                "asset_class_after": cls_after, "currency_before": ccy_before, "currency_after": ccy_after},
        source=SOURCE, computed_by="core.diversification.exposures")
    ids.append(registry.add(exp_ev))

    # 3. Verdict (code, thresholds from rules). Correlation first: a new asset class that moves
    # like a held position does not diversify much (e.g. NVDA next to SPY).
    cls_fr = ASSET_CLASS_FR.get(str(uni.loc[ticker, "asset_class"]), "")
    partner = (f" La position la plus proche est {top['ticker']} (corrélation mensuelle {format_num(top['correlation'])})."
               if top else "")
    if already_held:
        verdict, text = "overlap", f"{ticker} est déjà détenu: l'ajout augmente une exposition existante."
    elif top and top["correlation"] >= overlap_corr:
        verdict = "overlap"
        text = (f"{ticker} a évolué presque comme {top['ticker']}, déjà détenu (corrélation mensuelle "
                f"{format_num(top['correlation'])}, seuil {format_num(overlap_corr)}): exposition en grande partie en double.")
    elif corr_rest is None or corr_rest < new_exposure_corr:
        verdict = "new_exposure"
        reason = ("aucune autre position pour comparer" if corr_rest is None else
                  f"corrélation avec le reste du portefeuille de {format_num(corr_rest)}, sous le seuil "
                  f"{format_num(new_exposure_corr)}")
        text = f"{ticker} ajoute une source de risque différente ({reason}).{partner}"
    else:
        verdict = "partial"
        extra = f" C'est une nouvelle classe d'actifs ({cls_fr}), mais elle n'évolue pas de façon indépendante."             if new_class else ""
        text = (f"{ticker} diversifie en partie: corrélation de {format_num(corr_rest)} avec le reste du portefeuille "
                f"(entre {format_num(new_exposure_corr)} et {format_num(overlap_corr)}).{extra}{partner}")
    verdict_ev = make_evidence(
        kind="portfolio_calc", statement=text, value=DIVERSIFICATION_FR[verdict], unit=None, as_of=data.data_as_of(),
        inputs={"verdict": verdict, "ticker": ticker, "intended_weight": intended_weight, "max_corr_ticker": top["ticker"] if top else None,
                "max_corr": top["correlation"] if top else None, "corr_to_portfolio": corr_rest,
                "new_asset_class": new_class, "already_held": already_held, "overlap_corr": overlap_corr,
                "new_exposure_corr": new_exposure_corr},
        source="rules/instrument_risks.yaml (diversification)", computed_by="core.diversification.diversification_impact")
    verdict_id = registry.add(verdict_ev)
    return {
        "ticker": ticker,
        "verdict": verdict,
        "text_fr": text,
        "correlations": correlations,
        "corr_to_portfolio": corr_rest,
        "asset_class_before": cls_before,
        "asset_class_after": cls_after,
        "currency_before": ccy_before,
        "currency_after": ccy_after,
        "n_asset_classes_before": len(cls_before),
        "n_asset_classes_after": len(cls_after),
        "evidence_ids": [verdict_id, *[i for i in ids if i != verdict_id]],
    }
