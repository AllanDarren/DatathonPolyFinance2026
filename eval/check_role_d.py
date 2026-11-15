"""Local data audit for role D; does not replace the production rule engine or schemas."""
from __future__ import annotations

import csv
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = set('RY.TO TD.TO MFC.TO ENB.TO CNQ.TO CNR.TO FTS.TO ATD.TO SHOP.TO CSU.TO AAPL MSFT NVDA GOOGL AMZN TSLA JPM JNJ PG XOM XIU.TO SPY QQQ ESGV XBB.TO ZST.TO AGG TLT GLD BTC-USD ETH-USD'.split())
MISSING = object()


def read(path: str) -> Any:
    return yaml.safe_load((ROOT / path).read_text(encoding='utf-8'))


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def lookup(data: dict, path: str) -> Any:
    value = data
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return MISSING
        value = value[part]
    return value


def assign(data: dict, path: str, value: Any) -> None:
    parts = path.split('.')
    for part in parts[:-1]:
        data = data.setdefault(part, {})
    data[parts[-1]] = value


def matches(condition: dict, context: dict, metrics: dict | None = None) -> bool:
    if 'metric' in condition:
        left = (metrics or {}).get(condition['metric'], MISSING)
    else:
        left = lookup(context, condition['field'])
    right = lookup(context, condition['limit_from']) if 'limit_from' in condition else condition.get('value', MISSING)
    if left is MISSING or right is MISSING:
        return False
    op = condition['op']
    if op == '==':
        return left == right
    if left is None or right is None:
        return False
    if op == '>':
        return left > right
    if op == '<=':
        return left <= right
    if op == 'in':
        return left in right
    if op == 'contains':
        return right in left
    raise ValueError(f'Opérateur inconnu : {op}')


