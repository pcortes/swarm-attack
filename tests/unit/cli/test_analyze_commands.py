"""Tests for analyze CLI commands.

Tests cover the `swarm-attack analyze` sub-app:
- analyze all: Run all detectors
- analyze all --create-bugs: Also create BugState entries
- analyze tests: Run pytest only
- analyze types: Run mypy only
- analyze lint: Run ruff only
- analyze lint --fix: Run ruff --fix
"""

import pytest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from swarm_attack.static_analysis.models import StaticAnalysisResult, StaticBugReport


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_bug_critical():
    """Create a sample critical bug."""
    return StaticBugReport(
        source="pytest",
        file_path="tests/test_foo.py",
        line_number=42,
        error_code="TypeError",
        message="TypeError: 'NoneType' object is not callable",
        severity="critical",
    )


@pytest.fixture
def sample_bug_moderate():
    """Create a sample moderate bug."""
    return StaticBugReport(
        source="mypy",
        file_path="src/module.py",
        line_number=100,
        error_code="arg-type",
        message="Argument 1 has incompatible type",
        severity="moderate",
    )


@pytest.fixture
def sample_bug_minor():
    """Create a sample minor bug."""
    return StaticBugReport(
        source="ruff",
        file_path="src/utils.py",
        line_number=25,
        error_code="W293",
        message="blank line contains whitespace",
        severity="minor",
    )


@pytest.fixture
def sample_analysis_result(sample_bug_critical, sample_bug_moderate, sample_bug_minor):
    """Create a sample analysis result with bugs."""
    return StaticAnalysisResult(
        bugs=[sample_bug_critical, sample_bug_moderate, sample_bug_minor],
        tools_run=["pytest", "mypy", "ruff"],
        tools_skipped=[],
    )


