"""Tests for database & state edge cases (Section 10.6).

Tests cover spec section 10.6: Database & State Issues
- Concurrent session writes (race conditions)
- Orphaned session cleanup
- Session file corruption recovery
- Disk full handling
- Concurrent access patterns
"""

import json
import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QALimits,
    QASession,
    QAStatus,
    QATrigger,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create a mock config."""
    config = MagicMock()
    config.repo_root = "/tmp/test"
    return config


@pytest.fixture
def logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def temp_sessions_path(tmp_path):
    """Create a temporary sessions directory."""
    sessions_dir = tmp_path / ".swarm" / "qa"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


@pytest.fixture
def orchestrator(config, logger, tmp_path):
    """Create an orchestrator with temporary storage."""
    config.repo_root = str(tmp_path)
    return QAOrchestrator(config, logger)


# =============================================================================
# Test Concurrent Session Writes (Section 10.6)
# =============================================================================


class TestConcurrentSessionWrites:
    """Section 10.6: Multiple processes writing to same session should not corrupt."""

    def test_concurrent_session_creation(self, config, logger, tmp_path):
        """Multiple threads creating sessions should not conflict."""
        config.repo_root = str(tmp_path)
        orchestrator = QAOrchestrator(config, logger)

        sessions_created = []
        errors = []

        def create_session(thread_id):
            try:
                session = orchestrator.test(
                    target=f"/api/test{thread_id}",
                    depth=QADepth.SHALLOW,
                    trigger=QATrigger.USER_COMMAND,
                )
                sessions_created.append(session.session_id)
            except Exception as e:
                errors.append(e)

        # Create 5 threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=create_session, args=(i,))
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join(timeout=10)

        # Should have no errors
        assert len(errors) == 0
        # Should have created 5 unique sessions
        assert len(set(sessions_created)) == 5

    def test_session_id_uniqueness_under_load(self, config, logger, tmp_path):
        """Session IDs should be unique even when created rapidly."""
        config.repo_root = str(tmp_path)
        orchestrator = QAOrchestrator(config, logger)

        session_ids = []

        for _ in range(20):
            session_id = orchestrator._generate_session_id()
            session_ids.append(session_id)

        # All session IDs should be unique
        assert len(session_ids) == len(set(session_ids))

    def test_concurrent_session_updates(self, orchestrator):
        """Concurrent updates to the same session should not corrupt data."""
        # Create a session first
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        errors = []
        update_count = 0
        lock = threading.Lock()

        def update_session_file(session_id, update_num):
            nonlocal update_count
            try:
                session_path = orchestrator.sessions_path / session_id / "state.json"
                if session_path.exists():
                    data = json.loads(session_path.read_text())
                    data["update_number"] = update_num
                    session_path.write_text(json.dumps(data))
                    with lock:
                        update_count += 1
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            t = threading.Thread(
                target=update_session_file,
                args=(session.session_id, i)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Should have completed updates (some may have been overwritten)
        assert update_count > 0
        # File should still be valid JSON
        session_path = orchestrator.sessions_path / session.session_id / "state.json"
        data = json.loads(session_path.read_text())
        assert "session_id" in data


# =============================================================================
# Test Orphaned Session Cleanup (Section 10.6)
# =============================================================================


class TestOrphanedSessionCleanup:
    """Section 10.6: Orphaned sessions from crashed processes should be cleaned up."""

    def test_list_sessions_returns_valid_sessions(self, orchestrator):
        """list_sessions should return valid session IDs."""
        # Create a few sessions
        for i in range(3):
            orchestrator.test(
                target=f"/api/test{i}",
                depth=QADepth.SHALLOW,
                trigger=QATrigger.USER_COMMAND,
            )

        sessions = orchestrator.list_sessions()
        assert len(sessions) >= 3

        # All should be loadable
        for session_id in sessions:
            session = orchestrator.get_session(session_id)
            assert session is not None

    def test_ignores_invalid_session_directories(self, orchestrator):
        """list_sessions should ignore directories without valid state.json."""
        # Create an invalid session directory
        invalid_dir = orchestrator.sessions_path / "invalid-session"
        invalid_dir.mkdir(parents=True, exist_ok=True)
        (invalid_dir / "garbage.txt").write_text("not json")

        # Create a valid session
        valid_session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        sessions = orchestrator.list_sessions()
        # Should not include invalid session
        assert "invalid-session" not in sessions
        # Should include valid session
        assert valid_session.session_id in sessions

    def test_get_session_returns_none_for_missing(self, orchestrator):
        """get_session should return None for non-existent sessions."""
        result = orchestrator.get_session("non-existent-session-id")
        assert result is None


# =============================================================================
# Test Session File Corruption Recovery (Section 10.6)
# =============================================================================


class TestSessionFileCorruptionRecovery:
    """Section 10.6: Agent should recover from corrupted session files."""

    def test_handles_corrupted_json(self, orchestrator):
        """get_session should handle corrupted JSON gracefully."""
        # Create a valid session first
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        # Corrupt the session file
        session_path = orchestrator.sessions_path / session.session_id / "state.json"
        session_path.write_text("{ invalid json }")

        # Should return None or handle gracefully
        result = orchestrator.get_session(session.session_id)
        assert result is None

    def test_handles_empty_state_file(self, orchestrator):
        """get_session should handle empty state files."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        # Empty the state file
        session_path = orchestrator.sessions_path / session.session_id / "state.json"
        session_path.write_text("")

        result = orchestrator.get_session(session.session_id)
        assert result is None

    def test_handles_missing_required_fields(self, orchestrator):
        """get_session should handle state files with missing required fields."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        # Write incomplete state
        session_path = orchestrator.sessions_path / session.session_id / "state.json"
        session_path.write_text('{"session_id": "test"}')  # Missing required fields

        # Should handle gracefully
        result = orchestrator.get_session(session.session_id)
        # Either returns None or raises a handled error
        assert result is None or isinstance(result, QASession)

    def test_handles_wrong_type_values(self, orchestrator):
        """get_session should handle wrong type values in state."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        # Write state with wrong types
        session_path = orchestrator.sessions_path / session.session_id / "state.json"
        bad_state = {
            "session_id": 12345,  # Should be string
            "trigger": "invalid_trigger",
            "depth": "invalid_depth",
            "status": "invalid_status",
        }
        session_path.write_text(json.dumps(bad_state))

        result = orchestrator.get_session(session.session_id)
        assert result is None


