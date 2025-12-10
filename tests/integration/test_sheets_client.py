"""Integration tests for Google Sheets client (using mocked responses)."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.integrations.sheets_client import (
    InvalidSheetSchemaError,
    SheetsAPIError,
    SheetsAuthenticationError,
    SheetsClient,
    SheetsNotFoundError,
)
from src.integrations.config import GoogleSheetsConfig
from src.models import CrossSellPattern, PerformanceTier


@pytest.fixture
def mock_credentials_file():
    """Create a temporary mock credentials file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"type": "service_account", "project_id": "test"}')
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def sheets_config(mock_credentials_file: str) -> GoogleSheetsConfig:
    """Create test Google Sheets configuration."""
    return GoogleSheetsConfig(
        credentials_path=mock_credentials_file,
        spreadsheet_id="test_sheet_id_123",
    )


@pytest.fixture
def sample_tier_data() -> list[list]:
    """Sample Agent_Tiers sheet data."""
    return [
        [
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
        ["Top 10%", "55", "70", "35", "50", "25", "40", "25", "60", "150", "300"],
        ["Top 25%", "45", "55", "25", "35", "18", "25", "50", "90", "100", "150"],
        ["Average", "30", "45", "15", "25", "12", "18", "80", "130", "50", "100"],
    ]


@pytest.fixture
def sample_product_data() -> list[list]:
    """Sample Product_CAC sheet data."""
    return [
        ["Product", "Organic_CAC", "Inorganic_CAC", "Blended_CAC", "Avg_Annual_Premium", "Source"],
        ["Auto", "203.52", "305.28", "244.22", "950", "Focus Digital 2024"],
        ["Home", "140.72", "211.08", "168.86", "1200", "Focus Digital 2024"],
        ["Life", "24.96", "37.44", "29.95", "500", "Focus Digital 2024"],
    ]


@pytest.fixture
def sample_cross_sell_data() -> list[list]:
    """Sample Cross_Sell_Patterns sheet data."""
    return [
        [
            "Primary_Product",
            "Added_Product",
            "Avg_Lift_Pct",
            "Adoption_Rate",
            "Avg_Time_Months",
            "Tier",
        ],
        ["Home", "Auto", "35.2", "0.68", "6", "Top 25%"],
        ["Auto", "Home", "28.5", "0.54", "8", "Top 25%"],
    ]


@pytest.fixture
def mock_sheets_service():
    """Create a mock Google Sheets service."""
    service = MagicMock()
    return service


class TestSheetsClientInit:
    """Tests for SheetsClient initialization."""

    def test_init_missing_credentials_file(self, sheets_config: GoogleSheetsConfig):
        """Test that missing credentials file raises error."""
        sheets_config.credentials_path = "/nonexistent/path.json"

        with pytest.raises(SheetsAuthenticationError) as exc:
            with patch(
                "src.integrations.sheets_client.Credentials.from_service_account_file"
            ):
                SheetsClient(config=sheets_config)

        assert "not found" in str(exc.value)


class TestSheetsClientLoadBenchmarks:
    """Tests for load_benchmarks method."""

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_load_benchmarks_success(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
        sample_tier_data: list[list],
        sample_product_data: list[list],
        sample_cross_sell_data: list[list],
    ):
        """Test successful benchmark loading."""
        # Setup mock
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.spreadsheets.return_value.values.return_value.batchGet.return_value.execute.return_value = {
            "valueRanges": [
                {"range": "'Agent_Tiers'!A1:K20", "values": sample_tier_data},
                {"range": "'Product_CAC'!A1:F30", "values": sample_product_data},
                {"range": "'Cross_Sell_Patterns'!A1:G100", "values": sample_cross_sell_data},
            ]
        }

        client = SheetsClient(config=sheets_config)
        benchmarks = client.load_benchmarks(use_cache=False)

        assert len(benchmarks.tiers) == 3
        assert len(benchmarks.products) == 3
        assert len(benchmarks.cross_sell_patterns) == 2

        # Verify tier parsing
        top_10 = benchmarks.get_tier_by_name(PerformanceTier.TOP_10)
        assert top_10 is not None
        assert top_10.contact_rate_range == (55.0, 70.0)

        # Verify product parsing
        auto = benchmarks.get_product_benchmark("Auto")
        assert auto is not None
        assert auto.blended_cac == 244.22

        # Verify cross-sell parsing
        pattern = benchmarks.get_cross_sell_pattern("Home", "Auto")
        assert pattern is not None
        assert pattern.avg_revenue_lift_pct == 35.2
        assert pattern.tier == PerformanceTier.TOP_25

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_load_benchmarks_uses_cache(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
        sample_tier_data: list[list],
        sample_product_data: list[list],
        sample_cross_sell_data: list[list],
    ):
        """Test that cached results are returned on second call."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        batch_get = mock_service.spreadsheets.return_value.values.return_value.batchGet.return_value.execute
        batch_get.return_value = {
            "valueRanges": [
                {"range": "'Agent_Tiers'!A1:K20", "values": sample_tier_data},
                {"range": "'Product_CAC'!A1:F30", "values": sample_product_data},
                {"range": "'Cross_Sell_Patterns'!A1:G100", "values": sample_cross_sell_data},
            ]
        }

        client = SheetsClient(config=sheets_config)
        client.clear_cache()  # Ensure clean start

        # First call - hits API
        benchmarks1 = client.load_benchmarks(use_cache=True)

        # Second call - should use cache
        benchmarks2 = client.load_benchmarks(use_cache=True)

        assert benchmarks1.last_updated == benchmarks2.last_updated
        assert batch_get.call_count == 1  # Only one API call

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_load_benchmarks_empty_sheets(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test loading from empty sheets."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.spreadsheets.return_value.values.return_value.batchGet.return_value.execute.return_value = {
            "valueRanges": [
                {"range": "'Agent_Tiers'!A1:K20", "values": []},
                {"range": "'Product_CAC'!A1:F30", "values": []},
                {"range": "'Cross_Sell_Patterns'!A1:G100", "values": []},
            ]
        }

        client = SheetsClient(config=sheets_config)
        benchmarks = client.load_benchmarks(use_cache=False)

        assert len(benchmarks.tiers) == 0
        assert len(benchmarks.products) == 0
        assert len(benchmarks.cross_sell_patterns) == 0


class TestSheetsClientWritePatterns:
    """Tests for write_cross_sell_pattern methods."""

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_write_cross_sell_pattern(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test writing a single cross-sell pattern."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_append = mock_service.spreadsheets.return_value.values.return_value.append
        mock_append.return_value.execute.return_value = {"updates": {"updatedRows": 1}}

        client = SheetsClient(config=sheets_config)

        pattern = CrossSellPattern(
            primary_product="Auto",
            added_product="Home",
            avg_revenue_lift_pct=25.5,
            adoption_rate=0.45,
            avg_time_to_add_months=10,
            tier=PerformanceTier.AVERAGE,
        )

        result = client.write_cross_sell_pattern(pattern)

        assert result is True
        mock_append.assert_called_once()

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_write_cross_sell_patterns_batch(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test writing multiple cross-sell patterns."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_append = mock_service.spreadsheets.return_value.values.return_value.append
        mock_append.return_value.execute.return_value = {"updates": {"updatedRows": 2}}

        client = SheetsClient(config=sheets_config)

        patterns = [
            CrossSellPattern(
                primary_product="Auto",
                added_product="Home",
                avg_revenue_lift_pct=25.5,
                adoption_rate=0.45,
                avg_time_to_add_months=10,
            ),
            CrossSellPattern(
                primary_product="Home",
                added_product="Life",
                avg_revenue_lift_pct=15.0,
                adoption_rate=0.30,
                avg_time_to_add_months=12,
            ),
        ]

        count = client.write_cross_sell_patterns(patterns)

        assert count == 2

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_write_patterns_empty_list(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test writing empty pattern list returns 0."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        client = SheetsClient(config=sheets_config)

        count = client.write_cross_sell_patterns([])

        assert count == 0


class TestSheetsClientTestConnection:
    """Tests for test_connection method."""

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_connection_success(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test successful connection test."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.return_value = {
            "spreadsheetId": "test_id"
        }

        client = SheetsClient(config=sheets_config)
        assert client.test_connection() is True

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_connection_failure(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test failed connection test."""
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.spreadsheets.return_value.get.return_value.execute.side_effect = (
            HttpError(MagicMock(status=404), b"Not found")
        )

        client = SheetsClient(config=sheets_config)
        assert client.test_connection() is False


class TestSheetsClientParsing:
    """Tests for data parsing methods."""

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_parse_currency_values(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test parsing various currency formats."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        client = SheetsClient(config=sheets_config)

        # Test various formats
        assert client._parse_currency("$100.50") == 100.50
        assert client._parse_currency("1,000.00") == 1000.00
        assert client._parse_currency("$1,234.56") == 1234.56
        assert client._parse_currency(100) == 100.0
        assert client._parse_currency(100.5) == 100.5

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_parse_rate_values(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test parsing various rate formats."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        client = SheetsClient(config=sheets_config)

        # Test various formats
        assert client._parse_rate("55%") == 55.0
        assert client._parse_rate("55.5%") == 55.5
        assert client._parse_rate("55-70") == 55.0  # Takes first value
        assert client._parse_rate(55) == 55.0
        assert client._parse_rate(55.5) == 55.5


class TestSheetsClientCacheManagement:
    """Tests for cache management methods."""

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_clear_cache(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
        sample_tier_data: list[list],
        sample_product_data: list[list],
        sample_cross_sell_data: list[list],
    ):
        """Test cache clearing."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        batch_get = mock_service.spreadsheets.return_value.values.return_value.batchGet.return_value.execute
        batch_get.return_value = {
            "valueRanges": [
                {"range": "'Agent_Tiers'!A1:K20", "values": sample_tier_data},
                {"range": "'Product_CAC'!A1:F30", "values": sample_product_data},
                {"range": "'Cross_Sell_Patterns'!A1:G100", "values": sample_cross_sell_data},
            ]
        }

        client = SheetsClient(config=sheets_config)
        client.clear_cache()

        # First load
        client.load_benchmarks(use_cache=True)

        # Clear and load again
        client.clear_cache()
        client.load_benchmarks(use_cache=True)

        assert batch_get.call_count == 2  # Two API calls after cache clear

    @patch("src.integrations.sheets_client.build")
    @patch("src.integrations.sheets_client.Credentials.from_service_account_file")
    def test_get_cache_stats(
        self,
        mock_creds,
        mock_build,
        sheets_config: GoogleSheetsConfig,
    ):
        """Test cache statistics retrieval."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        client = SheetsClient(config=sheets_config)
        stats = client.get_cache_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats
