# Backend Python (rôle A)

Façade appelée par l'API (`api/handler.py`, rôle B). Simulation éducative: aucun conseil financier.

## Installation

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements-dev.txt                    # runtime + pytest, jsonschema, ruff
pip install -r requirements-ingest.txt                 # seulement pour l'ingestion (yfinance, lxml)
make test                                              # schémas à jour + pytest (aucun réseau, LLM_PROVIDER=mock)
```

## Commandes

| Commande | Rôle |
| --- | --- |
| `make test` / `make lint` | Tests (hors `integration`) et ruff |
| `make validate-rules` | Vérifie les fichiers de `rules/` (messages pour non-programmeurs) |
| `make contracts` | Régénère `contracts/*.schema.json` depuis `core/models.py` et `core/rules_models.py` |
| `make examples` | Régénère `contracts/examples/` avec le vrai pipeline |
| `make ingest` | Nouvelles (Yahoo, Google News) et événements -> `data/snapshots/news_*.json`, `events_*.json`, `REPORT_*.md` |
| `make classify` | Classe le dernier instantané de nouvelles -> `data/snapshots/classified_news_*.json` |
| `make eval` | Accord du classifieur avec `eval/labeled_headlines.csv` -> `eval/reports/` |
| `pytest -m integration` | Tests réseau ou Bedrock (`LLM_PROVIDER=bedrock` + identifiants AWS) |

Chaîne hors ligne complète: `make ingest && make classify && make examples`.

## Façade (`services`)

```python
health() -> Health
get_questionnaire() -> dict                       # rules/questionnaire.yaml
get_personas() -> list[Persona]                   # rules/personas/
score_profile(answers) -> Profile                 # règles, jamais le modèle
parse_portfolio(csv_text) -> Portfolio            # ticker,montant (CAD)
build_feed(profile, portfolio, consideration=None) -> FeedResponse
get_events(tickers=None) -> list[Event]
```

Erreurs: `services.ServiceError` (= `core.errors.AlphaForgeError`) avec `.code`, `.message`, `.status`
(400 ou 500) et `.to_dict()` au format `{error: {code, message, details?}}`. Codes: `INVALID_CSV`,
`UNKNOWN_TICKER`, `INVALID_ANSWERS`, `INVALID_PROFILE`, `INVALID_PORTFOLIO`, `INVALID_CONSIDERATION`,
`EMPTY_PORTFOLIO`, `INSUFFICIENT_DATA`, `DATA_UNAVAILABLE`, `RULES_INVALID`, `RULES_UNAVAILABLE`,
`PROFILE_INCOMPLETE`. Un modèle indisponible n'est jamais une erreur: le fil se dégrade (règles et preuves).

## Variables d'environnement

| Variable | Défaut | Rôle |
| --- | --- | --- |
| `LLM_PROVIDER` | `mock` | `mock` (hors ligne, déterministe) ou `bedrock` |
| `BEDROCK_MODEL_ID`, `BEDROCK_REGION` | — | Fournis par B (jamais devinés) |
| `DATA_DIR` | `data/` | Jeu de départ et `snapshots/` |
| `RULES_DIR` | `rules/` | Fichiers du rôle D; repli fichier par fichier sur `contracts/rules/examples/` |

## Notes pour le déploiement (rôle B)

- Dépendances d'exécution: `pandas`, `numpy`, `pydantic`, `PyYAML`, `jsonschema`, `boto3`. `pandas` et
  `numpy` sont lourds: couche « AWS SDK for pandas » ou image de conteneur.
- Lecture seule sur le chemin en ligne: `data/*.csv`, `data/snapshots/classified_news_*.json`,
  `events_*.json`, `rules/`. Les données sont mises en cache au démarrage à froid.
- Temps de `build_feed`: moins de 1 s en mode `mock`; en mode `bedrock`, 6 explications et le gardien
  tournent en parallèle, plus l'agent pour « J'envisage d'acheter X ».
- Aucune donnée de portefeuille ni texte de nouvelle n'est journalisé par le backend.
