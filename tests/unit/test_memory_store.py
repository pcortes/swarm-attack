"""
Unit tests for MemoryStore - Persistent Memory Layer Phase A.

TDD Tests for Issue A1: MemoryStore Base Class.
Tests written BEFORE implementation (RED phase).
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_memory_entry_creation(self):
        """Test creating a MemoryEntry with all fields."""
        from swarm_attack.memory.store import MemoryEntry

        entry = MemoryEntry(
            id="test-123",
            category="checkpoint_decision",
            feature_id="chief-of-staff-v3",
            issue_number=5,
            content={"trigger": "HICCUP", "decision": "Proceed"},
            outcome="success",
            created_at="2025-01-15T10:00:00Z",
            tags=["HICCUP", "Proceed"],
        )

        assert entry.id == "test-123"
        assert entry.category == "checkpoint_decision"
        assert entry.feature_id == "chief-of-staff-v3"
        assert entry.issue_number == 5
        assert entry.content == {"trigger": "HICCUP", "decision": "Proceed"}
        assert entry.outcome == "success"
        assert entry.tags == ["HICCUP", "Proceed"]

    def test_memory_entry_optional_fields(self):
        """Test creating a MemoryEntry with optional fields as None."""
        from swarm_attack.memory.store import MemoryEntry

        entry = MemoryEntry(
            id="test-456",
            category="schema_drift",
            feature_id="my-feature",
            issue_number=None,  # Optional
            content={"class_name": "AutopilotSession"},
            outcome=None,  # Optional
            created_at="2025-01-15T10:00:00Z",
            tags=[],
        )

        assert entry.issue_number is None
        assert entry.outcome is None
        assert entry.tags == []

    def test_memory_entry_to_dict(self):
        """Test serializing MemoryEntry to dictionary."""
        from swarm_attack.memory.store import MemoryEntry

        entry = MemoryEntry(
            id="test-789",
            category="test_failure",
            feature_id="feature-x",
            issue_number=3,
            content={"test": "test_something", "error": "AssertionError"},
            outcome="failure",
            created_at="2025-01-15T12:00:00Z",
            tags=["test_failure", "AssertionError"],
        )

        data = entry.to_dict()

        assert data["id"] == "test-789"
        assert data["category"] == "test_failure"
        assert data["feature_id"] == "feature-x"
        assert data["issue_number"] == 3
        assert data["content"] == {"test": "test_something", "error": "AssertionError"}
        assert data["outcome"] == "failure"
        assert data["tags"] == ["test_failure", "AssertionError"]

    def test_memory_entry_from_dict(self):
        """Test deserializing MemoryEntry from dictionary."""
        from swarm_attack.memory.store import MemoryEntry

        data = {
            "id": "test-abc",
            "category": "checkpoint_decision",
            "feature_id": "feature-y",
            "issue_number": 7,
            "content": {"decision": "Skip"},
            "outcome": "applied",
            "created_at": "2025-01-15T14:00:00Z",
            "tags": ["Skip"],
        }

        entry = MemoryEntry.from_dict(data)

        assert entry.id == "test-abc"
        assert entry.category == "checkpoint_decision"
        assert entry.feature_id == "feature-y"
        assert entry.issue_number == 7
        assert entry.content == {"decision": "Skip"}
        assert entry.outcome == "applied"
        assert entry.tags == ["Skip"]

    def test_memory_entry_roundtrip(self):
        """Test that to_dict/from_dict roundtrip preserves data."""
        from swarm_attack.memory.store import MemoryEntry

        original = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="roundtrip-test",
            issue_number=99,
            content={"class_name": "TestClass", "file": "test.py"},
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "TestClass"],
        )

        data = original.to_dict()
        restored = MemoryEntry.from_dict(data)

        assert restored.id == original.id
        assert restored.category == original.category
        assert restored.feature_id == original.feature_id
        assert restored.issue_number == original.issue_number
        assert restored.content == original.content
        assert restored.outcome == original.outcome
        assert restored.tags == original.tags


class TestMemoryStore:
    """Tests for MemoryStore class."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    @pytest.fixture
    def memory_store(self, temp_store_path):
        """Create a MemoryStore instance with temp path."""
        from swarm_attack.memory.store import MemoryStore

        return MemoryStore(store_path=temp_store_path)

    @pytest.fixture
    def sample_entry(self):
        """Create a sample MemoryEntry for tests."""
        from swarm_attack.memory.store import MemoryEntry

        return MemoryEntry(
            id=str(uuid4()),
            category="checkpoint_decision",
            feature_id="test-feature",
            issue_number=1,
            content={"trigger": "HICCUP", "decision": "Proceed"},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP", "Proceed"],
        )

    def test_add_and_query_entry(self, memory_store, sample_entry):
        """Test adding an entry and querying it back."""
        memory_store.add(sample_entry)
        memory_store.save()

        results = memory_store.query(category="checkpoint_decision")

        assert len(results) == 1
        assert results[0].id == sample_entry.id
        assert results[0].category == "checkpoint_decision"

    def test_query_by_category(self, memory_store):
        """Test filtering queries by category."""
        from swarm_attack.memory.store import MemoryEntry

        # Add entries with different categories
        checkpoint_entry = MemoryEntry(
            id="cp-1",
            category="checkpoint_decision",
            feature_id="feat-1",
            issue_number=1,
            content={"trigger": "HICCUP"},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP"],
        )
        schema_entry = MemoryEntry(
            id="sd-1",
            category="schema_drift",
            feature_id="feat-1",
            issue_number=2,
            content={"class_name": "Foo"},
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift"],
        )

        memory_store.add(checkpoint_entry)
        memory_store.add(schema_entry)
        memory_store.save()

        # Query by category
        checkpoint_results = memory_store.query(category="checkpoint_decision")
        schema_results = memory_store.query(category="schema_drift")

        assert len(checkpoint_results) == 1
        assert checkpoint_results[0].id == "cp-1"
        assert len(schema_results) == 1
        assert schema_results[0].id == "sd-1"

    def test_query_by_feature_id(self, memory_store):
        """Test filtering queries by feature_id."""
        from swarm_attack.memory.store import MemoryEntry

        # Add entries for different features
        entry1 = MemoryEntry(
            id="e1",
            category="test",
            feature_id="feature-a",
            issue_number=1,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=[],
        )
        entry2 = MemoryEntry(
            id="e2",
            category="test",
            feature_id="feature-b",
            issue_number=1,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=[],
        )

        memory_store.add(entry1)
        memory_store.add(entry2)
        memory_store.save()

        results = memory_store.query(feature_id="feature-a")

        assert len(results) == 1
        assert results[0].feature_id == "feature-a"

    def test_query_by_tags(self, memory_store):
        """Test filtering queries by tags."""
        from swarm_attack.memory.store import MemoryEntry

        entry1 = MemoryEntry(
            id="t1",
            category="checkpoint",
            feature_id="feat",
            issue_number=1,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP", "import_error"],
        )
        entry2 = MemoryEntry(
            id="t2",
            category="checkpoint",
            feature_id="feat",
            issue_number=2,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["COST_SINGLE"],
        )

        memory_store.add(entry1)
        memory_store.add(entry2)
        memory_store.save()

        # Query by single tag
        results = memory_store.query(tags=["HICCUP"])
        assert len(results) == 1
        assert results[0].id == "t1"

        # Query by tag that matches none
        results = memory_store.query(tags=["ARCHITECTURE"])
        assert len(results) == 0

    def test_query_with_limit(self, memory_store):
        """Test limiting query results."""
        from swarm_attack.memory.store import MemoryEntry

        # Add 10 entries
        for i in range(10):
            entry = MemoryEntry(
                id=f"limit-{i}",
                category="test",
                feature_id="feat",
                issue_number=i,
                content={},
                outcome="success",
                created_at=datetime.now().isoformat(),
                tags=[],
            )
            memory_store.add(entry)
        memory_store.save()

        results = memory_store.query(limit=5)

        assert len(results) == 5

    def test_query_combined_filters(self, memory_store):
        """Test combining multiple query filters."""
        from swarm_attack.memory.store import MemoryEntry

        entry1 = MemoryEntry(
            id="c1",
            category="checkpoint_decision",
            feature_id="feat-a",
            issue_number=1,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP"],
        )
        entry2 = MemoryEntry(
            id="c2",
            category="checkpoint_decision",
            feature_id="feat-b",
            issue_number=1,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP"],
        )
        entry3 = MemoryEntry(
            id="c3",
            category="schema_drift",
            feature_id="feat-a",
            issue_number=1,
            content={},
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift"],
        )

        memory_store.add(entry1)
        memory_store.add(entry2)
        memory_store.add(entry3)
        memory_store.save()

        # Query with category AND feature_id
        results = memory_store.query(
            category="checkpoint_decision",
            feature_id="feat-a",
        )

        assert len(results) == 1
        assert results[0].id == "c1"

    def test_find_similar_keyword_match(self, memory_store):
        """Test finding similar entries using keyword matching."""
        from swarm_attack.memory.store import MemoryEntry

        # Add entries with specific content
        entry1 = MemoryEntry(
            id="sim-1",
            category="schema_drift",
            feature_id="feat",
            issue_number=1,
            content={
                "class_name": "AutopilotSession",
                "existing_file": "models.py",
                "new_file": "runner.py",
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "AutopilotSession"],
        )
        entry2 = MemoryEntry(
            id="sim-2",
            category="schema_drift",
            feature_id="feat",
            issue_number=2,
            content={
                "class_name": "DailyGoal",
                "existing_file": "goals.py",
                "new_file": "tracker.py",
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "DailyGoal"],
        )

        memory_store.add(entry1)
        memory_store.add(entry2)
        memory_store.save()

        # Find similar - should match AutopilotSession
        results = memory_store.find_similar(
            content={"class_name": "AutopilotSession"},
            category="schema_drift",
        )

        assert len(results) >= 1
        assert any(r.id == "sim-1" for r in results)

    def test_find_similar_with_limit(self, memory_store):
        """Test find_similar respects limit parameter."""
        from swarm_attack.memory.store import MemoryEntry

        # Add multiple similar entries
        for i in range(10):
            entry = MemoryEntry(
                id=f"sim-limit-{i}",
                category="test_failure",
                feature_id="feat",
                issue_number=i,
                content={"error": "ImportError", "module": f"module_{i}"},
                outcome="failure",
                created_at=datetime.now().isoformat(),
                tags=["ImportError"],
            )
            memory_store.add(entry)
        memory_store.save()

        results = memory_store.find_similar(
            content={"error": "ImportError"},
            limit=3,
        )

        assert len(results) <= 3

    def test_persistence_across_sessions(self, temp_store_path):
        """Test that data persists across store instances."""
        from swarm_attack.memory.store import MemoryEntry, MemoryStore

        # Create first store and add entry
        store1 = MemoryStore(store_path=temp_store_path)
        entry = MemoryEntry(
            id="persist-1",
            category="checkpoint_decision",
            feature_id="persist-feat",
            issue_number=1,
            content={"decision": "Proceed"},
            outcome="applied",
            created_at=datetime.now().isoformat(),
            tags=["Proceed"],
        )
        store1.add(entry)
        store1.save()

        # Create new store instance and verify data persists
        store2 = MemoryStore.load(store_path=temp_store_path)

        results = store2.query(category="checkpoint_decision")

        assert len(results) == 1
        assert results[0].id == "persist-1"
        assert results[0].content == {"decision": "Proceed"}

    def test_empty_store_graceful(self, temp_store_path):
        """Test that empty/new store handles queries gracefully."""
        from swarm_attack.memory.store import MemoryStore

        # Load from non-existent path
        store = MemoryStore.load(store_path=temp_store_path)

        # Query should return empty list, not error
        results = store.query(category="anything")
        assert results == []

        # find_similar should return empty list
        similar = store.find_similar(content={"key": "value"})
        assert similar == []

    def test_save_creates_directory(self, temp_store_path):
        """Test that save() creates parent directories if needed."""
        from swarm_attack.memory.store import MemoryEntry, MemoryStore

        # Path doesn't exist yet
        assert not temp_store_path.parent.exists()

        store = MemoryStore(store_path=temp_store_path)
        entry = MemoryEntry(
            id="dir-create",
            category="test",
            feature_id="feat",
            issue_number=1,
            content={},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=[],
        )
        store.add(entry)
        store.save()

        # Directory and file should now exist
        assert temp_store_path.parent.exists()
        assert temp_store_path.exists()

    def test_default_store_path(self):
        """Test that default store path is .swarm/memory/memories.json."""
        from swarm_attack.memory.store import MemoryStore

        store = MemoryStore()

        expected_suffix = Path(".swarm") / "memory" / "memories.json"
        assert str(store.store_path).endswith(str(expected_suffix))

    def test_hit_count_tracking(self, memory_store):
        """Test that entries track how often they're returned in queries."""
        from swarm_attack.memory.store import MemoryEntry

        entry = MemoryEntry(
            id="hit-track",
            category="checkpoint_decision",
            feature_id="feat",
            issue_number=1,
            content={"trigger": "HICCUP"},
            outcome="success",
            created_at=datetime.now().isoformat(),
            tags=["HICCUP"],
        )
        memory_store.add(entry)
        memory_store.save()

        # Query multiple times
        memory_store.query(category="checkpoint_decision")
        memory_store.query(category="checkpoint_decision")
        memory_store.query(category="checkpoint_decision")

        # Check hit count (if implemented)
        # This is for measuring value per the panel's recommendation
        stats = memory_store.get_stats()
        assert "total_entries" in stats
        assert stats["total_entries"] >= 1


