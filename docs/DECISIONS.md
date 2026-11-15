# Journal des décisions

| Date (Montréal) | Décision | Raison | Responsable / état |
| --- | --- | --- | --- |
| 2026-11-14 | Utiliser le contexte commun d’AGENTS.md en l’absence de CLAUDE.md | Source fournie par l’équipe | D, appliqué |
| 2026-11-14 | Limiter la livraison à rules/, eval/ et docs/ de D | Respect de la propriété des dossiers | D, appliqué |
| 2026-11-14 | Fixer 100 000 CAD par portefeuille fictif | Comparaisons lisibles, même base | D, appliqué |
| 2026-11-14 | Risque dérivé de la réaction déclarée, pas de l’expérience | Éviter qu’expérience signifie capacité de perte | D, hypothèse de prototype |
| 2026-11-14 | Retenir les limites par risque de la section 11 | Format commun, sans prétention de calibration empirique | D, appliqué |
| 2026-11-14 | Comparer les profils sur une position commune de 10 % | Isoler l’effet du profil de celui du portefeuille | D, appliqué au CSV d’évaluation |
| 2026-11-14 | Bonus de position non cumulatifs; modificateurs cumulés | Éviter le double compte entre paliers | D, à intégrer par A |
| 2026-11-14 | Borne finale [0,1], niveaux inclusifs 0,35 et 0,70 | Reproduction du classement | D, à intégrer par A |
| 2026-11-14 | Limite de concentration appliquée aux FNB aussi | Pas d’exception cachée dans les règles | D; limites explicitées |
| 2026-11-14 | Poids visé = poids final; redimensionnement proportionnel du reste | Éviter l’ajout ambigu de points de pourcentage | D, convention à confirmer par A |
| 2026-11-14 | Différer la conversion récupération/horizon | Unité recovery_days non précisée dans v0 | Référence D maintenant en jours calendaires; confirmation A requise; alerte sommet non retrouvé disponible |
| 2026-11-14 | Livrer des validations calculables, marquer l’application non mesurée | Prix initialement absents, maintenant fournis; API toujours absente | D; aucun succès d’intégration déclaré |
| 2026-11-14 | Vérifier les sources concurrentielles avant citation | Ne pas attribuer une fonction sur simple supposition | D; voir TECH_DOC.md |

Heure, plateforme et format de remise officiels encore à confirmer par l’équipe. Le gel du dimanche 15 novembre 2026 à 22 h 59, heure de Montréal, reste une hypothèse d’organisation tirée du contexte commun.

Complément du 2026-11-14 : starter audité sans modification; 22 références vérifiées par Python standard et pandas. Conserver 252 pour v0 et publier 365 en sensibilité crypto. Correction de la première documentation : une chaîne de cinq taux annuels du même mois non chevauchants permet une inflation cumulée approximative; les niveaux non arrondis restent préférables. Adoption de jours calendaires pour la référence D de récupération, à confirmer par A. Les dates de récupération ne constituent pas une prévision.

Préparation supplémentaire du 2026-11-14 (D) : vérificateur d’acceptation API placé dans eval/ pour rester dans le périmètre D; devise des métriques exigée explicitement; tests hors réseau passés et aucun appel à une API absente. Seconde passe de lecture des trente titres synthétiques consignée sans prétendre à une indépendance humaine. Portefeuille commun de vidéo ajouté pour que la différence de profils ne soit pas confondue avec une différence de poids.
