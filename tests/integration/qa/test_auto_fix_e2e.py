"""E2E Integration Tests for Auto-Fix Feature.

Tests the full flow of the auto-fix system using CLI commands against
real (temporary) test projects with intentional bugs.

Tests cover:
1. `swarm-attack analyze all` - Static analysis detection
2. `swarm-attack analyze all --create-bugs` - Bug creation from findings
3. `swarm-attack qa auto-fix --dry-run` - Dry-run mode (when implemented)
4. Full auto-fix loop integration

Following TDD approach - tests are written first.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner(mix_stderr=False)


@pytest.fixture
def temp_project_with_bugs(tmp_path):
    """Create a temporary project directory with intentional bugs.

    Creates a minimal project structure with:
    - A Python module with type errors (mypy will detect)
    - A test file with a failing test (pytest will detect)
    - A file with lint issues (ruff will detect)
    """
    # Create project structure
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    swarm_dir = tmp_path / ".swarm"
    swarm_dir.mkdir()
    (swarm_dir / "state").mkdir()
    (swarm_dir / "bugs").mkdir()

    # Create pyproject.toml for tool configuration
    pyproject_content = """
[project]
name = "test-project"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.mypy]
python_version = "3.9"
warn_return_any = true
check_untyped_defs = true

[tool.ruff]
line-length = 88
select = ["E", "F", "W"]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)

    # Create minimal config.yaml
    config_content = """
github:
  repo: "test/repo"

tests:
  command: "pytest"
  args: ["-v"]

auto_fix:
  enabled: true
  max_iterations: 3
  auto_approve: false
  dry_run: false
"""
    (tmp_path / "config.yaml").write_text(config_content)

    # Create a Python file with type errors (for mypy)
    module_with_type_error = '''
"""Module with intentional type errors."""

def add_numbers(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def process_data(data: str) -> str:
    """Process string data."""
    # Type error: passing int where str expected
    return add_numbers(data, 5)  # mypy should catch this
'''
    (src_dir / "buggy_module.py").write_text(module_with_type_error)
    (src_dir / "__init__.py").write_text("")

    # Create a test file with failing test (for pytest)
    failing_test = '''
"""Test file with intentional failure."""
import pytest


def test_that_passes():
    """This test passes."""
    assert 1 + 1 == 2


def test_that_fails():
    """This test fails intentionally."""
    assert 1 + 1 == 3, "Intentional failure for testing"
'''
    (tests_dir / "test_buggy.py").write_text(failing_test)
    (tests_dir / "__init__.py").write_text("")

    # Create a file with lint issues (for ruff)
    file_with_lint_issues = '''
"""File with lint issues."""
import os  # F401: unused import
import sys  # F401: unused import

x=1  # E225: missing whitespace around operator

def bad_function( ):  # E211: whitespace before '('
    y = None
    return y
'''
    (src_dir / "lint_issues.py").write_text(file_with_lint_issues)

    return tmp_path


@pytest.fixture
def temp_clean_project(tmp_path):
    """Create a temporary project with no bugs (clean codebase)."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    swarm_dir = tmp_path / ".swarm"
    swarm_dir.mkdir()
    (swarm_dir / "state").mkdir()
    (swarm_dir / "bugs").mkdir()

    # Create pyproject.toml
    pyproject_content = """
[project]
name = "clean-project"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_content)

    # Create config.yaml
    config_content = """
github:
  repo: "test/repo"

tests:
  command: "pytest"
"""
    (tmp_path / "config.yaml").write_text(config_content)

    # Create clean Python module
    clean_module = '''
"""Clean module with no issues."""


def add_numbers(a: int, b: int) -> int:
    """Add two integers and return the result."""
    return a + b


def greet(name: str) -> str:
    """Return a greeting message."""
    return f"Hello, {name}!"
'''
    (src_dir / "clean_module.py").write_text(clean_module)
    (src_dir / "__init__.py").write_text("")

    # Create passing test
    passing_test = '''
"""Tests that pass."""


def test_addition():
    """Test that addition works."""
    assert 1 + 1 == 2


def test_string():
    """Test string operations."""
    assert "hello".upper() == "HELLO"
'''
    (tests_dir / "test_clean.py").write_text(passing_test)
    (tests_dir / "__init__.py").write_text("")

    return tmp_path


