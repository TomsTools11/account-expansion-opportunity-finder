"""Revenue lift projections based on peer group analysis."""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.models import Agent, BenchmarkData, ConfidenceLevel, PerformanceTier

from .similarity import (
    calculate_peer_group_stats,
    find_agents_with_product,
    find_agents_without_product,
)

logger = logging.getLogger(__name__)


@dataclass
class LiftProjection:
    """Result of a revenue lift projection."""

    product: str
    projected_lift_dollars: float
    projected_lift_pct: float
    confidence_score: float
    confidence_level: ConfidenceLevel
    similar_agent_count: int
    similar_agent_avg_revenue: float
    median_lift_from_peers: float
    adoption_rate: float
    data_source: str  # "peer_analysis" or "benchmark"


def calculate_confidence_score(
    sample_size: int,
    similarity_avg: float,
    pattern_adoption_rate: float,
    agent_readiness: float,
) -> float:
    """Calculate weighted confidence score.

    Args:
        sample_size: Number of similar agents found
        similarity_avg: Average similarity score of peer group
        pattern_adoption_rate: How common this cross-sell pattern is (0-1)
        agent_readiness: Agent's readiness score (0-1)

    Returns:
        Confidence score between 0 and 1
    """
    # Sample size factor (diminishing returns after 50)
    size_factor = min(sample_size / 50.0, 1.0)

    # Combine factors with weights
    confidence = (
        size_factor * 0.30 +
        similarity_avg * 0.30 +
        pattern_adoption_rate * 0.20 +
        agent_readiness * 0.20
    )

    return min(confidence, 1.0)


def project_revenue_lift(
    target_agent: Agent,
    all_agents: list[Agent],
    product_to_add: str,
    benchmarks: BenchmarkData,
    agent_readiness: float = 0.5,
    min_similar_agents: int = 5,
) -> Optional[LiftProjection]:
    """Project revenue lift if agent adds a specific product.

    Uses peer group analysis to estimate lift, falling back to
    benchmark data if insufficient peers are found.

    Args:
        target_agent: Agent to project lift for
        all_agents: Pool of agents for peer comparison
        product_to_add: Product being recommended
        benchmarks: Benchmark data with cross-sell patterns
        agent_readiness: Pre-calculated readiness score (0-1)
        min_similar_agents: Minimum peers required for peer-based projection

    Returns:
        LiftProjection with projected revenue increase, or None if cannot project
    """
    # Skip if agent already has this product
    if product_to_add in target_agent.current_products:
        logger.debug(f"Agent {target_agent.id} already has {product_to_add}")
        return None

    # Find similar agents who have the target product
    agents_with_product = find_agents_with_product(
        target=target_agent,
        all_agents=all_agents,
        product=product_to_add,
        top_k=100,
        min_similarity=0.5,
    )

    # Find similar agents who don't have the product (comparison group)
    agents_without_product = find_agents_without_product(
        target=target_agent,
        all_agents=all_agents,
        product=product_to_add,
        top_k=100,
        min_similarity=0.5,
    )

    # Try peer-based projection first
    if len(agents_with_product) >= min_similar_agents:
        return _project_from_peers(
            target_agent=target_agent,
            product=product_to_add,
            agents_with_product=agents_with_product,
            agents_without_product=agents_without_product,
            benchmarks=benchmarks,
            agent_readiness=agent_readiness,
        )

    # Fall back to benchmark-based projection
    return _project_from_benchmarks(
        target_agent=target_agent,
        product=product_to_add,
        agents_with_product=agents_with_product,
        benchmarks=benchmarks,
        agent_readiness=agent_readiness,
    )


def _project_from_peers(
    target_agent: Agent,
    product: str,
    agents_with_product: list[tuple[Agent, float]],
    agents_without_product: list[tuple[Agent, float]],
    benchmarks: BenchmarkData,
    agent_readiness: float,
) -> LiftProjection:
    """Project lift based on peer group analysis.

    Compares revenue of similar agents with vs without the product.
    """
    # Calculate stats for each group
    with_stats = calculate_peer_group_stats(agents_with_product)
    without_stats = calculate_peer_group_stats(agents_without_product)

    # Calculate lift percentage
    if without_stats["median_revenue"] > 0:
        lift_pct = (
            (with_stats["median_revenue"] - without_stats["median_revenue"])
            / without_stats["median_revenue"]
        ) * 100
    elif with_stats["median_revenue"] > 0:
        # If no comparison group, use benchmark patterns
        pattern = benchmarks.get_cross_sell_pattern(
            target_agent.primary_product or "", product
        )
        lift_pct = pattern.avg_revenue_lift_pct if pattern else 25.0
    else:
        lift_pct = 25.0  # Conservative default

    # Cap at reasonable range
    lift_pct = max(min(lift_pct, 100.0), 5.0)

    # Calculate dollar lift
    projected_lift_dollars = target_agent.annual_premium_volume * (lift_pct / 100.0)

    # Calculate adoption rate (what % of similar agents have this product)
    total_similar = len(agents_with_product) + len(agents_without_product)
    adoption_rate = len(agents_with_product) / total_similar if total_similar > 0 else 0.5

    # Calculate confidence
    confidence_score = calculate_confidence_score(
        sample_size=len(agents_with_product),
        similarity_avg=with_stats["avg_similarity"],
        pattern_adoption_rate=adoption_rate,
        agent_readiness=agent_readiness,
    )

    confidence_level = ConfidenceLevel.from_score(confidence_score)

    return LiftProjection(
        product=product,
        projected_lift_dollars=projected_lift_dollars,
        projected_lift_pct=lift_pct,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        similar_agent_count=len(agents_with_product),
        similar_agent_avg_revenue=with_stats["avg_revenue"],
        median_lift_from_peers=with_stats["median_revenue"] - without_stats["median_revenue"],
        adoption_rate=adoption_rate,
        data_source="peer_analysis",
    )


