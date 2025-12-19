# Engineering Spec: Chief of Staff Phase 8 - Hierarchical Recovery

## 1. Overview

### 1.1 Purpose

Enhance the existing `RecoveryManager` to implement a 4-level hierarchical recovery system. When goal execution fails, the system automatically tries different recovery strategies before escalating to humans, reducing manual intervention for transient issues.

### 1.2 Existing Infrastructure

The codebase already has substantial recovery infrastructure:

| Component | Location | Current State |
|-----------|----------|---------------|
| `RecoveryManager` | `swarm_attack/chief_of_staff/recovery.py` | Basic 3-retry with escalation |
| `CheckpointSystem` | `swarm_attack/chief_of_staff/checkpoints.py` | Full trigger detection, checkpoint creation |
| `CheckpointTrigger.HICCUP` | `checkpoints.py:30` | Already exists for error escalation |
| `EpisodeStore` | `swarm_attack/chief_of_staff/episodes.py` | JSONL logging for episodes |
| `LLMErrorType` | `swarm_attack/errors.py` | Error classification (RATE_LIMIT, TIMEOUT, etc.) |
| `GoalExecutionResult` | `swarm_attack/chief_of_staff/autopilot_runner.py:41` | Execution result model |
| `DailyGoal.error_count` | `swarm_attack/chief_of_staff/goal_tracker.py:59` | Already tracks errors per goal |
| `DailyGoal.is_hiccup` | `swarm_attack/chief_of_staff/goal_tracker.py:60` | Already marks hiccups |

### 1.3 Scope

**In Scope:**
- Extend `RecoveryManager` with 4-level recovery hierarchy
- Add error classification to map errors to recovery levels
- Integrate with `AutopilotRunner._execute_goal()`
- Log retry attempts via `EpisodeStore`
- Create checkpoints for Level 3-4 escalations

**Out of Scope:**
- Alternative approach generation (Level 2 is extension point only)
- LLM-based clarifying questions (Level 3 is manual via checkpoint)
- Changes to Orchestrator or BugOrchestrator internals
- Recovery configuration UI

## 2. Implementation

### 2.1 Approach

Extend the existing `RecoveryManager` (recovery.py:44) rather than creating a new class. The current implementation already has retry logic with exponential backoff - we'll enhance it with:

1. Error classification using existing `LLMErrorType` from `errors.py`
2. Four recovery levels with different strategies
3. Episode logging for learning/debugging
4. Checkpoint creation for human escalation (levels 3-4)

### 2.2 Changes Required

| File | Change | Why |
|------|--------|-----|
| `swarm_attack/chief_of_staff/recovery.py` | Add `RetryStrategy` enum, `ErrorCategory`, expand `RecoveryManager` | Core recovery logic |
| `swarm_attack/chief_of_staff/recovery.py` | Add `classify_error()` function | Map exceptions to recovery levels |
| `swarm_attack/chief_of_staff/autopilot_runner.py` | Wrap `_execute_goal()` with recovery | Integration point |
| `swarm_attack/chief_of_staff/episodes.py` | Add `retry_count`, `recovery_level` fields to `Episode` | Track retries for learning |
| `tests/generated/cos-phase8-recovery/test_recovery.py` | Create test file | Verify recovery behavior |

### 2.3 Data Model

**Extend `recovery.py` with:**

```python
# New enum at recovery.py
class RetryStrategy(Enum):
    """Strategy for retry attempts."""
    SAME = "same"           # Retry same approach
    ALTERNATIVE = "alternative"  # Extension point for future work
    CLARIFY = "clarify"     # Manual clarification via checkpoint
    ESCALATE = "escalate"   # Escalate to human

class ErrorCategory(Enum):
    """Classification of errors for recovery routing."""
    TRANSIENT = "transient"     # Network, timeout, rate limit -> Level 1
    SYSTEMATIC = "systematic"   # Wrong approach -> falls through to Level 4
    FATAL = "fatal"             # Security issue, destructive -> Level 4
```

