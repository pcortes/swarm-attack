# Fix Plan: tdd-regression-phase8

## Summary
Restore recovery.py from commit fd137c4 to fix uncommitted breaking changes that rewrote execute_with_recovery() with incompatible interfaces

## Risk Assessment
- **Risk Level:** LOW
- **Scope:** Single file: swarm_attack/chief_of_staff/recovery.py. Restores 3 key elements: (1) correct loop condition, (2) GoalExecutionResult return type, (3) _escalate_to_human() method with goal.is_hiccup assignment

### Risk Explanation
This fix restores the exact code from commit fd137c4, which was the last known-good state. The uncommitted changes are a complete rewrite that breaks backward compatibility. Restoring to the committed version is a safe operation with no risk of introducing new bugs - it simply reverts to tested, working code that all Issue #4 and #5 tests were written against.

## Proposed Changes

### Change 1: swarm_attack/chief_of_staff/recovery.py
- **Type:** modify
- **Explanation:** Restore TYPE_CHECKING import pattern from commit fd137c4 - Episode and EpisodeStore are imported at runtime inside the method, not at module level

**Current Code:**
```python
if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal

from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore
```

**Proposed Code:**
```python
if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal
    from swarm_attack.chief_of_staff.episodes import EpisodeStore
```

### Change 2: swarm_attack/chief_of_staff/recovery.py
- **Type:** modify
- **Explanation:** Remove max_retries instance variable (use MAX_RETRIES constant) and restore original __init__ signature with int types instead of float for backoff parameters

**Current Code:**
```python
class RecoveryManager:
    """Manager for handling goal execution with retry and escalation logic.

    Implements a 4-level hierarchical recovery system:
    - Level 1 (SAME): Retry same approach with exponential backoff for transient errors
    - Level 2 (ALTERNATIVE): Extension point for future alternative approaches
    - Level 3 (CLARIFY): Human-triggered clarification via checkpoint
    - Level 4 (ESCALATE): Escalate to human for manual intervention
    """

    def __init__(
        self,
        checkpoint_system: "CheckpointSystem",
        max_retries: int = MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
    ) -> None:
        """Initialize RecoveryManager.

        Args:
            checkpoint_system: System for creating escalation checkpoints.
            max_retries: Maximum retry attempts for transient errors.
            backoff_base_seconds: Base delay for exponential backoff.
            backoff_multiplier: Multiplier for exponential backoff.
        """
        self.checkpoint_system = checkpoint_system
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_multiplier = backoff_multiplier
```

**Proposed Code:**
```python
class RecoveryManager:
    """Manager for handling goal execution with retry and escalation logic.

    Implements a 4-level hierarchical recovery system:
    - Level 1 (SAME): Transient errors retry up to 3 times with exponential backoff
    - Level 2 (ALTERNATIVE): Systematic errors log fallthrough and proceed to Level 4
    - Level 3 (CLARIFY): Not auto-triggered - extension point for human-triggered retries
    - Level 4 (ESCALATE): Fatal errors + fallthrough create HICCUP checkpoint

    Usage:
        recovery = RecoveryManager(checkpoint_system)

        async def execute_goal():
            # goal execution logic
            return GoalExecutionResult(...)

        result = await recovery.execute_with_recovery(goal, execute_goal)
    """

    def __init__(
        self,
        checkpoint_system: "CheckpointSystem",
        backoff_base_seconds: int = DEFAULT_BACKOFF_BASE_SECONDS,
        backoff_multiplier: int = DEFAULT_BACKOFF_MULTIPLIER,
    ) -> None:
        """Initialize RecoveryManager.

        Args:
            checkpoint_system: CheckpointSystem for creating escalation checkpoints.
            backoff_base_seconds: Base delay for exponential backoff (default: 5).
            backoff_multiplier: Multiplier for exponential backoff (default: 2).
        """
        self.checkpoint_system = checkpoint_system
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_multiplier = backoff_multiplier
```

