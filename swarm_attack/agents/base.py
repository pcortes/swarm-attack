"""
Base class for Feature Swarm agents.

This module provides the foundation for all agents in the system:
- BaseAgent abstract class with common functionality
- AgentResult dataclass for standardized return values
- Skill loading from .claude/skills/<name>/SKILL.md
- Checkpoint support for progress tracking
- Retry decorator for transient failures
"""

from __future__ import annotations

import functools
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar

from swarm_attack.llm_clients import (
    ClaudeCliRunner,
    ClaudeInvocationError,
    ClaudeTimeoutError,
)
from swarm_attack.models import CheckpointData
from swarm_attack.utils.fs import FileSystemError, file_exists, read_file

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


@dataclass
class AgentResult:
    """
    Result from an agent execution.

    Provides a standardized return type for all agents with success/failure
    indication, output data, error messages, and cost tracking.
    """

    success: bool
    output: Any = None
    errors: list[str] = field(default_factory=list)
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "errors": self.errors,
            "cost_usd": self.cost_usd,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        """Create from dictionary."""
        return cls(
            success=data.get("success", False),
            output=data.get("output"),
            errors=data.get("errors", []),
            cost_usd=data.get("cost_usd", 0.0),
        )

    @classmethod
    def success_result(cls, output: Any = None, cost_usd: float = 0.0) -> AgentResult:
        """Create a successful result."""
        return cls(success=True, output=output, cost_usd=cost_usd)

    @classmethod
    def failure_result(cls, error: str, cost_usd: float = 0.0) -> AgentResult:
        """Create a failed result with a single error."""
        return cls(success=False, errors=[error], cost_usd=cost_usd)


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class SkillNotFoundError(AgentError):
    """Raised when a skill definition cannot be found."""

    pass


# Type variable for retry decorator
F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (ClaudeInvocationError, ClaudeTimeoutError),
) -> Callable[[F], F]:
    """
    Decorator for retrying agent operations on transient failures.

    Args:
        max_attempts: Maximum number of attempts (including first try).
        delay_seconds: Initial delay between retries.
        backoff_multiplier: Multiplier for delay on each retry.
        exceptions: Tuple of exception types to retry on.

    Returns:
        Decorated function that retries on specified exceptions.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            delay = delay_seconds

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                        delay *= backoff_multiplier

            # Exhausted all retries
            raise last_exception  # type: ignore

        return wrapper  # type: ignore

    return decorator


class BaseAgent(ABC):
    """
    Abstract base class for all Feature Swarm agents.

    Provides common functionality:
    - Configuration and logger access
    - LLM client for Claude invocations
    - Skill prompt loading from .claude/skills/
    - Checkpoint creation for progress tracking
    - Standard run() method interface

    Subclasses must implement the run() method to define agent behavior.
    """

    # Agent name used in logs and checkpoints (override in subclasses)
    name: str = "base_agent"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the agent.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            llm_runner: Optional Claude CLI runner (created if not provided).
            state_store: Optional state store for persistence.
        """
        self.config = config
        self._logger = logger
        self._llm = llm_runner
        self._state_store = state_store
        self._checkpoints: list[CheckpointData] = []
        self._total_cost: float = 0.0

    @property
    def logger(self) -> Optional[SwarmLogger]:
        """Get the logger."""
        return self._logger

    @property
    def llm(self) -> ClaudeCliRunner:
        """Get the LLM runner (lazy initialization)."""
        if self._llm is None:
            self._llm = ClaudeCliRunner(config=self.config, logger=self._logger)
        return self._llm

    @property
    def state_store(self) -> Optional[StateStore]:
        """Get the state store."""
        return self._state_store

    def _log(
        self, event_type: str, data: Optional[dict] = None, level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self._logger:
            log_data = {"agent": self.name}
            if data:
                log_data.update(data)
            self._logger.log(event_type, log_data, level=level)

    def load_skill(self, skill_name: str) -> str:
        """
        Load a skill prompt from .claude/skills/<name>/SKILL.md.

        Args:
            skill_name: Name of the skill (directory name).

        Returns:
            Content of the SKILL.md file.

        Raises:
            SkillNotFoundError: If the skill file doesn't exist.
        """
        skill_path = (
            Path(self.config.repo_root) / ".claude" / "skills" / skill_name / "SKILL.md"
        )

        if not file_exists(skill_path):
            raise SkillNotFoundError(f"Skill not found: {skill_name} at {skill_path}")

        try:
            content = read_file(skill_path)
            self._log("skill_loaded", {"skill": skill_name})
            return content
        except FileSystemError as e:
            raise SkillNotFoundError(f"Failed to load skill {skill_name}: {e}")

    def checkpoint(
        self,
        status: str,
        commit: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> CheckpointData:
        """
        Create a checkpoint to record progress.

        Checkpoints allow tracking agent progress and enable resumption
        from failure points.

        Args:
            status: Status description (e.g., "complete", "in_progress").
            commit: Optional git commit hash if applicable.
            cost_usd: Cost incurred up to this checkpoint.

        Returns:
            The created CheckpointData.
        """
        checkpoint = CheckpointData(
            agent=self.name,
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            commit=commit,
            cost_usd=cost_usd,
        )

        self._checkpoints.append(checkpoint)
        self._total_cost += cost_usd

        self._log(
            "checkpoint",
            {
                "status": status,
                "commit": commit,
                "cost_usd": cost_usd,
                "total_cost": self._total_cost,
            },
        )

        return checkpoint

    def get_checkpoints(self) -> list[CheckpointData]:
        """Get all checkpoints created during this run."""
        return self._checkpoints.copy()

    def get_total_cost(self) -> float:
        """Get total cost accumulated during this run."""
        return self._total_cost

    def reset(self) -> None:
        """Reset agent state for a fresh run."""
        self._checkpoints = []
        self._total_cost = 0.0

    @abstractmethod
    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute the agent's main task.

        Subclasses must implement this method to define the agent's behavior.

        Args:
            context: Dictionary containing context for the agent.
                     Contents vary by agent type.

        Returns:
            AgentResult with success/failure status and output data.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
