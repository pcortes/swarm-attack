# Swarm Self-Healing: Error Classification Integration

## Problem Statement

When the coder agent fails with import errors (e.g., `"undefined name(s): typer/testing.py:CliRunner"`), the swarm immediately returns `status="failed"` instead of attempting recovery. This happens despite having:

1. A fully implemented `_classify_coder_error()` method that recognizes import errors
2. A fully implemented `_extract_undefined_names()` method to parse error details
3. A RecoveryAgent that can analyze failures and generate recovery plans

The infrastructure exists but is **never invoked** - it's dead code.

## Root Cause

In `swarm_attack/orchestrator.py` lines 2946-3009, when coder fails:

```python
# Current (broken) flow:
if self._should_auto_split_on_timeout(coder_fail_result):
    # Handle timeout - ONLY recovery path
else:
    return IssueSessionResult(status="failed", ...)  # ALL other errors die here
```

The `_classify_coder_error()` method at lines 1830-1854 is **never called**.

## Solution Overview

Wire the existing error classification into the failure handling path and add targeted recovery for import errors:

1. **Classify errors** when coder fails (use existing method)
2. **Route by error type** (timeout, import_error, syntax_error, etc.)
3. **Handle import errors** by searching for correct import paths
4. **Retry with context** containing the correct paths
5. **Block with actionable message** if recovery fails

## Detailed Design

### 1. Error Classification Routing

**Location:** `orchestrator.py` lines 2946-3009

```python
# NEW flow:
error_type = self._classify_coder_error(error_msg)

if error_type == "timeout":
    if self._should_auto_split_on_timeout(coder_fail_result):
        return self._handle_timeout_auto_split(...)

elif error_type == "import_error":
    recovery_result = self._handle_import_error_recovery(
        error_msg=error_msg,
        issue=issue,
        attempt=attempt,
        max_retries=max_retries,
        session=session,
    )
    if recovery_result:
        return recovery_result
    # None means "retry with recovery context"

# Fall through to existing failure handling for other types
```

### 2. Import Error Recovery Handler

**New method:** `_handle_import_error_recovery()`

```python
def _handle_import_error_recovery(
    self,
    error_msg: str,
    issue: TaskRef,
    attempt: int,
    max_retries: int,
    session: IssueSession,
) -> Optional[IssueSessionResult]:
    """
    Handle import errors by finding correct import paths and retrying.

    Returns:
        IssueSessionResult if terminal (blocked/failed)
        None if should retry with recovery context
    """
    # 1. Extract undefined names
    undefined_names = self._extract_undefined_names(error_msg)

    if not undefined_names:
        # Can't parse - fall through to normal failure
        return None

    # 2. Search for correct import paths
    correct_paths = self._find_correct_import_paths(undefined_names)

    # 3. Build recovery context
    recovery_hint = self._build_import_recovery_hint(undefined_names, correct_paths)

    # 4. Store recovery context in session for retry
    session.recovery_context = {
        "error_type": "import_error",
        "undefined_names": undefined_names,
        "suggested_imports": correct_paths,
        "recovery_hint": recovery_hint,
    }

    # 5. Check if we should retry
    if attempt < max_retries:
        self._log(
            "import_error_recovery",
            {
                "issue": issue.issue_number,
                "undefined_names": undefined_names,
                "suggested_imports": correct_paths,
                "attempt": attempt,
            },
            level="warning",
        )
        return None  # Signal: retry with recovery context

    # 6. Max retries exhausted - block with actionable message
    return IssueSessionResult(
        status="blocked",
        error=f"Import errors after {attempt} attempts. Missing: {', '.join(undefined_names)}",
        recovery_hint=recovery_hint,
    )
```

### 3. Correct Import Path Finder

**New method:** `_find_correct_import_paths()`

```python
def _find_correct_import_paths(
    self,
    undefined_names: list[str],
) -> dict[str, str]:
    """
    Search the codebase for correct import paths for undefined names.

    Args:
        undefined_names: List of names like ["CliRunner", "chief_of_staff"]

    Returns:
        Dict mapping name to suggested import, e.g.:
        {"CliRunner": "from typer.testing import CliRunner",
         "chief_of_staff": "from swarm_attack.cli.chief_of_staff import app as cos_app"}
    """
    correct_paths = {}

    for name in undefined_names:
        # Strategy 1: Check if it's a known external library
        external = self._check_external_library(name)
        if external:
            correct_paths[name] = external
            continue

        # Strategy 2: Search codebase for class/function definition
        definition = self._search_codebase_for_definition(name)
        if definition:
            correct_paths[name] = definition
            continue

        # Strategy 3: Search for module with similar name
        module = self._search_for_module(name)
        if module:
            correct_paths[name] = module

    return correct_paths
```

### 4. External Library Lookup

**New method:** `_check_external_library()`

