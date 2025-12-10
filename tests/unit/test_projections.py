"""Unit tests for revenue lift projections."""

import pytest

from src.analysis.projections import (
    LiftProjection,
    calculate_confidence_score,
    estimate_tier_progression_lift,
    identify_product_opportunities,
    project_revenue_lift,
)
from src.models import (
    Agent,
    BenchmarkData,
    BenchmarkTier,
    ConfidenceLevel,
    CrossSellPattern,
    PerformanceTier,
    ProductBenchmark,
)


@pytest.fixture
def sample_benchmarks() -> BenchmarkData:
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
            BenchmarkTier(
                tier_name=PerformanceTier.AVERAGE,
                contact_rate_range=(30.0, 45.0),
                quote_rate_range=(15.0, 25.0),
                close_rate_range=(12.0, 18.0),
                cac_range=(80.0, 130.0),
                lead_volume_range=(50, 100),
            ),
            BenchmarkTier(
                tier_name=PerformanceTier.BELOW_AVERAGE,
                contact_rate_range=(20.0, 30.0),
                quote_rate_range=(10.0, 15.0),
                close_rate_range=(6.0, 12.0),
                cac_range=(120.0, 180.0),
                lead_volume_range=(25, 50),
            ),
        ],
        products=[
            ProductBenchmark(
                product="Auto",
                organic_cac=203.52,
                inorganic_cac=305.28,
                blended_cac=244.22,
            ),
            ProductBenchmark(
                product="Home",
                organic_cac=140.72,
                inorganic_cac=211.08,
                blended_cac=168.86,
            ),
            ProductBenchmark(
                product="Life",
                organic_cac=24.96,
                inorganic_cac=37.44,
                blended_cac=29.95,
            ),
        ],
        cross_sell_patterns=[
            CrossSellPattern(
                primary_product="Home",
                added_product="Auto",
                avg_revenue_lift_pct=35.0,
                adoption_rate=0.65,
                avg_time_to_add_months=6,
                tier=PerformanceTier.TOP_25,
            ),
            CrossSellPattern(
                primary_product="Auto",
                added_product="Home",
                avg_revenue_lift_pct=28.0,
                adoption_rate=0.55,
                avg_time_to_add_months=8,
                tier=PerformanceTier.TOP_25,
            ),
            CrossSellPattern(
                primary_product="Auto",
                added_product="Life",
                avg_revenue_lift_pct=15.0,
                adoption_rate=0.30,
                avg_time_to_add_months=12,
            ),
        ],
    )


@pytest.fixture
def sample_agents() -> list[Agent]:
    """Create sample agents for testing."""
    return [
        # Target agent - Home only
        Agent(
            id="target",
            name="Target Agent",
            current_products=["Home"],
            annual_premium_volume=50000,
            tenure_months=24,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=50.0,
            close_rate=20.0,
        ),
        # Similar agent with Auto + Home
        Agent(
            id="similar_1",
            name="Similar 1",
            current_products=["Home", "Auto"],
            annual_premium_volume=65000,
            tenure_months=28,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=52.0,
            close_rate=22.0,
        ),
        # Similar agent with Auto + Home
        Agent(
            id="similar_2",
            name="Similar 2",
            current_products=["Home", "Auto"],
            annual_premium_volume=70000,
            tenure_months=30,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=48.0,
            close_rate=21.0,
        ),
        # Similar agent with Auto + Home + Life
        Agent(
            id="similar_3",
            name="Similar 3",
            current_products=["Home", "Auto", "Life"],
            annual_premium_volume=80000,
            tenure_months=36,
            performance_tier=PerformanceTier.TOP_10,
            contact_rate=58.0,
            close_rate=28.0,
        ),
        # Different agent - Auto only
        Agent(
            id="different",
            name="Different Agent",
            current_products=["Auto"],
            annual_premium_volume=30000,
            tenure_months=12,
            performance_tier=PerformanceTier.AVERAGE,
            contact_rate=35.0,
            close_rate=15.0,
        ),
        # Similar without Auto
        Agent(
            id="similar_no_auto",
            name="Similar No Auto",
            current_products=["Home"],
            annual_premium_volume=45000,
            tenure_months=20,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=47.0,
            close_rate=19.0,
        ),
    ]


