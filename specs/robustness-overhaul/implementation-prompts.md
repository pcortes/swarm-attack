# Implementation Prompts for Robustness Overhaul

These prompts are designed to be executed by specialized LLM agents. Each prompt is self-contained with full context.

---

## Team 1: Input Validation Layer

```
You are a security-focused engineer implementing a centralized input validation layer for Swarm Attack, an autonomous AI-powered multi-agent development system.

## Context

Bug bash testing revealed critical input validation failures:
- Path traversal: `swarm-attack init "../../../../etc/passwd"` escapes project directory
- Empty feature names accepted, creating `.md` and `.json` files with empty names
- Shell metacharacters like `$(whoami)` stored literally as feature names
- Negative values accepted for `--budget -10`, `--duration -60`, `--issue -1`

The root cause: validation is scattered across CLI commands with inconsistent enforcement.

## Your Task

Create a centralized `InputValidator` class and wire it to all CLI entry points.

## Files to Create

### 1. `swarm_attack/validation/__init__.py`
```python
"""Centralized input validation."""
from .input_validator import InputValidator, ValidationError

__all__ = ["InputValidator", "ValidationError"]
```

### 2. `swarm_attack/validation/input_validator.py`

Implement this interface:

```python
from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path
import re

@dataclass
class ValidationError:
    """Structured validation error for consistent CLI output."""
    code: str           # e.g., "PATH_TRAVERSAL", "EMPTY_ID", "NOT_POSITIVE"
    message: str        # Human-readable description
    expected: str       # What format was expected
    got: str           # What was actually received
    hint: Optional[str] = None  # How to fix

class InputValidator:
    """Validates all user-facing inputs with security-first approach."""

    # Allowlist pattern for identifiers (lowercase alphanumeric with hyphens)
    IDENTIFIER_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$')

    # Characters that could enable shell injection
    UNSAFE_CHARS = re.compile(r'[$`|;&<>(){}[\]!#*?~]')

    @classmethod
    def validate_feature_id(cls, value: str) -> Union[str, ValidationError]:
        """Validate feature ID format and safety.

        Rules:
        - Non-empty
        - Max 64 characters
        - Matches IDENTIFIER_PATTERN
        - No path traversal (.., /, \)
        - No shell metacharacters
        """
        pass  # Implement

    @classmethod
    def validate_bug_id(cls, value: Optional[str]) -> Union[Optional[str], ValidationError]:
        """Validate bug ID format if provided.

        Same rules as feature_id, but allows None.
        Also allows underscores in addition to hyphens.
        """
        pass  # Implement

    @classmethod
    def validate_positive_int(cls, value: int, name: str, max_val: int = 99999) -> Union[int, ValidationError]:
        """Validate positive integer parameter.

        Rules:
        - Must be >= 1
        - Must be <= max_val
        """
        pass  # Implement

    @classmethod
    def validate_positive_float(cls, value: float, name: str, max_val: float = 1000.0) -> Union[float, ValidationError]:
        """Validate positive float parameter.

        Rules:
        - Must be > 0
        - Must be <= max_val
        """
        pass  # Implement

    @classmethod
    def validate_path_in_project(cls, path: Path, project_root: Path) -> Union[Path, ValidationError]:
        """Validate path doesn't escape project directory.

        Rules:
        - Resolve to absolute path
        - Must be within project_root after resolution
        - No symlink escape
        """
        pass  # Implement

    @classmethod
    def validate_enum_value(cls, value: str, valid_values: list[str], name: str) -> Union[str, ValidationError]:
        """Validate value is one of allowed enum values.

        Case-insensitive comparison, returns lowercase.
        """
        pass  # Implement
```

### 3. `tests/validation/test_input_validator.py`

Write comprehensive tests:

```python
import pytest
from pathlib import Path
from swarm_attack.validation import InputValidator, ValidationError

class TestValidateFeatureId:
    """Tests for feature ID validation."""

    def test_valid_simple_id(self):
        """Accept simple lowercase alphanumeric."""
        assert InputValidator.validate_feature_id("myfeature") == "myfeature"

    def test_valid_with_hyphens(self):
        """Accept hyphens in middle."""
        assert InputValidator.validate_feature_id("my-feature-v2") == "my-feature-v2"

    def test_valid_single_char(self):
        """Accept single character."""
        assert InputValidator.validate_feature_id("a") == "a"

    def test_reject_empty(self):
        """Reject empty string."""
        result = InputValidator.validate_feature_id("")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_reject_path_traversal(self):
        """Reject path traversal attempts."""
        result = InputValidator.validate_feature_id("../../../etc/passwd")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_reject_shell_metachar_dollar(self):
        """Reject shell metacharacters."""
        result = InputValidator.validate_feature_id("$(whoami)")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_reject_shell_metachar_backtick(self):
        """Reject backtick command substitution."""
        result = InputValidator.validate_feature_id("`id`")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_reject_leading_hyphen(self):
        """Reject leading hyphen."""
        result = InputValidator.validate_feature_id("-feature")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_reject_trailing_hyphen(self):
        """Reject trailing hyphen."""
        result = InputValidator.validate_feature_id("feature-")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_reject_uppercase(self):
        """Reject uppercase letters."""
        result = InputValidator.validate_feature_id("MyFeature")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_reject_too_long(self):
        """Reject IDs over 64 characters."""
        result = InputValidator.validate_feature_id("a" * 65)
        assert isinstance(result, ValidationError)
        assert result.code == "ID_TOO_LONG"

    def test_reject_slashes(self):
        """Reject forward and back slashes."""
        for char in ["/", "\\"]:
            result = InputValidator.validate_feature_id(f"my{char}feature")
            assert isinstance(result, ValidationError)
            assert result.code == "PATH_TRAVERSAL"


