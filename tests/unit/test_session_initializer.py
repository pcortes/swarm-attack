"""
Tests for Session Initialization Protocol.

TDD RED phase: These tests verify the session initialization, progress logging,
verification tracking, and session finalization components.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestSessionInitializer:
    """Tests for SessionInitializer class."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config with temp directory as repo root."""
        config = Mock()
        config.repo_root = str(tmp_path)
        (tmp_path / ".git").mkdir()
        return config

    @pytest.fixture
    def mock_state_store(self):
        """Create mock state store that returns a proper state."""
        from swarm_attack.models import TaskRef, TaskStage

        mock_task = TaskRef(
            issue_number=1,
            stage=TaskStage.READY,
            title="Test Issue"
        )
        mock_state = Mock()
        mock_state.tasks = [mock_task]

        store = Mock()
        store.load.return_value = mock_state
        return store

    @pytest.fixture
    def progress_logger(self, tmp_path):
        """Create a progress logger with temp .swarm directory."""
        from swarm_attack.progress_logger import ProgressLogger
        return ProgressLogger(tmp_path / ".swarm")

    def test_initialize_runs_all_five_steps(self, mock_config, mock_state_store, progress_logger):
        """Init must run all 5 steps in order."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        with patch.object(initializer, '_run_verification_tests') as mock_verify:
            mock_verify.return_value = Mock(passed=True, test_count=5)
            result = initializer.initialize_session("test-feature", issue_number=1)

        assert result.ready is True
        assert mock_verify.called

    def test_initialize_blocks_on_verification_failure(self, mock_config, mock_state_store, progress_logger):
        """If verification tests fail, session cannot start."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        with patch.object(initializer, '_run_verification_tests') as mock_verify:
            mock_verify.return_value = Mock(passed=False, failures=["test_foo failed"])
            result = initializer.initialize_session("test-feature", issue_number=1)

        assert result.ready is False
        assert "Verification failed" in result.reason

    def test_initialize_works_without_issue_number(self, mock_config, mock_state_store, progress_logger):
        """Session can initialize without specific issue (matches orchestrator signature)."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        with patch.object(initializer, '_run_verification_tests') as mock_verify:
            mock_verify.return_value = Mock(passed=True, test_count=0)
            result = initializer.initialize_session("test-feature")  # No issue_number

        assert result.ready is True

    def test_initialize_fails_if_not_git_repo(self, tmp_path, mock_state_store):
        """Session cannot start if working directory is not a git repo."""
        from swarm_attack.session_initializer import SessionInitializer
        from swarm_attack.progress_logger import ProgressLogger

        # No .git directory
        config = Mock()
        config.repo_root = str(tmp_path)
        progress_logger = ProgressLogger(tmp_path / ".swarm")

        initializer = SessionInitializer(config, mock_state_store, progress_logger)
        result = initializer.initialize_session("test-feature")

        assert result.ready is False
        assert "Working directory invalid" in result.reason

    def test_initialize_logs_session_start(self, mock_config, mock_state_store, tmp_path):
        """Session start is logged to progress.txt."""
        from swarm_attack.session_initializer import SessionInitializer
        from swarm_attack.progress_logger import ProgressLogger

        swarm_dir = tmp_path / ".swarm"
        progress_logger = ProgressLogger(swarm_dir)
        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        with patch.object(initializer, '_run_verification_tests') as mock_verify:
            mock_verify.return_value = Mock(passed=True, test_count=0)
            initializer.initialize_session("test-feature", issue_number=1)

        log_path = swarm_dir / "progress.txt"
        assert log_path.exists()
        content = log_path.read_text()
        assert "SESSION_START" in content
        assert "feature=test-feature" in content
        assert "issue=#1" in content


class TestProgressLogger:
    """Tests for ProgressLogger class."""

    def test_progress_log_is_append_only(self, tmp_path):
        """Progress log must never be truncated, only appended."""
        from swarm_attack.progress_logger import ProgressLogger

        logger = ProgressLogger(tmp_path / ".swarm")

        logger.log_session_start("feature-1", issue_number=1)
        logger.log_checkpoint("RED phase")
        logger.log_session_start("feature-2", issue_number=2)

        log_path = tmp_path / ".swarm" / "progress.txt"
        content = log_path.read_text()

        assert "SESSION_START feature=feature-1" in content
        assert "CHECKPOINT RED phase" in content
        assert "SESSION_START feature=feature-2" in content
        # Verify order preserved
        assert content.index("feature-1") < content.index("feature-2")

    def test_log_creates_directory_if_missing(self, tmp_path):
        """Logger creates .swarm directory if it doesn't exist."""
        from swarm_attack.progress_logger import ProgressLogger

        swarm_dir = tmp_path / ".swarm"
        assert not swarm_dir.exists()

        logger = ProgressLogger(swarm_dir)
        logger.log_session_start("test", issue_number=1)

        assert swarm_dir.exists()
        assert (swarm_dir / "progress.txt").exists()

    def test_log_verification_passed(self, tmp_path):
        """Verification passed is logged with test count."""
        from swarm_attack.progress_logger import ProgressLogger

        logger = ProgressLogger(tmp_path / ".swarm")
        logger.log_verification_passed(42)

        log_path = tmp_path / ".swarm" / "progress.txt"
        content = log_path.read_text()
        assert "VERIFICATION_PASSED 42 tests" in content

    def test_log_session_end(self, tmp_path):
        """Session end is logged with commits."""
        from swarm_attack.progress_logger import ProgressLogger

        logger = ProgressLogger(tmp_path / ".swarm")
        logger.log_session_end("my-feature", 1, "DONE", ["abc123", "def456"])

        log_path = tmp_path / ".swarm" / "progress.txt"
        content = log_path.read_text()
        assert "SESSION_END" in content
        assert "feature=my-feature" in content
        assert "issue=#1" in content
        assert "status=DONE" in content
        assert "abc123" in content


