"""Tests for AutoFixOrchestrator following TDD approach.

Tests cover the auto-fix core loop:
- Detection-fix loop logic
- Bug creation from static findings
- Auto-approve handling
- Critical bug checkpoints
- Dry-run mode
- Max iterations limit
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

from swarm_attack.static_analysis.models import StaticBugReport, StaticAnalysisResult


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify AutoFixOrchestrator can be imported."""

    def test_can_import_auto_fix_orchestrator(self):
        """Should be able to import AutoFixOrchestrator class."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        assert AutoFixOrchestrator is not None

    def test_can_import_auto_fix_result(self):
        """Should be able to import AutoFixResult dataclass."""
        from swarm_attack.qa.auto_fix import AutoFixResult
        assert AutoFixResult is not None


# =============================================================================
# AutoFixResult TESTS
# =============================================================================


class TestAutoFixResult:
    """Tests for AutoFixResult dataclass."""

    def test_default_values(self):
        """Should have sensible default values."""
        from swarm_attack.qa.auto_fix import AutoFixResult
        result = AutoFixResult()
        assert result.bugs_found == 0
        assert result.bugs_fixed == 0
        assert result.iterations_run == 0
        assert result.success is False
        assert result.checkpoints_triggered == 0
        assert result.dry_run is False
        assert result.errors == []

    def test_to_dict(self):
        """Should serialize to dictionary."""
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

    def test_from_dict(self):
        """Should deserialize from dictionary."""
        from swarm_attack.qa.auto_fix import AutoFixResult
        data = {
            "bugs_found": 10,
            "bugs_fixed": 7,
            "iterations_run": 3,
            "success": True,
            "checkpoints_triggered": 2,
            "dry_run": True,
            "errors": ["error1"],
        }
        result = AutoFixResult.from_dict(data)
        assert result.bugs_found == 10
        assert result.bugs_fixed == 7
        assert result.iterations_run == 3
        assert result.success is True
        assert result.checkpoints_triggered == 2
        assert result.dry_run is True
        assert result.errors == ["error1"]

    def test_from_dict_with_missing_keys(self):
        """Should handle missing keys with defaults."""
        from swarm_attack.qa.auto_fix import AutoFixResult
        result = AutoFixResult.from_dict({})
        assert result.bugs_found == 0
        assert result.success is False


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestAutoFixOrchestratorInit:
    """Tests for AutoFixOrchestrator initialization."""

    @pytest.fixture
    def mock_bug_orchestrator(self):
        return MagicMock()

    @pytest.fixture
    def mock_detector(self):
        return MagicMock()

    @pytest.fixture
    def mock_config(self):
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = False
        config.dry_run = False
        return config

    def test_init_with_required_params(self, mock_bug_orchestrator, mock_detector, mock_config):
        """Should initialize with required parameters."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )
        assert orchestrator._bug_orchestrator == mock_bug_orchestrator
        assert orchestrator._detector == mock_detector
        assert orchestrator._config == mock_config

    def test_checkpoint_callback_initially_none(self, mock_bug_orchestrator, mock_detector, mock_config):
        """Should have no checkpoint callback by default."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )
        assert orchestrator._checkpoint_callback is None

    def test_set_checkpoint_callback(self, mock_bug_orchestrator, mock_detector, mock_config):
        """Should accept a checkpoint callback."""
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        orchestrator = AutoFixOrchestrator(
            bug_orchestrator=mock_bug_orchestrator,
            detector=mock_detector,
            config=mock_config,
        )
        callback = MagicMock(return_value=True)
        orchestrator.set_checkpoint_callback(callback)
        assert orchestrator._checkpoint_callback == callback


# =============================================================================
# _create_bug_from_finding() TESTS
# =============================================================================


class TestCreateBugFromFinding:
    """Tests for _create_bug_from_finding method."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = False
        config.dry_run = False
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_creates_bug_from_pytest_finding(self, orchestrator):
        """Should create bug from pytest finding with test_path."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test_api.py",
            line_number=42,
            error_code="AssertionError",
            message="Expected 200, got 500",
            severity="critical",
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-expected-200-got-500-12345",
        )

        bug_id = orchestrator._create_bug_from_finding(bug)

        assert bug_id == "bug-expected-200-got-500-12345"
        orchestrator._bug_orchestrator.init_bug.assert_called_once()
        call_kwargs = orchestrator._bug_orchestrator.init_bug.call_args[1]
        assert "test_path" in call_kwargs
        assert call_kwargs["test_path"] == "tests/test_api.py"

    def test_creates_bug_from_mypy_finding_no_test_path(self, orchestrator):
        """Should create bug from mypy finding without test_path."""
        bug = StaticBugReport(
            source="mypy",
            file_path="src/api.py",
            line_number=10,
            error_code="arg-type",
            message="Argument 1 has incompatible type",
            severity="moderate",
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-arg-type-12345",
        )

        bug_id = orchestrator._create_bug_from_finding(bug)

        assert bug_id is not None
        call_kwargs = orchestrator._bug_orchestrator.init_bug.call_args[1]
        assert call_kwargs.get("test_path") is None

    def test_returns_none_on_failure(self, orchestrator):
        """Should return None if bug creation fails."""
        bug = StaticBugReport(
            source="ruff",
            file_path="src/api.py",
            line_number=5,
            error_code="F401",
            message="Module imported but unused",
            severity="minor",
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=False,
            error="Duplicate bug",
        )

        bug_id = orchestrator._create_bug_from_finding(bug)

        assert bug_id is None

    def test_description_includes_error_details(self, orchestrator):
        """Should include error details in description."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test_foo.py",
            line_number=100,
            error_code="TypeError",
            message="'NoneType' object is not subscriptable",
            severity="critical",
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-test-12345",
        )

        orchestrator._create_bug_from_finding(bug)

        call_kwargs = orchestrator._bug_orchestrator.init_bug.call_args[1]
        desc = call_kwargs["description"]
        assert "PYTEST" in desc
        assert "TypeError" in desc
        assert "'NoneType' object is not subscriptable" in desc
        assert "tests/test_foo.py:100" in desc


