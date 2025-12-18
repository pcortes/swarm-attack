"""
Core data models for Feature Swarm.

This module defines the foundational data structures used throughout the system:
- Enums for feature phases and task stages
- Dataclasses for state management, sessions, and Claude results
- JSON serialization support for all models
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional


class FeaturePhase(Enum):
    """
    Phases in the feature lifecycle.

    A feature progresses through these phases from idea to completion.
    The smart CLI uses this to determine what action to take next.
    """
    # Setup
    NO_PRD = auto()                  # Need to create PRD interactively
    PRD_READY = auto()               # PRD exists, ready for spec

    # Specification
    SPEC_IN_PROGRESS = auto()        # Spec debate running
    SPEC_NEEDS_APPROVAL = auto()     # Spec ready for human review
    SPEC_APPROVED = auto()           # Human approved spec

    # Issue Creation
    ISSUES_CREATING = auto()         # CCPM creating issues
    ISSUES_VALIDATING = auto()       # Validator checking issues
    ISSUES_NEED_REVIEW = auto()      # Validation done, needs greenlight
    READY_TO_IMPLEMENT = auto()      # Greenlit, ready to work

    # Implementation
    IMPLEMENTING = auto()            # Work in progress

    # Completion
    COMPLETE = auto()                # All issues done

    # Error states
    BLOCKED = auto()                 # Needs human intervention


class TaskStage(Enum):
    """
    Stages an individual task/issue can be in.

    Tasks are the atomic units of work within a feature.
    """
    # Pre-implementation
    BACKLOG = auto()                 # Created but not ready
    NEEDS_REVISION = auto()          # Failed validation
    READY = auto()                   # Ready to be picked up

    # Implementation
    IN_PROGRESS = auto()             # Currently being worked on
    INTERRUPTED = auto()             # Session interrupted

    # Verification
    VERIFYING = auto()               # Tests running

    # Completion
    DONE = auto()                    # Complete and verified
    BLOCKED = auto()                 # Needs human help
    SKIPPED = auto()                 # Skipped due to blocked dependency
    MANUAL_REQUIRED = auto()         # Requires manual human verification (not automatable)


@dataclass
class CheckpointData:
    """
    Data captured at each checkpoint during a session.

    Checkpoints allow resuming from any failure point.
    """
    agent: str                       # Name of the agent that created this checkpoint
    status: str                      # Status at checkpoint (e.g., "complete", "in_progress")
    timestamp: str                   # ISO format timestamp
    commit: Optional[str] = None     # Git commit hash if applicable
    cost_usd: float = 0.0            # Cost incurred up to this checkpoint

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointData:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class IssueOutput:
    """
    Files and classes created by an issue.

    Tracks what artifacts an issue produces for context handoff
    to subsequent issues that may depend on them.
    """
    files_created: list[str] = field(default_factory=list)
    classes_defined: dict[str, list[str]] = field(default_factory=dict)  # file -> [class names]
    semantic_summary: Optional[str] = None  # LLM-generated summary of implementation

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IssueOutput:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class TaskRef:
    """
    Reference to a task/issue with metadata for prioritization.

    Used by the PrioritizationAgent to determine issue order.
    """
    issue_number: int                # GitHub issue number
    stage: TaskStage                 # Current stage
    title: str                       # Issue title
    dependencies: list[int] = field(default_factory=list)  # Issue numbers this depends on
    estimated_size: str = "medium"   # "small", "medium", "large"
    business_value_score: float = 0.5  # 0-1, higher is more valuable
    technical_risk_score: float = 0.5  # 0-1, higher is riskier
    blocked_reason: Optional[str] = None  # Why this task is blocked (error message)
    outputs: Optional[IssueOutput] = None  # Files/classes created (populated after DONE)
    completion_summary: Optional[str] = None  # Semantic summary after DONE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["stage"] = self.stage.name
        # Handle IssueOutput serialization
        if self.outputs is not None:
            data["outputs"] = self.outputs.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRef:
        """Create from dictionary."""
        data = data.copy()
        data["stage"] = TaskStage[data["stage"]]
        # Handle IssueOutput deserialization
        if data.get("outputs") is not None:
            data["outputs"] = IssueOutput.from_dict(data["outputs"])
        return cls(**data)


@dataclass
class ClaudeResult:
    """
    Result from a Claude Code CLI invocation.

    Captures the response text and metadata from the JSON envelope.
    """
    text: str                        # Primary response text (from "result" field)
    total_cost_usd: float            # Cost of this invocation
    num_turns: int                   # Number of conversation turns
    duration_ms: int                 # Duration in milliseconds
    session_id: str                  # Claude session identifier
    raw: dict[str, Any] = field(default_factory=dict)  # Full JSON envelope

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaudeResult:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class SessionState:
    """
    State of a single work session (one issue).

    Persisted to .swarm/sessions/<feature>/sess_*.json
    """
    session_id: str                  # Unique session identifier
    feature_id: str                  # Feature this session belongs to
    issue_number: int                # GitHub issue being worked on
    started_at: str                  # ISO format timestamp
    status: str                      # Current status ("active", "complete", "interrupted")
    checkpoints: list[CheckpointData] = field(default_factory=list)
    ended_at: Optional[str] = None   # ISO format timestamp when ended
    end_status: Optional[str] = None # Final status ("success", "failed", "blocked")
    cost_usd: float = 0.0            # Total cost of this session
    worktree_path: Optional[str] = None  # Path to worktree if using worktrees
    commits: list[str] = field(default_factory=list)  # Git commit hashes created this session

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["checkpoints"] = [cp.to_dict() if isinstance(cp, CheckpointData) else cp
                               for cp in self.checkpoints]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create from dictionary."""
        data = data.copy()
        data["checkpoints"] = [CheckpointData.from_dict(cp) if isinstance(cp, dict) else cp
                               for cp in data.get("checkpoints", [])]
        return cls(**data)

    def add_checkpoint(self, agent: str, status: str,
                       commit: Optional[str] = None, cost_usd: float = 0.0) -> None:
        """Add a checkpoint to this session."""
        checkpoint = CheckpointData(
            agent=agent,
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            commit=commit,
            cost_usd=cost_usd
        )
        self.checkpoints.append(checkpoint)
        self.cost_usd += cost_usd


