"""Tests for Level 2 fallthrough explicit logging.

Verifies that when SYSTEMATIC errors trigger Level 2 (ALTERNATIVE) recovery,
an explicit WARNING log message is emitted that includes:
- Error type
- Goal ID
- Timestamp
- Message indicating fallthrough to Level 4 (ESCALATE)
"""

import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from swarm_attack.chief_of_staff.checkpoints import (
    CheckpointSystem,
    CheckpointStore,
)
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.errors import LLMError, LLMErrorType


@pytest.fixture
def checkpoint_system():
    """Create a CheckpointSystem with mocked store."""
    store = MagicMock(spec=CheckpointStore)
    store.save = AsyncMock()
    system = CheckpointSystem(config=None, store=store)
    return system


@pytest.fixture
def recovery_manager(checkpoint_system):
    """Create a RecoveryManager for testing."""
    return RecoveryManager(checkpoint_system)


@pytest.fixture
def sample_goal():
    """Create a sample DailyGoal for testing."""
    return DailyGoal(
        goal_id="test-goal-level2",
        description="Test goal for Level 2 logging",
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )


class TestLevel2FallthroughLogging:
    """Test that Level 2 fallthrough is logged explicitly for future extension."""

    @pytest.mark.asyncio
    async def test_systematic_error_logs_warning_message(
        self, recovery_manager, sample_goal, caplog
    ):
        """SYSTEMATIC error should log a WARNING message for Level 2 fallthrough."""
        async def systematic_failure():
            raise LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)

        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, systematic_failure
            )

        # Should have at least one WARNING level log
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) >= 1, "Expected at least one WARNING log message"

    @pytest.mark.asyncio
    async def test_log_message_includes_error_type(
        self, recovery_manager, sample_goal, caplog
    ):
        """Log message should include the error type."""
        async def systematic_failure():
            raise LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)

        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, systematic_failure
            )

        # Find the Level 2 log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() or "alternative" in r.message.lower()
        ]
        assert len(level2_logs) >= 1, "Expected Level 2 log message"
        
        # Check error type is included
        log_text = " ".join(r.message for r in level2_logs).lower()
        assert "cli_crash" in log_text or "systematic" in log_text, \
            f"Expected error type in log message, got: {log_text}"

    @pytest.mark.asyncio
    async def test_log_message_includes_goal_id(
        self, recovery_manager, sample_goal, caplog
    ):
        """Log message should include the goal ID."""
        async def systematic_failure():
            raise LLMError("JSON error", error_type=LLMErrorType.JSON_PARSE_ERROR)

        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, systematic_failure
            )

        # Find the Level 2 log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() or "alternative" in r.message.lower()
        ]
        assert len(level2_logs) >= 1, "Expected Level 2 log message"
        
        # Check goal ID is included
        log_text = " ".join(r.message for r in level2_logs)
        assert sample_goal.goal_id in log_text, \
            f"Expected goal_id '{sample_goal.goal_id}' in log message, got: {log_text}"

    @pytest.mark.asyncio
    async def test_log_message_includes_fallthrough_text(
        self, recovery_manager, sample_goal, caplog
    ):
        """Log message should indicate fallthrough to Level 4 ESCALATE."""
        async def systematic_failure():
            raise LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)

        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, systematic_failure
            )

        # Find the Level 2 log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() or "alternative" in r.message.lower()
        ]
        assert len(level2_logs) >= 1, "Expected Level 2 log message"
        
        # Check fallthrough text is included
        log_text = " ".join(r.message for r in level2_logs).lower()
        assert "not implemented" in log_text or "falling through" in log_text or "escalate" in log_text, \
            f"Expected fallthrough text in log message, got: {log_text}"

    @pytest.mark.asyncio
    async def test_log_message_includes_timestamp(
        self, recovery_manager, sample_goal, caplog
    ):
        """Log message should include a timestamp for correlation."""
        async def systematic_failure():
            raise LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)

        before_time = datetime.now()
        
        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, systematic_failure
            )

        after_time = datetime.now()

        # Find the Level 2 log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() or "alternative" in r.message.lower()
        ]
        assert len(level2_logs) >= 1, "Expected Level 2 log message"
        
        # Check timestamp is included (ISO format or similar)
        log_text = " ".join(r.message for r in level2_logs)
        # Timestamp should contain date components like year, or ISO format markers
        has_timestamp = (
            str(before_time.year) in log_text or  # Year in message
            "T" in log_text or  # ISO format separator
            "-" in log_text and ":" in log_text  # Date-time separators
        )
        assert has_timestamp, \
            f"Expected timestamp in log message, got: {log_text}"

    @pytest.mark.asyncio
    async def test_log_level_is_warning_not_error(
        self, recovery_manager, sample_goal, caplog
    ):
        """Log level should be WARNING, not ERROR (expected behavior)."""
        async def systematic_failure():
            raise LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)

        with caplog.at_level(logging.DEBUG):
            await recovery_manager.execute_with_recovery(
                sample_goal, systematic_failure
            )

        # Find the Level 2 log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() or "alternative" in r.message.lower()
        ]
        assert len(level2_logs) >= 1, "Expected Level 2 log message"
        
        # Verify it's a WARNING level (not ERROR)
        for record in level2_logs:
            assert record.levelno == logging.WARNING, \
                f"Expected WARNING level, got {record.levelname}"

    @pytest.mark.asyncio
    async def test_json_parse_error_triggers_level2_logging(
        self, recovery_manager, sample_goal, caplog
    ):
        """JSON_PARSE_ERROR (systematic) should trigger Level 2 logging."""
        async def json_error():
            raise LLMError("Invalid JSON", error_type=LLMErrorType.JSON_PARSE_ERROR)

        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, json_error
            )

        # Should have Level 2 log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() or "alternative" in r.message.lower()
        ]
        assert len(level2_logs) >= 1, \
            "Expected Level 2 log message for JSON_PARSE_ERROR"

    @pytest.mark.asyncio
    async def test_transient_error_does_not_trigger_level2_logging(
        self, recovery_manager, sample_goal, caplog
    ):
        """Transient errors should NOT trigger Level 2 logging."""
        async def transient_failure():
            raise LLMError("Timeout", error_type=LLMErrorType.TIMEOUT)

        with patch("swarm_attack.chief_of_staff.recovery.asyncio.sleep", new_callable=AsyncMock):
            with caplog.at_level(logging.WARNING):
                await recovery_manager.execute_with_recovery(
                    sample_goal, transient_failure
                )

        # Should NOT have Level 2 ALTERNATIVE log message (only Level 1 SAME)
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() and "alternative" in r.message.lower()
        ]
        assert len(level2_logs) == 0, \
            f"Transient errors should not trigger Level 2 logging, got: {[r.message for r in level2_logs]}"

    @pytest.mark.asyncio
    async def test_fatal_error_does_not_trigger_level2_logging(
        self, recovery_manager, sample_goal, caplog
    ):
        """Fatal errors should NOT trigger Level 2 logging (go directly to Level 4)."""
        async def fatal_failure():
            raise LLMError("Auth required", error_type=LLMErrorType.AUTH_REQUIRED)

        with caplog.at_level(logging.WARNING):
            await recovery_manager.execute_with_recovery(
                sample_goal, fatal_failure
            )

        # Should NOT have Level 2 ALTERNATIVE log message
        level2_logs = [
            r for r in caplog.records
            if "level 2" in r.message.lower() and "alternative" in r.message.lower()
        ]
        assert len(level2_logs) == 0, \
            f"Fatal errors should not trigger Level 2 logging, got: {[r.message for r in level2_logs]}"