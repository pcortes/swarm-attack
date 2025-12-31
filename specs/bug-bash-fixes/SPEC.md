# Bug Bash Fixes Specification

## Expert Specialist Implementation Prompt

```xml
<implementation_context>
  <spec_path>specs/bug-bash-fixes/SPEC.md</spec_path>
  <worktree_branch>fix/bug-bash-fixes</worktree_branch>
  <tdd_mode>strict</tdd_mode>
</implementation_context>

<specialist_team>
  <lead role="Security Engineer" focus="BUG-1, BUG-3, BUG-7, BUG-8, BUG-9, BUG-10, BUG-11, BUG-16">
    You are a Security Engineer specializing in input validation and path traversal prevention.
    Your bugs involve CLI input sanitization. The InputValidator class exists at
    swarm_attack/validation/input_validator.py but is NOT being called in CLI handlers.

    TDD approach:
    1. Write failing tests in tests/unit/test_input_validation_integration.py
    2. Tests must call CLI commands with malicious/invalid input
    3. Implementation: Wire InputValidator into CLI entry points
    4. All tests green before moving to next bug
  </lead>

  <specialist role="Test Infrastructure Engineer" focus="BUG-2, BUG-6, BUG-13, BUG-14, BUG-17, BUG-19">
    You are a Test Infrastructure Engineer specializing in pytest configuration and code generation.
    Your bugs involve corrupted test files, naming conflicts, and missing config.

    TDD approach:
    1. Write meta-tests that validate test infrastructure health
    2. Fix LLM output parsing in swarm_attack/agents/coder.py
    3. Rename production Test* classes to avoid pytest conflicts
    4. Add pytest-asyncio configuration to pyproject.toml
    5. Validate all tests collect without errors
  </specialist>

  <specialist role="Implementation Engineer" focus="BUG-4, BUG-5, BUG-12, BUG-15, BUG-18">
    You are an Implementation Engineer completing missing spec features.
    Your bugs involve missing methods, exports, and incomplete integrations.

    TDD approach:
    1. Write failing tests for each missing feature
    2. Implement the minimum code to pass tests
    3. Verify integration with existing systems
    4. BUG-4 belongs to schema-drift spec, not v3
    5. BUG-5 is a v2 foundation issue (add alias)
  </specialist>
</specialist_team>

<worktree_setup>
  <command>git worktree add ../worktrees/bug-bash-fixes -b fix/bug-bash-fixes</command>
  <working_directory>../worktrees/bug-bash-fixes</working_directory>
  <isolation>Each specialist works in same worktree, sequential commits per bug</isolation>
</worktree_setup>

<tdd_protocol>
  <step order="1">Write failing test for bug</step>
  <step order="2">Run test, confirm it fails for expected reason</step>
  <step order="3">Implement minimal fix</step>
  <step order="4">Run test, confirm it passes</step>
  <step order="5">Run full test suite, confirm no regressions</step>
  <step order="6">Commit with message "fix(BUG-N): description"</step>
  <step order="7">Move to next bug</step>
</tdd_protocol>

<success_criteria>
  <criterion>All 19 bugs have corresponding tests</criterion>
  <criterion>All tests pass (0 failures, 0 errors)</criterion>
  <criterion>No pytest collection warnings for Test* classes</criterion>
  <criterion>Security: path traversal blocked</criterion>
  <criterion>Validation: negative/empty inputs rejected</criterion>
</success_criteria>
```

---

## Executive Summary

**Source**: BUG_BASH_REPORT_2025_12_20.md
**Total Bugs**: 19 (2 Critical, 6 High, 8 Medium, 3 Low)
**Estimated Issues**: 19 atomic fixes

### Bug Categories

| Category | Bugs | Specialist |
|----------|------|------------|
| Security/Validation | 1,3,7,8,9,10,11,16 | Security Engineer |
| Test Infrastructure | 2,6,13,14,17,19 | Test Infra Engineer |
| Missing Implementation | 4,5,12,15,18 | Implementation Engineer |

---

## Phase 1: Security & Input Validation (CRITICAL)

### Issue 1: BUG-1 - Path Traversal Vulnerability

**Severity**: CRITICAL
**File**: `swarm_attack/cli/feature.py:517-593`
**Root Cause**: `feature_id` passed directly to path construction without validation

**Existing Code** (cli/common.py:115-122):
```python
def get_prd_path(config: "SwarmConfig", feature_id: str) -> Path:
    return Path(config.repo_root) / ".claude" / "prds" / f"{feature_id}.md"
```

