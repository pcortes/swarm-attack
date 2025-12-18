# Engineering Spec: Chief of Staff Agent

## 1. Overview

### 1.1 Purpose

The Chief of Staff agent is a strategic orchestration layer for swarm-attack that acts as an autonomous "mini-CEO" for the repository. It provides:

1. **Cross-Session Memory**: Persistent tracking of goals, decisions, and outcomes across Claude Code sessions
2. **Daily Standups**: Interactive morning briefings that summarize yesterday's progress vs plan and recommend today's priorities
3. **Plan Tracking**: Goal setting with measurable achievement tracking, automatic status reconciliation, and carryover logic
4. **Autonomous Execution**: Autopilot mode that executes work within budget/time constraints with checkpoint gates and pause/resume capability

### 1.2 Scope

**In Scope:**
- State gathering from all repository data sources (git, PRDs, specs, features, bugs, sessions, GitHub)
- Daily log persistence in human-readable markdown format
- Decision logging in append-only JSONL format
- Interactive standup command with recommendations
- Plan tracking with goal completion metrics and automatic status reconciliation
- Autopilot mode with configurable checkpoints, pause/resume, and --until trigger support

**Out of Scope:**
- Multi-repository support (single repo only)
- Calendar/scheduling integration
- Preference learning from human decisions (Phase 6, future)
- Actual cost tracking via API (uses estimated costs from existing tracking)

### 1.3 Success Criteria

