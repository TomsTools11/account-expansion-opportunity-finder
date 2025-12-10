"""Main analysis engine orchestrating similarity, projections, and scoring."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

from src.models import (
    Agent,
    AnalysisFilters,
    AnalysisResult,
    BatchAnalysisResult,
    BenchmarkData,
    ConfidenceLevel,
    ExpansionOpportunity,
    OpportunityType,
    PerformanceTier,
)

from .projections import (
    LiftProjection,
    estimate_tier_progression_lift,
    identify_product_opportunities,
)
from .scoring import (
    ReadinessAssessment,
    assess_readiness,
    generate_opportunity_message,
    rank_opportunities,
    score_opportunity,
)
from .similarity import (
    batch_calculate_vectors,
    calculate_peer_group_stats,
    find_similar_agents,
)

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Main engine for analyzing agent expansion opportunities.

    Orchestrates the analysis pipeline:
    1. Find similar agents (peer group)
    2. Project revenue lift for missing products
    3. Assess agent readiness
    4. Score and rank opportunities
    """

    def __init__(
        self,
        benchmarks: BenchmarkData,
        min_confidence: float = 0.5,
        min_similar_agents: int = 10,
        max_opportunities: int = 5,
    ):
        """Initialize the analysis engine.

        Args:
            benchmarks: Benchmark data for comparisons
            min_confidence: Minimum confidence threshold for opportunities
            min_similar_agents: Minimum peer group size for projections
            max_opportunities: Maximum opportunities to return per agent
        """
        self.benchmarks = benchmarks
        self.min_confidence = min_confidence
        self.min_similar_agents = min_similar_agents
        self.max_opportunities = max_opportunities

        # Cache for batch operations
        self._agent_vectors: dict[str, any] = {}
        self._agents_by_id: dict[str, Agent] = {}

    def analyze_single_agent(
        self,
        agent: Agent,
        all_agents: list[Agent],
        min_confidence: Optional[float] = None,
        max_opportunities: Optional[int] = None,
    ) -> AnalysisResult:
        """Analyze a single agent for expansion opportunities.

        Args:
            agent: Agent to analyze
            all_agents: Pool of agents for peer comparison
            min_confidence: Override default minimum confidence
            max_opportunities: Override default max opportunities

        Returns:
            AnalysisResult with opportunities and context
        """
        min_conf = min_confidence if min_confidence is not None else self.min_confidence
        max_opps = max_opportunities if max_opportunities is not None else self.max_opportunities

        logger.info(f"Analyzing agent {agent.id}: {agent.name}")

        # Step 1: Assess agent readiness
        readiness = assess_readiness(agent, self.benchmarks)
        logger.debug(f"Agent readiness score: {readiness.score:.2f}")

        # Step 2: Find similar agents
        similar = find_similar_agents(
            target=agent,
            all_agents=all_agents,
            top_k=100,
            min_similarity=0.5,
        )
        peer_stats = calculate_peer_group_stats(similar)
        logger.debug(f"Found {len(similar)} similar agents")

        # Step 3: Identify product opportunities
        projections = identify_product_opportunities(
            target_agent=agent,
            all_agents=all_agents,
            benchmarks=self.benchmarks,
            agent_readiness=readiness.score,
            min_confidence=min_conf,
        )
        logger.debug(f"Found {len(projections)} product opportunities")

        # Step 4: Rank opportunities
        ranked = rank_opportunities(
            projections=projections,
            agent=agent,
            readiness=readiness,
            benchmarks=self.benchmarks,
            top_n=max_opps,
        )

        # Step 5: Convert to ExpansionOpportunity objects
        opportunities = []
        for proj, score, rank in ranked:
            message = generate_opportunity_message(proj, agent, readiness, score)

            opp = ExpansionOpportunity(
                agent_id=agent.id,
                agent_name=agent.name,
                opportunity_type=OpportunityType.ADD_PRODUCT,
                message=message,
                recommended_product=proj.product,
                projected_revenue_lift=proj.projected_lift_dollars,
                projected_lift_pct=proj.projected_lift_pct,
                confidence_level=proj.confidence_level,
                confidence_score=proj.confidence_score,
                priority_score=score,
                rank=rank,
                similar_agent_count=proj.similar_agent_count,
                similar_agent_avg_revenue=proj.similar_agent_avg_revenue,
                agent_current_tier=agent.performance_tier or PerformanceTier.AVERAGE,
                agent_target_tier=self._determine_target_tier(agent),
                readiness_indicators=readiness.indicators,
                barriers=readiness.barriers,
            )
            opportunities.append(opp)

        # Build benchmark context
        benchmark_context = {
            "current_tier": (agent.performance_tier or PerformanceTier.AVERAGE).value,
            "peer_group_size": peer_stats["count"],
            "peer_avg_revenue": peer_stats["avg_revenue"],
            "peer_avg_similarity": peer_stats["avg_similarity"],
            "readiness_score": readiness.score,
            "readiness_recommendation": readiness.recommendation,
        }

        # Add tier progression opportunity if applicable
        tier_opp = self._create_tier_progression_opportunity(agent, readiness)
        if tier_opp and tier_opp.priority_score >= score * 0.8:  # Only if competitive
            opportunities.append(tier_opp)
            opportunities.sort(key=lambda o: o.priority_score, reverse=True)
            # Re-rank after adding
            for i, opp in enumerate(opportunities):
                opp.rank = i + 1
            opportunities = opportunities[:max_opps]

        logger.info(f"Analysis complete: {len(opportunities)} opportunities for {agent.name}")

        return AnalysisResult(
            agent=agent,
            opportunities=opportunities,
            benchmark_context=benchmark_context,
        )

    def analyze_batch(
        self,
        agents: list[Agent],
        filters: Optional[AnalysisFilters] = None,
        top_n: int = 20,
        parallel: bool = True,
        max_workers: int = 4,
    ) -> BatchAnalysisResult:
        """Analyze multiple agents and return top opportunities.

        Args:
            agents: List of agents to analyze
            filters: Optional filters to narrow analysis
            top_n: Return top N opportunities across all agents
            parallel: Whether to run analysis in parallel
            max_workers: Number of parallel workers

        Returns:
            BatchAnalysisResult with aggregated results
        """
        logger.info(f"Starting batch analysis of {len(agents)} agents")

        # Apply filters if provided
        if filters:
            filtered_agents = [a for a in agents if filters.matches(a)]
            logger.info(f"Filtered to {len(filtered_agents)} agents")
        else:
            filtered_agents = agents

        if not filtered_agents:
            return BatchAnalysisResult(
                total_agents_analyzed=0,
                total_opportunities_found=0,
                top_opportunities=[],
                summary_stats={},
            )

        # Pre-calculate vectors for efficiency
        self._agent_vectors = batch_calculate_vectors(filtered_agents)
        self._agents_by_id = {a.id: a for a in filtered_agents}

        # Run analysis
        all_opportunities: list[ExpansionOpportunity] = []

        if parallel and len(filtered_agents) > 1:
            all_opportunities = self._analyze_parallel(
                filtered_agents, max_workers
            )
        else:
            all_opportunities = self._analyze_sequential(filtered_agents)

        # Sort all opportunities by priority score
        all_opportunities.sort(key=lambda o: o.priority_score, reverse=True)

        # Take top N
        top_opportunities = all_opportunities[:top_n]

        # Re-rank the top opportunities
        for i, opp in enumerate(top_opportunities):
            opp.rank = i + 1

        # Calculate summary statistics
        summary_stats = self._calculate_summary_stats(
            all_opportunities, filtered_agents
        )

        logger.info(
            f"Batch analysis complete: {len(all_opportunities)} total opportunities, "
            f"returning top {len(top_opportunities)}"
        )

        return BatchAnalysisResult(
            total_agents_analyzed=len(filtered_agents),
            total_opportunities_found=len(all_opportunities),
            top_opportunities=top_opportunities,
            summary_stats=summary_stats,
        )

    def _analyze_sequential(self, agents: list[Agent]) -> list[ExpansionOpportunity]:
        """Run analysis sequentially."""
        all_opportunities: list[ExpansionOpportunity] = []

        for agent in agents:
            try:
                result = self.analyze_single_agent(agent, agents)
                all_opportunities.extend(result.opportunities)
            except Exception as e:
                logger.warning(f"Failed to analyze agent {agent.id}: {e}")
                continue

        return all_opportunities

    def _analyze_parallel(
        self, agents: list[Agent], max_workers: int
    ) -> list[ExpansionOpportunity]:
        """Run analysis in parallel using thread pool."""
        all_opportunities: list[ExpansionOpportunity] = []

        def analyze_one(agent: Agent) -> list[ExpansionOpportunity]:
            try:
                result = self.analyze_single_agent(agent, agents)
                return result.opportunities
            except Exception as e:
                logger.warning(f"Failed to analyze agent {agent.id}: {e}")
                return []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(analyze_one, agent) for agent in agents]
            for future in futures:
                opportunities = future.result()
                all_opportunities.extend(opportunities)

        return all_opportunities

    def _determine_target_tier(self, agent: Agent) -> Optional[PerformanceTier]:
        """Determine the target tier for an agent."""
        current = agent.performance_tier or PerformanceTier.AVERAGE

        progression = {
            PerformanceTier.BOTTOM_10: PerformanceTier.BELOW_AVERAGE,
            PerformanceTier.BELOW_AVERAGE: PerformanceTier.AVERAGE,
            PerformanceTier.AVERAGE: PerformanceTier.TOP_25,
            PerformanceTier.TOP_25: PerformanceTier.TOP_10,
            PerformanceTier.TOP_10: PerformanceTier.TOP_10,
        }

        return progression.get(current)

    def _create_tier_progression_opportunity(
        self, agent: Agent, readiness: ReadinessAssessment
    ) -> Optional[ExpansionOpportunity]:
        """Create an opportunity for tier progression improvement."""
        tier_info = estimate_tier_progression_lift(agent, self.benchmarks)
        if not tier_info:
            return None

        target_tier, lift_dollars, lift_pct = tier_info

        # Calculate confidence based on readiness and current position
        confidence = readiness.score * 0.7  # Lower confidence for tier progression
        if confidence < self.min_confidence:
            return None

        message = (
            f"By improving key metrics (contact rate, close rate), agent could progress "
            f"from {(agent.performance_tier or PerformanceTier.AVERAGE).value} to {target_tier.value}, "
            f"potentially adding ${lift_dollars:,.0f} ({lift_pct:.0f}% lift) in annual premium."
        )

        # Score this opportunity
        mock_projection = LiftProjection(
            product="Performance Improvement",
            projected_lift_dollars=lift_dollars,
            projected_lift_pct=lift_pct,
            confidence_score=confidence,
            confidence_level=ConfidenceLevel.from_score(confidence),
            similar_agent_count=0,
            similar_agent_avg_revenue=0,
            median_lift_from_peers=0,
            adoption_rate=0.5,
            data_source="benchmark",
        )

        priority_score = score_opportunity(
            mock_projection, agent, readiness, self.benchmarks
        )

        return ExpansionOpportunity(
            agent_id=agent.id,
            agent_name=agent.name,
            opportunity_type=OpportunityType.IMPROVE_CONVERSION,
            message=message,
            recommended_product=None,
            projected_revenue_lift=lift_dollars,
            projected_lift_pct=lift_pct,
            confidence_level=ConfidenceLevel.from_score(confidence),
            confidence_score=confidence,
            priority_score=priority_score,
            rank=None,  # Will be set later
            similar_agent_count=0,
            similar_agent_avg_revenue=0,
            agent_current_tier=agent.performance_tier or PerformanceTier.AVERAGE,
            agent_target_tier=target_tier,
            readiness_indicators=readiness.indicators,
            barriers=readiness.barriers,
        )

    def _calculate_summary_stats(
        self,
        opportunities: list[ExpansionOpportunity],
        agents: list[Agent],
    ) -> dict:
        """Calculate summary statistics for batch analysis."""
        if not opportunities:
            return {
                "total_projected_lift": 0.0,
                "avg_confidence_score": 0.0,
                "avg_priority_score": 0.0,
                "high_priority_count": 0,
                "medium_priority_count": 0,
                "low_priority_count": 0,
                "most_common_product": None,
                "agents_with_opportunities": 0,
            }

        # Calculate totals
        total_lift = sum(o.projected_revenue_lift for o in opportunities)
        avg_confidence = sum(o.confidence_score for o in opportunities) / len(opportunities)
        avg_priority = sum(o.priority_score for o in opportunities) / len(opportunities)

        # Count by priority level
        high_count = sum(1 for o in opportunities if o.priority_score >= 75)
        medium_count = sum(1 for o in opportunities if 60 <= o.priority_score < 75)
        low_count = sum(1 for o in opportunities if o.priority_score < 60)

        # Find most common product recommendation
        product_counts: dict[str, int] = {}
        for opp in opportunities:
            if opp.recommended_product:
                product_counts[opp.recommended_product] = (
                    product_counts.get(opp.recommended_product, 0) + 1
                )
        most_common = max(product_counts, key=product_counts.get) if product_counts else None

        # Count unique agents with opportunities
        agents_with_opps = len(set(o.agent_id for o in opportunities))

        return {
            "total_projected_lift": total_lift,
            "avg_confidence_score": avg_confidence,
            "avg_priority_score": avg_priority,
            "high_priority_count": high_count,
            "medium_priority_count": medium_count,
            "low_priority_count": low_count,
            "most_common_product": most_common,
            "agents_with_opportunities": agents_with_opps,
            "agents_analyzed": len(agents),
            "opportunities_per_agent": len(opportunities) / len(agents) if agents else 0,
        }


def create_analysis_engine(
    benchmarks: BenchmarkData,
    min_confidence: float = 0.5,
    min_similar_agents: int = 10,
    max_opportunities: int = 5,
) -> AnalysisEngine:
    """Factory function to create an analysis engine.

    Args:
        benchmarks: Benchmark data
        min_confidence: Minimum confidence threshold
        min_similar_agents: Minimum peer group size
        max_opportunities: Maximum opportunities per agent

    Returns:
        Configured AnalysisEngine instance
    """
    return AnalysisEngine(
        benchmarks=benchmarks,
        min_confidence=min_confidence,
        min_similar_agents=min_similar_agents,
        max_opportunities=max_opportunities,
    )
