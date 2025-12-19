# Auto-Fix Code Errors in Implementation Flow

## Problem

When coder produces code with errors (import errors, syntax errors, type errors), the implementation fails and stops. The Chief of Staff should automatically:

1. Detect the type of code error
2. Route to appropriate recovery agent
3. Fix the issue
4. Continue implementation

## Current Flow (Broken)

```
Coder → Bad imports → Verifier catches → Return failure → STUCK
```

## Desired Flow

```
Coder → Bad imports → ErrorClassifier → RecoveryRouter → FixAgent → Continue
```

## Error Types and Recovery Strategies

| Error Type | Detection | Recovery Agent | Strategy |
|------------|-----------|----------------|----------|
| **Import Error** | `undefined name`, `ImportError`, `ModuleNotFoundError` | FixPlanner + Coder | Add missing imports or fix import paths |
| **Syntax Error** | `SyntaxError`, `IndentationError` | Coder | Rewrite with correct syntax |
| **Type Error** | `TypeError`, type mismatch | RootCauseAnalyzer + Coder | Analyze types, fix signatures |
| **Test Assertion** | `AssertionError`, `failed` | Coder (retry) | Use failure context for retry |
| **Timeout** | `timed out` | IssueSplitter | Split into smaller issues (DONE) |

## Implementation Plan

### Phase 1: Error Classifier

Add `_classify_coder_error()` method to orchestrator:

```python
def _classify_coder_error(self, error_msg: str) -> str:
    """Classify coder error type for routing to recovery."""
    error_lower = error_msg.lower()

    if "timed out" in error_lower:
        return "timeout"

    if any(x in error_lower for x in ["undefined name", "importerror", "modulenotfounderror"]):
        return "import_error"

    if any(x in error_lower for x in ["syntaxerror", "indentationerror"]):
        return "syntax_error"

    if "typeerror" in error_lower:
        return "type_error"

    return "unknown"
```

### Phase 2: Recovery Router

Add `_route_to_recovery()` method:

```python
def _route_to_recovery(
    self,
    error_type: str,
    feature_id: str,
    issue_number: int,
    error_details: str,
    coder_output: dict,
) -> AgentResult:
    """Route error to appropriate recovery agent."""

    if error_type == "timeout":
        return self._handle_timeout_auto_split(...)  # DONE

    if error_type == "import_error":
        return self._handle_import_error(...)  # NEW

    if error_type == "syntax_error":
        return self._handle_syntax_error(...)  # NEW

    if error_type == "type_error":
        return self._handle_type_error(...)  # NEW

    # Unknown errors fall through to retry or block
    return AgentResult.failure_result(f"Unknown error type: {error_type}")
```

### Phase 3: Import Error Handler

```python
def _handle_import_error(
    self,
    feature_id: str,
    issue_number: int,
    error_details: str,
    file_path: str,
) -> AgentResult:
    """
    Handle import errors by analyzing and fixing imports.

    1. Parse error to find undefined names
    2. Search codebase for correct import paths
    3. Generate fix with correct imports
    4. Apply fix and retry
    """
    # Parse undefined names from error
    undefined_names = self._extract_undefined_names(error_details)

    # Search for correct imports
    import_fixes = []
    for name in undefined_names:
        # Use Grep to find where the name is defined
        location = self._find_symbol_definition(name)
        if location:
            import_fixes.append(f"from {location} import {name}")

    # Generate fix prompt
    fix_prompt = f"""
    The following names are undefined: {undefined_names}

    Add these imports to fix:
    {chr(10).join(import_fixes)}
    """

    # Call coder to apply fix
    return self._apply_quick_fix(file_path, fix_prompt)
```

### Phase 4: Integration

Modify `_run_implementation_cycle` to use recovery router:

```python
# Check if it was a coder failure (not verifier)
if verifier_result and not verifier_result.output:
    error_msg = verifier_result.errors[0] if verifier_result.errors else ""

    # Classify error
    error_type = self._classify_coder_error(error_msg)

    # Route to recovery
    if error_type != "unknown":
        recovery_result = self._route_to_recovery(
            error_type=error_type,
            feature_id=feature_id,
            issue_number=issue_number,
            error_details=error_msg,
            coder_output=coder_result.output if coder_result else {},
        )

        if recovery_result.success:
            # Recovery successful, continue
            continue
```

## Files to Modify

| File | Change |
|------|--------|
| `swarm_attack/orchestrator.py` | Add `_classify_coder_error`, `_route_to_recovery`, error handlers |
| `swarm_attack/agents/fix_planner.py` | May need new quick-fix mode |
| `tests/unit/test_auto_recovery.py` | New tests |

## Success Criteria

1. Import errors are automatically fixed without human intervention
2. Syntax errors trigger automatic rewrite
3. Type errors use RootCauseAnalyzer for context
4. All recoveries are logged for visibility
5. Recovery attempts are limited to prevent infinite loops

## Config Option

```python
@dataclass
class SwarmConfig:
    auto_fix_code_errors: bool = True  # Enable auto-recovery for code errors
    max_recovery_attempts: int = 2     # Max attempts before giving up
```

## Testing Plan

1. Create test with intentional import error
2. Verify error is classified correctly
3. Verify recovery agent is called
4. Verify fix is applied
5. Verify implementation continues
