"""Tests for goal state tracking and hiccup detection in _execute_goals_continue_on_block.

Issue #37: Implement goal state tracking and hiccup detection for continue-on-block

Tests verify:
- Track completed and blocked goal IDs in separate sets
- On success: set goal.status = GoalStatus.COMPLETE, add to completed set, increment goals_completed
- On failure: set goal.status = GoalStatus.BLOCKED, set goal.is_hiccup = True, add to blocked set
- Accumulate total_cost from each result.cost_usd
- Return (goals_completed, total_cost, blocked) tuple when done
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

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


class TestCompletedSetTracking:
    """Tests verifying completed goal IDs are tracked in a separate set."""

    def test_successful_goal_added_to_completed_set(self, runner, sample_session):
        """On success, goal_id should be added to completed set."""
        goal = create_goal("goal-1")
        goals = [goal]
        
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
        
        goals_completed, _, blocked_ids = result
        
        # goal-1 should be completed, not blocked
        assert goals_completed == 1
        assert "goal-1" not in blocked_ids

    def test_multiple_successful_goals_all_in_completed_set(self, runner, sample_session):
        """Multiple successful goals should all be tracked as completed."""
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
        
        goals_completed, _, blocked_ids = result
        
        assert goals_completed == 3
        assert len(blocked_ids) == 0

    def test_completed_set_and_blocked_set_are_separate(self, runner, sample_session):
        """Completed and blocked sets should be mutually exclusive."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        def mock_execute(goal):
            if goal.goal_id == "goal-1":
                return GoalExecutionResult(
                    success=True,
                    cost_usd=1.0,
                    duration_seconds=60,
                )
            return GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        
        runner._execute_goal = mock_execute
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, _, blocked_ids = result
        
        # goal-1 succeeded, goal-2 failed
        assert goals_completed == 1
        assert "goal-2" in blocked_ids
        assert "goal-1" not in blocked_ids


class TestBlockedSetTracking:
    """Tests verifying blocked goal IDs are tracked in a separate set."""

    def test_failed_goal_added_to_blocked_set(self, runner, sample_session):
        """On failure, goal_id should be added to blocked set."""
        goal = create_goal("goal-1")
        goals = [goal]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, _, blocked_ids = result
        
        assert "goal-1" in blocked_ids

    def test_multiple_failed_goals_all_in_blocked_set(self, runner, sample_session):
        """Multiple failed goals should all be in the blocked set."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, _, blocked_ids = result
        
        assert "goal-1" in blocked_ids
        assert "goal-2" in blocked_ids
        assert len(blocked_ids) == 2

    def test_blocked_set_is_python_set_type(self, runner, sample_session):
        """Blocked IDs should be returned as a Python set."""
        goal = create_goal("goal-1")
        goals = [goal]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, _, blocked_ids = result
        
        assert isinstance(blocked_ids, set)


class TestGoalStatusOnSuccess:
    """Tests verifying goal.status = GoalStatus.COMPLETE on success."""

    def test_successful_goal_status_set_to_complete(self, runner, sample_session):
        """On success, goal.status should be set to GoalStatus.COMPLETE."""
        goal = create_goal("goal-1")
        goals = [goal]
        
        # Verify initial status
        assert goal.status == GoalStatus.PENDING
        
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
        
        assert goal.status == GoalStatus.COMPLETE

    def test_all_successful_goals_have_complete_status(self, runner, sample_session):
        """All successful goals should have COMPLETE status."""
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
        
        for goal in goals:
            assert goal.status == GoalStatus.COMPLETE


class TestGoalStatusOnFailure:
    """Tests verifying goal.status = GoalStatus.BLOCKED on failure."""

    def test_failed_goal_status_set_to_blocked(self, runner, sample_session):
        """On failure, goal.status should be set to GoalStatus.BLOCKED."""
        goal = create_goal("goal-1")
        goals = [goal]
        
        # Verify initial status
        assert goal.status == GoalStatus.PENDING
        
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
        
        assert goal.status == GoalStatus.BLOCKED

    def test_all_failed_goals_have_blocked_status(self, runner, sample_session):
        """All failed goals should have BLOCKED status."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
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
        
        for goal in goals:
            assert goal.status == GoalStatus.BLOCKED


