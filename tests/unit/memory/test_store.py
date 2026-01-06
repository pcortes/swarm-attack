"""TDD tests for MemoryStore relevance-based pruning and retrieval.

Tests for new methods that will be added to MemoryStore:
- prune_by_relevance(threshold: float, min_entries: int) -> int
- get_by_relevance(category: str, limit: int) -> List[MemoryEntry]

These tests are written in TDD RED phase - they should FAIL because
the methods don't exist yet on MemoryStore.

Relevance scoring is based on hit_count (usage frequency) and
created_at timestamp (recency). Higher hit counts and more recent
entries have higher relevance scores.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryStore, MemoryEntry


def _create_entry(
    category: str = "test_category",
    feature_id: str = "test-feature",
    hit_count: int = 0,
    days_ago: int = 0,
    content: dict | None = None,
    tags: list[str] | None = None,
) -> MemoryEntry:
    """Create a MemoryEntry with configurable relevance factors.

    Args:
        category: Entry category.
        feature_id: Feature ID.
        hit_count: Number of times entry was accessed (higher = more relevant).
        days_ago: How many days ago the entry was created (0 = now, higher = less recent).
        content: Optional content dictionary.
        tags: Optional list of tags.

    Returns:
        MemoryEntry with specified attributes.
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    return MemoryEntry(
        id=str(uuid4()),
        category=category,
        feature_id=feature_id,
        issue_number=None,
        content=content or {"key": "value"},
        outcome="success",
        created_at=created_at.isoformat(),
        tags=tags or ["test"],
        hit_count=hit_count,
    )


@pytest.fixture
def temp_store_path(tmp_path: Path) -> Path:
    """Provide a temporary path for store persistence."""
    return tmp_path / "test_memories.json"


@pytest.fixture
def memory_store(temp_store_path: Path) -> MemoryStore:
    """Create a MemoryStore with temporary storage path."""
    return MemoryStore(store_path=temp_store_path)


class TestPruneByRelevanceThreshold:
    """Tests for prune_by_relevance removing low relevance entries."""

    def test_prune_by_relevance_threshold_removes_low_relevance_entries(
        self, memory_store: MemoryStore
    ) -> None:
        """prune_by_relevance removes entries below the threshold.

        Entries with low hit counts and old timestamps should be pruned.
        """
        # Arrange - Create entries with varying relevance
        # Low relevance: 0 hits, 30 days old
        low_relevance_entry = _create_entry(
            feature_id="low-relevance",
            hit_count=0,
            days_ago=30,
        )
        memory_store.add(low_relevance_entry)

        # High relevance: 10 hits, created today
        high_relevance_entry = _create_entry(
            feature_id="high-relevance",
            hit_count=10,
            days_ago=0,
        )
        memory_store.add(high_relevance_entry)

        # Act - Prune with threshold that should remove low relevance entry
        removed_count = memory_store.prune_by_relevance(threshold=0.3)

        # Assert
        assert removed_count == 1
        assert memory_store.get_entry(low_relevance_entry.id) is None
        assert memory_store.get_entry(high_relevance_entry.id) is not None

    def test_prune_by_relevance_threshold_returns_removed_count(
        self, memory_store: MemoryStore
    ) -> None:
        """prune_by_relevance returns the count of removed entries."""
        # Arrange - Create multiple low relevance entries
        for i in range(5):
            entry = _create_entry(
                feature_id=f"low-{i}",
                hit_count=0,
                days_ago=60,  # Old entries
            )
            memory_store.add(entry)

        # One high relevance entry
        high_entry = _create_entry(
            feature_id="high",
            hit_count=20,
            days_ago=0,
        )
        memory_store.add(high_entry)

        # Act
        removed_count = memory_store.prune_by_relevance(threshold=0.3)

        # Assert
        assert removed_count == 5
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 1

    def test_prune_by_relevance_threshold_zero_removes_nothing(
        self, memory_store: MemoryStore
    ) -> None:
        """prune_by_relevance with threshold=0 removes no entries.

        All entries have relevance >= 0, so none should be pruned.
        """
        # Arrange
        entries = [
            _create_entry(feature_id=f"entry-{i}", hit_count=0, days_ago=100)
            for i in range(3)
        ]
        for entry in entries:
            memory_store.add(entry)

        # Act
        removed_count = memory_store.prune_by_relevance(threshold=0.0)

        # Assert
        assert removed_count == 0
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 3

    def test_prune_by_relevance_threshold_one_removes_all_below_max(
        self, memory_store: MemoryStore
    ) -> None:
        """prune_by_relevance with threshold=1.0 removes all but perfect entries.

        Only entries with maximum relevance score should survive.
        """
        # Arrange - Create entries with varying relevance
        low_entry = _create_entry(feature_id="low", hit_count=1, days_ago=10)
        medium_entry = _create_entry(feature_id="medium", hit_count=5, days_ago=5)
        memory_store.add(low_entry)
        memory_store.add(medium_entry)

        # Act - High threshold should remove entries below it
        # Note: With min_entries default, some may be kept
        removed_count = memory_store.prune_by_relevance(threshold=1.0, min_entries=0)

        # Assert - At least some entries should be removed
        assert removed_count >= 1


