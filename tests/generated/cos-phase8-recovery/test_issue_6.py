"""Tests for episode logging in RecoveryManager.

This test file verifies that the RecoveryManager properly logs episodes
via EpisodeStore during recovery attempts, including:
- Episodes logged after each retry attempt (not just final result)
- Episode includes retry_count field with current attempt number
- Episode includes recovery_level field with current strategy
- Final episode includes total retry count and final recovery level
- Logging is optional - method works without EpisodeStore
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile

import pytest

from swarm_attack.chief_of_staff.recovery import (
    RecoveryManager,
    RetryStrategy,
    ErrorCategory,
    classify_error,
    MAX_RETRIES,
)
from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore
from swarm_attack.errors import LLMError, LLMErrorType


class MockGoal:
    """Mock DailyGoal for testing."""
    
    def __init__(self, goal_id: str = "test-goal-1", description: str = "Test goal"):
        self.goal_id = goal_id
        self.description = description
        self.error_count = 0
        self.is_hiccup = False


class MockCheckpointSystem:
    """Mock CheckpointSystem for testing."""
    
    def __init__(self):
        self.store = MagicMock()
        self.store.save = AsyncMock()


class TestEpisodeLoggedAfterRetryAttempt:
    """Test that episodes are logged after retry attempts."""

    @pytest.mark.asyncio
    async def test_episode_logged_on_success(self):
        """Episode is logged when execution succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            # Mock successful execution
            async def execute_fn():
                return MagicMock(cost_usd=0.05)
            
            result = await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            assert result.success
            episodes = episode_store.load_all()
            assert len(episodes) == 1
            assert episodes[0].success is True
            assert episodes[0].goal_id == "test-goal-1"

    @pytest.mark.asyncio
    async def test_episode_logged_on_failure_after_retries(self):
        """Episode is logged when execution fails after all retries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            # Use 0 backoff for faster tests
            recovery = RecoveryManager(
                checkpoint_system, 
                backoff_base_seconds=0,
                backoff_multiplier=1
            )
            goal = MockGoal()
            
            # Mock failing execution (transient error)
            async def execute_fn():
                raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
            
            result = await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            assert result.success is False
            episodes = episode_store.load_all()
            assert len(episodes) >= 1
            # Final episode should show failure
            final_episode = episodes[-1]
            assert final_episode.success is False


class TestEpisodeIncludesRetryCount:
    """Test that episodes include retry_count field."""

    @pytest.mark.asyncio
    async def test_retry_count_zero_on_first_success(self):
        """retry_count is 0 when first attempt succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            async def execute_fn():
                return MagicMock(cost_usd=0.01)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert len(episodes) == 1
            assert episodes[0].retry_count == 0

    @pytest.mark.asyncio
    async def test_retry_count_increments_with_failures(self):
        """retry_count reflects number of failed attempts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(
                checkpoint_system,
                backoff_base_seconds=0,
                backoff_multiplier=1
            )
            goal = MockGoal()
            
            # Fail MAX_RETRIES times
            async def execute_fn():
                raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert len(episodes) >= 1
            # Final episode should have retry_count = MAX_RETRIES
            final_episode = episodes[-1]
            assert final_episode.retry_count == MAX_RETRIES

    @pytest.mark.asyncio
    async def test_retry_count_correct_after_eventual_success(self):
        """retry_count reflects attempts when eventual success after retries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(
                checkpoint_system,
                backoff_base_seconds=0,
                backoff_multiplier=1
            )
            goal = MockGoal()
            
            # Fail twice, then succeed
            attempts = [0]
            
            async def execute_fn():
                attempts[0] += 1
                if attempts[0] < 3:
                    raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
                return MagicMock(cost_usd=0.02, success=True)

            result = await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )

            assert result.success is True
            episodes = episode_store.load_all()
            assert len(episodes) >= 1
            # Episode should reflect 2 failed attempts before success
            final_episode = episodes[-1]
            assert final_episode.retry_count == 2
            assert final_episode.success is True


class TestEpisodeIncludesRecoveryLevel:
    """Test that episodes include recovery_level field."""

    @pytest.mark.asyncio
    async def test_recovery_level_same_for_transient_retry(self):
        """recovery_level is 'same' for transient error retries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(
                checkpoint_system,
                backoff_base_seconds=0,
                backoff_multiplier=1
            )
            goal = MockGoal()
            
            # Fail once with transient error, then succeed
            attempts = [0]
            
            async def execute_fn():
                attempts[0] += 1
                if attempts[0] < 2:
                    raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
                return MagicMock(cost_usd=0.01)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            final_episode = episodes[-1]
            # After retries with SAME strategy, recovery_level should be "same"
            assert final_episode.recovery_level == RetryStrategy.SAME.value

    @pytest.mark.asyncio
    async def test_recovery_level_escalate_for_fatal_error(self):
        """recovery_level is 'escalate' for fatal errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            # Fatal error should escalate immediately
            async def execute_fn():
                raise LLMError("auth failed", error_type=LLMErrorType.AUTH_REQUIRED)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert len(episodes) >= 1
            final_episode = episodes[-1]
            assert final_episode.recovery_level == RetryStrategy.ESCALATE.value

    @pytest.mark.asyncio
    async def test_recovery_level_escalate_for_systematic_error(self):
        """recovery_level is 'escalate' for systematic errors (fallthrough from Level 2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            # Systematic error should fall through to escalate
            async def execute_fn():
                raise LLMError("cli crash", error_type=LLMErrorType.CLI_CRASH)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert len(episodes) >= 1
            final_episode = episodes[-1]
            assert final_episode.recovery_level == RetryStrategy.ESCALATE.value


class TestFinalEpisodeIncludesTotalRetryCount:
    """Test that final episode includes total retry count."""

    @pytest.mark.asyncio
    async def test_final_episode_has_total_retries_on_exhaustion(self):
        """Final episode shows total retry count when retries exhausted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(
                checkpoint_system,
                backoff_base_seconds=0,
                backoff_multiplier=1
            )
            goal = MockGoal()
            
            async def execute_fn():
                raise LLMError("rate limit", error_type=LLMErrorType.RATE_LIMIT)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            final_episode = episodes[-1]
            assert final_episode.retry_count == MAX_RETRIES
            assert final_episode.recovery_level == RetryStrategy.ESCALATE.value
            assert final_episode.success is False


