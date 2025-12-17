"""Data models for the Chief of Staff agent."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class GoalStatus(str, Enum):
    """Status of a daily goal."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class CheckpointTrigger(str, Enum):
    """Triggers for checkpoint events."""

    MANUAL = "manual"
    TIME_BASED = "time_based"
    GOAL_COMPLETED = "goal_completed"
    ERROR = "error"
    USER_INTERRUPT = "user_interrupt"
    PHASE_TRANSITION = "phase_transition"


@dataclass
class DailyGoal:
    """A goal for the day."""

    id: str
    description: str
    priority: int
    status: GoalStatus = GoalStatus.PENDING
    feature_id: Optional[str] = None
    bug_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "status": self.status.value,
            "feature_id": self.feature_id,
            "bug_id": self.bug_id,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyGoal":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            priority=data["priority"],
            status=GoalStatus(data.get("status", "pending")),
            feature_id=data.get("feature_id"),
            bug_id=data.get("bug_id"),
            notes=data.get("notes"),
        )


@dataclass
class Decision:
    """A decision made during work."""

    id: str
    description: str
    rationale: str
    timestamp: str
    context: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Decision":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            rationale=data["rationale"],
            timestamp=data["timestamp"],
            context=data.get("context"),
        )


@dataclass
class WorkLogEntry:
    """An entry in the work log."""

    timestamp: str
    action: str
    details: str
    goal_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "details": self.details,
            "goal_id": self.goal_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkLogEntry":
        """Deserialize from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            action=data["action"],
            details=data["details"],
            goal_id=data.get("goal_id"),
        )


@dataclass
class StandupSession:
    """A standup session with goals, decisions, and work log."""

    date: str
    goals: list[DailyGoal]
    decisions: list[Decision]
    work_log: list[WorkLogEntry]
    summary: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "date": self.date,
            "goals": [g.to_dict() for g in self.goals],
            "decisions": [d.to_dict() for d in self.decisions],
            "work_log": [e.to_dict() for e in self.work_log],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupSession":
        """Deserialize from dictionary."""
        return cls(
            date=data["date"],
            goals=[DailyGoal.from_dict(g) for g in data.get("goals", [])],
            decisions=[Decision.from_dict(d) for d in data.get("decisions", [])],
            work_log=[WorkLogEntry.from_dict(e) for e in data.get("work_log", [])],
            summary=data.get("summary"),
        )


@dataclass
class DailySummary:
    """Summary of a day's work."""

    date: str
    completed_goals: list[str]
    incomplete_goals: list[str]
    carryover_goals: list[str]
    key_decisions: list[str]
    blockers: list[str]
    notes: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "date": self.date,
            "completed_goals": self.completed_goals,
            "incomplete_goals": self.incomplete_goals,
            "carryover_goals": self.carryover_goals,
            "key_decisions": self.key_decisions,
            "blockers": self.blockers,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailySummary":
        """Deserialize from dictionary."""
        return cls(
            date=data["date"],
            completed_goals=data.get("completed_goals", []),
            incomplete_goals=data.get("incomplete_goals", []),
            carryover_goals=data.get("carryover_goals", []),
            key_decisions=data.get("key_decisions", []),
            blockers=data.get("blockers", []),
            notes=data.get("notes"),
        )


@dataclass
class DailyLog:
    """A daily log with entries and auto-initialized timestamp."""

    date: str
    entries: list[WorkLogEntry]
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "date": self.date,
            "entries": [e.to_dict() for e in self.entries],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyLog":
        """Deserialize from dictionary."""
        log = cls(
            date=data["date"],
            entries=[WorkLogEntry.from_dict(e) for e in data.get("entries", [])],
        )
        if "created_at" in data:
            log.created_at = data["created_at"]
        return log


