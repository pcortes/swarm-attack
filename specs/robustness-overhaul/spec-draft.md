# Swarm Attack Robustness Overhaul Spec

## 1. Executive Summary

This spec addresses 19 bugs discovered during bug bash testing, ranging from critical security vulnerabilities (path traversal, shell injection vectors) to test infrastructure failures (27 collection errors) to UX inconsistencies. Rather than fixing bugs individually, this spec establishes systemic remediation through four architectural changes: a centralized input validation layer, test infrastructure overhaul, CLI robustness patterns, and state lifecycle management.

The root causes cluster into three categories: (1) scattered/absent input validation allowing malicious or malformed data to flow into the system, (2) naming collisions in test infrastructure causing pytest failures, and (3) missing lifecycle management causing stale state accumulation. These are design flaws, not implementation bugs—fixing individual symptoms would leave the underlying patterns intact.

The fix plan is sequenced in three phases: Foundation (validation layer, test renames), Hardening (CLI robustness, state schemas), and Polish (cleanup jobs, monitoring). Each phase builds on the previous and can be validated independently.

## 2. Design Principles

1. **P1: Defense in Depth** - All user input passes through validation at CLI boundary AND domain boundary using a shared validator
2. **P2: Allowlist Patterns** - Identifiers must match positive patterns, not just exclude bad characters
3. **P3: Fail Loudly** - Invalid input produces clear, actionable error messages with code, expected, got, and hint
4. **P4: Globally Unique Test Names** - Test files include feature name: `test_{feature}_{issue}.py`
5. **P5: Package Isolation** - Each test directory is a proper Python package with `__init__.py`
6. **P6: No Production `Test*` Classes** - Production code never uses `Test` prefix (rename to `Suite*`, `*Handler`, etc.)
7. **P7: Non-Interactive by Default** - CLI works without tty; use `--interactive` to opt into prompts
8. **P8: Consistent Error Formatting** - All errors use structured format with code, message, expected, got, hint
9. **P9: Semantic Exit Codes** - 0=success, 1=user error, 2=system error, 3=blocked
10. **P10: Immutable Events, Schema-Validated State** - Events are append-only; state mutations validate invariants
11. **P11: State Lifecycle Management** - All state has timestamps and optional TTL; cleanup jobs remove expired state
12. **P12: Schema-First Persistence** - All persisted data has a typed schema; loading rejects malformed data

## 3. Architecture Changes

### 3.1 Input Validation Layer

**Location:** `swarm_attack/validation/input_validator.py` (NEW)

**Interface:**

```python
class ValidationError:
    code: str           # e.g., "PATH_TRAVERSAL", "EMPTY_ID"
    message: str        # Human-readable description
    expected: str       # What format was expected
    got: str           # What was actually received
    hint: Optional[str] # How to fix

class InputValidator:
    @classmethod
    def validate_feature_id(cls, value: str) -> str | ValidationError

    @classmethod
    def validate_bug_id(cls, value: str) -> str | ValidationError

    @classmethod
    def validate_positive_int(cls, value: int, name: str, max_val: int = 10000) -> int | ValidationError

    @classmethod
    def validate_positive_float(cls, value: float, name: str, max_val: float = 1000.0) -> float | ValidationError

    @classmethod
    def validate_path_in_project(cls, path: Path, project_root: Path) -> Path | ValidationError

    @classmethod
    def validate_discovery_type(cls, value: str, valid_types: list[str]) -> str | ValidationError
```

**Validation Rules:**

