"""TDD tests for MemoryStore file persistence methods.

Tests for new persistence methods that take explicit file paths:
- save_to_file(self, path: Path) -> None
- load_from_file(self, path: Path) -> None
- from_file(cls, path: Path) -> MemoryStore (classmethod)

These are DIFFERENT from the existing save()/load() which use self.store_path.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime
from uuid import uuid4

import pytest

from swarm_attack.memory.store import MemoryStore, MemoryEntry


def _create_sample_entry(
    category: str = "test_category",
    feature_id: str = "test-feature",
    content: dict | None = None,
) -> MemoryEntry:
    """Create a sample MemoryEntry for testing."""
    return MemoryEntry(
        id=str(uuid4()),
        category=category,
        feature_id=feature_id,
        issue_number=None,
        content=content or {"key": "value"},
        outcome="success",
        created_at=datetime.now().isoformat(),
        tags=["test", "sample"],
        hit_count=0,
    )


class TestSaveToFileCreatesJson:
    """Test that save_to_file creates a valid JSON file."""

    def test_save_to_file_creates_json(self, tmp_path: Path) -> None:
        """save_to_file should create a JSON file at the specified path."""
        # Arrange
        store = MemoryStore()
        entry = _create_sample_entry()
        store.add(entry)

        file_path = tmp_path / "test_memories.json"

        # Act
        store.save_to_file(file_path)

        # Assert
        assert file_path.exists(), "File should be created"

        # Verify it's valid JSON
        with open(file_path, "r") as f:
            data = json.load(f)

        assert "entries" in data, "JSON should have entries key"
        assert len(data["entries"]) == 1, "Should have one entry"
        assert data["entries"][0]["id"] == entry.id

    def test_save_to_file_empty_store(self, tmp_path: Path) -> None:
        """save_to_file should work with empty store."""
        # Arrange
        store = MemoryStore()
        file_path = tmp_path / "empty_store.json"

        # Act
        store.save_to_file(file_path)

        # Assert
        assert file_path.exists()
        with open(file_path, "r") as f:
            data = json.load(f)
        assert data["entries"] == []

    def test_save_to_file_multiple_entries(self, tmp_path: Path) -> None:
        """save_to_file should save multiple entries."""
        # Arrange
        store = MemoryStore()
        entries = [_create_sample_entry(feature_id=f"feature-{i}") for i in range(5)]
        for entry in entries:
            store.add(entry)

        file_path = tmp_path / "multi_entries.json"

        # Act
        store.save_to_file(file_path)

        # Assert
        with open(file_path, "r") as f:
            data = json.load(f)
        assert len(data["entries"]) == 5


class TestLoadFromFileRestoresEntries:
    """Test that load_from_file properly restores entries."""

    def test_load_from_file_restores_entries(self, tmp_path: Path) -> None:
        """load_from_file should restore entries from a JSON file."""
        # Arrange - Create a file with entries
        entry_data = {
            "version": "1.0",
            "entries": [
                {
                    "id": "test-id-123",
                    "category": "checkpoint_decision",
                    "feature_id": "my-feature",
                    "issue_number": 42,
                    "content": {"reason": "test"},
                    "outcome": "success",
                    "created_at": "2025-01-01T00:00:00",
                    "tags": ["important"],
                    "hit_count": 5,
                }
            ],
            "stats": {"total_queries": 10},
        }

        file_path = tmp_path / "entries.json"
        with open(file_path, "w") as f:
            json.dump(entry_data, f)

        store = MemoryStore()

        # Act
        store.load_from_file(file_path)

        # Assert
        restored_entry = store.get_entry("test-id-123")
        assert restored_entry is not None
        assert restored_entry.category == "checkpoint_decision"
        assert restored_entry.feature_id == "my-feature"
        assert restored_entry.issue_number == 42
        assert restored_entry.tags == ["important"]
        assert restored_entry.hit_count == 5

    def test_load_from_file_adds_to_existing(self, tmp_path: Path) -> None:
        """load_from_file should add to existing entries (not replace)."""
        # Arrange
        store = MemoryStore()
        existing_entry = _create_sample_entry(feature_id="existing")
        store.add(existing_entry)

        entry_data = {
            "version": "1.0",
            "entries": [
                {
                    "id": "new-id-456",
                    "category": "schema_drift",
                    "feature_id": "new-feature",
                    "issue_number": None,
                    "content": {},
                    "outcome": None,
                    "created_at": "2025-01-02T00:00:00",
                    "tags": [],
                    "hit_count": 0,
                }
            ],
        }

        file_path = tmp_path / "additional.json"
        with open(file_path, "w") as f:
            json.dump(entry_data, f)

        # Act
        store.load_from_file(file_path)

        # Assert - Should have both entries
        assert store.get_entry(existing_entry.id) is not None
        assert store.get_entry("new-id-456") is not None

    def test_load_from_file_multiple_entries(self, tmp_path: Path) -> None:
        """load_from_file should restore multiple entries."""
        # Arrange
        entry_data = {
            "version": "1.0",
            "entries": [
                {
                    "id": f"entry-{i}",
                    "category": "test",
                    "feature_id": f"feature-{i}",
                    "issue_number": None,
                    "content": {"index": i},
                    "outcome": "success",
                    "created_at": "2025-01-01T00:00:00",
                    "tags": [],
                    "hit_count": 0,
                }
                for i in range(10)
            ],
        }

        file_path = tmp_path / "many_entries.json"
        with open(file_path, "w") as f:
            json.dump(entry_data, f)

        store = MemoryStore()

        # Act
        store.load_from_file(file_path)

        # Assert
        stats = store.get_stats()
        assert stats["total_entries"] == 10


class TestSaveLoadRoundTrip:
    """Test that save and load work together as a round trip."""

    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        """Full round trip: save_to_file then load_from_file preserves data."""
        # Arrange
        original_store = MemoryStore()
        entries = [
            _create_sample_entry(
                category="checkpoint_decision",
                feature_id="feature-1",
                content={"decision": "proceed", "confidence": 0.95},
            ),
            _create_sample_entry(
                category="schema_drift",
                feature_id="feature-2",
                content={"class_name": "MyClass", "conflict": "duplicate"},
            ),
            _create_sample_entry(
                category="test_failure",
                feature_id="feature-3",
                content={"test_path": "tests/test_foo.py", "error": "AssertionError"},
            ),
        ]

        for entry in entries:
            original_store.add(entry)

        file_path = tmp_path / "round_trip.json"

        # Act
        original_store.save_to_file(file_path)

        restored_store = MemoryStore()
        restored_store.load_from_file(file_path)

        # Assert - All entries should be restored with correct data
        for original_entry in entries:
            restored = restored_store.get_entry(original_entry.id)
            assert restored is not None, f"Entry {original_entry.id} should be restored"
            assert restored.category == original_entry.category
            assert restored.feature_id == original_entry.feature_id
            assert restored.content == original_entry.content
            assert restored.tags == original_entry.tags

    def test_round_trip_with_classmethod(self, tmp_path: Path) -> None:
        """Round trip using from_file classmethod."""
        # Arrange
        original_store = MemoryStore()
        entry = _create_sample_entry(
            category="important",
            content={"data": [1, 2, 3], "nested": {"key": "value"}},
        )
        original_store.add(entry)

        file_path = tmp_path / "classmethod_test.json"
        original_store.save_to_file(file_path)

        # Act - Use classmethod to create new store from file
        restored_store = MemoryStore.from_file(file_path)

        # Assert
        restored = restored_store.get_entry(entry.id)
        assert restored is not None
        assert restored.content == entry.content

    def test_round_trip_preserves_stats(self, tmp_path: Path) -> None:
        """Round trip should preserve query statistics."""
        # Arrange
        original_store = MemoryStore()
        entry = _create_sample_entry()
        original_store.add(entry)

        # Perform some queries to increment stats
        original_store.query(category="test_category")
        original_store.query(feature_id="test-feature")
        original_store.query(tags=["test"])

        original_stats = original_store.get_stats()
        file_path = tmp_path / "stats_test.json"

        # Act
        original_store.save_to_file(file_path)
        restored_store = MemoryStore.from_file(file_path)

        # Assert
        restored_stats = restored_store.get_stats()
        assert restored_stats["total_queries"] == original_stats["total_queries"]


class TestLoadNonexistentFileReturnsEmpty:
    """Test graceful handling when loading from nonexistent files."""

    def test_load_nonexistent_file_returns_empty(self, tmp_path: Path) -> None:
        """load_from_file with nonexistent path should not raise, entries stay empty."""
        # Arrange
        store = MemoryStore()
        nonexistent_path = tmp_path / "does_not_exist.json"

        # Act - Should not raise
        store.load_from_file(nonexistent_path)

        # Assert - Store should remain empty
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_from_file_nonexistent_returns_empty_store(self, tmp_path: Path) -> None:
        """from_file classmethod with nonexistent path returns empty store."""
        # Arrange
        nonexistent_path = tmp_path / "nonexistent" / "deeply" / "nested" / "file.json"

        # Act
        store = MemoryStore.from_file(nonexistent_path)

        # Assert
        assert store is not None
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_load_from_file_preserves_existing_on_missing(self, tmp_path: Path) -> None:
        """load_from_file on missing file should preserve existing entries."""
        # Arrange
        store = MemoryStore()
        existing_entry = _create_sample_entry()
        store.add(existing_entry)

        nonexistent_path = tmp_path / "missing.json"

        # Act
        store.load_from_file(nonexistent_path)

        # Assert - Existing entry should still be there
        assert store.get_entry(existing_entry.id) is not None


class TestSaveCreatesDirectory:
    """Test that save_to_file creates parent directories if needed."""

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """save_to_file should create parent directories if they don't exist."""
        # Arrange
        store = MemoryStore()
        entry = _create_sample_entry()
        store.add(entry)

        # Deeply nested path that doesn't exist
        nested_path = tmp_path / "level1" / "level2" / "level3" / "memories.json"

        # Act
        store.save_to_file(nested_path)

        # Assert
        assert nested_path.exists()
        assert nested_path.parent.exists()

        # Verify content is valid
        with open(nested_path, "r") as f:
            data = json.load(f)
        assert len(data["entries"]) == 1

    def test_save_creates_single_level_directory(self, tmp_path: Path) -> None:
        """save_to_file should create single-level parent directory."""
        # Arrange
        store = MemoryStore()
        store.add(_create_sample_entry())

        single_level_path = tmp_path / "new_folder" / "store.json"

        # Act
        store.save_to_file(single_level_path)

        # Assert
        assert single_level_path.exists()

    def test_save_works_with_existing_directory(self, tmp_path: Path) -> None:
        """save_to_file should work when directory already exists."""
        # Arrange
        store = MemoryStore()
        store.add(_create_sample_entry())

        # Directory already exists (tmp_path)
        file_path = tmp_path / "already_exists.json"

        # Act - Should not raise
        store.save_to_file(file_path)

        # Assert
        assert file_path.exists()


