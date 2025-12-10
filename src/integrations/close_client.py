"""Close CRM API client for fetching agent data."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.models import Agent, AgencyType, PerformanceTier
from src.utils.cache import TTLCache, create_cache_key, get_agent_cache

from .config import CloseConfig, get_config

logger = logging.getLogger(__name__)


class CloseAPIError(Exception):
    """Base exception for Close API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class CloseRateLimitError(CloseAPIError):
    """Raised when rate limit is exceeded."""

    pass


class CloseAuthenticationError(CloseAPIError):
    """Raised when authentication fails."""

    pass


class CloseNotFoundError(CloseAPIError):
    """Raised when a resource is not found."""

    pass


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, max_per_second: float = 9.0):
        """Initialize rate limiter.

        Args:
            max_per_second: Maximum requests per second
        """
        self._rate = max_per_second
        self._tokens = max_per_second
        self._last_update = time.time()
        self._lock = None
        try:
            loop = asyncio.get_running_loop()
            self._lock = asyncio.Lock()
        except RuntimeError:
            # No running event loop, will use sync methods
            pass

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
        self._last_update = now

    def acquire_sync(self) -> None:
        """Synchronously acquire a token, blocking if necessary."""
        while True:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return
            time.sleep(0.1)

    async def acquire(self) -> None:
        """Asynchronously acquire a token, waiting if necessary."""
        while True:
            self._refill()
            if self._tokens >= 1:
                self._tokens -= 1
                return
            await asyncio.sleep(0.1)