class TestValidatePositiveInt:
    """Tests for positive integer validation."""

    def test_valid_positive(self):
        """Accept positive integers."""
        assert InputValidator.validate_positive_int(1, "issue") == 1
        assert InputValidator.validate_positive_int(100, "issue") == 100

    def test_reject_zero(self):
        """Reject zero."""
        result = InputValidator.validate_positive_int(0, "issue")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_negative(self):
        """Reject negative numbers."""
        result = InputValidator.validate_positive_int(-1, "issue")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_too_large(self):
        """Reject numbers over max."""
        result = InputValidator.validate_positive_int(100001, "issue", max_val=100000)
        assert isinstance(result, ValidationError)
        assert result.code == "TOO_LARGE"


class TestValidatePositiveFloat:
    """Tests for positive float validation."""

    def test_valid_positive(self):
        """Accept positive floats."""
        assert InputValidator.validate_positive_float(0.01, "budget") == 0.01
        assert InputValidator.validate_positive_float(100.0, "budget") == 100.0

    def test_reject_zero(self):
        """Reject zero."""
        result = InputValidator.validate_positive_float(0.0, "budget")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_negative(self):
        """Reject negative numbers."""
        result = InputValidator.validate_positive_float(-10.0, "budget")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"


class TestValidatePathInProject:
    """Tests for path containment validation."""

    def test_valid_relative_path(self, tmp_path):
        """Accept paths within project."""
        project = tmp_path / "project"
        project.mkdir()
        subdir = project / "src"
        subdir.mkdir()

        result = InputValidator.validate_path_in_project(subdir, project)
        assert result == subdir.resolve()

    def test_reject_path_escape(self, tmp_path):
        """Reject paths that escape project."""
        project = tmp_path / "project"
        project.mkdir()
        escape_path = tmp_path / "outside"

        result = InputValidator.validate_path_in_project(escape_path, project)
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_ESCAPE"

    def test_reject_traversal_escape(self, tmp_path):
        """Reject traversal that escapes project."""
        project = tmp_path / "project"
        project.mkdir()
        traversal = project / ".." / ".." / "etc" / "passwd"

        result = InputValidator.validate_path_in_project(traversal, project)
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_ESCAPE"
```

## Files to Modify

### 4. Update `swarm_attack/cli/feature.py`

Replace the existing `_validate_feature_id` function with a wrapper that uses InputValidator:

```python
from swarm_attack.validation import InputValidator, ValidationError

def _validate_feature_id(value: str) -> str:
    """Validate feature ID using centralized validator."""
    result = InputValidator.validate_feature_id(value)
    if isinstance(result, ValidationError):
        raise typer.BadParameter(
            f"{result.message}\n"
            f"  Expected: {result.expected}\n"
            f"  Got: {result.got}" +
            (f"\n  Hint: {result.hint}" if result.hint else "")
        )
    return result
```

### 5. Update `swarm_attack/cli/bug.py`

Same pattern - replace `_validate_bug_id` and `_validate_bug_description` with InputValidator calls.

### 6. Update `swarm_attack/cli/chief_of_staff.py`

Replace `_validate_positive_float`, `_validate_duration`, `_validate_discovery_type` with InputValidator calls.

## Acceptance Criteria

Run these commands and verify the expected behavior:

```bash
# Should fail with PATH_TRAVERSAL error
swarm-attack init "../../../../etc/passwd"

# Should fail with EMPTY_ID error
swarm-attack init ""

# Should fail with UNSAFE_CHARS error
swarm-attack init '$(whoami)'

# Should fail with NOT_POSITIVE error
swarm-attack cos autopilot --budget -10

# Should fail with NOT_POSITIVE error
swarm-attack run test-feature --issue -1

# Should succeed
swarm-attack init "valid-feature-name"

# All tests pass
pytest tests/validation/ -v
```

## Constraints

- Do not modify any business logic
- Validation must be pure functions with no side effects
- All error messages must include expected format and example
- Must handle Unicode by rejecting it (ASCII alphanumeric only)
```

---

## Team 2: Test Infrastructure Overhaul

```
You are a testing infrastructure engineer fixing pytest collection errors and warnings in Swarm Attack.

## Context

Bug bash revealed:
- 27 test collection errors due to duplicate `test_issue_N.py` names across feature directories
- pytest tries to import `test_issue_1.py` from multiple directories, causing module cache conflicts
- 12 production classes named `Test*` trigger pytest collection warnings

## Your Task

1. Add `__init__.py` files to make test directories proper packages
2. Rename test files to globally unique names
3. Rename production classes to avoid `Test*` prefix

## Part 1: Add Package Markers

Create `__init__.py` in each test directory:

```bash
# Directories needing __init__.py:
tests/generated/chief-of-staff/__init__.py
tests/generated/chief-of-staff-v2/__init__.py
tests/generated/chief-of-staff-v3/__init__.py
tests/generated/external-dashboard/__init__.py
tests/generated/cos-phase8-recovery/__init__.py
tests/generated/backlog-discovery/__init__.py
```

Each file should contain:
```python
"""Generated tests for {feature-name} feature."""
```

## Part 2: Rename Test Files

Create and run a migration script:

### `scripts/migrate_test_names.py`

```python
#!/usr/bin/env python3
"""Migrate test files to globally unique names.

Renames: test_issue_N.py -> test_{feature_slug}_issue_N.py

Usage:
    python scripts/migrate_test_names.py --dry-run  # Preview changes
    python scripts/migrate_test_names.py            # Execute rename
"""
import argparse
import re
import shutil
from pathlib import Path


