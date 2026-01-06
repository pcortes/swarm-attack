"""DebateRetryHandler for adding retry logic to debate agent calls.

This module provides retry functionality for debate loops (spec debate, bug debate)
to handle transient errors like rate limits and timeouts, while failing fast on
fatal errors like authentication failures.

Uses the error classification from chief_of_staff.recovery module.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Protocol

from swarm_attack.errors import LLMError, LLMErrorType
from swarm_attack.chief_of_staff.recovery import (
    ErrorCategory,
    classify_error,
    TRANSIENT_ERRORS,
    FATAL_ERRORS,
)

if TYPE_CHECKING:
    from swarm_attack.agents.base import BaseAgent
    from swarm_attack.config.main import DebateRetryConfig


logger = logging.getLogger(__name__)


# Default retry configuration - these are the NEW defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 30.0  # Was 5.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_MAX_BACKOFF_SECONDS = 300.0  # Was 60.0


@dataclass
class RetryResult:
    """Result from a retry-wrapped agent call."""

    success: bool
    output: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    errors: Optional[list[str]] = None
    retry_count: int = 0


class AgentProtocol(Protocol):
    """Protocol for agents that can be retried."""

    def run(self, context: dict) -> Any:
        """Run the agent with the given context."""
        ...

    def reset(self) -> None:
        """Reset the agent state."""
        ...


class DebateRetryHandler:
    """Handler for retrying debate agent calls with exponential backoff.

    Provides retry logic for transient errors (rate limits, timeouts, server errors)
    while failing fast on fatal errors (authentication).

    Usage:
        handler = DebateRetryHandler(max_retries=3)
        result = handler.run_with_retry(critic_agent, {"feature_id": "test"})

        if not result.success:
            # Handle failure - check result.errors for details
            pass
    """

    def __init__(
        self,
        config: Optional["DebateRetryConfig"] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        max_backoff_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS,
    ) -> None:
        """Initialize the retry handler.

        Args:
            config: Optional DebateRetryConfig object. If provided, overrides positional args.
            max_retries: Maximum number of retry attempts for transient errors.
            backoff_base_seconds: Initial backoff delay in seconds.
            backoff_multiplier: Multiplier for exponential backoff.
            max_backoff_seconds: Maximum backoff delay (cap).
        """
        if config is not None:
            # Config takes precedence over positional args
            self.max_retries = config.max_retries
            self.backoff_base_seconds = config.backoff_base_seconds
            self.backoff_multiplier = config.backoff_multiplier
            self.max_backoff_seconds = config.max_backoff_seconds
        else:
            # Use positional args (backward compatible)
            self.max_retries = max_retries
            self.backoff_base_seconds = backoff_base_seconds
            self.backoff_multiplier = backoff_multiplier
            self.max_backoff_seconds = max_backoff_seconds

    def _classify_error(self, error: Exception) -> ErrorCategory:
        """Classify an error to determine retry strategy.

        Uses the classify_error function from recovery module.

        Args:
            error: The exception to classify.

        Returns:
            ErrorCategory indicating the type of failure.
        """
        return classify_error(error)

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff delay for a given attempt number.

        Args:
            attempt: The retry attempt number (0-indexed).

        Returns:
            Backoff delay in seconds, capped at max_backoff_seconds.
        """
        delay = self.backoff_base_seconds * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_backoff_seconds)

    def run_with_retry(
        self,
        agent: AgentProtocol,
        context: dict,
    ) -> RetryResult:
        """Run an agent with retry logic for transient errors.

        Args:
            agent: The agent to run (must have run() and reset() methods).
            context: The context dict to pass to agent.run().

        Returns:
            RetryResult with success status, output, and error details.
        """
        attempt = 0
        last_error: Optional[Exception] = None
        total_cost = 0.0

        while attempt <= self.max_retries:
            try:
                # Reset agent state before each attempt
                agent.reset()

                # Run the agent
                result = agent.run(context)
                total_cost += getattr(result, 'cost_usd', 0.0)

                # Check if agent returned a failure result (not an exception)
                if hasattr(result, 'success') and not result.success:
                    # Agent-level failure (e.g., "spec too vague") - don't retry
                    logger.debug(
                        "Agent returned failure result (not retryable): %s",
                        getattr(result, 'errors', []),
                    )
                    return RetryResult(
                        success=False,
                        output=getattr(result, 'output', {}),
                        cost_usd=total_cost,
                        errors=getattr(result, 'errors', None),
                        retry_count=attempt,
                    )

                # Success!
                return RetryResult(
                    success=True,
                    output=getattr(result, 'output', {}),
                    cost_usd=total_cost,
                    errors=None,
                    retry_count=attempt,
                )

            except Exception as e:
                last_error = e
                error_category = self._classify_error(e)

                # Fatal errors: fail immediately, no retry
                if error_category == ErrorCategory.FATAL:
                    logger.error(
                        "Fatal error during debate (no retry): %s - %s",
                        type(e).__name__,
                        str(e),
                    )
                    return RetryResult(
                        success=False,
                        output={},
                        cost_usd=total_cost,
                        errors=[str(e)],
                        retry_count=attempt,
                    )

                # Transient errors: retry with backoff
                if error_category == ErrorCategory.TRANSIENT:
                    if attempt < self.max_retries:
                        backoff = self._calculate_backoff(attempt)
                        logger.warning(
                            "Transient error during debate (attempt %d/%d), "
                            "retrying in %.1fs: %s - %s",
                            attempt + 1,
                            self.max_retries + 1,
                            backoff,
                            type(e).__name__,
                            str(e),
                        )
                        time.sleep(backoff)
                        attempt += 1
                        continue
                    else:
                        logger.error(
                            "Transient error persisted after %d retries: %s - %s",
                            self.max_retries,
                            type(e).__name__,
                            str(e),
                        )

                # Systematic or exhausted retries - fail
                logger.error(
                    "Error during debate (category=%s): %s - %s",
                    error_category.value,
                    type(e).__name__,
                    str(e),
                )
                return RetryResult(
                    success=False,
                    output={},
                    cost_usd=total_cost,
                    errors=[str(e)],
                    retry_count=attempt,
                )

        # Should not reach here, but handle gracefully
        return RetryResult(
            success=False,
            output={},
            cost_usd=total_cost,
            errors=[str(last_error)] if last_error else ["Unknown error"],
            retry_count=attempt,
        )