**Note on ErrorCategory:** We intentionally omit AMBIGUITY as a category because ambiguity is not detectable by the system - it requires human judgment. When humans review escalations, they can choose "Retry with modifications" to effectively clarify requirements.

**Extend `Episode` dataclass (episodes.py:22):**

```python
# Add these fields to Episode
retry_count: int = 0
recovery_level: Optional[str] = None  # "same", "alternative", "clarify", "escalate"
```

## 3. Recovery Hierarchy

### 3.1 Level Definitions

| Level | Strategy | Error Types | Max Attempts | Behavior |
|-------|----------|-------------|--------------|----------|
| 1 | SAME | Transient (timeout, rate limit, server error) | 3 | Exponential backoff (5s, 10s, 20s) |
| 2 | ALTERNATIVE | Systematic (approach failed) | N/A | **Extension point - falls through to Level 4** |
| 3 | CLARIFY | N/A (human-triggered) | N/A | **Triggered by human via checkpoint, not auto-detected** |
| 4 | ESCALATE | Fatal + fallthrough from Level 2 | 1 | Creates HICCUP checkpoint |

**Why Level 2 is an extension point:** We currently have one orchestrator per task type. There's no "alternative approach" to try - you either run the FeatureOrchestrator or you don't. In the future, if we add multiple execution strategies (e.g., different LLM models, different code generation approaches), Level 2 can be expanded to try alternatives. For now, SYSTEMATIC errors fall through to ESCALATE.

**Why Level 3 is human-triggered:** Ambiguity ("unclear requirements") is not machine-detectable. When a human reviews an escalation checkpoint, choosing "Retry with modifications" is effectively the CLARIFY action.

### 3.2 Error Classification Mapping

Leverage existing `LLMErrorType` from `errors.py`:

```python
TRANSIENT_ERRORS = {
    LLMErrorType.RATE_LIMIT,
    LLMErrorType.RATE_LIMIT_TIMED,
    LLMErrorType.SERVER_OVERLOADED,
    LLMErrorType.SERVER_ERROR,
    LLMErrorType.TIMEOUT,
}

SYSTEMATIC_ERRORS = {
    LLMErrorType.CLI_CRASH,
    LLMErrorType.JSON_PARSE_ERROR,
}
# Note: SYSTEMATIC errors fall through to ESCALATE since we don't have alternative approaches

FATAL_ERRORS = {
    LLMErrorType.AUTH_REQUIRED,
    LLMErrorType.AUTH_EXPIRED,
    LLMErrorType.CLI_NOT_FOUND,
}
```

### 3.3 Recovery Flow

```
Error occurs
    │
    ├─ TRANSIENT? ──────────────────────────────────────────────┐
    │                                                            │
    │                                                            v
    │                                              ┌─────────────────────────┐
    │                                              │ Level 1: SAME           │
    │                                              │ Retry up to 3 times     │
    │                                              │ with exponential backoff│
    │                                              └─────────────────────────┘
    │                                                            │
    │                                                     Still failing?
    │                                                            │
    │                                                            v
    ├─ SYSTEMATIC? ─────────────────────────┐     ┌─────────────────────────┐
    │                                        │     │ Level 2: ALTERNATIVE    │
    │                                        ├────>│ (Extension point)       │
    │                                        │     │ Falls through to L4     │
    │                                        │     └─────────────────────────┘
    │                                        │                   │
    │                                        │                   v
    └─ FATAL? ──────────────────────────────┴────>┌─────────────────────────┐
                                                   │ Level 4: ESCALATE       │
                                                   │ Create HICCUP checkpoint│
                                                   └─────────────────────────┘
                                                              │
                                                    Human reviews checkpoint
                                                              │
                                                   ┌──────────┼──────────┐
                                                   │          │          │
                                                   v          v          v
                                              [Skip]   [Retry w/    [Manual]
                                                       modifications]
                                                              │
                                                              v
                                                   ┌─────────────────────────┐
                                                   │ Level 3: CLARIFY        │
                                                   │ (Human-triggered)       │
                                                   │ Resume with new context │
                                                   └─────────────────────────┘
```