def get_feature_slug(feature_dir: Path) -> str:
    """Convert feature directory name to valid Python identifier."""
    return feature_dir.name.replace("-", "_")


def migrate_tests(dry_run: bool = True) -> list[tuple[Path, Path]]:
    """Migrate test files to new naming convention.

    Returns list of (old_path, new_path) tuples.
    """
    generated = Path("tests/generated")
    if not generated.exists():
        print(f"Directory not found: {generated}")
        return []

    renames = []

    for feature_dir in sorted(generated.iterdir()):
        if not feature_dir.is_dir():
            continue

        feature_slug = get_feature_slug(feature_dir)

        # Find test_issue_*.py files (old naming)
        for test_file in sorted(feature_dir.glob("test_issue_*.py")):
            # Extract issue number
            match = re.match(r"test_issue_(\d+)\.py", test_file.name)
            if not match:
                continue

            issue_num = match.group(1)
            new_name = f"test_{feature_slug}_issue_{issue_num}.py"
            new_path = feature_dir / new_name

            if new_path.exists():
                print(f"SKIP (exists): {test_file} -> {new_path}")
                continue

            renames.append((test_file, new_path))

            if dry_run:
                print(f"WOULD RENAME: {test_file} -> {new_path}")
            else:
                print(f"RENAMING: {test_file} -> {new_path}")
                shutil.move(str(test_file), str(new_path))

    return renames


def main():
    parser = argparse.ArgumentParser(description="Migrate test file names")
    parser.add_argument("--dry-run", action="store_true", help="Preview without renaming")
    args = parser.parse_args()

    renames = migrate_tests(dry_run=args.dry_run)

    print(f"\nTotal: {len(renames)} files {'would be' if args.dry_run else ''} renamed")

    if args.dry_run and renames:
        print("\nRun without --dry-run to execute renames.")


if __name__ == "__main__":
    main()
```

## Part 3: Rename Production Classes

Rename these classes to avoid pytest collection:

| File | Old Name | New Name |
|------|----------|----------|
| `swarm_attack/edge_cases.py` | `TestFailureError` | `FailureError` |
| `swarm_attack/edge_cases.py` | `TestFailureHandler` | `FailureHandler` |
| `swarm_attack/config.py` | `TestRunnerConfig` | `RunnerConfig` |
| `swarm_attack/chief_of_staff/state_gatherer.py` | `TestState` | `SuiteState` |
| `swarm_attack/recovery.py` | `TestRunner` | `SuiteRunner` |
| `swarm_attack/recovery.py` | `TestRunResult` | `SuiteRunResult` |
| `swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py` | `TestFailureDiscoveryAgent` | `FailureDiscoveryAgent` |
| `swarm_attack/bug_models.py` | `TestCase` | `BugTestCase` |
| `swarm_attack/chief_of_staff/validation_gates.py` | `TestValidationGate` | `SuiteValidationGate` |
| `swarm_attack/chief_of_staff/critics.py` | `TestCritic` | `SuiteCritic` |

For each rename:
1. Rename the class definition
2. Update all imports of that class
3. Update all usages of that class
4. Verify tests still pass

Use this search pattern to find usages:
```bash
grep -r "TestFailureError" swarm_attack/ tests/
```

## Part 4: Update Test Generator

Modify `swarm_attack/agents/coder.py` to generate tests with new naming convention.

Find the code that creates test file paths and change:
```python
# Old
test_file = f"tests/generated/{feature_id}/test_issue_{issue_number}.py"

# New
feature_slug = feature_id.replace("-", "_")
test_file = f"tests/generated/{feature_id}/test_{feature_slug}_issue_{issue_number}.py"
```

## Acceptance Criteria

```bash
# Zero collection errors
pytest --collect-only 2>&1 | grep -c "ERROR collecting"
# Expected: 0

# No warnings about Test* classes
pytest --collect-only 2>&1 | grep -c "cannot collect test class"
# Expected: 0

# All tests still pass
pytest tests/ -v
# Expected: All pass

# Verify new naming
ls tests/generated/chief-of-staff-v2/
# Should show: test_chief_of_staff_v2_issue_*.py
```

## Constraints

- Run migration script with --dry-run first
- Commit `__init__.py` files before renaming tests
- Update imports in the same commit as class renames
- Do not change test logic, only file names and class names
```

---

## Team 3: CLI Robustness

```
You are a CLI/UX engineer making Swarm Attack commands work reliably in non-interactive environments.

## Context

Bug bash revealed:
- Standup command fails with truncated error when piped (non-interactive)
- Invalid discovery type silently ignored instead of failing
- Diagnose says "healthy" while showing "10 stuck features"
- Inconsistent error message formatting across commands

## Your Task

1. Create CLI UX utilities for consistent behavior
2. Fix non-interactive mode handling
3. Standardize error formatting
4. Fix semantic inconsistencies

## Files to Create

### 1. `swarm_attack/cli/ux.py`

```python
"""CLI UX utilities for consistent behavior across commands.

Provides:
- Interactive mode detection
- Consistent error formatting
- Semantic exit codes
- Non-interactive fallbacks
"""
from __future__ import annotations

