"""Opportunity scoring and agent readiness assessment."""

import logging
from dataclasses import dataclass
from typing import Optional

from src.models import Agent, BenchmarkData, PerformanceTier

from .projections import LiftProjection

logger = logging.getLogger(__name__)


@dataclass
class ReadinessAssessment:
    """Result of agent readiness assessment."""

    score: float  # 0-1
    indicators: list[str]  # Positive signals
    barriers: list[str]    # Potential obstacles
    recommendation: str    # Brief recommendation


def get_tier_avg_contact_rate(
    tier: Optional[PerformanceTier],
    benchmarks: Optional[BenchmarkData] = None,
) -> float:
    """Get average contact rate for a performance tier.

    Args:
        tier: Performance tier
        benchmarks: Optional benchmark data

    Returns:
        Average contact rate for the tier
    """
    if benchmarks and tier:
        tier_data = benchmarks.get_tier_by_name(tier)
        if tier_data:
            return (tier_data.contact_rate_range[0] + tier_data.contact_rate_range[1]) / 2

    # Default averages by tier
    defaults = {
        PerformanceTier.TOP_10: 62.5,
        PerformanceTier.TOP_25: 50.0,
        PerformanceTier.AVERAGE: 37.5,
        PerformanceTier.BELOW_AVERAGE: 25.0,
        PerformanceTier.BOTTOM_10: 15.0,
    }
    return defaults.get(tier, 40.0) if tier else 40.0


def get_tier_avg_close_rate(
    tier: Optional[PerformanceTier],
    benchmarks: Optional[BenchmarkData] = None,
) -> float:
    """Get average close rate for a performance tier."""
    if benchmarks and tier:
        tier_data = benchmarks.get_tier_by_name(tier)
        if tier_data:
            return (tier_data.close_rate_range[0] + tier_data.close_rate_range[1]) / 2

    defaults = {
        PerformanceTier.TOP_10: 32.5,
        PerformanceTier.TOP_25: 21.5,
        PerformanceTier.AVERAGE: 15.0,
        PerformanceTier.BELOW_AVERAGE: 9.0,
        PerformanceTier.BOTTOM_10: 5.0,
    }
    return defaults.get(tier, 15.0) if tier else 15.0


def get_tier_avg_lead_volume(
    tier: Optional[PerformanceTier],
    benchmarks: Optional[BenchmarkData] = None,
) -> int:
    """Get average monthly lead volume for a performance tier."""
    if benchmarks and tier:
        tier_data = benchmarks.get_tier_by_name(tier)
        if tier_data:
            return (tier_data.lead_volume_range[0] + tier_data.lead_volume_range[1]) // 2

    defaults = {
        PerformanceTier.TOP_10: 225,
        PerformanceTier.TOP_25: 125,
        PerformanceTier.AVERAGE: 75,
        PerformanceTier.BELOW_AVERAGE: 37,
        PerformanceTier.BOTTOM_10: 20,
    }
    return defaults.get(tier, 75) if tier else 75