### Change 3: swarm_attack/chief_of_staff/recovery.py
- **Type:** modify
- **Explanation:** Restore the complete execute_with_recovery() method from commit fd137c4. Key fixes: (1) Use 'while attempt < MAX_RETRIES' for correct 3 iterations, (2) Return GoalExecutionResult instead of RecoveryResult, (3) Restore goal.error_count += 1 on each failure, (4) Restore _log_level2_fallthrough() helper method with goal_id, (5) Restore _escalate_to_human() method that sets goal.is_hiccup = True and creates checkpoint

**Current Code:**
```python
    async def execute_with_recovery(
        self,
        goal: "DailyGoal",
        execute_fn: Callable[[], Awaitable[Any]],
        episode_store: Optional[EpisodeStore] = None,
    ) -> RecoveryResult:
        """Execute a goal with hierarchical recovery.

        Args:
            goal: The goal to execute.
            execute_fn: Async function that executes the goal.
            episode_store: Optional store for logging episodes.

        Returns:
            RecoveryResult with success status and any error info.
        """
        retry_count = 0
        last_error: Optional[Exception] = None
        last_strategy: Optional[RetryStrategy] = None
        
        while retry_count <= self.max_retries:
            try:
                result = await execute_fn()
                
                # Log success episode
                if episode_store is not None:
                    episode = Episode(
                        episode_id=f"ep-{uuid.uuid4().hex[:12]}",
                        timestamp=datetime.utcnow().isoformat(),
                        goal_id=goal.goal_id,
                        success=True,
                        cost_usd=getattr(result, "cost_usd", 0.0),
                        duration_seconds=0,
                        retry_count=retry_count,
                        recovery_level=last_strategy.value if last_strategy else None,
                    )
                    episode_store.save(episode)
                
                return RecoveryResult(
                    success=True,
                    action_result=result,
                    retry_count=retry_count,
                )
                
            except Exception as e:
                last_error = e
                category = classify_error(e)
                
                if category == ErrorCategory.TRANSIENT:
                    # Level 1: Retry with exponential backoff
                    retry_count += 1
                    last_strategy = RetryStrategy.SAME
                    
                    if retry_count <= self.max_retries:
                        backoff = self.backoff_base_seconds * (
                            self.backoff_multiplier ** (retry_count - 1)
                        )
                        logger.info(
                            f"Transient error, retrying in {backoff}s "
                            f"(attempt {retry_count}/{self.max_retries}): {e}"
                        )
                        await asyncio.sleep(backoff)
                        continue
                    else:
                        # Exhausted retries, escalate
                        last_strategy = RetryStrategy.ESCALATE
                        break
                        
                elif category == ErrorCategory.SYSTEMATIC:
                    # Level 2: Log fallthrough and escalate
                    logger.warning(
                        f"Level 2 fallthrough: systematic error '{e}' has no "
                        f"alternative approach implemented. Escalating to Level 4."
                    )
                    last_strategy = RetryStrategy.ESCALATE
                    break
                    
                else:  # FATAL
                    # Level 4: Immediate escalation
                    logger.error(f"Fatal error, escalating immediately: {e}")
                    last_strategy = RetryStrategy.ESCALATE
                    break
        
        # Log failure episode
        if episode_store is not None:
            episode = Episode(
                episode_id=f"ep-{uuid.uuid4().hex[:12]}",
                timestamp=datetime.utcnow().isoformat(),
                goal_id=goal.goal_id,
                success=False,
                cost_usd=0.0,
                duration_seconds=0,
                retry_count=retry_count,
                recovery_level=last_strategy.value if last_strategy else RetryStrategy.ESCALATE.value,
                error=str(last_error) if last_error else None,
            )
            episode_store.save(episode)
        
        return RecoveryResult(
            success=False,
            error=str(last_error) if last_error else "Unknown error",
            retry_count=retry_count,
            escalated=True,
        )
```