@dataclass
class GitState:
    """Current git repository state."""

    branch: str
    commit_hash: str
    is_clean: bool
    uncommitted_files: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "branch": self.branch,
            "commit_hash": self.commit_hash,
            "is_clean": self.is_clean,
            "uncommitted_files": self.uncommitted_files,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitState":
        """Deserialize from dictionary."""
        return cls(
            branch=data["branch"],
            commit_hash=data["commit_hash"],
            is_clean=data["is_clean"],
            uncommitted_files=data.get("uncommitted_files", []),
        )


@dataclass
class FeatureSummary:
    """Summary of a feature's state."""

    id: str
    name: str
    phase: str
    progress: float
    total_issues: Optional[int] = None
    completed_issues: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "phase": self.phase,
            "progress": self.progress,
            "total_issues": self.total_issues,
            "completed_issues": self.completed_issues,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeatureSummary":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            phase=data["phase"],
            progress=data["progress"],
            total_issues=data.get("total_issues"),
            completed_issues=data.get("completed_issues"),
        )


@dataclass
class BugSummary:
    """Summary of a bug investigation."""

    id: str
    description: str
    phase: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "phase": self.phase,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BugSummary":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            description=data["description"],
            phase=data["phase"],
            severity=data["severity"],
        )


@dataclass
class PRDSummary:
    """Summary of a PRD."""

    id: str
    title: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PRDSummary":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            status=data["status"],
        )


@dataclass
class SpecSummary:
    """Summary of a spec."""

    id: str
    feature_id: str
    status: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "feature_id": self.feature_id,
            "status": self.status,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpecSummary":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            feature_id=data["feature_id"],
            status=data["status"],
            score=data["score"],
        )


@dataclass
class TestState:
    """State of the test suite."""

    total: int
    passed: int
    failed: int
    skipped: int
    last_run: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestState":
        """Deserialize from dictionary."""
        return cls(
            total=data["total"],
            passed=data["passed"],
            failed=data["failed"],
            skipped=data["skipped"],
            last_run=data["last_run"],
        )


@dataclass
class GitHubState:
    """State of GitHub repository."""

    open_prs: int
    open_issues: int
    pending_reviews: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "open_prs": self.open_prs,
            "open_issues": self.open_issues,
            "pending_reviews": self.pending_reviews,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitHubState":
        """Deserialize from dictionary."""
        return cls(
            open_prs=data["open_prs"],
            open_issues=data["open_issues"],
            pending_reviews=data.get("pending_reviews", []),
        )


@dataclass
class InterruptedSession:
    """An interrupted session that may need recovery."""

    session_id: str
    feature_id: str
    phase: str
    interrupted_at: str
    reason: str
    recovery_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "feature_id": self.feature_id,
            "phase": self.phase,
            "interrupted_at": self.interrupted_at,
            "reason": self.reason,
            "recovery_data": self.recovery_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterruptedSession":
        """Deserialize from dictionary."""
        return cls(
            session_id=data["session_id"],
            feature_id=data["feature_id"],
            phase=data["phase"],
            interrupted_at=data["interrupted_at"],
            reason=data["reason"],
            recovery_data=data.get("recovery_data"),
        )