def assess_readiness(
    agent: Agent,
    benchmarks: Optional[BenchmarkData] = None,
) -> ReadinessAssessment:
    """Assess an agent's readiness to successfully expand their product offerings.

    Evaluates multiple factors to determine if an agent is ready to take
    on new products successfully.

    Args:
        agent: Agent to assess
        benchmarks: Optional benchmark data for tier comparisons

    Returns:
        ReadinessAssessment with score, indicators, and barriers
    """
    score = 0.0
    max_score = 0.0
    indicators: list[str] = []
    barriers: list[str] = []

    tier = agent.performance_tier or PerformanceTier.AVERAGE

    # Factor 1: Tenure (established relationships) - 25 points
    max_score += 25
    if agent.tenure_months >= 24:
        score += 25
        indicators.append(f"Tenure {agent.tenure_months} months (established relationships)")
    elif agent.tenure_months >= 12:
        score += 15
        indicators.append(f"Tenure {agent.tenure_months} months (growing experience)")
    elif agent.tenure_months >= 6:
        score += 5
        barriers.append(f"Limited tenure ({agent.tenure_months} months)")
    else:
        barriers.append(f"New agent ({agent.tenure_months} months tenure)")

    # Factor 2: Contact Rate (can reach clients) - 25 points
    max_score += 25
    tier_avg_contact = get_tier_avg_contact_rate(tier, benchmarks)
    if agent.contact_rate is not None:
        if agent.contact_rate >= tier_avg_contact * 1.1:  # 10% above tier avg
            score += 25
            indicators.append(
                f"Contact rate {agent.contact_rate:.0f}% (above tier average {tier_avg_contact:.0f}%)"
            )
        elif agent.contact_rate >= tier_avg_contact:
            score += 15
            indicators.append(f"Contact rate {agent.contact_rate:.0f}% (at tier average)")
        elif agent.contact_rate >= tier_avg_contact * 0.9:
            score += 5
            barriers.append(
                f"Contact rate {agent.contact_rate:.0f}% (slightly below tier average {tier_avg_contact:.0f}%)"
            )
        else:
            barriers.append(
                f"Contact rate {agent.contact_rate:.0f}% (below tier average {tier_avg_contact:.0f}%)"
            )
    else:
        score += 10  # Neutral score for missing data
        barriers.append("Contact rate data not available")

    # Factor 3: Close Rate (can convert) - 20 points
    max_score += 20
    tier_avg_close = get_tier_avg_close_rate(tier, benchmarks)
    if agent.close_rate is not None:
        if agent.close_rate >= tier_avg_close * 1.1:
            score += 20
            indicators.append(
                f"Close rate {agent.close_rate:.0f}% (above tier average {tier_avg_close:.0f}%)"
            )
        elif agent.close_rate >= tier_avg_close:
            score += 10
            indicators.append(f"Close rate {agent.close_rate:.0f}% (at tier average)")
        else:
            barriers.append(
                f"Close rate {agent.close_rate:.0f}% (below tier average {tier_avg_close:.0f}%)"
            )
    else:
        score += 7  # Neutral score for missing data
        barriers.append("Close rate data not available")

    # Factor 4: Book Size (has client base to cross-sell) - 15 points
    max_score += 15
    if agent.annual_premium_volume >= 50000:
        score += 15
        indicators.append(f"Book size ${agent.annual_premium_volume:,.0f} (solid cross-sell base)")
    elif agent.annual_premium_volume >= 25000:
        score += 10
        indicators.append(f"Book size ${agent.annual_premium_volume:,.0f} (adequate client base)")
    elif agent.annual_premium_volume >= 10000:
        score += 5
        barriers.append(f"Book size ${agent.annual_premium_volume:,.0f} (limited cross-sell base)")
    else:
        barriers.append(f"Book size ${agent.annual_premium_volume:,.0f} (small client base)")

    # Factor 5: Lead Volume Capacity - 15 points
    max_score += 15
    tier_avg_volume = get_tier_avg_lead_volume(tier, benchmarks)
    if agent.monthly_lead_volume is not None:
        if agent.monthly_lead_volume >= tier_avg_volume:
            score += 15
            indicators.append(
                f"Monthly lead volume {agent.monthly_lead_volume} (at/above tier average)"
            )
        elif agent.monthly_lead_volume >= tier_avg_volume * 0.8:
            score += 10
            indicators.append(f"Monthly lead volume {agent.monthly_lead_volume} (near tier average)")
        else:
            barriers.append(
                f"Monthly lead volume {agent.monthly_lead_volume} "
                f"(below tier average {tier_avg_volume})"
            )
    else:
        score += 5  # Neutral score for missing data
        barriers.append("Lead volume data not available")

    # Calculate final score
    final_score = score / max_score if max_score > 0 else 0.0

    # Generate recommendation
    if final_score >= 0.75:
        recommendation = "Highly ready for expansion - strong fundamentals in place"
    elif final_score >= 0.55:
        recommendation = "Moderately ready - consider expansion with support"
    elif final_score >= 0.40:
        recommendation = "Limited readiness - address barriers before expanding"
    else:
        recommendation = "Not ready - focus on improving current performance first"

    return ReadinessAssessment(
        score=final_score,
        indicators=indicators,
        barriers=barriers,
        recommendation=recommendation,
    )


