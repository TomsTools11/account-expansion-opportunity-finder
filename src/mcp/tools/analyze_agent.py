"""MCP tool for analyzing individual agent expansion opportunities."""

import logging
from typing import Any, Optional

from src.analysis import AnalysisEngine, create_analysis_engine
from src.integrations import CloseClient, SheetsClient
from src.models import Agent, BenchmarkData, ConfidenceLevel

from .tool_schemas import AnalyzeAgentInput

logger = logging.getLogger(__name__)


class AnalyzeAgentTool:
    """Tool for analyzing a single agent's expansion opportunities."""

    def __init__(
        self,
        close_client: CloseClient,
        sheets_client: SheetsClient,
        engine: Optional[AnalysisEngine] = None,
    ):
        """Initialize the tool.

        Args:
            close_client: Client for Close CRM API
            sheets_client: Client for Google Sheets API
            engine: Optional pre-configured analysis engine
        """
        self.close_client = close_client
        self.sheets_client = sheets_client
        self._engine = engine
        self._benchmarks: Optional[BenchmarkData] = None
        self._all_agents: Optional[list[Agent]] = None

    async def _ensure_data_loaded(self) -> None:
        """Ensure benchmark and agent data are loaded."""
        if self._benchmarks is None:
            logger.info("Loading benchmark data from Google Sheets")
            self._benchmarks = self.sheets_client.load_benchmarks()

        if self._all_agents is None:
            logger.info("Loading all agents from Close CRM")
            self._all_agents = self.close_client.fetch_all_agents()

        if self._engine is None:
            self._engine = create_analysis_engine(self._benchmarks)

    def _format_opportunity(self, opp: Any) -> dict:
        """Format an opportunity for output."""
        return {
            "rank": opp.rank,
            "type": opp.opportunity_type.value,
            "recommended_product": opp.recommended_product,
            "projected_lift": {
                "dollars": round(opp.projected_revenue_lift, 2),
                "percentage": round(opp.projected_lift_pct, 1),
            },
            "confidence": {
                "level": opp.confidence_level.value,
                "score": round(opp.confidence_score, 2),
            },
            "priority_score": round(opp.priority_score, 1),
            "message": opp.message,
            "peer_analysis": {
                "similar_agent_count": opp.similar_agent_count,
                "avg_revenue": round(opp.similar_agent_avg_revenue, 2)
                if opp.similar_agent_avg_revenue
                else None,
            },
            "readiness": {
                "indicators": opp.readiness_indicators,
                "barriers": opp.barriers,
            },
            "tier_progression": {
                "current": opp.agent_current_tier.value if opp.agent_current_tier else None,
                "target": opp.agent_target_tier.value if opp.agent_target_tier else None,
            },
        }

    def _format_result(self, result: Any, agent: Agent) -> dict:
        """Format the analysis result for output."""
        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "current_products": agent.current_products,
                "annual_premium_volume": agent.annual_premium_volume,
                "tenure_months": agent.tenure_months,
                "performance_tier": agent.performance_tier.value
                if agent.performance_tier
                else None,
            },
            "opportunities": [
                self._format_opportunity(opp) for opp in result.opportunities
            ],
            "summary": {
                "total_opportunities": len(result.opportunities),
                "total_projected_lift": sum(
                    o.projected_revenue_lift for o in result.opportunities
                ),
                "highest_confidence": max(
                    (o.confidence_score for o in result.opportunities), default=0
                ),
                "top_recommendation": result.opportunities[0].recommended_product
                if result.opportunities
                else None,
            },
            "benchmark_context": result.benchmark_context,
        }

    async def execute(self, input_data: AnalyzeAgentInput) -> dict:
        """Execute the analyze_agent_account tool.

        Args:
            input_data: Validated input parameters

        Returns:
            Analysis results with opportunities
        """
        logger.info(f"Analyzing agent: {input_data.agent_id}")

        # Ensure data is loaded
        await self._ensure_data_loaded()

        # Fetch the specific agent
        try:
            agent = self.close_client.fetch_agent(input_data.agent_id)
        except Exception as e:
            logger.error(f"Failed to fetch agent {input_data.agent_id}: {e}")
            return {
                "error": f"Could not fetch agent: {str(e)}",
                "agent_id": input_data.agent_id,
            }

        if agent is None:
            return {
                "error": f"Agent not found: {input_data.agent_id}",
                "agent_id": input_data.agent_id,
            }

        # Run analysis
        try:
            result = self._engine.analyze_single_agent(
                agent=agent,
                all_agents=self._all_agents,
                min_confidence=input_data.min_confidence,
                max_opportunities=input_data.max_opportunities,
            )
        except Exception as e:
            logger.error(f"Analysis failed for agent {input_data.agent_id}: {e}")
            return {
                "error": f"Analysis failed: {str(e)}",
                "agent_id": input_data.agent_id,
            }

        # Filter tier progression if not wanted
        if not input_data.include_tier_progression:
            from src.models import OpportunityType

            result.opportunities = [
                o
                for o in result.opportunities
                if o.opportunity_type != OpportunityType.IMPROVE_CONVERSION
            ]

        return self._format_result(result, agent)

    def invalidate_cache(self) -> None:
        """Invalidate cached data to force refresh."""
        self._benchmarks = None
        self._all_agents = None
        self._engine = None


async def analyze_agent_account(
    input_data: AnalyzeAgentInput,
    close_client: CloseClient,
    sheets_client: SheetsClient,
    engine: Optional[AnalysisEngine] = None,
) -> dict:
    """Analyze a single agent for expansion opportunities.

    This is the main entry point for the MCP tool.

    Args:
        input_data: Validated input parameters
        close_client: Client for Close CRM API
        sheets_client: Client for Google Sheets API
        engine: Optional pre-configured analysis engine

    Returns:
        Analysis results with opportunities
    """
    tool = AnalyzeAgentTool(close_client, sheets_client, engine)
    return await tool.execute(input_data)
