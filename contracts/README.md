# Contracts (v0.1.0)

Source of truth between roles. Owned by role A.

- `alphaforge.schema.json`: every contract type under `$defs/<Name>` (JSON Schema 2020-12).
  Example reference: `alphaforge.schema.json#/$defs/FeedResponse`.
  Generated from `core/models.py` with `make contracts`; never edit by hand.
- `examples/`: valid examples (`feed_robert.json` with a `coherence` block for 20 % NVDA,
  `feed_amira.json`, `feed_mateo.json`, `personas.json`). Rebuilt with `make examples`.
- `rules/`: schemas of role D's rule files (coming in A3).

Types: `Profile`, `Persona`, `Position`, `Portfolio`, `Consideration`, `NewsRecord`, `Event`,
`Evidence`, `Claim`, `Explanation`, `RuleHit`, `HistoricalContext`, `CoherenceResult`, `FeedItem`,
`FeedResponse`, request bodies (`ProfileRequest`, `PortfolioParseRequest`, `FeedRequest`),
`ErrorResponse` and `Health`.

## A0 examples: what is real and what is not

- Real (computed from `data/`): volatility, max drawdown, 2022 return, worst calendar year,
  position weights, and the RY.TO ex-dividend historical context.
- Placeholder: personas, taxonomy and relevance/coherence rules (role D owns the real ones in `rules/`).
- Synthetic: all news items (`is_synthetic: true`, source "Exemple fictif").

The real pipeline (A7) will regenerate these files without changing their shape.
Any breaking change follows the `[contract]` procedure in CLAUDE.md.