import sys
from typing import Any, Optional, TypeVar

import typer

# Semantic exit codes
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1      # Bad input, missing files, invalid arguments
EXIT_SYSTEM_ERROR = 2    # API failures, timeouts, internal errors
EXIT_BLOCKED = 3         # Needs human intervention

T = TypeVar("T")


def is_interactive() -> bool:
    """Check if running in interactive terminal.

    Returns True if both stdin and stdout are connected to a tty.
    Returns False in pipes, CI, or when redirected.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def prompt_or_default(
    prompt: str,
    default: T,
    *,
    require_interactive: bool = False,
    type: Optional[type] = None,
) -> T:
    """Prompt user if interactive, otherwise use default.

    Args:
        prompt: The prompt message to display
        default: Default value if non-interactive or user accepts default
        require_interactive: If True, exit with error in non-interactive mode
        type: Type to cast the response to (for typer.prompt)

    Returns:
        User's response or default value

    Raises:
        typer.Exit: If require_interactive=True and not in interactive mode
    """
    if is_interactive():
        return typer.prompt(prompt, default=default, type=type)

    if require_interactive:
        typer.echo(
            format_error(
                "INTERACTIVE_REQUIRED",
                "This command requires interactive input",
                hint="Run in a terminal or provide all required arguments"
            ),
            err=True
        )
        raise typer.Exit(EXIT_USER_ERROR)

    return default


def confirm_or_default(
    prompt: str,
    default: bool = False,
    *,
    require_interactive: bool = False,
) -> bool:
    """Confirm with user if interactive, otherwise use default.

    Args:
        prompt: The confirmation prompt
        default: Default if non-interactive
        require_interactive: If True, exit with error in non-interactive mode

    Returns:
        True if confirmed, False otherwise
    """
    if is_interactive():
        return typer.confirm(prompt, default=default)

    if require_interactive:
        typer.echo(
            format_error(
                "CONFIRMATION_REQUIRED",
                "This action requires confirmation",
                hint="Run in a terminal or use --yes flag"
            ),
            err=True
        )
        raise typer.Exit(EXIT_USER_ERROR)

    return default


def format_error(
    code: str,
    message: str,
    *,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    hint: Optional[str] = None,
) -> str:
    """Format error message consistently.

    Standard format:
        Error: [CODE] Message
          Expected: ...
          Got: ...
          Hint: ...

    Args:
        code: Error code (e.g., "INVALID_INPUT", "NOT_FOUND")
        message: Human-readable error description
        expected: What was expected (optional)
        got: What was received (optional)
        hint: How to fix the issue (optional)

    Returns:
        Formatted error string
    """
    lines = [f"Error: [{code}] {message}"]

    if expected:
        lines.append(f"  Expected: {expected}")
    if got:
        lines.append(f"  Got: {got}")
    if hint:
        lines.append(f"  Hint: {hint}")

    return "\n".join(lines)


def exit_with_error(
    code: str,
    message: str,
    *,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    hint: Optional[str] = None,
    exit_code: int = EXIT_USER_ERROR,
) -> None:
    """Print formatted error and exit.

    Args:
        code: Error code
        message: Error message
        expected: What was expected
        got: What was received
        hint: How to fix
        exit_code: Exit code (default: EXIT_USER_ERROR)
    """
    typer.echo(
        format_error(code, message, expected=expected, got=got, hint=hint),
        err=True
    )
    raise typer.Exit(exit_code)
```

### 2. `tests/cli/test_ux.py`

```python
"""Tests for CLI UX utilities."""
import pytest
from unittest.mock import patch
from swarm_attack.cli.ux import (
    is_interactive,
    prompt_or_default,
    confirm_or_default,
    format_error,
    EXIT_USER_ERROR,
)


class TestIsInteractive:
    """Tests for interactive mode detection."""

    def test_returns_false_when_stdin_not_tty(self):
        """Non-tty stdin means non-interactive."""
        with patch("sys.stdin.isatty", return_value=False):
            with patch("sys.stdout.isatty", return_value=True):
                assert is_interactive() is False

    def test_returns_false_when_stdout_not_tty(self):
        """Non-tty stdout means non-interactive."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=False):
                assert is_interactive() is False

    def test_returns_true_when_both_tty(self):
        """Both tty means interactive."""
        with patch("sys.stdin.isatty", return_value=True):
            with patch("sys.stdout.isatty", return_value=True):
                assert is_interactive() is True


