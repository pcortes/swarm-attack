"""Tests for _execute_goals_continue_on_block method in AutopilotRunner.

Issue #31: Unit tests for continue-on-block strategy

This test file covers:
1. Empty goals list returns (0, 0.0, set())
2. All goals succeed returns correct count and cost
3. Blocked goal is added to blocked_ids set
4. Dependent goals skipped when dependency blocked
5. Budget exhaustion stops execution
6. on_goal_start callback called for each executed goal
7. on_goal_complete callback called with result
8. Hiccup checkpoint created on goal failure (goal.is_hiccup = True)
9. Mixed success/failure returns correct counts
10. Independent goals continue after one blocks
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    ExecutionStrategy,
    GoalExecutionResult,
    DependencyGraph,
)
from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus


class TestExecuteGoalsContinueOnBlockEmptyGoals:
    """Tests for empty goals list behavior."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    def test_empty_goals_returns_zero_tuple(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """Empty goals list should return (0, 0.0, set())."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=[],
            budget_usd=10.0,
            session=session,
        )

        assert goals_completed == 0
        assert total_cost == 0.0
        assert blocked_ids == set()

    def test_empty_goals_does_not_call_execute_goal(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """Empty goals list should not call _execute_goal."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            runner._execute_goals_continue_on_block(
                goals=[],
                budget_usd=10.0,
                session=session,
            )

            mock_execute.assert_not_called()


class TestExecuteGoalsContinueOnBlockAllSucceed:
    """Tests for all goals succeeding."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    @pytest.fixture
    def sample_goals(self):
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-3",
                description="Third goal",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
        ]

    def test_all_goals_succeed_returns_correct_count(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """All goals succeeding should return correct goals_completed count."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.10, duration_seconds=10
            )

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            assert goals_completed == 3
            assert blocked_ids == set()

    def test_all_goals_succeed_returns_correct_total_cost(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """All goals succeeding should return correct total cost."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # Each goal costs $0.15
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.15, duration_seconds=10
            )

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            # 3 goals * $0.15 = $0.45
            assert total_cost == pytest.approx(0.45, rel=0.01)

    def test_all_goals_succeed_marks_status_complete(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """All succeeding goals should have status set to COMPLETE."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.10, duration_seconds=10
            )

            runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            for goal in sample_goals:
                assert goal.status == GoalStatus.COMPLETE


class TestExecuteGoalsContinueOnBlockBlocked:
    """Tests for blocked goal behavior."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    @pytest.fixture
    def sample_goals(self):
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

    def test_blocked_goal_added_to_blocked_ids(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """Failed goal should be added to blocked_ids set."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # First goal fails, second succeeds
            mock_execute.side_effect = [
                GoalExecutionResult(
                    success=False, cost_usd=0.10, duration_seconds=10, error="Test error"
                ),
                GoalExecutionResult(
                    success=True, cost_usd=0.10, duration_seconds=10
                ),
            ]

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            assert "goal-1" in blocked_ids
            assert "goal-2" not in blocked_ids

    def test_blocked_goal_has_status_blocked(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """Failed goal should have status set to BLOCKED."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=False, cost_usd=0.10, duration_seconds=10, error="Test error"
            )

            runner._execute_goals_continue_on_block(
                goals=[sample_goals[0]],
                budget_usd=10.0,
                session=session,
            )

            assert sample_goals[0].status == GoalStatus.BLOCKED


class TestExecuteGoalsContinueOnBlockDependencies:
    """Tests for dependency handling when goals are blocked."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    def test_dependency_graph_get_ready_goals_skips_blocked_dependents(self):
        """DependencyGraph.get_ready_goals should skip goals with blocked dependencies."""
        goals = [
            DailyGoal(
                goal_id="parent",
                description="Parent goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="child",
                description="Child goal depends on parent",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        graph.dependencies = {"child": ["parent"]}

        # Parent is blocked
        completed = set()
        blocked = {"parent"}

        ready = graph.get_ready_goals(completed, blocked)

        # Child should not be ready because parent is blocked
        assert len(ready) == 0

    def test_dependency_graph_get_ready_goals_returns_ready_when_deps_complete(self):
        """DependencyGraph.get_ready_goals should return goals when dependencies are complete."""
        goals = [
            DailyGoal(
                goal_id="parent",
                description="Parent goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="child",
                description="Child goal depends on parent",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        graph.dependencies = {"child": ["parent"]}

        # Parent is completed
        completed = {"parent"}
        blocked = set()

        ready = graph.get_ready_goals(completed, blocked)

        # Child should now be ready
        assert len(ready) == 1
        assert ready[0].goal_id == "child"

    def test_independent_goals_not_blocked_by_sibling_failure(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """Independent goals should continue even when siblings fail."""
        goals = [
            DailyGoal(
                goal_id="goal-a",
                description="Independent goal A",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-b",
                description="Independent goal B",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # goal-a fails, goal-b succeeds
            mock_execute.side_effect = [
                GoalExecutionResult(
                    success=False, cost_usd=0.10, duration_seconds=10, error="Error"
                ),
                GoalExecutionResult(
                    success=True, cost_usd=0.10, duration_seconds=10
                ),
            ]

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=10.0,
                session=session,
            )

            # goal-a blocked, goal-b completed
            assert goals_completed == 1
            assert "goal-a" in blocked_ids
            assert "goal-b" not in blocked_ids
            assert mock_execute.call_count == 2


class TestExecuteGoalsContinueOnBlockBudget:
    """Tests for budget exhaustion behavior."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=1.0,
            duration_minutes=60,
        )

    @pytest.fixture
    def sample_goals(self):
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-3",
                description="Third goal",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
        ]

    def test_budget_exhaustion_stops_execution(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """Execution should stop when budget is exhausted."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # Each goal costs $0.60 - after first goal, remaining budget is $0.40
            # which is below min_execution_budget of $0.50
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.60, duration_seconds=10
            )

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=1.0,
                session=session,
            )

            # Only first goal should be executed
            assert goals_completed == 1
            assert mock_execute.call_count == 1
            assert total_cost == pytest.approx(0.60, rel=0.01)

    def test_budget_allows_execution_when_sufficient(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """Execution should continue when budget is sufficient."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # Each goal costs $0.10 - plenty of budget
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.10, duration_seconds=10
            )

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            # All 3 goals should be executed
            assert goals_completed == 3
            assert mock_execute.call_count == 3


