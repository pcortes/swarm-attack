# Timeout-Triggered Auto-Split

## Problem

When an issue is estimated as "small" by the ComplexityGate but the coder times out during implementation, the system currently:
1. Returns a failure
2. May retry (which also times out)
3. Eventually blocks the issue

This happened with issue #24 (chief-of-staff-v3) which was marked "small" but timed out 3 times because it actually required implementing 7 CLI commands.

## Root Cause

The ComplexityGate estimates turns based on:
```python
estimated_turns = 5 + criteria_count + int(method_count * 1.5)
needs_split = estimated_turns > MAX_ESTIMATED_TURNS  # 20
```

But this heuristic doesn't account for:
- Nested/complex acceptance criteria
- CLI commands requiring extensive file reading
- Issues that look simple but have hidden complexity

## Solution

When coder times out, automatically trigger IssueSplitter:

```
[Coder Timeout] → [IssueSplitter] → [Create Sub-Issues] → [Continue]
```

## Implementation

### 1. Detect Timeout in Orchestrator

In `swarm_attack/orchestrator.py`, detect `ClaudeTimeoutError`:

```python
# In _implement_issue or _run_coder_agent
except ClaudeTimeoutError as e:
    self._log("coder_timeout_detected", {
        "feature_id": feature_id,
        "issue_number": issue_number,
        "timeout_seconds": self.config.claude.timeout_seconds,
    }, level="warning")

    # Auto-split on timeout
    return self._handle_timeout_auto_split(
        feature_id=feature_id,
        issue_number=issue_number,
        issue_data=issue_data,
    )
```

### 2. Handle Timeout Auto-Split

New method in orchestrator:

```python
def _handle_timeout_auto_split(
    self,
    feature_id: str,
    issue_number: int,
    issue_data: dict,
) -> tuple[bool, Optional[str], AgentResult, float]:
    """
    Handle timeout by auto-splitting the issue.

    When coder times out, it indicates the issue is more complex than estimated.
    Trigger IssueSplitter to break it into smaller pieces.
    """
    self._log("timeout_auto_split_started", {
        "feature_id": feature_id,
        "issue_number": issue_number,
    })

    # Create synthetic gate estimate with needs_split=True
    from swarm_attack.agents.complexity_gate import ComplexityEstimate
    gate_estimate = ComplexityEstimate(
        estimated_turns=30,  # Clearly over limit
        complexity_score=0.9,
        needs_split=True,
        split_suggestions=[
            "Issue timed out - actual complexity exceeds estimate",
            "Split into smaller, focused sub-issues",
        ],
        confidence=0.95,
        reasoning="Coder timeout triggered auto-split",
    )

    # Use existing _auto_split_issue method
    split_result = self._auto_split_issue(
        feature_id=feature_id,
        issue_number=issue_number,
        issue_data=issue_data,
        gate_estimate=gate_estimate,
    )

    if split_result.success:
        self._log("timeout_auto_split_success", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "sub_issues_count": split_result.output.get("count", 0),
        })
        return (
            True,
            None,
            AgentResult.success_result(
                output={
                    "action": "split",
                    "reason": "timeout_auto_split",
                    "sub_issues": split_result.output.get("sub_issues", []),
                    "count": split_result.output.get("count", 0),
                },
                cost_usd=split_result.cost_usd,
            ),
            split_result.cost_usd,
        )
    else:
        self._log("timeout_auto_split_failed", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "error": split_result.error,
        }, level="error")
        return (
            False,
            None,
            AgentResult.failure_result(
                f"Issue timed out and auto-split failed: {split_result.error}. "
                "Manual intervention required."
            ),
            split_result.cost_usd,
        )
```

### 3. Integration Point

The timeout handling should be integrated in the `_run_single_issue_implementation` method where `ClaudeTimeoutError` is caught.

Current flow:
```python
except ClaudeTimeoutError as e:
    error = f"Claude timed out: {e}"
    self._log("coder_timeout", {"error": error})
    return (False, commit_sha, AgentResult.failure_result(error), total_cost)
```

New flow:
```python
except ClaudeTimeoutError as e:
    # Check if auto-split is enabled and we have issue data
    if self.config.auto_split_on_timeout and issue_data:
        return self._handle_timeout_auto_split(feature_id, issue_number, issue_data)

    # Fallback to regular timeout error
    error = f"Claude timed out: {e}"
    self._log("coder_timeout", {"error": error})
    return (False, commit_sha, AgentResult.failure_result(error), total_cost)
```

### 4. Config Option

Add to `swarm_attack/config.py`:

```python
@dataclass
class SwarmConfig:
    # ... existing fields ...
    auto_split_on_timeout: bool = True  # Auto-split when coder times out
```

## Acceptance Criteria

- [ ] When coder times out, IssueSplitter is automatically triggered
- [ ] Sub-issues are created with proper dependencies
- [ ] Parent issue is marked as SPLIT
- [ ] Implementation continues with child issues
- [ ] Config flag allows disabling auto-split behavior
- [ ] Events are logged for timeout and split actions
- [ ] Unit tests for timeout detection and split triggering

## Files to Modify

| File | Change |
|------|--------|
| `swarm_attack/orchestrator.py` | Add `_handle_timeout_auto_split`, modify timeout handling |
| `swarm_attack/config.py` | Add `auto_split_on_timeout` config option |
| `tests/unit/test_orchestrator.py` | Add tests for timeout auto-split |

## Notes

- This is a safety net for when heuristic estimation fails
- Does NOT replace ComplexityGate - that still runs first
- Only triggers on timeout, not other errors
- Preserves retry behavior for non-timeout failures
