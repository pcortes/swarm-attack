"""Unit tests for FailurePredictor.

Tests for:
- Stuck loop detection (repeated similar actions)
- Token exhaustion detection (context limit approaching)
- Confidence drop detection (model uncertainty increasing)
- Error accumulation detection (multiple recoverable errors)
- Recovery suggestion generation
- Edge cases (empty state, single action, etc.)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pytest

from swarm_attack.self_healing.failure_predictor import (
    ExecutionState,
    PredictionResult,
    RecoverySuggestion,
    FailurePredictor,
    FailureType,
    RecoveryAction,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def predictor() -> FailurePredictor:
    """Create a FailurePredictor instance."""
    return FailurePredictor()


@pytest.fixture
def empty_state() -> ExecutionState:
    """Create an empty execution state."""
    return ExecutionState(
        session_id="test-session",
        actions=[],
        errors=[],
        token_usage=0,
        token_limit=100000,
        confidence_scores=[],
    )


@pytest.fixture
def normal_state() -> ExecutionState:
    """Create a normal execution state with no issues."""
    return ExecutionState(
        session_id="test-session",
        actions=[
            {"type": "read_file", "path": "/src/main.py", "timestamp": "2025-01-06T10:00:00Z"},
            {"type": "edit_file", "path": "/src/main.py", "timestamp": "2025-01-06T10:01:00Z"},
            {"type": "run_tests", "command": "pytest", "timestamp": "2025-01-06T10:02:00Z"},
        ],
        errors=[],
        token_usage=30000,
        token_limit=100000,
        confidence_scores=[0.95, 0.92, 0.90],
    )


# =============================================================================
# ExecutionState Tests
# =============================================================================


class TestExecutionState:
    """Tests for ExecutionState data class."""

    def test_create_execution_state(self):
        """Test creating an ExecutionState with all fields."""
        state = ExecutionState(
            session_id="sess_123",
            actions=[{"type": "test"}],
            errors=["error1"],
            token_usage=50000,
            token_limit=100000,
            confidence_scores=[0.9, 0.85],
        )

        assert state.session_id == "sess_123"
        assert len(state.actions) == 1
        assert len(state.errors) == 1
        assert state.token_usage == 50000
        assert state.token_limit == 100000
        assert state.confidence_scores == [0.9, 0.85]

    def test_execution_state_defaults(self):
        """Test ExecutionState with default values."""
        state = ExecutionState(
            session_id="sess_123",
            actions=[],
            errors=[],
            token_usage=0,
            token_limit=100000,
            confidence_scores=[],
        )

        assert state.actions == []
        assert state.errors == []
        assert state.confidence_scores == []

    def test_execution_state_token_ratio(self):
        """Test token usage ratio calculation."""
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=75000,
            token_limit=100000,
            confidence_scores=[],
        )

        assert state.token_usage_ratio == 0.75

    def test_execution_state_token_ratio_zero_limit(self):
        """Test token usage ratio with zero limit."""
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=1000,
            token_limit=0,
            confidence_scores=[],
        )

        assert state.token_usage_ratio == 1.0


# =============================================================================
# PredictionResult Tests
# =============================================================================


class TestPredictionResult:
    """Tests for PredictionResult data class."""

    def test_create_prediction_result(self):
        """Test creating a PredictionResult."""
        result = PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.STUCK_LOOP,
            confidence=0.85,
            details="Detected 5 repeated file read actions",
        )

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.STUCK_LOOP
        assert result.confidence == 0.85
        assert "repeated" in result.details

    def test_prediction_result_no_failure(self):
        """Test PredictionResult when no failure predicted."""
        result = PredictionResult(
            failure_predicted=False,
            failure_type=None,
            confidence=0.0,
            details="No failure patterns detected",
        )

        assert result.failure_predicted is False
        assert result.failure_type is None

    def test_prediction_result_to_dict(self):
        """Test PredictionResult.to_dict()."""
        result = PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.TOKEN_EXHAUSTION,
            confidence=0.9,
            details="Token usage at 90%",
        )

        data = result.to_dict()

        assert data["failure_predicted"] is True
        assert data["failure_type"] == "token_exhaustion"
        assert data["confidence"] == 0.9
        assert "90%" in data["details"]


# =============================================================================
# RecoverySuggestion Tests
# =============================================================================


class TestRecoverySuggestion:
    """Tests for RecoverySuggestion data class."""

    def test_create_recovery_suggestion(self):
        """Test creating a RecoverySuggestion."""
        suggestion = RecoverySuggestion(
            action=RecoveryAction.HANDOFF,
            reason="Session approaching context limit",
            priority=1,
            details={"remaining_tokens": 5000},
        )

        assert suggestion.action == RecoveryAction.HANDOFF
        assert "context limit" in suggestion.reason
        assert suggestion.priority == 1
        assert suggestion.details["remaining_tokens"] == 5000

    def test_recovery_suggestion_to_dict(self):
        """Test RecoverySuggestion.to_dict()."""
        suggestion = RecoverySuggestion(
            action=RecoveryAction.RETRY,
            reason="Transient error detected",
            priority=2,
        )

        data = suggestion.to_dict()

        assert data["action"] == "retry"
        assert data["reason"] == "Transient error detected"
        assert data["priority"] == 2


# =============================================================================
# FailureType Tests
# =============================================================================


class TestFailureType:
    """Tests for FailureType enum."""

    def test_failure_types_exist(self):
        """Test that all required failure types exist."""
        assert FailureType.STUCK_LOOP is not None
        assert FailureType.TOKEN_EXHAUSTION is not None
        assert FailureType.CONFIDENCE_DROP is not None
        assert FailureType.ERROR_ACCUMULATION is not None

    def test_failure_type_values(self):
        """Test failure type string values."""
        assert FailureType.STUCK_LOOP.value == "stuck_loop"
        assert FailureType.TOKEN_EXHAUSTION.value == "token_exhaustion"
        assert FailureType.CONFIDENCE_DROP.value == "confidence_drop"
        assert FailureType.ERROR_ACCUMULATION.value == "error_accumulation"


# =============================================================================
# RecoveryAction Tests
# =============================================================================


class TestRecoveryAction:
    """Tests for RecoveryAction enum."""

    def test_recovery_actions_exist(self):
        """Test that all required recovery actions exist."""
        assert RecoveryAction.HANDOFF is not None
        assert RecoveryAction.RETRY is not None
        assert RecoveryAction.ESCALATE is not None
        assert RecoveryAction.RESET_CONTEXT is not None
        assert RecoveryAction.CONTINUE is not None

    def test_recovery_action_values(self):
        """Test recovery action string values."""
        assert RecoveryAction.HANDOFF.value == "handoff"
        assert RecoveryAction.RETRY.value == "retry"
        assert RecoveryAction.ESCALATE.value == "escalate"
        assert RecoveryAction.RESET_CONTEXT.value == "reset_context"
        assert RecoveryAction.CONTINUE.value == "continue"


# =============================================================================
# Stuck Loop Detection Tests
# =============================================================================


class TestStuckLoopDetection:
    """Tests for stuck loop detection."""

    def test_detect_stuck_loop_repeated_file_reads(self, predictor):
        """Test detection of stuck loop with repeated file reads."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
            ],
            errors=[],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.STUCK_LOOP
        assert result.confidence >= 0.7

    def test_detect_stuck_loop_repeated_edit_undo_cycle(self, predictor):
        """Test detection of stuck loop with edit/undo cycle."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "edit_file", "path": "/src/main.py", "change": "add line"},
                {"type": "edit_file", "path": "/src/main.py", "change": "remove line"},
                {"type": "edit_file", "path": "/src/main.py", "change": "add line"},
                {"type": "edit_file", "path": "/src/main.py", "change": "remove line"},
                {"type": "edit_file", "path": "/src/main.py", "change": "add line"},
                {"type": "edit_file", "path": "/src/main.py", "change": "remove line"},
            ],
            errors=[],
            token_usage=15000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.STUCK_LOOP

    def test_no_stuck_loop_with_varied_actions(self, predictor, normal_state):
        """Test no stuck loop detection with varied actions."""
        result = predictor.predict(normal_state)

        # Should not detect stuck loop with varied actions
        assert result.failure_type != FailureType.STUCK_LOOP or result.failure_predicted is False

    def test_stuck_loop_threshold_configurable(self):
        """Test that stuck loop threshold is configurable."""
        predictor = FailurePredictor(stuck_loop_threshold=3)

        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
            ],
            errors=[],
            token_usage=5000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.STUCK_LOOP

    def test_stuck_loop_considers_action_similarity(self, predictor):
        """Test that stuck loop detection considers action similarity."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/a.py"},
                {"type": "read_file", "path": "/src/b.py"},
                {"type": "read_file", "path": "/src/c.py"},
                {"type": "read_file", "path": "/src/d.py"},
                {"type": "read_file", "path": "/src/e.py"},
            ],
            errors=[],
            token_usage=8000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        # Different files = not a stuck loop
        assert result.failure_type != FailureType.STUCK_LOOP or result.failure_predicted is False