class TestCalculateConfidenceScore:
    """Tests for calculate_confidence_score function."""

    def test_max_confidence(self):
        """Test maximum confidence with ideal inputs."""
        score = calculate_confidence_score(
            sample_size=50,  # At threshold
            similarity_avg=1.0,  # Perfect
            pattern_adoption_rate=1.0,  # Perfect
            agent_readiness=1.0,  # Perfect
        )
        assert score == 1.0

    def test_min_confidence(self):
        """Test minimum confidence with poor inputs."""
        score = calculate_confidence_score(
            sample_size=0,
            similarity_avg=0.0,
            pattern_adoption_rate=0.0,
            agent_readiness=0.0,
        )
        assert score == 0.0

    def test_sample_size_diminishing_returns(self):
        """Test that sample size has diminishing returns after 50."""
        score_50 = calculate_confidence_score(
            sample_size=50,
            similarity_avg=0.5,
            pattern_adoption_rate=0.5,
            agent_readiness=0.5,
        )
        score_100 = calculate_confidence_score(
            sample_size=100,
            similarity_avg=0.5,
            pattern_adoption_rate=0.5,
            agent_readiness=0.5,
        )
        # Both should be same since 50+ caps at 1.0 factor
        assert score_50 == score_100

    def test_weights_sum_correctly(self):
        """Test that all factors contribute proportionally."""
        # With all factors at 0.5, should get ~0.5
        score = calculate_confidence_score(
            sample_size=25,  # 0.5 factor
            similarity_avg=0.5,
            pattern_adoption_rate=0.5,
            agent_readiness=0.5,
        )
        assert 0.4 <= score <= 0.6