class TestMemoryStoreIntegration:
    """Integration tests for realistic usage patterns."""

    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary directory for test store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "memory" / "memories.json"

    def test_checkpoint_decision_workflow(self, temp_store_path):
        """Test typical checkpoint decision recording workflow."""
        from swarm_attack.memory.store import MemoryEntry, MemoryStore

        store = MemoryStore(store_path=temp_store_path)

        # Simulate recording checkpoint decisions
        decisions = [
            ("HICCUP", "Proceed", "import error resolved on retry"),
            ("HICCUP", "Proceed", "transient network error"),
            ("COST_SINGLE", "Skip", "too expensive for this task"),
            ("HICCUP", "Proceed", "test flakiness"),
        ]

        for trigger, decision, context in decisions:
            entry = MemoryEntry(
                id=str(uuid4()),
                category="checkpoint_decision",
                feature_id="test-feature",
                issue_number=None,
                content={
                    "trigger": trigger,
                    "decision": decision,
                    "context": context,
                },
                outcome="applied",
                created_at=datetime.now().isoformat(),
                tags=[trigger, decision],
            )
            store.add(entry)

        store.save()

        # Query for HICCUP decisions to learn preferences
        hiccup_decisions = store.query(
            category="checkpoint_decision",
            tags=["HICCUP"],
        )

        assert len(hiccup_decisions) == 3
        # All HICCUP decisions were "Proceed"
        for d in hiccup_decisions:
            assert d.content["decision"] == "Proceed"

    def test_schema_drift_detection_workflow(self, temp_store_path):
        """Test schema drift memory for preventing repeated mistakes."""
        from swarm_attack.memory.store import MemoryEntry, MemoryStore

        store = MemoryStore(store_path=temp_store_path)

        # Record a schema drift event
        drift_entry = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id="chief-of-staff-v3",
            issue_number=15,
            content={
                "class_name": "AutopilotSession",
                "existing_file": "swarm_attack/chief_of_staff/autopilot_runner.py",
                "new_file": "swarm_attack/chief_of_staff/session.py",
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", "AutopilotSession"],
        )
        store.add(drift_entry)
        store.save()

        # Later, when about to create AutopilotSession again, check memory
        similar = store.find_similar(
            content={"class_name": "AutopilotSession"},
            category="schema_drift",
        )

        assert len(similar) >= 1
        assert similar[0].outcome == "blocked"
        assert "autopilot_runner.py" in similar[0].content["existing_file"]
