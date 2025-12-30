"""Tests for CheckpointSystem - autopilot trigger detection."""

import pytest
from unittest.mock import MagicMock
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointTrigger
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


class TestCheckpointSystemInit:
    """Tests for CheckpointSystem initialization."""

    def test_init_with_config(self):
        """CheckpointSystem should initialize with config."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        assert system.config == config

    def test_init_sets_error_count_to_zero(self):
        """CheckpointSystem should start with zero errors."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        assert system._error_count == 0


class TestCheckTriggers:
    """Tests for check_triggers method."""

    def test_returns_none_when_no_triggers_match(self):
        """Should return None when no triggers match."""
        config = ChiefOfStaffConfig(budget_usd=100.0, duration_minutes=60)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 10.0
        session.elapsed_minutes = 5
        session.stop_trigger = None
        session.is_blocked = False  # Explicitly set to avoid MagicMock truthy value

        result = system.check_triggers(session, "simple action")
        assert result is None

    def test_returns_stop_trigger_first(self):
        """Stop trigger should be checked first."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = "implement feature"
        session.total_cost_usd = 1000.0  # Over budget but stop trigger takes priority
        
        result = system.check_triggers(session, "implement feature")
        assert result is not None
        assert result.trigger_type == "stop_trigger"

    def test_returns_cost_trigger_when_over_budget(self):
        """Should trigger when cost exceeds budget."""
        config = ChiefOfStaffConfig(budget_usd=50.0)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 55.0
        session.elapsed_minutes = 5
        session.stop_trigger = None
        
        result = system.check_triggers(session, "any action")
        assert result is not None
        assert result.trigger_type == "cost"

    def test_returns_time_trigger_when_over_duration(self):
        """Should trigger when time exceeds duration."""
        config = ChiefOfStaffConfig(budget_usd=100.0, duration_minutes=30)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 10.0
        session.elapsed_minutes = 35
        session.stop_trigger = None
        
        result = system.check_triggers(session, "any action")
        assert result is not None
        assert result.trigger_type == "time"

    def test_returns_approval_trigger_for_approval_action(self):
        """Should trigger for actions needing approval."""
        config = ChiefOfStaffConfig(budget_usd=100.0, duration_minutes=60)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 10.0
        session.elapsed_minutes = 5
        session.stop_trigger = None
        
        result = system.check_triggers(session, "approve deployment")
        assert result is not None
        assert result.trigger_type == "approval"

    def test_returns_high_risk_trigger_for_risky_action(self):
        """Should trigger for high-risk actions."""
        config = ChiefOfStaffConfig(budget_usd=100.0, duration_minutes=60)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 10.0
        session.elapsed_minutes = 5
        session.stop_trigger = None
        
        result = system.check_triggers(session, "push to main branch")
        assert result is not None
        assert result.trigger_type == "high_risk"

    def test_returns_errors_trigger_when_streak_exceeded(self):
        """Should trigger when error streak exceeds threshold."""
        config = ChiefOfStaffConfig(budget_usd=100.0, duration_minutes=60, error_streak=3)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 10.0
        session.elapsed_minutes = 5
        session.stop_trigger = None
        
        # Record errors to exceed streak
        system.record_error()
        system.record_error()
        system.record_error()
        
        result = system.check_triggers(session, "any action")
        assert result is not None
        assert result.trigger_type == "errors"

    def test_returns_blocker_trigger_when_session_blocked(self):
        """Should trigger when session is blocked."""
        config = ChiefOfStaffConfig(budget_usd=100.0, duration_minutes=60)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.total_cost_usd = 10.0
        session.elapsed_minutes = 5
        session.stop_trigger = None
        session.is_blocked = True
        
        result = system.check_triggers(session, "any action")
        assert result is not None
        assert result.trigger_type == "blocker"


class TestMatchesStopTrigger:
    """Tests for matches_stop_trigger method."""

    def test_returns_false_when_no_stop_trigger(self):
        """Should return False when session has no stop trigger."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = None
        
        result = system.matches_stop_trigger(session, "any action")
        assert result is False

    def test_returns_true_when_action_matches_trigger(self):
        """Should return True when action matches stop trigger."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = "implement feature"
        
        result = system.matches_stop_trigger(session, "implement feature")
        assert result is True

    def test_returns_true_when_action_contains_trigger(self):
        """Should return True when action contains stop trigger."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = "deploy"
        
        result = system.matches_stop_trigger(session, "deploy to production")
        assert result is True

    def test_returns_false_when_action_does_not_match(self):
        """Should return False when action doesn't match trigger."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = "deploy"
        
        result = system.matches_stop_trigger(session, "run tests")
        assert result is False

    def test_case_insensitive_matching(self):
        """Should match case-insensitively."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = "Deploy"
        
        result = system.matches_stop_trigger(session, "DEPLOY to production")
        assert result is True