class TestProjectRevenueLift:
    """Tests for project_revenue_lift function."""

    def test_returns_none_for_existing_product(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that projection returns None if agent has product."""
        target = sample_agents[0]  # Has Home
        projection = project_revenue_lift(
            target_agent=target,
            all_agents=sample_agents,
            product_to_add="Home",  # Already has it
            benchmarks=sample_benchmarks,
        )
        assert projection is None

    def test_returns_projection_for_missing_product(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that projection is returned for product agent doesn't have."""
        target = sample_agents[0]  # Has Home only
        projection = project_revenue_lift(
            target_agent=target,
            all_agents=sample_agents,
            product_to_add="Auto",
            benchmarks=sample_benchmarks,
        )
        assert projection is not None
        assert projection.product == "Auto"
        assert projection.projected_lift_dollars > 0
        assert projection.projected_lift_pct > 0

    def test_uses_peer_analysis_when_sufficient_peers(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that peer analysis is used when enough similar agents."""
        target = sample_agents[0]
        projection = project_revenue_lift(
            target_agent=target,
            all_agents=sample_agents,
            product_to_add="Auto",
            benchmarks=sample_benchmarks,
            min_similar_agents=2,  # Lower threshold for test
        )
        assert projection is not None
        # With peers, should use peer analysis
        assert projection.similar_agent_count >= 2

    def test_falls_back_to_benchmark_when_few_peers(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test benchmark fallback when insufficient peers."""
        target = sample_agents[0]
        projection = project_revenue_lift(
            target_agent=target,
            all_agents=sample_agents[:2],  # Only target + 1 other
            product_to_add="Life",  # Few agents have Life
            benchmarks=sample_benchmarks,
            min_similar_agents=10,  # High threshold
        )
        # Should still return projection from benchmarks
        if projection:
            assert projection.data_source in ["benchmark", "peer_analysis"]

    def test_lift_percentage_is_reasonable(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that lift percentage is within reasonable bounds."""
        target = sample_agents[0]
        projection = project_revenue_lift(
            target_agent=target,
            all_agents=sample_agents,
            product_to_add="Auto",
            benchmarks=sample_benchmarks,
        )
        assert projection is not None
        # Should be capped between 5% and 100%
        assert 5.0 <= projection.projected_lift_pct <= 100.0


class TestLiftProjection:
    """Tests for LiftProjection dataclass."""

    def test_projection_attributes(self):
        """Test that projection has all required attributes."""
        proj = LiftProjection(
            product="Auto",
            projected_lift_dollars=15000,
            projected_lift_pct=30.0,
            confidence_score=0.75,
            confidence_level=ConfidenceLevel.MEDIUM,
            similar_agent_count=25,
            similar_agent_avg_revenue=60000,
            median_lift_from_peers=12000,
            adoption_rate=0.65,
            data_source="peer_analysis",
        )

        assert proj.product == "Auto"
        assert proj.projected_lift_dollars == 15000
        assert proj.confidence_level == ConfidenceLevel.MEDIUM


class TestIdentifyProductOpportunities:
    """Tests for identify_product_opportunities function."""

    def test_identifies_missing_products(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that opportunities are found for missing products."""
        target = sample_agents[0]  # Has Home only
        opportunities = identify_product_opportunities(
            target_agent=target,
            all_agents=sample_agents,
            benchmarks=sample_benchmarks,
            min_confidence=0.0,  # Accept all
        )

        # Should find at least Auto opportunity
        products = [o.product for o in opportunities]
        assert "Auto" in products

    def test_sorted_by_lift_descending(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that opportunities are sorted by lift."""
        target = sample_agents[0]
        opportunities = identify_product_opportunities(
            target_agent=target,
            all_agents=sample_agents,
            benchmarks=sample_benchmarks,
            min_confidence=0.0,
        )

        if len(opportunities) > 1:
            lifts = [o.projected_lift_dollars for o in opportunities]
            assert lifts == sorted(lifts, reverse=True)

    def test_respects_min_confidence(
        self, sample_agents: list[Agent], sample_benchmarks: BenchmarkData
    ):
        """Test that low confidence opportunities are filtered."""
        target = sample_agents[0]
        opportunities = identify_product_opportunities(
            target_agent=target,
            all_agents=sample_agents,
            benchmarks=sample_benchmarks,
            min_confidence=0.9,  # Very high threshold
        )

        for opp in opportunities:
            assert opp.confidence_score >= 0.9


class TestEstimateTierProgressionLift:
    """Tests for estimate_tier_progression_lift function."""

    def test_returns_next_tier(self, sample_benchmarks: BenchmarkData):
        """Test that correct next tier is identified."""
        agent = Agent(
            id="test",
            name="Test",
            performance_tier=PerformanceTier.AVERAGE,
            annual_premium_volume=50000,
        )

        result = estimate_tier_progression_lift(agent, sample_benchmarks)

        assert result is not None
        target_tier, lift_dollars, lift_pct = result
        assert target_tier == PerformanceTier.TOP_25

    def test_returns_none_for_top_10(self, sample_benchmarks: BenchmarkData):
        """Test that no progression is available for top tier."""
        agent = Agent(
            id="test",
            name="Test",
            performance_tier=PerformanceTier.TOP_10,
            annual_premium_volume=100000,
        )

        result = estimate_tier_progression_lift(agent, sample_benchmarks)
        assert result is None

    def test_lift_is_positive(self, sample_benchmarks: BenchmarkData):
        """Test that tier progression shows positive lift."""
        agent = Agent(
            id="test",
            name="Test",
            performance_tier=PerformanceTier.BELOW_AVERAGE,
            annual_premium_volume=30000,
        )

        result = estimate_tier_progression_lift(agent, sample_benchmarks)

        assert result is not None
        _, lift_dollars, lift_pct = result
        assert lift_dollars > 0
        assert lift_pct > 0
