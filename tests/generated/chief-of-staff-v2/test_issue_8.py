"""Tests for checkpoint creation methods in CheckpointSystem.

Issue #8: Implement checkpoint creation methods
- _create_checkpoint(goal, trigger) creates Checkpoint with context, options, recommendation
- _build_context(goal, trigger) generates context string per trigger type
- _build_options(goal, trigger) returns list: Proceed, Skip, Modify, Pause
- _build_recommendation(goal, trigger) generates recommendation string
- Proceed option marked as is_recommended for most triggers
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointSystem,
    CheckpointTrigger,
    Checkpoint,
    CheckpointOption,
    CheckpointStore,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


class TestCreateCheckpoint:
    """Tests for _create_checkpoint method."""

    def test_create_checkpoint_returns_checkpoint(self):
        """_create_checkpoint returns a Checkpoint instance."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )
        trigger = CheckpointTrigger.UX_CHANGE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert isinstance(checkpoint, Checkpoint)

    def test_create_checkpoint_has_correct_goal_id(self):
        """Checkpoint has goal_id matching the input goal."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="my-goal-123",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
        )
        trigger = CheckpointTrigger.ARCHITECTURE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert checkpoint.goal_id == "my-goal-123"

    def test_create_checkpoint_has_correct_trigger(self):
        """Checkpoint has trigger matching the input trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.LOW,
            estimated_minutes=15,
        )
        trigger = CheckpointTrigger.COST_SINGLE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert checkpoint.trigger == CheckpointTrigger.COST_SINGLE

    def test_create_checkpoint_has_context(self):
        """Checkpoint has non-empty context string."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Implement user login",
            priority=GoalPriority.HIGH,
            estimated_minutes=45,
        )
        trigger = CheckpointTrigger.SCOPE_CHANGE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert checkpoint.context
        assert isinstance(checkpoint.context, str)
        assert len(checkpoint.context) > 0

    def test_create_checkpoint_has_options(self):
        """Checkpoint has list of options."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        trigger = CheckpointTrigger.HICCUP

        checkpoint = system._create_checkpoint(goal, trigger)

        assert isinstance(checkpoint.options, list)
        assert len(checkpoint.options) > 0
        assert all(isinstance(opt, CheckpointOption) for opt in checkpoint.options)

    def test_create_checkpoint_has_recommendation(self):
        """Checkpoint has non-empty recommendation string."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )
        trigger = CheckpointTrigger.UX_CHANGE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert checkpoint.recommendation
        assert isinstance(checkpoint.recommendation, str)
        assert len(checkpoint.recommendation) > 0

    def test_create_checkpoint_has_pending_status(self):
        """Checkpoint starts with pending status."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        trigger = CheckpointTrigger.ARCHITECTURE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert checkpoint.status == "pending"

    def test_create_checkpoint_has_created_at_timestamp(self):
        """Checkpoint has created_at timestamp."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )
        trigger = CheckpointTrigger.COST_CUMULATIVE

        checkpoint = system._create_checkpoint(goal, trigger)

        assert checkpoint.created_at
        # Should be valid ISO format
        datetime.fromisoformat(checkpoint.created_at)

    def test_create_checkpoint_has_unique_id(self):
        """Each checkpoint has a unique checkpoint_id."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        checkpoint1 = system._create_checkpoint(goal, CheckpointTrigger.UX_CHANGE)
        checkpoint2 = system._create_checkpoint(goal, CheckpointTrigger.ARCHITECTURE)

        assert checkpoint1.checkpoint_id != checkpoint2.checkpoint_id


