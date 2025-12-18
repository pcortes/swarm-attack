"""Tests for Issue #5: Pre-execution budget checks and estimated_cost_usd field.

This test file verifies:
1. DailyGoal has new fields: estimated_cost_usd, is_unplanned, error_count, is_hiccup
2. DailyGoal to_dict() and from_dict() handle all new fields
3. Default estimated cost values by goal type (feature=$3, bug=$2, spec=$1)
4. _execute_goal() checks remaining budget before execution
5. Returns failure if remaining_budget < config.min_execution_budget
6. ChiefOfStaffConfig has min_execution_budget field (default 0.50)
"""

import pytest
from typing import Any
from unittest.mock import MagicMock, patch

from swarm_attack.chief_of_staff.goal_tracker import (
    DailyGoal,
    GoalPriority,
    GoalStatus,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_runner import (
    AutopilotRunner,
    GoalExecutionResult,
)
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem


class TestDailyGoalNewFields:
    """Tests for new DailyGoal fields."""

    def test_estimated_cost_usd_field_exists(self):
        """DailyGoal has estimated_cost_usd field with None default."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert hasattr(goal, "estimated_cost_usd")
        assert goal.estimated_cost_usd is None

    def test_estimated_cost_usd_can_be_set(self):
        """estimated_cost_usd can be set to a float value."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=3.50,
        )
        assert goal.estimated_cost_usd == 3.50

    def test_is_unplanned_field_exists(self):
        """DailyGoal has is_unplanned field with False default."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert hasattr(goal, "is_unplanned")
        assert goal.is_unplanned is False

    def test_is_unplanned_can_be_set(self):
        """is_unplanned can be set to True."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            is_unplanned=True,
        )
        assert goal.is_unplanned is True

    def test_error_count_field_exists(self):
        """DailyGoal has error_count field with 0 default."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert hasattr(goal, "error_count")
        assert goal.error_count == 0

    def test_error_count_can_be_set(self):
        """error_count can be set to an integer value."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            error_count=5,
        )
        assert goal.error_count == 5

    def test_is_hiccup_field_exists(self):
        """DailyGoal has is_hiccup field with False default."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert hasattr(goal, "is_hiccup")
        assert goal.is_hiccup is False

    def test_is_hiccup_can_be_set(self):
        """is_hiccup can be set to True."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            is_hiccup=True,
        )
        assert goal.is_hiccup is True


class TestDailyGoalSerialization:
    """Tests for DailyGoal to_dict and from_dict with new fields."""

    def test_to_dict_includes_estimated_cost_usd(self):
        """to_dict includes estimated_cost_usd field."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            estimated_cost_usd=2.50,
        )
        result = goal.to_dict()
        assert "estimated_cost_usd" in result
        assert result["estimated_cost_usd"] == 2.50

    def test_to_dict_includes_is_unplanned(self):
        """to_dict includes is_unplanned field."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            is_unplanned=True,
        )
        result = goal.to_dict()
        assert "is_unplanned" in result
        assert result["is_unplanned"] is True

    def test_to_dict_includes_error_count(self):
        """to_dict includes error_count field."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            error_count=3,
        )
        result = goal.to_dict()
        assert "error_count" in result
        assert result["error_count"] == 3

    def test_to_dict_includes_is_hiccup(self):
        """to_dict includes is_hiccup field."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            is_hiccup=True,
        )
        result = goal.to_dict()
        assert "is_hiccup" in result
        assert result["is_hiccup"] is True

    def test_from_dict_parses_estimated_cost_usd(self):
        """from_dict parses estimated_cost_usd field."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
            "estimated_cost_usd": 5.00,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.estimated_cost_usd == 5.00

    def test_from_dict_parses_is_unplanned(self):
        """from_dict parses is_unplanned field."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
            "is_unplanned": True,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.is_unplanned is True

    def test_from_dict_parses_error_count(self):
        """from_dict parses error_count field."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
            "error_count": 7,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.error_count == 7

    def test_from_dict_parses_is_hiccup(self):
        """from_dict parses is_hiccup field."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
            "is_hiccup": True,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.is_hiccup is True

    def test_from_dict_defaults_estimated_cost_usd_to_none(self):
        """from_dict defaults estimated_cost_usd to None when not provided."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.estimated_cost_usd is None

    def test_from_dict_defaults_is_unplanned_to_false(self):
        """from_dict defaults is_unplanned to False when not provided."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.is_unplanned is False

    def test_from_dict_defaults_error_count_to_zero(self):
        """from_dict defaults error_count to 0 when not provided."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.error_count == 0

    def test_from_dict_defaults_is_hiccup_to_false(self):
        """from_dict defaults is_hiccup to False when not provided."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.is_hiccup is False

    def test_roundtrip_all_new_fields(self):
        """to_dict -> from_dict preserves all new fields."""
        original = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=45,
            estimated_cost_usd=4.25,
            is_unplanned=True,
            error_count=2,
            is_hiccup=True,
        )
        data = original.to_dict()
        restored = DailyGoal.from_dict(data)

        assert restored.estimated_cost_usd == original.estimated_cost_usd
        assert restored.is_unplanned == original.is_unplanned
        assert restored.error_count == original.error_count
        assert restored.is_hiccup == original.is_hiccup


