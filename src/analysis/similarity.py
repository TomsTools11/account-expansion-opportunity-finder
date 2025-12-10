"""Agent similarity matching using cosine similarity on feature vectors."""

import logging
from typing import Optional

import numpy as np

from src.models import Agent, PerformanceTier, ProductType

logger = logging.getLogger(__name__)


# Feature weights for similarity calculation
WEIGHTS = {
    "products": 0.40,      # Product mix is most important
    "tier": 0.25,          # Performance tier
    "tenure": 0.15,        # Agent tenure
    "book_size": 0.20,     # Book size / revenue
}


def create_agent_vector(agent: Agent) -> np.ndarray:
    """Create a normalized feature vector for similarity comparison.

    The vector includes:
    - Product mix (one-hot encoding) - Weight: 40%
    - Performance tier (ordinal encoding) - Weight: 25%
    - Tenure band (normalized) - Weight: 15%
    - Book size band (log-normalized) - Weight: 20%

    Args:
        agent: Agent to create vector for

    Returns:
        Numpy array representing the agent's feature vector
    """
    features = []

    # Product mix (one-hot encoding) - Weight: 40%
    products = ProductType.values()
    product_vector = [
        1.0 if p in agent.current_products else 0.0 for p in products
    ]
    # Apply weight to each product dimension
    weighted_products = [x * WEIGHTS["products"] for x in product_vector]
    features.extend(weighted_products)

    # Performance tier (ordinal encoding) - Weight: 25%
    tier_map = {
        PerformanceTier.BOTTOM_10: 1,
        PerformanceTier.BELOW_AVERAGE: 2,
        PerformanceTier.AVERAGE: 3,
        PerformanceTier.TOP_25: 4,
        PerformanceTier.TOP_10: 5,
    }
    tier_value = tier_map.get(agent.performance_tier, 3) / 5.0  # Normalize to 0-1
    features.append(tier_value * WEIGHTS["tier"])

    # Tenure band (normalized) - Weight: 15%
    # Cap at 60 months (5 years) for normalization
    tenure_normalized = min(agent.tenure_months / 60.0, 1.0)
    features.append(tenure_normalized * WEIGHTS["tenure"])

    # Book size band (log-normalized) - Weight: 20%
    # Use log scale to handle wide range of book sizes
    # Cap at $1M (log10(1,000,000) = 6)
    if agent.annual_premium_volume > 0:
        book_normalized = min(
            np.log10(agent.annual_premium_volume + 1) / 6.0, 1.0
        )
    else:
        book_normalized = 0.0
    features.append(book_normalized * WEIGHTS["book_size"])

    return np.array(features, dtype=np.float64)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score between 0 and 1
    """
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def find_similar_agents(
    target: Agent,
    all_agents: list[Agent],
    top_k: int = 50,
    min_similarity: float = 0.0,
    exclude_same_products: bool = False,
) -> list[tuple[Agent, float]]:
    """Find the most similar agents to a target agent.

    Args:
        target: The agent to find similar agents for
        all_agents: Pool of agents to search
        top_k: Maximum number of similar agents to return
        min_similarity: Minimum similarity threshold (0-1)
        exclude_same_products: If True, only include agents with different products

    Returns:
        List of (agent, similarity_score) tuples, sorted by similarity descending
    """
    if not all_agents:
        return []

    target_vec = create_agent_vector(target)
    target_products = set(target.current_products)
    similarities: list[tuple[Agent, float]] = []

    for agent in all_agents:
        # Skip self-comparison
        if agent.id == target.id:
            continue

        # Optionally filter to agents with different product mix
        if exclude_same_products:
            agent_products = set(agent.current_products)
            if agent_products == target_products:
                continue

        agent_vec = create_agent_vector(agent)
        similarity = cosine_similarity(target_vec, agent_vec)

        if similarity >= min_similarity:
            similarities.append((agent, similarity))

    # Sort by similarity descending
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:top_k]


def find_agents_with_product(
    target: Agent,
    all_agents: list[Agent],
    product: str,
    top_k: int = 50,
    min_similarity: float = 0.5,
) -> list[tuple[Agent, float]]:
    """Find similar agents who have a specific product the target doesn't have.

    This is used for cross-sell analysis - finding agents similar to target
    who already sell a product we want to recommend.

    Args:
        target: The agent to find similar agents for
        all_agents: Pool of agents to search
        product: Product that the similar agents must have
        top_k: Maximum number of agents to return
        min_similarity: Minimum similarity threshold

    Returns:
        List of (agent, similarity_score) tuples
    """
    # Filter to agents who have the product
    agents_with_product = [
        a for a in all_agents
        if product in a.current_products and a.id != target.id
    ]

    if not agents_with_product:
        return []

    target_vec = create_agent_vector(target)
    similarities: list[tuple[Agent, float]] = []

    for agent in agents_with_product:
        agent_vec = create_agent_vector(agent)
        similarity = cosine_similarity(target_vec, agent_vec)

        if similarity >= min_similarity:
            similarities.append((agent, similarity))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]


def find_agents_without_product(
    target: Agent,
    all_agents: list[Agent],
    product: str,
    top_k: int = 50,
    min_similarity: float = 0.5,
) -> list[tuple[Agent, float]]:
    """Find similar agents who don't have a specific product.

    This is used as a comparison group - similar agents who haven't
    adopted a product yet.

    Args:
        target: The agent to find similar agents for
        all_agents: Pool of agents to search
        product: Product that the similar agents must NOT have
        top_k: Maximum number of agents to return
        min_similarity: Minimum similarity threshold

    Returns:
        List of (agent, similarity_score) tuples
    """
    # Filter to agents who don't have the product
    agents_without_product = [
        a for a in all_agents
        if product not in a.current_products and a.id != target.id
    ]

    if not agents_without_product:
        return []

    target_vec = create_agent_vector(target)
    similarities: list[tuple[Agent, float]] = []

    for agent in agents_without_product:
        agent_vec = create_agent_vector(agent)
        similarity = cosine_similarity(target_vec, agent_vec)

        if similarity >= min_similarity:
            similarities.append((agent, similarity))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]


def get_similarity_confidence(similarity_score: float) -> str:
    """Convert similarity score to confidence level.

    Args:
        similarity_score: Cosine similarity between 0 and 1

    Returns:
        Confidence level string: "High", "Medium", or "Low"
    """
    if similarity_score > 0.75:
        return "High"
    elif similarity_score > 0.60:
        return "Medium"
    elif similarity_score > 0.50:
        return "Low"
    else:
        return "Very Low"


def calculate_peer_group_stats(
    agents: list[tuple[Agent, float]]
) -> dict[str, float]:
    """Calculate statistics for a peer group of similar agents.

    Args:
        agents: List of (agent, similarity_score) tuples

    Returns:
        Dictionary with peer group statistics
    """
    if not agents:
        return {
            "count": 0,
            "avg_similarity": 0.0,
            "avg_revenue": 0.0,
            "median_revenue": 0.0,
            "avg_contact_rate": 0.0,
            "avg_close_rate": 0.0,
        }

    agent_list = [a for a, _ in agents]
    similarity_scores = [s for _, s in agents]

    revenues = [a.annual_premium_volume for a in agent_list]
    contact_rates = [
        a.contact_rate for a in agent_list if a.contact_rate is not None
    ]
    close_rates = [
        a.close_rate for a in agent_list if a.close_rate is not None
    ]

    return {
        "count": len(agents),
        "avg_similarity": float(np.mean(similarity_scores)),
        "avg_revenue": float(np.mean(revenues)) if revenues else 0.0,
        "median_revenue": float(np.median(revenues)) if revenues else 0.0,
        "avg_contact_rate": float(np.mean(contact_rates)) if contact_rates else 0.0,
        "avg_close_rate": float(np.mean(close_rates)) if close_rates else 0.0,
    }


def batch_calculate_vectors(agents: list[Agent]) -> dict[str, np.ndarray]:
    """Pre-calculate feature vectors for a list of agents.

    This is more efficient when doing many similarity comparisons.

    Args:
        agents: List of agents to calculate vectors for

    Returns:
        Dictionary mapping agent IDs to their feature vectors
    """
    return {agent.id: create_agent_vector(agent) for agent in agents}


def find_similar_agents_batch(
    target: Agent,
    agent_vectors: dict[str, np.ndarray],
    agents_by_id: dict[str, Agent],
    top_k: int = 50,
    min_similarity: float = 0.0,
) -> list[tuple[Agent, float]]:
    """Find similar agents using pre-calculated vectors.

    More efficient version for batch processing.

    Args:
        target: Target agent
        agent_vectors: Pre-calculated vectors (from batch_calculate_vectors)
        agents_by_id: Agent lookup by ID
        top_k: Maximum results
        min_similarity: Minimum similarity threshold

    Returns:
        List of (agent, similarity_score) tuples
    """
    target_vec = create_agent_vector(target)
    similarities: list[tuple[Agent, float]] = []

    for agent_id, agent_vec in agent_vectors.items():
        if agent_id == target.id:
            continue

        similarity = cosine_similarity(target_vec, agent_vec)
        if similarity >= min_similarity:
            agent = agents_by_id.get(agent_id)
            if agent:
                similarities.append((agent, similarity))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]