**Proposed Code:**
```python
    def _log_level2_fallthrough(
        self,
        goal_id: str,
        error_type: LLMErrorType,
        error_message: str,
    ) -> None:
        """Log explicit message when Level 2 ALTERNATIVE falls through to ESCALATE.
        
        This creates an audit trail and makes the extension point visible for
        future implementation of alternative recovery strategies.
        
        Args:
            goal_id: The ID of the goal that encountered the error.
            error_type: The LLMErrorType of the systematic error.
            error_message: The error message from the exception.
        """
        timestamp = datetime.now().isoformat()
        logger.warning(
            f"[{timestamp}] Level 2 ALTERNATIVE not implemented, falling through to ESCALATE | "
            f"goal_id={goal_id} | error_type={error_type.name} | error={error_message}"
        )

    async def execute_with_recovery(
        self,
        goal: "DailyGoal",
        execute_fn: Callable[[], Awaitable[Any]],
        episode_store: Optional["EpisodeStore"] = None,
    ) -> "GoalExecutionResult":
        """Execute goal with hierarchical recovery.

        Routes errors through the 4-level recovery hierarchy:
        - Level 1 (SAME): Transient errors retry up to 3 times with exponential backoff
        - Level 2 (ALTERNATIVE): Systematic errors log fallthrough and proceed to Level 4
        - Level 3 (CLARIFY): Not auto-triggered - extension point for human-triggered retries
        - Level 4 (ESCALATE): Fatal errors + fallthrough create HICCUP checkpoint

        Args:
            goal: The DailyGoal being executed (error_count is incremented on failure).
            execute_fn: Async callable that performs the goal execution.
            episode_store: Optional EpisodeStore for logging recovery episodes.

        Returns:
            GoalExecutionResult with success status, cost, duration, and error info.
        """
        # Import here to avoid circular imports
        from swarm_attack.chief_of_staff.autopilot_runner import GoalExecutionResult
        from swarm_attack.chief_of_staff.episodes import Episode

        last_error: Optional[str] = None
        last_exception: Optional[Exception] = None
        retry_count = 0
        recovery_level = RetryStrategy.SAME.value
        start_time = datetime.now()

        # Attempt execution with retry logic for transient errors
        backoff = self.backoff_base_seconds
        attempt = 0

        while attempt < MAX_RETRIES:
            try:
                result = await execute_fn()
                
                # Log successful episode if store provided
                if episode_store is not None:
                    duration = int((datetime.now() - start_time).total_seconds())
                    episode = Episode(
                        episode_id=f"ep-{uuid.uuid4().hex[:8]}",
                        timestamp=datetime.now().isoformat(),
                        goal_id=goal.goal_id,
                        success=True,
                        cost_usd=getattr(result, "cost_usd", 0.0),
                        duration_seconds=duration,
                        retry_count=retry_count,
                        recovery_level=RetryStrategy.SAME.value if retry_count > 0 else None,
                    )
                    episode_store.save(episode)

                return result

            except Exception as e:
                attempt += 1
                goal.error_count += 1
                last_error = str(e)
                last_exception = e
                retry_count += 1

                # Classify error to determine recovery level
                category = classify_error(e)

                if category == ErrorCategory.TRANSIENT:
                    # Level 1: SAME - Retry with exponential backoff
                    recovery_level = RetryStrategy.SAME.value
                    
                    if attempt < MAX_RETRIES:
                        logger.info(
                            f"Level 1 (SAME): Transient error, retrying in {backoff}s "
                            f"(attempt {attempt}/{MAX_RETRIES}): {last_error}"
                        )
                        await asyncio.sleep(backoff)
                        backoff *= self.backoff_multiplier
                        continue
                    else:
                        # Exhausted retries, fall through to escalation
                        logger.warning(
                            f"Level 1 exhausted: Transient error persisted after {MAX_RETRIES} "
                            f"retries, escalating to Level 4"
                        )
                        recovery_level = RetryStrategy.ESCALATE.value
                        break

                elif category == ErrorCategory.SYSTEMATIC:
                    # Level 2: ALTERNATIVE - Extension point, falls through to Level 4
                    # Log explicit fallthrough message for audit trail and future extension
                    error_type = getattr(e, "error_type", None)
                    self._log_level2_fallthrough(
                        goal_id=goal.goal_id,
                        error_type=error_type,
                        error_message=last_error,
                    )
                    recovery_level = RetryStrategy.ESCALATE.value
                    break

                elif category == ErrorCategory.FATAL:
                    # Level 4: ESCALATE - Immediate escalation
                    logger.error(
                        f"Level 4 (ESCALATE): Fatal error detected, "
                        f"escalating immediately: {last_error}"
                    )
                    recovery_level = RetryStrategy.ESCALATE.value
                    break

        # All attempts exhausted or escalation triggered
        # Level 4: Create HICCUP checkpoint
        await self._escalate_to_human(goal, last_error or "Unknown error")

        # Log failed episode if store provided
        duration = int((datetime.now() - start_time).total_seconds())
        if episode_store is not None:
            episode = Episode(
                episode_id=f"ep-{uuid.uuid4().hex[:8]}",
                timestamp=datetime.now().isoformat(),
                goal_id=goal.goal_id,
                success=False,
                cost_usd=0.0,
                duration_seconds=duration,
                retry_count=retry_count,
                recovery_level=recovery_level,
                error=last_error,
            )
            episode_store.save(episode)

        return GoalExecutionResult(
            success=False,
            cost_usd=0.0,
            duration_seconds=duration,
            error=last_error,
        )

    async def _escalate_to_human(
        self,
        goal: "DailyGoal",
        failure_reason: str,
    ) -> None:
        """Escalate a goal to human-in-the-loop with HICCUP checkpoint.

        Sets goal.is_hiccup = True and creates a checkpoint with context
        including retry count, goal content, and error details.

        Args:
            goal: The DailyGoal that failed after retries.
            failure_reason: The error message from the last attempt.
        """
        from swarm_attack.chief_of_staff.checkpoints import (
            Checkpoint,
            CheckpointOption,
            CheckpointTrigger,
        )

        # Mark goal as hiccup
        goal.is_hiccup = True

        # Build context with retry info
        context = (
            f"Goal failed after recovery attempts.\n\n"
            f"Goal: {goal.description}\n"
            f"Error: {failure_reason}\n"
            f"Total errors: {goal.error_count}"
        )

        # Create HICCUP checkpoint
        checkpoint = Checkpoint(
            checkpoint_id=f"hiccup-{uuid.uuid4().hex[:8]}",
            trigger=CheckpointTrigger.HICCUP,
            context=context,
            options=[
                CheckpointOption(
                    label="Skip this goal",
                    description="Mark goal as skipped and continue",
                ),
                CheckpointOption(
                    label="Retry with modifications",
                    description="Provide additional context and retry",
                ),
                CheckpointOption(
                    label="Handle manually",
                    description="I'll handle this myself",
                ),
            ],
            recommendation="Review the error and decide how to proceed.",
            created_at=datetime.now().isoformat(),
            goal_id=goal.goal_id,
        )

        # Store checkpoint for human review
        await self.checkpoint_system.store.save(checkpoint)
```

