"""Tests for resolve_checkpoint and daily cost tracking in CheckpointSystem.

Issue #10: Implement resolve and cost tracking for CheckpointSystem
- resolve_checkpoint(checkpoint_id, chosen_option, notes) updates checkpoint status
- Sets status to 'approved' if chosen_option is 'Proceed'
- Sets status to 'rejected' for Skip/Modify/Pause
- Stores chosen_option and human_notes on checkpoint
- update_daily_cost(cost) increments daily cost tracking
- reset_daily_cost() resets daily cost to 0
"""

import pytest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointSystem,
    CheckpointStore,
    Checkpoint,
    CheckpointTrigger,
    CheckpointOption,
)
from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig


class TestResolveCheckpoint:
    """Tests for resolve_checkpoint method."""

    def test_resolve_checkpoint_exists(self):
        """CheckpointSystem has resolve_checkpoint method."""
        system = CheckpointSystem()
        assert hasattr(system, "resolve_checkpoint")
        assert callable(system.resolve_checkpoint)

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_proceed_sets_approved(self):
        """Choosing 'Proceed' sets status to 'approved'."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            # Create a checkpoint first
            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-1",
                trigger=CheckpointTrigger.COST_SINGLE,
                context="Test context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Skip", description="Skip this"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-1",
            )
            await store.save(checkpoint)

            # Resolve with Proceed
            result = await system.resolve_checkpoint("test-checkpoint-1", "Proceed", "Approved by user")

            # Check status is approved
            resolved = await store.get("test-checkpoint-1")
            assert resolved.status == "approved"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_skip_sets_rejected(self):
        """Choosing 'Skip' sets status to 'rejected'."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-2",
                trigger=CheckpointTrigger.UX_CHANGE,
                context="UX change context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Skip", description="Skip this"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-2",
            )
            await store.save(checkpoint)

            await system.resolve_checkpoint("test-checkpoint-2", "Skip", "Not needed")

            resolved = await store.get("test-checkpoint-2")
            assert resolved.status == "rejected"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_modify_sets_rejected(self):
        """Choosing 'Modify' sets status to 'rejected'."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-3",
                trigger=CheckpointTrigger.ARCHITECTURE,
                context="Architecture context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Modify", description="Modify approach"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-3",
            )
            await store.save(checkpoint)

            await system.resolve_checkpoint("test-checkpoint-3", "Modify", "Need changes")

            resolved = await store.get("test-checkpoint-3")
            assert resolved.status == "rejected"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_pause_sets_rejected(self):
        """Choosing 'Pause' sets status to 'rejected'."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-4",
                trigger=CheckpointTrigger.SCOPE_CHANGE,
                context="Scope change context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Pause", description="Pause execution"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-4",
            )
            await store.save(checkpoint)

            await system.resolve_checkpoint("test-checkpoint-4", "Pause", "Pausing for review")

            resolved = await store.get("test-checkpoint-4")
            assert resolved.status == "rejected"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_stores_chosen_option(self):
        """resolve_checkpoint stores the chosen_option on the checkpoint."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-5",
                trigger=CheckpointTrigger.COST_CUMULATIVE,
                context="Cost context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Skip", description="Skip"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-5",
            )
            await store.save(checkpoint)

            await system.resolve_checkpoint("test-checkpoint-5", "Skip", "Budget concerns")

            resolved = await store.get("test-checkpoint-5")
            assert resolved.chosen_option == "Skip"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_stores_human_notes(self):
        """resolve_checkpoint stores human_notes on the checkpoint."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-6",
                trigger=CheckpointTrigger.HICCUP,
                context="Hiccup context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Skip", description="Skip"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-6",
            )
            await store.save(checkpoint)

            notes = "This is my detailed feedback about the checkpoint"
            await system.resolve_checkpoint("test-checkpoint-6", "Proceed", notes)

            resolved = await store.get("test-checkpoint-6")
            assert resolved.human_notes == notes

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_returns_resolved_checkpoint(self):
        """resolve_checkpoint returns the resolved checkpoint."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            checkpoint = Checkpoint(
                checkpoint_id="test-checkpoint-7",
                trigger=CheckpointTrigger.UX_CHANGE,
                context="UX context",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="test-goal-7",
            )
            await store.save(checkpoint)

            result = await system.resolve_checkpoint("test-checkpoint-7", "Proceed", "OK")

            assert isinstance(result, Checkpoint)
            assert result.checkpoint_id == "test-checkpoint-7"
            assert result.status == "approved"

    @pytest.mark.asyncio
    async def test_resolve_checkpoint_not_found(self):
        """resolve_checkpoint raises error for non-existent checkpoint."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)

            with pytest.raises(KeyError):
                await system.resolve_checkpoint("non-existent-id", "Proceed", "notes")