def score_opportunity(
    projection: LiftProjection,
    agent: Agent,
    readiness: Optional[ReadinessAssessment] = None,
    benchmarks: Optional[BenchmarkData] = None,
) -> int:
    """Calculate priority score (0-100) for an expansion opportunity.

    Score components:
    - 50% Lift Potential: How much revenue increase is projected
    - 30% Confidence: How confident we are in the projection
    - 20% Agent Readiness: How ready the agent is to succeed

    Args:
        projection: The lift projection to score
        agent: The agent for this opportunity
        readiness: Pre-calculated readiness (calculated if not provided)
        benchmarks: Benchmark data for readiness calculation

    Returns:
        Priority score between 0 and 100
    """
    if readiness is None:
        readiness = assess_readiness(agent, benchmarks)

    # Component 1: Lift Potential (50% weight)
    # Normalize lift against agent's current revenue
    if agent.annual_premium_volume > 0:
        lift_pct = (projection.projected_lift_dollars / agent.annual_premium_volume) * 100
    else:
        lift_pct = projection.projected_lift_pct

    # Cap at 50% lift = max score for this component
    lift_score = min(lift_pct / 50.0, 1.0) * 50

    # Component 2: Confidence (30% weight)
    confidence_score = projection.confidence_score * 30

    # Component 3: Agent Readiness (20% weight)
    readiness_score = readiness.score * 20

    total_score = lift_score + confidence_score + readiness_score

    return int(round(total_score))


def get_score_interpretation(score: int) -> str:
    """Get human-readable interpretation of a priority score.

    Args:
        score: Priority score (0-100)

    Returns:
        Interpretation string
    """
    if score >= 90:
        return "Immediate action - very high confidence and impact"
    elif score >= 75:
        return "High priority - strong opportunity"
    elif score >= 60:
        return "Medium priority - good opportunity with some risk"
    elif score >= 50:
        return "Lower priority - consider after higher-ranked opportunities"
    else:
        return "Low priority - may not be worth pursuing"


def rank_opportunities(
    projections: list[LiftProjection],
    agent: Agent,
    readiness: Optional[ReadinessAssessment] = None,
    benchmarks: Optional[BenchmarkData] = None,
    top_n: Optional[int] = None,
) -> list[tuple[LiftProjection, int, int]]:
    """Rank opportunities by priority score.

    Args:
        projections: List of lift projections to rank
        agent: Agent for readiness scoring
        readiness: Pre-calculated readiness
        benchmarks: Benchmark data
        top_n: Optional limit on results

    Returns:
        List of (projection, score, rank) tuples sorted by score descending
    """
    if readiness is None:
        readiness = assess_readiness(agent, benchmarks)

    scored = []
    for proj in projections:
        score = score_opportunity(proj, agent, readiness, benchmarks)
        scored.append((proj, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Apply limit if specified
    if top_n is not None:
        scored = scored[:top_n]

    # Add ranks
    ranked = [(proj, score, rank + 1) for rank, (proj, score) in enumerate(scored)]

    return ranked


def generate_opportunity_message(
    projection: LiftProjection,
    agent: Agent,
    readiness: ReadinessAssessment,
    score: int,
) -> str:
    """Generate a human-readable message for an opportunity.

    Args:
        projection: The lift projection
        agent: The agent
        readiness: Agent readiness assessment
        score: Priority score

    Returns:
        Formatted opportunity message
    """
    # Build product context
    current_products = ", ".join(agent.current_products) if agent.current_products else "none"

    # Build message
    parts = [
        f"Agent currently sells {current_products} with ${agent.annual_premium_volume:,.0f} annual premium.",
    ]

    # Add peer comparison if available
    if projection.data_source == "peer_analysis" and projection.similar_agent_count > 0:
        parts.append(
            f"Similar agents ({projection.similar_agent_count} found) who added {projection.product} "
            f"see average {projection.projected_lift_pct:.0f}% revenue lift "
            f"(${projection.projected_lift_dollars:,.0f})."
        )
    else:
        parts.append(
            f"Based on industry benchmarks, adding {projection.product} could provide "
            f"{projection.projected_lift_pct:.0f}% revenue lift (${projection.projected_lift_dollars:,.0f})."
        )

    # Add readiness summary
    if readiness.indicators:
        top_indicators = readiness.indicators[:2]
        parts.append(
            f"Positive signals: {'; '.join(top_indicators)}."
        )

    # Add confidence
    parts.append(f"Confidence: {projection.confidence_level.value}.")

    return " ".join(parts)
