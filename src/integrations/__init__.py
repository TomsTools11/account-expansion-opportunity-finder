"""Integration clients for external APIs."""

from .close_client import (
    CloseAPIError,
    CloseAuthenticationError,
    CloseClient,
    CloseNotFoundError,
    CloseRateLimitError,
)
from .config import (
    AnalysisConfig,
    AppConfig,
    CacheConfig,
    CloseConfig,
    ConfigurationError,
    GoogleSheetsConfig,
    get_config,
    load_config,
    reset_config,
    validate_config,
)
from .sheets_client import (
    InvalidSheetSchemaError,
    SheetsAPIError,
    SheetsAuthenticationError,
    SheetsClient,
    SheetsNotFoundError,
)

__all__ = [
    # Close CRM
    "CloseAPIError",
    "CloseAuthenticationError",
    "CloseClient",
    "CloseNotFoundError",
    "CloseRateLimitError",
    # Google Sheets
    "InvalidSheetSchemaError",
    "SheetsAPIError",
    "SheetsAuthenticationError",
    "SheetsClient",
    "SheetsNotFoundError",
    # Config
    "AnalysisConfig",
    "AppConfig",
    "CacheConfig",
    "CloseConfig",
    "ConfigurationError",
    "GoogleSheetsConfig",
    "get_config",
    "load_config",
    "reset_config",
    "validate_config",
]
