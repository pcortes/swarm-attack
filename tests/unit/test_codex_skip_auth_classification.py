"""Tests for CodexCliRunner skip_auth_classification option."""
import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.codex_client import CodexCliRunner, CodexInvocationError
from swarm_attack.errors import CodexAuthError, LLMErrorType


class TestSkipAuthClassification:
    """Test the skip_auth_classification flag behavior."""

    def _make_runner(self, skip_auth: bool = False):
        """Create a CodexCliRunner with mock config."""
        mock_config = MagicMock()
        mock_config.repo_root = "/tmp"
        mock_config.codex = MagicMock()
        mock_config.codex.binary = "codex"
        mock_config.codex.model = None
        mock_config.codex.timeout_seconds = 60

        return CodexCliRunner(
            config=mock_config,
            skip_auth_classification=skip_auth,
        )

    @patch("swarm_attack.codex_client.subprocess.run")
    def test_default_raises_codex_auth_error(self, mock_run):
        """Default behavior: auth pattern raises CodexAuthError."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: not logged in. Please run codex login",
        )

        runner = self._make_runner(skip_auth=False)

        with pytest.raises(CodexAuthError):
            runner.run("test prompt")

    @patch("swarm_attack.codex_client.subprocess.run")
    def test_skip_auth_raises_invocation_error(self, mock_run):
        """With skip_auth=True: auth pattern raises CodexInvocationError instead."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: not logged in. Please run codex login",
        )

        runner = self._make_runner(skip_auth=True)

        # Should raise CodexInvocationError, NOT CodexAuthError
        with pytest.raises(CodexInvocationError) as exc_info:
            runner.run("test prompt")

        # Verify it's NOT a CodexAuthError
        assert not isinstance(exc_info.value, CodexAuthError)

    @patch("swarm_attack.codex_client.subprocess.run")
    def test_skip_auth_does_not_affect_rate_limit(self, mock_run):
        """skip_auth should NOT affect rate limit errors."""
        from swarm_attack.errors import RateLimitError

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: rate limit exceeded. Try again later.",
        )

        runner = self._make_runner(skip_auth=True)

        # Rate limit should still raise RateLimitError
        with pytest.raises(RateLimitError):
            runner.run("test prompt")

    @patch("swarm_attack.codex_client.subprocess.run")
    def test_skip_auth_does_not_affect_success(self, mock_run):
        """skip_auth should not affect successful runs."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"type": "turn.completed", "last_message": "ok"}',
            stderr="",
        )

        runner = self._make_runner(skip_auth=True)
        result = runner.run("test prompt")

        assert result.text == "ok"