@dataclass
class RepoStateSnapshot:
    """A snapshot of the entire repository state."""

    timestamp: str
    git: GitState
    features: list[FeatureSummary]
    bugs: list[BugSummary]
    prds: list[PRDSummary]
    specs: list[SpecSummary]
    tests: TestState
    github: GitHubState
    interrupted_sessions: list[InterruptedSession]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "git": self.git.to_dict(),
            "features": [f.to_dict() for f in self.features],
            "bugs": [b.to_dict() for b in self.bugs],
            "prds": [p.to_dict() for p in self.prds],
            "specs": [s.to_dict() for s in self.specs],
            "tests": self.tests.to_dict(),
            "github": self.github.to_dict(),
            "interrupted_sessions": [s.to_dict() for s in self.interrupted_sessions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RepoStateSnapshot":
        """Deserialize from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            git=GitState.from_dict(data["git"]),
            features=[FeatureSummary.from_dict(f) for f in data.get("features", [])],
            bugs=[BugSummary.from_dict(b) for b in data.get("bugs", [])],
            prds=[PRDSummary.from_dict(p) for p in data.get("prds", [])],
            specs=[SpecSummary.from_dict(s) for s in data.get("specs", [])],
            tests=TestState.from_dict(data["tests"]),
            github=GitHubState.from_dict(data["github"]),
            interrupted_sessions=[
                InterruptedSession.from_dict(s) for s in data.get("interrupted_sessions", [])
            ],
        )


@dataclass
class Recommendation:
    """A recommendation for action."""

    id: str
    action: str
    rationale: str
    priority: int
    feature_id: Optional[str] = None
    bug_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "rationale": self.rationale,
            "priority": self.priority,
            "feature_id": self.feature_id,
            "bug_id": self.bug_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recommendation":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            action=data["action"],
            rationale=data["rationale"],
            priority=data["priority"],
            feature_id=data.get("feature_id"),
            bug_id=data.get("bug_id"),
        )


@dataclass
class AttentionItem:
    """An item requiring attention."""

    id: str
    type: str
    message: str
    severity: str
    context: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "message": self.message,
            "severity": self.severity,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttentionItem":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            type=data["type"],
            message=data["message"],
            severity=data["severity"],
            context=data.get("context"),
        )


@dataclass
class StandupReport:
    """A complete standup report."""

    timestamp: str
    state_snapshot: RepoStateSnapshot
    recommendations: list[Recommendation]
    attention_items: list[AttentionItem]
    suggested_goals: list[DailyGoal]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "timestamp": self.timestamp,
            "state_snapshot": self.state_snapshot.to_dict(),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "attention_items": [a.to_dict() for a in self.attention_items],
            "suggested_goals": [g.to_dict() for g in self.suggested_goals],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StandupReport":
        """Deserialize from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            state_snapshot=RepoStateSnapshot.from_dict(data["state_snapshot"]),
            recommendations=[Recommendation.from_dict(r) for r in data.get("recommendations", [])],
            attention_items=[AttentionItem.from_dict(a) for a in data.get("attention_items", [])],
            suggested_goals=[DailyGoal.from_dict(g) for g in data.get("suggested_goals", [])],
        )


@dataclass
class CheckpointEvent:
    """A checkpoint event during autopilot."""

    id: str
    timestamp: str
    trigger: CheckpointTrigger
    summary: str
    goal_id: Optional[str] = None
    error_details: Optional[str] = None
    state_data: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "trigger": self.trigger.value,
            "summary": self.summary,
            "goal_id": self.goal_id,
            "error_details": self.error_details,
            "state_data": self.state_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointEvent":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            trigger=CheckpointTrigger(data["trigger"]),
            summary=data["summary"],
            goal_id=data.get("goal_id"),
            error_details=data.get("error_details"),
            state_data=data.get("state_data"),
        )


@dataclass
class AutopilotSession:
    """An autopilot session."""

    id: str
    started_at: str
    goals: list[DailyGoal]
    checkpoints: list[CheckpointEvent]
    work_log: list[WorkLogEntry]
    ended_at: Optional[str] = None
    status: Optional[str] = None
    final_summary: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "started_at": self.started_at,
            "goals": [g.to_dict() for g in self.goals],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "work_log": [e.to_dict() for e in self.work_log],
            "ended_at": self.ended_at,
            "status": self.status,
            "final_summary": self.final_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutopilotSession":
        """Deserialize from dictionary."""
        return cls(
            id=data["id"],
            started_at=data["started_at"],
            goals=[DailyGoal.from_dict(g) for g in data.get("goals", [])],
            checkpoints=[CheckpointEvent.from_dict(c) for c in data.get("checkpoints", [])],
            work_log=[WorkLogEntry.from_dict(e) for e in data.get("work_log", [])],
            ended_at=data.get("ended_at"),
            status=data.get("status"),
            final_summary=data.get("final_summary"),
        )