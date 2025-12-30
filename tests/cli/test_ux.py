"""Tests for CLI UX utilities."""
import pytest
from click.exceptions import Exit as ClickExit
from unittest.mock import patch
from swarm_attack.cli.ux import (
    is_interactive,
    prompt_or_default,
    confirm_or_default,
    format_error,
    EXIT_USER_ERROR,
    EXIT_SUCCESS,
    EXIT_SYSTEM_ERROR,
    EXIT_BLOCKED,
)


class TestExitCodes:
    """Tests for exit code constants."""

    def test_exit_codes_are_distinct(self):
        """All exit codes are distinct values."""
        codes = [EXIT_SUCCESS, EXIT_USER_ERROR, EXIT_SYSTEM_ERROR, EXIT_BLOCKED]
        assert len(codes) == len(set(codes))

    def test_exit_success_is_zero(self):
        """Success is 0 by convention."""
        assert EXIT_SUCCESS == 0


class TestIsInteractive:
    """Tests for interactive mode detection."""

    def test_returns_false_when_stdin_not_tty(self):
        """Non-tty stdin means non-interactive."""
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=True):
                assert is_interactive() is False

    def test_returns_false_when_stdout_not_tty(self):
        """Non-tty stdout means non-interactive."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=False):
                assert is_interactive() is False

    def test_returns_true_when_both_tty(self):
        """Both tty means interactive."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=True):
                assert is_interactive() is True

    def test_returns_false_when_neither_tty(self):
        """Neither tty means non-interactive."""
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=False):
                assert is_interactive() is False


class TestPromptOrDefault:
    """Tests for prompt_or_default."""

    def test_returns_default_when_non_interactive(self):
        """Use default in non-interactive mode."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            result = prompt_or_default("Enter value", "default_value")
            assert result == "default_value"

    def test_returns_int_default_when_non_interactive(self):
        """Use integer default in non-interactive mode."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            result = prompt_or_default("Enter number", 42)
            assert result == 42

    def test_exits_when_require_interactive(self):
        """Exit with error when interactive required but not available."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            with pytest.raises(ClickExit) as exc_info:
                prompt_or_default("Enter value", "default", require_interactive=True)
            assert exc_info.value.exit_code == EXIT_USER_ERROR


class TestConfirmOrDefault:
    """Tests for confirm_or_default."""

    def test_returns_false_default_when_non_interactive(self):
        """Use False default in non-interactive mode."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            result = confirm_or_default("Confirm?")
            assert result is False

    def test_returns_true_default_when_specified(self):
        """Use True default when specified."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            result = confirm_or_default("Confirm?", default=True)
            assert result is True

    def test_exits_when_require_interactive(self):
        """Exit with error when interactive required but not available."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            with pytest.raises(ClickExit) as exc_info:
                confirm_or_default("Confirm?", require_interactive=True)
            assert exc_info.value.exit_code == EXIT_USER_ERROR


class TestFormatError:
    """Tests for error formatting."""

    def test_basic_error(self):
        """Format basic error with just code and message."""
        result = format_error("TEST_ERROR", "Something went wrong")
        assert "Error: [TEST_ERROR] Something went wrong" in result

    def test_full_error(self):
        """Format error with all fields."""
        result = format_error(
            "INVALID_INPUT",
            "Value is invalid",
            expected="positive number",
            got="-5",
            hint="Use a number greater than 0"
        )
        assert "[INVALID_INPUT]" in result
        assert "Expected: positive number" in result
        assert "Got: -5" in result
        assert "Hint: Use a number greater than 0" in result

    def test_partial_error_with_expected_only(self):
        """Format error with only expected field."""
        result = format_error(
            "MISSING_FIELD",
            "Field is required",
            expected="non-empty string"
        )
        assert "Expected: non-empty string" in result
        assert "Got:" not in result
        assert "Hint:" not in result

    def test_partial_error_with_hint_only(self):
        """Format error with only hint field."""
        result = format_error(
            "NOT_FOUND",
            "File not found",
            hint="Check the file path and try again"
        )
        assert "Hint: Check the file path" in result
        assert "Expected:" not in result
        assert "Got:" not in result

    def test_error_lines_are_properly_indented(self):
        """Additional lines are indented."""
        result = format_error(
            "TEST",
            "Test",
            expected="expected",
            got="got",
            hint="hint"
        )
        lines = result.split("\n")
        assert lines[0].startswith("Error:")
        assert lines[1].startswith("  Expected:")
        assert lines[2].startswith("  Got:")
        assert lines[3].startswith("  Hint:")
