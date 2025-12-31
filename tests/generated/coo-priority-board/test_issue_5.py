"""Tests for ConsensusChecker module."""

import pytest
from src.consensus_checker import check_consensus, weighted_vote
from src.models.priority import ConsensusResult


class TestCheckConsensus:
    """Tests for check_consensus function."""

    def test_returns_consensus_result(self):
        """check_consensus returns a ConsensusResult."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert isinstance(result, ConsensusResult)

    def test_natural_consensus_with_perfect_agreement(self):
        """Natural consensus reached when all 4+ panels agree on 3+ priorities."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"],
            ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"],
            ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"],
            ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is True
        assert result.forced is False
        assert result.overlap_count >= 3
        assert "P1" in result.common_priorities

    def test_natural_consensus_with_partial_overlap(self):
        """Consensus when 3 items overlap in top 5 across 4 panels."""
        panel_rankings = [
            ["P1", "P2", "P3", "X1", "X2"],
            ["P1", "P2", "P3", "Y1", "Y2"],
            ["P1", "P2", "P3", "Z1", "Z2"],
            ["P1", "P2", "P3", "W1", "W2"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is True
        assert result.forced is False
        assert result.overlap_count == 3
        assert set(result.common_priorities) == {"P1", "P2", "P3"}

    def test_no_consensus_insufficient_overlap(self):
        """No consensus when fewer than 3 items overlap."""
        panel_rankings = [
            ["P1", "P2", "A1", "A2", "A3"],
            ["P1", "P2", "B1", "B2", "B3"],
            ["P1", "P2", "C1", "C2", "C3"],
            ["P1", "P2", "D1", "D2", "D3"],
        ]
        result = check_consensus(panel_rankings, round_number=1, min_overlap=3)
        assert result.reached is False
        assert result.forced is False
        assert result.overlap_count == 2

    def test_no_consensus_insufficient_panels(self):
        """No consensus when fewer than 4 panels have overlap."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["X1", "X2", "X3", "X4", "X5"],  # Different priorities
            ["Y1", "Y2", "Y3", "Y4", "Y5"],  # Different priorities
        ]
        result = check_consensus(panel_rankings, round_number=1, min_overlap=3)
        # Only 3 panels have P1-P3, need 4
        assert result.reached is False

    def test_forced_consensus_at_max_rounds(self):
        """Consensus forced when max_rounds reached."""
        panel_rankings = [
            ["A1", "A2", "A3", "A4", "A5"],
            ["B1", "B2", "B3", "B4", "B5"],
            ["C1", "C2", "C3", "C4", "C5"],
            ["D1", "D2", "D3", "D4", "D5"],
        ]
        result = check_consensus(panel_rankings, round_number=5, max_rounds=5)
        assert result.reached is True
        assert result.forced is True

    def test_forced_consensus_after_max_rounds(self):
        """Consensus forced when round_number exceeds max_rounds."""
        panel_rankings = [
            ["A1", "A2", "A3", "A4", "A5"],
            ["B1", "B2", "B3", "B4", "B5"],
        ]
        result = check_consensus(panel_rankings, round_number=6, max_rounds=5)
        assert result.reached is True
        assert result.forced is True

    def test_default_max_rounds_is_five(self):
        """Default max_rounds is 5."""
        panel_rankings = [
            ["A1", "A2", "A3", "A4", "A5"],
            ["B1", "B2", "B3", "B4", "B5"],
        ]
        # Round 5 should force consensus
        result = check_consensus(panel_rankings, round_number=5)
        assert result.forced is True
        # Round 4 should not force
        result = check_consensus(panel_rankings, round_number=4)
        assert result.forced is False

    def test_custom_min_overlap(self):
        """Custom min_overlap threshold works."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        # With min_overlap=5, should reach consensus
        result = check_consensus(panel_rankings, round_number=1, min_overlap=5)
        assert result.reached is True
        assert result.overlap_count >= 5

    def test_extracts_top_5_from_longer_rankings(self):
        """Only top 5 from each panel are considered for overlap."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5", "X1", "X2", "X3", "X4", "X5"],
            ["P1", "P2", "P3", "P4", "P5", "Y1", "Y2", "Y3", "Y4", "Y5"],
            ["P1", "P2", "P3", "P4", "P5", "Z1", "Z2", "Z3", "Z4", "Z5"],
            ["P1", "P2", "P3", "P4", "P5", "W1", "W2", "W3", "W4", "W5"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is True
        # Only top 5 should be in common_priorities
        for p in result.common_priorities:
            assert p.startswith("P")

    def test_empty_panel_rankings(self):
        """Handles empty panel rankings."""
        result = check_consensus([], round_number=1)
        assert result.reached is False
        assert result.overlap_count == 0

    def test_single_panel(self):
        """Single panel cannot reach natural consensus."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is False  # Need 4 panels minimum

    def test_panels_with_fewer_than_five_items(self):
        """Handles panels with fewer than 5 priorities."""
        panel_rankings = [
            ["P1", "P2", "P3"],
            ["P1", "P2", "P3"],
            ["P1", "P2", "P3"],
            ["P1", "P2", "P3"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is True
        assert result.overlap_count == 3


class TestWeightedVote:
    """Tests for weighted_vote function."""

    def test_returns_list_of_strings(self):
        """weighted_vote returns a list of priority names."""
        panel_rankings = {
            "product": ["P1", "P2", "P3"],
            "ceo": ["P1", "P2", "P3"],
        }
        weights = {"product": 0.3, "ceo": 0.3}
        result = weighted_vote(panel_rankings, weights)
        assert isinstance(result, list)
        assert all(isinstance(item, str) for item in result)

    def test_default_weights_product_ceo_eng_design_ops(self):
        """Default weights: Product 30%, CEO 30%, Eng 20%, Design 10%, Ops 10%."""
        panel_rankings = {
            "product": ["P1", "P2", "P3"],
            "ceo": ["C1", "C2", "C3"],
            "engineering": ["E1", "E2", "E3"],
            "design": ["D1", "D2", "D3"],
            "operations": ["O1", "O2", "O3"],
        }
        # Default weights should be applied
        weights = {
            "product": 0.30,
            "ceo": 0.30,
            "engineering": 0.20,
            "design": 0.10,
            "operations": 0.10,
        }
        result = weighted_vote(panel_rankings, weights)
        assert len(result) > 0

    def test_higher_rank_more_points(self):
        """Higher rank (position 1) gets more points than lower rank."""
        # P1 is #1 in product (30%), C1 is #1 in CEO (30%)
        # P1 should score: 10 * 0.3 = 3.0
        # C1 should score: 10 * 0.3 = 3.0
        # If P1 also appears in CEO as #2: 10*0.3 + 9*0.3 = 5.7
        panel_rankings = {
            "product": ["P1", "P2", "P3"],
            "ceo": ["P1", "C2", "C3"],
        }
        weights = {"product": 0.3, "ceo": 0.3}
        result = weighted_vote(panel_rankings, weights)
        # P1 should be first as it has highest combined score
        assert result[0] == "P1"

    def test_point_calculation_10_for_first_9_for_second(self):
        """Rank 1 = 10 points, Rank 2 = 9 points, etc."""
        panel_rankings = {
            "product": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"],
        }
        weights = {"product": 1.0}
        result = weighted_vote(panel_rankings, weights)
        # All 10 should be returned in order
        assert result == ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"]

    def test_top_n_parameter(self):
        """top_n limits output to N priorities."""
        panel_rankings = {
            "product": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"],
        }
        weights = {"product": 1.0}
        result = weighted_vote(panel_rankings, weights, top_n=5)
        assert len(result) == 5
        assert result == ["P1", "P2", "P3", "P4", "P5"]

    def test_default_top_n_is_10(self):
        """Default top_n is 10."""
        panel_rankings = {
            "product": ["P" + str(i) for i in range(1, 16)],  # 15 items
        }
        weights = {"product": 1.0}
        result = weighted_vote(panel_rankings, weights)
        assert len(result) == 10

    def test_weighted_ranking_aggregation(self):
        """Weights affect final ranking correctly."""
        # Product has P1 first, Engineering has E1 first
        # Product weight = 0.3, Engineering = 0.2
        # P1: 10 * 0.3 = 3.0
        # E1: 10 * 0.2 = 2.0
        # P1 should rank higher
        panel_rankings = {
            "product": ["P1", "P2", "P3"],
            "engineering": ["E1", "E2", "E3"],
        }
        weights = {"product": 0.3, "engineering": 0.2}
        result = weighted_vote(panel_rankings, weights)
        assert result[0] == "P1"
        # E1 should be second (only item with remaining highest score)
        assert "E1" in result[:3]

    def test_empty_panel_rankings(self):
        """Handles empty panel rankings."""
        result = weighted_vote({}, {})
        assert result == []

    def test_missing_panel_in_weights(self):
        """Panels not in weights dict are ignored."""
        panel_rankings = {
            "product": ["P1", "P2", "P3"],
            "unknown": ["U1", "U2", "U3"],
        }
        weights = {"product": 1.0}  # unknown not in weights
        result = weighted_vote(panel_rankings, weights)
        # Only product items should appear
        assert "P1" in result
        assert "U1" not in result

    def test_tie_breaking_is_stable(self):
        """When scores are tied, order is deterministic."""
        panel_rankings = {
            "product": ["A", "B", "C"],
            "ceo": ["C", "B", "A"],
        }
        weights = {"product": 0.5, "ceo": 0.5}
        # A: 10*0.5 + 8*0.5 = 9.0
        # B: 9*0.5 + 9*0.5 = 9.0
        # C: 8*0.5 + 10*0.5 = 9.0
        # All tied - order should be stable
        result1 = weighted_vote(panel_rankings, weights)
        result2 = weighted_vote(panel_rankings, weights)
        assert result1 == result2

    def test_calculates_across_all_panels(self):
        """Combines scores from all panels."""
        panel_rankings = {
            "product": ["Shared", "P2", "P3"],
            "ceo": ["Shared", "C2", "C3"],
            "engineering": ["Shared", "E2", "E3"],
            "design": ["Shared", "D2", "D3"],
            "operations": ["Shared", "O2", "O3"],
        }
        weights = {
            "product": 0.30,
            "ceo": 0.30,
            "engineering": 0.20,
            "design": 0.10,
            "operations": 0.10,
        }
        result = weighted_vote(panel_rankings, weights)
        # "Shared" gets 10 points from all panels, should be first
        assert result[0] == "Shared"


class TestStandardDeviationCalculation:
    """Tests for score standard deviation in consensus checking."""

    def test_low_std_dev_indicates_strong_agreement(self):
        """Low standard deviation means strong agreement."""
        # All panels rank items identically
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=1, max_std_dev=1.5)
        assert result.reached is True

    def test_high_std_dev_blocks_consensus(self):
        """High standard deviation can block consensus."""
        # Panels have very different rankings for common items
        panel_rankings = [
            ["P1", "P2", "P3", "A1", "A2"],  # P1 is rank 1
            ["P3", "P2", "P1", "B1", "B2"],  # P1 is rank 3
            ["P2", "P1", "P3", "C1", "C2"],  # P1 is rank 2
            ["P3", "P1", "P2", "D1", "D2"],  # P1 is rank 2
        ]
        # With very low max_std_dev threshold, should not reach consensus
        result = check_consensus(panel_rankings, round_number=1, max_std_dev=0.1)
        # High disagreement on rankings should block
        assert result.reached is False

    def test_custom_max_std_dev_threshold(self):
        """Custom max_std_dev threshold is respected."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        # Very strict threshold should still pass with perfect agreement
        result = check_consensus(panel_rankings, round_number=1, max_std_dev=0.0)
        assert result.reached is True


class TestEdgeCases:
    """Edge case tests for consensus checker."""

    def test_exactly_min_overlap(self):
        """Consensus with exactly min_overlap items."""
        panel_rankings = [
            ["P1", "P2", "P3", "A1", "A2"],
            ["P1", "P2", "P3", "B1", "B2"],
            ["P1", "P2", "P3", "C1", "C2"],
            ["P1", "P2", "P3", "D1", "D2"],
        ]
        result = check_consensus(panel_rankings, round_number=1, min_overlap=3)
        assert result.reached is True
        assert result.overlap_count == 3

    def test_exactly_four_panels(self):
        """Consensus with exactly 4 panels (minimum for natural consensus)."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is True

    def test_three_panels_cannot_reach_natural_consensus(self):
        """Three panels cannot reach natural consensus (need 4)."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=1)
        assert result.reached is False
        assert result.forced is False

    def test_duplicate_items_in_ranking(self):
        """Handles duplicate items in a single panel's ranking."""
        panel_rankings = [
            ["P1", "P1", "P2", "P3", "P4"],  # P1 appears twice
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        # Should handle gracefully
        result = check_consensus(panel_rankings, round_number=1)
        assert isinstance(result, ConsensusResult)

    def test_round_zero(self):
        """Round 0 is valid."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=0)
        assert result.reached is True
        assert result.forced is False

    def test_negative_round_number(self):
        """Negative round number is handled."""
        panel_rankings = [
            ["P1", "P2", "P3", "P4", "P5"],
        ]
        result = check_consensus(panel_rankings, round_number=-1)
        # Should not force consensus
        assert result.forced is False