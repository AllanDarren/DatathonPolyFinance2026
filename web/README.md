# web/ — Interface AlphaForge AI (rôle C)

React 18 + Vite + TypeScript strict, Recharts, Vitest. Aucun `localStorage`, aucun cookie, aucune analytique :
l'état vit en mémoire le temps de la session.

## Démarrer

```bash
cd web
npm install
cp .env.example .env      # VITE_MOCK=1 par défaut
npm run dev               # http://localhost:5173
```

| Variable | Rôle |
|---|---|
| `VITE_API_URL` | URL de l'API (rôle B). Vide = mode simulé. |
| `VITE_MOCK` | `1` = sert le faux backend de `src/api/mock/` (données **fictives**, badge « exemple fictif »). |

Avec l'API réelle : `VITE_MOCK=0 VITE_API_URL=https://… npm run dev`.

## Scripts

| Commande | Effet |
|---|---|
| `npm run dev` | Serveur de dev (régénère d'abord les données) |
| `npm run build` | Typage + build statique dans `web/dist` (livré à B) |
| `npm test` | Vitest + Testing Library |
| `npm run gen:types` | Génère `src/types/generated/` depuis `contracts/*.schema.json` (A). Sans `contracts/`, on garde `src/types/contracts.ts` (section 8). |
| `npm run build:data` | Convertit `rules/glossary.yaml` et `rules/questionnaire.yaml` (D) en JSON dans `src/generated/`. Sans ces fichiers, un brouillon de secours est utilisé. |

## Organisation

```
src/
├── api/            client typé (endpoints section 8) + mock/ (faux backend, mode simulé seulement)
├── components/     cartes de nouvelles, « Pourquoi? », preuves, verdict, historique, calendrier…
├── screens/        Accueil, Questionnaire, Profil, Portefeuille, Tableau de bord, Comparer
├── state/          état en mémoire (contexte React)
├── lib/            formatage (aucun calcul financier), univers des 31 actifs
├── strings.ts      toutes les chaînes visibles (français)
└── types/          contrats (provisoires tant que A n'a pas publié contracts/)
```

## Règles respectées

- Le front **ne calcule aucun chiffre financier** : il formate ce que l'API envoie. Le seul code qui calcule
  est `src/api/mock/`, qui imite le backend en mode simulé et n'est jamais utilisé avec l'API réelle.
- Le texte d'un claim est affiché comme texte, jamais injecté comme HTML.
- Aucun verbe d'ordre (test automatique).
- L'avertissement « Simulation éducative — pas un conseil financier » est visible sur tous les écrans.
- Fait / Hypothèse / Scénario se distinguent par la couleur, l'icône, le texte et le style de bordure.
