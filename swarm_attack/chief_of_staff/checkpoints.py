"""CheckpointSystem for detecting and handling checkpoint triggers."""

from typing import Optional

from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.models import AutopilotSession, CheckpointTrigger


class CheckpointSystem:
    """Detects and handles checkpoint triggers."""

    def __init__(self, config: ChiefOfStaffConfig) -> None:
        """Initialize with configuration."""
        self._config = config
        self._error_count = 0

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
        action_lower = current_action.lower()

        # Check if stop_trigger matches any condition that would fire
        if session.stop_trigger is not None:
            # Check if the stop trigger condition is met
            if session.stop_trigger == CheckpointTrigger.APPROVAL_REQUIRED:
                if self.should_pause_for_approval(current_action):
                    return CheckpointTrigger.APPROVAL_REQUIRED
            elif session.stop_trigger == CheckpointTrigger.HIGH_RISK_ACTION:
                if self.is_high_risk(current_action):
                    return CheckpointTrigger.HIGH_RISK_ACTION
            elif session.stop_trigger == CheckpointTrigger.COST_THRESHOLD:
                if session.cost_spent_usd >= session.budget_usd:
                    return CheckpointTrigger.COST_THRESHOLD
            elif session.stop_trigger == CheckpointTrigger.TIME_THRESHOLD:
                if session.duration_seconds >= session.duration_limit_seconds:
                    return CheckpointTrigger.TIME_THRESHOLD
            elif session.stop_trigger == CheckpointTrigger.ERROR_RATE_SPIKE:
                error_threshold = self._config.checkpoints.error_streak
                if self._error_count >= error_threshold:
                    return CheckpointTrigger.ERROR_RATE_SPIKE
            elif session.stop_trigger == CheckpointTrigger.BLOCKER_DETECTED:
                if self._is_blocker(action_lower):
                    return CheckpointTrigger.BLOCKER_DETECTED

        # Check cost threshold
        if session.cost_spent_usd >= session.budget_usd:
            return CheckpointTrigger.COST_THRESHOLD

        # Check time threshold
        if session.duration_seconds >= session.duration_limit_seconds:
            return CheckpointTrigger.TIME_THRESHOLD

        # Check approval required
        if self.should_pause_for_approval(current_action):
            return CheckpointTrigger.APPROVAL_REQUIRED

        # Check high risk action
        if self.is_high_risk(current_action):
            return CheckpointTrigger.HIGH_RISK_ACTION

        # Check error rate spike
        error_threshold = self._config.checkpoints.error_streak
        if self._error_count >= error_threshold:
            return CheckpointTrigger.ERROR_RATE_SPIKE

        # Check blocker detected
        if self._is_blocker(action_lower):
            return CheckpointTrigger.BLOCKER_DETECTED

        return None

    def _is_blocker(self, action_lower: str) -> bool:
        """Check if action indicates a blocker."""
        # Check for exact "blocked:" prefix first
        if action_lower.startswith("blocked:"):
            return True
        # Check for "cannot proceed"
        if "cannot proceed" in action_lower:
            return True
        # Check for "need human input"
        if "need human input" in action_lower:
            return True
        return False

    def matches_stop_trigger(
        self,
        session: AutopilotSession,
        trigger: CheckpointTrigger,
    ) -> bool:
        """Check if trigger matches the session's --until stop trigger."""
        if session.stop_trigger is None:
            return False
        return session.stop_trigger == trigger

    def is_high_risk(self, action: str) -> bool:
        """Check if an action is high-risk."""
        action_lower = action.lower()

        # Push to main/master
        if "push" in action_lower and ("main" in action_lower or "master" in action_lower):
            return True

        # Schema changes
        if "schema" in action_lower:
            return True

        # Delete operations
        if "delete" in action_lower:
            return True

        # Remove operations (also high risk)
        if "remove" in action_lower:
            return True

        return False

    def record_error(self) -> None:
        """Record an error for spike detection."""
        self._error_count += 1

    def reset_error_count(self) -> None:
        """Reset error count after success."""
        self._error_count = 0

    def should_pause_for_approval(self, action: str) -> bool:
        """Check if action requires human approval."""
        action_lower = action.lower()

        # Check for "approve" keyword
        if "approve" in action_lower:
            return True

        # Check for "approval" keyword
        if "approval" in action_lower:
            return True

        return False