class TestChiefOfStaffConfigMinExecutionBudget:
    """Tests for ChiefOfStaffConfig.min_execution_budget field."""

    def test_min_execution_budget_field_exists(self):
        """ChiefOfStaffConfig has min_execution_budget field."""
        config = ChiefOfStaffConfig()
        assert hasattr(config, "min_execution_budget")

    def test_min_execution_budget_default_value(self):
        """min_execution_budget defaults to 0.50."""
        config = ChiefOfStaffConfig()
        assert config.min_execution_budget == 0.50

    def test_min_execution_budget_can_be_set(self):
        """min_execution_budget can be set to a custom value."""
        config = ChiefOfStaffConfig(min_execution_budget=1.00)
        assert config.min_execution_budget == 1.00

    def test_from_dict_parses_min_execution_budget(self):
        """from_dict parses min_execution_budget field."""
        data = {"min_execution_budget": 0.75}
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.min_execution_budget == 0.75

    def test_from_dict_defaults_min_execution_budget(self):
        """from_dict defaults min_execution_budget to 0.50."""
        data = {}
        config = ChiefOfStaffConfig.from_dict(data)
        assert config.min_execution_budget == 0.50

    def test_to_dict_includes_min_execution_budget(self):
        """to_dict includes min_execution_budget field."""
        config = ChiefOfStaffConfig(min_execution_budget=0.80)
        data = config.to_dict()
        assert "min_execution_budget" in data
        assert data["min_execution_budget"] == 0.80

    def test_roundtrip_min_execution_budget(self):
        """to_dict -> from_dict preserves min_execution_budget."""
        original = ChiefOfStaffConfig(min_execution_budget=1.25)
        data = original.to_dict()
        restored = ChiefOfStaffConfig.from_dict(data)
        assert restored.min_execution_budget == original.min_execution_budget


class TestDefaultCostEstimation:
    """Tests for default cost estimation by goal type."""

    def test_feature_goal_default_cost(self):
        """Feature-linked goals have default estimated cost of $3."""
        from swarm_attack.chief_of_staff.budget import get_default_estimated_cost

        goal = DailyGoal(
            goal_id="test-1",
            description="Implement feature",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            linked_feature="my-feature",
        )
        cost = get_default_estimated_cost(goal)
        assert cost == 3.0

    def test_bug_goal_default_cost(self):
        """Bug-linked goals have default estimated cost of $2."""
        from swarm_attack.chief_of_staff.budget import get_default_estimated_cost

        goal = DailyGoal(
            goal_id="test-1",
            description="Fix bug",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            linked_bug="bug-123",
        )
        cost = get_default_estimated_cost(goal)
        assert cost == 2.0

    def test_spec_goal_default_cost(self):
        """Spec-linked goals have default estimated cost of $1."""
        from swarm_attack.chief_of_staff.budget import get_default_estimated_cost

        goal = DailyGoal(
            goal_id="test-1",
            description="Review spec",
            priority=GoalPriority.LOW,
            estimated_minutes=20,
            linked_spec="spec-xyz",
        )
        cost = get_default_estimated_cost(goal)
        assert cost == 1.0

    def test_manual_goal_default_cost_zero(self):
        """Manual goals (no links) have default estimated cost of $0."""
        from swarm_attack.chief_of_staff.budget import get_default_estimated_cost

        goal = DailyGoal(
            goal_id="test-1",
            description="Manual task",
            priority=GoalPriority.LOW,
            estimated_minutes=10,
        )
        cost = get_default_estimated_cost(goal)
        assert cost == 0.0

    def test_explicit_cost_overrides_default(self):
        """Explicit estimated_cost_usd takes precedence over default."""
        from swarm_attack.chief_of_staff.budget import get_effective_cost

        goal = DailyGoal(
            goal_id="test-1",
            description="Implement feature",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            linked_feature="my-feature",
            estimated_cost_usd=5.0,  # Explicit override
        )
        cost = get_effective_cost(goal)
        assert cost == 5.0  # Uses explicit, not default $3


class TestBudgetCheckBeforeExecution:
    """Tests for budget check before goal execution."""

    def test_check_budget_returns_true_when_sufficient(self):
        """check_budget returns True when remaining budget is sufficient."""
        from swarm_attack.chief_of_staff.budget import check_budget

        remaining = 5.0
        min_budget = 0.50
        result = check_budget(remaining, min_budget)
        assert result is True

    def test_check_budget_returns_false_when_insufficient(self):
        """check_budget returns False when remaining budget < min_execution_budget."""
        from swarm_attack.chief_of_staff.budget import check_budget

        remaining = 0.40
        min_budget = 0.50
        result = check_budget(remaining, min_budget)
        assert result is False

    def test_check_budget_edge_case_equal(self):
        """check_budget returns True when remaining equals min_execution_budget."""
        from swarm_attack.chief_of_staff.budget import check_budget

        remaining = 0.50
        min_budget = 0.50
        result = check_budget(remaining, min_budget)
        assert result is True

    def test_check_budget_zero_remaining(self):
        """check_budget returns False when remaining is zero."""
        from swarm_attack.chief_of_staff.budget import check_budget

        remaining = 0.0
        min_budget = 0.50
        result = check_budget(remaining, min_budget)
        assert result is False


