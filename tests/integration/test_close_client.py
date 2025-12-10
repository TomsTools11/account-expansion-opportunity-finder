"""Integration tests for Close CRM client (using mocked responses)."""

import pytest
import responses
from responses import matchers

from src.integrations.close_client import (
    CloseAPIError,
    CloseAuthenticationError,
    CloseClient,
    CloseNotFoundError,
)
from src.integrations.config import CloseConfig
from src.models import AgencyType, PerformanceTier


@pytest.fixture
def close_config() -> CloseConfig:
    """Create test Close CRM configuration."""
    return CloseConfig(
        api_key="test_api_key_123",
        base_url="https://api.close.com/api/v1",
        rate_limit_per_second=100.0,  # High limit for tests
        max_retries=1,
        timeout_seconds=5,
    )


@pytest.fixture
def client(close_config: CloseConfig) -> CloseClient:
    """Create a Close client for testing."""
    return CloseClient(config=close_config)


@pytest.fixture
def sample_lead_response() -> dict:
    """Sample lead response from Close API."""
    return {
        "id": "lead_abc123xyz",
        "display_name": "John Smith Insurance Agency",
        "status_label": "Active",
        "contacts": [
            {
                "id": "cont_xyz",
                "emails": [{"email": "john@smithinsurance.com", "type": "office"}],
                "phones": [{"phone": "+1-555-123-4567", "type": "office"}],
            }
        ],
        "custom": {
            "cf_product_lines": ["Auto", "Home", "Life"],
            "cf_book_size": 75000.0,
            "cf_agent_tenure": 36,
            "cf_contact_rate": 52.5,
            "cf_quote_rate": 28.0,
            "cf_close_rate": 19.5,
            "cf_monthly_leads": 85,
            "cf_cac": 95.0,
            "cf_region": "Northeast",
            "cf_agency_type": "Independent",
            "cf_agent_tier": "Top 25%",
        },
    }


class TestCloseClientInit:
    """Tests for CloseClient initialization."""

    def test_init_with_config(self, close_config: CloseConfig):
        """Test client initialization with explicit config."""
        client = CloseClient(config=close_config)
        assert client is not None

    def test_init_without_config_fails(self, monkeypatch):
        """Test that init without config and env vars raises error."""
        # Clear any existing config
        monkeypatch.delenv("CLOSE_API_KEY", raising=False)

        # Reset the config singleton
        from src.integrations.config import reset_config
        reset_config()

        with pytest.raises(CloseAuthenticationError):
            CloseClient()


