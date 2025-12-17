"""Models for Chief of Staff agent."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


class GoalStatus(Enum):
    """Status of a daily goal."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"
    PARTIAL = "partial"
    CARRIED_OVER = "carried_over"


class CheckpointTrigger(Enum):
    """Types of checkpoint triggers for autopilot sessions."""
    COST_THRESHOLD = "cost_threshold"
    TIME_THRESHOLD = "time_threshold"
    GOAL_COMPLETE = "goal_complete"
    APPROVAL_REQUIRED = "approval_required"
    ERROR = "error"
    USER_INTERRUPT = "user_interrupt"
    HIGH_RISK_ACTION = "high_risk_action"
    ERROR_RATE_SPIKE = "error_rate_spike"
    BLOCKER_DETECTED = "blocker_detected"


@dataclass
class DailyGoal:
    """A single goal for the day."""
    id: str
    content: str
    priority: str = "P2"
    status: GoalStatus = GoalStatus.PENDING
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    notes: Optional[str] = None
    completed_at: Optional[str] = None
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None
    linked_spec: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyGoal":
        """Create from dictionary."""
        status = data.get("status", "pending")
        if isinstance(status, str):
            status = GoalStatus(status)
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            priority=data.get("priority", "P2"),
            status=status,
            estimated_minutes=data.get("estimated_minutes"),
            actual_minutes=data.get("actual_minutes"),
            notes=data.get("notes"),
            completed_at=data.get("completed_at"),
            linked_feature=data.get("linked_feature"),
            linked_bug=data.get("linked_bug"),
            linked_spec=data.get("linked_spec"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "priority": self.priority,
            "status": self.status.value if isinstance(self.status, GoalStatus) else self.status,
            "estimated_minutes": self.estimated_minutes,
            "actual_minutes": self.actual_minutes,
            "notes": self.notes,
            "completed_at": self.completed_at,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
            "linked_spec": self.linked_spec,
        }


