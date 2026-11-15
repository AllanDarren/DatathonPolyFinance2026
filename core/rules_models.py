"""Schemas of role D's rule files (CLAUDE.md section 11).

Pydantic models are the source; `python -m tools.export_schemas` also writes
`contracts/rules/<file>.schema.json`. Conditions (`when`) are lists of comparisons
that must all be true (AND). No free-form expression is ever evaluated.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.models import Profile

Op = Literal["==", "!=", "<", "<=", ">", ">=", "in", "not_in", "contains", "not_contains"]
RiskLevel = Literal["low", "low_moderate", "moderate", "high"]
HorizonRelevance = Literal["structural", "macro_context", "short_term_noise"]


class RulesModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(RulesModel):
    """One comparison. Left side: `field` (dotted path) or `metric` (named metric).
    Right side: `value` (constant) or `value_from` / `limit_from` (dotted path)."""

    field: str | None = None
    metric: str | None = None
    op: Op
    value: Any = None
    value_from: str | None = None
    limit_from: str | None = None

    @model_validator(mode="after")
    def _one_side_each(self) -> Condition:
        if (self.field is None) == (self.metric is None):
            raise ValueError("indique soit « field », soit « metric » (un seul des deux)")
        # `value: null` is a legitimate constant (e.g. recovery_days == null): count it when explicitly set.
        rights = ["value" in self.model_fields_set, self.value_from is not None, self.limit_from is not None]
        if sum(rights) != 1:
            raise ValueError("indique exactement un de « value », « value_from » ou « limit_from »")
        return self

    @property
    def right_path(self) -> str | None:
        return self.value_from or self.limit_from


# --- questionnaire.yaml ---------------------------------------------------------


class QuestionOption(RulesModel):
    id: str
    label: str
    sets: dict[str, Any] = Field(default_factory=dict, description="Profile fields set by this option (dotted paths)")
    points: dict[str, float] = Field(default_factory=dict, description="Points added, e.g. {risk: 2}")


class Question(RulesModel):
    id: str
    text: str
    help: str | None = None
    optional: bool = False
    options: list[QuestionOption] = Field(min_length=2)


class Questionnaire(RulesModel):
    version: int
    questions: list[Question] = Field(min_length=1)


# --- profile_rules.yaml ---------------------------------------------------------


class HorizonBucketRule(RulesModel):
    id: Literal["short", "medium", "long"]
    max_years: float


class RiskTier(RulesModel):
    max_points: float
    value: RiskLevel


class Limits(RulesModel):
    max_single_position: float = Field(ge=0, le=1)
    max_high_vol_share: float = Field(ge=0, le=1)


class InconsistencyCheck(RulesModel):
    id: str
    when: list[Condition] = Field(min_length=1)
    text_fr: str


class ProfileRules(RulesModel):
    version: int
    horizon_buckets: list[HorizonBucketRule] = Field(min_length=1)
    risk_from_points: list[RiskTier] = Field(min_length=1)
    limits_by_risk: dict[RiskLevel, Limits]
    inconsistency_checks: list[InconsistencyCheck] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict, description="Profile fields used when no answer sets them")
    high_vol_threshold: float = Field(default=0.30, gt=0, lt=5)


# --- taxonomy.yaml --------------------------------------------------------------


class Category(RulesModel):
    id: str
    label_fr: str
    definition: str
    horizon_relevance: HorizonRelevance
    examples: list[str] = Field(min_length=1)


class Taxonomy(RulesModel):
    version: int
    categories: list[Category] = Field(min_length=1)
    controversy_types: list[str] = Field(min_length=1)


# --- relevance_rules.yaml -------------------------------------------------------


class PositionBonus(RulesModel):
    min_weight: float = Field(ge=0, le=1)
    add: float
    text_fr: str | None = None


class Modifier(RulesModel):
    id: str
    when: list[Condition] = Field(min_length=1)
    add: float
    text_fr: str


class Thresholds(RulesModel):
    show: float
    high: float
    medium: float | None = None


class RelevanceRules(RulesModel):
    version: int
    base_weights: dict[str, dict[str, float]]
    base_rule_text_fr: str
    position_weight_bonus: list[PositionBonus] = Field(default_factory=list)
    modifiers: list[Modifier] = Field(default_factory=list)
    thresholds: Thresholds
    hidden_reasons_fr: dict[str, str] = Field(
        default_factory=dict, description="Optional texts: keys 'short_term_noise' and 'low_relevance'"
    )


# --- coherence_rules.yaml -------------------------------------------------------


class Verdict(RulesModel):
    incoherent_if_high_at_least: int = Field(ge=1)
    tension_if_medium_at_least: int = Field(ge=1)


class CoherenceRule(RulesModel):
    id: str
    severity: Literal["low", "medium", "high"]
    when: list[Condition] = Field(min_length=1)
    text_fr: str


class CoherenceRules(RulesModel):
    version: int
    verdict: Verdict
    rules: list[CoherenceRule] = Field(min_length=1)


# --- glossary.yaml / limits_texts.yaml ------------------------------------------


class Term(RulesModel):
    id: str
    term: str
    definition_fr: str
    example_fr: str | None = None


class Glossary(RulesModel):
    terms: list[Term]


class LimitsTexts(RulesModel):
    limits: list[str]
    disclaimers: list[str]


# --- instrument_risks.yaml / source_tiers.yaml / language_policy.yaml -------------

RiskLevelText = Literal["low", "medium", "high"]


class RiskType(RulesModel):
    id: str
    label_fr: str
    question_fr: str


class InstrumentRisk(RulesModel):
    risk: str
    level: RiskLevelText
    text_fr: str


class InstrumentClass(RulesModel):
    label_fr: str
    what_you_own_fr: str
    return_source_fr: str
    risks: list[InstrumentRisk] = Field(min_length=1)


class DiversificationThresholds(RulesModel):
    overlap_corr: float = Field(default=0.8, ge=-1, le=1)
    new_exposure_corr: float = Field(default=0.3, ge=-1, le=1)


class SectorExclusion(RulesModel):
    label_fr: str
    sectors: list[str]


class InstrumentRisks(RulesModel):
    version: int
    source: str | None = None
    risk_types: list[RiskType] = Field(min_length=1)
    asset_classes: dict[str, InstrumentClass]
    diversification: DiversificationThresholds = Field(default_factory=DiversificationThresholds)
    sector_exclusions: dict[str, SectorExclusion] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _known_risks(self) -> InstrumentRisks:
        known = {r.id for r in self.risk_types}
        for cls_id, cls in self.asset_classes.items():
            for r in cls.risks:
                if r.risk not in known:
                    raise ValueError(f"asset_classes.{cls_id}: risque inconnu '{r.risk}' (absent de risk_types)")
        return self


class SourceTier(RulesModel):
    id: Literal["primary", "established", "aggregator"]
    label_fr: str
    text_fr: str
    patterns: list[str] = Field(min_length=1)


class UnknownTier(RulesModel):
    label_fr: str
    text_fr: str


class SourceTiers(RulesModel):
    version: int
    tiers: list[SourceTier] = Field(min_length=1)
    unknown: UnknownTier


class LanguagePolicy(RulesModel):
    version: int
    allowed: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    past_performance_terms: list[str] = Field(default_factory=list)
    forecast_terms: list[str] = Field(default_factory=list)
    risk_only_metrics: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)


class DataQualityRules(RulesModel):
    version: int
    min_years: float = Field(gt=0)
    max_missing_share: float = Field(ge=0, le=1)
    warn_missing_share: float = Field(ge=0, le=1)
    stale_run_days: int = Field(ge=2)
    blocking_stale_run_days: int = Field(ge=2)
    outlier_sigma: float = Field(gt=0)
    outlier_abs_return: float = Field(gt=0)
    max_stale_last_days: int = Field(ge=0)
    reference_calendars: dict[str, str]


RULE_FILES: dict[str, type[BaseModel]] = {
    "questionnaire.yaml": Questionnaire,
    "profile_rules.yaml": ProfileRules,
    "taxonomy.yaml": Taxonomy,
    "relevance_rules.yaml": RelevanceRules,
    "coherence_rules.yaml": CoherenceRules,
    "glossary.yaml": Glossary,
    "limits_texts.yaml": LimitsTexts,
    "instrument_risks.yaml": InstrumentRisks,
    "source_tiers.yaml": SourceTiers,
    "language_policy.yaml": LanguagePolicy,
    "data_quality.yaml": DataQualityRules,
}
PERSONA_MODEL = Profile
