"""
Event types for the swarm-attack event system.

Defines SwarmEvent dataclass and EventType enum covering all significant events
in the feature and bug pipelines.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


class EventType(Enum):
    """All event types in the swarm system."""

    # Spec lifecycle
    SPEC_DRAFT_CREATED = "spec.draft_created"
    SPEC_REVIEW_COMPLETE = "spec.review_complete"
    SPEC_APPROVED = "spec.approved"
    SPEC_REJECTED = "spec.rejected"

    # Issue lifecycle
    ISSUE_CREATED = "issue.created"
    ISSUE_VALIDATED = "issue.validated"
    ISSUE_COMPLEXITY_PASSED = "issue.complexity_passed"
    ISSUE_COMPLEXITY_FAILED = "issue.complexity_failed"
    ISSUE_READY = "issue.ready"
    ISSUE_COMPLETE = "issue.complete"

    # Implementation lifecycle
    IMPL_STARTED = "impl.started"
    IMPL_TESTS_WRITTEN = "impl.tests_written"
    IMPL_CODE_COMPLETE = "impl.code_complete"
    IMPL_VERIFIED = "impl.verified"
    IMPL_FAILED = "impl.failed"

    # Bug lifecycle
    BUG_DETECTED = "bug.detected"
    BUG_REPRODUCED = "bug.reproduced"
    BUG_ANALYZED = "bug.analyzed"
    BUG_PLANNED = "bug.planned"
    BUG_APPROVED = "bug.approved"
    BUG_FIXED = "bug.fixed"
    BUG_BLOCKED = "bug.blocked"

    # System events
    SYSTEM_PHASE_TRANSITION = "system.phase_transition"
    SYSTEM_ERROR = "system.error"
    SYSTEM_RECOVERY = "system.recovery"

    # Auto-approval events (for Phase 2)
    AUTO_APPROVAL_TRIGGERED = "auto.approval_triggered"
    AUTO_APPROVAL_BLOCKED = "auto.approval_blocked"
    MANUAL_OVERRIDE = "auto.manual_override"


@dataclass
class SwarmEvent:
    """A single event in the swarm system."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    event_type: EventType = EventType.SYSTEM_ERROR
    feature_id: str = ""
    issue_number: Optional[int] = None
    bug_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source_agent: str = ""
    payload: dict = field(default_factory=dict)
    confidence: float = 0.0  # For auto-approval decisions

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SwarmEvent":
        """Create from dict."""
        data = data.copy()  # Don't mutate input
        data["event_type"] = EventType(data["event_type"])
        return cls(**data)

    def __str__(self) -> str:
        return f"[{self.timestamp}] {self.event_type.value} feature={self.feature_id}"