class TestPruneKeepsHighRelevance:
    """Tests for prune_by_relevance preserving high relevance entries."""

    def test_prune_keeps_high_relevance_entries_with_many_hits(
        self, memory_store: MemoryStore
    ) -> None:
        """Entries with high hit counts are preserved regardless of age."""
        # Arrange
        # Old but frequently accessed
        old_popular_entry = _create_entry(
            feature_id="old-popular",
            hit_count=100,
            days_ago=90,
        )
        memory_store.add(old_popular_entry)

        # Recent but never accessed
        new_unused_entry = _create_entry(
            feature_id="new-unused",
            hit_count=0,
            days_ago=1,
        )
        memory_store.add(new_unused_entry)

        # Act
        memory_store.prune_by_relevance(threshold=0.3, min_entries=0)

        # Assert - The popular entry should be kept
        assert memory_store.get_entry(old_popular_entry.id) is not None

    def test_prune_keeps_high_relevance_entries_that_are_recent(
        self, memory_store: MemoryStore
    ) -> None:
        """Recent entries are preserved even with low hit counts."""
        # Arrange
        # Very recent entry, even with few hits
        very_recent_entry = _create_entry(
            feature_id="very-recent",
            hit_count=1,
            days_ago=0,  # Created today
        )
        memory_store.add(very_recent_entry)

        # Old entry with moderate hits
        old_moderate_entry = _create_entry(
            feature_id="old-moderate",
            hit_count=3,
            days_ago=60,
        )
        memory_store.add(old_moderate_entry)

        # Act - Use a moderate threshold
        memory_store.prune_by_relevance(threshold=0.3, min_entries=0)

        # Assert - Recent entry should be preserved
        assert memory_store.get_entry(very_recent_entry.id) is not None

    def test_prune_keeps_all_entries_above_threshold(
        self, memory_store: MemoryStore
    ) -> None:
        """All entries scoring above threshold are preserved."""
        # Arrange - Create entries that should all be above threshold
        high_entries = [
            _create_entry(feature_id=f"high-{i}", hit_count=10 + i, days_ago=i)
            for i in range(5)
        ]
        for entry in high_entries:
            memory_store.add(entry)

        # Act - Use low threshold
        removed_count = memory_store.prune_by_relevance(threshold=0.1, min_entries=0)

        # Assert - None should be removed
        assert removed_count == 0
        for entry in high_entries:
            assert memory_store.get_entry(entry.id) is not None


