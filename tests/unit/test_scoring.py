"""Unit tests for opportunity scoring and readiness assessment."""

import pytest

from src.analysis.projections import LiftProjection
from src.analysis.scoring import (
    ReadinessAssessment,
    assess_readiness,
    generate_opportunity_message,
    get_score_interpretation,
    get_tier_avg_close_rate,
    get_tier_avg_contact_rate,
    get_tier_avg_lead_volume,
    rank_opportunities,
    score_opportunity,
)
from src.models import (
    Agent,
    BenchmarkData,
    BenchmarkTier,
    ConfidenceLevel,
    PerformanceTier,
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
        ],
        products=[],
        cross_sell_patterns=[],
    )


@pytest.fixture
def high_performing_agent() -> Agent:
    """Create a high-performing agent."""
    return Agent(
        id="high_perf",
        name="High Performer",
        current_products=["Auto", "Home"],
        annual_premium_volume=75000,
        tenure_months=36,
        performance_tier=PerformanceTier.TOP_25,
        contact_rate=55.0,  # Above tier average
        quote_rate=30.0,
        close_rate=23.0,  # Above tier average
        monthly_lead_volume=130,  # Above tier average
        cost_per_acquisition=70.0,
    )


@pytest.fixture
def low_performing_agent() -> Agent:
    """Create a low-performing agent."""
    return Agent(
        id="low_perf",
        name="Low Performer",
        current_products=["Auto"],
        annual_premium_volume=15000,
        tenure_months=6,
        performance_tier=PerformanceTier.AVERAGE,
        contact_rate=25.0,  # Below average
        quote_rate=12.0,
        close_rate=10.0,  # Below average
        monthly_lead_volume=40,  # Below average
        cost_per_acquisition=120.0,
    )


@pytest.fixture
def sample_projection() -> LiftProjection:
    """Create a sample lift projection."""
    return LiftProjection(
        product="Life",
        projected_lift_dollars=15000,
        projected_lift_pct=30.0,
        confidence_score=0.75,
        confidence_level=ConfidenceLevel.MEDIUM,
        similar_agent_count=25,
        similar_agent_avg_revenue=60000,
        median_lift_from_peers=12000,
        adoption_rate=0.55,
        data_source="peer_analysis",
    )


class TestTierAverageHelpers:
    """Tests for tier average helper functions."""

    def test_get_tier_avg_contact_rate_with_benchmarks(
        self, sample_benchmarks: BenchmarkData
    ):
        """Test contact rate retrieval from benchmarks."""
        avg = get_tier_avg_contact_rate(PerformanceTier.TOP_25, sample_benchmarks)
        # (45 + 55) / 2 = 50
        assert avg == 50.0

    def test_get_tier_avg_contact_rate_without_benchmarks(self):
        """Test contact rate fallback without benchmarks."""
        avg = get_tier_avg_contact_rate(PerformanceTier.TOP_25, None)
        assert avg == 50.0  # Default for TOP_25

    def test_get_tier_avg_close_rate(self, sample_benchmarks: BenchmarkData):
        """Test close rate retrieval."""
        avg = get_tier_avg_close_rate(PerformanceTier.TOP_25, sample_benchmarks)
        # (18 + 25) / 2 = 21.5
        assert avg == 21.5

    def test_get_tier_avg_lead_volume(self, sample_benchmarks: BenchmarkData):
        """Test lead volume retrieval."""
        avg = get_tier_avg_lead_volume(PerformanceTier.TOP_25, sample_benchmarks)
        # (100 + 150) / 2 = 125
        assert avg == 125


