"""Unit tests for MCP tools."""

from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from src.models import (
    Agent,
    AnalysisResult,
    BatchAnalysisResult,
    BenchmarkData,
    BenchmarkTier,
    ConfidenceLevel,
    ExpansionOpportunity,
    OpportunityType,
    PerformanceTier,
    ProductBenchmark,
)
from src.mcp.tools import (
    AnalyzeAgentInput,
    BatchAnalysisInput,
    GetBenchmarkSummaryInput,
    RefreshBenchmarksInput,
)
from src.mcp.tools.analyze_agent import AnalyzeAgentTool
from src.mcp.tools.batch_analysis import BatchAnalysisTool
from src.mcp.tools.benchmarks import BenchmarkTools


@pytest.fixture
def mock_close_client():
    """Create a mock Close CRM client."""
    client = MagicMock()
    client.fetch_agent = MagicMock(return_value=Agent(
        id="agent_123",
        name="Test Agent",
        current_products=["Auto", "Home"],
        annual_premium_volume=50000,
        tenure_months=24,
        performance_tier=PerformanceTier.TOP_25,
    ))
    client.fetch_all_agents = MagicMock(return_value=[
        Agent(
            id="agent_1",
            name="Agent 1",
            current_products=["Auto"],
            annual_premium_volume=40000,
            tenure_months=18,
            performance_tier=PerformanceTier.AVERAGE,
        ),
        Agent(
            id="agent_2",
            name="Agent 2",
            current_products=["Auto", "Home"],
            annual_premium_volume=60000,
            tenure_months=30,
            performance_tier=PerformanceTier.TOP_25,
        ),
    ])
    client.clear_cache = MagicMock()
    return client


@pytest.fixture
def mock_sheets_client():
    """Create a mock Google Sheets client."""
    client = MagicMock()
    client.load_benchmarks = MagicMock(return_value=BenchmarkData(
        tiers=[
            BenchmarkTier(
                tier_name=PerformanceTier.TOP_10,
                contact_rate_range=(55.0, 70.0),
                quote_rate_range=(35.0, 50.0),
                close_rate_range=(25.0, 40.0),
                cac_range=(25.0, 60.0),
                lead_volume_range=(150, 300),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.TOP_25,
                contact_rate_range=(45.0, 55.0),
                quote_rate_range=(25.0, 35.0),
                close_rate_range=(18.0, 25.0),
                cac_range=(50.0, 90.0),
                lead_volume_range=(100, 150),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.AVERAGE,
                contact_rate_range=(30.0, 45.0),
                quote_rate_range=(15.0, 25.0),
                close_rate_range=(12.0, 18.0),
                cac_range=(80.0, 130.0),
                lead_volume_range=(50, 100),
            ),
        ],
        products=[
            ProductBenchmark(
                product="Auto",
                organic_cac=203.52,
                inorganic_cac=305.28,
                blended_cac=244.22,
            ),
            ProductBenchmark(
                product="Home",
                organic_cac=140.72,
                inorganic_cac=211.08,
                blended_cac=168.86,
            ),
        ],
        cross_sell_patterns=[],
    ))
    return client


