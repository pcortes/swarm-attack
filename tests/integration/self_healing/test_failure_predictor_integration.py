"""Integration tests for FailurePredictor with related modules.

Tests integration with:
- ExecutionState from continuity module
- CoderAgent from agents/coder.py
- ContextMonitor from statusline/

These tests verify the failure predictor works correctly when integrated
with real components from the autopilot system.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, MagicMock, patch

import pytest

from swarm_attack.self_healing.failure_predictor import (
    ExecutionState,
    FailurePredictor,
    FailureType,
    PredictionResult,
    RecoveryAction,
    RecoverySuggestion,
)
from swarm_attack.continuity.ledger import ContinuityLedger
from swarm_attack.statusline.context_monitor import (
    ContextMonitor,
    ContextLevel,
    ContextStatus,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def failure_predictor() -> FailurePredictor:
    """Create a FailurePredictor instance with default settings."""
    return FailurePredictor()


@pytest.fixture
def context_monitor() -> ContextMonitor:
    """Create a ContextMonitor instance with default thresholds."""
    return ContextMonitor()


@pytest.fixture
def continuity_ledger() -> ContinuityLedger:
    """Create a ContinuityLedger for tracking session state."""
    return ContinuityLedger(
        session_id="integration-test-session",
        feature_id="test-feature",
        issue_number=1,
    )


@pytest.fixture
def temp_project():
    """Create a temporary project directory with required structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create required directories
        (tmppath / ".swarm" / "state").mkdir(parents=True)
        (tmppath / ".swarm" / "continuity").mkdir(parents=True)
        (tmppath / "specs" / "test-feature").mkdir(parents=True)
        (tmppath / "tests" / "generated" / "test-feature").mkdir(parents=True)
        (tmppath / ".claude" / "skills" / "coder").mkdir(parents=True)

        # Create coder skill prompt
        (tmppath / ".claude" / "skills" / "coder" / "SKILL.md").write_text(
            "# Coder Skill\nImplement code following TDD."
        )

        # Create spec files
        (tmppath / "specs" / "test-feature" / "spec-final.md").write_text(
            "# Test Feature Spec\nImplement test functionality."
        )
        (tmppath / "specs" / "test-feature" / "issues.json").write_text(
            json.dumps({
                "issues": [
                    {
                        "order": 1,
                        "title": "Test Issue",
                        "body": "Implement the test feature",
                        "labels": ["feature"],
                        "estimated_size": "small",
                    }
                ]
            })
        )

        yield tmppath


@pytest.fixture
def mock_config(temp_project):
    """Create a mock SwarmConfig pointing to temp directory."""
    config = Mock()
    config.repo_root = temp_project
    config.swarm_path = temp_project / ".swarm"
    config.state_path = temp_project / ".swarm" / "state"
    config.specs_path = temp_project / "specs"
    config.skills_path = temp_project / ".claude" / "skills"
    return config


# =============================================================================
# Integration: FailurePredictor + ExecutionState
# =============================================================================