class TestPromptOrDefault:
    """Tests for prompt_or_default."""

    def test_returns_default_when_non_interactive(self):
        """Use default in non-interactive mode."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            result = prompt_or_default("Enter value", "default_value")
            assert result == "default_value"

    def test_exits_when_require_interactive(self):
        """Exit with error when interactive required but not available."""
        with patch("swarm_attack.cli.ux.is_interactive", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                prompt_or_default("Enter value", "default", require_interactive=True)
            assert exc_info.value.code == EXIT_USER_ERROR


class TestFormatError:
    """Tests for error formatting."""

    def test_basic_error(self):
        """Format basic error with just code and message."""
        result = format_error("TEST_ERROR", "Something went wrong")
        assert "Error: [TEST_ERROR] Something went wrong" in result

    def test_full_error(self):
        """Format error with all fields."""
        result = format_error(
            "INVALID_INPUT",
            "Value is invalid",
            expected="positive number",
            got="-5",
            hint="Use a number greater than 0"
        )
        assert "[INVALID_INPUT]" in result
        assert "Expected: positive number" in result
        assert "Got: -5" in result
        assert "Hint: Use a number greater than 0" in result
```

## Files to Modify

### 3. Fix `swarm_attack/cli/chief_of_staff.py` standup command

Find the `standup_command` function and replace `typer.prompt` calls with `prompt_or_default`:

```python
from swarm_attack.cli.ux import prompt_or_default, is_interactive

# In standup_command, around line 278:
# Old:
selection = typer.prompt("Select goals", default="0")

# New:
selection = prompt_or_default("Select goals", "0")
```

### 4. Fix discovery type validation

In the `discover` command, ensure invalid types fail loudly:

```python
from swarm_attack.cli.ux import exit_with_error

# Add validation at start of discover command:
if discovery_type.lower() not in VALID_DISCOVERY_TYPES:
    exit_with_error(
        "INVALID_DISCOVERY_TYPE",
        f"Unknown discovery type: {discovery_type}",
        expected=f"one of: {', '.join(VALID_DISCOVERY_TYPES)}",
        got=discovery_type,
        hint=f"Try: swarm-attack cos discover --type test"
    )
```

### 5. Fix diagnose health logic

Find the diagnose command and fix the health verdict:

```python
# The diagnose command should aggregate findings into health status
# If there are stuck features, blocked bugs, or failing tests, health should NOT be "healthy"

def get_health_status(snapshot) -> tuple[str, str]:
    """Determine overall health status.

    Returns (status, color) tuple.
    """
    issues = []

    # Check for stuck features
    stuck_features = [f for f in snapshot.features if f.phase == "BLOCKED"]
    if stuck_features:
        issues.append(f"{len(stuck_features)} stuck features")

    # Check for failing tests
    if snapshot.tests.failed > 0:
        issues.append(f"{snapshot.tests.failed} failing tests")

    # Check for blocked bugs
    blocked_bugs = [b for b in snapshot.bugs if b.phase == "blocked"]
    if blocked_bugs:
        issues.append(f"{len(blocked_bugs)} blocked bugs")

    if issues:
        return f"unhealthy ({', '.join(issues)})", "red"

    return "healthy", "green"
```

## Acceptance Criteria

```bash
# Non-interactive standup uses defaults without error
echo "" | swarm-attack cos standup --no-github
# Should complete without error, using default "0" for goal selection

# Invalid discovery type fails with clear error
swarm-attack cos discover --type invalid
# Should show: Error: [INVALID_DISCOVERY_TYPE] Unknown discovery type...

# Diagnose shows unhealthy when issues exist
swarm-attack diagnose
# Should show "unhealthy" if there are stuck features

# Error messages are consistent
swarm-attack init ""
# Should show: Error: [EMPTY_ID] Feature ID cannot be empty
#              Expected: non-empty string
#              Hint: ...
```

## Constraints

- Do not change behavior for interactive users
- Defaults in non-interactive mode should be safe (no destructive actions)
- All error messages must use format_error for consistency
- Exit codes must be semantic (1=user error, 2=system error, 3=blocked)
```

---

## Team 4: State Management Hardening

```
You are a state management engineer adding lifecycle tracking and schema validation to Swarm Attack.

## Context

Bug bash revealed:
- `bug-unknown-{timestamp}` created when empty values passed (no validation)
- Invalid issue -1 logged to event log (no schema validation)
- 18 stale checkpoints never cleaned up (no lifecycle management)
- Progress shows stale data (no staleness detection)

## Your Task

1. Add lifecycle metadata to persisted state
2. Add schema validation for events
3. Implement checkpoint cleanup
4. Add staleness detection to progress

## Files to Create

### 1. `swarm_attack/state/__init__.py`

```python
"""State management with lifecycle and schema validation."""
from .lifecycle import LifecycleMetadata, StateCleanupJob
from .schemas import SwarmEvent, validate_event

__all__ = [
    "LifecycleMetadata",
    "StateCleanupJob",
    "SwarmEvent",
    "validate_event",
]
```

### 2. `swarm_attack/state/lifecycle.py`

```python
"""State lifecycle management with TTL and cleanup.

Provides:
- LifecycleMetadata for tracking state age
- StateCleanupJob for removing expired state
- Staleness detection utilities
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import json


@dataclass
class LifecycleMetadata:
    """Lifecycle tracking for persisted state.

    Attributes:
        created_at: When the state was first created (ISO format)
        updated_at: When the state was last modified (ISO format)
        expires_at: Optional expiration time (ISO format)
    """
    created_at: str
    updated_at: str
    expires_at: Optional[str] = None

    @classmethod
    def now(cls, ttl_seconds: Optional[int] = None) -> "LifecycleMetadata":
        """Create metadata with current timestamp.

        Args:
            ttl_seconds: Optional TTL in seconds for expiration
        """
        now = datetime.now().isoformat()
        expires = None
        if ttl_seconds:
            expires = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
        return cls(created_at=now, updated_at=now, expires_at=expires)

    def touch(self) -> None:
        """Update the updated_at timestamp to now."""
        self.updated_at = datetime.now().isoformat()

    def is_stale(self, max_age: timedelta) -> bool:
        """Check if state is stale (not updated within max_age).

        Args:
            max_age: Maximum age before considered stale

        Returns:
            True if updated_at is older than max_age ago
        """
        updated = datetime.fromisoformat(self.updated_at)
        return datetime.now() - updated > max_age

    def is_expired(self) -> bool:
        """Check if state has passed its expiration time.

        Returns:
            True if expires_at is set and has passed
        """
        if self.expires_at is None:
            return False
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now() > expires

    def age_seconds(self) -> int:
        """Get age in seconds since last update."""
        updated = datetime.fromisoformat(self.updated_at)
        return int((datetime.now() - updated).total_seconds())

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LifecycleMetadata":
        """Deserialize from dictionary."""
        return cls(
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            expires_at=data.get("expires_at"),
        )


