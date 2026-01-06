"""Tests for MemoryStore query helper methods.

This module tests the query helper methods that provide convenient access
to common memory patterns:
- get_schema_drift_warnings() - Get schema drift entries for class names
- get_test_failure_patterns() - Get test failure entries for test paths
- get_recent_entries() - Get most recent entries by category
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


class TestGetSchemaDriftWarnings:
    """Tests for MemoryStore.get_schema_drift_warnings() method."""

    def test_get_schema_drift_warnings_returns_entries_for_class_names(self) -> None:
        """Test that get_schema_drift_warnings returns entries matching class names.

        Given a store with schema drift entries for multiple classes,
        when querying with specific class names,
        then only entries matching those class names should be returned.
        """
        store = MemoryStore()

        # Create schema drift entries for different classes
        entry_user = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-1",
            issue_number=1,
            content={
                "class_name": "UserProfile",
                "conflict_type": "duplicate_definition",
            },
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "UserProfile"],
        )

        entry_order = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-2",
            issue_number=2,
            content={
                "class_name": "OrderManager",
                "conflict_type": "field_mismatch",
            },
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "OrderManager"],
        )

        entry_payment = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-3",
            issue_number=3,
            content={
                "class_name": "PaymentProcessor",
                "conflict_type": "method_signature",
            },
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "PaymentProcessor"],
        )

        store.add(entry_user)
        store.add(entry_order)
        store.add(entry_payment)

        # Query for UserProfile and OrderManager
        results = store.get_schema_drift_warnings(["UserProfile", "OrderManager"])

        # Should return 2 entries
        assert len(results) == 2
        class_names = {r.content["class_name"] for r in results}
        assert class_names == {"UserProfile", "OrderManager"}

    def test_get_schema_drift_warnings_returns_empty_for_no_matches(self) -> None:
        """Test that get_schema_drift_warnings returns empty list when no matches.

        Given a store with schema drift entries,
        when querying with class names that don't exist,
        then an empty list should be returned.
        """
        store = MemoryStore()

        # Add some entries
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-1",
            issue_number=1,
            content={"class_name": "ExistingClass"},
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "ExistingClass"],
        )
        store.add(entry)

        # Query for non-existent classes
        results = store.get_schema_drift_warnings(["NonExistentClass", "AnotherMissing"])

        # Should return empty list
        assert results == []


class TestGetTestFailurePatterns:
    """Tests for MemoryStore.get_test_failure_patterns() method."""

    def test_get_test_failure_patterns_returns_entries_for_test_path(self) -> None:
        """Test that get_test_failure_patterns returns entries matching test path.

        Given a store with test failure entries for various test paths,
        when querying with a specific test path,
        then only entries matching that path should be returned.
        """
        store = MemoryStore()

        # Create test failure entries for different paths
        entry_auth = MemoryEntry(
            id=str(uuid.uuid4()),
            category="test_failure",
            feature_id="feature-1",
            issue_number=1,
            content={
                "test_path": "tests/unit/test_auth.py",
                "test_name": "test_login_success",
                "error": "AssertionError: expected 200, got 401",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["test_failure", "tests/unit/test_auth.py"],
        )

        entry_auth2 = MemoryEntry(
            id=str(uuid.uuid4()),
            category="test_failure",
            feature_id="feature-2",
            issue_number=2,
            content={
                "test_path": "tests/unit/test_auth.py",
                "test_name": "test_logout",
                "error": "TimeoutError",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["test_failure", "tests/unit/test_auth.py"],
        )

        entry_api = MemoryEntry(
            id=str(uuid.uuid4()),
            category="test_failure",
            feature_id="feature-3",
            issue_number=3,
            content={
                "test_path": "tests/integration/test_api.py",
                "test_name": "test_endpoint",
                "error": "ConnectionError",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["test_failure", "tests/integration/test_api.py"],
        )

        store.add(entry_auth)
        store.add(entry_auth2)
        store.add(entry_api)

        # Query for auth test failures
        results = store.get_test_failure_patterns("tests/unit/test_auth.py")

        # Should return 2 entries
        assert len(results) == 2
        assert all(r.content["test_path"] == "tests/unit/test_auth.py" for r in results)

    def test_get_test_failure_patterns_returns_empty_for_no_matches(self) -> None:
        """Test that get_test_failure_patterns returns empty list when no matches.

        Given a store with test failure entries,
        when querying with a test path that doesn't exist,
        then an empty list should be returned.
        """
        store = MemoryStore()

        # Add some entries
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="test_failure",
            feature_id="feature-1",
            issue_number=1,
            content={
                "test_path": "tests/unit/test_existing.py",
                "error": "SomeError",
            },
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["test_failure", "tests/unit/test_existing.py"],
        )
        store.add(entry)

        # Query for non-existent test path
        results = store.get_test_failure_patterns("tests/unit/test_nonexistent.py")

        # Should return empty list
        assert results == []


class TestGetRecentEntries:
    """Tests for MemoryStore.get_recent_entries() method."""

    def test_get_recent_entries_limits_by_count(self) -> None:
        """Test that get_recent_entries respects the limit parameter.

        Given a store with many entries in a category,
        when querying with a limit,
        then only that many entries should be returned.
        """
        store = MemoryStore()

        # Add 10 entries
        for i in range(10):
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id=f"feature-{i}",
                issue_number=i,
                content={"class_name": f"Class{i}"},
                outcome="detected",
                created_at=(datetime.now() - timedelta(hours=i)).isoformat(),
                tags=["schema_drift"],
            )
            store.add(entry)

        # Query with limit of 5
        results = store.get_recent_entries("schema_drift", limit=5)

        # Should return exactly 5 entries
        assert len(results) == 5

    def test_get_recent_entries_filters_by_category(self) -> None:
        """Test that get_recent_entries only returns entries from specified category.

        Given a store with entries in multiple categories,
        when querying for a specific category,
        then only entries from that category should be returned.
        """
        store = MemoryStore()

        # Add entries from different categories
        for i in range(3):
            drift_entry = MemoryEntry(
                id=str(uuid.uuid4()),
                category="schema_drift",
                feature_id=f"feature-drift-{i}",
                issue_number=i,
                content={"class_name": f"DriftClass{i}"},
                outcome="detected",
                created_at=datetime.now().isoformat(),
                tags=["schema_drift"],
            )
            store.add(drift_entry)

            failure_entry = MemoryEntry(
                id=str(uuid.uuid4()),
                category="test_failure",
                feature_id=f"feature-fail-{i}",
                issue_number=i + 10,
                content={"test_path": f"tests/test_{i}.py"},
                outcome="failure",
                created_at=datetime.now().isoformat(),
                tags=["test_failure"],
            )
            store.add(failure_entry)

        # Query for schema_drift category
        results = store.get_recent_entries("schema_drift", limit=10)

        # Should return only schema_drift entries
        assert len(results) == 3
        assert all(r.category == "schema_drift" for r in results)

    def test_get_recent_entries_sorts_by_timestamp_descending(self) -> None:
        """Test that get_recent_entries returns entries sorted by timestamp desc.

        Given a store with entries created at different times,
        when querying,
        then entries should be sorted by created_at in descending order
        (most recent first).
        """
        store = MemoryStore()

        # Create entries with known timestamps
        now = datetime.now()
        timestamps = [
            now - timedelta(hours=5),  # oldest
            now - timedelta(hours=1),  # middle
            now - timedelta(hours=3),  # older
            now,  # newest
        ]

        for i, ts in enumerate(timestamps):
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                category="checkpoint_decision",
                feature_id=f"feature-{i}",
                issue_number=i,
                content={"order": i, "timestamp": ts.isoformat()},
                outcome="success",
                created_at=ts.isoformat(),
                tags=["checkpoint"],
            )
            store.add(entry)

        # Query recent entries
        results = store.get_recent_entries("checkpoint_decision", limit=10)

        # Should be sorted by timestamp descending (newest first)
        assert len(results) == 4
        result_timestamps = [r.created_at for r in results]

        # Verify descending order
        for i in range(len(result_timestamps) - 1):
            assert result_timestamps[i] >= result_timestamps[i + 1], (
                f"Entry at index {i} ({result_timestamps[i]}) should be >= "
                f"entry at index {i+1} ({result_timestamps[i+1]})"
            )