class TestFailurePredictorWithExecutionState:
    """Tests for FailurePredictor integrated with ExecutionState."""

    def test_execution_state_token_usage_triggers_prediction(
        self, failure_predictor: FailurePredictor
    ):
        """Test that high token usage in ExecutionState triggers token exhaustion."""
        state = ExecutionState(
            session_id="test-session",
            actions=[
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "edit_file", "path": "/src/main.py"},
            ],
            errors=[],
            token_usage=88000,
            token_limit=100000,
            confidence_scores=[0.9, 0.85],
        )

        prediction = failure_predictor.predict(state)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION
        assert "Token usage" in prediction.details

    def test_execution_state_error_list_triggers_accumulation(
        self, failure_predictor: FailurePredictor
    ):
        """Test that errors in ExecutionState trigger error accumulation."""
        state = ExecutionState(
            session_id="test-session",
            actions=[
                {"type": "read_file", "path": "/src/a.py"},
                {"type": "edit_file", "path": "/src/b.py"},
                {"type": "run_tests", "command": "pytest"},
            ],
            errors=[
                {"type": "import_error", "message": "Module not found"},
                {"type": "import_error", "message": "Module not found"},
                {"type": "import_error", "message": "Module not found"},
            ],
            token_usage=30000,
            token_limit=100000,
            confidence_scores=[0.9],
        )

        prediction = failure_predictor.predict(state)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.ERROR_ACCUMULATION

    def test_execution_state_confidence_tracking(
        self, failure_predictor: FailurePredictor
    ):
        """Test that confidence scores in ExecutionState trigger confidence drop."""
        state = ExecutionState(
            session_id="test-session",
            actions=[
                {"type": "action1"},
                {"type": "action2"},
                {"type": "action3"},
                {"type": "action4"},
                {"type": "action5"},
            ],
            errors=[],
            token_usage=20000,
            token_limit=100000,
            confidence_scores=[0.95, 0.80, 0.65, 0.50, 0.35],
        )

        prediction = failure_predictor.predict(state)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.CONFIDENCE_DROP

    def test_execution_state_action_tracking_for_stuck_loop(
        self, failure_predictor: FailurePredictor
    ):
        """Test that repeated actions in ExecutionState trigger stuck loop detection."""
        state = ExecutionState(
            session_id="test-session",
            actions=[
                {"type": "read_file", "path": "/src/config.py"},
                {"type": "read_file", "path": "/src/config.py"},
                {"type": "read_file", "path": "/src/config.py"},
                {"type": "read_file", "path": "/src/config.py"},
                {"type": "read_file", "path": "/src/config.py"},
            ],
            errors=[],
            token_usage=15000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.STUCK_LOOP


# =============================================================================
# Integration: FailurePredictor + ContinuityLedger
# =============================================================================


class TestFailurePredictorWithContinuityLedger:
    """Tests for FailurePredictor integrated with ContinuityLedger."""

    def test_ledger_tracks_failure_prediction_as_decision(
        self, failure_predictor: FailurePredictor, continuity_ledger: ContinuityLedger
    ):
        """Test that failure predictions can be recorded in ContinuityLedger."""
        # Create state that will trigger failure
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[{"type": "read_file", "path": "/src/main.py"}] * 6,
            errors=[],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[],
        )

        # Predict failure
        prediction = failure_predictor.predict(state)
        assert prediction.failure_predicted is True

        # Record in ledger
        continuity_ledger.add_decision(
            decision=f"Failure predicted: {prediction.failure_type.value}",
            rationale=prediction.details,
            alternatives=["continue", "manual intervention"],
            impact="high",
            context={
                "failure_type": prediction.failure_type.value,
                "confidence": prediction.confidence,
            },
        )

        # Verify ledger recorded the decision
        assert len(continuity_ledger.decisions) == 1
        decision = continuity_ledger.decisions[0]
        assert "stuck_loop" in decision["decision"]
        assert decision["impact"] == "high"

    def test_ledger_tracks_blocker_from_failure(
        self, failure_predictor: FailurePredictor, continuity_ledger: ContinuityLedger
    ):
        """Test that failure predictions can be recorded as blockers."""
        # Create state that will trigger token exhaustion
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[],
            errors=[],
            token_usage=92000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Record blocker in ledger
        blocker_id = continuity_ledger.add_blocker(
            description=f"Predicted failure: {prediction.failure_type.value}",
            severity="critical" if suggestion.priority == 1 else "medium",
            suggested_resolution=suggestion.reason,
            related_files=[],
        )

        assert len(continuity_ledger.blockers) == 1
        blocker = continuity_ledger.blockers[0]
        assert blocker["severity"] == "critical"
        assert "handoff" in blocker["suggested_resolution"].lower()

    def test_ledger_handoff_notes_from_recovery_suggestion(
        self, failure_predictor: FailurePredictor, continuity_ledger: ContinuityLedger
    ):
        """Test that recovery suggestions can be recorded as handoff notes."""
        # Create state that triggers failure
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[{"type": "read_file", "path": "/x.py"}] * 6,
            errors=[],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Add handoff note
        continuity_ledger.add_handoff_note(
            note=f"Recovery action: {suggestion.action.value} - {suggestion.reason}",
            category="recovery",
            priority="high" if suggestion.priority == 1 else "normal",
        )

        assert len(continuity_ledger.handoff_notes) == 1
        note = continuity_ledger.handoff_notes[0]
        assert note["category"] == "recovery"
        assert "reset_context" in note["note"]

    def test_ledger_serialization_with_failure_context(
        self, failure_predictor: FailurePredictor, continuity_ledger: ContinuityLedger
    ):
        """Test that ledger can serialize/deserialize failure prediction context."""
        # Create and record failure prediction
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[],
            errors=[],
            token_usage=90000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)

        # Store prediction result in ledger context
        continuity_ledger.set_context(
            f"Last prediction: {prediction.failure_type.value if prediction.failure_type else 'none'}, "
            f"confidence: {prediction.confidence}"
        )

        # Serialize and deserialize
        data = continuity_ledger.to_dict()
        restored = ContinuityLedger.from_dict(data)

        assert restored.get_context() == continuity_ledger.get_context()
        assert "token_exhaustion" in restored.get_context().lower()