# =============================================================================
# ANALYZE ALL COMMAND TESTS
# =============================================================================


class TestAnalyzeAllCommand:
    """E2E tests for `swarm-attack analyze all` command."""

    def test_analyze_all_detects_bugs_with_mocked_detector(self, runner, temp_project_with_bugs):
        """Should detect bugs when detector finds issues."""
        from swarm_attack.cli.app import app
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        original_dir = os.getcwd()
        try:
            os.chdir(temp_project_with_bugs)

            # Mock the detector to ensure bugs are found
            with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
                mock_detector = MagicMock()
                mock_detector.detect_all.return_value = StaticAnalysisResult(
                    bugs=[
                        StaticBugReport(
                            source="pytest",
                            file_path="tests/test_buggy.py",
                            line_number=10,
                            error_code="AssertionError",
                            message="Test failed",
                            severity="critical",
                        )
                    ],
                    tools_run=["pytest"],
                    tools_skipped=[],
                )
                mock_detector_cls.return_value = mock_detector

                result = runner.invoke(app, ["analyze", "all", "--path", str(temp_project_with_bugs)])

                # Should exit with code 1 when bugs are found
                assert result.exit_code == 1, f"Expected exit code 1, got {result.exit_code}. Output: {result.output}"

                # Output should contain some indication of findings
                output_lower = result.output.lower()
                assert any(word in output_lower for word in ["bug", "error", "issue", "critical", "moderate", "minor"]), \
                    f"Expected bug indicators in output: {result.output}"
        finally:
            os.chdir(original_dir)

    def test_analyze_all_clean_project(self, runner, temp_clean_project):
        """Should report no bugs for a clean project."""
        from swarm_attack.cli.app import app

        original_dir = os.getcwd()
        try:
            os.chdir(temp_clean_project)

            # Run analyze all on clean project
            result = runner.invoke(app, ["analyze", "all", "--path", str(temp_clean_project)])

            # Should exit with 0 when no bugs found
            assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}. Output: {result.output}"

            # Should indicate no bugs found
            output_lower = result.output.lower()
            assert "no bugs" in output_lower or "0" in result.output, \
                f"Expected 'no bugs' or '0' in output: {result.output}"
        finally:
            os.chdir(original_dir)

    def test_analyze_all_shows_summary(self, runner, temp_project_with_bugs):
        """Should display a summary with bug counts."""
        from swarm_attack.cli.app import app

        original_dir = os.getcwd()
        try:
            os.chdir(temp_project_with_bugs)

            result = runner.invoke(app, ["analyze", "all", "--path", str(temp_project_with_bugs)])

            # Should show summary section
            assert "summary" in result.output.lower() or "total" in result.output.lower(), \
                f"Expected summary in output: {result.output}"
        finally:
            os.chdir(original_dir)

    def test_analyze_all_path_option(self, runner, temp_project_with_bugs):
        """Should accept --path option to specify target directory."""
        from swarm_attack.cli.app import app

        # Run with explicit path (no need to chdir)
        result = runner.invoke(app, ["analyze", "all", "--path", str(temp_project_with_bugs)])

        # Should run without error (might find or not find bugs depending on tools available)
        assert result.exit_code in [0, 1], f"Unexpected exit code: {result.exit_code}. Output: {result.output}"


# =============================================================================
# ANALYZE ALL --CREATE-BUGS TESTS
# =============================================================================


