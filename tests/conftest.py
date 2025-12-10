"""Shared pytest fixtures and configuration."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset global caches before each test."""
    try:
        from src.utils.cache import invalidate_all_caches
        invalidate_all_caches()
    except ImportError:
        pass
    yield
    try:
        from src.utils.cache import invalidate_all_caches
        invalidate_all_caches()
    except ImportError:
        pass


@pytest.fixture
def reset_config():
    """Reset global config for tests that need it."""
    try:
        from src.integrations.config import reset_config as do_reset
        do_reset()
    except ImportError:
        pass
    yield
    try:
        from src.integrations.config import reset_config as do_reset
        do_reset()
    except ImportError:
        pass


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("CLOSE_API_KEY", "test_api_key")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "/tmp/test_creds.json")
    monkeypatch.setenv("BENCHMARK_SHEET_ID", "test_sheet_id")
    yield