# =============================================================================
# Integration: FailurePredictor + ContextMonitor
# =============================================================================


class TestFailurePredictorWithContextMonitor:
    """Tests for FailurePredictor integrated with ContextMonitor."""

    def test_context_monitor_critical_triggers_token_exhaustion(
        self, failure_predictor: FailurePredictor, context_monitor: ContextMonitor
    ):
        """Test that CRITICAL context level correlates with token exhaustion prediction."""
        # Check context monitor status
        context_status = context_monitor.check_usage(0.92)
        assert context_status.level == ContextLevel.CRITICAL

        # Create corresponding ExecutionState
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=92000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)

        # Both should indicate critical situation
        assert context_status.should_handoff is True
        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION

    def test_context_monitor_warn_correlates_with_approaching_limit(
        self, failure_predictor: FailurePredictor, context_monitor: ContextMonitor
    ):
        """Test that WARN context level correlates with approaching token limit."""
        # Check context monitor status at 80%
        context_status = context_monitor.check_usage(0.82)
        assert context_status.level == ContextLevel.WARN

        # Create corresponding ExecutionState (below exhaustion threshold)
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=82000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)

        # Context monitor warns but predictor has higher threshold by default
        assert context_status.warning_message is not None
        # Default token_exhaustion_threshold is 0.85, so 82% shouldn't trigger
        assert prediction.failure_predicted is False

    def test_context_monitor_ok_no_failure_predicted(
        self, failure_predictor: FailurePredictor, context_monitor: ContextMonitor
    ):
        """Test that OK context level means no token exhaustion predicted."""
        context_status = context_monitor.check_usage(0.50)
        assert context_status.level == ContextLevel.OK

        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}],
            errors=[],
            token_usage=50000,
            token_limit=100000,
            confidence_scores=[0.9],
        )

        prediction = failure_predictor.predict(state)

        assert context_status.should_handoff is False
        assert prediction.failure_predicted is False

    def test_combined_monitoring_workflow(
        self, failure_predictor: FailurePredictor, context_monitor: ContextMonitor
    ):
        """Test complete monitoring workflow with both components."""
        # Simulate progression through a session
        usage_levels = [0.30, 0.50, 0.70, 0.85, 0.92]
        predictions = []
        statuses = []

        for i, usage in enumerate(usage_levels):
            # Check context monitor
            status = context_monitor.check_usage(usage)
            statuses.append(status)

            # Check failure predictor
            state = ExecutionState(
                session_id="test",
                actions=[{"type": f"action_{j}"} for j in range(i + 1)],
                errors=[],
                token_usage=int(usage * 100000),
                token_limit=100000,
                confidence_scores=[0.9] * (i + 1),
            )
            prediction = failure_predictor.predict(state)
            predictions.append(prediction)

        # Early stages: no failure
        assert not predictions[0].failure_predicted
        assert not predictions[1].failure_predicted
        assert statuses[0].level == ContextLevel.OK
        assert statuses[1].level == ContextLevel.OK

        # Middle stages: warnings begin
        assert statuses[2].level == ContextLevel.INFO
        assert statuses[3].level == ContextLevel.WARN

        # Final stage: both indicate critical
        assert predictions[4].failure_predicted
        assert predictions[4].failure_type == FailureType.TOKEN_EXHAUSTION
        assert statuses[4].level == ContextLevel.CRITICAL
        assert statuses[4].should_handoff

    def test_handoff_command_alignment(
        self, failure_predictor: FailurePredictor, context_monitor: ContextMonitor
    ):
        """Test that handoff suggestions align between components."""
        # Get context monitor handoff suggestion
        context_status = context_monitor.check_usage(0.88)
        assert context_status.should_handoff is True
        assert context_status.handoff_command is not None

        # Get failure predictor recovery suggestion
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=88000,
            token_limit=100000,
            confidence_scores=[],
        )
        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Both should recommend handoff
        assert suggestion.action == RecoveryAction.HANDOFF


