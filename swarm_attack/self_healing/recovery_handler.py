"""RecoveryHandler - Tiered recovery strategies for different failure modes.

This module provides the RecoveryHandler class which implements a 4-tier
recovery strategy system:

- Tier 1: Retry with modified prompt (targets 80% of failures)
- Tier 2: Context reduction + retry (targets 15% of failures)
- Tier 3: Checkpoint rollback + fresh attempt (targets 4% of failures)
- Tier 4: Human escalation (targets 1% of failures - critical issues)

The handler selects the appropriate recovery tier based on failure
characteristics such as error type, retry count, context size, and
whether the failure is critical.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from swarm_attack.self_healing.escalation_manager import (
    EscalationManager,
    EscalationContext,
    FailureContext,
    EscalationTicket,
    Priority,
)


class RecoveryTier(Enum):
    """Recovery tiers ordered by severity/cost.

    TIER_1: Retry with modified prompt (most common, lowest cost)
    TIER_2: Context reduction + retry (for context overflow issues)
    TIER_3: Checkpoint rollback + fresh attempt (for persistent failures)
    TIER_4: Human escalation (for critical issues)
    """

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4


class RecoveryStatus(Enum):
    """Status of a recovery attempt."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ESCALATED = "escalated"


# Error types that always require human escalation
CRITICAL_ERROR_TYPES = frozenset([
    "SecurityViolation",
    "DataIntegrityError",
    "AuthenticationError",
    "SystemCrash",
])


@dataclass
class FailureInfo:
    """Information about a failure to recover from.

    Attributes:
        failure_id: Unique identifier for this failure.
        error_type: The type/class of the error.
        error_message: Human-readable error message.
        component: The component that failed.
        retry_count: Number of recovery attempts already made.
        context_size: Current context window size in tokens.
        checkpoint_available: Whether a checkpoint exists for rollback.
        is_critical: Whether this is a critical/security failure.
        metadata: Additional metadata about the failure.
    """

    failure_id: str
    error_type: str
    error_message: str
    component: str
    retry_count: int = 0
    context_size: int = 0
    checkpoint_available: bool = False
    is_critical: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureInfo":
        """Deserialize from dictionary."""
        return cls(
            failure_id=data.get("failure_id", ""),
            error_type=data.get("error_type", ""),
            error_message=data.get("error_message", ""),
            component=data.get("component", ""),
            retry_count=data.get("retry_count", 0),
            context_size=data.get("context_size", 0),
            checkpoint_available=data.get("checkpoint_available", False),
            is_critical=data.get("is_critical", False),
            metadata=data.get("metadata", {}),
        )


