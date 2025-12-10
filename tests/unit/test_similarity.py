"""Unit tests for agent similarity matching."""

import numpy as np
import pytest

from src.analysis.similarity import (
    batch_calculate_vectors,
    calculate_peer_group_stats,
    cosine_similarity,
    create_agent_vector,
    find_agents_with_product,
    find_agents_without_product,
    find_similar_agents,
    find_similar_agents_batch,
    get_similarity_confidence,
)
from src.models import Agent, PerformanceTier


@pytest.fixture
def sample_agents() -> list[Agent]:
    """Create a set of sample agents for testing."""
    return [
        Agent(
            id="agent_1",
            name="Agent 1",
            current_products=["Auto", "Home"],
            annual_premium_volume=50000,
            tenure_months=24,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=50.0,
            close_rate=20.0,
        ),
        Agent(
            id="agent_2",
            name="Agent 2",
            current_products=["Auto", "Home"],  # Same products
            annual_premium_volume=55000,
            tenure_months=30,
            performance_tier=PerformanceTier.TOP_25,
            contact_rate=52.0,
            close_rate=22.0,
        ),
        Agent(
            id="agent_3",
            name="Agent 3",
            current_products=["Life"],  # Different products
            annual_premium_volume=20000,
            tenure_months=12,
            performance_tier=PerformanceTier.AVERAGE,
            contact_rate=35.0,
            close_rate=15.0,
        ),
        Agent(
            id="agent_4",
            name="Agent 4",
            current_products=["Auto", "Home", "Life"],  # Superset
            annual_premium_volume=80000,
            tenure_months=48,
            performance_tier=PerformanceTier.TOP_10,
            contact_rate=60.0,
            close_rate=30.0,
        ),
        Agent(
            id="agent_5",
            name="Agent 5",
            current_products=["Auto"],  # Subset
            annual_premium_volume=30000,
            tenure_months=18,
            performance_tier=PerformanceTier.AVERAGE,
            contact_rate=40.0,
            close_rate=16.0,
        ),
    ]


