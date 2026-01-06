"""Test for BUG-004: CLI should auto-load from config path."""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from swarm_attack.memory.store import MemoryStore, MemoryEntry
from datetime import datetime, timezone
import uuid


class TestCLIAutoloadBug004:
    """BUG-004: CLI should auto-load persisted data."""

    def test_get_memory_store_loads_from_store_json(self):
        """get_memory_store should load from .swarm/memory/store.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create store file in the standard location
            store_path = Path(tmpdir) / ".swarm" / "memory" / "store.json"
            store_path.parent.mkdir(parents=True, exist_ok=True)

            store = MemoryStore()
            for i in range(5):
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
            store.save_to_file(store_path)

            # Patch Path.cwd to return our temp directory
            with patch.object(Path, 'cwd', return_value=Path(tmpdir)):
                from swarm_attack.cli.memory import get_memory_store
                loaded_store = get_memory_store()

                # Should have loaded 5 entries
                assert len(loaded_store) == 5

    def test_get_memory_store_loads_from_memories_json_fallback(self):
        """get_memory_store should fallback to memories.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create store file in legacy location
            store_path = Path(tmpdir) / ".swarm" / "memory" / "memories.json"
            store_path.parent.mkdir(parents=True, exist_ok=True)

            store = MemoryStore()
            for i in range(3):
                store.add(MemoryEntry(
                    id=str(uuid.uuid4()),
                    category="legacy",
                    feature_id="test",
                    issue_number=i,
                    content={},
                    outcome="success",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    tags=[],
                ))
            store.save_to_file(store_path)

            with patch.object(Path, 'cwd', return_value=Path(tmpdir)):
                from swarm_attack.cli.memory import get_memory_store
                loaded_store = get_memory_store()

                # Should have loaded 3 entries from legacy location
                assert len(loaded_store) == 3

    def test_get_memory_store_prefers_store_json(self):
        """get_memory_store should prefer store.json over memories.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both files
            store_json = Path(tmpdir) / ".swarm" / "memory" / "store.json"
            memories_json = Path(tmpdir) / ".swarm" / "memory" / "memories.json"
            store_json.parent.mkdir(parents=True, exist_ok=True)

            # Put 5 entries in store.json
            store1 = MemoryStore()
            for i in range(5):
                store1.add(MemoryEntry(
                    id=str(uuid.uuid4()),
                    category="preferred",
                    feature_id="test",
                    issue_number=i,
                    content={},
                    outcome="success",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    tags=[],
                ))
            store1.save_to_file(store_json)

            # Put 3 entries in memories.json
            store2 = MemoryStore()
            for i in range(3):
                store2.add(MemoryEntry(
                    id=str(uuid.uuid4()),
                    category="legacy",
                    feature_id="test",
                    issue_number=i,
                    content={},
                    outcome="success",
                    created_at=datetime.now(timezone.utc).isoformat(),
                    tags=[],
                ))
            store2.save_to_file(memories_json)

            with patch.object(Path, 'cwd', return_value=Path(tmpdir)):
                from swarm_attack.cli.memory import get_memory_store
                loaded_store = get_memory_store()

                # Should prefer store.json with 5 entries
                assert len(loaded_store) == 5

    def test_get_memory_store_returns_empty_if_no_file(self):
        """get_memory_store should return empty store if no file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, 'cwd', return_value=Path(tmpdir)):
                from swarm_attack.cli.memory import get_memory_store
                loaded_store = get_memory_store()

                # Should return empty store
                assert len(loaded_store) == 0
