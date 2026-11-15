# DatathonPolyFinance2026
dathaton polyfinance 2026

> Simulation éducative: aucun conseil financier, aucune transaction réelle.

## Démarrage local (sans AWS)

```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt -r api/requirements-local.txt
make dev            # ou: python -m api.local_server  -> http://127.0.0.1:8000 (LLM_PROVIDER=mock)
make smoke-local    # ou: python scripts/smoke_test.py
make test           # tests du backend et de l'API
```

Le front (`web/`) pointe vers l'API locale avec `VITE_API_URL=http://127.0.0.1:8000 VITE_MOCK=0`.

## Déploiement AWS (rôle B)

Prérequis: AWS CLI v2, Python 3.11+, Node 22, identifiants AWS dans l'environnement (ou dans `.env`, jamais
commité). Pas besoin de Docker ni de la SAM CLI.

```bash
make check-aws      # audit du compte et test Bedrock          (python infra/scripts/check_bedrock.py)
make deploy         # Lambda, API, buckets, CloudFront, données (python scripts/deploy.py deploy)
make deploy-web     # build du site et invalidation du cache   (python scripts/deploy.py deploy-web)
make smoke          # test de fumée de l'API déployée          (python scripts/smoke_test.py --deployed)
make upload-data    # rafraîchir les snapshots sur S3, sans redéployer
make destroy        # tout retirer, après confirmation
```

Variables: `BEDROCK_MODEL_ID` (voir `docs/AWS_STATUS.md`; retenu: `us.anthropic.claude-sonnet-4-6`), `AWS_REGION` (`us-east-1`), `STACK_NAME`
(`alphaforge`), `BUDGET_EMAIL` (optionnel: alerte de coût). Détails: `docs/AWS.md`, `docs/architecture.md`.
