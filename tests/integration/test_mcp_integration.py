"""Integration tests for the MCP server end-to-end scenarios."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp.server import AccountExpansionServer, TOOL_DEFINITIONS
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


@pytest.fixture
def sample_benchmarks() -> BenchmarkData:
    """Create sample benchmark data."""
    return BenchmarkData(
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
    )


@pytest.fixture
def sample_agent() -> Agent:
    """Create a sample agent."""
    return Agent(
        id="lead_test123",
        name="Test Agent",
        current_products=["Home"],
        annual_premium_volume=50000,
        tenure_months=24,
        performance_tier=PerformanceTier.TOP_25,
        contact_rate=48.0,
        close_rate=20.0,
    )


@pytest.fixture
def sample_agents() -> list[Agent]:
    """Create a list of sample agents."""
    return [
        Agent(
            id=f"lead_{i}",
            name=f"Test Agent {i}",
            current_products=["Home"] if i % 2 == 0 else ["Auto"],
            annual_premium_volume=40000 + i * 5000,
            tenure_months=12 + i * 6,
            performance_tier=PerformanceTier.TOP_25 if i < 5 else PerformanceTier.AVERAGE,
        )
        for i in range(10)
    ]


class TestMCPEndToEnd:
    """End-to-end tests for MCP server scenarios."""

    @pytest.mark.asyncio
    async def test_analyze_agent_full_flow(
        self, sample_agent: Agent, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test complete analyze_agent_account flow."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_close.fetch_agent.return_value = sample_agent
        mock_close.fetch_all_agents.return_value = sample_agents

        mock_sheets = MagicMock()
        mock_sheets.load_benchmarks.return_value = sample_benchmarks

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.analyze_agent_account") as mock_tool:
            mock_tool.return_value = {
                "agent": {
                    "id": "lead_test123",
                    "name": "Test Agent",
                    "current_products": ["Home"],
                },
                "opportunities": [
                    {
                        "rank": 1,
                        "type": "Add Product",
                        "recommended_product": "Auto",
                        "projected_lift": {"dollars": 15000, "percentage": 30.0},
                    }
                ],
                "summary": {
                    "total_opportunities": 1,
                    "total_projected_lift": 15000,
                },
            }

            result = await server._handle_tool_call(
                "analyze_agent_account",
                {"agent_id": "lead_test123"}
            )

            assert "agent" in result
            assert "opportunities" in result
            assert result["agent"]["id"] == "lead_test123"

    @pytest.mark.asyncio
    async def test_batch_analysis_full_flow(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test complete batch_expansion_analysis flow."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_close.fetch_all_agents.return_value = sample_agents

        mock_sheets = MagicMock()
        mock_sheets.load_benchmarks.return_value = sample_benchmarks

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.batch_expansion_analysis") as mock_tool:
            mock_tool.return_value = {
                "summary": {
                    "total_agents_analyzed": 10,
                    "total_opportunities_found": 25,
                },
                "aggregate_metrics": {
                    "total_projected_lift": 150000,
                },
                "top_opportunities": [],
            }

            result = await server._handle_tool_call(
                "batch_expansion_analysis",
                {"top_n": 20, "filter_tiers": ["Top 25%"]}
            )

            assert "summary" in result
            assert result["summary"]["total_agents_analyzed"] == 10

    @pytest.mark.asyncio
    async def test_benchmark_summary_full_flow(self, sample_benchmarks: BenchmarkData):
        """Test complete get_benchmark_summary flow."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_sheets = MagicMock()
        mock_sheets.load_benchmarks.return_value = sample_benchmarks

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.get_benchmark_summary") as mock_tool:
            mock_tool.return_value = {
                "tier_benchmarks": [
                    {"tier": "Top 10%", "contact_rate": {"min": 55, "max": 70}},
                    {"tier": "Top 25%", "contact_rate": {"min": 45, "max": 55}},
                ],
                "product_benchmarks": [
                    {"product": "Auto", "blended_cac": 244.22},
                ],
                "last_refresh": "2025-12-10T12:00:00Z",
            }

            result = await server._handle_tool_call(
                "get_benchmark_summary",
                {"include_tiers": True, "include_products": True}
            )

            assert "tier_benchmarks" in result
            assert len(result["tier_benchmarks"]) == 2


