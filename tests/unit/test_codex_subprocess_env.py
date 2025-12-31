"""Tests for CodexCliRunner subprocess environment handling."""
import os
from unittest.mock import MagicMock, patch

import pytest


class TestCodexSubprocessEnvironment:
    """Test that CodexCliRunner passes environment to subprocess."""

    @patch("swarm_attack.codex_client.subprocess.run")
    def test_subprocess_receives_environment(self, mock_run):
        """Verify subprocess.run is called with env=os.environ.copy()."""
        from swarm_attack.codex_client import CodexCliRunner

        # Setup mock
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"type": "turn.completed", "last_message": "ok"}',
            stderr="",
        )

        # Create runner with minimal config
        mock_config = MagicMock()
        mock_config.repo_root = "/tmp"
        mock_config.codex = MagicMock()
        mock_config.codex.binary = "codex"
        mock_config.codex.model = None
        mock_config.codex.timeout_seconds = 60

        runner = CodexCliRunner(config=mock_config)

        # Run
        runner.run("test prompt")

        # Verify env was passed
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert "env" in call_kwargs, "subprocess.run must be called with env parameter"
        assert call_kwargs["env"] is not None, "env must not be None"
        # Verify it's a copy of os.environ (contains at least PATH)
        assert "PATH" in call_kwargs["env"], "env should contain PATH from os.environ"
