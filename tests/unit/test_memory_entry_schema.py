"""Tests for MemoryEntry structure used by agents.

This module tests the MemoryEntry dataclass schema and MemoryStore query functionality
to ensure agents can reliably store and retrieve memory entries.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


class TestMemoryEntrySchema:
    """Tests for MemoryEntry dataclass structure."""

    def test_schema_drift_entry_has_required_fields(self) -> None:
        """Test that a schema drift MemoryEntry has: category, content, tags, timestamp.

        This validates that the MemoryEntry dataclass has all required fields
        for storing schema drift information used by agents.
        """
        # Create a schema drift memory entry
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="test-feature",
            issue_number=42,
            content={
                "class_name": "UserProfile",
                "conflict_type": "duplicate_definition",
                "original_file": "models/user.py",
                "duplicate_file": "models/profile.py",
            },
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "UserProfile", "models"],
        )

        # Verify required fields exist and have correct values
        assert hasattr(entry, "category"), "MemoryEntry must have 'category' field"
        assert entry.category == "schema_drift"

        assert hasattr(entry, "content"), "MemoryEntry must have 'content' field"
        assert isinstance(entry.content, dict)
        assert "class_name" in entry.content

        assert hasattr(entry, "tags"), "MemoryEntry must have 'tags' field"
        assert isinstance(entry.tags, list)
        assert "schema_drift" in entry.tags

        assert hasattr(entry, "created_at"), "MemoryEntry must have 'created_at' (timestamp) field"
        assert entry.created_at is not None

    def test_schema_drift_entry_queryable_by_class_name(self) -> None:
        """Test that entries can be queried by class name tag.

        This validates that MemoryStore.query() can filter entries by tags,
        enabling agents to look up prior schema drift conflicts by class name.
        """
        store = MemoryStore()

        # Create multiple entries with different class names
        entry1 = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-1",
            issue_number=1,
            content={"class_name": "UserProfile"},
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "UserProfile"],
        )

        entry2 = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-2",
            issue_number=2,
            content={"class_name": "OrderManager"},
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "OrderManager"],
        )

        entry3 = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-3",
            issue_number=3,
            content={"class_name": "UserProfile"},
            outcome="resolved",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "UserProfile"],
        )

        store.add(entry1)
        store.add(entry2)
        store.add(entry3)

        # Query by class name tag
        results = store.query(tags=["UserProfile"])

        # Should find both UserProfile entries
        assert len(results) == 2
        class_names = [r.content["class_name"] for r in results]
        assert all(name == "UserProfile" for name in class_names)

        # Query by different class name
        results = store.query(tags=["OrderManager"])
        assert len(results) == 1
        assert results[0].content["class_name"] == "OrderManager"


class TestMemoryEntrySerialization:
    """Tests for MemoryEntry JSON serialization."""

    def test_memory_entry_round_trips_through_json(self) -> None:
        """Test that MemoryEntry serializes/deserializes correctly.

        This validates that MemoryEntry can be converted to dict, serialized
        to JSON, deserialized, and reconstructed without data loss.
        """
        original = MemoryEntry(
            id="test-id-12345",
            category="schema_drift",
            feature_id="feature-xyz",
            issue_number=99,
            content={
                "class_name": "TestClass",
                "conflict_type": "duplicate_definition",
                "details": {
                    "nested": True,
                    "count": 42,
                },
            },
            outcome="applied",
            created_at="2025-01-06T12:00:00",
            tags=["schema_drift", "TestClass", "unit-test"],
            hit_count=5,
        )

        # Serialize to dict then to JSON string
        entry_dict = original.to_dict()
        json_str = json.dumps(entry_dict)

        # Deserialize from JSON string back to dict then to MemoryEntry
        loaded_dict = json.loads(json_str)
        reconstructed = MemoryEntry.from_dict(loaded_dict)

        # Verify all fields match
        assert reconstructed.id == original.id
        assert reconstructed.category == original.category
        assert reconstructed.feature_id == original.feature_id
        assert reconstructed.issue_number == original.issue_number
        assert reconstructed.content == original.content
        assert reconstructed.outcome == original.outcome
        assert reconstructed.created_at == original.created_at
        assert reconstructed.tags == original.tags
        assert reconstructed.hit_count == original.hit_count

        # Verify nested content is preserved
        assert reconstructed.content["details"]["nested"] is True
        assert reconstructed.content["details"]["count"] == 42


class TestMemoryStoreQuery:
    """Tests for MemoryStore query functionality."""

    def test_memory_query_filters_by_category(self) -> None:
        """Test that MemoryStore.query() can filter by category.

        This validates that agents can query memories by category type,
        such as 'schema_drift', 'checkpoint_decision', or 'test_failure'.
        """
        store = MemoryStore()

        # Add entries with different categories
        schema_drift_entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-1",
            issue_number=1,
            content={"class_name": "MyClass"},
            outcome="detected",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift"],
        )

        checkpoint_entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="checkpoint_decision",
            feature_id="feature-1",
            issue_number=2,
            content={"decision": "approve", "reason": "tests pass"},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["checkpoint"],
        )

        test_failure_entry = MemoryEntry(
            id=str(uuid.uuid4()),
            category="test_failure",
            feature_id="feature-2",
            issue_number=3,
            content={"test_name": "test_user_login", "error": "AssertionError"},
            outcome="failure",
            created_at=datetime.now().isoformat(),
            tags=["test_failure"],
        )

        another_schema_drift = MemoryEntry(
            id=str(uuid.uuid4()),
            category="schema_drift",
            feature_id="feature-3",
            issue_number=4,
            content={"class_name": "AnotherClass"},
            outcome="resolved",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift"],
        )

        store.add(schema_drift_entry)
        store.add(checkpoint_entry)
        store.add(test_failure_entry)
        store.add(another_schema_drift)

        # Query by schema_drift category
        schema_drift_results = store.query(category="schema_drift")
        assert len(schema_drift_results) == 2
        assert all(r.category == "schema_drift" for r in schema_drift_results)

        # Query by checkpoint_decision category
        checkpoint_results = store.query(category="checkpoint_decision")
        assert len(checkpoint_results) == 1
        assert checkpoint_results[0].category == "checkpoint_decision"
        assert checkpoint_results[0].content["decision"] == "approve"

        # Query by test_failure category
        test_failure_results = store.query(category="test_failure")
        assert len(test_failure_results) == 1
        assert test_failure_results[0].category == "test_failure"
        assert test_failure_results[0].content["test_name"] == "test_user_login"

        # Query by non-existent category should return empty
        empty_results = store.query(category="nonexistent_category")
        assert len(empty_results) == 0
