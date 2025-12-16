"""Data models for Chief of Staff agent."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional


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
        """Convert to dictionary for JSON serialization."""
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
        """Convert to dictionary for JSON serialization."""
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


@dataclass
class Decision:
    """A decision made during the day."""
    timestamp: str
    type: str
    item: str
    decision: str
    rationale: str
    human_override: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "type": self.type,
            "item": self.item,
            "decision": self.decision,
            "rationale": self.rationale,
            "human_override": self.human_override,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class WorkLogEntry:
    """A single entry in the work log."""
    timestamp: str
    action: str
    result: str
    cost_usd: float = 0.0
    duration_seconds: int = 0
    checkpoint: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "result": self.result,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
            "checkpoint": self.checkpoint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkLogEntry":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class StandupSession:
    """Record of a standup session."""
    session_id: str
    time: str
    yesterday_goals: list[DailyGoal] = field(default_factory=list)
    today_goals: list[DailyGoal] = field(default_factory=list)
    philip_notes: str = ""
    recommendations_accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "time": self.time,
            "yesterday_goals": [g.to_dict() for g in self.yesterday_goals],
            "today_goals": [g.to_dict() for g in self.today_goals],
            "philip_notes": self.philip_notes,
            "recommendations_accepted": self.recommendations_accepted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupSession":
        """Create from dictionary."""
        data = data.copy()
        data["yesterday_goals"] = [DailyGoal.from_dict(g) for g in data.get("yesterday_goals", [])]
        data["today_goals"] = [DailyGoal.from_dict(g) for g in data.get("today_goals", [])]
        return cls(**data)


@dataclass
class DailySummary:
    """End-of-day summary."""
    goals_completed: int
    goals_total: int
    total_cost_usd: float
    key_accomplishments: list[str] = field(default_factory=list)
    blockers_for_tomorrow: list[str] = field(default_factory=list)
    carryover_goals: list[DailyGoal] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "goals_completed": self.goals_completed,
            "goals_total": self.goals_total,
            "total_cost_usd": self.total_cost_usd,
            "key_accomplishments": self.key_accomplishments,
            "blockers_for_tomorrow": self.blockers_for_tomorrow,
            "carryover_goals": [g.to_dict() for g in self.carryover_goals],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailySummary":
        """Create from dictionary."""
        data = data.copy()
        data["carryover_goals"] = [DailyGoal.from_dict(g) for g in data.get("carryover_goals", [])]
        return cls(**data)


@dataclass
class DailyLog:
    """Complete daily log for a single day."""
    date: str
    standups: list[StandupSession] = field(default_factory=list)
    work_log: list[WorkLogEntry] = field(default_factory=list)
    summary: Optional[DailySummary] = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date,
            "standups": [s.to_dict() for s in self.standups],
            "work_log": [w.to_dict() for w in self.work_log],
            "summary": self.summary.to_dict() if self.summary else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyLog":
        """Create from dictionary."""
        data = data.copy()
        data["standups"] = [StandupSession.from_dict(s) for s in data.get("standups", [])]
        data["work_log"] = [WorkLogEntry.from_dict(w) for w in data.get("work_log", [])]
        if data.get("summary"):
            data["summary"] = DailySummary.from_dict(data["summary"])
        return cls(**data)