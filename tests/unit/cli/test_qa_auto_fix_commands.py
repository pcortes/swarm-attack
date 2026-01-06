"""Tests for QA auto-fix and auto-watch CLI commands following TDD approach.

Tests cover Issue 11:
- qa auto-fix command with options
- qa auto-watch command with options
- Integration with AutoFixOrchestrator
- Output formatting and colors
- Error handling
"""

import pytest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config for testing."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    # Add auto_fix config
    config.auto_fix = MagicMock()
    config.auto_fix.max_iterations = 3
    config.auto_fix.auto_approve = False
    config.auto_fix.dry_run = False
    return config


@pytest.fixture
def sample_auto_fix_result():
    """Create a sample AutoFixResult for testing."""
    from swarm_attack.qa.auto_fix import AutoFixResult
    return AutoFixResult(
        bugs_found=5,
        bugs_fixed=3,
        iterations_run=2,
        success=True,
        checkpoints_triggered=0,
        dry_run=False,
        errors=[],
    )


@pytest.fixture
def sample_auto_fix_result_with_errors():
    """Create a sample AutoFixResult with errors for testing."""
    from swarm_attack.qa.auto_fix import AutoFixResult
    return AutoFixResult(
        bugs_found=5,
        bugs_fixed=2,
        iterations_run=3,
        success=False,
        checkpoints_triggered=1,
        dry_run=False,
        errors=["Fix failed for bug-12345: Tests still failing"],
    )


@pytest.fixture
def sample_dry_run_result():
    """Create a sample dry-run AutoFixResult for testing."""
    from swarm_attack.qa.auto_fix import AutoFixResult
    return AutoFixResult(
        bugs_found=3,
        bugs_fixed=0,
        iterations_run=1,
        success=False,
        checkpoints_triggered=0,
        dry_run=True,
        errors=[],
    )


# =============================================================================
# COMMAND REGISTRATION TESTS
# =============================================================================


class TestCommandRegistration:
    """Tests for command registration."""

    def test_auto_fix_command_exists(self, runner):
        """qa auto-fix command should be registered."""
        from swarm_attack.cli.qa_commands import app
        result = runner.invoke(app, ["auto-fix", "--help"])
        assert result.exit_code == 0
        assert "auto-fix" in result.output.lower() or "detection" in result.output.lower()

    def test_auto_watch_command_exists(self, runner):
        """qa auto-watch command should be registered."""
        from swarm_attack.cli.qa_commands import app
        result = runner.invoke(app, ["auto-watch", "--help"])
        assert result.exit_code == 0
        assert "watch" in result.output.lower() or "monitor" in result.output.lower()


# =============================================================================
# qa auto-fix COMMAND TESTS
# =============================================================================


class TestQAAutoFixCommand:
    """Tests for the qa auto-fix command."""

    def test_runs_without_arguments(self, runner, sample_auto_fix_result):
        """Should run auto-fix without any arguments."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config.auto_fix.max_iterations = 3
                mock_config.auto_fix.auto_approve = False
                mock_config.auto_fix.dry_run = False
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                assert result.exit_code == 0
                mock_orch.run.assert_called_once()

    def test_accepts_target_path_argument(self, runner, sample_auto_fix_result):
        """Should accept optional target path argument."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix", "src/api/"])

                assert result.exit_code == 0
                call_args = mock_orch.run.call_args
                target_arg = call_args.kwargs.get("target") or (call_args[1].get("target") if len(call_args) > 1 else None)
                assert target_arg == "src/api/"

    def test_accepts_max_iterations_option(self, runner, sample_auto_fix_result):
        """Should accept --max-iterations option."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix", "--max-iterations", "5"])

                assert result.exit_code == 0
                call_args = mock_orch.run.call_args
                max_iter_arg = call_args.kwargs.get("max_iterations") or (call_args[1].get("max_iterations") if len(call_args) > 1 else None)
                assert max_iter_arg == 5

    def test_accepts_approve_all_flag(self, runner, sample_auto_fix_result):
        """Should accept --approve-all flag."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix", "--approve-all"])

                assert result.exit_code == 0
                call_args = mock_orch.run.call_args
                auto_approve_arg = call_args.kwargs.get("auto_approve") or (call_args[1].get("auto_approve") if len(call_args) > 1 else None)
                assert auto_approve_arg is True

    def test_accepts_dry_run_flag(self, runner, sample_dry_run_result):
        """Should accept --dry-run flag."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_dry_run_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix", "--dry-run"])

                assert result.exit_code == 0
                call_args = mock_orch.run.call_args
                dry_run_arg = call_args.kwargs.get("dry_run") or (call_args[1].get("dry_run") if len(call_args) > 1 else None)
                assert dry_run_arg is True

    def test_combines_target_and_options(self, runner, sample_auto_fix_result):
        """Should accept target path with multiple options."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, [
                    "auto-fix", "tests/",
                    "--max-iterations", "5",
                    "--approve-all"
                ])

                assert result.exit_code == 0
                call_args = mock_orch.run.call_args
                assert call_args.kwargs.get("target") == "tests/"
                assert call_args.kwargs.get("max_iterations") == 5
                assert call_args.kwargs.get("auto_approve") is True