class TestSessionFinalizer:
    """Tests for SessionFinalizer class."""

    @pytest.fixture
    def mock_deps(self, tmp_path):
        """Create mock dependencies for SessionFinalizer."""
        from swarm_attack.progress_logger import ProgressLogger
        from swarm_attack.verification_tracker import VerificationTracker

        config = Mock()
        config.repo_root = str(tmp_path)
        state_store = Mock()
        progress_logger = ProgressLogger(tmp_path / ".swarm")
        verification_tracker = VerificationTracker(tmp_path / ".swarm")
        return config, state_store, progress_logger, verification_tracker

    def test_finalizer_requires_passing_tests(self, mock_deps):
        """Cannot mark complete if tests failing."""
        from swarm_attack.session_finalizer import SessionFinalizer

        config, state_store, progress_logger, verification_tracker = mock_deps
        finalizer = SessionFinalizer(config, state_store, progress_logger, verification_tracker)

        with patch.object(finalizer, '_run_all_feature_tests') as mock_tests:
            mock_tests.return_value = Mock(passed=False, failures=["regression detected"])
            result = finalizer.finalize_session("test-feature", issue_number=1)

        assert result.can_complete is False
        assert "Tests failing" in result.reason

    def test_finalizer_updates_verification_tracker(self, mock_deps):
        """Verification tracker must be updated on completion."""
        from swarm_attack.session_finalizer import SessionFinalizer

        config, state_store, progress_logger, verification_tracker = mock_deps
        finalizer = SessionFinalizer(config, state_store, progress_logger, verification_tracker)

        with patch.object(finalizer, '_run_all_feature_tests') as mock_tests:
            mock_tests.return_value = Mock(passed=True, test_count=10)
            with patch.object(verification_tracker, 'update_issue_status') as mock_update:
                finalizer.finalize_session("test-feature", issue_number=1)

                mock_update.assert_called_once()
                call_args = mock_update.call_args
                assert call_args[1]["status"] == "passing"

    def test_finalizer_logs_session_end(self, mock_deps):
        """Session end is logged when finalization succeeds."""
        from swarm_attack.session_finalizer import SessionFinalizer

        config, state_store, progress_logger, verification_tracker = mock_deps
        finalizer = SessionFinalizer(config, state_store, progress_logger, verification_tracker)

        with patch.object(finalizer, '_run_all_feature_tests') as mock_tests:
            mock_tests.return_value = Mock(passed=True, test_count=10)
            with patch.object(verification_tracker, 'update_issue_status'):
                finalizer.finalize_session("test-feature", issue_number=1, commits=["abc123"])

        log_path = Path(config.repo_root) / ".swarm" / "progress.txt"
        content = log_path.read_text()
        assert "SESSION_END" in content
        assert "abc123" in content

    def test_finalizer_returns_can_complete_true_on_success(self, mock_deps):
        """Finalizer returns can_complete=True when all tests pass."""
        from swarm_attack.session_finalizer import SessionFinalizer

        config, state_store, progress_logger, verification_tracker = mock_deps
        finalizer = SessionFinalizer(config, state_store, progress_logger, verification_tracker)

        with patch.object(finalizer, '_run_all_feature_tests') as mock_tests:
            mock_tests.return_value = Mock(passed=True, test_count=5)
            with patch.object(verification_tracker, 'update_issue_status'):
                result = finalizer.finalize_session("test-feature", issue_number=1)

        assert result.can_complete is True


