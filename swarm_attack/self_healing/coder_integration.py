"""Integration module connecting self-healing layer to CoderAgent.

This module provides CoderSelfHealingIntegration, which wires together:
- FailurePredictor: Detects failure trajectories before task completion
- EscalationManager: Manages human-in-loop escalation with context preservation
- RecoveryAgent: (via context handoff) Analyzes failures and generates recovery plans

The integration provides hooks for the CoderAgent execution loop:
- pre_execution_hook: Initialize execution state tracking
- post_action_hook: Record actions and check health after each action
- on_error_hook: Record errors and suggest recovery actions
- post_execution_hook: Generate execution summary

Usage:
    integration = CoderSelfHealingIntegration()

    # Before coder execution
    state = integration.pre_execution_hook(context)

    # After each action
    prediction = integration.post_action_hook(state, action, token_delta=100)
    if not prediction.failure_predicted:
        continue_execution()
    else:
        suggestion = integration.get_recovery_suggestion(prediction)
        handle_recovery(suggestion)

    # On error
    suggestion = integration.on_error_hook(state, error)

    # After execution
    summary = integration.post_execution_hook(state, success=True)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from swarm_attack.self_healing.failure_predictor import (
    ExecutionState,
    FailurePredictor,
    PredictionResult,
    RecoveryAction,
    RecoverySuggestion,
)
from swarm_attack.self_healing.escalation_manager import (
    EscalationContext,
    EscalationManager,
    EscalationTicket,
    FailureContext,
)


class CoderSelfHealingIntegration:
    """Integrates self-healing capabilities into CoderAgent execution loop.

    This class provides a unified interface for:
    - Execution state tracking (actions, errors, tokens, confidence)
    - Health checking during execution (failure prediction)
    - Recovery suggestions when failures are predicted
    - Escalation to human operators when recovery is not possible
    - Event emission for monitoring and logging

    Attributes:
        failure_predictor: Predictor for detecting failure trajectories.
        escalation_manager: Manager for human-in-loop escalations.
    """

    def __init__(
        self,
        failure_predictor: Optional[FailurePredictor] = None,
        escalation_manager: Optional[EscalationManager] = None,
    ):
        """Initialize the integration with optional custom components.

        Args:
            failure_predictor: Custom failure predictor. Uses defaults if None.
            escalation_manager: Custom escalation manager. Uses defaults if None.
        """
        self.failure_predictor = failure_predictor or FailurePredictor()
        self.escalation_manager = escalation_manager or EscalationManager()
        self._event_listeners: list[Callable[[dict[str, Any]], None]] = []

    # =========================================================================
    # Execution State Management
    # =========================================================================

    def create_execution_state(
        self,
        session_id: str,
        token_usage: int,
        token_limit: int,
        actions: Optional[list[dict[str, Any]]] = None,
        errors: Optional[list[dict[str, Any]]] = None,
        confidence_scores: Optional[list[float]] = None,
    ) -> ExecutionState:
        """Create a new ExecutionState for tracking coder execution.

        Args:
            session_id: Unique session identifier.
            token_usage: Current token usage count.
            token_limit: Maximum token limit for context window.
            actions: Optional initial list of actions.
            errors: Optional initial list of errors.
            confidence_scores: Optional initial confidence scores.

        Returns:
            ExecutionState instance ready for tracking.
        """
        return ExecutionState(
            session_id=session_id,
            actions=actions or [],
            errors=errors or [],
            token_usage=max(0, token_usage),  # Ensure non-negative
            token_limit=token_limit,
            confidence_scores=confidence_scores or [],
        )

    def record_action(self, state: ExecutionState, action: Optional[dict[str, Any]]) -> None:
        """Record an action into the execution state.

        Args:
            state: The execution state to update.
            action: The action to record. None values are ignored.
        """
        if action is not None:
            state.actions.append(action)

    def record_error(self, state: ExecutionState, error: dict[str, Any]) -> None:
        """Record an error into the execution state.

        Args:
            state: The execution state to update.
            error: The error to record.
        """
        state.errors.append(error)

    def record_confidence(self, state: ExecutionState, confidence: float) -> None:
        """Record a confidence score into the execution state.

        Args:
            state: The execution state to update.
            confidence: The confidence score (0.0-1.0).
        """
        state.confidence_scores.append(confidence)

    def update_token_usage(self, state: ExecutionState, token_usage: int) -> None:
        """Update the token usage in the execution state.

        Args:
            state: The execution state to update.
            token_usage: The new token usage value.
        """
        state.token_usage = token_usage

    # =========================================================================
    # Health Checking
    # =========================================================================

    def check_health(self, state: ExecutionState) -> PredictionResult:
        """Check the health of the current execution.

        Uses the FailurePredictor to analyze the execution state and
        predict potential failures.

        Args:
            state: The current execution state.

        Returns:
            PredictionResult indicating if failure is predicted.
        """
        result = self.failure_predictor.predict(state)

        # Emit health check event
        self._emit_event({
            "type": "health_check",
            "session_id": state.session_id,
            "failure_predicted": result.failure_predicted,
            "failure_type": result.failure_type.value if result.failure_type else None,
            "confidence": result.confidence,
            "token_usage_ratio": state.token_usage_ratio,
        })

        return result

    def get_recovery_suggestion(self, prediction: PredictionResult) -> RecoverySuggestion:
        """Get a recovery suggestion for a prediction result.

        Args:
            prediction: The prediction result from check_health.

        Returns:
            RecoverySuggestion with recommended action.
        """
        return self.failure_predictor.get_recovery_suggestion(prediction)

    def should_continue(self, state: ExecutionState) -> tuple[bool, Optional[str]]:
        """Determine if execution should continue.

        Convenience method that combines check_health with a continue decision.

        Args:
            state: The current execution state.

        Returns:
            Tuple of (should_continue, reason).
            - (True, None) if execution should continue
            - (False, reason) if execution should stop
        """
        prediction = self.check_health(state)

        if not prediction.failure_predicted:
            return True, None

        # Map failure types to reasons
        reason_map = {
            "token_exhaustion": "Token usage approaching limit, session handoff required",
            "stuck_loop": "Execution stuck in a loop, context reset needed",
            "confidence_drop": "Model confidence dropping, escalation recommended",
            "error_accumulation": "Multiple errors accumulated, retry with fresh approach",
        }

        failure_type = prediction.failure_type.value if prediction.failure_type else "unknown"
        reason = reason_map.get(failure_type, prediction.details)

        return False, reason

    # =========================================================================
    # Escalation
    # =========================================================================

    def should_escalate(self, failure_context: FailureContext) -> bool:
        """Determine if human escalation is needed.

        Delegates to EscalationManager's should_escalate method.

        Args:
            failure_context: Context about the failure.

        Returns:
            True if escalation should be triggered.
        """
        return self.escalation_manager.should_escalate(failure_context)

    def escalate(
        self,
        context: EscalationContext,
        override_priority: Optional[Any] = None,
    ) -> EscalationTicket:
        """Create an escalation ticket with full context.

        Args:
            context: The escalation context.
            override_priority: Optional priority override.

        Returns:
            The created escalation ticket.
        """
        ticket = self.escalation_manager.escalate(context, override_priority)

        # Emit escalation event
        self._emit_event({
            "type": "escalation_created",
            "ticket_id": ticket.ticket_id,
            "priority": ticket.priority.value if hasattr(ticket.priority, 'value') else ticket.priority,
            "status": ticket.status,
            "session_id": context.session_id,
            "feature_id": context.feature_id,
            "issue_number": context.issue_number,
        })

        return ticket

    # =========================================================================
    # CoderAgent Hooks
    # =========================================================================

    def pre_execution_hook(self, context: dict[str, Any]) -> ExecutionState:
        """Hook called before CoderAgent execution starts.

        Creates and returns an ExecutionState for tracking the execution.

        Args:
            context: CoderAgent context dictionary containing:
                - session_id: Session identifier
                - token_usage: Current token usage
                - token_limit: Maximum token limit

        Returns:
            ExecutionState for tracking execution.
        """
        return self.create_execution_state(
            session_id=context.get("session_id", "unknown"),
            token_usage=context.get("token_usage", 0),
            token_limit=context.get("token_limit", 10000),
        )

    def post_action_hook(
        self,
        state: ExecutionState,
        action: dict[str, Any],
        token_delta: int = 0,
        confidence: Optional[float] = None,
    ) -> PredictionResult:
        """Hook called after each action in the CoderAgent execution.

        Records the action, updates token usage, and checks health.

        Args:
            state: The current execution state.
            action: The action that was performed.
            token_delta: Change in token usage from this action.
            confidence: Optional confidence score for this action.

        Returns:
            PredictionResult from health check.
        """
        self.record_action(state, action)
        self.update_token_usage(state, state.token_usage + token_delta)

        if confidence is not None:
            self.record_confidence(state, confidence)

        return self.check_health(state)

    def on_error_hook(
        self,
        state: ExecutionState,
        error: dict[str, Any],
    ) -> RecoverySuggestion:
        """Hook called when an error occurs in the CoderAgent execution.

        Records the error and returns a recovery suggestion.

        Args:
            state: The current execution state.
            error: The error that occurred.

        Returns:
            RecoverySuggestion for handling the error.
        """
        self.record_error(state, error)

        # Check health after recording error
        prediction = self.check_health(state)

        # Get recovery suggestion
        return self.get_recovery_suggestion(prediction)

    def post_execution_hook(
        self,
        state: ExecutionState,
        success: bool,
        output: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Hook called after CoderAgent execution completes.

        Generates an execution summary.

        Args:
            state: The final execution state.
            success: Whether the execution was successful.
            output: Optional output from the execution.

        Returns:
            Dictionary with execution summary.
        """
        summary = {
            "session_id": state.session_id,
            "success": success,
            "total_actions": len(state.actions),
            "total_errors": len(state.errors),
            "final_token_usage": state.token_usage,
            "token_limit": state.token_limit,
            "token_usage_ratio": state.token_usage_ratio,
        }

        # Add confidence statistics if available
        if state.confidence_scores:
            summary["confidence_stats"] = {
                "min": min(state.confidence_scores),
                "max": max(state.confidence_scores),
                "avg": sum(state.confidence_scores) / len(state.confidence_scores),
                "count": len(state.confidence_scores),
            }

        if output:
            summary["output"] = output

        return summary

    # =========================================================================
    # RecoveryAgent Integration
    # =========================================================================

    def create_recovery_context(
        self,
        state: ExecutionState,
        feature_id: str,
        issue_number: int,
        failure_type: str,
        error_output: str,
        retry_count: int = 0,
    ) -> dict[str, Any]:
        """Create context for RecoveryAgent from execution state.

        This method prepares a context dictionary suitable for passing
        to RecoveryAgent.run().

        Args:
            state: The current execution state.
            feature_id: Feature being worked on.
            issue_number: Issue number being implemented.
            failure_type: Type of failure that occurred.
            error_output: Error output from the failed run.
            retry_count: Number of retries already attempted.

        Returns:
            Dictionary suitable for RecoveryAgent.run().
        """
        return {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "failure_type": failure_type,
            "error_output": error_output,
            "session_id": state.session_id,
            "retry_count": retry_count,
            "execution_state": {
                "actions_count": len(state.actions),
                "errors_count": len(state.errors),
                "token_usage": state.token_usage,
                "token_limit": state.token_limit,
                "recent_errors": state.errors[-5:] if state.errors else [],
            },
        }

    # =========================================================================
    # Event System
    # =========================================================================

    def add_event_listener(
        self,
        listener: Callable[[dict[str, Any]], None],
    ) -> None:
        """Add an event listener for monitoring.

        Args:
            listener: Callable that receives event dictionaries.
        """
        self._event_listeners.append(listener)

    def remove_event_listener(
        self,
        listener: Callable[[dict[str, Any]], None],
    ) -> None:
        """Remove an event listener.

        Args:
            listener: The listener to remove.
        """
        if listener in self._event_listeners:
            self._event_listeners.remove(listener)

    def _emit_event(self, event: dict[str, Any]) -> None:
        """Emit an event to all listeners.

        Args:
            event: The event dictionary to emit.
        """
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception:
                # Don't let listener errors break execution
                pass
