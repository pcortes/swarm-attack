"""Tests for Issue #14: Add escalation to checkpoint with hiccup marking.

Tests for:
- _escalate_to_human(goal, failure) creates HICCUP checkpoint
- Sets goal.is_hiccup = True before escalation
- Checkpoint context includes retry count, goal content, error
- RecoveryResult has escalated=True after escalation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from swarm_attack.chief_of_staff.recovery import (
    RecoveryManager,
    RecoveryResult,
    MAX_RETRIES,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority
from swarm_attack.chief_of_staff.checkpoints import CheckpointTrigger


class TestEscalateToHuman:
    """Tests for _escalate_to_human method."""

    @pytest.mark.asyncio
    async def test_sets_is_hiccup_true(self):
        """_escalate_to_human sets goal.is_hiccup = True."""
        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        mock_checkpoint_system = MagicMock()
        mock_checkpoint_system.store = mock_store

        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        goal.is_hiccup = False

        await manager._escalate_to_human(goal, "Test failure")

        assert goal.is_hiccup is True

    @pytest.mark.asyncio
    async def test_creates_hiccup_checkpoint(self):
        """_escalate_to_human creates a HICCUP checkpoint."""
        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        mock_checkpoint_system = MagicMock()
        mock_checkpoint_system.store = mock_store

        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        await manager._escalate_to_human(goal, "Test failure")

        # Verify store.save was called
        assert mock_store.save.called
        checkpoint = mock_store.save.call_args[0][0]

        # Verify checkpoint properties
        assert checkpoint.trigger == CheckpointTrigger.HICCUP
        assert checkpoint.goal_id == "test-1"
        assert checkpoint.status == "pending"

    @pytest.mark.asyncio
    async def test_checkpoint_context_includes_details(self):
        """Checkpoint context includes retry count, goal, and error."""
        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        mock_checkpoint_system = MagicMock()
        mock_checkpoint_system.store = mock_store

        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Important task",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
        )
        goal.error_count = 5

        await manager._escalate_to_human(goal, "Connection timeout")

        checkpoint = mock_store.save.call_args[0][0]

        # Verify context includes key information
        assert "Important task" in checkpoint.context
        assert "Connection timeout" in checkpoint.context
        assert "5" in checkpoint.context  # error_count


class TestExecuteWithRecoveryEscalation:
    """Tests for escalation in execute_with_recovery."""

    @pytest.mark.asyncio
    async def test_escalates_after_max_retries(self):
        """execute_with_recovery escalates after MAX_RETRIES failures."""
        from unittest.mock import patch

        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        mock_checkpoint_system = MagicMock()
        mock_checkpoint_system.store = mock_store

        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        # Use transient error to trigger retries before escalation
        from swarm_attack.errors import LLMError, LLMErrorType
        action = AsyncMock(side_effect=LLMError("Timeout", error_type=LLMErrorType.TIMEOUT))

        with patch("swarm_attack.chief_of_staff.recovery.asyncio.sleep", new_callable=AsyncMock):
            result = await manager.execute_with_recovery(goal, action)

        # Verify escalation occurred (result has success=False, goal marked as hiccup)
        assert result.success is False
        assert goal.is_hiccup is True
        assert mock_store.save.called

    @pytest.mark.asyncio
    async def test_no_escalation_on_success(self):
        """execute_with_recovery does not escalate on success."""
        from swarm_attack.chief_of_staff.autopilot_runner import GoalExecutionResult

        mock_store = MagicMock()
        mock_store.save = AsyncMock()
        mock_checkpoint_system = MagicMock()
        mock_checkpoint_system.store = mock_store

        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        # Return GoalExecutionResult on success
        success_result = GoalExecutionResult(success=True, cost_usd=1.0, duration_seconds=10)
        action = AsyncMock(return_value=success_result)

        result = await manager.execute_with_recovery(goal, action)

        # No escalation on success
        assert result.success is True
        assert not mock_store.save.called


class TestRecoveryResultEscalated:
    """Tests for escalated field in RecoveryResult."""

    def test_escalated_field_exists(self):
        """RecoveryResult has escalated field."""
        result = RecoveryResult(
            success=False,
            error="Error",
            retry_count=3,
            escalated=True,
        )
        assert result.escalated is True

    def test_escalated_defaults_false(self):
        """escalated defaults to False."""
        result = RecoveryResult(
            success=True,
            retry_count=0,
        )
        assert result.escalated is False
