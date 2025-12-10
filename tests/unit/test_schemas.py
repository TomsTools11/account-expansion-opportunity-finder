"""Unit tests for Pydantic schemas and models."""

from datetime import datetime, timedelta

import pytest

from src.models import (
    Agent,
    AgencyType,
    AnalysisFilters,
    BenchmarkData,
    BenchmarkTier,
    ConfidenceLevel,
    CrossSellPattern,
    ExpansionOpportunity,
    OpportunityType,
    PerformanceTier,
    ProductBenchmark,
    ProductType,
)


class TestProductType:
    """Tests for ProductType enum."""

    def test_values_returns_all_products(self):
        """Test that values() returns all product names."""
        values = ProductType.values()
        assert "Auto" in values
        assert "Home" in values
        assert "Life" in values
        assert len(values) == 8


class TestPerformanceTier:
    """Tests for PerformanceTier enum."""

    def test_from_percentile_top_10(self):
        """Test tier assignment for top 10%."""
        assert PerformanceTier.from_percentile(95) == PerformanceTier.TOP_10
        assert PerformanceTier.from_percentile(90) == PerformanceTier.TOP_10

    def test_from_percentile_top_25(self):
        """Test tier assignment for top 25%."""
        assert PerformanceTier.from_percentile(85) == PerformanceTier.TOP_25
        assert PerformanceTier.from_percentile(75) == PerformanceTier.TOP_25

    def test_from_percentile_average(self):
        """Test tier assignment for average."""
        assert PerformanceTier.from_percentile(50) == PerformanceTier.AVERAGE
        assert PerformanceTier.from_percentile(25) == PerformanceTier.AVERAGE

    def test_from_percentile_below_average(self):
        """Test tier assignment for below average."""
        assert PerformanceTier.from_percentile(20) == PerformanceTier.BELOW_AVERAGE
        assert PerformanceTier.from_percentile(10) == PerformanceTier.BELOW_AVERAGE

    def test_from_percentile_bottom_10(self):
        """Test tier assignment for bottom 10%."""
        assert PerformanceTier.from_percentile(5) == PerformanceTier.BOTTOM_10
        assert PerformanceTier.from_percentile(0) == PerformanceTier.BOTTOM_10

    def test_ordinal_ordering(self):
        """Test that ordinal values are correctly ordered."""
        assert PerformanceTier.TOP_10.ordinal > PerformanceTier.TOP_25.ordinal
        assert PerformanceTier.TOP_25.ordinal > PerformanceTier.AVERAGE.ordinal
        assert PerformanceTier.AVERAGE.ordinal > PerformanceTier.BELOW_AVERAGE.ordinal
        assert PerformanceTier.BELOW_AVERAGE.ordinal > PerformanceTier.BOTTOM_10.ordinal


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_from_score_high(self):
        """Test high confidence classification."""
        assert ConfidenceLevel.from_score(0.80) == ConfidenceLevel.HIGH
        assert ConfidenceLevel.from_score(0.76) == ConfidenceLevel.HIGH

    def test_from_score_medium(self):
        """Test medium confidence classification."""
        assert ConfidenceLevel.from_score(0.70) == ConfidenceLevel.MEDIUM
        assert ConfidenceLevel.from_score(0.56) == ConfidenceLevel.MEDIUM

    def test_from_score_low(self):
        """Test low confidence classification."""
        assert ConfidenceLevel.from_score(0.50) == ConfidenceLevel.LOW
        assert ConfidenceLevel.from_score(0.01) == ConfidenceLevel.LOW

    def test_from_score_insufficient(self):
        """Test insufficient data classification."""
        assert ConfidenceLevel.from_score(0.0) == ConfidenceLevel.INSUFFICIENT_DATA
        assert ConfidenceLevel.from_score(-0.1) == ConfidenceLevel.INSUFFICIENT_DATA


