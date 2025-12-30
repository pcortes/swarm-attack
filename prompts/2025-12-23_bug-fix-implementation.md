# Swarm Attack Bug Fix Implementation Prompt

**Working Directory:** `/Users/philipjcortes/Desktop/swarm-attack`
**Date:** 2025-12-23
**Branch:** `fix/bug-bash-2025-12-20`

---

## FIRST: Verify Your Working Directory

**Before reading further, run these commands:**

```bash
cd /Users/philipjcortes/Desktop/swarm-attack
pwd      # Must show: /Users/philipjcortes/Desktop/swarm-attack
git status   # Check current state
git checkout -b fix/bug-bash-2025-12-20 2>/dev/null || git checkout fix/bug-bash-2025-12-20
```

**STOP if you're not in the correct directory.**

---

<mission>
You are orchestrating a Team of Specialized Experts to fix critical bugs in Swarm Attack
using strict Test-Driven Development (TDD) methodology.

Priority: Fix bugs in order of severity (Critical → High → Medium).
Goal: All 2,180 tests passing after fixes are applied.
</mission>

<team_structure>
| Expert | Role | Responsibility |
|--------|------|----------------|
| SecurityExpert | Vulnerability Analysis | Path traversal fix, input sanitization |
| TestEngineer | RED Phase | Write failing tests FIRST for each bug |
| Coder | GREEN Phase | Implement minimal fixes to pass tests |
| Integrator | Wiring | Ensure fixes don't break existing functionality |
| Reviewer | Validation | Run full test suite, verify no regressions |
</team_structure>

<background_context>
<codebase_state>
- Total Tests: 2,180
- Currently Passing: 2,069 (94.9%)
- Failing: 104
- Errors: 7
- Last Bug Bash: 2025-12-20
</codebase_state>

<key_files>
- CLI Entry: `swarm_attack/cli/` (modular CLI)
- Orchestrator: `swarm_attack/orchestrator.py`
- Verifier: `swarm_attack/agents/verifier.py`
- Recovery: `swarm_attack/chief_of_staff/recovery.py`
- State Store: `swarm_attack/state_store.py`
</key_files>
</background_context>

---

## Bug Fixes Required

<bug id="1" severity="critical" category="security">
<title>Path Traversal Vulnerability in Feature Init</title>

<description>
`swarm-attack init "../../../../etc/passwd"` creates files outside project directory.
</description>

<reproduction>
```bash
swarm-attack init "../../../../etc/passwd"
# Creates: /Users/philipjcortes/etc/passwd.md (ESCAPED PROJECT DIR)
```
</reproduction>

<affected_files>
- `swarm_attack/cli/feature_commands.py` (or legacy `cli.py`)
- `swarm_attack/orchestrator.py`
</affected_files>

<interface_contract>
```python
# Add to swarm_attack/validation/feature_name.py (new file)
import re
from pathlib import Path

class FeatureNameValidationError(ValueError):
    """Raised when feature name is invalid."""
    pass

def validate_feature_name(name: str) -> str:
    """
    Validate and sanitize feature name.

    Args:
        name: Raw feature name from user input

    Returns:
        Sanitized feature name

    Raises:
        FeatureNameValidationError: If name is invalid
    """
    pass

def is_path_within_project(path: Path, project_root: Path) -> bool:
    """
    Check if resolved path stays within project directory.

    Returns:
        True if path is safe, False if it escapes project root
    """
    pass
```
</interface_contract>

