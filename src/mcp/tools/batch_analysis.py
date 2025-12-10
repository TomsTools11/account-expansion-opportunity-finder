"""MCP tool for batch analysis of agent expansion opportunities."""

import logging
from typing import Any, Optional

from src.analysis import AnalysisEngine, create_analysis_engine
from src.integrations import CloseClient, SheetsClient
from src.models import AnalysisFilters, Agent, BenchmarkData, PerformanceTier

from .tool_schemas import BatchAnalysisInput

logger = logging.getLogger(__name__)


class BatchAnalysisTool:
    """Tool for analyzing multiple agents for expansion opportunities."""

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

    def _build_filters(self, input_data: BatchAnalysisInput) -> Optional[AnalysisFilters]:
        """Build analysis filters from input data."""
        # Convert string tier names to PerformanceTier enums
        tiers = None
        if input_data.filter_tiers:
            tiers = [PerformanceTier(t) for t in input_data.filter_tiers]

        # Only create filters if any filter is specified
        has_filters = any([
            tiers,
            input_data.filter_products,
            input_data.min_tenure_months is not None,
            input_data.min_premium_volume is not None,
        ])

        if not has_filters:
            return None

        return AnalysisFilters(
            current_tiers=tiers,
            products=input_data.filter_products,
            min_tenure_months=input_data.min_tenure_months,
            min_book_size=input_data.min_premium_volume,
        )

    def _format_opportunity(self, opp: Any) -> dict:
        """Format an opportunity for output."""
        return {
            "rank": opp.rank,
            "agent": {
                "id": opp.agent_id,
                "name": opp.agent_name,
            },
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
        }

    def _format_result(self, result: Any) -> dict:
        """Format the batch analysis result for output."""
        stats = result.summary_stats

        return {
            "summary": {
                "total_agents_analyzed": result.total_agents_analyzed,
                "total_opportunities_found": result.total_opportunities_found,
                "agents_with_opportunities": stats.get("agents_with_opportunities", 0),
                "opportunities_per_agent": round(
                    stats.get("opportunities_per_agent", 0), 2
                ),
            },
            "aggregate_metrics": {
                "total_projected_lift": round(
                    stats.get("total_projected_lift", 0), 2
                ),
                "avg_confidence_score": round(
                    stats.get("avg_confidence_score", 0), 2
                ),
                "avg_priority_score": round(stats.get("avg_priority_score", 0), 1),
            },
            "priority_distribution": {
                "high_priority": stats.get("high_priority_count", 0),
                "medium_priority": stats.get("medium_priority_count", 0),
                "low_priority": stats.get("low_priority_count", 0),
            },
            "most_common_product": stats.get("most_common_product"),
            "top_opportunities": [
                self._format_opportunity(opp) for opp in result.top_opportunities
            ],
        }

    async def execute(self, input_data: BatchAnalysisInput) -> dict:
        """Execute the batch_expansion_analysis tool.

        Args:
            input_data: Validated input parameters

        Returns:
            Batch analysis results with top opportunities
        """
        logger.info("Starting batch expansion analysis")

        # Ensure data is loaded
        await self._ensure_data_loaded()

        if not self._all_agents:
            return {
                "error": "No agents found in Close CRM",
                "summary": {
                    "total_agents_analyzed": 0,
                    "total_opportunities_found": 0,
                },
            }

        # Build filters
        filters = self._build_filters(input_data)

        # Run batch analysis
        try:
            result = self._engine.analyze_batch(
                agents=self._all_agents,
                filters=filters,
                top_n=input_data.top_n,
                parallel=input_data.parallel,
            )
        except Exception as e:
            logger.error(f"Batch analysis failed: {e}")
            return {
                "error": f"Batch analysis failed: {str(e)}",
            }

        return self._format_result(result)

    def invalidate_cache(self) -> None:
        """Invalidate cached data to force refresh."""
        self._benchmarks = None
        self._all_agents = None
        self._engine = None


async def batch_expansion_analysis(
    input_data: BatchAnalysisInput,
    close_client: CloseClient,
    sheets_client: SheetsClient,
    engine: Optional[AnalysisEngine] = None,
) -> dict:
    """Analyze all agents for expansion opportunities.

    This is the main entry point for the MCP tool.

    Args:
        input_data: Validated input parameters
        close_client: Client for Close CRM API
        sheets_client: Client for Google Sheets API
        engine: Optional pre-configured analysis engine

    Returns:
        Batch analysis results with top opportunities
    """
    tool = BatchAnalysisTool(close_client, sheets_client, engine)
    return await tool.execute(input_data)
