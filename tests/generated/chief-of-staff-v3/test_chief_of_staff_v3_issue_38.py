"""Tests for budget checking and callbacks in _execute_goals_continue_on_block.

Issue #38: Implement budget checking and callbacks for continue-on-block

Tests verify:
- Check `remaining_budget = budget_usd - total_cost` before each goal execution
- Break loop if `remaining_budget < self.config.min_execution_budget`
- Call `self.on_goal_start(goal)` callback before execution if set
- Call `self.on_goal_complete(goal, result)` callback after execution if set
- Update `session.total_cost_usd` and `checkpoint_system.update_daily_cost()` after each goal
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, call

from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    GoalExecutionResult,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus, GoalPriority
from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock(spec=ChiefOfStaffConfig)
    config.storage_path = "/tmp/test-swarm"
    config.budget_usd = 100.0
    config.duration_minutes = 120
    config.min_execution_budget = 0.1
    config.checkpoint_cost_single = 5.0
    config.checkpoint_cost_daily = 15.0
    return config


@pytest.fixture
def mock_checkpoint_system(mock_config):
    """Create a mock checkpoint system."""
    system = MagicMock(spec=CheckpointSystem)
    system.config = mock_config
    system.update_daily_cost = MagicMock()
    system.reset_daily_cost = MagicMock()
    return system


@pytest.fixture
def mock_session_store():
    """Create a mock session store."""
    return MagicMock(spec=AutopilotSessionStore)


@pytest.fixture
def runner(mock_config, mock_checkpoint_system, mock_session_store):
    """Create an AutopilotRunner instance for testing."""
    return AutopilotRunner(
        config=mock_config,
        checkpoint_system=mock_checkpoint_system,
        session_store=mock_session_store,
    )


@pytest.fixture
def sample_session():
    """Create a sample AutopilotSession."""
    return AutopilotSession(
        session_id="test-session-123",
        state=AutopilotState.RUNNING,
        goals=[],
        current_goal_index=0,
        total_cost_usd=0.0,
        budget_usd=100.0,
        duration_minutes=120,
    )


def create_goal(goal_id: str, description: str = "Test goal") -> DailyGoal:
    """Helper to create a DailyGoal."""
    return DailyGoal(
        goal_id=goal_id,
        description=description,
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )


class TestBudgetCheckBeforeExecution:
    """Tests verifying remaining_budget is checked before each goal execution."""

    def test_budget_checked_before_execution(self, runner, sample_session):
        """remaining_budget should be calculated as budget_usd - total_cost before each goal."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        budget_usd = 10.0
        
        # First goal costs 5.0, second should still execute (5.0 remaining > 0.1 min)
        costs = [5.0, 3.0]
        call_idx = [0]
        
        def mock_execute(goal):
            cost = costs[call_idx[0]]
            call_idx[0] += 1
            return GoalExecutionResult(
                success=True,
                cost_usd=cost,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        goals_completed, total_cost, _ = result
        
        # Both goals should execute
        assert goals_completed == 2
        assert total_cost == 8.0

    def test_budget_remaining_calculated_correctly(self, runner, sample_session):
        """Budget remaining should be calculated as budget_usd - total_cost."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        budget_usd = 5.0
        
        # Each goal costs 2.0
        # Goal 1: 5.0 - 0 = 5.0 remaining (> 0.1, execute)
        # Goal 2: 5.0 - 2.0 = 3.0 remaining (> 0.1, execute)  
        # Goal 3: 5.0 - 4.0 = 1.0 remaining (> 0.1, execute)
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=2.0,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        goals_completed, total_cost, _ = result
        
        # All 3 goals should execute
        assert goals_completed == 3
        assert total_cost == 6.0


class TestBudgetBreakCondition:
    """Tests verifying loop breaks when remaining_budget < min_execution_budget."""

    def test_breaks_when_budget_below_min(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """Loop should break when remaining_budget < min_execution_budget."""
        mock_config.min_execution_budget = 1.0  # Higher threshold
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )
        
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        budget_usd = 3.0
        
        # Goal 1 costs 2.5, leaving 0.5 remaining
        # 0.5 < 1.0 min_execution_budget, so should break before goal 2
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=2.5,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        goals_completed, total_cost, _ = result
        
        # Only goal 1 should execute (then 0.5 remaining < 1.0 min)
        assert goals_completed == 1
        assert total_cost == 2.5

    def test_breaks_exactly_at_threshold(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """Loop should break when remaining_budget equals min_execution_budget."""
        mock_config.min_execution_budget = 2.0
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )
        
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        budget_usd = 5.0
        
        # Goal 1 costs 3.0, leaving 2.0 remaining
        # 2.0 is NOT less than 2.0, so goal 2 should still execute
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=3.0,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        goals_completed, _, _ = result
        
        # Both goals should execute (2.0 >= 2.0)
        assert goals_completed == 2

    def test_no_goals_executed_when_initial_budget_too_low(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """No goals should execute when initial budget is below threshold."""
        mock_config.min_execution_budget = 10.0
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )
        
        goals = [create_goal("goal-1")]
        budget_usd = 5.0  # Below min_execution_budget
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        goals_completed, total_cost, _ = result
        
        # No goals should execute
        assert goals_completed == 0
        assert total_cost == 0.0


class TestOnGoalStartCallback:
    """Tests verifying on_goal_start callback is called before execution."""

    def test_on_goal_start_called_before_execution(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_start should be called before goal execution if set."""
        on_goal_start = MagicMock()
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=on_goal_start,
        )
        
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        on_goal_start.assert_called_once()
        called_goal = on_goal_start.call_args[0][0]
        assert called_goal.goal_id == "goal-1"

    def test_on_goal_start_called_for_each_goal(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_start should be called for each executed goal."""
        on_goal_start = MagicMock()
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=on_goal_start,
        )
        
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert on_goal_start.call_count == 3

    def test_no_error_when_on_goal_start_not_set(self, runner, sample_session):
        """Method should not error when on_goal_start is not set."""
        assert runner.on_goal_start is None
        
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        # Should not raise any errors
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, _, _ = result
        assert goals_completed == 1

    def test_on_goal_start_called_before_execute_goal(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_start should be called BEFORE _execute_goal."""
        call_order = []
        
        def track_goal_start(goal):
            call_order.append(f"start:{goal.goal_id}")
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=track_goal_start,
        )
        
        def track_execute(goal):
            call_order.append(f"execute:{goal.goal_id}")
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        
        runner._execute_goal = track_execute
        
        goals = [create_goal("goal-1")]
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # on_goal_start should come before _execute_goal
        assert call_order == ["start:goal-1", "execute:goal-1"]