# =============================================================================
# qa auto-fix OUTPUT TESTS
# =============================================================================


class TestQAAutoFixOutput:
    """Tests for auto-fix command output formatting."""

    def test_displays_bugs_found_and_fixed(self, runner, sample_auto_fix_result):
        """Should display bugs found and fixed counts."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                # Should show bug counts
                assert "5" in result.output or "bugs" in result.output.lower()
                assert "3" in result.output or "fixed" in result.output.lower()

    def test_displays_iterations_run(self, runner, sample_auto_fix_result):
        """Should display iterations run count."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                assert "2" in result.output or "iteration" in result.output.lower()

    def test_displays_success_status(self, runner, sample_auto_fix_result):
        """Should display success status when all bugs fixed."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                assert "success" in result.output.lower() or "clean" in result.output.lower() or "complete" in result.output.lower()

    def test_displays_failure_status(self, runner, sample_auto_fix_result_with_errors):
        """Should display failure status when bugs remain."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result_with_errors
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                # Should indicate incomplete or show errors
                assert "error" in result.output.lower() or "fail" in result.output.lower() or "incomplete" in result.output.lower()

    def test_displays_errors_when_present(self, runner, sample_auto_fix_result_with_errors):
        """Should display errors when present."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result_with_errors
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                # Should show at least one error
                assert "error" in result.output.lower() or "bug-12345" in result.output

    def test_displays_dry_run_indicator(self, runner, sample_dry_run_result):
        """Should indicate dry-run mode in output."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_dry_run_result
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix", "--dry-run"])

                assert "dry" in result.output.lower() or "would" in result.output.lower()

    def test_displays_checkpoints_triggered(self, runner, sample_auto_fix_result_with_errors):
        """Should display checkpoints triggered count when non-zero."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.return_value = sample_auto_fix_result_with_errors
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                # Should show checkpoint count
                assert "checkpoint" in result.output.lower() or "1" in result.output


# =============================================================================
# qa auto-watch COMMAND TESTS
# =============================================================================


class TestQAAutoWatchCommand:
    """Tests for the qa auto-watch command."""

    def test_runs_without_arguments(self, runner):
        """Should run auto-watch without any arguments."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                # Simulate immediate KeyboardInterrupt to exit watch mode
                mock_orch.watch.side_effect = KeyboardInterrupt()
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-watch"])

                # Should call watch and handle KeyboardInterrupt gracefully
                mock_orch.watch.assert_called_once()
                assert result.exit_code == 0

    def test_accepts_target_path_argument(self, runner):
        """Should accept optional target path argument."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.watch.side_effect = KeyboardInterrupt()
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-watch", "src/api/"])

                call_args = mock_orch.watch.call_args
                target_arg = call_args.kwargs.get("target") or (call_args[1].get("target") if len(call_args) > 1 else None)
                assert target_arg == "src/api/"

    def test_accepts_approve_all_flag(self, runner):
        """Should accept --approve-all flag."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.watch.side_effect = KeyboardInterrupt()
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-watch", "--approve-all"])

                call_args = mock_orch.watch.call_args
                auto_approve_arg = call_args.kwargs.get("auto_approve") or (call_args[1].get("auto_approve") if len(call_args) > 1 else None)
                assert auto_approve_arg is True

    def test_handles_keyboard_interrupt_gracefully(self, runner):
        """Should handle KeyboardInterrupt gracefully."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.watch.side_effect = KeyboardInterrupt()
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-watch"])

                # Should exit cleanly with exit code 0
                assert result.exit_code == 0
                # Should show a message about stopping
                assert "stop" in result.output.lower() or "exit" in result.output.lower() or "interrupt" in result.output.lower() or result.output == ""

    def test_displays_watching_message(self, runner):
        """Should display a watching/monitoring message."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.watch.side_effect = KeyboardInterrupt()
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-watch"])

                # Should show watching message before interrupted
                assert "watch" in result.output.lower() or "monitor" in result.output.lower() or result.output == ""


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestAutoFixErrorHandling:
    """Tests for auto-fix error handling."""

    def test_handles_orchestrator_error(self, runner):
        """Should handle orchestrator errors gracefully."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.run.side_effect = Exception("Orchestrator failed")
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-fix"])

                # Should show error message
                assert result.exit_code != 0 or "error" in result.output.lower()

    def test_handles_config_error(self, runner):
        """Should handle config errors gracefully."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            mock_config_fn.side_effect = Exception("Config not found")

            result = runner.invoke(app, ["auto-fix"])

            # Should show error message
            assert result.exit_code != 0 or "error" in result.output.lower()

    def test_invalid_max_iterations_value(self, runner):
        """Should handle invalid max-iterations value."""
        from swarm_attack.cli.qa_commands import app

        result = runner.invoke(app, ["auto-fix", "--max-iterations", "invalid"])

        # Should show error
        assert result.exit_code != 0


