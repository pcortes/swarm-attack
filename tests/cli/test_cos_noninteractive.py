"""Tests for COS CLI non-interactive mode handling.

BUG-001: COS Standup Crashes in Non-Interactive Mode

These tests verify that chief_of_staff.py uses prompt_or_default and
confirm_or_default from ux.py to handle non-interactive mode gracefully.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestStandupPromptIntegration:
    """Tests for standup prompt using prompt_or_default."""

    def test_prompt_or_default_used_in_standup(self):
        """Verify prompt_or_default is imported and available."""
        from swarm_attack.cli.chief_of_staff import prompt_or_default
        assert callable(prompt_or_default)

    def test_confirm_or_default_used_in_chief_of_staff(self):
        """Verify confirm_or_default is imported and available."""
        from swarm_attack.cli.chief_of_staff import confirm_or_default
        assert callable(confirm_or_default)

    @patch("swarm_attack.cli.ux.is_interactive", return_value=False)
    def test_prompt_or_default_returns_default_in_noninteractive(self, mock_is_interactive):
        """prompt_or_default returns default when not interactive."""
        from swarm_attack.cli.chief_of_staff import prompt_or_default

        result = prompt_or_default("Select goals", "0")
        assert result == "0"

    @patch("swarm_attack.cli.ux.is_interactive", return_value=False)
    def test_confirm_or_default_returns_default_in_noninteractive(self, mock_is_interactive):
        """confirm_or_default returns default when not interactive."""
        from swarm_attack.cli.chief_of_staff import confirm_or_default

        # Default is True for the feedback-clear use case
        result = confirm_or_default("Are you sure?", default=True)
        assert result is True


class TestNonInteractiveBehavior:
    """Tests verifying non-interactive mode doesn't crash."""

    def test_ux_is_interactive_false_when_stdin_not_tty(self):
        """is_interactive should return False when stdin is not a tty."""
        from swarm_attack.cli.ux import is_interactive

        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=True):
                assert is_interactive() is False

    def test_prompt_or_default_does_not_block(self):
        """prompt_or_default should return immediately in non-interactive."""
        from swarm_attack.cli.ux import prompt_or_default

        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            # This should return immediately without blocking
            result = prompt_or_default("Enter value", "default_value")
            assert result == "default_value"

    def test_confirm_or_default_does_not_block(self):
        """confirm_or_default should return immediately in non-interactive."""
        from swarm_attack.cli.ux import confirm_or_default

        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            # This should return immediately without blocking
            result = confirm_or_default("Confirm?", default=True)
            assert result is True


class TestCodeChangesVerification:
    """Verify the actual code changes were applied correctly."""

    def test_chief_of_staff_imports_ux_utilities(self):
        """Verify chief_of_staff imports the required UX utilities."""
        import swarm_attack.cli.chief_of_staff as cos_module

        # Check that the functions are imported
        assert hasattr(cos_module, 'prompt_or_default')
        assert hasattr(cos_module, 'confirm_or_default')

    def test_prompt_or_default_in_module_namespace(self):
        """The prompt_or_default function should be in the module's namespace."""
        from swarm_attack.cli import chief_of_staff

        # Check via inspection that the import exists
        import inspect
        source = inspect.getsource(chief_of_staff)

        # Verify the import statement exists
        assert "from swarm_attack.cli.ux import prompt_or_default, confirm_or_default" in source

        # Verify prompt_or_default is used in standup (not typer.prompt)
        assert 'selection = prompt_or_default("Select goals", "0")' in source
