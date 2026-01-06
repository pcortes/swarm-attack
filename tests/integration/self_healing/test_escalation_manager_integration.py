"""Integration tests for EscalationManager.

Tests integration with:
- FailurePredictor (predicts failures and suggests recovery actions)
- RecoveryHandler (mocked - does not exist yet)
- Notification/alerting systems (mocked)

These tests verify the end-to-end flow from failure prediction through
escalation to notification.
"""

import json
import pytest
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock, patch

from swarm_attack.self_healing.escalation_manager import (
    EscalationManager,
    EscalationContext,
    EscalationTicket,
    EscalationTrigger,
    FailureContext,
    Priority,
    ResumeResult,
)
from swarm_attack.self_healing.failure_predictor import (
    ExecutionState,
    FailurePredictor,
    FailureType,
    PredictionResult,
    RecoveryAction,
    RecoverySuggestion,
)


# =============================================================================
# MOCK COMPONENTS
# =============================================================================


@dataclass
class MockAlert:
    """Represents an alert sent to a notification system."""

    alert_id: str
    priority: str
    title: str
    message: str
    channel: str
    timestamp: str
    metadata: Dict[str, Any]


class MockNotificationSystem:
    """Mock notification/alerting system for testing.

    Simulates integration with alerting systems like Slack, PagerDuty, etc.
    """

    def __init__(self):
        self.alerts: List[MockAlert] = []
        self.channels: Dict[str, List[MockAlert]] = {}
        self._lock = threading.Lock()
        self._alert_counter = 0

    def send_alert(
        self,
        priority: str,
        title: str,
        message: str,
        channel: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MockAlert:
        """Send an alert to the notification system."""
        with self._lock:
            self._alert_counter += 1
            alert = MockAlert(
                alert_id=f"ALERT-{self._alert_counter:04d}",
                priority=priority,
                title=title,
                message=message,
                channel=channel,
                timestamp=datetime.now().isoformat(),
                metadata=metadata or {},
            )
            self.alerts.append(alert)
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels[channel].append(alert)
            return alert

    def get_alerts_by_priority(self, priority: str) -> List[MockAlert]:
        """Get all alerts of a specific priority."""
        return [a for a in self.alerts if a.priority == priority]

    def get_alerts_by_channel(self, channel: str) -> List[MockAlert]:
        """Get all alerts sent to a specific channel."""
        return self.channels.get(channel, [])

    def clear(self) -> None:
        """Clear all alerts."""
        with self._lock:
            self.alerts.clear()
            self.channels.clear()


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    success: bool
    action: RecoveryAction
    message: str
    duration_seconds: float = 0.0


class MockRecoveryHandler:
    """Mock recovery handler for testing.

    Simulates recovery operations like context reset, retry, handoff, etc.
    """

    def __init__(self):
        self.recovery_attempts: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._success_rate = 0.8  # 80% success rate by default

    def set_success_rate(self, rate: float) -> None:
        """Set the success rate for recovery attempts."""
        self._success_rate = min(1.0, max(0.0, rate))

    def attempt_recovery(
        self,
        suggestion: RecoverySuggestion,
        context: Dict[str, Any],
    ) -> RecoveryResult:
        """Attempt recovery based on a suggestion."""
        with self._lock:
            attempt = {
                "action": suggestion.action,
                "reason": suggestion.reason,
                "priority": suggestion.priority,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            }
            self.recovery_attempts.append(attempt)

            # Simulate success/failure
            import random
            success = random.random() < self._success_rate

            return RecoveryResult(
                success=success,
                action=suggestion.action,
                message=f"Recovery {'succeeded' if success else 'failed'} for {suggestion.action.value}",
                duration_seconds=0.1,
            )

    def reset_context(self, session_id: str) -> bool:
        """Reset context for a session."""
        with self._lock:
            self.recovery_attempts.append({
                "action": RecoveryAction.RESET_CONTEXT,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            })
            return True

    def initiate_handoff(self, session_id: str, target_agent: str) -> bool:
        """Initiate handoff to another agent."""
        with self._lock:
            self.recovery_attempts.append({
                "action": RecoveryAction.HANDOFF,
                "session_id": session_id,
                "target_agent": target_agent,
                "timestamp": datetime.now().isoformat(),
            })
            return True


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def escalation_manager(tmp_path):
    """Create an EscalationManager with temp storage."""
    storage_dir = tmp_path / "escalations"
    return EscalationManager(storage_dir=storage_dir)


@pytest.fixture
def failure_predictor():
    """Create a FailurePredictor instance."""
    return FailurePredictor()


@pytest.fixture
def notification_system():
    """Create a mock notification system."""
    return MockNotificationSystem()


@pytest.fixture
def recovery_handler():
    """Create a mock recovery handler."""
    return MockRecoveryHandler()


@pytest.fixture
def normal_execution_state():
    """Create a normal execution state (no failures predicted)."""
    return ExecutionState(
        session_id="session-normal",
        actions=[
            {"type": "read", "path": "file1.py"},
            {"type": "write", "path": "file2.py"},
            {"type": "run", "path": "test.py"},
        ],
        errors=[],
        token_usage=5000,
        token_limit=100000,
        confidence_scores=[0.9, 0.88, 0.87],
    )


@pytest.fixture
def stuck_loop_state():
    """Create an execution state with a stuck loop."""
    # Same action repeated 5+ times
    repeated_action = {"type": "edit", "path": "module.py"}
    return ExecutionState(
        session_id="session-stuck",
        actions=[repeated_action] * 7,
        errors=[],
        token_usage=10000,
        token_limit=100000,
        confidence_scores=[0.9, 0.85, 0.8],
    )


@pytest.fixture
def token_exhaustion_state():
    """Create an execution state approaching token limit."""
    return ExecutionState(
        session_id="session-exhausted",
        actions=[{"type": "read", "path": f"file{i}.py"} for i in range(10)],
        errors=[],
        token_usage=90000,  # 90% of limit
        token_limit=100000,
        confidence_scores=[0.9, 0.85],
    )


@pytest.fixture
def error_accumulation_state():
    """Create an execution state with accumulated errors."""
    # Use varied actions to avoid triggering stuck loop detection
    return ExecutionState(
        session_id="session-errors",
        actions=[
            {"type": "read", "path": "module.py"},
            {"type": "edit", "path": "module.py"},
            {"type": "run", "path": "test_module.py"},
            {"type": "read", "path": "other.py"},
            {"type": "run", "path": "test_other.py"},
        ],
        errors=[
            {"type": "TestError", "message": "Test failed"},
            {"type": "TestError", "message": "Test failed again"},
            {"type": "TestError", "message": "Test still failing"},
        ],
        token_usage=5000,
        token_limit=100000,
        confidence_scores=[0.9],
    )


@pytest.fixture
def confidence_drop_state():
    """Create an execution state with dropping confidence."""
    return ExecutionState(
        session_id="session-confused",
        actions=[
            {"type": "read", "path": "file1.py"},
            {"type": "think", "path": ""},
            {"type": "think", "path": ""},
        ],
        errors=[],
        token_usage=5000,
        token_limit=100000,
        confidence_scores=[0.9, 0.7, 0.5],  # Significant drop
    )


# =============================================================================
# INTEGRATION: FailurePredictor + EscalationManager
# =============================================================================


class TestFailurePredictorEscalationIntegration:
    """Tests for FailurePredictor and EscalationManager integration."""

    def test_no_escalation_for_normal_state(
        self,
        failure_predictor,
        escalation_manager,
        normal_execution_state,
    ):
        """Normal execution state should not trigger escalation."""
        # Predict failure
        prediction = failure_predictor.predict(normal_execution_state)

        # Should not predict failure
        assert prediction.failure_predicted is False

        # Should not escalate
        if prediction.failure_predicted:
            failure_context = FailureContext(
                error_message=prediction.details,
                error_type=prediction.failure_type.value if prediction.failure_type else "Unknown",
                component="test_component",
            )
            should_escalate = escalation_manager.should_escalate(failure_context)
            assert should_escalate is False

    def test_stuck_loop_triggers_escalation(
        self,
        failure_predictor,
        escalation_manager,
        stuck_loop_state,
    ):
        """Stuck loop should trigger escalation with reset suggestion."""
        # Predict failure
        prediction = failure_predictor.predict(stuck_loop_state)

        # Should predict stuck loop
        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.STUCK_LOOP

        # Get recovery suggestion
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.RESET_CONTEXT

        # Create escalation context based on prediction
        failure_context = FailureContext(
            error_message=prediction.details,
            error_type="StuckLoop",
            component="agent_executor",
            attempts=5,
            max_attempts=3,  # Exceeded
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["context_reset_attempted"],
            failure_reason=f"Failure predicted: {prediction.failure_type.value}",
            session_id=stuck_loop_state.session_id,
        )

        # Escalate
        ticket = escalation_manager.escalate(escalation_context)

        # Verify ticket
        assert ticket.ticket_id.startswith("ESC-")
        assert "StuckLoop" in ticket.title or "stuck" in ticket.description.lower()
        assert ticket.session_state.get("session_id") == stuck_loop_state.session_id

    def test_token_exhaustion_triggers_p1_escalation(
        self,
        failure_predictor,
        escalation_manager,
        token_exhaustion_state,
    ):
        """Token exhaustion should trigger P1 escalation with handoff suggestion."""
        # Predict failure
        prediction = failure_predictor.predict(token_exhaustion_state)

        # Should predict token exhaustion
        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION

        # Get recovery suggestion - should recommend handoff
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.HANDOFF
        assert suggestion.priority == 1  # Highest priority

        # Create escalation context
        failure_context = FailureContext(
            error_message="Token limit approaching",
            error_type="SystemError",  # System-level error triggers P1
            component="context_manager",
            elapsed_seconds=600.0,  # 10 minutes - over timeout
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[],
            failure_reason=f"Token exhaustion: {prediction.details}",
            session_id=token_exhaustion_state.session_id,
        )

        # Escalate
        ticket = escalation_manager.escalate(escalation_context)

        # Verify P1 priority for system errors
        assert ticket.priority == Priority.P1

    def test_error_accumulation_triggers_retry_suggestion(
        self,
        failure_predictor,
        escalation_manager,
        error_accumulation_state,
    ):
        """Error accumulation should suggest retry with fresh approach."""
        # Predict failure
        prediction = failure_predictor.predict(error_accumulation_state)

        # Should predict error accumulation
        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.ERROR_ACCUMULATION

        # Get recovery suggestion - should recommend retry
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.RETRY

        # Create escalation context
        failure_context = FailureContext(
            error_message="Multiple test failures",
            error_type="TestError",
            component="test_runner",
            attempts=3,
            max_attempts=3,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["retry_test_1", "retry_test_2"],
            failure_reason="Error accumulation detected",
            session_id=error_accumulation_state.session_id,
        )

        # Escalate
        ticket = escalation_manager.escalate(escalation_context)

        # Should include attempted fixes in description
        assert "retry_test_1" in ticket.description or "retry_test_1" in ticket.context_summary

    def test_confidence_drop_suggests_human_escalation(
        self,
        failure_predictor,
        escalation_manager,
        confidence_drop_state,
    ):
        """Confidence drop should suggest escalation to human."""
        # Predict failure
        prediction = failure_predictor.predict(confidence_drop_state)

        # Should predict confidence drop
        assert prediction.failure_predicted is True
        assert prediction.failure_type == FailureType.CONFIDENCE_DROP

        # Get recovery suggestion - should recommend escalate
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.ESCALATE

        # Create and escalate
        failure_context = FailureContext(
            error_message="Model confidence dropping",
            error_type="ConfidenceDrop",
            component="agent_executor",
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[],
            failure_reason="Model uncertainty increasing",
            session_id=confidence_drop_state.session_id,
        )

        ticket = escalation_manager.escalate(escalation_context)

        # Verify ticket created
        assert ticket is not None
        assert "Confidence" in ticket.title or "confidence" in ticket.description.lower()


# =============================================================================
# INTEGRATION: EscalationManager + RecoveryHandler (Mocked)
# =============================================================================


class TestEscalationRecoveryIntegration:
    """Tests for EscalationManager and RecoveryHandler integration."""

    def test_recovery_after_escalation_resume(
        self,
        escalation_manager,
        recovery_handler,
    ):
        """Recovery handler should be invoked after escalation resume."""
        # Create and escalate a failure
        failure_context = FailureContext(
            error_message="Connection timeout",
            error_type="TimeoutError",
            component="api_client",
            attempts=4,
            max_attempts=3,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["retry_connection"],
            failure_reason="Connection repeatedly failing",
            session_id="session-recovery-test",
        )

        ticket = escalation_manager.escalate(escalation_context)

        # Human provides guidance
        resume_result = escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Use backup server endpoint",
            additional_context={"backup_endpoint": "https://backup.example.com"},
        )

        assert resume_result.success is True

        # Recovery handler acts on human guidance
        suggestion = RecoverySuggestion(
            action=RecoveryAction.RETRY,
            reason="Human guidance provided",
            priority=1,
            details={"guidance": resume_result.human_guidance},
        )

        recovery_result = recovery_handler.attempt_recovery(
            suggestion=suggestion,
            context=resume_result.resume_context,
        )

        # Verify recovery was attempted
        assert len(recovery_handler.recovery_attempts) == 1
        assert recovery_handler.recovery_attempts[0]["action"] == RecoveryAction.RETRY

    def test_handoff_flow(
        self,
        escalation_manager,
        recovery_handler,
        failure_predictor,
        token_exhaustion_state,
    ):
        """Test complete handoff flow from prediction to recovery."""
        # Step 1: Predict failure
        prediction = failure_predictor.predict(token_exhaustion_state)
        assert prediction.failure_type == FailureType.TOKEN_EXHAUSTION

        # Step 2: Get recovery suggestion
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.HANDOFF

        # Step 3: Create escalation
        failure_context = FailureContext(
            error_message="Context window nearly full",
            error_type="ResourceExhaustion",
            component="context_manager",
            elapsed_seconds=400.0,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[],
            failure_reason="Token exhaustion imminent",
            session_id=token_exhaustion_state.session_id,
        )

        ticket = escalation_manager.escalate(escalation_context)

        # Step 4: Recovery handler initiates handoff
        handoff_success = recovery_handler.initiate_handoff(
            session_id=token_exhaustion_state.session_id,
            target_agent="fresh_agent",
        )

        assert handoff_success is True
        assert any(
            a.get("action") == RecoveryAction.HANDOFF
            for a in recovery_handler.recovery_attempts
        )

    def test_context_reset_flow(
        self,
        escalation_manager,
        recovery_handler,
        failure_predictor,
        stuck_loop_state,
    ):
        """Test complete context reset flow."""
        # Step 1: Predict stuck loop
        prediction = failure_predictor.predict(stuck_loop_state)
        assert prediction.failure_type == FailureType.STUCK_LOOP

        # Step 2: Get suggestion
        suggestion = failure_predictor.get_recovery_suggestion(prediction)
        assert suggestion.action == RecoveryAction.RESET_CONTEXT

        # Step 3: Recovery handler resets context
        reset_success = recovery_handler.reset_context(
            session_id=stuck_loop_state.session_id,
        )

        assert reset_success is True
        assert any(
            a.get("action") == RecoveryAction.RESET_CONTEXT
            for a in recovery_handler.recovery_attempts
        )


