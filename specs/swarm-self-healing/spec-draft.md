# Swarm Self-Healing: RecoveryAgent Integration

## Overview

The swarm now has **general-purpose self-healing** for coder failures. When the coder agent fails with ANY type of error (import errors, syntax errors, type errors, logic errors, etc.), the `RecoveryAgent` is invoked to analyze the failure and determine if automatic recovery is possible.

This replaces the previous approach of hardcoded error handling with a flexible, LLM-powered recovery mechanism.

## How It Works

### Architecture

```
Coder fails (ANY error)
      │
      ▼
RecoveryAgent.run(context)
      │
      ├─ LLM analyzes error
      │
      ▼
Returns {recoverable, recovery_plan, root_cause}
      │
      ├─ recoverable=True  → Retry coder with recovery_plan
      │
      └─ recoverable=False → Fail with human_instructions
```

### Flow in Orchestrator

**File:** `swarm_attack/orchestrator.py` (lines ~3263-3300)

```python
# When coder fails (not timeout):
if attempt < max_retries:
    recovery_result = self._attempt_recovery_with_agent(
        feature_id=feature_id,
        issue_number=issue_number,
        error_msg=error_msg,
        attempt=attempt,
    )

    if recovery_result and recovery_result.get("recoverable"):
        # Store recovery plan for next attempt
        previous_failures.append({
            "type": "recovery_agent_plan",
            "message": recovery_result["recovery_plan"],
            "root_cause": recovery_result["root_cause"],
        })
        # Retry the coder
        continue
```

### RecoveryAgent Context

The RecoveryAgent receives this context:

```python
context = {
    "feature_id": "chief-of-staff-v3",
    "issue_number": 32,
    "failure_type": "coder_error",
    "error_output": "Incomplete implementation: test file(s) import 2 undefined name(s): typer/testing.py:CliRunner, swarm_attack/cli.py:chief_of_staff",
    "retry_count": 1,
}
```

### RecoveryAgent Response

The agent returns analysis via LLM:

```python
{
    "recoverable": True,
    "recovery_plan": "The import errors indicate wrong file paths. Use:\n  from typer.testing import CliRunner\n  from swarm_attack.cli.chief_of_staff import app as cos_app",
    "root_cause": "The test file tried to import from 'swarm_attack/cli.py' but the CLI is actually structured as a package at 'swarm_attack/cli/chief_of_staff.py'",
    "human_instructions": null,
    "suggested_actions": ["Check CLI structure", "Verify import paths"],
    "cost_usd": 0.35
}
```

## LLM Prompt (RecoveryAgent Skill)

**File:** `swarm_attack/agents/skills/recovery.md` (or inline in agent)

```markdown
Analyze this failure and respond with JSON:

## Failure Context

**Feature ID**: {feature_id}
**Issue Number**: {issue_number}
**Failure Type**: {failure_type}
**Retry Count**: {retry_count}

## Error Output
```
{error_output}
```

Respond with:
```json
{
  "root_cause": "description of what went wrong",
  "recoverable": true/false,
  "recovery_plan": "steps to fix (if recoverable) or null",
  "human_instructions": "what human should do (if not recoverable) or null",
  "suggested_actions": ["list", "of", "helpful", "actions"],
  "escalation_reason": "why this needs human help (if applicable) or null"
}
```

Consider:
- Is this a simple fix (wrong import, typo, missing dependency)?
- Or a fundamental issue (architecture mismatch, missing feature)?
- Can it be fixed by retrying with better instructions?
- If recoverable, provide SPECIFIC fix instructions
```

## Key Components

### 1. RecoveryAgent (`swarm_attack/agents/recovery.py`)

The existing RecoveryAgent that was previously unused. Now wired into the orchestrator.

Key methods:
- `run(context)` - Main entry point, validates context, invokes LLM
- `_analyze_failure_with_llm()` - Builds prompt, calls LLM, parses response
- `_determine_recoverability()` - Checks if retry is possible

### 2. Orchestrator Integration (`swarm_attack/orchestrator.py`)

New method: `_attempt_recovery_with_agent()`

```python
def _attempt_recovery_with_agent(
    self,
    feature_id: str,
    issue_number: int,
    error_msg: str,
    attempt: int,
) -> Optional[dict[str, Any]]:
    """
    Use RecoveryAgent to analyze coder failure and determine recovery.

    Returns dict with:
        - recoverable: bool
        - recovery_plan: str (fix instructions)
        - root_cause: str
        - cost_usd: float
    """
```

