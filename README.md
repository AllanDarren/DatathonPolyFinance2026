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

En local, sans `VITE_COGNITO_CLIENT_ID`, le front utilise une **authentification de développement** : comptes gardés
en mémoire de l'onglet, jeton `local.<id>` accepté seulement par `api/local_server.py`. Les données de chaque
compte local sont écrites dans `.build/local_users/` (ou `USER_STORE_DIR`).

## Comptes utilisateurs (Amazon Cognito)

Chaque utilisateur crée un compte (courriel + mot de passe), se connecte, se déconnecte, et retrouve à la
reconnexion **son** profil d'investisseur, **son** portefeuille déposé (CSV) et **ses** 10 derniers briefs.

| Élément | Choix |
| --- | --- |
| Identité | Pool d'utilisateurs Cognito `alphaforge-users` : connexion par courriel (insensible à la casse), mot de passe de 8 caractères au moins avec majuscule, minuscule et chiffre. Les mots de passe sont hachés et vérifiés par Cognito ; AlphaForge ne les voit jamais stockés. |
| Confirmation | Déclencheur `alphaforge-presignup` qui confirme le compte d'office : le compte d'atelier n'a pas SES, et l'expéditeur par défaut de Cognito est limité à quelques courriels par jour. Conséquence assumée pour la démo : la propriété du courriel n'est pas vérifiée. |
| Client du site | Client d'application **public** (sans secret), flux `USER_PASSWORD_AUTH` en HTTPS puis `REFRESH_TOKEN_AUTH`. Erreurs neutres (`PreventUserExistenceErrors`) : même message pour un courriel inconnu et un mauvais mot de passe. |
| Session | Jeton d'accès de 60 min, renouvelé automatiquement. « Rester connecté » : jeton de rafraîchissement dans `localStorage`, 30 jours au plus. Sinon : `sessionStorage`, effacé à la fermeture de l'onglet. La déconnexion révoque le jeton de rafraîchissement (`RevokeToken`). |
| API | Les routes `/me…` exigent un jeton : l'authorizer JWT d'API Gateway vérifie la signature, l'émetteur, l'audience et l'expiration avant d'appeler la Lambda. L'identité vient **uniquement** du `sub` vérifié, jamais du corps de la requête. |
| Stockage | DynamoDB (`user_id`, `sk`) : `PROFILE`, `PORTFOLIO` (portefeuille analysé), `BRIEF#<horodatage>` (index des briefs). S3 privé et chiffré : `users/<sub>/portfolio.csv` et `users/<sub>/briefs/<id>.json`. |
| IAM | La Lambda n'a que `GetItem`, `PutItem`, `DeleteItem`, `Query`, `BatchWriteItem` sur la table, et `GetObject`, `PutObject`, `DeleteObject` sur `users/*` du bucket utilisateurs. |

Routes ajoutées : `GET /me`, `PUT /me/profile`, `PUT /me/portfolio`, `POST /me/briefs`, `GET /me/briefs/{id}`,
`DELETE /me` (efface toutes les données du compte).

Seul ce que l'utilisateur saisit lui-même est stocké : aucune donnée bancaire, aucune connexion à un compte.

### Variables d'environnement

| Où | Variable | Valeur |
| --- | --- | --- |
| Front (build) | `VITE_API_URL` | URL de l'API (sortie `ApiUrl`) |
| Front (build) | `VITE_AUTH` | `cognito` (déploiement) ou `local` (développement) |
| Front (build) | `VITE_COGNITO_REGION` | `us-east-1` |
| Front (build) | `VITE_COGNITO_CLIENT_ID` | sortie `UserPoolClientId` (identifiant public, pas un secret) |
| Lambda | `USER_TABLE`, `USER_BUCKET` | posées par le template (table DynamoDB et bucket utilisateurs) |
| Local | `USER_STORE_DIR` | dossier des comptes locaux (par défaut `.build/local_users`) |

`make deploy-web` renseigne les variables `VITE_*` automatiquement à partir des sorties de la pile. Aucun secret
n'est nécessaire : le client Cognito du site est public par construction.

## Déploiement AWS (rôle B)

Prérequis: AWS CLI v2, Python 3.11+, Node 22, identifiants AWS dans l'environnement (ou dans `.env`, jamais
commité). Pas besoin de Docker ni de la SAM CLI.

```bash
make check-aws      # audit du compte et test Bedrock          (python infra/scripts/check_bedrock.py)
make deploy         # Lambda, API, Cognito, DynamoDB, buckets, CloudFront, données (python scripts/deploy.py deploy)
make deploy-web     # build du site et invalidation du cache   (python scripts/deploy.py deploy-web)
make smoke          # test de fumée de l'API déployée          (python scripts/smoke_test.py --deployed)
make upload-data    # rafraîchir les snapshots sur S3, sans redéployer
make destroy        # tout retirer, après confirmation
```

Variables: `BEDROCK_MODEL_ID` (voir `docs/AWS_STATUS.md`; retenu: `us.anthropic.claude-sonnet-4-6`), `AWS_REGION` (`us-east-1`), `STACK_NAME`
(`alphaforge`), `BUDGET_EMAIL` (optionnel: alerte de coût). Détails: `docs/AWS.md`, `docs/architecture.md`.