class TestExecuteGoalBudgetCheck:
    """Tests for _execute_goal budget check integration."""

    def _create_runner(
        self, min_execution_budget: float = 0.50
    ) -> tuple[AutopilotRunner, MagicMock, MagicMock]:
        """Create an AutopilotRunner with mocked dependencies."""
        config = ChiefOfStaffConfig(min_execution_budget=min_execution_budget)
        checkpoint_system = MagicMock(spec=CheckpointSystem)
        session_store = MagicMock()

        runner = AutopilotRunner(
            config=config,
            checkpoint_system=checkpoint_system,
            session_store=session_store,
        )
        return runner, checkpoint_system, session_store

    def test_execute_goal_fails_when_budget_insufficient(self):
        """_execute_goal returns failure when budget is insufficient."""
        runner, _, _ = self._create_runner(min_execution_budget=0.50)

        goal = DailyGoal(
            goal_id="test-1",
            description="Implement feature",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            linked_feature="my-feature",
        )

        # Set session context with insufficient budget
        result = runner._execute_goal_with_budget_check(
            goal=goal,
            remaining_budget=0.30,  # Less than min_execution_budget
        )

        assert result.success is False
        assert "budget" in result.error.lower()

    def test_execute_goal_succeeds_when_budget_sufficient(self):
        """_execute_goal proceeds when budget is sufficient."""
        runner, _, _ = self._create_runner(min_execution_budget=0.50)

        goal = DailyGoal(
            goal_id="test-1",
            description="Implement feature",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            linked_feature="my-feature",
        )

        # Mock _execute_goal to return success (testing budget check, not execution)
        from swarm_attack.chief_of_staff.autopilot_runner import GoalExecutionResult
        runner._execute_goal = MagicMock(return_value=GoalExecutionResult(
            success=True,
            cost_usd=2.0,
            duration_seconds=60,
            error=None,
            output="Test output",
        ))

        # Set session context with sufficient budget
        result = runner._execute_goal_with_budget_check(
            goal=goal,
            remaining_budget=5.0,  # More than min_execution_budget
        )

        assert result.success is True
        assert result.error is None

    def test_execute_goal_checks_before_orchestrator_call(self):
        """Budget is checked BEFORE any orchestrator call (David Dohan requirement)."""
        runner, _, _ = self._create_runner(min_execution_budget=0.50)

        # Mock the orchestrator
        mock_orchestrator = MagicMock()
        runner.orchestrator = mock_orchestrator

        goal = DailyGoal(
            goal_id="test-1",
            description="Implement feature",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
            linked_feature="my-feature",
        )

        # Call with insufficient budget
        result = runner._execute_goal_with_budget_check(
            goal=goal,
            remaining_budget=0.30,
        )

        # Verify orchestrator was never called
        mock_orchestrator.run_feature.assert_not_called()
        assert result.success is False


class TestRemainingBudgetCalculation:
    """Tests for remaining budget calculation."""

    def test_calculate_remaining_budget(self):
        """Remaining budget = session.budget_usd - session.cost_spent_usd."""
        from swarm_attack.chief_of_staff.budget import calculate_remaining_budget

        budget_usd = 10.0
        cost_spent_usd = 3.50
        remaining = calculate_remaining_budget(budget_usd, cost_spent_usd)
        assert remaining == 6.50

    def test_calculate_remaining_budget_all_spent(self):
        """Remaining budget is zero when all budget is spent."""
        from swarm_attack.chief_of_staff.budget import calculate_remaining_budget

        budget_usd = 10.0
        cost_spent_usd = 10.0
        remaining = calculate_remaining_budget(budget_usd, cost_spent_usd)
        assert remaining == 0.0

    def test_calculate_remaining_budget_nothing_spent(self):
        """Remaining budget equals total when nothing spent."""
        from swarm_attack.chief_of_staff.budget import calculate_remaining_budget

        budget_usd = 10.0
        cost_spent_usd = 0.0
        remaining = calculate_remaining_budget(budget_usd, cost_spent_usd)
        assert remaining == 10.0


class TestBudgetModuleExists:
    """Tests that the budget module exists and is importable."""

    def test_budget_module_importable(self):
        """The budget module can be imported."""
        from swarm_attack.chief_of_staff import budget
        assert budget is not None

    def test_budget_module_has_required_functions(self):
        """The budget module has all required functions."""
        from swarm_attack.chief_of_staff import budget

        assert hasattr(budget, "get_default_estimated_cost")
        assert hasattr(budget, "get_effective_cost")
        assert hasattr(budget, "check_budget")
        assert hasattr(budget, "calculate_remaining_budget")