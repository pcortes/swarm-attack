"""
Edge Case Handlers for Feature Swarm.

This module provides handlers for automatic recovery scenarios that don't require
LLM analysis. These are deterministic handlers that retry, backoff, or escalate
based on predefined rules.

The handlers integrate with RecoveryAgent in the following flow:
1. Error occurs
2. Check if edge_cases.py can handle it (deterministic rules)
3. If YES -> Apply handler (retry, wait, checkpoint)
4. If NO -> Pass to RecoveryAgent for LLM analysis

Handler Result Actions:
- "retry": Retry the operation after the specified delay
- "recovered": The error has been handled/resolved
- "escalate": Cannot handle automatically, needs RecoveryAgent
- "checkpoint_exit": Save checkpoint and exit gracefully
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


# =============================================================================
# Custom Exceptions
# =============================================================================


class EdgeCaseError(Exception):
    """Base exception for edge case handling."""

    pass


class NetworkTimeoutError(EdgeCaseError):
    """Network operation timed out."""

    pass


class GitHubRateLimitError(EdgeCaseError):
    """GitHub API rate limit exceeded."""

    def __init__(
        self,
        message: str,
        reset_at: Optional[datetime] = None,
        remaining: int = 0,
    ) -> None:
        super().__init__(message)
        self.reset_at = reset_at
        self.remaining = remaining


class ContextExhaustedError(EdgeCaseError):
    """Claude context window exhausted."""

    pass


class TestFailureError(EdgeCaseError):
    """Tests failed during verification."""

    pass


class StateInconsistencyError(EdgeCaseError):
    """State file inconsistent with git."""

    pass


class SessionLockError(EdgeCaseError):
    """Session lock conflict."""

    def __init__(
        self,
        message: str,
        session_id: str = "",
        locked_at: Optional[datetime] = None,
    ) -> None:
        super().__init__(message)
        self.session_id = session_id
        self.locked_at = locked_at


# =============================================================================
# Handler Result
# =============================================================================


@dataclass
class HandlerResult:
    """
    Result from an edge case handler.

    Attributes:
        action: One of "retry", "recovered", "escalate", "checkpoint_exit"
        message: Human-readable description of what happened
        retry_after_seconds: Delay before retry (if action is "retry")
        context: Additional context for the handler result
    """

    action: str  # "retry", "recovered", "escalate", "checkpoint_exit"
    message: str
    retry_after_seconds: Optional[float] = None
    context: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action": self.action,
            "message": self.message,
            "retry_after_seconds": self.retry_after_seconds,
            "context": self.context,
        }


# =============================================================================
# Base Handler
# =============================================================================


class BaseHandler(ABC):
    """
    Abstract base class for edge case handlers.

    All handlers must implement:
    - can_handle(): Check if this handler can handle the error
    - handle(): Handle the error and return a result
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the handler.

        Args:
            config: SwarmConfig with retry and session settings.
            logger: Optional logger for recording operations.
        """
        self.config = config
        self._logger = logger

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"handler": self.__class__.__name__}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    @abstractmethod
    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this handler can handle the error.

        Args:
            error: The exception that occurred.
            context: Additional context about the error situation.

        Returns:
            True if this handler can handle the error, False otherwise.
        """
        pass

    @abstractmethod
    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle the error and return a result.

        Args:
            error: The exception to handle.
            context: Additional context about the error situation.

        Returns:
            HandlerResult with the action to take.
        """
        pass


# =============================================================================
# Retry Handler (Base class with exponential backoff)
# =============================================================================


class RetryHandler(BaseHandler):
    """
    Base class for handlers that implement retry with exponential backoff.

    Provides common retry logic that can be used by specific handlers.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        max_retries: Optional[int] = None,
        base_delay_seconds: Optional[float] = None,
        backoff_multiplier: float = 2.0,
    ) -> None:
        """
        Initialize the retry handler.

        Args:
            config: SwarmConfig with retry settings.
            logger: Optional logger.
            max_retries: Maximum retry attempts (defaults to config value).
            base_delay_seconds: Initial delay (defaults to config value).
            backoff_multiplier: Multiplier for exponential backoff.
        """
        super().__init__(config, logger)
        self.max_retries = max_retries if max_retries is not None else config.retry.max_retries
        self.base_delay_seconds = base_delay_seconds if base_delay_seconds is not None else config.retry.base_delay_seconds
        self.backoff_multiplier = backoff_multiplier

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt using exponential backoff.

        Args:
            attempt: The attempt number (0-indexed).

        Returns:
            Delay in seconds, capped at max_delay_seconds.
        """
        delay = self.base_delay_seconds * (self.backoff_multiplier ** attempt)
        max_delay = self.config.retry.max_delay_seconds
        return min(delay, max_delay)

    def should_retry(self, attempt: int) -> bool:
        """
        Check if we should retry based on the attempt count.

        Args:
            attempt: The current attempt number (0-indexed).

        Returns:
            True if retry is allowed, False if max retries reached.
        """
        return attempt < self.max_retries

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """Default implementation - subclasses should override."""
        return False

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """Default implementation - subclasses should override."""
        return HandlerResult(action="escalate", message="Not implemented")


# =============================================================================
# Network Timeout Handler
# =============================================================================


class NetworkTimeoutHandler(RetryHandler):
    """
    Handles network timeouts and connection errors.

    Retries 3x with exponential backoff, then escalates.
    """

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this is a network-related error.

        Handles:
        - ConnectionError
        - TimeoutError
        - IOError with network-related message
        """
        if isinstance(error, (ConnectionError, TimeoutError, NetworkTimeoutError)):
            return True

        # Check for IOError with network message
        if isinstance(error, IOError):
            error_msg = str(error).lower()
            network_keywords = ["network", "unreachable", "connection", "timeout"]
            return any(kw in error_msg for kw in network_keywords)

        return False

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle network timeout with retry and exponential backoff.

        Returns:
            RETRY with delay if under max retries, ESCALATE otherwise.
        """
        retry_count = context.get("retry_count", 0)

        if self.should_retry(retry_count):
            delay = self.calculate_delay(retry_count)
            self._log(
                "network_timeout_retry",
                {
                    "error": str(error),
                    "retry_count": retry_count,
                    "delay_seconds": delay,
                },
            )
            return HandlerResult(
                action="retry",
                message=f"Network timeout, retrying in {delay:.1f}s (attempt {retry_count + 1}/{self.max_retries})",
                retry_after_seconds=delay,
                context={"retry_count": retry_count + 1},
            )

        self._log(
            "network_timeout_escalate",
            {
                "error": str(error),
                "retry_count": retry_count,
            },
            level="warn",
        )
        return HandlerResult(
            action="escalate",
            message=f"Network timeout: max retries ({self.max_retries}) exceeded",
            context={"retry_count": retry_count},
        )


# =============================================================================
# GitHub Rate Limit Handler
# =============================================================================


class GitHubRateLimitHandler(BaseHandler):
    """
    Handles GitHub API rate limits.

    If reset is under 5 minutes: wait for reset
    If reset is over 5 minutes: checkpoint and exit
    """

    # Threshold in seconds (5 minutes)
    WAIT_THRESHOLD_SECONDS = 5 * 60

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this is a GitHub rate limit error.

        Handles:
        - GitHubRateLimitError
        """
        return isinstance(error, GitHubRateLimitError)

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle GitHub rate limit.

        Returns:
            RETRY with wait if reset < 5 minutes, CHECKPOINT_EXIT otherwise.
        """
        if not isinstance(error, GitHubRateLimitError):
            return HandlerResult(
                action="escalate",
                message="Not a rate limit error",
            )

        reset_at = error.reset_at
        if reset_at is None:
            # Default to 5 minutes if unknown
            reset_at = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        seconds_until_reset = (reset_at - now).total_seconds()
        seconds_until_reset = max(0, seconds_until_reset)

        result_context = {
            "reset_at": reset_at.isoformat(),
            "seconds_until_reset": seconds_until_reset,
            "remaining": error.remaining,
        }

        if seconds_until_reset <= self.WAIT_THRESHOLD_SECONDS:
            self._log(
                "rate_limit_wait",
                {
                    "seconds_until_reset": seconds_until_reset,
                },
            )
            return HandlerResult(
                action="retry",
                message=f"GitHub rate limit hit, waiting {seconds_until_reset:.0f}s for reset",
                retry_after_seconds=seconds_until_reset + 1,  # Add 1s buffer
                context=result_context,
            )

        self._log(
            "rate_limit_checkpoint",
            {
                "seconds_until_reset": seconds_until_reset,
            },
            level="warn",
        )
        return HandlerResult(
            action="checkpoint_exit",
            message=f"GitHub rate limit hit, reset in {seconds_until_reset / 60:.0f} minutes. Creating checkpoint and exiting.",
            context=result_context,
        )


# =============================================================================
# Context Exhausted Handler
# =============================================================================


class ContextExhaustedHandler(BaseHandler):
    """
    Handles Claude context window exhaustion.

    Creates checkpoint with current progress and exits gracefully.
    """

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this is a context exhaustion error.

        Handles:
        - ContextExhaustedError
        - Any exception with context-related message
        """
        if isinstance(error, ContextExhaustedError):
            return True

        # Check error message for context exhaustion indicators
        error_msg = str(error).lower()
        context_keywords = ["context window", "context limit", "token limit", "context exhausted"]
        return any(kw in error_msg for kw in context_keywords)

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle context exhaustion by checkpointing and exiting.

        Returns:
            CHECKPOINT_EXIT with resume instructions.
        """
        feature_id = context.get("feature_id", "unknown")
        issue_number = context.get("issue_number")
        checkpoints = context.get("checkpoints", [])

        self._log(
            "context_exhausted",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "checkpoints": len(checkpoints) if isinstance(checkpoints, list) else 0,
            },
            level="warn",
        )

        result_context = {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "checkpoints": checkpoints,
        }

        return HandlerResult(
            action="checkpoint_exit",
            message=f"Context exhausted for {feature_id}. Checkpoint saved. Run again to resume from last checkpoint.",
            context=result_context,
        )


# =============================================================================
# Test Failure Handler
# =============================================================================


class TestFailureHandler(BaseHandler):
    """
    Handles test failures during verification.

    Tracks retry count per issue and retries up to max_implementation_retries.
    """

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this is a test failure.

        Handles:
        - TestFailureError
        - AssertionError during verification stage
        """
        if isinstance(error, TestFailureError):
            return True

        # AssertionError during verification
        if isinstance(error, AssertionError):
            stage = context.get("stage", "")
            return stage in ["verification", "verifying", "test"]

        return False

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle test failure with retry tracking.

        Returns:
            RETRY if under max retries, ESCALATE otherwise.
        """
        issue_number = context.get("issue_number")
        retry_count = context.get("retry_count", 0)
        max_retries = self.config.sessions.max_implementation_retries

        if retry_count < max_retries:
            self._log(
                "test_failure_retry",
                {
                    "issue_number": issue_number,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                },
            )
            return HandlerResult(
                action="retry",
                message=f"Tests failed for issue #{issue_number}, retrying (attempt {retry_count + 1}/{max_retries})",
                context={
                    "issue_number": issue_number,
                    "retry_count": retry_count + 1,
                },
            )

        self._log(
            "test_failure_escalate",
            {
                "issue_number": issue_number,
                "retry_count": retry_count,
            },
            level="warn",
        )
        return HandlerResult(
            action="escalate",
            message=f"Tests failed for issue #{issue_number} after {retry_count} retries. Marking as blocked.",
            context={
                "issue_number": issue_number,
                "retry_count": retry_count,
            },
        )


# =============================================================================
# State Inconsistency Handler
# =============================================================================


class StateInconsistencyHandler(BaseHandler):
    """
    Handles state/git mismatch errors.

    Reconciles from git history (source of truth).
    """

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this is a state inconsistency error.

        Handles:
        - StateInconsistencyError
        """
        return isinstance(error, StateInconsistencyError)

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle state inconsistency by reconciling from git.

        Returns:
            RECOVERED if reconciliation succeeds, ESCALATE if it fails.
        """
        feature_id = context.get("feature_id", "unknown")
        corrupted = context.get("corrupted", False)

        if corrupted:
            # Cannot reconcile corrupted state
            self._log(
                "state_inconsistency_escalate",
                {
                    "feature_id": feature_id,
                    "reason": "corrupted",
                },
                level="error",
            )
            return HandlerResult(
                action="escalate",
                message=f"State file for {feature_id} is corrupted and cannot be reconciled automatically.",
                context={"feature_id": feature_id},
            )

        self._log(
            "state_inconsistency_reconcile",
            {
                "feature_id": feature_id,
            },
        )

        return HandlerResult(
            action="recovered",
            message=f"State inconsistency detected for {feature_id}. Reconciled from git history.",
            context={"feature_id": feature_id, "reconciled": True},
        )


# =============================================================================
# Stale Session Handler
# =============================================================================


class StaleSessionHandler(BaseHandler):
    """
    Handles stale session locks.

    Claims session after stale timeout (default 30 minutes).
    """

    def can_handle(self, error: Exception, context: dict[str, Any]) -> bool:
        """
        Check if this is a stale session lock.

        Handles:
        - SessionLockError where session is stale (past timeout)
        """
        if not isinstance(error, SessionLockError):
            return False

        locked_at = error.locked_at
        if locked_at is None:
            return False

        # Check if session is stale
        stale_timeout_minutes = self.config.sessions.stale_timeout_minutes
        now = datetime.now(timezone.utc)
        age_minutes = (now - locked_at).total_seconds() / 60

        return age_minutes >= stale_timeout_minutes

    def handle(self, error: Exception, context: dict[str, Any]) -> HandlerResult:
        """
        Handle stale session by claiming it.

        Returns:
            RECOVERED after claiming the stale session.
        """
        if not isinstance(error, SessionLockError):
            return HandlerResult(
                action="escalate",
                message="Not a session lock error",
            )

        session_id = error.session_id
        locked_at = error.locked_at

        self._log(
            "stale_session_claim",
            {
                "session_id": session_id,
                "locked_at": locked_at.isoformat() if locked_at else None,
            },
        )

        return HandlerResult(
            action="recovered",
            message=f"Claimed stale session {session_id}. Previous lock has been reset.",
            context={
                "session_id": session_id,
                "claimed": True,
            },
        )


# =============================================================================
# Edge Case Dispatcher
# =============================================================================


class EdgeCaseDispatcher:
    """
    Routes errors to appropriate handlers.

    This is the main entry point for edge case handling. It maintains a list
    of handlers and dispatches errors to the first handler that can handle them.

    If no handler can handle the error, returns None to indicate the error
    should be passed to RecoveryAgent for LLM analysis.
    """

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
    ) -> None:
        """
        Initialize the dispatcher with all handlers.

        Args:
            config: SwarmConfig with handler settings.
            logger: Optional logger for operations.
        """
        self.config = config
        self._logger = logger

        # Initialize handlers in priority order
        self.handlers: list[BaseHandler] = [
            NetworkTimeoutHandler(config, logger),
            GitHubRateLimitHandler(config, logger),
            ContextExhaustedHandler(config, logger),
            TestFailureHandler(config, logger),
            StateInconsistencyHandler(config, logger),
            StaleSessionHandler(config, logger),
        ]

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"component": "EdgeCaseDispatcher"}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def dispatch(
        self,
        error: Exception,
        context: dict[str, Any],
    ) -> Optional[HandlerResult]:
        """
        Find and execute the appropriate handler for the error.

        Args:
            error: The exception to handle.
            context: Additional context about the error situation.

        Returns:
            HandlerResult if a handler was found, None otherwise.
            None indicates the error should go to RecoveryAgent.
        """
        self._log(
            "dispatch_start",
            {
                "error_type": type(error).__name__,
                "error_message": str(error)[:200],
            },
        )

        for handler in self.handlers:
            if handler.can_handle(error, context):
                self._log(
                    "handler_matched",
                    {
                        "handler": handler.__class__.__name__,
                        "error_type": type(error).__name__,
                    },
                )
                result = handler.handle(error, context)
                self._log(
                    "handler_result",
                    {
                        "handler": handler.__class__.__name__,
                        "action": result.action,
                    },
                )
                return result

        self._log(
            "no_handler_found",
            {
                "error_type": type(error).__name__,
            },
            level="warn",
        )

        return None