| Input Type | Pattern | Max Length | Additional Checks |
|------------|---------|------------|-------------------|
| feature_id | `^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$\|^[a-z0-9]$` | 64 | No `..`, `/`, `\`, `$`, backticks |
| bug_id | `^[a-z0-9][a-z0-9-_]{0,62}[a-z0-9]$\|^[a-z0-9]$` | 64 | No path components |
| issue_number | integer | - | ≥1, ≤99999 |
| budget | float | - | >0, ≤1000 |
| duration | string | - | matches `^\d+(h\|m\|min)?$`, parsed value >0 |
| path | Path | - | resolves within project root |

**Edge Cases Handled:**
- Empty strings → `EMPTY_ID` error
- Unicode → rejected (ASCII alphanumeric only)
- Leading/trailing hyphens → `INVALID_FORMAT` error
- Shell metacharacters (`$()`, backticks, `|`, `&`, `;`) → `UNSAFE_CHARS` error
- Path traversal (`..`) → `PATH_TRAVERSAL` error
- Whitespace → `INVALID_FORMAT` error

### 3.2 Test Infrastructure Overhaul

**Naming Convention:**

```
tests/generated/{feature}/test_{feature_slug}_issue_{N}.py
```

Where `feature_slug` is the feature name with hyphens replaced by underscores.

**Examples:**
- `tests/generated/chief-of-staff/test_chief_of_staff_issue_1.py`
- `tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_1.py`
- `tests/generated/external-dashboard/test_external_dashboard_issue_1.py`

**Directory Structure:**

```
tests/
├── generated/
│   ├── chief-of-staff/
│   │   ├── __init__.py              # NEW - package marker
│   │   ├── test_chief_of_staff_issue_1.py
│   │   └── ...
│   ├── chief-of-staff-v2/
│   │   ├── __init__.py              # NEW
│   │   ├── test_chief_of_staff_v2_issue_1.py
│   │   └── ...
│   └── ...
└── ...
```

**Production Class Renames:**

| Old Name | New Name | File |
|----------|----------|------|
| `TestFailureError` | `FailureError` | `swarm_attack/edge_cases.py` |
| `TestFailureHandler` | `FailureHandler` | `swarm_attack/edge_cases.py` |
| `TestRunnerConfig` | `RunnerConfig` | `swarm_attack/config.py` |
| `TestState` | `SuiteState` | `swarm_attack/chief_of_staff/state_gatherer.py` |
| `TestRunner` | `SuiteRunner` | `swarm_attack/recovery.py` |
| `TestRunResult` | `SuiteRunResult` | `swarm_attack/recovery.py` |
| `TestFailureDiscoveryAgent` | `FailureDiscoveryAgent` | `swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py` |
| `TestCase` | `BugTestCase` | `swarm_attack/bug_models.py` |
| `TestValidationGate` | `SuiteValidationGate` | `swarm_attack/chief_of_staff/validation_gates.py` |
| `TestCritic` | `SuiteCritic` | `swarm_attack/chief_of_staff/critics.py` |

**Isolation Guarantees:**
- Each feature's tests can run independently: `pytest tests/generated/chief-of-staff/`
- No module name collisions due to `__init__.py` packages
- Test discovery uses explicit imports, not module-level caching

### 3.3 State Machine Hardening

**Invariants:**

1. **Bug state invariant:** `bug.description` must be non-empty
2. **Event invariant:** `event.issue` must be ≥1 or None
3. **Feature state invariant:** `feature.phase` must be a valid enum value
4. **Checkpoint invariant:** `checkpoint.created_at` must be a valid ISO timestamp

**Transition Validation:**

Before any state mutation, check:
1. Current state is valid (schema conforms)
2. Transition is allowed (state machine rules)
3. New state will be valid (pre-validate)

**Schema Validation:**

Location: `swarm_attack/state/schemas.py` (NEW)

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SwarmEvent:
    """Schema for swarm events."""
    ts: str
    event: str
    feature_id: str
    issue: Optional[int] = None

    def __post_init__(self):
        if not self.ts:
            raise ValueError("Event timestamp required")
        if not self.event:
            raise ValueError("Event type required")
        if self.issue is not None and self.issue < 1:
            raise ValueError(f"Invalid issue number: {self.issue}")

@dataclass
class LifecycleMetadata:
    """Lifecycle tracking for persisted state."""
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None
```

**Recovery Procedures:**
1. Stale state detected → log warning, refresh from source
2. Malformed state loaded → log error, reject with specific field errors
3. Missing required field → reject with schema violation

### 3.4 CLI Robustness

**Non-Interactive Mode:**

Location: `swarm_attack/cli/ux.py` (NEW)

```python
def is_interactive() -> bool:
    """Check if running in interactive mode."""
    return sys.stdin.isatty() and sys.stdout.isatty()

def prompt_or_default(prompt: str, default: Any, require_interactive: bool = False) -> Any:
    """Prompt if interactive, else use default."""
    if is_interactive():
        return typer.prompt(prompt, default=default)
    elif require_interactive:
        raise typer.Exit(code=EXIT_USER_ERROR)
    return default
```

**Error Formatting Standard:**

```
Error: [ERROR_CODE] Description
  Expected: <what was expected>
  Got: <what was received>
  Hint: <how to fix>
```

**Exit Codes:**

| Code | Meaning | Examples |
|------|---------|----------|
| 0 | Success | Command completed |
| 1 | User error | Invalid input, missing file, bad arguments |
| 2 | System error | API failure, timeout, internal error |
| 3 | Blocked | Needs human intervention, checkpoint pending |

**Graceful Degradation Policy:**
- Missing optional dependencies → warn and continue with reduced functionality
- API rate limits → exponential backoff with max 3 retries
- Timeout → save partial state, report progress made

## 4. Implementation Plan

### Phase 1: Foundation (Must Do First)

| Task | Files | Bugs Fixed | Tests Added |
|------|-------|------------|-------------|
| Create `InputValidator` class | `swarm_attack/validation/input_validator.py` (NEW) | #1, #3, #4, #8 | `tests/validation/test_input_validator.py` |
| Wire validation to CLI arguments | `swarm_attack/cli/feature.py`, `bug.py`, `chief_of_staff.py` | #1, #3, #4, #8, #9 | Integration tests |
| Add `__init__.py` to test directories | `tests/generated/*/__init__.py` (NEW) | #5 | N/A |
| Rename test files | `tests/generated/**/*.py` | #5 | Migration verification |
| Rename `Test*` production classes | 10 files listed above | #14 | Existing tests still pass |

