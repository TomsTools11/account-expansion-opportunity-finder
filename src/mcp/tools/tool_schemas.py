"""Input schemas for MCP tools with validation."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.models import PerformanceTier


class AnalyzeAgentInput(BaseModel):
    """Input schema for analyze_agent_account tool."""

    agent_id: str = Field(
        ...,
        description="The Close CRM ID of the agent to analyze",
        min_length=1,
        max_length=100,
    )
    min_confidence: float = Field(
        default=0.5,
        description="Minimum confidence threshold (0.0-1.0) for opportunities",
        ge=0.0,
        le=1.0,
    )
    max_opportunities: int = Field(
        default=5,
        description="Maximum number of opportunities to return",
        ge=1,
        le=20,
    )
    include_tier_progression: bool = Field(
        default=True,
        description="Whether to include tier progression opportunities",
    )

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        """Validate agent ID format."""
        v = v.strip()
        if not v:
            raise ValueError("Agent ID cannot be empty")
        return v


class BatchAnalysisInput(BaseModel):
    """Input schema for batch_expansion_analysis tool."""

    top_n: int = Field(
        default=20,
        description="Return top N opportunities across all agents",
        ge=1,
        le=100,
    )
    min_confidence: float = Field(
        default=0.5,
        description="Minimum confidence threshold (0.0-1.0) for opportunities",
        ge=0.0,
        le=1.0,
    )
    filter_tiers: Optional[list[str]] = Field(
        default=None,
        description="Filter to specific performance tiers (e.g., ['TOP_25', 'TOP_10'])",
    )
    filter_products: Optional[list[str]] = Field(
        default=None,
        description="Filter to agents with specific current products",
    )
    filter_missing_products: Optional[list[str]] = Field(
        default=None,
        description="Filter to agents missing specific products (cross-sell targets)",
    )
    min_tenure_months: Optional[int] = Field(
        default=None,
        description="Minimum agent tenure in months",
        ge=0,
    )
    max_tenure_months: Optional[int] = Field(
        default=None,
        description="Maximum agent tenure in months",
        ge=0,
    )
    min_premium_volume: Optional[float] = Field(
        default=None,
        description="Minimum annual premium volume",
        ge=0,
    )
    max_premium_volume: Optional[float] = Field(
        default=None,
        description="Maximum annual premium volume",
        ge=0,
    )
    parallel: bool = Field(
        default=True,
        description="Whether to run analysis in parallel for performance",
    )

    @field_validator("filter_tiers")
    @classmethod
    def validate_tiers(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        """Validate tier names."""
        if v is None:
            return None
        valid_tiers = {t.value for t in PerformanceTier}
        for tier in v:
            if tier not in valid_tiers:
                raise ValueError(
                    f"Invalid tier '{tier}'. Valid tiers: {sorted(valid_tiers)}"
                )
        return v


class GetBenchmarkSummaryInput(BaseModel):
    """Input schema for get_benchmark_summary tool."""

    include_tiers: bool = Field(
        default=True,
        description="Include tier benchmark details",
    )
    include_products: bool = Field(
        default=True,
        description="Include product benchmark details (CAC metrics)",
    )
    include_cross_sell: bool = Field(
        default=True,
        description="Include cross-sell pattern data",
    )
    tier_filter: Optional[str] = Field(
        default=None,
        description="Filter to a specific tier (e.g., 'TOP_25')",
    )

    @field_validator("tier_filter")
    @classmethod
    def validate_tier_filter(cls, v: Optional[str]) -> Optional[str]:
        """Validate tier filter."""
        if v is None:
            return None
        valid_tiers = {t.value for t in PerformanceTier}
        if v not in valid_tiers:
            raise ValueError(
                f"Invalid tier '{v}'. Valid tiers: {sorted(valid_tiers)}"
            )
        return v


class RefreshBenchmarksInput(BaseModel):
    """Input schema for refresh_benchmarks tool."""

    force: bool = Field(
        default=False,
        description="Force refresh even if cache is still valid",
    )
    clear_agent_cache: bool = Field(
        default=False,
        description="Also clear the agent data cache",
    )
