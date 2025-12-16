"""Tests for CheckpointSystem.

These tests verify the CheckpointSystem component that detects and handles
checkpoint triggers during autopilot execution.

Tests will FAIL until the Coder implements swarm_attack/chief_of_staff/checkpoints.py
"""

import pytest
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

# Import from real module paths - these will fail until Coder creates them
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig, CheckpointConfig
from swarm_attack.chief_of_staff.models import (
    AutopilotSession,
    CheckpointTrigger,
    DailyGoal,
    GoalStatus,
)


class TestCheckTriggersBasic:
    """Tests for check_triggers() method - basic trigger detection."""

    def test_returns_none_when_no_triggers_fire(self):
        """Test that check_triggers returns None when all conditions are within limits."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,  # Well under budget
            duration_seconds=600,  # Well under time limit
        )
        
        result = system.check_triggers(session, "write tests")
        assert result is None

    def test_cost_threshold_trigger_fires_when_budget_exceeded(self):
        """Test COST_THRESHOLD trigger fires when cost >= budget."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=10.0,  # At budget limit
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.COST_THRESHOLD

    def test_cost_threshold_trigger_fires_when_budget_exceeded_over(self):
        """Test COST_THRESHOLD trigger fires when cost > budget."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=15.0,  # Over budget
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.COST_THRESHOLD

    def test_time_threshold_trigger_fires_when_duration_exceeded(self):
        """Test TIME_THRESHOLD trigger fires when duration >= limit."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,  # 2 hours
            cost_spent_usd=1.0,
            duration_seconds=7200,  # At time limit
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.TIME_THRESHOLD

    def test_time_threshold_trigger_fires_when_duration_exceeded_over(self):
        """Test TIME_THRESHOLD trigger fires when duration > limit."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=8000,  # Over time limit
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.TIME_THRESHOLD


class TestCheckTriggersApproval:
    """Tests for APPROVAL_REQUIRED trigger detection."""

    def test_approval_required_trigger_for_spec_approval(self):
        """Test APPROVAL_REQUIRED fires for spec approval actions."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "approve spec")
        assert result == CheckpointTrigger.APPROVAL_REQUIRED

    def test_approval_required_trigger_for_fix_plan_approval(self):
        """Test APPROVAL_REQUIRED fires for fix plan approval actions."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "approve fix plan")
        assert result == CheckpointTrigger.APPROVAL_REQUIRED


class TestCheckTriggersHighRisk:
    """Tests for HIGH_RISK_ACTION trigger detection."""

    def test_high_risk_trigger_for_push_to_main(self):
        """Test HIGH_RISK_ACTION fires for push to main branch."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "push to main")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION

    def test_high_risk_trigger_for_schema_changes(self):
        """Test HIGH_RISK_ACTION fires for schema change actions."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "modify database schema")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION

    def test_high_risk_trigger_for_delete_operations(self):
        """Test HIGH_RISK_ACTION fires for delete operations."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "delete user data")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION


