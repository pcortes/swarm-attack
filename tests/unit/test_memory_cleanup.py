"""Tests for MemoryStore cleanup methods.

Tests prune_old_entries() and prune_low_value_entries() methods for
managing memory store growth and removing stale/unused entries.
"""

from datetime import datetime, timedelta
from pathlib import Path
import tempfile

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


def _create_entry(
    entry_id: str,
    created_at: datetime | None = None,
    hit_count: int = 0,
) -> MemoryEntry:
    """Helper to create a MemoryEntry with specified age and hit count."""
    if created_at is None:
        created_at = datetime.now()

    return MemoryEntry(
        id=entry_id,
        category="test",
        feature_id="test-feature",
        issue_number=None,
        content={"test": "data"},
        outcome="success",
        created_at=created_at.isoformat(),
        tags=["test"],
        hit_count=hit_count,
    )


class TestPruneOldEntries:
    """Tests for prune_old_entries() method."""

    def test_prune_old_entries_removes_entries_older_than_days(self) -> None:
        """Entries older than the specified days should be removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(store_path=Path(tmpdir) / "test.json")

            # Add an old entry (10 days ago)
            old_entry = _create_entry(
                "old-entry",
                created_at=datetime.now() - timedelta(days=10),
            )
            store.add(old_entry)

            # Add a recent entry (1 day ago)
            recent_entry = _create_entry(
                "recent-entry",
                created_at=datetime.now() - timedelta(days=1),
            )
            store.add(recent_entry)

            # Prune entries older than 7 days
            removed_count = store.prune_old_entries(days=7)

            # Should have removed 1 entry
            assert removed_count == 1

            # Old entry should be gone
            assert store.get_entry("old-entry") is None

            # Recent entry should remain
            assert store.get_entry("recent-entry") is not None

    def test_prune_old_entries_keeps_recent_entries(self) -> None:
        """Entries newer than the specified days should be kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(store_path=Path(tmpdir) / "test.json")

            # Add entries that are 1, 2, 3 days old
            for i in range(1, 4):
                entry = _create_entry(
                    f"entry-{i}",
                    created_at=datetime.now() - timedelta(days=i),
                )
                store.add(entry)

            # Prune entries older than 7 days
            removed_count = store.prune_old_entries(days=7)

            # Nothing should be removed
            assert removed_count == 0

            # All entries should still exist
            for i in range(1, 4):
                assert store.get_entry(f"entry-{i}") is not None

    def test_prune_old_entries_with_zero_days_removes_nothing(self) -> None:
        """With days=0, no entries should be removed (edge case)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(store_path=Path(tmpdir) / "test.json")

            # Add an entry from just now
            entry = _create_entry("now-entry", created_at=datetime.now())
            store.add(entry)

            # Add an entry from 1 second ago
            entry_old = _create_entry(
                "second-ago",
                created_at=datetime.now() - timedelta(seconds=1),
            )
            store.add(entry_old)

            # Prune with 0 days - nothing should be removed
            # (0 days means "remove entries older than 0 days", but nothing can be
            # older than 0 days, so nothing is removed)
            removed_count = store.prune_old_entries(days=0)

            # Nothing removed
            assert removed_count == 0
            assert store.get_entry("now-entry") is not None
            assert store.get_entry("second-ago") is not None


class TestPruneLowValueEntries:
    """Tests for prune_low_value_entries() method."""

    def test_prune_low_value_entries_removes_entries_with_zero_hits(self) -> None:
        """Entries with 0 hit_count should be removed with default min_hits=1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(store_path=Path(tmpdir) / "test.json")

            # Add entry with 0 hits
            zero_hit = _create_entry("zero-hit", hit_count=0)
            store.add(zero_hit)

            # Add entry with 1 hit
            one_hit = _create_entry("one-hit", hit_count=1)
            store.add(one_hit)

            # Prune low value entries (default min_hits=1)
            removed_count = store.prune_low_value_entries()

            # Should have removed 1 entry
            assert removed_count == 1

            # Zero hit entry should be gone
            assert store.get_entry("zero-hit") is None

            # One hit entry should remain
            assert store.get_entry("one-hit") is not None

    def test_prune_low_value_entries_keeps_entries_with_hits(self) -> None:
        """Entries with hit_count >= min_hits should be kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(store_path=Path(tmpdir) / "test.json")

            # Add entries with varying hit counts
            for hits in [1, 2, 5, 10]:
                entry = _create_entry(f"entry-{hits}-hits", hit_count=hits)
                store.add(entry)

            # Prune with min_hits=1
            removed_count = store.prune_low_value_entries(min_hits=1)

            # Nothing should be removed
            assert removed_count == 0

            # All entries should still exist
            for hits in [1, 2, 5, 10]:
                assert store.get_entry(f"entry-{hits}-hits") is not None

    def test_prune_low_value_entries_with_custom_threshold(self) -> None:
        """Custom min_hits threshold should work correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = MemoryStore(store_path=Path(tmpdir) / "test.json")

            # Add entries with varying hit counts
            store.add(_create_entry("hits-0", hit_count=0))
            store.add(_create_entry("hits-1", hit_count=1))
            store.add(_create_entry("hits-2", hit_count=2))
            store.add(_create_entry("hits-5", hit_count=5))

            # Prune with min_hits=3 (removes entries with < 3 hits)
            removed_count = store.prune_low_value_entries(min_hits=3)

            # Should have removed 3 entries (0, 1, 2 hits)
            assert removed_count == 3

            # Only entry with 5 hits should remain
            assert store.get_entry("hits-0") is None
            assert store.get_entry("hits-1") is None
            assert store.get_entry("hits-2") is None
            assert store.get_entry("hits-5") is not None
