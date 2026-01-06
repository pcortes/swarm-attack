"""Test for BUG-001: DateTime offset-naive vs offset-aware."""
import pytest
from datetime import datetime, timezone, timedelta
from swarm_attack.memory.store import MemoryStore, MemoryEntry
from swarm_attack.memory.patterns import PatternDetector
import uuid


class TestDatetimeBug001:
    """BUG-001: TypeError in _calculate_confidence_score."""

    def test_detect_fix_patterns_with_timezone_aware_entries(self):
        """Pattern detection should work with timezone-aware timestamps."""
        store = MemoryStore()

        # Add entries with timezone-aware timestamps (as real usage does)
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="fix_applied",
                feature_id="test-feature",
                issue_number=i,
                content={"fix_type": "test", "description": f"Fix {i}"},
                outcome="success",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["test", "fix"],
            ))

        detector = PatternDetector(store)

        # This should NOT raise TypeError
        patterns = detector.detect_common_fix_patterns(min_occurrences=1)

        # Should return list (possibly empty, but no crash)
        assert isinstance(patterns, list)

    def test_confidence_score_with_mixed_timezones(self):
        """Confidence calculation should handle various timestamp formats."""
        store = MemoryStore()

        # Add entry with explicit UTC timezone
        store.add(MemoryEntry(
            id=str(uuid.uuid4()),
            category="fix_applied",
            feature_id="test-feature",
            issue_number=1,
            content={"fix_type": "test"},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["test"],
        ))

        detector = PatternDetector(store)
        patterns = detector.detect_common_fix_patterns(min_occurrences=1)

        # Should complete without TypeError
        assert patterns is not None

    def test_is_within_time_window_with_timezone_aware(self):
        """_is_within_time_window should handle timezone-aware timestamps."""
        store = MemoryStore()

        # Add entry with timezone-aware timestamp
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="test-feature",
            issue_number=1,
            content={"class_name": "TestClass"},
            outcome="detected",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=["test"],
        )
        store.add(entry)

        detector = PatternDetector(store)

        # This should NOT raise TypeError
        result = detector._is_within_time_window(entry, time_window_days=30)

        # Entry created now should be within 30-day window
        assert result is True

    def test_detect_patterns_unified_api_with_timezone_aware(self):
        """detect_patterns unified API should handle timezone-aware timestamps."""
        store = MemoryStore()

        # Add entries with timezone-aware timestamps
        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="test_failure",
                feature_id="test-feature",
                issue_number=i,
                content={"error_type": "TimeoutError", "test_path": "test.py"},
                outcome="failure",
                created_at=(datetime.now(timezone.utc) - timedelta(days=i)).isoformat(),
                tags=["test"],
            ))

        detector = PatternDetector(store)

        # This should NOT raise TypeError
        patterns = detector.detect_patterns(min_occurrences=2, days=30)

        # Should return list with patterns
        assert isinstance(patterns, list)