class TestCloseClientFetchAgent:
    """Tests for fetch_agent method."""

    @responses.activate
    def test_fetch_agent_success(
        self, client: CloseClient, sample_lead_response: dict
    ):
        """Test successful agent fetch."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc123xyz/",
            json=sample_lead_response,
            status=200,
        )

        agent = client.fetch_agent("lead_abc123xyz")

        assert agent.id == "lead_abc123xyz"
        assert agent.name == "John Smith Insurance Agency"
        assert agent.email == "john@smithinsurance.com"
        assert "Auto" in agent.current_products
        assert "Home" in agent.current_products
        assert agent.annual_premium_volume == 75000.0
        assert agent.tenure_months == 36
        assert agent.contact_rate == 52.5
        assert agent.performance_tier == PerformanceTier.TOP_25
        assert agent.agency_type == AgencyType.INDEPENDENT

    @responses.activate
    def test_fetch_agent_not_found(self, client: CloseClient):
        """Test agent not found error."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_nonexistent/",
            json={"error": "Not found"},
            status=404,
        )

        with pytest.raises(CloseNotFoundError):
            client.fetch_agent("lead_nonexistent")

    @responses.activate
    def test_fetch_agent_unauthorized(self, client: CloseClient):
        """Test authentication error."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc/",
            json={"error": "Unauthorized"},
            status=401,
        )

        with pytest.raises(CloseAuthenticationError):
            client.fetch_agent("lead_abc")

    @responses.activate
    def test_fetch_agent_uses_cache(
        self, client: CloseClient, sample_lead_response: dict
    ):
        """Test that cached results are returned on second call."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc123xyz/",
            json=sample_lead_response,
            status=200,
        )

        # First call - hits API
        agent1 = client.fetch_agent("lead_abc123xyz")

        # Second call - should use cache
        agent2 = client.fetch_agent("lead_abc123xyz")

        assert agent1.id == agent2.id
        assert len(responses.calls) == 1  # Only one API call made

    @responses.activate
    def test_fetch_agent_bypass_cache(
        self, client: CloseClient, sample_lead_response: dict
    ):
        """Test bypassing cache."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc123xyz/",
            json=sample_lead_response,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc123xyz/",
            json=sample_lead_response,
            status=200,
        )

        # First call
        client.fetch_agent("lead_abc123xyz", use_cache=False)

        # Second call with cache bypass
        client.fetch_agent("lead_abc123xyz", use_cache=False)

        assert len(responses.calls) == 2  # Two API calls made

    @responses.activate
    def test_fetch_agent_with_missing_custom_fields(self, client: CloseClient):
        """Test handling of missing custom fields."""
        response = {
            "id": "lead_minimal",
            "display_name": "Minimal Agent",
            "contacts": [],
            "custom": {},
        }
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_minimal/",
            json=response,
            status=200,
        )

        agent = client.fetch_agent("lead_minimal")

        assert agent.id == "lead_minimal"
        assert agent.name == "Minimal Agent"
        assert agent.current_products == []
        assert agent.annual_premium_volume == 0.0
        assert agent.contact_rate is None


class TestCloseClientSearchAgents:
    """Tests for search_agents method."""

    @responses.activate
    def test_search_agents_success(self, client: CloseClient, sample_lead_response: dict):
        """Test successful agent search."""
        search_response = {
            "data": [sample_lead_response, sample_lead_response.copy()],
            "has_more": False,
        }

        responses.add(
            responses.POST,
            "https://api.close.com/api/v1/data/search/",
            json=search_response,
            status=200,
        )

        agents = client.search_agents(query="status:active")

        assert len(agents) == 2
        assert agents[0].id == "lead_abc123xyz"

    @responses.activate
    def test_search_agents_empty_results(self, client: CloseClient):
        """Test search with no results."""
        responses.add(
            responses.POST,
            "https://api.close.com/api/v1/data/search/",
            json={"data": [], "has_more": False},
            status=200,
        )

        agents = client.search_agents(query="nonexistent")

        assert len(agents) == 0

    @responses.activate
    def test_search_agents_pagination(self, client: CloseClient, sample_lead_response: dict):
        """Test search with pagination parameters."""
        responses.add(
            responses.POST,
            "https://api.close.com/api/v1/data/search/",
            json={"data": [sample_lead_response], "has_more": False},
            status=200,
        )

        agents = client.search_agents(query="status:active", limit=50, skip=10)

        assert len(agents) == 1
        # Verify request body
        request_body = responses.calls[0].request.body
        assert b'"results_limit": 50' in request_body
        assert b'"skip": 10' in request_body


class TestCloseClientFetchAllAgents:
    """Tests for fetch_all_agents method."""

    @responses.activate
    def test_fetch_all_agents_single_batch(
        self, client: CloseClient, sample_lead_response: dict
    ):
        """Test fetching all agents in single batch."""
        responses.add(
            responses.POST,
            "https://api.close.com/api/v1/data/search/",
            json={"data": [sample_lead_response], "has_more": False},
            status=200,
        )

        agents = client.fetch_all_agents(max_agents=100)

        assert len(agents) == 1

    @responses.activate
    def test_fetch_all_agents_multiple_batches(
        self, client: CloseClient, sample_lead_response: dict
    ):
        """Test fetching all agents across multiple batches."""
        # First batch
        batch1 = [sample_lead_response.copy() for _ in range(3)]
        responses.add(
            responses.POST,
            "https://api.close.com/api/v1/data/search/",
            json={"data": batch1, "has_more": True},
            status=200,
        )

        # Second batch (fewer results indicates end)
        batch2 = [sample_lead_response.copy()]
        responses.add(
            responses.POST,
            "https://api.close.com/api/v1/data/search/",
            json={"data": batch2, "has_more": False},
            status=200,
        )

        agents = client.fetch_all_agents(max_agents=100, batch_size=3)

        assert len(agents) == 4


class TestCloseClientRateLimiting:
    """Tests for rate limiting behavior."""

    @responses.activate
    def test_rate_limit_retry(self, client: CloseClient, sample_lead_response: dict):
        """Test that rate limit errors trigger retry."""
        # First request returns 429
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc/",
            json={"error": "Rate limit exceeded"},
            status=429,
            headers={"Retry-After": "1"},
        )

        # Second request succeeds
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc/",
            json=sample_lead_response,
            status=200,
        )

        agent = client.fetch_agent("lead_abc")

        assert agent is not None
        assert len(responses.calls) == 2


class TestCloseClientTestConnection:
    """Tests for test_connection method."""

    @responses.activate
    def test_connection_success(self, client: CloseClient):
        """Test successful connection test."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/me/",
            json={"id": "user_123"},
            status=200,
        )

        assert client.test_connection() is True

    @responses.activate
    def test_connection_failure(self, client: CloseClient):
        """Test failed connection test."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/me/",
            json={"error": "Unauthorized"},
            status=401,
        )

        assert client.test_connection() is False


class TestCloseClientCacheManagement:
    """Tests for cache management methods."""

    @responses.activate
    def test_get_cache_stats(self, client: CloseClient, sample_lead_response: dict):
        """Test cache statistics retrieval."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc/",
            json=sample_lead_response,
            status=200,
        )

        client.fetch_agent("lead_abc")
        stats = client.get_cache_stats()

        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats

    @responses.activate
    def test_clear_cache(self, client: CloseClient, sample_lead_response: dict):
        """Test cache clearing."""
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc/",
            json=sample_lead_response,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.close.com/api/v1/lead/lead_abc/",
            json=sample_lead_response,
            status=200,
        )

        # Populate cache
        client.fetch_agent("lead_abc")

        # Clear cache
        client.clear_cache()

        # Next fetch should hit API again
        client.fetch_agent("lead_abc")

        assert len(responses.calls) == 2
