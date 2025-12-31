# Codex Authentication False Positive Fixes - Engineering Spec

## Overview

This spec addresses critical bugs discovered during the COO Orchestration Evaluation that prevent autonomous operation of Swarm Attack. The root cause is false positive Codex authentication errors that block the spec debate pipeline.

## Problem Statement

When running `swarm-attack run <feature>`, the Codex CLI subprocess fails with "CODEX CLI AUTHENTICATION REQUIRED" even though:
- `codex login status` shows "Logged in using ChatGPT"
- `codex exec` works from terminal
- `~/.codex/auth.json` exists with valid tokens

This blocks the entire spec debate pipeline (Author → Critic → Moderator) because SpecCritic uses Codex.

## Root Causes Identified

### RC-1: Subprocess Environment Not Inherited
`codex_client.py:321` uses `subprocess.run()` without explicit `env=` parameter. While subprocess inherits environment by default, shell-specific credential handling may differ.

### RC-2: Overly Broad Auth Pattern
`errors.py:189` uses pattern `r"unauthorized"` which matches the word anywhere in stderr, causing false positives from permission errors, policy violations, etc.

### RC-3: Config Option Not Wired
`config.preflight.check_codex_auth` only affects preflight checks, not runtime error classification in CodexCliRunner.

### RC-4: Missing Stdlib Module
`coder.py:113-132` STDLIB_MODULES is missing `'importlib'`, causing import validation to fail on stdlib imports.

---

## Issues to Implement

### Issue 1: Fix Subprocess Environment Inheritance

**Priority:** P0 - Critical
**Effort:** Small
**Files:** `swarm_attack/codex_client.py`

#### Acceptance Criteria
1. `subprocess.run()` at line 321 explicitly passes `env=os.environ.copy()`
2. Add `import os` if not present
3. All existing tests pass
4. New test verifies environment is passed to subprocess

#### Interface Contract
```python
# In CodexCliRunner.run() method
proc = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    cwd=cwd,
    timeout=timeout_seconds,
    env=os.environ.copy(),  # NEW: Explicit environment
)
```

#### Test Requirements
- Test that `os.environ.copy()` is passed to subprocess
- Mock subprocess.run to verify env parameter
- Verify existing functionality unchanged

---

### Issue 2: Make Auth Patterns More Specific

**Priority:** P0 - Critical
**Effort:** Small
**Files:** `swarm_attack/errors.py`

#### Acceptance Criteria
1. Replace `r"unauthorized"` with more specific pattern `r"(?:^|\s)unauthorized(?:\s|$|:)"` or remove (covered by `r"401\s+Unauthorized"`)
2. Add negative test: stderr containing "unauthorized access denied by policy" should NOT trigger AUTH_REQUIRED
3. Add positive test: stderr containing "401 Unauthorized" still triggers AUTH_REQUIRED
4. Existing auth detection tests pass

#### Interface Contract
```python
CODEX_AUTH_PATTERNS = [
    r"not\s+logged\s+in",
    r"login\s+required",
    r"invalid\s+session",
    r"session\s+expired",
    # REMOVED: r"unauthorized" - too broad, causes false positives
    r"please\s+run\s+`codex\s+login`",
    r"AuthenticationError:",
    r"401\s+Unauthorized",  # Kept - specific HTTP error
    r"Token\s+exchange\s+(?:error|failed)",
]
```

#### Test Requirements
- Negative test: "unauthorized access to resource" → NOT AUTH_REQUIRED
- Negative test: "policy unauthorized module import" → NOT AUTH_REQUIRED
- Positive test: "401 Unauthorized" → AUTH_REQUIRED
- Positive test: "not logged in" → AUTH_REQUIRED
- All existing error classification tests pass

---

### Issue 3: Wire Config to Skip Auth Classification

**Priority:** P1 - High
**Effort:** Medium
**Files:** `swarm_attack/codex_client.py`, `swarm_attack/config.py`