@pytest.fixture
def empty_analysis_result():
    """Create an empty analysis result (no bugs)."""
    return StaticAnalysisResult(
        bugs=[],
        tools_run=["pytest", "mypy", "ruff"],
        tools_skipped=[],
    )


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify analyze CLI commands can be imported."""

    def test_can_import_analyze_app(self):
        """Should be able to import analyze Typer app."""
        from swarm_attack.cli.analyze import app
        import typer
        assert isinstance(app, typer.Typer)

    def test_analyze_app_has_commands(self):
        """analyze app should have registered commands."""
        from swarm_attack.cli.analyze import app
        # Typer commands are registered as callbacks
        assert app.registered_commands is not None


# =============================================================================
# COMMAND REGISTRATION TESTS
# =============================================================================


class TestCommandRegistration:
    """Tests for command registration."""

    def test_all_command_exists(self, runner):
        """analyze all command should be registered."""
        from swarm_attack.cli.analyze import app
        result = runner.invoke(app, ["all", "--help"])
        assert result.exit_code == 0
        assert "all" in result.output.lower() or "detectors" in result.output.lower()

    def test_tests_command_exists(self, runner):
        """analyze tests command should be registered."""
        from swarm_attack.cli.analyze import app
        result = runner.invoke(app, ["tests", "--help"])
        assert result.exit_code == 0
        assert "pytest" in result.output.lower()

    def test_types_command_exists(self, runner):
        """analyze types command should be registered."""
        from swarm_attack.cli.analyze import app
        result = runner.invoke(app, ["types", "--help"])
        assert result.exit_code == 0
        assert "mypy" in result.output.lower()

    def test_lint_command_exists(self, runner):
        """analyze lint command should be registered."""
        from swarm_attack.cli.analyze import app
        result = runner.invoke(app, ["lint", "--help"])
        assert result.exit_code == 0
        assert "ruff" in result.output.lower()


# =============================================================================
# analyze all COMMAND TESTS
# =============================================================================


class TestAnalyzeAllCommand:
    """Tests for the analyze all command."""

    def test_runs_all_detectors(self, runner, empty_analysis_result):
        """Should run all detectors."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = empty_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            assert result.exit_code == 0
            mock_detector.detect_all.assert_called_once()

    def test_accepts_path_option(self, runner, empty_analysis_result):
        """Should accept --path option."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = empty_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all", "--path", "/src"])

            assert result.exit_code == 0
            mock_detector.detect_all.assert_called_once_with("/src")

    def test_exit_code_0_when_no_bugs(self, runner, empty_analysis_result):
        """Should exit with 0 when no bugs found."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = empty_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            assert result.exit_code == 0

    def test_exit_code_1_when_bugs_found(self, runner, sample_analysis_result):
        """Should exit with 1 when bugs found."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = sample_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            assert result.exit_code == 1

    def test_displays_bugs_by_severity(self, runner, sample_analysis_result):
        """Should display bugs grouped by severity."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = sample_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            # Should show severity levels
            assert "critical" in result.output.lower() or "CRITICAL" in result.output

    def test_displays_summary(self, runner, sample_analysis_result):
        """Should display summary statistics."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = sample_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            # Should show total count
            assert "3" in result.output or "total" in result.output.lower()

    def test_create_bugs_option(self, runner, sample_analysis_result):
        """Should create bug entries when --create-bugs is passed."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            with patch("swarm_attack.bug_orchestrator.BugOrchestrator") as mock_bug_orch_cls:
                mock_detector = MagicMock()
                mock_detector.detect_all.return_value = sample_analysis_result
                mock_detector_cls.return_value = mock_detector

                mock_bug_orch = MagicMock()
                mock_bug_orch.init_bug.return_value = MagicMock(success=True)
                mock_bug_orch_cls.return_value = mock_bug_orch

                result = runner.invoke(app, ["all", "--create-bugs"])

                # Should have called init_bug for each bug
                assert mock_bug_orch.init_bug.call_count == 3

    def test_shows_tools_run(self, runner, sample_analysis_result):
        """Should show which tools were run."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = sample_analysis_result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            # Should mention tools run
            assert "pytest" in result.output.lower() or "mypy" in result.output.lower() or "ruff" in result.output.lower()


# =============================================================================
# analyze tests COMMAND TESTS
# =============================================================================


class TestAnalyzeTestsCommand:
    """Tests for the analyze tests command."""

    def test_runs_pytest(self, runner):
        """Should run pytest detector."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_tests.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["tests"])

            assert result.exit_code == 0
            mock_detector.detect_from_tests.assert_called_once()

    def test_accepts_path_option(self, runner):
        """Should accept --path option."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_tests.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["tests", "--path", "tests/unit/"])

            assert result.exit_code == 0
            mock_detector.detect_from_tests.assert_called_once_with("tests/unit/")

    def test_exit_code_0_when_all_pass(self, runner):
        """Should exit with 0 when all tests pass."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_tests.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["tests"])

            assert result.exit_code == 0
            assert "passed" in result.output.lower() or "no" in result.output.lower()

    def test_exit_code_1_when_failures(self, runner, sample_bug_critical):
        """Should exit with 1 when test failures found."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_tests.return_value = [sample_bug_critical]
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["tests"])

            assert result.exit_code == 1


# =============================================================================
# analyze types COMMAND TESTS
# =============================================================================


class TestAnalyzeTypesCommand:
    """Tests for the analyze types command."""

    def test_runs_mypy(self, runner):
        """Should run mypy detector."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_types.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["types"])

            assert result.exit_code == 0
            mock_detector.detect_from_types.assert_called_once()

    def test_accepts_path_option(self, runner):
        """Should accept --path option."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_types.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["types", "--path", "src/"])

            assert result.exit_code == 0
            mock_detector.detect_from_types.assert_called_once_with("src/")

    def test_exit_code_0_when_no_errors(self, runner):
        """Should exit with 0 when no type errors."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_types.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["types"])

            assert result.exit_code == 0
            assert "no" in result.output.lower() or "error" not in result.output.lower()

    def test_exit_code_1_when_type_errors(self, runner, sample_bug_moderate):
        """Should exit with 1 when type errors found."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_types.return_value = [sample_bug_moderate]
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["types"])

            assert result.exit_code == 1


# =============================================================================
# analyze lint COMMAND TESTS
# =============================================================================


class TestAnalyzeLintCommand:
    """Tests for the analyze lint command."""

    def test_runs_ruff(self, runner):
        """Should run ruff detector."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_lint.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["lint"])

            assert result.exit_code == 0
            mock_detector.detect_from_lint.assert_called_once()

    def test_accepts_path_option(self, runner):
        """Should accept --path option."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_lint.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["lint", "--path", "src/"])

            assert result.exit_code == 0
            mock_detector.detect_from_lint.assert_called_once_with("src/")

    def test_exit_code_0_when_no_issues(self, runner):
        """Should exit with 0 when no lint issues."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_lint.return_value = []
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["lint"])

            assert result.exit_code == 0

    def test_exit_code_1_when_lint_issues(self, runner, sample_bug_minor):
        """Should exit with 1 when lint issues found."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_from_lint.return_value = [sample_bug_minor]
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["lint"])

            assert result.exit_code == 1

    def test_fix_option_runs_ruff_fix(self, runner):
        """Should run ruff --fix when --fix is passed."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            with patch("swarm_attack.cli.analyze.subprocess.run") as mock_run:
                mock_detector = MagicMock()
                mock_detector.detect_from_lint.return_value = []
                mock_detector_cls.return_value = mock_detector

                mock_run.return_value = MagicMock(returncode=0)

                result = runner.invoke(app, ["lint", "--fix"])

                # Should have called ruff with --fix
                assert mock_run.called
                call_args = mock_run.call_args[0][0]
                assert "ruff" in call_args
                assert "--fix" in call_args

    def test_fix_option_still_shows_remaining_issues(self, runner, sample_bug_minor):
        """Should still show remaining issues after --fix."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            with patch("swarm_attack.cli.analyze.subprocess.run") as mock_run:
                mock_detector = MagicMock()
                mock_detector.detect_from_lint.return_value = [sample_bug_minor]
                mock_detector_cls.return_value = mock_detector

                mock_run.return_value = MagicMock(returncode=0)

                result = runner.invoke(app, ["lint", "--fix"])

                # Should still run lint check and show issues
                mock_detector.detect_from_lint.assert_called_once()
                assert result.exit_code == 1


# =============================================================================
# OUTPUT FORMATTING TESTS
# =============================================================================


class TestOutputFormatting:
    """Tests for output formatting."""

    def test_critical_bugs_displayed_prominently(self, runner, sample_bug_critical):
        """Critical bugs should be displayed prominently."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            result = StaticAnalysisResult(
                bugs=[sample_bug_critical],
                tools_run=["pytest"],
                tools_skipped=[],
            )
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            assert "critical" in result.output.lower() or "CRITICAL" in result.output

    def test_shows_file_path_and_line(self, runner, sample_bug_critical):
        """Should show file path and line number."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            result = StaticAnalysisResult(
                bugs=[sample_bug_critical],
                tools_run=["pytest"],
                tools_skipped=[],
            )
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            # Should show file path
            assert "test_foo.py" in result.output
            # Should show line number
            assert "42" in result.output

    def test_shows_error_code(self, runner, sample_bug_critical):
        """Should show error code."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            result = StaticAnalysisResult(
                bugs=[sample_bug_critical],
                tools_run=["pytest"],
                tools_skipped=[],
            )
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            # Should show error code
            assert "TypeError" in result.output

    def test_shows_tools_skipped(self, runner):
        """Should show which tools were skipped."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            result = StaticAnalysisResult(
                bugs=[],
                tools_run=["pytest"],
                tools_skipped=["mypy", "ruff"],
            )
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            # Should show skipped tools
            assert "skipped" in result.output.lower() or "mypy" in result.output.lower()


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_detector_exception(self, runner):
        """Should handle detector exceptions gracefully."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            mock_detector = MagicMock()
            mock_detector.detect_all.side_effect = Exception("Detector failed")
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["all"])

            assert result.exit_code != 0
            assert "error" in result.output.lower()

    def test_handles_subprocess_error_in_lint_fix(self, runner):
        """Should handle subprocess errors in lint --fix."""
        from swarm_attack.cli.analyze import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            with patch("swarm_attack.cli.analyze.subprocess.run") as mock_run:
                mock_detector = MagicMock()
                mock_detector.detect_from_lint.return_value = []
                mock_detector_cls.return_value = mock_detector

                mock_run.side_effect = Exception("Subprocess failed")

                result = runner.invoke(app, ["lint", "--fix"])

                assert result.exit_code != 0


# =============================================================================
# INTEGRATION WITH MAIN APP TESTS
# =============================================================================


class TestMainAppIntegration:
    """Tests for integration with main CLI app."""

    def test_analyze_command_registered_in_main_app(self, runner):
        """analyze commands should be registered in main app."""
        from swarm_attack.cli.app import app

        result = runner.invoke(app, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "analyze" in result.output.lower()

    def test_can_run_analyze_all_from_main_app(self, runner):
        """Should be able to run analyze all from main app."""
        from swarm_attack.cli.app import app

        with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
            result = StaticAnalysisResult(
                bugs=[],
                tools_run=["pytest", "mypy", "ruff"],
                tools_skipped=[],
            )
            mock_detector = MagicMock()
            mock_detector.detect_all.return_value = result
            mock_detector_cls.return_value = mock_detector

            result = runner.invoke(app, ["analyze", "all"])

            assert result.exit_code == 0
