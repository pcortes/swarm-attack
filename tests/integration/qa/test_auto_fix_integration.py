"""Integration Tests for Auto-Fix Orchestrator.

Tests the AutoFixOrchestrator end-to-end with mocked BugOrchestrator
and StaticBugDetector components working together.

These tests verify:
1. Full flow: detect_all -> create_bug -> analyze -> approve -> fix
2. Dry run mode with all components
3. Critical bugs trigger checkpoints correctly
4. Graceful handling when BugOrchestrator.fix() fails
5. Multiple bugs in one iteration are all processed

Following integration test patterns from the existing test suite.
"""

import json
import pytest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch, call

from swarm_attack.config import AutoFixConfig
from swarm_attack.qa.auto_fix import AutoFixOrchestrator, AutoFixResult
from swarm_attack.static_analysis.detector import StaticBugDetector
from swarm_attack.static_analysis.models import StaticAnalysisResult, StaticBugReport


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock AutoFixConfig for testing."""
    return AutoFixConfig(
        enabled=True,
        max_iterations=3,
        auto_approve=True,
        dry_run=False,
        watch_poll_seconds=5,
    )


@pytest.fixture
def mock_config_no_auto_approve():
    """Create a mock AutoFixConfig with auto_approve disabled."""
    return AutoFixConfig(
        enabled=True,
        max_iterations=3,
        auto_approve=False,
        dry_run=False,
        watch_poll_seconds=5,
    )


@pytest.fixture
def mock_config_dry_run():
    """Create a mock AutoFixConfig for dry run testing."""
    return AutoFixConfig(
        enabled=True,
        max_iterations=3,
        auto_approve=True,
        dry_run=True,
        watch_poll_seconds=5,
    )


@pytest.fixture
def sample_pytest_bug():
    """Create a sample pytest failure bug report."""
    return StaticBugReport(
        source="pytest",
        file_path="tests/test_example.py",
        line_number=42,
        error_code="AssertionError",
        message="assert 1 == 2",
        severity="moderate",
    )


@pytest.fixture
def sample_mypy_bug():
    """Create a sample mypy type error bug report."""
    return StaticBugReport(
        source="mypy",
        file_path="src/module.py",
        line_number=15,
        error_code="arg-type",
        message="Argument 1 has incompatible type",
        severity="moderate",
    )


@pytest.fixture
def sample_ruff_bug():
    """Create a sample ruff lint error bug report."""
    return StaticBugReport(
        source="ruff",
        file_path="src/config.py",
        line_number=10,
        error_code="F401",
        message="'os' imported but unused",
        severity="moderate",
    )


@pytest.fixture
def sample_critical_bug():
    """Create a sample critical security bug report."""
    return StaticBugReport(
        source="ruff",
        file_path="src/auth.py",
        line_number=25,
        error_code="S105",
        message="Possible hardcoded password",
        severity="critical",
    )


@pytest.fixture
def mock_bug_orchestrator():
    """Create a mock BugOrchestrator with successful operations."""
    mock = MagicMock()

    # Mock init_bug to return success with bug_id
    init_result = MagicMock()
    init_result.success = True
    init_result.bug_id = "bug-test-001"
    mock.init_bug.return_value = init_result

    # Mock analyze to return success
    analyze_result = MagicMock()
    analyze_result.success = True
    analyze_result.error = None
    mock.analyze.return_value = analyze_result

    # Mock approve to return success
    approve_result = MagicMock()
    approve_result.success = True
    approve_result.error = None
    mock.approve.return_value = approve_result

    # Mock fix to return success
    fix_result = MagicMock()
    fix_result.success = True
    fix_result.error = None
    mock.fix.return_value = fix_result

    return mock


@pytest.fixture
def mock_detector():
    """Create a mock StaticBugDetector."""
    return MagicMock(spec=StaticBugDetector)


def create_analysis_result(bugs, tools_run=None, tools_skipped=None):
    """Helper to create StaticAnalysisResult instances."""
    return StaticAnalysisResult(
        bugs=bugs,
        tools_run=tools_run or ["pytest", "mypy", "ruff"],
        tools_skipped=tools_skipped or [],
    )


# =============================================================================
# END-TO-END FLOW TESTS
# =============================================================================


class TestAutoFixEndToEndFlow:
    """Integration tests for the complete auto-fix flow.

    Tests: detect_all -> create_bug -> analyze -> approve -> fix
    """

    def test_full_flow_single_bug_fixed(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should complete full flow: detect -> create -> analyze -> approve -> fix."""
        # First call returns a bug, second call returns clean
        mock_detector.detect_all.side_effect = [
            create_analysis_result([sample_pytest_bug]),
            create_analysis_result([]),  # Clean on second iteration
        ]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="tests/", max_iterations=3)

        # Verify result
        assert result.success is True
        assert result.bugs_found == 1
        assert result.bugs_fixed == 1
        assert result.iterations_run == 2  # First to fix, second to verify clean
        assert result.dry_run is False
        assert len(result.errors) == 0

        # Verify full pipeline was called
        mock_detector.detect_all.assert_called()
        mock_bug_orchestrator.init_bug.assert_called_once()
        mock_bug_orchestrator.analyze.assert_called_once_with("bug-test-001")
        mock_bug_orchestrator.approve.assert_called_once_with("bug-test-001")
        mock_bug_orchestrator.fix.assert_called_once_with("bug-test-001")

    def test_full_flow_multiple_bugs_all_fixed(
        self, mock_config, mock_bug_orchestrator, mock_detector,
        sample_pytest_bug, sample_mypy_bug, sample_ruff_bug
    ):
        """Should fix all bugs when multiple are detected."""
        bugs = [sample_pytest_bug, sample_mypy_bug, sample_ruff_bug]

        # Track bug IDs for each init call
        bug_ids = ["bug-pytest-001", "bug-mypy-002", "bug-ruff-003"]
        call_count = [0]

        def mock_init_bug(**kwargs):
            result = MagicMock()
            result.success = True
            result.bug_id = bug_ids[call_count[0]]
            call_count[0] += 1
            return result

        mock_bug_orchestrator.init_bug.side_effect = mock_init_bug

        # First call returns bugs, second call returns clean
        mock_detector.detect_all.side_effect = [
            create_analysis_result(bugs),
            create_analysis_result([]),  # Clean on second iteration
        ]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="src/", max_iterations=5)

        # Verify result
        assert result.success is True
        assert result.bugs_found == 3
        assert result.bugs_fixed == 3
        assert result.iterations_run == 2

        # Verify all bugs were processed
        assert mock_bug_orchestrator.init_bug.call_count == 3
        assert mock_bug_orchestrator.analyze.call_count == 3
        assert mock_bug_orchestrator.approve.call_count == 3
        assert mock_bug_orchestrator.fix.call_count == 3

    def test_full_flow_stops_when_codebase_clean(
        self, mock_config, mock_bug_orchestrator, mock_detector
    ):
        """Should stop immediately when no bugs detected."""
        mock_detector.detect_all.return_value = create_analysis_result([])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="src/", max_iterations=3)

        # Verify result
        assert result.success is True
        assert result.bugs_found == 0
        assert result.bugs_fixed == 0
        assert result.iterations_run == 1

        # Verify no bug operations were called
        mock_bug_orchestrator.init_bug.assert_not_called()
        mock_bug_orchestrator.analyze.assert_not_called()
        mock_bug_orchestrator.fix.assert_not_called()

    def test_full_flow_uses_config_defaults(
        self, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should use config defaults when parameters not provided."""
        config = AutoFixConfig(
            enabled=True,
            max_iterations=2,
            auto_approve=True,
            dry_run=False,
        )

        mock_detector.detect_all.side_effect = [
            create_analysis_result([sample_pytest_bug]),
            create_analysis_result([sample_pytest_bug]),  # Still has bugs
            create_analysis_result([sample_pytest_bug]),  # Would exceed max
        ]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=config,
        )

        # Run without explicit parameters - should use config defaults
        result = orchestrator.run(target="tests/")

        # Should stop at max_iterations from config (2)
        assert result.iterations_run == 2
        assert result.success is False  # Bugs still remain


# =============================================================================
# DRY RUN MODE TESTS
# =============================================================================


class TestAutoFixDryRunMode:
    """Integration tests for dry run mode.

    Verifies that dry run detects bugs but doesn't apply fixes.
    """

    def test_dry_run_detects_bugs_no_fix(
        self, mock_config_dry_run, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Dry run should detect and create bugs but not fix them."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config_dry_run,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Verify result
        assert result.dry_run is True
        assert result.bugs_found == 1
        assert result.bugs_fixed == 0  # No fixes in dry run

        # Bug should be created but not fixed
        mock_bug_orchestrator.init_bug.assert_called_once()
        mock_bug_orchestrator.analyze.assert_not_called()
        mock_bug_orchestrator.approve.assert_not_called()
        mock_bug_orchestrator.fix.assert_not_called()

    def test_dry_run_with_multiple_bugs(
        self, mock_config_dry_run, mock_bug_orchestrator, mock_detector,
        sample_pytest_bug, sample_mypy_bug
    ):
        """Dry run should log all bugs without fixing any."""
        bugs = [sample_pytest_bug, sample_mypy_bug]
        mock_detector.detect_all.return_value = create_analysis_result(bugs)

        # Track bug IDs for each init call
        bug_ids = ["bug-001", "bug-002"]
        call_count = [0]

        def mock_init_bug(**kwargs):
            result = MagicMock()
            result.success = True
            result.bug_id = bug_ids[call_count[0]]
            call_count[0] += 1
            return result

        mock_bug_orchestrator.init_bug.side_effect = mock_init_bug

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config_dry_run,
        )

        result = orchestrator.run(target="src/", max_iterations=1)

        # Verify result
        assert result.dry_run is True
        assert result.bugs_found == 2
        assert result.bugs_fixed == 0

        # Both bugs should be created
        assert mock_bug_orchestrator.init_bug.call_count == 2

        # But no fixes applied
        mock_bug_orchestrator.fix.assert_not_called()

    def test_dry_run_parameter_overrides_config(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Explicit dry_run=True should override config setting."""
        # Config has dry_run=False, but we pass True explicitly
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,  # dry_run=False in config
        )

        result = orchestrator.run(target="tests/", dry_run=True, max_iterations=1)

        # Verify dry run was used despite config
        assert result.dry_run is True
        assert result.bugs_fixed == 0
        mock_bug_orchestrator.fix.assert_not_called()


