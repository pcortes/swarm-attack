"""
Data models for the Chief of Staff agent.

This module provides all data models for:
- Core state models: GoalStatus, CheckpointTrigger, DailyGoal, Decision, WorkLogEntry, etc.
- State snapshot models: GitState, FeatureSummary, BugSummary, PRDSummary, etc.
- Recommendation models: Recommendation, AttentionItem, StandupReport
- Autopilot models: CheckpointEvent, AutopilotSession
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional


# =============================================================================
# Enums
# =============================================================================


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


# =============================================================================
# Core State Models
# =============================================================================


@dataclass
class DailyGoal:
    """A single goal for the day."""

    id: str  # Unique identifier (e.g., "goal-001")
    content: str  # Goal description
    priority: Literal["P1", "P2", "P3"]  # Priority level
    status: GoalStatus = GoalStatus.PENDING
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    notes: str = ""
    linked_feature: Optional[str] = None  # Feature ID if applicable
    linked_bug: Optional[str] = None  # Bug ID if applicable
    linked_spec: Optional[str] = None  # Spec feature ID if applicable
    completed_at: Optional[str] = None  # ISO timestamp

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
        data["status"] = GoalStatus(data.get("status", "pending"))
        return cls(**data)


@dataclass
class Decision:
    """A decision made during the day."""

    timestamp: str  # ISO format
    type: str  # "approval", "priority", "checkpoint", "skip", etc.
    item: str  # What the decision is about
    decision: str  # The actual decision made
    rationale: str  # Why this decision was made
    human_override: bool = False  # Was this a human override of recommendation?
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

    timestamp: str  # ISO format
    action: str  # What was done
    result: str  # Outcome
    cost_usd: float = 0.0  # Cost of this action
    duration_seconds: int = 0  # Duration if applicable
    checkpoint: Optional[str] = None  # Checkpoint trigger if paused

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

    session_id: str  # Unique session ID (e.g., "cos-20251212-001")
    time: str  # ISO timestamp of standup
    yesterday_goals: list[DailyGoal] = field(default_factory=list)  # Goals from yesterday
    today_goals: list[DailyGoal] = field(default_factory=list)  # Goals set for today
    philip_notes: str = ""  # Notes from human
    recommendations_accepted: bool = False  # Did human accept recommendations?

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
        data["yesterday_goals"] = [
            DailyGoal.from_dict(g) for g in data.get("yesterday_goals", [])
        ]
        data["today_goals"] = [
            DailyGoal.from_dict(g) for g in data.get("today_goals", [])
        ]
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
        data["carryover_goals"] = [
            DailyGoal.from_dict(g) for g in data.get("carryover_goals", [])
        ]
        return cls(**data)


@dataclass
class DailyLog:
    """Complete daily log for a single day."""

    date: str  # YYYY-MM-DD format
    standups: list[StandupSession] = field(default_factory=list)
    work_log: list[WorkLogEntry] = field(default_factory=list)
    summary: Optional[DailySummary] = None
    created_at: str = ""  # ISO timestamp
    updated_at: str = ""  # ISO timestamp

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
        data["standups"] = [
            StandupSession.from_dict(s) for s in data.get("standups", [])
        ]
        data["work_log"] = [WorkLogEntry.from_dict(w) for w in data.get("work_log", [])]
        if data.get("summary"):
            data["summary"] = DailySummary.from_dict(data["summary"])
        return cls(**data)


# =============================================================================
# State Snapshot Models
# =============================================================================


@dataclass
class GitState:
    """Current git state."""

    branch: str
    is_clean: bool
    uncommitted_files: list[str] = field(default_factory=list)
    recent_commits: list[dict[str, str]] = field(
        default_factory=list
    )  # [{hash, message, author, date}]
    ahead_behind: tuple[int, int] = (0, 0)  # (ahead, behind) from remote

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
        if "ahead_behind" in data:
            data["ahead_behind"] = tuple(data["ahead_behind"])
        return cls(**data)


@dataclass
class FeatureSummary:
    """Summary of a feature's state."""

    feature_id: str
    phase: str  # FeaturePhase.name
    tasks_done: int
    tasks_total: int
    tasks_blocked: int
    cost_usd: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    phase: str  # BugPhase.value
    cost_usd: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    phase: str  # From frontmatter or inferred
    path: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    has_review: bool  # Whether spec-review.json exists
    review_passed: bool  # Whether review recommendation is "APPROVE"
    review_scores: Optional[dict[str, float]] = None  # Scores from review if present
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
class TestSuiteState:
    """Current test suite state."""

    total_tests: int
    passing: int
    failing: int
    skipped: int
    last_run_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_tests": self.total_tests,
            "passing": self.passing,
            "failing": self.failing,
            "skipped": self.skipped,
            "last_run_at": self.last_run_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestSuiteState":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class GitHubState:
    """GitHub state from gh CLI."""

    open_issues: int
    closed_issues_today: int
    open_prs: int
    pending_reviews: list[dict[str, Any]] = field(
        default_factory=list
    )  # PRs awaiting review

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    last_checkpoint: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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

    gathered_at: str  # ISO timestamp
    git: GitState
    features: list[FeatureSummary] = field(default_factory=list)
    bugs: list[BugSummary] = field(default_factory=list)
    prds: list[PRDSummary] = field(default_factory=list)
    specs: list[SpecSummary] = field(default_factory=list)  # Spec pipeline status
    tests: Optional[TestSuiteState] = None
    github: Optional[GitHubState] = None
    interrupted_sessions: list[InterruptedSession] = field(default_factory=list)
    total_cost_today: float = 0.0
    total_cost_week: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "gathered_at": self.gathered_at,
            "git": self.git.to_dict(),
            "features": [f.to_dict() for f in self.features],
            "bugs": [b.to_dict() for b in self.bugs],
            "prds": [p.to_dict() for p in self.prds],
            "specs": [s.to_dict() for s in self.specs],
            "tests": self.tests.to_dict() if self.tests else None,
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
        if data.get("tests"):
            data["tests"] = TestSuiteState.from_dict(data["tests"])
        if data.get("github"):
            data["github"] = GitHubState.from_dict(data["github"])
        data["interrupted_sessions"] = [
            InterruptedSession.from_dict(s) for s in data.get("interrupted_sessions", [])
        ]
        return cls(**data)