class TestCreateAgentVector:
    """Tests for create_agent_vector function."""

    def test_vector_length(self, sample_agents: list[Agent]):
        """Test that vector has correct length."""
        agent = sample_agents[0]
        vector = create_agent_vector(agent)
        # 8 products + 1 tier + 1 tenure + 1 book size = 11
        assert len(vector) == 11

    def test_product_encoding(self):
        """Test that products are correctly encoded."""
        agent = Agent(
            id="test",
            name="Test",
            current_products=["Auto"],  # First product type
            annual_premium_volume=0,
            tenure_months=0,
        )
        vector = create_agent_vector(agent)
        # Auto should be first product, with weight 0.4
        assert vector[0] == 0.4  # Auto is present
        assert vector[1] == 0.0  # Home is not present

    def test_tenure_normalization(self):
        """Test tenure is normalized correctly."""
        agent_short = Agent(
            id="short",
            name="Short Tenure",
            tenure_months=12,
        )
        agent_long = Agent(
            id="long",
            name="Long Tenure",
            tenure_months=60,  # 5 years - max
        )
        agent_very_long = Agent(
            id="very_long",
            name="Very Long Tenure",
            tenure_months=120,  # 10 years - should cap
        )

        vec_short = create_agent_vector(agent_short)
        vec_long = create_agent_vector(agent_long)
        vec_very_long = create_agent_vector(agent_very_long)

        # Index 9 is tenure (after 8 products + 1 tier)
        # Short tenure should be less than long
        assert vec_short[9] < vec_long[9]
        # Very long should cap at same as long
        assert vec_long[9] == vec_very_long[9]

    def test_book_size_log_normalization(self):
        """Test book size uses log normalization."""
        agent_small = Agent(
            id="small",
            name="Small Book",
            annual_premium_volume=10000,
        )
        agent_large = Agent(
            id="large",
            name="Large Book",
            annual_premium_volume=100000,
        )

        vec_small = create_agent_vector(agent_small)
        vec_large = create_agent_vector(agent_large)

        # Index 10 is book size
        assert vec_small[10] < vec_large[10]
        # Both should be positive
        assert vec_small[10] > 0
        assert vec_large[10] > 0


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self):
        """Test that identical vectors have similarity 1.0."""
        vec = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        """Test that orthogonal vectors have similarity 0.0."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        """Test that opposite vectors have similarity -1.0."""
        vec1 = np.array([1.0, 2.0])
        vec2 = np.array([-1.0, -2.0])
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0)

    def test_zero_vector(self):
        """Test that zero vector returns 0.0 similarity."""
        vec = np.array([1.0, 2.0])
        zero = np.array([0.0, 0.0])
        assert cosine_similarity(vec, zero) == 0.0
        assert cosine_similarity(zero, vec) == 0.0


class TestFindSimilarAgents:
    """Tests for find_similar_agents function."""

    def test_excludes_self(self, sample_agents: list[Agent]):
        """Test that target agent is excluded from results."""
        target = sample_agents[0]
        similar = find_similar_agents(target, sample_agents)

        agent_ids = [a.id for a, _ in similar]
        assert target.id not in agent_ids

    def test_returns_sorted_by_similarity(self, sample_agents: list[Agent]):
        """Test that results are sorted by similarity descending."""
        target = sample_agents[0]
        similar = find_similar_agents(target, sample_agents)

        similarities = [s for _, s in similar]
        assert similarities == sorted(similarities, reverse=True)

    def test_respects_top_k(self, sample_agents: list[Agent]):
        """Test that top_k limits results."""
        target = sample_agents[0]
        similar = find_similar_agents(target, sample_agents, top_k=2)

        assert len(similar) <= 2

    def test_respects_min_similarity(self, sample_agents: list[Agent]):
        """Test that min_similarity filters low scores."""
        target = sample_agents[0]
        similar = find_similar_agents(target, sample_agents, min_similarity=0.9)

        for _, similarity in similar:
            assert similarity >= 0.9

    def test_similar_agents_have_high_score(self, sample_agents: list[Agent]):
        """Test that agent_1 and agent_2 (very similar) have high similarity."""
        target = sample_agents[0]  # agent_1
        similar = find_similar_agents(target, sample_agents)

        # Find agent_2 in results
        agent_2_sim = None
        for agent, sim in similar:
            if agent.id == "agent_2":
                agent_2_sim = sim
                break

        # agent_2 has same products and similar metrics
        assert agent_2_sim is not None
        assert agent_2_sim > 0.9  # Should be very similar

    def test_dissimilar_agents_have_lower_score(self, sample_agents: list[Agent]):
        """Test that agent_1 and agent_3 (dissimilar) have lower similarity."""
        target = sample_agents[0]  # agent_1
        similar = find_similar_agents(target, sample_agents)

        # Find agent_3 (Life only) in results
        agent_3_sim = None
        for agent, sim in similar:
            if agent.id == "agent_3":
                agent_3_sim = sim
                break

        # agent_3 has different products and metrics
        assert agent_3_sim is not None
        assert agent_3_sim < 0.7  # Should be less similar


class TestFindAgentsWithProduct:
    """Tests for find_agents_with_product function."""

    def test_filters_to_product_holders(self, sample_agents: list[Agent]):
        """Test that only agents with the product are returned."""
        target = sample_agents[0]  # Has Auto, Home
        similar = find_agents_with_product(
            target, sample_agents, product="Life", min_similarity=0.0
        )

        for agent, _ in similar:
            assert "Life" in agent.current_products

    def test_excludes_target(self, sample_agents: list[Agent]):
        """Test that target is excluded even if they have the product."""
        # Use agent_4 who has Life
        target = sample_agents[3]  # agent_4
        similar = find_agents_with_product(
            target, sample_agents, product="Life", min_similarity=0.0
        )

        agent_ids = [a.id for a, _ in similar]
        assert target.id not in agent_ids


class TestFindAgentsWithoutProduct:
    """Tests for find_agents_without_product function."""

    def test_filters_to_non_product_holders(self, sample_agents: list[Agent]):
        """Test that only agents without the product are returned."""
        target = sample_agents[0]
        similar = find_agents_without_product(
            target, sample_agents, product="Life", min_similarity=0.0
        )

        for agent, _ in similar:
            assert "Life" not in agent.current_products


class TestGetSimilarityConfidence:
    """Tests for get_similarity_confidence function."""

    def test_high_similarity(self):
        """Test high similarity returns High confidence."""
        assert get_similarity_confidence(0.80) == "High"
        assert get_similarity_confidence(0.76) == "High"

    def test_medium_similarity(self):
        """Test medium similarity returns Medium confidence."""
        assert get_similarity_confidence(0.70) == "Medium"
        assert get_similarity_confidence(0.61) == "Medium"

    def test_low_similarity(self):
        """Test low similarity returns Low confidence."""
        assert get_similarity_confidence(0.55) == "Low"
        assert get_similarity_confidence(0.51) == "Low"

    def test_very_low_similarity(self):
        """Test very low similarity returns Very Low confidence."""
        assert get_similarity_confidence(0.40) == "Very Low"
        assert get_similarity_confidence(0.0) == "Very Low"


class TestCalculatePeerGroupStats:
    """Tests for calculate_peer_group_stats function."""

    def test_empty_list(self):
        """Test stats for empty agent list."""
        stats = calculate_peer_group_stats([])
        assert stats["count"] == 0
        assert stats["avg_revenue"] == 0.0

    def test_calculates_averages(self, sample_agents: list[Agent]):
        """Test that averages are calculated correctly."""
        agents_with_sim = [(a, 0.8) for a in sample_agents[:3]]
        stats = calculate_peer_group_stats(agents_with_sim)

        assert stats["count"] == 3
        assert stats["avg_similarity"] == pytest.approx(0.8)
        # Average of 50000, 55000, 20000
        expected_avg = (50000 + 55000 + 20000) / 3
        assert stats["avg_revenue"] == pytest.approx(expected_avg)


class TestBatchCalculateVectors:
    """Tests for batch_calculate_vectors function."""

    def test_returns_dict_of_vectors(self, sample_agents: list[Agent]):
        """Test that batch calculation returns dict keyed by ID."""
        vectors = batch_calculate_vectors(sample_agents)

        assert len(vectors) == len(sample_agents)
        for agent in sample_agents:
            assert agent.id in vectors
            assert isinstance(vectors[agent.id], np.ndarray)

    def test_vectors_match_individual(self, sample_agents: list[Agent]):
        """Test that batch vectors match individual calculation."""
        vectors = batch_calculate_vectors(sample_agents)

        for agent in sample_agents:
            individual = create_agent_vector(agent)
            np.testing.assert_array_almost_equal(vectors[agent.id], individual)


class TestFindSimilarAgentsBatch:
    """Tests for find_similar_agents_batch function."""

    def test_matches_regular_function(self, sample_agents: list[Agent]):
        """Test that batch version matches regular find_similar_agents."""
        target = sample_agents[0]

        # Regular function
        regular = find_similar_agents(target, sample_agents, top_k=3)

        # Batch function
        vectors = batch_calculate_vectors(sample_agents)
        agents_by_id = {a.id: a for a in sample_agents}
        batch = find_similar_agents_batch(
            target, vectors, agents_by_id, top_k=3
        )

        # Should return same agents in same order
        regular_ids = [a.id for a, _ in regular]
        batch_ids = [a.id for a, _ in batch]
        assert regular_ids == batch_ids

        # Similarities should match
        regular_sims = [s for _, s in regular]
        batch_sims = [s for _, s in batch]
        np.testing.assert_array_almost_equal(regular_sims, batch_sims)
