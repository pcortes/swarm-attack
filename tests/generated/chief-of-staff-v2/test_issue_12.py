"""Tests for Issue #12: Integrate CheckpointSystem with AutopilotRunner.

This module tests the integration of CheckpointSystem into AutopilotRunner:
- reset_daily_cost() called at session start
- check_before_execution() called before each goal
- update_daily_cost() called after each goal
- Execution pauses when checkpoint requires approval
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    GoalExecutionResult,
    AutopilotRunResult,
)
from swarm_attack.chief_of_staff.checkpoints import (
    Checkpoint,
    CheckpointResult,
    CheckpointSystem,
    CheckpointStore,
    CheckpointTrigger,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus
from swarm_attack.chief_of_staff.autopilot import AutopilotState


class TestAutopilotRunnerInit:
    """Tests for AutopilotRunner initialization."""

    def test_init_accepts_checkpoint_system(self):
        """Test that __init__ accepts checkpoint_system parameter."""
        config = ChiefOfStaffConfig()
        store = CheckpointStore()
        checkpoint_system = CheckpointSystem(config=config, store=store)

        with patch("swarm_attack.chief_of_staff.autopilot_runner.AutopilotSessionStore"):
            runner = AutopilotRunner(
                config=config,
                checkpoint_system=checkpoint_system,
                session_store=MagicMock(),
            )

            assert runner.checkpoint_system is checkpoint_system


class TestStartResetsDailyCost:
    """Tests for reset_daily_cost() being called at session start."""

    def test_start_calls_reset_daily_cost(self):
        """Test that start() calls checkpoint_system.reset_daily_cost()."""
        config = ChiefOfStaffConfig()
        checkpoint_system = MagicMock(spec=CheckpointSystem)
        checkpoint_system.check_before_execution = AsyncMock(
            return_value=CheckpointResult(requires_approval=False, approved=True)
        )
        session_store = MagicMock()
        session_store.save = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Test goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            )
        ]

        runner.start(goals, budget_usd=10.0)

        # Verify reset_daily_cost was called
        checkpoint_system.reset_daily_cost.assert_called_once()


class TestCheckBeforeExecution:
    """Tests for check_before_execution() integration."""

    def test_start_calls_check_before_execution_for_each_goal(self):
        """Test that check_before_execution is called before each goal."""
        config = ChiefOfStaffConfig()
        checkpoint_system = MagicMock(spec=CheckpointSystem)
        checkpoint_system.check_before_execution = AsyncMock(
            return_value=CheckpointResult(requires_approval=False, approved=True)
        )
        session_store = MagicMock()
        session_store.save = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Test goal 1",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Test goal 2",
                priority=GoalPriority.HIGH,
                estimated_minutes=45,
            ),
        ]

        runner.start(goals, budget_usd=10.0)

        # Verify check_before_execution was called for each goal
        assert checkpoint_system.check_before_execution.call_count == 2

    def test_pauses_when_checkpoint_requires_approval(self):
        """Test that execution pauses when checkpoint requires approval."""
        config = ChiefOfStaffConfig()

        # First goal requires approval
        checkpoint_system = MagicMock(spec=CheckpointSystem)
        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test",
            trigger=CheckpointTrigger.COST_SINGLE,
            context="High cost goal",
            options=[],
            recommendation="Review before proceeding",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-1",
            status="pending",
        )
        checkpoint_system.check_before_execution = AsyncMock(
            return_value=CheckpointResult(
                requires_approval=True,
                approved=False,
                checkpoint=mock_checkpoint,
            )
        )
        session_store = MagicMock()
        session_store.save = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="High cost goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                estimated_cost_usd=10.0,
            ),
        ]

        result = runner.start(goals, budget_usd=20.0)

        # Session should be paused
        assert result.session.state == AutopilotState.PAUSED
        # No goals should be completed
        assert result.goals_completed == 0


class TestUpdateDailyCost:
    """Tests for update_daily_cost() integration."""

    def test_start_calls_update_daily_cost_after_goal(self):
        """Test that update_daily_cost is called after each goal execution."""
        config = ChiefOfStaffConfig()
        checkpoint_system = MagicMock(spec=CheckpointSystem)
        checkpoint_system.check_before_execution = AsyncMock(
            return_value=CheckpointResult(requires_approval=False, approved=True)
        )
        session_store = MagicMock()
        session_store.save = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Test goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            )
        ]

        runner.start(goals, budget_usd=10.0)

        # Verify update_daily_cost was called
        checkpoint_system.update_daily_cost.assert_called()


class TestGoalExecutionResultCheckpointPending:
    """Tests for checkpoint_pending field in GoalExecutionResult."""

    def test_goal_execution_result_has_checkpoint_pending(self):
        """Test that GoalExecutionResult has checkpoint_pending field."""
        result = GoalExecutionResult(
            success=True,
            cost_usd=1.0,
            duration_seconds=60,
            checkpoint_pending=True,
        )

        assert result.checkpoint_pending is True

    def test_goal_execution_result_checkpoint_pending_defaults_false(self):
        """Test that checkpoint_pending defaults to False."""
        result = GoalExecutionResult(
            success=True,
            cost_usd=1.0,
            duration_seconds=60,
        )

        assert result.checkpoint_pending is False


class TestExecutionLoopBreaksOnCheckpointPending:
    """Tests for execution breaking when checkpoint_pending is True."""

    def test_execution_breaks_when_checkpoint_pending(self):
        """Test that execution loop breaks when checkpoint requires approval."""
        config = ChiefOfStaffConfig()

        # Set up checkpoint to require approval on second goal
        call_count = [0]

        async def mock_check(goal):
            call_count[0] += 1
            if call_count[0] == 2:
                return CheckpointResult(
                    requires_approval=True,
                    approved=False,
                    checkpoint=Checkpoint(
                        checkpoint_id="chk-test",
                        trigger=CheckpointTrigger.UX_CHANGE,
                        context="UI change detected",
                        options=[],
                        recommendation="Review UI changes",
                        created_at="2025-01-01T12:00:00",
                        goal_id="goal-2",
                        status="pending",
                    ),
                )
            return CheckpointResult(requires_approval=False, approved=True)

        checkpoint_system = MagicMock(spec=CheckpointSystem)
        checkpoint_system.check_before_execution = mock_check
        session_store = MagicMock()
        session_store.save = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Goal 1",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Goal 2 with UI changes",
                priority=GoalPriority.HIGH,
                estimated_minutes=45,
                tags=["ui"],
            ),
            DailyGoal(
                goal_id="goal-3",
                description="Goal 3",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
        ]

        result = runner.start(goals, budget_usd=20.0)

        # Should complete first goal, pause at second
        assert result.goals_completed == 1
        assert result.session.state == AutopilotState.PAUSED


class TestCheckpointCallback:
    """Tests for on_checkpoint callback."""

    def test_on_checkpoint_called_when_pausing(self):
        """Test that on_checkpoint callback is called when pausing."""
        config = ChiefOfStaffConfig()

        mock_checkpoint = Checkpoint(
            checkpoint_id="chk-test",
            trigger=CheckpointTrigger.ARCHITECTURE,
            context="Architecture change",
            options=[],
            recommendation="Review architecture",
            created_at="2025-01-01T12:00:00",
            goal_id="goal-1",
            status="pending",
        )

        checkpoint_system = MagicMock(spec=CheckpointSystem)
        checkpoint_system.check_before_execution = AsyncMock(
            return_value=CheckpointResult(
                requires_approval=True,
                approved=False,
                checkpoint=mock_checkpoint,
            )
        )
        session_store = MagicMock()
        session_store.save = MagicMock()

        on_checkpoint_called = []

        def on_checkpoint(trigger):
            on_checkpoint_called.append(trigger)

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
            on_checkpoint=on_checkpoint,
        )

        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="Architecture goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                tags=["architecture"],
            ),
        ]

        runner.start(goals, budget_usd=10.0)

        # Verify callback was called with the trigger
        assert len(on_checkpoint_called) == 1
        assert on_checkpoint_called[0] == CheckpointTrigger.ARCHITECTURE


class TestIntegrationWithCheckpointSystem:
    """Integration tests with real CheckpointSystem."""

    def test_full_integration_with_triggers(self):
        """Test full integration flow with checkpoint triggers."""
        config = ChiefOfStaffConfig()
        config.checkpoint_cost_single = 5.0  # Trigger at $5

        store = MagicMock(spec=CheckpointStore)
        store.get_pending_for_goal = AsyncMock(return_value=None)
        store.save = AsyncMock()

        checkpoint_system = CheckpointSystem(config=config, store=store)

        session_store = MagicMock()
        session_store.save = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )

        # Create a goal that will trigger COST_SINGLE
        high_cost_goal = DailyGoal(
            goal_id="goal-expensive",
            description="Expensive goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            estimated_cost_usd=10.0,  # Above $5 threshold
        )

        result = runner.start([high_cost_goal], budget_usd=20.0)

        # Should pause due to COST_SINGLE trigger
        assert result.session.state == AutopilotState.PAUSED
        assert result.goals_completed == 0
