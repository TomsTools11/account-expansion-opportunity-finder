"""Pydantic schemas for the Insurance Agent Account Expansion Analyzer."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, computed_field

from .enums import (
    AgencyType,
    ConfidenceLevel,
    OpportunityType,
    PerformanceTier,
    ProductType,
)


class Agent(BaseModel):
    """Agent profile data from Close CRM."""

    # Identity
    id: str = Field(..., description="Close CRM lead_id or contact_id")
    name: str = Field(..., description="Agent display name")
    email: Optional[str] = Field(None, description="Agent email address")
    phone: Optional[str] = Field(None, description="Agent phone number")

    # Business Profile
    current_products: list[str] = Field(
        default_factory=list, description="List of products the agent currently sells"
    )
    annual_premium_volume: float = Field(
        0.0, ge=0, description="Total book size in dollars"
    )
    tenure_months: int = Field(0, ge=0, description="Months as an agent")
    region: Optional[str] = Field(None, description="Geographic region")
    agency_type: Optional[AgencyType] = Field(None, description="Type of agency")

    # Performance Metrics
    contact_rate: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of leads contacted (0-100)"
    )
    quote_rate: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of contacts quoted (0-100)"
    )
    close_rate: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of quotes closed (0-100)"
    )
    monthly_lead_volume: Optional[int] = Field(
        None, ge=0, description="Average leads per month"
    )
    cost_per_acquisition: Optional[float] = Field(
        None, ge=0, description="CAC in dollars"
    )

    # Derived Fields
    performance_tier: Optional[PerformanceTier] = Field(
        None, description="Performance tier classification"
    )

    # Metadata
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last data update timestamp"
    )

    @field_validator("current_products", mode="before")
    @classmethod
    def validate_products(cls, v: list[str]) -> list[str]:
        """Validate that products are recognized types."""
        valid_products = ProductType.values()
        validated = []
        for product in v:
            if product in valid_products:
                validated.append(product)
        return validated

    @computed_field
    @property
    def product_vector(self) -> list[float]:
        """One-hot encoding of products for similarity calculations."""
        all_products = ProductType.values()
        return [1.0 if p in self.current_products else 0.0 for p in all_products]

    @computed_field
    @property
    def data_completeness_score(self) -> float:
        """Calculate completeness score (0-100) based on filled fields."""
        required_fields = [
            self.current_products,
            self.annual_premium_volume,
            self.tenure_months,
            self.contact_rate,
            self.quote_rate,
            self.close_rate,
            self.monthly_lead_volume,
        ]
        filled = sum(
            1
            for f in required_fields
            if f is not None and (not isinstance(f, (list, str)) or len(f) > 0)
        )
        return (filled / len(required_fields)) * 100

    @computed_field
    @property
    def primary_product(self) -> Optional[str]:
        """Return the first product in the list as primary."""
        return self.current_products[0] if self.current_products else None

    def has_minimum_data(self, threshold: float = 60.0) -> bool:
        """Check if agent has minimum required data for analysis."""
        return self.data_completeness_score >= threshold

    def get_missing_fields(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.current_products:
            missing.append("current_products")
        if not self.annual_premium_volume:
            missing.append("annual_premium_volume")
        if self.tenure_months == 0:
            missing.append("tenure_months")
        if self.contact_rate is None:
            missing.append("contact_rate")
        if self.quote_rate is None:
            missing.append("quote_rate")
        if self.close_rate is None:
            missing.append("close_rate")
        if self.monthly_lead_volume is None:
            missing.append("monthly_lead_volume")
        return missing


class BenchmarkTier(BaseModel):
    """Performance tier benchmark ranges."""

    tier_name: PerformanceTier
    contact_rate_range: tuple[float, float] = Field(
        ..., description="Min/max contact rate for tier"
    )
    quote_rate_range: tuple[float, float] = Field(
        ..., description="Min/max quote rate for tier"
    )
    close_rate_range: tuple[float, float] = Field(
        ..., description="Min/max close rate for tier"
    )
    cac_range: tuple[float, float] = Field(..., description="Min/max CAC for tier")
    lead_volume_range: tuple[int, int] = Field(
        ..., description="Min/max monthly lead volume for tier"
    )

    def agent_fits_tier(self, agent: Agent) -> bool:
        """Check if an agent's metrics fit within this tier's ranges."""
        if agent.contact_rate is not None:
            if not (
                self.contact_rate_range[0]
                <= agent.contact_rate
                <= self.contact_rate_range[1]
            ):
                return False

        if agent.close_rate is not None:
            if not (
                self.close_rate_range[0] <= agent.close_rate <= self.close_rate_range[1]
            ):
                return False

        return True


class ProductBenchmark(BaseModel):
    """Benchmark data for a specific product."""

    product: str = Field(..., description="Product name")
    organic_cac: float = Field(..., ge=0, description="Organic CAC in dollars")
    inorganic_cac: float = Field(..., ge=0, description="Inorganic CAC in dollars")
    blended_cac: float = Field(..., ge=0, description="Blended average CAC in dollars")
    avg_annual_premium: Optional[float] = Field(
        None, ge=0, description="Industry average annual premium per policy"
    )
    source: str = Field(default="Industry Data", description="Data source reference")
    penetration_by_tier: dict[str, float] = Field(
        default_factory=dict,
        description="Product penetration rate by performance tier",
    )


class CrossSellPattern(BaseModel):
    """Historical cross-sell pattern data."""

    primary_product: str = Field(..., description="The product agent currently sells")
    added_product: str = Field(..., description="The product that was added")
    avg_revenue_lift_pct: float = Field(
        ..., description="Average percentage revenue increase"
    )
    adoption_rate: float = Field(
        ..., ge=0, le=1, description="What percentage of similar agents do this"
    )
    avg_time_to_add_months: int = Field(
        ..., ge=0, description="Average months after starting to add this product"
    )
    tier: Optional[PerformanceTier] = Field(
        None, description="Which tier this pattern applies to"
    )


class ConversionRates(BaseModel):
    """Industry benchmark conversion rates."""

    search_ad_conversion: Optional[float] = Field(
        None, description="Search ad conversion rate"
    )
    display_ad_conversion: Optional[float] = Field(
        None, description="Display ad conversion rate"
    )
    landing_page_conversion_min: Optional[float] = Field(
        None, description="Landing page conversion rate minimum"
    )
    landing_page_conversion_max: Optional[float] = Field(
        None, description="Landing page conversion rate maximum"
    )
    lead_to_quote_min: Optional[float] = Field(
        None, description="Lead to quote conversion minimum"
    )
    lead_to_quote_max: Optional[float] = Field(
        None, description="Lead to quote conversion maximum"
    )
    quote_to_bind_top_performers: Optional[tuple[float, float]] = Field(
        None, description="Quote to bind rate range for top performers"
    )
    quote_to_bind_average: Optional[tuple[float, float]] = Field(
        None, description="Quote to bind rate range for average performers"
    )
    exclusive_lead_conversion_min: Optional[float] = Field(
        None, description="Exclusive lead conversion minimum"
    )
    exclusive_lead_conversion_max: Optional[float] = Field(
        None, description="Exclusive lead conversion maximum"
    )


class BenchmarkData(BaseModel):
    """Complete benchmark data container."""

    tiers: list[BenchmarkTier] = Field(
        default_factory=list, description="Performance tier definitions"
    )
    products: list[ProductBenchmark] = Field(
        default_factory=list, description="Product benchmark data"
    )
    cross_sell_patterns: list[CrossSellPattern] = Field(
        default_factory=list, description="Historical cross-sell patterns"
    )
    conversion_rates: Optional[ConversionRates] = Field(
        None, description="Industry conversion rate benchmarks"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last benchmark update timestamp"
    )
    source: str = Field(
        default="Multiple Sources", description="Primary data source"
    )

    def get_tier_by_name(self, tier_name: PerformanceTier) -> Optional[BenchmarkTier]:
        """Get benchmark tier by name."""
        for tier in self.tiers:
            if tier.tier_name == tier_name:
                return tier
        return None

    def get_product_benchmark(self, product: str) -> Optional[ProductBenchmark]:
        """Get product benchmark by name."""
        for p in self.products:
            if p.product == product:
                return p
        return None

    def get_cross_sell_pattern(
        self, primary_product: str, added_product: str
    ) -> Optional[CrossSellPattern]:
        """Get cross-sell pattern for a specific product combination."""
        for pattern in self.cross_sell_patterns:
            if (
                pattern.primary_product == primary_product
                and pattern.added_product == added_product
            ):
                return pattern
        return None

    def get_tier_avg_contact_rate(self, tier: PerformanceTier) -> float:
        """Get average contact rate for a tier."""
        tier_data = self.get_tier_by_name(tier)
        if tier_data:
            return (
                tier_data.contact_rate_range[0] + tier_data.contact_rate_range[1]
            ) / 2
        return 40.0  # Default fallback

    def get_tier_avg_close_rate(self, tier: PerformanceTier) -> float:
        """Get average close rate for a tier."""
        tier_data = self.get_tier_by_name(tier)
        if tier_data:
            return (tier_data.close_rate_range[0] + tier_data.close_rate_range[1]) / 2
        return 15.0  # Default fallback

    def get_tier_avg_lead_volume(self, tier: PerformanceTier) -> int:
        """Get average lead volume for a tier."""
        tier_data = self.get_tier_by_name(tier)
        if tier_data:
            return (
                tier_data.lead_volume_range[0] + tier_data.lead_volume_range[1]
            ) // 2
        return 75  # Default fallback


class ExpansionOpportunity(BaseModel):
    """An identified expansion opportunity for an agent."""

    # Identification
    opportunity_id: str = Field(
        default_factory=lambda: f"opp_{uuid4().hex[:8]}",
        description="Unique opportunity identifier",
    )
    agent_id: str = Field(..., description="Close CRM agent/lead ID")
    agent_name: str = Field(..., description="Agent display name")

    # Recommendation
    opportunity_type: OpportunityType = Field(..., description="Type of opportunity")
    message: str = Field(..., description="Human-readable recommendation description")
    recommended_product: Optional[str] = Field(
        None, description="Recommended product to add (if applicable)"
    )

    # Projections
    projected_revenue_lift: float = Field(
        ..., ge=0, description="Projected revenue increase in dollars"
    )
    projected_lift_pct: float = Field(
        ..., description="Projected percentage revenue increase"
    )
    confidence_level: ConfidenceLevel = Field(
        ..., description="Confidence classification"
    )
    confidence_score: float = Field(
        ..., ge=0, le=1, description="Raw confidence score (0-1)"
    )

    # Scoring
    priority_score: int = Field(
        ..., ge=0, le=100, description="Composite priority score (0-100)"
    )
    rank: Optional[int] = Field(None, ge=1, description="Ranking in batch analysis")

    # Evidence
    similar_agent_count: int = Field(
        ..., ge=0, description="Number of similar agents found"
    )
    similar_agent_avg_revenue: float = Field(
        ..., ge=0, description="Average revenue of similar agents"
    )
    agent_current_tier: PerformanceTier = Field(
        ..., description="Agent's current performance tier"
    )
    agent_target_tier: Optional[PerformanceTier] = Field(
        None, description="Target tier if opportunity is pursued"
    )

    # Readiness Signals
    readiness_indicators: list[str] = Field(
        default_factory=list, description="Positive readiness signals"
    )
    barriers: list[str] = Field(
        default_factory=list, description="Potential barriers to success"
    )

    # Metadata
    generated_at: datetime = Field(
        default_factory=datetime.utcnow, description="When this opportunity was generated"
    )
    expires_at: Optional[datetime] = Field(
        None, description="When this opportunity becomes stale"
    )

    def model_post_init(self, __context) -> None:
        """Set expiration to 30 days from generation if not set."""
        if self.expires_at is None:
            from datetime import timedelta

            self.expires_at = self.generated_at + timedelta(days=30)

    def is_expired(self) -> bool:
        """Check if this opportunity has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_high_priority(self) -> bool:
        """Check if this is a high priority opportunity (score >= 75)."""
        return self.priority_score >= 75