# =============================================================================
# Integration: FailurePredictor + CoderAgent (Mocked)
# =============================================================================


class TestFailurePredictorWithCoderAgent:
    """Tests for FailurePredictor integrated with CoderAgent workflows."""

    def test_coder_agent_state_tracking(
        self, failure_predictor: FailurePredictor, mock_config, temp_project
    ):
        """Test that CoderAgent actions can be tracked for failure prediction."""
        # Simulate CoderAgent workflow actions
        actions = [
            {"type": "read_file", "path": "specs/test-feature/spec-final.md"},
            {"type": "read_file", "path": "specs/test-feature/issues.json"},
            {"type": "write_file", "path": "tests/generated/test-feature/test_issue_1.py"},
            {"type": "write_file", "path": "src/feature.py"},
            {"type": "run_tests", "command": "pytest tests/"},
        ]

        state = ExecutionState(
            session_id="coder-session",
            actions=actions,
            errors=[],
            token_usage=25000,
            token_limit=100000,
            confidence_scores=[0.95, 0.92, 0.90, 0.88, 0.85],
        )

        prediction = failure_predictor.predict(state)

        # Normal workflow should not trigger failure
        assert prediction.failure_predicted is False

    def test_coder_agent_stuck_in_test_loop(
        self, failure_predictor: FailurePredictor
    ):
        """Test detection of CoderAgent stuck in test-fix loop."""
        # Simulate stuck in repeated test/fix cycle
        actions = [
            {"type": "run_tests", "path": "tests/"},
            {"type": "edit_file", "path": "src/feature.py"},
            {"type": "run_tests", "path": "tests/"},
            {"type": "edit_file", "path": "src/feature.py"},
            {"type": "run_tests", "path": "tests/"},
            {"type": "edit_file", "path": "src/feature.py"},
        ]

        state = ExecutionState(
            session_id="coder-session",
            actions=actions,
            errors=[
                {"type": "test_failure", "test": "test_something"},
                {"type": "test_failure", "test": "test_something"},
                {"type": "test_failure", "test": "test_something"},
            ],
            token_usage=40000,
            token_limit=100000,
            confidence_scores=[0.9, 0.8, 0.7, 0.6, 0.5, 0.4],
        )

        prediction = failure_predictor.predict(state)

        # Should detect failure pattern
        assert prediction.failure_predicted is True
        # Either stuck loop (oscillating) or confidence drop should be detected
        assert prediction.failure_type in [
            FailureType.STUCK_LOOP,
            FailureType.CONFIDENCE_DROP,
            FailureType.ERROR_ACCUMULATION,
        ]

    def test_coder_agent_context_exhaustion(
        self, failure_predictor: FailurePredictor
    ):
        """Test detection of CoderAgent approaching context limit."""
        # Simulate long session with large files read
        state = ExecutionState(
            session_id="coder-session",
            actions=[
                {"type": "read_file", "path": f"/src/module_{i}.py"}
                for i in range(20)
            ],
            errors=[],
            token_usage=90000,
            token_limit=100000,
            confidence_scores=[0.9] * 20,
        )

        prediction = failure_predictor.predict(state)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION

        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.HANDOFF

    def test_coder_agent_import_errors_accumulation(
        self, failure_predictor: FailurePredictor
    ):
        """Test detection of accumulated import errors in CoderAgent session."""
        state = ExecutionState(
            session_id="coder-session",
            actions=[
                {"type": "write_file", "path": "src/feature.py"},
                {"type": "run_tests", "path": "tests/"},
                {"type": "edit_file", "path": "src/feature.py"},
                {"type": "run_tests", "path": "tests/"},
            ],
            errors=[
                {"type": "ImportError", "message": "No module named 'missing_dep'"},
                {"type": "ImportError", "message": "No module named 'missing_dep'"},
                {"type": "ImportError", "message": "No module named 'missing_dep'"},
            ],
            token_usage=35000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.ERROR_ACCUMULATION

        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.RETRY

    def test_recovery_suggestion_for_coder_stuck_loop(
        self, failure_predictor: FailurePredictor
    ):
        """Test that stuck loop recovery suggests context reset."""
        state = ExecutionState(
            session_id="coder-session",
            actions=[
                {"type": "edit_file", "path": "src/feature.py", "change": "fix"},
                {"type": "edit_file", "path": "src/feature.py", "change": "fix"},
                {"type": "edit_file", "path": "src/feature.py", "change": "fix"},
                {"type": "edit_file", "path": "src/feature.py", "change": "fix"},
                {"type": "edit_file", "path": "src/feature.py", "change": "fix"},
            ],
            errors=[],
            token_usage=30000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.STUCK_LOOP
        assert suggestion.action == RecoveryAction.RESET_CONTEXT


# =============================================================================
# Integration: Full Workflow Tests
# =============================================================================


class TestFullIntegrationWorkflow:
    """Full integration workflow tests combining all components."""

    def test_complete_failure_detection_to_handoff_workflow(
        self,
        failure_predictor: FailurePredictor,
        context_monitor: ContextMonitor,
        continuity_ledger: ContinuityLedger,
    ):
        """Test complete workflow from failure detection to handoff preparation."""
        # Step 1: Monitor context usage
        usage = 0.91
        context_status = context_monitor.check_usage(usage)
        assert context_status.level == ContextLevel.CRITICAL

        # Step 2: Create execution state
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[{"type": "read_file", "path": "/src/main.py"}] * 10,
            errors=[],
            token_usage=int(usage * 100000),
            token_limit=100000,
            confidence_scores=[0.9] * 10,
        )

        # Step 3: Predict failure
        prediction = failure_predictor.predict(state)
        assert prediction.failure_predicted is True

        # Step 4: Get recovery suggestion
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.HANDOFF

        # Step 5: Record in ledger for handoff
        continuity_ledger.add_decision(
            decision=f"Initiating handoff due to {prediction.failure_type.value}",
            rationale=prediction.details,
            impact="high",
        )

        continuity_ledger.add_handoff_note(
            note=f"Handoff required: {suggestion.reason}",
            category="recovery",
            priority="high",
        )

        # Step 6: Verify ledger is ready for handoff
        summary = continuity_ledger.get_summary()
        assert summary["decisions"]["total"] == 1
        assert summary["handoff_notes"]["total"] == 1

        # Step 7: Verify injection context includes handoff info
        injection = continuity_ledger.get_injection_context()
        assert "handoff" in injection.lower()

    def test_ledger_persistence_with_failure_state(
        self,
        failure_predictor: FailurePredictor,
        continuity_ledger: ContinuityLedger,
        temp_project: Path,
    ):
        """Test that failure state persists correctly in ledger."""
        # Create failure state
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[{"type": "same_action", "path": "/x.py"}] * 6,
            errors=[],
            token_usage=50000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Record blocker
        continuity_ledger.add_blocker(
            description=f"Failure: {prediction.failure_type.value}",
            severity="high",
            suggested_resolution=suggestion.reason,
        )

        # Persist ledger
        ledger_path = temp_project / ".swarm" / "continuity" / "session.json"
        continuity_ledger.save(ledger_path)

        # Reload and verify
        loaded = ContinuityLedger.load(ledger_path)
        assert loaded is not None
        assert len(loaded.blockers) == 1
        assert "stuck_loop" in loaded.blockers[0]["description"]

    def test_session_continuation_after_failure(
        self,
        failure_predictor: FailurePredictor,
        continuity_ledger: ContinuityLedger,
    ):
        """Test session continuation from a failed state."""
        # Original session encountered failure
        state = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[],
            errors=[],
            token_usage=95000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Add handoff note
        continuity_ledger.add_handoff_note(
            note=f"Session ended due to {prediction.failure_type.value}. "
            f"Recommendation: {suggestion.action.value}",
            category="recovery",
            priority="high",
        )

        # Add goal (incomplete)
        continuity_ledger.add_goal(
            description="Implement test feature",
            priority="high",
            status="in_progress",
        )

        # Continue to new session
        new_ledger = ContinuityLedger.continue_from(continuity_ledger)

        # Verify continuation
        assert new_ledger.parent_session_id == continuity_ledger.session_id
        assert len(new_ledger.prior_handoff_notes) == 1
        assert "token_exhaustion" in new_ledger.prior_handoff_notes[0]["note"]
        # Incomplete goals should carry over
        assert len(new_ledger.goals) == 1
        assert new_ledger.goals[0]["description"] == "Implement test feature"

    def test_context_monitor_and_predictor_threshold_alignment(
        self,
        failure_predictor: FailurePredictor,
        context_monitor: ContextMonitor,
    ):
        """Test that custom thresholds align between context monitor and predictor."""
        # Create aligned components
        aligned_monitor = ContextMonitor(
            warn_threshold=0.80,
            critical_threshold=0.85,
            handoff_threshold=0.85,
        )
        aligned_predictor = FailurePredictor(
            token_exhaustion_threshold=0.85,
        )

        # Test at threshold boundary
        usage = 0.85
        context_status = aligned_monitor.check_usage(usage)

        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=85000,
            token_limit=100000,
            confidence_scores=[],
        )
        prediction = aligned_predictor.predict(state)

        # Both should trigger at exactly 85%
        assert context_status.level == ContextLevel.CRITICAL
        assert context_status.should_handoff is True
        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestIntegrationEdgeCases:
    """Edge case tests for integration scenarios."""

    def test_empty_ledger_with_failure_prediction(
        self, failure_predictor: FailurePredictor
    ):
        """Test adding failure prediction to fresh ledger."""
        fresh_ledger = ContinuityLedger(session_id="fresh-session")

        state = ExecutionState(
            session_id="fresh-session",
            actions=[],
            errors=[],
            token_usage=95000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)

        # Should work with fresh ledger
        fresh_ledger.add_decision(
            decision=f"First decision: {prediction.failure_type.value}",
            rationale=prediction.details,
        )

        assert len(fresh_ledger.decisions) == 1

    def test_multiple_failure_types_in_single_session(
        self,
        failure_predictor: FailurePredictor,
        continuity_ledger: ContinuityLedger,
    ):
        """Test tracking multiple failure types across a session."""
        # First failure: stuck loop
        state1 = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[{"type": "same", "path": "/x.py"}] * 6,
            errors=[],
            token_usage=30000,
            token_limit=100000,
            confidence_scores=[],
        )
        pred1 = failure_predictor.predict(state1)
        continuity_ledger.add_blocker(
            description=f"Failure 1: {pred1.failure_type.value}",
            severity="medium",
        )

        # Second failure: token exhaustion (after "recovery")
        state2 = ExecutionState(
            session_id=continuity_ledger.session_id,
            actions=[{"type": "different"}] * 10,
            errors=[],
            token_usage=92000,
            token_limit=100000,
            confidence_scores=[],
        )
        pred2 = failure_predictor.predict(state2)
        continuity_ledger.add_blocker(
            description=f"Failure 2: {pred2.failure_type.value}",
            severity="critical",
        )

        # Verify both recorded
        assert len(continuity_ledger.blockers) == 2
        assert "stuck_loop" in continuity_ledger.blockers[0]["description"]
        assert "token_exhaustion" in continuity_ledger.blockers[1]["description"]

    def test_context_monitor_statusline_with_prediction(
        self,
        failure_predictor: FailurePredictor,
        context_monitor: ContextMonitor,
    ):
        """Test generating statusline data alongside failure prediction."""
        # Use 92% which is above critical threshold (0.90 default)
        usage = 0.92
        statusline_data = context_monitor.get_statusline_data(usage)

        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=int(usage * 100000),
            token_limit=100000,
            confidence_scores=[],
        )
        prediction = failure_predictor.predict(state)

        # Both provide useful status information
        assert statusline_data["level"] == "CRITICAL"
        assert statusline_data["should_handoff"] is True
        assert "handoff suggested" in statusline_data["formatted"]

        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION

    def test_recovery_action_serialization(
        self, failure_predictor: FailurePredictor
    ):
        """Test that recovery suggestions serialize correctly for storage."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "same", "path": "/x.py"}] * 6,
            errors=[],
            token_usage=30000,
            token_limit=100000,
            confidence_scores=[],
        )

        prediction = failure_predictor.predict(state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Serialize
        pred_dict = prediction.to_dict()
        sugg_dict = suggestion.to_dict()

        # Verify serialization
        assert pred_dict["failure_type"] == "stuck_loop"
        assert pred_dict["failure_predicted"] is True
        assert sugg_dict["action"] == "reset_context"
        assert sugg_dict["priority"] == 2

        # Can be stored in JSON
        json_str = json.dumps({"prediction": pred_dict, "suggestion": sugg_dict})
        restored = json.loads(json_str)
        assert restored["prediction"]["failure_type"] == "stuck_loop"
