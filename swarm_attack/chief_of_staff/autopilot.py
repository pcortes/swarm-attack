"""Autopilot session models for pause/resume functionality."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AutopilotState(Enum):
    """State of an autopilot session."""
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AutopilotSession:
    """Represents an autopilot session that can be paused and resumed."""

    session_id: str
    state: AutopilotState = AutopilotState.RUNNING

    # Legacy fields (for feature-based sessions)
    feature_id: str = ""
    current_issue: Optional[int] = None
    completed_issues: list[int] = field(default_factory=list)

    # Goal-based execution fields (Issue #12 / chief-of-staff-v2)
    goals: list[dict[str, Any]] = field(default_factory=list)
    current_goal_index: int = 0
    total_cost_usd: float = 0.0
    budget_usd: Optional[float] = None
    duration_minutes: Optional[int] = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    last_persisted_at: Optional[datetime] = None

    # Error tracking
    error_message: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotSession":
        """Create AutopilotSession from dictionary."""
        state_str = data.get("state", "running")
        try:
            state = AutopilotState(state_str)
        except ValueError:
            state = AutopilotState.RUNNING

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        last_persisted_at = data.get("last_persisted_at")
        if isinstance(last_persisted_at, str):
            last_persisted_at = datetime.fromisoformat(last_persisted_at)

        return cls(
            session_id=data.get("session_id", ""),
            state=state,
            feature_id=data.get("feature_id", ""),
            current_issue=data.get("current_issue"),
            completed_issues=data.get("completed_issues", []),
            goals=data.get("goals", []),
            current_goal_index=data.get("current_goal_index", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            budget_usd=data.get("budget_usd"),
            duration_minutes=data.get("duration_minutes"),
            created_at=created_at,
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            last_persisted_at=last_persisted_at,
            error_message=data.get("error_message"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert AutopilotSession to dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "feature_id": self.feature_id,
            "current_issue": self.current_issue,
            "completed_issues": self.completed_issues,
            "goals": self.goals,
            "current_goal_index": self.current_goal_index,
            "total_cost_usd": self.total_cost_usd,
            "budget_usd": self.budget_usd,
            "duration_minutes": self.duration_minutes,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "last_persisted_at": self.last_persisted_at.isoformat() if self.last_persisted_at else None,
            "error_message": self.error_message,
        }