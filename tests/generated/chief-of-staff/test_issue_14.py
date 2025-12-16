"""Tests for --until trigger support in CheckpointSystem."""

import pytest
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.models import (
    AutopilotSession,
    CheckpointTrigger,
    DailyGoal,
    GoalStatus,
)


class TestMatchesStopTrigger:
    """Tests for matches_stop_trigger method."""

    def test_matches_stop_trigger_exists(self):
        """Verify matches_stop_trigger method exists."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        assert hasattr(checkpoint_system, "matches_stop_trigger")
        assert callable(checkpoint_system.matches_stop_trigger)

    def test_matches_stop_trigger_returns_false_when_no_stop_trigger(self):
        """Returns False when session has no stop_trigger set."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
            stop_trigger=None,
        )
        result = checkpoint_system.matches_stop_trigger(
            session, CheckpointTrigger.COST_THRESHOLD
        )
        assert result is False

    def test_matches_stop_trigger_returns_true_when_trigger_matches(self):
        """Returns True when trigger matches session's stop_trigger."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
        )
        result = checkpoint_system.matches_stop_trigger(
            session, CheckpointTrigger.APPROVAL_REQUIRED
        )
        assert result is True

    def test_matches_stop_trigger_returns_false_when_trigger_does_not_match(self):
        """Returns False when trigger does not match session's stop_trigger."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
            stop_trigger=CheckpointTrigger.COST_THRESHOLD,
        )
        result = checkpoint_system.matches_stop_trigger(
            session, CheckpointTrigger.APPROVAL_REQUIRED
        )
        assert result is False

    def test_matches_stop_trigger_for_all_trigger_types(self):
        """Test matches_stop_trigger works for all CheckpointTrigger types."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        
        for trigger_type in CheckpointTrigger:
            session = AutopilotSession(
                session_id=f"test-session-{trigger_type.value}",
                started_at="2025-01-01T10:00:00",
                budget_usd=10.0,
                duration_limit_seconds=3600,
                stop_trigger=trigger_type,
            )
            # Should match itself
            assert checkpoint_system.matches_stop_trigger(session, trigger_type) is True
            # Should not match a different trigger
            other_trigger = CheckpointTrigger.END_OF_SESSION
            if trigger_type != CheckpointTrigger.END_OF_SESSION:
                assert checkpoint_system.matches_stop_trigger(session, other_trigger) is False


class TestStopTriggerInAutopilotSession:
    """Tests for stop_trigger field in AutopilotSession."""

    def test_autopilot_session_has_stop_trigger_field(self):
        """Verify AutopilotSession has stop_trigger field."""
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
        )
        assert hasattr(session, "stop_trigger")

    def test_stop_trigger_default_is_none(self):
        """stop_trigger defaults to None."""
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
        )
        assert session.stop_trigger is None

    def test_stop_trigger_can_be_set(self):
        """stop_trigger can be set to a CheckpointTrigger."""
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
            stop_trigger=CheckpointTrigger.HIGH_RISK_ACTION,
        )
        assert session.stop_trigger == CheckpointTrigger.HIGH_RISK_ACTION

    def test_stop_trigger_serialization_roundtrip(self):
        """stop_trigger is correctly serialized and deserialized."""
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
            stop_trigger=CheckpointTrigger.BLOCKER_DETECTED,
        )
        data = session.to_dict()
        assert data["stop_trigger"] == CheckpointTrigger.BLOCKER_DETECTED.value
        
        restored = AutopilotSession.from_dict(data)
        assert restored.stop_trigger == CheckpointTrigger.BLOCKER_DETECTED

    def test_stop_trigger_serialization_when_none(self):
        """stop_trigger serializes correctly when None."""
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
            stop_trigger=None,
        )
        data = session.to_dict()
        assert data["stop_trigger"] is None
        
        restored = AutopilotSession.from_dict(data)
        assert restored.stop_trigger is None


class TestCheckTriggersWithStopTrigger:
    """Tests for check_triggers with --until stop trigger support."""

    def test_check_triggers_returns_stop_trigger_when_approval_required_matches(self):
        """check_triggers returns stop trigger first when approval action matches."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,  # High budget, won't trigger cost
            duration_limit_seconds=36000,  # Long duration, won't trigger time
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
        )
        # Action that requires approval
        result = checkpoint_system.check_triggers(session, "approve deployment")
        assert result == CheckpointTrigger.APPROVAL_REQUIRED

    def test_check_triggers_returns_stop_trigger_when_high_risk_matches(self):
        """check_triggers returns stop trigger first when high risk action matches."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.HIGH_RISK_ACTION,
        )
        # Action that is high risk (push to main)
        result = checkpoint_system.check_triggers(session, "push to main")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION

    def test_check_triggers_returns_stop_trigger_when_cost_threshold_matches(self):
        """check_triggers returns stop trigger when cost exceeds budget."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=36000,
            cost_spent_usd=15.0,  # Over budget
            stop_trigger=CheckpointTrigger.COST_THRESHOLD,
        )
        result = checkpoint_system.check_triggers(session, "normal action")
        assert result == CheckpointTrigger.COST_THRESHOLD

    def test_check_triggers_returns_stop_trigger_when_time_threshold_matches(self):
        """check_triggers returns stop trigger when time exceeds limit."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=3600,
            duration_seconds=4000,  # Over time limit
            stop_trigger=CheckpointTrigger.TIME_THRESHOLD,
        )
        result = checkpoint_system.check_triggers(session, "normal action")
        assert result == CheckpointTrigger.TIME_THRESHOLD

    def test_check_triggers_returns_stop_trigger_when_error_rate_matches(self):
        """check_triggers returns stop trigger when error streak is high."""
        config = ChiefOfStaffConfig()
        config.checkpoints.error_streak = 3
        checkpoint_system = CheckpointSystem(config)
        # Record enough errors to trigger
        checkpoint_system.record_error()
        checkpoint_system.record_error()
        checkpoint_system.record_error()
        
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.ERROR_RATE_SPIKE,
        )
        result = checkpoint_system.check_triggers(session, "normal action")
        assert result == CheckpointTrigger.ERROR_RATE_SPIKE

    def test_check_triggers_returns_stop_trigger_when_blocker_detected(self):
        """check_triggers returns stop trigger when blocker is detected."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.BLOCKER_DETECTED,
        )
        result = checkpoint_system.check_triggers(session, "blocked: need credentials")
        assert result == CheckpointTrigger.BLOCKER_DETECTED

    def test_check_triggers_does_not_return_stop_trigger_when_condition_not_met(self):
        """check_triggers does not return stop trigger if condition not met."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
        )
        # Normal action that doesn't require approval
        result = checkpoint_system.check_triggers(session, "run tests")
        # Should return None because the stop_trigger condition is not met
        # and no other trigger conditions are met either
        assert result is None

    def test_check_triggers_returns_none_when_no_stop_trigger_and_no_conditions(self):
        """check_triggers returns None when no stop trigger and no conditions met."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=None,
        )
        result = checkpoint_system.check_triggers(session, "normal action")
        assert result is None

    def test_check_triggers_evaluates_stop_trigger_before_other_triggers(self):
        """Verify stop trigger is checked before other triggers."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=36000,
            cost_spent_usd=15.0,  # Over budget - would trigger COST_THRESHOLD
            stop_trigger=CheckpointTrigger.COST_THRESHOLD,  # Stop trigger set
        )
        # Both stop_trigger and normal COST_THRESHOLD would fire
        # Stop trigger should return first (same result in this case)
        result = checkpoint_system.check_triggers(session, "normal action")
        assert result == CheckpointTrigger.COST_THRESHOLD

    def test_check_triggers_without_stop_trigger_still_triggers_normally(self):
        """Normal triggers still fire when no stop_trigger is set."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=36000,
            cost_spent_usd=15.0,  # Over budget
            stop_trigger=None,  # No stop trigger
        )
        result = checkpoint_system.check_triggers(session, "normal action")
        assert result == CheckpointTrigger.COST_THRESHOLD