```python
# Known external library imports
KNOWN_EXTERNAL_IMPORTS = {
    "CliRunner": "from typer.testing import CliRunner",
    "TestClient": "from fastapi.testclient import TestClient",
    "Mock": "from unittest.mock import Mock",
    "patch": "from unittest.mock import patch",
    "MagicMock": "from unittest.mock import MagicMock",
    "pytest": "import pytest",
    "Path": "from pathlib import Path",
    "Console": "from rich.console import Console",
    # Add more as discovered
}

def _check_external_library(self, name: str) -> Optional[str]:
    """Check if name is a known external library import."""
    return KNOWN_EXTERNAL_IMPORTS.get(name)
```

### 5. Codebase Search for Definitions

**New method:** `_search_codebase_for_definition()`

```python
def _search_codebase_for_definition(self, name: str) -> Optional[str]:
    """
    Search codebase for class or function definition.

    Searches for patterns like:
    - class ClassName:
    - def function_name(
    - ClassName = ...
    """
    import subprocess

    # Search for class definition
    patterns = [
        f"^class {name}\\(",
        f"^class {name}:",
        f"^def {name}\\(",
        f"^{name} = ",
    ]

    for pattern in patterns:
        result = subprocess.run(
            ["rg", "-l", "-e", pattern, "--type", "py", "."],
            capture_output=True,
            text=True,
            cwd=self.project_dir,
        )

        if result.returncode == 0 and result.stdout.strip():
            file_path = result.stdout.strip().split("\n")[0]
            # Convert file path to import
            module = self._file_path_to_module(file_path)
            return f"from {module} import {name}"

    return None
```

### 6. Recovery Context in Retry Loop

**Location:** `_run_implementation_cycle()`

Pass recovery context to coder:

```python
# Build coder context
coder_context = {
    "issue_spec": issue_spec,
    "existing_implementation": existing_impl,
    "test_failures": test_failures,
}

# Add recovery context if present (from previous failed attempt)
if session.recovery_context:
    coder_context["recovery_context"] = session.recovery_context
    coder_context["recovery_hint"] = session.recovery_context.get("recovery_hint", "")
```

### 7. Coder Uses Recovery Context

**Location:** `swarm_attack/agents/coder.py`

In the coder prompt, include recovery hints:

```python
# In build_prompt():
if context.get("recovery_hint"):
    prompt += f"""
## Recovery Context (IMPORTANT - Previous Attempt Failed)

{context['recovery_hint']}

Please use the suggested imports above to fix the import errors from the previous attempt.
"""
```

## Files to Modify

| File | Changes |
|------|---------|
| `swarm_attack/orchestrator.py` | Wire `_classify_coder_error()`, add `_handle_import_error_recovery()`, add `_find_correct_import_paths()` |
| `swarm_attack/agents/coder.py` | Use recovery_hint in prompt |
| `swarm_attack/config.py` | Add `auto_fix_import_errors: bool = True` |
| `tests/unit/test_orchestrator_recovery.py` | TDD tests |

## Acceptance Criteria

1. When coder fails with "undefined name", error is classified as `import_error`
2. Orchestrator searches codebase for correct import paths
3. Coder is retried with recovery context containing correct paths
4. If retry succeeds, issue completes normally
5. If retry fails after max attempts, issue marked `blocked` with actionable message
6. Existing timeout auto-split behavior unchanged
7. All new code has unit tests

## Test Plan

### Unit Tests

```python
# test_orchestrator_recovery.py

def test_classify_coder_error_import():
    """_classify_coder_error returns 'import_error' for undefined names."""
    error = "Incomplete implementation: test file(s) import 2 undefined name(s): foo, bar"
    assert orchestrator._classify_coder_error(error) == "import_error"

def test_extract_undefined_names():
    """_extract_undefined_names parses error message correctly."""
    error = "undefined name(s): typer/testing.py:CliRunner, swarm_attack/cli.py:chief_of_staff"
    names = orchestrator._extract_undefined_names(error)
    assert names == ["CliRunner", "chief_of_staff"]

def test_find_correct_import_paths_external():
    """_find_correct_import_paths finds known external libraries."""
    paths = orchestrator._find_correct_import_paths(["CliRunner"])
    assert paths["CliRunner"] == "from typer.testing import CliRunner"

def test_import_error_triggers_retry():
    """Import error triggers retry with recovery context instead of immediate failure."""
    # Mock coder to fail with import error
    # Verify retry is attempted with recovery_context set

def test_max_retries_blocks_with_message():
    """After max retries, issue is blocked with actionable message."""
    # Mock coder to fail repeatedly
    # Verify status="blocked" with recovery_hint
```

### Integration Tests

```python
def test_import_error_recovery_e2e():
    """End-to-end: coder fails with import error, retry succeeds with hints."""
    # 1. Run issue that will have import error
    # 2. Verify first attempt fails
    # 3. Verify retry happens with recovery context
    # 4. Verify issue completes on retry
```

## Rollout

1. Feature flag: `auto_fix_import_errors` (default: True)
2. Logging: All recovery attempts logged at WARNING level
3. Metrics: Track recovery success rate

## Future Enhancements

1. **RecoveryAgent integration** - For complex errors, invoke full RecoveryAgent analysis
2. **BugOrchestrator escalation** - When recovery fails, optionally create bug investigation
3. **Learning** - Track which import patterns fail and pre-populate KNOWN_EXTERNAL_IMPORTS
