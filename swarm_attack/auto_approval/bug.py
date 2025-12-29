"""
Bug Fix Auto-Approver for Bug Bash.

Automatically approves bug fixes when confidence is high and risk is acceptable.

Replaces manual `swarm-attack bug approve` command when conditions are met.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Any, Optional

from swarm_attack.auto_approval.models import ApprovalResult

if TYPE_CHECKING:
    from swarm_attack.event_logger import EventLogger


class FixPlanProtocol(Protocol):
    """Protocol for fix plan objects."""
    confidence: float
    risk_level: str
    breaks_api: bool
    requires_migration: bool


class BugStateProtocol(Protocol):
    """Protocol for bug state objects."""
    bug_id: str
    fix_plan: Optional[Any]


class BugStoreProtocol(Protocol):
    """Protocol for bug store operations."""
    def get(self, bug_id: str) -> BugStateProtocol | None: ...
    def approve_fix(self, bug_id: str) -> None: ...


class BugAutoApprover:
    """
    Replace manual `swarm-attack bug approve` command.

    Auto-approves bug fixes when:
    - Confidence >= 0.9
    - Risk level is low or medium (not high)
    - No API-breaking changes
    - No migrations required
    """

    CONFIDENCE_THRESHOLD = 0.9
    ALLOWED_RISK_LEVELS = ["low", "medium"]

    def __init__(
        self,
        bug_store: BugStoreProtocol,
        event_logger: "EventLogger",
    ) -> None:
        """
        Initialize the bug auto-approver.

        Args:
            bug_store: Bug store for accessing bug state.
            event_logger: Event logger for audit trail.
        """
        self._bug_store = bug_store
        self._logger = event_logger

    def should_auto_approve(self, bug_id: str) -> tuple[bool, str]:
        """
        Check if bug fix should be auto-approved.

        High-risk bugs always require manual review.

        Args:
            bug_id: The bug identifier.

        Returns:
            Tuple of (should_approve, reason).
        """
        bug_state = self._bug_store.get(bug_id)
        if bug_state is None:
            return False, "Bug not found"

        fix_plan = bug_state.fix_plan
        if not fix_plan:
            return False, "No fix plan available"

        # Risk level check
        risk_level = getattr(fix_plan, "risk_level", "unknown")
        if risk_level not in self.ALLOWED_RISK_LEVELS:
            return False, f"Risk level '{risk_level}' requires manual review"

        # Confidence check
        confidence = getattr(fix_plan, "confidence", 0.0)
        if confidence < self.CONFIDENCE_THRESHOLD:
            return False, f"Confidence {confidence:.2f} below threshold {self.CONFIDENCE_THRESHOLD}"

        # Breaking changes require manual review
        if getattr(fix_plan, "breaks_api", False):
            return False, "API-breaking changes require manual review"

        if getattr(fix_plan, "requires_migration", False):
            return False, "Migration required - needs manual review"

        return True, f"Auto-approved: {confidence:.2f} confidence, {risk_level} risk"

    def _get_confidence(self, bug_id: str) -> float:
        """Get confidence level from bug fix plan."""
        bug_state = self._bug_store.get(bug_id)
        if bug_state and bug_state.fix_plan:
            return getattr(bug_state.fix_plan, "confidence", 0.0)
        return 0.0

    def auto_approve_if_ready(self, bug_id: str) -> ApprovalResult:
        """
        Check and auto-approve if conditions met.

        Args:
            bug_id: The bug identifier.

        Returns:
            ApprovalResult with approval status and reason.
        """
        should, reason = self.should_auto_approve(bug_id)

        if not should:
            return ApprovalResult(approved=False, reason=reason)

        self._bug_store.approve_fix(bug_id)
        self._logger.log_auto_approval("bug_fix", bug_id, reason)

        return ApprovalResult(
            approved=True,
            reason=reason,
            confidence=self._get_confidence(bug_id),
        )
