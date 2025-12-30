"""Tests for check_before_execution in CheckpointSystem.

Issue #9: Implement check_before_execution for CheckpointSystem
- check_before_execution(goal) returns CheckpointResult
- Returns existing pending checkpoint if one exists for the goal
- Creates new checkpoint if triggers detected and no pending exists
- Returns CheckpointResult(requires_approval=False) if no triggers
- Uses _detect_triggers and _create_checkpoint internally
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointSystem,
    CheckpointTrigger,
    Checkpoint,
    CheckpointOption,
    CheckpointResult,
    CheckpointStore,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority, GoalStatus
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


class TestCheckBeforeExecutionReturnsCheckpointResult:
    """Tests that check_before_execution returns CheckpointResult."""

    @pytest.mark.asyncio
    async def test_returns_checkpoint_result(self):
        """check_before_execution returns a CheckpointResult instance."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Test goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            )

            result = await system.check_before_execution(goal)

            assert isinstance(result, CheckpointResult)

    @pytest.mark.asyncio
    async def test_result_has_requires_approval_field(self):
        """CheckpointResult has requires_approval field."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Test goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
            )

            result = await system.check_before_execution(goal)

            assert hasattr(result, "requires_approval")
            assert isinstance(result.requires_approval, bool)


class TestCheckBeforeExecutionNoTriggers:
    """Tests that check_before_execution returns requires_approval=False when no triggers."""

    @pytest.mark.asyncio
    async def test_no_triggers_requires_approval_false(self):
        """Returns requires_approval=False when goal has no triggers."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            # Goal with no tags, no cost, not unplanned, no errors
            goal = DailyGoal(
                goal_id="goal-1",
                description="Simple task",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is False

    @pytest.mark.asyncio
    async def test_no_triggers_approved_true(self):
        """Returns approved=True when no triggers detected."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Simple task",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            )

            result = await system.check_before_execution(goal)

            assert result.approved is True

    @pytest.mark.asyncio
    async def test_no_triggers_checkpoint_none(self):
        """Returns checkpoint=None when no triggers detected."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Simple task",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            )

            result = await system.check_before_execution(goal)

            assert result.checkpoint is None


