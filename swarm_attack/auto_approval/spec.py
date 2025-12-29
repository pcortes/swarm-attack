"""
Spec Auto-Approver for Feature Swarm.

Automatically approves specs when critic score meets threshold
for consecutive rounds.

Replaces manual `swarm-attack approve` command when conditions are met.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Any

from swarm_attack.auto_approval.models import ApprovalResult

if TYPE_CHECKING:
    from swarm_attack.event_logger import EventLogger


class DebateScoreProtocol(Protocol):
    """Protocol for debate score objects."""
    @property
    def average(self) -> float: ...


class RunStateProtocol(Protocol):
    """Protocol for run state objects."""
    debate_scores: list[Any]
    manual_mode: bool


class StateStoreProtocol(Protocol):
    """Protocol for state store operations."""
    def get_run_state(self, feature_id: str) -> RunStateProtocol | None: ...
    def approve_spec(self, feature_id: str) -> None: ...
    def is_manual_mode(self, feature_id: str) -> bool: ...


class SpecAutoApprover:
    """
    Replace manual `swarm-attack approve` command.

    Auto-approves specs when:
    - Score >= 0.85 for at least 2 consecutive debate rounds
    - Manual mode is not enabled

    This allows the spec debate to automatically proceed to issue creation
    when quality thresholds are met.
    """

    APPROVAL_THRESHOLD = 0.85
    REQUIRED_ROUNDS = 2

    def __init__(
        self,
        state_store: StateStoreProtocol,
        event_logger: "EventLogger",
    ) -> None:
        """
        Initialize the spec auto-approver.

        Args:
            state_store: State store for accessing feature state.
            event_logger: Event logger for audit trail.
        """
        self._state_store = state_store
        self._logger = event_logger

    def should_auto_approve(self, feature_id: str) -> tuple[bool, str]:
        """
        Check if spec should be auto-approved.

        Args:
            feature_id: The feature identifier.

        Returns:
            Tuple of (should_approve, reason).
        """
        run_state = self._state_store.get_run_state(feature_id)
        if run_state is None:
            return False, "Feature state not found"

        scores = run_state.debate_scores or []

        # Need 2+ consecutive rounds above threshold
        if len(scores) < self.REQUIRED_ROUNDS:
            return False, f"Need {self.REQUIRED_ROUNDS} debate rounds, have {len(scores)}"

        recent = scores[-self.REQUIRED_ROUNDS:]

        # Check if all recent rounds meet threshold
        if all(self._get_average(s) >= self.APPROVAL_THRESHOLD for s in recent):
            avg = self._get_average(recent[-1])
            return True, f"Auto-approved: {avg:.2f} score for {self.REQUIRED_ROUNDS} rounds"

        avg = self._get_average(recent[-1])
        return False, f"Score {avg:.2f} below threshold {self.APPROVAL_THRESHOLD}"

    def _get_average(self, score: Any) -> float:
        """Get average score from a debate score object."""
        if hasattr(score, "average"):
            return score.average
        # Fallback for dict-like objects
        if hasattr(score, "__getitem__"):
            try:
                values = [score["clarity"], score["coverage"], score["architecture"], score["risk"]]
                return sum(values) / len(values)
            except (KeyError, TypeError):
                pass
        return 0.0

    def _is_manual_mode(self, feature_id: str) -> bool:
        """Check if manual mode is enabled for this feature."""
        return self._state_store.is_manual_mode(feature_id)

    def auto_approve_if_ready(self, feature_id: str) -> ApprovalResult:
        """
        Check and auto-approve if conditions met.

        Called after each spec debate round.

        Args:
            feature_id: The feature identifier.

        Returns:
            ApprovalResult with approval status and reason.
        """
        # Check for manual mode override first
        if self._is_manual_mode(feature_id):
            return ApprovalResult(approved=False, reason="Manual mode enabled")

        should, reason = self.should_auto_approve(feature_id)

        if not should:
            return ApprovalResult(approved=False, reason=reason)

        # Perform approval
        self._state_store.approve_spec(feature_id)
        self._logger.log_auto_approval("spec", feature_id, reason)

        return ApprovalResult(approved=True, reason=reason)