**Existing Validator** (validation/input_validator.py:58-65):
```python
def validate_feature_id(self, value: str) -> ValidationResult:
    if not value or value.strip() == "":
        return ValidationResult(False, "Feature ID cannot be empty")
    if '..' in value or '/' in value:
        return ValidationResult(False, "Feature ID cannot contain path separators")
    return ValidationResult(True, "")
```

**TDD Test** (`tests/unit/test_cli_security.py`):
```python
import pytest
from typer.testing import CliRunner
from swarm_attack.cli import app

runner = CliRunner()

class TestPathTraversalPrevention:
    def test_init_rejects_path_traversal(self):
        """BUG-1: Path traversal must be blocked."""
        result = runner.invoke(app, ["init", "../../../../etc/passwd"])
        assert result.exit_code != 0
        assert "path" in result.output.lower() or "invalid" in result.output.lower()

    def test_init_rejects_forward_slash(self):
        result = runner.invoke(app, ["init", "foo/bar"])
        assert result.exit_code != 0

    def test_init_rejects_backslash(self):
        result = runner.invoke(app, ["init", "foo\\bar"])
        assert result.exit_code != 0
```

**Implementation** (`swarm_attack/cli/feature.py`):
```python
from swarm_attack.validation.input_validator import InputValidator

@app.command()
def init(feature_id: str = typer.Argument(...)):
    validator = InputValidator()
    result = validator.validate_feature_id(feature_id)
    if not result.valid:
        console.print(f"[red]Error: {result.message}[/red]")
        raise typer.Exit(1)
    # ... rest of init logic
```

---

### Issue 2: BUG-3 - Empty Feature Name Validation

**Severity**: HIGH
**File**: `swarm_attack/cli/feature.py:517-593`
**Root Cause**: No empty string check before creating feature

**TDD Test** (`tests/unit/test_cli_security.py`):
```python
class TestEmptyInputValidation:
    def test_init_rejects_empty_string(self):
        """BUG-3: Empty feature name must be rejected."""
        result = runner.invoke(app, ["init", ""])
        assert result.exit_code != 0
        assert "empty" in result.output.lower() or "required" in result.output.lower()

    def test_init_rejects_whitespace_only(self):
        result = runner.invoke(app, ["init", "   "])
        assert result.exit_code != 0
```

**Implementation**: Same as BUG-1 - validator already handles empty strings.

---

### Issue 3: BUG-7 - Negative Budget Validation

**Severity**: MEDIUM
**File**: `swarm_attack/cli/chief_of_staff.py:800-938`
**Root Cause**: No validation on budget parameter

**TDD Test** (`tests/unit/test_cli_validation.py`):
```python
class TestBudgetValidation:
    def test_autopilot_rejects_negative_budget(self):
        """BUG-7: Negative budget must be rejected."""
        result = runner.invoke(app, ["cos", "autopilot", "--budget", "-10"])
        assert result.exit_code != 0
        assert "positive" in result.output.lower() or "invalid" in result.output.lower()

    def test_autopilot_rejects_zero_budget(self):
        """BUG-16: Zero budget must be rejected."""
        result = runner.invoke(app, ["cos", "autopilot", "--budget", "0"])
        assert result.exit_code != 0
```

**Implementation** (`swarm_attack/cli/chief_of_staff.py`):
```python
@app.command("autopilot")
def autopilot_command(budget: float = typer.Option(10.0, "--budget", "-b")):
    if budget <= 0:
        console.print("[red]Error: Budget must be positive[/red]")
        raise typer.Exit(1)
```

---

### Issue 4: BUG-8 - Negative Duration Validation

**Severity**: MEDIUM
**File**: `swarm_attack/cli/chief_of_staff.py:801-911`

**TDD Test**:
```python
def test_autopilot_rejects_negative_duration(self):
    """BUG-8: Negative duration must be rejected."""
    result = runner.invoke(app, ["cos", "autopilot", "--duration", "-60m"])
    assert result.exit_code != 0
```

---

### Issue 5: BUG-9 - Empty Bug Init Validation

**Severity**: MEDIUM
**File**: `swarm_attack/cli/bug.py:32-83`
**Root Cause**: Falls back to "unknown" slug instead of rejecting

**TDD Test**:
```python
def test_bug_init_rejects_empty_description(self):
    """BUG-9: Empty bug description must be rejected."""
    result = runner.invoke(app, ["bug", "init", ""])
    assert result.exit_code != 0
    assert "bug-unknown" not in result.output
```