class TestAssessReadiness:
    """Tests for assess_readiness function."""

    def test_high_performer_has_high_readiness(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that high performers get high readiness scores."""
        readiness = assess_readiness(high_performing_agent, sample_benchmarks)

        assert readiness.score >= 0.7
        assert len(readiness.indicators) > 0
        assert "High" in readiness.recommendation or "ready" in readiness.recommendation.lower()

    def test_low_performer_has_low_readiness(
        self, low_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that low performers get lower readiness scores."""
        readiness = assess_readiness(low_performing_agent, sample_benchmarks)

        assert readiness.score < 0.6
        assert len(readiness.barriers) > 0

    def test_tenure_impacts_score(self, sample_benchmarks: BenchmarkData):
        """Test that tenure affects readiness score."""
        new_agent = Agent(
            id="new",
            name="New Agent",
            tenure_months=3,
        )
        experienced_agent = Agent(
            id="exp",
            name="Experienced Agent",
            tenure_months=36,
        )

        new_readiness = assess_readiness(new_agent, sample_benchmarks)
        exp_readiness = assess_readiness(experienced_agent, sample_benchmarks)

        assert exp_readiness.score > new_readiness.score

    def test_book_size_impacts_score(self, sample_benchmarks: BenchmarkData):
        """Test that book size affects readiness score."""
        small_book = Agent(
            id="small",
            name="Small Book",
            annual_premium_volume=5000,
        )
        large_book = Agent(
            id="large",
            name="Large Book",
            annual_premium_volume=75000,
        )

        small_readiness = assess_readiness(small_book, sample_benchmarks)
        large_readiness = assess_readiness(large_book, sample_benchmarks)

        assert large_readiness.score > small_readiness.score

    def test_missing_data_handled_gracefully(self, sample_benchmarks: BenchmarkData):
        """Test that missing metrics don't cause errors."""
        agent_missing_data = Agent(
            id="missing",
            name="Missing Data",
            # No contact_rate, close_rate, etc.
        )

        readiness = assess_readiness(agent_missing_data, sample_benchmarks)

        # Should still return a result
        assert 0 <= readiness.score <= 1
        assert readiness.recommendation is not None

    def test_readiness_assessment_has_all_fields(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that assessment has all required fields."""
        readiness = assess_readiness(high_performing_agent, sample_benchmarks)

        assert hasattr(readiness, "score")
        assert hasattr(readiness, "indicators")
        assert hasattr(readiness, "barriers")
        assert hasattr(readiness, "recommendation")
        assert isinstance(readiness.indicators, list)
        assert isinstance(readiness.barriers, list)


class TestScoreOpportunity:
    """Tests for score_opportunity function."""

    def test_score_in_valid_range(
        self,
        sample_projection: LiftProjection,
        high_performing_agent: Agent,
        sample_benchmarks: BenchmarkData,
    ):
        """Test that scores are in valid 0-100 range."""
        score = score_opportunity(
            sample_projection, high_performing_agent, None, sample_benchmarks
        )

        assert 0 <= score <= 100

    def test_high_lift_increases_score(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that higher lift results in higher score."""
        low_lift = LiftProjection(
            product="Test",
            projected_lift_dollars=5000,
            projected_lift_pct=10.0,
            confidence_score=0.7,
            confidence_level=ConfidenceLevel.MEDIUM,
            similar_agent_count=20,
            similar_agent_avg_revenue=50000,
            median_lift_from_peers=4000,
            adoption_rate=0.5,
            data_source="peer_analysis",
        )
        high_lift = LiftProjection(
            product="Test",
            projected_lift_dollars=30000,
            projected_lift_pct=60.0,
            confidence_score=0.7,
            confidence_level=ConfidenceLevel.MEDIUM,
            similar_agent_count=20,
            similar_agent_avg_revenue=50000,
            median_lift_from_peers=25000,
            adoption_rate=0.5,
            data_source="peer_analysis",
        )

        low_score = score_opportunity(
            low_lift, high_performing_agent, None, sample_benchmarks
        )
        high_score = score_opportunity(
            high_lift, high_performing_agent, None, sample_benchmarks
        )

        assert high_score > low_score

    def test_high_confidence_increases_score(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that higher confidence results in higher score."""
        low_conf = LiftProjection(
            product="Test",
            projected_lift_dollars=15000,
            projected_lift_pct=30.0,
            confidence_score=0.3,
            confidence_level=ConfidenceLevel.LOW,
            similar_agent_count=5,
            similar_agent_avg_revenue=50000,
            median_lift_from_peers=12000,
            adoption_rate=0.3,
            data_source="benchmark",
        )
        high_conf = LiftProjection(
            product="Test",
            projected_lift_dollars=15000,
            projected_lift_pct=30.0,
            confidence_score=0.9,
            confidence_level=ConfidenceLevel.HIGH,
            similar_agent_count=50,
            similar_agent_avg_revenue=50000,
            median_lift_from_peers=12000,
            adoption_rate=0.7,
            data_source="peer_analysis",
        )

        low_score = score_opportunity(
            low_conf, high_performing_agent, None, sample_benchmarks
        )
        high_score = score_opportunity(
            high_conf, high_performing_agent, None, sample_benchmarks
        )

        assert high_score > low_score


class TestGetScoreInterpretation:
    """Tests for get_score_interpretation function."""

    def test_immediate_action(self):
        """Test immediate action interpretation."""
        interp = get_score_interpretation(92)
        assert "Immediate" in interp or "immediate" in interp

    def test_high_priority(self):
        """Test high priority interpretation."""
        interp = get_score_interpretation(80)
        assert "High" in interp or "high" in interp

    def test_medium_priority(self):
        """Test medium priority interpretation."""
        interp = get_score_interpretation(65)
        assert "Medium" in interp or "medium" in interp

    def test_lower_priority(self):
        """Test lower priority interpretation."""
        interp = get_score_interpretation(55)
        assert "Lower" in interp.lower() or "consider" in interp.lower()

    def test_low_priority(self):
        """Test low priority interpretation."""
        interp = get_score_interpretation(40)
        assert "Low" in interp or "low" in interp


class TestRankOpportunities:
    """Tests for rank_opportunities function."""

    def test_returns_sorted_by_score(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that results are sorted by score descending."""
        projections = [
            LiftProjection(
                product=f"Product_{i}",
                projected_lift_dollars=10000 + i * 5000,
                projected_lift_pct=20.0 + i * 5,
                confidence_score=0.5 + i * 0.1,
                confidence_level=ConfidenceLevel.MEDIUM,
                similar_agent_count=20,
                similar_agent_avg_revenue=50000,
                median_lift_from_peers=8000,
                adoption_rate=0.5,
                data_source="peer_analysis",
            )
            for i in range(5)
        ]

        ranked = rank_opportunities(
            projections, high_performing_agent, None, sample_benchmarks
        )

        scores = [score for _, score, _ in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_assigns_correct_ranks(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that ranks are assigned sequentially."""
        projections = [
            LiftProjection(
                product=f"Product_{i}",
                projected_lift_dollars=10000 + i * 5000,
                projected_lift_pct=20.0,
                confidence_score=0.6,
                confidence_level=ConfidenceLevel.MEDIUM,
                similar_agent_count=20,
                similar_agent_avg_revenue=50000,
                median_lift_from_peers=8000,
                adoption_rate=0.5,
                data_source="peer_analysis",
            )
            for i in range(3)
        ]

        ranked = rank_opportunities(
            projections, high_performing_agent, None, sample_benchmarks
        )

        ranks = [rank for _, _, rank in ranked]
        assert ranks == [1, 2, 3]

    def test_respects_top_n(
        self, high_performing_agent: Agent, sample_benchmarks: BenchmarkData
    ):
        """Test that top_n limits results."""
        projections = [
            LiftProjection(
                product=f"Product_{i}",
                projected_lift_dollars=10000,
                projected_lift_pct=20.0,
                confidence_score=0.6,
                confidence_level=ConfidenceLevel.MEDIUM,
                similar_agent_count=20,
                similar_agent_avg_revenue=50000,
                median_lift_from_peers=8000,
                adoption_rate=0.5,
                data_source="peer_analysis",
            )
            for i in range(10)
        ]

        ranked = rank_opportunities(
            projections, high_performing_agent, None, sample_benchmarks, top_n=3
        )

        assert len(ranked) == 3


class TestGenerateOpportunityMessage:
    """Tests for generate_opportunity_message function."""

    def test_includes_current_products(
        self,
        sample_projection: LiftProjection,
        high_performing_agent: Agent,
        sample_benchmarks: BenchmarkData,
    ):
        """Test that message includes current product info."""
        readiness = assess_readiness(high_performing_agent, sample_benchmarks)
        message = generate_opportunity_message(
            sample_projection, high_performing_agent, readiness, 75
        )

        assert "Auto" in message or "Home" in message

    def test_includes_projected_lift(
        self,
        sample_projection: LiftProjection,
        high_performing_agent: Agent,
        sample_benchmarks: BenchmarkData,
    ):
        """Test that message includes projected lift amount."""
        readiness = assess_readiness(high_performing_agent, sample_benchmarks)
        message = generate_opportunity_message(
            sample_projection, high_performing_agent, readiness, 75
        )

        # Should include dollar amount
        assert "$" in message

    def test_includes_confidence(
        self,
        sample_projection: LiftProjection,
        high_performing_agent: Agent,
        sample_benchmarks: BenchmarkData,
    ):
        """Test that message includes confidence level."""
        readiness = assess_readiness(high_performing_agent, sample_benchmarks)
        message = generate_opportunity_message(
            sample_projection, high_performing_agent, readiness, 75
        )

        assert "Confidence" in message or "confidence" in message
