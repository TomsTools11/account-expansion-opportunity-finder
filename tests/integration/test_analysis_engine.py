"""Integration tests for the analysis engine."""

import time

import pytest

from src.analysis import AnalysisEngine, create_analysis_engine
from src.models import (
    Agent,
    AnalysisFilters,
    BenchmarkData,
    BenchmarkTier,
    CrossSellPattern,
    OpportunityType,
    PerformanceTier,
    ProductBenchmark,
)


@pytest.fixture
def sample_benchmarks() -> BenchmarkData:
    """Create comprehensive benchmark data."""
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
            ),
            CrossSellPattern(
                primary_product="Auto",
                added_product="Life",
                avg_revenue_lift_pct=15.0,
                adoption_rate=0.30,
                avg_time_to_add_months=12,
            ),
            CrossSellPattern(
                primary_product="Home",
                added_product="Life",
                avg_revenue_lift_pct=12.0,
                adoption_rate=0.25,
                avg_time_to_add_months=14,
            ),
        ],
    )


@pytest.fixture
def sample_agents() -> list[Agent]:
    """Create a diverse set of agents for testing."""
    agents = []

    # Home-only agents (candidates for Auto cross-sell)
    for i in range(5):
        agents.append(Agent(
            id=f"home_only_{i}",
            name=f"Home Only Agent {i}",
            current_products=["Home"],
            annual_premium_volume=40000 + i * 10000,
            tenure_months=18 + i * 6,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=48 + i * 2,
            close_rate=19 + i,
            monthly_lead_volume=110 + i * 10,
        ))

    # Auto-only agents (candidates for Home cross-sell)
    for i in range(5):
        agents.append(Agent(
            id=f"auto_only_{i}",
            name=f"Auto Only Agent {i}",
            current_products=["Auto"],
            annual_premium_volume=35000 + i * 8000,
            tenure_months=12 + i * 4,
            performance_tier=PerformanceTier.AVERAGE,
            contact_rate=35 + i * 3,
            close_rate=14 + i,
            monthly_lead_volume=60 + i * 8,
        ))

    # Auto + Home agents (high performers)
    for i in range(8):
        agents.append(Agent(
            id=f"auto_home_{i}",
            name=f"Auto Home Agent {i}",
            current_products=["Auto", "Home"],
            annual_premium_volume=60000 + i * 12000,
            tenure_months=24 + i * 6,
            performance_tier=PerformanceTier.TOP_25 if i < 5 else PerformanceTier.TOP_10,
            contact_rate=50 + i * 2,
            close_rate=20 + i * 1.5,
            monthly_lead_volume=120 + i * 15,
        ))

    # Full product line agents (top performers)
    for i in range(3):
        agents.append(Agent(
            id=f"full_line_{i}",
            name=f"Full Line Agent {i}",
            current_products=["Auto", "Home", "Life"],
            annual_premium_volume=90000 + i * 15000,
            tenure_months=48 + i * 12,
            performance_tier=PerformanceTier.TOP_10,
            contact_rate=60 + i * 3,
            close_rate=28 + i * 2,
            monthly_lead_volume=180 + i * 20,
        ))

    return agents


class TestAnalysisEngineInit:
    """Tests for AnalysisEngine initialization."""

    def test_create_with_factory(self, sample_benchmarks: BenchmarkData):
        """Test engine creation with factory function."""
        engine = create_analysis_engine(
            benchmarks=sample_benchmarks,
            min_confidence=0.5,
            min_similar_agents=5,
            max_opportunities=3,
        )

        assert engine is not None
        assert engine.min_confidence == 0.5
        assert engine.min_similar_agents == 5
        assert engine.max_opportunities == 3

    def test_create_directly(self, sample_benchmarks: BenchmarkData):
        """Test direct engine instantiation."""
        engine = AnalysisEngine(benchmarks=sample_benchmarks)

        assert engine is not None
        assert engine.benchmarks == sample_benchmarks


