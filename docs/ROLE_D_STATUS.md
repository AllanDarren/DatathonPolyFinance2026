# État final des livrables D — 14 novembre 2026

Le contenu réalisable dans les dossiers du rôle D est livré et vérifié localement. Les dépendances applicatives et humaines ne sont pas déclarées terminées.

| Livrable | État | Preuve / dépendance |
| --- | --- | --- |
| D0 Personas et portefeuilles | Livré, contrôlé localement | Trois profils complets, CSV à 100 000 CAD; schémas A encore absents |
| D1 Questionnaire | Livré | Sept questions, reconstruction des champs financiers des trois profils |
| D2 Profil | Livré | Tranches, points, limites et incohérences |
| D3 Taxonomie | Livré | Douze catégories avec trois exemples chacune |
| D4 Pertinence | Livré, contrôlé sur cas fixes | Six catégories de niveaux différents Robert/Amira |
| D5 Cohérence | Livré, vérifié sur fixtures et starter | Robert NVDA 20 % incohérent; Amira en tension; récupération non retrouvée traitée |
| D6 Évaluation | Trente titres fictifs livrés | 60–100 titres réels et annotation indépendante en attente de collecte A |
| D7 Validation | 22 références du snapshot fourni, deux méthodes, classeur préparé | Recalcul humain dans tableur et comparaison à l’application encore à faire |
| D8 Scénarios manuels | Dix-huit scénarios livrés; références financières exécutées | Tests API/UI non exécutables sans A/C |
| D9 Textes | Livré | Vingt-cinq termes, limites, avertissements, vocabulaire |
| D10 Livrables concours | Documents rédigés et mis à jour avec les calculs | Relecture équipe, captures, trace AWS et enregistrement vidéo encore à faire |
| D11 Relecture des explications | Grille de revue livrée | Aucune explication applicative disponible à relire |

## Reproduction

Depuis la racine du dépôt, avec Python 3.11+, PyYAML et pandas :

```sh
python3 eval/check_role_d.py
python3 eval/audit_starter.py --data-dir ../alphaforge_starter
```

Résultats locaux : contrôles réussis, aucun téléchargement. `make validate-rules` ne peut pas fonctionner tant que la cible et les schémas A/B sont absents. Les rapports se trouvent dans `eval/reports/`; les manques de données sont détaillés dans DATA_AUDIT.md.

Les fichiers du starter restent à côté du dépôt. L’équipe doit prévoir leur distribution avec le projet. Aucun dossier d’un autre rôle ni fichier source fourni n’a été modifié; aucune issue ou communication distante n’a été publiée.

## Préparation de la reprise après merge

`docs/AFTER_MERGE.md` liste les dépendances par rôle et les seules interventions humaines restantes. `eval/verify_after_merge.py` est prêt pour l’API v0 : profils, poids, métriques, verdicts et références des explications. Ses sept tests hors réseau passent; il n’a pas été exécuté contre une application absente. La procédure d’annotation est dans `eval/ANNOTATION_GUIDE.md`; le CSV commun pour la vidéo est prêt. Aucune intégration distante n’a été annoncée comme réussie.
