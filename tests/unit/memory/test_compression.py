"""TDD tests for MemoryCompressor - memory entry compression.

Tests for the MemoryCompressor class that will be implemented in
swarm_attack/memory/compression.py.

These tests are written in TDD RED phase - they should FAIL because
MemoryCompressor doesn't exist yet.

MemoryCompressor compresses similar memory entries to reduce store size.
Entries are similar if they have:
- Same category
- Same feature_id
- Content keywords overlap >= similarity_threshold

When merging:
- Keep the most recent timestamp
- Sum hit_counts
- Merge tags (union)
- Keep most recent content
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry
from swarm_attack.memory.compression import MemoryCompressor


def _create_entry(
    category: str = "test_category",
    feature_id: str = "test-feature",
    content: dict | None = None,
    tags: list[str] | None = None,
    hit_count: int = 0,
    days_ago: int = 0,
) -> MemoryEntry:
    """Create a MemoryEntry with configurable attributes.

    Args:
        category: Entry category.
        feature_id: Feature ID.
        content: Content dictionary.
        tags: List of tags.
        hit_count: Number of times entry was accessed.
        days_ago: How many days ago the entry was created.

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
        tags=tags or [],
        hit_count=hit_count,
    )


class TestCompressSimilarEntries:
    """Tests for compress() merging similar entries."""

    def test_compress_similar_entries_merges_when_above_threshold(self) -> None:
        """Two entries with same category, feature_id, and overlapping keywords are merged."""
        # Arrange
        compressor = MemoryCompressor()

        # Two entries with same category and feature_id, overlapping content
        entry1 = _create_entry(
            category="schema_drift",
            feature_id="auth-feature",
            content={"class_name": "UserAuth", "field": "password", "error": "type mismatch"},
            tags=["auth", "schema"],
            hit_count=3,
            days_ago=5,
        )
        entry2 = _create_entry(
            category="schema_drift",
            feature_id="auth-feature",
            content={"class_name": "UserAuth", "field": "password", "error": "validation failed"},
            tags=["auth", "validation"],
            hit_count=2,
            days_ago=1,  # More recent
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert - Should merge into one entry
        assert len(result) == 1

    def test_compress_similar_entries_keeps_most_recent_content(self) -> None:
        """When merging, the most recent entry's content is preserved."""
        # Arrange
        compressor = MemoryCompressor()

        old_entry = _create_entry(
            category="test_failure",
            feature_id="api-tests",
            content={"test_path": "tests/test_api.py", "error": "old error message"},
            days_ago=10,
        )
        recent_entry = _create_entry(
            category="test_failure",
            feature_id="api-tests",
            content={"test_path": "tests/test_api.py", "error": "new error message"},
            days_ago=1,  # More recent
        )

        entries = [old_entry, recent_entry]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert - Should have recent content
        assert len(result) == 1
        assert result[0].content["error"] == "new error message"

    def test_compress_similar_entries_keeps_most_recent_timestamp(self) -> None:
        """When merging, the most recent timestamp is preserved."""
        # Arrange
        compressor = MemoryCompressor()

        old_entry = _create_entry(
            category="checkpoint_decision",
            feature_id="deploy",
            content={"action": "deploy", "env": "staging"},
            days_ago=7,
        )
        recent_entry = _create_entry(
            category="checkpoint_decision",
            feature_id="deploy",
            content={"action": "deploy", "env": "staging"},
            days_ago=0,  # Today
        )

        entries = [old_entry, recent_entry]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert - Should have recent timestamp
        assert len(result) == 1
        recent_time = datetime.fromisoformat(recent_entry.created_at)
        result_time = datetime.fromisoformat(result[0].created_at)
        # Result timestamp should be close to recent entry (within seconds)
        assert abs((result_time - recent_time).total_seconds()) < 60

    def test_compress_three_similar_entries_into_one(self) -> None:
        """Three similar entries should be merged into one."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="schema_drift",
            feature_id="user-model",
            content={"class_name": "User", "field": "email", "error": "missing"},
            hit_count=1,
            days_ago=5,
        )
        entry2 = _create_entry(
            category="schema_drift",
            feature_id="user-model",
            content={"class_name": "User", "field": "email", "error": "invalid"},
            hit_count=2,
            days_ago=3,
        )
        entry3 = _create_entry(
            category="schema_drift",
            feature_id="user-model",
            content={"class_name": "User", "field": "email", "error": "type error"},
            hit_count=3,
            days_ago=1,
        )

        entries = [entry1, entry2, entry3]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert
        assert len(result) == 1


class TestCompressionPreservesKeyInfo:
    """Tests for compression preserving important data."""

    def test_compression_preserves_category(self) -> None:
        """Merged entry preserves the category."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="test_failure",
            feature_id="unit-tests",
            content={"test": "test_foo", "error": "assertion"},
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="unit-tests",
            content={"test": "test_foo", "error": "timeout"},
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert
        assert len(result) == 1
        assert result[0].category == "test_failure"

    def test_compression_preserves_feature_id(self) -> None:
        """Merged entry preserves the feature_id."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="checkpoint_decision",
            feature_id="auth-feature-123",
            content={"action": "approve"},
        )
        entry2 = _create_entry(
            category="checkpoint_decision",
            feature_id="auth-feature-123",
            content={"action": "approve", "reason": "tests pass"},
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert
        assert len(result) == 1
        assert result[0].feature_id == "auth-feature-123"

    def test_compression_preserves_outcome_from_recent(self) -> None:
        """Merged entry preserves the outcome from the most recent entry."""
        # Arrange
        compressor = MemoryCompressor()

        old_entry = _create_entry(
            category="test_failure",
            feature_id="api-tests",
            content={"test": "test_endpoint"},
            days_ago=5,
        )
        old_entry_dict = old_entry.to_dict()
        old_entry = MemoryEntry.from_dict({**old_entry_dict, "outcome": "failure"})

        recent_entry = _create_entry(
            category="test_failure",
            feature_id="api-tests",
            content={"test": "test_endpoint"},
            days_ago=1,
        )
        recent_entry_dict = recent_entry.to_dict()
        recent_entry = MemoryEntry.from_dict({**recent_entry_dict, "outcome": "success"})

        entries = [old_entry, recent_entry]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert
        assert len(result) == 1
        assert result[0].outcome == "success"

    def test_compression_generates_new_id(self) -> None:
        """Merged entry should have a new unique ID."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "Foo"},
        )
        entry2 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "Foo", "extra": "data"},
        )

        original_ids = {entry1.id, entry2.id}
        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert - Result ID should be different from both originals
        assert len(result) == 1
        assert result[0].id not in original_ids