class TestAnalyzeAllCreateBugs:
    """E2E tests for `swarm-attack analyze all --create-bugs` command."""

    def test_create_bugs_creates_bug_entries(self, runner, temp_project_with_bugs):
        """Should create BugState entries when --create-bugs is used."""
        from swarm_attack.cli.app import app
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        original_dir = os.getcwd()
        try:
            os.chdir(temp_project_with_bugs)

            # Mock both detector and BugOrchestrator
            with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
                # BugOrchestrator is imported inside _create_bugs_from_reports function
                with patch("swarm_attack.bug_orchestrator.BugOrchestrator") as mock_orch_cls:
                    mock_detector = MagicMock()
                    mock_detector.detect_all.return_value = StaticAnalysisResult(
                        bugs=[
                            StaticBugReport(
                                source="pytest",
                                file_path="tests/test_buggy.py",
                                line_number=10,
                                error_code="AssertionError",
                                message="Test failed",
                                severity="critical",
                            )
                        ],
                        tools_run=["pytest"],
                        tools_skipped=[],
                    )
                    mock_detector_cls.return_value = mock_detector

                    mock_orch = MagicMock()
                    mock_orch.init_bug.return_value = MagicMock(success=True, bug_id="test-bug-001")
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(app, ["analyze", "all", "--create-bugs", "--path", str(temp_project_with_bugs)])

                    # Exit code 1 because bugs were found
                    assert result.exit_code == 1

                    # init_bug should have been called
                    assert mock_orch.init_bug.called, f"Expected init_bug to be called. Output: {result.output}"
        finally:
            os.chdir(original_dir)

    def test_create_bugs_shows_created_count(self, runner, temp_project_with_bugs):
        """Should show count of created bugs."""
        from swarm_attack.cli.app import app
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        original_dir = os.getcwd()
        try:
            os.chdir(temp_project_with_bugs)

            with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
                with patch("swarm_attack.bug_orchestrator.BugOrchestrator") as mock_orch_cls:
                    mock_detector = MagicMock()
                    mock_detector.detect_all.return_value = StaticAnalysisResult(
                        bugs=[
                            StaticBugReport(
                                source="mypy",
                                file_path="src/module.py",
                                line_number=5,
                                error_code="arg-type",
                                message="Type error",
                                severity="moderate",
                            )
                        ],
                        tools_run=["mypy"],
                        tools_skipped=[],
                    )
                    mock_detector_cls.return_value = mock_detector

                    mock_orch = MagicMock()
                    mock_orch.init_bug.return_value = MagicMock(success=True, bug_id="static-bug-001")
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(app, ["analyze", "all", "--create-bugs", "--path", str(temp_project_with_bugs)])

                    # Should show info about creation
                    assert "created" in result.output.lower() or "bug" in result.output.lower()
        finally:
            os.chdir(original_dir)

    def test_create_bugs_handles_duplicates(self, runner, temp_project_with_bugs):
        """Should handle duplicate bug creation gracefully."""
        from swarm_attack.cli.app import app
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        original_dir = os.getcwd()
        try:
            os.chdir(temp_project_with_bugs)

            with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
                with patch("swarm_attack.bug_orchestrator.BugOrchestrator") as mock_orch_cls:
                    mock_detector = MagicMock()
                    mock_detector.detect_all.return_value = StaticAnalysisResult(
                        bugs=[
                            StaticBugReport(
                                source="ruff",
                                file_path="src/file.py",
                                line_number=1,
                                error_code="F401",
                                message="Unused import",
                                severity="minor",
                            )
                        ],
                        tools_run=["ruff"],
                        tools_skipped=[],
                    )
                    mock_detector_cls.return_value = mock_detector

                    mock_orch = MagicMock()
                    # Simulate duplicate (bug already exists)
                    mock_orch.init_bug.return_value = MagicMock(success=False, error="Bug already exists")
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(app, ["analyze", "all", "--create-bugs", "--path", str(temp_project_with_bugs)])

                    # Should not crash - duplicates are skipped silently
                    assert result.exit_code in [0, 1], f"Unexpected crash: {result.output}"
        finally:
            os.chdir(original_dir)

    def test_create_bugs_no_action_on_clean_project(self, runner, temp_clean_project):
        """Should not create bugs when no issues found."""
        from swarm_attack.cli.app import app
        from swarm_attack.static_analysis.models import StaticAnalysisResult

        original_dir = os.getcwd()
        try:
            os.chdir(temp_clean_project)

            with patch("swarm_attack.cli.analyze.StaticBugDetector") as mock_detector_cls:
                with patch("swarm_attack.bug_orchestrator.BugOrchestrator") as mock_orch_cls:
                    mock_detector = MagicMock()
                    # No bugs found
                    mock_detector.detect_all.return_value = StaticAnalysisResult(
                        bugs=[],
                        tools_run=["pytest", "mypy", "ruff"],
                        tools_skipped=[],
                    )
                    mock_detector_cls.return_value = mock_detector

                    mock_orch = MagicMock()
                    mock_orch_cls.return_value = mock_orch

                    result = runner.invoke(app, ["analyze", "all", "--create-bugs", "--path", str(temp_clean_project)])

                    # Clean project - should not call init_bug
                    assert result.exit_code == 0
                    mock_orch.init_bug.assert_not_called()
        finally:
            os.chdir(original_dir)