# =============================================================================
# CHECKPOINT TRIGGER TESTS
# =============================================================================


class TestAutoFixCheckpointTriggers:
    """Integration tests for checkpoint handling on critical bugs.

    Verifies that critical bugs trigger checkpoints when auto_approve=False.
    """

    def test_critical_bug_triggers_checkpoint(
        self, mock_config_no_auto_approve, mock_bug_orchestrator,
        mock_detector, sample_critical_bug
    ):
        """Critical bug should trigger checkpoint when auto_approve=False."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_critical_bug])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config_no_auto_approve,
        )

        result = orchestrator.run(target="src/", max_iterations=1)

        # Verify checkpoint was triggered
        assert result.checkpoints_triggered == 1

        # Bug should not be fixed without callback approval
        mock_bug_orchestrator.fix.assert_not_called()

    def test_critical_bug_with_checkpoint_callback_approved(
        self, mock_config_no_auto_approve, mock_bug_orchestrator,
        mock_detector, sample_critical_bug
    ):
        """Critical bug should proceed to analysis when callback approves.

        Note: With auto_approve=False, the checkpoint callback approves the
        bug for investigation (analyze), but the bug stays in PLANNED state
        awaiting manual approval. To also fix the bug, auto_approve must be True.
        """
        mock_detector.detect_all.side_effect = [
            create_analysis_result([sample_critical_bug]),
            create_analysis_result([]),  # Clean on subsequent iteration
        ]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config_no_auto_approve,
        )

        # Set callback that approves
        callback_calls = []
        def approve_callback(bug):
            callback_calls.append(bug)
            return True

        orchestrator.set_checkpoint_callback(approve_callback)

        result = orchestrator.run(target="src/", max_iterations=3)

        # Verify checkpoint was triggered
        assert result.checkpoints_triggered == 1

        # Verify callback was called with the bug
        assert len(callback_calls) == 1
        assert callback_calls[0].severity == "critical"
        assert callback_calls[0].file_path == "src/auth.py"

        # Bug should be analyzed but not fixed (auto_approve=False)
        # The checkpoint allows investigation, but fix still requires auto_approve
        mock_bug_orchestrator.init_bug.assert_called_once()
        mock_bug_orchestrator.analyze.assert_called_once()
        mock_bug_orchestrator.approve.assert_not_called()  # No auto_approve
        mock_bug_orchestrator.fix.assert_not_called()  # No fix without approval

    def test_critical_bug_with_checkpoint_callback_rejected(
        self, mock_config_no_auto_approve, mock_bug_orchestrator,
        mock_detector, sample_critical_bug
    ):
        """Critical bug should be skipped when callback rejects."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_critical_bug])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config_no_auto_approve,
        )

        # Set callback that rejects
        def reject_callback(bug):
            return False

        orchestrator.set_checkpoint_callback(reject_callback)

        result = orchestrator.run(target="src/", max_iterations=1)

        # Verify checkpoint was triggered
        assert result.checkpoints_triggered == 1

        # Bug should not be fixed since callback rejected
        assert result.bugs_fixed == 0
        mock_bug_orchestrator.init_bug.assert_not_called()

    def test_moderate_bug_no_checkpoint_without_auto_approve(
        self, mock_config_no_auto_approve, mock_bug_orchestrator,
        mock_detector, sample_pytest_bug
    ):
        """Moderate bugs should proceed to analysis but not fix without auto_approve."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config_no_auto_approve,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # No checkpoint for moderate bugs
        assert result.checkpoints_triggered == 0

        # Bug should be analyzed but not fixed (no auto_approve)
        mock_bug_orchestrator.init_bug.assert_called_once()
        mock_bug_orchestrator.analyze.assert_called_once()
        mock_bug_orchestrator.approve.assert_not_called()  # Requires auto_approve
        mock_bug_orchestrator.fix.assert_not_called()

    def test_critical_bug_bypasses_checkpoint_with_auto_approve(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_critical_bug
    ):
        """Critical bug should bypass checkpoint when auto_approve=True."""
        mock_detector.detect_all.side_effect = [
            create_analysis_result([sample_critical_bug]),
            create_analysis_result([]),  # Clean after fix
        ]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,  # auto_approve=True
        )

        result = orchestrator.run(target="src/", max_iterations=3)

        # No checkpoint with auto_approve
        assert result.checkpoints_triggered == 0

        # Bug should be fixed
        assert result.bugs_fixed == 1
        mock_bug_orchestrator.fix.assert_called_once()


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestAutoFixErrorHandling:
    """Integration tests for graceful error handling.

    Verifies that the orchestrator handles failures gracefully.
    """

    def test_handles_fix_failure_gracefully(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should continue when BugOrchestrator.fix() fails."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        # Make fix fail
        fix_result = MagicMock()
        fix_result.success = False
        fix_result.error = "Fix failed: merge conflict"
        mock_bug_orchestrator.fix.return_value = fix_result

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Verify error was recorded
        assert result.bugs_found == 1
        assert result.bugs_fixed == 0
        assert len(result.errors) == 1
        assert "Fix failed" in result.errors[0]

        # Verify all steps were attempted
        mock_bug_orchestrator.fix.assert_called_once()

    def test_handles_fix_exception_gracefully(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should continue when BugOrchestrator.fix() raises exception."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        # Make fix raise exception
        mock_bug_orchestrator.fix.side_effect = RuntimeError("Unexpected error")

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Verify error was recorded
        assert result.bugs_found == 1
        assert result.bugs_fixed == 0
        assert len(result.errors) == 1
        assert "exception" in result.errors[0].lower()

    def test_handles_analyze_failure_gracefully(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should continue when BugOrchestrator.analyze() fails."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        # Make analyze fail
        analyze_result = MagicMock()
        analyze_result.success = False
        analyze_result.error = "Analysis failed: timeout"
        mock_bug_orchestrator.analyze.return_value = analyze_result

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Verify error was recorded
        assert len(result.errors) == 1
        assert "Analysis failed" in result.errors[0]

        # Fix should not be called since analyze failed
        mock_bug_orchestrator.fix.assert_not_called()

    def test_handles_approve_failure_gracefully(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should continue when BugOrchestrator.approve() fails."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        # Make approve fail
        approve_result = MagicMock()
        approve_result.success = False
        approve_result.error = "Approval failed: no fix plan"
        mock_bug_orchestrator.approve.return_value = approve_result

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Verify error was recorded
        assert len(result.errors) == 1
        assert "Approval failed" in result.errors[0]

        # Fix should not be called since approve failed
        mock_bug_orchestrator.fix.assert_not_called()

    def test_handles_init_bug_failure_gracefully(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should continue when BugOrchestrator.init_bug() fails."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        # Make init_bug fail
        init_result = MagicMock()
        init_result.success = False
        init_result.bug_id = None
        init_result.error = "Failed to create bug"
        mock_bug_orchestrator.init_bug.return_value = init_result

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Verify error was recorded
        assert len(result.errors) == 1
        assert "Failed to create bug" in result.errors[0]

        # Subsequent steps should not be called
        mock_bug_orchestrator.analyze.assert_not_called()
        mock_bug_orchestrator.fix.assert_not_called()

    def test_partial_success_with_mixed_results(
        self, mock_config, mock_bug_orchestrator, mock_detector,
        sample_pytest_bug, sample_mypy_bug
    ):
        """Should handle partial success when some bugs fail to fix."""
        bugs = [sample_pytest_bug, sample_mypy_bug]
        mock_detector.detect_all.return_value = create_analysis_result(bugs)

        # Track bug IDs for each init call
        bug_ids = ["bug-success", "bug-fail"]
        call_count = [0]

        def mock_init_bug(**kwargs):
            result = MagicMock()
            result.success = True
            result.bug_id = bug_ids[call_count[0]]
            call_count[0] += 1
            return result

        mock_bug_orchestrator.init_bug.side_effect = mock_init_bug

        # First fix succeeds, second fails
        fix_success = MagicMock()
        fix_success.success = True
        fix_fail = MagicMock()
        fix_fail.success = False
        fix_fail.error = "Fix failed for this bug"
        mock_bug_orchestrator.fix.side_effect = [fix_success, fix_fail]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="src/", max_iterations=1)

        # Verify partial success
        assert result.bugs_found == 2
        assert result.bugs_fixed == 1
        assert len(result.errors) == 1


# =============================================================================
# MULTIPLE BUGS PER ITERATION TESTS
# =============================================================================


class TestAutoFixMultipleBugsProcessing:
    """Integration tests for processing multiple bugs in one iteration.

    Verifies that all bugs detected in a single iteration are processed.
    """

    def test_processes_all_bugs_in_iteration(
        self, mock_config, mock_bug_orchestrator, mock_detector,
        sample_pytest_bug, sample_mypy_bug, sample_ruff_bug
    ):
        """Should process all bugs found in single iteration."""
        bugs = [sample_pytest_bug, sample_mypy_bug, sample_ruff_bug]
        mock_detector.detect_all.side_effect = [
            create_analysis_result(bugs),
            create_analysis_result([]),  # Clean after fixes
        ]

        # Track bug IDs
        bug_ids = ["bug-001", "bug-002", "bug-003"]
        call_count = [0]

        def mock_init_bug(**kwargs):
            result = MagicMock()
            result.success = True
            result.bug_id = bug_ids[call_count[0]]
            call_count[0] += 1
            return result

        mock_bug_orchestrator.init_bug.side_effect = mock_init_bug

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="src/", max_iterations=3)

        # Verify all bugs were processed
        assert result.bugs_found == 3
        assert result.bugs_fixed == 3
        assert mock_bug_orchestrator.init_bug.call_count == 3
        assert mock_bug_orchestrator.fix.call_count == 3

    def test_continues_after_individual_bug_failure(
        self, mock_config, mock_bug_orchestrator, mock_detector,
        sample_pytest_bug, sample_mypy_bug, sample_ruff_bug
    ):
        """Should continue processing other bugs when one fails."""
        bugs = [sample_pytest_bug, sample_mypy_bug, sample_ruff_bug]
        mock_detector.detect_all.return_value = create_analysis_result(bugs)

        # Track bug IDs
        bug_ids = ["bug-001", "bug-002", "bug-003"]
        call_count = [0]

        def mock_init_bug(**kwargs):
            result = MagicMock()
            result.success = True
            result.bug_id = bug_ids[call_count[0]]
            call_count[0] += 1
            return result

        mock_bug_orchestrator.init_bug.side_effect = mock_init_bug

        # Second bug fails to fix
        fix_success = MagicMock()
        fix_success.success = True
        fix_fail = MagicMock()
        fix_fail.success = False
        fix_fail.error = "Fix failed"
        mock_bug_orchestrator.fix.side_effect = [fix_success, fix_fail, fix_success]

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="src/", max_iterations=1)

        # Verify all bugs were attempted
        assert mock_bug_orchestrator.fix.call_count == 3
        assert result.bugs_found == 3
        assert result.bugs_fixed == 2  # Two succeeded
        assert len(result.errors) == 1  # One failed

    def test_counts_bugs_across_multiple_iterations(
        self, mock_config, mock_bug_orchestrator, mock_detector,
        sample_pytest_bug, sample_mypy_bug
    ):
        """Should accumulate bug counts across iterations."""
        # First iteration: 2 bugs
        # Second iteration: 1 bug (new one detected after first fixes)
        # Third iteration: clean
        mock_detector.detect_all.side_effect = [
            create_analysis_result([sample_pytest_bug, sample_mypy_bug]),
            create_analysis_result([sample_pytest_bug]),  # New bug after fix
            create_analysis_result([]),  # Clean
        ]

        # Track bug IDs
        bug_ids = ["bug-001", "bug-002", "bug-003"]
        call_count = [0]

        def mock_init_bug(**kwargs):
            result = MagicMock()
            result.success = True
            result.bug_id = bug_ids[min(call_count[0], 2)]
            call_count[0] += 1
            return result

        mock_bug_orchestrator.init_bug.side_effect = mock_init_bug

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )

        result = orchestrator.run(target="src/", max_iterations=5)

        # Verify cumulative counts
        assert result.bugs_found == 3  # 2 + 1
        assert result.bugs_fixed == 3
        assert result.iterations_run == 3
        assert result.success is True


# =============================================================================
# RESULT SERIALIZATION TESTS
# =============================================================================


class TestAutoFixResultSerialization:
    """Tests for AutoFixResult serialization."""

    def test_result_to_dict(self):
        """AutoFixResult should serialize to dictionary correctly."""
        result = AutoFixResult(
            bugs_found=5,
            bugs_fixed=3,
            iterations_run=2,
            success=False,
            checkpoints_triggered=1,
            dry_run=False,
            errors=["Error 1", "Error 2"],
        )

        data = result.to_dict()

        assert data["bugs_found"] == 5
        assert data["bugs_fixed"] == 3
        assert data["iterations_run"] == 2
        assert data["success"] is False
        assert data["checkpoints_triggered"] == 1
        assert data["dry_run"] is False
        assert len(data["errors"]) == 2

    def test_result_from_dict(self):
        """AutoFixResult should deserialize from dictionary correctly."""
        data = {
            "bugs_found": 10,
            "bugs_fixed": 8,
            "iterations_run": 3,
            "success": True,
            "checkpoints_triggered": 2,
            "dry_run": True,
            "errors": ["Error 1"],
        }

        result = AutoFixResult.from_dict(data)

        assert result.bugs_found == 10
        assert result.bugs_fixed == 8
        assert result.iterations_run == 3
        assert result.success is True
        assert result.checkpoints_triggered == 2
        assert result.dry_run is True
        assert len(result.errors) == 1

    def test_result_roundtrip(self):
        """AutoFixResult should survive serialization roundtrip."""
        original = AutoFixResult(
            bugs_found=7,
            bugs_fixed=5,
            iterations_run=4,
            success=False,
            checkpoints_triggered=3,
            dry_run=True,
            errors=["Error A", "Error B", "Error C"],
        )

        data = original.to_dict()
        restored = AutoFixResult.from_dict(data)

        assert restored.bugs_found == original.bugs_found
        assert restored.bugs_fixed == original.bugs_fixed
        assert restored.iterations_run == original.iterations_run
        assert restored.success == original.success
        assert restored.checkpoints_triggered == original.checkpoints_triggered
        assert restored.dry_run == original.dry_run
        assert restored.errors == original.errors

    def test_result_from_dict_with_defaults(self):
        """AutoFixResult should use defaults for missing fields."""
        data = {}

        result = AutoFixResult.from_dict(data)

        assert result.bugs_found == 0
        assert result.bugs_fixed == 0
        assert result.iterations_run == 0
        assert result.success is False
        assert result.checkpoints_triggered == 0
        assert result.dry_run is False
        assert result.errors == []


# =============================================================================
# MAX ITERATIONS TESTS
# =============================================================================


class TestAutoFixMaxIterations:
    """Tests for max iterations limit."""

    def test_stops_at_max_iterations(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Should stop when max iterations reached."""
        # Always return bugs (infinite loop without limit)
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        config = AutoFixConfig(
            enabled=True,
            max_iterations=2,
            auto_approve=True,
            dry_run=False,
        )

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=config,
        )

        result = orchestrator.run(target="tests/")

        # Should stop at 2 iterations
        assert result.iterations_run == 2
        assert result.success is False  # Bugs still remain
        assert mock_detector.detect_all.call_count == 2

    def test_parameter_overrides_config_max_iterations(
        self, mock_config, mock_bug_orchestrator, mock_detector, sample_pytest_bug
    ):
        """Explicit max_iterations should override config."""
        mock_detector.detect_all.return_value = create_analysis_result([sample_pytest_bug])

        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,  # max_iterations=3 in config
        )

        result = orchestrator.run(target="tests/", max_iterations=1)

        # Should stop at 1 iteration (explicit override)
        assert result.iterations_run == 1
        assert mock_detector.detect_all.call_count == 1