class TestAgent:
    """Tests for Agent model."""

    @pytest.fixture
    def sample_agent(self) -> Agent:
        """Create a sample agent for testing."""
        return Agent(
            id="lead_abc123",
            name="John Smith",
            email="john@example.com",
            phone="555-1234",
            current_products=["Auto", "Home"],
            annual_premium_volume=50000.0,
            tenure_months=24,
            region="Northeast",
            agency_type=AgencyType.INDEPENDENT,
            contact_rate=55.0,
            quote_rate=30.0,
            close_rate=20.0,
            monthly_lead_volume=100,
            cost_per_acquisition=80.0,
            performance_tier=PerformanceTier.TOP_25,
        )

    def test_agent_creation(self, sample_agent: Agent):
        """Test agent model creation."""
        assert sample_agent.id == "lead_abc123"
        assert sample_agent.name == "John Smith"
        assert len(sample_agent.current_products) == 2

    def test_product_vector(self, sample_agent: Agent):
        """Test product vector generation."""
        vector = sample_agent.product_vector
        assert len(vector) == 8  # Number of product types
        assert vector[0] == 1.0  # Auto
        assert vector[1] == 1.0  # Home
        assert vector[2] == 0.0  # Life (not present)

    def test_data_completeness_score(self, sample_agent: Agent):
        """Test data completeness calculation."""
        assert sample_agent.data_completeness_score == 100.0

    def test_data_completeness_score_partial(self):
        """Test data completeness with missing fields."""
        agent = Agent(
            id="lead_xyz",
            name="Jane Doe",
            current_products=["Auto"],
            annual_premium_volume=30000.0,
            # Missing: tenure_months, contact_rate, quote_rate, close_rate, monthly_lead_volume
        )
        # 3 out of 7 fields filled
        assert agent.data_completeness_score == pytest.approx(42.86, rel=0.1)

    def test_has_minimum_data(self, sample_agent: Agent):
        """Test minimum data check."""
        assert sample_agent.has_minimum_data(60.0) is True

    def test_has_minimum_data_fails(self):
        """Test minimum data check fails with incomplete data."""
        agent = Agent(id="lead_xyz", name="Jane Doe")
        assert agent.has_minimum_data(60.0) is False

    def test_get_missing_fields(self):
        """Test missing fields detection."""
        agent = Agent(
            id="lead_xyz",
            name="Jane Doe",
            current_products=["Auto"],
        )
        missing = agent.get_missing_fields()
        assert "annual_premium_volume" in missing
        assert "tenure_months" in missing
        assert "contact_rate" in missing

    def test_primary_product(self, sample_agent: Agent):
        """Test primary product derivation."""
        assert sample_agent.primary_product == "Auto"

    def test_primary_product_none(self):
        """Test primary product when no products."""
        agent = Agent(id="lead_xyz", name="Jane Doe")
        assert agent.primary_product is None

    def test_product_validation(self):
        """Test that invalid products are filtered out."""
        agent = Agent(
            id="lead_xyz",
            name="Jane Doe",
            current_products=["Auto", "InvalidProduct", "Home"],
        )
        assert "Auto" in agent.current_products
        assert "Home" in agent.current_products
        assert "InvalidProduct" not in agent.current_products


class TestBenchmarkTier:
    """Tests for BenchmarkTier model."""

    @pytest.fixture
    def top_25_tier(self) -> BenchmarkTier:
        """Create a sample benchmark tier."""
        return BenchmarkTier(
            tier_name=PerformanceTier.TOP_25,
            contact_rate_range=(45.0, 55.0),
            quote_rate_range=(25.0, 35.0),
            close_rate_range=(18.0, 25.0),
            cac_range=(50.0, 90.0),
            lead_volume_range=(100, 150),
        )

    def test_agent_fits_tier(self, top_25_tier: BenchmarkTier):
        """Test agent tier matching."""
        agent = Agent(
            id="lead_xyz",
            name="Test Agent",
            contact_rate=50.0,
            close_rate=22.0,
        )
        assert top_25_tier.agent_fits_tier(agent) is True

    def test_agent_does_not_fit_tier(self, top_25_tier: BenchmarkTier):
        """Test agent tier non-matching."""
        agent = Agent(
            id="lead_xyz",
            name="Test Agent",
            contact_rate=30.0,  # Too low
            close_rate=22.0,
        )
        assert top_25_tier.agent_fits_tier(agent) is False


