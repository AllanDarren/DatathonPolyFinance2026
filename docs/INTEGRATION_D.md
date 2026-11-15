# Intégration des livrables D

État au 14 novembre 2026 : pack disponible dans `../alphaforge_starter`; dépôt encore sans `CLAUDE.md`, schémas, Makefile ou application. Le contexte commun d’`AGENTS.md` fait foi. Les fichiers respectent sa section 11; validation par les schémas de A encore à faire. Aucun dossier de A, B ou C n’a été modifié.

## Lecture par A et C

- Les fichiers `rules/personas/{id}.yaml` sont directement des `Profile`, sans enveloppe. Les CSV sont des montants **déjà en CAD**, non des quantités ou des prix USD.
- Questionnaire : `sets` utilise des chemins à points comme `preferences.interests`. Appliquer les affectations aux champs autorisés, jamais par évaluation de texte. Réponse absente à `q_expenses` = `x_skip`; les six autres sont obligatoires. Option inconnue = erreur, sans profil inventé. Initialiser les champs fixes `profile_id=custom`, `source=questionnaire`, `base_currency=CAD`, `inconsistencies=[]`; dériver horizon, tolérance et limites des règles. Ne pas inventer un âge.
- Les seuils de profil sont triés : première borne supérieure inclusive correspondante. Les points de risque viennent uniquement de `q_drop`. Le score mesure la préférence déclarée, pas une évaluation professionnelle de capacité financière.
- Comparaisons : `==`, `>`, `<=`, `in` et `contains`; toutes les conditions de `when` sont nécessaires. Résoudre les chemins uniquement dans un contexte explicitement autorisé. `in` signifie « valeur présente dans la liste »; `contains` signifie « liste du contexte contenant la valeur ».
- Pertinence : contexte `profile`, `item` (classification aplatie avec `category`, `controversy`, `tickers`) et `position_weight`. Bonus : **un seul**, le plus grand palier applicable. Modificateurs cumulatifs, score borné à [0,1]. `score < show` : masqué; `show <= score < high` : moyen; `score >= high` : élevé. Comparer les décimales sans erreur de frontière binaire. Chaque différence doit conserver ses preuves et règles.
- Identifiants de traces du poids de base et des paliers : A peut produire `R_BASE_{category}` et `R_POSITION_{min_weight}` avec `base_rule_text_fr` et un texte tel que « Le poids de la position ajoute {delta} au score. » Les objets de ces deux blocs restent au format v0 de la section 11.
- `R_INTEREST_AI` est un rapprochement thématique limité à NVDA, explicitement une hypothèse. Pas de score ESG, de filtre sectoriel ou de transparisation des FNB déduit de données absentes. Les autres intérêts restent visibles dans le profil mais ne donnent pas de bonus automatique.
- Le test de concentration en pertinence s’applique à chaque ticker. Pour une nouvelle multi-tickers, sommer les poids des tickers détenus sans doublons pour la pertinence; ne pas assimiler ce total à une position unique pour la cohérence. A doit confirmer cette convention lors de l’intégration.

## Cohérence : conventions à implémenter

`intended_weight` est le poids **final** visé. Les autres positions sont redimensionnées proportionnellement pour que le total analysé fasse 1; ne pas ajouter 20 % au poids existant. Si le portefeuille n’a que cet actif et qu’un poids inférieur à 1 est demandé, refuser faute de répartition du reliquat. Afficher la part hors univers séparément : le verdict ne couvre que la partie analysée.

`annualized_vol > 0.30` définit très volatile. `high_vol_share` et `top3_concentration` se calculent **après** simulation; `max_drawdown_abs` est positif, `max_drawdown` négatif. Une métrique absente ne satisfait jamais une règle : produire une limite « analyse partielle ». Ne jamais afficher `coherent` comme une validation complète si les données nécessaires manquent.

`recovery_days: null` signifie sommet historique non retrouvé à la fin de la fenêtre, avec preuve de calcul. Une clé absente signifie métrique indisponible. `C_UNRECOVERED_SHORT` vise uniquement le premier cas. Une comparaison chiffrée jours/années est différée : La référence D adopte les jours calendaires dans `metric_policy.yaml`; A doit confirmer cette unité avant toute conversion. Aucun délai de récupération futur n’est estimé.

Sévérités : au moins une règle `high` donne `incoherent`; sinon une `medium` donne `tension`; sinon `coherent` sous réserve de complétude. Le texte de chaque règle cite les valeurs observées et limites lorsque la comparaison est numérique; ces valeurs doivent venir des `Evidence`.

Les FNB restent soumis au seuil par ticker, sans exception implicite. Cela peut signaler la concentration du portefeuille prudent de Robert (ZST.TO 35 %, XBB.TO 20 %) ou de Mateo (ESGV 30 %). Une concentration en fonds n’a pas le même sens qu’en action unique : afficher cette limite méthodologique, sans prétendre que le portefeuille initial passe tous les contrôles. Le choix d’exempter les FNB nécessite une décision d’équipe et de nouvelles données sur leurs expositions.

## Dépendances à traiter par les autres rôles

| Responsable | Besoin | Vérification attendue |
| --- | --- | --- |
| A | Schémas `contracts/rules/`, moteur et validation officielle | `make validate-rules` puis tests des cas d’`eval/` |
| A | Intégrer le starter disponible, puis produire les sorties Evidence | Comparer aux 22 références de `eval/reports/market_validation.csv` |
| A | Export de 60 à 100 vraies nouvelles sourcées | Annotation D puis rapport de classement distinct du jeu synthétique |
| A | Métriques après simulation et sémantique récupération | Résultats Robert/Amira à confronter aux tests contrôlés |
| A/C | Exclusions éthiques sans données sectorielles suffisantes | Afficher « non évalué », jamais « exclusion respectée » |
| B | Commandes Make et preuves AWS | Reprise des validations dans CI; captures et traces expurgées |
| C | Captures, états d’erreur, scénario de comparaison | Exécuter les scénarios manuels et filmer le vrai résultat |

Cette liste prépare les demandes d’intégration. Aucune issue distante ni aucun message à l’équipe n’a été envoyé depuis cette session.

## Complément après réception du starter

Voir DATA_AUDIT.md pour les manques, `rules/asset_class_mapping.yaml` pour les classes, et `rules/metric_policy.yaml` pour les conventions des références. Les scripts D lisent directement `../alphaforge_starter`, sans déplacer ou modifier les sources. B/A doivent fournir un chemin de données au déploiement.

Les deux versions du scénario NVDA 20 % sont maintenant calculées à partir des prix : Robert est incohérent (20 % par titre et très volatile contre 10 %), Amira en tension (50 % très volatile contre une limite de 60 %, avec alerte de chute historique). Voir `eval/reports/portfolio_scenarios.json`. Ce fichier est un résultat de validation D, pas une réponse API ni un objet Evidence déjà émis par A.