class TestVerificationTracker:
    """Tests for VerificationTracker class."""

    def test_creates_verification_file(self, tmp_path):
        """Tracker creates verification.json for feature."""
        from swarm_attack.verification_tracker import VerificationTracker

        tracker = VerificationTracker(tmp_path / ".swarm")

        tracker.update_issue_status("my-feature", issue_number=1, status="passing", test_count=5)

        path = tmp_path / ".swarm" / "features" / "my-feature" / "verification.json"
        assert path.exists()

    def test_tracks_multiple_issues(self, tmp_path):
        """Tracker tracks all issues in a feature."""
        from swarm_attack.verification_tracker import VerificationTracker

        tracker = VerificationTracker(tmp_path / ".swarm")

        tracker.update_issue_status("my-feature", issue_number=1, status="passing", test_count=5)
        tracker.update_issue_status("my-feature", issue_number=2, status="failing", test_count=3)

        verification = tracker.load("my-feature")
        assert len(verification.issues) == 2

    def test_updates_existing_issue(self, tmp_path):
        """Tracker updates status of existing issue."""
        from swarm_attack.verification_tracker import VerificationTracker

        tracker = VerificationTracker(tmp_path / ".swarm")

        tracker.update_issue_status("my-feature", issue_number=1, status="failing", test_count=5)
        tracker.update_issue_status("my-feature", issue_number=1, status="passing", test_count=5)

        verification = tracker.load("my-feature")
        assert len(verification.issues) == 1
        assert verification.issues[0].status == "passing"

    def test_load_returns_none_if_not_exists(self, tmp_path):
        """Load returns None if verification file doesn't exist."""
        from swarm_attack.verification_tracker import VerificationTracker

        tracker = VerificationTracker(tmp_path / ".swarm")
        verification = tracker.load("nonexistent-feature")

        assert verification is None

    def test_verification_includes_timestamp(self, tmp_path):
        """Verification records include last_verified timestamp."""
        from swarm_attack.verification_tracker import VerificationTracker

        tracker = VerificationTracker(tmp_path / ".swarm")
        tracker.update_issue_status("my-feature", issue_number=1, status="passing", test_count=5)

        verification = tracker.load("my-feature")
        assert verification.issues[0].last_verified is not None
        assert verification.last_updated is not None
