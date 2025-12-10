"""MCP tools for benchmark data management."""

import logging
from datetime import datetime
from typing import Any, Optional

from src.integrations import CloseClient, SheetsClient
from src.models import BenchmarkData, PerformanceTier

from .tool_schemas import GetBenchmarkSummaryInput, RefreshBenchmarksInput

logger = logging.getLogger(__name__)


class BenchmarkTools:
    """Tools for managing and querying benchmark data."""

    def __init__(
        self,
        sheets_client: SheetsClient,
        close_client: Optional[CloseClient] = None,
    ):
        """Initialize the tools.

        Args:
            sheets_client: Client for Google Sheets API
            close_client: Optional client for Close CRM API (for cache clearing)
        """
        self.sheets_client = sheets_client
        self.close_client = close_client
        self._benchmarks: Optional[BenchmarkData] = None
        self._last_refresh: Optional[datetime] = None

    async def _ensure_benchmarks_loaded(self) -> None:
        """Ensure benchmark data is loaded."""
        if self._benchmarks is None:
            logger.info("Loading benchmark data from Google Sheets")
            self._benchmarks = self.sheets_client.load_benchmarks()
            self._last_refresh = datetime.now()

    def _format_tier_benchmark(self, tier: Any) -> dict:
        """Format a tier benchmark for output."""
        return {
            "tier": tier.tier_name.value,
            "contact_rate": {
                "min": tier.contact_rate_range[0],
                "max": tier.contact_rate_range[1],
                "avg": (tier.contact_rate_range[0] + tier.contact_rate_range[1]) / 2,
            },
            "quote_rate": {
                "min": tier.quote_rate_range[0],
                "max": tier.quote_rate_range[1],
                "avg": (tier.quote_rate_range[0] + tier.quote_rate_range[1]) / 2,
            },
            "close_rate": {
                "min": tier.close_rate_range[0],
                "max": tier.close_rate_range[1],
                "avg": (tier.close_rate_range[0] + tier.close_rate_range[1]) / 2,
            },
            "cac": {
                "min": tier.cac_range[0],
                "max": tier.cac_range[1],
                "avg": (tier.cac_range[0] + tier.cac_range[1]) / 2,
            },
            "lead_volume": {
                "min": tier.lead_volume_range[0],
                "max": tier.lead_volume_range[1],
                "avg": (tier.lead_volume_range[0] + tier.lead_volume_range[1]) / 2,
            },
        }

    def _format_product_benchmark(self, product: Any) -> dict:
        """Format a product benchmark for output."""
        return {
            "product": product.product,
            "cac": {
                "organic": product.organic_cac,
                "inorganic": product.inorganic_cac,
                "blended": product.blended_cac,
            },
        }

    def _format_cross_sell_pattern(self, pattern: Any) -> dict:
        """Format a cross-sell pattern for output."""
        return {
            "primary_product": pattern.primary_product,
            "added_product": pattern.added_product,
            "avg_revenue_lift_pct": pattern.avg_revenue_lift_pct,
            "adoption_rate": round(pattern.adoption_rate * 100, 1),
            "avg_time_to_add_months": pattern.avg_time_to_add_months,
            "tier": pattern.tier.value if pattern.tier else "ALL",
        }

    async def get_summary(self, input_data: GetBenchmarkSummaryInput) -> dict:
        """Get a summary of benchmark data.

        Args:
            input_data: Validated input parameters

        Returns:
            Benchmark summary data
        """
        logger.info("Getting benchmark summary")

        await self._ensure_benchmarks_loaded()

        result: dict[str, Any] = {
            "last_refresh": self._last_refresh.isoformat()
            if self._last_refresh
            else None,
        }

        # Tier benchmarks
        if input_data.include_tiers:
            tiers = self._benchmarks.tiers
            if input_data.tier_filter:
                target_tier = PerformanceTier(input_data.tier_filter)
                tiers = [t for t in tiers if t.tier_name == target_tier]

            result["tier_benchmarks"] = [
                self._format_tier_benchmark(t) for t in tiers
            ]

        # Product benchmarks
        if input_data.include_products:
            result["product_benchmarks"] = [
                self._format_product_benchmark(p) for p in self._benchmarks.products
            ]

        # Cross-sell patterns
        if input_data.include_cross_sell:
            patterns = self._benchmarks.cross_sell_patterns
            if input_data.tier_filter:
                target_tier = PerformanceTier(input_data.tier_filter)
                patterns = [
                    p
                    for p in patterns
                    if p.tier is None or p.tier == target_tier
                ]

            result["cross_sell_patterns"] = [
                self._format_cross_sell_pattern(p) for p in patterns
            ]

        # Summary statistics
        if self._benchmarks.tiers:
            top_tier = next(
                (t for t in self._benchmarks.tiers if t.tier_name == PerformanceTier.TOP_10),
                None,
            )
            avg_tier = next(
                (t for t in self._benchmarks.tiers if t.tier_name == PerformanceTier.AVERAGE),
                None,
            )

            if top_tier and avg_tier:
                result["insights"] = {
                    "top_10_vs_average_close_rate_improvement": round(
                        ((top_tier.close_rate_range[0] + top_tier.close_rate_range[1]) / 2)
                        - ((avg_tier.close_rate_range[0] + avg_tier.close_rate_range[1]) / 2),
                        1,
                    ),
                    "top_10_vs_average_cac_reduction": round(
                        ((avg_tier.cac_range[0] + avg_tier.cac_range[1]) / 2)
                        - ((top_tier.cac_range[0] + top_tier.cac_range[1]) / 2),
                        2,
                    ),
                }

        return result

    async def refresh(self, input_data: RefreshBenchmarksInput) -> dict:
        """Refresh benchmark data from Google Sheets.

        Args:
            input_data: Validated input parameters

        Returns:
            Refresh status and summary
        """
        logger.info(f"Refreshing benchmarks (force={input_data.force})")

        old_last_refresh = self._last_refresh

        # Force refresh if requested or if we have no data
        if input_data.force or self._benchmarks is None:
            try:
                self._benchmarks = self.sheets_client.load_benchmarks()
                self._last_refresh = datetime.now()
            except Exception as e:
                logger.error(f"Failed to refresh benchmarks: {e}")
                return {
                    "success": False,
                    "error": f"Failed to refresh benchmarks: {str(e)}",
                    "last_refresh": old_last_refresh.isoformat()
                    if old_last_refresh
                    else None,
                }

        # Clear agent cache if requested
        agents_cleared = False
        if input_data.clear_agent_cache and self.close_client:
            try:
                self.close_client.clear_cache()
                agents_cleared = True
            except Exception as e:
                logger.warning(f"Failed to clear agent cache: {e}")

        return {
            "success": True,
            "last_refresh": self._last_refresh.isoformat()
            if self._last_refresh
            else None,
            "previous_refresh": old_last_refresh.isoformat()
            if old_last_refresh
            else None,
            "agents_cache_cleared": agents_cleared,
            "summary": {
                "tiers_loaded": len(self._benchmarks.tiers)
                if self._benchmarks
                else 0,
                "products_loaded": len(self._benchmarks.products)
                if self._benchmarks
                else 0,
                "cross_sell_patterns_loaded": len(self._benchmarks.cross_sell_patterns)
                if self._benchmarks
                else 0,
            },
        }

    def invalidate_cache(self) -> None:
        """Invalidate cached data to force refresh."""
        self._benchmarks = None
        self._last_refresh = None