class StateCleanupJob:
    """Cleanup expired and stale state files.

    Scans a directory for JSON state files with lifecycle metadata
    and removes those that are expired or stale.
    """

    def __init__(
        self,
        state_dir: Path,
        max_age_days: int = 30,
        dry_run: bool = False,
    ):
        """Initialize cleanup job.

        Args:
            state_dir: Directory containing state files
            max_age_days: Remove state older than this many days
            dry_run: If True, report but don't delete
        """
        self.state_dir = state_dir
        self.max_age = timedelta(days=max_age_days)
        self.dry_run = dry_run

    def run(self) -> list[Path]:
        """Execute cleanup, removing expired state files.

        Returns:
            List of paths that were removed (or would be in dry_run)
        """
        removed = []

        if not self.state_dir.exists():
            return removed

        for state_file in self.state_dir.glob("**/*.json"):
            try:
                data = json.loads(state_file.read_text())

                # Check for lifecycle metadata
                if "lifecycle" not in data:
                    continue

                meta = LifecycleMetadata.from_dict(data["lifecycle"])

                should_remove = meta.is_expired() or meta.is_stale(self.max_age)

                if should_remove:
                    removed.append(state_file)
                    if not self.dry_run:
                        state_file.unlink()

            except (json.JSONDecodeError, KeyError, ValueError):
                # Skip malformed files
                continue

        return removed


def get_staleness_indicator(updated_at: str, thresholds: dict[int, str] = None) -> Optional[str]:
    """Get human-readable staleness indicator.

    Args:
        updated_at: ISO format timestamp of last update
        thresholds: Dict of seconds -> label, defaults provided

    Returns:
        Staleness label if stale, None if fresh

    Example:
        >>> get_staleness_indicator("2025-12-20T10:00:00")
        "stale (5 min ago)"
    """
    if thresholds is None:
        thresholds = {
            300: "stale",      # 5 minutes
            3600: "very stale", # 1 hour
            86400: "outdated",  # 1 day
        }

    try:
        updated = datetime.fromisoformat(updated_at)
        age_seconds = (datetime.now() - updated).total_seconds()

        for threshold, label in sorted(thresholds.items()):
            if age_seconds >= threshold:
                if age_seconds < 60:
                    age_str = f"{int(age_seconds)}s ago"
                elif age_seconds < 3600:
                    age_str = f"{int(age_seconds / 60)}m ago"
                elif age_seconds < 86400:
                    age_str = f"{int(age_seconds / 3600)}h ago"
                else:
                    age_str = f"{int(age_seconds / 86400)}d ago"
                return f"{label} ({age_str})"

        return None  # Fresh

    except ValueError:
        return "unknown"
```

### 3. `swarm_attack/state/schemas.py`

```python
"""Schema validation for persisted state and events.

All persisted data must conform to a schema. Loading validates
and rejects malformed data with specific errors.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class SchemaValidationError(Exception):
    """Raised when data doesn't conform to schema."""

    def __init__(self, field: str, message: str, value: any = None):
        self.field = field
        self.message = message
        self.value = value
        super().__init__(f"Schema validation failed for '{field}': {message}")


@dataclass
class SwarmEvent:
    """Schema for swarm events logged to event log.

    All fields are validated on construction.
    """
    ts: str
    event: str
    feature_id: str
    issue: Optional[int] = None

    # Additional optional fields
    agent: Optional[str] = None
    cost_usd: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None

    def __post_init__(self):
        """Validate all fields on construction."""
        if not self.ts:
            raise SchemaValidationError("ts", "timestamp is required")

        if not self.event:
            raise SchemaValidationError("event", "event type is required")

        if not self.feature_id:
            raise SchemaValidationError("feature_id", "feature_id is required")

        if self.issue is not None:
            if not isinstance(self.issue, int):
                raise SchemaValidationError("issue", "must be an integer", self.issue)
            if self.issue < 1:
                raise SchemaValidationError("issue", "must be >= 1", self.issue)

        if self.cost_usd is not None:
            if not isinstance(self.cost_usd, (int, float)):
                raise SchemaValidationError("cost_usd", "must be a number", self.cost_usd)
            if self.cost_usd < 0:
                raise SchemaValidationError("cost_usd", "cannot be negative", self.cost_usd)

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        d = {
            "ts": self.ts,
            "event": self.event,
            "feature_id": self.feature_id,
        }
        if self.issue is not None:
            d["issue"] = self.issue
        if self.agent is not None:
            d["agent"] = self.agent
        if self.cost_usd is not None:
            d["cost_usd"] = self.cost_usd
        if self.success is not None:
            d["success"] = self.success
        if self.error is not None:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SwarmEvent":
        """Deserialize from dictionary, validating schema."""
        return cls(
            ts=data.get("ts", ""),
            event=data.get("event", ""),
            feature_id=data.get("feature_id", ""),
            issue=data.get("issue"),
            agent=data.get("agent"),
            cost_usd=data.get("cost_usd"),
            success=data.get("success"),
            error=data.get("error"),
        )