class TestCheckTriggersErrorRate:
    """Tests for ERROR_RATE_SPIKE trigger detection."""

    def test_error_rate_spike_after_three_consecutive_errors(self):
        """Test ERROR_RATE_SPIKE fires after 3+ consecutive failures."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # Record 3 errors
        system.record_error()
        system.record_error()
        system.record_error()
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "run tests")
        assert result == CheckpointTrigger.ERROR_RATE_SPIKE

    def test_error_rate_does_not_trigger_with_two_errors(self):
        """Test ERROR_RATE_SPIKE does not fire with only 2 errors."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # Record only 2 errors
        system.record_error()
        system.record_error()
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "run tests")
        assert result is None

    def test_error_count_resets_after_success(self):
        """Test that error count resets after calling reset_error_count."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # Record 3 errors then reset
        system.record_error()
        system.record_error()
        system.record_error()
        system.reset_error_count()
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "run tests")
        assert result is None


class TestMatchesStopTrigger:
    """Tests for matches_stop_trigger() method."""

    def test_matches_when_stop_trigger_matches_current_trigger(self):
        """Test returns True when --until trigger matches current state."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
        )
        
        result = system.matches_stop_trigger(session, CheckpointTrigger.APPROVAL_REQUIRED)
        assert result is True

    def test_does_not_match_when_triggers_differ(self):
        """Test returns False when --until trigger differs from current."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
        )
        
        result = system.matches_stop_trigger(session, CheckpointTrigger.COST_THRESHOLD)
        assert result is False

    def test_does_not_match_when_no_stop_trigger_set(self):
        """Test returns False when session has no --until trigger set."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=None,
        )
        
        result = system.matches_stop_trigger(session, CheckpointTrigger.APPROVAL_REQUIRED)
        assert result is False

    def test_stop_trigger_takes_priority_in_check_triggers(self):
        """Test that --until trigger is checked first in check_triggers."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=CheckpointTrigger.APPROVAL_REQUIRED,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        # Action that requires approval should trigger the stop_trigger
        result = system.check_triggers(session, "approve spec")
        assert result == CheckpointTrigger.APPROVAL_REQUIRED


class TestIsHighRisk:
    """Tests for is_high_risk() method."""

    def test_push_to_main_is_high_risk(self):
        """Test that pushing to main branch is detected as high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("push to main") is True
        assert system.is_high_risk("git push origin main") is True
        assert system.is_high_risk("push changes to main branch") is True

    def test_push_to_master_is_high_risk(self):
        """Test that pushing to master branch is detected as high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("push to master") is True
        assert system.is_high_risk("git push origin master") is True

    def test_schema_changes_are_high_risk(self):
        """Test that schema changes are detected as high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("modify schema") is True
        assert system.is_high_risk("alter database schema") is True
        assert system.is_high_risk("schema migration") is True

    def test_delete_operations_are_high_risk(self):
        """Test that delete operations are detected as high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("delete files") is True
        assert system.is_high_risk("remove user data") is True
        assert system.is_high_risk("delete database records") is True

    def test_normal_actions_are_not_high_risk(self):
        """Test that normal actions are not flagged as high risk."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("write tests") is False
        assert system.is_high_risk("implement feature") is False
        assert system.is_high_risk("fix bug") is False
        assert system.is_high_risk("update documentation") is False


class TestRecordAndResetErrors:
    """Tests for record_error() and reset_error_count() methods."""

    def test_record_error_increments_count(self):
        """Test that record_error increments the error count."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # Initially no errors, record one
        system.record_error()
        
        # After 1 error, should not trigger (need 3)
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
        )
        assert system.check_triggers(session, "run tests") is None
        
        # Record two more
        system.record_error()
        system.record_error()
        
        # Now should trigger
        assert system.check_triggers(session, "run tests") == CheckpointTrigger.ERROR_RATE_SPIKE

    def test_reset_error_count_clears_errors(self):
        """Test that reset_error_count clears the error streak."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # Record errors
        system.record_error()
        system.record_error()
        system.record_error()
        
        # Reset
        system.reset_error_count()
        
        # Record one more - should not trigger since we reset
        system.record_error()
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
        )
        assert system.check_triggers(session, "run tests") is None


class TestShouldPauseForApproval:
    """Tests for should_pause_for_approval() method."""

    def test_spec_approval_requires_pause(self):
        """Test that spec approval actions require pause."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("approve spec") is True
        assert system.should_pause_for_approval("spec approval needed") is True

    def test_fix_plan_approval_requires_pause(self):
        """Test that fix plan approval actions require pause."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("approve fix plan") is True
        assert system.should_pause_for_approval("fix plan approval") is True

    def test_approval_keyword_triggers_pause(self):
        """Test that actions containing 'approval' trigger pause."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("needs approval") is True
        assert system.should_pause_for_approval("waiting for approval") is True

    def test_normal_actions_do_not_require_pause(self):
        """Test that normal actions do not require pause."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.should_pause_for_approval("write code") is False
        assert system.should_pause_for_approval("run tests") is False
        assert system.should_pause_for_approval("fix bug") is False