def audit() -> dict:
    questionnaire = read('rules/questionnaire.yaml')
    profile_rules = read('rules/profile_rules.yaml')
    taxonomy = read('rules/taxonomy.yaml')
    relevance = read('rules/relevance_rules.yaml')
    coherence = read('rules/coherence_rules.yaml')
    documents = [questionnaire, profile_rules, taxonomy, relevance, coherence]
    require(all(d['version'] == 1 for d in documents), 'Versions de règles différentes de v1.')
    questions = questionnaire['questions']
    require(6 <= len(questions) <= 7, 'Questionnaire hors de la limite 6–7 questions.')
    require(len({q['id'] for q in questions}) == len(questions), 'Question dupliquée.')
    for question in questions:
        options = question['options']
        require(len({o['id'] for o in options}) == len(options), 'Option dupliquée.')
        require(all('sets' in o or 'points' in o for o in options), 'Option sans effet.')
    categories = {c['id']: c for c in taxonomy['categories']}
    require(10 <= len(categories) <= 12 and len(categories) == len(taxonomy['categories']), 'Catégories manquantes ou dupliquées.')
    for category in categories.values():
        require(len(category['examples']) == 3, 'Trois exemples requis par catégorie.')
        require(category['horizon_relevance'] in {'structural', 'macro_context', 'short_term_noise'}, 'Horizon de nouvelle invalide.')
    for weights in relevance['base_weights'].values():
        require(set(weights) == set(categories), 'Poids de base incomplets.')
        require(all(0 <= w <= 1 for w in weights.values()), 'Poids de base hors limites.')
    require(0 <= relevance['thresholds']['show'] < relevance['thresholds']['high'] <= 1, 'Seuils invalides.')
    ids = [r['id'] for r in relevance['modifiers'] + coherence['rules'] + profile_rules['inconsistency_checks']]
    require(len(ids) == len(set(ids)), 'Identifiant de règle dupliqué.')
    allowed_metrics = {'annualized_vol', 'max_drawdown', 'max_drawdown_abs', 'recovery_days', 'calendar_year_return', 'worst_calendar_year_return', 'return_5y', 'dividend_yield_ttm', 'position_weight', 'position_weight_after', 'is_high_vol', 'high_vol_share', 'top3_concentration', 'asset_class', 'corr_to_portfolio'}
    for rule in coherence['rules'] + relevance['modifiers'] + profile_rules['inconsistency_checks']:
        require(bool(rule['text_fr']) and bool(rule['when']), 'Règle sans texte ou condition.')
        for condition in rule['when']:
            require(condition['op'] in {'==', '>', '<=', 'in', 'contains'}, 'Comparaison inconnue.')
            require(('field' in condition) != ('metric' in condition), 'Condition ambiguë.')
            require(('limit_from' in condition) != ('value' in condition), 'Limite ambiguë.')
            if 'metric' in condition:
                require(condition['metric'] in allowed_metrics, 'Métrique hors section 10.')
    profiles = {}
    totals = {}
    expected_keys = set('profile_id label source age horizon_years horizon_bucket risk_tolerance max_acceptable_loss_pct objective experience preferences limits monthly_expenses_cad base_currency inconsistencies'.split())
    for pid in ['amira', 'mateo', 'robert']:
        p = read(f'rules/personas/{pid}.yaml')
        require(set(p) == expected_keys, f'Champs de Profile incomplets : {pid}')
        require(p['profile_id'] == pid and p['source'] == 'persona_preset' and p['base_currency'] == 'CAD', f'Identité invalide : {pid}')
        require(0 <= p['max_acceptable_loss_pct'] <= 1, 'Perte acceptable hors limites.')
        require(p['limits'] == profile_rules['limits_by_risk'][p['risk_tolerance']], 'Limites du persona incohérentes.')
        require(all(0 <= v <= 1 for v in p['limits'].values()), 'Limites hors [0,1].')
        profiles[pid] = p
        with (ROOT / f'rules/personas/{pid}_portfolio.csv').open() as f:
            reader = csv.DictReader(f)
            require(reader.fieldnames == ['ticker', 'montant'], 'En-tête CSV invalide.')
            rows = list(reader)
        require(len({r['ticker'] for r in rows}) == len(rows), 'Ticker dupliqué.')
        require(all(r['ticker'] in UNIVERSE and Decimal(r['montant']) > 0 for r in rows), 'Position invalide.')
        total = sum(Decimal(r['montant']) for r in rows)
        require(total == 100000, f'Total incorrect pour {pid} : {total}')
        totals[pid] = str(total)
    for case in read('eval/profile_cases.yaml')['cases']:
        actual = {'preferences': {}, 'monthly_expenses_cad': None, 'base_currency': 'CAD'}
        points = 0
        for question in questions:
            option = next(o for o in question['options'] if o['id'] == case['answers'][question['id']])
            for path, value in option.get('sets', {}).items():
                assign(actual, path, value)
            points += option.get('points', {}).get('risk', 0)
        actual['risk_tolerance'] = next(x['value'] for x in profile_rules['risk_from_points'] if points <= x['max_points'])
        actual['horizon_bucket'] = next(x['id'] for x in profile_rules['horizon_buckets'] if actual['horizon_years'] <= x['max_years'])
        actual['limits'] = profile_rules['limits_by_risk'][actual['risk_tolerance']]
        actual['inconsistencies'] = [r['text_fr'] for r in profile_rules['inconsistency_checks'] if all(matches(c, actual) for c in r['when'])]
        expected = read(case['expected_profile'])
        for field in case['compare_fields']:
            require(actual[field] == expected[field], f'Questionnaire {case["id"]} : {field} différent.')
    with (ROOT / 'eval/labeled_headlines.csv').open() as f:
        headlines = list(csv.DictReader(f))
    require(len(headlines) == 30 and len({r['id'] for r in headlines}) == 30, '30 titres uniques requis.')
    require({r['category'] for r in headlines} == set(categories), 'Couverture des catégories incomplète.')
    differences = set()
    for row in headlines:
        require(row['is_synthetic'] == 'true' and row['ticker'] in UNIVERSE, 'Titre non étiqueté fictif ou ticker inconnu.')
        require(row['horizon_relevance'] == categories[row['category']]['horizon_relevance'], 'Horizon incorrect.')
        for pid, p in profiles.items():
            item = dict(category=row['category'], controversy=row['controversy'] == 'true', tickers=[row['ticker']])
            context = dict(profile=p, item=item, position_weight=.10)
            score = Decimal(str(relevance['base_weights'][p['horizon_bucket']][row['category']]))
            score += max((Decimal(str(b['add'])) for b in relevance['position_weight_bonus'] if .10 >= b['min_weight']), default=Decimal(0))
            score += sum((Decimal(str(r['add'])) for r in relevance['modifiers'] if all(matches(c, context) for c in r['when'])), Decimal(0))
            score = min(Decimal(1), max(Decimal(0), score))
            level = 'high' if score >= Decimal(str(relevance['thresholds']['high'])) else 'medium' if score >= Decimal(str(relevance['thresholds']['show'])) else 'low'
            require(level == row[f'expected_relevance_{pid}'], f'Pertinence incorrecte : {row["id"]}/{pid}')
        if row['expected_relevance_robert'] != row['expected_relevance_amira']:
            differences.add(row['category'])
    require(len(differences) >= 3, 'Au moins trois catégories doivent différer entre Robert et Amira.')
    for case in read('eval/coherence_cases.yaml')['cases']:
        hits = [r for r in coherence['rules'] if all(matches(c, {'profile': profiles[case['profile_id']]}, case['metrics']) for c in r['when'])]
        verdict = 'incoherent' if any(r['severity'] == 'high' for r in hits) else 'tension' if any(r['severity'] == 'medium' for r in hits) else 'coherent'
        require(verdict == case['expected_verdict'], f'Verdict différent : {case["id"]}')
        require(sorted(r['id'] for r in hits) == sorted(case['expected_rule_ids']), f'Règles différentes : {case["id"]}')
    # Missing data must not trigger the null/recovery rule.
    require(not matches({'metric': 'recovery_days', 'op': '==', 'value': None}, {}, {}), 'Métrique absente confondue avec sommet non retrouvé.')
    terms = read('rules/glossary.yaml')['terms']
    require(len(terms) == len({t['id'] for t in terms}) == 25, '25 termes uniques requis.')
    require(all(t['term'] and t['definition_fr'] for t in terms), 'Terme vide.')
    texts = read('rules/limits_texts.yaml')
    require(bool(texts['limits']) and bool(texts['disclaimers']), 'Textes de limites manquants.')
    with (ROOT / 'eval/independent_checks.csv').open() as f:
        checks = list(csv.DictReader(f))
    for row in checks:
        kind = row['method']
        a, b = float(row['input_a']), float(row['input_b'])
        calculated = a / b if kind == 'weight' else a / b - 1 if kind in {'return', 'drawdown', 'inflation'} else a * math.sqrt(b)
        require(math.isclose(calculated, float(row['reference_value']), abs_tol=1e-10), f'Valeur de référence incorrecte : {row["id"]}')
    return {'personas': len(profiles), 'totaux_CAD': totals, 'questions': len(questions), 'titres_fictifs': len(headlines), 'categories_differentes_robert_amira': sorted(differences), 'cas_coherence': len(read('eval/coherence_cases.yaml')['cases']), 'termes': len(terms), 'calculs_controles': len(checks)}


if __name__ == '__main__':
    try:
        result = audit()
    except (ValueError, KeyError, StopIteration, TypeError) as exc:
        raise SystemExit(f'ÉCHEC du contrôle local D : {exc}') from exc
    print('OK — contrôle local des données D (hors schémas et application).')
    for key, value in result.items():
        print(f'  {key}: {value}')