class TestUpdateDailyCost:
    """Tests for update_daily_cost method."""

    def test_update_daily_cost_exists(self):
        """CheckpointSystem has update_daily_cost method."""
        system = CheckpointSystem()
        assert hasattr(system, "update_daily_cost")
        assert callable(system.update_daily_cost)

    def test_update_daily_cost_increments(self):
        """update_daily_cost increments daily cost tracking."""
        system = CheckpointSystem()
        system.daily_cost = 0.0
        initial_cost = system.daily_cost

        system.update_daily_cost(5.0)

        assert system.daily_cost == initial_cost + 5.0

    def test_update_daily_cost_accumulates(self):
        """update_daily_cost accumulates multiple costs."""
        system = CheckpointSystem()
        system.reset_daily_cost()

        system.update_daily_cost(2.5)
        system.update_daily_cost(3.5)
        system.update_daily_cost(1.0)

        assert system.daily_cost == 7.0

    def test_update_daily_cost_handles_zero(self):
        """update_daily_cost handles zero cost."""
        system = CheckpointSystem()
        system.reset_daily_cost()

        system.update_daily_cost(0.0)

        assert system.daily_cost == 0.0

    def test_update_daily_cost_handles_small_values(self):
        """update_daily_cost handles small decimal values."""
        system = CheckpointSystem()
        system.reset_daily_cost()

        system.update_daily_cost(0.001)
        system.update_daily_cost(0.002)

        assert abs(system.daily_cost - 0.003) < 0.0001


class TestResetDailyCost:
    """Tests for reset_daily_cost method."""

    def test_reset_daily_cost_exists(self):
        """CheckpointSystem has reset_daily_cost method."""
        system = CheckpointSystem()
        assert hasattr(system, "reset_daily_cost")
        assert callable(system.reset_daily_cost)

    def test_reset_daily_cost_resets_to_zero(self):
        """reset_daily_cost resets daily cost to 0."""
        system = CheckpointSystem()
        system.update_daily_cost(100.0)

        system.reset_daily_cost()

        assert system.daily_cost == 0.0

    def test_reset_daily_cost_after_multiple_updates(self):
        """reset_daily_cost works after multiple cost updates."""
        system = CheckpointSystem()
        system.update_daily_cost(10.0)
        system.update_daily_cost(20.0)
        system.update_daily_cost(30.0)

        system.reset_daily_cost()

        assert system.daily_cost == 0.0

    def test_reset_daily_cost_idempotent(self):
        """reset_daily_cost is idempotent (calling twice is safe)."""
        system = CheckpointSystem()
        system.update_daily_cost(50.0)

        system.reset_daily_cost()
        system.reset_daily_cost()

        assert system.daily_cost == 0.0


class TestDailyCostProperty:
    """Tests for daily_cost property."""

    def test_daily_cost_property_exists(self):
        """CheckpointSystem has daily_cost attribute."""
        system = CheckpointSystem()
        assert hasattr(system, "daily_cost")

    def test_daily_cost_starts_at_zero(self):
        """daily_cost starts at 0 for new system."""
        system = CheckpointSystem()
        system.reset_daily_cost()
        assert system.daily_cost == 0.0

    def test_daily_cost_returns_float(self):
        """daily_cost returns a float value."""
        system = CheckpointSystem()
        assert isinstance(system.daily_cost, float)


class TestIntegrationResolveAndCost:
    """Integration tests for resolve and cost tracking."""

    @pytest.mark.asyncio
    async def test_resolve_and_track_cost_workflow(self):
        """Full workflow: create checkpoint, track cost, resolve."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            config = ChiefOfStaffConfig()
            system = CheckpointSystem(config=config, store=store)
            system.reset_daily_cost()

            # Track some costs
            system.update_daily_cost(5.0)
            system.update_daily_cost(3.0)
            assert system.daily_cost == 8.0

            # Create and resolve a checkpoint
            checkpoint = Checkpoint(
                checkpoint_id="workflow-checkpoint",
                trigger=CheckpointTrigger.COST_SINGLE,
                context="Cost exceeded",
                options=[
                    CheckpointOption(label="Proceed", description="Continue"),
                    CheckpointOption(label="Skip", description="Skip"),
                ],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="workflow-goal",
            )
            await store.save(checkpoint)

            result = await system.resolve_checkpoint("workflow-checkpoint", "Proceed", "Approved")

            assert result.status == "approved"
            assert result.chosen_option == "Proceed"
            assert result.human_notes == "Approved"
            # Cost tracking should be independent
            assert system.daily_cost == 8.0

    @pytest.mark.asyncio
    async def test_reset_cost_does_not_affect_checkpoints(self):
        """Resetting daily cost doesn't affect checkpoint state."""
        with TemporaryDirectory() as tmpdir:
            store = CheckpointStore(base_path=Path(tmpdir))
            system = CheckpointSystem(store=store)
            system.update_daily_cost(100.0)

            checkpoint = Checkpoint(
                checkpoint_id="cost-reset-test",
                trigger=CheckpointTrigger.COST_CUMULATIVE,
                context="High cumulative cost",
                options=[CheckpointOption(label="Proceed", description="Continue")],
                recommendation="Proceed",
                status="pending",
                created_at=datetime.now().isoformat(),
                goal_id="cost-reset-goal",
            )
            await store.save(checkpoint)
            await system.resolve_checkpoint("cost-reset-test", "Proceed", "OK")

            # Reset cost
            system.reset_daily_cost()

            # Checkpoint should still be resolved
            resolved = await store.get("cost-reset-test")
            assert resolved.status == "approved"
            assert system.daily_cost == 0.0