class TestMCPErrorScenarios:
    """Tests for MCP error handling scenarios."""

    @pytest.mark.asyncio
    async def test_agent_not_found_error(self):
        """Test handling when agent is not found."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_close.fetch_agent.return_value = None

        mock_sheets = MagicMock()

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.analyze_agent_account") as mock_tool:
            mock_tool.return_value = {
                "error": "Agent not found: lead_nonexistent",
                "agent_id": "lead_nonexistent",
            }

            result = await server._handle_tool_call(
                "analyze_agent_account",
                {"agent_id": "lead_nonexistent"}
            )

            assert "error" in result
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_api_error_handling(self):
        """Test handling of API errors."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_sheets = MagicMock()

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.analyze_agent_account") as mock_tool:
            mock_tool.return_value = {
                "error": "Could not fetch agent: API connection failed",
                "agent_id": "lead_123",
            }

            result = await server._handle_tool_call(
                "analyze_agent_account",
                {"agent_id": "lead_123"}
            )

            assert "error" in result
            assert "Could not fetch agent" in result["error"]

    @pytest.mark.asyncio
    async def test_invalid_tool_name(self):
        """Test handling of invalid tool name."""
        server = AccountExpansionServer()
        server.close_client = MagicMock()
        server.sheets_client = MagicMock()

        with pytest.raises(ValueError) as exc:
            await server._handle_tool_call("invalid_tool", {})

        assert "Unknown tool" in str(exc.value)

    @pytest.mark.asyncio
    async def test_validation_error_handling(self):
        """Test handling of input validation errors."""
        server = AccountExpansionServer()
        server.close_client = MagicMock()
        server.sheets_client = MagicMock()

        # Empty agent_id should fail validation
        from pydantic import ValidationError as PydanticValidationError

        with patch("src.mcp.server.AnalyzeAgentInput") as mock_input:
            mock_input.side_effect = PydanticValidationError.from_exception_data(
                "validation error",
                [{"type": "missing", "loc": ("agent_id",), "msg": "Field required"}],
            )

            with pytest.raises(PydanticValidationError):
                await server._handle_tool_call(
                    "analyze_agent_account",
                    {}
                )

    @pytest.mark.asyncio
    async def test_empty_batch_analysis(self):
        """Test batch analysis with no agents."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_close.fetch_all_agents.return_value = []

        mock_sheets = MagicMock()

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.batch_expansion_analysis") as mock_tool:
            mock_tool.return_value = {
                "error": "No agents found in Close CRM",
                "summary": {
                    "total_agents_analyzed": 0,
                    "total_opportunities_found": 0,
                },
            }

            result = await server._handle_tool_call(
                "batch_expansion_analysis",
                {}
            )

            assert "error" in result
            assert "No agents found" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_benchmarks_failure(self):
        """Test handling of benchmark refresh failure."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_sheets = MagicMock()
        mock_sheets.load_benchmarks.side_effect = Exception("Sheet connection failed")

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.refresh_benchmarks") as mock_tool:
            mock_tool.return_value = {
                "success": False,
                "error": "Failed to refresh: Sheet connection failed",
            }

            result = await server._handle_tool_call(
                "refresh_benchmarks",
                {"force": True}
            )

            assert result["success"] is False
            assert "error" in result


class TestToolDefinitions:
    """Tests for MCP tool definitions."""

    def test_all_tools_have_valid_schemas(self):
        """Test that all tool schemas are valid JSON Schema."""
        for tool in TOOL_DEFINITIONS:
            schema = tool.inputSchema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert isinstance(schema.get("required", []), list)

    def test_analyze_agent_schema(self):
        """Test analyze_agent_account schema completeness."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "analyze_agent_account")

        props = tool.inputSchema["properties"]
        assert "agent_id" in props
        assert "min_confidence" in props
        assert "max_opportunities" in props

    def test_batch_analysis_schema(self):
        """Test batch_expansion_analysis schema completeness."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "batch_expansion_analysis")

        props = tool.inputSchema["properties"]
        assert "top_n" in props
        assert "filter_tiers" in props
        assert "min_tenure_months" in props

    def test_benchmark_summary_schema(self):
        """Test get_benchmark_summary schema completeness."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_benchmark_summary")

        props = tool.inputSchema["properties"]
        assert "include_tiers" in props
        assert "include_products" in props
        assert "tier_filter" in props

    def test_refresh_benchmarks_schema(self):
        """Test refresh_benchmarks schema completeness."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "refresh_benchmarks")

        props = tool.inputSchema["properties"]
        assert "force" in props
        assert "clear_agent_cache" in props