class TestCorruptedFileHandledGracefully:
    """Test graceful handling of corrupted/invalid JSON files."""

    def test_corrupted_file_handled_gracefully(self, tmp_path: Path) -> None:
        """load_from_file with corrupted JSON should not raise, return empty."""
        # Arrange
        store = MemoryStore()
        corrupted_path = tmp_path / "corrupted.json"

        # Write invalid JSON
        with open(corrupted_path, "w") as f:
            f.write("{ this is not valid json }")

        # Act - Should not raise
        store.load_from_file(corrupted_path)

        # Assert - Store should be empty
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_from_file_corrupted_returns_empty_store(self, tmp_path: Path) -> None:
        """from_file classmethod with corrupted file returns empty store."""
        # Arrange
        corrupted_path = tmp_path / "bad_json.json"
        with open(corrupted_path, "w") as f:
            f.write("not json at all")

        # Act
        store = MemoryStore.from_file(corrupted_path)

        # Assert
        assert store is not None
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_empty_file_handled_gracefully(self, tmp_path: Path) -> None:
        """load_from_file with empty file should not raise."""
        # Arrange
        store = MemoryStore()
        empty_path = tmp_path / "empty.json"
        empty_path.touch()  # Create empty file

        # Act - Should not raise
        store.load_from_file(empty_path)

        # Assert
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_partial_json_handled_gracefully(self, tmp_path: Path) -> None:
        """load_from_file with truncated JSON should not raise."""
        # Arrange
        store = MemoryStore()
        partial_path = tmp_path / "partial.json"

        # Write truncated JSON (missing closing brace)
        with open(partial_path, "w") as f:
            f.write('{"version": "1.0", "entries": [')

        # Act - Should not raise
        store.load_from_file(partial_path)

        # Assert
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_wrong_structure_handled_gracefully(self, tmp_path: Path) -> None:
        """load_from_file with valid JSON but wrong structure should handle gracefully."""
        # Arrange
        store = MemoryStore()
        wrong_structure_path = tmp_path / "wrong_structure.json"

        # Valid JSON but wrong structure (array instead of object)
        with open(wrong_structure_path, "w") as f:
            json.dump([1, 2, 3], f)

        # Act - Should not raise
        store.load_from_file(wrong_structure_path)

        # Assert - Should remain empty
        stats = store.get_stats()
        assert stats["total_entries"] == 0

    def test_corrupted_preserves_existing_entries(self, tmp_path: Path) -> None:
        """load_from_file with corrupted file should preserve existing entries."""
        # Arrange
        store = MemoryStore()
        existing_entry = _create_sample_entry(feature_id="existing-before-corruption")
        store.add(existing_entry)

        corrupted_path = tmp_path / "corrupt_after_existing.json"
        with open(corrupted_path, "w") as f:
            f.write("garbage data")

        # Act
        store.load_from_file(corrupted_path)

        # Assert - Existing entry should still be there
        assert store.get_entry(existing_entry.id) is not None
        assert store.get_entry(existing_entry.id).feature_id == "existing-before-corruption"
