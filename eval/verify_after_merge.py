"""D acceptance checks against the v0 API, using only fictional persona portfolios.

Run after A/B merge: python3 eval/verify_after_merge.py --api-url http://localhost:8000 --metric-basis CAD
This is a targeted acceptance audit, not full schema or semantic validation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]


def near(actual, expected, tolerance=1e-10):
    if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
        raise ValueError('Valeur numérique absente ou non finie.')
    if abs(actual - expected) > tolerance:
        raise ValueError(f'Valeur {actual}; référence {expected}; tolérance {tolerance}.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect_explanation(explanation, evidence):
    require(isinstance(explanation, dict), 'Explication absente.')
    guardian = explanation['guardian']
    require(guardian['status'] in {'passed', 'flagged', 'not_run'}, 'Statut gardien invalide.')
    for claim in explanation['claims']:
        require(claim['label'] in {'fact', 'hypothesis', 'scenario'}, 'Étiquette claim invalide.')
        require(claim['verified'] in {'supported', 'unsupported', 'not_checked'}, 'Vérification claim invalide.')
        require('{{' not in claim['text'], 'Repère de preuve non rendu.')
        references = claim['evidence_ids']
        require(all(key in evidence for key in references), 'Claim citant une preuve inexistante.')
        if claim['verified'] == 'supported':
            require(bool(references), 'Claim soutenu sans preuve.')
        if guardian['status'] == 'passed':
            require(claim['verified'] == 'supported', 'Gardien passed malgré un claim non soutenu.')
    require(guardian['status'] != 'flagged' or bool(guardian['flags']), 'Gardien flagged sans raison.')


def inspect_feed(feed):
    evidence = feed['evidence']
    require(bool(feed['disclaimers']) and bool(feed['limits']), 'Avertissements ou limites absents.')
    for key, proof in evidence.items():
        require(proof['id'] == key, 'Identifiant de preuve incohérent.')
        require(bool(proof['source']) and bool(proof['computed_by']) and bool(proof['as_of']), 'Provenance de preuve incomplète.')
        require('inputs' in proof and 'value' in proof, 'Entrées ou valeur de preuve absentes.')
    for item in feed['items']:
        inspect_explanation(item['explanation'], evidence)
        context = item.get('historical_context')
        if context is not None:
            require(context['n_events'] >= 8, 'Contexte historique avec moins de huit cas.')
            require(context['evidence_id'] in evidence, 'Preuve du contexte historique absente.')
            require(bool(context['caveats']), 'Limites historiques absentes.')
    if feed['coherence'] is not None:
        inspect_explanation(feed['coherence']['explanation'], evidence)


class API:
    def __init__(self, base_url, timeout=60):
        parsed = urlparse(base_url)
        require(parsed.scheme in {'http', 'https'} and bool(parsed.netloc), 'URL API invalide.')
        require(not parsed.username and not parsed.password and not parsed.query and not parsed.fragment, 'URL API sans identifiants, paramètres ni fragment attendue.')
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def __call__(self, method, path, body=None):
        request = Request(self.base_url + path, data=None if body is None else json.dumps(body, allow_nan=False).encode(), headers={'Content-Type': 'application/json'}, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)
        except URLError as error:
            # Avoid printing endpoint credentials, payloads or server responses in reports.
            raise ValueError('API inaccessible : vérifier le serveur et son URL.') from error


def audit_api(request, basis):
    require(basis in {'listing', 'CAD'}, 'Base de devise attendue : listing ou CAD.')
    results = []

    def case(id, fn):
        try:
            fn()
            results.append(dict(id=id, status='passed', detail='Contrôle ciblé réussi.'))
        except (ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
            results.append(dict(id=id, status='failed', detail=str(error)))

    def get(method, path, body=None):
        status, payload = request(method, path, body)
        require(status == 200, f'{method} {path} : statut HTTP {status}, attendu 200.')
        return payload

    def health():
        payload = get('GET', '/health')
        require(bool(payload['version']) and payload['llm_provider'] in {'mock', 'bedrock'}, 'Version ou fournisseur absent/invalide.')
    case('health', health)
    case('questionnaire', lambda: require(get('GET', '/questionnaire') == yaml.safe_load((ROOT/'rules/questionnaire.yaml').read_text()), 'Questionnaire différent des règles D.'))
    personas = {}

    def presets():
        for persona in get('GET', '/personas'):
            personas[persona['id']] = persona
        require({'amira', 'robert', 'mateo'} <= set(personas), 'Persona manquant.')
        for pid in ['amira', 'robert', 'mateo']:
            expected = yaml.safe_load((ROOT/f'rules/personas/{pid}.yaml').read_text())
            require(personas[pid]['profile'] == expected, f'Preset {pid} différent des règles D.')
    case('personas', presets)
    profile_cases = yaml.safe_load((ROOT/'eval/profile_cases.yaml').read_text())['cases']
    with (ROOT/'eval/reports/asset_metrics.csv').open() as handle:
        metric_ref = next(r for r in csv.DictReader(handle) if r['ticker'] == 'NVDA' and r['basis'] == basis)
    scenarios = json.loads((ROOT/'eval/reports/portfolio_scenarios.json').read_text())
    for item in profile_cases:
        pid = item['id']

        def profile(item=item, pid=pid):
            actual = get('POST', '/profile', dict(answers=item['answers']))
            expected = yaml.safe_load((ROOT/item['expected_profile']).read_text())
            require(actual['profile_id'] == 'custom' and actual['source'] == 'questionnaire', 'Identité custom/source incorrecte.')
            for field in item['compare_fields']:
                require(actual[field] == expected[field], f'{pid} : champ profil différent : {field}.')
        case('profile_' + pid, profile)

        def portfolio_and_feed(pid=pid):
            csv_text = (ROOT/f'rules/personas/{pid}_portfolio.csv').read_text()
            portfolio = get('POST', '/portfolio/parse', {'csv': csv_text})
            near(portfolio['total_amount'], 100000)
            near(portfolio['unanalyzed']['weight'], 0)
            expected_rows = list(csv.DictReader(csv_text.splitlines()))
            positions = portfolio['positions']
            require(len(positions) == len(expected_rows), 'Nombre de positions incorrect.')
            actual = {r['ticker']: r for r in positions}
            require(set(actual) == {r['ticker'] for r in expected_rows}, 'Tickers modifiés.')
            for row in expected_rows:
                near(actual[row['ticker']]['amount'], float(row['montant']))
                near(actual[row['ticker']]['weight'], float(row['montant']) / 100000)
            baseline = next(s for s in scenarios if s['profile_id'] == pid and s['basis'] == basis and s['scenario'] == 'baseline')
            profile = yaml.safe_load((ROOT/f'rules/personas/{pid}.yaml').read_text())
            feed = get('POST', '/feed', dict(profile=profile, portfolio=portfolio))
            inspect_feed(feed)
            near(feed['portfolio_summary']['high_vol_share'], baseline['high_vol_share'])
            near(feed['portfolio_summary']['top3_concentration'], baseline['top3_concentration'])
            require(feed['coherence'] is None, 'Cohérence présente sans demande simulée.')
            if pid == 'mateo':
                return
            simulated = get('POST', '/feed', dict(profile=profile, portfolio=portfolio, consideration=dict(ticker='NVDA', intended_weight=.20)))
            inspect_feed(simulated)
            result = simulated['coherence']
            expected = next(s for s in scenarios if s['profile_id'] == pid and s['basis'] == basis and s['scenario'] == 'NVDA_final_20pct')
            require(result['verdict'] == expected['verdict'], f'Verdict {pid} différent de la référence D.')
            require({r['rule_id'] for r in result['rule_hits']} == set(expected['rule_ids']), f'Règles {pid} différentes de la référence D.')
            near(result['metrics']['position_weight_after'], .20)
            for metric in ['annualized_vol', 'max_drawdown', 'worst_calendar_year_return']:
                near(result['metrics'][metric], float(metric_ref[metric]), .005)
        case('portfolio_feed_' + pid, portfolio_and_feed)

    def empty_csv():
        status, payload = request('POST', '/portfolio/parse', {'csv': 'ticker,montant\n'})
        require(400 <= status < 500, 'CSV vide accepté ou erreur serveur.')
        require(payload['error']['code'] == 'INVALID_CSV' and bool(payload['error']['message']), 'Erreur CSV non conforme.')
    case('empty_csv', empty_csv)
    return dict(checked_at=datetime.now(timezone.utc).isoformat(), metric_basis=basis, scope='Targeted D API acceptance; not full schema, semantic, UI or AWS validation.', checks=results, passed=all(r['status'] == 'passed' for r in results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', required=True)
    parser.add_argument('--metric-basis', required=True, choices=['listing', 'CAD'], help='Devise des métriques convenue avec A, jamais devinée.')
    args = parser.parse_args()
    output = audit_api(API(args.api_url), args.metric_basis)
    path = ROOT/'eval/reports/api_acceptance.json'
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    for result in output['checks']:
        print(result['status'], result['id'], result['detail'])
    print(f'Rapport : {path}')
    raise SystemExit(0 if output['passed'] else 1)
