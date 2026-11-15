# Métriques nommées (v0)

Implémentées dans `core/metrics.py`. Chaque fonction retourne `MetricResult(value, evidence)`; l'`Evidence` contient la valeur, les entrées, la source et la fonction (`computed_by`). Les identifiants de preuve sont dérivés du contenu: le même calcul donne toujours le même `ev_…`.

Conventions communes:

- Prix: `adj_close` (ajusté des dividendes et des fractionnements), dans la **devise de cotation** par défaut. Les fonctions sur un seul actif acceptent `currency="CAD"` (conversion par le taux USD/CAD du même jour; dernier taux connu reporté les jours sans taux).
- Fenêtre: toute la période du jeu de départ (2021-11-12 au 2026-11-12). Chaque actif garde ses propres jours de cotation (aucun alignement).
- Fractions entre 0 et 1; les pertes sont négatives.

| Nom (règles) | Fonction | Définition | Unité |
| --- | --- | --- | --- |
| `annualized_vol` | `annualized_vol(ticker)` | Écart-type des rendements quotidiens × √252 (titres et FNB) ou × √365 (crypto, qui cote 7 jours sur 7). Décision d'équipe du 2026-11-14 | fraction |
| `max_drawdown` | `max_drawdown(ticker)` | Pire chute entre un sommet et le creux suivant (négatif); dates du sommet et du creux dans les entrées | fraction |
| `max_drawdown_abs` | `max_drawdown_abs(ticker)` | Valeur absolue de `max_drawdown` | fraction |
| `recovery_days` | `recovery_days(ticker)` | Jours **calendaires** entre le creux de la pire chute et le retour au sommet précédent; `null` si jamais retrouvé | jours |
| `calendar_year_return` | `calendar_year_return(ticker, year)` | Dernier prix de l'année ÷ dernier prix de l'année précédente − 1. Refusé pour 2021 (pas de fin d'année précédente) et 2026 (année incomplète) | fraction |
| `worst_calendar_year_return` | `worst_calendar_year_return(ticker)` | Pire rendement parmi les années civiles complètes (2022 à 2025) | fraction |
| `return_5y` | `return_5y(ticker)` | Dernier prix ÷ premier prix − 1 sur la fenêtre | fraction |
| `dividend_yield_ttm` | `dividend_yield_ttm(ticker)` | Dividendes dont la date ex est dans les 365 derniers jours ÷ dernier `close` (même devise). Distributions des FNB possiblement incomplètes | fraction |
| `position_weight` | `position_weight(portfolio, ticker)` | Poids de la position dans le portefeuille analysé (0 si non détenue) | fraction |
| `position_weight_after` | `position_weight_after(portfolio, ticker, w)` | Poids visé après l'ajout hypothétique (= `w`). Les entrées contiennent le montant implicite à ajouter: (w·T − a) ÷ (1 − w) | fraction |
| `is_high_vol` | `is_high_vol(ticker, threshold=0.30)` | Vrai si `annualized_vol` > seuil | booléen |
| `high_vol_share` | `high_vol_share(portfolio, threshold=0.30)` | Somme des poids des positions très volatiles | fraction |
| `top3_concentration` | `top3_concentration(portfolio)` | Poids cumulé des trois plus grosses positions | fraction |
| `asset_class` | `asset_class(ticker)` | `equity_ca`, `equity_us`, `bond_etf`, `equity_etf`, `gold_etf` ou `crypto` | texte |
| `corr_to_portfolio` | `corr_to_portfolio(portfolio, ticker)` | Corrélation des rendements **mensuels en CAD** de la position avec le reste du portefeuille (poids renormalisés) | corrélation |

Fonctions complémentaires (validation, documentation):

| Fonction | Définition |
| --- | --- |
| `monthly_correlation(a, b)` | Corrélation des rendements mensuels (fin de mois, devise de cotation) |
| `cumulative_inflation_ca()` | Produit des variations annuelles de l'IPC canadien (`STATIC_TOTALCPICHANGE`) de sept. 2022 à sept. 2026, soit sept. 2021 à sept. 2026. Approximation |

## Validation des valeurs de référence (2026-11-14)

Recalcul indépendant (script séparé, pandas) des valeurs de la section 6 du contexte commun. Elles sont figées dans `tests/test_metrics.py`.

| Mesure | Référence | Recalcul | Verdict |
| --- | --- | --- | --- |
| Rendement 2022 | SPY −18,2; QQQ −32,6; AGG −13,0; XBB.TO −11,7; TLT −31,2; GLD −0,8; BTC −64; ETH −67; NVDA −50; XOM +87 | −18,2; −32,6; −13,0; −11,7; −31,2; −0,8; −64,3; −67,5; −50,3; +87,4 | conforme |
| Perte maximale | NVDA −66; TSLA −73; BTC −76; ETH −79; SPY −24,5; AGG −17; XBB.TO −15,5; TLT −44; ZST.TO −0,4 | −66,3; −73,0; −75,9; −78,7; −24,5; −17,2; −15,5; −43,7; −0,4 | conforme |
| Corrélation mensuelle | QQQ–SPY 0,91; ESGV–SPY 0,99; BTC–ETH 0,83; BTC–QQQ 0,49 | 0,912; 0,991; 0,828; 0,493 | conforme |
| Rendement sur 5 ans | SPY +73,2 (USD), +96,5 (CAD); QQQ +79,6; ESGV +61,4 | identiques | conforme |
| Inflation canadienne cumulée | environ +19 | +19,0 | conforme |
| Volatilité annualisée | BTC ≈ 54; NVDA ≈ 50; SPY ≈ 15 | quotidien ×√252/365: **50,8; 51,9; 17,3** | **écart expliqué**: la référence venait de rendements mensuels ×√12 (53,7; 49,8; 15,4). On garde les rendements quotidiens, plus nombreux; les tests utilisent les valeurs recalculées |

## Limites

- Une seule fenêtre de 5 ans (hausse des taux, marché porté par la technologie); biais du survivant (actifs choisis en 2026).
- Les métriques sur un actif sont en devise de cotation par défaut; pour un investisseur en CAD, l'expérience réelle d'un actif américain diffère (effet de change). `currency="CAD"` est disponible.
- `adj_close` est rétro-ajusté: un nouveau téléchargement peut changer les valeurs anciennes.
- La volatilité de la crypto (365 jours) et celle des actions (252 jours) sont annualisées chacune sur ses propres jours de cotation.

## Métriques des règles de cohérence

Utilisables dans `rules/coherence_rules.yaml` (`metric: …`), calculées pour l'actif envisagé par `core.rules_engine.coherence_metrics`:

| Nom | Définition | Format de `{observed}` |
| --- | --- | --- |
| `position_weight_after` | Poids visé après l'ajout | % |
| `annualized_vol`, `max_drawdown`, `max_drawdown_abs`, `worst_calendar_year_return`, `return_5y`, `dividend_yield_ttm` | Voir le tableau principal | % |
| `worst_calendar_year_loss_abs` | Perte de la pire année civile (0 si aucune année négative) | % |
| `recovery_days` / `recovery_years` | Temps de récupération après la pire chute (vide si jamais retrouvé: la règle ne se déclenche pas) | jours / ans |
| `is_high_vol` | Vrai si volatilité > `high_vol_threshold` de `profile_rules.yaml` | — |
| `asset_class` | Classe d'actif | — |
| `high_vol_share_after` | Part des positions très volatiles après l'ajout (les autres montants inchangés) | % |
| `top3_concentration_after` | Poids des trois plus grosses positions après l'ajout | % |
| `crypto_share_after` | Part des cryptomonnaies après l'ajout | % |
| `corr_to_portfolio` | Corrélation mensuelle (CAD) avec le portefeuille actuel | nombre |

Portefeuille après l'ajout: les montants des autres positions restent fixes et la position envisagée est portée à `intended_weight` du nouveau total.

## Contexte historique (`core/event_study.py`)

`historical_context(event_type, asset)`: rendement `adj_close` (devise de cotation) de la clôture de la veille de l'événement à la clôture du 5e jour de bourse après le premier jour de bourse à partir de l'événement (fenêtre t−1 → t+5, jours de cotation propres à l'actif). Médiane, p10, p90 (percentiles linéaires), part de cas positifs, liste des événements. Refus sous 8 événements (« données insuffisantes »). Mentions obligatoires: échantillon, chevauchements (comptés), biais du survivant, « pas une prévision »; pour les dates ex-dividende, neutralisation par les prix ajustés. Dates: instantané `data/snapshots/events_*.json` (résultats et dividendes par titre; décisions de taux de la Fed ou de la Banque du Canada via `macro_source`).
