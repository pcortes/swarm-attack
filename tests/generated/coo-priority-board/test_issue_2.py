"""Tests for COO Codex client."""

import pytest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch


class TestCodexClientImport:
    """Test that the codex_client module can be imported."""

    def test_import_codex_result(self):
        """Test CodexResult can be imported."""
        from src.codex_client import CodexResult
        assert CodexResult is not None

    def test_import_codex_cli_runner(self):
        """Test CodexCliRunner can be imported."""
        from src.codex_client import CodexCliRunner
        assert CodexCliRunner is not None


class TestCodexResult:
    """Test CodexResult dataclass."""

    def test_codex_result_has_required_fields(self):
        """Test CodexResult has all required fields per interface contract."""
        from src.codex_client import CodexResult

        result = CodexResult(
            success=True,
            text="Test response",
            cost_usd=0.01,
            error=None,
        )
        assert result.success is True
        assert result.text == "Test response"
        assert result.cost_usd == 0.01
        assert result.error is None

    def test_codex_result_with_error(self):
        """Test CodexResult with an error."""
        from src.codex_client import CodexResult

        result = CodexResult(
            success=False,
            text="",
            cost_usd=0.0,
            error="Connection failed",
        )
        assert result.success is False
        assert result.text == ""
        assert result.error == "Connection failed"

    def test_codex_result_to_dict(self):
        """Test CodexResult to_dict method."""
        from src.codex_client import CodexResult

        result = CodexResult(
            success=True,
            text="Test",
            cost_usd=0.05,
            error=None,
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["text"] == "Test"
        assert data["cost_usd"] == 0.05
        assert data["error"] is None


class TestCodexCliRunnerInit:
    """Test CodexCliRunner initialization."""

    def test_init_with_config_dict(self):
        """Test initialization with config dictionary."""
        from src.codex_client import CodexCliRunner

        config = {
            "codex": {
                "binary": "codex",
                "timeout_seconds": 120,
            }
        }
        runner = CodexCliRunner(config=config)
        assert runner is not None

    def test_init_with_config_and_logger(self):
        """Test initialization with config and logger."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "codex"}}
        logger = MagicMock()
        runner = CodexCliRunner(config=config, logger=logger)
        assert runner.logger is logger

    def test_init_with_empty_config(self):
        """Test initialization with empty config uses defaults."""
        from src.codex_client import CodexCliRunner

        runner = CodexCliRunner(config={})
        assert runner is not None


class TestCodexCliRunnerRun:
    """Test CodexCliRunner.run method."""

    def test_run_returns_codex_result(self):
        """Test run returns CodexResult."""
        from src.codex_client import CodexCliRunner, CodexResult

        config = {"codex": {"binary": "codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Hello"}',
                stderr="",
            )
            result = runner.run("Test prompt")

        assert isinstance(result, CodexResult)

    def test_run_with_timeout_parameter(self):
        """Test run accepts timeout parameter."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Hello"}',
                stderr="",
            )
            # Should not raise - accepts timeout parameter
            runner.run("Test prompt", timeout=600)

            # Verify timeout was passed to subprocess
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["timeout"] == 600

    def test_run_default_timeout_is_300(self):
        """Test run uses 300 second default timeout."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Hello"}',
                stderr="",
            )
            runner.run("Test prompt")

            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["timeout"] == 300

    def test_run_success_sets_success_true(self):
        """Test successful run sets success=True in result."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Success response"}',
                stderr="",
            )
            result = runner.run("Test prompt")

        assert result.success is True
        assert "Success response" in result.text

    def test_run_failure_sets_success_false(self):
        """Test failed run sets success=False and error message."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Command failed",
            )
            result = runner.run("Test prompt")

        assert result.success is False
        assert result.error is not None
        assert "Command failed" in result.error or "failed" in result.error.lower()

    def test_run_with_logger_logs_events(self):
        """Test run logs events when logger is provided."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "codex"}}
        logger = MagicMock()
        runner = CodexCliRunner(config=config, logger=logger)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Test"}',
                stderr="",
            )
            runner.run("Test prompt")

        # Logger should have been called
        assert logger.log.called or logger.info.called or logger.debug.called


class TestCodexCliRunnerConfigAccess:
    """Test CodexCliRunner config access patterns."""

    def test_gets_binary_from_config(self):
        """Test runner gets binary path from config."""
        from src.codex_client import CodexCliRunner

        config = {"codex": {"binary": "/usr/local/bin/codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Test"}',
                stderr="",
            )
            runner.run("Test prompt")

            # Check that the binary was used in the command
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "/usr/local/bin/codex"

    def test_uses_default_binary_when_not_specified(self):
        """Test runner uses 'codex' when binary not in config."""
        from src.codex_client import CodexCliRunner

        config = {}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"type":"turn.completed","last_message":"Test"}',
                stderr="",
            )
            runner.run("Test prompt")

            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "codex"


class TestCodexCliRunnerTimeout:
    """Test timeout handling."""

    def test_timeout_error_returns_failure_result(self):
        """Test that timeout returns a failure result with error."""
        from src.codex_client import CodexCliRunner
        import subprocess

        config = {"codex": {"binary": "codex"}}
        runner = CodexCliRunner(config=config)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=300)
            result = runner.run("Test prompt")

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()


class TestCodexResultDefaults:
    """Test CodexResult default values."""

    def test_cost_usd_defaults_to_zero(self):
        """Test cost_usd defaults to 0.0 if not provided."""
        from src.codex_client import CodexResult

        # Using positional args - this should still work
        result = CodexResult(success=True, text="Test")
        assert result.cost_usd == 0.0

    def test_error_defaults_to_none(self):
        """Test error defaults to None if not provided."""
        from src.codex_client import CodexResult

        result = CodexResult(success=True, text="Test")
        assert result.error is None