# =============================================================================
# INTEGRATION: EscalationManager + NotificationSystem (Mocked)
# =============================================================================


class TestEscalationNotificationIntegration:
    """Tests for EscalationManager and notification system integration."""

    def test_p0_escalation_sends_urgent_alert(
        self,
        escalation_manager,
        notification_system,
    ):
        """P0 escalations should send urgent alerts."""
        # Create P0 escalation (data loss risk)
        failure_context = FailureContext(
            error_message="Database corruption detected",
            error_type="DataIntegrityError",
            component="database",
            is_data_loss_risk=True,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[],
            failure_reason="Data integrity at risk",
            session_id="session-p0",
        )

        ticket = escalation_manager.escalate(escalation_context)
        assert ticket.priority == Priority.P0

        # Send notification
        alert = notification_system.send_alert(
            priority=ticket.priority.value,
            title=ticket.title,
            message=ticket.description[:500],
            channel="urgent",
            metadata={"ticket_id": ticket.ticket_id},
        )

        # Verify alert
        assert alert.priority == "P0"
        assert alert.channel == "urgent"
        assert ticket.ticket_id in alert.metadata.values()

        # Verify urgent channel has the alert
        urgent_alerts = notification_system.get_alerts_by_channel("urgent")
        assert len(urgent_alerts) == 1
        assert urgent_alerts[0].alert_id == alert.alert_id

    def test_p1_escalation_sends_high_priority_alert(
        self,
        escalation_manager,
        notification_system,
    ):
        """P1 escalations should send high priority alerts."""
        failure_context = FailureContext(
            error_message="System crash detected",
            error_type="SystemCrash",
            component="orchestrator",
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["restart_attempted"],
            failure_reason="System unresponsive",
            session_id="session-p1",
        )

        ticket = escalation_manager.escalate(escalation_context)

        # Send notification
        alert = notification_system.send_alert(
            priority=ticket.priority.value,
            title=ticket.title,
            message=ticket.description[:500],
            channel="high-priority",
            metadata={"ticket_id": ticket.ticket_id},
        )

        # Verify
        high_priority_alerts = notification_system.get_alerts_by_priority("P1")
        assert len(high_priority_alerts) == 1

    def test_multiple_escalations_send_multiple_alerts(
        self,
        escalation_manager,
        notification_system,
    ):
        """Multiple escalations should result in multiple alerts."""
        for i in range(3):
            failure_context = FailureContext(
                error_message=f"Error {i}",
                error_type="TestError",
                component=f"component_{i}",
                attempts=5,
                max_attempts=3,
            )
            escalation_context = EscalationContext(
                failure_context=failure_context,
                attempted_fixes=[],
                failure_reason=f"Test failure {i}",
                session_id=f"session-{i}",
            )

            ticket = escalation_manager.escalate(escalation_context)

            notification_system.send_alert(
                priority=ticket.priority.value,
                title=ticket.title,
                message=f"Alert for ticket {ticket.ticket_id}",
                channel="default",
            )

        # Verify all alerts sent
        assert len(notification_system.alerts) == 3

    def test_alert_routing_by_priority(
        self,
        escalation_manager,
        notification_system,
    ):
        """Alerts should be routed to appropriate channels based on priority."""
        priority_channels = {
            Priority.P0: "pagerduty",
            Priority.P1: "slack-urgent",
            Priority.P2: "slack-alerts",
            Priority.P3: "slack-notifications",
        }

        # Create escalations of different priorities
        test_cases = [
            (Priority.P0, True, "DataIntegrityError"),
            (Priority.P1, False, "SystemError"),
            (Priority.P2, False, "ConnectionError"),
            (Priority.P3, False, "WarningError"),
        ]

        for i, (expected_priority, is_data_loss, error_type) in enumerate(test_cases):
            failure_context = FailureContext(
                error_message=f"Error {i}",
                error_type=error_type,
                component=f"component_{i}",
                is_data_loss_risk=is_data_loss,
                attempts=5 if expected_priority == Priority.P2 else 1,
            )
            escalation_context = EscalationContext(
                failure_context=failure_context,
                attempted_fixes=[],
                failure_reason=f"Test {i}",
                session_id=f"session-priority-{i}",
            )

            ticket = escalation_manager.escalate(escalation_context)
            channel = priority_channels[ticket.priority]

            notification_system.send_alert(
                priority=ticket.priority.value,
                title=ticket.title,
                message=ticket.description[:200],
                channel=channel,
            )

        # Verify routing
        pagerduty_alerts = notification_system.get_alerts_by_channel("pagerduty")
        assert len(pagerduty_alerts) >= 1


