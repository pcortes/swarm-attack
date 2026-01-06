"""TDD tests for RecommendationEngine that provides recommendations based on memory patterns.

Tests for RecommendationEngine class that will be in swarm_attack/memory/recommendations.py:
- recommend_for_schema_drift() - get recommendations for schema drift issues
- recommend_for_test_failure() - suggest approach based on past similar failures
- get_recommendations() - general recommendations by category and context
- no recommendation for novel issues - return empty list for issues with no history
- recommendation confidence score - each recommendation must have confidence score
- recommendation source context - recommendations include source entry information
- multiple recommendations sorted by relevance - descending confidence order

The RecommendationEngine works with MemoryStore and optionally PatternDetector
to provide actionable recommendations based on historical patterns.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryStore, MemoryEntry
from swarm_attack.memory.patterns import PatternDetector
from swarm_attack.memory.recommendations import RecommendationEngine, Recommendation


def _create_schema_drift_entry(
    class_name: str,
    feature_id: str = "test-feature",
    days_ago: int = 0,
    outcome: str = "detected",
    drift_type: str = "field_mismatch",
    resolution: str | None = None,
    content_extra: dict | None = None,
) -> MemoryEntry:
    """Create a schema_drift MemoryEntry for testing.

    Args:
        class_name: Name of the class that drifted.
        feature_id: Feature ID.
        days_ago: How many days ago the entry was created.
        outcome: Outcome of the drift detection.
        drift_type: Type of schema drift.
        resolution: How the drift was resolved (for successful outcomes).
        content_extra: Additional content to merge.

    Returns:
        MemoryEntry with category="schema_drift".
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    content = {
        "class_name": class_name,
        "drift_type": drift_type,
        "file_path": f"swarm_attack/models/{class_name.lower()}.py",
    }
    if resolution:
        content["resolution"] = resolution
    if content_extra:
        content.update(content_extra)

    return MemoryEntry(
        id=str(uuid4()),
        category="schema_drift",
        feature_id=feature_id,
        issue_number=None,
        content=content,
        outcome=outcome,
        created_at=created_at.isoformat(),
        tags=["schema", class_name.lower()],
        hit_count=0,
    )


def _create_test_failure_entry(
    test_path: str,
    test_name: str,
    error_type: str = "AssertionError",
    feature_id: str = "test-feature",
    days_ago: int = 0,
    outcome: str = "failed",
    resolution: str | None = None,
    content_extra: dict | None = None,
) -> MemoryEntry:
    """Create a test_failure MemoryEntry for testing.

    Args:
        test_path: Path to the test file.
        test_name: Name of the failing test.
        error_type: Type of error (e.g., "AssertionError", "TypeError").
        feature_id: Feature ID.
        days_ago: How many days ago the entry was created.
        outcome: Outcome.
        resolution: How the failure was resolved (for successful outcomes).
        content_extra: Additional content to merge.

    Returns:
        MemoryEntry with category="test_failure".
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    content = {
        "test_path": test_path,
        "test_name": test_name,
        "error_type": error_type,
        "error_message": f"{error_type}: test assertion failed",
    }
    if resolution:
        content["resolution"] = resolution
    if content_extra:
        content.update(content_extra)

    return MemoryEntry(
        id=str(uuid4()),
        category="test_failure",
        feature_id=feature_id,
        issue_number=None,
        content=content,
        outcome=outcome,
        created_at=created_at.isoformat(),
        tags=["test", "failure", error_type.lower()],
        hit_count=0,
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
def pattern_detector(memory_store: MemoryStore) -> PatternDetector:
    """Create a PatternDetector with the memory store."""
    return PatternDetector(memory_store)


@pytest.fixture
def recommendation_engine(
    memory_store: MemoryStore, pattern_detector: PatternDetector
) -> RecommendationEngine:
    """Create a RecommendationEngine with memory store and pattern detector."""
    return RecommendationEngine(memory_store, pattern_detector)


class TestRecommendForSchemaDrift:
    """Tests for recommend_for_schema_drift returning suggestions."""

    def test_recommend_for_schema_drift_returns_suggestions(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Should return recommendations for schema drift issues.

        When there are historical schema drift entries for a class with
        successful resolutions, recommendations should be returned.
        """
        # Arrange - Add historical schema drift entries with resolutions
        entry1 = _create_schema_drift_entry(
            class_name="UserConfig",
            outcome="resolved",
            resolution="Add missing field 'timeout' with default value",
            days_ago=5,
        )
        memory_store.add(entry1)

        entry2 = _create_schema_drift_entry(
            class_name="UserConfig",
            outcome="resolved",
            resolution="Update type annotation to match parent class",
            days_ago=3,
        )
        memory_store.add(entry2)

        # Act
        recommendations = recommendation_engine.recommend_for_schema_drift("UserConfig")

        # Assert
        assert len(recommendations) >= 1
        # Recommendations should have action text
        for rec in recommendations:
            assert rec.action is not None
            assert len(rec.action) > 0