@dataclass
class RunState:
    """
    Persistent state of a feature.

    Persisted to .swarm/state/<feature>.json
    This is the source of truth for where a feature is in its lifecycle.
    """
    feature_id: str                  # Unique feature identifier (slug)
    phase: FeaturePhase              # Current phase
    tasks: list[TaskRef] = field(default_factory=list)  # All tasks for this feature
    current_session: Optional[str] = None  # Active session ID if any
    created_at: str = ""             # ISO format timestamp
    updated_at: str = ""             # ISO format timestamp
    cost_total_usd: float = 0.0      # Total cost across all sessions
    cost_by_phase: dict[str, float] = field(default_factory=dict)  # Cost breakdown

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["phase"] = self.phase.name
        data["tasks"] = [task.to_dict() if isinstance(task, TaskRef) else task
                         for task in self.tasks]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunState:
        """Create from dictionary."""
        data = data.copy()
        data["phase"] = FeaturePhase[data["phase"]]
        data["tasks"] = [TaskRef.from_dict(task) if isinstance(task, dict) else task
                         for task in data.get("tasks", [])]
        return cls(**data)

    def update_phase(self, new_phase: FeaturePhase) -> None:
        """Update the phase and refresh updated_at timestamp."""
        self.phase = new_phase
        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def add_cost(self, cost_usd: float, phase: Optional[str] = None) -> None:
        """Track cost, optionally by phase."""
        self.cost_total_usd += cost_usd
        if phase:
            self.cost_by_phase[phase] = self.cost_by_phase.get(phase, 0.0) + cost_usd
        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def get_tasks_by_stage(self, stage: TaskStage) -> list[TaskRef]:
        """Get all tasks in a specific stage."""
        return [task for task in self.tasks if task.stage == stage]

    @property
    def ready_tasks(self) -> list[TaskRef]:
        """Get all tasks ready to be worked on."""
        return self.get_tasks_by_stage(TaskStage.READY)

    @property
    def done_tasks(self) -> list[TaskRef]:
        """Get all completed tasks."""
        return self.get_tasks_by_stage(TaskStage.DONE)

    @property
    def blocked_tasks(self) -> list[TaskRef]:
        """Get all blocked tasks."""
        return self.get_tasks_by_stage(TaskStage.BLOCKED)

    @property
    def skipped_tasks(self) -> list[TaskRef]:
        """Get all skipped tasks (blocked due to dependency failure)."""
        return self.get_tasks_by_stage(TaskStage.SKIPPED)


# JSON encoder for custom types
class SwarmEncoder(json.JSONEncoder):
    """JSON encoder that handles Feature Swarm model types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.name
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)


def model_to_json(obj: Any, **kwargs: Any) -> str:
    """Serialize a model object to JSON string."""
    return json.dumps(obj, cls=SwarmEncoder, **kwargs)


def model_from_json(json_str: str, model_class: type) -> Any:
    """Deserialize a JSON string to a model object."""
    data = json.loads(json_str)
    if hasattr(model_class, "from_dict"):
        return model_class.from_dict(data)
    return model_class(**data)
