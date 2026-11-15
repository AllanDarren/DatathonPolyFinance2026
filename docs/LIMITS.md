# Hypothèses et limites

Tous les profils, portefeuilles et titres du jeu d’évaluation sont fictifs. Les seuils de risque sont des paramètres pédagogiques choisis par D, pas des limites réglementaires ou des conseils.

Le jeu financier décrit par le contexte commun couvre du 12 novembre 2021 au 12 novembre 2026. Il est maintenant disponible dans le dossier voisin `../alphaforge_starter` : les métriques de 31 actifs sont recalculées en devise de cotation et en CAD dans `eval/reports/asset_metrics.csv`. La fenêtre prévue comporte un cycle de taux et une forte composante technologique; aucune généralisation à tous les régimes n’est justifiée.

L’univers de 31 actifs sélectionnés en 2026 comporte un biais du survivant. Des actifs disparus ou moins performants peuvent manquer; les pertes observées peuvent donc minimiser certains risques. La diversification n’est pas mesurée par le simple nombre de lignes : QQQ, SPY et des titres technologiques peuvent se recouper.

Les événements historiques sont peu nombreux, potentiellement environ vingt publications trimestrielles par entreprise sur cinq ans, mais le nombre réellement disponible doit être compté. Les fenêtres se chevauchent; le nombre d’observations n’est pas le nombre d’épisodes indépendants. Les centiles sont descriptifs, pas des probabilités de gain ni des bornes futures. Sous huit événements valides, le contexte prévu doit indiquer « données insuffisantes ».

Les prix ajustés dépendent du fournisseur et peuvent être révisés. Ne pas recompter les dividendes. Les séries macro sont parfois révisées ou datées au mois de référence plutôt qu’à la publication : risque d’utiliser une information encore inconnue à l’époque. Le facteur CNQ.TO du 22 août 2022 mentionné dans le contexte doit être vérifié avant interprétation.

Les montants importés sont supposés en CAD. Les prix USD nécessitent une conversion avec le taux connu à la date, sans remplissage vers le passé. Actions et cryptos n’ont pas le même calendrier. La convention v0 de volatilité utilise 252 séances même pour les cryptos : elle doit être indiquée et ne vaut pas convention naturelle 365 jours. Les séries de rendements d’actifs ne sont pas remplies de zéros pour simuler des jours de bourse.

Aucune note ESG ni donnée fondamentale ne permet de certifier un fonds ou une entreprise. Un incident ou une allégation ne prouve pas une faute. Les exclusions sectorielles restent non évaluées sans données explicites, notamment sur les fonds.

La perte annuelle acceptable et la chute historique sommet-creux n’ont pas la même durée. Leur comparaison est un signal pédagogique, pas un calcul de perte future du portefeuille. Les limites par ticker ne distinguent pas encore les FNB diversifiés des titres uniques, ce qui peut produire des alertes excessives sur les fonds. Un profil cohérent avec une règle peut encore subir une perte.

La température zéro et les snapshots facilitent la reproduction, sans garantir à eux seuls une réponse textuelle identique du modèle. Conserver version des données, des règles, des prompts et du modèle. Le gardien peut manquer une erreur sémantique : une vérification automatisée n’est pas une garantie de vérité.

Le produit ne prévoit pas de rendement, ne passe pas de transaction et ne conserve pas de portefeuille. Ces comportements applicatifs restent à vérifier quand l’application sera disponible.