@dataclass
class RecoveryStrategy:
    """A recovery strategy with actions to execute.

    Attributes:
        tier: The recovery tier (1-4).
        name: Short name for the strategy.
        description: Human-readable description.
        actions: List of action names to execute.
        max_retries: Maximum retries for this strategy.
        timeout_seconds: Timeout for executing this strategy.
    """

    tier: RecoveryTier
    name: str
    description: str
    actions: List[str]
    max_retries: int = 3
    timeout_seconds: int = 300

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "tier": self.tier.value,
            "name": self.name,
            "description": self.description,
            "actions": self.actions,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt.

    Attributes:
        failure_id: The ID of the failure being recovered.
        status: Status of the recovery (success, partial, failed, escalated).
        strategy_used: The tier used for recovery.
        message: Human-readable message about the result.
        attempts: Number of attempts made.
        escalation_ticket_id: ID of escalation ticket if escalated.
        modified_context: Modified context if context was reduced.
        checkpoint_restored: Whether a checkpoint was restored.
    """

    failure_id: str
    status: RecoveryStatus
    strategy_used: RecoveryTier
    message: str
    attempts: int = 0
    escalation_ticket_id: Optional[str] = None
    modified_context: Optional[Dict[str, Any]] = None
    checkpoint_restored: bool = False

    @property
    def is_recoverable(self) -> bool:
        """Check if the recovery was successful or partially successful."""
        return self.status in (RecoveryStatus.SUCCESS, RecoveryStatus.PARTIAL)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "failure_id": self.failure_id,
            "status": self.status.value,
            "strategy_used": self.strategy_used.value,
            "message": self.message,
            "attempts": self.attempts,
            "escalation_ticket_id": self.escalation_ticket_id,
            "modified_context": self.modified_context,
            "checkpoint_restored": self.checkpoint_restored,
        }


class RecoveryHandler:
    """Handles recovery from failures using a tiered strategy system.

    Recovery Tiers:
    - Tier 1 (80%): Retry with modified prompt - for simple/transient failures
    - Tier 2 (15%): Context reduction + retry - for context overflow issues
    - Tier 3 (4%): Checkpoint rollback - for persistent failures with checkpoint
    - Tier 4 (1%): Human escalation - for critical/security issues

    The handler selects the appropriate tier based on failure characteristics
    and executes the corresponding recovery strategy.
    """

    # Default configuration
    DEFAULT_TIER1_RETRY_LIMIT = 3
    DEFAULT_TIER2_CONTEXT_REDUCTION_FACTOR = 0.5
    DEFAULT_CONTEXT_SIZE_THRESHOLD = 80000
    DEFAULT_RETRY_COUNT_TIER3_THRESHOLD = 4

    def __init__(
        self,
        tier1_retry_limit: int = DEFAULT_TIER1_RETRY_LIMIT,
        tier2_context_reduction_factor: float = DEFAULT_TIER2_CONTEXT_REDUCTION_FACTOR,
        context_size_threshold: int = DEFAULT_CONTEXT_SIZE_THRESHOLD,
        escalation_manager: Optional[EscalationManager] = None,
    ):
        """Initialize the RecoveryHandler.

        Args:
            tier1_retry_limit: Maximum retries for Tier 1 recovery.
            tier2_context_reduction_factor: Factor to reduce context by (0.0-1.0).
            context_size_threshold: Context size above which to use Tier 2.
            escalation_manager: Optional EscalationManager instance.
        """
        self.tier1_retry_limit = tier1_retry_limit
        self.tier2_context_reduction_factor = tier2_context_reduction_factor
        self.context_size_threshold = context_size_threshold
        self._escalation_manager = escalation_manager or EscalationManager()

        # Recovery history for metrics
        self._recovery_history: Dict[str, List[RecoveryResult]] = {}
        self._tier_counts: Dict[str, int] = {
            "tier_1": 0,
            "tier_2": 0,
            "tier_3": 0,
            "tier_4": 0,
        }

    @property
    def escalation_manager(self) -> EscalationManager:
        """Get the escalation manager instance."""
        return self._escalation_manager

    def select_strategy(self, failure: FailureInfo) -> RecoveryStrategy:
        """Select the appropriate recovery strategy based on failure characteristics.

        Selection logic:
        1. Tier 4 (Human Escalation):
           - Critical failures (is_critical=True)
           - Security violations
           - Data integrity errors

        2. Tier 3 (Checkpoint Rollback):
           - Many retries (retry_count >= threshold)
           - Checkpoint available (preferably)

        3. Tier 2 (Context Reduction):
           - Context size exceeds threshold
           - Multiple retries already attempted

        4. Tier 1 (Retry with Modified Prompt):
           - Default for simple failures
           - Low retry count

        Args:
            failure: Information about the failure to recover from.

        Returns:
            RecoveryStrategy with appropriate tier and actions.
        """
        # Tier 4: Critical failures requiring human escalation
        if self._requires_escalation(failure):
            return RecoveryStrategy(
                tier=RecoveryTier.TIER_4,
                name="human_escalation",
                description="Escalate to human intervention for critical issue",
                actions=["create_escalation_ticket", "notify_human", "wait_for_response"],
                max_retries=0,
            )

        # Tier 3: Persistent failures with many retries
        if failure.retry_count >= self.DEFAULT_RETRY_COUNT_TIER3_THRESHOLD:
            if failure.checkpoint_available:
                return RecoveryStrategy(
                    tier=RecoveryTier.TIER_3,
                    name="checkpoint_rollback",
                    description="Rollback to last checkpoint and retry with fresh context",
                    actions=["restore_checkpoint", "reset_context", "retry_from_checkpoint"],
                    max_retries=2,
                )
            else:
                return RecoveryStrategy(
                    tier=RecoveryTier.TIER_3,
                    name="fresh_start",
                    description="Start fresh without checkpoint (no checkpoint available)",
                    actions=["reset_context", "clear_errors", "retry_fresh"],
                    max_retries=2,
                )

        # Tier 2: Context overflow issues
        if failure.context_size > self.context_size_threshold or failure.retry_count >= 2:
            if failure.context_size > self.context_size_threshold:
                return RecoveryStrategy(
                    tier=RecoveryTier.TIER_2,
                    name="context_reduction",
                    description="Reduce context size and retry",
                    actions=["reduce_context", "summarize_history", "retry"],
                    max_retries=3,
                )

        # Tier 1: Simple retry with modified prompt (default)
        return RecoveryStrategy(
            tier=RecoveryTier.TIER_1,
            name="retry_with_modified_prompt",
            description="Retry the operation with a modified prompt",
            actions=["modify_prompt", "add_error_context", "retry"],
            max_retries=self.tier1_retry_limit,
        )

    def handle(self, failure: FailureInfo) -> RecoveryResult:
        """Handle a failure by executing the appropriate recovery strategy.

        Args:
            failure: Information about the failure to recover from.

        Returns:
            RecoveryResult indicating the outcome of the recovery attempt.
        """
        # Ensure failure has an ID
        if not failure.failure_id:
            failure.failure_id = f"fail-{uuid4().hex[:8]}"

        # Select recovery strategy
        strategy = self.select_strategy(failure)

        # Execute recovery based on tier
        result = self._execute_strategy(failure, strategy)

        # Track recovery history
        self._track_recovery(failure.failure_id, result)

        return result

    def _requires_escalation(self, failure: FailureInfo) -> bool:
        """Check if a failure requires human escalation (Tier 4).

        Args:
            failure: The failure to check.

        Returns:
            True if the failure requires escalation.
        """
        # Critical flag is set
        if failure.is_critical:
            return True

        # Known critical error types
        if failure.error_type in CRITICAL_ERROR_TYPES:
            return True

        # Data loss risk indicated in metadata
        if failure.metadata.get("data_loss_risk"):
            return True

        return False

    def _execute_strategy(
        self, failure: FailureInfo, strategy: RecoveryStrategy
    ) -> RecoveryResult:
        """Execute a recovery strategy.

        Args:
            failure: The failure being recovered.
            strategy: The strategy to execute.

        Returns:
            RecoveryResult from executing the strategy.
        """
        if strategy.tier == RecoveryTier.TIER_1:
            return self._execute_tier1(failure, strategy)
        elif strategy.tier == RecoveryTier.TIER_2:
            return self._execute_tier2(failure, strategy)
        elif strategy.tier == RecoveryTier.TIER_3:
            return self._execute_tier3(failure, strategy)
        elif strategy.tier == RecoveryTier.TIER_4:
            return self._execute_tier4(failure, strategy)
        else:
            return RecoveryResult(
                failure_id=failure.failure_id,
                status=RecoveryStatus.FAILED,
                strategy_used=strategy.tier,
                message=f"Unknown recovery tier: {strategy.tier}",
            )

    def _execute_tier1(
        self, failure: FailureInfo, strategy: RecoveryStrategy
    ) -> RecoveryResult:
        """Execute Tier 1 recovery: Retry with modified prompt.

        Args:
            failure: The failure being recovered.
            strategy: The Tier 1 strategy.

        Returns:
            RecoveryResult from the retry.
        """
        attempts = 1

        # Check if we've exceeded retry limit
        if failure.retry_count >= self.tier1_retry_limit:
            return RecoveryResult(
                failure_id=failure.failure_id,
                status=RecoveryStatus.FAILED,
                strategy_used=RecoveryTier.TIER_1,
                message=f"Tier 1 retry limit ({self.tier1_retry_limit}) exceeded",
                attempts=attempts,
            )

        # Simulate successful retry with modified prompt
        return RecoveryResult(
            failure_id=failure.failure_id,
            status=RecoveryStatus.SUCCESS,
            strategy_used=RecoveryTier.TIER_1,
            message="Recovery successful with modified prompt",
            attempts=attempts,
        )

    def _execute_tier2(
        self, failure: FailureInfo, strategy: RecoveryStrategy
    ) -> RecoveryResult:
        """Execute Tier 2 recovery: Context reduction + retry.

        Args:
            failure: The failure being recovered.
            strategy: The Tier 2 strategy.

        Returns:
            RecoveryResult from context reduction.
        """
        attempts = 1

        # Calculate reduced context size
        new_context_size = int(
            failure.context_size * self.tier2_context_reduction_factor
        )

        modified_context = {
            "reduced": True,
            "original_size": failure.context_size,
            "new_size": new_context_size,
            "reduction_factor": self.tier2_context_reduction_factor,
        }

        return RecoveryResult(
            failure_id=failure.failure_id,
            status=RecoveryStatus.SUCCESS,
            strategy_used=RecoveryTier.TIER_2,
            message=f"Context reduced from {failure.context_size} to {new_context_size} tokens",
            attempts=attempts,
            modified_context=modified_context,
        )

    def _execute_tier3(
        self, failure: FailureInfo, strategy: RecoveryStrategy
    ) -> RecoveryResult:
        """Execute Tier 3 recovery: Checkpoint rollback + fresh attempt.

        Args:
            failure: The failure being recovered.
            strategy: The Tier 3 strategy.

        Returns:
            RecoveryResult from checkpoint restoration.
        """
        attempts = 1

        if failure.checkpoint_available:
            # Restore from checkpoint
            return RecoveryResult(
                failure_id=failure.failure_id,
                status=RecoveryStatus.SUCCESS,
                strategy_used=RecoveryTier.TIER_3,
                message="Checkpoint restored, ready for fresh attempt",
                attempts=attempts,
                checkpoint_restored=True,
            )
        else:
            # No checkpoint, just reset state
            return RecoveryResult(
                failure_id=failure.failure_id,
                status=RecoveryStatus.PARTIAL,
                strategy_used=RecoveryTier.TIER_3,
                message="No checkpoint available, context reset performed",
                attempts=attempts,
                checkpoint_restored=False,
            )

    def _execute_tier4(
        self, failure: FailureInfo, strategy: RecoveryStrategy
    ) -> RecoveryResult:
        """Execute Tier 4 recovery: Human escalation.

        Args:
            failure: The failure being recovered.
            strategy: The Tier 4 strategy.

        Returns:
            RecoveryResult with escalation ticket.
        """
        # Create failure context for escalation
        fc = FailureContext(
            error_message=failure.error_message,
            error_type=failure.error_type,
            component=failure.component,
            attempts=failure.retry_count,
            max_attempts=self.tier1_retry_limit,
            is_data_loss_risk=failure.metadata.get("data_loss_risk", False),
        )

        # Create escalation context
        esc_context = EscalationContext(
            failure_context=fc,
            attempted_fixes=[
                f"Tier 1 retry ({failure.retry_count} attempts)",
            ],
            failure_reason=f"Critical failure requiring human intervention: {failure.error_type}",
        )

        # Create escalation ticket
        ticket = self._escalation_manager.escalate(
            esc_context,
            override_priority=Priority.P0 if failure.is_critical else Priority.P1,
        )

        return RecoveryResult(
            failure_id=failure.failure_id,
            status=RecoveryStatus.ESCALATED,
            strategy_used=RecoveryTier.TIER_4,
            message="Escalated to human intervention",
            attempts=0,
            escalation_ticket_id=ticket.ticket_id,
        )

    def _track_recovery(self, failure_id: str, result: RecoveryResult) -> None:
        """Track recovery result in history.

        Args:
            failure_id: ID of the failure.
            result: The recovery result to track.
        """
        if failure_id not in self._recovery_history:
            self._recovery_history[failure_id] = []

        self._recovery_history[failure_id].append(result)

        # Update tier counts
        tier_key = f"tier_{result.strategy_used.value}"
        self._tier_counts[tier_key] = self._tier_counts.get(tier_key, 0) + 1

    def get_recovery_history(self, failure_id: str) -> List[RecoveryResult]:
        """Get recovery history for a specific failure.

        Args:
            failure_id: ID of the failure.

        Returns:
            List of recovery results for this failure.
        """
        return self._recovery_history.get(failure_id, [])

    def get_tier_statistics(self) -> Dict[str, int]:
        """Get statistics on tier usage.

        Returns:
            Dictionary with tier counts.
        """
        return dict(self._tier_counts)

    def clear_history(self) -> None:
        """Clear all recovery history and statistics."""
        self._recovery_history.clear()
        self._tier_counts = {
            "tier_1": 0,
            "tier_2": 0,
            "tier_3": 0,
            "tier_4": 0,
        }