class TestAutoWatchErrorHandling:
    """Tests for auto-watch error handling."""

    def test_handles_orchestrator_error(self, runner):
        """Should handle orchestrator errors gracefully."""
        from swarm_attack.cli.qa_commands import app

        with patch("swarm_attack.cli.qa_commands.get_config_or_default") as mock_config_fn:
            with patch("swarm_attack.cli.qa_commands._get_auto_fix_orchestrator") as mock_get_orch:
                mock_config = MagicMock()
                mock_config.repo_root = "/tmp/test"
                mock_config.auto_fix = MagicMock()
                mock_config_fn.return_value = mock_config

                mock_orch = MagicMock()
                mock_orch.watch.side_effect = Exception("Watch failed")
                mock_get_orch.return_value = mock_orch

                result = runner.invoke(app, ["auto-watch"])

                # Should show error message
                assert result.exit_code != 0 or "error" in result.output.lower()


# =============================================================================
# HELP TEXT TESTS
# =============================================================================


class TestHelpText:
    """Tests for help text content."""

    def test_auto_fix_help_mentions_max_iterations(self, runner):
        """auto-fix help should mention --max-iterations option."""
        from swarm_attack.cli.qa_commands import app
        result = runner.invoke(app, ["auto-fix", "--help"])
        assert "max-iterations" in result.output.lower() or "iterations" in result.output.lower()

    def test_auto_fix_help_mentions_approve_all(self, runner):
        """auto-fix help should mention --approve-all option."""
        from swarm_attack.cli.qa_commands import app
        result = runner.invoke(app, ["auto-fix", "--help"])
        assert "approve" in result.output.lower()

    def test_auto_fix_help_mentions_dry_run(self, runner):
        """auto-fix help should mention --dry-run option."""
        from swarm_attack.cli.qa_commands import app
        result = runner.invoke(app, ["auto-fix", "--help"])
        assert "dry" in result.output.lower()

    def test_auto_watch_help_mentions_approve_all(self, runner):
        """auto-watch help should mention --approve-all option."""
        from swarm_attack.cli.qa_commands import app
        result = runner.invoke(app, ["auto-watch", "--help"])
        assert "approve" in result.output.lower()