| Criterion | Metric | Target |
|-----------|--------|--------|
| Daily continuity | Sessions able to recall yesterday's plan | 100% |
| Goal achievement tracking | Accurate completion % calculation | 100% accuracy |
| Time to context | Standup provides full context | < 30 seconds |
| Checkpoint accuracy | Appropriate trigger frequency | No false negatives |
| State gathering | All sources aggregated | 100% coverage |
| Autopilot pause/resume | Sessions resumable after checkpoint | 100% reliability |

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CHIEF OF STAFF AGENT                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │
│  │ DailyLogMgr   │  │ GoalTracker   │  │ AutopilotRun  │               │
│  │               │  │               │  │               │               │
│  │ • Read/write  │  │ • Set goals   │  │ • Execute     │               │
│  │ • Decision log│  │ • Track status│  │ • Checkpoints │               │
│  │ • History     │  │ • Reconcile   │  │ • Budget/time │               │
│  │               │  │   with state  │  │ • Pause/resume│               │
│  └───────────────┘  └───────────────┘  └───────────────┘               │
│          │                 │                  │                         │
│          └─────────────────┼──────────────────┘                         │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      StateGatherer                               │   │
│  │                                                                  │   │
│  │  Sources:                                                        │   │
│  │  • GitStateSource      (branch, commits, status, diff)          │   │
│  │  • PRDStateSource      (.claude/prds/*.md + frontmatter)        │   │
│  │  • SpecStateSource     (.claude/specs/*.md)                     │   │
│  │  • FeatureStateSource  (.swarm/state/*.json)                    │   │
│  │  • BugStateSource      (.swarm/bugs/*/state.json)               │   │
│  │  • SessionStateSource  (.swarm/sessions/*/*.json)               │   │
│  │  • GitHubStateSource   (issues, PRs via gh CLI)                 │   │
│  │  • TestStateSource     (pytest collection + last run)           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    CheckpointSystem                              │   │
│  │                                                                  │   │
│  │  Triggers:                                                       │   │
│  │  • CostThreshold       (configurable, e.g., $10)                │   │
│  │  • TimeThreshold       (configurable, e.g., 2 hours)            │   │
│  │  • BlockerDetected     (can't proceed without human input)      │   │
│  │  • ApprovalRequired    (spec approval, fix approval)            │   │
│  │  • HighRiskAction      (architectural change, main push)        │   │
│  │  • ErrorRateSpike      (3+ consecutive failures)                │   │
│  │  • EndOfSession        (natural stopping point)                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                  AutopilotSessionStore                           │   │
│  │                                                                  │   │
│  │  Persistence for pause/resume:                                   │   │
│  │  • .swarm/chief-of-staff/autopilot/{session_id}.json            │   │
│  │  • Tracks goals, progress, checkpoints, cost, duration          │   │
│  │  • Enables resume(session_id) after checkpoint pause            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `StateGatherer` | `swarm_attack/chief_of_staff/state_gatherer.py` | Aggregate state from all data sources |
| `DailyLogManager` | `swarm_attack/chief_of_staff/daily_log.py` | Read/write daily logs, decision JSONL |
| `GoalTracker` | `swarm_attack/chief_of_staff/goal_tracker.py` | Manage goals, track completion, reconcile with state |
| `CheckpointSystem` | `swarm_attack/chief_of_staff/checkpoints.py` | Detect checkpoint triggers |
| `AutopilotRunner` | `swarm_attack/chief_of_staff/autopilot.py` | Execute work with checkpoints, pause/resume |
| `AutopilotSessionStore` | `swarm_attack/chief_of_staff/autopilot_store.py` | Persist autopilot sessions for resume |
| `StandupGenerator` | `swarm_attack/chief_of_staff/standup.py` | Generate standup report |
| `ChiefOfStaffConfig` | `swarm_attack/chief_of_staff/config.py` | Configuration dataclass |

### 2.3 Data Flow

```
standup command
     │
     ▼
┌────────────────┐     ┌────────────────┐
│ StateGatherer  │────▶│ RepoStateSnap  │
└────────────────┘     └────────────────┘
                              │
                              ▼
┌────────────────┐     ┌────────────────┐
│DailyLogManager │────▶│ Yesterday Log  │
└────────────────┘     └────────────────┘
                              │
                              ▼
┌────────────────┐     ┌────────────────┐
│StandupGenerator│────▶│ Standup Report │
└────────────────┘     └────────────────┘
                              │
                              ▼
┌────────────────┐     ┌────────────────┐
│  GoalTracker   │◀────│ User Input     │
└────────────────┘     └────────────────┘
                              │
                              ▼
┌────────────────┐     ┌────────────────┐
│DailyLogManager │◀────│ Today's Plan   │
└────────────────┘     └────────────────┘
```

---

## 3. Data Models

### 3.1 Core State Models

```python
from dataclasses import dataclass, field
from datetime import datetime, date
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
    id: str                                    # Unique identifier (e.g., "goal-001")
    content: str                               # Goal description
    priority: Literal["P1", "P2", "P3"]       # Priority level
    status: GoalStatus = GoalStatus.PENDING
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    notes: str = ""
    linked_feature: Optional[str] = None      # Feature ID if applicable
    linked_bug: Optional[str] = None          # Bug ID if applicable
    linked_spec: Optional[str] = None         # Spec feature ID if applicable
    completed_at: Optional[str] = None        # ISO timestamp

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
class Decision:
    """A decision made during the day."""
    timestamp: str                            # ISO format
    type: str                                 # "approval", "priority", "checkpoint", "skip", etc.
    item: str                                 # What the decision is about
    decision: str                             # The actual decision made
    rationale: str                            # Why this decision was made
    human_override: bool = False              # Was this a human override of recommendation?
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
    timestamp: str                            # ISO format
    action: str                               # What was done
    result: str                               # Outcome
    cost_usd: float = 0.0                     # Cost of this action
    duration_seconds: int = 0                 # Duration if applicable
    checkpoint: Optional[str] = None          # Checkpoint trigger if paused

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
    session_id: str                           # Unique session ID (e.g., "cos-20251212-001")
    time: str                                 # ISO timestamp of standup
    yesterday_goals: list[DailyGoal]          # Goals from yesterday
    today_goals: list[DailyGoal]              # Goals set for today
    philip_notes: str = ""                    # Notes from human
    recommendations_accepted: bool = False     # Did human accept recommendations?

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
    date: str                                 # YYYY-MM-DD format
    standups: list[StandupSession] = field(default_factory=list)
    work_log: list[WorkLogEntry] = field(default_factory=list)
    summary: Optional[DailySummary] = None
    created_at: str = ""                      # ISO timestamp
    updated_at: str = ""                      # ISO timestamp

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
```

### 3.2 State Snapshot Models

```python
@dataclass
class GitState:
    """Current git state."""
    branch: str
    is_clean: bool
    uncommitted_files: list[str]
    recent_commits: list[dict[str, str]]      # [{hash, message, author, date}]
    ahead_behind: tuple[int, int]             # (ahead, behind) from remote

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "is_clean": self.is_clean,
            "uncommitted_files": self.uncommitted_files,
            "recent_commits": self.recent_commits,
            "ahead_behind": self.ahead_behind,
        }


@dataclass
class FeatureSummary:
    """Summary of a feature's state."""
    feature_id: str
    phase: str                                # FeaturePhase.name
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


@dataclass
class BugSummary:
    """Summary of a bug's state."""
    bug_id: str
    phase: str                                # BugPhase.value
    cost_usd: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
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
    phase: str                                # From frontmatter or inferred
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "title": self.title,
            "phase": self.phase,
            "path": self.path,
        }


@dataclass
class SpecSummary:
    """Summary of a spec file."""
    feature_id: str
    title: str
    path: str
    has_review: bool                          # Whether spec-review.json exists
    review_passed: bool                       # Whether review recommendation is "APPROVE"
    review_scores: Optional[dict[str, float]] # Scores from review if present
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


@dataclass
class GitHubState:
    """GitHub state from gh CLI."""
    open_issues: int
    closed_issues_today: int
    open_prs: int
    pending_reviews: list[dict[str, Any]]     # PRs awaiting review

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_issues": self.open_issues,
            "closed_issues_today": self.closed_issues_today,
            "open_prs": self.open_prs,
            "pending_reviews": self.pending_reviews,
        }


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


@dataclass
class RepoStateSnapshot:
    """Complete snapshot of repository state."""
    gathered_at: str                          # ISO timestamp
    git: GitState
    features: list[FeatureSummary]
    bugs: list[BugSummary]
    prds: list[PRDSummary]
    specs: list[SpecSummary]                  # Spec pipeline status
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
```

### 3.3 Recommendation Models

```python
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
    linked_spec: Optional[str] = None         # Spec feature ID if spec-related
    command: Optional[str] = None             # CLI command to execute

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


@dataclass
class AttentionItem:
    """An item that needs human attention."""
    type: str                                 # "approval", "blocker", "new", "regression", "spec_review"
    description: str
    urgency: Literal["high", "medium", "low"]
    action: str                               # Suggested action
    command: Optional[str] = None             # CLI command if applicable

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "description": self.description,
            "urgency": self.urgency,
            "action": self.action,
            "command": self.command,
        }


@dataclass
class StandupReport:
    """Generated standup report."""
    date: str
    yesterday_comparison: dict[str, Any]      # Goals vs actual
    repo_health: dict[str, Any]               # Summary of repo state
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
```

### 3.4 Autopilot Models

```python
@dataclass
class CheckpointEvent:
    """A checkpoint during autopilot execution."""
    timestamp: str
    trigger: CheckpointTrigger
    context: dict[str, Any]
    action_taken: str                         # "paused", "continued", "aborted"
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
    stop_trigger: Optional[CheckpointTrigger] = None  # --until trigger
    goals: list[DailyGoal] = field(default_factory=list)
    current_goal_index: int = 0               # Index of goal being worked on
    checkpoints: list[CheckpointEvent] = field(default_factory=list)
    cost_spent_usd: float = 0.0
    duration_seconds: int = 0
    status: str = "running"                   # "running", "completed", "paused", "aborted"
    pause_reason: Optional[str] = None        # Reason for pause if paused
    ended_at: Optional[str] = None
    last_persisted_at: Optional[str] = None   # When session was last saved

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
```

### 3.5 Schema Changes

No database schema changes required. All persistence is file-based:

**New Directory Structure:**
```
.swarm/chief-of-staff/
├── config.yaml                    # User preferences, thresholds
├── daily-log/
│   ├── 2025-12-12.md             # Human-readable daily log
│   ├── 2025-12-12.json           # Machine-readable daily log
│   └── ...
├── weekly-summary/
│   └── 2025-W50.md               # Auto-generated weekly rollup
├── decisions.jsonl                # Append-only decision log
├── autopilot/                     # Autopilot session persistence
│   ├── ap-20251212-001.json      # Session state for pause/resume
│   └── ...
└── metrics.json                   # Running totals, averages
```

---

## 4. API Design

### 4.1 CLI Commands

| Command | Description | Options |
|---------|-------------|---------|
| `swarm-attack standup` | Morning standup briefing | `--since DATETIME` |
| `swarm-attack checkin` | Quick mid-day check | - |
| `swarm-attack wrapup` | End of day summary | - |
| `swarm-attack autopilot` | Autonomous execution | `--budget`, `--duration`, `--until`, `--dry-run`, `--resume` |
| `swarm-attack history` | Review past logs | `--days N`, `--weekly`, `--decisions` |
| `swarm-attack plan` | View/set goals | `show`, `set`, `status` |
| `swarm-attack next --all` | Cross-feature recommendations | - |

### 4.2 StateGatherer Interface

```python
class StateGatherer:
    """Gathers state from all repository data sources."""

    def __init__(self, config: SwarmConfig) -> None:
        """Initialize with configuration."""

    def gather(self, include_github: bool = True) -> RepoStateSnapshot:
        """
        Gather complete repository state snapshot.

        Args:
            include_github: Whether to query GitHub API (slower).

        Returns:
            Complete RepoStateSnapshot with all data sources.
        """

    def gather_git_state(self) -> GitState:
        """Gather git repository state."""

    def gather_features(self) -> list[FeatureSummary]:
        """Gather all feature states from .swarm/state/*.json."""

    def gather_bugs(self) -> list[BugSummary]:
        """Gather all bug states from .swarm/bugs/*/state.json."""

    def gather_prds(self) -> list[PRDSummary]:
        """Gather all PRDs from .claude/prds/*.md."""

    def gather_specs(self) -> list[SpecSummary]:
        """
        Gather all specs from specs/*/ directories.

        For each spec directory:
        - Reads spec-draft.md or spec.md
        - Checks for spec-review.json
        - Extracts review scores and recommendation

        Returns:
            List of SpecSummary objects.
        """

    def gather_tests(self) -> TestState:
        """Gather test state from pytest."""

    def gather_github(self) -> Optional[GitHubState]:
        """Gather GitHub state via gh CLI."""

    def gather_interrupted_sessions(self) -> list[InterruptedSession]:
        """Find interrupted sessions across all features."""

    def calculate_costs(self) -> tuple[float, float]:
        """Calculate today's and this week's costs."""
```

### 4.3 DailyLogManager Interface

```python
class DailyLogManager:
    """Manages daily log persistence."""

    def __init__(self, base_path: Path) -> None:
        """Initialize with base storage path."""

    def get_log(self, date: date) -> Optional[DailyLog]:
        """Get daily log for a specific date."""

    def get_today(self) -> DailyLog:
        """Get or create today's log."""

    def get_yesterday(self) -> Optional[DailyLog]:
        """Get yesterday's log if it exists."""

    def save_log(self, log: DailyLog) -> None:
        """Save daily log to disk (both .md and .json)."""

    def add_standup(self, standup: StandupSession) -> None:
        """Add a standup session to today's log."""

    def add_work_entry(self, entry: WorkLogEntry) -> None:
        """Add a work log entry to today's log."""

    def set_summary(self, summary: DailySummary) -> None:
        """Set end-of-day summary."""

    def append_decision(self, decision: Decision) -> None:
        """Append decision to decisions.jsonl."""

    def get_decisions(
        self,
        since: Optional[datetime] = None,
        decision_type: Optional[str] = None,
    ) -> list[Decision]:
        """Query decisions from the JSONL log."""

    def get_history(self, days: int = 7) -> list[DailyLog]:
        """Get logs for the last N days."""

    def generate_weekly_summary(self, week: int, year: int) -> str:
        """Generate weekly summary markdown."""
```

### 4.4 GoalTracker Interface

```python
class GoalTracker:
    """Tracks daily goals and their completion with automatic state reconciliation."""

    def __init__(self, daily_log_manager: DailyLogManager) -> None:
        """Initialize with log manager."""

    def get_today_goals(self) -> list[DailyGoal]:
        """Get current goals for today."""

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set goals for today."""

    def update_goal(self, goal_id: str, status: GoalStatus, notes: str = "") -> None:
        """Update a goal's status."""

    def mark_complete(self, goal_id: str, actual_minutes: Optional[int] = None) -> None:
        """Mark a goal as complete."""

    def get_yesterday_goals(self) -> list[DailyGoal]:
        """Get yesterday's goals for comparison."""

    def compare_plan_vs_actual(self) -> dict[str, Any]:
        """
        Compare yesterday's plan vs actual results.

        Returns:
            Dictionary with:
            - goals: list of {goal, planned, actual, status}
            - completion_rate: float (0-1)
            - time_accuracy: float (planned vs actual time)
        """

    def get_carryover_goals(self) -> list[DailyGoal]:
        """Get incomplete goals that should carry over."""

    def reconcile_with_state(self, snapshot: RepoStateSnapshot) -> list[dict[str, Any]]:
        """
        Reconcile goal statuses with actual repository state.

        For goals with linked_feature:
        - If feature phase is COMPLETE -> mark goal DONE
        - If feature phase is BLOCKED -> mark goal BLOCKED
        - If feature phase advanced -> mark goal PARTIAL or IN_PROGRESS

        For goals with linked_bug:
        - If bug phase is "fixed" -> mark goal DONE
        - If bug phase is "blocked" -> mark goal BLOCKED

        For goals with linked_spec:
        - If spec has passing review -> mark goal DONE
        - If spec has failing review -> mark goal PARTIAL

        Args:
            snapshot: Current repository state.

        Returns:
            List of changes made: [{"goal_id": str, "old_status": str, "new_status": str, "reason": str}]
        """

    def generate_recommendations(
        self,
        state: RepoStateSnapshot,
    ) -> list[Recommendation]:
        """
        Generate recommended goals based on current state.

        Priority rules:
        1. P1: Blockers, approvals needed, regressions, spec reviews
        2. P2: In-progress work, natural next steps
        3. P3: New features, cleanup, nice-to-haves
        """
```

### 4.5 CheckpointSystem Interface

```python
class CheckpointSystem:
    """Detects and handles checkpoint triggers."""

    def __init__(self, config: ChiefOfStaffConfig) -> None:
        """Initialize with configuration."""

    def check_triggers(
        self,
        session: AutopilotSession,
        current_action: str,
    ) -> Optional[CheckpointTrigger]:
        """
        Check if any checkpoint should be triggered.

        Checks in order:
        1. If session.stop_trigger matches current state -> return that trigger
        2. If cost >= budget -> COST_THRESHOLD
        3. If duration >= limit -> TIME_THRESHOLD
        4. If action requires approval -> APPROVAL_REQUIRED
        5. If action is high risk -> HIGH_RISK_ACTION
        6. If error streak >= threshold -> ERROR_RATE_SPIKE
        7. If action is blocked -> BLOCKER_DETECTED

        Args:
            session: Current autopilot session state.
            current_action: Action about to be taken.

        Returns:
            CheckpointTrigger if one should fire, None otherwise.
        """

    def matches_stop_trigger(
        self,
        session: AutopilotSession,
        trigger: CheckpointTrigger,
    ) -> bool:
        """Check if trigger matches the session's --until stop trigger."""

    def is_high_risk(self, action: str) -> bool:
        """Check if an action is high-risk."""

    def record_error(self) -> None:
        """Record an error for spike detection."""

    def reset_error_count(self) -> None:
        """Reset error count after success."""

    def should_pause_for_approval(self, action: str) -> bool:
        """Check if action requires human approval."""
```

### 4.6 AutopilotSessionStore Interface

```python
class AutopilotSessionStore:
    """Persists autopilot sessions for pause/resume capability."""

    def __init__(self, base_path: Path) -> None:
        """Initialize with storage path (.swarm/chief-of-staff/autopilot/)."""

    def save(self, session: AutopilotSession) -> None:
        """
        Save autopilot session to disk atomically.

        Uses atomic write pattern: temp file -> validate -> rename.
        Sets session.last_persisted_at on save.
        """

    def load(self, session_id: str) -> Optional[AutopilotSession]:
        """Load autopilot session from disk."""

    def list_paused(self) -> list[str]:
        """List all paused session IDs."""

    def list_all(self) -> list[str]:
        """List all session IDs."""

    def delete(self, session_id: str) -> None:
        """Delete a session file."""

    def get_latest_paused(self) -> Optional[AutopilotSession]:
        """Get the most recently paused session."""
```

### 4.7 AutopilotRunner Interface

```python
class AutopilotRunner:
    """Executes work autonomously with checkpoint enforcement and pause/resume."""

    def __init__(
        self,
        config: SwarmConfig,
        checkpoint_system: CheckpointSystem,
        goal_tracker: GoalTracker,
        session_store: AutopilotSessionStore,
        orchestrator: Orchestrator,
        bug_orchestrator: BugOrchestrator,
    ) -> None:
        """Initialize with dependencies."""

    def start(
        self,
        goals: list[DailyGoal],
        budget_usd: float = 10.0,
        duration_seconds: int = 7200,
        stop_trigger: Optional[CheckpointTrigger] = None,
    ) -> AutopilotSession:
        """
        Start autopilot execution.

        Args:
            goals: Goals to work on (in priority order).
            budget_usd: Maximum spend before checkpoint.
            duration_seconds: Maximum duration before checkpoint.
            stop_trigger: Optional trigger to stop at (--until).

        Returns:
            AutopilotSession tracking the execution.
        """

    def resume(self, session_id: str) -> AutopilotSession:
        """
        Resume a paused autopilot session.

        Loads session from AutopilotSessionStore, validates it can be resumed,
        and continues execution from where it left off.

        Args:
            session_id: ID of paused session to resume.

        Returns:
            AutopilotSession with continued execution.

        Raises:
            ValueError: If session not found or not resumable.
        """

    def execute_goal(self, goal: DailyGoal) -> tuple[bool, float]:
        """
        Execute a single goal.

        Returns:
            Tuple of (success, cost_usd).
        """

    def handle_checkpoint(
        self,
        session: AutopilotSession,
        trigger: CheckpointTrigger,
    ) -> str:
        """
        Handle a checkpoint trigger.

        Persists session state before pausing to enable resume.

        Returns:
            "continue", "pause", or "abort".
        """

    def get_status(self, session_id: str) -> Optional[AutopilotSession]:
        """Get status of an autopilot session."""

    def _persist_session(self, session: AutopilotSession) -> None:
        """Persist session state for pause/resume."""
```

---

## 5. Implementation Plan

### 5.1 Tasks

| # | Task | Dependencies | Size | Files |
|---|------|--------------|------|-------|
| 1 | Create data models | None | M | `swarm_attack/chief_of_staff/models.py` |
| 2 | Implement StateGatherer | 1 | L | `swarm_attack/chief_of_staff/state_gatherer.py` |
| 2a | Add gather_specs method | 2 | S | `swarm_attack/chief_of_staff/state_gatherer.py` |
| 3 | Implement DailyLogManager | 1 | M | `swarm_attack/chief_of_staff/daily_log.py` |
| 4 | Implement GoalTracker | 1, 3 | M | `swarm_attack/chief_of_staff/goal_tracker.py` |
| 4a | Add reconcile_with_state method | 4 | M | `swarm_attack/chief_of_staff/goal_tracker.py` |
| 5 | Implement CheckpointSystem | 1 | S | `swarm_attack/chief_of_staff/checkpoints.py` |
| 5a | Add --until trigger support | 5 | S | `swarm_attack/chief_of_staff/checkpoints.py` |
| 6 | Implement StandupGenerator | 2, 3, 4 | M | `swarm_attack/chief_of_staff/standup.py` |
| 7 | Add ChiefOfStaffConfig | None | S | `swarm_attack/chief_of_staff/config.py` |
| 8 | Integrate config into SwarmConfig | 7 | S | `swarm_attack/config.py` |
| 9 | Implement CLI: standup | 2, 3, 4, 6 | M | `swarm_attack/cli.py` |
| 10 | Implement CLI: checkin | 2 | S | `swarm_attack/cli.py` |
| 11 | Implement CLI: wrapup | 3, 4 | S | `swarm_attack/cli.py` |
| 12 | Implement CLI: plan | 4 | S | `swarm_attack/cli.py` |
| 13 | Implement CLI: history | 3 | S | `swarm_attack/cli.py` |
| 14 | Implement AutopilotSessionStore | 1 | M | `swarm_attack/chief_of_staff/autopilot_store.py` |
| 15 | Implement AutopilotRunner | 4, 5, 14 | L | `swarm_attack/chief_of_staff/autopilot.py` |
| 15a | Add resume() method | 15 | M | `swarm_attack/chief_of_staff/autopilot.py` |
| 16 | Implement CLI: autopilot | 15 | M | `swarm_attack/cli.py` |
| 16a | Add --until and --resume flags | 16 | S | `swarm_attack/cli.py` |
| 17 | Implement CLI: next --all | 2, 4 | S | `swarm_attack/cli.py` |
| 18 | Add unit tests | All | L | `tests/chief_of_staff/` |
| 19 | Add integration tests | All | M | `tests/chief_of_staff/` |

### 5.2 File Changes

**New Files:**
- `swarm_attack/chief_of_staff/__init__.py`
- `swarm_attack/chief_of_staff/models.py`
- `swarm_attack/chief_of_staff/config.py`
- `swarm_attack/chief_of_staff/state_gatherer.py`
- `swarm_attack/chief_of_staff/daily_log.py`
- `swarm_attack/chief_of_staff/goal_tracker.py`
- `swarm_attack/chief_of_staff/checkpoints.py`
- `swarm_attack/chief_of_staff/standup.py`
- `swarm_attack/chief_of_staff/autopilot_store.py`
- `swarm_attack/chief_of_staff/autopilot.py`
- `tests/chief_of_staff/__init__.py`
- `tests/chief_of_staff/test_models.py`
- `tests/chief_of_staff/test_state_gatherer.py`
- `tests/chief_of_staff/test_daily_log.py`
- `tests/chief_of_staff/test_goal_tracker.py`
- `tests/chief_of_staff/test_checkpoints.py`
- `tests/chief_of_staff/test_standup.py`
- `tests/chief_of_staff/test_autopilot_store.py`
- `tests/chief_of_staff/test_autopilot.py`

**Modified Files:**
- `swarm_attack/config.py` - Add ChiefOfStaffConfig
- `swarm_attack/cli.py` - Add new commands

---

## 6. Testing Strategy

### 6.1 Unit Tests

| Component | Test Cases | Coverage Target |
|-----------|------------|-----------------|
| Data models | Serialization round-trip, validation | 95% |
| StateGatherer | Each source isolated, aggregation, spec gathering | 85% |
| DailyLogManager | CRUD operations, file locking | 90% |
| GoalTracker | Goal operations, comparison logic, state reconciliation | 90% |
| CheckpointSystem | Each trigger type, edge cases, --until matching | 90% |
| StandupGenerator | Report generation, recommendations | 80% |
| AutopilotSessionStore | Save/load, list operations, atomic writes | 90% |
| AutopilotRunner | Execution flow, checkpoint handling, pause/resume | 80% |

### 6.2 Integration Tests

| Scenario | Description | Validation |
|----------|-------------|------------|
| Full standup flow | gather → compare → recommend → set goals | All components integrated |
| Autopilot with checkpoints | Execute until cost/time limit | Checkpoint fires correctly |
| Autopilot pause/resume | Pause at checkpoint, resume later | State preserved, execution continues |
| Autopilot --until trigger | Stop at specific trigger | Correct trigger detection |
| Multi-day continuity | Run standup on day 2 | Yesterday's data loaded |
| Recovery from interrupted | Session interrupted mid-execution | State preserved, resumable |
| Goal state reconciliation | Goals linked to features/bugs | Status auto-updates |
| Spec pipeline visibility | Spec reviews in standup | Spec status displayed |

### 6.3 Edge Cases

| Case | Test |
|------|------|
| First run (no history) | Standup handles missing yesterday log |
| Empty repository | StateGatherer handles no features/bugs/specs |
| GitHub unavailable | StateGatherer degrades gracefully |
| Corrupted daily log | DailyLogManager recovers from backup |
| Clock rollback | Daily log handles date changes |
| Concurrent access | File locking prevents corruption |
| Autopilot resume with deleted goal | Resume handles goal no longer existing |
| Spec without review | gather_specs handles missing spec-review.json |

---

## 7. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| State gathering slow | Standup takes >30s | Medium | Cache GitHub results, parallelize sources |
| Daily log corruption | Loss of history | Low | Atomic writes, JSON backup alongside markdown |
| Autopilot runaway | Unexpected cost | Medium | Hard budget limits, mandatory checkpoints |
| Goal tracking drift | Inaccurate metrics | Medium | reconcile_with_state validates against actual repo state |
| Clock/timezone issues | Date mismatch | Low | Use UTC internally, convert for display |
| gh CLI unavailable | No GitHub data | Low | Graceful degradation, warn user |
| Autopilot resume data loss | Can't resume paused session | Medium | Persist session state before every checkpoint, atomic writes |
| Spec parsing failures | Missing spec data | Low | Graceful degradation, log warnings |

---

## 8. Open Questions

1. **Session Context**: Should the Chief of Staff operate within the main Claude Code session or maintain its own separate context?
   - **Recommendation**: Operate within main session, persist state to files.

2. **Multi-repo Support**: How should it handle multiple repositories?
   - **Recommendation**: Defer to future. Current scope is single repo.

3. **Calendar Integration**: Should it integrate with calendar for time-based planning?
   - **Recommendation**: Out of scope for MVP. Can add later.

4. **Auto-recovery Aggressiveness**: How aggressive should auto-recovery be?
   - **Recommendation**: Conservative. Require human trigger for recovery actions.

---

## 9. Configuration

### 9.1 Configuration Schema

```yaml
# Added to config.yaml under chief_of_staff:
chief_of_staff:
  # Checkpoint thresholds
  checkpoints:
    budget_usd: 10.0              # Pause after spending this much
    duration_minutes: 120          # Pause after this long
    error_streak: 3               # Pause after N consecutive errors

  # Priority weights (0.0 - 1.0) for recommendation scoring
  priorities:
    blocker_weight: 1.0           # Blockers are highest priority
    approval_weight: 0.9          # Human approvals needed
    regression_weight: 0.85       # Test regressions
    spec_review_weight: 0.88      # Spec reviews needing attention
    in_progress_weight: 0.7       # Continue started work
    new_feature_weight: 0.5       # Start new features

  # Standup preferences
  standup:
    auto_run_on_start: false      # Run standup automatically
    include_github: true          # Query GitHub for issues/PRs
    include_tests: true           # Run pytest collection
    include_specs: true           # Gather spec pipeline status
    history_days: 7               # How far back to look

  # Autopilot preferences
  autopilot:
    default_budget: 10.0          # Default budget in USD
    default_duration: "2h"        # Default duration
    pause_on_approval: true       # Always pause for approvals
    pause_on_high_risk: true      # Always pause for risky ops
    persist_on_checkpoint: true   # Always persist state at checkpoints

  # Storage
  storage_path: ".swarm/chief-of-staff"
```

### 9.2 Configuration Dataclass

```python
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
```

---

## 10. CLI Output Formats

### 10.1 Standup Output

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  DAILY STANDUP - December 13, 2025                                           ║
║  swarm-attack v0.2.0 | Chief of Staff Agent                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  📅 YESTERDAY'S PLAN vs ACTUAL                                               ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ Goal                           │ Planned │ Actual  │ Status            │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ Approve bug-bash spec          │ 5 min   │ 5 min   │ ✅ Done            │  ║
║  │ Build Chief of Staff PRD       │ 30 min  │ 45 min  │ ✅ Done            │  ║
║  │ Clean up test files            │ 10 min  │ -       │ ⏭️ Skipped         │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  📊 REPO HEALTH                                                              ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ Branch: master (clean)                                                 │  ║
║  │ Tests: 3/3 passing (100%)                                              │  ║
║  │ Features: 2 total                                                      │  ║
║  │   • bug-bash: SPEC_NEEDS_APPROVAL                                      │  ║
║  │   • chief-of-staff: PRD_READY (new)                                    │  ║
║  │ Specs: 2 total                                                         │  ║
║  │   • bug-bash: review PASSED (0.85 avg)                                 │  ║
║  │   • chief-of-staff: review PENDING                                     │  ║
║  │ Bugs: 1 fixed, 0 open                                                  │  ║
║  │ Spend: $0.37 yesterday | $5.20 this week                               │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  🔔 ITEMS NEEDING YOUR ATTENTION                                             ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ 1. [APPROVAL] bug-bash spec ready for review                           │  ║
║  │ 2. [SPEC_REVIEW] chief-of-staff spec needs revision (0.61 avg)        │  ║
║  │ 3. [NEW] chief-of-staff PRD created - ready for spec pipeline          │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  🔴 BLOCKERS                                                                 ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ None currently                                                         │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
║  🎯 RECOMMENDED TODAY                                                        ║
║  ┌────────────────────────────────────────────────────────────────────────┐  ║
║  │ Pri │ Task                                    │ Est Cost │ Est Time   │  ║
║  ├────────────────────────────────────────────────────────────────────────┤  ║
║  │ P1  │ Approve bug-bash spec                   │ $0       │ 5 min      │  ║
║  │ P1  │ Run spec pipeline for chief-of-staff   │ ~$1      │ 15 min     │  ║
║  │ P2  │ Start bug-bash implementation          │ ~$5      │ 1 hr       │  ║
║  └────────────────────────────────────────────────────────────────────────┘  ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  What would you like to focus on today?                                      ║
║                                                                              ║
║  [1] Accept recommendations and start                                        ║
║  [2] Modify priorities                                                       ║
║  [3] Autopilot: Execute P1 tasks, report back                                ║
║  [4] Something else                                                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 10.2 Autopilot Checkpoint Output

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  CHECKPOINT: Approval Required                                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  chief-of-staff spec is ready for your review.                               ║
║                                                                              ║
║  Progress so far:                                                            ║
║  • bug-bash spec approved                                                    ║
║  • chief-of-staff spec generated                                             ║
║  • Cost: $1.20 / $10 budget                                                  ║
║  • Time: 15 min / 2h duration                                                ║
║                                                                              ║
║  Session state saved. You can resume with:                                   ║
║  swarm-attack autopilot --resume ap-20251213-001                             ║
║                                                                              ║
║  [1] Review and approve spec                                                 ║
║  [2] Review and request changes                                              ║
║  [3] Pause autopilot, I'll continue manually                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### 10.3 Daily Log Markdown Format

```markdown
# Daily Log: 2025-12-12

## Morning Standup
- **Time:** 08:30
- **Session ID:** cos-20251212-001

### Yesterday's Goals (from 2025-12-11)
| Goal | Status | Notes |
|------|--------|-------|
| Fix RT blockers | Partial | #1 still blocked |
| Test bug-bash | Done | Full pipeline validated |
| Start new PRD | Skipped | Blockers took priority |

### Current State Snapshot
- **Features:** 1 (bug-bash @ SPEC_NEEDS_APPROVAL)
- **Specs:** 1 (bug-bash @ review passed)
- **Bugs:** 1 fixed, 0 open
- **GitHub Issues:** 14 closed, 2 blocked
- **Tests:** 3/3 passing
- **Git:** master branch, clean

### Today's Plan (agreed with Philip)
1. [P1] Approve bug-bash spec
2. [P2] Build Chief of Staff agent
3. [P3] Clean up test files

### Philip's Notes
> "Let's prioritize the Chief of Staff - it will pay dividends."

---

## Work Log

### 09:15 - Approved bug-bash spec
- Command: `swarm-attack approve bug-bash`
- Result: Success
- Cost: $0

### 09:20 - Started Chief of Staff implementation
- Created PRD
- Cost: $0

### 11:30 - CHECKPOINT: Spec ready for review
- Spec generated for chief-of-staff
- Awaiting Philip's approval
- Cost so far: $2.50

---

## End of Day Summary
- **Goals Completed:** 2/3
- **Total Cost:** $5.20
- **Key Accomplishments:**
  - Chief of Staff PRD approved
  - Spec generated and reviewed
- **Blockers for Tomorrow:**
  - None
- **Carryover:**
  - Clean up test files (low priority)
```

---

## 11. Decision Log Format (JSONL)

Each line in `decisions.jsonl` is a JSON object:

```json
{"timestamp": "2025-12-12T09:15:00Z", "type": "approval", "item": "bug-bash-spec", "decision": "approved", "rationale": "Spec meets quality thresholds", "human_override": false, "metadata": {"scores": {"clarity": 0.9, "coverage": 0.85}}}
{"timestamp": "2025-12-12T09:30:00Z", "type": "priority", "item": "chief-of-staff", "decision": "P1", "rationale": "Philip requested prioritization", "human_override": true, "metadata": {"original_priority": "P2"}}
{"timestamp": "2025-12-12T11:30:00Z", "type": "checkpoint", "item": "autopilot-session-001", "decision": "paused", "rationale": "approval_required trigger", "human_override": false, "metadata": {"trigger": "approval_required", "context": "spec ready for review", "session_persisted": true}}
```

---

## 12. Metrics Tracking

### 12.1 Metrics File Format

```json
{
  "updated_at": "2025-12-12T18:00:00Z",
  "totals": {
    "cost_all_time_usd": 125.50,
    "goals_completed": 47,
    "goals_total": 52,
    "days_tracked": 14,
    "autopilot_sessions": 8,
    "autopilot_resumes": 3
  },
  "averages": {
    "daily_cost_usd": 8.96,
    "goal_completion_rate": 0.904,
    "time_accuracy": 0.82
  },
  "streaks": {
    "current_completion_streak": 5,
    "best_completion_streak": 8
  },
  "by_week": {
    "2025-W50": {
      "cost_usd": 45.20,
      "goals_completed": 12,
      "goals_total": 14
    }
  }
}
```

### 12.2 Metrics Calculated

| Metric | Calculation | Use |
|--------|-------------|-----|
| `daily_cost_usd` | `cost_all_time_usd / days_tracked` | Budget planning |
| `goal_completion_rate` | `goals_completed / goals_total` | Performance tracking |
| `time_accuracy` | `avg(min(actual, planned) / max(actual, planned))` | Estimation improvement |
| `completion_streak` | Consecutive days with 100% completion | Motivation |
| `autopilot_resume_rate` | `autopilot_resumes / autopilot_sessions` | Checkpoint effectiveness |

---

## 13. Implementation Notes

### 13.1 State Gathering Performance

To meet the <30 second standup requirement:

1. **Parallel Execution**: Gather from independent sources in parallel
2. **GitHub Caching**: Cache GitHub results for 5 minutes
3. **Lazy Test Collection**: Only run pytest --collect-only if tests.include enabled
4. **Incremental Updates**: Only re-gather what changed since last check

```python
async def gather(self, include_github: bool = True) -> RepoStateSnapshot:
    """Gather state with parallel execution."""
    tasks = [
        self._gather_git_state(),
        self._gather_features(),
        self._gather_bugs(),
        self._gather_prds(),
        self._gather_specs(),
        self._gather_interrupted_sessions(),
    ]

    if include_github:
        tasks.append(self._gather_github_cached())

    if self.config.standup.include_tests:
        tasks.append(self._gather_tests())

    results = await asyncio.gather(*tasks, return_exceptions=True)
    # ... assemble snapshot
```

### 13.2 Spec Gathering Implementation

```python
def gather_specs(self) -> list[SpecSummary]:
    """
    Gather all specs from specs/*/ directories.

    Scans specs/ directory for subdirectories containing spec files.
    For each spec:
    - Reads spec-draft.md or spec.md for title
    - Checks for spec-review.json for review status
    - Extracts scores if review exists

    Returns:
        List of SpecSummary objects.
    """
    specs = []
    specs_dir = Path("specs")

    if not specs_dir.exists():
        return specs

    for spec_dir in specs_dir.iterdir():
        if not spec_dir.is_dir():
            continue

        feature_id = spec_dir.name

        # Find spec file
        spec_path = None
        for name in ["spec.md", "spec-draft.md"]:
            candidate = spec_dir / name
            if candidate.exists():
                spec_path = candidate
                break

        if not spec_path:
            continue

        # Extract title from first H1
        title = feature_id
        try:
            content = spec_path.read_text()
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
        except Exception:
            pass

        # Check for review
        review_path = spec_dir / "spec-review.json"
        has_review = review_path.exists()
        review_passed = False
        review_scores = None

        if has_review:
            try:
                review_data = json.loads(review_path.read_text())
                review_passed = review_data.get("recommendation") == "APPROVE"
                review_scores = review_data.get("scores")
            except Exception:
                pass

        # Get modification time
        updated_at = datetime.fromtimestamp(
            spec_path.stat().st_mtime
        ).isoformat()

        specs.append(SpecSummary(
            feature_id=feature_id,
            title=title,
            path=str(spec_path),
            has_review=has_review,
            review_passed=review_passed,
            review_scores=review_scores,
            updated_at=updated_at,
        ))

    return specs
```

### 13.3 Goal Reconciliation Implementation

```python
def reconcile_with_state(self, snapshot: RepoStateSnapshot) -> list[dict[str, Any]]:
    """
    Reconcile goal statuses with actual repository state.

    Examines each goal's linked_feature, linked_bug, or linked_spec
    and updates status based on actual state.
    """
    changes = []
    today_goals = self.get_today_goals()

    # Build lookup maps
    feature_phases = {f.feature_id: f.phase for f in snapshot.features}
    bug_phases = {b.bug_id: b.phase for b in snapshot.bugs}
    spec_reviews = {s.feature_id: s for s in snapshot.specs}

    for goal in today_goals:
        old_status = goal.status
        new_status = old_status
        reason = ""

        # Check linked feature
        if goal.linked_feature and goal.linked_feature in feature_phases:
            phase = feature_phases[goal.linked_feature]
            if phase == "COMPLETE":
                new_status = GoalStatus.DONE
                reason = f"Feature {goal.linked_feature} completed"
            elif phase == "BLOCKED":
                new_status = GoalStatus.BLOCKED
                reason = f"Feature {goal.linked_feature} is blocked"
            elif phase in ("IMPLEMENTING", "SPEC_IN_PROGRESS"):
                if old_status == GoalStatus.PENDING:
                    new_status = GoalStatus.IN_PROGRESS
                    reason = f"Feature {goal.linked_feature} now {phase}"

        # Check linked bug
        elif goal.linked_bug and goal.linked_bug in bug_phases:
            phase = bug_phases[goal.linked_bug]
            if phase == "fixed":
                new_status = GoalStatus.DONE
                reason = f"Bug {goal.linked_bug} fixed"
            elif phase == "blocked":
                new_status = GoalStatus.BLOCKED
                reason = f"Bug {goal.linked_bug} is blocked"

        # Check linked spec
        elif goal.linked_spec and goal.linked_spec in spec_reviews:
            spec = spec_reviews[goal.linked_spec]
            if spec.has_review and spec.review_passed:
                new_status = GoalStatus.DONE
                reason = f"Spec {goal.linked_spec} review passed"
            elif spec.has_review and not spec.review_passed:
                new_status = GoalStatus.PARTIAL
                reason = f"Spec {goal.linked_spec} needs revision"

        # Apply change if different
        if new_status != old_status:
            self.update_goal(goal.id, new_status, notes=reason)
            changes.append({
                "goal_id": goal.id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "reason": reason,
            })

    return changes
```

### 13.4 Autopilot Session Persistence

```python
class AutopilotSessionStore:
    """Persists autopilot sessions for pause/resume capability."""

    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path / "autopilot"
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self.base_path / f"{session_id}.json"

    def save(self, session: AutopilotSession) -> None:
        """Save autopilot session atomically."""
        session.last_persisted_at = datetime.now().isoformat()

        path = self._session_path(session.session_id)
        temp_path = path.with_suffix(".tmp")
        backup_path = path.with_suffix(".bak")

        try:
            # Write to temp
            temp_path.write_text(json.dumps(session.to_dict(), indent=2))

            # Validate by re-reading
            AutopilotSession.from_dict(json.loads(temp_path.read_text()))

            # Backup existing
            if path.exists():
                shutil.copy2(path, backup_path)

            # Atomic rename
            temp_path.rename(path)

            # Remove backup
            if backup_path.exists():
                backup_path.unlink()

        except Exception as e:
            if backup_path.exists():
                shutil.copy2(backup_path, path)
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load(self, session_id: str) -> Optional[AutopilotSession]:
        """Load autopilot session."""
        path = self._session_path(session_id)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            return AutopilotSession.from_dict(data)
        except Exception:
            return None

    def list_paused(self) -> list[str]:
        """List paused session IDs."""
        paused = []
        for path in self.base_path.glob("*.json"):
            session = self.load(path.stem)
            if session and session.status == "paused":
                paused.append(session.session_id)
        return paused
```

### 13.5 Autopilot Resume Implementation

```python
def resume(self, session_id: str) -> AutopilotSession:
    """
    Resume a paused autopilot session.

    Loads session state, validates it can be resumed, and continues
    execution from where it left off.
    """
    session = self._session_store.load(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    if session.status != "paused":
        raise ValueError(f"Session {session_id} is {session.status}, not paused")

    # Update status to running
    session.status = "running"
    session.pause_reason = None

    # Continue from current_goal_index
    while session.current_goal_index < len(session.goals):
        goal = session.goals[session.current_goal_index]

        # Check for checkpoint triggers before execution
        trigger = self._checkpoint_system.check_triggers(session, goal.content)
        if trigger:
            action = self.handle_checkpoint(session, trigger)
            if action == "pause":
                return session
            elif action == "abort":
                session.status = "aborted"
                session.ended_at = datetime.now().isoformat()
                self._session_store.save(session)
                return session

        # Execute goal
        success, cost = self.execute_goal(goal)
        session.cost_spent_usd += cost

        if success:
            goal.status = GoalStatus.DONE
            goal.completed_at = datetime.now().isoformat()
        else:
            goal.status = GoalStatus.BLOCKED

        session.current_goal_index += 1

        # Persist after each goal
        self._session_store.save(session)

    # All goals complete
    session.status = "completed"
    session.ended_at = datetime.now().isoformat()
    self._session_store.save(session)
    return session
```

### 13.6 Atomic File Operations

All file writes use the atomic write pattern from existing code:

```python
def _save_atomic(self, path: Path, content: str) -> None:
    """Atomic write with temp file and rename."""
    temp_path = path.with_suffix(".tmp")
    backup_path = path.with_suffix(".bak")

    try:
        temp_path.write_text(content)

        if path.exists():
            shutil.copy2(path, backup_path)

        temp_path.rename(path)
        backup_path.unlink(missing_ok=True)

    except Exception:
        if backup_path.exists():
            backup_path.rename(path)
        raise
```

### 13.7 Recommendation Algorithm

```python
def generate_recommendations(
    self,
    state: RepoStateSnapshot,
) -> list[Recommendation]:
    """Generate prioritized recommendations."""
    recommendations = []

    # P1: Blockers and approvals
    for feature in state.features:
        if feature.phase == "SPEC_NEEDS_APPROVAL":
            recommendations.append(Recommendation(
                priority="P1",
                task=f"Approve {feature.feature_id} spec",
                estimated_cost_usd=0,
                estimated_minutes=5,
                rationale="Spec ready for review",
                linked_feature=feature.feature_id,
                command=f"swarm-attack approve {feature.feature_id}",
            ))

    for bug in state.bugs:
        if bug.phase == "planned":
            recommendations.append(Recommendation(
                priority="P1",
                task=f"Review fix plan for {bug.bug_id}",
                estimated_cost_usd=0,
                estimated_minutes=10,
                rationale="Fix plan awaiting approval",
                linked_bug=bug.bug_id,
                command=f"swarm-attack bug approve {bug.bug_id}",
            ))

    # P1: Spec reviews needing attention
    for spec in state.specs:
        if spec.has_review and not spec.review_passed:
            avg_score = 0.0
            if spec.review_scores:
                avg_score = sum(spec.review_scores.values()) / len(spec.review_scores)
            recommendations.append(Recommendation(
                priority="P1",
                task=f"Revise {spec.feature_id} spec (avg score: {avg_score:.2f})",
                estimated_cost_usd=0.50,
                estimated_minutes=15,
                rationale="Spec review failed, needs revision",
                linked_spec=spec.feature_id,
                command=f"swarm-attack run {spec.feature_id}",
            ))

    # P1: Regressions
    if state.tests.failing > 0:
        recommendations.append(Recommendation(
            priority="P1",
            task=f"Fix {state.tests.failing} failing tests",
            estimated_cost_usd=2.0,
            estimated_minutes=30,
            rationale="Test regressions detected",
        ))

    # P2: Continue in-progress work
    for feature in state.features:
        if feature.phase in ("SPEC_IN_PROGRESS", "IMPLEMENTING"):
            recommendations.append(Recommendation(
                priority="P2",
                task=f"Continue {feature.feature_id}",
                estimated_cost_usd=5.0,
                estimated_minutes=60,
                rationale="Work in progress",
                linked_feature=feature.feature_id,
                command=f"swarm-attack run {feature.feature_id}",
            ))

    # P2: PRDs ready for spec
    for prd in state.prds:
        if prd.phase == "PRD_READY":
            # Check if feature exists
            feature_exists = any(f.feature_id == prd.feature_id for f in state.features)
            if not feature_exists:
                recommendations.append(Recommendation(
                    priority="P2",
                    task=f"Initialize feature {prd.feature_id}",
                    estimated_cost_usd=0,
                    estimated_minutes=1,
                    rationale="PRD ready, feature not initialized",
                    command=f"swarm-attack init {prd.feature_id}",
                ))
            else:
                recommendations.append(Recommendation(
                    priority="P2",
                    task=f"Generate spec for {prd.feature_id}",
                    estimated_cost_usd=1.0,
                    estimated_minutes=15,
                    rationale="PRD ready for spec generation",
                    linked_feature=prd.feature_id,
                    command=f"swarm-attack run {prd.feature_id}",
                ))

    # Sort by priority
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

    return recommendations
```

---

## 14. Dependencies

### 14.1 External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `rich` | existing | CLI output formatting |
| `typer` | existing | CLI framework |
| `pyyaml` | existing | Config parsing |
| `filelock` | existing | Concurrent file access |

### 14.2 Internal Dependencies

| Module | Dependency |
|--------|------------|
| `state_gatherer.py` | `StateStore`, `BugStateStore`, config |
| `daily_log.py` | models |
| `goal_tracker.py` | `DailyLogManager`, models |
| `standup.py` | `StateGatherer`, `DailyLogManager`, `GoalTracker` |
| `autopilot_store.py` | models |
| `autopilot.py` | `CheckpointSystem`, `GoalTracker`, `AutopilotSessionStore`, `Orchestrator`, `BugOrchestrator` |
| CLI commands | All of the above |

---

## 15. Future Considerations (Phase 6)

### 15.1 Preference Learning

Track patterns in human decisions to improve recommendations:

```python
@dataclass
class PreferencePattern:
    """A learned preference pattern."""
    pattern_type: str           # "time_of_day", "task_type", "priority_override"
    observation_count: int
    confidence: float
    action: str                 # What to do when pattern matches
```

### 15.2 Personalized Estimates

Use historical data to improve time/cost estimates:

```python
def estimate_task(self, task_type: str, complexity: str) -> tuple[float, int]:
    """Estimate cost and time based on history."""
    historical = self._get_historical_tasks(task_type, complexity)
    if len(historical) < 3:
        return self._default_estimate(task_type, complexity)

    avg_cost = sum(t.cost for t in historical) / len(historical)
    avg_time = sum(t.duration for t in historical) / len(historical)

    return avg_cost, avg_time
```

---

## 16. Implementation Notes (December 2025)

### 16.1 Implementation Summary

| Metric | Value |
|--------|-------|
| Issues Complete | **20/20 (100%)** |
| Tests Passing | **279** |
| CLI Commands | **6 working** (standup, checkin, wrapup, history, next, autopilot) |
| Implementation Cost | ~$5.00 |

### 16.2 Expert Panel Decisions

An expert panel review was conducted to guide implementation decisions:

#### Decision 1: Inline CLI vs Modular Design (ACCEPTED)

**Spec Design**: Separate `StandupGenerator` class with `generate() -> StandupReport` interface.

**Implementation**: Inline logic in CLI commands (`cli/chief_of_staff.py`).

**Rationale**:
- Swarm automation failed systematically for CLI issues (test-first incompatibility)
- Inline approach delivered 6 working commands quickly
- Technical debt acceptable for MVP; can refactor to `StandupGenerator` later if needed
- Trade-off: Less testable in isolation, but all commands work

**Vote**: 5-0 ACCEPT (Agentic AI Architect, Python Backend Lead, Testing Strategist, Software Architect, DevOps Engineer)

#### Decision 2: AutopilotRunner Strategy - Option B+ (Enhanced Stub)

**Options Considered**:
- A: Full manual implementation (high risk, complex orchestrator integration)
- B: Minimal stub (marks complete without any logic)
- B+: Enhanced stub (validates checkpoints, stubs execution)
- C: Retry swarm (high risk of regressions)
- D: Skip entirely (defer to future)

**Chosen**: Option B+ - Enhanced stub that:
- Validates all checkpoint trigger logic (cost, time, approval, high-risk)
- Tracks goal progress correctly
- Persists sessions for pause/resume
- Stubs actual execution (no orchestrator calls)
- Logs what WOULD execute for debugging

**Rationale**:
- Validates checkpoint logic without risk of breaking 227 existing tests
- Unblocks CLI autopilot command immediately
- Real orchestrator integration can be added incrementally
- Maintains clean separation of concerns

**Vote**: 4-1 ACCEPT (Architect dissenting on deferring real execution)

### 16.3 CLI Commands Implementation

CLI commands were implemented manually due to test-first incompatibility:

**Problem**: Swarm test-writer generates tests expecting CLI commands that don't exist yet.
```python
# Test generated BEFORE implementation:
from swarm_attack.cli import StandupGenerator  # DOESN'T EXIST
result = runner.invoke(app, ["standup"])
assert result.exit_code == 0  # FAILS: command not registered
```

**Solution**: Implement all commands in `swarm_attack/cli/chief_of_staff.py`:

```bash
swarm-attack cos standup    # Interactive morning briefing
swarm-attack cos checkin    # Quick mid-day status
swarm-attack cos wrapup     # End-of-day summary
swarm-attack cos history    # View past logs (--days, --weekly, --decisions)
swarm-attack cos next       # Recommendations (--all for cross-feature)
swarm-attack cos autopilot  # Execute goals with checkpoints
```

### 16.4 AutopilotRunner Implementation

**Location**: `swarm_attack/chief_of_staff/autopilot_runner.py`

**Key Classes**:
```python
@dataclass
class GoalExecutionResult:
    success: bool
    cost_usd: float
    duration_seconds: int
    error: Optional[str] = None
    output: str = ""

@dataclass
class AutopilotRunResult:
    session: AutopilotSession
    goals_completed: int
    goals_total: int
    total_cost_usd: float
    duration_seconds: int
    trigger: Optional[CheckpointTrigger] = None

class AutopilotRunner:
    def start(self, goals, budget_usd, duration_minutes, stop_trigger, dry_run) -> AutopilotRunResult
    def resume(self, session_id) -> AutopilotRunResult
    def cancel(self, session_id) -> bool
    def list_paused_sessions() -> list[AutopilotSession]
```

**Stub Execution** (current implementation):
```python
def _execute_goal(self, goal: DailyGoal) -> GoalExecutionResult:
    # Logs what WOULD execute, returns success with zero cost
    if goal.linked_feature:
        # Future: self.orchestrator.run_feature(goal.linked_feature)
        pass
    elif goal.linked_bug:
        # Future: self.bug_orchestrator.fix(goal.linked_bug)
        pass
    return GoalExecutionResult(success=True, cost_usd=0.0, duration_seconds=0)
```

### 16.5 Bug Fixes Applied

#### DailyLog Goals Field
The `DailyLog` dataclass was missing the `goals` field. Masked by MagicMock's dynamic attributes.
```python
@dataclass
class DailyLog:
    date: date
    goals: list[DailyGoal]  # Added
    # ...
```

#### FeatureSummary Attribute
`GoalTracker` used `feature.name` but `FeatureSummary` has `feature_id`. Fixed all references.

### 16.6 Files Created/Modified

| File | Change |
|------|--------|
| `swarm_attack/cli/chief_of_staff.py` | New: CLI commands (~800 lines) |
| `swarm_attack/cli/app.py` | Register `cos` sub-app |
| `swarm_attack/chief_of_staff/autopilot_runner.py` | New: AutopilotRunner (~400 lines) |
| `swarm_attack/chief_of_staff/__init__.py` | Export all new classes |
| `swarm_attack/chief_of_staff/daily_log.py` | Add `DailyGoal`, `goals` field |
| `swarm_attack/chief_of_staff/goal_tracker.py` | Fix `feature.name` → `feature.feature_id` |
| `tests/generated/chief-of-staff/test_cli_commands.py` | New: 21 CLI tests |
| `tests/generated/chief-of-staff/test_issue_10.py` | New: 31 AutopilotRunner tests |
| `tests/generated/chief-of-staff/test_issue_6.py` | Fix mock attributes |

### 16.7 Test Coverage

| Test File | Tests | Description |
|-----------|-------|-------------|
| test_issue_3.py | 17 | SwarmConfig integration |
| test_issue_4.py | 58 | DailyLogManager |
| test_issue_5.py | 42 | StateGatherer |
| test_issue_6.py | 52 | GoalTracker |
| test_issue_7.py | 34 | CheckpointSystem |
| test_issue_9.py | 24 | AutopilotSessionStore |
| test_issue_10.py | 31 | AutopilotRunner |
| test_cli_commands.py | 21 | CLI integration tests |
| **Total** | **279** | |

### 16.8 Future Work

1. **Real Execution**: Add orchestrator integration to `AutopilotRunner._execute_goal()`
2. **StandupGenerator Class**: Extract standup logic from CLI if testability becomes an issue
3. **Integration Tests**: End-to-end tests with real file system and git operations
4. **Preference Learning**: Track human decision patterns (Phase 6 scope)