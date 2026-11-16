# Évaluation du rôle D

Tous les titres et toutes les métriques de test sont fictifs. Les valeurs ne valident pas les marchés réels.

- `labeled_headlines.csv` : 30 titres, 12 catégories, une position commune de 10 % dans chacun des trois profils pour isoler l’effet du profil. Les colonnes de pertinence sont des niveaux `low`, `medium`, `high`; `low` est masqué si le score est inférieur à 0,35.
- Les titres de taxonomie sont aussi fictifs. Les étiquettes sont préparées avec la taxonomie puis relues lors du contrôle local; ce n’est pas une annotation indépendante à deux personnes. Une séparation apprentissage/test et 60 à 100 titres réels restent à fournir par A avant de mesurer la généralisation.
- `profile_cases.yaml` : réponses qui retrouvent les champs financiers des personas. Le profil personnalisé garde `profile_id=custom`, `source=questionnaire` et son propre libellé; l’âge n’est pas demandé et ne peut pas être reconstruit.
- `coherence_cases.yaml` : entrées métriques contrôlées pour vérifier le verdict, sur des métriques fictives contrôlées, distinctes des prix maintenant fournis. Ce ne sont pas des métriques calculées sur les portefeuilles CSV.
- `check_role_d.py` : contrôle local de cohérence des données, pas un moteur de production. Exécuter `python3 eval/check_role_d.py` (PyYAML nécessaire).

Le calcul de référence de pertinence part du poids de la catégorie, ajoute le plus grand palier de position applicable (non cumulatif), les modificateurs dont toutes les conditions sont satisfaites, puis borne à [0,1]. Niveau élevé dès 0,70; moyen dès 0,35. Les frontières décimales sont inclusives.

Les vraies nouvelles devront conserver source, URL, date de publication et de collecte. Le CSV d’évaluation ne remplace pas un snapshot `NewsRecord`. Un accord sur ce jeu synthétique ne démontre pas une qualité de classement en production.

## Starter désormais disponible

`python3 eval/audit_starter.py --data-dir ../alphaforge_starter` produit un audit sans téléchargement (pandas et PyYAML nécessaires). Les sorties reproductibles sont dans `reports/` : couvertures, empreintes SHA-256, 62 lignes de métriques (31 actifs en devise de cotation et en CAD), 22 références calculées par deux méthodes et scénarios NVDA 20 % sur les vrais prix du snapshot fourni. Les rapports ne remplacent pas les Evidence de l’application.

`reports/validation_workbook.xml` contient des données et formules prêtes à ouvrir dans Excel/LibreOffice; les caches sont générés par Python et le recalcul dans un tableur reste à effectuer. Les corrélations excluent novembre 2026, mois incomplet; elles utilisent 59 paires de rendements mensuels.

Les deux nouveaux fichiers `rules/asset_class_mapping.yaml` et `rules/metric_policy.yaml` documentent la conversion des classes et les conventions de calcul des références D; les schémas A correspondants restent à ajouter avant validation officielle.

## Reprise après merge

- `verify_after_merge.py` : contrôles ciblés de l’API, à lancer avec URL et devise explicites après intégration. Aucun appel effectué pendant sa préparation.
- `test_verify_after_merge.py` : sept tests hors réseau, dont preuves manquantes, faux succès du gardien et nombres non finis.
- `ANNOTATION_GUIDE.md` : annotation des vraies nouvelles quand A fournit l’export.
- `demo_common_portfolio.csv` : portefeuille fictif commun pour isoler l’effet Robert/Amira, total 100 000 CAD et NVDA à 10 %.

Commandes : `make eval` (évaluation du classifieur, rapport dans `eval/reports/`) et `make validate-rules`.