## Test Cases

### Test 1: test_retry_count_is_three_not_four
- **Category:** regression
- **Description:** Regression test: verify transient errors retry exactly 3 times (0,1,2) not 4 times

```python
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
```

### Test 2: test_returns_goal_execution_result_not_recovery_result
- **Category:** regression
- **Description:** Regression test: verify execute_with_recovery returns GoalExecutionResult not RecoveryResult

```python
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
```

### Test 3: test_escalation_sets_goal_is_hiccup_true
- **Category:** regression
- **Description:** Regression test: verify that escalation properly sets goal.is_hiccup = True

```python
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
```

### Test 4: test_level2_log_includes_goal_id
- **Category:** regression
- **Description:** Regression test: verify Level 2 fallthrough log includes goal_id in structured format

```python
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
```

## Potential Side Effects
- Issue #6 tests (test_issue_6.py) may need to be updated if they depend on the new RecoveryResult type
- Any in-progress Issue #6 implementation will need to be redone with backward-compatible changes

## Rollback Plan
The fix IS the rollback - it restores recovery.py to commit fd137c4 state. If further issues arise, git checkout fd137c4 -- swarm_attack/chief_of_staff/recovery.py will restore the known-good version.

## Estimated Effort
Small - single file restore via git checkout fd137c4 -- swarm_attack/chief_of_staff/recovery.py