class TestAnalyzeSingleAgent:
    """Tests for analyze_single_agent method."""

    def test_returns_analysis_result(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that analysis returns proper result structure."""
        engine = create_analysis_engine(sample_benchmarks)
        target = sample_agents[0]  # Home only

        result = engine.analyze_single_agent(target, sample_agents)

        assert result.agent == target
        assert isinstance(result.opportunities, list)
        assert "current_tier" in result.benchmark_context

    def test_finds_product_opportunities(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that product opportunities are identified."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )
        target = sample_agents[0]  # Home only

        result = engine.analyze_single_agent(target, sample_agents)

        # Should find Auto as an opportunity
        products = [o.recommended_product for o in result.opportunities]
        assert "Auto" in products or len(result.opportunities) > 0

    def test_respects_max_opportunities(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that max_opportunities limit is respected."""
        engine = create_analysis_engine(
            sample_benchmarks,
            max_opportunities=2,
            min_confidence=0.1,
        )
        target = sample_agents[0]

        result = engine.analyze_single_agent(target, sample_agents)

        assert len(result.opportunities) <= 2

    def test_opportunities_are_ranked(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that opportunities have sequential ranks."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )
        target = sample_agents[0]

        result = engine.analyze_single_agent(target, sample_agents)

        if len(result.opportunities) > 1:
            ranks = [o.rank for o in result.opportunities]
            expected = list(range(1, len(result.opportunities) + 1))
            assert ranks == expected

    def test_opportunities_sorted_by_priority(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that opportunities are sorted by priority score."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )
        target = sample_agents[0]

        result = engine.analyze_single_agent(target, sample_agents)

        if len(result.opportunities) > 1:
            scores = [o.priority_score for o in result.opportunities]
            assert scores == sorted(scores, reverse=True)

    def test_opportunity_has_required_fields(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that opportunities have all required fields."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )
        target = sample_agents[0]

        result = engine.analyze_single_agent(target, sample_agents)

        if result.opportunities:
            opp = result.opportunities[0]
            assert opp.agent_id == target.id
            assert opp.agent_name == target.name
            assert opp.opportunity_type in [OpportunityType.ADD_PRODUCT, OpportunityType.IMPROVE_CONVERSION]
            assert opp.projected_revenue_lift >= 0
            assert 0 <= opp.confidence_score <= 1
            assert 0 <= opp.priority_score <= 100

    def test_includes_readiness_indicators(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that opportunities include readiness info."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )
        target = sample_agents[0]

        result = engine.analyze_single_agent(target, sample_agents)

        if result.opportunities:
            opp = result.opportunities[0]
            assert isinstance(opp.readiness_indicators, list)
            assert isinstance(opp.barriers, list)


class TestAnalyzeBatch:
    """Tests for analyze_batch method."""

    def test_returns_batch_result(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that batch analysis returns proper result structure."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        result = engine.analyze_batch(sample_agents, top_n=10)

        assert result.total_agents_analyzed == len(sample_agents)
        assert result.total_opportunities_found >= 0
        assert isinstance(result.top_opportunities, list)
        assert isinstance(result.summary_stats, dict)

    def test_respects_top_n(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that top_n limits returned opportunities."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        result = engine.analyze_batch(sample_agents, top_n=5)

        assert len(result.top_opportunities) <= 5

    def test_opportunities_sorted_by_priority(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that batch opportunities are sorted by priority."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        result = engine.analyze_batch(sample_agents, top_n=20)

        if len(result.top_opportunities) > 1:
            scores = [o.priority_score for o in result.top_opportunities]
            assert scores == sorted(scores, reverse=True)

    def test_applies_filters(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that filters are applied correctly."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        # Filter to only TOP_25 agents
        filters = AnalysisFilters(
            current_tiers=[PerformanceTier.TOP_25]
        )

        result = engine.analyze_batch(sample_agents, filters=filters, top_n=20)

        # Should have fewer agents analyzed
        top_25_count = sum(
            1 for a in sample_agents
            if a.performance_tier == PerformanceTier.TOP_25
        )
        assert result.total_agents_analyzed == top_25_count

    def test_summary_stats_calculated(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that summary statistics are calculated."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        result = engine.analyze_batch(sample_agents, top_n=20)

        stats = result.summary_stats
        assert "total_projected_lift" in stats
        assert "avg_confidence_score" in stats
        assert "high_priority_count" in stats
        assert "agents_with_opportunities" in stats

    def test_parallel_matches_sequential(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that parallel and sequential analysis give same results."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        # Take a smaller subset for this test
        subset = sample_agents[:5]

        seq_result = engine.analyze_batch(subset, top_n=10, parallel=False)
        par_result = engine.analyze_batch(subset, top_n=10, parallel=True, max_workers=2)

        # Should find same number of opportunities
        assert seq_result.total_opportunities_found == par_result.total_opportunities_found


class TestPerformance:
    """Performance tests for the analysis engine."""

    def test_batch_completes_in_reasonable_time(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that batch analysis of sample agents completes quickly."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )

        start = time.time()
        result = engine.analyze_batch(sample_agents, top_n=20)
        elapsed = time.time() - start

        # Should complete in under 10 seconds for ~20 agents
        assert elapsed < 10.0
        assert result.total_agents_analyzed > 0

    def test_single_analysis_is_fast(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test that single agent analysis is fast."""
        engine = create_analysis_engine(sample_benchmarks)
        target = sample_agents[0]

        start = time.time()
        result = engine.analyze_single_agent(target, sample_agents)
        elapsed = time.time() - start

        # Should complete in under 2 seconds
        assert elapsed < 2.0
        assert result is not None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_agent_list(self, sample_benchmarks: BenchmarkData):
        """Test handling of empty agent list."""
        engine = create_analysis_engine(sample_benchmarks)

        result = engine.analyze_batch([], top_n=10)

        assert result.total_agents_analyzed == 0
        assert result.total_opportunities_found == 0
        assert len(result.top_opportunities) == 0

    def test_single_agent(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test analysis with only one agent."""
        engine = create_analysis_engine(
            sample_benchmarks, min_confidence=0.1
        )
        single = sample_agents[:1]

        result = engine.analyze_batch(single, top_n=10)

        assert result.total_agents_analyzed == 1

    def test_agent_with_all_products(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test agent who has all products."""
        engine = create_analysis_engine(sample_benchmarks)

        # Create agent with all products
        full_agent = Agent(
            id="full",
            name="Full Product Agent",
            current_products=["Auto", "Home", "Life", "Health", "Renters", "Medicare", "Commercial Property", "Commercial Auto"],
            annual_premium_volume=150000,
            tenure_months=60,
            performance_tier=PerformanceTier.TOP_10,
        )

        result = engine.analyze_single_agent(full_agent, sample_agents)

        # May still have tier progression opportunity
        add_product_opps = [
            o for o in result.opportunities
            if o.opportunity_type == OpportunityType.ADD_PRODUCT
        ]
        # Should have no product add opportunities
        assert len(add_product_opps) == 0

    def test_filters_with_no_matches(
        self, sample_benchmarks: BenchmarkData, sample_agents: list[Agent]
    ):
        """Test filters that match no agents."""
        engine = create_analysis_engine(sample_benchmarks)

        filters = AnalysisFilters(
            min_tenure_months=1000  # No agent has this
        )

        result = engine.analyze_batch(sample_agents, filters=filters, top_n=10)

        assert result.total_agents_analyzed == 0
