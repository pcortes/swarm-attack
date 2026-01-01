"""Tests for AgentDispatcher._call_claude_cli() method.

TDD tests for the synchronous Claude CLI subprocess helper method.
"""

import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock

from swarm_attack.commit_review.dispatcher import AgentDispatcher


class TestCallClaudeCli:
    """Tests for _call_claude_cli() helper method."""

    @pytest.fixture
    def dispatcher(self):
        """Create an AgentDispatcher instance."""
        return AgentDispatcher(max_concurrent=5)

    def test_call_claude_cli_method_exists(self, dispatcher):
        """_call_claude_cli method exists on AgentDispatcher."""
        assert hasattr(dispatcher, "_call_claude_cli")
        assert callable(getattr(dispatcher, "_call_claude_cli"))

    def test_call_claude_cli_returns_dict(self, dispatcher):
        """_call_claude_cli returns a dict on success."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"result": "test"}',
                stderr="",
            )

            result = dispatcher._call_claude_cli("test prompt")

            assert isinstance(result, dict)
            assert result == {"result": "test"}

    def test_call_claude_cli_calls_subprocess_with_correct_args(self, dispatcher):
        """Calls subprocess.run with correct command arguments."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{}',
                stderr="",
            )

            dispatcher._call_claude_cli("my test prompt")

            mock_run.assert_called_once()
            call_args = mock_run.call_args

            # Check the command list
            cmd = call_args[0][0]
            assert cmd[0] == "claude"
            assert "--print" in cmd
            assert "--output-format" in cmd
            assert "json" in cmd
            assert "-p" in cmd
            assert "my test prompt" in cmd

    def test_call_claude_cli_uses_capture_output_true(self, dispatcher):
        """Uses capture_output=True in subprocess call."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{}',
                stderr="",
            )

            dispatcher._call_claude_cli("prompt")

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("capture_output") is True

    def test_call_claude_cli_uses_text_true(self, dispatcher):
        """Uses text=True in subprocess call."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{}',
                stderr="",
            )

            dispatcher._call_claude_cli("prompt")

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("text") is True

    def test_call_claude_cli_uses_timeout_300(self, dispatcher):
        """Uses timeout=300 in subprocess call."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{}',
                stderr="",
            )

            dispatcher._call_claude_cli("prompt")

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs.get("timeout") == 300

    def test_call_claude_cli_raises_runtime_error_on_non_zero_exit(self, dispatcher):
        """Raises RuntimeError on non-zero exit code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Error: something went wrong",
            )

            with pytest.raises(RuntimeError) as exc_info:
                dispatcher._call_claude_cli("prompt")

            # Error message should include stderr
            assert "something went wrong" in str(exc_info.value)

    def test_call_claude_cli_runtime_error_includes_stderr(self, dispatcher):
        """RuntimeError message includes the stderr content."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=2,
                stdout="",
                stderr="Detailed error message from CLI",
            )

            with pytest.raises(RuntimeError) as exc_info:
                dispatcher._call_claude_cli("prompt")

            assert "Detailed error message from CLI" in str(exc_info.value)

    def test_call_claude_cli_parses_json_stdout(self, dispatcher):
        """Parses stdout as JSON and returns dict."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"key": "value", "number": 42}',
                stderr="",
            )

            result = dispatcher._call_claude_cli("prompt")

            assert result == {"key": "value", "number": 42}

    def test_call_claude_cli_propagates_timeout_expired(self, dispatcher):
        """Propagates subprocess.TimeoutExpired to caller."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

            with pytest.raises(subprocess.TimeoutExpired):
                dispatcher._call_claude_cli("prompt")

    def test_call_claude_cli_propagates_json_decode_error(self, dispatcher):
        """Propagates json.JSONDecodeError to caller."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr="",
            )

            with pytest.raises(json.JSONDecodeError):
                dispatcher._call_claude_cli("prompt")

    def test_call_claude_cli_handles_empty_stdout(self, dispatcher):
        """Raises JSONDecodeError on empty stdout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            with pytest.raises(json.JSONDecodeError):
                dispatcher._call_claude_cli("prompt")

    def test_call_claude_cli_handles_complex_json(self, dispatcher):
        """Parses complex nested JSON correctly."""
        complex_json = {
            "result": "text output",
            "findings": [
                {"severity": "HIGH", "description": "Issue 1"},
                {"severity": "LOW", "description": "Issue 2"},
            ],
            "metadata": {
                "turns": 5,
                "cost": 0.05,
            },
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(complex_json),
                stderr="",
            )

            result = dispatcher._call_claude_cli("prompt")

            assert result == complex_json
            assert len(result["findings"]) == 2
            assert result["metadata"]["turns"] == 5

    def test_call_claude_cli_command_order(self, dispatcher):
        """Command arguments are in the correct order."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{}',
                stderr="",
            )

            dispatcher._call_claude_cli("test prompt")

            cmd = mock_run.call_args[0][0]

            # Expected: ["claude", "--print", "--output-format", "json", "-p", prompt]
            assert cmd == ["claude", "--print", "--output-format", "json", "-p", "test prompt"]