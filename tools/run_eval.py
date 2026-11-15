"""Evaluate the headline classifier against role D's labels (A8).

Usage: python -m tools.run_eval [--labels eval/labeled_headlines.csv] [--out eval/reports]

Columns used: id, title, ticker, category, controversy (true/false), is_synthetic.
Writes eval/reports/classifier_<YYYYMMDD>.md: global and per-category agreement,
controversy agreement, confusion matrix, error examples. Uses LLM_PROVIDER
(mock = keyword classifier, bedrock = real model).
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents.classifier import Classifier
from agents.llm import LLMUnavailableError, get_client
from core import rules_engine

ROOT = Path(__file__).resolve().parent.parent
TARGET = 0.80


def _bool(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "vrai", "oui", "yes")


def load_labels(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = {"id", "title", "category"} - set(rows[0].keys() if rows else [])
    if missing:
        raise ValueError(f"colonnes manquantes dans {path.name}: {sorted(missing)}")
    return rows


def evaluate(rows: list[dict[str, Any]], classifier: Classifier) -> dict[str, Any]:
    results = []
    for r in rows:
        rec = {"id": f"eval_{r['id']}", "title": r["title"], "snippet": None}
        try:
            pred = classifier.classify(rec)
        except LLMUnavailableError as exc:
            pred = {"category": "ERREUR", "controversy": None, "error": str(exc)}
        results.append({"id": r["id"], "title": r["title"], "expected": r["category"].strip(),
                        "predicted": pred["category"], "exp_contro": _bool(r.get("controversy", "false")),
                        "pred_contro": pred.get("controversy"), "is_synthetic": _bool(r.get("is_synthetic", ""))})
    n = len(results)
    ok = sum(x["expected"] == x["predicted"] for x in results)
    contro_ok = sum(x["exp_contro"] == x["pred_contro"] for x in results)
    per_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    confusion: Counter[tuple[str, str]] = Counter()
    for x in results:
        per_cat[x["expected"]][1] += 1
        per_cat[x["expected"]][0] += x["expected"] == x["predicted"]
        confusion[(x["expected"], x["predicted"])] += 1
    return {"n": n, "accuracy": ok / n if n else 0.0, "controversy_accuracy": contro_ok / n if n else 0.0,
            "per_category": {k: {"correct": v[0], "total": v[1], "accuracy": v[0] / v[1]} for k, v in per_cat.items()},
            "confusion": confusion, "errors": [x for x in results if x["expected"] != x["predicted"]],
            "results": results, "model_id": classifier.model_id, "prompt_version": classifier.prompt_version,
            "n_synthetic": sum(x["is_synthetic"] for x in results)}


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def report_md(ev: dict[str, Any], labels_path: Path) -> str:
    cats = sorted({c for pair in ev["confusion"] for c in pair})
    verdict = "atteint" if ev["accuracy"] >= TARGET else "NON atteint"
    lines = [
        f"# Évaluation du classifieur — {datetime.now(UTC):%Y-%m-%d}", "",
        f"- Étiquettes: `{labels_path.relative_to(ROOT) if labels_path.is_relative_to(ROOT) else labels_path}` "
        f"({ev['n']} titres, dont {ev['n_synthetic']} fictifs).",
        f"- Modèle: `{ev['model_id']}`, prompt `{ev['prompt_version']}`.",
        f"- **Accord global sur la catégorie: {_pct(ev['accuracy'])}** (objectif {_pct(TARGET)}: {verdict}).",
        f"- Accord sur le drapeau de controverse: {_pct(ev['controversy_accuracy'])}.", "",
        "## Accord par catégorie", "", "| Catégorie attendue | Correct | Total | Accord |", "| --- | --- | --- | --- |",
    ]
    lines += [f"| {k} | {v['correct']} | {v['total']} | {_pct(v['accuracy'])} |"
              for k, v in sorted(ev["per_category"].items())]
    lines += ["", "## Matrice de confusion (lignes: attendu, colonnes: prédit)", "",
              "| attendu \\ prédit | " + " | ".join(cats) + " |", "|" + " --- |" * (len(cats) + 1)]
    for a in cats:
        lines.append(f"| {a} | " + " | ".join(str(ev["confusion"].get((a, b), "")) for b in cats) + " |")
    lines += ["", "## Exemples d'erreurs", ""]
    lines += [f"- `{x['id']}` « {x['title']} »: attendu **{x['expected']}**, prédit **{x['predicted']}**"
              for x in ev["errors"][:20]] or ["- Aucune."]
    lines += ["", "Limites: petit échantillon; une seule personne étiquette; les catégories proches "
              "(stratégie, produit, résultats) se confondent facilement.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default=str(ROOT / "eval" / "labeled_headlines.csv"))
    parser.add_argument("--out", default=str(ROOT / "eval" / "reports"))
    args = parser.parse_args(argv)
    labels = Path(args.labels)
    if not labels.exists():
        print(f"Fichier d'étiquettes absent: {labels}. Le rôle D doit le créer (eval/labeled_headlines.csv).")
        return 1
    clf = Classifier(get_client(), rules_engine.load_rules().taxonomy)
    ev = evaluate(load_labels(labels), clf)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"classifier_{datetime.now(UTC):%Y%m%d}.md"
    path.write_text(report_md(ev, labels), encoding="utf-8")
    print(f"Accord global: {_pct(ev['accuracy'])} sur {ev['n']} titres ({ev['model_id']}). Rapport: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
