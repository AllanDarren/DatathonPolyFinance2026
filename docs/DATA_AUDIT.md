# Audit du pack alphaforge_starter

Audit effectué le 14 novembre 2026 sur les fichiers locaux fournis. Aucune donnée source n’a été modifiée ou retéléchargée. La provenance est celle déclarée dans `sources_metadata.csv` (Yahoo via yfinance, Banque du Canada et FRED); cet audit confirme les calculs sur le snapshot, pas l’authenticité de chaque observation auprès de son émetteur.

## Présence et intégrité

| Élément | Constat |
| --- | --- |
| Fichiers attendus | Les neuf fichiers du pack sont présents |
| Univers | 31 actifs, tous présents dans les prix |
| Prix | 40 049 lignes; 1 255 par actif coté hors crypto, 1 827 par crypto |
| Période des prix | Tous les actifs : 2021-11-12 à 2026-11-12 |
| FX USD/CAD | 1 245 lignes; jours sans taux reportés depuis le passé pour les calculs CAD |
| Macro | 8 281 lignes, neuf séries; couverture variable selon la série |
| Actions sur titres | 658 lignes |
| Contrôles bloquants | Aucun doublon détecté dans les clés contrôlées; aucun prix nul, négatif, non fini ou champ de prix manquant; OHLC cohérents; devises conformes à l’univers; taux inverses cohérents à l’arrondi fourni |
| Avertissement confirmé | ZST.TO : volume nul le 2022-07-06; ligne conservée dans les calculs sur prix ajustés |

Le détail des couvertures, reports FX, empreintes SHA-256 et contrôles se trouve dans `eval/reports/starter_audit.json` et `asset_coverage.csv`. Les empreintes permettent de vérifier que deux personnes utilisent le même snapshot. Un calendrier officiel de chaque bourse n’a pas été intégré : la présence de toutes les séances attendues n’est pas certifiée par les seuls totaux.

## Ce qui manque au produit prévu

| Manque | Conséquence | Responsable / suite |
| --- | --- | --- |
| Vraies nouvelles : titre, source, URL, dates et extraits autorisés | Pas d’évaluation indépendante sur 60–100 titres réels ni de fil réel | A collecte; D annote ensuite |
| Calendrier historique avec dates et heures de publication | Pas d’étude fiable des résultats, annonces de taux ou inflation; les dates de référence macro ne sont pas des dates de diffusion | A collecte les événements sourcés |
| Calendrier à venir | Bonus calendrier non alimenté | A, bonus |
| Rapports de controverse et preuves ESG | Pas de score ESG ou de conclusion sur la conduite d’une société | A collecte; D étiquette |
| Composition des FNB et données sectorielles détaillées | Exclusions et diversification internes non vérifiables | A; afficher cette limite |
| Niveaux d’IPC canadien | L’inflation cumulée peut être approximée par chaîne annuelle, mais pas contrôlée exactement avec des niveaux non arrondis | Complément souhaitable, non bloquant pour l’approximation |
| Source émetteur sur CNQ.TO le 2022-08-22 | Facteur 1,021 non interprété | A vérifie; ne jamais appliquer un second ajustement |
| Schémas, cible make validate-rules, moteur, API et interface | Pas de validation applicative de bout en bout | A, B, C |
| Captures et preuve de requête AWS | D ne peut pas certifier la démonstration ni enregistrer une vidéo réelle | B/C puis relecture D |

Le pack est **à côté du dépôt**, dans `../alphaforge_starter`, et n’est donc pas automatiquement inclus dans un clone du dépôt Git. B/A doivent prévoir la livraison des données ou un `DATA_DIR` explicite. Le rôle D laisse les sources intactes et conserve uniquement ses rapports et références dans `eval/`.

## Compatibilité importante

L’univers utilise `equity`, `etf_equity`, `etf_bond`, `etf_commodity`, alors que l’API v0 demande `equity_ca`, `equity_us`, `equity_etf`, `bond_etf`, `gold_etf`, `crypto`. La correspondance explicite est dans `rules/asset_class_mapping.yaml`. Aucun changement du contrat n’est nécessaire; une classe inconnue ne doit pas être assimilée silencieusement à une action.

Le secteur simplifié `Energy` permet d’identifier ENB.TO, CNQ.TO et XOM comme candidats à une revue de l’exclusion des combustibles fossiles; il ne suffit pas à vérifier les revenus fossiles ou les participations des FNB. La préférence de Mateo n’est pas une certification du portefeuille.

## Résultats remarquables

Les rendements 2022, chutes et corrélations de référence sont proches des estimations du contexte. Les volatilités recalculées avec écart-type échantillonnal ×√252 sont SPY **17,3335 %**, NVDA **51,9384 %**, Bitcoin **42,1734 %**. Les valeurs exploratoires 15 %, 50 % et 54 % d’AGENTS.md ne doivent pas être utilisées comme résultats calculés. Pour Bitcoin, ×√365 donne environ **50,76 %** : cela ne justifie pas de changer discrètement la convention v0.

L’inflation canadienne septembre 2021–septembre 2026 est approximativement **19,0220 %** par `(1+6,9/100)×(1+3,8/100)×(1+1,6/100)×(1+2,4/100)×(1+3,1/100)−1`. Ces cinq périodes annuelles sont adjacentes, sans chevauchement. Les taux sont arrondis; ne pas présenter ce résultat comme une mesure exacte issue de niveaux d’IPC.

L’audit reproductible : `python3 eval/audit_starter.py --data-dir ../alphaforge_starter`. Dépendances : Python 3.11+, pandas et PyYAML. Aucun appel réseau.
