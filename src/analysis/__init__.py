"""Analysis engine for insurance agent expansion opportunities."""

from .engine import AnalysisEngine, create_analysis_engine
from .projections import (
    LiftProjection,
    calculate_confidence_score,
    estimate_tier_progression_lift,
    identify_product_opportunities,
    project_revenue_lift,
)
from .scoring import (
    ReadinessAssessment,
    assess_readiness,
    generate_opportunity_message,
    get_score_interpretation,
    rank_opportunities,
    score_opportunity,
)
from .similarity import (
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

__all__ = [
    # Engine
    "AnalysisEngine",
    "create_analysis_engine",
    # Similarity
    "batch_calculate_vectors",
    "calculate_peer_group_stats",
    "cosine_similarity",
    "create_agent_vector",
    "find_agents_with_product",
    "find_agents_without_product",
    "find_similar_agents",
    "find_similar_agents_batch",
    "get_similarity_confidence",
    # Projections
    "LiftProjection",
    "calculate_confidence_score",
    "estimate_tier_progression_lift",
    "identify_product_opportunities",
    "project_revenue_lift",
    # Scoring
    "ReadinessAssessment",
    "assess_readiness",
    "generate_opportunity_message",
    "get_score_interpretation",
    "rank_opportunities",
    "score_opportunity",
]