# =============================================================================
# Recommendation Models
# =============================================================================


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
    linked_spec: Optional[str] = None  # Spec feature ID if spec-related
    command: Optional[str] = None  # CLI command to execute

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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

    type: str  # "approval", "blocker", "new", "regression", "spec_review"
    description: str
    urgency: Literal["high", "medium", "low"]
    action: str  # Suggested action
    command: Optional[str] = None  # CLI command if applicable

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
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
    yesterday_comparison: dict[str, Any] = field(default_factory=dict)  # Goals vs actual
    repo_health: dict[str, Any] = field(default_factory=dict)  # Summary of repo state
    attention_items: list[AttentionItem] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    state_snapshot: Optional[RepoStateSnapshot] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "date": self.date,
            "yesterday_comparison": self.yesterday_comparison,
            "repo_health": self.repo_health,
            "attention_items": [a.to_dict() for a in self.attention_items],
            "blockers": self.blockers,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "state_snapshot": self.state_snapshot.to_dict() if self.state_snapshot else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupReport":
        """Create from dictionary."""
        data = data.copy()
        data["attention_items"] = [
            AttentionItem.from_dict(a) for a in data.get("attention_items", [])
        ]
        data["recommendations"] = [
            Recommendation.from_dict(r) for r in data.get("recommendations", [])
        ]
        if data.get("state_snapshot"):
            data["state_snapshot"] = RepoStateSnapshot.from_dict(data["state_snapshot"])
        return cls(**data)


# =============================================================================
# Autopilot Models
# =============================================================================


@dataclass
class CheckpointEvent:
    """A checkpoint during autopilot execution."""

    timestamp: str
    trigger: CheckpointTrigger
    context: dict[str, Any] = field(default_factory=dict)
    action_taken: str = ""  # "paused", "continued", "aborted"
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
    stop_trigger: Optional[CheckpointTrigger] = None  # --until trigger
    goals: list[DailyGoal] = field(default_factory=list)
    current_goal_index: int = 0  # Index of goal being worked on
    checkpoints: list[CheckpointEvent] = field(default_factory=list)
    cost_spent_usd: float = 0.0
    duration_seconds: int = 0
    status: str = "running"  # "running", "completed", "paused", "aborted"
    pause_reason: Optional[str] = None  # Reason for pause if paused
    ended_at: Optional[str] = None
    last_persisted_at: Optional[str] = None  # When session was last saved

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
        data["checkpoints"] = [
            CheckpointEvent.from_dict(c) for c in data.get("checkpoints", [])
        ]
        return cls(**data)
