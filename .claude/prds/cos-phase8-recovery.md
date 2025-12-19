# Chief of Staff Phase 8: Hierarchical Recovery

## Overview

Implement hierarchical error recovery for AutopilotRunner so it can automatically retry and recover from failures without human intervention.

## Background

Phase 7 (Real Execution) is complete - AutopilotRunner now calls real orchestrators. But when execution fails, it just stops. We need automatic recovery.

## Requirements

### RecoveryManager Class

Create `swarm_attack/chief_of_staff/recovery.py` with:

```python
class RecoveryManager:
    """Hierarchical recovery with 4 levels."""

    LEVELS = [
        (RetryStrategy.SAME, max_attempts=3),      # Level 1: Retry same approach
        (RetryStrategy.ALTERNATIVE, max_attempts=2),  # Level 2: Try alternative
        (RetryStrategy.CLARIFY, max_attempts=1),   # Level 3: Ask clarifying question
        (RetryStrategy.ESCALATE, max_attempts=1),  # Level 4: Escalate to human
    ]

    async def execute_with_recovery(self, goal: DailyGoal, action: Callable) -> GoalExecutionResult:
        """Execute action with hierarchical recovery."""
        pass
```

### Integration Points

1. **AutopilotRunner._execute_goal()** should use RecoveryManager
2. **Checkpoint triggers** should be created for Level 3-4 escalations
3. **Episode logging** should record retry attempts for learning

### Retry Strategies

| Level | Strategy | When | Max Attempts |
|-------|----------|------|--------------|
| 1 | SAME | Transient failures (timeout, rate limit) | 3 |
| 2 | ALTERNATIVE | Systematic failures (approach didn't work) | 2 |
| 3 | CLARIFY | Unclear requirements | 1 |
| 4 | ESCALATE | Unrecoverable | 1 |

### Error Classification

RecoveryManager needs to classify errors:
- `TransientError`: Network, timeout, rate limit → Level 1
- `SystematicError`: Wrong approach, missing dependency → Level 2
- `AmbiguityError`: Unclear spec, multiple interpretations → Level 3
- `FatalError`: Security issue, destructive action → Level 4

## Success Criteria

1. Transient failures auto-retry up to 3 times
2. After 3 same-approach failures, try alternative approach
3. After alternatives exhausted, create checkpoint for human
4. All retry attempts logged for learning
5. Tests cover all 4 recovery levels

## Files to Create/Modify

- CREATE: `swarm_attack/chief_of_staff/recovery.py`
- MODIFY: `swarm_attack/chief_of_staff/autopilot_runner.py` (integrate RecoveryManager)
- CREATE: `tests/generated/cos-phase8-recovery/test_recovery.py`