class TestBenchmarkData:
    """Tests for BenchmarkData model."""

    @pytest.fixture
    def benchmark_data(self) -> BenchmarkData:
        """Create sample benchmark data."""
        return BenchmarkData(
            tiers=[
                BenchmarkTier(
                    tier_name=PerformanceTier.TOP_10,
                    contact_rate_range=(55.0, 70.0),
                    quote_rate_range=(35.0, 50.0),
                    close_rate_range=(25.0, 40.0),
                    cac_range=(25.0, 60.0),
                    lead_volume_range=(150, 300),
                ),
                BenchmarkTier(
                    tier_name=PerformanceTier.TOP_25,
                    contact_rate_range=(45.0, 55.0),
                    quote_rate_range=(25.0, 35.0),
                    close_rate_range=(18.0, 25.0),
                    cac_range=(50.0, 90.0),
                    lead_volume_range=(100, 150),
                ),
            ],
            products=[
                ProductBenchmark(
                    product="Auto",
                    organic_cac=203.52,
                    inorganic_cac=305.28,
                    blended_cac=244.22,
                    source="Focus Digital 2024",
                ),
            ],
            cross_sell_patterns=[
                CrossSellPattern(
                    primary_product="Home",
                    added_product="Auto",
                    avg_revenue_lift_pct=35.2,
                    adoption_rate=0.68,
                    avg_time_to_add_months=6,
                    tier=PerformanceTier.TOP_25,
                ),
            ],
        )

    def test_get_tier_by_name(self, benchmark_data: BenchmarkData):
        """Test tier lookup by name."""
        tier = benchmark_data.get_tier_by_name(PerformanceTier.TOP_25)
        assert tier is not None
        assert tier.contact_rate_range == (45.0, 55.0)

    def test_get_tier_by_name_not_found(self, benchmark_data: BenchmarkData):
        """Test tier lookup with non-existent tier."""
        tier = benchmark_data.get_tier_by_name(PerformanceTier.BOTTOM_10)
        assert tier is None

    def test_get_product_benchmark(self, benchmark_data: BenchmarkData):
        """Test product benchmark lookup."""
        product = benchmark_data.get_product_benchmark("Auto")
        assert product is not None
        assert product.blended_cac == 244.22

    def test_get_cross_sell_pattern(self, benchmark_data: BenchmarkData):
        """Test cross-sell pattern lookup."""
        pattern = benchmark_data.get_cross_sell_pattern("Home", "Auto")
        assert pattern is not None
        assert pattern.avg_revenue_lift_pct == 35.2

    def test_get_tier_avg_contact_rate(self, benchmark_data: BenchmarkData):
        """Test tier average contact rate calculation."""
        avg = benchmark_data.get_tier_avg_contact_rate(PerformanceTier.TOP_25)
        assert avg == 50.0  # (45 + 55) / 2

    def test_get_tier_avg_close_rate(self, benchmark_data: BenchmarkData):
        """Test tier average close rate calculation."""
        avg = benchmark_data.get_tier_avg_close_rate(PerformanceTier.TOP_25)
        assert avg == 21.5  # (18 + 25) / 2