**Validation Criteria:**
- [ ] `pytest --collect-only` reports 0 errors
- [ ] `swarm-attack init "../../../../etc/passwd"` fails with `PATH_TRAVERSAL` error
- [ ] `swarm-attack init ""` fails with `EMPTY_ID` error
- [ ] `swarm-attack cos autopilot --budget -10` fails with `NOT_POSITIVE` error

### Phase 2: Hardening

| Task | Files | Bugs Fixed | Tests Added |
|------|-------|------------|-------------|
| Add CLI UX utilities | `swarm_attack/cli/ux.py` (NEW) | #10 | `tests/cli/test_ux.py` |
| Replace `typer.prompt()` with `prompt_or_default()` | `swarm_attack/cli/chief_of_staff.py` | #10 | Non-interactive mode tests |
| Add event schema validation | `swarm_attack/event_logger.py` | #9 | `tests/test_event_logger.py` |
| Add discovery type validation | `swarm_attack/cli/chief_of_staff.py` | #11 | Validation tests |
| Fix diagnose health logic | `swarm_attack/cli/admin.py` | #13 | Health check tests |
| Add missing methods | Files referencing `_check_duplicate_classes`, `BACKOFF_SECONDS` | #7 | Unit tests |

**Validation Criteria:**
- [ ] `echo "" | swarm-attack cos standup` uses defaults (no crash)
- [ ] `swarm-attack cos discover --type invalid` returns error
- [ ] `swarm-attack diagnose` shows "unhealthy" when stuck features exist
- [ ] All 42 failing tests pass

### Phase 3: Polish

| Task | Files | Bugs Fixed | Tests Added |
|------|-------|------------|-------------|
| Add checkpoint cleanup job | `swarm_attack/chief_of_staff/checkpoints.py` | #15 | Cleanup tests |
| Add state lifecycle metadata | `swarm_attack/state/lifecycle.py` (NEW) | #19 | Lifecycle tests |
| Add zero budget warning | `swarm_attack/cli/chief_of_staff.py` | #16 | Edge case tests |
| Fix asyncio deprecation | Affected async code | #17 | N/A |
| Fix empty highlights | `swarm_attack/cli/display.py` | #18 | Display tests |
| Add progress refresh | `swarm_attack/chief_of_staff/progress.py` | #19 | Staleness tests |

**Validation Criteria:**
- [ ] Checkpoints older than 7 days are cleaned up on startup
- [ ] Progress shows "stale" indicator after 5 minutes
- [ ] `--budget 0` shows warning but proceeds

## 5. Edge Cases Handled Proactively

Beyond the 19 bugs found, we address these edge cases proactively:

1. **Unicode in identifiers** - Rejected explicitly (ASCII only)
2. **Very long identifiers** - Capped at 64 characters
3. **Concurrent state writes** - File locking or atomic rename
4. **Corrupted JSON state files** - Schema validation on load, reject with specific errors
5. **Disk full on state write** - Catch and report clearly
6. **Test file grows too large** - Warn at 1000 lines, fail at 5000
7. **Circular feature dependencies** - Detect and reject at issue creation
8. **Orphaned lock files** - Cleanup on startup with TTL check
9. **API key in input** - Detect and reject strings matching `sk-*` pattern
10. **Symlinks in paths** - Resolve and verify still in project

## 6. Validation Criteria

- [ ] All 19 bugs verified fixed
- [ ] Zero test collection errors (`pytest --collect-only`)
- [ ] 100% test pass rate (`pytest tests/`)
- [ ] No pytest warnings about production classes
- [ ] All CLI commands work non-interactively (in CI)
- [ ] Fuzzing input validation passes 10,000 random inputs
- [ ] No new security warnings from static analysis (bandit, semgrep)
- [ ] State schema validation catches all malformed inputs

## 7. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test rename breaks local branches | Medium | Medium | Provide migration script; document in CHANGELOG |
| Class renames break external imports | Low | High | These are internal classes; grep for external usage first |
| Non-interactive mode changes behavior | Medium | Low | Preserve all current defaults; only affect edge cases |
| Schema validation too strict | Low | Medium | Log warnings before rejecting; add migration path for old data |
| Performance overhead from validation | Low | Low | Validation is O(1) string checks; negligible vs LLM calls |
| Cleanup job deletes wanted state | Low | High | Only delete if `expires_at` set AND passed; never auto-expire important state |

## 8. Future Considerations

Not in scope for this spec, but should be addressed:

1. **Rate limiting on LLM calls** - Add token bucket per feature
2. **Cost alerts** - Warn at 50%, 80%, 100% of budget
3. **Audit log** - Append-only log of all state mutations
4. **Snapshot/restore** - Ability to rollback state to previous point
5. **Test parallelization** - pytest-xdist configuration for generated tests

---

*Spec authored by: Alex, Maya, Jordan, Sam (Panel of 4 Engineers)*
*Date: 2025-12-20*