class AnalysisResult(BaseModel):
    """Result of analyzing a single agent."""

    agent: Agent = Field(..., description="The analyzed agent")
    opportunities: list[ExpansionOpportunity] = Field(
        default_factory=list, description="Identified opportunities"
    )
    benchmark_context: dict = Field(
        default_factory=dict, description="Tier comparison context"
    )
    analysis_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When analysis was performed"
    )


class BatchAnalysisResult(BaseModel):
    """Result of batch analysis across multiple agents."""

    total_agents_analyzed: int = Field(..., description="Number of agents processed")
    total_opportunities_found: int = Field(
        ..., description="Total opportunities identified"
    )
    top_opportunities: list[ExpansionOpportunity] = Field(
        default_factory=list, description="Top ranked opportunities"
    )
    summary_stats: dict = Field(
        default_factory=dict, description="Aggregate statistics"
    )
    analysis_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When analysis was performed"
    )


class AnalysisFilters(BaseModel):
    """Filters for batch analysis."""

    min_tenure_months: Optional[int] = Field(None, ge=0)
    min_book_size: Optional[float] = Field(None, ge=0)
    regions: Optional[list[str]] = Field(None)
    current_tiers: Optional[list[PerformanceTier]] = Field(None)
    products: Optional[list[str]] = Field(None)

    def matches(self, agent: Agent) -> bool:
        """Check if an agent matches all specified filters."""
        if self.min_tenure_months is not None:
            if agent.tenure_months < self.min_tenure_months:
                return False

        if self.min_book_size is not None:
            if agent.annual_premium_volume < self.min_book_size:
                return False

        if self.regions is not None:
            if agent.region not in self.regions:
                return False

        if self.current_tiers is not None:
            if agent.performance_tier not in self.current_tiers:
                return False

        if self.products is not None:
            if not any(p in agent.current_products for p in self.products):
                return False

        return True
