"""
Bug Bash data models for swarm-attack.

This module defines all data structures for the Bug Bash pipeline:
- BugPhase enum for state machine
- BugReport, ReproductionResult, RootCauseAnalysis, FixPlan
- BugState for complete investigation state
- Cost tracking and phase transitions
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional


class BugPhase(Enum):
    """
    Phases of bug investigation.

    The bug investigation progresses through these phases:
    CREATED → REPRODUCING → REPRODUCED/NOT_REPRODUCIBLE
    REPRODUCED → ANALYZING → ANALYZED → PLANNING → PLANNED
    PLANNED → APPROVED/WONT_FIX
    APPROVED → IMPLEMENTING → VERIFYING → FIXED/BLOCKED
    """

    CREATED = "created"
    REPRODUCING = "reproducing"
    REPRODUCED = "reproduced"
    NOT_REPRODUCIBLE = "not_reproducible"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    PLANNING = "planning"
    PLANNED = "planned"
    APPROVED = "approved"
    WONT_FIX = "wont_fix"
    IMPLEMENTING = "implementing"
    VERIFYING = "verifying"
    FIXED = "fixed"
    BLOCKED = "blocked"


# Valid phase transitions
# BLOCKED can be reached from any intermediate phase where agent errors can occur
VALID_TRANSITIONS: dict[BugPhase, list[BugPhase]] = {
    BugPhase.CREATED: [BugPhase.REPRODUCING],
    BugPhase.REPRODUCING: [BugPhase.REPRODUCED, BugPhase.NOT_REPRODUCIBLE, BugPhase.BLOCKED],
    BugPhase.REPRODUCED: [BugPhase.ANALYZING, BugPhase.BLOCKED],
    BugPhase.ANALYZING: [BugPhase.ANALYZED, BugPhase.BLOCKED],
    BugPhase.ANALYZED: [BugPhase.PLANNING, BugPhase.BLOCKED],
    BugPhase.PLANNING: [BugPhase.PLANNED, BugPhase.BLOCKED],
    BugPhase.PLANNED: [BugPhase.APPROVED, BugPhase.WONT_FIX],
    BugPhase.APPROVED: [BugPhase.IMPLEMENTING, BugPhase.BLOCKED],
    BugPhase.IMPLEMENTING: [BugPhase.VERIFYING, BugPhase.BLOCKED],
    BugPhase.VERIFYING: [BugPhase.FIXED, BugPhase.BLOCKED],
    BugPhase.BLOCKED: [BugPhase.REPRODUCING],  # Can retry
    BugPhase.NOT_REPRODUCIBLE: [BugPhase.WONT_FIX],
    BugPhase.WONT_FIX: [],
    BugPhase.FIXED: [],
}


def is_valid_transition(from_phase: BugPhase, to_phase: BugPhase) -> bool:
    """Check if a phase transition is valid."""
    return to_phase in VALID_TRANSITIONS.get(from_phase, [])


@dataclass
class BugReport:
    """
    Initial bug report from user.

    Contains the information provided when a bug investigation is created.
    """

    description: str
    test_path: Optional[str] = None
    github_issue: Optional[int] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    steps_to_reproduce: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BugReport:
        """Create from dictionary."""
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate the bug report. Returns list of errors."""
        errors = []
        if not self.description or not self.description.strip():
            errors.append("description is required")
        return errors


