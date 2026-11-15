# Évaluation du classifieur — 2026-11-15

- Étiquettes: `eval/labeled_headlines.csv` (30 titres, dont 30 fictifs).
- Modèle: `us.anthropic.claude-sonnet-4-6`, prompt `classifier_v1+tx240b40`.
- **Accord global sur la catégorie: 100,0 %** (objectif 80,0 %: atteint).
- Accord sur le drapeau de controverse: 93,3 %.

## Accord par catégorie

| Catégorie attendue | Correct | Total | Accord |
| --- | --- | --- | --- |
| analyst_opinion | 2 | 2 | 100,0 % |
| controversy | 3 | 3 | 100,0 % |
| daily_price | 2 | 2 | 100,0 % |
| dividend | 3 | 3 | 100,0 % |
| earnings_results | 3 | 3 | 100,0 % |
| macro | 2 | 2 | 100,0 % |
| management_change | 3 | 3 | 100,0 % |
| merger_acquisition | 2 | 2 | 100,0 % |
| product | 2 | 2 | 100,0 % |
| regulation_legal | 3 | 3 | 100,0 % |
| rumor_hype | 2 | 2 | 100,0 % |
| strategy_guidance | 3 | 3 | 100,0 % |

## Matrice de confusion (lignes: attendu, colonnes: prédit)

| attendu \ prédit | analyst_opinion | controversy | daily_price | dividend | earnings_results | macro | management_change | merger_acquisition | product | regulation_legal | rumor_hype | strategy_guidance |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| analyst_opinion | 2 |  |  |  |  |  |  |  |  |  |  |  |
| controversy |  | 3 |  |  |  |  |  |  |  |  |  |  |
| daily_price |  |  | 2 |  |  |  |  |  |  |  |  |  |
| dividend |  |  |  | 3 |  |  |  |  |  |  |  |  |
| earnings_results |  |  |  |  | 3 |  |  |  |  |  |  |  |
| macro |  |  |  |  |  | 2 |  |  |  |  |  |  |
| management_change |  |  |  |  |  |  | 3 |  |  |  |  |  |
| merger_acquisition |  |  |  |  |  |  |  | 2 |  |  |  |  |
| product |  |  |  |  |  |  |  |  | 2 |  |  |  |
| regulation_legal |  |  |  |  |  |  |  |  |  | 3 |  |  |
| rumor_hype |  |  |  |  |  |  |  |  |  |  | 2 |  |
| strategy_guidance |  |  |  |  |  |  |  |  |  |  |  | 3 |

## Exemples d'erreurs

- Aucune.

Limites: petit échantillon; une seule personne étiquette; les catégories proches (stratégie, produit, résultats) se confondent facilement.
