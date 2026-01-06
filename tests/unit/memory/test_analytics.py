"""TDD tests for memory analytics and reporting.

Tests for MemoryAnalytics class that will be created in swarm_attack/memory/analytics.py.

The analytics module provides:
- category_counts(): Entry counts per category
- hit_rate(): Query success rate (entries with hit_count > 0)
- age_distribution(): Entry age histogram in day buckets
- relevance_distribution(): Relevance score histogram
- growth_timeline(): Entries created per day
- generate_report(): Text report with all analytics data

TDD RED PHASE: Tests should FAIL because MemoryAnalytics doesn't exist yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryStore, MemoryEntry

# This import will fail initially (TDD RED phase)
from swarm_attack.memory.analytics import MemoryAnalytics


def _create_entry(
    category: str = "test_category",
    hit_count: int = 0,
    created_at: datetime | None = None,
    feature_id: str = "test-feature",
    content: dict | None = None,
    tags: list[str] | None = None,
) -> MemoryEntry:
    """Create a sample MemoryEntry for testing.

    Args:
        category: Entry category.
        hit_count: Number of times entry was accessed.
        created_at: Timestamp for entry creation. Defaults to now.
        feature_id: Feature ID.
        content: Optional content dictionary.
        tags: Optional list of tags.

    Returns:
        MemoryEntry with specified attributes.
    """
    if created_at is None:
        created_at = datetime.now()

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


@pytest.fixture
def analytics(memory_store: MemoryStore) -> MemoryAnalytics:
    """Create a MemoryAnalytics instance with the test store."""
    return MemoryAnalytics(memory_store)


# =============================================================================
# Test 1: test_entry_count_by_category - counts per category
# =============================================================================


class TestEntryCategoryCount:
    """Tests for category_counts() method."""

    def test_entry_count_by_category_single_category(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """category_counts returns correct count for single category."""
        # Arrange - Add entries in one category
        for _ in range(5):
            memory_store.add(_create_entry(category="schema_drift"))

        # Act
        counts = analytics.category_counts()

        # Assert
        assert counts == {"schema_drift": 5}

    def test_entry_count_by_category_multiple_categories(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """category_counts returns correct counts for multiple categories."""
        # Arrange - Add entries in multiple categories
        for _ in range(5):
            memory_store.add(_create_entry(category="schema_drift"))
        for _ in range(3):
            memory_store.add(_create_entry(category="bug_fix"))
        for _ in range(7):
            memory_store.add(_create_entry(category="verification_failure"))

        # Act
        counts = analytics.category_counts()

        # Assert
        assert counts == {
            "schema_drift": 5,
            "bug_fix": 3,
            "verification_failure": 7,
        }

    def test_entry_count_by_category_empty_store(
        self, analytics: MemoryAnalytics
    ) -> None:
        """category_counts returns empty dict for empty store."""
        # Act
        counts = analytics.category_counts()

        # Assert
        assert counts == {}

    def test_entry_count_by_category_returns_dict(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """category_counts returns a Dict[str, int]."""
        # Arrange
        memory_store.add(_create_entry(category="test"))

        # Act
        counts = analytics.category_counts()

        # Assert
        assert isinstance(counts, dict)
        for key, value in counts.items():
            assert isinstance(key, str)
            assert isinstance(value, int)


# =============================================================================
# Test 2: test_hit_rate_calculation - query success rate
# =============================================================================


class TestHitRateCalculation:
    """Tests for hit_rate() method."""

    def test_hit_rate_calculation_all_hits(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """hit_rate returns 1.0 when all entries have been hit."""
        # Arrange - All entries have hit_count > 0
        for i in range(5):
            memory_store.add(_create_entry(hit_count=i + 1))  # 1, 2, 3, 4, 5

        # Act
        rate = analytics.hit_rate()

        # Assert
        assert rate == 1.0

    def test_hit_rate_calculation_no_hits(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """hit_rate returns 0.0 when no entries have been hit."""
        # Arrange - All entries have hit_count = 0
        for _ in range(5):
            memory_store.add(_create_entry(hit_count=0))

        # Act
        rate = analytics.hit_rate()

        # Assert
        assert rate == 0.0

    def test_hit_rate_calculation_partial_hits(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """hit_rate returns correct ratio for partial hits."""
        # Arrange - 3 out of 5 entries have hits
        memory_store.add(_create_entry(hit_count=5))
        memory_store.add(_create_entry(hit_count=0))
        memory_store.add(_create_entry(hit_count=2))
        memory_store.add(_create_entry(hit_count=0))
        memory_store.add(_create_entry(hit_count=1))

        # Act
        rate = analytics.hit_rate()

        # Assert - 3/5 = 0.6
        assert rate == pytest.approx(0.6, rel=0.01)

    def test_hit_rate_calculation_empty_store(
        self, analytics: MemoryAnalytics
    ) -> None:
        """hit_rate returns 0.0 for empty store."""
        # Act
        rate = analytics.hit_rate()

        # Assert
        assert rate == 0.0

    def test_hit_rate_calculation_single_entry_with_hit(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """hit_rate returns 1.0 for single entry with hit."""
        # Arrange
        memory_store.add(_create_entry(hit_count=10))

        # Act
        rate = analytics.hit_rate()

        # Assert
        assert rate == 1.0

    def test_hit_rate_calculation_single_entry_without_hit(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """hit_rate returns 0.0 for single entry without hit."""
        # Arrange
        memory_store.add(_create_entry(hit_count=0))

        # Act
        rate = analytics.hit_rate()

        # Assert
        assert rate == 0.0


# =============================================================================
# Test 3: test_age_distribution - entry age histogram
# =============================================================================


class TestAgeDistribution:
    """Tests for age_distribution() method."""

    def test_age_distribution_all_recent(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """age_distribution places recent entries in first bucket."""
        # Arrange - All entries created today
        now = datetime.now()
        for _ in range(5):
            memory_store.add(_create_entry(created_at=now))

        # Act
        dist = analytics.age_distribution(buckets=5)

        # Assert - All entries should be in first bucket (0-7 days)
        assert "0-7 days" in dist
        assert dist["0-7 days"] == 5

    def test_age_distribution_varied_ages(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """age_distribution correctly buckets entries by age."""
        now = datetime.now()

        # Arrange - Create entries with different ages
        # 3 entries from today (0-7 days bucket)
        for _ in range(3):
            memory_store.add(_create_entry(created_at=now))

        # 2 entries from 10 days ago (8-14 days bucket)
        for _ in range(2):
            memory_store.add(_create_entry(created_at=now - timedelta(days=10)))

        # 1 entry from 20 days ago (15-21 days bucket)
        memory_store.add(_create_entry(created_at=now - timedelta(days=20)))

        # Act
        dist = analytics.age_distribution(buckets=5)

        # Assert
        assert dist.get("0-7 days", 0) == 3
        assert dist.get("8-14 days", 0) == 2
        assert dist.get("15-21 days", 0) == 1

    def test_age_distribution_empty_store(
        self, analytics: MemoryAnalytics
    ) -> None:
        """age_distribution returns empty buckets for empty store."""
        # Act
        dist = analytics.age_distribution(buckets=5)

        # Assert - Should return dict with bucket labels but zero counts
        assert isinstance(dist, dict)
        # All values should be 0
        total = sum(dist.values())
        assert total == 0

    def test_age_distribution_returns_dict_with_string_keys(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """age_distribution returns Dict[str, int] with day range labels."""
        # Arrange
        memory_store.add(_create_entry())

        # Act
        dist = analytics.age_distribution(buckets=5)

        # Assert
        assert isinstance(dist, dict)
        for key, value in dist.items():
            assert isinstance(key, str)
            assert isinstance(value, int)
            # Keys should contain "days"
            assert "days" in key.lower()

    def test_age_distribution_custom_buckets(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """age_distribution respects custom bucket count."""
        # Arrange
        memory_store.add(_create_entry())

        # Act - Request 3 buckets
        dist = analytics.age_distribution(buckets=3)

        # Assert - Should have 3 buckets
        assert len(dist) == 3

    def test_age_distribution_default_buckets_is_five(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """age_distribution defaults to 5 buckets."""
        # Arrange
        memory_store.add(_create_entry())

        # Act - No buckets parameter
        dist = analytics.age_distribution()

        # Assert - Should have 5 buckets by default
        assert len(dist) == 5


# =============================================================================
# Test 4: test_relevance_distribution - relevance score histogram
# =============================================================================


class TestRelevanceDistribution:
    """Tests for relevance_distribution() method."""

    def test_relevance_distribution_returns_histogram(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """relevance_distribution returns a histogram dict."""
        # Arrange - Create entries with varying relevance factors
        now = datetime.now()
        memory_store.add(_create_entry(hit_count=0, created_at=now - timedelta(days=30)))
        memory_store.add(_create_entry(hit_count=5, created_at=now))
        memory_store.add(_create_entry(hit_count=10, created_at=now))

        # Act
        dist = analytics.relevance_distribution(buckets=5)

        # Assert
        assert isinstance(dist, dict)
        # Total entries should match
        total = sum(dist.values())
        assert total == 3

    def test_relevance_distribution_empty_store(
        self, analytics: MemoryAnalytics
    ) -> None:
        """relevance_distribution returns empty histogram for empty store."""
        # Act
        dist = analytics.relevance_distribution(buckets=5)

        # Assert
        assert isinstance(dist, dict)
        total = sum(dist.values())
        assert total == 0

    def test_relevance_distribution_bucket_labels_are_ranges(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """relevance_distribution bucket labels should be score ranges."""
        # Arrange
        memory_store.add(_create_entry(hit_count=1))

        # Act
        dist = analytics.relevance_distribution(buckets=5)

        # Assert - Keys should be score range labels like "0.0-0.2"
        assert isinstance(dist, dict)
        for key in dist.keys():
            assert isinstance(key, str)
            # Should contain a hyphen indicating range
            assert "-" in key

    def test_relevance_distribution_default_buckets_is_five(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """relevance_distribution defaults to 5 buckets."""
        # Arrange
        memory_store.add(_create_entry())

        # Act
        dist = analytics.relevance_distribution()

        # Assert
        assert len(dist) == 5

    def test_relevance_distribution_custom_buckets(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """relevance_distribution respects custom bucket count."""
        # Arrange
        memory_store.add(_create_entry())

        # Act
        dist = analytics.relevance_distribution(buckets=10)

        # Assert
        assert len(dist) == 10

    def test_relevance_distribution_high_relevance_entries(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """relevance_distribution places high-value entries in higher buckets."""
        # Arrange - Create high relevance entries (high hits, recent)
        now = datetime.now()
        for _ in range(5):
            memory_store.add(_create_entry(
                hit_count=50,
                created_at=now,
                category="schema_warning"  # High weight category
            ))

        # Act
        dist = analytics.relevance_distribution(buckets=5)

        # Assert - Most entries should be in higher buckets
        # Get the last bucket (highest scores)
        bucket_keys = list(dist.keys())
        high_buckets = bucket_keys[-2:]  # Last 2 buckets
        high_bucket_count = sum(dist[k] for k in high_buckets)
        assert high_bucket_count >= 3, (
            f"High relevance entries should be in higher buckets. Got dist: {dist}"
        )


# =============================================================================
# Test 5: test_growth_over_time - entries added over time
# =============================================================================


class TestGrowthTimeline:
    """Tests for growth_timeline() method."""

    def test_growth_over_time_single_day(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline shows entries for a single day."""
        # Arrange - All entries created today
        now = datetime.now()
        for _ in range(5):
            memory_store.add(_create_entry(created_at=now))

        # Act
        timeline = analytics.growth_timeline(days=7)

        # Assert
        today_key = now.strftime("%Y-%m-%d")
        assert today_key in timeline
        assert timeline[today_key] == 5

    def test_growth_over_time_multiple_days(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline shows entries spread across multiple days."""
        now = datetime.now()

        # Arrange - Create entries on different days
        # 3 today
        for _ in range(3):
            memory_store.add(_create_entry(created_at=now))

        # 2 yesterday
        yesterday = now - timedelta(days=1)
        for _ in range(2):
            memory_store.add(_create_entry(created_at=yesterday))

        # 4 two days ago
        two_days_ago = now - timedelta(days=2)
        for _ in range(4):
            memory_store.add(_create_entry(created_at=two_days_ago))

        # Act
        timeline = analytics.growth_timeline(days=7)

        # Assert
        assert timeline.get(now.strftime("%Y-%m-%d"), 0) == 3
        assert timeline.get(yesterday.strftime("%Y-%m-%d"), 0) == 2
        assert timeline.get(two_days_ago.strftime("%Y-%m-%d"), 0) == 4

    def test_growth_over_time_empty_store(
        self, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline returns dates with zero counts for empty store."""
        # Act
        timeline = analytics.growth_timeline(days=7)

        # Assert - Should have 7 days of dates with zero values
        assert isinstance(timeline, dict)
        assert len(timeline) == 7
        for count in timeline.values():
            assert count == 0

    def test_growth_over_time_returns_dict_with_date_keys(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline returns Dict[str, int] with date string keys."""
        # Arrange
        memory_store.add(_create_entry())

        # Act
        timeline = analytics.growth_timeline(days=7)

        # Assert
        assert isinstance(timeline, dict)
        for key, value in timeline.items():
            assert isinstance(key, str)
            assert isinstance(value, int)
            # Key should be a valid date format YYYY-MM-DD
            datetime.strptime(key, "%Y-%m-%d")  # Will raise if invalid

    def test_growth_over_time_default_days_is_seven(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline defaults to 7 days."""
        # Arrange
        memory_store.add(_create_entry())

        # Act
        timeline = analytics.growth_timeline()

        # Assert
        assert len(timeline) == 7

    def test_growth_over_time_custom_days(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline respects custom days parameter."""
        # Arrange
        memory_store.add(_create_entry())

        # Act
        timeline = analytics.growth_timeline(days=14)

        # Assert
        assert len(timeline) == 14

    def test_growth_over_time_excludes_old_entries(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """growth_timeline only includes entries within the time window."""
        now = datetime.now()

        # Arrange - Create entry from 10 days ago (outside 7-day window)
        old_date = now - timedelta(days=10)
        memory_store.add(_create_entry(created_at=old_date))

        # Also add an entry from today
        memory_store.add(_create_entry(created_at=now))

        # Act
        timeline = analytics.growth_timeline(days=7)

        # Assert - Only today's entry should be counted
        total = sum(timeline.values())
        assert total == 1


# =============================================================================
# Test: generate_report() - text report generation
# =============================================================================


class TestGenerateReport:
    """Tests for generate_report() method."""

    def test_generate_report_returns_non_empty_string(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """generate_report returns a non-empty string."""
        # Arrange
        memory_store.add(_create_entry(category="bug_fix", hit_count=5))

        # Act
        report = analytics.generate_report()

        # Assert
        assert isinstance(report, str)
        assert len(report) > 0

    def test_generate_report_includes_category_counts(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """generate_report includes category count information."""
        # Arrange
        memory_store.add(_create_entry(category="schema_drift"))
        memory_store.add(_create_entry(category="bug_fix"))

        # Act
        report = analytics.generate_report()

        # Assert - Report should mention categories
        assert "schema_drift" in report or "category" in report.lower()

    def test_generate_report_includes_hit_rate(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """generate_report includes hit rate information."""
        # Arrange
        memory_store.add(_create_entry(hit_count=5))
        memory_store.add(_create_entry(hit_count=0))

        # Act
        report = analytics.generate_report()

        # Assert - Report should mention hit rate
        assert "hit" in report.lower() or "rate" in report.lower()

    def test_generate_report_empty_store(
        self, analytics: MemoryAnalytics
    ) -> None:
        """generate_report works for empty store."""
        # Act
        report = analytics.generate_report()

        # Assert - Should return valid string (even if empty or minimal)
        assert isinstance(report, str)

    def test_generate_report_includes_total_entries(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """generate_report includes total entry count."""
        # Arrange
        for _ in range(10):
            memory_store.add(_create_entry())

        # Act
        report = analytics.generate_report()

        # Assert - Report should include total count
        assert "10" in report or "total" in report.lower()


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestAnalyticsEdgeCases:
    """Edge case tests for MemoryAnalytics."""

    def test_analytics_single_entry(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """Analytics work correctly with a single entry."""
        # Arrange
        now = datetime.now()
        memory_store.add(_create_entry(
            category="bug_fix",
            hit_count=3,
            created_at=now
        ))

        # Act
        counts = analytics.category_counts()
        rate = analytics.hit_rate()
        age_dist = analytics.age_distribution()
        growth = analytics.growth_timeline(days=7)

        # Assert
        assert counts == {"bug_fix": 1}
        assert rate == 1.0  # Single entry with hits
        assert sum(age_dist.values()) == 1
        assert sum(growth.values()) == 1

    def test_analytics_store_reference(
        self, memory_store: MemoryStore
    ) -> None:
        """MemoryAnalytics stores reference to MemoryStore."""
        # Arrange & Act
        analytics = MemoryAnalytics(memory_store)

        # Assert
        assert analytics.store is memory_store

    def test_analytics_reflects_store_changes(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """Analytics reflects changes to the underlying store."""
        # Arrange - Start with empty store
        assert analytics.category_counts() == {}

        # Act - Add entries after analytics created
        memory_store.add(_create_entry(category="new_category"))

        # Assert - Analytics should see the new entry
        counts = analytics.category_counts()
        assert counts == {"new_category": 1}

    def test_analytics_large_dataset(
        self, memory_store: MemoryStore, analytics: MemoryAnalytics
    ) -> None:
        """Analytics handle large number of entries."""
        # Arrange - Add many entries
        now = datetime.now()
        categories = ["schema_drift", "bug_fix", "test_failure", "recovery_action"]
        for i in range(100):
            memory_store.add(_create_entry(
                category=categories[i % len(categories)],
                hit_count=i % 10,
                created_at=now - timedelta(days=i % 30)
            ))

        # Act - All analytics should complete without error
        counts = analytics.category_counts()
        rate = analytics.hit_rate()
        age_dist = analytics.age_distribution()
        rel_dist = analytics.relevance_distribution()
        growth = analytics.growth_timeline(days=30)
        report = analytics.generate_report()

        # Assert - Basic validations
        assert sum(counts.values()) == 100
        assert 0 <= rate <= 1.0
        assert sum(age_dist.values()) == 100
        assert sum(rel_dist.values()) == 100
        assert len(growth) == 30
        assert len(report) > 0