class TestBuildContext:
    """Tests for _build_context method."""

    def test_build_context_for_ux_change(self):
        """Context for UX_CHANGE mentions UI/UX impact."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Redesign login page",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            tags=["ui", "frontend"],
        )

        context = system._build_context(goal, CheckpointTrigger.UX_CHANGE)

        assert "ux" in context.lower() or "ui" in context.lower() or "user" in context.lower()

    def test_build_context_for_cost_single(self):
        """Context for COST_SINGLE mentions cost threshold."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Complex feature",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            estimated_cost_usd=10.0,
        )

        context = system._build_context(goal, CheckpointTrigger.COST_SINGLE)

        assert "cost" in context.lower() or "$" in context or "budget" in context.lower()

    def test_build_context_for_cost_cumulative(self):
        """Context for COST_CUMULATIVE mentions daily budget."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Another feature",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        context = system._build_context(goal, CheckpointTrigger.COST_CUMULATIVE)

        assert "daily" in context.lower() or "cumulative" in context.lower() or "budget" in context.lower()

    def test_build_context_for_architecture(self):
        """Context for ARCHITECTURE mentions architectural impact."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Refactor database layer",
            priority=GoalPriority.HIGH,
            estimated_minutes=90,
            tags=["architecture", "refactor"],
        )

        context = system._build_context(goal, CheckpointTrigger.ARCHITECTURE)

        assert "architect" in context.lower() or "structural" in context.lower() or "refactor" in context.lower()

    def test_build_context_for_scope_change(self):
        """Context for SCOPE_CHANGE mentions unplanned work."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Unplanned bug fix",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            is_unplanned=True,
        )

        context = system._build_context(goal, CheckpointTrigger.SCOPE_CHANGE)

        assert "unplanned" in context.lower() or "scope" in context.lower()

    def test_build_context_for_hiccup(self):
        """Context for HICCUP mentions errors or issues."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Failing tests",
            priority=GoalPriority.HIGH,
            estimated_minutes=45,
            error_count=3,
            is_hiccup=True,
        )

        context = system._build_context(goal, CheckpointTrigger.HICCUP)

        assert "error" in context.lower() or "issue" in context.lower() or "hiccup" in context.lower()

    def test_build_context_includes_goal_description(self):
        """Context includes the goal description."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Implement payment processing feature",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
        )

        context = system._build_context(goal, CheckpointTrigger.UX_CHANGE)

        assert "payment" in context.lower() or goal.description in context


class TestBuildOptions:
    """Tests for _build_options method."""

    def test_build_options_returns_list(self):
        """_build_options returns a list."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.UX_CHANGE)

        assert isinstance(options, list)

    def test_build_options_returns_checkpoint_options(self):
        """All items in options are CheckpointOption instances."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.ARCHITECTURE)

        assert all(isinstance(opt, CheckpointOption) for opt in options)

    def test_build_options_has_proceed(self):
        """Options include a Proceed option."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.COST_SINGLE)

        labels = [opt.label.lower() for opt in options]
        assert any("proceed" in label for label in labels)

    def test_build_options_has_skip(self):
        """Options include a Skip option."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.SCOPE_CHANGE)

        labels = [opt.label.lower() for opt in options]
        assert any("skip" in label for label in labels)

    def test_build_options_has_modify(self):
        """Options include a Modify option."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.HICCUP)

        labels = [opt.label.lower() for opt in options]
        assert any("modify" in label for label in labels)

    def test_build_options_has_pause(self):
        """Options include a Pause option."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.LOW,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.COST_CUMULATIVE)

        labels = [opt.label.lower() for opt in options]
        assert any("pause" in label for label in labels)

    def test_build_options_four_standard_options(self):
        """Options include exactly four standard options."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.UX_CHANGE)

        assert len(options) == 4

    def test_options_have_descriptions(self):
        """Each option has a non-empty description."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.ARCHITECTURE)

        for opt in options:
            assert opt.description
            assert len(opt.description) > 0


class TestBuildRecommendation:
    """Tests for _build_recommendation method."""

    def test_build_recommendation_returns_string(self):
        """_build_recommendation returns a string."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        recommendation = system._build_recommendation(goal, CheckpointTrigger.UX_CHANGE)

        assert isinstance(recommendation, str)

    def test_build_recommendation_not_empty(self):
        """Recommendation is not empty."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        recommendation = system._build_recommendation(goal, CheckpointTrigger.COST_SINGLE)

        assert len(recommendation) > 0

    def test_build_recommendation_for_ux_change(self):
        """Recommendation for UX_CHANGE trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Update button styles",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            tags=["ui"],
        )

        recommendation = system._build_recommendation(goal, CheckpointTrigger.UX_CHANGE)

        assert isinstance(recommendation, str)
        assert len(recommendation) > 10  # Should be a meaningful recommendation

    def test_build_recommendation_for_hiccup(self):
        """Recommendation for HICCUP mentions reviewing errors."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Fix failing tests",
            priority=GoalPriority.HIGH,
            estimated_minutes=45,
            error_count=5,
            is_hiccup=True,
        )

        recommendation = system._build_recommendation(goal, CheckpointTrigger.HICCUP)

        assert "error" in recommendation.lower() or "issue" in recommendation.lower() or "review" in recommendation.lower()


class TestProceedRecommended:
    """Tests for Proceed being marked as is_recommended."""

    def test_proceed_is_recommended_for_ux_change(self):
        """Proceed is recommended for UX_CHANGE trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.UX_CHANGE)

        proceed_option = next((opt for opt in options if "proceed" in opt.label.lower()), None)
        assert proceed_option is not None
        assert proceed_option.is_recommended is True

    def test_proceed_is_recommended_for_architecture(self):
        """Proceed is recommended for ARCHITECTURE trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.ARCHITECTURE)

        proceed_option = next((opt for opt in options if "proceed" in opt.label.lower()), None)
        assert proceed_option is not None
        assert proceed_option.is_recommended is True

    def test_proceed_is_recommended_for_scope_change(self):
        """Proceed is recommended for SCOPE_CHANGE trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.SCOPE_CHANGE)

        proceed_option = next((opt for opt in options if "proceed" in opt.label.lower()), None)
        assert proceed_option is not None
        assert proceed_option.is_recommended is True

    def test_proceed_is_recommended_for_cost_single(self):
        """Proceed is recommended for COST_SINGLE trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.COST_SINGLE)

        proceed_option = next((opt for opt in options if "proceed" in opt.label.lower()), None)
        assert proceed_option is not None
        assert proceed_option.is_recommended is True

    def test_proceed_is_recommended_for_cost_cumulative(self):
        """Proceed is recommended for COST_CUMULATIVE trigger."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        options = system._build_options(goal, CheckpointTrigger.COST_CUMULATIVE)

        proceed_option = next((opt for opt in options if "proceed" in opt.label.lower()), None)
        assert proceed_option is not None
        assert proceed_option.is_recommended is True

    def test_only_one_option_is_recommended(self):
        """Only one option is marked as recommended."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )

        for trigger in CheckpointTrigger:
            options = system._build_options(goal, trigger)
            recommended_count = sum(1 for opt in options if opt.is_recommended)
            assert recommended_count == 1, f"Expected 1 recommended option for {trigger}, got {recommended_count}"


class TestIntegration:
    """Integration tests for checkpoint creation."""

    def test_full_checkpoint_creation_flow(self):
        """Full flow of creating a checkpoint."""
        config = ChiefOfStaffConfig()
        system = CheckpointSystem(config=config)
        goal = DailyGoal(
            goal_id="integration-test-goal",
            description="Implement new dashboard widget",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            tags=["ui", "frontend"],
            estimated_cost_usd=8.0,
        )

        checkpoint = system._create_checkpoint(goal, CheckpointTrigger.UX_CHANGE)

        # Verify all components
        assert checkpoint.checkpoint_id
        assert checkpoint.goal_id == "integration-test-goal"
        assert checkpoint.trigger == CheckpointTrigger.UX_CHANGE
        assert checkpoint.context
        assert len(checkpoint.options) == 4
        assert checkpoint.recommendation
        assert checkpoint.status == "pending"
        assert checkpoint.created_at

        # Verify options
        labels = [opt.label.lower() for opt in checkpoint.options]
        assert any("proceed" in label for label in labels)
        assert any("skip" in label for label in labels)
        assert any("modify" in label for label in labels)
        assert any("pause" in label for label in labels)

        # Verify exactly one recommended
        recommended = [opt for opt in checkpoint.options if opt.is_recommended]
        assert len(recommended) == 1

    def test_checkpoint_serialization_roundtrip(self):
        """Checkpoint can be serialized and deserialized."""
        system = CheckpointSystem()
        goal = DailyGoal(
            goal_id="serialization-test",
            description="Test serialization",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        checkpoint = system._create_checkpoint(goal, CheckpointTrigger.ARCHITECTURE)

        # Serialize and deserialize
        data = checkpoint.to_dict()
        restored = Checkpoint.from_dict(data)

        assert restored.checkpoint_id == checkpoint.checkpoint_id
        assert restored.goal_id == checkpoint.goal_id
        assert restored.trigger == checkpoint.trigger
        assert restored.context == checkpoint.context
        assert restored.recommendation == checkpoint.recommendation
        assert restored.status == checkpoint.status
        assert len(restored.options) == len(checkpoint.options)