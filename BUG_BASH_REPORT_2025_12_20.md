# Bug Bash Report: Swarm Attack

**Date**: 2025-12-20
**Tester**: PM Bug Bash Agent
**Scope**: Full system testing - CLI, test suite, edge cases, security
**Duration**: ~45 minutes

## Executive Summary

- **Total Bugs Found**: 19
- **Critical**: 2
- **High**: 6
- **Medium**: 8
- **Low**: 3

### Top 3 Issues Requiring Immediate Attention

1. **BUG-1**: Path traversal vulnerability allows file creation outside project directory
2. **BUG-2**: Corrupted test file with LLM output leaked into Python code
3. **BUG-3**: Empty feature name creates invalid state and `.md` file

## Test Coverage

| Area | Status | Bugs Found |
|------|--------|------------|
| Test Suite | Tested | 7 |
| CLI Commands | Tested | 8 |
| Input Validation | Tested | 3 |
| Security | Tested | 1 |
| Chief of Staff | Tested | 4 |

## Detailed Bug Reports

---

### BUG-1: Path traversal vulnerability in feature init

**Severity**: Critical
**Category**: Security
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack init "../../../../etc/passwd"`
2. Check if file was created

**Expected Behavior:**
Feature name should be validated and rejected if it contains path traversal sequences.

**Actual Behavior:**
File created at `/Users/{user}/etc/passwd.md` - escaped project directory.

**Evidence:**
```
$ swarm-attack init "../../../../etc/passwd"
Created PRD template at:
/Users/philipjcortes/Desktop/swarm-attack/.claude/prds/../../../../etc/passwd.md

$ ls -la /Users/philipjcortes/etc/passwd.md
-rw-------@ 1 philipjcortes  staff  334 Dec 20 08:18 /Users/philipjcortes/etc/passwd.md
```

**Environment:**
- Component: `swarm_attack/cli.py` or `swarm_attack/orchestrator.py`
- Test command: `swarm-attack init "../../../../etc/passwd"`

**Suggested Fix:**
Sanitize feature names by rejecting or stripping path separators and `..` sequences.

---

### BUG-2: Corrupted test file with LLM output

**Severity**: Critical
**Category**: Data Corruption
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `pytest tests/generated/chief-of-staff-v3/test_issue_29.py`

**Expected Behavior:**
Test file should contain valid Python code.

**Actual Behavior:**
File contains raw LLM output at line 564:
```python
Now I'll output the implementation. Since I need to add a method to an existing file, I'll output the complete file with the new method added.
```

**Evidence:**
```
E     File "tests/generated/chief-of-staff-v3/test_issue_29.py", line 564
E       Now I'll output the implementation...
E   SyntaxError: invalid syntax
```

**Environment:**
- Component: `tests/generated/chief-of-staff-v3/test_issue_29.py`
- Test command: `PYTHONPATH=. pytest tests/`

**Suggested Fix:**
The coder agent or test writer agent failed to properly extract code from LLM response. Fix the output parsing logic.

---

### BUG-3: Empty feature name creates invalid state

**Severity**: High
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack init ""`
2. Check created files

**Expected Behavior:**
Should reject empty feature name with validation error.

**Actual Behavior:**
Creates feature with empty name, file `.claude/prds/.md`, and shows as "Feature: " in status.

**Evidence:**
```
$ swarm-attack init ""
Created feature:
Created PRD template at: /Users/.../Desktop/swarm-attack/.claude/prds/.md

$ swarm-attack status ""
╭──────────────── Feature:  ────────────────╮
│ Feature:                                  │
│ Phase: PRD Ready                          │
╰───────────────────────────────────────────╯
```

**Environment:**
- Component: `swarm_attack/cli.py`
- Test command: `swarm-attack init ""`

---

### BUG-4: Missing `_check_duplicate_classes` method

**Severity**: High
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `PYTHONPATH=. pytest tests/unit/test_verifier_schema_drift.py`

**Expected Behavior:**
Tests should find the method on VerifierAgent.

**Actual Behavior:**
`AttributeError: 'VerifierAgent' object has no attribute '_check_duplicate_classes'`

**Evidence:**
```
tests/unit/test_verifier_schema_drift.py:101: in test_no_conflicts_empty_registry
    conflicts = verifier._check_duplicate_classes(new_classes, registry)
E   AttributeError: 'VerifierAgent' object has no attribute '_check_duplicate_classes'
```

**Environment:**
- Component: `swarm_attack/agents/verifier.py`
- Test command: `PYTHONPATH=. pytest tests/unit/test_verifier_schema_drift.py -v`

---

### BUG-5: Missing `BACKOFF_SECONDS` export

**Severity**: High
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `PYTHONPATH=. pytest tests/generated/chief-of-staff-v2/test_issue_13.py`

**Expected Behavior:**
`BACKOFF_SECONDS` should be importable from recovery module.

**Actual Behavior:**
```
ImportError: cannot import name 'BACKOFF_SECONDS' from 'swarm_attack.chief_of_staff.recovery'
```

