# Validation financière — données du starter

Mise à jour du 14 novembre 2026. **22 valeurs sont recalculées par deux méthodes distinctes** : boucles, ratios, `statistics` et sommes centrées de la bibliothèque standard Python; puis séries et opérations vectorielles pandas. Les résultats concordent à 1e-10 en fraction ou unité de corrélation. Ce contrôle est indépendant du futur moteur applicatif, mais réalisé par le même auteur : il ne constitue pas une revue indépendante à deux personnes.

Les sources sont les snapshots fournis dans `../alphaforge_starter`; les calculs ne requièrent aucun téléchargement. Empreintes et couvertures dans `eval/reports/starter_audit.json`. La provenance est déclarée par les métadonnées du pack, pas recertifiée auprès des fournisseurs.

## Comparaisons exécutées

| Identifiant | Méthode standard Python | Méthode pandas | Écart brut | Application | Verdict |
| --- | --- | --- | --- | --- | --- |
| R2022_SPY | -18.175368 % | -18.175368 % | 0 | À mesurer | Accord local |
| R2022_QQQ | -32.577001 % | -32.577001 % | 0 | À mesurer | Accord local |
| R2022_AGG | -13.021618 % | -13.021618 % | 0 | À mesurer | Accord local |
| R2022_XBB.TO | -11.664548 % | -11.664548 % | 0 | À mesurer | Accord local |
| R2022_NVDA | -50.264642 % | -50.264642 % | 0 | À mesurer | Accord local |
| R2022_XOM | 87.409056 % | 87.409056 % | 0 | À mesurer | Accord local |
| DD_NVDA | -66.335081 % | -66.335081 % | 0 | À mesurer | Accord local |
| DD_BTC-USD | -75.885068 % | -75.885068 % | 0 | À mesurer | Accord local |
| DD_TLT | -43.696516 % | -43.696516 % | 0 | À mesurer | Accord local |
| VOL_SPY | 17.333534 % | 17.333534 % | 0 | À mesurer | Accord local |
| VOL_NVDA | 51.938413 % | 51.938413 % | 1.1e-16 | À mesurer | Accord local |
| VOL_BTC-USD | 42.173360 % | 42.173360 % | 5.6e-17 | À mesurer | Accord local |
| CORR_QQQ_SPY | 0.911686542 | 0.911686542 | 3.3e-16 | À mesurer | Accord local |
| CORR_ESGV_SPY | 0.991159818 | 0.991159818 | 4.4e-16 | À mesurer | Accord local |
| CORR_BTC-USD_ETH-USD | 0.826743247 | 0.826743247 | 1.1e-16 | À mesurer | Accord local |
| CORR_BTC-USD_QQQ | 0.492384637 | 0.492384637 | 1.1e-16 | À mesurer | Accord local |
| TOTAL_SPY_listing | 73.238627 % | 73.238627 % | 0 | À mesurer | Accord local |
| TOTAL_SPY_CAD | 96.539326 % | 96.539326 % | 0 | À mesurer | Accord local |
| CPI_CA_SEP21_SEP26 | 19.022040 % | 19.022040 % | 0 | À mesurer | Accord local |
| WEIGHT_amira | 20.000000 % | 20.000000 % | 0 | À mesurer | Accord local |
| WEIGHT_robert | 35.000000 % | 35.000000 % | 0 | À mesurer | Accord local |
| WEIGHT_mateo | 30.000000 % | 30.000000 % | 0 | À mesurer | Accord local |

Le détail des méthodes, sources, écarts aux estimations d’AGENTS.md et valeurs brutes est dans `eval/reports/market_validation.csv`. Les colonnes applicatives y sont volontairement vides : aucune API ni sortie Evidence n’est disponible. Aucune comparaison avec l’application n’est déclarée réussie.

## Méthodes et unités