class TestCompressIncrementsHitCount:
    """Tests for hit_count summing during compression."""

    def test_compress_increments_hit_count_sums_values(self) -> None:
        """When merging, hit_counts are summed."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_foo"},
            hit_count=5,
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_foo"},
            hit_count=3,
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        assert result[0].hit_count == 8  # 5 + 3

    def test_compress_increments_hit_count_three_entries(self) -> None:
        """Hit counts from multiple entries are summed."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "User"},
            hit_count=10,
        )
        entry2 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "User"},
            hit_count=7,
        )
        entry3 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "User"},
            hit_count=3,
        )

        entries = [entry1, entry2, entry3]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        assert result[0].hit_count == 20  # 10 + 7 + 3

    def test_compress_increments_hit_count_preserves_zero(self) -> None:
        """Zero hit counts don't affect the sum incorrectly."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_bar"},
            hit_count=0,
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_bar"},
            hit_count=5,
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        assert result[0].hit_count == 5  # 0 + 5


class TestCompressUpdatesTags:
    """Tests for tag merging during compression."""

    def test_compress_updates_metadata_merges_tags_union(self) -> None:
        """When merging, tags are combined as union."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "User"},
            tags=["auth", "user"],
        )
        entry2 = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "User"},
            tags=["validation", "user"],
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        result_tags = set(result[0].tags)
        assert result_tags == {"auth", "user", "validation"}

    def test_compress_updates_metadata_handles_empty_tags(self) -> None:
        """Merging handles entries with empty tags."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_x"},
            tags=[],
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_x"},
            tags=["important", "regression"],
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        result_tags = set(result[0].tags)
        assert result_tags == {"important", "regression"}

    def test_compress_updates_metadata_deduplicates_tags(self) -> None:
        """Duplicate tags are deduplicated."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="checkpoint_decision",
            feature_id="deploy",
            content={"action": "approve"},
            tags=["deploy", "staging", "approved"],
        )
        entry2 = _create_entry(
            category="checkpoint_decision",
            feature_id="deploy",
            content={"action": "approve"},
            tags=["deploy", "staging", "production"],
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        result_tags = set(result[0].tags)
        assert result_tags == {"deploy", "staging", "approved", "production"}
        # Should have no duplicates in the list
        assert len(result[0].tags) == len(set(result[0].tags))


class TestNoCompressDifferentCategories:
    """Tests for entries with different categories staying separate."""

    def test_no_compress_different_categories_same_feature_id(self) -> None:
        """Entries with different categories are NOT merged, even with same feature_id."""
        # Arrange
        compressor = MemoryCompressor()

        schema_entry = _create_entry(
            category="schema_drift",
            feature_id="auth-feature",
            content={"class": "User", "field": "email"},
            hit_count=5,
        )
        failure_entry = _create_entry(
            category="test_failure",
            feature_id="auth-feature",
            content={"class": "User", "error": "assertion"},
            hit_count=3,
        )

        entries = [schema_entry, failure_entry]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert - Should NOT merge, stays as 2 entries
        assert len(result) == 2

    def test_no_compress_different_categories_overlapping_content(self) -> None:
        """Different categories are not merged even with highly similar content."""
        # Arrange
        compressor = MemoryCompressor()

        # Very similar content but different categories
        entry1 = _create_entry(
            category="checkpoint_decision",
            feature_id="deploy",
            content={"action": "approve", "env": "staging", "reason": "tests pass"},
        )
        entry2 = _create_entry(
            category="schema_drift",
            feature_id="deploy",
            content={"action": "approve", "env": "staging", "reason": "tests pass"},
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.1)  # Very low threshold

        # Assert - Different categories, should NOT merge
        assert len(result) == 2

    def test_no_compress_different_feature_ids_same_category(self) -> None:
        """Entries with different feature_ids are NOT merged, even with same category."""
        # Arrange
        compressor = MemoryCompressor()

        entry1 = _create_entry(
            category="test_failure",
            feature_id="feature-alpha",
            content={"test": "test_foo", "error": "assertion"},
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="feature-beta",
            content={"test": "test_foo", "error": "assertion"},
        )

        entries = [entry1, entry2]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert - Different feature_ids, should NOT merge
        assert len(result) == 2

    def test_no_compress_below_similarity_threshold(self) -> None:
        """Entries below similarity threshold are NOT merged."""
        # Arrange
        compressor = MemoryCompressor()

        # Same category and feature_id but different content
        entry1 = _create_entry(
            category="test_failure",
            feature_id="api-tests",
            content={"test": "test_authentication", "error": "unauthorized"},
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="api-tests",
            content={"test": "test_pagination", "error": "timeout"},
        )

        entries = [entry1, entry2]

        # Act - Use high threshold that content won't meet
        result = compressor.compress(entries, similarity_threshold=0.95)

        # Assert - Below threshold, should NOT merge
        assert len(result) == 2


class TestSimilarityMethod:
    """Tests for the similarity() method directly."""

    def test_similarity_returns_zero_for_different_category(self) -> None:
        """Similarity is 0.0 when categories differ."""
        # Arrange
        compressor = MemoryCompressor()

        entry_a = _create_entry(
            category="schema_drift",
            feature_id="auth",
            content={"class": "User"},
        )
        entry_b = _create_entry(
            category="test_failure",
            feature_id="auth",
            content={"class": "User"},
        )

        # Act
        score = compressor.similarity(entry_a, entry_b)

        # Assert
        assert score == 0.0

    def test_similarity_returns_zero_for_different_feature_id(self) -> None:
        """Similarity is 0.0 when feature_ids differ."""
        # Arrange
        compressor = MemoryCompressor()

        entry_a = _create_entry(
            category="test_failure",
            feature_id="feature-x",
            content={"test": "test_foo"},
        )
        entry_b = _create_entry(
            category="test_failure",
            feature_id="feature-y",
            content={"test": "test_foo"},
        )

        # Act
        score = compressor.similarity(entry_a, entry_b)

        # Assert
        assert score == 0.0

    def test_similarity_returns_one_for_identical_content(self) -> None:
        """Similarity is 1.0 when content is identical."""
        # Arrange
        compressor = MemoryCompressor()

        content = {"class": "User", "field": "email", "error": "type mismatch"}

        entry_a = _create_entry(
            category="schema_drift",
            feature_id="auth",
            content=content,
        )
        entry_b = _create_entry(
            category="schema_drift",
            feature_id="auth",
            content=content.copy(),
        )

        # Act
        score = compressor.similarity(entry_a, entry_b)

        # Assert
        assert score == 1.0

    def test_similarity_returns_partial_for_overlapping_keywords(self) -> None:
        """Similarity is between 0 and 1 for partial keyword overlap."""
        # Arrange
        compressor = MemoryCompressor()

        entry_a = _create_entry(
            category="test_failure",
            feature_id="api",
            content={"test": "test_auth", "error": "unauthorized", "status": "401"},
        )
        entry_b = _create_entry(
            category="test_failure",
            feature_id="api",
            content={"test": "test_auth", "error": "forbidden", "status": "403"},
        )

        # Act
        score = compressor.similarity(entry_a, entry_b)

        # Assert - Should be between 0 and 1 (partial overlap)
        assert 0.0 < score < 1.0

    def test_similarity_returns_zero_for_no_keyword_overlap(self) -> None:
        """Similarity is 0.0 when keywords don't overlap at all."""
        # Arrange
        compressor = MemoryCompressor()

        entry_a = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"class": "Alpha", "field": "x"},
        )
        entry_b = _create_entry(
            category="schema_drift",
            feature_id="model",
            content={"type": "Beta", "attr": "y"},
        )

        # Act
        score = compressor.similarity(entry_a, entry_b)

        # Assert
        assert score == 0.0

    def test_similarity_is_symmetric(self) -> None:
        """similarity(a, b) equals similarity(b, a)."""
        # Arrange
        compressor = MemoryCompressor()

        entry_a = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_foo", "error": "assertion", "line": "42"},
        )
        entry_b = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_foo", "error": "timeout", "duration": "5s"},
        )

        # Act
        score_ab = compressor.similarity(entry_a, entry_b)
        score_ba = compressor.similarity(entry_b, entry_a)

        # Assert
        assert score_ab == score_ba