---

### Issue 6: BUG-10 - Negative Issue Number Validation

**Severity**: MEDIUM
**File**: `swarm_attack/models.py:122-159` (TaskRef dataclass)

**TDD Test**:
```python
def test_task_ref_rejects_negative_issue(self):
    """BUG-10: Negative issue numbers must be rejected."""
    with pytest.raises(ValueError):
        TaskRef(issue_number=-1, stage=TaskStage.BACKLOG, title="test")
```

**Implementation** (`swarm_attack/models.py`):
```python
@dataclass
class TaskRef:
    issue_number: int
    # ...

    def __post_init__(self):
        if self.issue_number < 1:
            raise ValueError(f"issue_number must be >= 1, got {self.issue_number}")
```

---

### Issue 7: BUG-11 - Invalid Discovery Type Validation

**Severity**: MEDIUM
**File**: `swarm_attack/chief_of_staff/backlog_discovery/candidates.py:196-210`

**TDD Test**:
```python
def test_opportunity_rejects_invalid_type(self):
    """BUG-11: Invalid discovery type must raise error, not default."""
    with pytest.raises(ValueError):
        Opportunity.from_dict({"opportunity_type": "invalid_type"})
```

---

### Issue 8: BUG-16 - Zero Budget Validation

**Covered by Issue 3 (BUG-7)** - same validation logic.

---

## Phase 2: Test Infrastructure (CRITICAL)

### Issue 9: BUG-2 - Corrupted Test File

**Severity**: CRITICAL
**File**: `tests/generated/chief-of-staff-v3/test_issue_29.py:564`
**Root Cause**: LLM output parsing includes explanation text after code block

**Corrupted Content**:
```python
# Line 562 - valid code ends
        )

# Line 564 - LLM explanation leaked in
Now I'll output the implementation. Since I need to add a method to an existing file...
```

**TDD Test** (`tests/unit/test_code_extraction.py`):
```python
class TestCodeExtraction:
    def test_extracts_only_code_blocks(self):
        """BUG-2: LLM explanations must not leak into extracted code."""
        response = '''
Here's the implementation:

```python
def foo():
    return 42
```

Now I'll explain what this does...
'''
        extracted = extract_code_from_response(response)
        assert "def foo" in extracted
        assert "explain" not in extracted.lower()
        # Validate it's syntactically correct
        ast.parse(extracted)
```

**Implementation** (`swarm_attack/agents/coder.py`):
```python
import re
import ast

def extract_code_from_response(response: str) -> str:
    """Extract Python code from LLM response, excluding explanations."""
    # Find all code blocks
    pattern = r'```(?:python)?\n(.*?)```'
    matches = re.findall(pattern, response, re.DOTALL)

    if not matches:
        raise ValueError("No code block found in response")

    code = '\n\n'.join(matches)

    # Validate syntax
    try:
        ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Extracted code has syntax error: {e}")

    return code
```

**Immediate Fix**: Delete/regenerate `test_issue_29.py`:
```bash
rm tests/generated/chief-of-staff-v3/test_issue_29.py
# Regenerate via: swarm-attack run --issue 29 chief-of-staff-v3
```

---

### Issue 10: BUG-6 - Test Collection Errors (28 files)

**Severity**: CRITICAL
**Files**: `tests/generated/*/test_issue_*.py` (28 files truncated)
**Root Cause**: Code extraction truncates files mid-function

**TDD Test**:
```python
def test_all_generated_tests_have_valid_syntax():
    """BUG-6: All generated test files must be syntactically valid."""
    from pathlib import Path
    import ast

    errors = []
    for test_file in Path("tests/generated").rglob("test_*.py"):
        try:
            ast.parse(test_file.read_text())
        except SyntaxError as e:
            errors.append(f"{test_file}: {e}")

    assert not errors, f"Syntax errors in test files:\n" + "\n".join(errors)
```

**Implementation**: Add AST validation before writing files (same as BUG-2 fix).

---

### Issue 11: BUG-13 - TestState Class Rename

**Severity**: HIGH
**File**: `swarm_attack/chief_of_staff/state_gatherer.py:76-81`
**Root Cause**: Production class named `TestState` conflicts with pytest

**TDD Test**:
```python
def test_no_production_classes_named_test(self):
    """BUG-13, BUG-14: Production code must not use Test* class names."""
    import ast
    from pathlib import Path

    violations = []
    for py_file in Path("swarm_attack").rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                violations.append(f"{py_file}:{node.lineno} - {node.name}")

    assert not violations, f"Production Test* classes:\n" + "\n".join(violations)
```

