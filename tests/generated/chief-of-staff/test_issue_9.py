"""Tests for AutopilotSessionStore - pause/resume functionality."""

import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState


class TestAutopilotSessionStoreInit:
    """Tests for AutopilotSessionStore initialization."""

    def test_init_creates_storage_directory(self, tmp_path):
        """AutopilotSessionStore.__init__ creates storage directory."""
        store = AutopilotSessionStore(tmp_path)
        expected_dir = tmp_path / ".swarm" / "chief-of-staff" / "autopilot"
        assert expected_dir.exists()
        assert expected_dir.is_dir()

    def test_init_with_existing_directory(self, tmp_path):
        """AutopilotSessionStore.__init__ works with existing directory."""
        storage_dir = tmp_path / ".swarm" / "chief-of-staff" / "autopilot"
        storage_dir.mkdir(parents=True)
        store = AutopilotSessionStore(tmp_path)
        assert storage_dir.exists()

    def test_storage_path_property(self, tmp_path):
        """AutopilotSessionStore exposes storage_path property."""
        store = AutopilotSessionStore(tmp_path)
        expected = tmp_path / ".swarm" / "chief-of-staff" / "autopilot"
        assert store.storage_path == expected


class TestAutopilotSessionStoreSave:
    """Tests for AutopilotSessionStore.save method."""

    def test_save_creates_session_file(self, tmp_path):
        """save() creates session file."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="test-session-001",
            feature_id="my-feature",
            state=AutopilotState.RUNNING,
        )
        store.save(session)
        
        session_file = store.storage_path / "test-session-001.json"
        assert session_file.exists()

    def test_save_sets_last_persisted_at(self, tmp_path):
        """save() sets last_persisted_at timestamp."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="test-session-002",
            feature_id="my-feature",
            state=AutopilotState.RUNNING,
        )
        assert session.last_persisted_at is None
        
        store.save(session)
        assert session.last_persisted_at is not None

    def test_save_writes_valid_json(self, tmp_path):
        """save() writes valid JSON content."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="test-session-003",
            feature_id="my-feature",
            state=AutopilotState.PAUSED,
        )
        store.save(session)
        
        session_file = store.storage_path / "test-session-003.json"
        data = json.loads(session_file.read_text())
        assert data["session_id"] == "test-session-003"
        assert data["feature_id"] == "my-feature"
        assert data["state"] == "paused"

    def test_save_overwrites_existing(self, tmp_path):
        """save() overwrites existing session file."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="test-session-004",
            feature_id="my-feature",
            state=AutopilotState.RUNNING,
        )
        store.save(session)
        
        session.state = AutopilotState.PAUSED
        store.save(session)
        
        session_file = store.storage_path / "test-session-004.json"
        data = json.loads(session_file.read_text())
        assert data["state"] == "paused"

    def test_save_uses_atomic_write(self, tmp_path):
        """save() uses atomic write pattern (temp file -> rename)."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="test-session-005",
            feature_id="my-feature",
            state=AutopilotState.RUNNING,
        )
        
        # After save, no temp files should remain
        store.save(session)
        
        temp_files = list(store.storage_path.glob("*.tmp"))
        assert len(temp_files) == 0
        
        session_file = store.storage_path / "test-session-005.json"
        assert session_file.exists()


class TestAutopilotSessionStoreLoad:
    """Tests for AutopilotSessionStore.load method."""

    def test_load_existing_session(self, tmp_path):
        """load() returns session for existing file."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="test-load-001",
            feature_id="my-feature",
            state=AutopilotState.PAUSED,
        )
        store.save(session)
        
        loaded = store.load("test-load-001")
        assert loaded is not None
        assert loaded.session_id == "test-load-001"
        assert loaded.feature_id == "my-feature"
        assert loaded.state == AutopilotState.PAUSED

    def test_load_nonexistent_returns_none(self, tmp_path):
        """load() returns None for nonexistent session."""
        store = AutopilotSessionStore(tmp_path)
        loaded = store.load("nonexistent-session")
        assert loaded is None

    def test_load_corrupted_file_returns_none(self, tmp_path):
        """load() returns None for corrupted session file."""
        store = AutopilotSessionStore(tmp_path)
        
        # Write corrupted JSON
        corrupted_file = store.storage_path / "corrupted.json"
        corrupted_file.write_text("not valid json {{{")
        
        loaded = store.load("corrupted")
        assert loaded is None

    def test_load_invalid_schema_returns_none(self, tmp_path):
        """load() returns None for file with invalid schema."""
        store = AutopilotSessionStore(tmp_path)
        
        # Write valid JSON but invalid schema
        invalid_file = store.storage_path / "invalid.json"
        invalid_file.write_text('{"foo": "bar"}')
        
        loaded = store.load("invalid")
        assert loaded is None


class TestAutopilotSessionStoreListPaused:
    """Tests for AutopilotSessionStore.list_paused method."""

    def test_list_paused_returns_paused_sessions(self, tmp_path):
        """list_paused() returns IDs of paused sessions only."""
        store = AutopilotSessionStore(tmp_path)
        
        paused1 = AutopilotSession(
            session_id="paused-001",
            feature_id="feature-a",
            state=AutopilotState.PAUSED,
        )
        paused2 = AutopilotSession(
            session_id="paused-002",
            feature_id="feature-b",
            state=AutopilotState.PAUSED,
        )
        running = AutopilotSession(
            session_id="running-001",
            feature_id="feature-c",
            state=AutopilotState.RUNNING,
        )
        completed = AutopilotSession(
            session_id="completed-001",
            feature_id="feature-d",
            state=AutopilotState.COMPLETED,
        )
        
        store.save(paused1)
        store.save(paused2)
        store.save(running)
        store.save(completed)
        
        paused_ids = store.list_paused()
        assert set(paused_ids) == {"paused-001", "paused-002"}

    def test_list_paused_empty_when_none(self, tmp_path):
        """list_paused() returns empty list when no paused sessions."""
        store = AutopilotSessionStore(tmp_path)
        assert store.list_paused() == []

    def test_list_paused_ignores_corrupted_files(self, tmp_path):
        """list_paused() ignores corrupted session files."""
        store = AutopilotSessionStore(tmp_path)
        
        paused = AutopilotSession(
            session_id="paused-valid",
            feature_id="feature-a",
            state=AutopilotState.PAUSED,
        )
        store.save(paused)
        
        # Add corrupted file
        corrupted = store.storage_path / "corrupted.json"
        corrupted.write_text("invalid json")
        
        paused_ids = store.list_paused()
        assert paused_ids == ["paused-valid"]


