"""RecoveryManager for handling goal execution failures with retry logic.

This module provides:
- RecoveryLevel enum for retry/escalation decisions
- RetryStrategy enum for defining retry approaches
- ErrorCategory enum for classifying errors
- RecoveryManager class with exponential backoff retry logic
- Integration with CheckpointSystem for escalation
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Awaitable, Optional

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal


class RecoveryLevel(Enum):
    """Level of recovery action to take after failure."""

    RETRY_SAME = "retry_same"
    ESCALATE = "escalate"


class RetryStrategy(Enum):
    """Strategy for retry attempts.
    
    Defines the available strategies for handling failed goal executions:
    - SAME: Retry the exact same approach with no modifications
    - ALTERNATIVE: Try a different approach (extension point for future work)
    - CLARIFY: Request clarification from human via checkpoint
    - ESCALATE: Escalate to human for manual intervention
    """

    SAME = "same"
    ALTERNATIVE = "alternative"
    CLARIFY = "clarify"
    ESCALATE = "escalate"


class ErrorCategory(Enum):
    """Classification of errors for recovery routing.
    
    Categorizes errors to determine appropriate recovery strategy:
    - TRANSIENT: Temporary failures (network, timeout, rate limit) -> Level 1 retry
    - SYSTEMATIC: Approach failures (wrong method) -> Falls through to Level 4
    - FATAL: Unrecoverable failures (auth, security) -> Immediate Level 4 escalation
    """

    TRANSIENT = "transient"
    SYSTEMATIC = "systematic"
    FATAL = "fatal"


# Constants for retry logic
MAX_RETRIES = 3
BACKOFF_SECONDS = 5


@dataclass
class RecoveryResult:
    """Result from a recovery attempt."""

    success: bool
    action_result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    escalated: bool = False


class RecoveryManager:
    """Manager for handling goal execution with retry and escalation logic.

    Provides exponential backoff retry (5s, 10s, 20s) with escalation
    to human-in-the-loop checkpoints after MAX_RETRIES failures.

    Usage:
        recovery = RecoveryManager(checkpoint_system)

        async def execute_goal():
            # goal execution logic
            return result

        result = await recovery.execute_with_recovery(goal, execute_goal)
    """

    def __init__(self, checkpoint_system: "CheckpointSystem") -> None:
        """Initialize RecoveryManager.

        Args:
            checkpoint_system: CheckpointSystem for creating escalation checkpoints.
        """
        self.checkpoint_system = checkpoint_system

    async def execute_with_recovery(
        self,
        goal: "DailyGoal",
        action: Callable[[], Awaitable[Any]],
    ) -> RecoveryResult:
        """Execute an action with retry logic and escalation.

        Retries the action up to MAX_RETRIES times with exponential backoff:
        - First retry: 5 seconds
        - Second retry: 10 seconds
        - Third retry: 20 seconds

        Increments goal.error_count on each failure.
        Returns immediately on success.

        Args:
            goal: The DailyGoal being executed (error_count is incremented on failure).
            action: Async callable that performs the goal execution.

        Returns:
            RecoveryResult with success status, result/error, and retry count.
        """
        last_error: Optional[str] = None
        backoff = BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES):
            try:
                result = await action()
                # Success - return immediately
                return RecoveryResult(
                    success=True,
                    action_result=result,
                    retry_count=attempt,
                    escalated=False,
                )
            except Exception as e:
                # Failure - increment error count and prepare for retry
                goal.error_count += 1
                last_error = str(e)

                # If not last attempt, wait with exponential backoff
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff *= 2  # Exponential backoff: 5s, 10s, 20s

        # All retries exhausted - escalate to human
        escalate_result = await self._escalate_to_human(goal, last_error)
        return RecoveryResult(
            success=False,
            error=last_error,
            retry_count=MAX_RETRIES,
            escalated=True,
        )

    async def _escalate_to_human(
        self,
        goal: "DailyGoal",
        failure_reason: str,
    ) -> None:
        """Escalate a goal to human-in-the-loop with HICCUP checkpoint.

        Sets goal.is_hiccup = True and creates a checkpoint with context
        including retry count, goal content, and error details.

        Args:
            goal: The DailyGoal that failed after retries.
            failure_reason: The error message from the last attempt.
        """
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointTrigger,
        )
        from datetime import datetime
        import uuid

        # Mark goal as hiccup
        goal.is_hiccup = True

        # Build context with retry info
        context = (
            f"Goal failed after {MAX_RETRIES} retry attempts.\n\n"
            f"Goal: {goal.description}\n"
            f"Error: {failure_reason}\n"
            f"Total errors: {goal.error_count}"
        )

        # Create HICCUP checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=f"hiccup-{uuid.uuid4().hex[:8]}",
            trigger=CheckpointTrigger.HICCUP,
            context=context,
            options=[
                CheckpointOption(
                    label="Skip this goal",
                    action="skip",
                    description="Mark goal as skipped and continue",
                ),
                CheckpointOption(
                    label="Retry with modifications",
                    action="retry",
                    description="Provide additional context and retry",
                ),
                CheckpointOption(
                    label="Handle manually",
                    action="manual",
                    description="I'll handle this myself",
                ),
            ],
            created_at=datetime.now(),
        )

        # Store checkpoint for human review
        await self.checkpoint_system.create_checkpoint(checkpoint)