**Implementation**:
```python
# Before:
@dataclass
class TestState:
    """Test suite state."""

# After:
@dataclass
class TestSuiteMetrics:
    """Test suite state metrics."""
```

**Update imports** in all files that reference `TestState`.

---

### Issue 12: BUG-14 - Multiple Test* Class Renames

**Severity**: HIGH
**Files**: Multiple (see rename table below)

**Rename Table**:

| Current Name | New Name | File |
|--------------|----------|------|
| `TestState` | `TestSuiteMetrics` | state_gatherer.py:76 |
| `TestCritic` | `TestingCritic` | critics.py:646 |
| `TestValidationGate` | `TestingValidationGate` | validation_gates.py:238 |
| `TestRunnerConfig` | `ExecutorConfig` | config.py |
| `TestRunResult` | `ExecutionResult` | recovery.py |
| `TestCase` | `BugTestCase` | bug_models.py |
| `TestFailureError` | `ExecutionFailureError` | edge_cases.py |
| `TestFailureHandler` | `FailureHandler` | edge_cases.py |

---

### Issue 13: BUG-17 - pytest-asyncio Configuration

**Severity**: LOW
**File**: `pyproject.toml`

**TDD Test**:
```python
def test_pytest_asyncio_configured():
    """BUG-17: pytest-asyncio loop scope must be configured."""
    import tomllib

    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)

    pytest_opts = config.get("tool", {}).get("pytest", {}).get("ini_options", {})
    assert "asyncio_default_fixture_loop_scope" in pytest_opts
```

