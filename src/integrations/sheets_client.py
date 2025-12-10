"""Google Sheets API client for benchmark data."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.models import (
    BenchmarkData,
    BenchmarkTier,
    ConversionRates,
    CrossSellPattern,
    PerformanceTier,
    ProductBenchmark,
)
from src.utils.cache import TTLCache, get_benchmark_cache

from .config import GoogleSheetsConfig, get_config

logger = logging.getLogger(__name__)


class SheetsAPIError(Exception):
    """Base exception for Google Sheets API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SheetsAuthenticationError(SheetsAPIError):
    """Raised when authentication fails."""

    pass


class SheetsNotFoundError(SheetsAPIError):
    """Raised when a sheet or range is not found."""

    pass


class InvalidSheetSchemaError(SheetsAPIError):
    """Raised when sheet schema doesn't match expected structure."""

    def __init__(
        self,
        message: str,
        expected_columns: Optional[list[str]] = None,
        actual_columns: Optional[list[str]] = None,
    ):
        super().__init__(message)
        self.expected_columns = expected_columns
        self.actual_columns = actual_columns


class SheetsClient:
    """Client for interacting with Google Sheets API.

    Handles authentication, reading benchmarks, and writing patterns.
    """

    # Expected column headers for schema validation
    EXPECTED_SCHEMAS = {
        "Agent_Tiers": [
            "Tier",
            "Contact_Rate_Min",
            "Contact_Rate_Max",
            "Quote_Rate_Min",
            "Quote_Rate_Max",
            "Close_Rate_Min",
            "Close_Rate_Max",
            "CAC_Min",
            "CAC_Max",
            "Lead_Volume_Min",
            "Lead_Volume_Max",
        ],
        "Product_CAC": [
            "Product",
            "Organic_CAC",
            "Inorganic_CAC",
            "Blended_CAC",
            "Avg_Annual_Premium",
            "Source",
        ],
        "Cross_Sell_Patterns": [
            "Primary_Product",
            "Added_Product",
            "Avg_Lift_Pct",
            "Adoption_Rate",
            "Avg_Time_Months",
            "Tier",
        ],
    }

    def __init__(self, config: Optional[GoogleSheetsConfig] = None):
        """Initialize Google Sheets client.

        Args:
            config: Optional GoogleSheetsConfig, loads from environment if not provided
        """
        if config is None:
            app_config = get_config()
            if app_config.google_sheets is None:
                raise SheetsAuthenticationError(
                    "Google Sheets not configured. Set GOOGLE_SHEETS_CREDENTIALS_PATH "
                    "and BENCHMARK_SHEET_ID environment variables."
                )
            config = app_config.google_sheets

        self._config = config
        self._service = self._create_service()
        self._cache: TTLCache[Any] = get_benchmark_cache()

    def _create_service(self) -> Any:
        """Create the Google Sheets API service.

        Returns:
            Google Sheets API service instance

        Raises:
            SheetsAuthenticationError: If credentials are invalid
        """
        creds_path = Path(self._config.credentials_path)
        if not creds_path.exists():
            raise SheetsAuthenticationError(
                f"Credentials file not found: {creds_path}"
            )

        try:
            credentials = Credentials.from_service_account_file(
                str(creds_path), scopes=self._config.scopes
            )
            service = build("sheets", "v4", credentials=credentials)
            return service.spreadsheets()
        except Exception as e:
            raise SheetsAuthenticationError(f"Failed to create Sheets service: {e}")

    def _read_range(self, range_name: str) -> list[list[Any]]:
        """Read data from a sheet range.

        Args:
            range_name: Sheet range (e.g., "Sheet1!A1:Z100")

        Returns:
            2D list of cell values

        Raises:
            SheetsNotFoundError: If sheet or range not found
            SheetsAPIError: On other API errors
        """
        try:
            result = (
                self._service.values()
                .get(spreadsheetId=self._config.spreadsheet_id, range=range_name)
                .execute()
            )
            return result.get("values", [])
        except HttpError as e:
            if e.resp.status == 404:
                raise SheetsNotFoundError(f"Sheet or range not found: {range_name}")
            raise SheetsAPIError(f"Failed to read range {range_name}: {e}")

    def _batch_read(self, ranges: list[str]) -> dict[str, list[list[Any]]]:
        """Read multiple ranges in a single API call.

        Args:
            ranges: List of range names

        Returns:
            Dictionary mapping range names to their values
        """
        try:
            result = (
                self._service.values()
                .batchGet(spreadsheetId=self._config.spreadsheet_id, ranges=ranges)
                .execute()
            )

            data = {}
            for value_range in result.get("valueRanges", []):
                range_name = value_range.get("range", "")
                # Extract sheet name from full range
                sheet_name = range_name.split("!")[0].strip("'")
                data[sheet_name] = value_range.get("values", [])

            return data
        except HttpError as e:
            raise SheetsAPIError(f"Failed to batch read: {e}")

    def _validate_schema(
        self, sheet_name: str, headers: list[str]
    ) -> None:
        """Validate that sheet headers match expected schema.

        Args:
            sheet_name: Name of the sheet
            headers: Actual column headers from sheet

        Raises:
            InvalidSheetSchemaError: If schema doesn't match
        """
        expected = self.EXPECTED_SCHEMAS.get(sheet_name)
        if expected is None:
            return  # No validation for unknown sheets

        missing = [col for col in expected if col not in headers]
        if missing:
            raise InvalidSheetSchemaError(
                f"Sheet '{sheet_name}' missing required columns: {missing}",
                expected_columns=expected,
                actual_columns=headers,
            )

    def _parse_tier_data(self, rows: list[list[Any]]) -> list[BenchmarkTier]:
        """Parse Agent_Tiers sheet data.

        Args:
            rows: Raw sheet rows (including header)

        Returns:
            List of BenchmarkTier models
        """
        if len(rows) < 2:
            return []

        headers = rows[0]
        self._validate_schema("Agent_Tiers", headers)

        tiers = []
        tier_name_map = {
            "Top Performer (Top 10%)": PerformanceTier.TOP_10,
            "Top 10%": PerformanceTier.TOP_10,
            "Above Average (Top 25%)": PerformanceTier.TOP_25,
            "Top 25%": PerformanceTier.TOP_25,
            "Average (Middle 50%)": PerformanceTier.AVERAGE,
            "Average": PerformanceTier.AVERAGE,
            "Below Average (Bottom 25%)": PerformanceTier.BELOW_AVERAGE,
            "Below Average": PerformanceTier.BELOW_AVERAGE,
            "Struggling (Bottom 10%)": PerformanceTier.BOTTOM_10,
            "Bottom 10%": PerformanceTier.BOTTOM_10,
        }

        for row in rows[1:]:
            if len(row) < 11:
                continue

            tier_str = row[0]
            tier_name = tier_name_map.get(tier_str)
            if tier_name is None:
                continue

            try:
                tier = BenchmarkTier(
                    tier_name=tier_name,
                    contact_rate_range=(
                        self._parse_rate(row[1]),
                        self._parse_rate(row[2]),
                    ),
                    quote_rate_range=(
                        self._parse_rate(row[3]),
                        self._parse_rate(row[4]),
                    ),
                    close_rate_range=(
                        self._parse_rate(row[5]),
                        self._parse_rate(row[6]),
                    ),
                    cac_range=(
                        self._parse_currency(row[7]),
                        self._parse_currency(row[8]),
                    ),
                    lead_volume_range=(int(row[9]), int(row[10])),
                )
                tiers.append(tier)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse tier row: {e}")
                continue

        return tiers

    def _parse_product_data(self, rows: list[list[Any]]) -> list[ProductBenchmark]:
        """Parse Product_CAC sheet data.

        Args:
            rows: Raw sheet rows (including header)

        Returns:
            List of ProductBenchmark models
        """
        if len(rows) < 2:
            return []

        headers = rows[0]
        products = []

        for row in rows[1:]:
            if len(row) < 4:
                continue

            product_name = row[0]
            if not product_name:
                continue

            try:
                product = ProductBenchmark(
                    product=product_name,
                    organic_cac=self._parse_currency(row[1]),
                    inorganic_cac=self._parse_currency(row[2]),
                    blended_cac=self._parse_currency(row[3]),
                    avg_annual_premium=self._parse_currency(row[4]) if len(row) > 4 else None,
                    source=row[5] if len(row) > 5 else "Unknown",
                )
                products.append(product)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse product row: {e}")
                continue

        return products

    def _parse_cross_sell_data(self, rows: list[list[Any]]) -> list[CrossSellPattern]:
        """Parse Cross_Sell_Patterns sheet data.

        Args:
            rows: Raw sheet rows (including header)

        Returns:
            List of CrossSellPattern models
        """
        if len(rows) < 2:
            return []

        headers = rows[0]
        patterns = []

        tier_map = {
            "Top 10%": PerformanceTier.TOP_10,
            "Top 25%": PerformanceTier.TOP_25,
            "Average": PerformanceTier.AVERAGE,
            "Below Average": PerformanceTier.BELOW_AVERAGE,
            "Bottom 10%": PerformanceTier.BOTTOM_10,
        }

        for row in rows[1:]:
            if len(row) < 5:
                continue

            try:
                tier = None
                if len(row) > 5 and row[5]:
                    tier = tier_map.get(row[5])

                pattern = CrossSellPattern(
                    primary_product=row[0],
                    added_product=row[1],
                    avg_revenue_lift_pct=float(row[2]),
                    adoption_rate=float(row[3]),
                    avg_time_to_add_months=int(row[4]),
                    tier=tier,
                )
                patterns.append(pattern)
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse cross-sell row: {e}")
                continue

        return patterns

    def _parse_rate(self, value: Any) -> float:
        """Parse a rate value, handling percentage strings."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove % sign if present
            cleaned = value.replace("%", "").replace(",", "").strip()
            if "-" in cleaned:
                # Handle range like "55-70"
                parts = cleaned.split("-")
                return float(parts[0])
            return float(cleaned)
        return 0.0

    def _parse_currency(self, value: Any) -> float:
        """Parse a currency value, handling $ and commas."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").strip()
            if "-" in cleaned:
                parts = cleaned.split("-")
                return float(parts[0].strip("$").replace(",", ""))
            return float(cleaned)
        return 0.0

    def load_benchmarks(self, use_cache: bool = True) -> BenchmarkData:
        """Load all benchmark data from Google Sheets.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            BenchmarkData model with all benchmark information
        """
        cache_key = "benchmarks_all"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for benchmark data")
                return cached

        logger.info("Loading benchmark data from Google Sheets")

        sheet_names = self._config.sheet_names

        # Batch read all sheets
        ranges = [
            f"{sheet_names['tiers']}!A1:K20",
            f"{sheet_names['products']}!A1:F30",
            f"{sheet_names['cross_sell']}!A1:G100",
        ]

        try:
            data = self._batch_read(ranges)
        except SheetsAPIError as e:
            logger.error(f"Failed to load benchmarks: {e}")
            raise

        # Parse each sheet
        tiers = self._parse_tier_data(data.get(sheet_names["tiers"], []))
        products = self._parse_product_data(data.get(sheet_names["products"], []))
        cross_sell = self._parse_cross_sell_data(data.get(sheet_names["cross_sell"], []))

        benchmark_data = BenchmarkData(
            tiers=tiers,
            products=products,
            cross_sell_patterns=cross_sell,
            last_updated=datetime.now(timezone.utc),
            source="Google Sheets",
        )

        self._cache.set(cache_key, benchmark_data)
        return benchmark_data

    def write_cross_sell_pattern(self, pattern: CrossSellPattern) -> bool:
        """Write a new cross-sell pattern to the sheet.

        Args:
            pattern: CrossSellPattern to append

        Returns:
            True if successful
        """
        sheet_name = self._config.sheet_names["cross_sell"]
        range_name = f"{sheet_name}!A:G"

        values = [[
            pattern.primary_product,
            pattern.added_product,
            pattern.avg_revenue_lift_pct,
            pattern.adoption_rate,
            pattern.avg_time_to_add_months,
            pattern.tier.value if pattern.tier else "",
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ]]

        try:
            self._service.values().append(
                spreadsheetId=self._config.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()

            # Invalidate cache
            self._cache.delete("benchmarks_all")
            return True

        except HttpError as e:
            logger.error(f"Failed to write cross-sell pattern: {e}")
            raise SheetsAPIError(f"Failed to write pattern: {e}")

    def write_cross_sell_patterns(self, patterns: list[CrossSellPattern]) -> int:
        """Write multiple cross-sell patterns to the sheet.

        Args:
            patterns: List of CrossSellPattern to append

        Returns:
            Number of patterns written
        """
        if not patterns:
            return 0

        sheet_name = self._config.sheet_names["cross_sell"]
        range_name = f"{sheet_name}!A:G"

        values = []
        for pattern in patterns:
            values.append([
                pattern.primary_product,
                pattern.added_product,
                pattern.avg_revenue_lift_pct,
                pattern.adoption_rate,
                pattern.avg_time_to_add_months,
                pattern.tier.value if pattern.tier else "",
                datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            ])

        try:
            self._service.values().append(
                spreadsheetId=self._config.spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            ).execute()

            # Invalidate cache
            self._cache.delete("benchmarks_all")
            return len(patterns)

        except HttpError as e:
            logger.error(f"Failed to write cross-sell patterns: {e}")
            raise SheetsAPIError(f"Failed to write patterns: {e}")

    def test_connection(self) -> bool:
        """Test the API connection.

        Returns:
            True if connection is successful
        """
        try:
            self._service.get(spreadsheetId=self._config.spreadsheet_id).execute()
            return True
        except HttpError:
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the benchmark cache."""
        self._cache.clear()

    def invalidate_cache(self) -> None:
        """Invalidate benchmark cache (alias for clear_cache)."""
        self.clear_cache()