@pytest.fixture
def mock_engine():
    """Create a mock analysis engine."""
    engine = MagicMock()
    engine.analyze_single_agent = MagicMock(return_value=AnalysisResult(
        agent=Agent(
            id="agent_123",
            name="Test Agent",
            current_products=["Auto", "Home"],
            annual_premium_volume=50000,
        ),
        opportunities=[
            ExpansionOpportunity(
                agent_id="agent_123",
                agent_name="Test Agent",
                opportunity_type=OpportunityType.ADD_PRODUCT,
                message="Add Life insurance to expand book",
                recommended_product="Life",
                projected_revenue_lift=15000,
                projected_lift_pct=30.0,
                confidence_level=ConfidenceLevel.MEDIUM,
                confidence_score=0.75,
                priority_score=72,
                rank=1,
                similar_agent_count=25,
                similar_agent_avg_revenue=60000,
                agent_current_tier=PerformanceTier.TOP_25,
                agent_target_tier=PerformanceTier.TOP_10,
                readiness_indicators=["Strong performance"],
                barriers=["New to Life products"],
            ),
        ],
        benchmark_context={
            "current_tier": "TOP_25",
            "peer_group_size": 25,
            "peer_avg_revenue": 60000,
            "peer_avg_similarity": 0.85,
            "readiness_score": 0.8,
            "readiness_recommendation": "Ready for expansion",
        },
    ))
    engine.analyze_batch = MagicMock(return_value=BatchAnalysisResult(
        total_agents_analyzed=10,
        total_opportunities_found=25,
        top_opportunities=[
            ExpansionOpportunity(
                agent_id="agent_1",
                agent_name="Agent 1",
                opportunity_type=OpportunityType.ADD_PRODUCT,
                message="Add Home insurance",
                recommended_product="Home",
                projected_revenue_lift=12000,
                projected_lift_pct=25.0,
                confidence_level=ConfidenceLevel.HIGH,
                confidence_score=0.85,
                priority_score=82,
                rank=1,
                similar_agent_count=30,
                similar_agent_avg_revenue=55000,
                agent_current_tier=PerformanceTier.AVERAGE,
                agent_target_tier=PerformanceTier.TOP_25,
                readiness_indicators=["Growing book"],
                barriers=[],
            ),
        ],
        summary_stats={
            "total_projected_lift": 180000,
            "avg_confidence_score": 0.72,
            "avg_priority_score": 68.5,
            "high_priority_count": 5,
            "medium_priority_count": 12,
            "low_priority_count": 8,
            "most_common_product": "Home",
            "agents_with_opportunities": 8,
            "opportunities_per_agent": 2.5,
        },
    ))
    return engine


