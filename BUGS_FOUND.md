# Bugs Found During Manual Testing

**Test Date:** 2025-12-16
**Tester:** QA Engineer (Claude)
**Swarm Version:** agents-cutover branch
**Test Directory:** /tmp/swarm-test-*

---

## Summary

| Bug ID | Severity | Phase | Status | Description |
|--------|----------|-------|--------|-------------|
| BUG-001 | High | Implementation | OPEN | Verifier has blocking test file check (verifier.py:453-456) |
| BUG-002 | Low | Documentation | CONFIRMED | Test guide uses outdated API (guide is outdated) |

---

## Correct CLI Usage (From Code Analysis)

```bash
# Correct way to run swarm against a different project directory:
python -m swarm_attack --project /path/to/project run my-feature --issue 1

# Or using short form:
python -m swarm_attack -p /path/to/project run my-feature -i 1

# Import path:
from swarm_attack.orchestrator import Orchestrator  # NOT SwarmOrchestrator
from swarm_attack.config import load_config, SwarmConfig
```

---

## Integration Test Results

### Manual Task Detection (PASS)

**Test Issue 2** (explicit `automation_type: "manual"` in issues.json):
```
✓ PASS - System correctly rejects with message:
"Issue #2 requires manual verification and cannot be automated.
 Title: Visual QA review.
 Mark this task as MANUAL_REQUIRED or complete it manually."
```

**Test Issue 3** (no `automation_type` field):
```
Result: Attempted to run coder (failed due to missing skill file)
Note: Keyword detection only happens during IssueCreatorAgent (issue generation),
      not during runtime. The automation_type must be set in issues.json.
```

**Conclusion:** Manual task rejection works correctly when `automation_type: "manual"` is set in issues.json.

---

## Detailed Bug Reports

### BUG-001: Verifier Has Blocking Test File Check (When Coder Creates Tests)

**Severity:** High
**Phase:** Implementation / Verification
**Reproducible:** Yes

**Description:**
While the coder agent was updated to support TDD mode (creating tests when they don't exist), the verifier agent (`swarm_attack/agents/verifier.py`) still has a blocking check that fails if test files don't exist.

**Location:**
`swarm_attack/agents/verifier.py:453-456`

**Code:**
```python
# Check if test file exists
if not file_exists(test_path):
    error = f"Test file not found at {test_path}"
    self._log("verifier_error", {"error": error}, level="error")
    return AgentResult.failure_result(error)
```

**Coder.py TDD Mode (Fixed):**
`swarm_attack/agents/coder.py:797-801` now logs:
```
"Test file not found - coder will create tests (TDD mode)"
```

**Expected Behavior:**
- Coder creates tests in TDD mode ✓ (FIXED)
- Verifier should handle case where coder created tests or expect tests to exist after coder runs

**Actual Behavior:**
- If verifier runs before tests are created, it fails with "Test file not found"
- This may cause race conditions in the pipeline

**Suggested Fix:**
Either:
1. Ensure verifier only runs after coder has committed test files
2. Add a similar TDD-aware check in verifier that doesn't fail when tests don't exist yet

---

### BUG-002: Test Guide References Non-Existent `--repo-root` CLI Option

**Severity:** Low (Documentation)
**Phase:** Documentation
**Reproducible:** Yes

**Description:**
The test guide references `--repo-root` CLI option that doesn't exist.

**Guide Says:**
```bash
PYTHONPATH=. python -m swarm_attack run manual-test --issue 2 --repo-root "$MANUAL_TEST_DIR"
```

**Actual CLI:**
```bash
# Global option is -p / --project
python -m swarm_attack -p /path/to/project run feature_id --issue 1
```

**Evidence:**
```
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ No such option: --repo-root                                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

**Suggested Fix:**
Update test guide to use `-p` or `--project` global option instead of `--repo-root`.

---

### BUG-003: Test Guide References Wrong Class Name

**Severity:** Low (Documentation)
**Phase:** Documentation
**Reproducible:** Yes

**Description:**
The test guide references `SwarmOrchestrator` class which doesn't exist.

**Guide Says:**
```python
from swarm_attack.orchestrator import SwarmOrchestrator
```

**Actual Code:**
```python
from swarm_attack.orchestrator import Orchestrator
```

**Evidence:**
```
ImportError: cannot import name 'SwarmOrchestrator' from 'swarm_attack.orchestrator'
```

**Suggested Fix:**
Update test guide to use correct class name `Orchestrator`.

---

### BUG-004: Undocumented `SWARM_REPO_ROOT` Environment Variable

**Severity:** Medium (Documentation/Feature Gap)
**Phase:** Documentation
**Reproducible:** N/A

**Description:**
The test guide mentions setting `SWARM_REPO_ROOT` environment variable but this doesn't appear to be documented or consistently used.

**Guide Says:**
```bash
export SWARM_REPO_ROOT="$TEST_DIR"
```

**Actual Behavior:**
The CLI uses `-p` / `--project` option or defaults to current working directory. The environment variable behavior is unclear.

**Suggested Fix:**
Either:
1. Document the `SWARM_REPO_ROOT` env var if it's supported
2. Remove from test guide if not supported
3. Implement if desired for CI/CD use cases

---

## Test Results Summary

### Unit Tests Passed

| Test | Result |
|------|--------|
| Project Type Detection (Python) | ✓ PASS |
| Project Type Detection (Flutter/Dart) | ✓ PASS |
| Project Type Detection (Node.js/TypeScript) | ✓ PASS |
| Manual Task Detection ("QA review") | ✓ PASS |
| Manual Task Detection ("verify on simulator") | ✓ PASS |
| Manual Task Detection ("visual inspection") | ✓ PASS |
| Manual Task Detection ("implement function" = automated) | ✓ PASS |
| TaskStage.MANUAL_REQUIRED exists | ✓ PASS |
| TDD mode implemented in coder | ✓ PASS |

### Known Working Features

1. **Project Type Detection** - Correctly identifies Python, Flutter/Dart, and Node.js projects based on spec content
2. **Manual Task Detection** - `_detect_automation_type()` correctly identifies manual tasks by keywords
3. **TaskStage Enum** - Includes MANUAL_REQUIRED stage for manual verification tasks
4. **TDD Mode (Coder)** - Coder logs TDD mode when test files don't exist

### Needs Integration Testing

1. Full pipeline: PRD → Spec → Issues → Code (requires LLM calls)
2. TDD mode end-to-end (coder creates tests, verifier validates)
3. Manual task rejection flow (orchestrator behavior)

---

## Recommendations

1. **Update Documentation** - Sync test guide with actual CLI options and class names
2. **Fix Verifier TDD Handling** - Ensure verifier doesn't fail when tests were just created by coder
3. **Add Integration Tests** - Automated pytest tests for the scenarios in this guide
4. **Environment Variable Support** - Either document or implement `SWARM_REPO_ROOT` for CI/CD

---

## Test Environment

- **Platform:** macOS Darwin 24.6.0
- **Python:** 3.x
- **Branch:** agents-cutover
- **Swarm Attack Path:** /Users/philipjcortes/Desktop/swarm-attack
