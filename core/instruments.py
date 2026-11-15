"""Risk analyst: what you really own and the risks to understand, by instrument type.

Text comes from rules/instrument_risks.yaml (role D); the code only selects the
asset's class and adds a currency line when the listing currency is not CAD.
"""

from __future__ import annotations

from typing import Any

from core import data
from core.errors import AlphaForgeError


def instrument_risks(ticker: str) -> dict[str, Any]:
    """InstrumentRisks contract dict for one asset of the universe."""
    from core.rules_engine import load_rules

    uni = data.load_universe()
    if ticker not in uni.index:
        raise AlphaForgeError("UNKNOWN_TICKER", f"{ticker} hors univers")
    cfg = load_rules().instrument_risks
    cls_id = str(uni.loc[ticker, "asset_class"])
    if cfg is None or cls_id not in cfg.asset_classes:
        raise AlphaForgeError("RULES_UNAVAILABLE", f"Aucun profil de risque pour la classe {cls_id}.", status=500)
    types = {t.id: t for t in cfg.risk_types}
    cls = cfg.asset_classes[cls_id]
    risks = [{"risk": r.risk, "label_fr": types[r.risk].label_fr, "question_fr": types[r.risk].question_fr,
              "level": r.level, "text_fr": r.text_fr} for r in cls.risks]
    ccy = str(uni.loc[ticker, "price_currency"])
    if ccy != "CAD" and not any(r["risk"] == "currency" for r in risks) and "currency" in types:
        risks.append({"risk": "currency", "label_fr": types["currency"].label_fr,
                      "question_fr": types["currency"].question_fr, "level": "medium",
                      "text_fr": f"Coté en {ccy}: pour un investisseur en CAD, le taux de change modifie le résultat."})
    return {"ticker": ticker, "name": str(uni.loc[ticker, "name"]), "asset_class": cls_id, "label_fr": cls.label_fr,
            "what_you_own_fr": cls.what_you_own_fr, "return_source_fr": cls.return_source_fr,
            "price_currency": ccy, "risks": risks, "source": "rules/instrument_risks.yaml"}
