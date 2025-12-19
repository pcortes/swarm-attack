"""Tests for _execute_goals_continue_on_block method in AutopilotRunner."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    DependencyGraph,
    GoalExecutionResult,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus, GoalPriority
from swarm_attack.chief_of_staff.autopilot import AutopilotSession, AutopilotState
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointResult
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
    # Default: no checkpoints triggered
    system.check_before_execution = AsyncMock(
        return_value=CheckpointResult(requires_approval=False, approved=True)
    )
    system.update_daily_cost = MagicMock()
    system.reset_daily_cost = MagicMock()
    system._create_checkpoint = MagicMock()
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


class TestExecuteGoalsContinueOnBlockExists:
    """Tests to verify method exists and has correct signature."""

    def test_has_method(self, runner):
        """AutopilotRunner should have _execute_goals_continue_on_block method."""
        assert hasattr(runner, "_execute_goals_continue_on_block")
        assert callable(runner._execute_goals_continue_on_block)

    def test_method_returns_tuple(self, runner, sample_session):
        """Method should return a tuple of (int, float, set[str])."""
        goals = [create_goal("goal-1")]
        
        # Mock _execute_goal to return success
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
        
        assert isinstance(result, tuple)
        assert len(result) == 3
        goals_completed, total_cost, blocked_ids = result
        assert isinstance(goals_completed, int)
        assert isinstance(total_cost, float)
        assert isinstance(blocked_ids, set)


class TestExecuteGoalsContinueOnBlockBuildsDependencyGraph:
    """Tests for DependencyGraph building."""

    def test_builds_dependency_graph_from_goals(self, runner, sample_session):
        """Method should build DependencyGraph from goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        # Mock _execute_goal to return success
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


class TestExecuteGoalsContinueOnBlockTracksCompleted:
    """Tests for tracking completed goals."""

    def test_tracks_completed_goals(self, runner, sample_session):
        """Method should track completed goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        # Both goals succeed
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert goals_completed == 2
        assert total_cost == 2.0
        assert len(blocked_ids) == 0

    def test_increments_cost_correctly(self, runner, sample_session):
        """Method should track total cost across all executed goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        # Each goal costs different amount
        costs = [1.5, 2.5, 3.0]
        call_count = [0]
        
        def mock_execute(goal):
            cost = costs[call_count[0]]
            call_count[0] += 1
            return GoalExecutionResult(
                success=True,
                cost_usd=cost,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert goals_completed == 3
        assert total_cost == 7.0  # 1.5 + 2.5 + 3.0


class TestExecuteGoalsContinueOnBlockTracksBlocked:
    """Tests for tracking blocked goals."""

    def test_tracks_blocked_goals(self, runner, sample_session):
        """Method should track blocked (failed) goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        # First goal fails, second succeeds
        call_count = [0]
        
        def mock_execute(goal):
            call_count[0] += 1
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
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert goals_completed == 1
        assert "goal-1" in blocked_ids
        assert "goal-2" not in blocked_ids

    def test_continues_past_blocked_goals(self, runner, sample_session):
        """Method should continue executing independent goals when some are blocked."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        # First goal fails but others can continue
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
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Should have executed goal-2 and goal-3 despite goal-1 failing
        assert goals_completed == 2
        assert len(blocked_ids) == 1
        assert "goal-1" in blocked_ids


class TestExecuteGoalsContinueOnBlockCreatesHiccupCheckpoint:
    """Tests for hiccup checkpoint creation when goals are blocked."""

    def test_creates_hiccup_checkpoint_when_goal_blocked(
        self, runner, mock_checkpoint_system, sample_session
    ):
        """Method should create HICCUP checkpoint when a goal is blocked."""
        goals = [create_goal("goal-1")]
        
        # Goal fails
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Should have created a hiccup checkpoint via checkpoint_system
        # The goal should be marked as hiccup
        assert goals[0].is_hiccup is True


class TestExecuteGoalsContinueOnBlockWithDependencies:
    """Tests for handling goals with dependencies."""

    def test_respects_dependencies(self, runner, sample_session):
        """Method should not execute goals with unmet dependencies."""
        goal1 = create_goal("goal-1")
        goal2 = create_goal("goal-2")
        
        # Create graph with dependency: goal-2 depends on goal-1
        graph = DependencyGraph(
            issues=[goal1, goal2],
            dependencies={"goal-2": ["goal-1"]}
        )
        
        # Goal-1 fails
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
        
        # Patch from_goals to return our custom graph
        with patch.object(DependencyGraph, "from_goals", return_value=graph):
            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=[goal1, goal2],
                budget_usd=100.0,
                session=sample_session,
            )
        
        # goal-2 should not be executed because goal-1 (its dependency) is blocked
        # Only goal-1 was attempted and failed
        assert goals_completed == 0
        assert "goal-1" in blocked_ids