class TestLoggingIsOptional:
    """Test that logging works without EpisodeStore."""

    @pytest.mark.asyncio
    async def test_works_without_episode_store_on_success(self):
        """Method works when episode_store is None (success case)."""
        checkpoint_system = MockCheckpointSystem()
        recovery = RecoveryManager(checkpoint_system)
        goal = MockGoal()
        
        async def execute_fn():
            return MagicMock(cost_usd=0.01, success=True)
        
        # Should not raise when episode_store is None
        result = await recovery.execute_with_recovery(
            goal, execute_fn, episode_store=None
        )
        
        assert result.success

    @pytest.mark.asyncio
    async def test_works_without_episode_store_on_failure(self):
        """Method works when episode_store is None (failure case)."""
        checkpoint_system = MockCheckpointSystem()
        recovery = RecoveryManager(
            checkpoint_system,
            backoff_base_seconds=0,
            backoff_multiplier=1
        )
        goal = MockGoal()
        
        async def execute_fn():
            raise LLMError("auth error", error_type=LLMErrorType.AUTH_REQUIRED)
        
        # Should not raise when episode_store is None
        result = await recovery.execute_with_recovery(
            goal, execute_fn, episode_store=None
        )
        
        assert result.success is False

    @pytest.mark.asyncio
    async def test_no_error_when_episode_store_is_none_with_retries(self):
        """No error when episode_store is None during retry sequence."""
        checkpoint_system = MockCheckpointSystem()
        recovery = RecoveryManager(
            checkpoint_system,
            backoff_base_seconds=0,
            backoff_multiplier=1
        )
        goal = MockGoal()
        
        attempts = [0]
        
        async def execute_fn():
            attempts[0] += 1
            if attempts[0] < 3:
                raise LLMError("timeout", error_type=LLMErrorType.TIMEOUT)
            return MagicMock(cost_usd=0.02, success=True)

        # Should complete without error even with retries
        result = await recovery.execute_with_recovery(
            goal, execute_fn, episode_store=None
        )

        assert result.success is True


class TestEpisodeFieldsCorrect:
    """Test that episode fields are populated correctly."""

    @pytest.mark.asyncio
    async def test_episode_has_goal_id(self):
        """Episode includes goal_id from the goal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal(goal_id="my-test-goal-123")
            
            async def execute_fn():
                return MagicMock(cost_usd=0.01)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert episodes[0].goal_id == "my-test-goal-123"

    @pytest.mark.asyncio
    async def test_episode_has_error_on_failure(self):
        """Episode includes error message on failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            async def execute_fn():
                raise LLMError("auth required", error_type=LLMErrorType.AUTH_REQUIRED)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert episodes[0].error is not None
            assert "auth required" in episodes[0].error

    @pytest.mark.asyncio
    async def test_episode_has_timestamp(self):
        """Episode includes timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            async def execute_fn():
                return MagicMock(cost_usd=0.01)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert episodes[0].timestamp is not None
            # Verify it's a valid ISO format timestamp
            datetime.fromisoformat(episodes[0].timestamp)

    @pytest.mark.asyncio
    async def test_episode_has_episode_id(self):
        """Episode has a unique episode_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            async def execute_fn():
                return MagicMock(cost_usd=0.01)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            assert episodes[0].episode_id is not None
            assert episodes[0].episode_id.startswith("ep-")

    @pytest.mark.asyncio
    async def test_recovery_level_none_on_first_attempt_success(self):
        """recovery_level is None when first attempt succeeds (no recovery needed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            episode_store = EpisodeStore(base_path=Path(tmpdir))
            checkpoint_system = MockCheckpointSystem()
            recovery = RecoveryManager(checkpoint_system)
            goal = MockGoal()
            
            async def execute_fn():
                return MagicMock(cost_usd=0.01)
            
            await recovery.execute_with_recovery(
                goal, execute_fn, episode_store=episode_store
            )
            
            episodes = episode_store.load_all()
            # No retries means no recovery level needed
            assert episodes[0].recovery_level is None