- Rendement 2022 : dernier prix ajusté du 30 décembre 2022 / dernier du 31 décembre 2021 − 1 pour les actions et FNB concernés. La borne est la dernière observation disponible au plus tard le 31 décembre de chaque année, pas la première séance de janvier.
- Chute maximale : minimum de prix / maximum cumulatif − 1 sur les cinq ans. Valeur négative; la valeur absolue sert à la comparaison de cohérence.
- Volatilité : rendements quotidiens simples sur `adj_close`, écart-type échantillonnal (ddof=1), ×√252. Les cryptos ont des jours UTC; ×√365 est fourni à part dans `asset_metrics.csv` pour rendre la convention visible.
- Corrélation : fin de mois, rendements mensuels, intersection des dates, 59 paires complètes de décembre 2021 à octobre 2026. Novembre 2026 est exclu car le snapshot s’arrête le 12. Le mois initial incomplet fournit la base du premier rendement; aucune paire n’est créée à partir de deux niveaux de prix.
- SPY en CAD : prix USD × dernier FX connu à chaque date; le FX n’est jamais rempli depuis une date future. Les deux bornes du rendement de fenêtre sont 2021-11-12 et 2026-11-12.
- Inflation CA : produit des cinq facteurs annuels de septembre 2022 à septembre 2026 moins 1. Ces périodes sont non chevauchantes. Le résultat 19,0220 % est approximatif car les taux sources sont arrondis à 0,1 point. Multiplier tous les taux annuels mensuels serait incorrect.
- `worst_calendar_year_return` dans les métriques de référence ne couvre que les années complètes 2022–2025. 2021 et 2026 sont exclues. `recovery_days` de référence est en jours calendaires depuis le sommet de la pire chute jusqu’à son premier retour; null signifie non retrouvé à la fin des données. A doit confirmer cette unité lors de l’intégration.

`eval/reports/asset_metrics.csv` contient les métriques des 31 actifs dans leur devise de cotation et en CAD, soit 62 lignes. Les résultats de cohérence des portfolios en CAD et en devise de cotation sont conservés séparément; aucun mélange de devises n’est caché dans un même calcul.

## Écarts signalés à la reprise de A

Les estimations exploratoires de volatilité dans AGENTS.md ne correspondent pas au snapshot sous la convention v0 : SPY 15 % contre **17,3335 %**, NVDA 50 % contre **51,9384 %**, Bitcoin 54 % contre **42,1734 %**. L’écart est respectivement de +2,3335, +1,9384 et −11,8266 points. La tolérance de 0,5 point utilisée ici pour signalement n’est pas une calibration empirique : la comparaison des deux méthodes exactes prévaut. Ces écarts sont consignés pour A; aucun message externe n’a été envoyé.

## Tableur prêt pour revue

`eval/reports/validation_workbook.xml` est un classeur Excel XML avec prix bruts ajustés de SPY, NVDA, QQQ et AGG, formules de rendements, sommets courants, chutes, volatilités, corrélation et inflation. Douze comparaisons y sont préparées. Les valeurs en cache proviennent de Python; **aucun recalcul dans Excel ou LibreOffice n’a été exécuté**. Il faut ouvrir le classeur, recalculer puis noter les résultats dans la colonne applicative une fois les Evidence disponibles. La préparation du tableur ne remplace pas cette revue humaine.

Les dix exemples arithmétiques fictifs de `eval/independent_checks.csv` sont conservés comme tests de démarrage; ils ne sont plus la seule base de validation.

## Vérifications et reste à faire

Exécuter depuis la racine du dépôt :

```sh
python3 eval/check_role_d.py
python3 eval/audit_starter.py --data-dir ../alphaforge_starter
make validate-rules
```

Les deux scripts Python passent. `make validate-rules` reste indisponible, car la cible et les schémas appartiennent aux livraisons A/B encore absentes. La structure est relue contre la section 11 d’AGENTS.md.

Pour terminer D7 au sens strict : relecture du classeur par une personne, valeurs de l’application et Evidence, écarts et explications. Rendements : tolérance de reprise 0,5 point; corrélations : 0,02; poids exacts : 1e-10 en fraction. Toute différence de devise, bornes, calendrier ou annualisation doit être expliquée avant validation. D11 reste la relecture des explications réellement générées, indisponibles à ce stade.
