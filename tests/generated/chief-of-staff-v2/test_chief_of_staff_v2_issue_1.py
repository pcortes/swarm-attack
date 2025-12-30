"""Tests for DailyGoal tags field and AutopilotRunner orchestrator dependencies.

Issue 1: Add orchestrator dependency and tags field to DailyGoal
"""

import pytest
from unittest.mock import Mock, MagicMock

from swarm_attack.chief_of_staff.goal_tracker import (
    DailyGoal,
    GoalStatus,
    GoalPriority,
)
from swarm_attack.chief_of_staff.autopilot_runner import AutopilotRunner
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore


class TestDailyGoalTags:
    """Tests for the DailyGoal tags field."""

    def test_daily_goal_has_tags_field(self):
        """DailyGoal should have a tags field."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert hasattr(goal, "tags")

    def test_daily_goal_tags_default_empty_list(self):
        """DailyGoal tags should default to an empty list."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert goal.tags == []
        assert isinstance(goal.tags, list)

    def test_daily_goal_tags_can_be_set(self):
        """DailyGoal tags can be set at creation."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["enhancement", "backend"],
        )
        assert goal.tags == ["enhancement", "backend"]

    def test_daily_goal_to_dict_includes_tags(self):
        """DailyGoal.to_dict() should include tags."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["ux", "frontend"],
        )
        result = goal.to_dict()
        assert "tags" in result
        assert result["tags"] == ["ux", "frontend"]

    def test_daily_goal_to_dict_includes_empty_tags(self):
        """DailyGoal.to_dict() should include empty tags list."""
        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        result = goal.to_dict()
        assert "tags" in result
        assert result["tags"] == []

    def test_daily_goal_from_dict_with_tags(self):
        """DailyGoal.from_dict() should handle tags."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
            "tags": ["architect", "review"],
        }
        goal = DailyGoal.from_dict(data)
        assert goal.tags == ["architect", "review"]

    def test_daily_goal_from_dict_without_tags(self):
        """DailyGoal.from_dict() should default tags to empty list."""
        data = {
            "goal_id": "test-1",
            "description": "Test goal",
            "priority": "medium",
            "estimated_minutes": 30,
        }
        goal = DailyGoal.from_dict(data)
        assert goal.tags == []

    def test_daily_goal_roundtrip_with_tags(self):
        """DailyGoal serialization roundtrip preserves tags."""
        original = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            tags=["enhancement", "backend", "chief-of-staff-v2"],
        )
        roundtrip = DailyGoal.from_dict(original.to_dict())
        assert roundtrip.tags == original.tags
        assert roundtrip.goal_id == original.goal_id
        assert roundtrip.description == original.description


class TestAutopilotRunnerOrchestratorDependencies:
    """Tests for AutopilotRunner orchestrator dependencies."""

    def test_autopilot_runner_accepts_orchestrator(self):
        """AutopilotRunner __init__ accepts orchestrator parameter."""
        mock_orchestrator = Mock()
        mock_bug_orchestrator = Mock()
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session_store = Mock(spec=AutopilotSessionStore)

        runner = AutopilotRunner(
            orchestrator=mock_orchestrator,
            bug_orchestrator=mock_bug_orchestrator,
            checkpoint_system=checkpoint_system,
            config=config,
            session_store=session_store,
        )

        assert runner.orchestrator is mock_orchestrator

    def test_autopilot_runner_accepts_bug_orchestrator(self):
        """AutopilotRunner __init__ accepts bug_orchestrator parameter."""
        mock_orchestrator = Mock()
        mock_bug_orchestrator = Mock()
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session_store = Mock(spec=AutopilotSessionStore)

        runner = AutopilotRunner(
            orchestrator=mock_orchestrator,
            bug_orchestrator=mock_bug_orchestrator,
            checkpoint_system=checkpoint_system,
            config=config,
            session_store=session_store,
        )

        assert runner.bug_orchestrator is mock_bug_orchestrator

    def test_autopilot_runner_stores_orchestrators(self):
        """AutopilotRunner stores both orchestrators as instance attributes."""
        mock_orchestrator = Mock()
        mock_bug_orchestrator = Mock()
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session_store = Mock(spec=AutopilotSessionStore)

        runner = AutopilotRunner(
            orchestrator=mock_orchestrator,
            bug_orchestrator=mock_bug_orchestrator,
            checkpoint_system=checkpoint_system,
            config=config,
            session_store=session_store,
        )

        assert hasattr(runner, "orchestrator")
        assert hasattr(runner, "bug_orchestrator")
        assert runner.orchestrator is mock_orchestrator
        assert runner.bug_orchestrator is mock_bug_orchestrator

    def test_autopilot_runner_with_optional_orchestrators(self):
        """AutopilotRunner works with None orchestrators (backwards compat)."""
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session_store = Mock(spec=AutopilotSessionStore)

        runner = AutopilotRunner(
            orchestrator=None,
            bug_orchestrator=None,
            checkpoint_system=checkpoint_system,
            config=config,
            session_store=session_store,
        )

        assert runner.orchestrator is None
        assert runner.bug_orchestrator is None

    def test_autopilot_runner_initialization_order(self):
        """AutopilotRunner accepts parameters in the specified order."""
        mock_orchestrator = Mock()
        mock_bug_orchestrator = Mock()
        config = ChiefOfStaffConfig()
        checkpoint_system = CheckpointSystem(config)
        session_store = Mock(spec=AutopilotSessionStore)

        # Test positional argument order from spec:
        # orchestrator, bug_orchestrator, checkpoint_system, config
        runner = AutopilotRunner(
            orchestrator=mock_orchestrator,
            bug_orchestrator=mock_bug_orchestrator,
            checkpoint_system=checkpoint_system,
            config=config,
            session_store=session_store,
        )

        assert runner.config is config
        assert runner.checkpoint_system is checkpoint_system
        assert runner.orchestrator is mock_orchestrator
        assert runner.bug_orchestrator is mock_bug_orchestrator


class TestDailyGoalTagsFromGitHubLabels:
    """Tests for populating tags from GitHub issue labels."""

    def test_tags_from_github_labels_enhancement(self):
        """Tags should include 'enhancement' label from GitHub."""
        data = {
            "goal_id": "gh-123",
            "description": "Add new feature",
            "priority": "medium",
            "estimated_minutes": 60,
            "tags": ["enhancement"],
        }
        goal = DailyGoal.from_dict(data)
        assert "enhancement" in goal.tags

    def test_tags_from_github_labels_multiple(self):
        """Tags should include all labels from GitHub."""
        data = {
            "goal_id": "gh-456",
            "description": "Fix architecture issue",
            "priority": "high",
            "estimated_minutes": 120,
            "tags": ["enhancement", "backend", "chief-of-staff-v2", "architect"],
        }
        goal = DailyGoal.from_dict(data)
        assert "enhancement" in goal.tags
        assert "backend" in goal.tags
        assert "chief-of-staff-v2" in goal.tags
        assert "architect" in goal.tags
        assert len(goal.tags) == 4

    def test_tags_preserved_through_serialization(self):
        """Tags from GitHub labels should be preserved through serialization."""
        original_tags = ["bug", "ux", "high-priority"]
        goal = DailyGoal(
            goal_id="gh-789",
            description="Fix UX bug",
            priority=GoalPriority.HIGH,
            estimated_minutes=45,
            tags=original_tags,
        )
        
        serialized = goal.to_dict()
        restored = DailyGoal.from_dict(serialized)
        
        assert restored.tags == original_tags