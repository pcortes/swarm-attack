"""Tests for approve alias flags.

BUG-002: Top-Level approve Command Missing --auto/--manual Flags

The backward-compatible `swarm-attack approve` command should have the
same --auto/--manual flags as `swarm-attack feature approve`.
"""

import pytest
from typer.testing import CliRunner
from swarm_attack.cli_legacy import app


runner = CliRunner()


class TestApproveAliasFlags:
    """Tests for approve alias command flags."""

    def test_approve_alias_has_auto_flag(self):
        """The approve alias should accept --auto flag."""
        result = runner.invoke(app, ["approve", "--help"])

        assert result.exit_code == 0
        assert "--auto" in result.output

    def test_approve_alias_has_manual_flag(self):
        """The approve alias should accept --manual flag."""
        result = runner.invoke(app, ["approve", "--help"])

        assert result.exit_code == 0
        assert "--manual" in result.output

    def test_approve_alias_matches_feature_approve(self):
        """approve alias should have the same flags as feature approve."""
        from swarm_attack.cli.feature import app as feature_app

        # Get help for feature approve
        feature_result = runner.invoke(feature_app, ["approve", "--help"])

        # Get help for top-level approve
        alias_result = runner.invoke(app, ["approve", "--help"])

        # Both should have --auto
        assert "--auto" in feature_result.output, "feature approve should have --auto"
        assert "--auto" in alias_result.output, "approve alias should have --auto"

        # Both should have --manual
        assert "--manual" in feature_result.output, "feature approve should have --manual"
        assert "--manual" in alias_result.output, "approve alias should have --manual"


class TestApproveAliasCodeVerification:
    """Verify the actual code changes for the alias."""

    def test_approve_function_has_auto_parameter(self):
        """The approve alias function should have an auto parameter."""
        import inspect
        from swarm_attack.cli_legacy import approve

        sig = inspect.signature(approve)
        param_names = list(sig.parameters.keys())

        assert "auto" in param_names, f"Expected 'auto' in {param_names}"

    def test_approve_function_has_manual_parameter(self):
        """The approve alias function should have a manual parameter."""
        import inspect
        from swarm_attack.cli_legacy import approve

        sig = inspect.signature(approve)
        param_names = list(sig.parameters.keys())

        assert "manual" in param_names, f"Expected 'manual' in {param_names}"