class TestRecommendForTestFailure:
    """Tests for recommend_for_test_failure based on history."""

    def test_recommend_for_test_failure_based_on_history(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Should suggest approach based on past similar failures.

        When there are historical test failure entries for a test path
        with successful resolutions, recommendations should be returned.
        """
        # Arrange - Add historical test failure entries with resolutions
        entry1 = _create_test_failure_entry(
            test_path="tests/unit/test_auth.py",
            test_name="test_login",
            error_type="AssertionError",
            outcome="resolved",
            resolution="Mock the authentication service response",
            days_ago=7,
        )
        memory_store.add(entry1)

        entry2 = _create_test_failure_entry(
            test_path="tests/unit/test_auth.py",
            test_name="test_logout",
            error_type="AssertionError",
            outcome="resolved",
            resolution="Add session cleanup fixture",
            days_ago=4,
        )
        memory_store.add(entry2)

        # Act
        recommendations = recommendation_engine.recommend_for_test_failure(
            "tests/unit/test_auth.py"
        )

        # Assert
        assert len(recommendations) >= 1
        # Each recommendation should have an action
        for rec in recommendations:
            assert rec.action is not None
            assert len(rec.action) > 0


class TestNoRecommendationForNewIssue:
    """Tests for novel issues returning empty recommendations."""

    def test_no_recommendation_for_novel_issue(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Should return empty list for issues with no history.

        When there are no historical entries matching the query,
        an empty list should be returned rather than fabricated recommendations.
        """
        # Arrange - Add entries for different classes/paths
        entry = _create_schema_drift_entry(
            class_name="ExistingClass",
            outcome="resolved",
            resolution="Some fix",
            days_ago=1,
        )
        memory_store.add(entry)

        # Act - Query for a class with no history
        recommendations = recommendation_engine.recommend_for_schema_drift("NovelClass")

        # Assert
        assert recommendations == []

    def test_no_recommendation_for_novel_test_path(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Should return empty list for test paths with no history."""
        # Arrange - Add entries for different test paths
        entry = _create_test_failure_entry(
            test_path="tests/existing/test_known.py",
            test_name="test_something",
            outcome="resolved",
            resolution="Some fix",
            days_ago=1,
        )
        memory_store.add(entry)

        # Act - Query for a test path with no history
        recommendations = recommendation_engine.recommend_for_test_failure(
            "tests/novel/test_new.py"
        )

        # Assert
        assert recommendations == []


class TestRecommendationConfidence:
    """Tests for recommendation confidence scores."""

    def test_recommendation_includes_confidence_score(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Each recommendation must have confidence score.

        Confidence score should be a float between 0.0 and 1.0 that
        indicates how reliable the recommendation is.
        """
        # Arrange - Add historical entries
        entry = _create_schema_drift_entry(
            class_name="ConfigClass",
            outcome="resolved",
            resolution="Update schema definition",
            days_ago=2,
        )
        memory_store.add(entry)

        # Add more entries to increase confidence
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="ConfigClass",
                outcome="resolved",
                resolution="Update schema definition",
                days_ago=i + 1,
            )
            memory_store.add(entry)

        # Act
        recommendations = recommendation_engine.recommend_for_schema_drift("ConfigClass")

        # Assert
        assert len(recommendations) >= 1
        for rec in recommendations:
            assert isinstance(rec.confidence, float)
            assert 0.0 <= rec.confidence <= 1.0

    def test_confidence_increases_with_more_occurrences(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Confidence should be higher when more similar entries exist."""
        # Arrange - Add entries with different occurrence counts
        # Class with many resolutions (high confidence)
        for i in range(10):
            entry = _create_schema_drift_entry(
                class_name="FrequentClass",
                outcome="resolved",
                resolution="Consistent fix approach",
                days_ago=i,
            )
            memory_store.add(entry)

        # Class with few resolutions (lower confidence)
        for i in range(2):
            entry = _create_schema_drift_entry(
                class_name="RareClass",
                outcome="resolved",
                resolution="Some fix",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act
        freq_recs = recommendation_engine.recommend_for_schema_drift("FrequentClass")
        rare_recs = recommendation_engine.recommend_for_schema_drift("RareClass")

        # Assert
        assert len(freq_recs) >= 1
        assert len(rare_recs) >= 1
        # Higher occurrence count should mean higher confidence
        assert freq_recs[0].confidence >= rare_recs[0].confidence


class TestRecommendationContext:
    """Tests for recommendation source context."""

    def test_recommendation_includes_source_context(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Recommendations include source entry information.

        Each recommendation should include context about which entries
        informed the recommendation, enabling transparency and verification.
        """
        # Arrange - Add historical entries with distinct IDs
        entry1 = _create_schema_drift_entry(
            class_name="ContextClass",
            outcome="resolved",
            resolution="Apply standard fix pattern",
            days_ago=1,
        )
        memory_store.add(entry1)

        entry2 = _create_schema_drift_entry(
            class_name="ContextClass",
            outcome="resolved",
            resolution="Apply standard fix pattern",
            days_ago=2,
        )
        memory_store.add(entry2)

        # Act
        recommendations = recommendation_engine.recommend_for_schema_drift("ContextClass")

        # Assert
        assert len(recommendations) >= 1
        for rec in recommendations:
            # Should have context dict
            assert isinstance(rec.context, dict)
            # Should have source_entries list (entry IDs)
            assert isinstance(rec.source_entries, list)
            assert len(rec.source_entries) >= 1
            # Source entries should be entry IDs (strings)
            for entry_id in rec.source_entries:
                assert isinstance(entry_id, str)

    def test_context_includes_category_info(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Recommendation context should include category information."""
        # Arrange
        entry = _create_test_failure_entry(
            test_path="tests/test_context.py",
            test_name="test_example",
            outcome="resolved",
            resolution="Add proper fixture",
            days_ago=1,
        )
        memory_store.add(entry)

        # Act
        recommendations = recommendation_engine.recommend_for_test_failure(
            "tests/test_context.py"
        )

        # Assert
        assert len(recommendations) >= 1
        rec = recommendations[0]
        assert "category" in rec.context
        assert rec.context["category"] == "test_failure"


class TestMultipleRecommendations:
    """Tests for multiple recommendations sorted by relevance."""

    def test_multiple_recommendations_sorted_by_relevance(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Multiple recs returned in descending confidence order.

        When multiple recommendations are available, they should be
        sorted by confidence score with highest confidence first.
        """
        # Arrange - Add entries with different resolutions and frequencies
        # High frequency resolution
        for i in range(5):
            entry = _create_schema_drift_entry(
                class_name="MultiClass",
                outcome="resolved",
                resolution="Common fix: update type annotation",
                days_ago=i,
            )
            memory_store.add(entry)

        # Medium frequency resolution
        for i in range(3):
            entry = _create_schema_drift_entry(
                class_name="MultiClass",
                outcome="resolved",
                resolution="Alternative fix: add default value",
                days_ago=i + 5,
            )
            memory_store.add(entry)

        # Low frequency resolution
        entry = _create_schema_drift_entry(
            class_name="MultiClass",
            outcome="resolved",
            resolution="Rare fix: restructure class hierarchy",
            days_ago=10,
        )
        memory_store.add(entry)

        # Act
        recommendations = recommendation_engine.recommend_for_schema_drift("MultiClass")

        # Assert
        assert len(recommendations) >= 2
        # Verify descending confidence order
        for i in range(len(recommendations) - 1):
            assert recommendations[i].confidence >= recommendations[i + 1].confidence

    def test_get_recommendations_respects_limit(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """get_recommendations should respect the limit parameter."""
        # Arrange - Add many entries
        for i in range(10):
            entry = _create_schema_drift_entry(
                class_name="LimitClass",
                outcome="resolved",
                resolution=f"Fix approach {i}",
                days_ago=i,
            )
            memory_store.add(entry)

        # Act - Request with limit using get_recommendations_by_category
        recommendations = recommendation_engine.get_recommendations_by_category(
            category="schema_drift",
            context={"class_name": "LimitClass"},
            limit=3,
        )

        # Assert
        assert len(recommendations) <= 3

    def test_get_recommendations_returns_empty_for_no_matches(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """get_recommendations should return empty list when no matches."""
        # Arrange - Empty store (no entries)

        # Act - Use get_recommendations_by_category for category-based lookup
        recommendations = recommendation_engine.get_recommendations_by_category(
            category="schema_drift",
            context={"class_name": "NonexistentClass"},
            limit=5,
        )

        # Assert
        assert recommendations == []


class TestRecommendationDataclass:
    """Tests for the Recommendation dataclass structure."""

    def test_recommendation_has_required_fields(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Recommendation dataclass must have all required fields."""
        # Arrange
        entry = _create_schema_drift_entry(
            class_name="DataclassTest",
            outcome="resolved",
            resolution="Test fix",
            days_ago=1,
        )
        memory_store.add(entry)

        # Act
        recommendations = recommendation_engine.recommend_for_schema_drift("DataclassTest")

        # Assert
        assert len(recommendations) >= 1
        rec = recommendations[0]

        # Verify required fields exist
        assert hasattr(rec, "action")
        assert hasattr(rec, "confidence")
        assert hasattr(rec, "context")
        assert hasattr(rec, "source_entries")

    def test_recommendation_action_is_string(
        self, memory_store: MemoryStore, recommendation_engine: RecommendationEngine
    ) -> None:
        """Recommendation action should be a string."""
        # Arrange
        entry = _create_schema_drift_entry(
            class_name="ActionTest",
            outcome="resolved",
            resolution="Apply this fix",
            days_ago=1,
        )
        memory_store.add(entry)

        # Act
        recommendations = recommendation_engine.recommend_for_schema_drift("ActionTest")

        # Assert
        assert len(recommendations) >= 1
        assert isinstance(recommendations[0].action, str)