class TestAnalyzeAgentTool:
    """Tests for AnalyzeAgentTool."""

    @pytest.mark.asyncio
    async def test_execute_returns_formatted_result(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test that execute returns properly formatted result."""
        tool = AnalyzeAgentTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._all_agents = []  # Pre-populate to skip loading

        input_data = AnalyzeAgentInput(agent_id="agent_123")
        result = await tool.execute(input_data)

        assert "agent" in result
        assert "opportunities" in result
        assert "summary" in result
        assert "benchmark_context" in result

    @pytest.mark.asyncio
    async def test_execute_agent_not_found(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test handling of agent not found."""
        mock_close_client.fetch_agent.return_value = None
        tool = AnalyzeAgentTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._all_agents = []

        input_data = AnalyzeAgentInput(agent_id="nonexistent")
        result = await tool.execute(input_data)

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_fetch_error(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test handling of fetch errors."""
        mock_close_client.fetch_agent.side_effect = Exception("API error")
        tool = AnalyzeAgentTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._all_agents = []

        input_data = AnalyzeAgentInput(agent_id="agent_123")
        result = await tool.execute(input_data)

        assert "error" in result
        assert "Could not fetch agent" in result["error"]

    @pytest.mark.asyncio
    async def test_opportunity_formatting(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test that opportunities are properly formatted."""
        tool = AnalyzeAgentTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._all_agents = []

        input_data = AnalyzeAgentInput(agent_id="agent_123")
        result = await tool.execute(input_data)

        opp = result["opportunities"][0]
        assert "rank" in opp
        assert "type" in opp
        assert "recommended_product" in opp
        assert "projected_lift" in opp
        assert "dollars" in opp["projected_lift"]
        assert "percentage" in opp["projected_lift"]
        assert "confidence" in opp
        assert "level" in opp["confidence"]
        assert "score" in opp["confidence"]

    def test_invalidate_cache(self, mock_close_client, mock_sheets_client, mock_engine):
        """Test cache invalidation."""
        tool = AnalyzeAgentTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._benchmarks = "something"
        tool._all_agents = []

        tool.invalidate_cache()

        assert tool._benchmarks is None
        assert tool._all_agents is None
        assert tool._engine is None


class TestBatchAnalysisTool:
    """Tests for BatchAnalysisTool."""

    @pytest.mark.asyncio
    async def test_execute_returns_formatted_result(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test that execute returns properly formatted result."""
        tool = BatchAnalysisTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._all_agents = [Agent(id="a", name="A")]

        input_data = BatchAnalysisInput()
        result = await tool.execute(input_data)

        assert "summary" in result
        assert "aggregate_metrics" in result
        assert "priority_distribution" in result
        assert "top_opportunities" in result

    @pytest.mark.asyncio
    async def test_execute_no_agents(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test handling when no agents are found."""
        mock_close_client.fetch_all_agents.return_value = []
        tool = BatchAnalysisTool(mock_close_client, mock_sheets_client, mock_engine)

        input_data = BatchAnalysisInput()
        result = await tool.execute(input_data)

        assert "error" in result
        assert "No agents found" in result["error"]

    @pytest.mark.asyncio
    async def test_filter_building(
        self, mock_close_client, mock_sheets_client, mock_engine
    ):
        """Test that filters are built correctly."""
        tool = BatchAnalysisTool(mock_close_client, mock_sheets_client, mock_engine)
        tool._all_agents = [Agent(id="a", name="A")]

        input_data = BatchAnalysisInput(
            filter_tiers=["Top 25%"],
            min_tenure_months=12,
            min_premium_volume=25000,
        )

        filters = tool._build_filters(input_data)

        assert filters is not None
        assert filters.current_tiers == [PerformanceTier.TOP_25]
        assert filters.min_tenure_months == 12
        assert filters.min_book_size == 25000

    def test_build_filters_returns_none_when_empty(
        self, mock_close_client, mock_sheets_client
    ):
        """Test that build_filters returns None when no filters specified."""
        tool = BatchAnalysisTool(mock_close_client, mock_sheets_client)
        input_data = BatchAnalysisInput()

        filters = tool._build_filters(input_data)

        assert filters is None


class TestBenchmarkTools:
    """Tests for BenchmarkTools."""

    @pytest.mark.asyncio
    async def test_get_summary_returns_formatted_result(
        self, mock_sheets_client
    ):
        """Test that get_summary returns properly formatted result."""
        tools = BenchmarkTools(mock_sheets_client)

        input_data = GetBenchmarkSummaryInput()
        result = await tools.get_summary(input_data)

        assert "tier_benchmarks" in result
        assert "product_benchmarks" in result
        assert "last_refresh" in result

    @pytest.mark.asyncio
    async def test_get_summary_with_tier_filter(
        self, mock_sheets_client
    ):
        """Test filtering by tier."""
        tools = BenchmarkTools(mock_sheets_client)

        input_data = GetBenchmarkSummaryInput(tier_filter="Top 25%")
        result = await tools.get_summary(input_data)

        # Should only have TOP_25 tier
        assert len(result["tier_benchmarks"]) == 1
        assert result["tier_benchmarks"][0]["tier"] == "Top 25%"

    @pytest.mark.asyncio
    async def test_get_summary_selective_sections(
        self, mock_sheets_client
    ):
        """Test selective section inclusion."""
        tools = BenchmarkTools(mock_sheets_client)

        input_data = GetBenchmarkSummaryInput(
            include_tiers=True,
            include_products=False,
            include_cross_sell=False,
        )
        result = await tools.get_summary(input_data)

        assert "tier_benchmarks" in result
        assert "product_benchmarks" not in result
        assert "cross_sell_patterns" not in result

    @pytest.mark.asyncio
    async def test_refresh_success(
        self, mock_sheets_client, mock_close_client
    ):
        """Test successful benchmark refresh."""
        tools = BenchmarkTools(mock_sheets_client, mock_close_client)

        input_data = RefreshBenchmarksInput(force=True, clear_agent_cache=True)
        result = await tools.refresh(input_data)

        assert result["success"] is True
        assert result["last_refresh"] is not None
        assert result["agents_cache_cleared"] is True
        mock_close_client.clear_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_failure(
        self, mock_sheets_client
    ):
        """Test handling of refresh failure."""
        mock_sheets_client.load_benchmarks.side_effect = Exception("Sheet error")
        tools = BenchmarkTools(mock_sheets_client)

        input_data = RefreshBenchmarksInput(force=True)
        result = await tools.refresh(input_data)

        assert result["success"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_tier_benchmark_formatting(
        self, mock_sheets_client
    ):
        """Test tier benchmark formatting."""
        tools = BenchmarkTools(mock_sheets_client)

        input_data = GetBenchmarkSummaryInput(
            include_tiers=True,
            include_products=False,
            include_cross_sell=False,
        )
        result = await tools.get_summary(input_data)

        tier = result["tier_benchmarks"][0]
        assert "tier" in tier
        assert "contact_rate" in tier
        assert "min" in tier["contact_rate"]
        assert "max" in tier["contact_rate"]
        assert "avg" in tier["contact_rate"]

    def test_invalidate_cache(self, mock_sheets_client):
        """Test cache invalidation."""
        tools = BenchmarkTools(mock_sheets_client)
        tools._benchmarks = "something"

        tools.invalidate_cache()

        assert tools._benchmarks is None
        assert tools._last_refresh is None