@dataclass
class StandupSession:
    """A standup session with goals."""
    session_id: str
    time: str
    yesterday_goals: list[DailyGoal] = field(default_factory=list)
    today_goals: list[DailyGoal] = field(default_factory=list)
    notes: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupSession":
        """Create from dictionary."""
        return cls(
            session_id=data.get("session_id", ""),
            time=data.get("time", ""),
            yesterday_goals=[DailyGoal.from_dict(g) for g in data.get("yesterday_goals", [])],
            today_goals=[DailyGoal.from_dict(g) for g in data.get("today_goals", [])],
            notes=data.get("notes"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "time": self.time,
            "yesterday_goals": [g.to_dict() for g in self.yesterday_goals],
            "today_goals": [g.to_dict() for g in self.today_goals],
            "notes": self.notes,
        }


@dataclass
class WorkLogEntry:
    """A work log entry."""
    entry_id: str
    time: str
    description: str
    duration_minutes: Optional[int] = None
    outcome: Optional[str] = None
    linked_goal_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkLogEntry":
        """Create from dictionary."""
        return cls(
            entry_id=data.get("entry_id", ""),
            time=data.get("time", ""),
            description=data.get("description", ""),
            duration_minutes=data.get("duration_minutes"),
            outcome=data.get("outcome"),
            linked_goal_id=data.get("linked_goal_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "time": self.time,
            "description": self.description,
            "duration_minutes": self.duration_minutes,
            "outcome": self.outcome,
            "linked_goal_id": self.linked_goal_id,
        }


@dataclass
class DailySummary:
    """End-of-day summary."""
    accomplishments: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    mood: Optional[str] = None
    productivity_score: Optional[int] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailySummary":
        """Create from dictionary."""
        return cls(
            accomplishments=data.get("accomplishments", []),
            blockers=data.get("blockers", []),
            learnings=data.get("learnings", []),
            mood=data.get("mood"),
            productivity_score=data.get("productivity_score"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "accomplishments": self.accomplishments,
            "blockers": self.blockers,
            "learnings": self.learnings,
            "mood": self.mood,
            "productivity_score": self.productivity_score,
        }


@dataclass
class Decision:
    """A recorded decision."""
    decision_id: str
    timestamp: str
    decision_type: str
    description: str
    rationale: Optional[str] = None
    alternatives_considered: list[str] = field(default_factory=list)
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        """Create from dictionary."""
        return cls(
            decision_id=data.get("decision_id", ""),
            timestamp=data.get("timestamp", ""),
            decision_type=data.get("decision_type", ""),
            description=data.get("description", ""),
            rationale=data.get("rationale"),
            alternatives_considered=data.get("alternatives_considered", []),
            linked_feature=data.get("linked_feature"),
            linked_bug=data.get("linked_bug"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp,
            "decision_type": self.decision_type,
            "description": self.description,
            "rationale": self.rationale,
            "alternatives_considered": self.alternatives_considered,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
        }


@dataclass
class DailyLog:
    """A daily log containing standups, work entries, and summary."""
    date: str
    standups: list[StandupSession] = field(default_factory=list)
    work_log: list[WorkLogEntry] = field(default_factory=list)
    summary: Optional[DailySummary] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyLog":
        """Create from dictionary."""
        summary_data = data.get("summary")
        return cls(
            date=data.get("date", ""),
            standups=[StandupSession.from_dict(s) for s in data.get("standups", [])],
            work_log=[WorkLogEntry.from_dict(e) for e in data.get("work_log", [])],
            summary=DailySummary.from_dict(summary_data) if summary_data else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "standups": [s.to_dict() for s in self.standups],
            "work_log": [e.to_dict() for e in self.work_log],
            "summary": self.summary.to_dict() if self.summary else None,
        }


@dataclass
class GitState:
    """Git repository state."""
    branch: str
    is_clean: bool
    uncommitted_files: list[str] = field(default_factory=list)
    unpushed_commits: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitState":
        """Create from dictionary."""
        return cls(
            branch=data.get("branch", ""),
            is_clean=data.get("is_clean", True),
            uncommitted_files=data.get("uncommitted_files", []),
            unpushed_commits=data.get("unpushed_commits", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "branch": self.branch,
            "is_clean": self.is_clean,
            "uncommitted_files": self.uncommitted_files,
            "unpushed_commits": self.unpushed_commits,
        }


@dataclass
class FeatureSummary:
    """Summary of a feature's state."""
    feature_id: str
    phase: str
    tasks_done: int
    tasks_total: int
    tasks_blocked: int
    cost_usd: float
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureSummary":
        """Create from dictionary."""
        return cls(
            feature_id=data.get("feature_id", ""),
            phase=data.get("phase", ""),
            tasks_done=data.get("tasks_done", 0),
            tasks_total=data.get("tasks_total", 0),
            tasks_blocked=data.get("tasks_blocked", 0),
            cost_usd=data.get("cost_usd", 0.0),
            updated_at=data.get("updated_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_id": self.feature_id,
            "phase": self.phase,
            "tasks_done": self.tasks_done,
            "tasks_total": self.tasks_total,
            "tasks_blocked": self.tasks_blocked,
            "cost_usd": self.cost_usd,
            "updated_at": self.updated_at,
        }


@dataclass
class BugSummary:
    """Summary of a bug's state."""
    bug_id: str
    phase: str
    cost_usd: float
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BugSummary":
        """Create from dictionary."""
        return cls(
            bug_id=data.get("bug_id", ""),
            phase=data.get("phase", ""),
            cost_usd=data.get("cost_usd", 0.0),
            updated_at=data.get("updated_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bug_id": self.bug_id,
            "phase": self.phase,
            "cost_usd": self.cost_usd,
            "updated_at": self.updated_at,
        }


@dataclass
class PRDSummary:
    """Summary of a PRD."""
    feature_id: str
    title: str
    phase: str
    path: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PRDSummary":
        """Create from dictionary."""
        return cls(
            feature_id=data.get("feature_id", ""),
            title=data.get("title", ""),
            phase=data.get("phase", ""),
            path=data.get("path", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "phase": self.phase,
            "path": self.path,
        }


@dataclass
class SpecSummary:
    """Summary of a spec."""
    feature_id: str
    title: str
    path: str
    has_review: bool = False
    review_passed: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpecSummary":
        """Create from dictionary."""
        return cls(
            feature_id=data.get("feature_id", ""),
            title=data.get("title", ""),
            path=data.get("path", ""),
            has_review=data.get("has_review", False),
            review_passed=data.get("review_passed", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "path": self.path,
            "has_review": self.has_review,
            "review_passed": self.review_passed,
        }


@dataclass
class TestState:
    """Test suite state."""
    total_tests: int = 0
    passing: int = 0
    failing: int = 0
    skipped: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestState":
        """Create from dictionary."""
        return cls(
            total_tests=data.get("total_tests", 0),
            passing=data.get("passing", 0),
            failing=data.get("failing", 0),
            skipped=data.get("skipped", 0),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_tests": self.total_tests,
            "passing": self.passing,
            "failing": self.failing,
            "skipped": self.skipped,
        }


@dataclass
class RepoStateSnapshot:
    """Snapshot of the entire repository state."""
    gathered_at: str
    git: GitState = field(default_factory=lambda: GitState(branch="main", is_clean=True))
    features: list[FeatureSummary] = field(default_factory=list)
    bugs: list[BugSummary] = field(default_factory=list)
    prds: list[PRDSummary] = field(default_factory=list)
    specs: list[SpecSummary] = field(default_factory=list)
    tests: Optional[TestState] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoStateSnapshot":
        """Create from dictionary."""
        git_data = data.get("git", {"branch": "main", "is_clean": True})
        tests_data = data.get("tests")
        return cls(
            gathered_at=data.get("gathered_at", ""),
            git=GitState.from_dict(git_data),
            features=[FeatureSummary.from_dict(f) for f in data.get("features", [])],
            bugs=[BugSummary.from_dict(b) for b in data.get("bugs", [])],
            prds=[PRDSummary.from_dict(p) for p in data.get("prds", [])],
            specs=[SpecSummary.from_dict(s) for s in data.get("specs", [])],
            tests=TestState.from_dict(tests_data) if tests_data else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gathered_at": self.gathered_at,
            "git": self.git.to_dict(),
            "features": [f.to_dict() for f in self.features],
            "bugs": [b.to_dict() for b in self.bugs],
            "prds": [p.to_dict() for p in self.prds],
            "specs": [s.to_dict() for s in self.specs],
            "tests": self.tests.to_dict() if self.tests else None,
        }


@dataclass
class Recommendation:
    """A task recommendation."""
    task: str
    priority: str
    rationale: str
    estimated_minutes: Optional[int] = None
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None
    linked_spec: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recommendation":
        """Create from dictionary."""
        return cls(
            task=data.get("task", ""),
            priority=data.get("priority", "P2"),
            rationale=data.get("rationale", ""),
            estimated_minutes=data.get("estimated_minutes"),
            linked_feature=data.get("linked_feature"),
            linked_bug=data.get("linked_bug"),
            linked_spec=data.get("linked_spec"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task": self.task,
            "priority": self.priority,
            "rationale": self.rationale,
            "estimated_minutes": self.estimated_minutes,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
            "linked_spec": self.linked_spec,
        }


@dataclass
class CheckpointEvent:
    """A checkpoint event during autopilot execution."""
    event_id: str
    timestamp: str
    trigger: CheckpointTrigger
    description: str
    cost_at_checkpoint: float = 0.0
    duration_at_checkpoint: int = 0
    goal_index: Optional[int] = None
    requires_approval: bool = False
    approved: Optional[bool] = None
    approved_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointEvent":
        """Create from dictionary."""
        trigger = data.get("trigger")
        if isinstance(trigger, str):
            trigger = CheckpointTrigger(trigger)
        return cls(
            event_id=data.get("event_id", ""),
            timestamp=data.get("timestamp", ""),
            trigger=trigger,
            description=data.get("description", ""),
            cost_at_checkpoint=data.get("cost_at_checkpoint", 0.0),
            duration_at_checkpoint=data.get("duration_at_checkpoint", 0),
            goal_index=data.get("goal_index"),
            requires_approval=data.get("requires_approval", False),
            approved=data.get("approved"),
            approved_at=data.get("approved_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "trigger": self.trigger.value if isinstance(self.trigger, CheckpointTrigger) else self.trigger,
            "description": self.description,
            "cost_at_checkpoint": self.cost_at_checkpoint,
            "duration_at_checkpoint": self.duration_at_checkpoint,
            "goal_index": self.goal_index,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "approved_at": self.approved_at,
        }


@dataclass
class AutopilotSession:
    """An autopilot session for autonomous goal execution."""
    session_id: str
    started_at: str
    budget_usd: float
    duration_limit_seconds: int
    goals: list[DailyGoal] = field(default_factory=list)
    current_goal_index: int = 0
    cost_spent_usd: float = 0.0
    duration_seconds: int = 0
    status: str = "pending"  # pending, running, paused, completed, failed
    stop_trigger: Optional[CheckpointTrigger] = None
    checkpoint_events: list[CheckpointEvent] = field(default_factory=list)
    ended_at: Optional[str] = None
    end_reason: Optional[str] = None
    last_persisted_at: Optional[str] = None
    pause_reason: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotSession":
        """Create from dictionary."""
        stop_trigger = data.get("stop_trigger")
        if isinstance(stop_trigger, str):
            stop_trigger = CheckpointTrigger(stop_trigger)
        return cls(
            session_id=data.get("session_id", ""),
            started_at=data.get("started_at", ""),
            budget_usd=data.get("budget_usd", 0.0),
            duration_limit_seconds=data.get("duration_limit_seconds", 0),
            goals=[DailyGoal.from_dict(g) for g in data.get("goals", [])],
            current_goal_index=data.get("current_goal_index", 0),
            cost_spent_usd=data.get("cost_spent_usd", 0.0),
            duration_seconds=data.get("duration_seconds", 0),
            status=data.get("status", "pending"),
            stop_trigger=stop_trigger,
            checkpoint_events=[CheckpointEvent.from_dict(e) for e in data.get("checkpoint_events", [])],
            ended_at=data.get("ended_at"),
            end_reason=data.get("end_reason"),
            last_persisted_at=data.get("last_persisted_at"),
            pause_reason=data.get("pause_reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "budget_usd": self.budget_usd,
            "duration_limit_seconds": self.duration_limit_seconds,
            "goals": [g.to_dict() for g in self.goals],
            "current_goal_index": self.current_goal_index,
            "cost_spent_usd": self.cost_spent_usd,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "stop_trigger": self.stop_trigger.value if isinstance(self.stop_trigger, CheckpointTrigger) else self.stop_trigger,
            "checkpoint_events": [e.to_dict() for e in self.checkpoint_events],
            "ended_at": self.ended_at,
            "end_reason": self.end_reason,
            "last_persisted_at": self.last_persisted_at,
            "pause_reason": self.pause_reason,
        }