# =============================================================================
# Token Exhaustion Detection Tests
# =============================================================================


class TestTokenExhaustionDetection:
    """Tests for token exhaustion detection."""

    def test_detect_token_exhaustion_at_90_percent(self, predictor):
        """Test detection of token exhaustion at 90% usage."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "read_file", "path": "/src/main.py"}],
            errors=[],
            token_usage=90000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION
        assert result.confidence >= 0.8

    def test_detect_token_exhaustion_at_95_percent(self, predictor):
        """Test detection of token exhaustion at 95% usage."""
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=95000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION
        assert result.confidence >= 0.9

    def test_no_token_exhaustion_at_50_percent(self, predictor):
        """Test no token exhaustion at 50% usage."""
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=50000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        # Should not detect token exhaustion at 50%
        assert result.failure_type != FailureType.TOKEN_EXHAUSTION or result.failure_predicted is False

    def test_token_exhaustion_threshold_configurable(self):
        """Test that token exhaustion threshold is configurable."""
        predictor = FailurePredictor(token_exhaustion_threshold=0.7)

        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=75000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION

    def test_token_exhaustion_zero_limit_handled(self, predictor):
        """Test token exhaustion handles zero limit gracefully."""
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=1000,
            token_limit=0,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        # Should predict failure when limit is zero
        assert result.failure_predicted is True
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION


# =============================================================================
# Confidence Drop Detection Tests
# =============================================================================


class TestConfidenceDropDetection:
    """Tests for confidence drop detection."""

    def test_detect_confidence_drop_gradual(self, predictor):
        """Test detection of gradual confidence drop."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/a.py"},
                {"type": "edit_file", "path": "/src/b.py"},
                {"type": "run_tests", "command": "pytest"},
                {"type": "search", "query": "foo"},
                {"type": "write_file", "path": "/src/c.py"},
            ],
            errors=[],
            token_usage=20000,
            token_limit=100000,
            confidence_scores=[0.95, 0.85, 0.75, 0.65, 0.55],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.CONFIDENCE_DROP

    def test_detect_confidence_drop_sudden(self, predictor):
        """Test detection of sudden confidence drop."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 3,
            errors=[],
            token_usage=15000,
            token_limit=100000,
            confidence_scores=[0.95, 0.90, 0.40],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.CONFIDENCE_DROP

    def test_no_confidence_drop_with_stable_scores(self, predictor):
        """Test no confidence drop with stable scores."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 5,
            errors=[],
            token_usage=25000,
            token_limit=100000,
            confidence_scores=[0.90, 0.88, 0.91, 0.89, 0.90],
        )

        result = predictor.predict(state)

        # Should not detect confidence drop with stable scores
        assert result.failure_type != FailureType.CONFIDENCE_DROP or result.failure_predicted is False

    def test_confidence_drop_needs_minimum_scores(self, predictor):
        """Test confidence drop detection needs minimum scores."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}],
            errors=[],
            token_usage=5000,
            token_limit=100000,
            confidence_scores=[0.50],  # Single low score
        )

        result = predictor.predict(state)

        # Should not detect drop with insufficient data
        assert result.failure_type != FailureType.CONFIDENCE_DROP or result.failure_predicted is False

    def test_confidence_drop_threshold_configurable(self):
        """Test that confidence drop threshold is configurable."""
        predictor = FailurePredictor(confidence_drop_threshold=0.1)

        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 3,
            errors=[],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[0.90, 0.85, 0.75],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.CONFIDENCE_DROP


# =============================================================================
# Error Accumulation Detection Tests
# =============================================================================


class TestErrorAccumulationDetection:
    """Tests for error accumulation detection."""

    def test_detect_error_accumulation_multiple_errors(self, predictor):
        """Test detection of multiple errors."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/a.py"},
                {"type": "edit_file", "path": "/src/b.py"},
                {"type": "run_tests", "command": "pytest"},
                {"type": "search", "query": "foo"},
                {"type": "write_file", "path": "/src/c.py"},
            ],
            errors=[
                {"type": "import_error", "message": "No module named 'foo'"},
                {"type": "syntax_error", "message": "Invalid syntax"},
                {"type": "type_error", "message": "Expected str got int"},
                {"type": "name_error", "message": "Name 'x' is not defined"},
            ],
            token_usage=20000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.ERROR_ACCUMULATION

    def test_detect_error_accumulation_repeated_same_error(self, predictor):
        """Test detection of repeated same errors."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/a.py"},
                {"type": "edit_file", "path": "/src/b.py"},
                {"type": "run_tests", "command": "pytest"},
                {"type": "search", "query": "foo"},
                {"type": "write_file", "path": "/src/c.py"},
            ],
            errors=[
                {"type": "import_error", "message": "No module named 'foo'"},
                {"type": "import_error", "message": "No module named 'foo'"},
                {"type": "import_error", "message": "No module named 'foo'"},
            ],
            token_usage=15000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.ERROR_ACCUMULATION

    def test_no_error_accumulation_single_error(self, predictor):
        """Test no error accumulation with single error."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 5,
            errors=[{"type": "import_error", "message": "No module named 'foo'"}],
            token_usage=15000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        # Should not detect accumulation with single error
        assert result.failure_type != FailureType.ERROR_ACCUMULATION or result.failure_predicted is False

    def test_error_accumulation_threshold_configurable(self):
        """Test that error accumulation threshold is configurable."""
        predictor = FailurePredictor(error_accumulation_threshold=2)

        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 3,
            errors=[
                {"type": "error1", "message": "Error 1"},
                {"type": "error2", "message": "Error 2"},
            ],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.ERROR_ACCUMULATION

    def test_error_accumulation_considers_error_rate(self, predictor):
        """Test error accumulation considers error rate relative to actions."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 100,  # Many actions
            errors=[
                {"type": "error1", "message": "Error 1"},
                {"type": "error2", "message": "Error 2"},
            ],  # Few errors
            token_usage=50000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        # Low error rate should not trigger accumulation
        assert result.failure_type != FailureType.ERROR_ACCUMULATION or result.failure_predicted is False


# =============================================================================
# Recovery Suggestion Tests
# =============================================================================


class TestRecoverySuggestions:
    """Tests for recovery suggestion generation."""

    def test_recovery_for_stuck_loop(self, predictor):
        """Test recovery suggestion for stuck loop."""
        prediction = PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.STUCK_LOOP,
            confidence=0.85,
            details="Detected repeated actions",
        )

        suggestion = predictor.get_recovery_suggestion(prediction)

        assert suggestion.action in [RecoveryAction.RESET_CONTEXT, RecoveryAction.ESCALATE]
        assert suggestion.priority <= 2

    def test_recovery_for_token_exhaustion(self, predictor):
        """Test recovery suggestion for token exhaustion."""
        prediction = PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.TOKEN_EXHAUSTION,
            confidence=0.9,
            details="Token usage at 95%",
        )

        suggestion = predictor.get_recovery_suggestion(prediction)

        assert suggestion.action == RecoveryAction.HANDOFF
        assert suggestion.priority == 1  # High priority

    def test_recovery_for_confidence_drop(self, predictor):
        """Test recovery suggestion for confidence drop."""
        prediction = PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.CONFIDENCE_DROP,
            confidence=0.75,
            details="Confidence dropped from 0.9 to 0.5",
        )

        suggestion = predictor.get_recovery_suggestion(prediction)

        assert suggestion.action in [RecoveryAction.ESCALATE, RecoveryAction.RETRY]

    def test_recovery_for_error_accumulation(self, predictor):
        """Test recovery suggestion for error accumulation."""
        prediction = PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.ERROR_ACCUMULATION,
            confidence=0.8,
            details="4 errors in last 5 actions",
        )

        suggestion = predictor.get_recovery_suggestion(prediction)

        assert suggestion.action in [RecoveryAction.RETRY, RecoveryAction.ESCALATE]

    def test_recovery_for_no_failure(self, predictor):
        """Test recovery suggestion when no failure predicted."""
        prediction = PredictionResult(
            failure_predicted=False,
            failure_type=None,
            confidence=0.0,
            details="No failure patterns detected",
        )

        suggestion = predictor.get_recovery_suggestion(prediction)

        assert suggestion.action == RecoveryAction.CONTINUE
        assert suggestion.priority >= 3  # Low priority


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_state(self, predictor, empty_state):
        """Test prediction with empty state."""
        result = predictor.predict(empty_state)

        # Empty state should not predict failure
        assert result.failure_predicted is False

    def test_single_action(self, predictor):
        """Test prediction with single action."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "read_file", "path": "/src/main.py"}],
            errors=[],
            token_usage=1000,
            token_limit=100000,
            confidence_scores=[0.95],
        )

        result = predictor.predict(state)

        # Single action should not predict failure
        assert result.failure_predicted is False

    def test_none_actions_handled(self, predictor):
        """Test that None in actions list is handled."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}, None, {"type": "action"}],
            errors=[],
            token_usage=5000,
            token_limit=100000,
            confidence_scores=[],
        )

        # Should not raise exception
        result = predictor.predict(state)
        assert result is not None

    def test_empty_confidence_scores(self, predictor):
        """Test prediction with empty confidence scores."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 5,
            errors=[],
            token_usage=25000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)

        # Should not detect confidence drop with no scores
        assert result.failure_type != FailureType.CONFIDENCE_DROP or result.failure_predicted is False

    def test_negative_token_usage_handled(self, predictor):
        """Test that negative token usage is handled."""
        state = ExecutionState(
            session_id="test",
            actions=[],
            errors=[],
            token_usage=-1000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)
        assert result is not None

    def test_confidence_scores_outside_range(self, predictor):
        """Test confidence scores outside 0-1 range are handled."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "action"}] * 3,
            errors=[],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[1.5, 0.9, -0.1],
        )

        result = predictor.predict(state)
        assert result is not None

    def test_multiple_failure_types_prioritized(self, predictor):
        """Test that multiple failure types are prioritized correctly."""
        state = ExecutionState(
            session_id="test",
            actions=[
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
                {"type": "read_file", "path": "/src/main.py"},
            ],
            errors=[
                {"type": "error1", "message": "Error"},
                {"type": "error2", "message": "Error"},
                {"type": "error3", "message": "Error"},
            ],
            token_usage=92000,  # High token usage
            token_limit=100000,
            confidence_scores=[0.9, 0.7, 0.5, 0.3, 0.2],  # Dropping confidence
        )

        result = predictor.predict(state)

        # Should predict failure and return highest priority issue
        assert result.failure_predicted is True
        # Token exhaustion should be highest priority
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION

    def test_very_long_action_history(self, predictor):
        """Test prediction with very long action history."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": f"action_{i}", "data": f"data_{i}"} for i in range(1000)],
            errors=[],
            token_usage=50000,
            token_limit=100000,
            confidence_scores=[0.9] * 100,
        )

        # Should not raise exception or timeout
        result = predictor.predict(state)
        assert result is not None


