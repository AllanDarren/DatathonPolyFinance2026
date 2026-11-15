# AlphaForge AI — comprendre ce qui compte pour son profil

**Problème.** Un même titre d’actualité ne mérite pas la même attention lorsqu’on approche de la retraite ou qu’on investit à très long terme. Le bruit encourage les réactions sans contexte.

**Solution proposée.** Un fil de nouvelles relié au portefeuille, trié selon des règles visibles. Le bouton « Pourquoi? » montre la catégorie, le poids de la position, les règles et les preuves. Un champ « J’envisage d’acheter X » teste une situation hypothétique : cohérente, en tension ou incohérente avec les paramètres déclarés. Aucun ordre d’achat ou de vente.

**Approche agentique prévue.** Un classifieur organise les nouvelles; un orchestrateur choisit les outils utiles; un rédacteur assemble une courte explication à partir de preuves; un gardien contrôle les phrases. Le code calcule et tranche selon des règles versionnées. AWS Bedrock doit exécuter réellement les agents lors de la démonstration.

**Originalité visée.** Relier chaque phrase à ses preuves et distinguer faits, hypothèses et scénarios. La personnalisation de nouvelles et les explications de portefeuille existent déjà chez [Questrade](https://www.questrade.com/learning/using-questrade/discover-and-explore-feed-on-questrade-app), [Interactive Brokers](https://www.interactivebrokers.com/en/portfolioanalyst/features.php) et [Delta](https://delta.app/academy/post/ai-portfolio-analyst-whats-going-on). Notre angle combine règles de cohérence et explication vérifiable; aucune exclusivité n’est revendiquée.

**Données prévues.** Trente et un actifs publics, cinq ans de prix ajustés, change USD/CAD, séries macro et nouvelles sourcées. Le starter fourni contient les métadonnées Yahoo/yfinance, Banque du Canada et FRED; ses empreintes sont conservées dans le rapport D. Le démarrage dispose de trente titres fictifs clairement étiquetés.

**Démonstration à enregistrer.** Robert, horizon quatre ans, et Amira, vingt ans, regardent la même nouvelle fictive de stratégie de NVDA, à poids identique. Les règles donnent une pertinence moyenne pour Robert et élevée pour Amira. Une position hypothétique de 20 % dépasse la limite de Robert de 10 %; chez Amira, la limite par titre est 25 %, mais d’autres alertes restent possibles. Sources des paramètres : rules/personas/ et rules/relevance_rules.yaml.

**Bénéfices à tester.** Moins de bruit, raisonnement inspectable, limites compréhensibles. Aucune promesse de gain ou de meilleure performance financière.

**État de cette livraison.** Contenu du rôle D disponible. Vingt-deux valeurs du starter sont recalculées par deux méthodes. Comparaison à l’application, preuve AWS et vidéo finale restent à effectuer avec A, B et C. Simulation pédagogique, pas un conseil financier.