class TestOnGoalCompleteCallback:
    """Tests verifying on_goal_complete callback is called after execution."""

    def test_on_goal_complete_called_after_execution(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_complete should be called after goal execution if set."""
        on_goal_complete = MagicMock()
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_complete=on_goal_complete,
        )
        
        goals = [create_goal("goal-1")]
        
        expected_result = GoalExecutionResult(
            success=True,
            cost_usd=1.5,
            duration_seconds=60,
        )
        runner._execute_goal = MagicMock(return_value=expected_result)
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        on_goal_complete.assert_called_once()
        called_goal, called_result = on_goal_complete.call_args[0]
        assert called_goal.goal_id == "goal-1"
        assert called_result == expected_result

    def test_on_goal_complete_called_for_each_goal(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_complete should be called for each executed goal."""
        on_goal_complete = MagicMock()
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_complete=on_goal_complete,
        )
        
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert on_goal_complete.call_count == 2

    def test_on_goal_complete_called_for_failed_goals(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_complete should be called even for failed goals."""
        on_goal_complete = MagicMock()
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_complete=on_goal_complete,
        )
        
        goals = [create_goal("goal-1")]
        
        failed_result = GoalExecutionResult(
            success=False,
            cost_usd=0.5,
            duration_seconds=30,
            error="Test error",
        )
        runner._execute_goal = MagicMock(return_value=failed_result)
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        on_goal_complete.assert_called_once()
        _, called_result = on_goal_complete.call_args[0]
        assert called_result.success is False

    def test_no_error_when_on_goal_complete_not_set(self, runner, sample_session):
        """Method should not error when on_goal_complete is not set."""
        assert runner.on_goal_complete is None
        
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        # Should not raise any errors
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, _, _ = result
        assert goals_completed == 1

    def test_on_goal_complete_receives_goal_and_result(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """on_goal_complete should receive both goal and result as arguments."""
        received_args = []
        
        def capture_complete(goal, result):
            received_args.append((goal, result))
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_complete=capture_complete,
        )
        
        goals = [create_goal("goal-1")]
        
        expected_result = GoalExecutionResult(
            success=True,
            cost_usd=2.5,
            duration_seconds=120,
        )
        runner._execute_goal = MagicMock(return_value=expected_result)
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert len(received_args) == 1
        goal, result = received_args[0]
        assert goal.goal_id == "goal-1"
        assert result.cost_usd == 2.5


class TestSessionTotalCostUpdate:
    """Tests verifying session.total_cost_usd is updated after each goal."""

    def test_session_total_cost_updated_after_each_goal(self, runner, sample_session):
        """session.total_cost_usd should be updated after each goal execution."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        costs = [3.0, 2.0]
        call_idx = [0]
        
        def mock_execute(goal):
            cost = costs[call_idx[0]]
            call_idx[0] += 1
            return GoalExecutionResult(
                success=True,
                cost_usd=cost,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Session should have accumulated total cost
        assert sample_session.total_cost_usd == 5.0

    def test_session_total_cost_includes_failed_goals(self, runner, sample_session):
        """session.total_cost_usd should include costs from failed goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        def mock_execute(goal):
            if goal.goal_id == "goal-1":
                return GoalExecutionResult(
                    success=True,
                    cost_usd=2.0,
                    duration_seconds=60,
                )
            return GoalExecutionResult(
                success=False,
                cost_usd=1.5,
                duration_seconds=30,
                error="Test error",
            )
        
        runner._execute_goal = mock_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Session should have both costs
        assert sample_session.total_cost_usd == 3.5

    def test_session_total_cost_starts_at_zero(self, runner, sample_session):
        """session.total_cost_usd should start at 0 and accumulate."""
        assert sample_session.total_cost_usd == 0.0
        
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=5.0,
                duration_seconds=60,
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert sample_session.total_cost_usd == 5.0


class TestCheckpointSystemDailyCostUpdate:
    """Tests verifying checkpoint_system.update_daily_cost() is called after each goal."""

    def test_update_daily_cost_called_after_each_goal(self, runner, mock_checkpoint_system, sample_session):
        """checkpoint_system.update_daily_cost() should be called after each goal."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=2.0,
                duration_seconds=60,
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert mock_checkpoint_system.update_daily_cost.call_count == 2

    def test_update_daily_cost_called_with_goal_cost(self, runner, mock_checkpoint_system, sample_session):
        """checkpoint_system.update_daily_cost() should be called with the goal's cost."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=3.5,
                duration_seconds=60,
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        mock_checkpoint_system.update_daily_cost.assert_called_once_with(3.5)

    def test_update_daily_cost_called_for_failed_goals(self, runner, mock_checkpoint_system, sample_session):
        """checkpoint_system.update_daily_cost() should be called even for failed goals."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=1.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        mock_checkpoint_system.update_daily_cost.assert_called_once_with(1.5)

    def test_update_daily_cost_with_correct_costs_for_multiple_goals(self, runner, mock_checkpoint_system, sample_session):
        """checkpoint_system.update_daily_cost() should be called with each goal's cost."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        costs = [1.0, 2.0, 3.0]
        call_idx = [0]
        
        def mock_execute(goal):
            cost = costs[call_idx[0]]
            call_idx[0] += 1
            return GoalExecutionResult(
                success=True,
                cost_usd=cost,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Verify all calls with correct costs
        assert mock_checkpoint_system.update_daily_cost.call_count == 3
        calls = mock_checkpoint_system.update_daily_cost.call_args_list
        assert calls[0] == call(1.0)
        assert calls[1] == call(2.0)
        assert calls[2] == call(3.0)


class TestCallbackOrderAndIntegration:
    """Integration tests for callback order and budget/cost interactions."""

    def test_callback_order_start_execute_complete(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """Callbacks should fire in order: on_goal_start -> execute -> on_goal_complete."""
        call_order = []
        
        def track_start(goal):
            call_order.append(f"start:{goal.goal_id}")
        
        def track_complete(goal, result):
            call_order.append(f"complete:{goal.goal_id}")
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=track_start,
            on_goal_complete=track_complete,
        )
        
        def track_execute(goal):
            call_order.append(f"execute:{goal.goal_id}")
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        
        runner._execute_goal = track_execute
        
        goals = [create_goal("goal-1")]
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert call_order == ["start:goal-1", "execute:goal-1", "complete:goal-1"]

    def test_budget_check_before_callbacks(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """Budget check should happen before callbacks and execution."""
        mock_config.min_execution_budget = 10.0
        
        on_goal_start = MagicMock()
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=on_goal_start,
        )
        
        runner._execute_goal = MagicMock()
        
        goals = [create_goal("goal-1")]
        budget_usd = 5.0  # Below threshold
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        # Neither callback nor execute should be called
        on_goal_start.assert_not_called()
        runner._execute_goal.assert_not_called()

    def test_session_and_checkpoint_updated_after_each_goal(self, runner, mock_checkpoint_system, sample_session):
        """Both session.total_cost_usd and checkpoint_system.update_daily_cost should be updated after each goal."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        costs = [2.0, 3.0]
        call_idx = [0]
        
        def mock_execute(goal):
            cost = costs[call_idx[0]]
            call_idx[0] += 1
            return GoalExecutionResult(
                success=True,
                cost_usd=cost,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Session total should be accumulated
        assert sample_session.total_cost_usd == 5.0
        
        # Checkpoint system should be called twice
        assert mock_checkpoint_system.update_daily_cost.call_count == 2


class TestFileExists:
    """Tests to verify implementation file exists."""

    def test_autopilot_runner_file_exists(self):
        """autopilot_runner.py must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        assert path.exists(), "autopilot_runner.py must exist"

    def test_min_execution_budget_used_in_method(self):
        """min_execution_budget should be used in _execute_goals_continue_on_block."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "min_execution_budget" in content, (
            "min_execution_budget should be used in autopilot_runner.py"
        )

    def test_on_goal_start_used_in_method(self):
        """on_goal_start callback should be used in _execute_goals_continue_on_block."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "on_goal_start" in content, (
            "on_goal_start should be used in autopilot_runner.py"
        )

    def test_on_goal_complete_used_in_method(self):
        """on_goal_complete callback should be used in _execute_goals_continue_on_block."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "on_goal_complete" in content, (
            "on_goal_complete should be used in autopilot_runner.py"
        )

    def test_update_daily_cost_called_in_method(self):
        """update_daily_cost should be called in _execute_goals_continue_on_block."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "update_daily_cost" in content, (
            "update_daily_cost should be called in autopilot_runner.py"
        )