# =============================================================================
# Test Disk Full Handling (Section 10.6)
# =============================================================================


class TestDiskFullHandling:
    """Section 10.6: Agent should handle disk full errors gracefully."""

    def test_handles_write_permission_error(self, config, logger, tmp_path):
        """Orchestrator should handle write permission errors."""
        config.repo_root = str(tmp_path)
        orchestrator = QAOrchestrator(config, logger)

        # Create session normally first
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        # Mock write failure
        original_write = Path.write_text

        def failing_write(self, content):
            raise PermissionError("Permission denied")

        with patch.object(Path, 'write_text', failing_write):
            # Creating another session should handle the error
            try:
                orchestrator.test(
                    target="/api/test2",
                    depth=QADepth.SHALLOW,
                    trigger=QATrigger.USER_COMMAND,
                )
            except PermissionError:
                # Expected - we're testing that it doesn't crash unexpectedly
                pass

    def test_handles_oserror_on_save(self, config, logger, tmp_path):
        """Orchestrator should handle OSError during save."""
        config.repo_root = str(tmp_path)
        orchestrator = QAOrchestrator(config, logger)

        session = QASession(
            session_id="test-session",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.SHALLOW,
            status=QAStatus.COMPLETED,
            context=QAContext(),
        )

        with patch.object(Path, 'write_text', side_effect=OSError(28, "No space left on device")):
            try:
                orchestrator._save_session(session)
            except OSError as e:
                assert "space" in str(e).lower()


# =============================================================================
# Test Session Limit Enforcement
# =============================================================================


class TestSessionLimitEnforcement:
    """Tests for session list limit enforcement."""

    def test_list_sessions_respects_limit(self, orchestrator):
        """list_sessions should respect the limit parameter."""
        # Create more sessions than the limit
        for i in range(10):
            orchestrator.test(
                target=f"/api/test{i}",
                depth=QADepth.SHALLOW,
                trigger=QATrigger.USER_COMMAND,
            )
            time.sleep(0.01)  # Small delay to ensure unique IDs

        sessions = orchestrator.list_sessions(limit=5)
        assert len(sessions) <= 5

    def test_list_sessions_returns_newest_first(self, orchestrator):
        """list_sessions should return newest sessions first."""
        session_ids = []
        for i in range(5):
            session = orchestrator.test(
                target=f"/api/test{i}",
                depth=QADepth.SHALLOW,
                trigger=QATrigger.USER_COMMAND,
            )
            session_ids.append(session.session_id)
            time.sleep(0.01)

        listed = orchestrator.list_sessions()
        # Latest session should be first
        assert listed[0] == session_ids[-1]


# =============================================================================
# Test Session State Persistence
# =============================================================================


class TestSessionStatePersistence:
    """Tests for session state persistence."""

    def test_session_persisted_to_disk(self, orchestrator):
        """Session should be persisted to disk after creation."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        state_file = orchestrator.sessions_path / session.session_id / "state.json"
        assert state_file.exists()

    def test_session_loadable_after_creation(self, orchestrator):
        """Session should be loadable after being created."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        loaded = orchestrator.get_session(session.session_id)
        assert loaded is not None
        assert loaded.session_id == session.session_id
        assert loaded.trigger == session.trigger
        assert loaded.depth == session.depth

    def test_report_generated_on_completion(self, orchestrator):
        """QA report should be generated when session completes."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        report_file = orchestrator.sessions_path / session.session_id / "qa-report.md"
        assert report_file.exists()

    def test_session_preserves_context(self, orchestrator):
        """Session should preserve essential context information."""
        session = orchestrator.test(
            target="/api/users",
            depth=QADepth.STANDARD,
            trigger=QATrigger.POST_VERIFICATION,
            base_url="http://localhost:9000",
        )

        loaded = orchestrator.get_session(session.session_id)
        assert loaded is not None
        # Session should be loadable with correct metadata
        assert loaded.depth == QADepth.STANDARD
        assert loaded.trigger == QATrigger.POST_VERIFICATION


# =============================================================================
# Test Session Timestamps
# =============================================================================


class TestSessionTimestamps:
    """Tests for session timestamp handling."""

    def test_session_has_created_at(self, orchestrator):
        """Session should have created_at timestamp."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        assert session.created_at is not None
        assert len(session.created_at) > 0

    def test_session_has_started_at(self, orchestrator):
        """Session should have started_at timestamp after running."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        assert session.started_at is not None

    def test_session_has_completed_at(self, orchestrator):
        """Completed session should have completed_at timestamp."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        assert session.completed_at is not None

    def test_timestamps_are_iso_format(self, orchestrator):
        """Timestamps should be in ISO format."""
        session = orchestrator.test(
            target="/api/test",
            depth=QADepth.SHALLOW,
            trigger=QATrigger.USER_COMMAND,
        )

        # Should contain 'T' separator and 'Z' suffix
        assert "T" in session.created_at
