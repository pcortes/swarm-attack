"""Tests for core loop of _execute_goals_continue_on_block method in AutopilotRunner.

Issue #36: Implement core loop for _execute_goals_continue_on_block method

Tests verify:
- Method signature: (goals, budget_usd, session) -> tuple[int, float, set[str]]
- Method builds DependencyGraph.from_goals(goals) at start
- Method iteratively calls graph.get_ready_goals(completed, blocked) until no ready goals remain
- Method executes first ready goal via _execute_goal() in each iteration
- Method handles empty goals list by returning (0, 0.0, set())
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    DependencyGraph,
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


class TestMethodSignature:
    """Tests to verify method signature matches acceptance criteria."""

    def test_method_signature_accepts_goals_budget_session(self, runner, sample_session):
        """Method should accept goals: list[DailyGoal], budget_usd: float, session: AutopilotSession."""
        goals = [create_goal("goal-1")]
        budget_usd = 100.0
        
        # Mock _execute_goal to return success
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
            budget_usd=budget_usd,
            session=sample_session,
        )
        
        assert result is not None

    def test_return_type_is_tuple_int_float_set(self, runner, sample_session):
        """Method should return tuple[int, float, set[str]]."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.5,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert isinstance(result, tuple), "Return type must be tuple"
        assert len(result) == 3, "Tuple must have 3 elements"
        
        goals_completed, total_cost, blocked_ids = result
        assert isinstance(goals_completed, int), "First element must be int (goals_completed)"
        assert isinstance(total_cost, float), "Second element must be float (total_cost)"
        assert isinstance(blocked_ids, set), "Third element must be set (blocked_goal_ids)"


class TestDependencyGraphBuilding:
    """Tests verifying DependencyGraph is built from goals at start."""

    def test_builds_dependency_graph_from_goals_at_start(self, runner, sample_session):
        """Method should call DependencyGraph.from_goals(goals) at start."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        with patch.object(
            DependencyGraph, "from_goals", wraps=DependencyGraph.from_goals
        ) as mock_from_goals:
            runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=sample_session,
            )
            
            mock_from_goals.assert_called_once_with(goals)

    def test_dependency_graph_receives_all_goals(self, runner, sample_session):
        """DependencyGraph.from_goals should receive all goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        captured_goals = None
        
        original_from_goals = DependencyGraph.from_goals
        
        def capture_from_goals(g):
            nonlocal captured_goals
            captured_goals = g
            return original_from_goals(g)
        
        with patch.object(DependencyGraph, "from_goals", side_effect=capture_from_goals):
            runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=sample_session,
            )
        
        assert captured_goals is not None
        assert len(captured_goals) == 3
        assert [g.goal_id for g in captured_goals] == ["goal-1", "goal-2", "goal-3"]