# =============================================================================
# Integration Tests
# =============================================================================


class TestFailurePredictorIntegration:
    """Integration tests for FailurePredictor."""

    def test_predict_then_recover_workflow(self, predictor):
        """Test full predict-then-recover workflow."""
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "read_file", "path": "/src/main.py"}] * 6,
            errors=[],
            token_usage=85000,
            token_limit=100000,
            confidence_scores=[],
        )

        # Step 1: Predict
        prediction = predictor.predict(state)
        assert prediction.failure_predicted is True

        # Step 2: Get recovery
        suggestion = predictor.get_recovery_suggestion(prediction)
        assert suggestion is not None
        assert suggestion.action != RecoveryAction.CONTINUE

    def test_predictor_state_independence(self, predictor):
        """Test that predictor is stateless between calls."""
        state1 = ExecutionState(
            session_id="test1",
            actions=[{"type": "read_file", "path": "/src/main.py"}] * 6,
            errors=[],
            token_usage=10000,
            token_limit=100000,
            confidence_scores=[],
        )

        state2 = ExecutionState(
            session_id="test2",
            actions=[{"type": "action"}],
            errors=[],
            token_usage=5000,
            token_limit=100000,
            confidence_scores=[0.95],
        )

        # First prediction should detect stuck loop
        result1 = predictor.predict(state1)
        assert result1.failure_predicted is True

        # Second prediction should be independent
        result2 = predictor.predict(state2)
        assert result2.failure_predicted is False

    def test_custom_thresholds_all_at_once(self):
        """Test predictor with all custom thresholds."""
        predictor = FailurePredictor(
            stuck_loop_threshold=3,
            token_exhaustion_threshold=0.8,
            confidence_drop_threshold=0.15,
            error_accumulation_threshold=2,
        )

        # Test stuck loop with lower threshold
        state = ExecutionState(
            session_id="test",
            actions=[{"type": "read_file", "path": "/src/main.py"}] * 3,
            errors=[],
            token_usage=5000,
            token_limit=100000,
            confidence_scores=[],
        )

        result = predictor.predict(state)
        assert result.failure_predicted is True
        assert result.failure_type == FailureType.STUCK_LOOP