# =============================================================================
# run() METHOD - BASIC TESTS
# =============================================================================


class TestRunBasic:
    """Basic tests for the run() method."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = True
        config.dry_run = False
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_returns_success_when_no_bugs(self, orchestrator):
        """Should return success=True when no bugs are found."""
        from swarm_attack.qa.auto_fix import AutoFixResult
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest", "mypy", "ruff"],
            tools_skipped=[],
        )

        result = orchestrator.run(target="tests/")

        assert result.success is True
        assert result.bugs_found == 0
        assert result.iterations_run == 1

    def test_uses_config_defaults(self, orchestrator):
        """Should use config defaults when params not provided."""
        from swarm_attack.qa.auto_fix import AutoFixResult
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        result = orchestrator.run()

        # Should have used config.max_iterations (3) and config.auto_approve (True)
        assert result.success is True

    def test_respects_max_iterations(self, orchestrator):
        """Should stop after max_iterations even with remaining bugs."""
        from swarm_attack.qa.auto_fix import AutoFixResult

        # Always return a bug to force max iterations
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(success=False)

        result = orchestrator.run(max_iterations=2)

        assert result.iterations_run == 2
        assert result.success is False

    def test_counts_bugs_found_across_iterations(self, orchestrator):
        """Should count total bugs found across all iterations."""
        from swarm_attack.qa.auto_fix import AutoFixResult

        bug1 = StaticBugReport(
            source="pytest",
            file_path="tests/test1.py",
            line_number=1,
            error_code="AssertionError",
            message="Test 1 failed",
            severity="moderate",
        )
        bug2 = StaticBugReport(
            source="pytest",
            file_path="tests/test2.py",
            line_number=2,
            error_code="AssertionError",
            message="Test 2 failed",
            severity="moderate",
        )

        # First iteration: 2 bugs, second: 0 (clean)
        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug1, bug2], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        result = orchestrator.run()

        assert result.bugs_found == 2
        assert result.success is True


# =============================================================================
# run() METHOD - FULL PIPELINE TESTS
# =============================================================================


class TestRunFullPipeline:
    """Tests for complete detection-fix pipeline."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = True
        config.dry_run = False
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_calls_analyze_for_each_bug(self, orchestrator):
        """Should call analyze for each detected bug."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        orchestrator.run()

        orchestrator._bug_orchestrator.analyze.assert_called_with("bug-12345")

    def test_calls_approve_when_auto_approve(self, orchestrator):
        """Should call approve when auto_approve=True."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        orchestrator.run(auto_approve=True)

        orchestrator._bug_orchestrator.approve.assert_called_with("bug-12345")

    def test_skips_approve_when_not_auto_approve(self, orchestrator):
        """Should skip approve when auto_approve=False."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)

        orchestrator.run(max_iterations=1, auto_approve=False)

        orchestrator._bug_orchestrator.approve.assert_not_called()
        orchestrator._bug_orchestrator.fix.assert_not_called()

    def test_calls_fix_after_approve(self, orchestrator):
        """Should call fix after successful approve."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        orchestrator.run(auto_approve=True)

        orchestrator._bug_orchestrator.fix.assert_called_with("bug-12345")

    def test_counts_bugs_fixed(self, orchestrator):
        """Should count successfully fixed bugs."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        result = orchestrator.run(auto_approve=True)

        assert result.bugs_fixed == 1


# =============================================================================
# DRY RUN TESTS
# =============================================================================


class TestDryRun:
    """Tests for dry_run mode."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = True
        config.dry_run = True
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_dry_run_skips_analyze(self, orchestrator):
        """Should skip analyze in dry_run mode."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )

        orchestrator.run(max_iterations=1, dry_run=True)

        orchestrator._bug_orchestrator.analyze.assert_not_called()

    def test_dry_run_skips_fix(self, orchestrator):
        """Should skip fix in dry_run mode."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )

        orchestrator.run(max_iterations=1, dry_run=True)

        orchestrator._bug_orchestrator.fix.assert_not_called()

    def test_dry_run_sets_result_flag(self, orchestrator):
        """Should set dry_run flag in result."""
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        result = orchestrator.run(dry_run=True)

        assert result.dry_run is True