@dataclass
class ReproductionResult:
    """
    Output from Bug Researcher agent.

    Contains evidence gathered during reproduction attempt.
    """

    confirmed: bool
    reproduction_steps: list[str]
    test_output: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    affected_files: list[str] = field(default_factory=list)
    related_code_snippets: dict[str, str] = field(default_factory=dict)
    confidence: Literal["high", "medium", "low"] = "medium"
    notes: str = ""
    attempts: int = 1
    environment: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReproductionResult:
        """Create from dictionary."""
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate the reproduction result. Returns list of errors."""
        errors = []
        if self.confirmed:
            if not self.affected_files:
                errors.append("affected_files must have at least 1 entry when confirmed")
            if not self.reproduction_steps:
                errors.append("reproduction_steps must have at least 1 step when confirmed")
        if self.confidence not in ("high", "medium", "low"):
            errors.append(f"confidence must be high, medium, or low, got: {self.confidence}")
        return errors


@dataclass
class RootCauseAnalysis:
    """
    Output from Root Cause Analyzer agent.

    Contains the analysis of why the bug occurs.
    """

    summary: str
    execution_trace: list[str]
    root_cause_file: str
    root_cause_line: Optional[int] = None
    root_cause_code: str = ""
    root_cause_explanation: str = ""
    why_not_caught: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    alternative_hypotheses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RootCauseAnalysis:
        """Create from dictionary."""
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate the root cause analysis. Returns list of errors."""
        errors = []
        if len(self.summary) > 100:
            errors.append(f"summary must be at most 100 characters, got {len(self.summary)}")
        if len(self.execution_trace) < 3:
            errors.append(f"execution_trace must have at least 3 steps, got {len(self.execution_trace)}")
        if not self.root_cause_file:
            errors.append("root_cause_file is required")
        if not self.root_cause_code:
            errors.append("root_cause_code is required")
        if not self.root_cause_explanation:
            errors.append("root_cause_explanation is required")
        if self.confidence not in ("high", "medium", "low"):
            errors.append(f"confidence must be high, medium, or low, got: {self.confidence}")
        return errors


@dataclass
class FileChange:
    """
    A single file change in the fix plan.

    Represents one modification to apply during fix implementation.
    """

    file_path: str
    change_type: Literal["modify", "create", "delete"]
    current_code: Optional[str] = None
    proposed_code: Optional[str] = None
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileChange:
        """Create from dictionary."""
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate the file change. Returns list of errors."""
        errors = []
        if not self.file_path:
            errors.append("file_path is required")
        if self.change_type not in ("modify", "create", "delete"):
            errors.append(f"change_type must be modify, create, or delete, got: {self.change_type}")
        if self.change_type == "modify" and not self.current_code:
            errors.append("current_code is required for modify changes")
        if self.change_type in ("modify", "create") and not self.proposed_code:
            errors.append("proposed_code is required for modify and create changes")
        return errors


@dataclass
class TestCase:
    """
    A test case to verify the fix.

    Generated by the Fix Planner to ensure the fix works correctly.
    """

    name: str
    description: str
    test_code: str
    category: Literal["regression", "edge_case", "integration"] = "regression"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TestCase:
        """Create from dictionary."""
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate the test case. Returns list of errors."""
        errors = []
        if not self.name:
            errors.append("name is required")
        if not self.description:
            errors.append("description is required")
        if not self.test_code:
            errors.append("test_code is required")
        if self.category not in ("regression", "edge_case", "integration"):
            errors.append(f"category must be regression, edge_case, or integration, got: {self.category}")
        return errors


@dataclass
class FixPlan:
    """
    Output from Fix Planner agent.

    Contains the complete plan for fixing the bug.
    """

    summary: str
    changes: list[FileChange]
    test_cases: list[TestCase]
    risk_level: Literal["low", "medium", "high"] = "low"
    risk_explanation: str = ""
    scope: str = ""
    side_effects: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    estimated_effort: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["changes"] = [c if isinstance(c, dict) else c.to_dict() for c in self.changes]
        data["test_cases"] = [t if isinstance(t, dict) else t.to_dict() for t in self.test_cases]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FixPlan:
        """Create from dictionary."""
        data = data.copy()
        data["changes"] = [
            FileChange.from_dict(c) if isinstance(c, dict) else c
            for c in data.get("changes", [])
        ]
        data["test_cases"] = [
            TestCase.from_dict(t) if isinstance(t, dict) else t
            for t in data.get("test_cases", [])
        ]
        return cls(**data)

    def validate(self, min_test_cases: int = 2) -> list[str]:
        """Validate the fix plan. Returns list of errors."""
        errors = []
        if not self.summary:
            errors.append("summary is required")
        if not self.changes:
            errors.append("changes must have at least 1 entry")
        if len(self.test_cases) < min_test_cases:
            errors.append(f"test_cases must have at least {min_test_cases} entries, got {len(self.test_cases)}")
        if self.risk_level not in ("low", "medium", "high"):
            errors.append(f"risk_level must be low, medium, or high, got: {self.risk_level}")
        if not self.rollback_plan:
            errors.append("rollback_plan is required")

        # Validate nested objects
        for i, change in enumerate(self.changes):
            for err in change.validate():
                errors.append(f"changes[{i}]: {err}")

        for i, test in enumerate(self.test_cases):
            for err in test.validate():
                errors.append(f"test_cases[{i}]: {err}")

        return errors

    def get_hash(self) -> str:
        """Get SHA256 hash of the fix plan for audit trail."""
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode()
        ).hexdigest()


