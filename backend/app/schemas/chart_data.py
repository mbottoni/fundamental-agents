"""
The report chart payload
========================
The contract between `Orchestrator._build_chart_data()` and the Recharts
components on the report page.

This used to be a bare `dict[str, Any]` serialized to a JSON string, with its
shape mirrored by hand in `frontend/src/types/index.ts`. Nothing enforced the
mirror, and nothing failed when they drifted — the chart simply rendered empty.
Declaring it here puts the shape in the OpenAPI document, where the frontend
types can be generated from it instead of retyped.

**Every field is optional with a default.** That is deliberate. The pipeline
already tolerates partial provider data — a missing MACD leaves `{}`, an
out-of-plan endpoint leaves a section absent — and a model that rejected those
would turn today's slightly-thin report into a failed analysis. The point here
is to publish an exact schema, not to add a new way for the pipeline to fail.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _ChartModel(BaseModel):
    """
    Base for every model below.

    `json_schema_serialization_defaults_required` marks defaulted fields as
    required in the *output* schema. That is the accurate description: on the
    way out every field is present, carrying its default when the pipeline had
    nothing to put there. Without it the generated TypeScript makes every field
    optional, which pushes a `?.` onto every read in the frontend for values
    that are in fact always sent.
    """

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class PricePoint(_ChartModel):
    date: Optional[str] = None
    close: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None


class BarDataPoint(_ChartModel):
    name: str
    value: Optional[float] = None


class SentimentSlice(_ChartModel):
    name: str
    value: float = 0
    color: Optional[str] = None


class MovingAverages(_ChartModel):
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None


class BollingerBands(_ChartModel):
    upper: Optional[float] = None
    lower: Optional[float] = None
    middle: Optional[float] = None


class Macd(_ChartModel):
    # The producer calls the third field `macd_histogram`; the hand-written TS
    # interface called it `histogram` and so never matched. Nothing read it, so
    # nothing broke visibly — which is the whole argument for generating these
    # types instead of retyping them.
    macd_line: Optional[float] = None
    signal_line: Optional[float] = None
    macd_histogram: Optional[float] = None


class VolumeProfile(_ChartModel):
    avg_volume: Optional[float] = None
    relative_volume: Optional[float] = None


class Momentum(_ChartModel):
    price_momentum_1m: Optional[float] = None
    price_momentum_3m: Optional[float] = None
    price_momentum_6m: Optional[float] = None


class SupportResistance(_ChartModel):
    support: Optional[float] = None
    resistance: Optional[float] = None


class RiskSummary(_ChartModel):
    rating: str = "unknown"
    annual_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    beta: Optional[float] = None
    var_95: Optional[float] = None
    annualized_return: Optional[float] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None


class DcfSummary(_ChartModel):
    intrinsic_value: Optional[float] = None
    wacc: Optional[float] = None
    current_price: Optional[float] = None
    # Range across the WACC x terminal-growth sensitivity grid.
    value_low: Optional[float] = None
    value_high: Optional[float] = None
    net_debt: Optional[float] = None
    status: Optional[str] = None
    error: Optional[str] = None


class PeerCompany(_ChartModel):
    symbol: Optional[str] = None
    name: Optional[str] = None
    market_cap: Optional[float] = None


class PeerMetricComparison(_ChartModel):
    """
    One metric measured against the peer group.

    `premium_discount` is the company's position relative to the peer median, so
    negative means cheaper for a multiple and weaker for a margin — read it with
    `lower_is_better`.
    """

    key: Optional[str] = None
    label: Optional[str] = None
    company: Optional[float] = None
    peer_median: Optional[float] = None
    premium_discount: Optional[float] = None
    percentile: Optional[float] = None
    lower_is_better: Optional[bool] = None
    verdict: Optional[str] = None


class SectorSnapshot(_ChartModel):
    sector: Optional[str] = None
    industry: Optional[str] = None
    sector_pe: Optional[float] = None
    industry_pe: Optional[float] = None
    vs_sector_pe: Optional[float] = None
    vs_industry_pe: Optional[float] = None
    as_of: Optional[str] = None


class PeersSummary(_ChartModel):
    peer_count: int = 0
    companies: list[PeerCompany] = Field(default_factory=list)
    comparisons: list[PeerMetricComparison] = Field(default_factory=list)
    sector: SectorSnapshot = Field(default_factory=SectorSnapshot)
    relative_valuation_score: Optional[float] = None
    summary: Optional[str] = None


class EarningsSurprise(_ChartModel):
    date: Optional[str] = None
    eps_actual: Optional[float] = None
    eps_estimated: Optional[float] = None
    surprise_pct: Optional[float] = None


class EarningsSummary(_ChartModel):
    available: bool = False
    next_date: Optional[str] = None
    days_until: Optional[int] = None
    is_imminent: Optional[bool] = None
    eps_estimate: Optional[float] = None
    beat_rate: Optional[float] = None
    reports_assessed: Optional[int] = None
    recent_surprises: list[EarningsSurprise] = Field(default_factory=list)
    note: Optional[str] = None


class RecommendationFactor(_ChartModel):
    """One scored dimension of the recommendation. `score` is null when the
    factor had insufficient data."""

    key: Optional[str] = None
    label: Optional[str] = None
    weight: Optional[float] = None
    score: Optional[float] = None
    drivers: list[str] = Field(default_factory=list)


class RecommendationSummary(_ChartModel):
    call: Optional[str] = None
    composite_score: Optional[float] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    coverage: Optional[float] = None
    factors: list[RecommendationFactor] = Field(default_factory=list)


class RevenueSegment(_ChartModel):
    name: str
    value: float


class RevenueSegments(_ChartModel):
    product: list[RevenueSegment] = Field(default_factory=list)
    geographic: list[RevenueSegment] = Field(default_factory=list)


class DividendPoint(_ChartModel):
    date: str
    dividend: float


class ChartData(_ChartModel):
    """Everything the report page's charts read. See module docstring."""

    # Defaulted rather than required so that reports stored before this schema
    # existed still deserialize. A response that 500s on a legacy row is worse
    # than one with an empty ticker.
    ticker: str = ""
    company_name: str = "Unknown"
    current_price: Optional[float] = None
    price_series: list[PricePoint] = Field(default_factory=list)

    # Technical
    moving_averages: MovingAverages = Field(default_factory=MovingAverages)
    bollinger_bands: BollingerBands = Field(default_factory=BollingerBands)
    rsi: Optional[float] = None
    macd: Macd = Field(default_factory=Macd)
    atr: Optional[float] = None
    volume_profile: VolumeProfile = Field(default_factory=VolumeProfile)
    momentum: Momentum = Field(default_factory=Momentum)
    trend_signals: list[str] = Field(default_factory=list)
    support_resistance: SupportResistance = Field(default_factory=SupportResistance)

    # Fundamentals
    profitability: list[BarDataPoint] = Field(default_factory=list)
    valuation_multiples: list[BarDataPoint] = Field(default_factory=list)
    growth: list[BarDataPoint] = Field(default_factory=list)
    liquidity: dict[str, Optional[float]] = Field(default_factory=dict)
    leverage: dict[str, Optional[float]] = Field(default_factory=dict)

    # Sentiment
    sentiment: list[SentimentSlice] = Field(default_factory=list)
    sentiment_score: float = 0

    # Conclusions
    risk: RiskSummary = Field(default_factory=RiskSummary)
    dcf: DcfSummary = Field(default_factory=DcfSummary)
    peers: PeersSummary = Field(default_factory=PeersSummary)
    earnings: EarningsSummary = Field(default_factory=EarningsSummary)
    recommendation: RecommendationSummary = Field(default_factory=RecommendationSummary)

    # Optional extras — absent for companies with no segment or dividend data.
    revenue_segments: Optional[RevenueSegments] = None
    dividend_history: list[DividendPoint] = Field(default_factory=list)
