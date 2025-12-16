# Fix Plan: Coder Agent TDD and Multi-Language Support Bugs

**Date:** 2025-12-16
**Author:** Claude (automated analysis)
**Status:** Draft - Awaiting Approval

---

## Executive Summary

Four critical bugs were discovered in the Swarm Attack coder pipeline that prevent proper TDD workflow execution and multi-language project support. The bugs share a common root cause: the coder was designed to receive pre-written tests but the SKILL.md documents a TDD workflow where the coder writes tests itself.

**Priority Order:**
1. BUG-001: Test file pre-existence requirement (Critical - blocks all new issues)
2. BUG-002: Python tests for non-Python projects (Critical - incorrect test type)
3. BUG-003: Missing test files for backlog issues (Resolved by fixing BUG-001)
4. BUG-004: Manual task classification (Moderate - causes false failures)

---

## Bug Analysis

### BUG-001: Coder Requires Pre-existing Test File

**Severity:** Critical
**Impact:** Blocks ALL new issues from being implemented

#### Root Cause Flow

```
User runs: swarm-attack run hello-counter --issue 7

orchestrator.py:run_issue_session()
  └── _run_implementation_cycle() [line 1288-1354]
      └── CoderAgent.run() [line 634-860]
          └── Line 681-684: FAILS HERE
              if not file_exists(test_path):
                  error = f"Test file not found at {test_path}"
                  return AgentResult.failure_result(error)
```

#### Contradiction Analysis

**What SKILL.md says (lines 54-56):**
```
### Phase 2: Write Tests First (RED)
Create test file: `tests/generated/{feature}/test_issue_{N}.py`
```

**What coder.py does (lines 681-684):**
```python
if not file_exists(test_path):
    error = f"Test file not found at {test_path}"
    return AgentResult.failure_result(error)
```

The skill describes TDD where the coder CREATES tests, but the code REQUIRES tests to exist.

#### Why This Happened

The coder was originally designed for a **thin-agent pipeline** where:
1. A separate TestWriter agent would create tests
2. The coder would just implement code to pass those tests

When converted to **thick-agent architecture**, the skill was updated to describe TDD but the code check was not removed.

---

### BUG-002: Python Tests for Flutter/Dart Projects

**Severity:** Critical
**Impact:** Tests don't verify actual Flutter functionality

#### Root Cause Flow

```
coder.py:_get_default_test_path() [line 141-144]
  └── Always returns: tests/generated/{feature}/test_issue_{N}.py
      └── Extension is ALWAYS .py regardless of project type

coder.py:_build_prompt() [line 493-497]
  └── Always shows Python code fence:
      ```python
      {test_content}
      ```
```

#### Detection vs Usage Gap

The coder DOES detect project type at `_detect_project_type()` (lines 339-363):
```python
if "flutter" in combined or ".dart" in combined or "pubspec.yaml" in combined:
    return {
        "type": "Flutter/Dart",
        "source_dir": "lib/",
        "file_ext": ".dart",
        ...
    }
```

But this detection result is ONLY used for:
- `project_info['type']` in prompt context
- Directory structure hints

NOT used for:
- Test file extension
- Test content format
- Verifier test command

---

### BUG-003: Missing Test Files for Later Issues

**Severity:** Moderate (resolved by fixing BUG-001)

#### Root Cause

