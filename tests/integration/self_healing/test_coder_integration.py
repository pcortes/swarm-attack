"""Integration tests for CoderSelfHealingIntegration.

Tests the integration module that wires FailurePredictor, RecoveryAgent,
and EscalationManager into the CoderAgent execution loop.

TDD: These tests are written first to define the expected behavior.
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import MagicMock, patch, AsyncMock

from swarm_attack.self_healing import (
    FailurePredictor,
    ExecutionState,
    PredictionResult,
    RecoveryAction,
    RecoverySuggestion,
    FailureType,
    EscalationManager,
    EscalationContext,
    EscalationTicket,
    FailureContext,
    Priority,
)


class TestCoderSelfHealingIntegrationBasics:
    """Basic tests for CoderSelfHealingIntegration initialization."""

    def test_integration_init_with_defaults(self):
        """Test that integration module can be initialized with defaults."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        assert integration.failure_predictor is not None
        assert integration.escalation_manager is not None
        assert isinstance(integration.failure_predictor, FailurePredictor)
        assert isinstance(integration.escalation_manager, EscalationManager)

    def test_integration_init_with_custom_predictor(self):
        """Test integration with custom FailurePredictor."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        custom_predictor = FailurePredictor(
            stuck_loop_threshold=10,
            token_exhaustion_threshold=0.9,
        )

        integration = CoderSelfHealingIntegration(
            failure_predictor=custom_predictor,
        )

        assert integration.failure_predictor is custom_predictor
        assert integration.failure_predictor.stuck_loop_threshold == 10

    def test_integration_init_with_custom_escalation_manager(self):
        """Test integration with custom EscalationManager."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        custom_manager = EscalationManager(
            timeout_threshold_seconds=600.0,
        )

        integration = CoderSelfHealingIntegration(
            escalation_manager=custom_manager,
        )

        assert integration.escalation_manager is custom_manager
        assert integration.escalation_manager.timeout_threshold_seconds == 600.0


