"""MCP server for account expansion opportunity analysis."""

import asyncio
import json
import logging
import sys
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)
from pydantic import ValidationError

from src.integrations import CloseClient, SheetsClient, load_config
from src.mcp.tools import (
    AnalyzeAgentInput,
    BatchAnalysisInput,
    GetBenchmarkSummaryInput,
    RefreshBenchmarksInput,
    analyze_agent_account,
    batch_expansion_analysis,
    get_benchmark_summary,
    refresh_benchmarks,
)

logger = logging.getLogger(__name__)


# Tool definitions for MCP
TOOL_DEFINITIONS = [
    Tool(
        name="analyze_agent_account",
        description=(
            "Analyze a specific insurance agent's account for expansion opportunities. "
            "Returns cross-sell/upsell recommendations with projected revenue lift, "
            "confidence scores, and actionable insights based on peer comparison."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The Close CRM ID of the agent to analyze",
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence threshold (0.0-1.0) for opportunities",
                    "default": 0.5,
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "max_opportunities": {
                    "type": "integer",
                    "description": "Maximum number of opportunities to return",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "include_tier_progression": {
                    "type": "boolean",
                    "description": "Whether to include tier progression opportunities",
                    "default": True,
                },
            },
            "required": ["agent_id"],
        },
    ),
    Tool(
        name="batch_expansion_analysis",
        description=(
            "Analyze all agents in the book for expansion opportunities. "
            "Returns top opportunities across the entire agent population, "
            "with aggregate metrics and priority distribution. Supports filtering "
            "by tier, products, tenure, and premium volume."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "Return top N opportunities across all agents",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
                "min_confidence": {
                    "type": "number",
                    "description": "Minimum confidence threshold (0.0-1.0)",
                    "default": 0.5,
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "filter_tiers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to specific performance tiers (e.g., ['TOP_25', 'TOP_10'])",
                },
                "filter_products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to agents with specific current products",
                },
                "filter_missing_products": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter to agents missing specific products (cross-sell targets)",
                },
                "min_tenure_months": {
                    "type": "integer",
                    "description": "Minimum agent tenure in months",
                    "minimum": 0,
                },
                "max_tenure_months": {
                    "type": "integer",
                    "description": "Maximum agent tenure in months",
                    "minimum": 0,
                },
                "min_premium_volume": {
                    "type": "number",
                    "description": "Minimum annual premium volume",
                    "minimum": 0,
                },
                "max_premium_volume": {
                    "type": "number",
                    "description": "Maximum annual premium volume",
                    "minimum": 0,
                },
                "parallel": {
                    "type": "boolean",
                    "description": "Whether to run analysis in parallel",
                    "default": True,
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_benchmark_summary",
        description=(
            "Get a summary of industry benchmark data including tier performance ranges, "
            "product CAC metrics, and cross-sell patterns. Useful for understanding "
            "baseline expectations and opportunity thresholds."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "include_tiers": {
                    "type": "boolean",
                    "description": "Include tier benchmark details",
                    "default": True,
                },
                "include_products": {
                    "type": "boolean",
                    "description": "Include product benchmark details (CAC metrics)",
                    "default": True,
                },
                "include_cross_sell": {
                    "type": "boolean",
                    "description": "Include cross-sell pattern data",
                    "default": True,
                },
                "tier_filter": {
                    "type": "string",
                    "description": "Filter to a specific tier (e.g., 'TOP_25')",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="refresh_benchmarks",
        description=(
            "Refresh benchmark data from Google Sheets and optionally clear agent cache. "
            "Use this when benchmark data has been updated or to force a fresh analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Force refresh even if cache is still valid",
                    "default": False,
                },
                "clear_agent_cache": {
                    "type": "boolean",
                    "description": "Also clear the agent data cache",
                    "default": False,
                },
            },
            "required": [],
        },
    ),
]


class AccountExpansionServer:
    """MCP server for account expansion opportunity analysis."""

    def __init__(self):
        """Initialize the server."""
        self.server = Server("account-expansion-opportunity-finder")
        self.close_client: Optional[CloseClient] = None
        self.sheets_client: Optional[SheetsClient] = None
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up MCP request handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return TOOL_DEFINITIONS

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls."""
            try:
                result = await self._handle_tool_call(name, arguments)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except ValidationError as e:
                error_msg = f"Invalid input: {e.errors()}"
                logger.error(error_msg)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]
            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return [TextContent(type="text", text=json.dumps({"error": error_msg}))]

    async def _ensure_clients_initialized(self) -> None:
        """Ensure API clients are initialized."""
        if self.close_client is None or self.sheets_client is None:
            logger.info("Initializing API clients")
            config = load_config()

            self.close_client = CloseClient(
                api_key=config.close.api_key,
                base_url=config.close.base_url,
            )

            self.sheets_client = SheetsClient(
                spreadsheet_id=config.google_sheets.spreadsheet_id,
                credentials_path=config.google_sheets.credentials_path,
            )

    async def _handle_tool_call(self, name: str, arguments: dict) -> dict:
        """Handle a tool call and return results.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool execution results
        """
        await self._ensure_clients_initialized()

        if name == "analyze_agent_account":
            input_data = AnalyzeAgentInput(**arguments)
            return await analyze_agent_account(
                input_data, self.close_client, self.sheets_client
            )

        elif name == "batch_expansion_analysis":
            input_data = BatchAnalysisInput(**arguments)
            return await batch_expansion_analysis(
                input_data, self.close_client, self.sheets_client
            )

        elif name == "get_benchmark_summary":
            input_data = GetBenchmarkSummaryInput(**arguments)
            return await get_benchmark_summary(input_data, self.sheets_client)

        elif name == "refresh_benchmarks":
            input_data = RefreshBenchmarksInput(**arguments)
            return await refresh_benchmarks(
                input_data, self.sheets_client, self.close_client
            )

        else:
            raise ValueError(f"Unknown tool: {name}")

    async def run(self) -> None:
        """Run the MCP server using stdio transport."""
        logger.info("Starting Account Expansion MCP Server")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def create_server() -> AccountExpansionServer:
    """Create and return a new server instance.

    Returns:
        Configured AccountExpansionServer instance
    """
    return AccountExpansionServer()


async def async_main() -> None:
    """Async main entry point for the MCP server."""
    # IMPORTANT: Log to stderr, not stdout. MCP uses stdio for communication,
    # so any output to stdout corrupts the protocol and breaks Claude Desktop.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    server = create_server()
    await server.run()


def main() -> None:
    """Synchronous main entry point for the MCP server.

    This is the entry point used by the console script.
    """
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
