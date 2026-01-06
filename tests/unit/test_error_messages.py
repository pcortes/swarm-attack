"""Tests for error message consistency with configured CLI binary (TDD RED phase).

The codebase has been migrated from Codex to Claude, as shown in config.yaml:
  claude:
    binary: "claude"

However, error messages in codex_client.py still reference "Codex" when they
should reference "Claude" since that's the actual CLI being used.

Bug:
- RateLimitError message says "Codex rate limit reached"
- Auth error message says "Codex authentication required"

Expected:
- RateLimitError message should say "Claude CLI rate limit reached"
- Auth error message should say "Claude CLI authentication required"
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def make_mock_config():
    """Create a mock SwarmConfig that uses Claude binary."""
    from swarm_attack.config import SwarmConfig

    config = MagicMock(spec=SwarmConfig)
    config.repo_root = "/tmp/test-repo"
    config.specs_path = Path("/tmp/test-repo/specs")

    # Config uses Claude, not Codex
    claude_config = MagicMock()
    claude_config.binary = "claude"
    claude_config.timeout_seconds = 300
    config.claude = claude_config

    # Also set codex to None to match real-world config where we use claude
    config.codex = None

    return config


class TestRateLimitErrorMessage:
    """Tests for rate limit error message correctness.

    The error message should reflect that we're using Claude CLI,
    not the legacy Codex CLI.
    """

    def test_rate_limit_error_says_claude(self):
        """RateLimitError from codex_client.py should say 'Claude CLI rate limit reached'.

        Currently FAILS because line 257-258 in codex_client.py says:
            raise RateLimitError(
                "Codex rate limit reached",  # <-- BUG: should say "Claude CLI rate limit reached"
                stderr=stderr,
            )
        """
        from swarm_attack.codex_client import CodexCliRunner
        from swarm_attack.errors import RateLimitError, LLMErrorType

        config = make_mock_config()
        runner = CodexCliRunner(config=config)

        # Simulate stderr that triggers rate limit classification
        stderr = "rate limit exceeded - too many requests"
        stdout = ""
        returncode = 1

        # This should raise RateLimitError with message containing "Claude"
        with pytest.raises(RateLimitError) as exc_info:
            runner._classify_and_raise(
                stderr=stderr,
                stdout=stdout,
                returncode=returncode,
            )

        error = exc_info.value
        error_message = str(error)

        # The error message should reference Claude, not Codex
        assert "Claude" in error_message, (
            f"Error message should say 'Claude' but got: {error_message!r}. "
            f"The config uses claude binary but error references Codex."
        )
        assert "Codex" not in error_message, (
            f"Error message should NOT say 'Codex' but got: {error_message!r}. "
            f"We're using Claude CLI, not Codex CLI."
        )

    def test_rate_limit_error_message_format(self):
        """Rate limit error message should follow the expected format.

        Expected: "Claude CLI rate limit reached"
        """
        from swarm_attack.codex_client import CodexCliRunner
        from swarm_attack.errors import RateLimitError

        config = make_mock_config()
        runner = CodexCliRunner(config=config)

        stderr = "429 too many requests"
        stdout = ""
        returncode = 1

        with pytest.raises(RateLimitError) as exc_info:
            runner._classify_and_raise(
                stderr=stderr,
                stdout=stdout,
                returncode=returncode,
            )

        error = exc_info.value
        error_message = str(error)

        # Check for expected format
        assert "Claude CLI rate limit reached" in error_message, (
            f"Expected message containing 'Claude CLI rate limit reached' "
            f"but got: {error_message!r}"
        )


class TestAuthErrorMessage:
    """Tests for auth error message correctness.

    When running with Claude binary (as per config.yaml), auth errors
    should reference Claude, not Codex.
    """

    def test_auth_error_says_claude(self):
        """Auth errors should reference Claude when using Claude binary.

        Currently FAILS because line 251-253 in codex_client.py says:
            raise CodexAuthError(
                "Codex authentication required",  # <-- BUG: should say "Claude"
                stderr=stderr,
            )
        """
        from swarm_attack.codex_client import CodexCliRunner
        from swarm_attack.errors import CodexAuthError, LLMErrorType

        config = make_mock_config()
        runner = CodexCliRunner(config=config)

        # Simulate stderr that triggers auth error classification
        stderr = "not logged in - please authenticate"
        stdout = ""
        returncode = 1

        # This should raise CodexAuthError with message containing "Claude"
        with pytest.raises(CodexAuthError) as exc_info:
            runner._classify_and_raise(
                stderr=stderr,
                stdout=stdout,
                returncode=returncode,
            )

        error = exc_info.value
        error_message = str(error)

        # The error message should reference Claude, not Codex
        assert "Claude" in error_message, (
            f"Error message should say 'Claude' but got: {error_message!r}. "
            f"The config uses claude binary but error references Codex."
        )
        assert "Codex" not in error_message, (
            f"Error message should NOT say 'Codex' but got: {error_message!r}. "
            f"We're using Claude CLI, not Codex CLI."
        )

    def test_auth_error_message_format(self):
        """Auth error message should follow the expected format.

        Expected: "Claude CLI authentication required"
        """
        from swarm_attack.codex_client import CodexCliRunner
        from swarm_attack.errors import CodexAuthError

        config = make_mock_config()
        runner = CodexCliRunner(config=config)

        stderr = "login required"
        stdout = ""
        returncode = 1

        with pytest.raises(CodexAuthError) as exc_info:
            runner._classify_and_raise(
                stderr=stderr,
                stdout=stdout,
                returncode=returncode,
            )

        error = exc_info.value
        error_message = str(error)

        # Check for expected format
        assert "Claude" in error_message and "authentication" in error_message.lower(), (
            f"Expected message mentioning 'Claude' and 'authentication' "
            f"but got: {error_message!r}"
        )


class TestErrorClassificationWithClaudeConfig:
    """Integration tests verifying error messages in context of Claude config.

    These tests simulate the real scenario where config.yaml specifies:
      claude:
        binary: "claude"

    All error messages should reflect this configuration.
    """

    def test_rate_limit_with_full_runner_invocation(self):
        """Full integration test: subprocess returns rate limit, message says Claude.

        This test mocks subprocess.run to simulate a rate limit error
        and verifies the raised exception message references Claude.
        """
        from swarm_attack.codex_client import CodexCliRunner
        from swarm_attack.errors import RateLimitError
        import subprocess

        config = make_mock_config()
        runner = CodexCliRunner(config=config)

        # Mock subprocess to return a rate limit error
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: rate limit exceeded - please wait before retrying"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RateLimitError) as exc_info:
                runner.run("test prompt")

        error = exc_info.value
        error_message = str(error)

        # Should say Claude, not Codex
        assert "Claude" in error_message, (
            f"Rate limit error should reference Claude but got: {error_message!r}"
        )
        assert "Codex" not in error_message, (
            f"Rate limit error should NOT reference Codex but got: {error_message!r}"
        )

    def test_auth_error_with_full_runner_invocation(self):
        """Full integration test: subprocess returns auth error, message says Claude.

        This test mocks subprocess.run to simulate an auth error
        and verifies the raised exception message references Claude.
        """
        from swarm_attack.codex_client import CodexCliRunner
        from swarm_attack.errors import CodexAuthError
        import subprocess

        config = make_mock_config()
        runner = CodexCliRunner(config=config)

        # Mock subprocess to return an auth error
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: not logged in - run 'claude login' first"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(CodexAuthError) as exc_info:
                runner.run("test prompt")

        error = exc_info.value
        error_message = str(error)

        # Should say Claude, not Codex
        assert "Claude" in error_message, (
            f"Auth error should reference Claude but got: {error_message!r}"
        )
        assert "Codex" not in error_message, (
            f"Auth error should NOT reference Codex but got: {error_message!r}"
        )
