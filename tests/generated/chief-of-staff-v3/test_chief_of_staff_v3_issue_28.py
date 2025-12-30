"""Tests for ExecutionStrategy enum and DependencyGraph data model."""

import pytest
from enum import Enum
from pathlib import Path

from swarm_attack.chief_of_staff.autopilot_runner import (
    ExecutionStrategy,
    DependencyGraph,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalStatus, GoalPriority


class TestExecutionStrategy:
    """Tests for ExecutionStrategy enum."""

    def test_is_enum(self):
        """ExecutionStrategy should be an Enum."""
        assert issubclass(ExecutionStrategy, Enum)

    def test_has_sequential(self):
        """ExecutionStrategy should have SEQUENTIAL value."""
        assert hasattr(ExecutionStrategy, "SEQUENTIAL")
        assert ExecutionStrategy.SEQUENTIAL.value == "sequential"

    def test_has_continue_on_block(self):
        """ExecutionStrategy should have CONTINUE_ON_BLOCK value."""
        assert hasattr(ExecutionStrategy, "CONTINUE_ON_BLOCK")
        assert ExecutionStrategy.CONTINUE_ON_BLOCK.value == "continue_on_block"

    def test_has_parallel_safe(self):
        """ExecutionStrategy should have PARALLEL_SAFE value."""
        assert hasattr(ExecutionStrategy, "PARALLEL_SAFE")
        assert ExecutionStrategy.PARALLEL_SAFE.value == "parallel_safe"

    def test_all_values(self):
        """ExecutionStrategy should have exactly 3 values."""
        assert len(ExecutionStrategy) == 3


class TestDependencyGraph:
    """Tests for DependencyGraph dataclass."""

    def test_is_dataclass(self):
        """DependencyGraph should be a dataclass."""
        from dataclasses import is_dataclass
        assert is_dataclass(DependencyGraph)

    def test_has_issues_attribute(self):
        """DependencyGraph should have issues attribute."""
        graph = DependencyGraph(issues=[], dependencies={})
        assert hasattr(graph, "issues")
        assert graph.issues == []

    def test_has_dependencies_attribute(self):
        """DependencyGraph should have dependencies attribute."""
        graph = DependencyGraph(issues=[], dependencies={})
        assert hasattr(graph, "dependencies")
        assert graph.dependencies == {}

    def test_create_with_goals(self):
        """DependencyGraph can be created with goals."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(
            issues=[goal1, goal2],
            dependencies={"goal-2": ["goal-1"]}
        )
        
        assert len(graph.issues) == 2
        assert graph.dependencies["goal-2"] == ["goal-1"]


class TestDependencyGraphGetReadyGoals:
    """Tests for DependencyGraph.get_ready_goals() method."""

    def test_has_get_ready_goals_method(self):
        """DependencyGraph should have get_ready_goals method."""
        graph = DependencyGraph(issues=[], dependencies={})
        assert hasattr(graph, "get_ready_goals")
        assert callable(graph.get_ready_goals)

    def test_returns_goals_with_no_dependencies(self):
        """Goals with no dependencies should be ready."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(issues=[goal1, goal2], dependencies={})
        
        ready = graph.get_ready_goals(completed=set(), blocked=set())
        
        assert len(ready) == 2
        goal_ids = [g.goal_id for g in ready]
        assert "goal-1" in goal_ids
        assert "goal-2" in goal_ids

    def test_excludes_goals_with_unmet_dependencies(self):
        """Goals with unmet dependencies should not be ready."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(
            issues=[goal1, goal2],
            dependencies={"goal-2": ["goal-1"]}
        )
        
        ready = graph.get_ready_goals(completed=set(), blocked=set())
        
        assert len(ready) == 1
        assert ready[0].goal_id == "goal-1"

    def test_includes_goals_with_met_dependencies(self):
        """Goals whose dependencies are completed should be ready."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(
            issues=[goal1, goal2],
            dependencies={"goal-2": ["goal-1"]}
        )
        
        ready = graph.get_ready_goals(completed={"goal-1"}, blocked=set())
        
        assert len(ready) == 1
        assert ready[0].goal_id == "goal-2"

    def test_excludes_blocked_goals(self):
        """Blocked goals should not be returned."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(issues=[goal1, goal2], dependencies={})
        
        ready = graph.get_ready_goals(completed=set(), blocked={"goal-1"})
        
        assert len(ready) == 1
        assert ready[0].goal_id == "goal-2"

    def test_excludes_completed_goals(self):
        """Already completed goals should not be returned as ready."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(issues=[goal1, goal2], dependencies={})
        
        ready = graph.get_ready_goals(completed={"goal-1"}, blocked=set())
        
        assert len(ready) == 1
        assert ready[0].goal_id == "goal-2"

    def test_empty_graph_returns_empty_list(self):
        """Empty graph should return empty list."""
        graph = DependencyGraph(issues=[], dependencies={})
        
        ready = graph.get_ready_goals(completed=set(), blocked=set())
        
        assert ready == []

    def test_all_blocked_returns_empty_list(self):
        """If all goals are blocked, return empty list."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(issues=[goal1], dependencies={})
        
        ready = graph.get_ready_goals(completed=set(), blocked={"goal-1"})
        
        assert ready == []

    def test_multiple_dependencies_all_must_be_met(self):
        """Goal with multiple dependencies needs all to be completed."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal3 = DailyGoal(goal_id="goal-3", description="Third goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph(
            issues=[goal1, goal2, goal3],
            dependencies={"goal-3": ["goal-1", "goal-2"]}
        )
        
        # Only goal-1 completed - goal-3 still not ready
        ready = graph.get_ready_goals(completed={"goal-1"}, blocked=set())
        goal_ids = [g.goal_id for g in ready]
        assert "goal-3" not in goal_ids
        assert "goal-2" in goal_ids
        
        # Both dependencies completed - goal-3 now ready
        ready = graph.get_ready_goals(completed={"goal-1", "goal-2"}, blocked=set())
        goal_ids = [g.goal_id for g in ready]
        assert "goal-3" in goal_ids