class TestExecutionStateTracking:
    """Tests for execution state tracking during CoderAgent runs."""

    def test_create_execution_state_from_context(self):
        """Test creating ExecutionState from CoderAgent context."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        context = {
            "session_id": "test-session-123",
            "feature_id": "my-feature",
            "issue_number": 1,
            "token_usage": 5000,
            "token_limit": 10000,
        }

        state = integration.create_execution_state(
            session_id=context["session_id"],
            token_usage=context["token_usage"],
            token_limit=context["token_limit"],
        )

        assert isinstance(state, ExecutionState)
        assert state.session_id == "test-session-123"
        assert state.token_usage == 5000
        assert state.token_limit == 10000
        assert state.actions == []
        assert state.errors == []
        assert state.confidence_scores == []

    def test_record_action(self):
        """Test recording actions into execution state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        action = {"type": "file_write", "path": "src/foo.py"}
        integration.record_action(state, action)

        assert len(state.actions) == 1
        assert state.actions[0] == action

    def test_record_error(self):
        """Test recording errors into execution state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        error = {"type": "SyntaxError", "message": "Invalid syntax"}
        integration.record_error(state, error)

        assert len(state.errors) == 1
        assert state.errors[0] == error

    def test_record_confidence_score(self):
        """Test recording confidence scores."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        integration.record_confidence(state, 0.95)
        integration.record_confidence(state, 0.85)

        assert len(state.confidence_scores) == 2
        assert state.confidence_scores[0] == 0.95
        assert state.confidence_scores[1] == 0.85

    def test_update_token_usage(self):
        """Test updating token usage in execution state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        integration.update_token_usage(state, 5000)

        assert state.token_usage == 5000


class TestFailurePrediction:
    """Tests for failure prediction during execution."""

    def test_check_health_returns_prediction_result(self):
        """Test that check_health returns PredictionResult."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        result = integration.check_health(state)

        assert isinstance(result, PredictionResult)
        assert result.failure_predicted is False  # Healthy state

    def test_check_health_detects_token_exhaustion(self):
        """Test that check_health detects token exhaustion."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=9000,  # 90% of limit
            token_limit=10000,
        )

        result = integration.check_health(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION

    def test_check_health_detects_stuck_loop(self):
        """Test that check_health detects stuck loops."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        # Record the same action multiple times to trigger stuck loop
        same_action = {"type": "file_write", "path": "src/foo.py"}
        for _ in range(6):
            integration.record_action(state, same_action)

        result = integration.check_health(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.STUCK_LOOP

    def test_check_health_detects_error_accumulation(self):
        """Test that check_health detects error accumulation."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        # Record multiple errors of the same type
        for i in range(5):
            integration.record_error(state, {"type": "SyntaxError", "message": f"Error {i}"})

        result = integration.check_health(state)

        assert result.failure_predicted is True
        assert result.failure_type == FailureType.ERROR_ACCUMULATION


class TestRecoverySuggestions:
    """Tests for recovery suggestion generation."""

    def test_get_recovery_suggestion_for_healthy_state(self):
        """Test getting recovery suggestion for healthy state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        prediction = integration.check_health(state)
        suggestion = integration.get_recovery_suggestion(prediction)

        assert isinstance(suggestion, RecoverySuggestion)
        assert suggestion.action == RecoveryAction.CONTINUE

    def test_get_recovery_suggestion_for_token_exhaustion(self):
        """Test getting recovery suggestion for token exhaustion."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=9000,
            token_limit=10000,
        )

        prediction = integration.check_health(state)
        suggestion = integration.get_recovery_suggestion(prediction)

        assert suggestion.action == RecoveryAction.HANDOFF
        assert suggestion.priority == 1  # Highest priority

    def test_get_recovery_suggestion_for_stuck_loop(self):
        """Test getting recovery suggestion for stuck loop."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        same_action = {"type": "file_write", "path": "src/foo.py"}
        for _ in range(6):
            integration.record_action(state, same_action)

        prediction = integration.check_health(state)
        suggestion = integration.get_recovery_suggestion(prediction)

        assert suggestion.action == RecoveryAction.RESET_CONTEXT


class TestEscalationFlow:
    """Tests for escalation flow when recovery is not possible."""

    def test_should_escalate_returns_false_for_healthy_state(self):
        """Test that healthy state does not trigger escalation."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        failure_context = FailureContext(
            error_message="Test error",
            error_type="TestError",
            component="coder",
            attempts=1,
            max_attempts=3,
        )

        result = integration.should_escalate(failure_context)
        assert result is False

    def test_should_escalate_returns_true_for_max_attempts_exceeded(self):
        """Test that max attempts exceeded triggers escalation."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        failure_context = FailureContext(
            error_message="Test error",
            error_type="TestError",
            component="coder",
            attempts=5,
            max_attempts=3,
        )

        result = integration.should_escalate(failure_context)
        assert result is True

    def test_should_escalate_returns_true_for_data_loss_risk(self):
        """Test that data loss risk triggers escalation."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        failure_context = FailureContext(
            error_message="Database corruption",
            error_type="DataIntegrityError",
            component="coder",
            attempts=1,
            max_attempts=3,
            is_data_loss_risk=True,
        )

        result = integration.should_escalate(failure_context)
        assert result is True

    def test_escalate_creates_ticket(self):
        """Test that escalate creates an EscalationTicket."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        failure_context = FailureContext(
            error_message="Test error",
            error_type="TestError",
            component="coder",
            attempts=5,
            max_attempts=3,
        )

        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["retry once", "reset state"],
            failure_reason="Max attempts exceeded",
            session_id="test-session",
            feature_id="my-feature",
            issue_number=1,
        )

        ticket = integration.escalate(escalation_context)

        assert isinstance(ticket, EscalationTicket)
        assert ticket.ticket_id is not None
        assert ticket.status == "open"
        assert ticket.priority in [Priority.P0, Priority.P1, Priority.P2, Priority.P3]


class TestCoderAgentHooks:
    """Tests for hooks that integrate with CoderAgent execution loop."""

    def test_pre_execution_hook_returns_state(self):
        """Test pre-execution hook creates and returns execution state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        context = {
            "session_id": "test-session",
            "feature_id": "my-feature",
            "issue_number": 1,
            "token_usage": 0,
            "token_limit": 10000,
        }

        state = integration.pre_execution_hook(context)

        assert isinstance(state, ExecutionState)
        assert state.session_id == "test-session"

    def test_post_action_hook_records_action_and_checks_health(self):
        """Test post-action hook records action and checks health."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        action = {"type": "file_write", "path": "src/foo.py"}
        result = integration.post_action_hook(state, action, token_delta=100)

        assert len(state.actions) == 1
        assert state.token_usage == 1100  # Updated
        assert isinstance(result, PredictionResult)

    def test_on_error_hook_records_error_and_suggests_recovery(self):
        """Test on-error hook records error and returns recovery suggestion."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        error = {"type": "SyntaxError", "message": "Invalid syntax"}
        suggestion = integration.on_error_hook(state, error)

        assert len(state.errors) == 1
        assert isinstance(suggestion, RecoverySuggestion)

    def test_post_execution_hook_returns_summary(self):
        """Test post-execution hook returns execution summary."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        integration.record_action(state, {"type": "file_write", "path": "src/foo.py"})
        integration.record_action(state, {"type": "file_write", "path": "src/bar.py"})
        integration.record_error(state, {"type": "SyntaxError", "message": "Error"})

        summary = integration.post_execution_hook(state, success=True)

        assert isinstance(summary, dict)
        assert summary["session_id"] == "test-session"
        assert summary["total_actions"] == 2
        assert summary["total_errors"] == 1
        assert summary["success"] is True


