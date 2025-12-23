"""
Chief of Staff configuration dataclasses.

This module provides configuration for the Chief of Staff autonomous orchestration layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.autopilot_runner import ExecutionStrategy as ES


# Import ExecutionStrategy at runtime to avoid circular imports
def _get_execution_strategy_enum():
    """Get ExecutionStrategy enum lazily to avoid circular imports."""
    from swarm_attack.chief_of_staff.autopilot_runner import ExecutionStrategy
    return ExecutionStrategy


@dataclass
class CheckpointConfig:
    """Checkpoint trigger configuration."""
    budget_usd: float = 10.0
    duration_minutes: int = 120
    error_streak: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointConfig":
        """Create config from dictionary."""
        return cls(
            budget_usd=data.get("budget_usd", 10.0),
            duration_minutes=data.get("duration_minutes", 120),
            error_streak=data.get("error_streak", 3),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "budget_usd": self.budget_usd,
            "duration_minutes": self.duration_minutes,
            "error_streak": self.error_streak,
        }


@dataclass
class PriorityConfig:
    """Priority weight configuration."""
    blocker_weight: float = 1.0
    approval_weight: float = 0.9
    regression_weight: float = 0.85
    spec_review_weight: float = 0.88
    in_progress_weight: float = 0.7
    new_feature_weight: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriorityConfig":
        """Create config from dictionary."""
        return cls(
            blocker_weight=data.get("blocker_weight", 1.0),
            approval_weight=data.get("approval_weight", 0.9),
            regression_weight=data.get("regression_weight", 0.85),
            spec_review_weight=data.get("spec_review_weight", 0.88),
            in_progress_weight=data.get("in_progress_weight", 0.7),
            new_feature_weight=data.get("new_feature_weight", 0.5),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "blocker_weight": self.blocker_weight,
            "approval_weight": self.approval_weight,
            "regression_weight": self.regression_weight,
            "spec_review_weight": self.spec_review_weight,
            "in_progress_weight": self.in_progress_weight,
            "new_feature_weight": self.new_feature_weight,
        }


@dataclass
class StandupConfig:
    """Standup preferences."""
    auto_run_on_start: bool = False
    include_github: bool = True
    include_tests: bool = True
    include_specs: bool = True
    history_days: int = 7

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupConfig":
        """Create config from dictionary."""
        return cls(
            auto_run_on_start=data.get("auto_run_on_start", False),
            include_github=data.get("include_github", True),
            include_tests=data.get("include_tests", True),
            include_specs=data.get("include_specs", True),
            history_days=data.get("history_days", 7),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "auto_run_on_start": self.auto_run_on_start,
            "include_github": self.include_github,
            "include_tests": self.include_tests,
            "include_specs": self.include_specs,
            "history_days": self.history_days,
        }


@dataclass
class AutopilotConfig:
    """Autopilot preferences."""
    default_budget: float = 10.0
    default_duration: str = "2h"
    pause_on_approval: bool = True
    pause_on_high_risk: bool = True
    persist_on_checkpoint: bool = True
    execution_strategy: Any = None  # ExecutionStrategy enum, defaults to CONTINUE_ON_BLOCK

    # Jarvis MVP: Risk thresholds
    risk_checkpoint_threshold: float = 0.5  # Score > this requires checkpoint
    risk_block_threshold: float = 0.8  # Score > this blocks execution

    # Jarvis MVP: Auto-approve low-risk
    auto_approve_low_risk: bool = True  # If True, skip checkpoint for risk < 0.3

    # Jarvis MVP: Checkpoint budget (per session) - limits interruptions
    checkpoint_budget: int = 3  # Max checkpoints before auto-logging instead of pausing

    # Jarvis MVP: Show similar decisions in checkpoint context
    show_similar_decisions: bool = True  # Include past similar decisions in checkpoint

    def __post_init__(self) -> None:
        """Set default execution_strategy if not provided."""
        if self.execution_strategy is None:
            ExecutionStrategy = _get_execution_strategy_enum()
            self.execution_strategy = ExecutionStrategy.SEQUENTIAL

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotConfig":
        """Create config from dictionary."""
        # Parse execution_strategy from string to enum
        ExecutionStrategy = _get_execution_strategy_enum()
        execution_strategy_str = data.get("execution_strategy")
        execution_strategy = None
        if execution_strategy_str:
            try:
                execution_strategy = ExecutionStrategy(execution_strategy_str)
            except ValueError:
                execution_strategy = ExecutionStrategy.SEQUENTIAL

        return cls(
            default_budget=data.get("default_budget", 10.0),
            default_duration=data.get("default_duration", "2h"),
            pause_on_approval=data.get("pause_on_approval", True),
            pause_on_high_risk=data.get("pause_on_high_risk", True),
            persist_on_checkpoint=data.get("persist_on_checkpoint", True),
            execution_strategy=execution_strategy,
            risk_checkpoint_threshold=data.get("risk_checkpoint_threshold", 0.5),
            risk_block_threshold=data.get("risk_block_threshold", 0.8),
            auto_approve_low_risk=data.get("auto_approve_low_risk", True),
            checkpoint_budget=data.get("checkpoint_budget", 3),
            show_similar_decisions=data.get("show_similar_decisions", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        # Get execution_strategy value (handle enum or string)
        exec_strategy = self.execution_strategy
        if hasattr(exec_strategy, 'value'):
            exec_strategy_value = exec_strategy.value
        else:
            exec_strategy_value = str(exec_strategy)

        return {
            "default_budget": self.default_budget,
            "default_duration": self.default_duration,
            "pause_on_approval": self.pause_on_approval,
            "pause_on_high_risk": self.pause_on_high_risk,
            "persist_on_checkpoint": self.persist_on_checkpoint,
            "execution_strategy": exec_strategy_value,
            "risk_checkpoint_threshold": self.risk_checkpoint_threshold,
            "risk_block_threshold": self.risk_block_threshold,
            "auto_approve_low_risk": self.auto_approve_low_risk,
            "checkpoint_budget": self.checkpoint_budget,
            "show_similar_decisions": self.show_similar_decisions,
        }


@dataclass
class ChiefOfStaffConfig:
    """Chief of Staff configuration."""
    checkpoints: CheckpointConfig = field(default_factory=CheckpointConfig)
    priorities: PriorityConfig = field(default_factory=PriorityConfig)
    standup: StandupConfig = field(default_factory=StandupConfig)
    autopilot: AutopilotConfig = field(default_factory=AutopilotConfig)
    storage_path: str = ".swarm/chief-of-staff"
    budget_usd: float | None = None
    duration_minutes: int | None = None
    error_streak: int | None = None
    min_execution_budget: float = 0.50
    checkpoint_cost_single: float = 5.0
    checkpoint_cost_daily: float = 15.0

    def __post_init__(self) -> None:
        """Set budget/duration/error_streak from checkpoints if not explicitly set."""
        if self.budget_usd is None:
            self.budget_usd = self.checkpoints.budget_usd
        if self.duration_minutes is None:
            self.duration_minutes = self.checkpoints.duration_minutes
        if self.error_streak is None:
            self.error_streak = self.checkpoints.error_streak

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChiefOfStaffConfig":
        """Create config from dictionary (e.g., from YAML)."""
        if not data:
            return cls()

        checkpoints_data = data.get("checkpoints", {})
        priorities_data = data.get("priorities", {})
        standup_data = data.get("standup", {})
        autopilot_data = data.get("autopilot", {})

        return cls(
            checkpoints=CheckpointConfig.from_dict(checkpoints_data),
            priorities=PriorityConfig.from_dict(priorities_data),
            standup=StandupConfig.from_dict(standup_data),
            autopilot=AutopilotConfig.from_dict(autopilot_data),
            storage_path=data.get("storage_path", ".swarm/chief-of-staff"),
            budget_usd=data.get("budget_usd"),
            duration_minutes=data.get("duration_minutes"),
            error_streak=data.get("error_streak"),
            min_execution_budget=data.get("min_execution_budget", 0.50),
            checkpoint_cost_single=data.get("checkpoint_cost_single", 5.0),
            checkpoint_cost_daily=data.get("checkpoint_cost_daily", 15.0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "checkpoints": self.checkpoints.to_dict(),
            "priorities": self.priorities.to_dict(),
            "standup": self.standup.to_dict(),
            "autopilot": self.autopilot.to_dict(),
            "storage_path": self.storage_path,
            "budget_usd": self.budget_usd,
            "duration_minutes": self.duration_minutes,
            "error_streak": self.error_streak,
            "min_execution_budget": self.min_execution_budget,
            "checkpoint_cost_single": self.checkpoint_cost_single,
            "checkpoint_cost_daily": self.checkpoint_cost_daily,
        }