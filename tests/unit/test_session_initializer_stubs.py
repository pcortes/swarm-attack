"""
Tests for SessionInitializer stub method implementations.

These tests verify that:
- _review_git_history() extracts recent commits for context
- _review_progress_log() loads prior session summaries
- Both methods remain informational (don't block initialization)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import subprocess


class TestReviewGitHistory:
    """Tests for _review_git_history() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config with temp directory as repo root."""
        config = Mock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        (tmp_path / ".git").mkdir()
        return config

    @pytest.fixture
    def mock_state_store(self):
        """Create mock state store."""
        return Mock()

    @pytest.fixture
    def progress_logger(self, tmp_path):
        """Create a progress logger with temp .swarm directory."""
        from swarm_attack.progress_logger import ProgressLogger
        return ProgressLogger(tmp_path / ".swarm")

    @pytest.fixture
    def initializer(self, mock_config, mock_state_store, progress_logger):
        """Create a SessionInitializer instance."""
        from swarm_attack.session_initializer import SessionInitializer
        return SessionInitializer(mock_config, mock_state_store, progress_logger)

    def test_review_git_history_returns_list_of_commits(self, initializer):
        """_review_git_history should return a list of commit strings."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="abc1234 First commit\ndef5678 Second commit\n"
            )
            result = initializer._review_git_history("test-feature")

        assert isinstance(result, list)
        assert len(result) == 2
        assert "abc1234 First commit" in result
        assert "def5678 Second commit" in result

    def test_review_git_history_returns_up_to_10_commits(self, initializer):
        """_review_git_history should request last 10 commits."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="")
            initializer._review_git_history("test-feature")

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "-10" in call_args[0][0] or "-10" in call_args.kwargs.get("args", [])

    def test_review_git_history_returns_empty_list_on_error(self, initializer):
        """_review_git_history should return empty list on subprocess error."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.SubprocessError("Git failed")
            result = initializer._review_git_history("test-feature")

        assert result == []

    def test_review_git_history_returns_empty_list_on_timeout(self, initializer):
        """_review_git_history should return empty list on timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("git", 5)
            result = initializer._review_git_history("test-feature")

        assert result == []

    def test_review_git_history_returns_empty_list_on_non_zero_exit(self, initializer):
        """_review_git_history should return empty list on non-zero exit code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")
            result = initializer._review_git_history("test-feature")

        assert result == []

    def test_review_git_history_does_not_block_initialization(
        self, mock_config, mock_state_store, progress_logger
    ):
        """_review_git_history errors should not block session initialization."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        with patch("subprocess.run") as mock_git:
            mock_git.side_effect = Exception("Git completely broken")

            with patch.object(initializer, "_run_verification_tests") as mock_verify:
                mock_verify.return_value = Mock(passed=True, test_count=0)
                result = initializer.initialize_session("test-feature")

        # Session should still initialize successfully
        assert result.ready is True


class TestReviewProgressLog:
    """Tests for _review_progress_log() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config with temp directory as repo root."""
        config = Mock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        (tmp_path / ".git").mkdir()
        return config

    @pytest.fixture
    def mock_state_store(self):
        """Create mock state store."""
        return Mock()

    @pytest.fixture
    def progress_logger(self, tmp_path):
        """Create a progress logger with temp .swarm directory."""
        from swarm_attack.progress_logger import ProgressLogger
        return ProgressLogger(tmp_path / ".swarm")

    @pytest.fixture
    def initializer(self, mock_config, mock_state_store, progress_logger):
        """Create a SessionInitializer instance."""
        from swarm_attack.session_initializer import SessionInitializer
        return SessionInitializer(mock_config, mock_state_store, progress_logger)

    def test_review_progress_log_returns_string(self, initializer, tmp_path):
        """_review_progress_log should return progress.txt content as string."""
        # Create a progress.txt file
        swarm_dir = tmp_path / ".swarm" / "features" / "test-feature"
        swarm_dir.mkdir(parents=True, exist_ok=True)
        progress_file = swarm_dir / "progress.txt"
        progress_file.write_text("SESSION_START feature=test-feature\nCHECKPOINT Done")

        result = initializer._review_progress_log("test-feature")

        assert isinstance(result, str)
        assert "SESSION_START" in result
        assert "CHECKPOINT" in result

    def test_review_progress_log_returns_empty_string_when_file_missing(self, initializer):
        """_review_progress_log should return empty string if no progress.txt."""
        result = initializer._review_progress_log("nonexistent-feature")

        assert result == ""

    def test_review_progress_log_returns_empty_string_on_error(
        self, initializer, mock_config, tmp_path
    ):
        """_review_progress_log should return empty string on read error."""
        # Create a directory instead of a file to cause read error
        swarm_dir = tmp_path / ".swarm" / "features" / "test-feature"
        swarm_dir.mkdir(parents=True, exist_ok=True)
        # Create progress.txt as a directory (will cause read error)
        progress_path = swarm_dir / "progress.txt"
        progress_path.mkdir()

        result = initializer._review_progress_log("test-feature")

        assert result == ""

    def test_review_progress_log_does_not_block_initialization(
        self, mock_config, mock_state_store, progress_logger, tmp_path
    ):
        """_review_progress_log errors should not block session initialization."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        # Create a broken progress file (directory instead of file)
        swarm_dir = tmp_path / ".swarm" / "features" / "test-feature"
        swarm_dir.mkdir(parents=True, exist_ok=True)
        progress_path = swarm_dir / "progress.txt"
        progress_path.mkdir()

        with patch.object(initializer, "_run_verification_tests") as mock_verify:
            mock_verify.return_value = Mock(passed=True, test_count=0)
            result = initializer.initialize_session("test-feature")

        # Session should still initialize successfully
        assert result.ready is True

    def test_review_progress_log_uses_feature_specific_path(self, initializer, tmp_path):
        """_review_progress_log should load from features/{feature_id}/progress.txt."""
        # Create progress files for different features
        for feature in ["feature-a", "feature-b"]:
            swarm_dir = tmp_path / ".swarm" / "features" / feature
            swarm_dir.mkdir(parents=True, exist_ok=True)
            progress_file = swarm_dir / "progress.txt"
            progress_file.write_text(f"CONTENT FOR {feature}")

        result_a = initializer._review_progress_log("feature-a")
        result_b = initializer._review_progress_log("feature-b")

        assert "feature-a" in result_a
        assert "feature-b" in result_b
        assert "feature-b" not in result_a
        assert "feature-a" not in result_b