**Implementation** (add to `pyproject.toml`):
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
filterwarnings = [
    "ignore::pytest.PytestCollectionWarning",
]
```

---

### Issue 14: BUG-19 - 42 Test Failures

**Severity**: HIGH
**Root Cause**: Blocked by BUG-2, BUG-6, BUG-13, BUG-14, BUG-17

**This issue resolves automatically** when the preceding bugs are fixed.

**Validation Test**:
```python
def test_full_suite_passes():
    """BUG-19: Full test suite must pass."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True
    )
    assert result.returncode == 0, f"Tests failed:\n{result.stdout.decode()}"
```

---

## Phase 3: Missing Implementation

### Issue 15: BUG-4 - Missing `_check_duplicate_classes`

**Severity**: HIGH
**File**: `swarm_attack/agents/verifier.py`
**Spec**: NOT in chief-of-staff-v3 (belongs to schema-drift-prevention spec)

**TDD Test** (`tests/unit/test_verifier_schema_drift.py` - already exists):
```python
def test_check_duplicate_classes_finds_conflicts(self):
    """BUG-4: VerifierAgent must detect duplicate class definitions."""
    verifier = VerifierAgent(config)
    new_classes = {"Foo": "module_a.py"}
    registry = {"Foo": "module_b.py"}

    conflicts = verifier._check_duplicate_classes(new_classes, registry)
    assert len(conflicts) == 1
    assert conflicts[0].class_name == "Foo"
```

**Implementation** (`swarm_attack/agents/verifier.py`):
```python
def _check_duplicate_classes(
    self,
    new_classes: dict[str, str],
    registry: dict[str, str]
) -> list[ClassConflict]:
    """Check for duplicate class definitions across modules."""
    conflicts = []
    for class_name, new_file in new_classes.items():
        if class_name in registry:
            existing_file = registry[class_name]
            if new_file != existing_file:
                conflicts.append(ClassConflict(
                    class_name=class_name,
                    existing_file=existing_file,
                    new_file=new_file
                ))
    return conflicts
```

---

### Issue 16: BUG-5 - Missing `BACKOFF_SECONDS` Export

**Severity**: HIGH
**File**: `swarm_attack/chief_of_staff/recovery.py:67-70`
**Spec**: chief-of-staff-v2 (cos-phase8-recovery), not v3

**TDD Test**:
```python
def test_backoff_seconds_exported():
    """BUG-5: BACKOFF_SECONDS must be importable for backward compatibility."""
    from swarm_attack.chief_of_staff.recovery import BACKOFF_SECONDS
    assert BACKOFF_SECONDS > 0
```

**Implementation** (`swarm_attack/chief_of_staff/recovery.py`):
```python
# Constants for retry logic
MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 5
DEFAULT_BACKOFF_MULTIPLIER = 2

# Backward compatibility alias
BACKOFF_SECONDS = DEFAULT_BACKOFF_BASE_SECONDS
```

---

### Issue 17: BUG-12 - Standup Error Handling

**Severity**: MEDIUM
**File**: `swarm_attack/cli/chief_of_staff.py` (standup command)
**Spec**: chief-of-staff-v3, Issue #11 (Phase 10)

**TDD Test**:
```python
def test_standup_shows_full_error_message():
    """BUG-12: Standup must show complete error details, not truncated."""
    result = runner.invoke(app, ["cos", "standup"])
    if result.exit_code != 0:
        assert "Error during standup:" not in result.output or \
               len(result.output.split("Error during standup:")[-1].strip()) > 10
```

**Implementation**: Add proper exception handling with full traceback logging.

---

### Issue 18: BUG-15 - Stale Checkpoint Cleanup

**Severity**: LOW
**File**: `swarm_attack/chief_of_staff/checkpoints.py:305-387`
**Spec**: Not explicitly specified in v3

**TDD Test**:
```python
def test_checkpoints_command_cleans_stale():
    """BUG-15: Viewing checkpoints should auto-cleanup stale entries."""
    # Create stale checkpoint (8+ days old)
    store = CheckpointStore(config)
    store.save(Checkpoint(created_at=datetime.now() - timedelta(days=8), ...))

    # List checkpoints
    result = runner.invoke(app, ["cos", "checkpoints"])

    # Stale checkpoint should be cleaned
    assert "hiccup" not in result.output or result.output.count("hiccup") < 5
```

**Implementation**: Call `cleanup_stale_checkpoints_sync()` at start of checkpoints command.

---

### Issue 19: BUG-18 - Event Logger Validation

**Severity**: MEDIUM
**File**: `swarm_attack/event_logger.py:185-195`

**TDD Test**:
```python
def test_event_logger_rejects_negative_issue():
    """BUG-18: EventLogger must reject negative issue numbers."""
    logger = EventLogger(config)
    with pytest.raises(ValueError):
        logger.log_issue_started("feature", issue_number=-1, session_id="sess")
```

**Implementation** (`swarm_attack/event_logger.py`):
```python
def log_issue_started(self, feature_id: str, issue_number: int, session_id: str = ""):
    if issue_number < 1:
        raise ValueError(f"Invalid issue number: {issue_number}")
    # ... rest of method
```

---

## Implementation Order

```
Phase 1 (Security) - Sequential, high priority:
  1. BUG-1 (path traversal) - CRITICAL
  2. BUG-3 (empty feature)
  3. BUG-10 (negative issue)
  4. BUG-7, BUG-16 (budget validation)
  5. BUG-8 (duration validation)
  6. BUG-9 (bug init validation)
  7. BUG-11 (discovery type)

Phase 2 (Test Infra) - Parallel where possible:
  8. BUG-17 (pytest config) - quick win
  9. BUG-13, BUG-14 (Test* renames) - batch together
  10. BUG-2 (corrupted file) - delete + fix parser
  11. BUG-6 (truncated files) - fix parser
  12. BUG-19 (verify all pass)

Phase 3 (Implementation) - After Phase 2:
  13. BUG-5 (BACKOFF_SECONDS alias)
  14. BUG-4 (_check_duplicate_classes)
  15. BUG-12 (standup error handling)
  16. BUG-15 (checkpoint cleanup)
  17. BUG-18 (event logger validation)
```

---

## Success Criteria

```yaml
tests:
  collection_errors: 0
  failures: 0
  warnings: 0  # No Test* collection warnings

security:
  path_traversal_blocked: true
  empty_input_rejected: true
  negative_values_rejected: true

coverage:
  all_19_bugs_have_tests: true
  all_tests_pass: true
```

---

## Worktree Commands

```bash
# Setup
cd ~/Desktop/swarm-attack
git worktree add ../worktrees/bug-bash-fixes -b fix/bug-bash-fixes
cd ../worktrees/bug-bash-fixes

# Run tests for specific bug
PYTHONPATH=. pytest tests/unit/test_cli_security.py -v -k "path_traversal"

# Run full suite
PYTHONPATH=. pytest tests/ --ignore=tests/generated -v

# Commit pattern
git add -A
git commit -m "fix(BUG-1): Block path traversal in feature init

- Add InputValidator call to cli/feature.py
- Reject feature names containing .. or /
- Add tests for path traversal prevention

Fixes: BUG-1 from BUG_BASH_REPORT_2025_12_20.md"
```