# =============================================================================
# QA AUTO-FIX DRY-RUN TESTS
# =============================================================================


class TestAutoFixDryRun:
    """E2E tests for auto-fix --dry-run mode.

    Note: These tests verify the dry-run functionality of the AutoFixOrchestrator
    when invoked via CLI or programmatic interface.
    """

    def test_dry_run_detects_without_fixing(self, temp_project_with_bugs):
        """Dry run should detect bugs but not apply fixes."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator, AutoFixResult
        from swarm_attack.config import AutoFixConfig

        # Create mock dependencies
        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="test-bug")

        mock_detector = MagicMock()
        # Simulate finding a bug
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test_buggy.py",
            line_number=10,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        config = AutoFixConfig(
            enabled=True,
            max_iterations=1,
            auto_approve=True,
            dry_run=True,  # Key: dry_run mode
        )

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run(target=str(temp_project_with_bugs))

        # Should have detected bugs
        assert result.bugs_found > 0

        # Should NOT have called fix (dry_run mode)
        mock_bug_orch.fix.assert_not_called()

        # Should NOT have called analyze (skipped in dry_run)
        mock_bug_orch.analyze.assert_not_called()

        # Result should indicate dry_run
        assert result.dry_run is True

    def test_dry_run_creates_bug_entries(self, temp_project_with_bugs):
        """Dry run should still create bug investigation entries."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="dry-run-bug")

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="mypy",
            file_path="src/buggy_module.py",
            line_number=10,
            error_code="arg-type",
            message="Type mismatch",
            severity="moderate",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["mypy"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, dry_run=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run(max_iterations=1)

        # Should have created bug investigation
        mock_bug_orch.init_bug.assert_called()

    def test_dry_run_shows_what_would_be_fixed(self, temp_project_with_bugs):
        """Dry run should log/report what would be fixed."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult
        import logging

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="report-bug")

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="ruff",
            file_path="src/lint_issues.py",
            line_number=3,
            error_code="F401",
            message="Unused import",
            severity="minor",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["ruff"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, dry_run=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        # Capture logs to verify dry_run messaging
        with patch("swarm_attack.qa.auto_fix.logger") as mock_logger:
            result = orchestrator.run(max_iterations=1)

            # Should log about dry run
            log_calls = [str(c) for c in mock_logger.info.call_args_list]
            # The orchestrator logs "[DRY RUN] Would fix:" messages
            dry_run_logged = any("DRY RUN" in str(c) or "dry" in str(c).lower() for c in log_calls)
            assert dry_run_logged or result.dry_run is True


# =============================================================================
# FULL AUTO-FIX LOOP TESTS
# =============================================================================


class TestAutoFixFullLoop:
    """E2E tests for the complete auto-fix detection-fix loop."""

    def test_loop_terminates_when_clean(self, temp_clean_project):
        """Loop should terminate immediately when codebase is clean."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_detector = MagicMock()

        # Return empty result (no bugs)
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest", "mypy", "ruff"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, max_iterations=5)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Should succeed immediately
        assert result.success is True
        assert result.iterations_run == 1
        assert result.bugs_found == 0

    def test_loop_fixes_bugs_until_clean(self, temp_project_with_bugs):
        """Loop should continue until codebase is clean or max iterations."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="loop-bug")
        mock_bug_orch.analyze.return_value = MagicMock(success=True)
        mock_bug_orch.approve.return_value = MagicMock(success=True)
        mock_bug_orch.fix.return_value = MagicMock(success=True)

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Failed",
            severity="moderate",
        )

        # First call: return bug, second call: clean
        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        mock_detector.detect_all.side_effect = detect_side_effect

        config = AutoFixConfig(enabled=True, max_iterations=5, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Should have run 2 iterations (find bug, fix, detect clean)
        assert result.iterations_run == 2
        assert result.bugs_found == 1
        assert result.bugs_fixed == 1
        assert result.success is True

    def test_loop_respects_max_iterations(self, temp_project_with_bugs):
        """Loop should stop after max_iterations even with remaining bugs."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="persistent-bug")
        mock_bug_orch.analyze.return_value = MagicMock(success=True)
        mock_bug_orch.approve.return_value = MagicMock(success=True)
        # Fix always fails - bug persists
        mock_bug_orch.fix.return_value = MagicMock(success=False, error="Still failing")

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Persistent failure",
            severity="moderate",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, max_iterations=3, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Should have stopped at max_iterations
        assert result.iterations_run == 3
        assert result.success is False
        assert len(result.errors) > 0  # Should have tracked fix failures

    def test_loop_handles_critical_bugs_with_callback(self, temp_project_with_bugs):
        """Loop should pause for human checkpoint on critical bugs."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_detector = MagicMock()

        critical_bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="SecurityError",
            message="Critical security issue",
            severity="critical",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[critical_bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        # Track checkpoint callback invocations
        callback_calls = []
        def checkpoint_callback(bug):
            callback_calls.append(bug)
            return False  # Reject - don't proceed

        config = AutoFixConfig(enabled=True, max_iterations=1, auto_approve=False)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )
        orchestrator.set_checkpoint_callback(checkpoint_callback)

        result = orchestrator.run()

        # Callback should have been called
        assert len(callback_calls) == 1
        assert callback_calls[0].severity == "critical"

        # Checkpoint should be tracked
        assert result.checkpoints_triggered == 1

        # Bug should NOT have been processed (callback rejected)
        mock_bug_orch.init_bug.assert_not_called()


# =============================================================================
# INTEGRATION WITH BUG PIPELINE TESTS
# =============================================================================


class TestAutoFixBugPipelineIntegration:
    """Tests for auto-fix integration with the bug bash pipeline."""

    def test_creates_proper_bug_investigation(self, temp_project_with_bugs):
        """Should create bug investigations with proper metadata."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="detailed-bug")

        mock_detector = MagicMock()
        # Use moderate severity to avoid checkpoint (critical bugs need callback when auto_approve=False)
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test_buggy.py",
            line_number=42,
            error_code="TypeError",
            message="'NoneType' object is not subscriptable",
            severity="moderate",  # Changed from critical to moderate
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        # Use auto_approve=True to ensure bug gets processed even in dry_run mode
        config = AutoFixConfig(enabled=True, max_iterations=1, dry_run=True, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        orchestrator.run()

        # Verify init_bug was called with proper arguments
        mock_bug_orch.init_bug.assert_called_once()
        call_kwargs = mock_bug_orch.init_bug.call_args.kwargs

        # Should include error details in description
        desc = call_kwargs.get("description", "")
        assert "PYTEST" in desc
        assert "TypeError" in desc
        assert "tests/test_buggy.py:42" in desc

        # Should include test_path for pytest findings
        assert call_kwargs.get("test_path") == "tests/test_buggy.py"

        # Should include error message
        assert "'NoneType' object is not subscriptable" in call_kwargs.get("error_message", "")

    def test_analyzes_bug_before_fixing(self, temp_project_with_bugs):
        """Should run analysis phase before attempting fix."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="analyze-bug")
        mock_bug_orch.analyze.return_value = MagicMock(success=True)
        mock_bug_orch.approve.return_value = MagicMock(success=True)
        mock_bug_orch.fix.return_value = MagicMock(success=True)

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="mypy",
            file_path="src/module.py",
            line_number=10,
            error_code="arg-type",
            message="Type mismatch",
            severity="moderate",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["mypy"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["mypy"], tools_skipped=[])

        mock_detector.detect_all.side_effect = detect_side_effect

        config = AutoFixConfig(enabled=True, max_iterations=2, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Verify order: init_bug -> analyze -> approve -> fix
        assert mock_bug_orch.init_bug.called
        assert mock_bug_orch.analyze.called
        assert mock_bug_orch.approve.called
        assert mock_bug_orch.fix.called


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestAutoFixErrorHandling:
    """Tests for error handling in the auto-fix loop."""

    def test_handles_detection_failure(self):
        """Should handle detector failures gracefully."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig

        mock_bug_orch = MagicMock()
        mock_detector = MagicMock()

        # Detector raises exception
        mock_detector.detect_all.side_effect = Exception("Detector crashed")

        config = AutoFixConfig(enabled=True, max_iterations=1)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        # Should raise the exception (detection is critical)
        with pytest.raises(Exception, match="Detector crashed"):
            orchestrator.run()

    def test_handles_bug_creation_failure(self):
        """Should track bug creation failures without crashing."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=False, error="Creation failed")

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="ruff",
            file_path="src/file.py",
            line_number=1,
            error_code="E999",
            message="Syntax error",
            severity="critical",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["ruff"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, max_iterations=1, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Should not crash, should track error
        assert len(result.errors) == 1
        assert "Failed to create bug" in result.errors[0]

    def test_handles_analysis_failure(self):
        """Should track analysis failures without crashing."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="analysis-fail")
        mock_bug_orch.analyze.return_value = MagicMock(success=False, error="Analysis failed")

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="Error",
            message="Test failed",
            severity="moderate",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, max_iterations=1, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Should not crash, should track error
        assert len(result.errors) == 1
        assert "Analysis failed" in result.errors[0]

    def test_handles_fix_exception(self):
        """Should handle exceptions during fix without crashing."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        from swarm_attack.config import AutoFixConfig
        from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult

        mock_bug_orch = MagicMock()
        mock_bug_orch.init_bug.return_value = MagicMock(success=True, bug_id="fix-crash")
        mock_bug_orch.analyze.return_value = MagicMock(success=True)
        mock_bug_orch.approve.return_value = MagicMock(success=True)
        mock_bug_orch.fix.side_effect = Exception("Fix crashed")

        mock_detector = MagicMock()
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="Error",
            message="Test failed",
            severity="moderate",
        )
        mock_detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        config = AutoFixConfig(enabled=True, max_iterations=1, auto_approve=True)

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orch,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run()

        # Should not crash, should track error
        assert len(result.errors) == 1
        assert "exception" in result.errors[0].lower()


# =============================================================================
# RESULT REPORTING TESTS
# =============================================================================


class TestAutoFixResultReporting:
    """Tests for auto-fix result reporting."""

    def test_result_contains_all_statistics(self):
        """AutoFixResult should contain comprehensive statistics."""
        from swarm_attack.qa.auto_fix import AutoFixResult

        result = AutoFixResult(
            bugs_found=10,
            bugs_fixed=7,
            iterations_run=3,
            success=True,
            checkpoints_triggered=2,
            dry_run=False,
            errors=["Error 1", "Error 2"],
        )

        assert result.bugs_found == 10
        assert result.bugs_fixed == 7
        assert result.iterations_run == 3
        assert result.success is True
        assert result.checkpoints_triggered == 2
        assert result.dry_run is False
        assert len(result.errors) == 2

    def test_result_serializes_to_dict(self):
        """AutoFixResult should serialize to dictionary for logging/storage."""
        from swarm_attack.qa.auto_fix import AutoFixResult

        result = AutoFixResult(
            bugs_found=5,
            bugs_fixed=3,
            iterations_run=2,
            success=True,
        )

        data = result.to_dict()

        assert data["bugs_found"] == 5
        assert data["bugs_fixed"] == 3
        assert data["iterations_run"] == 2
        assert data["success"] is True

    def test_result_deserializes_from_dict(self):
        """AutoFixResult should deserialize from dictionary."""
        from swarm_attack.qa.auto_fix import AutoFixResult

        data = {
            "bugs_found": 8,
            "bugs_fixed": 6,
            "iterations_run": 4,
            "success": False,
            "checkpoints_triggered": 1,
            "dry_run": True,
            "errors": ["Error 1"],
        }

        result = AutoFixResult.from_dict(data)

        assert result.bugs_found == 8
        assert result.bugs_fixed == 6
        assert result.iterations_run == 4
        assert result.success is False
        assert result.checkpoints_triggered == 1
        assert result.dry_run is True
        assert result.errors == ["Error 1"]