class TestStopTriggerEdgeCases:
    """Edge case tests for --until stop trigger functionality."""

    def test_stop_trigger_cannot_proceed_blocker(self):
        """Blocker trigger fires on 'cannot proceed' message."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.BLOCKER_DETECTED,
        )
        result = checkpoint_system.check_triggers(
            session, "We cannot proceed without API keys"
        )
        assert result == CheckpointTrigger.BLOCKER_DETECTED

    def test_stop_trigger_need_human_input_blocker(self):
        """Blocker trigger fires on 'need human input' message."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.BLOCKER_DETECTED,
        )
        result = checkpoint_system.check_triggers(
            session, "need human input for this decision"
        )
        assert result == CheckpointTrigger.BLOCKER_DETECTED

    def test_stop_trigger_delete_high_risk(self):
        """High risk trigger fires on delete operations."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.HIGH_RISK_ACTION,
        )
        result = checkpoint_system.check_triggers(session, "delete user data")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION

    def test_stop_trigger_schema_high_risk(self):
        """High risk trigger fires on schema changes."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.HIGH_RISK_ACTION,
        )
        result = checkpoint_system.check_triggers(session, "modify database schema")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION

    def test_stop_trigger_approval_keyword(self):
        """Approval trigger fires on 'approval' keyword."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session = AutopilotSession(
            session_id="test-session",
            started_at="2025-01-01T10:00:00",
            budget_usd=100.0,
            duration_limit_seconds=36000,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
        )
        result = checkpoint_system.check_triggers(session, "waiting for approval")
        assert result == CheckpointTrigger.APPROVAL_REQUIRED