class TestIsHighRisk:
    """Tests for is_high_risk method."""

    def test_architectural_changes_are_high_risk(self):
        """Architectural changes should be high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("refactor architecture") is True
        assert system.is_high_risk("architectural redesign") is True

    def test_main_branch_push_is_high_risk(self):
        """Pushing to main branch should be high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("push to main branch") is True
        assert system.is_high_risk("push to master") is True
        assert system.is_high_risk("merge to main") is True

    def test_destructive_operations_are_high_risk(self):
        """Destructive operations should be high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("delete database") is True
        assert system.is_high_risk("drop table users") is True
        assert system.is_high_risk("rm -rf directory") is True
        assert system.is_high_risk("force push") is True

    def test_normal_actions_are_not_high_risk(self):
        """Normal actions should not be high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("run tests") is False
        assert system.is_high_risk("add feature") is False
        assert system.is_high_risk("fix bug") is False


class TestRecordError:
    """Tests for record_error method."""

    def test_increments_error_count(self):
        """Should increment error count."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system._error_count == 0
        system.record_error()
        assert system._error_count == 1
        system.record_error()
        assert system._error_count == 2

    def test_multiple_errors_accumulate(self):
        """Multiple errors should accumulate."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        for _ in range(5):
            system.record_error()
        
        assert system._error_count == 5


class TestResetErrorCount:
    """Tests for reset_error_count method."""

    def test_resets_to_zero(self):
        """Should reset error count to zero."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        system.record_error()
        system.record_error()
        system.record_error()
        assert system._error_count == 3
        
        system.reset_error_count()
        assert system._error_count == 0

    def test_reset_from_zero_stays_zero(self):
        """Resetting from zero should stay at zero."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system._error_count == 0
        system.reset_error_count()
        assert system._error_count == 0


class TestShouldPauseForApproval:
    """Tests for should_pause_for_approval method."""

    def test_approve_actions_need_approval(self):
        """Actions with 'approve' should need approval."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("approve deployment") is True
        assert system.should_pause_for_approval("needs approval") is True

    def test_confirm_actions_need_approval(self):
        """Actions with 'confirm' should need approval."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("confirm changes") is True
        assert system.should_pause_for_approval("confirmation required") is True

    def test_review_actions_need_approval(self):
        """Actions with 'review' should need approval."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("review pr") is True
        assert system.should_pause_for_approval("code review needed") is True

    def test_normal_actions_dont_need_approval(self):
        """Normal actions should not need approval."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("run tests") is False
        assert system.should_pause_for_approval("implement feature") is False


class TestTriggerOrder:
    """Tests for trigger checking order."""

    def test_stop_trigger_checked_before_cost(self):
        """Stop trigger should be checked before cost."""
        config = ChiefOfStaffConfig(budget_usd=10.0)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = "deploy"
        session.total_cost_usd = 100.0  # Over budget
        session.elapsed_minutes = 5
        
        result = system.check_triggers(session, "deploy now")
        assert result.trigger_type == "stop_trigger"

    def test_cost_checked_before_time(self):
        """Cost should be checked before time."""
        config = ChiefOfStaffConfig(budget_usd=10.0, duration_minutes=10)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = None
        session.total_cost_usd = 100.0  # Over budget
        session.elapsed_minutes = 100  # Also over time
        
        result = system.check_triggers(session, "any action")
        assert result.trigger_type == "cost"

    def test_time_checked_before_approval(self):
        """Time should be checked before approval."""
        config = ChiefOfStaffConfig(budget_usd=1000.0, duration_minutes=10)
        system = CheckpointSystem(config)
        session = MagicMock()
        session.stop_trigger = None
        session.total_cost_usd = 5.0
        session.elapsed_minutes = 100  # Over time
        
        result = system.check_triggers(session, "approve something")
        assert result.trigger_type == "time"


class TestCheckpointTrigger:
    """Tests for CheckpointTrigger dataclass."""

    def test_trigger_has_required_fields(self):
        """CheckpointTrigger should have required fields."""
        trigger = CheckpointTrigger(
            trigger_type="cost",
            reason="Budget exceeded",
            action="pause session"
        )
        
        assert trigger.trigger_type == "cost"
        assert trigger.reason == "Budget exceeded"
        assert trigger.action == "pause session"

    def test_trigger_from_dict(self):
        """CheckpointTrigger should be creatable from dict."""
        data = {
            "trigger_type": "time",
            "reason": "Duration exceeded",
            "action": "notify user"
        }
        trigger = CheckpointTrigger.from_dict(data)
        
        assert trigger.trigger_type == "time"
        assert trigger.reason == "Duration exceeded"
        assert trigger.action == "notify user"

    def test_trigger_to_dict(self):
        """CheckpointTrigger should be convertible to dict."""
        trigger = CheckpointTrigger(
            trigger_type="errors",
            reason="Too many errors",
            action="stop execution"
        )
        data = trigger.to_dict()
        
        assert data["trigger_type"] == "errors"
        assert data["reason"] == "Too many errors"
        assert data["action"] == "stop execution"

    def test_trigger_roundtrip(self):
        """CheckpointTrigger should roundtrip through dict."""
        original = CheckpointTrigger(
            trigger_type="high_risk",
            reason="Risky operation",
            action="require approval"
        )
        roundtrip = CheckpointTrigger.from_dict(original.to_dict())
        
        assert roundtrip.trigger_type == original.trigger_type
        assert roundtrip.reason == original.reason
        assert roundtrip.action == original.action