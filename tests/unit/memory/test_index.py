"""TDD tests for MemoryIndex - inverted index for fast memory search.

Tests for MemoryIndex class that will be in swarm_attack/memory/index.py.

The MemoryIndex provides:
- Inverted index built on MemoryStore load
- Index updates on entry add/delete
- Fast keyword-based lookup via index
- Persistence alongside the MemoryStore

These tests are written in TDD RED phase - they should FAIL because
the MemoryIndex class doesn't exist yet.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryEntry, MemoryStore


def _create_entry(
    category: str = "test_category",
    feature_id: str = "test-feature",
    content: dict | None = None,
    tags: list[str] | None = None,
    entry_id: str | None = None,
    days_ago: int = 0,
) -> MemoryEntry:
    """Create a MemoryEntry for testing.

    Args:
        category: Entry category.
        feature_id: Feature ID.
        content: Optional content dictionary.
        tags: Optional list of tags.
        entry_id: Optional specific ID for the entry.
        days_ago: How many days ago the entry was created.

    Returns:
        MemoryEntry with specified attributes.
    """
    created_at = datetime.now() - timedelta(days=days_ago)
    return MemoryEntry(
        id=entry_id or str(uuid4()),
        category=category,
        feature_id=feature_id,
        issue_number=None,
        content=content or {"key": "value"},
        outcome="success",
        created_at=created_at.isoformat(),
        tags=tags or ["test"],
        hit_count=0,
    )


@pytest.fixture
def temp_store_path(tmp_path: Path) -> Path:
    """Provide a temporary path for store persistence."""
    return tmp_path / "test_memories.json"


@pytest.fixture
def temp_index_path(tmp_path: Path) -> Path:
    """Provide a temporary path for index persistence."""
    return tmp_path / "test_index.json"


@pytest.fixture
def memory_store(temp_store_path: Path) -> MemoryStore:
    """Create a MemoryStore with temporary storage path."""
    return MemoryStore(store_path=temp_store_path)


class TestIndexBuildsOnInit:
    """Tests for test_index_builds_on_init - index built when store loaded."""

    def test_index_builds_on_init_with_existing_entries(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex builds inverted index when initialized with populated store.

        When a MemoryStore has existing entries, creating a MemoryIndex should
        build the inverted index from all entries' content keywords.
        """
        # Import the class we're testing (will fail - RED phase)
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Add entries with searchable content
        entry1 = _create_entry(
            entry_id="entry-1",
            content={"message": "authentication failed", "error_code": "AUTH_001"},
        )
        entry2 = _create_entry(
            entry_id="entry-2",
            content={"message": "database connection timeout", "error_code": "DB_001"},
        )
        memory_store.add(entry1)
        memory_store.add(entry2)

        # Act - Create index from store
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Index should have keywords mapped to entry IDs
        assert index.get_entries_for_keyword("authentication") == {"entry-1"}
        assert index.get_entries_for_keyword("database") == {"entry-2"}
        assert index.get_entries_for_keyword("failed") == {"entry-1"}
        assert index.get_entries_for_keyword("timeout") == {"entry-2"}

    def test_index_builds_on_init_empty_store(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex initializes with empty index when store is empty."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Store is empty

        # Act
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Index should be empty but functional
        assert index.get_entries_for_keyword("anything") == set()
        assert index.keyword_count() == 0

    def test_index_builds_on_init_indexes_tags(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex indexes entry tags for searchability."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="tagged-entry",
            tags=["schema_drift", "user_model", "urgent"],
        )
        memory_store.add(entry)

        # Act
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Tags should be indexed
        assert index.get_entries_for_keyword("schema_drift") == {"tagged-entry"}
        assert index.get_entries_for_keyword("user_model") == {"tagged-entry"}
        assert index.get_entries_for_keyword("urgent") == {"tagged-entry"}

    def test_index_builds_on_init_indexes_category_and_feature(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex indexes category and feature_id for fast filtering."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="categorized-entry",
            category="test_failure",
            feature_id="auth-system",
        )
        memory_store.add(entry)

        # Act
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Category and feature_id should be indexed
        assert index.get_entries_for_keyword("test_failure") == {"categorized-entry"}
        assert index.get_entries_for_keyword("auth-system") == {"categorized-entry"}

    def test_index_builds_on_init_handles_nested_content(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex indexes deeply nested content values."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="nested-entry",
            content={
                "error": {
                    "type": "ValidationError",
                    "details": {
                        "field": "email",
                        "message": "invalid format",
                    },
                },
            },
        )
        memory_store.add(entry)

        # Act
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Nested values should be indexed
        assert index.get_entries_for_keyword("validationerror") == {"nested-entry"}
        assert index.get_entries_for_keyword("email") == {"nested-entry"}
        assert index.get_entries_for_keyword("invalid") == {"nested-entry"}


class TestIndexUpdatesOnAdd:
    """Tests for test_index_updates_on_add - new entries added to index."""

    def test_index_updates_on_add_single_entry(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Adding an entry to the store updates the index immediately."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Create index with empty store
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Add entry to store (index should observe this)
        new_entry = _create_entry(
            entry_id="new-entry",
            content={"message": "new feature implemented"},
        )
        index.add_entry(new_entry)

        # Assert - New keywords should be in index
        assert index.get_entries_for_keyword("new") == {"new-entry"}
        assert index.get_entries_for_keyword("feature") == {"new-entry"}
        assert index.get_entries_for_keyword("implemented") == {"new-entry"}

    def test_index_updates_on_add_multiple_entries(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Adding multiple entries updates index with all keywords."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        entry1 = _create_entry(
            entry_id="entry-1",
            content={"keyword": "shared_term"},
        )
        entry2 = _create_entry(
            entry_id="entry-2",
            content={"keyword": "shared_term"},
        )
        index.add_entry(entry1)
        index.add_entry(entry2)

        # Assert - Shared keyword should map to both entries
        assert index.get_entries_for_keyword("shared_term") == {"entry-1", "entry-2"}

    def test_index_updates_on_add_preserves_existing_mappings(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Adding new entries doesn't affect existing index mappings."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        existing_entry = _create_entry(
            entry_id="existing",
            content={"term": "original"},
        )
        memory_store.add(existing_entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Add new entry
        new_entry = _create_entry(
            entry_id="new",
            content={"term": "different"},
        )
        index.add_entry(new_entry)

        # Assert - Original mapping preserved
        assert "existing" in index.get_entries_for_keyword("original")
        # New mapping added
        assert "new" in index.get_entries_for_keyword("different")

    def test_index_updates_on_add_also_adds_to_store(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """add_entry adds entry to both the index and the underlying store."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        new_entry = _create_entry(entry_id="test-entry")
        index.add_entry(new_entry)

        # Assert - Entry should be in the store as well
        assert memory_store.get_entry("test-entry") is not None


class TestIndexUpdatesOnDelete:
    """Tests for test_index_updates_on_delete - removed entries removed from index."""

    def test_index_updates_on_delete_removes_entry_mappings(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Deleting an entry removes its keywords from the index."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="to-delete",
            content={"keyword": "removable"},
        )
        memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Verify entry is indexed
        assert "to-delete" in index.get_entries_for_keyword("removable")

        # Act - Delete entry
        index.delete_entry("to-delete")

        # Assert - Entry should no longer be in index
        assert "to-delete" not in index.get_entries_for_keyword("removable")

    def test_index_updates_on_delete_preserves_other_entries_with_same_keyword(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Deleting entry only removes that entry, not others with same keyword."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry1 = _create_entry(
            entry_id="entry-1",
            content={"shared": "common_keyword"},
        )
        entry2 = _create_entry(
            entry_id="entry-2",
            content={"shared": "common_keyword"},
        )
        memory_store.add(entry1)
        memory_store.add(entry2)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Delete only entry-1
        index.delete_entry("entry-1")

        # Assert - entry-2 should still be indexed
        assert index.get_entries_for_keyword("common_keyword") == {"entry-2"}

    def test_index_updates_on_delete_removes_orphaned_keywords(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """When last entry with a keyword is deleted, keyword is removed from index."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="only-entry",
            content={"unique": "orphan_keyword"},
        )
        memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        initial_keyword_count = index.keyword_count()

        # Act
        index.delete_entry("only-entry")

        # Assert - Keyword should be removed entirely
        assert index.get_entries_for_keyword("orphan_keyword") == set()
        assert index.keyword_count() < initial_keyword_count

    def test_index_updates_on_delete_handles_nonexistent_entry(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Deleting non-existent entry is a no-op, doesn't raise."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act & Assert - Should not raise
        result = index.delete_entry("nonexistent-id")
        assert result is False  # Indicates nothing was deleted

    def test_index_updates_on_delete_also_removes_from_store(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """delete_entry removes entry from both the index and the underlying store."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(entry_id="to-remove")
        memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        index.delete_entry("to-remove")

        # Assert - Entry should be removed from store as well
        assert memory_store.get_entry("to-remove") is None


class TestSearchUsesIndex:
    """Tests for test_search_uses_index - fast lookup via index."""

    def test_search_uses_index_single_keyword(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search with single keyword uses index for fast lookup."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entries = [
            _create_entry(entry_id="match-1", content={"msg": "error occurred"}),
            _create_entry(entry_id="match-2", content={"msg": "another error"}),
            _create_entry(entry_id="no-match", content={"msg": "success"}),
        ]
        for entry in entries:
            memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        results = index.search(keywords=["error"])

        # Assert - Only entries with "error" returned
        result_ids = {entry.id for entry in results}
        assert result_ids == {"match-1", "match-2"}

    def test_search_uses_index_multiple_keywords_intersection(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search with multiple keywords returns intersection (AND logic)."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entries = [
            _create_entry(entry_id="both", content={"msg": "authentication error"}),
            _create_entry(entry_id="only-auth", content={"msg": "authentication success"}),
            _create_entry(entry_id="only-error", content={"msg": "database error"}),
        ]
        for entry in entries:
            memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Search for entries with both keywords
        results = index.search(keywords=["authentication", "error"])

        # Assert - Only entry with both keywords
        result_ids = {entry.id for entry in results}
        assert result_ids == {"both"}

    def test_search_uses_index_case_insensitive(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search is case-insensitive."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="mixed-case",
            content={"msg": "AuthenticationError occurred"},
        )
        memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Search with different cases
        results_lower = index.search(keywords=["authenticationerror"])
        results_upper = index.search(keywords=["AUTHENTICATIONERROR"])

        # Assert - Both should find the entry
        assert {e.id for e in results_lower} == {"mixed-case"}
        assert {e.id for e in results_upper} == {"mixed-case"}

    def test_search_uses_index_respects_limit(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search respects the limit parameter."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        for i in range(10):
            entry = _create_entry(
                entry_id=f"entry-{i}",
                content={"keyword": "common"},
            )
            memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        results = index.search(keywords=["common"], limit=3)

        # Assert
        assert len(results) == 3

    def test_search_uses_index_returns_empty_for_no_matches(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search returns empty list when no entries match."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(content={"msg": "hello world"})
        memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        results = index.search(keywords=["nonexistent"])

        # Assert
        assert results == []

    def test_search_uses_index_filters_by_category(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search can optionally filter by category."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry1 = _create_entry(
            entry_id="drift-entry",
            category="schema_drift",
            content={"msg": "class renamed"},
        )
        entry2 = _create_entry(
            entry_id="failure-entry",
            category="test_failure",
            content={"msg": "class not found"},
        )
        memory_store.add(entry1)
        memory_store.add(entry2)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Search for "class" but only in schema_drift category
        results = index.search(keywords=["class"], category="schema_drift")

        # Assert
        result_ids = {entry.id for entry in results}
        assert result_ids == {"drift-entry"}

    def test_search_uses_index_is_faster_than_linear_scan(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """Search via index should be O(1) lookup, not O(n) scan.

        This test verifies the index is actually being used by checking
        that search doesn't iterate all entries for a single keyword lookup.
        """
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Add many entries, only one matches
        for i in range(100):
            entry = _create_entry(
                entry_id=f"entry-{i}",
                content={"data": f"content_{i}"},
            )
            memory_store.add(entry)

        # Add one entry with unique keyword
        unique_entry = _create_entry(
            entry_id="unique-entry",
            content={"special": "unique_searchable_keyword"},
        )
        memory_store.add(unique_entry)

        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act - Search should use index, not scan all entries
        results = index.search(keywords=["unique_searchable_keyword"])

        # Assert - Should find only the unique entry efficiently
        assert len(results) == 1
        assert results[0].id == "unique-entry"


class TestIndexPersistsWithStore:
    """Tests for test_index_persists_with_store - index saved/loaded with store."""

    def test_index_persists_with_store_saves_to_file(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex saves index data to file when save() is called."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        entry = _create_entry(
            entry_id="persist-test",
            content={"msg": "persistent data"},
        )
        memory_store.add(entry)
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Act
        index.save()

        # Assert - File should exist with index data
        assert temp_index_path.exists()
        with open(temp_index_path) as f:
            data = json.load(f)
        assert "inverted_index" in data
        assert "persistent" in data["inverted_index"]

    def test_index_persists_with_store_loads_from_file(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex loads index from file on init if file exists."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Create and save index
        entry = _create_entry(
            entry_id="load-test",
            content={"msg": "loadable data"},
        )
        memory_store.add(entry)
        index1 = MemoryIndex(store=memory_store, index_path=temp_index_path)
        index1.save()

        # Act - Create new index from same path (should load)
        index2 = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Index should have loaded data
        assert index2.get_entries_for_keyword("loadable") == {"load-test"}

    def test_index_persists_with_store_rebuilds_if_file_missing(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex rebuilds from store if index file is missing."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Add entry to store, no index file
        entry = _create_entry(
            entry_id="rebuild-test",
            content={"msg": "rebuild data"},
        )
        memory_store.add(entry)
        assert not temp_index_path.exists()

        # Act
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Index should have been built from store
        assert index.get_entries_for_keyword("rebuild") == {"rebuild-test"}

    def test_index_persists_with_store_rebuilds_if_file_corrupted(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex rebuilds from store if index file is corrupted."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Create corrupted index file
        with open(temp_index_path, "w") as f:
            f.write("not valid json {{{")

        entry = _create_entry(
            entry_id="corrupt-test",
            content={"msg": "recovered data"},
        )
        memory_store.add(entry)

        # Act - Should handle corruption gracefully
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Index should be rebuilt from store
        assert index.get_entries_for_keyword("recovered") == {"corrupt-test"}

    def test_index_persists_with_store_version_mismatch_rebuilds(
        self, memory_store: MemoryStore, temp_index_path: Path
    ) -> None:
        """MemoryIndex rebuilds if persisted index version doesn't match."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange - Create index file with old version
        old_index_data = {
            "version": "0.1",  # Old version
            "inverted_index": {"old": ["old-entry"]},
        }
        with open(temp_index_path, "w") as f:
            json.dump(old_index_data, f)

        entry = _create_entry(
            entry_id="version-test",
            content={"msg": "new version data"},
        )
        memory_store.add(entry)

        # Act
        index = MemoryIndex(store=memory_store, index_path=temp_index_path)

        # Assert - Index should be rebuilt with current version
        # Old entries from stale index file shouldn't be present if entry not in store
        assert index.get_entries_for_keyword("new") == {"version-test"}

    def test_index_persists_with_store_sync_with_store_save(
        self, temp_store_path: Path, temp_index_path: Path
    ) -> None:
        """MemoryIndex and MemoryStore can be saved together."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        store = MemoryStore(store_path=temp_store_path)
        index = MemoryIndex(store=store, index_path=temp_index_path)

        entry = _create_entry(
            entry_id="sync-test",
            content={"msg": "synchronized"},
        )
        index.add_entry(entry)

        # Act - Save both
        store.save()
        index.save()

        # Assert - Both files should exist
        assert temp_store_path.exists()
        assert temp_index_path.exists()

        # Verify we can reload
        store2 = MemoryStore.load(temp_store_path)
        index2 = MemoryIndex(store=store2, index_path=temp_index_path)

        assert store2.get_entry("sync-test") is not None
        assert index2.get_entries_for_keyword("synchronized") == {"sync-test"}

    def test_index_persists_with_store_default_path_alongside_store(
        self, temp_store_path: Path
    ) -> None:
        """MemoryIndex defaults to index file alongside store file."""
        from swarm_attack.memory.index import MemoryIndex

        # Arrange
        store = MemoryStore(store_path=temp_store_path)
        entry = _create_entry(entry_id="default-path")
        store.add(entry)

        # Act - Create index without explicit path
        index = MemoryIndex(store=store)
        index.save()

        # Assert - Index file should be next to store file
        expected_index_path = temp_store_path.parent / "index.json"
        assert expected_index_path.exists()
