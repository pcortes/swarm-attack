"""Failure predictor for detecting failure trajectories before task completion.

This module provides the FailurePredictor class which analyzes execution state
to predict potential failures and suggest recovery actions.

Signals detected:
- Stuck loops (repeated similar actions)
- Token exhaustion (approaching context limit)
- Confidence drops (model uncertainty increasing)
- Error accumulation (multiple recoverable errors)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FailureType(Enum):
    """Types of failures that can be predicted."""

    STUCK_LOOP = "stuck_loop"
    TOKEN_EXHAUSTION = "token_exhaustion"
    CONFIDENCE_DROP = "confidence_drop"
    ERROR_ACCUMULATION = "error_accumulation"


class RecoveryAction(Enum):
    """Actions that can be taken to recover from predicted failures."""

    HANDOFF = "handoff"
    RETRY = "retry"
    ESCALATE = "escalate"
    RESET_CONTEXT = "reset_context"
    CONTINUE = "continue"


@dataclass
class ExecutionState:
    """Represents the current execution state of an agent session.

    Attributes:
        session_id: Unique identifier for the session.
        actions: List of actions performed in the session.
        errors: List of errors encountered during execution.
        token_usage: Current token usage count.
        token_limit: Maximum token limit for the context window.
        confidence_scores: List of confidence scores for recent actions.
    """

    session_id: str
    actions: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    token_usage: int
    token_limit: int
    confidence_scores: list[float]

    @property
    def token_usage_ratio(self) -> float:
        """Calculate the ratio of token usage to limit.

        Returns:
            Float between 0.0 and 1.0 representing usage ratio.
            Returns 1.0 if token_limit is 0.
        """
        if self.token_limit <= 0:
            return 1.0
        return self.token_usage / self.token_limit


@dataclass
class PredictionResult:
    """Result of failure prediction analysis.

    Attributes:
        failure_predicted: Whether a failure is predicted.
        failure_type: Type of failure predicted, if any.
        confidence: Confidence level of the prediction (0.0-1.0).
        details: Human-readable details about the prediction.
    """

    failure_predicted: bool
    failure_type: Optional[FailureType]
    confidence: float
    details: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "failure_predicted": self.failure_predicted,
            "failure_type": self.failure_type.value if self.failure_type else None,
            "confidence": self.confidence,
            "details": self.details,
        }


@dataclass
class RecoverySuggestion:
    """Suggested recovery action for a predicted failure.

    Attributes:
        action: The recommended recovery action.
        reason: Explanation for why this action is suggested.
        priority: Priority level (1=highest, 3=lowest).
        details: Additional details or parameters for the action.
    """

    action: RecoveryAction
    reason: str
    priority: int
    details: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "action": self.action.value,
            "reason": self.reason,
            "priority": self.priority,
            "details": self.details,
        }


class FailurePredictor:
    """Predicts potential failures by analyzing execution state.

    The predictor analyzes various signals to detect failure trajectories
    before they occur, allowing for proactive recovery actions.

    Attributes:
        stuck_loop_threshold: Number of similar actions to trigger stuck loop detection.
        token_exhaustion_threshold: Token usage ratio to trigger exhaustion warning.
        confidence_drop_threshold: Minimum confidence drop to trigger detection.
        error_accumulation_threshold: Number of errors to trigger accumulation warning.
    """

    # Default thresholds
    DEFAULT_STUCK_LOOP_THRESHOLD: int = 5
    DEFAULT_TOKEN_EXHAUSTION_THRESHOLD: float = 0.85
    DEFAULT_CONFIDENCE_DROP_THRESHOLD: float = 0.2
    DEFAULT_ERROR_ACCUMULATION_THRESHOLD: int = 3
    DEFAULT_MIN_CONFIDENCE_SCORES: int = 2

    def __init__(
        self,
        stuck_loop_threshold: Optional[int] = None,
        token_exhaustion_threshold: Optional[float] = None,
        confidence_drop_threshold: Optional[float] = None,
        error_accumulation_threshold: Optional[int] = None,
    ):
        """Initialize the FailurePredictor.

        Args:
            stuck_loop_threshold: Number of similar actions to trigger stuck loop.
            token_exhaustion_threshold: Token usage ratio (0.0-1.0) to trigger warning.
            confidence_drop_threshold: Minimum drop in confidence to trigger detection.
            error_accumulation_threshold: Number of errors to trigger warning.
        """
        self.stuck_loop_threshold = (
            stuck_loop_threshold
            if stuck_loop_threshold is not None
            else self.DEFAULT_STUCK_LOOP_THRESHOLD
        )
        self.token_exhaustion_threshold = (
            token_exhaustion_threshold
            if token_exhaustion_threshold is not None
            else self.DEFAULT_TOKEN_EXHAUSTION_THRESHOLD
        )
        self.confidence_drop_threshold = (
            confidence_drop_threshold
            if confidence_drop_threshold is not None
            else self.DEFAULT_CONFIDENCE_DROP_THRESHOLD
        )
        self.error_accumulation_threshold = (
            error_accumulation_threshold
            if error_accumulation_threshold is not None
            else self.DEFAULT_ERROR_ACCUMULATION_THRESHOLD
        )

    def predict(self, execution_state: ExecutionState) -> PredictionResult:
        """Analyze execution state and predict potential failures.

        Checks for multiple failure types in priority order:
        1. Token exhaustion (highest priority - immediate action needed)
        2. Stuck loop (next highest - wasting resources)
        3. Error accumulation (recoverable but concerning)
        4. Confidence drop (may indicate confusion)

        Args:
            execution_state: Current state of the execution.

        Returns:
            PredictionResult indicating if failure is predicted and details.
        """
        # Filter out None actions
        valid_actions = [a for a in execution_state.actions if a is not None]

        # Priority 1: Check token exhaustion first (most critical)
        token_result = self._check_token_exhaustion(execution_state)
        if token_result.failure_predicted:
            return token_result

        # Priority 2: Check for stuck loops
        stuck_result = self._check_stuck_loop(valid_actions)
        if stuck_result.failure_predicted:
            return stuck_result

        # Priority 3: Check error accumulation
        error_result = self._check_error_accumulation(
            execution_state.errors, len(valid_actions)
        )
        if error_result.failure_predicted:
            return error_result

        # Priority 4: Check confidence drops
        confidence_result = self._check_confidence_drop(execution_state.confidence_scores)
        if confidence_result.failure_predicted:
            return confidence_result

        # No failure predicted
        return PredictionResult(
            failure_predicted=False,
            failure_type=None,
            confidence=0.0,
            details="No failure patterns detected",
        )

    def get_recovery_suggestion(self, prediction: PredictionResult) -> RecoverySuggestion:
        """Get suggested recovery action for a prediction.

        Args:
            prediction: The prediction result to get recovery for.

        Returns:
            RecoverySuggestion with recommended action.
        """
        if not prediction.failure_predicted or prediction.failure_type is None:
            return RecoverySuggestion(
                action=RecoveryAction.CONTINUE,
                reason="No failure predicted, continue normal operation",
                priority=3,
            )

        if prediction.failure_type == FailureType.TOKEN_EXHAUSTION:
            return RecoverySuggestion(
                action=RecoveryAction.HANDOFF,
                reason="Session approaching context limit, handoff required",
                priority=1,
                details={"prediction_confidence": prediction.confidence},
            )

        if prediction.failure_type == FailureType.STUCK_LOOP:
            return RecoverySuggestion(
                action=RecoveryAction.RESET_CONTEXT,
                reason="Session stuck in a loop, context reset recommended",
                priority=2,
                details={"loop_details": prediction.details},
            )

        if prediction.failure_type == FailureType.CONFIDENCE_DROP:
            return RecoverySuggestion(
                action=RecoveryAction.ESCALATE,
                reason="Model confidence dropping, escalation to human recommended",
                priority=2,
                details={"confidence_trend": prediction.details},
            )

        if prediction.failure_type == FailureType.ERROR_ACCUMULATION:
            return RecoverySuggestion(
                action=RecoveryAction.RETRY,
                reason="Multiple errors accumulated, retry with fresh approach",
                priority=2,
                details={"error_details": prediction.details},
            )

        # Fallback
        return RecoverySuggestion(
            action=RecoveryAction.ESCALATE,
            reason=f"Unknown failure type: {prediction.failure_type}",
            priority=1,
        )

    def _check_token_exhaustion(self, state: ExecutionState) -> PredictionResult:
        """Check for token exhaustion.

        Args:
            state: Current execution state.

        Returns:
            PredictionResult for token exhaustion check.
        """
        usage_ratio = state.token_usage_ratio

        if usage_ratio >= self.token_exhaustion_threshold:
            # Calculate confidence based on how close to limit
            # At threshold: 0.8, at 95%: 0.9, at 100%: 1.0
            confidence = min(1.0, 0.8 + (usage_ratio - self.token_exhaustion_threshold) * 2)

            percentage = int(usage_ratio * 100)
            return PredictionResult(
                failure_predicted=True,
                failure_type=FailureType.TOKEN_EXHAUSTION,
                confidence=confidence,
                details=f"Token usage at {percentage}% of limit",
            )

        return PredictionResult(
            failure_predicted=False,
            failure_type=None,
            confidence=0.0,
            details="Token usage within acceptable range",
        )

    def _check_stuck_loop(self, actions: list[dict[str, Any]]) -> PredictionResult:
        """Check for stuck loop patterns.

        Detects when the same action is repeated multiple times,
        indicating the agent may be stuck.

        Args:
            actions: List of actions to analyze.

        Returns:
            PredictionResult for stuck loop check.
        """
        if len(actions) < self.stuck_loop_threshold:
            return PredictionResult(
                failure_predicted=False,
                failure_type=None,
                confidence=0.0,
                details="Not enough actions to detect stuck loop",
            )

        # Check the most recent actions for repetition
        recent_actions = actions[-self.stuck_loop_threshold:]

        # Create action signatures for comparison
        def action_signature(action: dict[str, Any]) -> tuple[str, str]:
            """Create a hashable signature for an action."""
            action_type = action.get("type", "")
            action_path = action.get("path", "")
            return (action_type, action_path)

        signatures = [action_signature(a) for a in recent_actions]

        # Check if all recent actions are identical
        if len(set(signatures)) == 1:
            confidence = min(1.0, 0.7 + (len(recent_actions) - self.stuck_loop_threshold) * 0.05)
            return PredictionResult(
                failure_predicted=True,
                failure_type=FailureType.STUCK_LOOP,
                confidence=confidence,
                details=f"Detected {len(recent_actions)} repeated identical actions",
            )

        # Check for oscillating patterns (A-B-A-B)
        if len(recent_actions) >= 4:
            even_actions = [signatures[i] for i in range(0, len(signatures), 2)]
            odd_actions = [signatures[i] for i in range(1, len(signatures), 2)]

            if len(set(even_actions)) == 1 and len(set(odd_actions)) == 1 and even_actions[0] != odd_actions[0]:
                return PredictionResult(
                    failure_predicted=True,
                    failure_type=FailureType.STUCK_LOOP,
                    confidence=0.75,
                    details="Detected oscillating action pattern (A-B-A-B)",
                )

        return PredictionResult(
            failure_predicted=False,
            failure_type=None,
            confidence=0.0,
            details="No stuck loop pattern detected",
        )

    def _check_confidence_drop(self, confidence_scores: list[float]) -> PredictionResult:
        """Check for confidence drops.

        Detects when model confidence is dropping over time.

        Args:
            confidence_scores: List of recent confidence scores.

        Returns:
            PredictionResult for confidence drop check.
        """
        if len(confidence_scores) < self.DEFAULT_MIN_CONFIDENCE_SCORES:
            return PredictionResult(
                failure_predicted=False,
                failure_type=None,
                confidence=0.0,
                details="Not enough confidence scores to analyze trend",
            )

        # Clamp scores to valid range
        valid_scores = [max(0.0, min(1.0, s)) for s in confidence_scores]

        # Calculate overall drop from first to last
        first_score = valid_scores[0]
        last_score = valid_scores[-1]
        overall_drop = first_score - last_score

        # Check for significant overall drop
        if overall_drop >= self.confidence_drop_threshold:
            confidence = min(1.0, 0.7 + overall_drop)
            return PredictionResult(
                failure_predicted=True,
                failure_type=FailureType.CONFIDENCE_DROP,
                confidence=confidence,
                details=f"Confidence dropped from {first_score:.2f} to {last_score:.2f}",
            )

        # Check for sudden drop (any adjacent pair)
        for i in range(len(valid_scores) - 1):
            drop = valid_scores[i] - valid_scores[i + 1]
            if drop >= self.confidence_drop_threshold * 1.5:  # Sudden drop threshold
                return PredictionResult(
                    failure_predicted=True,
                    failure_type=FailureType.CONFIDENCE_DROP,
                    confidence=0.8,
                    details=f"Sudden confidence drop from {valid_scores[i]:.2f} to {valid_scores[i+1]:.2f}",
                )

        return PredictionResult(
            failure_predicted=False,
            failure_type=None,
            confidence=0.0,
            details="Confidence scores are stable",
        )

    def _check_error_accumulation(
        self, errors: list[dict[str, Any]], action_count: int
    ) -> PredictionResult:
        """Check for error accumulation.

        Detects when errors are accumulating at an alarming rate.

        Args:
            errors: List of errors encountered.
            action_count: Number of actions performed.

        Returns:
            PredictionResult for error accumulation check.
        """
        error_count = len(errors)

        if error_count < self.error_accumulation_threshold:
            return PredictionResult(
                failure_predicted=False,
                failure_type=None,
                confidence=0.0,
                details="Error count below threshold",
            )

        # Calculate error rate relative to actions
        if action_count > 0:
            error_rate = error_count / action_count
            # If error rate is low (< 10%), don't flag as accumulation
            if error_rate < 0.1:
                return PredictionResult(
                    failure_predicted=False,
                    failure_type=None,
                    confidence=0.0,
                    details=f"Error rate ({error_rate:.1%}) is acceptable",
                )

        # Check for repeated same errors
        error_types = [e.get("type", "unknown") for e in errors]
        unique_errors = set(error_types)

        # More concerning if same error repeats
        if len(unique_errors) == 1 and error_count >= self.error_accumulation_threshold:
            confidence = min(1.0, 0.8 + (error_count - self.error_accumulation_threshold) * 0.1)
            return PredictionResult(
                failure_predicted=True,
                failure_type=FailureType.ERROR_ACCUMULATION,
                confidence=confidence,
                details=f"Same error repeated {error_count} times: {list(unique_errors)[0]}",
            )

        # General error accumulation
        confidence = min(1.0, 0.7 + error_count * 0.05)
        return PredictionResult(
            failure_predicted=True,
            failure_type=FailureType.ERROR_ACCUMULATION,
            confidence=confidence,
            details=f"{error_count} errors accumulated ({len(unique_errors)} unique types)",
        )
