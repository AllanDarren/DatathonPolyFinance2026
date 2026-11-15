"""Validate role D's rule files (`make validate-rules`).

Usage: python -m tools.validate_rules [--dir rules] [--strict]

Messages are written for someone who does not write code: which file, where in the
file, what is wrong and how to fix it. Exit code 1 if any error (or any warning
with --strict). A missing file is a warning: the app then uses the reference
example from contracts/rules/examples/.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from core.errors import AlphaForgeError
from core.models import Profile
from core.rules_engine import COHERENCE_METRICS, PERSONA_IDS, PROFILE_FIELDS, RELEVANCE_FIELDS, ROOT
from core.rules_models import (
    RULE_FILES,
    CoherenceRules,
    Condition,
    ProfileRules,
    Questionnaire,
    RelevanceRules,
    Taxonomy,
)

QUESTIONNAIRE_SETTABLE = {
    "horizon_years", "max_acceptable_loss_pct", "objective", "experience", "monthly_expenses_cad", "age",
    "risk_tolerance", "preferences.avoid_controversies", "preferences.excluded_sectors", "preferences.interests",
}
REQUIRED_PROFILE_INPUTS = {"horizon_years", "max_acceptable_loss_pct", "objective", "experience"}
RISK_LEVELS = {"low", "low_moderate", "moderate", "high"}
BUCKETS = {"short", "medium", "long"}

_TYPE_MESSAGES = {
    "missing": "ce champ est obligatoire et il manque",
    "extra_forbidden": "ce champ n'est pas prévu (faute de frappe?)",
    "string_type": "on attend du texte",
    "int_type": "on attend un nombre entier",
    "int_parsing": "on attend un nombre entier",
    "float_type": "on attend un nombre",
    "float_parsing": "on attend un nombre (avec un point décimal, ex.: 0.25)",
    "bool_type": "on attend true ou false",
    "bool_parsing": "on attend true ou false",
    "list_type": "on attend une liste (ex.: [a, b] ou des lignes commençant par « - »)",
    "dict_type": "on attend une section avec des clés (ex.: nom: valeur)",
    "model_type": "on attend une section avec des clés (ex.: nom: valeur)",
    "literal_error": "valeur non permise",
    "too_short": "la liste est trop courte",
    "greater_than_equal": "la valeur est trop petite",
    "less_than_equal": "la valeur est trop grande",
    "greater_than": "la valeur est trop petite",
    "less_than": "la valeur est trop grande",
}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    def error(self, file: str, where: str, msg: str) -> None:
        self.errors.append(f"✗ {file}{f' → {where}' if where else ''}: {msg}")

    def warn(self, file: str, where: str, msg: str) -> None:
        self.warnings.append(f"! {file}{f' → {where}' if where else ''}: {msg}")


def _where(loc: tuple[Any, ...]) -> str:
    parts = []
    for p in loc:
        parts.append(f"élément n° {p + 1}" if isinstance(p, int) else str(p))
    return " → ".join(parts)


def _explain(err: dict[str, Any]) -> str:
    base = _TYPE_MESSAGES.get(err["type"], err["msg"])
    if err["type"] == "literal_error":
        expected = err.get("ctx", {}).get("expected", "")
        base = f"valeur non permise; valeurs possibles: {expected}"
    if err["type"] == "value_error":
        base = str(err["msg"]).removeprefix("Value error, ")
    got = err.get("input")
    if err["type"] not in ("missing",) and not isinstance(got, dict | list):
        base += f" (trouvé: {got!r})"
    return base


def _load(path: Path, rep: Report) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = f"ligne {mark.line + 1}" if mark else ""
        hint = ""
        if "mapping values" in str(getattr(exc, "problem", "")):
            hint = " Un texte qui contient « : » doit être entre guillemets, ex.: text_fr: \"Limite: {limit}\"."
        rep.error(path.name, line, "le fichier YAML est illisible (indentation, deux-points ou guillemets?). "
                  f"Détail: {getattr(exc, 'problem', exc)}.{hint}")
        return None


def _check_conditions(file: str, where: str, conds: list[Condition], rep: Report, *, allowed_fields: set[str],
                      allow_metrics: bool, prefix_profile: bool) -> None:
    for i, c in enumerate(conds, 1):
        loc = f"{where} → when → condition n° {i}"
        if c.metric is not None:
            if not allow_metrics:
                rep.error(file, loc, "« metric » n'est pas permis ici; utilise « field ».")
            elif c.metric not in COHERENCE_METRICS:
                rep.error(file, loc, f"métrique inconnue « {c.metric} ». Métriques possibles: "
                          f"{', '.join(sorted(COHERENCE_METRICS))}.")
        paths = [p for p in (c.field, c.right_path) if p]
        for p in paths:
            ok = p in allowed_fields
            if prefix_profile and p.startswith("profile."):
                ok = p.removeprefix("profile.") in PROFILE_FIELDS
            if not ok:
                rep.error(file, loc, f"chemin inconnu « {p} ». Chemins possibles: "
                          f"{', '.join(sorted(allowed_fields | ({'profile.<champ du profil>'} if prefix_profile else set())))}.")
        if c.op in ("contains", "not_contains") and isinstance(c.value, list):
            rep.warn(file, loc, "« contains » compare à une seule valeur, pas à une liste.")
        if c.op in ("in", "not_in") and c.value is not None and not isinstance(c.value, list):
            rep.error(file, loc, "avec « in », « value » doit être une liste, ex.: [low, low_moderate].")


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def validate(rules_dir: Path) -> Report:
    rep = Report()
    models: dict[str, Any] = {}
    for name, model in RULE_FILES.items():
        path = rules_dir / name
        if not path.exists():
            rep.warn(name, "", "fichier absent: l'application utilise l'exemple de contracts/rules/examples/.")
            example = ROOT / "contracts" / "rules" / "examples" / name
            raw = yaml.safe_load(example.read_text(encoding="utf-8"))
            models[name] = model.model_validate(raw)
            continue
        raw = _load(path, rep)
        if raw is None:
            continue
        rep.checked.append(name)
        try:
            models[name] = model.model_validate(raw)
        except ValidationError as exc:
            for err in exc.errors(include_url=False):
                rep.error(name, _where(err["loc"]), _explain(err))

    q: Questionnaire | None = models.get("questionnaire.yaml")
    pr: ProfileRules | None = models.get("profile_rules.yaml")
    tx: Taxonomy | None = models.get("taxonomy.yaml")
    rr: RelevanceRules | None = models.get("relevance_rules.yaml")
    cr: CoherenceRules | None = models.get("coherence_rules.yaml")

    if q:
        f = "questionnaire.yaml"
        ids = [x.id for x in q.questions]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            rep.error(f, dup, "deux questions ont le même id.")
        settable: set[str] = set()
        for qu in q.questions:
            oids = [o.id for o in qu.options]
            for dup in sorted({i for i in oids if oids.count(i) > 1}):
                rep.error(f, qu.id, f"deux options ont le même id « {dup} ».")
            for o in qu.options:
                for key in o.sets:
                    if key not in QUESTIONNAIRE_SETTABLE:
                        rep.error(f, f"{qu.id} → {o.id} → sets", f"champ « {key} » non modifiable. Champs possibles: "
                                  f"{', '.join(sorted(QUESTIONNAIRE_SETTABLE))}.")
                    settable.add(key)
                for key in o.points:
                    if key != "risk":
                        rep.warn(f, f"{qu.id} → {o.id} → points", f"points « {key} » ignorés (seul « risk » est utilisé).")
        if pr:
            missing = REQUIRED_PROFILE_INPUTS - settable - set(pr.defaults)
            for m in sorted(missing):
                rep.error("profile_rules.yaml", "defaults", f"aucune question ni valeur par défaut ne fixe « {m} »: "
                          "ajoute-le dans « defaults » ou dans une option du questionnaire.")
        if not any(o.points.get("risk") for qu in q.questions for o in qu.options) and "risk_tolerance" not in settable:
            rep.error(f, "", "aucune option ne donne de points « risk »: la tolérance au risque ne peut pas être calculée.")

    if pr:
        f = "profile_rules.yaml"
        found = {b.id for b in pr.horizon_buckets}
        if found != BUCKETS:
            rep.error(f, "horizon_buckets", f"il faut exactement les tranches short, medium et long (trouvé: {sorted(found)}).")
        mx = [b.max_years for b in pr.horizon_buckets]
        if mx != sorted(mx):
            rep.error(f, "horizon_buckets", "les tranches doivent être en ordre croissant de max_years.")
        pts = [t.max_points for t in pr.risk_from_points]
        if pts != sorted(pts):
            rep.error(f, "risk_from_points", "les paliers doivent être en ordre croissant de max_points.")
        missing_lv = RISK_LEVELS - set(pr.limits_by_risk)
        if missing_lv:
            rep.error(f, "limits_by_risk", f"niveaux de risque sans limites: {', '.join(sorted(missing_lv))}.")
        for key in pr.defaults:
            if key not in QUESTIONNAIRE_SETTABLE:
                rep.error(f, f"defaults → {key}", "champ inconnu.")
        for chk in pr.inconsistency_checks:
            _check_conditions(f, chk.id, chk.when, rep, allowed_fields=PROFILE_FIELDS, allow_metrics=False,
                              prefix_profile=False)

    cat_ids: set[str] = set()
    if tx:
        f = "taxonomy.yaml"
        ids = [c.id for c in tx.categories]
        cat_ids = set(ids)
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            rep.error(f, dup, "deux catégories ont le même id.")
        for c in tx.categories:
            if len(c.examples) < 3:
                rep.warn(f, c.id, f"{len(c.examples)} exemple(s) seulement; 3 sont recommandés pour le classifieur.")
        if not 6 <= len(ids) <= 14:
            rep.warn(f, "categories", f"{len(ids)} catégories; 10 à 12 sont recommandées.")

    if rr:
        f = "relevance_rules.yaml"
        if set(rr.base_weights) != BUCKETS:
            rep.error(f, "base_weights", f"il faut une ligne pour short, medium et long (trouvé: {sorted(rr.base_weights)}).")
        for bucket, weights in rr.base_weights.items():
            for cat, w in weights.items():
                if cat_ids and cat not in cat_ids:
                    rep.error(f, f"base_weights → {bucket} → {cat}", "catégorie absente de taxonomy.yaml.")
                if not 0 <= w <= 1:
                    rep.error(f, f"base_weights → {bucket} → {cat}", f"le poids doit être entre 0 et 1 (trouvé: {w}).")
            for cat in sorted(cat_ids - set(weights)):
                rep.warn(f, f"base_weights → {bucket}", f"pas de poids pour « {cat} » (0 sera utilisé).")
        unknown_ph = _placeholders(rr.base_rule_text_fr) - {"category", "weight", "horizon_bucket"}
        if unknown_ph:
            rep.error(f, "base_rule_text_fr", f"repère(s) inconnu(s): {', '.join(sorted(unknown_ph))}. "
                      "Repères possibles: {category}, {weight}, {horizon_bucket}.")
        mids = [m.id for m in rr.modifiers]
        for dup in sorted({i for i in mids if mids.count(i) > 1}):
            rep.error(f, dup, "deux règles ont le même id.")
        for m in rr.modifiers:
            _check_conditions(f, m.id, m.when, rep, allowed_fields=RELEVANCE_FIELDS, allow_metrics=False,
                              prefix_profile=True)
        if rr.thresholds.show > rr.thresholds.high:
            rep.error(f, "thresholds", "le seuil « show » doit être inférieur ou égal au seuil « high ».")

    if cr:
        f = "coherence_rules.yaml"
        rids = [r.id for r in cr.rules]
        for dup in sorted({i for i in rids if rids.count(i) > 1}):
            rep.error(f, dup, "deux règles ont le même id.")
        for r in cr.rules:
            _check_conditions(f, r.id, r.when, rep, allowed_fields={"consideration.ticker", "consideration.intended_weight"},
                              allow_metrics=True, prefix_profile=True)
            unknown_ph = _placeholders(r.text_fr) - {"limit", "observed", "ticker"}
            if unknown_ph:
                rep.error(f, f"{r.id} → text_fr", f"repère(s) inconnu(s): {', '.join(sorted(unknown_ph))}. "
                          "Repères possibles: {limit}, {observed}, {ticker}.")

    _validate_personas(rules_dir, rep)
    return rep


def _validate_personas(rules_dir: Path, rep: Report) -> None:
    from core.portfolio import parse_portfolio

    pdir = rules_dir / "personas"
    for pid in PERSONA_IDS:
        name = f"personas/{pid}.yaml"
        path = pdir / f"{pid}.yaml"
        if not path.exists():
            rep.warn(name, "", "fichier absent: l'application utilise l'exemple.")
        else:
            rep.checked.append(name)
            raw = _load(path, rep)
            if raw is not None:
                try:
                    prof = Profile.model_validate(raw)
                    if prof.profile_id != pid:
                        rep.error(name, "profile_id", f"doit valoir « {pid} » (trouvé: {prof.profile_id!r}).")
                except ValidationError as exc:
                    for err in exc.errors(include_url=False):
                        rep.error(name, _where(err["loc"]), _explain(err))
        cname = f"personas/{pid}_portfolio.csv"
        cpath = pdir / f"{pid}_portfolio.csv"
        if not cpath.exists():
            rep.warn(cname, "", "fichier absent: l'application utilise l'exemple.")
            continue
        rep.checked.append(cname)
        try:
            port = parse_portfolio(cpath.read_text(encoding="utf-8"))
        except AlphaForgeError as exc:
            rep.error(cname, "", exc.message)
            continue
        if port["unanalyzed"]["tickers"]:
            rep.error(cname, "", f"tickers hors des 31 actifs: {', '.join(port['unanalyzed']['tickers'])}.")
        if abs(port["total_amount"] - 100000) > 0.5:
            rep.warn(cname, "", f"le total est de {port['total_amount']:.0f} $ (100 000 $ prévus).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vérifie les fichiers de règles du rôle D.")
    parser.add_argument("--dir", default=str(ROOT / "rules"), help="dossier des règles (défaut: rules/)")
    parser.add_argument("--strict", action="store_true", help="les avertissements comptent comme des erreurs")
    args = parser.parse_args(argv)
    rules_dir = Path(args.dir)
    rep = validate(rules_dir)
    print(f"Vérification des règles dans {rules_dir}")
    for line in rep.errors + rep.warnings:
        print("  " + line)
    if rep.checked:
        print(f"Fichiers vérifiés: {', '.join(rep.checked)}")
    if rep.errors:
        print(f"Résultat: {len(rep.errors)} erreur(s) à corriger, {len(rep.warnings)} avertissement(s).")
        return 1
    if rep.warnings and args.strict:
        print(f"Résultat: aucune erreur, mais {len(rep.warnings)} avertissement(s) (mode strict).")
        return 1
    print(f"Résultat: tout est valide ({len(rep.warnings)} avertissement(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