class CloseClient:
    """Client for interacting with Close CRM API.

    Handles authentication, rate limiting, retries, and caching.
    """

    def __init__(self, config: Optional[CloseConfig] = None):
        """Initialize Close CRM client.

        Args:
            config: Optional CloseConfig, loads from environment if not provided
        """
        if config is None:
            app_config = get_config()
            if app_config.close is None:
                raise CloseAuthenticationError(
                    "Close CRM not configured. Set CLOSE_API_KEY environment variable."
                )
            config = app_config.close

        self._config = config
        self._session = self._create_session()
        self._rate_limiter = RateLimiter(config.rate_limit_per_second)
        self._cache: TTLCache[Any] = get_agent_cache()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()

        # Configure retries for transient errors
        retry_strategy = Retry(
            total=self._config.max_retries,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set authentication header
        session.auth = (self._config.api_key, "")

        return session

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Make an API request with rate limiting and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body data

        Returns:
            JSON response data

        Raises:
            CloseAPIError: On API errors
        """
        # Apply rate limiting
        self._rate_limiter.acquire_sync()

        url = f"{self._config.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self._config.timeout_seconds,
            )

            # Handle specific error codes
            if response.status_code == 401:
                raise CloseAuthenticationError(
                    "Invalid Close CRM API key", status_code=401
                )
            elif response.status_code == 404:
                raise CloseNotFoundError(
                    f"Resource not found: {endpoint}", status_code=404
                )
            elif response.status_code == 429:
                # Rate limit - wait and retry
                retry_after = int(response.headers.get("Retry-After", 5))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                return self._make_request(method, endpoint, params, json_data)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Close API request failed: {e}")
            raise CloseAPIError(f"Request failed: {e}")

    def _extract_custom_field(
        self, data: dict[str, Any], field_path: str
    ) -> Optional[Any]:
        """Extract a value from nested custom fields.

        Args:
            data: API response data
            field_path: Dot-notation field path (e.g., "custom.cf_field")

        Returns:
            Field value or None
        """
        parts = field_path.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def _parse_agent_data(self, lead_data: dict[str, Any]) -> Agent:
        """Parse Close CRM lead data into an Agent model.

        Args:
            lead_data: Raw lead data from Close API

        Returns:
            Agent model instance
        """
        field_map = self._config.field_map

        # Extract basic identity
        agent_id = lead_data.get("id", "")
        name = lead_data.get("display_name", "Unknown")

        # Extract contact info
        contacts = lead_data.get("contacts", [])
        email = None
        phone = None
        if contacts:
            first_contact = contacts[0]
            emails = first_contact.get("emails", [])
            phones = first_contact.get("phones", [])
            email = emails[0].get("email") if emails else None
            phone = phones[0].get("phone") if phones else None

        # Extract custom fields
        products_raw = self._extract_custom_field(lead_data, field_map["current_products"])
        current_products = products_raw if isinstance(products_raw, list) else []

        annual_premium = self._extract_custom_field(
            lead_data, field_map["annual_premium_volume"]
        )
        tenure = self._extract_custom_field(lead_data, field_map["tenure_months"])
        contact_rate = self._extract_custom_field(lead_data, field_map["contact_rate"])
        quote_rate = self._extract_custom_field(lead_data, field_map["quote_rate"])
        close_rate = self._extract_custom_field(lead_data, field_map["close_rate"])
        lead_volume = self._extract_custom_field(
            lead_data, field_map["monthly_lead_volume"]
        )
        cac = self._extract_custom_field(lead_data, field_map["cost_per_acquisition"])
        region = self._extract_custom_field(lead_data, field_map["region"])
        agency_type_str = self._extract_custom_field(lead_data, field_map["agency_type"])
        tier_str = self._extract_custom_field(lead_data, field_map["performance_tier"])

        # Parse agency type
        agency_type = None
        if agency_type_str:
            try:
                agency_type = AgencyType(agency_type_str)
            except ValueError:
                pass

        # Parse performance tier
        performance_tier = None
        if tier_str:
            try:
                performance_tier = PerformanceTier(tier_str)
            except ValueError:
                pass

        return Agent(
            id=agent_id,
            name=name,
            email=email,
            phone=phone,
            current_products=current_products,
            annual_premium_volume=float(annual_premium) if annual_premium else 0.0,
            tenure_months=int(tenure) if tenure else 0,
            region=region,
            agency_type=agency_type,
            contact_rate=float(contact_rate) if contact_rate else None,
            quote_rate=float(quote_rate) if quote_rate else None,
            close_rate=float(close_rate) if close_rate else None,
            monthly_lead_volume=int(lead_volume) if lead_volume else None,
            cost_per_acquisition=float(cac) if cac else None,
            performance_tier=performance_tier,
            last_updated=datetime.utcnow(),
        )

    def fetch_agent(self, lead_id: str, use_cache: bool = True) -> Agent:
        """Fetch a single agent by Close CRM lead ID.

        Args:
            lead_id: Close CRM lead ID (e.g., "lead_xyz789")
            use_cache: Whether to use cached data if available

        Returns:
            Agent model instance

        Raises:
            CloseNotFoundError: If agent not found
            CloseAPIError: On other API errors
        """
        cache_key = create_cache_key("agent", lead_id)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for agent {lead_id}")
                return cached

        logger.debug(f"Fetching agent {lead_id} from Close CRM")
        lead_data = self._make_request("GET", f"lead/{lead_id}/")

        agent = self._parse_agent_data(lead_data)
        self._cache.set(cache_key, agent)

        return agent

    def search_agents(
        self,
        query: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
        use_cache: bool = True,
    ) -> list[Agent]:
        """Search for agents using Close CRM search API.

        Args:
            query: Close CRM query string (e.g., "status:active")
            limit: Maximum results to return (max 200)
            skip: Number of results to skip (for pagination)
            use_cache: Whether to use cached data

        Returns:
            List of Agent models
        """
        # Build search query
        search_query = query or "lead_status_label:Active"

        cache_key = create_cache_key("search", search_query, str(limit), str(skip))

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for search query")
                return cached

        logger.debug(f"Searching agents with query: {search_query}")

        # Use the search endpoint
        response = self._make_request(
            "POST",
            "data/search/",
            json_data={
                "query": {"type": "and", "queries": [{"type": "query_string", "value": search_query}]},
                "results_limit": min(limit, 200),
                "skip": skip,
                "include_smart_views_counts": False,
            },
        )

        agents = []
        for lead_data in response.get("data", []):
            try:
                agent = self._parse_agent_data(lead_data)
                agents.append(agent)
            except Exception as e:
                logger.warning(f"Failed to parse agent data: {e}")
                continue

        self._cache.set(cache_key, agents)
        return agents

    def fetch_all_agents(
        self,
        query: Optional[str] = None,
        max_agents: int = 1000,
        batch_size: int = 100,
    ) -> list[Agent]:
        """Fetch all agents matching a query with pagination.

        Args:
            query: Close CRM query string
            max_agents: Maximum total agents to fetch
            batch_size: Number of agents per request

        Returns:
            List of all matching Agent models
        """
        all_agents: list[Agent] = []
        skip = 0

        while len(all_agents) < max_agents:
            batch = self.search_agents(
                query=query,
                limit=min(batch_size, max_agents - len(all_agents)),
                skip=skip,
                use_cache=False,  # Don't cache paginated results
            )

            if not batch:
                break

            all_agents.extend(batch)
            skip += len(batch)

            if len(batch) < batch_size:
                break

        logger.info(f"Fetched {len(all_agents)} agents total")
        return all_agents

    def test_connection(self) -> bool:
        """Test the API connection.

        Returns:
            True if connection is successful
        """
        try:
            self._make_request("GET", "me/")
            return True
        except CloseAPIError:
            return False

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache stats dictionary
        """
        return self._cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the agent cache."""
        self._cache.clear()