# Singleton instance for shared state across tool calls
_benchmark_tools: Optional[BenchmarkTools] = None


def get_benchmark_tools(
    sheets_client: SheetsClient,
    close_client: Optional[CloseClient] = None,
) -> BenchmarkTools:
    """Get or create the benchmark tools instance.

    Args:
        sheets_client: Client for Google Sheets API
        close_client: Optional client for Close CRM API

    Returns:
        BenchmarkTools instance
    """
    global _benchmark_tools
    if _benchmark_tools is None:
        _benchmark_tools = BenchmarkTools(sheets_client, close_client)
    return _benchmark_tools


async def get_benchmark_summary(
    input_data: GetBenchmarkSummaryInput,
    sheets_client: SheetsClient,
) -> dict:
    """Get a summary of benchmark data.

    This is the main entry point for the MCP tool.

    Args:
        input_data: Validated input parameters
        sheets_client: Client for Google Sheets API

    Returns:
        Benchmark summary data
    """
    tools = get_benchmark_tools(sheets_client)
    return await tools.get_summary(input_data)


async def refresh_benchmarks(
    input_data: RefreshBenchmarksInput,
    sheets_client: SheetsClient,
    close_client: Optional[CloseClient] = None,
) -> dict:
    """Refresh benchmark data from Google Sheets.

    This is the main entry point for the MCP tool.

    Args:
        input_data: Validated input parameters
        sheets_client: Client for Google Sheets API
        close_client: Optional client for Close CRM API

    Returns:
        Refresh status and summary
    """
    tools = get_benchmark_tools(sheets_client, close_client)
    return await tools.refresh(input_data)
