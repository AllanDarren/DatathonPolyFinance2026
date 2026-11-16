# AlphaForge AI — documentation technique

Version D du 14 novembre 2026. Livré : règles, personas, questionnaire, évaluation synthétique et documents. Architecture applicative ci-dessous **prévue par le contexte**, non exécutée dans cette livraison. Le starter financier est maintenant disponible à côté du dépôt; aucune API n’est encore présente.

## Problème et méthode

Le produit trie les nouvelles selon l’horizon, les positions et les préférences, puis montre les règles et preuves du classement. Les personas fictifs Robert, Amira et Mateo servent de situations contrastées, jamais de recommandations de placement.

Le code doit déterminer le profil, calculer les métriques et appliquer les règles YAML. Le modèle classe les titres selon douze catégories puis rédige à partir de preuves. Un gardien contrôle les explications. Pour une demande hypothétique, l’orchestrateur choisit les outils à appeler; le verdict reste celui du moteur de règles. L’intégration AWS prévue utilise Bedrock pour les agents et les services décrits dans les documents de B. Leur fonctionnement doit être démontré par une trace réelle, pas par ce texte.

## Sources, actifs et traitements

La liste d’actifs prévue est celle du cahier des charges commun de l’équipe : dix actions canadiennes, dix américaines, neuf FNB et deux cryptos. Les fichiers attendus sont `assets_universe.csv`, `prices_daily.csv`, `corporate_actions.csv`, `fx_usdcad_daily.csv`, `macro_rates.csv` et `sources_metadata.csv`. Les métadonnées fournies identifient Yahoo Finance via yfinance, la Banque du Canada et FRED; dates de collecte et limites sont présentes. L’audit local conserve leurs empreintes, sans recertification de chaque observation auprès des fournisseurs. Les taux USD/CAD sont prévus via la Banque du Canada, les séries macro canadiennes et FRED selon le contexte commun.

Les montants des CSV sont déjà en CAD. Pour une série de prix USD, `P_CAD(t) = adj_close_USD(t) × FX_USDCAD(t)`; reporter seulement le dernier FX connu. Ne pas confondre une performance USD et CAD. Les données réelles devront être vérifiées pour doublons, valeurs invalides, dates et observations manquantes, sans remplir artificiellement les rendements des actions le week-end.

## Calculs attendus

- Rendement quotidien : `P(t)/P(t-1)-1`, sur prix ajustés dans la devise annoncée.
- Rendement 2022 : dernier prix valide de 2022 / dernier prix valide de 2021 − 1. Utiliser le dernier jour connu au plus tard à chaque borne, en indiquant les dates.
- Volatilité : écart-type **échantillonnal** des rendements × racine de 252 selon v0; convention crypto à afficher, voir LIMITS.md.
- Perte maximale : minimum de `P(t)/max(P(s), s<=t)-1`. Elle est négative; sa valeur absolue sert aux règles.
- Corrélation mensuelle : prix de fin de mois, rendements, intersection des mois valides, puis corrélation de Pearson. Ni somme de corrélations ni calcul à partir des seuls niveaux de prix.
- Poids : montant / total analysé; part hors univers = montant hors univers / total importé. Conserver les deux dénominateurs.
- Inflation cumulée : rapport de niveaux d’IPC comparables moins 1. Ne pas sommer ni multiplier des taux annuels qui se chevauchent. Les cinq taux de septembre 2022 à septembre 2026 couvrent des années adjacentes : leur produit donne environ 19,0220 % depuis septembre 2021, sous réserve de l’arrondi des taux. Ne pas multiplier les taux annuels de tous les mois.
- Contexte d’événement : de la dernière séance avant l’événement à la cinquième séance après; l’heure de publication et les événements hors séance doivent être traités explicitement par A. Médiane et centiles sur les cas valides, au moins huit cas, limites visibles.

Les choix de règles, l’ordre d’application et les unités sont détaillés dans les fichiers de `rules/` et leurs schémas (`contracts/rules/`). Les seuils sont une politique pédagogique du prototype. Les portefeuilles n’ont pas été optimisés et ne constituent pas des allocations proposées à une personne réelle.