class TestPruneRespectsMinimumEntries:
    """Tests for prune_by_relevance respecting min_entries parameter."""

    def test_prune_respects_minimum_entries_keeps_at_least_n(
        self, memory_store: MemoryStore
    ) -> None:
        """prune_by_relevance keeps at least min_entries even if all are low relevance."""
        # Arrange - Create only low relevance entries
        entries = [
            _create_entry(feature_id=f"low-{i}", hit_count=0, days_ago=100)
            for i in range(15)
        ]
        for entry in entries:
            memory_store.add(entry)

        # Act - Prune with high threshold but require keeping 10
        removed_count = memory_store.prune_by_relevance(threshold=0.9, min_entries=10)

        # Assert - Should have removed only 5 (15 - 10)
        assert removed_count == 5
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 10

    def test_prune_respects_minimum_entries_keeps_highest_relevance(
        self, memory_store: MemoryStore
    ) -> None:
        """When respecting min_entries, keeps the highest relevance entries."""
        # Arrange - Create entries with varying relevance
        low_entry = _create_entry(feature_id="low", hit_count=0, days_ago=100)
        medium_entry = _create_entry(feature_id="medium", hit_count=5, days_ago=50)
        high_entry = _create_entry(feature_id="high", hit_count=10, days_ago=10)

        memory_store.add(low_entry)
        memory_store.add(medium_entry)
        memory_store.add(high_entry)

        # Act - Prune with high threshold, keep at least 2
        memory_store.prune_by_relevance(threshold=0.9, min_entries=2)

        # Assert - Should keep the 2 highest relevance entries
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 2
        assert memory_store.get_entry(high_entry.id) is not None
        assert memory_store.get_entry(medium_entry.id) is not None
        assert memory_store.get_entry(low_entry.id) is None

    def test_prune_respects_minimum_entries_default_is_ten(
        self, memory_store: MemoryStore
    ) -> None:
        """Default min_entries should be 10."""
        # Arrange - Create 12 low relevance entries
        entries = [
            _create_entry(feature_id=f"low-{i}", hit_count=0, days_ago=200)
            for i in range(12)
        ]
        for entry in entries:
            memory_store.add(entry)

        # Act - Prune with very high threshold (should try to remove all)
        # but default min_entries=10 should preserve 10
        removed_count = memory_store.prune_by_relevance(threshold=0.99)

        # Assert
        assert removed_count == 2
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 10

    def test_prune_respects_minimum_entries_zero_allows_full_prune(
        self, memory_store: MemoryStore
    ) -> None:
        """min_entries=0 allows pruning all entries."""
        # Arrange - Create low relevance entries
        entries = [
            _create_entry(feature_id=f"low-{i}", hit_count=0, days_ago=365)
            for i in range(5)
        ]
        for entry in entries:
            memory_store.add(entry)

        # Act - Prune with high threshold and min_entries=0
        removed_count = memory_store.prune_by_relevance(threshold=0.99, min_entries=0)

        # Assert - All should be removed
        assert removed_count == 5
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 0

    def test_prune_respects_minimum_entries_when_fewer_exist(
        self, memory_store: MemoryStore
    ) -> None:
        """When fewer entries exist than min_entries, none are removed."""
        # Arrange - Create only 3 entries
        entries = [
            _create_entry(feature_id=f"entry-{i}", hit_count=0, days_ago=100)
            for i in range(3)
        ]
        for entry in entries:
            memory_store.add(entry)

        # Act - Require keeping 10, but only 3 exist
        removed_count = memory_store.prune_by_relevance(threshold=0.9, min_entries=10)

        # Assert - None should be removed
        assert removed_count == 0
        stats = memory_store.get_stats()
        assert stats["total_entries"] == 3


