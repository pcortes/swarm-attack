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
        if isinstance(data.get("status"), str):
            data["status"] = GoalStatus(data["status"])
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
    yesterday_goals: list[DailyGoal]
    today_goals: list[DailyGoal]
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
    key_accomplishments: list[str]
    blockers_for_tomorrow: list[str]
    carryover_goals: list[DailyGoal]

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


@dataclass
class GitState:
    """Current git state."""
    branch: str
    is_clean: bool
    uncommitted_files: list[str]
    recent_commits: list[dict[str, str]]
    ahead_behind: tuple[int, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "is_clean": self.is_clean,
            "uncommitted_files": self.uncommitted_files,
            "recent_commits": self.recent_commits,
            "ahead_behind": list(self.ahead_behind),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitState":
        """Create from dictionary."""
        data = data.copy()
        if isinstance(data.get("ahead_behind"), list):
            data["ahead_behind"] = tuple(data["ahead_behind"])
        return cls(**data)


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "phase": self.phase,
            "tasks_done": self.tasks_done,
            "tasks_total": self.tasks_total,
            "tasks_blocked": self.tasks_blocked,
            "cost_usd": self.cost_usd,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureSummary":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BugSummary:
    """Summary of a bug's state."""
    bug_id: str
    phase: str
    cost_usd: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bug_id": self.bug_id,
            "phase": self.phase,
            "cost_usd": self.cost_usd,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BugSummary":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PRDSummary:
    """Summary of a PRD."""
    feature_id: str
    title: str
    phase: str
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "phase": self.phase,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PRDSummary":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SpecSummary:
    """Summary of a spec file."""
    feature_id: str
    title: str
    path: str
    has_review: bool
    review_passed: bool
    review_scores: Optional[dict[str, float]]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "path": self.path,
            "has_review": self.has_review,
            "review_passed": self.review_passed,
            "review_scores": self.review_scores,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpecSummary":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class TestState:
    """Current test state."""
    total_tests: int
    passing: int
    failing: int
    skipped: int
    last_run_at: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tests": self.total_tests,
            "passing": self.passing,
            "failing": self.failing,
            "skipped": self.skipped,
            "last_run_at": self.last_run_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestState":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class GitHubState:
    """GitHub state from gh CLI."""
    open_issues: int
    closed_issues_today: int
    open_prs: int
    pending_reviews: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_issues": self.open_issues,
            "closed_issues_today": self.closed_issues_today,
            "open_prs": self.open_prs,
            "pending_reviews": self.pending_reviews,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitHubState":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class InterruptedSession:
    """An interrupted session that needs attention."""
    session_id: str
    feature_id: str
    issue_number: int
    started_at: str
    last_checkpoint: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "feature_id": self.feature_id,
            "issue_number": self.issue_number,
            "started_at": self.started_at,
            "last_checkpoint": self.last_checkpoint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterruptedSession":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class RepoStateSnapshot:
    """Complete snapshot of repository state."""
    gathered_at: str
    git: GitState
    features: list[FeatureSummary]
    bugs: list[BugSummary]
    prds: list[PRDSummary]
    specs: list[SpecSummary]
    tests: TestState
    github: Optional[GitHubState]
    interrupted_sessions: list[InterruptedSession]
    total_cost_today: float
    total_cost_week: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "gathered_at": self.gathered_at,
            "git": self.git.to_dict(),
            "features": [f.to_dict() for f in self.features],
            "bugs": [b.to_dict() for b in self.bugs],
            "prds": [p.to_dict() for p in self.prds],
            "specs": [s.to_dict() for s in self.specs],
            "tests": self.tests.to_dict(),
            "github": self.github.to_dict() if self.github else None,
            "interrupted_sessions": [s.to_dict() for s in self.interrupted_sessions],
            "total_cost_today": self.total_cost_today,
            "total_cost_week": self.total_cost_week,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoStateSnapshot":
        """Create from dictionary."""
        data = data.copy()
        data["git"] = GitState.from_dict(data["git"])
        data["features"] = [FeatureSummary.from_dict(f) for f in data.get("features", [])]
        data["bugs"] = [BugSummary.from_dict(b) for b in data.get("bugs", [])]
        data["prds"] = [PRDSummary.from_dict(p) for p in data.get("prds", [])]
        data["specs"] = [SpecSummary.from_dict(s) for s in data.get("specs", [])]
        data["tests"] = TestState.from_dict(data["tests"])
        if data.get("github"):
            data["github"] = GitHubState.from_dict(data["github"])
        data["interrupted_sessions"] = [
            InterruptedSession.from_dict(s) for s in data.get("interrupted_sessions", [])
        ]
        return cls(**data)


@dataclass
class Recommendation:
    """A recommended action for today."""
    priority: Literal["P1", "P2", "P3"]
    task: str
    estimated_cost_usd: float
    estimated_minutes: int
    rationale: str
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None
    linked_spec: Optional[str] = None
    command: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "task": self.task,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_minutes": self.estimated_minutes,
            "rationale": self.rationale,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
            "linked_spec": self.linked_spec,
            "command": self.command,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recommendation":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AttentionItem:
    """An item that needs human attention."""
    type: str
    description: str
    urgency: Literal["high", "medium", "low"]
    action: str
    command: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "description": self.description,
            "urgency": self.urgency,
            "action": self.action,
            "command": self.command,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttentionItem":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class StandupReport:
    """Generated standup report."""
    date: str
    yesterday_comparison: dict[str, Any]
    repo_health: dict[str, Any]
    attention_items: list[AttentionItem]
    blockers: list[str]
    recommendations: list[Recommendation]
    state_snapshot: RepoStateSnapshot

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "yesterday_comparison": self.yesterday_comparison,
            "repo_health": self.repo_health,
            "attention_items": [a.to_dict() for a in self.attention_items],
            "blockers": self.blockers,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "state_snapshot": self.state_snapshot.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupReport":
        """Create from dictionary."""
        data = data.copy()
        data["attention_items"] = [AttentionItem.from_dict(a) for a in data.get("attention_items", [])]
        data["recommendations"] = [Recommendation.from_dict(r) for r in data.get("recommendations", [])]
        data["state_snapshot"] = RepoStateSnapshot.from_dict(data["state_snapshot"])
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