This is a direct consequence of BUG-001:
1. Issue 1 runs → coder creates test + implementation → marked DONE
2. Issues 2-6 follow the same pattern
3. Issue 7 runs → requires test_issue_7.py → FAILS (doesn't exist yet)

Test files are only created as OUTPUT of successful coder runs. The chicken-and-egg problem means issues that haven't run yet have no tests.

---

### BUG-004: Manual Tasks Cannot Be Automated

**Severity:** Moderate
**Impact:** Manual verification tasks fail or block incorrectly

#### Root Cause

`issue_creator.py` generates issues without classifying them by automation capability. Issues 8-9 in hello-counter are:
- "Verify app on iOS simulator" (requires human + simulator)
- "Verify app on Android emulator" (requires human + emulator)

These cannot be automated but the orchestrator treats them identically to code tasks.

---

## Fix Design

### Fix 1: Remove Test Pre-existence Check (BUG-001)

**Approach:** Make test file optional - coder creates tests if missing.

**File:** `swarm_attack/agents/coder.py`

**Changes:**

1. **Remove the existence check** (lines 681-684):
```python
# BEFORE (delete this block):
if not file_exists(test_path):
    error = f"Test file not found at {test_path}"
    self._log("coder_error", {"error": error}, level="error")
    return AgentResult.failure_result(error)

# AFTER: Remove entirely - coder will create tests if missing
```

2. **Handle missing test content** (around line 686-692):
```python
# Read test file content IF IT EXISTS
test_content = ""
if file_exists(test_path):
    try:
        test_content = read_file(test_path)
    except Exception as e:
        # Log but don't fail - we can still generate tests
        self._log("coder_warning", {
            "warning": f"Could not read existing test file: {e}"
        }, level="warning")
```

3. **Update prompt to handle no-test case** (in `_build_prompt()`):
```python
# Add conditional test section
if test_content:
    test_section = f"""
**Test File Content (your implementation must make these tests pass):**

```{code_fence_lang}
{test_content}
```
"""
else:
    test_section = """
**No Test File Found - You Must Create Tests First**

Following TDD principles:
1. Create test file at: {test_path}
2. Write failing tests that verify the acceptance criteria
3. Implement code to make tests pass

Your test file MUST be included in your output using:
# FILE: {test_path}
"""
```

4. **Ensure test file is written** (in file output section):
   - The existing `_parse_file_outputs()` already handles `# FILE:` markers
   - Coder's LLM output will include test files when prompted

**Why This Works:**
- Existing issues with test files: Coder reads them, implements code
- New issues without test files: Coder creates tests + implements code
- Maintains thick-agent TDD workflow as documented in SKILL.md

---

### Fix 2: Multi-Language Test Support (BUG-002)

**Approach:** Make test paths and verification project-type aware.

**Files:**
- `swarm_attack/agents/coder.py`
- `swarm_attack/agents/verifier.py`
- `swarm_attack/config.py`

**Changes:**

#### 2A: Add ProjectType dataclass to config.py

```python
from enum import Enum, auto

class ProjectType(Enum):
    PYTHON = auto()
    FLUTTER = auto()
    NODEJS = auto()
    UNKNOWN = auto()

@dataclass
class ProjectTypeInfo:
    """Project type detection and configuration."""
    type: ProjectType
    source_dir: str
    test_dir: str
    test_ext: str
    test_command: str
    code_fence: str

    @classmethod
    def python(cls) -> "ProjectTypeInfo":
        return cls(
            type=ProjectType.PYTHON,
            source_dir="src/",
            test_dir="tests/generated",
            test_ext=".py",
            test_command="pytest",
            code_fence="python",
        )

    @classmethod
    def flutter(cls) -> "ProjectTypeInfo":
        return cls(
            type=ProjectType.FLUTTER,
            source_dir="lib/",
            test_dir="test",  # Flutter convention
            test_ext=".dart",
            test_command="flutter test",
            code_fence="dart",
        )

    @classmethod
    def nodejs(cls) -> "ProjectTypeInfo":
        return cls(
            type=ProjectType.NODEJS,
            source_dir="src/",
            test_dir="tests",
            test_ext=".ts",
            test_command="npm test",
            code_fence="typescript",
        )
```

#### 2B: Update coder.py test path generation

```python
def _get_default_test_path(self, feature_id: str, issue_number: int, project_info: Optional[ProjectTypeInfo] = None) -> Path:
    """Get the default path for generated tests."""
    if project_info is None:
        # Default to Python
        test_ext = ".py"
        test_dir = "tests/generated"
    else:
        test_ext = project_info.test_ext
        test_dir = project_info.test_dir

    tests_dir = Path(self.config.repo_root) / test_dir / feature_id
    return tests_dir / f"test_issue_{issue_number}{test_ext}"
```

#### 2C: Update prompt code fence language

```python
def _build_prompt(self, ...):
    # Use detected project type for code fence
    code_fence_lang = project_info.code_fence if project_info else "python"

    # In test content section:
    f"""```{code_fence_lang}
{test_content}
```"""
```

#### 2D: Update verifier.py to use project-aware test command

```python
def _run_tests(self, test_path: Path, project_info: ProjectTypeInfo) -> tuple[int, str]:
    """Run tests using appropriate command for project type."""
    if project_info.type == ProjectType.FLUTTER:
        cmd = ["flutter", "test", str(test_path)]
    elif project_info.type == ProjectType.NODEJS:
        cmd = ["npm", "test", "--", str(test_path)]
    else:
        cmd = ["pytest", str(test_path), "-v", "--tb=short"]

    # ... existing subprocess logic
```

---

### Fix 3: Manual Task Classification (BUG-004)

**Approach:** Add issue classification during creation and skip manual tasks.

**Files:**
- `swarm_attack/agents/issue_creator.py`
- `swarm_attack/orchestrator.py`
- `.claude/skills/issue-creator/SKILL.md` (update prompt)

**Changes:**

#### 3A: Update issue schema

Add `automation_type` field to issues:
```python
# In issue_creator.py _build_prompt():
{
  "title": "...",
  "body": "...",
  "labels": [...],
  "estimated_size": "small|medium|large",
  "dependencies": [],
  "order": 1,
  "automation_type": "automated|manual|hybrid"  # NEW FIELD
}
```

#### 3B: Update issue validation

```python
def _validate_issues(self, data: dict[str, Any]) -> list[str]:
    # Add validation for automation_type
    valid_automation_types = {"automated", "manual", "hybrid"}
    for issue in issues:
        auto_type = issue.get("automation_type", "automated")
        if auto_type not in valid_automation_types:
            errors.append(f"Issue {i + 1} invalid automation_type: {auto_type}")
```

#### 3C: Update orchestrator to skip manual tasks

```python
def run_issue_session(self, feature_id: str, issue_number: Optional[int] = None):
    # ... existing code ...

    # After loading issue, check automation type
    issue = self._find_issue(issues_data, issue_number)
    automation_type = issue.get("automation_type", "automated")

    if automation_type == "manual":
        # Mark as requiring manual verification
        self._mark_task_manual(feature_id, issue_number)
        return IssueSessionResult(
            status="manual_required",
            issue_number=issue_number,
            # ...
            error="Issue requires manual verification"
        )
```

#### 3D: Add auto-detection keywords

In `issue_creator.py`:
```python
MANUAL_KEYWORDS = [
    "manually test",
    "visual inspection",
    "verify on simulator",
    "verify on emulator",
    "user acceptance",
    "qa review",
]

def _detect_automation_type(self, issue_body: str) -> str:
    """Detect if issue requires manual work."""
    body_lower = issue_body.lower()
    for keyword in self.MANUAL_KEYWORDS:
        if keyword in body_lower:
            return "manual"
    return "automated"
```

---

## Implementation Order

### Phase 1: Fix BUG-001 (Critical Path)

1. Remove test file existence check in `coder.py:681-684`
2. Add conditional test content handling
3. Update prompt to handle no-test case
4. Update SKILL.md to clarify test creation responsibility
5. Test with hello-counter issue 7

**Files Modified:**
- `swarm_attack/agents/coder.py` (lines 681-692, 493-497)
- `.claude/skills/coder/SKILL.md` (clarify test creation)

**Estimated Changes:** ~50 lines

### Phase 2: Fix BUG-002 (Multi-Language)

1. Add `ProjectTypeInfo` to config.py
2. Update `_detect_project_type()` to return `ProjectTypeInfo`
3. Update `_get_default_test_path()` to use project type
4. Update prompt code fence language
5. Update verifier.py to use project-aware commands
6. Test with Flutter project

**Files Modified:**
- `swarm_attack/config.py` (+30 lines)
- `swarm_attack/agents/coder.py` (~40 lines)
- `swarm_attack/agents/verifier.py` (~30 lines)

**Estimated Changes:** ~100 lines

### Phase 3: Fix BUG-004 (Manual Tasks)

1. Update issue schema with `automation_type`
2. Add keyword-based detection
3. Update orchestrator to handle manual tasks
4. Add new `TaskStage.MANUAL_REQUIRED` state
5. Test with hello-counter issues 8-9

**Files Modified:**
- `swarm_attack/agents/issue_creator.py` (~30 lines)
- `swarm_attack/orchestrator.py` (~20 lines)
- `swarm_attack/models/__init__.py` (+1 enum value)

**Estimated Changes:** ~50 lines

---

## Test Plan

### Unit Tests

1. **test_coder_creates_tests_when_missing.py**
   - Test coder runs without pre-existing test file
   - Verify test file is included in output
   - Verify implementation works with generated tests

2. **test_project_type_detection.py**
   - Test Flutter detection from pubspec.yaml
   - Test Node.js detection from package.json
   - Test Python detection (default)

3. **test_test_path_generation.py**
   - Verify Python tests go to `tests/generated/{feature}/test_issue_N.py`
   - Verify Flutter tests go to `test/{feature}/test_issue_N.dart`

4. **test_manual_task_classification.py**
   - Test keyword detection for manual tasks
   - Test orchestrator skip behavior

### Integration Tests

1. **test_flutter_tdd_workflow.py**
   - Run full TDD cycle on Flutter project
   - Verify Dart tests are generated
   - Verify `flutter test` command is used

2. **test_python_backward_compat.py**
   - Ensure existing Python project workflow unchanged
   - Run on chief-of-staff or similar Python feature

### Manual Verification

1. Run `swarm-attack run hello-counter --issue 7` in test environment
2. Verify test file `test_issue_7.py` is created
3. Verify implementation passes tests
4. Check issues 8-9 are marked as manual

---

## Rollback Plan

### If Phase 1 causes issues:
```bash
# Revert coder.py changes
git checkout HEAD~1 -- swarm_attack/agents/coder.py
```

### If Phase 2 causes issues:
```bash
# Revert all phase 2 files
git checkout HEAD~1 -- swarm_attack/agents/coder.py swarm_attack/agents/verifier.py swarm_attack/config.py
```

### Feature Flag Option:
Add `allow_test_creation: bool = True` to config.yaml to toggle behavior:
```python
if self.config.sessions.allow_test_creation and not file_exists(test_path):
    # Create tests
else:
    # Require existing tests (legacy behavior)
```

---

## Success Criteria

After all fixes:

- [ ] `swarm-attack run hello-counter --issue 7` succeeds in test environment
- [ ] Test file `test_issue_7.py` is created by coder
- [ ] Flutter projects get `.dart` test files in `test/` directory
- [ ] Flutter verifier runs `flutter test` not `pytest`
- [ ] Manual tasks (issues 8-9) are marked appropriately
- [ ] Existing Python workflows continue working
- [ ] All existing tests pass (`pytest tests/`)

---

## Files to Modify Summary

| File | Changes | Lines |
|------|---------|-------|
| `swarm_attack/agents/coder.py` | Remove check, add test creation flow | ~60 |
| `swarm_attack/agents/verifier.py` | Add project-aware test command | ~30 |
| `swarm_attack/config.py` | Add ProjectTypeInfo | ~30 |
| `swarm_attack/agents/issue_creator.py` | Add automation_type | ~30 |
| `swarm_attack/orchestrator.py` | Handle manual tasks | ~20 |
| `swarm_attack/models/__init__.py` | Add MANUAL_REQUIRED stage | ~5 |
| `.claude/skills/coder/SKILL.md` | Clarify test responsibility | ~10 |

**Total Estimated Changes:** ~185 lines

---

## Appendix: Code Snippets for Reference

### Current Test Check (to remove)
```python
# swarm_attack/agents/coder.py:681-684
if not file_exists(test_path):
    error = f"Test file not found at {test_path}"
    self._log("coder_error", {"error": error}, level="error")
    return AgentResult.failure_result(error)
```

### Current Test Path Generation (to modify)
```python
# swarm_attack/agents/coder.py:141-144
def _get_default_test_path(self, feature_id: str, issue_number: int) -> Path:
    tests_dir = Path(self.config.repo_root) / "tests" / "generated" / feature_id
    return tests_dir / f"test_issue_{issue_number}.py"
```

### Current Project Detection (to enhance)
```python
# swarm_attack/agents/coder.py:339-363
def _detect_project_type(self, spec_content: str, test_content: str) -> dict[str, str]:
    combined = spec_content.lower() + test_content.lower()
    if "flutter" in combined or ".dart" in combined or "pubspec.yaml" in combined:
        return {
            "type": "Flutter/Dart",
            "source_dir": "lib/",
            "file_ext": ".dart",
            ...
        }
```
