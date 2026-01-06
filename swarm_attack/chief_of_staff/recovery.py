"""RecoveryManager for handling goal execution failures with retry logic.

This module provides:
- RecoveryLevel enum for retry/escalation decisions
- RetryStrategy enum for defining retry approaches
- ErrorCategory enum for classifying errors
- RecoveryManager class with exponential backoff retry logic
- classify_error() function for mapping exceptions to error categories
- Integration with CheckpointSystem for escalation
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Awaitable, Optional

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal
    from swarm_attack.chief_of_staff.episodes import EpisodeStore

logger = logging.getLogger(__name__)


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
DEFAULT_BACKOFF_BASE_SECONDS = 5
DEFAULT_BACKOFF_MULTIPLIER = 2

# BUG-5: Backward compatibility alias
BACKOFF_SECONDS = DEFAULT_BACKOFF_BASE_SECONDS


# Error classification mappings using LLMErrorType from errors.py
# Import at module level for classify_error function
from swarm_attack.errors import LLMErrorType

# Transient errors: temporary failures that are worth retrying
TRANSIENT_ERRORS = {
    LLMErrorType.RATE_LIMIT,
    LLMErrorType.RATE_LIMIT_TIMED,
    LLMErrorType.SERVER_OVERLOADED,
    LLMErrorType.SERVER_ERROR,
    LLMErrorType.TIMEOUT,
}

# Systematic errors: approach failures that fall through to escalation
SYSTEMATIC_ERRORS = {
    LLMErrorType.CLI_CRASH,
    LLMErrorType.JSON_PARSE_ERROR,
}

# Fatal errors: unrecoverable failures requiring immediate escalation
FATAL_ERRORS = {
    LLMErrorType.AUTH_REQUIRED,
    LLMErrorType.AUTH_EXPIRED,
    LLMErrorType.CLI_NOT_FOUND,
}


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an error to determine recovery strategy.
    
    Maps exceptions to ErrorCategory based on their error_type attribute
    (for LLMError instances) or defaults to FATAL for unknown/generic exceptions.
    
    Args:
        error: The exception to classify.
        
    Returns:
        ErrorCategory indicating the type of failure:
        - TRANSIENT: For rate limits, timeouts, server errors (Level 1 retry)
        - SYSTEMATIC: For CLI crashes, JSON parse errors (falls through to Level 4)
        - FATAL: For auth errors, CLI not found, or unknown errors (immediate Level 4)
    
    Examples:
        >>> from swarm_attack.errors import LLMError, LLMErrorType
        >>> error = LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
        >>> classify_error(error)
        <ErrorCategory.TRANSIENT: 'transient'>
        
        >>> classify_error(ValueError("unknown"))
        <ErrorCategory.FATAL: 'fatal'>
    """
    # Check if the exception has an error_type attribute (LLMError instances)
    error_type = getattr(error, "error_type", None)
    
    # If no error_type attribute or it's None, default to FATAL (fail-safe)
    if error_type is None:
        return ErrorCategory.FATAL
    
    # Classify based on error type mappings
    if error_type in TRANSIENT_ERRORS:
        return ErrorCategory.TRANSIENT
    
    if error_type in SYSTEMATIC_ERRORS:
        return ErrorCategory.SYSTEMATIC
    
    if error_type in FATAL_ERRORS:
        return ErrorCategory.FATAL
    
    # Unknown error types default to FATAL (fail-safe behavior)
    return ErrorCategory.FATAL


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

    Implements a 4-level hierarchical recovery system:
    - Level 1 (SAME): Transient errors retry up to 3 times with exponential backoff
    - Level 2 (ALTERNATIVE): Systematic errors log fallthrough and proceed to Level 4
    - Level 3 (CLARIFY): Not auto-triggered - extension point for human-triggered retries
    - Level 4 (ESCALATE): Fatal errors + fallthrough create HICCUP checkpoint

    Usage:
        recovery = RecoveryManager(checkpoint_system)

        async def execute_goal():
            # goal execution logic
            return GoalExecutionResult(...)

        result = await recovery.execute_with_recovery(goal, execute_goal)
    """

    def __init__(
        self,
        checkpoint_system: "CheckpointSystem",
        backoff_base_seconds: int = DEFAULT_BACKOFF_BASE_SECONDS,
        backoff_multiplier: int = DEFAULT_BACKOFF_MULTIPLIER,
        level2_analyzer: Optional[Any] = None,
    ) -> None:
        """Initialize RecoveryManager.

        Args:
            checkpoint_system: CheckpointSystem for creating escalation checkpoints.
            backoff_base_seconds: Base delay for exponential backoff (default: 5).
            backoff_multiplier: Multiplier for exponential backoff (default: 2).
            level2_analyzer: Optional Level2Analyzer for intelligent recovery (extension point).
        """
        self.checkpoint_system = checkpoint_system
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_multiplier = backoff_multiplier
        self.level2_analyzer = level2_analyzer

    def _log_level2_fallthrough(
        self,
        goal_id: str,
        error_type: LLMErrorType,
        error_message: str,
    ) -> None:
        """Log explicit message when Level 2 ALTERNATIVE falls through to ESCALATE.
        
        This creates an audit trail and makes the extension point visible for
        future implementation of alternative recovery strategies.
        
        Args:
            goal_id: The ID of the goal that encountered the error.
            error_type: The LLMErrorType of the systematic error.
            error_message: The error message from the exception.
        """
        timestamp = datetime.now().isoformat()
        logger.warning(
            f"[{timestamp}] Level 2 ALTERNATIVE not implemented, falling through to ESCALATE | "
            f"goal_id={goal_id} | error_type={error_type.name} | error={error_message}"
        )

    async def execute_with_recovery(
        self,
        goal: "DailyGoal",
        execute_fn: Callable[[], Awaitable[Any]],
        episode_store: Optional["EpisodeStore"] = None,
    ) -> "GoalExecutionResult":
        """Execute goal with hierarchical recovery.

        Routes errors through the 4-level recovery hierarchy:
        - Level 1 (SAME): Transient errors retry up to 3 times with exponential backoff
        - Level 2 (ALTERNATIVE): Systematic errors log fallthrough and proceed to Level 4
        - Level 3 (CLARIFY): Not auto-triggered - extension point for human-triggered retries
        - Level 4 (ESCALATE): Fatal errors + fallthrough create HICCUP checkpoint

        Args:
            goal: The DailyGoal being executed (error_count is incremented on failure).
            execute_fn: Async callable that performs the goal execution.
            episode_store: Optional EpisodeStore for logging recovery episodes.

        Returns:
            GoalExecutionResult with success status, cost, duration, and error info.
        """
        # Import here to avoid circular imports
        from swarm_attack.chief_of_staff.autopilot_runner import GoalExecutionResult
        from swarm_attack.chief_of_staff.episodes import Episode

        last_error: Optional[str] = None
        last_exception: Optional[Exception] = None
        retry_count = 0
        recovery_level = RetryStrategy.SAME.value
        start_time = datetime.now()

        # Attempt execution with retry logic for transient errors
        backoff = self.backoff_base_seconds
        attempt = 0

        while attempt < MAX_RETRIES:
            try:
                result = await execute_fn()
                
                # Log successful episode if store provided
                if episode_store is not None:
                    duration = int((datetime.now() - start_time).total_seconds())
                    episode = Episode(
                        episode_id=f"ep-{uuid.uuid4().hex[:8]}",
                        timestamp=datetime.now().isoformat(),
                        goal_id=goal.goal_id,
                        success=True,
                        cost_usd=getattr(result, "cost_usd", 0.0),
                        duration_seconds=duration,
                        retry_count=retry_count,
                        recovery_level=RetryStrategy.SAME.value if retry_count > 0 else None,
                    )
                    episode_store.save(episode)

                return result

            except Exception as e:
                attempt += 1
                goal.error_count += 1
                last_error = str(e)
                last_exception = e
                retry_count += 1

                # Classify error to determine recovery level
                category = classify_error(e)

                if category == ErrorCategory.TRANSIENT:
                    # Level 1: SAME - Retry with exponential backoff
                    recovery_level = RetryStrategy.SAME.value
                    
                    if attempt < MAX_RETRIES:
                        logger.info(
                            f"Level 1 (SAME): Transient error, retrying in {backoff}s "
                            f"(attempt {attempt}/{MAX_RETRIES}): {last_error}"
                        )
                        await asyncio.sleep(backoff)
                        backoff *= self.backoff_multiplier
                        continue
                    else:
                        # Exhausted retries, fall through to escalation
                        logger.warning(
                            f"Level 1 exhausted: Transient error persisted after {MAX_RETRIES} "
                            f"retries, escalating to Level 4"
                        )
                        recovery_level = RetryStrategy.ESCALATE.value
                        break

                elif category == ErrorCategory.SYSTEMATIC:
                    # Level 2: ALTERNATIVE - Use analyzer if available, otherwise fall through
                    error_type = getattr(e, "error_type", None)

                    if self.level2_analyzer is not None:
                        # Use Level 2 analyzer for intelligent recovery
                        from swarm_attack.chief_of_staff.level2_recovery import RecoveryActionType

                        try:
                            analysis = await self.level2_analyzer.analyze(
                                goal=goal,
                                error=e,
                            )

                            if analysis.action_type == RecoveryActionType.ALTERNATIVE:
                                # Retry with the hint from analysis
                                recovery_level = RetryStrategy.ALTERNATIVE.value
                                # Store hint on goal for retry context
                                goal.recovery_hint = analysis.hint
                                logger.info(
                                    f"Level 2 (ALTERNATIVE): Retrying with hint: {analysis.hint}"
                                )
                                # Continue to retry loop for next attempt
                                continue
                            elif analysis.action_type == RecoveryActionType.DIAGNOSTICS:
                                # Run diagnostics before escalating
                                recovery_level = RetryStrategy.ESCALATE.value
                                logger.info(
                                    f"Level 2 (DIAGNOSTICS): Running diagnostics before escalation"
                                )
                                break
                            elif analysis.action_type == RecoveryActionType.UNBLOCK:
                                # Suggest unblocking steps
                                recovery_level = RetryStrategy.ESCALATE.value
                                logger.info(
                                    f"Level 2 (UNBLOCK): Suggesting unblock steps"
                                )
                                break
                            else:
                                # Escalate as fallback
                                recovery_level = RetryStrategy.ESCALATE.value
                                break
                        except Exception as analyzer_error:
                            logger.warning(
                                f"Level 2 analyzer failed: {analyzer_error}, falling through to Level 4"
                            )
                            recovery_level = RetryStrategy.ESCALATE.value
                            break
                    else:
                        # No analyzer available - log fallthrough
                        self._log_level2_fallthrough(
                            goal_id=goal.goal_id,
                            error_type=error_type,
                            error_message=last_error,
                        )
                        recovery_level = RetryStrategy.ESCALATE.value
                        break

                elif category == ErrorCategory.FATAL:
                    # Level 4: ESCALATE - Immediate escalation
                    logger.error(
                        f"Level 4 (ESCALATE): Fatal error detected, "
                        f"escalating immediately: {last_error}"
                    )
                    recovery_level = RetryStrategy.ESCALATE.value
                    break

        # All attempts exhausted or escalation triggered
        # Level 4: Create HICCUP checkpoint
        await self._escalate_to_human(goal, last_error or "Unknown error")

        # Log failed episode if store provided
        duration = int((datetime.now() - start_time).total_seconds())
        if episode_store is not None:
            episode = Episode(
                episode_id=f"ep-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now().isoformat(),
                goal_id=goal.goal_id,
                success=False,
                cost_usd=0.0,
                duration_seconds=duration,
                retry_count=retry_count,
                recovery_level=recovery_level,
                error=last_error,
            )
            episode_store.save(episode)

        return GoalExecutionResult(
            success=False,
            cost_usd=0.0,
            duration_seconds=duration,
            error=last_error,
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

        # Mark goal as hiccup
        goal.is_hiccup = True

        # Build context with retry info
        context = (
            f"Goal failed after recovery attempts.\n\n"
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
                    description="Mark goal as skipped and continue",
                ),
                CheckpointOption(
                    label="Retry with modifications",
                    description="Provide additional context and retry",
                ),
                CheckpointOption(
                    label="Handle manually",
                    description="I'll handle this myself",
                ),
            ],
            recommendation="Review the error and decide how to proceed.",
            created_at=datetime.now().isoformat(),
            goal_id=goal.goal_id,
        )

        # Store checkpoint for human review
        await self.checkpoint_system.store.save(checkpoint)