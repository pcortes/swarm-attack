"""Data models for Chief of Staff agent."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Literal


class GoalStatus(Enum):
    """Status of a daily goal."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class CheckpointTrigger(Enum):
    """Types of checkpoint triggers."""
    COST_THRESHOLD = "cost_threshold_reached"
    TIME_THRESHOLD = "time_threshold_reached"
    BLOCKER_DETECTED = "blocker_detected"
    APPROVAL_REQUIRED = "approval_required"
    HIGH_RISK_ACTION = "high_risk_action"
    ERROR_RATE_SPIKE = "error_rate_spike"
    END_OF_SESSION = "end_of_session"


@dataclass
class DailyGoal:
    """A single goal for the day."""
    id: str
    content: str
    priority: Literal["P1", "P2", "P3"]
    status: GoalStatus = GoalStatus.PENDING
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    notes: str = ""
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None
    linked_spec: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "priority": self.priority,
            "status": self.status.value,
            "estimated_minutes": self.estimated_minutes,
            "actual_minutes": self.actual_minutes,
            "notes": self.notes,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
            "linked_spec": self.linked_spec,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyGoal":
        """Create from dictionary."""
        data = data.copy()
        data["status"] = GoalStatus(data["status"])
        return cls(**data)


@dataclass
class CheckpointEvent:
    """A checkpoint during autopilot execution."""
    timestamp: str
    trigger: CheckpointTrigger
    context: dict[str, Any]
    action_taken: str
    human_response: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "trigger": self.trigger.value,
            "context": self.context,
            "action_taken": self.action_taken,
            "human_response": self.human_response,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointEvent":
        """Create from dictionary."""
        data = data.copy()
        data["trigger"] = CheckpointTrigger(data["trigger"])
        return cls(**data)


@dataclass
class AutopilotSession:
    """An autopilot execution session with persistence support."""
    session_id: str
    started_at: str
    budget_usd: float
    duration_limit_seconds: int
    stop_trigger: Optional[CheckpointTrigger] = None
    goals: list[DailyGoal] = field(default_factory=list)
    current_goal_index: int = 0
    checkpoints: list[CheckpointEvent] = field(default_factory=list)
    cost_spent_usd: float = 0.0
    duration_seconds: int = 0
    status: str = "running"
    pause_reason: Optional[str] = None
    ended_at: Optional[str] = None
    last_persisted_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "budget_usd": self.budget_usd,
            "duration_limit_seconds": self.duration_limit_seconds,
            "stop_trigger": self.stop_trigger.value if self.stop_trigger else None,
            "goals": [g.to_dict() for g in self.goals],
            "current_goal_index": self.current_goal_index,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "cost_spent_usd": self.cost_spent_usd,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "pause_reason": self.pause_reason,
            "ended_at": self.ended_at,
            "last_persisted_at": self.last_persisted_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotSession":
        """Create from dictionary."""
        data = data.copy()
        if data.get("stop_trigger"):
            data["stop_trigger"] = CheckpointTrigger(data["stop_trigger"])
        data["goals"] = [DailyGoal.from_dict(g) for g in data.get("goals", [])]
        data["checkpoints"] = [CheckpointEvent.from_dict(c) for c in data.get("checkpoints", [])]
        return cls(**data)