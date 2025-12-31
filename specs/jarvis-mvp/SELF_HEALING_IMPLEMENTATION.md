# Self-Healing Jarvis: Implementation Spec

## LLM Implementation Prompt

Copy everything below this line and give to an LLM to implement:

---

# IMPLEMENTATION TASK: Self-Healing Jarvis

You are implementing two critical components that transform Jarvis from a "batch job that stops" into a "self-healing autonomous partner."

## Your Mission

Implement ~300 lines of code across 2 new files + 2 modifications to make existing tests pass.

## Pre-existing Tests (Already Written)

Tests are at:
- `tests/chief_of_staff/test_checkpoint_ux.py` (14 tests)
- `tests/chief_of_staff/test_level2_recovery.py` (15 tests)

Run tests with:
```bash
PYTHONPATH=. pytest tests/chief_of_staff/test_checkpoint_ux.py tests/chief_of_staff/test_level2_recovery.py -v
```

**Your goal: Make ALL tests pass (GREEN).**

---

## COMPONENT 1: Blocking Checkpoint UX (~100 LOC)

### File to Create: `swarm_attack/chief_of_staff/checkpoint_ux.py`

### Purpose
When a checkpoint triggers, BLOCK execution and prompt user for a decision interactively. Currently checkpoints just pause - user must manually discover and approve them.

### Required Classes

```python
"""Blocking checkpoint UX for interactive decision making."""

from dataclasses import dataclass
from typing import Optional

from swarm_attack.chief_of_staff.checkpoints import Checkpoint, CheckpointOption


@dataclass
class CheckpointDecision:
    """Result of a checkpoint decision."""
    checkpoint_id: str
    chosen_option: str
    notes: str = ""


class CheckpointUX:
    """Interactive checkpoint UX that blocks until user decides."""

    def format_checkpoint(self, checkpoint: Checkpoint) -> str:
        """
        Format checkpoint for display.

        Must include:
        - Trigger type (e.g., HICCUP, UX_CHANGE)
        - Context
        - Numbered options [1], [2], [3]
        - Mark recommended option

        Example output:
        ⚠️  HICCUP Checkpoint
        ━━━━━━━━━━━━━━━━━━━━━
        Goal failed after retries.
        Goal: Implement auth
        Error: Import failed

        Options:
          [1] Proceed - Continue execution (recommended)
          [2] Skip - Skip this goal
          [3] Pause - Pause for manual review

        Recommendation: Proceed is recommended based on similar past decisions
        """
        # IMPLEMENT THIS
        pass

    def get_decision(
        self,
        checkpoint: Checkpoint,
        allow_notes: bool = False
    ) -> CheckpointDecision:
        """
        Get user decision for checkpoint.

        Behavior:
        - Display formatted checkpoint
        - Prompt for input (1, 2, 3, etc.)
        - Empty input selects recommended option
        - Invalid input reprompts
        - If allow_notes, prompt for optional notes after selection

        Returns:
            CheckpointDecision with chosen_option and notes
        """
        # IMPLEMENT THIS
        pass

    def prompt_and_wait(self, checkpoint: Checkpoint) -> CheckpointDecision:
        """
        Display checkpoint and block until user responds.

        Convenience method that calls format_checkpoint, prints it,
        then calls get_decision.

        This is the main entry point for blocking checkpoint flow.
        """
        # IMPLEMENT THIS
        pass
```

### Implementation Notes

1. Use `print()` for output (tests use capsys to capture)
2. Use `input()` for prompts (tests mock this)
3. Find recommended option: `next((o for o in checkpoint.options if o.is_recommended), checkpoint.options[0])`
4. Handle invalid input by looping until valid
5. Empty string input = select recommended

### Test Cases to Pass

```
test_checkpoint_ux_import - Module imports
test_checkpoint_ux_init - Class instantiates
test_format_checkpoint_includes_context - Context in output
test_format_checkpoint_shows_numbered_options - [1], [2], [3] visible
test_format_checkpoint_marks_recommended - "recommended" appears
test_get_decision_returns_selected_option - Input "1" returns first option
test_get_decision_skip_option - Input "2" returns second
test_get_decision_pause_option - Input "3" returns third
test_get_decision_empty_input_selects_recommended - "" selects recommended
test_get_decision_invalid_reprompts - Bad input tries again
test_get_decision_allows_notes - Second prompt for notes
test_decision_dataclass_fields - Dataclass has required fields
test_prompt_and_wait_blocks_until_input - Blocks on input()
test_prompt_and_wait_displays_formatted - Prints formatted output
```

---

## COMPONENT 2: Level 2 Intelligent Recovery (~150 LOC)

### File to Create: `swarm_attack/chief_of_staff/level2_recovery.py`

### Purpose
When a systematic error occurs (CLI crash, JSON parse error), use LLM to decide recovery strategy instead of immediately escalating to human.

### Required Classes