# =============================================================================
# CRITICAL BUG CHECKPOINT TESTS
# =============================================================================


class TestCriticalBugCheckpoint:
    """Tests for critical bug checkpoint behavior."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = False
        config.dry_run = False
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_critical_bug_triggers_checkpoint(self, orchestrator):
        """Should trigger checkpoint for critical bugs when auto_approve=False."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="TypeError",
            message="Critical error",
            severity="critical",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        result = orchestrator.run(max_iterations=1, auto_approve=False)

        assert result.checkpoints_triggered == 1

    def test_checkpoint_callback_called(self, orchestrator):
        """Should call checkpoint callback for critical bugs."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="TypeError",
            message="Critical error",
            severity="critical",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        callback = MagicMock(return_value=True)
        orchestrator.set_checkpoint_callback(callback)
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)

        orchestrator.run(max_iterations=1, auto_approve=False)

        callback.assert_called_once_with(bug)

    def test_checkpoint_callback_can_skip_bug(self, orchestrator):
        """Should skip bug if checkpoint callback returns False."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="TypeError",
            message="Critical error",
            severity="critical",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        callback = MagicMock(return_value=False)  # Reject
        orchestrator.set_checkpoint_callback(callback)

        orchestrator.run(max_iterations=1, auto_approve=False)

        # Should not have called init_bug since callback rejected
        orchestrator._bug_orchestrator.init_bug.assert_not_called()

    def test_checkpoint_callback_can_proceed(self, orchestrator):
        """Should proceed if checkpoint callback returns True."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="TypeError",
            message="Critical error",
            severity="critical",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        callback = MagicMock(return_value=True)  # Approve
        orchestrator.set_checkpoint_callback(callback)
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)

        orchestrator.run(max_iterations=1, auto_approve=False)

        # Should have called init_bug since callback approved
        orchestrator._bug_orchestrator.init_bug.assert_called_once()

    def test_critical_skipped_without_callback(self, orchestrator):
        """Should skip critical bugs without callback when auto_approve=False."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="TypeError",
            message="Critical error",
            severity="critical",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        # No callback set

        orchestrator.run(max_iterations=1, auto_approve=False)

        # Should not have called init_bug - skipped due to no callback
        orchestrator._bug_orchestrator.init_bug.assert_not_called()

    def test_auto_approve_bypasses_checkpoint(self, orchestrator):
        """Should bypass checkpoint when auto_approve=True."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="TypeError",
            message="Critical error",
            severity="critical",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        result = orchestrator.run(auto_approve=True)

        # Should have processed the bug even though it's critical
        assert result.checkpoints_triggered == 0
        orchestrator._bug_orchestrator.fix.assert_called_once()


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling during fix loop."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = True
        config.dry_run = False
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_tracks_init_bug_failures(self, orchestrator):
        """Should track errors when init_bug fails."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=False,
            error="Duplicate bug",
        )

        result = orchestrator.run(max_iterations=1)

        assert len(result.errors) == 1
        assert "Failed to create bug" in result.errors[0]

    def test_tracks_analyze_failures(self, orchestrator):
        """Should track errors when analyze fails."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(
            success=False,
            error="Reproduction failed",
        )

        result = orchestrator.run(max_iterations=1)

        assert len(result.errors) == 1
        assert "Analysis failed" in result.errors[0]

    def test_tracks_fix_failures(self, orchestrator):
        """Should track errors when fix fails."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(
            success=False,
            error="Tests still failing",
        )

        result = orchestrator.run(max_iterations=1)

        assert len(result.errors) == 1
        assert "Fix failed" in result.errors[0]

    def test_handles_analyze_exception(self, orchestrator):
        """Should handle exceptions during analyze."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.side_effect = Exception("Network error")

        result = orchestrator.run(max_iterations=1)

        assert len(result.errors) == 1
        assert "exception" in result.errors[0].lower()

    def test_handles_fix_exception(self, orchestrator):
        """Should handle exceptions during fix."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.side_effect = Exception("Disk full")

        result = orchestrator.run(max_iterations=1)

        assert len(result.errors) == 1
        assert "exception" in result.errors[0].lower()


