"""
Chief of Staff configuration dataclasses.

This module provides configuration for the Chief of Staff autonomous orchestration layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckpointConfig:
    """Checkpoint trigger configuration."""
    budget_usd: float = 10.0
    duration_minutes: int = 120
    error_streak: int = 3


@dataclass
class PriorityConfig:
    """Priority weight configuration."""
    blocker_weight: float = 1.0
    approval_weight: float = 0.9
    regression_weight: float = 0.85
    spec_review_weight: float = 0.88
    in_progress_weight: float = 0.7
    new_feature_weight: float = 0.5


@dataclass
class StandupConfig:
    """Standup preferences."""
    auto_run_on_start: bool = False
    include_github: bool = True
    include_tests: bool = True
    include_specs: bool = True
    history_days: int = 7


@dataclass
class AutopilotConfig:
    """Autopilot preferences."""
    default_budget: float = 10.0
    default_duration: str = "2h"
    pause_on_approval: bool = True
    pause_on_high_risk: bool = True
    persist_on_checkpoint: bool = True


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
            checkpoints=CheckpointConfig(
                budget_usd=checkpoints_data.get("budget_usd", 10.0),
                duration_minutes=checkpoints_data.get("duration_minutes", 120),
                error_streak=checkpoints_data.get("error_streak", 3),
            ),
            priorities=PriorityConfig(
                blocker_weight=priorities_data.get("blocker_weight", 1.0),
                approval_weight=priorities_data.get("approval_weight", 0.9),
                regression_weight=priorities_data.get("regression_weight", 0.85),
                spec_review_weight=priorities_data.get("spec_review_weight", 0.88),
                in_progress_weight=priorities_data.get("in_progress_weight", 0.7),
                new_feature_weight=priorities_data.get("new_feature_weight", 0.5),
            ),
            standup=StandupConfig(
                auto_run_on_start=standup_data.get("auto_run_on_start", False),
                include_github=standup_data.get("include_github", True),
                include_tests=standup_data.get("include_tests", True),
                include_specs=standup_data.get("include_specs", True),
                history_days=standup_data.get("history_days", 7),
            ),
            autopilot=AutopilotConfig(
                default_budget=autopilot_data.get("default_budget", 10.0),
                default_duration=autopilot_data.get("default_duration", "2h"),
                pause_on_approval=autopilot_data.get("pause_on_approval", True),
                pause_on_high_risk=autopilot_data.get("pause_on_high_risk", True),
                persist_on_checkpoint=autopilot_data.get("persist_on_checkpoint", True),
            ),
            storage_path=data.get("storage_path", ".swarm/chief-of-staff"),
            budget_usd=data.get("budget_usd"),
            duration_minutes=data.get("duration_minutes"),
            error_streak=data.get("error_streak"),
            min_execution_budget=data.get("min_execution_budget", 0.50),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "checkpoints": {
                "budget_usd": self.checkpoints.budget_usd,
                "duration_minutes": self.checkpoints.duration_minutes,
                "error_streak": self.checkpoints.error_streak,
            },
            "priorities": {
                "blocker_weight": self.priorities.blocker_weight,
                "approval_weight": self.priorities.approval_weight,
                "regression_weight": self.priorities.regression_weight,
                "spec_review_weight": self.priorities.spec_review_weight,
                "in_progress_weight": self.priorities.in_progress_weight,
                "new_feature_weight": self.priorities.new_feature_weight,
            },
            "standup": {
                "auto_run_on_start": self.standup.auto_run_on_start,
                "include_github": self.standup.include_github,
                "include_tests": self.standup.include_tests,
                "include_specs": self.standup.include_specs,
                "history_days": self.standup.history_days,
            },
            "autopilot": {
                "default_budget": self.autopilot.default_budget,
                "default_duration": self.autopilot.default_duration,
                "pause_on_approval": self.autopilot.pause_on_approval,
                "pause_on_high_risk": self.autopilot.pause_on_high_risk,
                "persist_on_checkpoint": self.autopilot.persist_on_checkpoint,
            },
            "storage_path": self.storage_path,
            "budget_usd": self.budget_usd,
            "duration_minutes": self.duration_minutes,
            "error_streak": self.error_streak,
            "min_execution_budget": self.min_execution_budget,
        }