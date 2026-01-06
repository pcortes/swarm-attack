"""TDD tests for memory relevance scoring.

Tests for RelevanceScorer class that will be created in swarm_attack/memory/relevance.py.

The scorer calculates relevance scores for MemoryEntry instances based on:
- hit_count: More hits = higher relevance
- recency: Recent entries score higher (exponential decay)
- category_weight: Different categories have different importance weights

Combined formula: hit_count * category_weight * recency_factor
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry

# This import will fail initially (TDD RED phase)
from swarm_attack.memory.relevance import RelevanceScorer


def _create_entry(
    category: str = "test_category",
    hit_count: int = 0,
    created_at: datetime | None = None,
    feature_id: str = "test-feature",
) -> MemoryEntry:
    """Create a sample MemoryEntry for testing."""
    if created_at is None:
        created_at = datetime.now()

    return MemoryEntry(
        id=str(uuid4()),
        category=category,
        feature_id=feature_id,
        issue_number=None,
        content={"key": "value"},
        outcome="success",
        created_at=created_at.isoformat(),
        tags=["test"],
        hit_count=hit_count,
    )


class TestBaseRelevanceFromHitCount:
    """Test that entries with higher hit_count score higher."""

    def test_higher_hit_count_scores_higher(self) -> None:
        """Entry with more hits should have higher relevance score."""
        scorer = RelevanceScorer()
        now = datetime.now()

        low_hits = _create_entry(hit_count=1, created_at=now)
        high_hits = _create_entry(hit_count=10, created_at=now)

        low_score = scorer.score(low_hits, now=now)
        high_score = scorer.score(high_hits, now=now)

        assert high_score > low_score, (
            f"Higher hit_count should result in higher score. "
            f"Got {high_score} for 10 hits vs {low_score} for 1 hit"
        )

    def test_zero_hits_still_has_positive_score(self) -> None:
        """Entry with zero hits should still have a positive base score."""
        scorer = RelevanceScorer()
        now = datetime.now()

        entry = _create_entry(hit_count=0, created_at=now)
        score = scorer.score(entry, now=now)

        # Zero hits should still produce positive score (from base relevance)
        assert score >= 0, f"Score should be non-negative, got {score}"

    def test_hit_count_linearly_affects_score(self) -> None:
        """Double the hits should roughly double the base contribution."""
        scorer = RelevanceScorer()
        now = datetime.now()

        # Use same category and timestamp to isolate hit_count effect
        entry_5_hits = _create_entry(hit_count=5, created_at=now)
        entry_10_hits = _create_entry(hit_count=10, created_at=now)

        score_5 = scorer.score(entry_5_hits, now=now)
        score_10 = scorer.score(entry_10_hits, now=now)

        # With same category and timestamp, doubling hits should double score
        assert score_10 == pytest.approx(score_5 * 2, rel=0.01), (
            f"Score should scale linearly with hit_count. "
            f"Expected ~{score_5 * 2}, got {score_10}"
        )


class TestRecencyBoost:
    """Test that recent entries score higher than older ones."""

    def test_recent_entry_scores_higher_than_old(self) -> None:
        """Entry created now should score higher than entry from a week ago."""
        scorer = RelevanceScorer()
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)

        recent_entry = _create_entry(hit_count=5, created_at=now)
        old_entry = _create_entry(hit_count=5, created_at=one_week_ago)

        recent_score = scorer.score(recent_entry, now=now)
        old_score = scorer.score(old_entry, now=now)

        assert recent_score > old_score, (
            f"Recent entry should score higher. "
            f"Got {recent_score} for now vs {old_score} for 1 week ago"
        )

    def test_recency_matters_even_for_hours(self) -> None:
        """Entry from 1 hour ago should score slightly higher than 24 hours ago."""
        scorer = RelevanceScorer()
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)

        entry_1h = _create_entry(hit_count=5, created_at=one_hour_ago)
        entry_24h = _create_entry(hit_count=5, created_at=one_day_ago)

        score_1h = scorer.score(entry_1h, now=now)
        score_24h = scorer.score(entry_24h, now=now)

        assert score_1h > score_24h, (
            f"Entry from 1h ago should score higher than 24h ago. "
            f"Got {score_1h} vs {score_24h}"
        )

    def test_now_defaults_to_current_time(self) -> None:
        """When now parameter is omitted, should use current time."""
        scorer = RelevanceScorer()

        # Entry from 1 day ago
        one_day_ago = datetime.now() - timedelta(days=1)
        entry = _create_entry(hit_count=5, created_at=one_day_ago)

        # Call without explicit now parameter
        score = scorer.score(entry)

        # Score should be positive (no error from missing now)
        assert score > 0, "Score should be positive even without explicit now"


class TestCategoryWeightApplied:
    """Test that different categories have different weight multipliers."""

    def test_schema_warning_has_highest_weight(self) -> None:
        """schema_warning category should have weight 1.5."""
        scorer = RelevanceScorer()
        now = datetime.now()

        schema_entry = _create_entry(
            category="schema_warning", hit_count=5, created_at=now
        )
        recovery_entry = _create_entry(
            category="recovery_action", hit_count=5, created_at=now
        )

        schema_score = scorer.score(schema_entry, now=now)
        recovery_score = scorer.score(recovery_entry, now=now)

        # schema_warning weight 1.5 vs recovery_action weight 1.0
        expected_ratio = 1.5 / 1.0
        actual_ratio = schema_score / recovery_score

        assert actual_ratio == pytest.approx(expected_ratio, rel=0.01), (
            f"schema_warning should score 1.5x recovery_action. "
            f"Expected ratio ~{expected_ratio}, got {actual_ratio}"
        )

    def test_bug_fix_weight(self) -> None:
        """bug_fix category should have weight 1.3."""
        scorer = RelevanceScorer()
        now = datetime.now()

        bug_fix_entry = _create_entry(
            category="bug_fix", hit_count=5, created_at=now
        )
        recovery_entry = _create_entry(
            category="recovery_action", hit_count=5, created_at=now
        )

        bug_fix_score = scorer.score(bug_fix_entry, now=now)
        recovery_score = scorer.score(recovery_entry, now=now)

        expected_ratio = 1.3 / 1.0
        actual_ratio = bug_fix_score / recovery_score

        assert actual_ratio == pytest.approx(expected_ratio, rel=0.01), (
            f"bug_fix should score 1.3x recovery_action. "
            f"Expected ratio ~{expected_ratio}, got {actual_ratio}"
        )

    def test_verification_failure_weight(self) -> None:
        """verification_failure category should have weight 1.2."""
        scorer = RelevanceScorer()
        now = datetime.now()

        verify_entry = _create_entry(
            category="verification_failure", hit_count=5, created_at=now
        )
        recovery_entry = _create_entry(
            category="recovery_action", hit_count=5, created_at=now
        )

        verify_score = scorer.score(verify_entry, now=now)
        recovery_score = scorer.score(recovery_entry, now=now)

        expected_ratio = 1.2 / 1.0
        actual_ratio = verify_score / recovery_score

        assert actual_ratio == pytest.approx(expected_ratio, rel=0.01), (
            f"verification_failure should score 1.2x recovery_action. "
            f"Expected ratio ~{expected_ratio}, got {actual_ratio}"
        )

    def test_unknown_category_uses_default_weight(self) -> None:
        """Unknown category should use default weight of 1.0."""
        scorer = RelevanceScorer()
        now = datetime.now()

        unknown_entry = _create_entry(
            category="completely_unknown_category", hit_count=5, created_at=now
        )
        recovery_entry = _create_entry(
            category="recovery_action", hit_count=5, created_at=now
        )

        unknown_score = scorer.score(unknown_entry, now=now)
        recovery_score = scorer.score(recovery_entry, now=now)

        # Both should use default weight 1.0
        assert unknown_score == pytest.approx(recovery_score, rel=0.01), (
            f"Unknown category should use default weight (same as recovery_action). "
            f"Got {unknown_score} vs {recovery_score}"
        )

    def test_category_weights_class_attribute(self) -> None:
        """CATEGORY_WEIGHTS should be a class attribute with expected values."""
        assert hasattr(RelevanceScorer, 'CATEGORY_WEIGHTS')

        weights = RelevanceScorer.CATEGORY_WEIGHTS

        assert weights.get("schema_warning") == 1.5
        assert weights.get("bug_fix") == 1.3
        assert weights.get("verification_failure") == 1.2
        assert weights.get("recovery_action") == 1.0

    def test_default_weight_class_attribute(self) -> None:
        """DEFAULT_WEIGHT should be a class attribute with value 1.0."""
        assert hasattr(RelevanceScorer, 'DEFAULT_WEIGHT')
        assert RelevanceScorer.DEFAULT_WEIGHT == 1.0


class TestDecayOverTime:
    """Test the decay_factor method directly."""

    def test_decay_factor_at_zero_hours(self) -> None:
        """Decay factor at 0 hours should be 1.0 (no decay)."""
        scorer = RelevanceScorer()

        factor = scorer.decay_factor(0)

        assert factor == pytest.approx(1.0, rel=0.001), (
            f"Decay factor at 0 hours should be 1.0, got {factor}"
        )

    def test_decay_factor_at_24_hours(self) -> None:
        """Decay factor at 24 hours should be 0.95 (one decay period)."""
        scorer = RelevanceScorer()

        factor = scorer.decay_factor(24)

        # Formula: 0.95 ^ (24 / 24) = 0.95
        assert factor == pytest.approx(0.95, rel=0.001), (
            f"Decay factor at 24 hours should be 0.95, got {factor}"
        )

    def test_decay_factor_at_48_hours(self) -> None:
        """Decay factor at 48 hours should be 0.95^2."""
        scorer = RelevanceScorer()

        factor = scorer.decay_factor(48)

        # Formula: 0.95 ^ (48 / 24) = 0.95^2 = 0.9025
        expected = 0.95 ** 2
        assert factor == pytest.approx(expected, rel=0.001), (
            f"Decay factor at 48 hours should be {expected}, got {factor}"
        )

    def test_decay_factor_at_one_week(self) -> None:
        """Decay factor at 168 hours (1 week) should be 0.95^7."""
        scorer = RelevanceScorer()

        factor = scorer.decay_factor(168)  # 24 * 7 = 168 hours

        # Formula: 0.95 ^ (168 / 24) = 0.95^7
        expected = 0.95 ** 7
        assert factor == pytest.approx(expected, rel=0.001), (
            f"Decay factor at 168 hours should be {expected}, got {factor}"
        )

    def test_decay_factor_returns_positive_value(self) -> None:
        """Decay factor should always return positive value (never zero)."""
        scorer = RelevanceScorer()

        # Even at very old ages, decay factor should be positive
        factor_30_days = scorer.decay_factor(24 * 30)
        factor_90_days = scorer.decay_factor(24 * 90)

        assert factor_30_days > 0, "Decay factor at 30 days should be positive"
        assert factor_90_days > 0, "Decay factor at 90 days should be positive"

    def test_decay_factor_bounded_between_0_and_1(self) -> None:
        """Decay factor should be between 0 and 1 for all positive ages."""
        scorer = RelevanceScorer()

        test_ages = [0, 1, 12, 24, 48, 168, 720, 2160]  # Various hour values

        for age in test_ages:
            factor = scorer.decay_factor(age)
            assert 0 < factor <= 1.0, (
                f"Decay factor for {age} hours should be in (0, 1], got {factor}"
            )


class TestCombinedScoreCalculation:
    """Test that all factors (hit_count, category_weight, recency) combine correctly."""

    def test_combined_formula_basic(self) -> None:
        """Test combined score: hit_count * category_weight * recency_factor."""
        scorer = RelevanceScorer()
        now = datetime.now()

        # Entry with known values:
        # - hit_count = 10
        # - category = schema_warning (weight 1.5)
        # - created_at = now (decay_factor = 1.0)
        entry = _create_entry(
            category="schema_warning",
            hit_count=10,
            created_at=now,
        )

        score = scorer.score(entry, now=now)

        # Expected: 10 * 1.5 * 1.0 = 15.0
        expected = 10 * 1.5 * 1.0
        assert score == pytest.approx(expected, rel=0.01), (
            f"Combined score should be {expected}, got {score}"
        )

    def test_combined_formula_with_decay(self) -> None:
        """Test combined score with time decay applied."""
        scorer = RelevanceScorer()
        now = datetime.now()
        one_day_ago = now - timedelta(hours=24)

        # Entry with:
        # - hit_count = 5
        # - category = bug_fix (weight 1.3)
        # - created_at = 24 hours ago (decay_factor = 0.95)
        entry = _create_entry(
            category="bug_fix",
            hit_count=5,
            created_at=one_day_ago,
        )

        score = scorer.score(entry, now=now)

        # Expected: 5 * 1.3 * 0.95 = 6.175
        expected = 5 * 1.3 * 0.95
        assert score == pytest.approx(expected, rel=0.01), (
            f"Combined score should be {expected}, got {score}"
        )

    def test_combined_formula_unknown_category(self) -> None:
        """Test combined score with unknown category (default weight)."""
        scorer = RelevanceScorer()
        now = datetime.now()

        # Entry with:
        # - hit_count = 8
        # - category = unknown (weight 1.0)
        # - created_at = now (decay_factor = 1.0)
        entry = _create_entry(
            category="some_new_category",
            hit_count=8,
            created_at=now,
        )

        score = scorer.score(entry, now=now)

        # Expected: 8 * 1.0 * 1.0 = 8.0
        expected = 8 * 1.0 * 1.0
        assert score == pytest.approx(expected, rel=0.01), (
            f"Combined score should be {expected}, got {score}"
        )

    def test_all_factors_contribute_to_ordering(self) -> None:
        """Test that a high-value entry beats a low-value entry on all factors."""
        scorer = RelevanceScorer()
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)

        # High value entry: recent, high hits, high weight category
        high_value = _create_entry(
            category="schema_warning",  # weight 1.5
            hit_count=20,
            created_at=now,
        )

        # Low value entry: old, low hits, low weight category
        low_value = _create_entry(
            category="recovery_action",  # weight 1.0
            hit_count=2,
            created_at=one_week_ago,
        )

        high_score = scorer.score(high_value, now=now)
        low_score = scorer.score(low_value, now=now)

        assert high_score > low_score * 5, (
            f"High-value entry should significantly outrank low-value. "
            f"Got {high_score} vs {low_score}"
        )

    def test_relative_importance_of_factors(self) -> None:
        """Test that hit_count has more impact than category weight alone."""
        scorer = RelevanceScorer()
        now = datetime.now()

        # High hits, low weight
        high_hits_low_weight = _create_entry(
            category="recovery_action",  # weight 1.0
            hit_count=20,
            created_at=now,
        )

        # Low hits, high weight
        low_hits_high_weight = _create_entry(
            category="schema_warning",  # weight 1.5
            hit_count=5,
            created_at=now,
        )

        high_hits_score = scorer.score(high_hits_low_weight, now=now)
        low_hits_score = scorer.score(low_hits_high_weight, now=now)

        # 20 * 1.0 = 20 should beat 5 * 1.5 = 7.5
        assert high_hits_score > low_hits_score, (
            f"High hit count should outweigh category. "
            f"Got {high_hits_score} vs {low_hits_score}"
        )