class TestEdgeCases:
    """Edge case tests for compression."""

    def test_compress_empty_list_returns_empty(self) -> None:
        """Compressing empty list returns empty list."""
        # Arrange
        compressor = MemoryCompressor()

        # Act
        result = compressor.compress([], similarity_threshold=0.8)

        # Assert
        assert result == []

    def test_compress_single_entry_returns_same(self) -> None:
        """Compressing single entry returns list with that entry."""
        # Arrange
        compressor = MemoryCompressor()

        entry = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_solo"},
        )

        # Act
        result = compressor.compress([entry], similarity_threshold=0.8)

        # Assert
        assert len(result) == 1
        assert result[0].content == entry.content

    def test_compress_preserves_unrelated_entries(self) -> None:
        """Entries that don't match any other entry are preserved."""
        # Arrange
        compressor = MemoryCompressor()

        # Three completely different entries
        entry1 = _create_entry(
            category="schema_drift",
            feature_id="model-a",
            content={"class": "Alpha"},
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="tests-b",
            content={"test": "test_beta"},
        )
        entry3 = _create_entry(
            category="checkpoint_decision",
            feature_id="deploy-c",
            content={"action": "approve"},
        )

        entries = [entry1, entry2, entry3]

        # Act
        result = compressor.compress(entries, similarity_threshold=0.5)

        # Assert - All should be preserved, no merging
        assert len(result) == 3

    def test_compress_default_threshold_is_0_8(self) -> None:
        """Default similarity_threshold is 0.8."""
        # Arrange
        compressor = MemoryCompressor()

        # Entries with ~50% overlap should NOT merge with default threshold
        entry1 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_foo", "error": "assertion", "a": "1", "b": "2"},
        )
        entry2 = _create_entry(
            category="test_failure",
            feature_id="tests",
            content={"test": "test_foo", "error": "timeout", "c": "3", "d": "4"},
        )

        entries = [entry1, entry2]

        # Act - Use default threshold (0.8)
        result = compressor.compress(entries)

        # Assert - Should NOT merge with default 0.8 threshold
        assert len(result) == 2
