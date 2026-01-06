"""Test for BUG-005: save_to_file should accept string paths."""
import pytest
import tempfile
import os
from pathlib import Path
from swarm_attack.memory.store import MemoryStore, MemoryEntry
import uuid
from datetime import datetime, timezone


class TestStringPathBug005:
    """BUG-005: save_to_file only accepts Path, not string."""

    def test_save_to_file_accepts_string_path(self):
        """save_to_file should accept string paths."""
        store = MemoryStore()
        store.add(MemoryEntry(
            id=str(uuid.uuid4()),
            category="test",
            feature_id="test",
            issue_number=None,
            content={"test": True},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[],
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            # String path (not Path object)
            path_str = os.path.join(tmpdir, "test.json")

            # This should NOT raise AttributeError
            store.save_to_file(path_str)

            # Verify file was created
            assert os.path.exists(path_str)

    def test_save_to_file_accepts_path_object(self):
        """save_to_file should still accept Path objects."""
        store = MemoryStore()
        store.add(MemoryEntry(
            id=str(uuid.uuid4()),
            category="test",
            feature_id="test",
            issue_number=None,
            content={"test": True},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[],
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.json"
            store.save_to_file(path)
            assert path.exists()

    def test_load_from_file_accepts_string_path(self):
        """load_from_file should accept string paths."""
        store = MemoryStore()
        entry_id = str(uuid.uuid4())
        store.add(MemoryEntry(
            id=entry_id,
            category="test",
            feature_id="test",
            issue_number=None,
            content={"test": True},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[],
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            path_str = os.path.join(tmpdir, "test.json")
            store.save_to_file(Path(path_str))  # Use Path for save

            # Load with string path
            store2 = MemoryStore()
            store2.load_from_file(path_str)

            # Verify entry was loaded
            assert store2.get_entry(entry_id) is not None

    def test_save_creates_parent_directories(self):
        """save_to_file should create parent directories for string paths."""
        store = MemoryStore()
        store.add(MemoryEntry(
            id=str(uuid.uuid4()),
            category="test",
            feature_id="test",
            issue_number=None,
            content={"test": True},
            outcome="success",
            created_at=datetime.now(timezone.utc).isoformat(),
            tags=[],
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            # Nested path that doesn't exist
            path_str = os.path.join(tmpdir, "nested", "dir", "test.json")

            # This should create the directories
            store.save_to_file(path_str)

            assert os.path.exists(path_str)