class TestDependencyGraphFromGoals:
    """Tests for DependencyGraph.from_goals() factory method."""

    def test_has_from_goals_classmethod(self):
        """DependencyGraph should have from_goals classmethod."""
        assert hasattr(DependencyGraph, "from_goals")
        assert callable(DependencyGraph.from_goals)

    def test_creates_graph_from_goals(self):
        """from_goals should create a DependencyGraph from goal list."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph.from_goals([goal1, goal2])
        
        assert isinstance(graph, DependencyGraph)
        assert len(graph.issues) == 2
        assert graph.dependencies == {}

    def test_creates_empty_graph_from_empty_list(self):
        """from_goals with empty list creates empty graph."""
        graph = DependencyGraph.from_goals([])
        
        assert graph.issues == []
        assert graph.dependencies == {}

    def test_preserves_goal_order(self):
        """from_goals should preserve the order of goals."""
        goal1 = DailyGoal(goal_id="goal-1", description="First goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal2 = DailyGoal(goal_id="goal-2", description="Second goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        goal3 = DailyGoal(goal_id="goal-3", description="Third goal", priority=GoalPriority.MEDIUM, estimated_minutes=30)
        
        graph = DependencyGraph.from_goals([goal1, goal2, goal3])
        
        assert graph.issues[0].goal_id == "goal-1"
        assert graph.issues[1].goal_id == "goal-2"
        assert graph.issues[2].goal_id == "goal-3"


class TestFileExists:
    """Tests to verify implementation file exists."""

    def test_autopilot_runner_file_exists(self):
        """autopilot_runner.py must exist with ExecutionStrategy and DependencyGraph."""
        path = Path.cwd() / "swarm_attack" / "chief_of_staff" / "autopilot_runner.py"
        assert path.exists(), "autopilot_runner.py must exist"
        
        content = path.read_text()
        assert "class ExecutionStrategy" in content or "ExecutionStrategy" in content
        assert "class DependencyGraph" in content or "DependencyGraph" in content