class TestIsHiccupFlagOnFailure:
    """Tests verifying goal.is_hiccup = True on failure."""

    def test_failed_goal_has_is_hiccup_true(self, runner, sample_session):
        """On failure, goal.is_hiccup should be set to True."""
        goal = create_goal("goal-1")
        goals = [goal]
        
        # Verify initial is_hiccup flag
        assert goal.is_hiccup is False
        
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
        
        assert goal.is_hiccup is True

    def test_all_failed_goals_have_is_hiccup_true(self, runner, sample_session):
        """All failed goals should have is_hiccup = True."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
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
        
        for goal in goals:
            assert goal.is_hiccup is True

    def test_successful_goal_has_is_hiccup_false(self, runner, sample_session):
        """Successful goals should NOT have is_hiccup set to True."""
        goal = create_goal("goal-1")
        goals = [goal]
        
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
        
        # is_hiccup should remain False for successful goals
        assert goal.is_hiccup is False


class TestGoalsCompletedIncrement:
    """Tests verifying goals_completed is incremented on success."""

    def test_goals_completed_incremented_on_success(self, runner, sample_session):
        """goals_completed should be incremented for each successful goal."""
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
        
        goals_completed, _, _ = result
        assert goals_completed == 1

    def test_goals_completed_not_incremented_on_failure(self, runner, sample_session):
        """goals_completed should NOT be incremented for failed goals."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, _, _ = result
        assert goals_completed == 0

    def test_goals_completed_counts_only_successes_in_mixed(self, runner, sample_session):
        """In mixed results, goals_completed should count only successes."""
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
        
        goals_completed, _, _ = result
        assert goals_completed == 2  # goal-1 and goal-3 succeeded