class TestExecuteGoalsContinueOnBlockCallbacks:
    """Tests for callback invocation."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    @pytest.fixture
    def sample_goals(self):
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

    def test_on_goal_start_called_for_each_executed_goal(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """on_goal_start should be called for each executed goal."""
        on_goal_start = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=on_goal_start,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.10, duration_seconds=10
            )

            runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            assert on_goal_start.call_count == 2
            # Verify called with each goal
            on_goal_start.assert_any_call(sample_goals[0])
            on_goal_start.assert_any_call(sample_goals[1])

    def test_on_goal_complete_called_with_result(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """on_goal_complete should be called with goal and result."""
        on_goal_complete = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_complete=on_goal_complete,
        )

        execution_result = GoalExecutionResult(
            success=True, cost_usd=0.10, duration_seconds=10
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = execution_result

            runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            assert on_goal_complete.call_count == 2
            # Verify called with goal and result
            on_goal_complete.assert_any_call(sample_goals[0], execution_result)
            on_goal_complete.assert_any_call(sample_goals[1], execution_result)

    def test_callbacks_not_called_when_none(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """No error when callbacks are None."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=None,
            on_goal_complete=None,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.10, duration_seconds=10
            )

            # Should not raise
            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            assert goals_completed == 2


class TestExecuteGoalsContinueOnBlockHiccup:
    """Tests for hiccup (is_hiccup flag) behavior on failure."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    def test_failed_goal_sets_is_hiccup_true(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """Failed goal should have is_hiccup set to True."""
        goal = DailyGoal(
            goal_id="goal-1",
            description="Will fail",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            is_hiccup=False,
        )

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=False, cost_usd=0.10, duration_seconds=10, error="Test failure"
            )

            runner._execute_goals_continue_on_block(
                goals=[goal],
                budget_usd=10.0,
                session=session,
            )

            assert goal.is_hiccup is True

    def test_successful_goal_keeps_is_hiccup_false(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """Successful goal should keep is_hiccup as False."""
        goal = DailyGoal(
            goal_id="goal-1",
            description="Will succeed",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            is_hiccup=False,
        )

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.return_value = GoalExecutionResult(
                success=True, cost_usd=0.10, duration_seconds=10
            )

            runner._execute_goals_continue_on_block(
                goals=[goal],
                budget_usd=10.0,
                session=session,
            )

            assert goal.is_hiccup is False


class TestExecuteGoalsContinueOnBlockMixedResults:
    """Tests for mixed success/failure scenarios."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    @pytest.fixture
    def sample_goals(self):
        """Create sample goals for testing."""
        return [
            DailyGoal(
                goal_id="goal-1",
                description="First goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-2",
                description="Second goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="goal-3",
                description="Third goal",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
            DailyGoal(
                goal_id="goal-4",
                description="Fourth goal",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
        ]

    def test_mixed_results_returns_correct_counts(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """Mixed success/failure should return correct counts."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # goal-1: success, goal-2: fail, goal-3: success, goal-4: fail
            mock_execute.side_effect = [
                GoalExecutionResult(success=True, cost_usd=0.10, duration_seconds=10),
                GoalExecutionResult(
                    success=False, cost_usd=0.10, duration_seconds=10, error="Error"
                ),
                GoalExecutionResult(success=True, cost_usd=0.10, duration_seconds=10),
                GoalExecutionResult(
                    success=False, cost_usd=0.10, duration_seconds=10, error="Error"
                ),
            ]

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            assert goals_completed == 2
            assert len(blocked_ids) == 2
            assert "goal-2" in blocked_ids
            assert "goal-4" in blocked_ids

    def test_mixed_results_returns_correct_total_cost(
        self, mock_checkpoint_system, mock_session_store, config, session, sample_goals
    ):
        """Mixed results should sum costs for all executed goals (including failures)."""
        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            # Different costs: $0.10, $0.20, $0.15, $0.25
            mock_execute.side_effect = [
                GoalExecutionResult(success=True, cost_usd=0.10, duration_seconds=10),
                GoalExecutionResult(
                    success=False, cost_usd=0.20, duration_seconds=10, error="Error"
                ),
                GoalExecutionResult(success=True, cost_usd=0.15, duration_seconds=10),
                GoalExecutionResult(
                    success=False, cost_usd=0.25, duration_seconds=10, error="Error"
                ),
            ]

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=sample_goals,
                budget_usd=10.0,
                session=session,
            )

            # Total: $0.10 + $0.20 + $0.15 + $0.25 = $0.70
            assert total_cost == pytest.approx(0.70, rel=0.01)


class TestExecuteGoalsContinueOnBlockIndependentContinuation:
    """Tests for independent goals continuing after one blocks."""

    @pytest.fixture
    def mock_checkpoint_system(self):
        """Create a mock checkpoint system."""
        mock = MagicMock()
        mock.reset_daily_cost = MagicMock()
        mock.update_daily_cost = MagicMock()
        mock_result = MagicMock()
        mock_result.requires_approval = False
        mock_result.approved = True
        mock.check_before_execution = MagicMock(return_value=mock_result)
        return mock

    @pytest.fixture
    def mock_session_store(self):
        """Create a mock session store."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def config(self):
        """Create a config with CONTINUE_ON_BLOCK strategy."""
        cfg = ChiefOfStaffConfig()
        cfg.autopilot.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
        cfg.min_execution_budget = 0.50
        return cfg

    @pytest.fixture
    def session(self):
        """Create a mock autopilot session."""
        return AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            total_cost_usd=0.0,
            budget_usd=10.0,
            duration_minutes=60,
        )

    def test_independent_goals_all_execute_despite_failures(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """All independent goals should execute even if some fail."""
        goals = [
            DailyGoal(
                goal_id="independent-1",
                description="Independent goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="independent-2",
                description="Independent goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="independent-3",
                description="Independent goal 3",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            ),
        ]

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        execute_count = 0

        def track_execution(goal):
            nonlocal execute_count
            execute_count += 1
            if goal.goal_id == "independent-2":
                return GoalExecutionResult(
                    success=False, cost_usd=0.10, duration_seconds=10, error="Error"
                )
            return GoalExecutionResult(success=True, cost_usd=0.10, duration_seconds=10)

        with patch.object(runner, '_execute_goal', side_effect=track_execution):
            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=10.0,
                session=session,
            )

            # All 3 goals should be executed
            assert execute_count == 3
            # 2 succeed, 1 fails
            assert goals_completed == 2
            assert len(blocked_ids) == 1
            assert "independent-2" in blocked_ids

    def test_blocked_goal_does_not_prevent_subsequent_goals(
        self, mock_checkpoint_system, mock_session_store, config, session
    ):
        """A blocked goal should not prevent subsequent independent goals from running."""
        goals = [
            DailyGoal(
                goal_id="first",
                description="First goal (will fail)",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="second",
                description="Second goal (should still run)",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
        )

        with patch.object(runner, '_execute_goal') as mock_execute:
            mock_execute.side_effect = [
                GoalExecutionResult(
                    success=False, cost_usd=0.10, duration_seconds=10, error="First fails"
                ),
                GoalExecutionResult(
                    success=True, cost_usd=0.10, duration_seconds=10
                ),
            ]

            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=10.0,
                session=session,
            )

            # Both should be executed (continue-on-block behavior)
            assert mock_execute.call_count == 2
            # Second goal should complete
            assert goals_completed == 1
            assert goals[1].status == GoalStatus.COMPLETE


class TestDependencyGraphUnit:
    """Unit tests for DependencyGraph class."""

    def test_from_goals_creates_graph_with_all_goals(self):
        """from_goals should create a graph containing all goals."""
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)

        assert len(graph.issues) == 2
        assert graph.issues[0].goal_id == "g1"
        assert graph.issues[1].goal_id == "g2"

    def test_from_goals_creates_empty_dependencies(self):
        """from_goals should create a graph with empty dependencies."""
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)

        assert graph.dependencies == {}

    def test_get_ready_goals_returns_all_when_no_deps(self):
        """get_ready_goals should return all goals when none have dependencies."""
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        ready = graph.get_ready_goals(completed=set(), blocked=set())

        assert len(ready) == 2

    def test_get_ready_goals_excludes_completed(self):
        """get_ready_goals should not return completed goals."""
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        ready = graph.get_ready_goals(completed={"g1"}, blocked=set())

        assert len(ready) == 1
        assert ready[0].goal_id == "g2"

    def test_get_ready_goals_excludes_blocked(self):
        """get_ready_goals should not return blocked goals."""
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        ready = graph.get_ready_goals(completed=set(), blocked={"g1"})

        assert len(ready) == 1
        assert ready[0].goal_id == "g2"

    def test_get_ready_goals_respects_dependencies(self):
        """get_ready_goals should not return goals with unmet dependencies."""
        goals = [
            DailyGoal(
                goal_id="parent",
                description="Parent goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="child",
                description="Child goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        graph.dependencies = {"child": ["parent"]}

        ready = graph.get_ready_goals(completed=set(), blocked=set())

        # Only parent should be ready (child depends on parent)
        assert len(ready) == 1
        assert ready[0].goal_id == "parent"

    def test_get_ready_goals_returns_empty_when_all_processed(self):
        """get_ready_goals should return empty when all goals are completed/blocked."""
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=30,
            ),
        ]

        graph = DependencyGraph.from_goals(goals)
        ready = graph.get_ready_goals(completed={"g1"}, blocked={"g2"})

        assert len(ready) == 0