```python
"""Level 2 intelligent recovery with LLM-powered decision making."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm_attack.chief_of_staff.goal_tracker import DailyGoal


class RecoveryActionType(Enum):
    """Types of recovery actions Level 2 can suggest."""
    ALTERNATIVE = "alternative"   # Try different approach
    DIAGNOSTICS = "diagnostics"   # Run bug bash / diagnostics
    UNBLOCK = "unblock"           # Use admin unblock commands
    ESCALATE = "escalate"         # Give up, escalate to human


@dataclass
class RecoveryAction:
    """Action suggested by Level 2 analyzer."""
    action_type: RecoveryActionType
    hint: str = ""                # Hint for retry (e.g., "try async")
    reasoning: str = ""           # Why this action


class Level2Analyzer:
    """
    LLM-powered recovery analyzer for systematic errors.

    When a systematic error occurs (not transient, not fatal),
    asks LLM to suggest a recovery strategy.
    """

    def __init__(
        self,
        llm: Any,
        max_alternatives: int = 2,  # Max alternative attempts before escalate
    ):
        """
        Initialize Level 2 analyzer.

        Args:
            llm: LLM client with async ask() method
            max_alternatives: Max times to try alternative before escalating
        """
        self.llm = llm
        self.max_alternatives = max_alternatives
        self._alternative_count = 0

    async def analyze(
        self,
        goal: "DailyGoal",
        error: Exception,
    ) -> RecoveryAction:
        """
        Analyze error and suggest recovery action.

        Calls LLM with prompt:
        - Goal description
        - Error message
        - Ask for: action (alternative/diagnostics/unblock/escalate), hint, reasoning

        Returns:
            RecoveryAction with suggested strategy
        """
        # IMPLEMENT THIS
        # 1. Build prompt with goal.description and str(error)
        # 2. Call self.llm.ask(prompt)
        # 3. Parse JSON response
        # 4. Return RecoveryAction
        # 5. Handle invalid JSON by returning ESCALATE
        # 6. Handle LLM exception by returning ESCALATE
        pass

    def _build_prompt(self, goal: "DailyGoal", error: Exception) -> str:
        """Build LLM prompt for recovery analysis."""
        return f"""You are a recovery analyzer for an AI development system.

A goal failed with a systematic error. Analyze and suggest recovery.

GOAL: {goal.description}
ERROR: {str(error)}

Choose ONE action:
- "alternative": Suggest a different approach to try
- "diagnostics": Run bug bash or diagnostics to investigate
- "unblock": Use admin commands to reset/unblock state
- "escalate": Give up and ask human (last resort)

Respond with JSON only:
{{"action": "alternative|diagnostics|unblock|escalate", "hint": "specific suggestion", "reasoning": "why this action"}}
"""

    def _parse_response(self, response: str) -> RecoveryAction:
        """Parse LLM response into RecoveryAction."""
        try:
            data = json.loads(response)
            action_type = RecoveryActionType(data.get("action", "escalate"))
            return RecoveryAction(
                action_type=action_type,
                hint=data.get("hint", ""),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError):
            return RecoveryAction(
                action_type=RecoveryActionType.ESCALATE,
                hint="",
                reasoning="Failed to parse LLM response",
            )
```

### Implementation Notes

1. LLM has async `ask(prompt: str) -> str` method
2. Response is JSON string, parse it
3. Invalid JSON = return ESCALATE
4. LLM exception = return ESCALATE
5. Track alternative count to limit retries

### Test Cases to Pass

```
test_level2_analyzer_import - Module imports
test_level2_analyzer_init - Class instantiates with LLM
test_recovery_action_types_exist - Enum has expected values
test_recovery_action_dataclass - Dataclass has fields
test_analyze_calls_llm - LLM.ask() called with prompt
test_analyze_returns_alternative - Returns ALTERNATIVE when LLM suggests
test_analyze_returns_diagnostics - Returns DIAGNOSTICS
test_analyze_returns_unblock - Returns UNBLOCK
test_analyze_returns_escalate_as_fallback - Returns ESCALATE
test_analyze_handles_invalid_llm_response - Invalid JSON = ESCALATE
test_analyze_handles_llm_exception - Exception = ESCALATE
test_recovery_manager_has_level2_analyzer - RecoveryManager accepts analyzer
test_systematic_error_triggers_level2 - Systematic errors call Level 2
test_level2_alternative_retries_with_hint - Hint passed to retry
test_level2_limits_alternative_attempts - Max 2 alternatives then escalate
```

---

## COMPONENT 3: Wire Level 2 into RecoveryManager (~50 LOC)

### File to Modify: `swarm_attack/chief_of_staff/recovery.py`

### Changes Needed

1. Add `level2_analyzer` parameter to `__init__`:

```python
def __init__(
    self,
    checkpoint_system: "CheckpointSystem",
    level2_analyzer: Optional["Level2Analyzer"] = None,  # NEW
    backoff_base_seconds: int = DEFAULT_BACKOFF_BASE_SECONDS,
    backoff_multiplier: int = DEFAULT_BACKOFF_MULTIPLIER,
) -> None:
    self.checkpoint_system = checkpoint_system
    self.level2_analyzer = level2_analyzer  # NEW
    # ... rest unchanged
```