class TestTotalCostAccumulation:
    """Tests verifying total_cost accumulates from each result.cost_usd."""

    def test_total_cost_accumulates_from_single_goal(self, runner, sample_session):
        """total_cost should include cost from single executed goal."""
        goals = [create_goal("goal-1")]
        
        runner._execute_goal = MagicMock(
            return_value=GoalExecutionResult(
                success=True,
                cost_usd=2.5,
                duration_seconds=60,
            )
        )
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, total_cost, _ = result
        assert total_cost == 2.5

    def test_total_cost_accumulates_from_multiple_goals(self, runner, sample_session):
        """total_cost should sum costs from all executed goals."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        costs = [1.5, 2.5, 3.0]
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
        assert total_cost == 7.0  # 1.5 + 2.5 + 3.0

    def test_total_cost_includes_failed_goal_costs(self, runner, sample_session):
        """total_cost should include costs from failed goals too."""
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
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        _, total_cost, _ = result
        assert total_cost == 3.5  # 2.0 + 1.5

    def test_total_cost_is_float(self, runner, sample_session):
        """total_cost should be returned as a float."""
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
        
        _, total_cost, _ = result
        assert isinstance(total_cost, float)


class TestReturnTupleFormat:
    """Tests verifying the return tuple format (goals_completed, total_cost, blocked)."""

    def test_returns_tuple_of_three_elements(self, runner, sample_session):
        """Method should return a tuple with exactly 3 elements."""
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
        
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_return_tuple_types_are_correct(self, runner, sample_session):
        """Return tuple should have correct types: (int, float, set[str])."""
        goals = [create_goal("goal-1"), create_goal("goal-2")]
        
        def mock_execute(goal):
            if goal.goal_id == "goal-1":
                return GoalExecutionResult(
                    success=True,
                    cost_usd=1.0,
                    duration_seconds=60,
                )
            return GoalExecutionResult(
                success=False,
                cost_usd=0.5,
                duration_seconds=30,
                error="Test error",
            )
        
        runner._execute_goal = mock_execute
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, total_cost, blocked_ids = result
        
        assert isinstance(goals_completed, int)
        assert isinstance(total_cost, float)
        assert isinstance(blocked_ids, set)
        # Verify blocked_ids contains strings
        for item in blocked_ids:
            assert isinstance(item, str)

    def test_return_values_match_tracking(self, runner, sample_session):
        """Return values should accurately reflect execution tracking."""
        goals = [create_goal("goal-1"), create_goal("goal-2"), create_goal("goal-3")]
        
        def mock_execute(goal):
            # goal-2 and goal-3 fail
            if goal.goal_id == "goal-1":
                return GoalExecutionResult(
                    success=True,
                    cost_usd=3.0,
                    duration_seconds=60,
                )
            return GoalExecutionResult(
                success=False,
                cost_usd=1.0,
                duration_seconds=30,
                error="Test error",
            )
        
        runner._execute_goal = mock_execute
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, total_cost, blocked_ids = result
        
        assert goals_completed == 1  # Only goal-1 succeeded
        assert total_cost == 5.0  # 3.0 + 1.0 + 1.0
        assert blocked_ids == {"goal-2", "goal-3"}


class TestMixedSuccessAndFailure:
    """Integration tests for mixed success/failure scenarios."""

    def test_mixed_results_update_goal_statuses_correctly(self, runner, sample_session):
        """Mixed results should update goal statuses appropriately."""
        goal1 = create_goal("goal-1")
        goal2 = create_goal("goal-2")
        goal3 = create_goal("goal-3")
        goals = [goal1, goal2, goal3]
        
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
        
        runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        # Check statuses
        assert goal1.status == GoalStatus.COMPLETE
        assert goal2.status == GoalStatus.BLOCKED
        assert goal3.status == GoalStatus.COMPLETE
        
        # Check is_hiccup flags
        assert goal1.is_hiccup is False
        assert goal2.is_hiccup is True
        assert goal3.is_hiccup is False

    def test_mixed_results_correct_metrics(self, runner, sample_session):
        """Mixed results should produce correct metrics."""
        goals = [
            create_goal("goal-1"),
            create_goal("goal-2"),
            create_goal("goal-3"),
            create_goal("goal-4"),
        ]
        
        def mock_execute(goal):
            # goal-1 and goal-3 succeed, goal-2 and goal-4 fail
            if goal.goal_id in ("goal-1", "goal-3"):
                return GoalExecutionResult(
                    success=True,
                    cost_usd=2.0,
                    duration_seconds=60,
                )
            return GoalExecutionResult(
                success=False,
                cost_usd=1.0,
                duration_seconds=30,
                error="Test error",
            )
        
        runner._execute_goal = mock_execute
        
        result = runner._execute_goals_continue_on_block(
            goals=goals,
            budget_usd=100.0,
            session=sample_session,
        )
        
        goals_completed, total_cost, blocked_ids = result
        
        assert goals_completed == 2  # goal-1 and goal-3
        assert total_cost == 6.0  # 2.0 + 1.0 + 2.0 + 1.0
        assert blocked_ids == {"goal-2", "goal-4"}


class TestFileExists:
    """Tests to verify implementation file exists."""

    def test_autopilot_runner_file_exists(self):
        """autopilot_runner.py must exist."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        assert path.exists(), "autopilot_runner.py must exist"

    def test_goal_status_complete_used_in_file(self):
        """GoalStatus.COMPLETE should be used in autopilot_runner.py."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "GoalStatus.COMPLETE" in content, (
            "GoalStatus.COMPLETE must be used in autopilot_runner.py"
        )

    def test_goal_status_blocked_used_in_file(self):
        """GoalStatus.BLOCKED should be used in autopilot_runner.py."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "GoalStatus.BLOCKED" in content, (
            "GoalStatus.BLOCKED must be used in autopilot_runner.py"
        )

    def test_is_hiccup_flag_used_in_file(self):
        """is_hiccup flag should be set in autopilot_runner.py."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        content = path.read_text()
        assert "is_hiccup" in content, (
            "is_hiccup flag must be used in autopilot_runner.py"
        )