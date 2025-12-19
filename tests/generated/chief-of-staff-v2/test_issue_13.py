"""Tests for Issue #13: Create RecoveryManager with retry logic.

Tests for:
- RecoveryLevel enum with RETRY_SAME and ESCALATE values
- RecoveryManager class with checkpoint_system dependency
- MAX_RETRIES = 3 and BACKOFF_SECONDS = 5 constants
- execute_with_recovery(goal, action) async method
- Retries with exponential backoff (5s, 10s, 20s)
- Increments goal.error_count on each failure
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from swarm_attack.chief_of_staff.recovery import (
    RecoveryLevel,
    RecoveryManager,
    RecoveryResult,
    MAX_RETRIES,
    BACKOFF_SECONDS,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority


class TestRecoveryLevelEnum:
    """Tests for RecoveryLevel enum."""

    def test_retry_same_value(self):
        """RecoveryLevel.RETRY_SAME has correct value."""
        assert RecoveryLevel.RETRY_SAME.value == "retry_same"

    def test_escalate_value(self):
        """RecoveryLevel.ESCALATE has correct value."""
        assert RecoveryLevel.ESCALATE.value == "escalate"

    def test_has_both_values(self):
        """RecoveryLevel enum has both required values."""
        values = [level.value for level in RecoveryLevel]
        assert "retry_same" in values
        assert "escalate" in values


class TestConstants:
    """Tests for module constants."""

    def test_max_retries_is_3(self):
        """MAX_RETRIES constant is 3."""
        assert MAX_RETRIES == 3

    def test_backoff_seconds_is_5(self):
        """BACKOFF_SECONDS constant is 5."""
        assert BACKOFF_SECONDS == 5


class TestRecoveryManagerInit:
    """Tests for RecoveryManager initialization."""

    def test_init_accepts_checkpoint_system(self):
        """RecoveryManager __init__ accepts checkpoint_system."""
        mock_checkpoint_system = MagicMock()
        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)
        assert manager.checkpoint_system is mock_checkpoint_system


class TestExecuteWithRecovery:
    """Tests for execute_with_recovery method."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Returns success immediately when action succeeds."""
        mock_checkpoint_system = MagicMock()
        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        action = AsyncMock(return_value="success_result")

        result = await manager.execute_with_recovery(goal, action)

        assert result.success is True
        assert result.action_result == "success_result"
        assert result.retry_count == 0
        assert goal.error_count == 0

    @pytest.mark.asyncio
    async def test_success_on_second_try(self):
        """Retries and succeeds on second attempt."""
        import asyncio

        mock_checkpoint_system = MagicMock()
        manager = RecoveryManager(checkpoint_system=mock_checkpoint_system)

        goal = DailyGoal(
            goal_id="test-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )

        # Fail first, succeed second
        call_count = [0]

        async def action():
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First attempt failed")
            return "success_on_retry"

        # Mock sleep to not actually wait
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", AsyncMock())
            result = await manager.execute_with_recovery(goal, action)

        assert result.success is True
        assert result.action_result == "success_on_retry"
        assert result.retry_count == 1
        assert goal.error_count == 1

    @pytest.mark.asyncio
    async def test_failure_after_max_retries(self):
        """Returns failure after MAX_RETRIES exhausted."""
        import asyncio

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

        action = AsyncMock(side_effect=Exception("Always fails"))

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", AsyncMock())
            result = await manager.execute_with_recovery(goal, action)

        assert result.success is False
        assert result.error == "Always fails"
        assert result.retry_count == MAX_RETRIES
        assert goal.error_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_increments_error_count_on_each_failure(self):
        """Increments goal.error_count on each failed attempt."""
        import asyncio

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
        goal.error_count = 0

        action = AsyncMock(side_effect=Exception("Fails"))

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(asyncio, "sleep", AsyncMock())
            await manager.execute_with_recovery(goal, action)

        # error_count incremented for each retry
        assert goal.error_count == 3


class TestRecoveryResult:
    """Tests for RecoveryResult dataclass."""

    def test_success_result(self):
        """RecoveryResult captures success."""
        result = RecoveryResult(
            success=True,
            action_result="data",
            retry_count=0,
        )
        assert result.success is True
        assert result.action_result == "data"
        assert result.error is None

    def test_failure_result(self):
        """RecoveryResult captures failure."""
        result = RecoveryResult(
            success=False,
            error="Something went wrong",
            retry_count=3,
        )
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.retry_count == 3