## Exemple de conclusion reliée aux preuves

**Exemple entièrement fictif**, dérivé de `eval/coherence_cases.yaml`, pas des prix de NVDA : Robert simule une position finale de 20 %; sa limite est 10 %.

| Preuve illustrative | Valeur | Source | Producteur attendu |
| --- | --- | --- | --- |
| ev_demo_weight | 0,20 | consideration et cas robert_nvda_20 | moteur de simulation de A |
| ev_demo_limit | 0,10 | rules/personas/robert.yaml | moteur de profil de A |
| ev_demo_high_vol | 0,20 | métrique fictive du cas contrôlé | calcul de portefeuille de A |
| ev_demo_high_vol_limit | 0,10 | rules/personas/robert.yaml | moteur de profil de A |
| ev_demo_rule | C_MAX_SINGLE | rules/coherence_rules.yaml | moteur de cohérence de A |

Chaque objet Evidence réel devra aussi porter `kind`, `statement`, `as_of`, `inputs`, `source` et `computed_by`. Ces identifiants sont illustratifs et ne prétendent pas être des Evidence déjà émises par l’API.

Claim de scénario : « Dans cette simulation, le poids visé de {{ev_demo_weight}} dépasse la limite de {{ev_demo_limit}}. » Le code remplace les repères en 20 % et 10 %. Le gardien vérifie les identifiants, valeurs et soutien du texte. `C_MAX_SINGLE` suffit au verdict `incoherent`; `C_HIGH_VOL_SHARE` apporte une deuxième comparaison chiffrable. Une chute fictive de 66 % contre une perte annuelle acceptable de 8 % ajoute une alerte de sévérité moyenne, avec sa limite de durée clairement affichée.

Si une preuve manque, le claim ne peut pas être marqué `supported`. Si le modèle est indisponible, afficher règles et preuves sans résumé généré. Ne pas fabriquer une justification après le verdict. Le front affiche séparément Fait, Hypothèse et Scénario; jamais de HTML issu d’un titre externe.

## Évaluation et état des validations

Le contrôle local `python3 eval/check_role_d.py` vérifie les structures v0, totaux, réponses des personas, étiquettes et verdicts sur entrées contrôlées. Il ne remplace pas `make validate-rules` ni les tests de l’application. `docs/VALIDATION.md` compare 22 valeurs par deux méthodes indépendantes du moteur; les résultats applicatifs restent à compléter. `docs/TEST_SCENARIOS.md` contient les tests de bout en bout encore non exécutés.

Le jeu des trente titres est synthétique et chevauche les exemples de la taxonomie : il sert au démarrage, pas à une estimation indépendante de performance. A doit exporter de vraies nouvelles sourcées; D étiquettera 60 à 100 titres avant une évaluation séparée. Aucun taux d’accord réel n’est annoncé.

## Positionnement vérifié

Sources officielles consultées le 14 novembre 2026 : [Questrade](https://www.questrade.com/learning/using-questrade/discover-and-explore-feed-on-questrade-app) décrit un fil adapté aux positions, à la liste de suivi et aux préférences. [Interactive Brokers](https://www.interactivebrokers.com/en/portfolioanalyst/features.php) décrit ses outils PortfolioAnalyst, dont l’attribution de performance. [Delta](https://delta.app/academy/post/ai-portfolio-analyst-whats-going-on) décrit des explications IA des mouvements adaptées aux positions.

Notre contribution visée combine traçabilité des phrases, règles de cohérence du profil et limites visibles. C’est un objectif de conception, pas une revendication d’exclusivité ni une démonstration que les produits cités n’ont pas ces fonctions. La référence Vanguard du contexte n’a pas été utilisée faute de vérification primaire dans cette livraison.

## Limites et améliorations

Voir LIMITS.md : période courte, survivance, échantillons dépendants, devises, absence de notes ESG, données partielles et incertitude des modèles. Priorités : terminer les schémas et intégrations, confronter l’application aux références recalculées, évaluer sur titres indépendants, préciser la récupération et les expositions internes des FNB, puis relire les sorties des trois profils avec l’équipe.
