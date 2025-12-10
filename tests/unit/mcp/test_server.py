"""Unit tests for MCP server."""

from unittest.mock import MagicMock, AsyncMock, patch
import json
import pytest

from src.mcp.server import (
    AccountExpansionServer,
    create_server,
    TOOL_DEFINITIONS,
)


class TestToolDefinitions:
    """Tests for tool definitions."""

    def test_all_tools_defined(self):
        """Test that all expected tools are defined."""
        tool_names = {t.name for t in TOOL_DEFINITIONS}
        expected = {
            "analyze_agent_account",
            "batch_expansion_analysis",
            "get_benchmark_summary",
            "refresh_benchmarks",
        }
        assert tool_names == expected

    def test_analyze_agent_has_required_field(self):
        """Test that analyze_agent_account has agent_id as required."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "analyze_agent_account")
        assert "agent_id" in tool.inputSchema["required"]

    def test_batch_analysis_has_no_required_fields(self):
        """Test that batch_expansion_analysis has no required fields."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "batch_expansion_analysis")
        assert tool.inputSchema["required"] == []

    def test_all_tools_have_descriptions(self):
        """Test that all tools have descriptions."""
        for tool in TOOL_DEFINITIONS:
            assert tool.description
            assert len(tool.description) > 20

    def test_tool_schema_types(self):
        """Test that tool schemas have proper types."""
        for tool in TOOL_DEFINITIONS:
            assert tool.inputSchema["type"] == "object"
            assert "properties" in tool.inputSchema


class TestAccountExpansionServer:
    """Tests for AccountExpansionServer."""

    def test_create_server(self):
        """Test server creation."""
        server = create_server()
        assert server is not None
        assert isinstance(server, AccountExpansionServer)

    def test_server_initialization(self):
        """Test server initialization."""
        server = AccountExpansionServer()
        assert server.close_client is None
        assert server.sheets_client is None
        assert server.server is not None

    @pytest.mark.asyncio
    async def test_handle_unknown_tool(self):
        """Test handling of unknown tool call."""
        server = AccountExpansionServer()
        # Set up mock clients to avoid _ensure_clients_initialized failure
        server.close_client = MagicMock()
        server.sheets_client = MagicMock()

        with pytest.raises(ValueError) as exc:
            await server._handle_tool_call("unknown_tool", {})
        assert "Unknown tool" in str(exc.value)

    @pytest.mark.asyncio
    async def test_handle_analyze_agent_tool(self):
        """Test handling of analyze_agent_account tool."""
        server = AccountExpansionServer()

        # Mock the clients
        mock_close = MagicMock()
        mock_close.fetch_agent = MagicMock(return_value=MagicMock(
            id="agent_123",
            name="Test",
            current_products=["Auto"],
            annual_premium_volume=50000,
            tenure_months=24,
            performance_tier=MagicMock(value="TOP_25"),
        ))
        mock_close.fetch_all_agents = MagicMock(return_value=[])

        mock_sheets = MagicMock()
        mock_sheets.load_benchmarks = MagicMock(return_value=MagicMock(
            tiers=[],
            products=[],
            cross_sell_patterns=[],
        ))

        server.close_client = mock_close
        server.sheets_client = mock_sheets

        # This will fail since we don't have a real engine, but we can test the routing
        with patch("src.mcp.server.analyze_agent_account") as mock_tool:
            mock_tool.return_value = {"agent": {"id": "agent_123"}}
            result = await server._handle_tool_call(
                "analyze_agent_account",
                {"agent_id": "agent_123"}
            )
            assert result == {"agent": {"id": "agent_123"}}
            mock_tool.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_batch_analysis_tool(self):
        """Test handling of batch_expansion_analysis tool."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_sheets = MagicMock()
        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.batch_expansion_analysis") as mock_tool:
            mock_tool.return_value = {"summary": {}}
            result = await server._handle_tool_call(
                "batch_expansion_analysis",
                {"top_n": 10}
            )
            assert result == {"summary": {}}

    @pytest.mark.asyncio
    async def test_handle_benchmark_summary_tool(self):
        """Test handling of get_benchmark_summary tool."""
        server = AccountExpansionServer()

        mock_close = MagicMock()
        mock_sheets = MagicMock()
        server.close_client = mock_close
        server.sheets_client = mock_sheets

        with patch("src.mcp.server.get_benchmark_summary") as mock_tool:
            mock_tool.return_value = {"tier_benchmarks": []}
            result = await server._handle_tool_call(
                "get_benchmark_summary",
                {}
            )
            assert result == {"tier_benchmarks": []}

    @pytest.mark.asyncio
    async def test_handle_refresh_benchmarks_tool(self):
        """Test handling of refresh_benchmarks tool."""
        server = AccountExpansionServer()

        mock_sheets = MagicMock()
        mock_close = MagicMock()
        server.sheets_client = mock_sheets
        server.close_client = mock_close

        with patch("src.mcp.server.refresh_benchmarks") as mock_tool:
            mock_tool.return_value = {"success": True}
            result = await server._handle_tool_call(
                "refresh_benchmarks",
                {"force": True}
            )
            assert result == {"success": True}


class TestClientInitialization:
    """Tests for client initialization."""

    @pytest.mark.asyncio
    async def test_ensure_clients_initialized(self):
        """Test that clients are initialized on first tool call."""
        server = AccountExpansionServer()

        with patch("src.mcp.server.CloseClient") as MockClose:
            with patch("src.mcp.server.SheetsClient") as MockSheets:
                await server._ensure_clients_initialized()

                MockClose.assert_called_once_with()
                MockSheets.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_clients_not_reinitialized(self):
        """Test that clients are not reinitialized if already set."""
        server = AccountExpansionServer()
        server.close_client = MagicMock()
        server.sheets_client = MagicMock()

        with patch("src.mcp.server.CloseClient") as MockClose:
            with patch("src.mcp.server.SheetsClient") as MockSheets:
                await server._ensure_clients_initialized()

                MockClose.assert_not_called()
                MockSheets.assert_not_called()
