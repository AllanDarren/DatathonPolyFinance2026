"""Contract models v0 (CLAUDE.md section 8).

These Pydantic models are the single source of the JSON Schemas in `contracts/`.
Regenerate the schemas with `python -m tools.export_schemas` after any change, and
follow the contract-change procedure (section "Synchronisation") for breaking changes.
All percentages are fractions between 0 and 1.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "0.1.0"

RiskTolerance = Literal["low", "low_moderate", "moderate", "high"]
HorizonBucket = Literal["short", "medium", "long"]
HorizonRelevance = Literal["structural", "macro_context", "short_term_noise"]
AssetClass = Literal["equity_ca", "equity_us", "bond_etf", "equity_etf", "gold_etf", "crypto"]
Currency = Literal["CAD", "USD"]
EventType = Literal["earnings", "dividend_ex_date", "rate_decision", "cpi_release", "other"]
EvidenceKind = Literal["metric", "rule_hit", "classification", "event_study", "portfolio_calc", "news_source"]
ClaimLabel = Literal["fact", "hypothesis", "scenario"]
Severity = Literal["low", "medium", "high"]


class Contract(BaseModel):
    """Base class: unknown fields are rejected so contract drift is caught early."""

    model_config = ConfigDict(extra="forbid")


# --- Profile ---------------------------------------------------------------


class Preferences(Contract):
    avoid_controversies: bool
    excluded_sectors: list[str]
    interests: list[str]


class ProfileLimits(Contract):
    max_single_position: float = Field(ge=0, le=1)
    max_high_vol_share: float = Field(ge=0, le=1)


class Profile(Contract):
    """Investor profile computed by rules (never by the LLM)."""

    profile_id: str = Field(description="'amira' | 'mateo' | 'robert' | 'custom'")
    label: str
    source: Literal["persona_preset", "questionnaire"]
    age: int | None = None
    horizon_years: float = Field(ge=0)
    horizon_bucket: HorizonBucket = Field(description="short <= 5, medium 6 to 12, long > 12")
    risk_tolerance: RiskTolerance
    max_acceptable_loss_pct: float = Field(ge=0, le=1, description="Acceptable annual loss, fraction")
    objective: Literal["capital_preservation", "income", "balanced", "growth"]
    experience: Literal["beginner", "intermediate", "advanced"]
    preferences: Preferences
    limits: ProfileLimits
    monthly_expenses_cad: float | None
    base_currency: Literal["CAD"]
    inconsistencies: list[str]


class Persona(Contract):
    id: str
    label: str
    profile: Profile
    sample_portfolio_csv: str


# --- Portfolio -------------------------------------------------------------


class Position(Contract):
    ticker: str
    amount: float = Field(ge=0, description="Amount in CAD")
    weight: float = Field(ge=0, le=1, description="Share of the analyzed total")
    asset_class: AssetClass
    price_currency: Currency
    in_universe: bool


class Unanalyzed(Contract):
    tickers: list[str]
    weight: float = Field(ge=0, le=1, description="Share of the total amount outside the universe")


class Portfolio(Contract):
    base_currency: Literal["CAD"]
    total_amount: float = Field(ge=0)
    positions: list[Position]
    unanalyzed: Unanalyzed
    warnings: list[str]


class Consideration(Contract):
    ticker: str
    intended_weight: float = Field(gt=0, le=1, description="Target portfolio share after the addition")


# --- News & events ---------------------------------------------------------


class NewsClassification(Contract):
    category: str = Field(description="Category id from rules/taxonomy.yaml")
    horizon_relevance: HorizonRelevance = Field(description="Comes from the taxonomy, not the model")
    controversy: bool
    controversy_type: str | None
    confidence: float = Field(ge=0, le=1)
    model_id: str
    prompt_version: str


class NewsRecord(Contract):
    id: str
    title: str
    source: str
    url: str
    published_at: str = Field(description="ISO 8601")
    snippet: str | None = Field(default=None, max_length=300)
    tickers: list[str]
    is_synthetic: bool
    retrieved_at: str
    classification: NewsClassification | None = None


class Event(Contract):
    id: str
    type: EventType
    scope: Literal["ticker", "macro"]
    tickers: list[str]
    date: str = Field(description="YYYY-MM-DD")
    title: str
    is_estimated: bool
    source: str
    retrieved_at: str


# --- Explainability --------------------------------------------------------


class Evidence(Contract):
    id: str = Field(pattern=r"^ev_[0-9a-z_]+$", description="e.g. 'ev_001'")
    kind: EvidenceKind
    statement: str = Field(description="Short factual sentence")
    value: float | str | None
    unit: str | None
    as_of: str
    inputs: dict[str, Any]
    source: str = Field(description="File, snapshot or URL")
    computed_by: str = Field(description="e.g. core.metrics.max_drawdown")


class Claim(Contract):
    text: str = Field(description="Rendered text: the code replaced every {{ev_id}} marker")
    label: ClaimLabel
    evidence_ids: list[str]
    verified: Literal["supported", "unsupported", "not_checked"]


class Guardian(Contract):
    status: Literal["passed", "flagged", "not_run"]
    flags: list[str]


class Explanation(Contract):
    summary: str
    claims: list[Claim]
    generated_by: Literal["bedrock", "template"]
    guardian: Guardian


class RuleHit(Contract):
    rule_id: str
    text: str
    delta: float | None = None
    observed: float | None = None
    limit: float | None = None
    severity: Severity | None = None


class PastEvent(Contract):
    date: str
    return_: float = Field(alias="return")

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HistoricalContext(Contract):
    event_type: EventType
    asset: str
    window: str = Field(description="e.g. day before to +5 trading days")
    n_events: int = Field(ge=0)
    median_return: float
    p10: float
    p90: float
    share_positive: float = Field(ge=0, le=1)
    events: list[PastEvent]
    caveats: list[str] = Field(min_length=1, description="Mandatory: sample, overlap, survivorship, not a forecast")
    evidence_id: str


class CoherenceMetrics(Contract):
    annualized_vol: float
    max_drawdown: float
    worst_calendar_year_return: float
    position_weight_after: float


class CoherenceResult(Contract):
    verdict: Literal["coherent", "tension", "incoherent"]
    rule_hits: list[RuleHit]
    metrics: CoherenceMetrics
    explanation: Explanation


# --- Feed ------------------------------------------------------------------


class Relevance(Contract):
    score: float = Field(ge=0)
    level: Literal["high", "medium", "low"]
    shown: bool
    position_weight: float = Field(ge=0, le=1)
    rule_hits: list[RuleHit]


class FeedItem(Contract):
    news_id: str
    title: str
    url: str
    source: str
    published_at: str
    tickers: list[str]
    is_synthetic: bool
    category: str
    horizon_relevance: HorizonRelevance
    relevance: Relevance
    explanation: Explanation
    historical_context: HistoricalContext | None


class PortfolioSummary(Contract):
    top_positions: list[Position]
    asset_class_weights: dict[str, float]
    high_vol_share: float = Field(ge=0, le=1)
    top3_concentration: float = Field(ge=0, le=1)


class HiddenReason(Contract):
    reason: str
    count: int = Field(ge=0)


class Hidden(Contract):
    count: int = Field(ge=0)
    by_reason: list[HiddenReason]


class FeedResponse(Contract):
    generated_at: str
    data_as_of: str
    news_as_of: str
    profile: Profile
    portfolio_summary: PortfolioSummary
    items: list[FeedItem]
    hidden: Hidden
    coherence: CoherenceResult | None = Field(description="Present only if a consideration was given")
    events: list[Event]
    evidence: dict[str, Evidence] = Field(description="Every cited evidence, by id")
    disclaimers: list[str]
    limits: list[str]


# --- Requests & errors -----------------------------------------------------


class ProfileRequest(Contract):
    answers: dict[str, str]


class PortfolioParseRequest(Contract):
    csv: str


class FeedRequest(Contract):
    profile: Profile
    portfolio: Portfolio
    consideration: Consideration | None = None


class ErrorBody(Contract):
    code: str = Field(description="e.g. INVALID_CSV, UNKNOWN_TICKER, LLM_UNAVAILABLE")
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(Contract):
    error: ErrorBody


class Health(Contract):
    status: Literal["ok", "degraded"]
    version: str
    llm_provider: Literal["mock", "bedrock"]


# Top-level contracts: one schema file each in contracts/.
TOP_LEVEL: tuple[type[BaseModel], ...] = (
    Profile,
    Persona,
    Position,
    Portfolio,
    Consideration,
    NewsRecord,
    Event,
    Evidence,
    Claim,
    Explanation,
    RuleHit,
    HistoricalContext,
    CoherenceResult,
    FeedItem,
    FeedResponse,
    ProfileRequest,
    PortfolioParseRequest,
    FeedRequest,
    ErrorResponse,
    Health,
)
