# Services AWS utilisés

Chaque service a un rôle réel dans le produit. Aucun n'est là pour décorer. Tout est décrit en code dans
`infra/template.yaml` (AWS SAM) et créé par `make deploy`.

| Service | Rôle dans AlphaForge | Pourquoi il est nécessaire | Comment le démontrer |
| --- | --- | --- | --- |
| **Amazon Bedrock** (API Converse) | Classe les titres de nouvelles (sortie JSON imposée par schéma), rédige les explications à partir des preuves, sert de gardien (contrôle du soutien de chaque phrase), et pilote l'agent à outils de « J'envisage d'acheter X » | C'est la partie agentique: le modèle choisit quels outils appeler et rédige; le code calcule et décide | Console Bedrock, métriques `AWS/Bedrock` (invocations, jetons) sur le tableau de bord; champ `agent_trace` de la réponse `/feed`; journal `tools` de chaque requête |
| **AWS Lambda** | Exécute `api/handler.py` puis `services/` (règles, métriques, étude d'événements, agents) | Calcul à la demande, sans serveur à gérer, payé à la requête | Console Lambda (fonction `alphaforge-api`), invocations et durée |
| **Amazon API Gateway** (HTTP API) | Expose les 7 routes du contrat en HTTPS, gère CORS et limite le débit | Point d'entrée public et sécurisé de la fonction; la limite de débit protège les quotas Bedrock | `curl $ApiUrl/health`; `make smoke` |
| **Amazon S3** (2 buckets privés, chiffrés) | Données: jeu de départ (`starter/`) et snapshots de nouvelles et d'événements (`snapshots/`), lus par la Lambda au démarrage à froid. Site: build statique de `web/` | Les données sont versionnées hors du code: on rafraîchit les snapshots (`make upload-data`) sans redéployer | Console S3: contenu des deux buckets; journal `cold_start` (`data_source: s3://...`) |
| **Amazon CloudFront** | Sert le site en HTTPS (domaine `cloudfront.net`, aucun domaine acheté), avec accès au bucket par OAC seulement | Le bucket du site reste privé; HTTPS sans certificat à gérer | URL `WebUrl`; le bucket refuse un accès direct |
| **Amazon CloudWatch** | Journaux structurés (une ligne JSON par requête, sans portefeuille ni nouvelle), métriques personnalisées par route (format EMF), tableau de bord de démo | Observabilité et preuve de fonctionnement pour le jury | Tableau de bord `alphaforge-demo` (lien `DashboardUrl`); Logs Insights sur `/aws/lambda/alphaforge-api` |
| **IAM** | Rôle d'exécution de la Lambda au moindre privilège: `bedrock:InvokeModel` sur le seul modèle choisi, `s3:GetObject` sur les seuls préfixes `starter/` et `snapshots/` | Sécurité | Console IAM, politique du rôle de la fonction |
| **CloudFormation** | Crée et retire tout (`make deploy`, `make destroy`) | Reproductible dans un autre compte | Console CloudFormation, pile `alphaforge` |
| **AWS Budgets** (optionnel) | Alerte courriel à 80 % d'un budget mensuel | Surveiller les coûts | Créé seulement si `BUDGET_EMAIL` est défini |

Non utilisés, volontairement: bases de données (aucun portefeuille n'est stocké), Cognito (pas
d'authentification, hors périmètre), Route 53 (aucun domaine), instances EC2 ou GPU.

## Décisions

- **SAM plutôt que CDK**: un seul fichier YAML lisible, aucune dépendance Node ou compilation. Le
  déploiement passe par `aws cloudformation package/deploy` (la transformation SAM s'exécute côté AWS):
  pas besoin d'installer la SAM CLI.
- **Zip avec wheels Linux plutôt qu'image de conteneur ou couche « AWS SDK for pandas »**: pas de Docker
  sur les postes de l'équipe; pip télécharge des wheels `manylinux` pour Python 3.12 depuis n'importe quel
  système. Versions épinglées dans `api/requirements-lambda.txt` sur celles des tests de A (pandas 2.3.3,
  pas 3.x). Taille: environ 29 Mo compressé, 91 Mo décompressé (limite: 250 Mo).
- **HTTP API plutôt que URL de fonction**: CORS et limitation de débit gérés par AWS, routes explicites
  (une route inconnue n'atteint jamais la fonction).
- **Données sur S3, pas dans le zip**: les snapshots changent plus souvent que le code.
- **Mémoire 1 769 Mo** (1 vCPU complet): démarrage à froid plus court avec pandas et appels Bedrock
  parallèles. Délai maximal 29 s (la limite d'intégration d'API Gateway est de 30 s).
- **Journaux de 7 jours**: assez pour l'évaluation, coût négligeable.

## Coûts estimés (démo de 72 h)

| Poste | Estimation |
| --- | --- |
| Lambda, API Gateway, S3, CloudWatch Logs | Quelques cents (offre gratuite pour l'essentiel) |
| CloudFront | Moins de 1 $ |
| Tableau de bord CloudWatch | ~3 $/mois, au prorata: ~0,30 $ |
| Bedrock (Haiku 4.5) | Classement hors ligne de ~400 titres et quelques centaines de fils: quelques dollars au plus |

## Liste de captures pour la vidéo et le dossier (B6)

1. Pile CloudFormation `alphaforge` et ses ressources.
2. Fonction Lambda `alphaforge-api`: configuration (variables d'environnement sans secret) et onglet Monitor.
3. Buckets S3: `starter/`, `snapshots/` (data) et les fichiers du site (web).
4. Tableau de bord CloudWatch `alphaforge-demo` après une démo: latence par route, invocations Bedrock, jetons.
5. Logs Insights: une requête `POST /feed` avec `tools` = outils appelés par l'agent, sans aucune donnée de portefeuille.
6. Console Bedrock: modèle utilisé.
7. Le site sur son URL `cloudfront.net` (cadenas HTTPS).
8. Sortie de `make smoke` contre l'API déployée.

Requête Logs Insights utile:

```text
filter event = "request" | fields @timestamp, route, status, latency_ms, cold_start, tools.0, tools.1, tools.2
| sort @timestamp desc | limit 50
```
