"""Test --auto and --manual flags for feature approve command."""

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch
from pathlib import Path

from swarm_attack.cli.feature import app


runner = CliRunner()


class TestApproveFlags:
    """Test cases for --auto and --manual flags on approve command."""

    def test_approve_accepts_auto_flag(self):
        """Test that approve command accepts --auto flag without 'No such option' error."""
        # Invoke with --auto flag
        result = runner.invoke(app, ["approve", "test-feature", "--auto"])

        # The flag should be recognized (no 'No such option' error)
        # The command will fail for other reasons (feature doesn't exist) but that's expected
        assert "No such option: --auto" not in result.output

    def test_approve_accepts_manual_flag(self):
        """Test that approve command accepts --manual flag without 'No such option' error."""
        # Invoke with --manual flag
        result = runner.invoke(app, ["approve", "test-feature", "--manual"])

        # The flag should be recognized
        assert "No such option: --manual" not in result.output

    def test_approve_rejects_both_flags_together(self):
        """Test that approve command rejects --auto and --manual together."""
        result = runner.invoke(app, ["approve", "test-feature", "--auto", "--manual"])

        # Should fail with error about mutually exclusive options
        assert result.exit_code != 0
        # Check for error message about mutual exclusivity
        output_lower = result.output.lower()
        assert "cannot" in output_lower or "mutually exclusive" in output_lower or "both" in output_lower

    def test_approve_auto_sets_manual_mode_false(self):
        """Test that --auto flag calls set_manual_mode(feature_id, False)."""
        from swarm_attack.models import FeaturePhase, RunState

        mock_store = MagicMock()
        mock_state = MagicMock(spec=RunState)
        mock_state.feature_id = "test-feature"
        mock_state.phase = FeaturePhase.SPEC_NEEDS_APPROVAL
        mock_store.load.return_value = mock_state

        mock_spec_dir = MagicMock()
        mock_spec_dir.__truediv__ = lambda self, x: Path(f"/tmp/fake/{x}")

        with patch("swarm_attack.state_store.get_store", return_value=mock_store), \
             patch("swarm_attack.cli.common.get_config_or_default") as mock_config, \
             patch("swarm_attack.cli.common.init_swarm_directory"), \
             patch("swarm_attack.cli.common.get_spec_dir", return_value=mock_spec_dir), \
             patch("swarm_attack.utils.fs.file_exists", return_value=True), \
             patch("swarm_attack.utils.fs.read_file", return_value="# Draft spec"), \
             patch("swarm_attack.utils.fs.safe_write"):

            mock_config.return_value = MagicMock()
            mock_config.return_value.repo_root = "/tmp/fake"

            runner.invoke(app, ["approve", "test-feature", "--auto"])

            # Verify set_manual_mode was called with False
            mock_store.set_manual_mode.assert_called_once_with("test-feature", False)

    def test_approve_manual_sets_manual_mode_true(self):
        """Test that --manual flag calls set_manual_mode(feature_id, True)."""
        from swarm_attack.models import FeaturePhase, RunState

        mock_store = MagicMock()
        mock_state = MagicMock(spec=RunState)
        mock_state.feature_id = "test-feature"
        mock_state.phase = FeaturePhase.SPEC_NEEDS_APPROVAL
        mock_store.load.return_value = mock_state

        mock_spec_dir = MagicMock()
        mock_spec_dir.__truediv__ = lambda self, x: Path(f"/tmp/fake/{x}")

        with patch("swarm_attack.state_store.get_store", return_value=mock_store), \
             patch("swarm_attack.cli.common.get_config_or_default") as mock_config, \
             patch("swarm_attack.cli.common.init_swarm_directory"), \
             patch("swarm_attack.cli.common.get_spec_dir", return_value=mock_spec_dir), \
             patch("swarm_attack.utils.fs.file_exists", return_value=True), \
             patch("swarm_attack.utils.fs.read_file", return_value="# Draft spec"), \
             patch("swarm_attack.utils.fs.safe_write"):

            mock_config.return_value = MagicMock()
            mock_config.return_value.repo_root = "/tmp/fake"

            runner.invoke(app, ["approve", "test-feature", "--manual"])

            # Verify set_manual_mode was called with True
            mock_store.set_manual_mode.assert_called_once_with("test-feature", True)