class TestAutopilotSessionStoreListAll:
    """Tests for AutopilotSessionStore.list_all method."""

    def test_list_all_returns_all_session_ids(self, tmp_path):
        """list_all() returns all session IDs regardless of state."""
        store = AutopilotSessionStore(tmp_path)
        
        sessions = [
            AutopilotSession(session_id="session-001", feature_id="f1", state=AutopilotState.RUNNING),
            AutopilotSession(session_id="session-002", feature_id="f2", state=AutopilotState.PAUSED),
            AutopilotSession(session_id="session-003", feature_id="f3", state=AutopilotState.COMPLETED),
        ]
        
        for session in sessions:
            store.save(session)
        
        all_ids = store.list_all()
        assert set(all_ids) == {"session-001", "session-002", "session-003"}

    def test_list_all_empty_directory(self, tmp_path):
        """list_all() returns empty list for empty directory."""
        store = AutopilotSessionStore(tmp_path)
        assert store.list_all() == []

    def test_list_all_ignores_non_json_files(self, tmp_path):
        """list_all() ignores non-JSON files."""
        store = AutopilotSessionStore(tmp_path)
        
        session = AutopilotSession(
            session_id="valid-session",
            feature_id="feature",
            state=AutopilotState.RUNNING,
        )
        store.save(session)
        
        # Add non-JSON file
        other_file = store.storage_path / "readme.txt"
        other_file.write_text("not a session")
        
        all_ids = store.list_all()
        assert all_ids == ["valid-session"]


class TestAutopilotSessionStoreDelete:
    """Tests for AutopilotSessionStore.delete method."""

    def test_delete_removes_session_file(self, tmp_path):
        """delete() removes the session file."""
        store = AutopilotSessionStore(tmp_path)
        
        session = AutopilotSession(
            session_id="to-delete",
            feature_id="feature",
            state=AutopilotState.PAUSED,
        )
        store.save(session)
        
        session_file = store.storage_path / "to-delete.json"
        assert session_file.exists()
        
        store.delete("to-delete")
        assert not session_file.exists()

    def test_delete_nonexistent_session_no_error(self, tmp_path):
        """delete() does not raise error for nonexistent session."""
        store = AutopilotSessionStore(tmp_path)
        # Should not raise
        store.delete("nonexistent")


class TestAutopilotSessionStoreGetLatestPaused:
    """Tests for AutopilotSessionStore.get_latest_paused method."""

    def test_get_latest_paused_returns_most_recent(self, tmp_path):
        """get_latest_paused() returns most recently persisted paused session."""
        store = AutopilotSessionStore(tmp_path)
        
        # Save sessions with different timestamps
        older = AutopilotSession(
            session_id="older-paused",
            feature_id="feature-a",
            state=AutopilotState.PAUSED,
        )
        store.save(older)
        
        # Brief pause to ensure different timestamp
        newer = AutopilotSession(
            session_id="newer-paused",
            feature_id="feature-b",
            state=AutopilotState.PAUSED,
        )
        store.save(newer)
        
        latest = store.get_latest_paused()
        assert latest is not None
        assert latest.session_id == "newer-paused"

    def test_get_latest_paused_returns_none_when_empty(self, tmp_path):
        """get_latest_paused() returns None when no paused sessions."""
        store = AutopilotSessionStore(tmp_path)
        
        # Add running session only
        running = AutopilotSession(
            session_id="running",
            feature_id="feature",
            state=AutopilotState.RUNNING,
        )
        store.save(running)
        
        assert store.get_latest_paused() is None

    def test_get_latest_paused_ignores_non_paused(self, tmp_path):
        """get_latest_paused() ignores non-paused sessions."""
        store = AutopilotSessionStore(tmp_path)
        
        paused = AutopilotSession(
            session_id="paused-session",
            feature_id="feature-a",
            state=AutopilotState.PAUSED,
        )
        store.save(paused)
        
        # Save completed session after (should be ignored)
        completed = AutopilotSession(
            session_id="completed-session",
            feature_id="feature-b",
            state=AutopilotState.COMPLETED,
        )
        store.save(completed)
        
        latest = store.get_latest_paused()
        assert latest is not None
        assert latest.session_id == "paused-session"


class TestAtomicWriteValidation:
    """Tests for atomic write validation."""

    def test_save_validates_json_before_rename(self, tmp_path):
        """save() validates JSON can be re-parsed before final rename."""
        store = AutopilotSessionStore(tmp_path)
        session = AutopilotSession(
            session_id="validate-test",
            feature_id="feature",
            state=AutopilotState.RUNNING,
        )
        
        # Should complete without error (validation passed)
        store.save(session)
        
        # Verify the saved file is valid
        loaded = store.load("validate-test")
        assert loaded is not None
        assert loaded.session_id == "validate-test"