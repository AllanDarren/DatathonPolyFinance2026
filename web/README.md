# web/ — Interface AlphaAI

React 18 + Vite + TypeScript strict, Recharts, Vitest. Aucun `localStorage`, aucun cookie, aucune analytique :
l'état vit en mémoire le temps de la session.

## Démarrer

```bash
cd web
npm install
npm run dev               # http://localhost:5173
```

Le site appelle toujours la vraie API : `http://127.0.0.1:8000` par défaut (`python -m api.local_server` à la racine).

| Variable | Rôle |
|---|---|
| `VITE_API_URL` | URL de l'API. Vide = `http://127.0.0.1:8000`. Au déploiement, renseignée par `make deploy-web`. |
| `VITE_MOCK` | `1` = faux backend de `src/api/mock/` (données **fictives**), réservé aux tests automatiques. |

Pour viser une autre API : copier `.env.example` en `.env` et renseigner `VITE_API_URL`.

## Scripts

| Commande | Effet |
|---|---|
| `npm run dev` | Serveur de dev (régénère d'abord les données) |
| `npm run build` | Typage + build statique dans `web/dist` |
| `npm test` | Vitest + Testing Library |
| `npm run gen:types` | Génère les types depuis `contracts/*.schema.json` |
| `npm run build:data` | Convertit `rules/glossary.yaml` et `rules/questionnaire.yaml` en JSON dans `src/generated/` |

## Organisation

```
src/
├── api/            client typé + mock/ (faux backend, tests seulement)
├── components/     barre latérale, cartes de nouvelles, « Pourquoi? », preuves, verdict, historique…
├── screens/        Accueil, Questionnaire, Profil, Portefeuille, Mes nouvelles, Tester un achat, Calendrier
├── state/          état en mémoire (contexte React), navigation par hash
├── lib/            formatage (aucun calcul financier)
├── strings.ts      toutes les chaînes visibles (français)
├── styles.css      styles de base ; redesign.css : thème sombre
└── types/          types des contrats
```

## Règles respectées

- Le front **ne calcule aucun chiffre financier** : il formate ce que l'API envoie. Le seul code qui calcule
  est `src/api/mock/`, utilisé uniquement par les tests.
- Le texte d'un claim est affiché comme texte, jamais injecté comme HTML.
- Aucun verbe d'ordre (test automatique).
- Fait / Hypothèse / Scénario se distinguent par la couleur, l'icône, le texte et le style de bordure.
- Les hypothèses et limites restent accessibles depuis le pied de page de chaque écran.