2. Replace Level 2 stub (lines 302-312) with actual analysis:

```python
elif category == ErrorCategory.SYSTEMATIC:
    # Level 2: ALTERNATIVE - Use LLM to decide recovery
    if self.level2_analyzer:
        action = await self.level2_analyzer.analyze(goal, e)

        if action.action_type == RecoveryActionType.ALTERNATIVE:
            # Add hint to goal for retry
            goal.recovery_hint = action.hint
            recovery_level = RetryStrategy.ALTERNATIVE.value
            continue  # Retry with hint

        elif action.action_type == RecoveryActionType.DIAGNOSTICS:
            # Log for future: could run bug bash here
            logger.info(f"Level 2 suggests diagnostics: {action.hint}")
            recovery_level = RetryStrategy.ESCALATE.value
            break

        elif action.action_type == RecoveryActionType.UNBLOCK:
            # Log for future: could run unblock here
            logger.info(f"Level 2 suggests unblock: {action.hint}")
            recovery_level = RetryStrategy.ESCALATE.value
            break

        else:  # ESCALATE
            recovery_level = RetryStrategy.ESCALATE.value
            break
    else:
        # No analyzer, fall through to escalate (original behavior)
        self._log_level2_fallthrough(goal.goal_id, error_type, last_error)
        recovery_level = RetryStrategy.ESCALATE.value
        break
```

3. Import at top of file:

```python
from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer, RecoveryActionType
```

---

## COMPONENT 4: Wire Checkpoint UX into Autopilot (~30 LOC)

### File to Modify: `swarm_attack/chief_of_staff/autopilot_runner.py`

### Changes Needed

1. Add import:
```python
from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX, CheckpointDecision
```

2. Add to `__init__`:
```python
self.checkpoint_ux = CheckpointUX()
```

3. When checkpoint triggers (around line 960), instead of just pausing:

```python
if checkpoint_result.requires_approval and not checkpoint_result.approved:
    # Use blocking UX instead of just pausing
    checkpoint = checkpoint_result.checkpoint
    if checkpoint:
        decision = self.checkpoint_ux.prompt_and_wait(checkpoint)

        if decision.chosen_option == "Proceed":
            # Continue with this goal
            pass  # Fall through to execute
        elif decision.chosen_option == "Skip":
            # Mark as skipped, continue to next
            goal.status = GoalStatus.SKIPPED
            continue
        else:  # Pause or other
            checkpoint_pending = True
            session.state = AutopilotState.PAUSED
            break
    else:
        checkpoint_pending = True
        session.state = AutopilotState.PAUSED
        break
```

---

## Verification

After implementation, run:

```bash
# Run all new tests
PYTHONPATH=. pytest tests/chief_of_staff/test_checkpoint_ux.py tests/chief_of_staff/test_level2_recovery.py -v

# Should see:
# 29 passed
```

Then manual test:

```bash
# Test checkpoint UX
PYTHONPATH=. python -c "
from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX, CheckpointDecision
from swarm_attack.chief_of_staff.checkpoints import Checkpoint, CheckpointOption, CheckpointTrigger

ux = CheckpointUX()
checkpoint = Checkpoint(
    checkpoint_id='test',
    trigger=CheckpointTrigger.HICCUP,
    context='Test checkpoint',
    options=[
        CheckpointOption(label='Proceed', description='Continue', is_recommended=True),
        CheckpointOption(label='Skip', description='Skip goal', is_recommended=False),
    ],
    recommendation='Proceed',
    created_at='2025-01-01',
    goal_id='test-goal',
)

print(ux.format_checkpoint(checkpoint))
"
```

---

## File Summary

| File | Action | LOC |
|------|--------|-----|
| `swarm_attack/chief_of_staff/checkpoint_ux.py` | CREATE | ~100 |
| `swarm_attack/chief_of_staff/level2_recovery.py` | CREATE | ~100 |
| `swarm_attack/chief_of_staff/recovery.py` | MODIFY | +50 |
| `swarm_attack/chief_of_staff/autopilot_runner.py` | MODIFY | +30 |
| **TOTAL** | | ~280 |

---

## Success Criteria

1. All 29 tests pass
2. `checkpoint_ux.py` implements blocking interactive prompts
3. `level2_recovery.py` implements LLM-powered recovery decisions
4. `recovery.py` uses Level2Analyzer for systematic errors
5. `autopilot_runner.py` uses CheckpointUX for blocking decisions

---

## What This Enables

After implementation:

```
Goal fails with systematic error
    ↓
Level 2 Analyzer asks LLM: "What should we try?"
    ↓
LLM: "Try async pattern" (ALTERNATIVE)
    ↓
Retry with hint in context
    ↓
Still failing? Try again (max 2 alternatives)
    ↓
Still failing? Create HICCUP checkpoint
    ↓
Blocking UX: "⚠️ HICCUP - Goal failed. [1] Proceed [2] Skip [3] Pause > _"
    ↓
User types "1" → Continues immediately (no manual approve command needed)
```

**This is self-healing Jarvis.**