**Evidence:**
The module has `DEFAULT_BACKOFF_BASE_SECONDS` instead of `BACKOFF_SECONDS`.

**Environment:**
- Component: `swarm_attack/chief_of_staff/recovery.py`
- Test command: See above

**Suggested Fix:**
Either add `BACKOFF_SECONDS = DEFAULT_BACKOFF_BASE_SECONDS` alias or update tests.

---

### BUG-6: 27 test collection errors due to duplicate test file names

**Severity**: High
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `PYTHONPATH=. pytest tests/`

**Expected Behavior:**
All tests should be collected.

**Actual Behavior:**
27 collection errors due to duplicate module names across different directories (test_issue_1.py, test_issue_2.py, etc.)

**Evidence:**
```
import file mismatch:
imported module 'test_issue_10' has this __file__ attribute:
  .../tests/generated/chief-of-staff/test_issue_10.py
which is not the same as the test file we want to collect:
  .../tests/generated/chief-of-staff-v2/test_issue_10.py
```

**Environment:**
- Component: `tests/generated/*/`
- Test command: `PYTHONPATH=. pytest tests/`

**Suggested Fix:**
Add `__init__.py` with unique module paths or rename test files with feature prefix.

---

### BUG-7: Negative budget accepted by autopilot

**Severity**: Medium
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack cos autopilot --budget -10`

**Expected Behavior:**
Should reject negative budget with validation error.

**Actual Behavior:**
Accepts budget: "Budget: $-10.00"

**Environment:**
- Component: `swarm_attack/cli/chief_of_staff.py`
- Test command: `swarm-attack cos autopilot --budget -10`

---

### BUG-8: Negative duration accepted by autopilot

**Severity**: Medium
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack cos autopilot --duration -60`

**Expected Behavior:**
Should reject negative duration.

**Actual Behavior:**
Accepts and shows "Duration: -60"

**Environment:**
- Component: `swarm_attack/cli/chief_of_staff.py`
- Test command: `swarm-attack cos autopilot --duration -60`

---

### BUG-9: Bug init with empty values creates "bug-unknown" entry

**Severity**: Medium
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack bug init "" --id "" --test "" -e ""`

**Expected Behavior:**
Should validate required fields and reject empty values.

**Actual Behavior:**
Creates bug with ID `bug-unknown-{timestamp}`

**Evidence:**
```
Bug ID: bug-unknown-20251220161727
```

**Environment:**
- Component: `swarm_attack/cli/bug.py` (inferred)
- Test command: See above

---

### BUG-10: Negative issue number accepted

**Severity**: Medium
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack run --issue -1 chief-of-staff-v3`

**Expected Behavior:**
Should reject negative issue number.

**Actual Behavior:**
Attempts to run issue #-1, fails with confusing error message.

**Evidence:**
```
Issue: #-1
Error: Coder failed: Baseline check failed: 0 pre-existing test failure(s).
```

**Environment:**
- Component: `swarm_attack/orchestrator.py`
- Test command: See above

---

### BUG-11: Invalid discovery type silently ignored

**Severity**: Medium
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack cos discover --type invalid`

**Expected Behavior:**
Should show error about invalid type.

**Actual Behavior:**
Shows "Type: invalid" then returns no results silently.

**Environment:**
- Component: `swarm_attack/cli/chief_of_staff.py`
- Test command: `swarm-attack cos discover --type invalid`

---

### BUG-12: Standup ends with "Error during standup:" message

**Severity**: Medium
**Category**: UX
**Reproducibility**: Often

**Steps to Reproduce:**
1. Run `swarm-attack cos standup`
2. Let it prompt for goal selection

**Expected Behavior:**
Should complete gracefully or show full error message.

**Actual Behavior:**
Output ends with truncated "Error during standup:" (no error details shown).

**Environment:**
- Component: `swarm_attack/cli/chief_of_staff.py`
- Test command: `swarm-attack cos standup`

---

### BUG-13: `TestState` class name conflicts with pytest

**Severity**: Medium
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `PYTHONPATH=. pytest tests/`

**Expected Behavior:**
No collection warnings about production classes.

**Actual Behavior:**
```
PytestCollectionWarning: cannot collect test class 'TestState' because it has a __init__ constructor
```

**Evidence:**
`swarm_attack/chief_of_staff/state_gatherer.py:76` has `class TestState` (a production dataclass).

**Environment:**
- Component: `swarm_attack/chief_of_staff/state_gatherer.py`
- Test command: `PYTHONPATH=. pytest tests/`

**Suggested Fix:**
Rename `TestState` to `StateForTesting`, `TestingState`, or similar.

---

### BUG-14: Multiple similar class names causing pytest warnings

**Severity**: Low
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run pytest

**Expected Behavior:**
No warnings about production classes.

**Actual Behavior:**
Multiple warnings for classes named `Test*` including:
- `TestFailureDiscoveryAgent`
- `TestCritic`
- `TestValidationGate`
- `TestRunnerConfig`

**Environment:**
- Component: Multiple files in `swarm_attack/`
- Test command: `PYTHONPATH=. pytest tests/`

---

### BUG-15: Stale checkpoints not cleaned up

**Severity**: Low
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack cos checkpoints`

