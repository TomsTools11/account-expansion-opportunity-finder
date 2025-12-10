"""Configuration management for API integrations."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""

    pass


@dataclass
class CloseConfig:
    """Configuration for Close CRM API."""

    api_key: str
    base_url: str = "https://api.close.com/api/v1"
    rate_limit_per_second: float = 9.0  # Safety margin below 10 req/sec
    max_retries: int = 3
    timeout_seconds: int = 30

    # Close CRM custom field mappings
    field_map: dict[str, str] = field(default_factory=lambda: {
        "current_products": "custom.cf_product_lines",
        "annual_premium_volume": "custom.cf_book_size",
        "tenure_months": "custom.cf_agent_tenure",
        "contact_rate": "custom.cf_contact_rate",
        "quote_rate": "custom.cf_quote_rate",
        "close_rate": "custom.cf_close_rate",
        "monthly_lead_volume": "custom.cf_monthly_leads",
        "cost_per_acquisition": "custom.cf_cac",
        "region": "custom.cf_region",
        "agency_type": "custom.cf_agency_type",
        "performance_tier": "custom.cf_agent_tier",
    })


@dataclass
class GoogleSheetsConfig:
    """Configuration for Google Sheets API."""

    credentials_path: str
    spreadsheet_id: str
    scopes: list[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/spreadsheets"
    ])

    # Expected sheet names
    sheet_names: dict[str, str] = field(default_factory=lambda: {
        "tiers": "Agent_Tiers",
        "products": "Product_CAC",
        "cross_sell": "Cross_Sell_Patterns",
        "conversion_rates": "Conversion_Rates",
    })


@dataclass
class AnalysisConfig:
    """Configuration for analysis engine."""

    min_confidence_threshold: float = 0.5
    min_similar_agents: int = 10
    max_opportunities_per_agent: int = 5
    similarity_threshold_high: float = 0.75
    similarity_threshold_medium: float = 0.60
    similarity_threshold_low: float = 0.50


@dataclass
class CacheConfig:
    """Configuration for caching."""

    agent_ttl_seconds: int = 300  # 5 minutes
    benchmark_ttl_seconds: int = 3600  # 1 hour
    max_agent_cache_entries: int = 1000
    max_benchmark_cache_entries: int = 100


@dataclass
class AppConfig:
    """Main application configuration."""

    close: Optional[CloseConfig] = None
    google_sheets: Optional[GoogleSheetsConfig] = None
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    log_level: str = "INFO"
    log_format: str = "json"

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.close is None:
            errors.append("Close CRM configuration is missing (CLOSE_API_KEY)")
        elif not self.close.api_key:
            errors.append("Close CRM API key is empty")

        if self.google_sheets is None:
            errors.append(
                "Google Sheets configuration is missing "
                "(GOOGLE_SHEETS_CREDENTIALS_PATH, BENCHMARK_SHEET_ID)"
            )
        else:
            if not self.google_sheets.credentials_path:
                errors.append("Google Sheets credentials path is empty")
            elif not Path(self.google_sheets.credentials_path).exists():
                errors.append(
                    f"Google Sheets credentials file not found: "
                    f"{self.google_sheets.credentials_path}"
                )
            if not self.google_sheets.spreadsheet_id:
                errors.append("Google Sheets spreadsheet ID is empty")

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0


def load_config(env_file: Optional[str] = None) -> AppConfig:
    """Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file

    Returns:
        AppConfig instance

    Raises:
        ConfigurationError: If required configuration is missing
    """
    # Load .env file if specified or exists in cwd
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    # Close CRM config
    close_api_key = os.getenv("CLOSE_API_KEY")
    close_config = None
    if close_api_key:
        close_config = CloseConfig(
            api_key=close_api_key,
            base_url=os.getenv("CLOSE_BASE_URL", "https://api.close.com/api/v1"),
            rate_limit_per_second=float(os.getenv("RATE_LIMIT_PER_SECOND", "9")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            timeout_seconds=int(os.getenv("CLOSE_TIMEOUT_SECONDS", "30")),
        )

    # Google Sheets config
    sheets_creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
    sheets_id = os.getenv("BENCHMARK_SHEET_ID")
    sheets_config = None
    if sheets_creds_path and sheets_id:
        sheets_config = GoogleSheetsConfig(
            credentials_path=sheets_creds_path,
            spreadsheet_id=sheets_id,
        )

    # Analysis config
    analysis_config = AnalysisConfig(
        min_confidence_threshold=float(
            os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.5")
        ),
        min_similar_agents=int(os.getenv("MIN_SIMILAR_AGENTS", "10")),
        max_opportunities_per_agent=int(
            os.getenv("MAX_OPPORTUNITIES_PER_AGENT", "5")
        ),
    )

    # Cache config
    cache_config = CacheConfig(
        agent_ttl_seconds=int(os.getenv("CACHE_TTL_SECONDS", "300")),
        benchmark_ttl_seconds=int(os.getenv("BENCHMARK_CACHE_TTL_SECONDS", "3600")),
        max_agent_cache_entries=int(os.getenv("MAX_AGENT_CACHE_ENTRIES", "1000")),
    )

    return AppConfig(
        close=close_config,
        google_sheets=sheets_config,
        analysis=analysis_config,
        cache=cache_config,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_format=os.getenv("LOG_FORMAT", "json"),
    )


def validate_config(config: AppConfig) -> None:
    """Validate configuration and raise error if invalid.

    Args:
        config: AppConfig to validate

    Raises:
        ConfigurationError: If configuration is invalid
    """
    errors = config.validate()
    if errors:
        error_msg = "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ConfigurationError(error_msg)


# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create the global configuration instance.

    Returns:
        Global AppConfig instance
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
