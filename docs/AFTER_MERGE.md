# Reprise du rôle D après merge

Le travail local D est prêt. Aucune action manuelle supplémentaire n’est nécessaire avant de recevoir les autres livraisons. Ce document distingue les dépendances techniques de la revue humaine demandée par le projet.

## Ce qui peut attendre le merge

| Travail D restant | Livraison attendue | Ce que D fera ensuite |
| --- | --- | --- |
| Étiqueter 60–100 nouvelles réelles | A : export NewsRecord sourcé | Annotation à l’aveugle avec eval/ANNOTATION_GUIDE.md, puis seconde passe |
| Valider les profils, poids et métriques de l’API | A/B : API démarrée, schémas et conventions confirmées | Exécuter eval/verify_after_merge.py et analyser chaque écart |
| Vérifier les vraies explications | A : agents, gardien et sorties Evidence | Contrôles de références automatiques, puis relecture du sens des phrases |
| Vérifier le parcours et l’affichage | C : interface connectée à l’API | Exécuter docs/TEST_SCENARIOS.md, surtout Robert, Amira et les erreurs |
| Finaliser la partie AWS de la présentation | B : vraie requête Bedrock et trace expurgée | Remplacer la scène préparée par une démonstration exécutée |
| Figurer les résultats définitifs dans les documents | Résultats précédents disponibles | Mettre à jour VALIDATION, TECH_DOC, ONE_PAGER et VIDEO_SCRIPT |

Les calendriers et preuves ESG/controverses se collectent chez A. D ne peut pas les déduire des seuls prix. Si ces données n’arrivent pas, conserver l’état « données insuffisantes / non évalué » et les exemples synthétiques explicitement marqués.

## Commandes prêtes

Depuis la racine du dépôt :

```sh
python3 eval/check_role_d.py
python3 -m unittest discover -s eval -p 'test_verify_after_merge.py' -v
python3 eval/audit_starter.py --data-dir ../alphaforge_starter
make validate-rules
```

Puis, seulement quand l’API tourne :

```sh
python3 eval/verify_after_merge.py --api-url http://localhost:8000 --metric-basis CAD
```

Remplacer l’URL par celle donnée par B. Choisir `CAD` ou `listing` **avec A** selon la devise de ses métriques; ne pas choisir celle qui fait passer un test. L’outil vérifie dix groupes de contrôles et écrit `eval/reports/api_acceptance.json`. Il utilise uniquement les portefeuilles fictifs du projet, sans opération financière ni donnée personnelle. Aucun appel réseau n’est effectué tant que cette commande n’est pas lancée.

L’outil compare la politique D actuelle. Un désaccord de convention doit être examiné, jamais masqué en changeant la référence pour obtenir un succès. Les tolérances et écarts sont dans le rapport; toute validation en mode mock doit rester annoncée comme telle. Cet outil ne remplace pas la validation JSON Schema, l’évaluation sémantique du gardien, les tests d’interface ni la preuve AWS.

## Démonstration préparée

`eval/demo_common_portfolio.csv` donne exactement le même poids NVDA de 10 % à Robert et Amira. Pour la nouvelle synthétique syn_007 de stratégie NVDA, les scores attendus sont respectivement 0,45 et 0,95. A/C doivent charger le titre comme exemple fictif et conserver sa provenance; sa présence dans le CSV d’évaluation ne signifie pas qu’il existe dans leurs snapshots.

Ensuite, charger les portefeuilles propres aux personas et simuler NVDA au poids final de 20 % : Robert incohérent, Amira en tension sur les références du starter. Ne pas confondre les deux étapes, qui utilisent des portefeuilles différents.

## Ce qui reste à une personne de l’équipe

1. Ouvrir `eval/reports/validation_workbook.xml` dans Excel ou LibreOffice, recalculer et relire les valeurs. Les caches Python ne prouvent pas un recalcul dans un tableur. Après merge, reporter les valeurs de l’application et leurs preuves dans VALIDATION.md.
2. Faire relire le contenu financier et les limites, puis les documents de concours par l’équipe. L’annotation et la relecture réalisées par une seule IA ne constituent pas un double contrôle humain indépendant.
3. Enregistrer la vidéo de cinq minutes dans l’application fonctionnelle, avec les captures C et la preuve AWS B, puis vérifier le fichier final et sa durée.
4. Confirmer les modalités officielles de remise et soumettre les livrables.

Je pourrai reprendre les vérifications automatisées, l’annotation et les corrections documentaires dès que les fichiers des autres rôles seront présents. Les tâches ci-dessus ne sont pas déclarées terminées en leur absence.