## 4. Implementation Tasks

| # | Task | Files | Size |
|---|------|-------|------|
| 1 | Add `RetryStrategy` and `ErrorCategory` enums to recovery.py | recovery.py | S |
| 2 | Implement `classify_error()` function using LLMErrorType patterns | recovery.py | S |
| 3 | Refactor `execute_with_recovery()` to support 4 levels | recovery.py | M |
| 4 | Log Level 2 fallthrough explicitly (for future extension) | recovery.py | S |
| 5 | Add `retry_count` and `recovery_level` fields to Episode | episodes.py | S |
| 6 | Log retry attempts in RecoveryManager via EpisodeStore | recovery.py | S |
| 7 | Integrate RecoveryManager into AutopilotRunner._execute_goal() | autopilot_runner.py | M |
| 8 | Create tests for all 4 recovery levels | test_recovery.py | M |

## 5. Testing

### 5.1 Manual Test Plan

1. **Transient failure recovery:**
   - Trigger a timeout error during goal execution
   - Verify 3 retry attempts with exponential backoff
   - Check episode log shows retry_count=3

2. **Escalation to human:**
   - Trigger an auth error (fatal)
   - Verify immediate escalation (no retries)
   - Verify checkpoint created with trigger=HICCUP

3. **Resume after checkpoint:**
   - Resolve a HICCUP checkpoint with "Retry with modifications"
   - Verify goal execution resumes

### 5.2 Automated Tests

```python
# tests/generated/cos-phase8-recovery/test_recovery.py

def test_classify_transient_error():
    """Rate limit errors should classify as TRANSIENT."""

def test_classify_systematic_error():
    """CLI crash errors should classify as SYSTEMATIC."""

def test_classify_fatal_error():
    """Auth errors should classify as FATAL."""

def test_level1_retries_three_times():
    """Transient errors retry 3 times with backoff."""

def test_level2_falls_through_to_escalate():
    """Systematic errors log fallthrough and escalate."""

def test_level3_triggered_by_human_choice():
    """Level 3 CLARIFY is triggered when human chooses 'Retry with modifications'."""

def test_level4_escalates_immediately():
    """Fatal errors create checkpoint without retry."""

def test_episode_logs_retry_count():
    """Episodes record retry attempts for learning."""

def test_episode_logs_recovery_level():
    """Episodes record which recovery level was reached."""

def test_integration_with_autopilot_runner():
    """AutopilotRunner uses RecoveryManager for execution."""
```

## 6. Future Extensions

### 6.1 Level 2 Alternative Approaches (Not in Scope)

When we have multiple execution strategies, Level 2 can be expanded:

- Different LLM models (Opus vs Sonnet)
- Different prompting strategies
- Different code generation approaches

For now, this is an extension point that logs and falls through.

### 6.2 Level 3 Automated Clarification (Not in Scope)

Future work could add LLM-based ambiguity detection, but this requires:

- Defining what "ambiguity" looks like in error output
- Building a clarifying question generator
- This is over-engineering for our current 100-user stage

## 7. Open Questions

None. The spec is focused on what we can ship now, with clear extension points for future work.

## 8. PRD Deviation Note

The PRD specifies `AmbiguityError` classification and Level 2 alternative attempts. After analysis, these are not implementable with current infrastructure:

1. **AmbiguityError:** There is no exception type that indicates "unclear requirements." This is a human judgment, not machine detectable. The checkpoint system already supports human clarification via "Retry with modifications."

2. **Level 2 alternatives:** We have one orchestrator per task type. There is no alternative approach to try. When we add multiple execution strategies in the future, this extension point is ready.

The spec implements the PRD's intent (automatic recovery for transient failures, human escalation for unrecoverable ones) while being honest about what is currently implementable.