**Expected Behavior:**
Only shows relevant pending checkpoints.

**Actual Behavior:**
Shows 18+ duplicate "hiccup" checkpoints from Dec 18th, all with same goal and error.

**Environment:**
- Component: `swarm_attack/chief_of_staff/checkpoint_store.py`
- Test command: `swarm-attack cos checkpoints`

---

### BUG-16: Zero budget accepted by autopilot

**Severity**: Low
**Category**: UX
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack cos autopilot --budget 0`

**Expected Behavior:**
Should warn about zero budget or reject.

**Actual Behavior:**
Accepts: "Budget: $0.00"

**Environment:**
- Component: `swarm_attack/cli/chief_of_staff.py`
- Test command: `swarm-attack cos autopilot --budget 0`

---

### BUG-17: asyncio_default_fixture_loop_scope deprecation warning

**Severity**: Low
**Category**: Technical Debt
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run any pytest command

**Expected Behavior:**
No deprecation warnings.

**Actual Behavior:**
```
PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
```

**Environment:**
- Component: `pyproject.toml`
- Test command: Any pytest run

**Suggested Fix:**
Add `asyncio_default_fixture_loop_scope = "function"` to pytest config.

---

### BUG-18: Issue #-1 recorded in event log

**Severity**: Medium
**Category**: Data Integrity
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `swarm-attack run --issue -1 chief-of-staff-v3`
2. Check `swarm-attack events chief-of-staff-v3`

**Expected Behavior:**
Invalid issue numbers should not be logged.

**Actual Behavior:**
Event log shows `issue_started │  -1   │ session=sess_20251220...`

**Environment:**
- Component: `swarm_attack/event_logger.py`
- Test command: See above

---

### BUG-19: 42 test failures in test suite

**Severity**: High
**Category**: Functional
**Reproducibility**: Always

**Steps to Reproduce:**
1. Run `PYTHONPATH=. pytest tests/ --ignore=tests/generated/chief-of-staff-v2 --ignore=tests/generated/chief-of-staff-v3 --ignore=tests/generated/cos-phase8-recovery --ignore=tests/generated/external-dashboard`

**Expected Behavior:**
All tests pass.

**Actual Behavior:**
42 failures, 7 errors (722 passed).

**Evidence:**
Key failing test categories:
- Schema drift prevention tests (missing `_check_duplicate_classes`)
- Autopilot runner tests
- Goal tracker tests

**Environment:**
- Component: Various
- Test command: See above

---

## Areas Not Tested

- GitHub API integration (would require real GitHub token)
- Actual LLM calls (cost/time prohibitive)
- Multi-user scenarios
- Concurrent operations stress testing
- All bug fix/analyze workflows with real bugs

## Recommendations

### Must Fix Before Release

1. **BUG-1**: Path traversal vulnerability - SECURITY CRITICAL
2. **BUG-2**: Corrupted test file - development blocker
3. **BUG-3**: Empty feature name validation - data integrity
4. **BUG-6**: Test collection errors - CI/CD blocker

### Should Fix Soon

5. **BUG-4, BUG-5**: Missing methods/exports - spec mismatch
6. **BUG-7, BUG-8**: Negative value validation
7. **BUG-10**: Negative issue number validation
8. **BUG-13**: Rename production `Test*` classes

### Nice to Have

9. **BUG-15**: Clean up stale checkpoints
10. **BUG-14**: Rename conflicting class names
11. **BUG-17**: Fix asyncio deprecation warning

## Appendix: Test Commands Used

```bash
# Run test suite
PYTHONPATH=. pytest tests/ -v --tb=short

# Run tests excluding problem directories
PYTHONPATH=. pytest tests/ --ignore=tests/generated/chief-of-staff-v2 \
  --ignore=tests/generated/chief-of-staff-v3 \
  --ignore=tests/generated/cos-phase8-recovery \
  --ignore=tests/generated/external-dashboard -v

# CLI tests
swarm-attack --help
swarm-attack status
swarm-attack init ""
swarm-attack init "../../../../etc/passwd"
swarm-attack run "nonexistent-feature"
swarm-attack run --issue -1 chief-of-staff-v3
swarm-attack cos standup
swarm-attack cos autopilot --budget -10
swarm-attack cos autopilot --budget 0
swarm-attack cos autopilot --duration -60
swarm-attack cos discover --type invalid
swarm-attack cos checkpoints
swarm-attack bug init "" --id "" --test "" -e ""
swarm-attack bug list
swarm-attack greenlight ""

# Search for missing exports
grep -r "BACKOFF_SECONDS" swarm_attack/
grep -r "_check_duplicate_classes" swarm_attack/
```

---

*Generated by PM Bug Bash Agent*
