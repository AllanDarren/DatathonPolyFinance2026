# Format des fichiers de règles (pour le rôle D)

Les fichiers de `rules/` sont lus par `core/rules_engine.py`. Avant chaque PR: `make validate-rules`.
Les messages disent quel fichier, à quel endroit, ce qui ne va pas et comment corriger.

- `*.schema.json`: le format exact de chaque fichier (généré depuis `core/rules_models.py`).
- `examples/`: un jeu complet et valide, conforme au format des fichiers de règles. **Point de départ
  conseillé**: copie `examples/` vers `rules/`, puis modifie. Tant qu'un fichier manque dans `rules/`,
  l'application utilise celui de `examples/` (avertissement de `make validate-rules`).

## Conditions (`when`)

Liste de comparaisons toutes vraies (ET). Jamais d'expression libre.

```yaml
when:
  - {field: profile.risk_tolerance, op: in, value: [low, low_moderate]}          # constante
  - {field: position.weight, op: '>', value_from: profile.limits.max_single_position}  # autre champ
  - {metric: max_drawdown_abs, op: '>', limit_from: profile.max_acceptable_loss_pct}   # cohérence
```

Opérateurs: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not_in` (valeur dans une liste),
`contains`, `not_contains` (une liste contient une valeur, ex.: intérêts contient `crypto`).

Champs lisibles:

- profil (`profile_rules.yaml`: sans préfixe; ailleurs: `profile.`): `horizon_years`, `horizon_bucket`,
  `risk_tolerance`, `max_acceptable_loss_pct`, `objective`, `experience`, `age`,
  `preferences.avoid_controversies`, `preferences.excluded_sectors`, `preferences.interests`,
  `limits.max_single_position`, `limits.max_high_vol_share`, `monthly_expenses_cad`;
- pertinence: `position_weight` (alias de `position.weight`), `item.category`, `item.horizon_relevance`, `item.controversy`, `item.controversy_type`,
  `position.weight`, `position.asset_class`, `position.sector` (secteur de `data/assets_universe.csv`,
  en anglais, ex.: `Energy`), `position.is_high_vol`, `position.annualized_vol`, `position.held`;
- cohérence: métriques de `core/METRICS.md` (section « Métriques des règles de cohérence »).

Repères dans les textes: pertinence `{category}`, `{weight}`, `{horizon_bucket}`;
cohérence `{limit}`, `{observed}`, `{ticker}` (formatés par le code, ex.: « 20 % »).

**Piège YAML**: un texte qui contient « : » doit être entre guillemets
(`text_fr: "Limite: {limit}"`). L'exemple initial du cahier des charges avait ce piège.

## Ajouts au format de la section 11 (tous facultatifs)

- `profile_rules.yaml`: `defaults` (valeurs du profil quand aucune réponse ne les fixe) et
  `high_vol_threshold` (0,30 par défaut).
- `questionnaire.yaml`: `optional: true` pour une question facultative.
- `relevance_rules.yaml`: `text_fr` pour chaque palier de `position_weight_bonus`, `thresholds.medium`,
  `hidden_reasons_fr` (`short_term_noise`, `low_relevance`).
- `glossary.yaml`: `example_fr` par terme.