@dataclass
class ImplementationResult:
    """
    Output from fix implementation.

    Records what happened during the fix application.
    """

    success: bool
    files_changed: list[str]
    tests_passed: int
    tests_failed: int
    commit_hash: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImplementationResult:
        """Create from dictionary."""
        return cls(**data)


@dataclass
class AgentCost:
    """
    Cost tracking for a single agent run.

    Records tokens used and cost incurred for audit and budgeting.
    """

    agent_name: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: str  # ISO format

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCost:
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def create(
        cls,
        agent_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
    ) -> AgentCost:
        """Create a new AgentCost with current timestamp."""
        return cls(
            agent_name=agent_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )


@dataclass
class PhaseTransition:
    """
    Record of a phase transition.

    Maintains audit trail of all state changes.
    """

    from_phase: str  # BugPhase.value
    to_phase: str  # BugPhase.value
    timestamp: str  # ISO format
    trigger: str  # "auto", "user_command", "agent_output"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PhaseTransition:
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def create(
        cls,
        from_phase: BugPhase,
        to_phase: BugPhase,
        trigger: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> PhaseTransition:
        """Create a new PhaseTransition with current timestamp."""
        return cls(
            from_phase=from_phase.value,
            to_phase=to_phase.value,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            trigger=trigger,
            metadata=metadata or {},
        )


@dataclass
class ApprovalRecord:
    """
    Audit record for approval.

    Tracks who approved the fix plan and when.
    """

    approved_by: str
    approved_at: str  # ISO format
    fix_plan_hash: str  # SHA256 of fix plan JSON

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApprovalRecord:
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def create(cls, approved_by: str, fix_plan: FixPlan) -> ApprovalRecord:
        """Create a new ApprovalRecord with current timestamp."""
        return cls(
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            fix_plan_hash=fix_plan.get_hash(),
        )


@dataclass
class BugState:
    """
    Complete state of a bug investigation.

    This is the main state object persisted to .swarm/bugs/{bug_id}/state.json.
    It contains all information about the bug investigation lifecycle.
    """

    bug_id: str
    phase: BugPhase
    created_at: str  # ISO format
    updated_at: str  # ISO format
    report: BugReport

    reproduction: Optional[ReproductionResult] = None
    root_cause: Optional[RootCauseAnalysis] = None
    fix_plan: Optional[FixPlan] = None
    implementation: Optional[ImplementationResult] = None

    costs: list[AgentCost] = field(default_factory=list)
    transitions: list[PhaseTransition] = field(default_factory=list)
    approval_record: Optional[ApprovalRecord] = None
    blocked_reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    version: int = 1

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def total_cost_usd(self) -> float:
        """Get total cost across all agent runs."""
        return sum(c.cost_usd for c in self.costs)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            "bug_id": self.bug_id,
            "phase": self.phase.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "report": self.report.to_dict() if self.report else None,
            "reproduction": self.reproduction.to_dict() if self.reproduction else None,
            "root_cause": self.root_cause.to_dict() if self.root_cause else None,
            "fix_plan": self.fix_plan.to_dict() if self.fix_plan else None,
            "implementation": self.implementation.to_dict() if self.implementation else None,
            "costs": [c.to_dict() for c in self.costs],
            "transitions": [t.to_dict() for t in self.transitions],
            "approval_record": self.approval_record.to_dict() if self.approval_record else None,
            "blocked_reason": self.blocked_reason,
            "rejection_reason": self.rejection_reason,
            "notes": self.notes,
            "version": self.version,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BugState:
        """Create from dictionary."""
        return cls(
            bug_id=data["bug_id"],
            phase=BugPhase(data["phase"]),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            report=BugReport.from_dict(data["report"]) if data.get("report") else BugReport(description=""),
            reproduction=ReproductionResult.from_dict(data["reproduction"]) if data.get("reproduction") else None,
            root_cause=RootCauseAnalysis.from_dict(data["root_cause"]) if data.get("root_cause") else None,
            fix_plan=FixPlan.from_dict(data["fix_plan"]) if data.get("fix_plan") else None,
            implementation=ImplementationResult.from_dict(data["implementation"]) if data.get("implementation") else None,
            costs=[AgentCost.from_dict(c) for c in data.get("costs", [])],
            transitions=[PhaseTransition.from_dict(t) for t in data.get("transitions", [])],
            approval_record=ApprovalRecord.from_dict(data["approval_record"]) if data.get("approval_record") else None,
            blocked_reason=data.get("blocked_reason"),
            rejection_reason=data.get("rejection_reason"),
            notes=data.get("notes", []),
            version=data.get("version", 1),
        )

    def transition_to(self, new_phase: BugPhase, trigger: str, metadata: Optional[dict[str, Any]] = None) -> None:
        """
        Transition to a new phase with validation and logging.

        Args:
            new_phase: The target phase.
            trigger: What triggered the transition (auto, user_command, agent_output).
            metadata: Optional additional context.

        Raises:
            InvalidPhaseError: If the transition is not valid.
        """
        if not is_valid_transition(self.phase, new_phase):
            raise InvalidPhaseError(
                f"Cannot transition from {self.phase.value} to {new_phase.value}. "
                f"Valid transitions: {[p.value for p in VALID_TRANSITIONS.get(self.phase, [])]}"
            )

        # Record transition
        transition = PhaseTransition.create(self.phase, new_phase, trigger, metadata)
        self.transitions.append(transition)

        # Update phase
        self.phase = new_phase
        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def add_cost(self, cost: AgentCost) -> None:
        """Add an agent cost record."""
        self.costs.append(cost)
        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def add_note(self, note: str) -> None:
        """Add a note to the investigation."""
        self.notes.append(note)
        self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def create(
        cls,
        bug_id: str,
        description: str,
        test_path: Optional[str] = None,
        github_issue: Optional[int] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> BugState:
        """Create a new bug investigation with initial state."""
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        report = BugReport(
            description=description,
            test_path=test_path,
            github_issue=github_issue,
            error_message=error_message,
            stack_trace=stack_trace,
        )
        return cls(
            bug_id=bug_id,
            phase=BugPhase.CREATED,
            created_at=now,
            updated_at=now,
            report=report,
        )


# Exception classes for Bug Bash
class BugBashError(Exception):
    """Base exception for Bug Bash errors."""
    pass


class BugNotFoundError(BugBashError):
    """Raised when bug_id does not exist."""
    pass


class InvalidPhaseError(BugBashError):
    """Raised when operation is invalid for current phase."""
    pass


class ApprovalRequiredError(BugBashError):
    """Raised when implementation attempted without approval."""
    pass


class StateCorruptionError(BugBashError):
    """Raised when state file is corrupted."""
    pass


class CostLimitExceededError(BugBashError):
    """Raised when cost exceeds limits."""
    pass


class ValidationError(BugBashError):
    """Raised when validation fails."""
    pass
