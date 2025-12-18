"""CheckpointSystem for autopilot trigger detection.

Detects when autopilot should pause for human intervention based on:
- Cost thresholds
- Time/duration limits
- Error streaks
- Approval requirements
- High-risk actions
"""

from dataclasses import dataclass
from typing import Any, Optional

from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


@dataclass
class CheckpointTrigger:
    """Represents a trigger that caused autopilot to pause."""

    trigger_type: str
    reason: str
    action: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointTrigger":
        """Create CheckpointTrigger from dictionary."""
        return cls(
            trigger_type=data.get("trigger_type", ""),
            reason=data.get("reason", ""),
            action=data.get("action", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert CheckpointTrigger to dictionary."""
        return {
            "trigger_type": self.trigger_type,
            "reason": self.reason,
            "action": self.action,
        }


class CheckpointSystem:
    """Detects when autopilot should pause for human intervention.

    Checks triggers in order:
    1. stop_trigger - User-specified --until trigger
    2. cost - Budget exceeded
    3. time - Duration exceeded
    4. approval - Action needs human approval
    5. high_risk - Risky operation detected
    6. errors - Error streak exceeded
    7. blocker - Session is blocked
    """

    # High-risk action patterns
    HIGH_RISK_PATTERNS = [
        "architect",
        "main branch",
        "master",
        "merge to main",
        "push to main",
        "push to master",
        "delete",
        "drop",
        "rm -rf",
        "force push",
        "destructive",
    ]

    # Approval-required patterns
    APPROVAL_PATTERNS = [
        "approve",
        "approval",
        "confirm",
        "confirmation",
        "review",
    ]

    def __init__(self, config: ChiefOfStaffConfig) -> None:
        """Initialize CheckpointSystem with configuration.

        Args:
            config: ChiefOfStaffConfig with threshold settings
        """
        self.config = config
        self._error_count = 0

    def check_triggers(
        self, session: Any, current_action: str
    ) -> Optional[CheckpointTrigger]:
        """Check all triggers and return first match.

        Triggers are checked in order: stop_trigger, cost, time,
        approval, high_risk, errors, blocker.

        Args:
            session: Session object with cost, time, and state info
            current_action: Current action being performed

        Returns:
            CheckpointTrigger if a trigger matched, None otherwise
        """
        # 1. Check stop trigger (--until)
        if self.matches_stop_trigger(session, current_action):
            return CheckpointTrigger(
                trigger_type="stop_trigger",
                reason=f"Reached stop trigger: {session.stop_trigger}",
                action="pause_for_user",
            )

        # 2. Check cost
        if hasattr(session, "total_cost_usd") and self.config.budget_usd is not None:
            if session.total_cost_usd > self.config.budget_usd:
                return CheckpointTrigger(
                    trigger_type="cost",
                    reason=f"Cost ${session.total_cost_usd:.2f} exceeds budget ${self.config.budget_usd:.2f}",
                    action="pause_for_user",
                )

        # 3. Check time/duration
        if hasattr(session, "elapsed_minutes") and self.config.duration_minutes is not None:
            if session.elapsed_minutes > self.config.duration_minutes:
                return CheckpointTrigger(
                    trigger_type="time",
                    reason=f"Duration {session.elapsed_minutes}m exceeds limit {self.config.duration_minutes}m",
                    action="pause_for_user",
                )

        # 4. Check approval requirement
        if self.should_pause_for_approval(current_action):
            return CheckpointTrigger(
                trigger_type="approval",
                reason=f"Action requires approval: {current_action}",
                action="request_approval",
            )

        # 5. Check high-risk
        if self.is_high_risk(current_action):
            return CheckpointTrigger(
                trigger_type="high_risk",
                reason=f"High-risk action detected: {current_action}",
                action="require_confirmation",
            )

        # 6. Check error streak
        if self.config.error_streak is not None and self._error_count >= self.config.error_streak:
            return CheckpointTrigger(
                trigger_type="errors",
                reason=f"Error streak {self._error_count} exceeds threshold {self.config.error_streak}",
                action="pause_for_investigation",
            )

        # 7. Check blocker
        if hasattr(session, "is_blocked") and session.is_blocked:
            return CheckpointTrigger(
                trigger_type="blocker",
                reason="Session is blocked",
                action="pause_for_resolution",
            )

        return None

    def matches_stop_trigger(self, session: Any, current_action: str) -> bool:
        """Check if current action matches the session's stop trigger.

        Args:
            session: Session object with optional stop_trigger attribute
            current_action: Current action being performed

        Returns:
            True if action matches stop trigger, False otherwise
        """
        if not hasattr(session, "stop_trigger") or session.stop_trigger is None:
            return False

        trigger = session.stop_trigger.lower()
        action = current_action.lower()

        return trigger in action

    def is_high_risk(self, action: str) -> bool:
        """Check if action is high-risk.

        High-risk actions include:
        - Architectural changes
        - Main/master branch operations
        - Destructive operations (delete, drop, rm -rf)
        - Force push

        Args:
            action: Action string to check

        Returns:
            True if action is high-risk, False otherwise
        """
        action_lower = action.lower()

        for pattern in self.HIGH_RISK_PATTERNS:
            if pattern in action_lower:
                return True

        return False

    def record_error(self) -> None:
        """Record an error, incrementing the error count."""
        self._error_count += 1

    def reset_error_count(self) -> None:
        """Reset error count to zero after successful operation."""
        self._error_count = 0

    def should_pause_for_approval(self, action: str) -> bool:
        """Check if action requires human approval.

        Actions requiring approval include those with:
        - approve/approval
        - confirm/confirmation
        - review

        Args:
            action: Action string to check

        Returns:
            True if action needs approval, False otherwise
        """
        action_lower = action.lower()

        for pattern in self.APPROVAL_PATTERNS:
            if pattern in action_lower:
                return True

        return False