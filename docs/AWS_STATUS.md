# État du compte AWS (B0)

Audit du 2026-11-14, refait avec `make check-aws` (ou `python infra/scripts/check_bedrock.py`).

| Élément | Valeur |
| --- | --- |
| Compte | `026090516737` (compte d'atelier fourni, rôle `WSParticipantRole`) |
| Région | `us-east-1` |
| Expiration | lundi en fin de journée (identifiants temporaires d'atelier: à renouveler depuis le tableau de bord de l'atelier quand ils expirent) |
| Bedrock, API Converse | Accessible. Appel de test avec sortie structurée (appel d'outil forcé) réussi |
| Droits IAM (simulation) | Autorisés: `iam:CreateRole`, `iam:PassRole`, `lambda:CreateFunction`, `s3:CreateBucket`, `cloudformation:CreateStack`, `apigateway:POST`, `cloudfront:CreateDistribution`, `logs:CreateLogGroup`, `budgets:ModifyBudget`, `bedrock:InvokeModel`. La simulation ne voit pas d'éventuelles SCP: confirmé au premier déploiement |
| Lecture des services | Lambda, S3, API Gateway v2, CloudFront, CloudFormation, CloudWatch Logs, IAM: OK |

## Modèles testés (Converse, température 0, appel d'outil forcé)

| Identifiant | Résultat | Latence du test |
| --- | --- | --- |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | OK | ~1,1 s |
| `us.anthropic.claude-sonnet-4-6` | OK | ~1,3 s |
| `amazon.nova-micro-v1:0` | OK | ~0,9 s |
| `us.amazon.nova-pro-v1:0` | OK | ~1,0 s |
| `us.anthropic.claude-haiku-5-5` | **Échec**: `temperature is deprecated for this model` (le client de A envoie `temperature: 0`) | — |

Les modèles Anthropic ne sont disponibles qu'en profil d'inférence (`us.` ou `global.`), pas en appel direct.

**Modèle retenu par l'équipe: `BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6`, `BEDROCK_REGION=us-east-1`.**
Accepte `temperature: 0`, sortie structurée fiable. Replis testés: `us.anthropic.claude-haiku-4-5-20251001-v1:0`
(plus rapide et moins cher) puis `amazon.nova-micro-v1:0` (appel direct, le moins cher). Changer de modèle
demande seulement `BEDROCK_MODEL_ID=... make deploy` (la politique IAM suit le modèle).

## Quotas relevés (us-east-1)

| Quota | Valeur |
| --- | --- |
| Claude Haiku 4.5, inférence interrégionale, requêtes par minute | 10 000 |
| Claude Haiku 4.5, inférence interrégionale, jetons par minute | 5 000 000 |
| Nova Micro, à la demande, jetons par minute | 4 000 000 |

L'API limite elle-même le débit (10 requêtes/s, rafales de 20) pour protéger ces quotas et les coûts.

## Ce qui bloque

Rien pour l'instant. Points à surveiller:

- Les identifiants d'atelier expirent: les renouveler avant chaque déploiement.
- Pas de Docker ni de SAM CLI sur le poste de B: empaquetage en zip avec des wheels Linux (voir `docs/AWS.md`).
