"""Unit tests for MCP tool input schemas."""

import pytest
from pydantic import ValidationError

from src.mcp.tools import (
    AnalyzeAgentInput,
    BatchAnalysisInput,
    GetBenchmarkSummaryInput,
    RefreshBenchmarksInput,
)


class TestAnalyzeAgentInput:
    """Tests for AnalyzeAgentInput schema."""

    def test_valid_minimal_input(self):
        """Test minimal valid input."""
        input_data = AnalyzeAgentInput(agent_id="agent_123")
        assert input_data.agent_id == "agent_123"
        assert input_data.min_confidence == 0.5  # default
        assert input_data.max_opportunities == 5  # default
        assert input_data.include_tier_progression is True  # default

    def test_valid_full_input(self):
        """Test full valid input."""
        input_data = AnalyzeAgentInput(
            agent_id="agent_123",
            min_confidence=0.7,
            max_opportunities=3,
            include_tier_progression=False,
        )
        assert input_data.agent_id == "agent_123"
        assert input_data.min_confidence == 0.7
        assert input_data.max_opportunities == 3
        assert input_data.include_tier_progression is False

    def test_agent_id_required(self):
        """Test that agent_id is required."""
        with pytest.raises(ValidationError) as exc:
            AnalyzeAgentInput()
        assert "agent_id" in str(exc.value)

    def test_empty_agent_id_rejected(self):
        """Test that empty agent_id is rejected."""
        with pytest.raises(ValidationError):
            AnalyzeAgentInput(agent_id="")

    def test_whitespace_agent_id_rejected(self):
        """Test that whitespace-only agent_id is rejected."""
        with pytest.raises(ValidationError):
            AnalyzeAgentInput(agent_id="   ")

    def test_agent_id_stripped(self):
        """Test that agent_id is stripped of whitespace."""
        input_data = AnalyzeAgentInput(agent_id="  agent_123  ")
        assert input_data.agent_id == "agent_123"

    def test_min_confidence_range(self):
        """Test min_confidence validation."""
        # Valid boundary values
        assert AnalyzeAgentInput(agent_id="x", min_confidence=0.0).min_confidence == 0.0
        assert AnalyzeAgentInput(agent_id="x", min_confidence=1.0).min_confidence == 1.0

        # Invalid values
        with pytest.raises(ValidationError):
            AnalyzeAgentInput(agent_id="x", min_confidence=-0.1)
        with pytest.raises(ValidationError):
            AnalyzeAgentInput(agent_id="x", min_confidence=1.1)

    def test_max_opportunities_range(self):
        """Test max_opportunities validation."""
        # Valid boundary values
        assert AnalyzeAgentInput(agent_id="x", max_opportunities=1).max_opportunities == 1
        assert AnalyzeAgentInput(agent_id="x", max_opportunities=20).max_opportunities == 20

        # Invalid values
        with pytest.raises(ValidationError):
            AnalyzeAgentInput(agent_id="x", max_opportunities=0)
        with pytest.raises(ValidationError):
            AnalyzeAgentInput(agent_id="x", max_opportunities=21)


class TestBatchAnalysisInput:
    """Tests for BatchAnalysisInput schema."""

    def test_valid_minimal_input(self):
        """Test minimal valid input (all defaults)."""
        input_data = BatchAnalysisInput()
        assert input_data.top_n == 20
        assert input_data.min_confidence == 0.5
        assert input_data.filter_tiers is None
        assert input_data.parallel is True

    def test_valid_full_input(self):
        """Test full valid input."""
        input_data = BatchAnalysisInput(
            top_n=50,
            min_confidence=0.7,
            filter_tiers=["Top 10%", "Top 25%"],
            filter_products=["Auto", "Home"],
            filter_missing_products=["Life"],
            min_tenure_months=12,
            max_tenure_months=48,
            min_premium_volume=25000,
            max_premium_volume=100000,
            parallel=False,
        )
        assert input_data.top_n == 50
        assert input_data.filter_tiers == ["Top 10%", "Top 25%"]
        assert input_data.filter_missing_products == ["Life"]
        assert input_data.parallel is False

    def test_top_n_range(self):
        """Test top_n validation."""
        assert BatchAnalysisInput(top_n=1).top_n == 1
        assert BatchAnalysisInput(top_n=100).top_n == 100

        with pytest.raises(ValidationError):
            BatchAnalysisInput(top_n=0)
        with pytest.raises(ValidationError):
            BatchAnalysisInput(top_n=101)

    def test_invalid_tier_rejected(self):
        """Test that invalid tier names are rejected."""
        with pytest.raises(ValidationError) as exc:
            BatchAnalysisInput(filter_tiers=["INVALID_TIER"])
        assert "Invalid tier" in str(exc.value)

    def test_valid_tiers_accepted(self):
        """Test that all valid tier names are accepted."""
        valid_tiers = ["Top 10%", "Top 25%", "Average", "Below Average", "Bottom 10%"]
        input_data = BatchAnalysisInput(filter_tiers=valid_tiers)
        assert input_data.filter_tiers == valid_tiers

    def test_tenure_validation(self):
        """Test tenure month validation."""
        # Valid
        assert BatchAnalysisInput(min_tenure_months=0).min_tenure_months == 0
        assert BatchAnalysisInput(max_tenure_months=0).max_tenure_months == 0

        # Invalid
        with pytest.raises(ValidationError):
            BatchAnalysisInput(min_tenure_months=-1)

    def test_premium_validation(self):
        """Test premium volume validation."""
        # Valid
        assert BatchAnalysisInput(min_premium_volume=0).min_premium_volume == 0
        assert BatchAnalysisInput(max_premium_volume=1000000).max_premium_volume == 1000000

        # Invalid
        with pytest.raises(ValidationError):
            BatchAnalysisInput(min_premium_volume=-1)


class TestGetBenchmarkSummaryInput:
    """Tests for GetBenchmarkSummaryInput schema."""

    def test_valid_defaults(self):
        """Test default values."""
        input_data = GetBenchmarkSummaryInput()
        assert input_data.include_tiers is True
        assert input_data.include_products is True
        assert input_data.include_cross_sell is True
        assert input_data.tier_filter is None

    def test_custom_values(self):
        """Test custom values."""
        input_data = GetBenchmarkSummaryInput(
            include_tiers=False,
            include_products=False,
            include_cross_sell=True,
            tier_filter="Top 25%",
        )
        assert input_data.include_tiers is False
        assert input_data.tier_filter == "Top 25%"

    def test_invalid_tier_filter_rejected(self):
        """Test that invalid tier filter is rejected."""
        with pytest.raises(ValidationError) as exc:
            GetBenchmarkSummaryInput(tier_filter="INVALID")
        assert "Invalid tier" in str(exc.value)

    def test_valid_tier_filters(self):
        """Test that valid tier filters are accepted."""
        for tier in ["Top 10%", "Top 25%", "Average", "Below Average", "Bottom 10%"]:
            input_data = GetBenchmarkSummaryInput(tier_filter=tier)
            assert input_data.tier_filter == tier


class TestRefreshBenchmarksInput:
    """Tests for RefreshBenchmarksInput schema."""

    def test_valid_defaults(self):
        """Test default values."""
        input_data = RefreshBenchmarksInput()
        assert input_data.force is False
        assert input_data.clear_agent_cache is False

    def test_custom_values(self):
        """Test custom values."""
        input_data = RefreshBenchmarksInput(
            force=True,
            clear_agent_cache=True,
        )
        assert input_data.force is True
        assert input_data.clear_agent_cache is True