def _project_from_benchmarks(
    target_agent: Agent,
    product: str,
    agents_with_product: list[tuple[Agent, float]],
    benchmarks: BenchmarkData,
    agent_readiness: float,
) -> Optional[LiftProjection]:
    """Project lift based on benchmark data when insufficient peers.

    Uses cross-sell patterns from benchmark data.
    """
    # Look up cross-sell pattern
    primary_product = target_agent.primary_product
    pattern = None

    if primary_product:
        pattern = benchmarks.get_cross_sell_pattern(primary_product, product)

    if pattern:
        lift_pct = pattern.avg_revenue_lift_pct
        adoption_rate = pattern.adoption_rate
    else:
        # Use conservative defaults if no pattern exists
        lift_pct = 20.0
        adoption_rate = 0.3

    # Calculate dollar lift
    projected_lift_dollars = target_agent.annual_premium_volume * (lift_pct / 100.0)

    # Calculate stats for any peers we did find
    peer_stats = calculate_peer_group_stats(agents_with_product)

    # Lower confidence since using benchmarks instead of peers
    confidence_score = calculate_confidence_score(
        sample_size=len(agents_with_product),
        similarity_avg=peer_stats["avg_similarity"] if agents_with_product else 0.5,
        pattern_adoption_rate=adoption_rate,
        agent_readiness=agent_readiness,
    )

    # Reduce confidence since we're using benchmarks
    confidence_score = confidence_score * 0.8
    confidence_level = ConfidenceLevel.from_score(confidence_score)

    return LiftProjection(
        product=product,
        projected_lift_dollars=projected_lift_dollars,
        projected_lift_pct=lift_pct,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        similar_agent_count=len(agents_with_product),
        similar_agent_avg_revenue=peer_stats["avg_revenue"],
        median_lift_from_peers=0.0,  # No peer comparison
        adoption_rate=adoption_rate,
        data_source="benchmark",
    )


def identify_product_opportunities(
    target_agent: Agent,
    all_agents: list[Agent],
    benchmarks: BenchmarkData,
    agent_readiness: float = 0.5,
    min_confidence: float = 0.3,
) -> list[LiftProjection]:
    """Identify all product addition opportunities for an agent.

    Args:
        target_agent: Agent to analyze
        all_agents: Pool of agents for peer comparison
        benchmarks: Benchmark data
        agent_readiness: Pre-calculated readiness score
        min_confidence: Minimum confidence to include opportunity

    Returns:
        List of LiftProjections for products agent doesn't have, sorted by lift
    """
    opportunities = []

    # Get all products the agent doesn't have
    current_products = set(target_agent.current_products)
    all_products = set(p.product for p in benchmarks.products)

    # Also consider standard product types
    from src.models import ProductType
    all_products.update(ProductType.values())

    missing_products = all_products - current_products

    for product in missing_products:
        projection = project_revenue_lift(
            target_agent=target_agent,
            all_agents=all_agents,
            product_to_add=product,
            benchmarks=benchmarks,
            agent_readiness=agent_readiness,
        )

        if projection and projection.confidence_score >= min_confidence:
            opportunities.append(projection)

    # Sort by projected lift (descending)
    opportunities.sort(key=lambda p: p.projected_lift_dollars, reverse=True)

    return opportunities


def estimate_tier_progression_lift(
    target_agent: Agent,
    benchmarks: BenchmarkData,
) -> Optional[tuple[PerformanceTier, float, float]]:
    """Estimate revenue lift from moving to next performance tier.

    Args:
        target_agent: Agent to analyze
        benchmarks: Benchmark data with tier definitions

    Returns:
        Tuple of (target_tier, lift_dollars, lift_pct) or None
    """
    current_tier = target_agent.performance_tier
    if current_tier is None:
        current_tier = PerformanceTier.AVERAGE

    # Determine next tier
    tier_progression = {
        PerformanceTier.BOTTOM_10: PerformanceTier.BELOW_AVERAGE,
        PerformanceTier.BELOW_AVERAGE: PerformanceTier.AVERAGE,
        PerformanceTier.AVERAGE: PerformanceTier.TOP_25,
        PerformanceTier.TOP_25: PerformanceTier.TOP_10,
        PerformanceTier.TOP_10: None,  # Already at top
    }

    target_tier = tier_progression.get(current_tier)
    if target_tier is None:
        return None

    # Get tier benchmark data
    current_benchmark = benchmarks.get_tier_by_name(current_tier)
    target_benchmark = benchmarks.get_tier_by_name(target_tier)

    if not current_benchmark or not target_benchmark:
        return None

    # Estimate lift based on CAC improvement
    # Lower CAC typically correlates with higher efficiency and revenue
    current_cac_avg = (current_benchmark.cac_range[0] + current_benchmark.cac_range[1]) / 2
    target_cac_avg = (target_benchmark.cac_range[0] + target_benchmark.cac_range[1]) / 2

    # Estimate ~15-25% lift per tier based on typical patterns
    tier_lift_estimates = {
        PerformanceTier.BELOW_AVERAGE: 0.15,  # 15% lift to average
        PerformanceTier.AVERAGE: 0.20,        # 20% lift to top 25%
        PerformanceTier.TOP_25: 0.25,         # 25% lift to top 10%
    }

    lift_pct = tier_lift_estimates.get(target_tier, 0.20) * 100
    lift_dollars = target_agent.annual_premium_volume * (lift_pct / 100)

    return (target_tier, lift_dollars, lift_pct)