class TestIntegrationWithRecoveryAgent:
    """Tests for integration with RecoveryAgent."""

    def test_create_recovery_context_from_execution_state(self):
        """Test creating recovery context from execution state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        integration.record_action(state, {"type": "file_write", "path": "src/foo.py"})
        integration.record_error(state, {"type": "SyntaxError", "message": "Invalid syntax"})

        recovery_context = integration.create_recovery_context(
            state=state,
            feature_id="my-feature",
            issue_number=1,
            failure_type="test_failure",
            error_output="Test output",
        )

        assert isinstance(recovery_context, dict)
        assert recovery_context["feature_id"] == "my-feature"
        assert recovery_context["issue_number"] == 1
        assert recovery_context["failure_type"] == "test_failure"
        assert recovery_context["session_id"] == "test-session"
        assert "error_output" in recovery_context


class TestHealthCheckIntegration:
    """Tests for continuous health checking during execution."""

    def test_should_continue_returns_true_for_healthy_state(self):
        """Test should_continue returns True for healthy state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        should_continue, reason = integration.should_continue(state)

        assert should_continue is True
        assert reason is None

    def test_should_continue_returns_false_for_failing_state(self):
        """Test should_continue returns False for failing state."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=9500,  # 95% - critical
            token_limit=10000,
        )

        should_continue, reason = integration.should_continue(state)

        assert should_continue is False
        assert reason is not None
        assert "token" in reason.lower()


class TestEventEmission:
    """Tests for event emission during self-healing operations."""

    def test_emit_health_check_event(self):
        """Test that health check emits event."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()
        events_emitted = []

        def event_listener(event):
            events_emitted.append(event)

        integration.add_event_listener(event_listener)

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=9000,
            token_limit=10000,
        )

        integration.check_health(state)

        assert len(events_emitted) >= 1
        assert any(e.get("type") == "health_check" for e in events_emitted)

    def test_emit_escalation_event(self):
        """Test that escalation emits event."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()
        events_emitted = []

        def event_listener(event):
            events_emitted.append(event)

        integration.add_event_listener(event_listener)

        failure_context = FailureContext(
            error_message="Test error",
            error_type="TestError",
            component="coder",
            attempts=5,
            max_attempts=3,
        )

        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["retry once"],
            failure_reason="Max attempts exceeded",
        )

        integration.escalate(escalation_context)

        assert any(e.get("type") == "escalation_created" for e in events_emitted)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_actions_list_does_not_crash(self):
        """Test that empty actions list is handled gracefully."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        # No actions recorded
        result = integration.check_health(state)

        assert result.failure_predicted is False

    def test_zero_token_limit_handled_gracefully(self):
        """Test that zero token limit is handled without division by zero."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=0,  # Edge case
        )

        # Should not raise exception
        result = integration.check_health(state)

        # With zero limit, should trigger exhaustion
        assert result.failure_predicted is True
        assert result.failure_type == FailureType.TOKEN_EXHAUSTION

    def test_negative_token_usage_treated_as_zero(self):
        """Test that negative token usage is handled."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=-100,  # Edge case
            token_limit=10000,
        )

        result = integration.check_health(state)

        # Should handle gracefully
        assert isinstance(result, PredictionResult)

    def test_none_action_filtered_out(self):
        """Test that None actions are filtered out."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        integration = CoderSelfHealingIntegration()

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        integration.record_action(state, None)
        integration.record_action(state, {"type": "file_write", "path": "src/foo.py"})

        # Health check should filter out None actions
        result = integration.check_health(state)
        assert isinstance(result, PredictionResult)


class TestConfigurability:
    """Tests for configurable thresholds and behavior."""

    def test_custom_stuck_loop_threshold(self):
        """Test custom stuck loop threshold is respected."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        # Set higher threshold
        predictor = FailurePredictor(stuck_loop_threshold=10)
        integration = CoderSelfHealingIntegration(failure_predictor=predictor)

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=1000,
            token_limit=10000,
        )

        # 6 identical actions - below threshold of 10
        same_action = {"type": "file_write", "path": "src/foo.py"}
        for _ in range(6):
            integration.record_action(state, same_action)

        result = integration.check_health(state)

        # Should NOT trigger stuck loop with threshold=10
        assert result.failure_type != FailureType.STUCK_LOOP

    def test_custom_token_exhaustion_threshold(self):
        """Test custom token exhaustion threshold is respected."""
        from swarm_attack.self_healing.coder_integration import (
            CoderSelfHealingIntegration,
        )

        # Set higher threshold (95%)
        predictor = FailurePredictor(token_exhaustion_threshold=0.95)
        integration = CoderSelfHealingIntegration(failure_predictor=predictor)

        state = integration.create_execution_state(
            session_id="test-session",
            token_usage=9000,  # 90%
            token_limit=10000,
        )

        result = integration.check_health(state)

        # Should NOT trigger with 95% threshold
        assert result.failure_predicted is False
