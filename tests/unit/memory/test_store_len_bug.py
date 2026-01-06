"""Test for BUG-007: MemoryStore missing __len__ method."""
import pytest
from swarm_attack.memory.store import MemoryStore, MemoryEntry
import uuid
from datetime import datetime, timezone


class TestLenBug007:
    """BUG-007: MemoryStore should support len()."""

    def test_len_empty_store(self):
        """len() should return 0 for empty store."""
        store = MemoryStore()
        assert len(store) == 0

    def test_len_after_add(self):
        """len() should return correct count after adds."""
        store = MemoryStore()

        for i in range(5):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="test",
                feature_id="test",
                issue_number=i,
                content={"i": i},
                outcome="success",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=[],
            ))

        assert len(store) == 5

    def test_len_after_delete(self):
        """len() should update after deletes."""
        store = MemoryStore()

        entry_id = str(uuid.uuid4())
        store.add(MemoryEntry(
            id=entry_id,
            category="test",
            feature_id="test",
            issue_number=None,
            content={},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[],
        ))

        assert len(store) == 1
        store.delete(entry_id)
        assert len(store) == 0

    def test_len_after_clear(self):
        """len() should return 0 after clear."""
        store = MemoryStore()

        for i in range(3):
            store.add(MemoryEntry(
                id=str(uuid.uuid4()),
                category="test",
                feature_id="test",
                issue_number=i,
                content={},
                outcome="success",
                created_at=datetime.now(timezone.utc).isoformat(),
                tags=[],
            ))

        assert len(store) == 3
        store.clear()
        assert len(store) == 0

    def test_len_with_bool_conversion(self):
        """Empty store should be falsy, non-empty should be truthy."""
        store = MemoryStore()

        # Empty store should be falsy
        assert not store  # Uses __len__ for bool conversion

        store.add(MemoryEntry(
            id=str(uuid.uuid4()),
            category="test",
            feature_id="test",
            issue_number=None,
            content={},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[],
        ))

        # Non-empty store should be truthy
        assert store  # Uses __len__ for bool conversion