<acceptance_criteria>
- [ ] Rejects feature names containing `..`
- [ ] Rejects feature names containing path separators (`/`, `\`)
- [ ] Rejects empty or whitespace-only names
- [ ] Returns sanitized name (alphanumeric, hyphens, underscores only)
- [ ] CLI shows clear error message for invalid names
- [ ] Existing valid feature names still work
</acceptance_criteria>

<test_file>tests/unit/test_feature_name_validation.py</test_file>
</bug>

---

<bug id="2" severity="critical" category="data_corruption">
<title>Corrupted Test File with LLM Output</title>

<description>
`tests/generated/chief-of-staff-v3/test_issue_29.py` contains raw LLM output at line 564.
</description>

<reproduction>
```bash
PYTHONPATH=. pytest tests/generated/chief-of-staff-v3/test_issue_29.py
# SyntaxError: invalid syntax at line 564
```
</reproduction>

<affected_files>
- `tests/generated/chief-of-staff-v3/test_issue_29.py`
</affected_files>

<fix_approach>
1. Read the corrupted file
2. Identify the LLM output contamination (starts with "Now I'll output...")
3. Remove the contaminated section
4. Verify file is valid Python syntax
5. Run tests to ensure they pass
</fix_approach>

<acceptance_criteria>
- [ ] File contains only valid Python code
- [ ] No LLM prose/explanation text in file
- [ ] File passes `python -m py_compile` check
- [ ] Tests in file pass when run
</acceptance_criteria>
</bug>

---

<bug id="3" severity="high" category="functional">
<title>Empty Feature Name Creates Invalid State</title>

<description>
`swarm-attack init ""` creates a feature with empty name, producing `.claude/prds/.md`.
</description>

<reproduction>
```bash
swarm-attack init ""
# Creates: .claude/prds/.md
# Status shows: "Feature: " (empty)
```
</reproduction>

<affected_files>
- `swarm_attack/cli/feature_commands.py`
- `swarm_attack/validation/feature_name.py` (from Bug #1)
</affected_files>

<acceptance_criteria>
- [ ] Empty string rejected with clear error
- [ ] Whitespace-only names rejected
- [ ] Names with only special characters rejected
- [ ] Minimum length: 1 alphanumeric character
</acceptance_criteria>

<note>This is addressed by Bug #1's validation - ensure tests cover empty case.</note>
</bug>

---

<bug id="4" severity="high" category="functional">
<title>Missing _check_duplicate_classes Method</title>

<description>
`VerifierAgent` is missing the `_check_duplicate_classes` method that tests expect.
</description>

<reproduction>
```bash
PYTHONPATH=. pytest tests/unit/test_verifier_schema_drift.py -v
# AttributeError: 'VerifierAgent' object has no attribute '_check_duplicate_classes'
```
</reproduction>

<affected_files>
- `swarm_attack/agents/verifier.py`
</affected_files>

<interface_contract>
```python
# Add to VerifierAgent class in swarm_attack/agents/verifier.py
def _check_duplicate_classes(
    self,
    new_classes: dict[str, list[str]],  # {filepath: [class_names]}
    registry: dict[str, str]  # {class_name: filepath}
) -> list[dict]:
    """
    Check for duplicate class definitions across files.

    Args:
        new_classes: Newly defined classes from current implementation
        registry: Existing class registry from previous implementations

    Returns:
        List of conflict dicts: [{"class": name, "existing": path, "new": path}]
    """
    pass
```
</interface_contract>

<pattern_reference>
See existing `_extract_classes_from_output` method in same file for patterns.
</pattern_reference>

<acceptance_criteria>
- [ ] Method exists on VerifierAgent
- [ ] Returns empty list when no conflicts
- [ ] Detects duplicate class names across different files
- [ ] Returns conflict details with both file paths
- [ ] All tests in `test_verifier_schema_drift.py` pass
</acceptance_criteria>

<test_file>tests/unit/test_verifier_schema_drift.py</test_file>
</bug>

---

<bug id="5" severity="high" category="functional">
<title>Missing BACKOFF_SECONDS Export</title>

<description>
Tests expect `BACKOFF_SECONDS` but module has `DEFAULT_BACKOFF_BASE_SECONDS`.
</description>

<reproduction>
```bash
PYTHONPATH=. pytest tests/generated/chief-of-staff-v2/test_issue_13.py
# ImportError: cannot import name 'BACKOFF_SECONDS' from 'swarm_attack.chief_of_staff.recovery'
```
</reproduction>

<affected_files>
- `swarm_attack/chief_of_staff/recovery.py`
</affected_files>

<fix_approach>
Add alias export:
```python
# At module level in recovery.py
BACKOFF_SECONDS = DEFAULT_BACKOFF_BASE_SECONDS
```

Or update `__all__` to include the alias.
</fix_approach>

<acceptance_criteria>
- [ ] `BACKOFF_SECONDS` is importable from recovery module
- [ ] Existing `DEFAULT_BACKOFF_BASE_SECONDS` still works
- [ ] Tests in `test_issue_13.py` pass
</acceptance_criteria>
</bug>

---

<bug id="6" severity="high" category="functional">
<title>COS Phase 8 Recovery Tests Failing</title>

<description>
16 tests in `test_cos_phase8_recovery_issue_7.py` are failing due to RecoveryManager integration issues.
</description>

<reproduction>
```bash
PYTHONPATH=. pytest tests/generated/cos-phase8-recovery/test_cos_phase8_recovery_issue_7.py -v
# 16 failures related to RecoveryManager
```
</reproduction>

<affected_files>
- `swarm_attack/chief_of_staff/recovery.py`
- `swarm_attack/chief_of_staff/autopilot_runner.py`
</affected_files>

<investigation_required>
1. Read the failing test file to understand expected behavior
2. Compare with actual RecoveryManager implementation
3. Identify interface mismatches
4. Fix either tests or implementation (prefer fixing implementation)
</investigation_required>

<acceptance_criteria>
- [ ] All 16 tests in `test_cos_phase8_recovery_issue_7.py` pass
- [ ] RecoveryManager integrates correctly with AutopilotRunner
- [ ] Episode logging works during goal execution
- [ ] HICCUP checkpoints created on fatal errors
</acceptance_criteria>
</bug>

---

<bug id="7" severity="high" category="functional">
<title>External Dashboard Missing Implementation</title>

<description>
6 tests failing for `get_user_login_history` function that doesn't exist.
</description>

<reproduction>
```bash
PYTHONPATH=. pytest tests/generated/external-dashboard/test_external_dashboard_issue_2.py -v
# 6 failures - function not implemented
```
</reproduction>

<affected_files>
- `swarm_attack/external_dashboard/` (may need to create)
</affected_files>

<interface_contract>
```python
# swarm_attack/external_dashboard/user_history.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class UserLoginHistory:
    timestamps: list[datetime]  # Descending order
    last_active: datetime
    total_actions: int

def get_user_login_history(user_id: str, db_connection) -> Optional[UserLoginHistory]:
    """
    Get login history for a user.

    Args:
        user_id: User identifier
        db_connection: Database connection for auth_logs table

    Returns:
        UserLoginHistory if user exists, None otherwise
    """
    pass
```
</interface_contract>

<acceptance_criteria>
- [ ] Returns timestamps in descending order
- [ ] Returns last_active timestamp
- [ ] Returns total_actions count
- [ ] Returns None for nonexistent user
- [ ] Queries auth_logs table
- [ ] Filters by user_id
</acceptance_criteria>

<test_file>tests/generated/external-dashboard/test_external_dashboard_issue_2.py</test_file>
</bug>

---

## TDD Protocol

<tdd_protocol>
<phase name="RED" order="1">
**For each bug, TestEngineer does:**

1. Read existing test file (if exists) or create new one
2. Write/verify tests cover ALL acceptance criteria
3. Run tests - they MUST FAIL initially
4. Commit failing tests: `git add tests/ && git commit -m "RED: Add failing tests for Bug #N"`

```bash
# Example for Bug #1
PYTHONPATH=. pytest tests/unit/test_feature_name_validation.py -v
# Expected: FAILURES (tests written, implementation missing)
```
</phase>

<phase name="GREEN" order="2">
**Coder implements minimal fix:**

1. Read the failing tests carefully
2. Implement ONLY what's needed to pass tests
3. Run tests after each change
4. Iterate until all tests pass

```bash
# Run specific bug's tests
PYTHONPATH=. pytest tests/unit/test_feature_name_validation.py -v
# Expected: ALL PASS
```
</phase>

<phase name="REFACTOR" order="3">
**Integrator verifies no regressions:**

1. Run full test suite
2. Fix any regressions introduced
3. Ensure code quality (no hardcoded values, follows patterns)

```bash
# Full test suite
PYTHONPATH=. pytest tests/ -v --tb=short
# Expected: 2180+ tests, all passing
```
</phase>

<phase name="COMMIT" order="4">
**Reviewer creates commit:**

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: Bug #N - [brief description]

- Implemented [what was done]
- Added tests for [what's tested]
- Fixes: [issue reference]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```
</phase>
</tdd_protocol>

---

## Execution Order

<execution_order>
| Order | Bug ID | Reason |
|-------|--------|--------|
| 1 | Bug #2 | Quick fix - just clean corrupted file |
| 2 | Bug #1 + #3 | Security + validation (same fix) |
| 3 | Bug #5 | Quick alias addition |
| 4 | Bug #4 | Add missing method |
| 5 | Bug #7 | Implement missing feature |
| 6 | Bug #6 | Complex integration fix (last) |
</execution_order>

---

## Success Criteria

<success_criteria>
After all fixes are applied:

```bash
# Must pass
PYTHONPATH=. pytest tests/ -v --tb=short

# Expected output
# ========================= test session starts ==========================
# collected 2180 items
# ...
# ========================= 2180 passed in X.XXs =========================
```

Additionally:
- [ ] No security vulnerabilities (path traversal blocked)
- [ ] No corrupted test files
- [ ] All imports work
- [ ] All interface contracts satisfied
- [ ] No regressions in existing functionality
</success_criteria>

---

## Constraints

<constraints>
- **TDD Required**: Write failing tests BEFORE implementing fixes
- **No Hardcoded Dates**: Use dynamic date helpers if dates needed
- **No Over-Engineering**: Fix ONLY what's broken
- **Pattern Matching**: Follow existing code patterns in each file
- **One Bug at a Time**: Complete full TDD cycle per bug before moving on
- **Commit After Each Bug**: Small, atomic commits
</constraints>

---

## Pattern References

<pattern_references>
| Pattern | Location | Use For |
|---------|----------|---------|
| CLI validation | `swarm_attack/cli/bug_commands.py:validate_bug_id()` | Bug #1 validation |
| Method addition | `swarm_attack/agents/verifier.py:_extract_classes_from_output()` | Bug #4 pattern |
| Module exports | `swarm_attack/chief_of_staff/__init__.py` | Bug #5 export pattern |
| Dataclass models | `swarm_attack/chief_of_staff/episodes.py:Episode` | Bug #7 model pattern |
</pattern_references>

---

<output_format>
After completing each bug fix, report:

```json
{
  "bug_id": 1,
  "status": "fixed",
  "files_modified": ["path/to/file.py"],
  "files_created": ["path/to/new_file.py"],
  "tests_added": 5,
  "tests_passing": true,
  "commit_hash": "abc1234"
}
```

After all bugs fixed:

```json
{
  "total_bugs_fixed": 7,
  "total_tests": 2185,
  "tests_passing": 2185,
  "pass_rate": "100%",
  "security_vulnerabilities": 0,
  "branch": "fix/bug-bash-2025-12-20"
}
```
</output_format>