class TestConfigurableThresholds:
    """Tests for configurable thresholds from ChiefOfStaffConfig."""

    def test_custom_budget_threshold(self):
        """Test that custom budget threshold from config is respected."""
        checkpoint_config = CheckpointConfig(budget_usd=5.0)
        config = ChiefOfStaffConfig(checkpoints=checkpoint_config)
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=5.0,  # Custom budget
            duration_limit_seconds=7200,
            cost_spent_usd=5.0,  # At custom budget
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.COST_THRESHOLD

    def test_custom_duration_threshold(self):
        """Test that custom duration threshold from config is respected."""
        checkpoint_config = CheckpointConfig(duration_minutes=60)  # 1 hour
        config = ChiefOfStaffConfig(checkpoints=checkpoint_config)
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=3600,  # 1 hour
            cost_spent_usd=1.0,
            duration_seconds=3600,  # At custom time limit
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.TIME_THRESHOLD

    def test_custom_error_streak_threshold(self):
        """Test that custom error streak threshold from config is respected."""
        checkpoint_config = CheckpointConfig(error_streak=5)
        config = ChiefOfStaffConfig(checkpoints=checkpoint_config)
        system = CheckpointSystem(config)
        
        # Record 3 errors - should not trigger with threshold of 5
        system.record_error()
        system.record_error()
        system.record_error()
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
        )
        
        # Should not trigger yet
        assert system.check_triggers(session, "run tests") is None
        
        # Record 2 more to reach threshold
        system.record_error()
        system.record_error()
        
        # Now should trigger
        assert system.check_triggers(session, "run tests") == CheckpointTrigger.ERROR_RATE_SPIKE


class TestTriggerPriority:
    """Tests for trigger priority order in check_triggers."""

    def test_stop_trigger_checked_first(self):
        """Test that --until stop_trigger is checked before other triggers."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # Session with stop_trigger set and also over budget
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=CheckpointTrigger.HIGH_RISK_ACTION,
            cost_spent_usd=15.0,  # Over budget
            duration_seconds=600,
        )
        
        # High risk action should return the stop trigger, not cost threshold
        result = system.check_triggers(session, "push to main")
        assert result == CheckpointTrigger.HIGH_RISK_ACTION

    def test_cost_before_time_when_both_exceeded(self):
        """Test that cost threshold is checked before time threshold."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=15.0,  # Over budget
            duration_seconds=8000,  # Also over time
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.COST_THRESHOLD


class TestBlockerDetected:
    """Tests for BLOCKER_DETECTED trigger."""

    def test_blocker_detected_for_blocked_action(self):
        """Test BLOCKER_DETECTED fires when action indicates a blocker."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "blocked: waiting for external API access")
        assert result == CheckpointTrigger.BLOCKER_DETECTED

    def test_blocker_detected_when_cannot_proceed(self):
        """Test BLOCKER_DETECTED fires when action indicates cannot proceed."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "cannot proceed without credentials")
        assert result == CheckpointTrigger.BLOCKER_DETECTED

    def test_blocker_detected_for_human_input_needed(self):
        """Test BLOCKER_DETECTED fires when human input is needed."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "need human input for design decision")
        assert result == CheckpointTrigger.BLOCKER_DETECTED


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_action_string(self):
        """Test that empty action string does not crash."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
            cost_spent_usd=1.0,
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "")
        assert result is None

    def test_case_insensitive_high_risk_detection(self):
        """Test that high risk detection is case insensitive."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        assert system.is_high_risk("PUSH TO MAIN") is True
        assert system.is_high_risk("Push To Main") is True
        assert system.is_high_risk("DELETE files") is True

    def test_zero_budget_triggers_immediately(self):
        """Test that zero budget triggers cost threshold on any spend."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=0.0,  # Zero budget
            duration_limit_seconds=7200,
            cost_spent_usd=0.01,  # Any spend
            duration_seconds=600,
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.COST_THRESHOLD

    def test_zero_duration_triggers_immediately(self):
        """Test that zero duration limit triggers time threshold on any time."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=0,  # Zero duration
            cost_spent_usd=1.0,
            duration_seconds=1,  # Any time
        )
        
        result = system.check_triggers(session, "write code")
        assert result == CheckpointTrigger.TIME_THRESHOLD

    def test_multiple_error_resets_maintain_independence(self):
        """Test that multiple error sessions can be reset independently."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config)
        
        # First round of errors
        system.record_error()
        system.record_error()
        system.reset_error_count()
        
        # Second round
        system.record_error()
        system.reset_error_count()
        
        # Third round - should need 3 more to trigger
        system.record_error()
        system.record_error()
        
        session = AutopilotSession(
            session_id="test-001",
            started_at=datetime.now().isoformat(),
            budget_usd=10.0,
            duration_limit_seconds=7200,
        )
        
        # Should not trigger with only 2 errors
        assert system.check_triggers(session, "run tests") is None