"""
Generated test cases for bug: tdd-regression-phase8

These tests verify the fix for the identified bug.
"""

import pytest


# Regression test: verify transient errors retry exactly 3 times (0,1,2) not 4 times
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointStore
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority
from swarm_attack.errors import LLMError, LLMErrorType


@pytest.mark.asyncio
async def test_retry_count_is_three_not_four():
    """Regression test: transient errors should execute exactly 3 times, not 4.
    
    The bug was: 'while retry_count <= self.max_retries' with max_retries=3
    executed 4 times (0,1,2,3). Correct is 'while attempt < MAX_RETRIES'
    which executes 3 times (0,1,2).
    """
    store = MagicMock(spec=CheckpointStore)
    store.save = AsyncMock()
    checkpoint_system = CheckpointSystem(config=None, store=store)
    recovery_manager = RecoveryManager(checkpoint_system)
    
    goal = DailyGoal(
        goal_id="test-retry-count",
        description="Test goal",
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )
    
    call_count = 0
    
    async def failing_action():
        nonlocal call_count
        call_count += 1
        raise LLMError("Timeout", error_type=LLMErrorType.TIMEOUT)
    
    with patch("swarm_attack.chief_of_staff.recovery.asyncio.sleep", new_callable=AsyncMock):
        result = await recovery_manager.execute_with_recovery(goal, failing_action)
    
    # CRITICAL: Should be exactly 3, not 4
    assert call_count == 3, f"Expected 3 attempts, got {call_count}. The loop condition is wrong."
    assert result.success is False
    assert goal.error_count == 3, f"Expected error_count=3, got {goal.error_count}"

# Regression test: verify execute_with_recovery returns GoalExecutionResult not RecoveryResult
import pytest
from unittest.mock import AsyncMock, MagicMock
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.chief_of_staff.autopilot_runner import GoalExecutionResult
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointStore
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority


@pytest.mark.asyncio
async def test_returns_goal_execution_result_not_recovery_result():
    """Regression test: execute_with_recovery must return GoalExecutionResult.
    
    The bug changed the return type to RecoveryResult, breaking the interface
    contract with callers that expect GoalExecutionResult fields like cost_usd.
    """
    store = MagicMock(spec=CheckpointStore)
    store.save = AsyncMock()
    checkpoint_system = CheckpointSystem(config=None, store=store)
    recovery_manager = RecoveryManager(checkpoint_system)
    
    goal = DailyGoal(
        goal_id="test-return-type",
        description="Test goal",
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )
    
    expected_result = GoalExecutionResult(
        success=True,
        cost_usd=2.5,
        duration_seconds=60,
    )
    
    async def successful_action():
        return expected_result
    
    result = await recovery_manager.execute_with_recovery(goal, successful_action)
    
    # CRITICAL: Must be GoalExecutionResult, not RecoveryResult
    assert isinstance(result, GoalExecutionResult), f"Expected GoalExecutionResult, got {type(result).__name__}"
    assert result.success is True
    assert result.cost_usd == 2.5
    assert result.duration_seconds == 60

# Regression test: verify that escalation properly sets goal.is_hiccup = True
import pytest
from unittest.mock import AsyncMock, MagicMock
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointStore
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority
from swarm_attack.errors import LLMError, LLMErrorType


@pytest.mark.asyncio
async def test_escalation_sets_goal_is_hiccup_true():
    """Regression test: escalation must set goal.is_hiccup = True.
    
    The bug removed the _escalate_to_human() call which sets is_hiccup=True
    and creates the HICCUP checkpoint. This breaks the entire escalation flow.
    """
    store = MagicMock(spec=CheckpointStore)
    store.save = AsyncMock()
    checkpoint_system = CheckpointSystem(config=None, store=store)
    recovery_manager = RecoveryManager(checkpoint_system)
    
    goal = DailyGoal(
        goal_id="test-hiccup-flag",
        description="Test goal",
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )
    
    async def fatal_failure():
        raise LLMError("Auth expired", error_type=LLMErrorType.AUTH_EXPIRED)
    
    await recovery_manager.execute_with_recovery(goal, fatal_failure)
    
    # CRITICAL: goal.is_hiccup must be True after escalation
    assert goal.is_hiccup is True, "goal.is_hiccup should be True after escalation"
    # Checkpoint should have been saved
    assert store.save.called, "Checkpoint store.save() should have been called"

# Regression test: verify Level 2 fallthrough log includes goal_id in structured format
import pytest
import logging
from unittest.mock import AsyncMock, MagicMock
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointStore
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority
from swarm_attack.errors import LLMError, LLMErrorType


@pytest.mark.asyncio
async def test_level2_log_includes_goal_id(caplog):
    """Regression test: Level 2 fallthrough log must include goal_id.
    
    The bug simplified the log format to not include goal_id, breaking
    the audit trail required by Issue #5's acceptance criteria.
    """
    store = MagicMock(spec=CheckpointStore)
    store.save = AsyncMock()
    checkpoint_system = CheckpointSystem(config=None, store=store)
    recovery_manager = RecoveryManager(checkpoint_system)
    
    goal = DailyGoal(
        goal_id="test-goal-level2-audit",
        description="Test goal for Level 2 logging",
        priority=GoalPriority.MEDIUM,
        estimated_minutes=30,
    )
    
    async def systematic_failure():
        raise LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)
    
    with caplog.at_level(logging.WARNING):
        await recovery_manager.execute_with_recovery(goal, systematic_failure)
    
    # Find Level 2 log messages
    level2_logs = [
        r for r in caplog.records
        if "level 2" in r.message.lower() or "alternative" in r.message.lower()
    ]
    assert len(level2_logs) >= 1, "Expected at least one Level 2 log message"
    
    # CRITICAL: Log must include goal_id for audit trail
    log_text = " ".join(r.message for r in level2_logs)
    assert goal.goal_id in log_text, f"Expected goal_id '{goal.goal_id}' in log, got: {log_text}"