class TestGetEntriesSortedByRelevance:
    """Tests for get_by_relevance retrieval sorted by relevance score."""

    def test_get_entries_sorted_by_relevance_returns_highest_first(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance returns entries sorted by relevance, highest first."""
        # Arrange - Create entries with different relevance levels
        low_entry = _create_entry(feature_id="low", hit_count=1, days_ago=30)
        medium_entry = _create_entry(feature_id="medium", hit_count=10, days_ago=15)
        high_entry = _create_entry(feature_id="high", hit_count=50, days_ago=0)

        # Add in random order
        memory_store.add(medium_entry)
        memory_store.add(low_entry)
        memory_store.add(high_entry)

        # Act
        results = memory_store.get_by_relevance(limit=10)

        # Assert - Should be sorted high to low
        assert len(results) == 3
        assert results[0].feature_id == "high"
        assert results[1].feature_id == "medium"
        assert results[2].feature_id == "low"

    def test_get_entries_sorted_by_relevance_respects_limit(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance returns at most limit entries."""
        # Arrange - Create many entries
        for i in range(20):
            entry = _create_entry(feature_id=f"entry-{i}", hit_count=i, days_ago=i)
            memory_store.add(entry)

        # Act
        results = memory_store.get_by_relevance(limit=5)

        # Assert
        assert len(results) == 5

    def test_get_entries_sorted_by_relevance_filters_by_category(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance filters by category when specified."""
        # Arrange
        drift_entry = _create_entry(
            category="schema_drift",
            feature_id="drift-1",
            hit_count=10,
        )
        failure_entry = _create_entry(
            category="test_failure",
            feature_id="failure-1",
            hit_count=20,
        )
        checkpoint_entry = _create_entry(
            category="checkpoint_decision",
            feature_id="checkpoint-1",
            hit_count=15,
        )

        memory_store.add(drift_entry)
        memory_store.add(failure_entry)
        memory_store.add(checkpoint_entry)

        # Act
        results = memory_store.get_by_relevance(category="test_failure", limit=10)

        # Assert
        assert len(results) == 1
        assert results[0].category == "test_failure"
        assert results[0].feature_id == "failure-1"

    def test_get_entries_sorted_by_relevance_default_limit_is_ten(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance default limit should be 10."""
        # Arrange - Create 15 entries
        for i in range(15):
            entry = _create_entry(feature_id=f"entry-{i}", hit_count=i)
            memory_store.add(entry)

        # Act - No limit specified
        results = memory_store.get_by_relevance()

        # Assert
        assert len(results) == 10

    def test_get_entries_sorted_by_relevance_empty_store_returns_empty(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance on empty store returns empty list."""
        # Arrange - Store is empty

        # Act
        results = memory_store.get_by_relevance(limit=10)

        # Assert
        assert results == []

    def test_get_entries_sorted_by_relevance_category_not_found_returns_empty(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance with non-existent category returns empty list."""
        # Arrange
        entry = _create_entry(category="test_failure")
        memory_store.add(entry)

        # Act
        results = memory_store.get_by_relevance(category="nonexistent", limit=10)

        # Assert
        assert results == []

    def test_get_entries_sorted_by_relevance_considers_both_hits_and_recency(
        self, memory_store: MemoryStore
    ) -> None:
        """Relevance scoring considers both hit_count and recency."""
        # Arrange
        # Old with many hits - should still be relevant
        old_popular = _create_entry(
            feature_id="old-popular",
            hit_count=100,
            days_ago=60,
        )
        # New with few hits - recency helps
        new_quiet = _create_entry(
            feature_id="new-quiet",
            hit_count=2,
            days_ago=1,
        )
        # Old with few hits - lowest relevance
        old_quiet = _create_entry(
            feature_id="old-quiet",
            hit_count=1,
            days_ago=90,
        )

        memory_store.add(old_quiet)
        memory_store.add(new_quiet)
        memory_store.add(old_popular)

        # Act
        results = memory_store.get_by_relevance(limit=10)

        # Assert - Old popular should be first due to high hits
        assert results[0].feature_id == "old-popular"
        # Old quiet should be last
        assert results[-1].feature_id == "old-quiet"

    def test_get_entries_sorted_by_relevance_updates_hit_count(
        self, memory_store: MemoryStore
    ) -> None:
        """get_by_relevance should increment hit_count of returned entries."""
        # Arrange
        entry = _create_entry(feature_id="test", hit_count=5)
        memory_store.add(entry)
        original_hit_count = entry.hit_count

        # Act
        results = memory_store.get_by_relevance(limit=10)

        # Assert
        assert len(results) == 1
        # The returned entry should have incremented hit count
        assert results[0].hit_count == original_hit_count + 1


class TestRelevanceScoringIntegration:
    """Integration tests for relevance-based operations."""

    def test_prune_then_get_returns_only_remaining_entries(
        self, memory_store: MemoryStore
    ) -> None:
        """After pruning, get_by_relevance only returns remaining entries."""
        # Arrange
        # High relevance entries
        high_entries = [
            _create_entry(feature_id=f"high-{i}", hit_count=50, days_ago=i)
            for i in range(3)
        ]
        # Low relevance entries
        low_entries = [
            _create_entry(feature_id=f"low-{i}", hit_count=0, days_ago=100 + i)
            for i in range(5)
        ]

        for entry in high_entries + low_entries:
            memory_store.add(entry)

        # Act - Prune low relevance
        memory_store.prune_by_relevance(threshold=0.3, min_entries=0)

        # Then get remaining
        results = memory_store.get_by_relevance(limit=10)

        # Assert - Only high relevance entries remain
        assert len(results) == 3
        for result in results:
            assert result.feature_id.startswith("high-")

    def test_multiple_prunes_accumulate_removals(
        self, memory_store: MemoryStore
    ) -> None:
        """Multiple prune calls continue to remove entries."""
        # Arrange
        for i in range(10):
            entry = _create_entry(
                feature_id=f"entry-{i}",
                hit_count=i,  # 0 to 9 hits
                days_ago=10 - i,  # Most hits = most recent
            )
            memory_store.add(entry)

        # Act - First prune with low threshold
        removed1 = memory_store.prune_by_relevance(threshold=0.2, min_entries=0)

        # Second prune with higher threshold
        removed2 = memory_store.prune_by_relevance(threshold=0.5, min_entries=0)

        # Assert
        assert removed1 > 0  # Some should be removed
        assert removed2 >= 0  # Possibly more removed
        # Total remaining should be less than original
        stats = memory_store.get_stats()
        assert stats["total_entries"] < 10
