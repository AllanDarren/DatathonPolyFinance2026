# Vidéo — déroulé de cinq minutes

Durée cible : 5:00. Script de préparation, pas compte rendu d’une démonstration exécutée. Utiliser la vraie application seulement après les tests; si elle fonctionne en mock, le dire et l’afficher. Toute nouvelle synthétique doit porter le badge « exemple fictif ».

| Temps | Image et action | Voix proposée |
| --- | --- | --- |
| 0:00–0:30 | Accueil, avertissement visible | « Trop de nouvelles, peu de contexte. Nous voulons montrer ce qui compte pour un profil, et pourquoi. Ceci est une simulation, pas un conseil financier. » |
| 0:30–1:00 | Charger Robert, afficher horizon et limites, son CSV fictif | « Robert a besoin d’une partie de son argent dans quatre ans. Ses préférences donnent des limites explicites, choisies pour ce prototype. Voici son portefeuille fictif; les alertes de concentration sur les fonds restent visibles. » |
| 1:00–1:40 | Comparaison Robert/Amira, même nouvelle syn_007 de stratégie NVDA, position commune à 10 % | « Amira regarde à vingt ans et s’intéresse à l’IA. Pour la même nouvelle et le même poids, Robert obtient 0,45 et Amira 0,95 selon ces règles. Le bouton Pourquoi montre chaque contribution. Les chiffres viennent du calcul de règles, pas du modèle. » |
| 1:40–2:20 | Simulation Robert, NVDA à 20 %, ouvrir les règles et preuves | « Cette demande dépasse la limite par titre de Robert. La part très volatile doit être recalculée après simulation. Les chutes passées apportent du contexte, sans prédire sa perte future. Chez Amira, le poids seul respecte le seuil, mais ne dispense pas des autres contrôles. » |
| 2:20–3:00 | Afficher les appels d’outils et les claims étiquetés | « Le classifieur range le titre. L’orchestrateur choisit les outils de métriques et de cohérence. Le code applique les règles. Le rédacteur utilise les preuves; le gardien contrôle le soutien des phrases. Une phrase non soutenue doit être retirée ou signalée. » |
| 3:00–3:35 | Ouvrir un contexte historique réel validé, ou état données insuffisantes | « Voici les événements effectivement disponibles et leurs résultats descriptifs. L’échantillon est limité, les fenêtres peuvent se chevaucher. Ce n’est pas une probabilité de gain. Si les données manquent, l’application le dit. » |
| 3:35–4:10 | B montre une vraie requête Bedrock et sa trace expurgée, snapshots S3 et réponse API | « Ici, AWS apporte une contribution effective. Nous montrons la région et le modèle réellement configurés et une requête exécutée. Les journaux de démonstration ne doivent révéler aucun portefeuille personnel ni secret. » |
| 4:10–4:40 | Tableau de validation et test d’une preuve manquante | « Les contrôles ont un statut explicite. Les valeurs comparées sont recalculées indépendamment. Une donnée indisponible ne devient pas un chiffre inventé. » |
| 4:40–5:00 | Retour à la comparaison et tiroir limites | « Notre objectif : rendre le tri compréhensible et vérifiable. Les règles, preuves et limites permettent d’examiner le résultat. Aucune prédiction et aucune transaction. » |

Les scores de la scène 1:00 sont des calculs sur règles et scénario fictif : Robert 0,35 + 0,10 = 0,45; Amira 0,75 + 0,10 + 0,10 = 0,95. Ils ne décrivent pas une probabilité ni un impact financier. Si l’interface ne permet pas encore un portefeuille commun, préparer le même CSV de test pour les deux appels.

Avant tournage : remplacer les statuts en attente par les résultats réellement obtenus; obtenir les captures de C et la preuve AWS de B; vérifier le résultat Amira sur son portefeuille réel de démo plutôt que promettre le verdict du cas contrôlé; masquer les identifiants sensibles; faire relire par l’équipe. La vidéo et la relecture collective ne sont pas réalisées par cette livraison.
