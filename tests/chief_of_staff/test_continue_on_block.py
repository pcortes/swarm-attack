"""Tests for continue-on-block execution strategy in AutopilotRunner.

Issue #31: Add unit tests for continue-on-block execution strategy

Tests verify the behavior of the CONTINUE_ON_BLOCK execution strategy:
- When goal A blocks, goals B and C (that don't depend on A) continue
- When goal B depends on goal A and A blocks, B is transitively blocked
- The blocked_goals set is correctly updated
- Total cost is correctly accumulated only for executed goals
- The final result includes correct counts (goals_completed, goals_blocked)
- Integration with the start() method using ExecutionStrategy.CONTINUE_ON_BLOCK
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    ExecutionStrategy,
    DependencyGraph,
    GoalExecutionResult,
    AutopilotRunResult,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus, GoalPriority
from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig, AutopilotConfig
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore


@pytest.fixture
def mock_config():
    """Create a mock config with CONTINUE_ON_BLOCK strategy."""
    config = MagicMock(spec=ChiefOfStaffConfig)
    config.storage_path = "/tmp/test-swarm"
    config.budget_usd = 100.0
    config.duration_minutes = 120
    config.min_execution_budget = 0.1
    config.checkpoint_cost_single = 5.0
    config.checkpoint_cost_daily = 15.0

    # Configure autopilot with CONTINUE_ON_BLOCK strategy
    autopilot_config = MagicMock(spec=AutopilotConfig)
    autopilot_config.execution_strategy = ExecutionStrategy.CONTINUE_ON_BLOCK
    config.autopilot = autopilot_config

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


def create_goal(goal_id: str, description: str = "Test goal") -> DailyGoal:
    """Helper to create a DailyGoal."""
    return DailyGoal(
        goal_id=goal_id,
        description=description,
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )


class TestIndependentGoalsContinueWhenOneBlocks:
    """Tests verifying that independent goals continue when one goal blocks."""

    def test_goal_b_and_c_continue_when_goal_a_blocks(self, runner):
        """When goal A blocks, goals B and C (independent) should continue."""
        goal_a = create_goal("goal-a", "First goal that will block")
        goal_b = create_goal("goal-b", "Second goal (independent)")
        goal_c = create_goal("goal-c", "Third goal (independent)")
        goals = [goal_a, goal_b, goal_c]

        # Goal A fails, B and C succeed
        def mock_execute(goal):
            if goal.goal_id == "goal-a":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal A blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Should have completed 2 goals (B and C)
        assert result.goals_completed == 2
        assert result.goals_total == 3

        # Check goal statuses
        assert goal_a.status == GoalStatus.BLOCKED
        assert goal_b.status == GoalStatus.COMPLETE
        assert goal_c.status == GoalStatus.COMPLETE

        # Check hiccup flag
        assert goal_a.is_hiccup is True
        assert goal_b.is_hiccup is False
        assert goal_c.is_hiccup is False

    def test_all_independent_goals_continue_despite_middle_failure(self, runner):
        """All independent goals should continue even if middle goal fails."""
        goals = [
            create_goal("goal-1"),
            create_goal("goal-2"),
            create_goal("goal-3"),
            create_goal("goal-4"),
        ]

        # Goal 2 fails, others succeed
        def mock_execute(goal):
            if goal.goal_id == "goal-2":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal 2 blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Should have completed 3 goals (1, 3, 4)
        assert result.goals_completed == 3
        assert goals[0].status == GoalStatus.COMPLETE
        assert goals[1].status == GoalStatus.BLOCKED
        assert goals[2].status == GoalStatus.COMPLETE
        assert goals[3].status == GoalStatus.COMPLETE

    def test_multiple_blocked_goals_dont_stop_others(self, runner):
        """Multiple blocked goals should not stop other independent goals."""
        goals = [
            create_goal("goal-1"),
            create_goal("goal-2"),
            create_goal("goal-3"),
            create_goal("goal-4"),
            create_goal("goal-5"),
        ]

        # Goals 2 and 4 fail, others succeed
        def mock_execute(goal):
            if goal.goal_id in ("goal-2", "goal-4"):
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Should have completed 3 goals (1, 3, 5)
        assert result.goals_completed == 3

        # Check blocked goals
        blocked_goals = [g for g in goals if g.status == GoalStatus.BLOCKED]
        assert len(blocked_goals) == 2
        assert set(g.goal_id for g in blocked_goals) == {"goal-2", "goal-4"}


class TestDependentGoalsTransitivelyBlocked:
    """Tests verifying that dependent goals are transitively blocked."""

    def test_goal_b_blocked_when_dependency_a_blocks(self, runner):
        """When goal A blocks and B depends on A, B should be transitively blocked."""
        goal_a = create_goal("goal-a", "Dependency goal")
        goal_b = create_goal("goal-b", "Dependent goal")
        goals = [goal_a, goal_b]

        # Goal A fails
        def mock_execute(goal):
            if goal.goal_id == "goal-a":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal A blocked",
                )
            # Goal B should not be executed because A failed
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        # Manually set up dependency graph
        session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            current_goal_index=0,
            total_cost_usd=0.0,
            budget_usd=100.0,
            duration_minutes=120,
        )

        # Create dependency graph with B depending on A
        graph = DependencyGraph(
            issues=goals,
            dependencies={"goal-b": ["goal-a"]}
        )

        # Patch DependencyGraph.from_goals to return our graph
        with patch.object(DependencyGraph, 'from_goals', return_value=graph):
            goals_completed, total_cost, blocked = runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=session,
            )

        # Should have completed 0 goals
        assert goals_completed == 0

        # Goal A should be blocked (failed execution)
        assert "goal-a" in blocked

        # Goal B should never have been executed (dependency not met)
        assert goal_b.status == GoalStatus.PENDING  # Never executed

    def test_chain_of_dependencies_all_blocked(self, runner):
        """When A blocks and B depends on A and C depends on B, all should be blocked."""
        goal_a = create_goal("goal-a", "Root dependency")
        goal_b = create_goal("goal-b", "Middle dependency")
        goal_c = create_goal("goal-c", "Final dependent")
        goals = [goal_a, goal_b, goal_c]

        # Goal A fails
        executed_goals = []

        def mock_execute(goal):
            executed_goals.append(goal.goal_id)
            if goal.goal_id == "goal-a":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal A blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            current_goal_index=0,
            total_cost_usd=0.0,
            budget_usd=100.0,
            duration_minutes=120,
        )

        # Create dependency chain: C depends on B, B depends on A
        graph = DependencyGraph(
            issues=goals,
            dependencies={
                "goal-b": ["goal-a"],
                "goal-c": ["goal-b"],
            }
        )

        with patch.object(DependencyGraph, 'from_goals', return_value=graph):
            goals_completed, total_cost, blocked = runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=session,
            )

        # Only goal A should have been executed (and failed)
        assert executed_goals == ["goal-a"]
        assert goals_completed == 0
        assert "goal-a" in blocked

        # B and C never executed because dependencies not met
        assert goal_b.status == GoalStatus.PENDING
        assert goal_c.status == GoalStatus.PENDING

    def test_independent_goal_continues_when_dependency_chain_blocks(self, runner):
        """Independent goal D should continue when dependency chain A->B->C blocks."""
        goal_a = create_goal("goal-a", "Root dependency")
        goal_b = create_goal("goal-b", "Middle dependency")
        goal_c = create_goal("goal-c", "Final dependent")
        goal_d = create_goal("goal-d", "Independent goal")
        goals = [goal_a, goal_b, goal_c, goal_d]

        # Goal A fails, D succeeds
        def mock_execute(goal):
            if goal.goal_id == "goal-a":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal A blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            current_goal_index=0,
            total_cost_usd=0.0,
            budget_usd=100.0,
            duration_minutes=120,
        )

        # Create dependency chain: C depends on B, B depends on A, D is independent
        graph = DependencyGraph(
            issues=goals,
            dependencies={
                "goal-b": ["goal-a"],
                "goal-c": ["goal-b"],
            }
        )

        with patch.object(DependencyGraph, 'from_goals', return_value=graph):
            goals_completed, total_cost, blocked = runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=session,
            )

        # Only goal D should have completed
        assert goals_completed == 1
        assert goal_d.status == GoalStatus.COMPLETE

        # A should be blocked
        assert "goal-a" in blocked
        assert goal_a.status == GoalStatus.BLOCKED


class TestBlockedGoalsSetCorrectness:
    """Tests verifying that blocked_goals set is correctly updated."""

    def test_blocked_set_contains_failed_goals(self, runner):
        """Blocked set should contain all failed goal IDs."""
        goals = [
            create_goal("goal-1"),
            create_goal("goal-2"),
            create_goal("goal-3"),
        ]

        # Goals 1 and 3 fail
        def mock_execute(goal):
            if goal.goal_id in ("goal-1", "goal-3"):
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Goal blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Check that blocked goals are tracked
        blocked_goals = [g for g in goals if g.status == GoalStatus.BLOCKED]
        assert len(blocked_goals) == 2
        assert set(g.goal_id for g in blocked_goals) == {"goal-1", "goal-3"}

    def test_blocked_set_empty_when_all_succeed(self, runner):
        """Blocked set should be empty when all goals succeed."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # No goals should be blocked
        blocked_goals = [g for g in goals if g.status == GoalStatus.BLOCKED]
        assert len(blocked_goals) == 0
        assert result.goals_completed == 2

    def test_blocked_set_is_set_type(self, runner):
        """Blocked goals should be returned as a Python set."""
        goals = [create_goal("goal-1")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Blocked",
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        session = AutopilotSession(
            session_id="test-session",
            state=AutopilotState.RUNNING,
            goals=[g.to_dict() for g in goals],
            current_goal_index=0,
            total_cost_usd=0.0,
            budget_usd=100.0,
            duration_minutes=120,
        )

        _, _, blocked = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=session,
        )

        assert isinstance(blocked, set)
        assert "goal-1" in blocked


