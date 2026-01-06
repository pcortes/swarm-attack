"""Test for BUG-002: Recurring schema drift detection."""
import pytest
from datetime import datetime, timezone, timedelta
from swarm_attack.memory.store import MemoryStore, MemoryEntry
from swarm_attack.memory.patterns import PatternDetector
import uuid


class TestRecurringPatternBug002:
    """BUG-002: Pattern detection should find recurring issues."""

    def test_detect_recurring_schema_drift_same_class(self):
        """Should detect pattern when same class has multiple drifts."""
        store = MemoryStore()

        # Add 3 entries for same class using "class" key (common usage)
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id="auth-feature",
                issue_number=i+1,
                content={
                    "class": "UserModel",
                    "change_type": ["added", "removed", "renamed"][i],
                },
                outcome="detected",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["UserModel", "schema"],
            ))

        detector = PatternDetector(store)
        patterns = detector.detect_recurring_schema_drift(min_occurrences=2)

        # Should find UserModel pattern
        assert len(patterns) >= 1, "Should detect at least one pattern"

        # Find the UserModel pattern
        user_model_patterns = [p for p in patterns if "UserModel" in str(p)]
        assert len(user_model_patterns) >= 1, "Should find UserModel pattern"

    def test_detect_recurring_with_class_name_key(self):
        """Should also work with class_name key (backwards compat)."""
        store = MemoryStore()

        # Add entries using class_name key
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id="test",
                issue_number=None,
                content={"class_name": "OrderModel"},
                outcome="detected",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["OrderModel"],
            ))

        detector = PatternDetector(store)
        patterns = detector.detect_recurring_schema_drift(min_occurrences=2)

        # Should find OrderModel pattern
        assert len(patterns) >= 1
        order_patterns = [p for p in patterns if p.class_name == "OrderModel"]
        assert len(order_patterns) >= 1

    def test_detect_recurring_with_different_classes(self):
        """Should detect multiple patterns for different classes."""
        store = MemoryStore()

        # Add entries for two classes
        for cls in ["UserModel", "OrderModel"]:
            for i in range(3):
                store.add(MemoryEntry(
                    id=str(uuid.uuid4()),
                    category="schema_drift",
                    feature_id="test",
                    issue_number=None,
                    content={"class": cls},
                    outcome="detected",
                    created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                    tags=[cls, "schema"],
                ))

        detector = PatternDetector(store)
        patterns = detector.detect_recurring_schema_drift(min_occurrences=2)

        # Should find both patterns
        assert len(patterns) >= 2

    def test_no_pattern_below_threshold(self):
        """Should not detect pattern with fewer than min_occurrences."""
        store = MemoryStore()

        # Add only 1 entry
        store.add(MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="test",
            issue_number=None,
            content={"class": "SingleClass"},
            outcome="detected",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["SingleClass"],
        ))

        detector = PatternDetector(store)
        patterns = detector.detect_recurring_schema_drift(min_occurrences=2)

        # Should NOT find pattern for single occurrence
        single_patterns = [p for p in patterns if "SingleClass" in str(p)]
        assert len(single_patterns) == 0

    def test_occurrence_count_correct(self):
        """Pattern should report correct occurrence count."""
        store = MemoryStore()

        # Add exactly 5 entries for same class
        for i in range(5):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id="test",
                issue_number=i,
                content={"class": "FiveTimeClass"},
                outcome="detected",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["FiveTimeClass"],
            ))

        detector = PatternDetector(store)
        patterns = detector.detect_recurring_schema_drift(min_occurrences=2)

        # Find the FiveTimeClass pattern
        five_patterns = [p for p in patterns if p.class_name == "FiveTimeClass"]
        assert len(five_patterns) == 1
        assert five_patterns[0].occurrence_count == 5