class TestIterativeGetReadyGoals:
    """Tests verifying iterative calls to get_ready_goals until no ready goals remain."""

    def test_calls_get_ready_goals_until_no_ready_goals(self, runner, sample_session):
        """Method should call get_ready_goals iteratively until it returns empty list."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        # Track calls to get_ready_goals
        get_ready_calls = []
        original_get_ready = DependencyGraph.get_ready_goals
        
        def track_get_ready(self, completed, blocked):
            get_ready_calls.append((set(completed), set(blocked)))
            return original_get_ready(self, completed, blocked)
        
        with patch.object(DependencyGraph, "get_ready_goals", track_get_ready):
            runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=sample_session,
            )
        
        # Should have called get_ready_goals 3 times:
        # 1. Initial call with empty completed/blocked -> returns both goals
        # 2. After goal-1 completes -> returns goal-2
        # 3. After goal-2 completes -> returns empty (loop exits)
        assert len(get_ready_calls) >= 3
        
        # First call should have empty completed set
        assert get_ready_calls[0][0] == set()
        
        # Last call should return empty (verified by loop termination)
        # After all goals complete, completed set should have all goal_ids

    def test_stops_when_get_ready_goals_returns_empty(self, runner, sample_session):
        """Method should exit loop when get_ready_goals returns empty list."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Method should complete successfully
        goals_completed, total_cost, blocked_ids = result
        assert goals_completed == 1
        assert total_cost == 1.0

    def test_passes_completed_and_blocked_sets_to_get_ready_goals(self, runner, sample_session):
        """Method should pass completed and blocked sets to get_ready_goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        # First goal fails, second succeeds
        def mock_execute(goal):
            if goal.goal_id == "goal-1":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Test error",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        # Track completed and blocked sets passed to get_ready_goals
        calls_after_first_goal = []
        call_count = [0]
        original_get_ready = DependencyGraph.get_ready_goals
        
        def track_get_ready(self, completed, blocked):
            call_count[0] += 1
            if call_count[0] > 1:  # After first goal executed
                calls_after_first_goal.append((set(completed), set(blocked)))
            return original_get_ready(self, completed, blocked)
        
        with patch.object(DependencyGraph, "get_ready_goals", track_get_ready):
            runner._execute_goals_continue_on_block(
                goals=goals,
                budget_usd=100.0,
                session=sample_session,
            )
        
        # After goal-1 fails, blocked set should contain "goal-1"
        assert len(calls_after_first_goal) >= 1
        _, blocked = calls_after_first_goal[0]
        assert "goal-1" in blocked


class TestExecutesFirstReadyGoal:
    """Tests verifying that method executes first ready goal via _execute_goal()."""

    def test_executes_first_ready_goal_in_each_iteration(self, runner, sample_session):
        """Method should execute first ready goal via _execute_goal() in each iteration."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        executed_goals = []
        
        def track_execute(goal):
            executed_goals.append(goal.goal_id)
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        
        runner._execute_goal = track_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Should have executed all 3 goals
        assert len(executed_goals) == 3
        assert "goal-1" in executed_goals
        assert "goal-2" in executed_goals
        assert "goal-3" in executed_goals

    def test_executes_goals_one_at_a_time(self, runner, sample_session):
        """Method should execute goals one at a time, not in parallel."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        execution_order = []
        
        def track_execute(goal):
            execution_order.append(f"start-{goal.goal_id}")
            result = GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
            execution_order.append(f"end-{goal.goal_id}")
            return result
        
        runner._execute_goal = track_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Verify sequential execution (start-end pairs)
        assert execution_order[0].startswith("start-")
        assert execution_order[1].startswith("end-")
        assert execution_order[0].replace("start-", "") == execution_order[1].replace("end-", "")

    def test_calls_execute_goal_method(self, runner, sample_session):
        """Method should call _execute_goal to execute each goal."""
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
        
        runner._execute_goal.assert_called_once()
        called_goal = runner._execute_goal.call_args[0][0]
        assert called_goal.goal_id == "goal-1"


class TestEmptyGoalsListHandling:
    """Tests verifying empty goals list returns (0, 0.0, set())."""

    def test_empty_goals_returns_zero_completed(self, runner, sample_session):
        """Method should return 0 goals completed for empty list."""
        result = runner._execute_goals_continue_on_block(
            goals=[],
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, _, _ = result
        assert goals_completed == 0

    def test_empty_goals_returns_zero_cost(self, runner, sample_session):
        """Method should return 0.0 total cost for empty list."""
        result = runner._execute_goals_continue_on_block(
            goals=[],
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, total_cost, _ = result
        assert total_cost == 0.0

    def test_empty_goals_returns_empty_blocked_set(self, runner, sample_session):
        """Method should return empty blocked set for empty list."""
        result = runner._execute_goals_continue_on_block(
            goals=[],
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, _, blocked_ids = result
        assert blocked_ids == set()

    def test_empty_goals_exact_return_value(self, runner, sample_session):
        """Method should return exactly (0, 0.0, set()) for empty list."""
        result = runner._execute_goals_continue_on_block(
            goals=[],
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert result == (0, 0.0, set())


class TestCoreLoopBehavior:
    """Integration tests for the core loop behavior."""

    def test_loop_processes_all_ready_goals(self, runner, sample_session):
        """Core loop should process all ready goals until none remain."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, total_cost, blocked_ids = result
        
        assert goals_completed == 3
        assert total_cost == 3.0
        assert len(blocked_ids) == 0

    def test_loop_handles_mixed_success_failure(self, runner, sample_session):
        """Core loop should handle mixed success and failure results."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        def mock_execute(goal):
            # goal-2 fails
            if goal.goal_id == "goal-2":
                return GoalExecutionResult(
                    success=False,
                    cost_usd=0.5,
                    duration_seconds=30,
                    error="Test error",
                )
            return GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, total_cost, blocked_ids = result
        
        assert goals_completed == 2  # goal-1 and goal-3
        assert "goal-2" in blocked_ids
        assert len(blocked_ids) == 1

    def test_loop_accumulates_costs_correctly(self, runner, sample_session):
        """Core loop should accumulate costs from all executed goals."""
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
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, total_cost, _ = result
        
        assert total_cost == 6.0  # 2.5 + 3.5


class TestFileExists:
    """Tests to verify implementation file exists."""

    def test_autopilot_runner_file_exists(self):
        """autopilot_runner.py must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        assert path.exists(), "autopilot_runner.py must exist"

    def test_method_in_file(self):
        """_execute_goals_continue_on_block method must be in autopilot_runner.py."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "_execute_goals_continue_on_block" in content, (
            "_execute_goals_continue_on_block method must be in autopilot_runner.py"
        )

    def test_dependency_graph_class_exists(self):
        """DependencyGraph class must exist in autopilot_runner.py."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "class DependencyGraph" in content, (
            "DependencyGraph class must be in autopilot_runner.py"
        )