class TestCostAccumulation:
    """Tests verifying that total cost is correctly accumulated."""

    def test_cost_accumulates_from_successful_goals(self, runner):
        """Total cost should accumulate from all successful goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]

        costs = [2.5, 3.5]
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
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Total cost should be sum of both
        assert result.total_cost_usd == 6.0  # 2.5 + 3.5

    def test_cost_includes_failed_goal_costs(self, runner):
        """Total cost should include costs from failed goals too."""
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
                error="Blocked",
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Total cost should include both successful and failed
        assert result.total_cost_usd == 3.5  # 2.0 + 1.5
        assert result.goals_completed == 1

    def test_cost_accumulation_with_mixed_results(self, runner):
        """Cost should accumulate correctly with mixed success/failure."""
        goals = [
            create_goal("goal-1"),
            create_goal("goal-2"),
            create_goal("goal-3"),
            create_goal("goal-4"),
        ]

        costs = [1.0, 2.0, 3.0, 4.0]
        call_idx = [0]

        def mock_execute(goal):
            cost = costs[call_idx[0]]
            call_idx[0] += 1
            # Goals 2 and 4 fail
            success = goal.goal_id not in ("goal-2", "goal-4")
            return GoalExecutionResult(
                success=success,
                cost_usd=cost,
                duration_seconds=60 if success else 30,
                error=None if success else "Blocked",
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        # Total cost: 1.0 + 2.0 + 3.0 + 4.0 = 10.0
        assert result.total_cost_usd == 10.0
        # Goals completed: goal-1 and goal-3
        assert result.goals_completed == 2


class TestResultCounts:
    """Tests verifying final result includes correct counts."""

    def test_goals_completed_count_accurate(self, runner):
        """goals_completed should accurately reflect number of successful goals."""
        goals = [
            create_goal("goal-1"),
            create_goal("goal-2"),
            create_goal("goal-3"),
        ]

        def mock_execute(goal):
            # Only goal-2 fails
            if goal.goal_id == "goal-2":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Blocked",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )

        runner._execute_goal = mock_execute
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.goals_completed == 2
        assert result.goals_total == 3

    def test_goals_total_always_equals_input_count(self, runner):
        """goals_total should always equal the number of input goals."""
        goals = [create_goal(f"goal-{i}") for i in range(5)]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.goals_total == 5
        assert result.goals_completed == 5

    def test_zero_completed_when_all_fail(self, runner):
        """goals_completed should be 0 when all goals fail."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Blocked",
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.goals_completed == 0
        assert result.goals_total == 2

    def test_result_type_is_autopilot_run_result(self, runner):
        """start() should return AutopilotRunResult."""
        goals = [create_goal("goal-1")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert isinstance(result, AutopilotRunResult)
        assert hasattr(result, 'goals_completed')
        assert hasattr(result, 'goals_total')
        assert hasattr(result, 'total_cost_usd')


class TestStrategyIntegration:
    """Tests verifying integration with start() method using ExecutionStrategy.CONTINUE_ON_BLOCK."""

    def test_start_uses_continue_on_block_strategy(self, runner):
        """start() should use CONTINUE_ON_BLOCK strategy when configured."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]

        # Mock _execute_goals_continue_on_block to verify it's called
        with patch.object(runner, '_execute_goals_continue_on_block',
                         return_value=(2, 2.0, set())) as mock_continue_on_block:
            runner._execute_goal = MagicMock(
                return_value=GoalExecutionResult(
                    success=True,
                    cost_usd=1.0,
                    duration_seconds=60,
                )
            )
            runner._run_preflight = MagicMock(return_value=None)

            result = runner.start(goals=goals, budget_usd=100.0)

            # Verify _execute_goals_continue_on_block was called
            mock_continue_on_block.assert_called_once()
            assert result.goals_completed == 2

    def test_session_state_completed_when_all_goals_processed(self, runner):
        """Session state should be COMPLETED when all goals are processed."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.session.state == AutopilotState.COMPLETED

    def test_session_cost_updated_correctly(self, runner):
        """Session total_cost_usd should be updated correctly."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=2.5,
                duration_seconds=60,
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.session.total_cost_usd == 5.0  # 2.5 * 2


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_goals_list(self, runner):
        """Should handle empty goals list gracefully."""
        runner._execute_goal = MagicMock()
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=[], budget_usd=100.0)

        assert result.goals_completed == 0
        assert result.goals_total == 0
        assert result.total_cost_usd == 0.0

        # Should not call _execute_goal
        runner._execute_goal.assert_not_called()

    def test_single_goal_success(self, runner):
        """Should handle single successful goal correctly."""
        goals = [create_goal("goal-1")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.5,
                duration_seconds=60,
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.goals_completed == 1
        assert result.goals_total == 1
        assert result.total_cost_usd == 1.5
        assert goals[0].status == GoalStatus.COMPLETE

    def test_single_goal_failure(self, runner):
        """Should handle single failed goal correctly."""
        goals = [create_goal("goal-1")]

        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Blocked",
            )
        )
        runner._run_preflight = MagicMock(return_value=None)

        result = runner.start(goals=goals, budget_usd=100.0)

        assert result.goals_completed == 0
        assert result.goals_total == 1
        assert result.total_cost_usd == 0.5
        assert goals[0].status == GoalStatus.BLOCKED
        assert goals[0].is_hiccup is True


class TestFileExists:
    """Tests to verify implementation file exists."""

    def test_autopilot_runner_file_exists(self):
        """autopilot_runner.py must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        assert path.exists(), "autopilot_runner.py must exist"

    def test_execution_strategy_enum_exists(self):
        """ExecutionStrategy enum must exist in autopilot_runner.py."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "ExecutionStrategy" in content, (
            "ExecutionStrategy enum must be in autopilot_runner.py"
        )

    def test_continue_on_block_strategy_exists(self):
        """CONTINUE_ON_BLOCK strategy must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "CONTINUE_ON_BLOCK" in content, (
            "CONTINUE_ON_BLOCK strategy must be in autopilot_runner.py"
        )

    def test_execute_goals_continue_on_block_method_exists(self):
        """_execute_goals_continue_on_block method must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "_execute_goals_continue_on_block" in content, (
            "_execute_goals_continue_on_block method must be in autopilot_runner.py"
        )