class TestCheckBeforeExecutionWithTriggers:
    """Tests that check_before_execution creates checkpoint when triggers detected."""

    @pytest.mark.asyncio
    async def test_triggers_requires_approval_true(self):
        """Returns requires_approval=True when triggers detected."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            # Goal with UI tag triggers UX_CHANGE
            goal = DailyGoal(
                goal_id="goal-1",
                description="UI update",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["ui"],
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_triggers_approved_false(self):
        """Returns approved=False when triggers detected (pending approval)."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Frontend update",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["frontend"],
            )

            result = await system.check_before_execution(goal)

            assert result.approved is False

    @pytest.mark.asyncio
    async def test_triggers_returns_checkpoint(self):
        """Returns a Checkpoint when triggers detected."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="UX improvement",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["ux"],
            )

            result = await system.check_before_execution(goal)

            assert result.checkpoint is not None
            assert isinstance(result.checkpoint, Checkpoint)

    @pytest.mark.asyncio
    async def test_checkpoint_has_correct_goal_id(self):
        """Created checkpoint has correct goal_id."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="my-special-goal",
                description="Architecture change",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                tags=["architecture"],
            )

            result = await system.check_before_execution(goal)

            assert result.checkpoint.goal_id == "my-special-goal"

    @pytest.mark.asyncio
    async def test_checkpoint_saved_to_store(self):
        """Created checkpoint is saved to the store."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Refactor core",
                priority=GoalPriority.HIGH,
                estimated_minutes=45,
                tags=["refactor"],
            )

            result = await system.check_before_execution(goal)

            # Verify checkpoint was saved
            saved = await store.get(result.checkpoint.checkpoint_id)
            assert saved is not None
            assert saved.checkpoint_id == result.checkpoint.checkpoint_id


class TestCheckBeforeExecutionExistingPending:
    """Tests that check_before_execution returns existing pending checkpoint."""

    @pytest.mark.asyncio
    async def test_returns_existing_pending_checkpoint(self):
        """Returns existing pending checkpoint if one exists for the goal."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-with-pending",
                description="Test with existing checkpoint",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["ui"],
            )

            # First call creates a checkpoint
            result1 = await system.check_before_execution(goal)
            checkpoint_id = result1.checkpoint.checkpoint_id

            # Second call should return the same checkpoint
            result2 = await system.check_before_execution(goal)

            assert result2.checkpoint.checkpoint_id == checkpoint_id

    @pytest.mark.asyncio
    async def test_existing_pending_requires_approval_true(self):
        """Returns requires_approval=True for existing pending checkpoint."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-pending",
                description="Test goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["frontend"],
            )

            # First call
            await system.check_before_execution(goal)

            # Second call
            result = await system.check_before_execution(goal)

            assert result.requires_approval is True

    @pytest.mark.asyncio
    async def test_existing_pending_approved_false(self):
        """Returns approved=False for existing pending checkpoint."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-pending",
                description="Test goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["ux"],
            )

            # First call
            await system.check_before_execution(goal)

            # Second call
            result = await system.check_before_execution(goal)

            assert result.approved is False

    @pytest.mark.asyncio
    async def test_does_not_create_duplicate_checkpoints(self):
        """Does not create duplicate checkpoints for the same goal."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="no-duplicates",
                description="Test no duplicates",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["core"],
            )

            # Call multiple times
            await system.check_before_execution(goal)
            await system.check_before_execution(goal)
            await system.check_before_execution(goal)

            # Should only have one pending checkpoint
            pending = await store.list_pending()
            goal_checkpoints = [c for c in pending if c.goal_id == "no-duplicates"]
            assert len(goal_checkpoints) == 1


class TestCheckBeforeExecutionTriggerTypes:
    """Tests for different trigger types."""

    @pytest.mark.asyncio
    async def test_ux_change_trigger(self):
        """UX_CHANGE trigger works with ui tag."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="UI update",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["ui"],
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True
            assert result.checkpoint.trigger == CheckpointTrigger.UX_CHANGE

    @pytest.mark.asyncio
    async def test_architecture_trigger(self):
        """ARCHITECTURE trigger works with architecture tag."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Architecture change",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                tags=["architecture"],
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True
            assert result.checkpoint.trigger == CheckpointTrigger.ARCHITECTURE

    @pytest.mark.asyncio
    async def test_scope_change_trigger(self):
        """SCOPE_CHANGE trigger works with is_unplanned=True."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Unplanned work",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                is_unplanned=True,
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True
            assert result.checkpoint.trigger == CheckpointTrigger.SCOPE_CHANGE

    @pytest.mark.asyncio
    async def test_hiccup_trigger(self):
        """HICCUP trigger works with error_count > 0."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Goal with errors",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                error_count=3,
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True
            assert result.checkpoint.trigger == CheckpointTrigger.HICCUP

    @pytest.mark.asyncio
    async def test_cost_single_trigger(self):
        """COST_SINGLE trigger works with high estimated_cost_usd."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            config = ChiefOfStaffConfig()
            config.checkpoint_cost_single = 5.0
            system = CheckpointSystem(config=config, store=store)
            goal = DailyGoal(
                goal_id="goal-1",
                description="Expensive task",
                priority=GoalPriority.HIGH,
                estimated_minutes=120,
                estimated_cost_usd=10.0,
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True
            assert result.checkpoint.trigger == CheckpointTrigger.COST_SINGLE


class TestCheckBeforeExecutionIntegration:
    """Integration tests for check_before_execution."""

    @pytest.mark.asyncio
    async def test_full_workflow_no_triggers(self):
        """Full workflow when no triggers - goal can proceed."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="simple-goal",
                description="Simple task with no triggers",
                priority=GoalPriority.LOW,
                estimated_minutes=15,
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is False
            assert result.approved is True
            assert result.checkpoint is None

            # No checkpoints should be created
            pending = await store.list_pending()
            assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_full_workflow_with_trigger(self):
        """Full workflow when trigger detected - checkpoint created."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            goal = DailyGoal(
                goal_id="ui-goal",
                description="Update dashboard UI",
                priority=GoalPriority.HIGH,
                estimated_minutes=45,
                tags=["ui", "frontend"],
            )

            result = await system.check_before_execution(goal)

            assert result.requires_approval is True
            assert result.approved is False
            assert result.checkpoint is not None
            assert result.checkpoint.status == "pending"

            # Checkpoint should be persisted
            pending = await store.list_pending()
            assert len(pending) == 1
            assert pending[0].goal_id == "ui-goal"

    @pytest.mark.asyncio
    async def test_multiple_goals_independent_checkpoints(self):
        """Multiple goals get independent checkpoints."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            goal1 = DailyGoal(
                goal_id="goal-1",
                description="UI task",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                tags=["ui"],
            )
            goal2 = DailyGoal(
                goal_id="goal-2",
                description="Architecture task",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                tags=["architecture"],
            )

            result1 = await system.check_before_execution(goal1)
            result2 = await system.check_before_execution(goal2)

            assert result1.checkpoint.checkpoint_id != result2.checkpoint.checkpoint_id
            assert result1.checkpoint.goal_id == "goal-1"
            assert result2.checkpoint.goal_id == "goal-2"

            pending = await store.list_pending()
            assert len(pending) == 2