class TestExecuteGoalsContinueOnBlockReturnsWhenNoReadyGoals:
    """Tests for termination when no ready goals remain."""

    def test_returns_when_all_completed(self, runner, sample_session):
        """Method should return when all goals are completed."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=1.0,
                duration_seconds=60,
            )
        )
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert goals_completed == 1
        assert len(blocked_ids) == 0

    def test_returns_when_all_blocked(self, runner, sample_session):
        """Method should return when all goals are blocked."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        # All goals fail
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert goals_completed == 0
        assert len(blocked_ids) == 2

    def test_returns_when_remaining_blocked_by_dependencies(self, runner, sample_session):
        """Method should return when remaining goals are blocked by dependencies."""
        goal1 = create_goal("goal-1")
        goal2 = create_goal("goal-2")
        goal3 = create_goal("goal-3")
        
        # goal-2 and goal-3 depend on goal-1
        graph = DependencyGraph(
            issues=[goal1, goal2, goal3],
            dependencies={"goal-2": ["goal-1"], "goal-3": ["goal-1"]}
        )
        
        # Goal-1 fails
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        with patch.object(DependencyGraph, "from_goals", return_value=graph):
            goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
                goals=[goal1, goal2, goal3],
                budget_usd=100.0,
                session=sample_session,
            )
        
        # Only goal-1 was attempted (failed)
        # goal-2 and goal-3 couldn't run because dependency not met
        assert goals_completed == 0
        assert "goal-1" in blocked_ids

    def test_handles_empty_goals_list(self, runner, sample_session):
        """Method should handle empty goals list gracefully."""
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=[],
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert goals_completed == 0
        assert total_cost == 0.0
        assert len(blocked_ids) == 0


class TestExecuteGoalsContinueOnBlockBudgetHandling:
    """Tests for budget handling during continue-on-block execution."""

    def test_stops_when_budget_exceeded(self, runner, sample_session, mock_config):
        """Method should stop when budget is exceeded."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        # Each goal costs 40.0 - budget is 100.0, so third should not run
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=40.0,
                duration_seconds=60,
            )
        )
        
        goals_completed, total_cost, blocked_ids = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Should execute 2 goals (80.0 spent), then have 20.0 remaining
        # which might be below min_execution_budget depending on config
        assert goals_completed >= 2
        assert total_cost <= 100.0


class TestExecuteGoalsContinueOnBlockCallbacks:
    """Tests for callback handling during continue-on-block execution."""

    def test_calls_on_goal_start_callback(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """Method should call on_goal_start callback for each executed goal."""
        started_goals = []
        
        def on_start(goal):
            started_goals.append(goal.goal_id)
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_start=on_start,
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
        
        assert "goal-1" in started_goals
        assert "goal-2" in started_goals

    def test_calls_on_goal_complete_callback(self, mock_config, mock_checkpoint_system, mock_session_store, sample_session):
        """Method should call on_goal_complete callback for each executed goal."""
        completed_goals = []
        
        def on_complete(goal, result):
            completed_goals.append((goal.goal_id, result.success))
        
        runner = AutopilotRunner(
            config=mock_config,
            checkpoint_system=mock_checkpoint_system,
            session_store=mock_session_store,
            on_goal_complete=on_complete,
        )
        
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        # First succeeds, second fails
        call_count = [0]
        
        def mock_execute(goal):
            call_count[0] += 1
            success = goal.goal_id == "goal-1"
            return GoalExecutionResult(
                success=success,
                cost_usd=1.0,
                duration_seconds=60,
            )
        
        runner._execute_goal = mock_execute
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        assert ("goal-1", True) in completed_goals
        assert ("goal-2", False) in completed_goals


class TestFileExists:
    """Tests to verify implementation file exists with required method."""

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

Now I'll output the implementation. Since I need to add a method to an existing file, I'll output the complete file with the new method added.