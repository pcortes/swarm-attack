"""Test for BUG-003: RecommendationEngine returns empty."""
import pytest
from datetime import datetime, timezone, timedelta
from swarm_attack.memory.store import MemoryStore, MemoryEntry
from swarm_attack.memory.patterns import PatternDetector
from swarm_attack.memory.recommendations import RecommendationEngine
import uuid


class TestRecommendationBug003:
    """BUG-003: Recommendations should return suggestions."""

    def test_recommend_for_recurring_schema_drift(self):
        """Should recommend based on historical resolutions."""
        store = MemoryStore()

        # Create historical schema drift entries WITH resolutions
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id="auth",
                issue_number=i+1,
                content={
                    "class_name": "UserModel",
                    "drift_type": "field_added",
                    "resolution": "Apply migration script to update schema",
                },
                outcome="resolved",  # Must be resolved/success/applied
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["UserModel"],
            ))

        detector = PatternDetector(store)
        engine = RecommendationEngine(store, detector)

        recs = engine.get_recommendations_by_category(
            category="schema_drift",
            context={"class_name": "UserModel"},
        )

        # Should return at least one recommendation
        assert len(recs) >= 1
        assert "migration" in recs[0].suggestion.lower()

    def test_recommend_for_schema_drift_with_class_key(self):
        """Should work with 'class' key in content (common variant)."""
        store = MemoryStore()

        # Add entries with "class" key (not "class_name")
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id="auth",
                issue_number=i+1,
                content={
                    "class": "OrderModel",  # Using "class" key
                    "resolution": "Regenerate API client from spec",
                },
                outcome="success",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["OrderModel"],
            ))

        detector = PatternDetector(store)
        engine = RecommendationEngine(store, detector)

        # Use recommend_for_schema_drift method
        recs = engine.recommend_for_schema_drift("OrderModel")

        # Should return at least one recommendation
        assert len(recs) >= 1

    def test_no_recommendation_for_novel_issue(self):
        """Should return empty for issues with no history."""
        store = MemoryStore()
        detector = PatternDetector(store)
        engine = RecommendationEngine(store, detector)

        recs = engine.get_recommendations_by_category(
            category="schema_drift",
            context={"class_name": "NewClass"},
        )

        # No history = no recommendations
        assert len(recs) == 0

    def test_recommendation_confidence_based_on_count(self):
        """Higher occurrence count should give higher confidence."""
        store = MemoryStore()

        # Add many entries with same resolution
        for i in range(10):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id="test",
                issue_number=i,
                content={
                    "class_name": "FrequentClass",
                    "resolution": "Common fix that works",
                },
                outcome="resolved",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["FrequentClass"],
            ))

        detector = PatternDetector(store)
        engine = RecommendationEngine(store, detector)

        recs = engine.recommend_for_schema_drift("FrequentClass")

        # Should have recommendation with reasonable confidence
        assert len(recs) >= 1
        assert recs[0].confidence > 0.3  # 10 entries should give decent confidence

    def test_get_recommendations_by_category_test_failure(self):
        """Should return recommendations for test_failure category."""
        store = MemoryStore()

        # Add test failure entries with resolutions
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="test_failure",
                feature_id="api",
                issue_number=i,
                content={
                    "test_path": "tests/test_api.py",
                    "error_type": "AssertionError",
                    "resolution": "Fix mock to return correct response format",
                },
                outcome="resolved",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["api", "mock"],
            ))

        detector = PatternDetector(store)
        engine = RecommendationEngine(store, detector)

        recs = engine.recommend_for_test_failure("tests/test_api.py")

        # Should return recommendations
        assert len(recs) >= 1
        assert "mock" in recs[0].suggestion.lower()
