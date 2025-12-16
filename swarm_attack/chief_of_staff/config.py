"""Configuration for Chief of Staff agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckpointConfig:
    """Checkpoint trigger configuration."""
    budget_usd: float = 10.0
    duration_minutes: int = 120
    error_streak: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointConfig:
        """Create CheckpointConfig from dictionary."""
        return cls(
            budget_usd=data.get("budget_usd", 10.0),
            duration_minutes=data.get("duration_minutes", 120),
            error_streak=data.get("error_streak", 3),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
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
    def from_dict(cls, data: dict[str, Any]) -> PriorityConfig:
        """Create PriorityConfig from dictionary."""
        return cls(
            blocker_weight=data.get("blocker_weight", 1.0),
            approval_weight=data.get("approval_weight", 0.9),
            regression_weight=data.get("regression_weight", 0.85),
            spec_review_weight=data.get("spec_review_weight", 0.88),
            in_progress_weight=data.get("in_progress_weight", 0.7),
            new_feature_weight=data.get("new_feature_weight", 0.5),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
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
    def from_dict(cls, data: dict[str, Any]) -> StandupConfig:
        """Create StandupConfig from dictionary."""
        return cls(
            auto_run_on_start=data.get("auto_run_on_start", False),
            include_github=data.get("include_github", True),
            include_tests=data.get("include_tests", True),
            include_specs=data.get("include_specs", True),
            history_days=data.get("history_days", 7),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "auto_run_on_start": self.auto_run_on_start,
            "include_github": self.include_github,
            "include_tests": self.include_tests,
            "include_specs": self.include_specs,
            "history_days": self.history_days,
        }


@dataclass
class AutopilotConfigPrefs:
    """Autopilot preferences."""
    default_budget: float = 10.0
    default_duration: str = "2h"
    pause_on_approval: bool = True
    pause_on_high_risk: bool = True
    persist_on_checkpoint: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutopilotConfigPrefs:
        """Create AutopilotConfigPrefs from dictionary."""
        return cls(
            default_budget=data.get("default_budget", 10.0),
            default_duration=data.get("default_duration", "2h"),
            pause_on_approval=data.get("pause_on_approval", True),
            pause_on_high_risk=data.get("pause_on_high_risk", True),
            persist_on_checkpoint=data.get("persist_on_checkpoint", True),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "default_budget": self.default_budget,
            "default_duration": self.default_duration,
            "pause_on_approval": self.pause_on_approval,
            "pause_on_high_risk": self.pause_on_high_risk,
            "persist_on_checkpoint": self.persist_on_checkpoint,
        }


@dataclass
class ChiefOfStaffConfig:
    """Chief of Staff configuration."""
    checkpoints: CheckpointConfig = field(default_factory=CheckpointConfig)
    priorities: PriorityConfig = field(default_factory=PriorityConfig)
    standup: StandupConfig = field(default_factory=StandupConfig)
    autopilot: AutopilotConfigPrefs = field(default_factory=AutopilotConfigPrefs)
    storage_path: str = ".swarm/chief-of-staff"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChiefOfStaffConfig:
        """Create ChiefOfStaffConfig from dictionary."""
        return cls(
            checkpoints=CheckpointConfig.from_dict(data.get("checkpoints", {})),
            priorities=PriorityConfig.from_dict(data.get("priorities", {})),
            standup=StandupConfig.from_dict(data.get("standup", {})),
            autopilot=AutopilotConfigPrefs.from_dict(data.get("autopilot", {})),
            storage_path=data.get("storage_path", ".swarm/chief-of-staff"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoints": self.checkpoints.to_dict(),
            "priorities": self.priorities.to_dict(),
            "standup": self.standup.to_dict(),
            "autopilot": self.autopilot.to_dict(),
            "storage_path": self.storage_path,
        }