"""Test --auto and --manual flags for bug approve command."""

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from swarm_attack.cli.bug import app


runner = CliRunner()


class TestBugApproveFlags:
    """Test cases for --auto and --manual flags on bug approve command."""

    def test_bug_approve_accepts_auto_flag(self):
        """Test that bug approve command accepts --auto flag without 'No such option' error."""
        # Invoke with --auto flag
        result = runner.invoke(app, ["approve", "test-bug", "--auto"])

        # The flag should be recognized (no 'No such option' error)
        # The command will fail for other reasons (bug doesn't exist) but that's expected
        assert "No such option: --auto" not in result.output

    def test_bug_approve_accepts_manual_flag(self):
        """Test that bug approve command accepts --manual flag without 'No such option' error."""
        # Invoke with --manual flag
        result = runner.invoke(app, ["approve", "test-bug", "--manual"])

        # The flag should be recognized
        assert "No such option: --manual" not in result.output

    def test_bug_approve_rejects_both_flags_together(self):
        """Test that bug approve command rejects --auto and --manual together."""
        result = runner.invoke(app, ["approve", "test-bug", "--auto", "--manual"])

        # Should fail with error about mutually exclusive options
        assert result.exit_code != 0
        # Check for error message about mutual exclusivity
        output_lower = result.output.lower()
        assert "cannot" in output_lower or "mutually exclusive" in output_lower or "both" in output_lower