def validate_event(data: dict) -> SwarmEvent:
    """Validate event data and return typed SwarmEvent.

    Args:
        data: Raw event dictionary

    Returns:
        Validated SwarmEvent

    Raises:
        SchemaValidationError: If validation fails
    """
    return SwarmEvent.from_dict(data)
```

### 4. `tests/state/test_lifecycle.py`

```python
"""Tests for state lifecycle management."""
import pytest
import json
from datetime import datetime, timedelta
from pathlib import Path

from swarm_attack.state.lifecycle import (
    LifecycleMetadata,
    StateCleanupJob,
    get_staleness_indicator,
)


class TestLifecycleMetadata:
    """Tests for LifecycleMetadata."""

    def test_now_creates_current_timestamp(self):
        """now() creates metadata with current time."""
        meta = LifecycleMetadata.now()
        created = datetime.fromisoformat(meta.created_at)
        assert (datetime.now() - created).total_seconds() < 1

    def test_now_with_ttl_sets_expiration(self):
        """now() with TTL sets expires_at."""
        meta = LifecycleMetadata.now(ttl_seconds=3600)
        assert meta.expires_at is not None
        expires = datetime.fromisoformat(meta.expires_at)
        assert expires > datetime.now()

    def test_is_stale_returns_true_for_old_state(self):
        """is_stale returns True for state older than max_age."""
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        meta = LifecycleMetadata(created_at=old_time, updated_at=old_time)
        assert meta.is_stale(timedelta(hours=1)) is True

    def test_is_stale_returns_false_for_fresh_state(self):
        """is_stale returns False for recently updated state."""
        meta = LifecycleMetadata.now()
        assert meta.is_stale(timedelta(hours=1)) is False

    def test_is_expired_returns_true_after_expiration(self):
        """is_expired returns True after expires_at passes."""
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        meta = LifecycleMetadata(
            created_at=past,
            updated_at=past,
            expires_at=past,
        )
        assert meta.is_expired() is True

    def test_is_expired_returns_false_when_no_expiration(self):
        """is_expired returns False when expires_at is None."""
        meta = LifecycleMetadata.now()
        assert meta.is_expired() is False