class TestBothMethodsIntegration:
    """Integration tests for both stub methods."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock config with temp directory as repo root."""
        config = Mock()
        config.repo_root = str(tmp_path)
        config.swarm_path = tmp_path / ".swarm"
        (tmp_path / ".git").mkdir()
        return config

    @pytest.fixture
    def mock_state_store(self):
        """Create mock state store."""
        return Mock()

    @pytest.fixture
    def progress_logger(self, tmp_path):
        """Create a progress logger with temp .swarm directory."""
        from swarm_attack.progress_logger import ProgressLogger
        return ProgressLogger(tmp_path / ".swarm")

    def test_both_methods_are_called_during_initialization(
        self, mock_config, mock_state_store, progress_logger
    ):
        """Both _review_git_history and _review_progress_log are called during init."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        with patch.object(initializer, "_review_git_history") as mock_git:
            with patch.object(initializer, "_review_progress_log") as mock_progress:
                mock_git.return_value = []
                mock_progress.return_value = ""

                with patch.object(initializer, "_run_verification_tests") as mock_verify:
                    mock_verify.return_value = Mock(passed=True, test_count=0)
                    initializer.initialize_session("test-feature")

        mock_git.assert_called_once_with("test-feature")
        mock_progress.assert_called_once_with("test-feature")

    def test_methods_provide_informational_context_only(
        self, mock_config, mock_state_store, progress_logger
    ):
        """Both methods provide context but don't affect initialization success."""
        from swarm_attack.session_initializer import SessionInitializer

        initializer = SessionInitializer(mock_config, mock_state_store, progress_logger)

        # Simulate both methods returning useful context
        with patch.object(initializer, "_review_git_history") as mock_git:
            with patch.object(initializer, "_review_progress_log") as mock_progress:
                mock_git.return_value = ["abc123 Some commit", "def456 Another"]
                mock_progress.return_value = "SESSION_START feature=test"

                with patch.object(initializer, "_run_verification_tests") as mock_verify:
                    mock_verify.return_value = Mock(passed=True, test_count=0)
                    result = initializer.initialize_session("test-feature")

        # Initialization should succeed regardless of method return values
        assert result.ready is True

        # Now simulate both methods failing/returning empty
        with patch.object(initializer, "_review_git_history") as mock_git:
            with patch.object(initializer, "_review_progress_log") as mock_progress:
                mock_git.return_value = []
                mock_progress.return_value = ""

                with patch.object(initializer, "_run_verification_tests") as mock_verify:
                    mock_verify.return_value = Mock(passed=True, test_count=0)
                    result = initializer.initialize_session("test-feature")

        # Initialization should still succeed
        assert result.ready is True