### 3. Config Option (`swarm_attack/config.py`)

```python
auto_fix_import_errors: bool = True  # Enable self-healing
```

### 4. Known External Imports (`swarm_attack/orchestrator.py`)

Fast-path for common imports (no LLM call needed):

```python
KNOWN_EXTERNAL_IMPORTS = {
    "CliRunner": "from typer.testing import CliRunner",
    "Mock": "from unittest.mock import Mock",
    "Path": "from pathlib import Path",
    # ... many more
}
```

## Quick Start: Using Self-Healing

### 1. Self-healing is ON by default

No configuration needed. When coder fails, RecoveryAgent is automatically invoked.

### 2. Monitoring Self-Healing

Check logs for recovery attempts:
```bash
# Look for recovery agent events
grep "recovery_agent" .swarm/logs/chief-of-staff-v3.log
```

Events logged:
- `recovery_agent_invoked` - Agent called
- `recovery_agent_complete` - Analysis done
- `recovery_agent_retry` - Retrying with plan
- `recovery_agent_failed` - Agent itself failed

### 3. Viewing Recovery Plans

When swarm retries after recovery:
```
[WARNING] recovery_agent_retry: {
  "feature_id": "chief-of-staff-v3",
  "issue_number": 32,
  "retry": 2,
  "recovery_plan": "Use correct import: from swarm_attack.cli.chief_of_staff import ...",
  "root_cause": "Wrong file path in import"
}
```

### 4. Disabling Self-Healing (if needed)

```yaml
# swarm-config.yaml
auto_fix_import_errors: false
```

## Error Types Handled

| Error Type | Example | Self-Healing Action |
|------------|---------|---------------------|
| Import Error | `undefined name: CliRunner` | LLM suggests correct import |
| Syntax Error | `SyntaxError: invalid syntax` | LLM identifies fix location |
| Type Error | `TypeError: expected str` | LLM suggests type fix |
| Logic Error | `AssertionError: test failed` | LLM analyzes test failure |
| Timeout | `Claude timed out after 300s` | Auto-split (separate mechanism) |

## Decision Flow

```
Coder Fails
    │
    ├─ Is it a timeout?
    │   └─ YES → Auto-split issue (existing mechanism)
    │
    └─ NO → Invoke RecoveryAgent
            │
            ├─ Agent analyzes error via LLM
            │
            ├─ recoverable=True?
            │   ├─ YES → Retry with recovery_plan
            │   │         └─ Coder gets: "Fix instructions: {recovery_plan}"
            │   │
            │   └─ NO → Fail with human_instructions
            │           └─ User sees: "Needs manual fix: {human_instructions}"
            │
            └─ Agent itself failed?
                └─ Fall through to normal failure handling
```

## Cost

Self-healing adds one LLM call per failed coder attempt:
- Typical cost: ~$0.30-0.50 per recovery analysis
- Only invoked when coder fails (not on success)
- Cached knowledge in KNOWN_EXTERNAL_IMPORTS avoids LLM for common issues

## Testing

Run the self-healing tests:
```bash
PYTHONPATH=. pytest tests/unit/test_error_classification_routing.py -v
```

Key test classes:
- `TestAttemptRecoveryWithAgent` - Tests the new recovery method
- `TestClassifyCoderError` - Tests error classification
- `TestErrorRoutingIntegration` - Tests full flow

## Example: Import Error Recovery

**Before (swarm got stuck):**
```
Coder failed: undefined name(s): CliRunner
Status: FAILED
Action: Manual intervention required
```

**After (self-healing):**
```
Coder failed: undefined name(s): CliRunner
RecoveryAgent: Analyzing failure...
RecoveryAgent: recoverable=True, root_cause="Wrong import path"
RecoveryAgent: recovery_plan="Use: from typer.testing import CliRunner"
Retrying coder with recovery context...
Coder succeeded on retry #2
Status: DONE
```

## Future Enhancements

1. **Persistent Learning** - Store successful recovery plans for future reference
2. **Pattern Recognition** - Detect recurring errors and pre-empt them
3. **BugOrchestrator Escalation** - For complex failures, invoke full bug investigation
4. **Cost Optimization** - Skip LLM for known error patterns