class TestStateCleanupJob:
    """Tests for StateCleanupJob."""

    def test_removes_expired_files(self, tmp_path: Path):
        """Cleanup removes files past expiration."""
        state_file = tmp_path / "test.json"
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        state_file.write_text(json.dumps({
            "data": "test",
            "lifecycle": {
                "created_at": past,
                "updated_at": past,
                "expires_at": past,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 1
        assert not state_file.exists()

    def test_keeps_fresh_files(self, tmp_path: Path):
        """Cleanup keeps files that are not expired or stale."""
        state_file = tmp_path / "fresh.json"
        now = datetime.now().isoformat()
        state_file.write_text(json.dumps({
            "data": "test",
            "lifecycle": {
                "created_at": now,
                "updated_at": now,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30)
        removed = job.run()

        assert len(removed) == 0
        assert state_file.exists()

    def test_dry_run_does_not_delete(self, tmp_path: Path):
        """Dry run reports but doesn't delete."""
        state_file = tmp_path / "expired.json"
        past = (datetime.now() - timedelta(days=60)).isoformat()
        state_file.write_text(json.dumps({
            "lifecycle": {
                "created_at": past,
                "updated_at": past,
            }
        }))

        job = StateCleanupJob(tmp_path, max_age_days=30, dry_run=True)
        removed = job.run()

        assert len(removed) == 1
        assert state_file.exists()  # Still exists because dry_run


class TestGetStalenessIndicator:
    """Tests for staleness indicator."""

    def test_returns_none_for_fresh(self):
        """Fresh state returns None."""
        now = datetime.now().isoformat()
        assert get_staleness_indicator(now) is None

    def test_returns_stale_after_5_minutes(self):
        """State over 5 minutes old is stale."""
        old = (datetime.now() - timedelta(minutes=10)).isoformat()
        result = get_staleness_indicator(old)
        assert "stale" in result
```

## Files to Modify

### 5. Update `swarm_attack/event_logger.py`

Add schema validation when logging events:

```python
from swarm_attack.state.schemas import SwarmEvent, SchemaValidationError

def log_event(self, feature_id: str, event: str, **kwargs):
    """Log an event with schema validation."""
    try:
        validated = SwarmEvent(
            ts=datetime.now().isoformat(),
            event=event,
            feature_id=feature_id,
            **kwargs
        )
        self._append_event(validated.to_dict())
    except SchemaValidationError as e:
        # Log warning but don't crash
        logger.warning(f"Invalid event rejected: {e}")
```

### 6. Update `swarm_attack/chief_of_staff/checkpoints.py`

Add cleanup method:

```python
from swarm_attack.state.lifecycle import StateCleanupJob

class CheckpointStore:
    # ... existing code ...

    def cleanup_stale_checkpoints(self, max_age_days: int = 7) -> list[str]:
        """Remove checkpoints older than max_age_days.

        Returns list of removed checkpoint IDs.
        """
        cleanup = StateCleanupJob(
            self.checkpoint_dir,
            max_age_days=max_age_days,
        )
        removed_files = cleanup.run()
        return [f.stem for f in removed_files]
```

Call cleanup on startup in CLI commands that use checkpoints.

### 7. Update progress display

Add staleness indicator to progress output:

```python
from swarm_attack.state.lifecycle import get_staleness_indicator

def show_progress(snapshot):
    staleness = get_staleness_indicator(snapshot.updated_at)
    if staleness:
        console.print(f"[yellow]Data is {staleness}[/yellow]")
```

## Acceptance Criteria

```bash
# Invalid event rejected with validation error
# (check logs for "Invalid event rejected")
swarm-attack run test-feature --issue -1

# Stale checkpoints cleaned up
# (run cleanup, verify old checkpoints removed)

# Progress shows staleness indicator
# (wait 5+ minutes, verify "stale" appears)

# All schema tests pass
pytest tests/state/ -v
```

## Constraints

- Schema validation must not crash on invalid data (log and reject)
- Cleanup must only remove files with explicit lifecycle metadata
- Staleness is a warning, not an error
- Do not break existing state files (add lifecycle metadata on save, not load)
```

---

## Execution Order

1. **Team 1 (Input Validation)** - Run first, creates foundation
2. **Team 2 (Test Infrastructure)** - Can run in parallel with Team 1
3. **Team 3 (CLI Robustness)** - Depends on Team 1 for validation imports
4. **Team 4 (State Management)** - Can run after Team 1

## Verification Checklist

After all teams complete:

```bash
# Full test suite passes
pytest tests/ -v

# Zero collection errors
pytest --collect-only 2>&1 | grep -c ERROR
# Expected: 0

# Security validation works
swarm-attack init "../../../etc/passwd"
# Expected: Error: [PATH_TRAVERSAL]

# Non-interactive mode works
echo "" | swarm-attack cos standup --no-github
# Expected: Completes without error

# Stale state cleaned up
ls .swarm/checkpoints/ | wc -l
# Expected: Fewer than before cleanup
```

---

## Implementation Status

### Completed (Phase 1)

| Item | Status | Tests |
|------|--------|-------|
| `swarm_attack/validation/` module | ✅ Done | 40 passing |
| CLI validation wiring (feature.py, bug.py, chief_of_staff.py) | ✅ Done | - |
| `swarm_attack/cli/ux.py` module | ✅ Done | 18 passing |
| `swarm_attack/state/` module (lifecycle, schemas) | ✅ Done | 42 passing |
| Test file migration (55 files renamed) | ✅ Done | 0 collection errors |
| pyproject.toml updated for Test* pattern | ✅ Done | - |

### Remaining (Phase 2)

#### Team 2: Rename Production Test* Classes

| File | Current Name | New Name |
|------|--------------|----------|
| `swarm_attack/edge_cases.py` | `TestFailureError` | `FailureError` |
| `swarm_attack/edge_cases.py` | `TestFailureHandler` | `FailureHandler` |
| `swarm_attack/config.py` | `TestRunnerConfig` | `RunnerConfig` |
| `swarm_attack/chief_of_staff/state_gatherer.py` | `TestState` | `SuiteState` |
| `swarm_attack/recovery.py` | `TestRunner` | `SuiteRunner` |
| `swarm_attack/recovery.py` | `TestRunResult` | `SuiteRunResult` |
| `swarm_attack/chief_of_staff/backlog_discovery/discovery_agent.py` | `TestFailureDiscoveryAgent` | `FailureDiscoveryAgent` |
| `swarm_attack/bug_models.py` | `TestCase` | `BugTestCase` |
| `swarm_attack/chief_of_staff/validation_gates.py` | `TestValidationGate` | `SuiteValidationGate` |
| `swarm_attack/chief_of_staff/critics.py` | `TestCritic` | `SuiteCritic` |

#### Team 2: Update Test Generator

Update `swarm_attack/agents/coder.py` to generate test files with new naming:
```python
# Old pattern
test_file = f"tests/generated/{feature_id}/test_issue_{issue_number}.py"

# New pattern
feature_slug = feature_id.replace("-", "_")
test_file = f"tests/generated/{feature_id}/test_{feature_slug}_issue_{issue_number}.py"
```

#### Team 3: Wire UX Utilities

1. **Fix standup non-interactive mode** in `chief_of_staff.py`:
```python
from swarm_attack.cli.ux import prompt_or_default

# Replace typer.prompt with:
selection = prompt_or_default("Select goals", "0")
```

2. **Fix diagnose health logic** - aggregate issues into health status

#### Team 4: Wire State Management

1. **Update `event_logger.py`** to validate events:
```python
from swarm_attack.state.schemas import SwarmEvent, SchemaValidationError

def log_event(self, feature_id: str, event: str, **kwargs):
    try:
        validated = SwarmEvent(ts=..., event=event, feature_id=feature_id, **kwargs)
        self._append_event(validated.to_dict())
    except SchemaValidationError as e:
        logger.warning(f"Invalid event rejected: {e}")
```

2. **Update `checkpoints.py`** with cleanup method:
```python
def cleanup_stale_checkpoints(self, max_age_days: int = 7) -> list[str]:
    cleanup = StateCleanupJob(self.checkpoint_dir, max_age_days=max_age_days)
    return [f.stem for f in cleanup.run()]
```

3. **Add staleness indicator to progress display**