#### Acceptance Criteria
1. `CodexCliRunner.__init__` accepts optional `skip_auth_classification: bool` parameter
2. When `skip_auth_classification=True`, `_classify_and_raise()` treats auth patterns as `CLI_CRASH` instead of `AUTH_REQUIRED`
3. Default behavior unchanged (auth classification enabled)
4. Config option `preflight.check_codex_auth` controls this when passed to runner

#### Interface Contract
```python
@dataclass
class CodexCliRunner:
    config: SwarmConfig
    logger: Optional[SwarmLogger] = None
    checkpoint_callback: Optional[Callable[[], None]] = None
    skip_auth_classification: bool = False  # NEW

    def _classify_and_raise(self, stderr: str, stdout: str, returncode: int) -> None:
        error_type = ErrorClassifier.classify_codex_error(...)

        # NEW: Skip auth classification if configured
        if self.skip_auth_classification and error_type == LLMErrorType.AUTH_REQUIRED:
            error_type = LLMErrorType.CLI_CRASH

        if error_type == LLMErrorType.AUTH_REQUIRED:
            raise CodexAuthError(...)
        # ... rest unchanged
```

#### Test Requirements
- Test `skip_auth_classification=False` (default) raises CodexAuthError on auth pattern
- Test `skip_auth_classification=True` raises CodexInvocationError (CLI_CRASH) on auth pattern
- Test that rate limit and other errors unaffected by flag

---

### Issue 4: Add importlib to STDLIB_MODULES

**Priority:** P1 - High
**Effort:** Small
**Files:** `swarm_attack/agents/coder.py`

#### Acceptance Criteria
1. Add `'importlib'` to `STDLIB_MODULES` frozenset at line 113-132
2. Import validation skips `importlib.util`, `importlib.metadata`, etc.
3. Existing import validation tests pass
4. New test verifies importlib imports are skipped

#### Interface Contract
```python
STDLIB_MODULES = frozenset([
    # ... existing modules ...
    'importlib',  # NEW: Standard library import utilities
    # ... rest of modules ...
])
```

#### Test Requirements
- Test that `from importlib.util import find_spec` is skipped during validation
- Test that `from importlib import resources` is skipped
- Test that project imports still validated (e.g., `from myproject import foo`)

---

### Issue 5: Add Retry Logic to Spec Critic

**Priority:** P2 - Medium
**Effort:** Medium
**Files:** `swarm_attack/orchestrator.py`

#### Acceptance Criteria
1. Wrap critic invocation (lines 802-837) in retry loop
2. Retry up to 2 times on Codex failure before blocking
3. Log each retry attempt with error details
4. Only block feature after all retries exhausted

#### Interface Contract
```python
# In run_spec_pipeline(), around lines 802-837
MAX_CRITIC_RETRIES = 2

for critic_attempt in range(MAX_CRITIC_RETRIES + 1):
    critic_result = self._critic.run(critic_context)

    if critic_result.success:
        break

    if critic_attempt < MAX_CRITIC_RETRIES:
        self._log("critic_retry", {
            "attempt": critic_attempt + 1,
            "max_retries": MAX_CRITIC_RETRIES,
            "error": critic_result.errors,
        }, level="warning")
        continue

    # All retries exhausted
    self._update_phase(feature_id, FeaturePhase.BLOCKED)
    return PipelineResult(status="failure", ...)
```

#### Test Requirements
- Test critic succeeds on first attempt → no retry
- Test critic fails once, succeeds on retry → continues
- Test critic fails all retries → BLOCKED status
- Test retry logging occurs

---

## Implementation Order

1. **Issue 2** (auth patterns) - Highest impact, simplest fix
2. **Issue 1** (subprocess env) - Critical, simple fix
3. **Issue 4** (importlib stdlib) - Independent, simple fix
4. **Issue 3** (config wiring) - Safety valve for future
5. **Issue 5** (retry logic) - Defense in depth

## Testing Strategy

All fixes use TDD:
1. Write failing test that reproduces the bug
2. Implement minimal fix to pass test
3. Verify no regressions in existing tests
4. Run full test suite

## Success Criteria

- `swarm-attack run <feature>` completes spec debate autonomously
- No false positive "CODEX CLI AUTHENTICATION REQUIRED" errors
- All existing tests pass
- New regression tests prevent future occurrences