# =============================================================================
# END-TO-END INTEGRATION FLOW
# =============================================================================


class TestEndToEndIntegration:
    """Tests for complete end-to-end integration flows."""

    def test_full_escalation_flow_with_successful_recovery(
        self,
        failure_predictor,
        escalation_manager,
        recovery_handler,
        notification_system,
        stuck_loop_state,
    ):
        """Test complete flow: prediction -> escalation -> notification -> recovery."""
        # Step 1: Predict failure
        prediction = failure_predictor.predict(stuck_loop_state)
        assert prediction.failure_predicted is True

        # Step 2: Get recovery suggestion
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Step 3: Create escalation
        failure_context = FailureContext(
            error_message=prediction.details,
            error_type=prediction.failure_type.value,
            component="agent_executor",
            attempts=5,
            max_attempts=3,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[suggestion.action.value],
            failure_reason=f"Predicted: {prediction.failure_type.value}",
            session_id=stuck_loop_state.session_id,
        )

        ticket = escalation_manager.escalate(escalation_context)

        # Step 4: Send notification
        alert = notification_system.send_alert(
            priority=ticket.priority.value,
            title=ticket.title,
            message=ticket.description[:500],
            channel="default",
            metadata={"ticket_id": ticket.ticket_id, "session_id": stuck_loop_state.session_id},
        )

        # Step 5: Human provides guidance and resumes
        resume_result = escalation_manager.resume(
            ticket_id=ticket.ticket_id,
            human_guidance="Reset context and retry with different approach",
        )
        assert resume_result.success is True

        # Step 6: Recovery handler acts
        recovery_result = recovery_handler.attempt_recovery(
            suggestion=suggestion,
            context=resume_result.resume_context,
        )

        # Verify complete flow
        assert len(notification_system.alerts) == 1
        assert len(recovery_handler.recovery_attempts) == 1
        assert escalation_manager.get_ticket(ticket.ticket_id).status == "resumed"

    def test_full_flow_with_failed_recovery_and_re_escalation(
        self,
        failure_predictor,
        escalation_manager,
        recovery_handler,
        notification_system,
        error_accumulation_state,
    ):
        """Test flow where recovery fails and re-escalation is needed."""
        # Set recovery to always fail
        recovery_handler.set_success_rate(0.0)

        # Step 1: Initial prediction
        prediction = failure_predictor.predict(error_accumulation_state)
        suggestion = failure_predictor.get_recovery_suggestion(prediction)

        # Step 2: First escalation
        failure_context = FailureContext(
            error_message=prediction.details,
            error_type="ErrorAccumulation",
            component="test_runner",
            attempts=3,
            max_attempts=3,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[],
            failure_reason="Error accumulation",
            session_id=error_accumulation_state.session_id,
        )

        ticket1 = escalation_manager.escalate(escalation_context)

        # Step 3: Send alert
        notification_system.send_alert(
            priority=ticket1.priority.value,
            title=ticket1.title,
            message="First escalation",
            channel="default",
        )

        # Step 4: Resume and attempt recovery (will fail)
        resume_result = escalation_manager.resume(
            ticket_id=ticket1.ticket_id,
            human_guidance="Try retry",
        )

        recovery_result = recovery_handler.attempt_recovery(
            suggestion=suggestion,
            context=resume_result.resume_context,
        )
        assert recovery_result.success is False

        # Step 5: Re-escalate with higher priority
        failure_context2 = FailureContext(
            error_message="Recovery failed",
            error_type="RecoveryFailure",
            component="recovery_handler",
            attempts=4,
            max_attempts=3,
        )
        escalation_context2 = EscalationContext(
            failure_context=failure_context2,
            attempted_fixes=["retry_failed", "reset_failed"],
            failure_reason="All recovery attempts failed",
            session_id=error_accumulation_state.session_id,
        )

        # Override to P1 since recovery failed
        ticket2 = escalation_manager.escalate(
            escalation_context2,
            override_priority=Priority.P1,
        )

        # Step 6: Send urgent alert
        notification_system.send_alert(
            priority=ticket2.priority.value,
            title=ticket2.title,
            message="Recovery failed - escalating",
            channel="urgent",
        )

        # Verify
        assert len(notification_system.alerts) == 2
        assert ticket2.priority == Priority.P1
        urgent_alerts = notification_system.get_alerts_by_channel("urgent")
        assert len(urgent_alerts) == 1

    def test_concurrent_escalations_and_notifications(
        self,
        escalation_manager,
        notification_system,
    ):
        """Test concurrent escalations from multiple sessions."""
        errors = []
        tickets = []

        def create_escalation(session_id: str, error_idx: int):
            try:
                failure_context = FailureContext(
                    error_message=f"Concurrent error {error_idx}",
                    error_type="ConcurrencyTest",
                    component=f"worker_{error_idx}",
                    attempts=4,
                    max_attempts=3,
                )
                escalation_context = EscalationContext(
                    failure_context=failure_context,
                    attempted_fixes=[],
                    failure_reason=f"Test {error_idx}",
                    session_id=session_id,
                )

                ticket = escalation_manager.escalate(escalation_context)
                tickets.append(ticket)

                notification_system.send_alert(
                    priority=ticket.priority.value,
                    title=ticket.title,
                    message=f"Alert {error_idx}",
                    channel="concurrent-test",
                )
            except Exception as e:
                errors.append(e)

        # Create 10 concurrent escalations
        threads = []
        for i in range(10):
            t = threading.Thread(
                target=create_escalation,
                args=(f"session-concurrent-{i}", i),
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no errors
        assert len(errors) == 0

        # Verify all tickets created
        assert len(tickets) == 10

        # Verify all alerts sent
        assert len(notification_system.alerts) == 10

        # Verify all ticket IDs are unique
        ticket_ids = [t.ticket_id for t in tickets]
        assert len(set(ticket_ids)) == 10


# =============================================================================
# PERSISTENCE INTEGRATION
# =============================================================================


class TestPersistenceIntegration:
    """Tests for persistence integration between components."""

    def test_escalation_persistence_survives_restart(self, tmp_path):
        """Escalations should persist and be loadable after restart."""
        storage_dir = tmp_path / "escalation_store"

        # Create manager and escalate
        manager1 = EscalationManager(storage_dir=storage_dir)

        failure_context = FailureContext(
            error_message="Persistent error",
            error_type="PersistenceTest",
            component="test_component",
            attempts=4,
            max_attempts=3,
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=["fix1", "fix2"],
            failure_reason="Testing persistence",
            session_id="session-persist",
            feature_id="feature-persist",
            issue_number=123,
        )

        ticket = manager1.escalate(escalation_context)
        ticket_id = ticket.ticket_id
        manager1.save()

        # Create new manager and load
        manager2 = EscalationManager(storage_dir=storage_dir)
        manager2.load()

        # Verify ticket persisted
        loaded_ticket = manager2.get_ticket(ticket_id)
        assert loaded_ticket is not None
        assert loaded_ticket.ticket_id == ticket_id
        assert loaded_ticket.session_state.get("session_id") == "session-persist"
        assert loaded_ticket.session_state.get("feature_id") == "feature-persist"

    def test_resume_persists_status_change(self, tmp_path):
        """Resume status changes should persist."""
        storage_dir = tmp_path / "resume_persist"

        manager1 = EscalationManager(storage_dir=storage_dir)

        failure_context = FailureContext(
            error_message="Resume test",
            error_type="Test",
            component="test",
        )
        escalation_context = EscalationContext(
            failure_context=failure_context,
            attempted_fixes=[],
            failure_reason="Test",
            session_id="session-resume-persist",
        )

        ticket = manager1.escalate(escalation_context)
        ticket_id = ticket.ticket_id

        # Resume
        manager1.resume(ticket_id, "Human guidance here")
        manager1.save()

        # Load in new manager
        manager2 = EscalationManager(storage_dir=storage_dir)
        manager2.load()

        loaded_ticket = manager2.get_ticket(ticket_id)
        assert loaded_ticket.status == "resumed"

    def test_history_filtering_after_load(self, tmp_path):
        """History filtering should work after loading from persistence."""
        storage_dir = tmp_path / "history_filter"

        manager1 = EscalationManager(storage_dir=storage_dir)

        # Create tickets with different priorities
        for i, (is_data_loss, error_type, feature_id) in enumerate([
            (True, "DataIntegrityError", "feature-a"),
            (False, "SystemError", "feature-b"),
            (False, "ConnectionError", "feature-a"),
        ]):
            fc = FailureContext(
                error_message=f"Error {i}",
                error_type=error_type,
                component=f"comp_{i}",
                is_data_loss_risk=is_data_loss,
                attempts=5 if "Connection" in error_type else 1,
            )
            ec = EscalationContext(
                failure_context=fc,
                attempted_fixes=[],
                failure_reason=f"Reason {i}",
                session_id=f"session-{i}",
                feature_id=feature_id,
            )
            manager1.escalate(ec)

        manager1.save()

        # Load in new manager
        manager2 = EscalationManager(storage_dir=storage_dir)
        manager2.load()

        # Test filtering
        p0_tickets = manager2.get_history(priority=Priority.P0)
        assert len(p0_tickets) >= 1

        feature_a_tickets = manager2.get_history(feature_id="feature-a")
        assert len(feature_a_tickets) == 2