class TestExpansionOpportunity:
    """Tests for ExpansionOpportunity model."""

    @pytest.fixture
    def opportunity(self) -> ExpansionOpportunity:
        """Create a sample opportunity."""
        return ExpansionOpportunity(
            agent_id="lead_abc123",
            agent_name="John Smith",
            opportunity_type=OpportunityType.ADD_PRODUCT,
            message="Consider adding Auto insurance to your portfolio.",
            recommended_product="Auto",
            projected_revenue_lift=15800.0,
            projected_lift_pct=35.1,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_score=0.82,
            priority_score=87,
            similar_agent_count=47,
            similar_agent_avg_revenue=60800.0,
            agent_current_tier=PerformanceTier.AVERAGE,
            agent_target_tier=PerformanceTier.TOP_25,
            readiness_indicators=["Strong contact rate", "High tenure"],
            barriers=["Low lead volume"],
        )

    def test_opportunity_creation(self, opportunity: ExpansionOpportunity):
        """Test opportunity model creation."""
        assert opportunity.agent_id == "lead_abc123"
        assert opportunity.priority_score == 87
        assert opportunity.opportunity_id.startswith("opp_")

    def test_opportunity_expires_at(self, opportunity: ExpansionOpportunity):
        """Test that expires_at is set to 30 days from generation."""
        assert opportunity.expires_at is not None
        delta = opportunity.expires_at - opportunity.generated_at
        assert delta.days == 30

    def test_is_expired(self, opportunity: ExpansionOpportunity):
        """Test expiration check."""
        assert opportunity.is_expired() is False

    def test_is_expired_true(self):
        """Test expiration check with expired opportunity."""
        opp = ExpansionOpportunity(
            agent_id="lead_xyz",
            agent_name="Test",
            opportunity_type=OpportunityType.ADD_PRODUCT,
            message="Test",
            projected_revenue_lift=1000.0,
            projected_lift_pct=10.0,
            confidence_level=ConfidenceLevel.LOW,
            confidence_score=0.3,
            priority_score=30,
            similar_agent_count=5,
            similar_agent_avg_revenue=20000.0,
            agent_current_tier=PerformanceTier.AVERAGE,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        assert opp.is_expired() is True

    def test_is_high_priority(self, opportunity: ExpansionOpportunity):
        """Test high priority check."""
        assert opportunity.is_high_priority() is True

    def test_is_high_priority_false(self):
        """Test high priority check with low score."""
        opp = ExpansionOpportunity(
            agent_id="lead_xyz",
            agent_name="Test",
            opportunity_type=OpportunityType.ADD_PRODUCT,
            message="Test",
            projected_revenue_lift=1000.0,
            projected_lift_pct=10.0,
            confidence_level=ConfidenceLevel.LOW,
            confidence_score=0.3,
            priority_score=50,
            similar_agent_count=5,
            similar_agent_avg_revenue=20000.0,
            agent_current_tier=PerformanceTier.AVERAGE,
        )
        assert opp.is_high_priority() is False


class TestAnalysisFilters:
    """Tests for AnalysisFilters model."""

    def test_matches_all_filters(self):
        """Test filter matching with all criteria."""
        filters = AnalysisFilters(
            min_tenure_months=12,
            min_book_size=30000,
            regions=["Northeast"],
            current_tiers=[PerformanceTier.AVERAGE, PerformanceTier.TOP_25],
        )
        agent = Agent(
            id="lead_xyz",
            name="Test Agent",
            tenure_months=24,
            annual_premium_volume=50000,
            region="Northeast",
            performance_tier=PerformanceTier.TOP_25,
        )
        assert filters.matches(agent) is True

    def test_matches_fails_tenure(self):
        """Test filter matching fails on tenure."""
        filters = AnalysisFilters(min_tenure_months=24)
        agent = Agent(id="lead_xyz", name="Test Agent", tenure_months=12)
        assert filters.matches(agent) is False

    def test_matches_fails_region(self):
        """Test filter matching fails on region."""
        filters = AnalysisFilters(regions=["Northeast", "Southeast"])
        agent = Agent(id="lead_xyz", name="Test Agent", region="West")
        assert filters.matches(agent) is False

    def test_matches_empty_filters(self):
        """Test that empty filters match all agents."""
        filters = AnalysisFilters()
        agent = Agent(id="lead_xyz", name="Test Agent")
        assert filters.matches(agent) is True