# =============================================================================
# LOOP TERMINATION TESTS
# =============================================================================


class TestLoopTermination:
    """Tests for loop termination conditions."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 5
        config.auto_approve = True
        config.dry_run = False
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_terminates_when_clean(self, orchestrator):
        """Should terminate immediately when codebase is clean."""
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest", "mypy"],
            tools_skipped=[],
        )

        result = orchestrator.run()

        assert result.success is True
        assert result.iterations_run == 1
        # Should only call detect once
        assert orchestrator._detector.detect_all.call_count == 1

    def test_terminates_after_fixing_all_bugs(self, orchestrator):
        """Should terminate after all bugs are fixed."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        call_count = [0]
        def detect_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_side_effect
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        result = orchestrator.run()

        assert result.success is True
        assert result.iterations_run == 2
        assert result.bugs_fixed == 1

    def test_terminates_at_max_iterations(self, orchestrator):
        """Should terminate at max_iterations with remaining bugs."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        # Always return a bug that fails to fix
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(
            success=False,
            error="Still failing",
        )

        result = orchestrator.run(max_iterations=3)

        assert result.success is False
        assert result.iterations_run == 3


# =============================================================================
# WATCH MODE TESTS
# =============================================================================


class TestWatchMode:
    """Tests for watch() method - file watching with polling."""

    @pytest.fixture
    def orchestrator(self):
        from swarm_attack.qa.auto_fix import AutoFixOrchestrator
        bug_orch = MagicMock()
        detector = MagicMock()
        config = MagicMock()
        config.max_iterations = 3
        config.auto_approve = True
        config.dry_run = False
        config.watch_poll_seconds = 5
        return AutoFixOrchestrator(bug_orch, detector, config)

    def test_watch_method_exists(self, orchestrator):
        """Should have a watch() method."""
        assert hasattr(orchestrator, "watch")
        assert callable(orchestrator.watch)

    def test_watch_accepts_expected_parameters(self, orchestrator):
        """Should accept target, max_iterations, and auto_approve parameters."""
        import inspect
        sig = inspect.signature(orchestrator.watch)
        params = list(sig.parameters.keys())
        assert "target" in params
        assert "max_iterations" in params
        assert "auto_approve" in params

    def test_watch_stops_on_keyboard_interrupt(self, orchestrator):
        """Should handle KeyboardInterrupt gracefully (Ctrl+C)."""
        # Make detector raise KeyboardInterrupt on second call
        call_count = [0]
        def interrupt_after_first(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt()
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = interrupt_after_first

        # Should not raise, should exit gracefully
        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=KeyboardInterrupt):
            orchestrator.watch(target="tests/", max_iterations=1)

        # Verify it ran at least once
        assert call_count[0] >= 1

    def test_watch_uses_config_poll_seconds(self, orchestrator):
        """Should use config.watch_poll_seconds for polling interval."""
        orchestrator._detector.detect_all.return_value = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=[],
        )

        # Make it stop after first iteration
        call_count = [0]
        def stop_after_one(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt()
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = stop_after_one

        sleep_args = []
        def capture_sleep(seconds):
            sleep_args.append(seconds)
            raise KeyboardInterrupt()

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=capture_sleep):
            orchestrator.watch(target="tests/", max_iterations=1)

        # Should have called sleep with config.watch_poll_seconds (5)
        assert 5 in sleep_args

    def test_watch_detects_file_changes(self, orchestrator, tmp_path):
        """Should detect file changes and run detection when files change."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("# initial content")

        call_count = [0]
        def detect_and_track(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 2:
                raise KeyboardInterrupt()
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_and_track

        sleep_count = [0]
        def modify_file_on_sleep(seconds):
            sleep_count[0] += 1
            if call_count[0] == 1:
                test_file.write_text("# modified content")
            # Safety: exit after a few sleep calls to prevent infinite loop
            if sleep_count[0] > 5:
                raise KeyboardInterrupt()

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=modify_file_on_sleep):
            orchestrator.watch(target=str(tmp_path), max_iterations=1)

        # Should have called detect_all at least twice (initial + after change)
        assert call_count[0] >= 2

    def test_watch_runs_detection_fix_loop_on_change(self, orchestrator, tmp_path):
        """Should run the detection-fix loop when changes detected."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("# initial content")

        bug = StaticBugReport(
            source="pytest",
            file_path=str(test_file),
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        detect_count = [0]
        def detect_with_bug(*args, **kwargs):
            detect_count[0] += 1
            if detect_count[0] > 2:
                raise KeyboardInterrupt()
            # Return bug on first detection, clean on second
            if detect_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_with_bug
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        sleep_count = [0]
        def sleep_with_exit(seconds):
            sleep_count[0] += 1
            if sleep_count[0] > 3:
                raise KeyboardInterrupt()

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=sleep_with_exit):
            orchestrator.watch(target=str(tmp_path), max_iterations=1, auto_approve=True)

        # Should have called the fix pipeline
        orchestrator._bug_orchestrator.fix.assert_called()

    def test_watch_skips_when_no_file_changes(self, orchestrator, tmp_path):
        """Should skip detection loop when no files have changed."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("# initial content")

        call_count = [0]
        def track_calls(*args, **kwargs):
            call_count[0] += 1
            # Only called once initially, then not called again since no changes
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = track_calls

        sleep_count = [0]
        def sleep_and_exit(seconds):
            sleep_count[0] += 1
            # After a few polls with no changes, exit
            if sleep_count[0] >= 2:
                raise KeyboardInterrupt()

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=sleep_and_exit):
            orchestrator.watch(target=str(tmp_path), max_iterations=1)

        # First call is initial, subsequent calls only if files changed
        # With no file changes, should only have initial call
        assert call_count[0] == 1

    def test_watch_tracks_file_mtimes(self, orchestrator, tmp_path):
        """Should track file modification times to detect changes."""
        test_file = tmp_path / "test_example.py"
        test_file.write_text("# initial content")
        initial_mtime = test_file.stat().st_mtime

        detect_count = [0]

        def detect_and_count(*args, **kwargs):
            detect_count[0] += 1
            if detect_count[0] > 2:
                raise KeyboardInterrupt()
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_and_count

        import os
        sleep_count = [0]

        def modify_file_during_sleep(seconds):
            sleep_count[0] += 1
            if detect_count[0] == 1 and sleep_count[0] == 1:
                # Modify file to trigger change detection
                # Use os.utime to ensure mtime changes
                test_file.write_text("# modified content")
                # Force different mtime
                os.utime(str(test_file), (initial_mtime + 10, initial_mtime + 10))
            # Safety exit
            if sleep_count[0] > 5:
                raise KeyboardInterrupt()

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=modify_file_during_sleep):
            orchestrator.watch(target=str(tmp_path), max_iterations=1)

        # Should have detected the file change
        assert detect_count[0] >= 2

    def test_watch_uses_target_parameter(self, orchestrator):
        """Should pass target parameter to detection."""
        call_count = [0]
        def track_target(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt()
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = track_target

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=KeyboardInterrupt):
            orchestrator.watch(target="src/api/", max_iterations=1)

        # The run() method should have been called with target
        # We can verify the detector was called
        orchestrator._detector.detect_all.assert_called()

    def test_watch_defaults_max_iterations_from_config(self, orchestrator):
        """Should use config.max_iterations as default."""
        orchestrator._config.max_iterations = 5

        call_count = [0]
        def stop_after_one(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt()
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = stop_after_one

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=KeyboardInterrupt):
            # Don't pass max_iterations, should use config default
            orchestrator.watch(target="tests/")

        # Should have used config value
        assert call_count[0] >= 1

    def test_watch_defaults_auto_approve_from_config(self, orchestrator):
        """Should use config.auto_approve as default."""
        orchestrator._config.auto_approve = True

        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        call_count = [0]
        def detect_once(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt()
            if call_count[0] == 1:
                return StaticAnalysisResult(bugs=[bug], tools_run=["pytest"], tools_skipped=[])
            return StaticAnalysisResult(bugs=[], tools_run=["pytest"], tools_skipped=[])

        orchestrator._detector.detect_all.side_effect = detect_once
        orchestrator._bug_orchestrator.init_bug.return_value = MagicMock(
            success=True,
            bug_id="bug-12345",
        )
        orchestrator._bug_orchestrator.analyze.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.approve.return_value = MagicMock(success=True)
        orchestrator._bug_orchestrator.fix.return_value = MagicMock(success=True)

        with patch("swarm_attack.qa.auto_fix.time.sleep", side_effect=KeyboardInterrupt):
            orchestrator.watch(target="tests/")  # Don't pass auto_approve

        # Should have called approve (using config.auto_approve=True)
        orchestrator._bug_orchestrator.approve.assert_called()
