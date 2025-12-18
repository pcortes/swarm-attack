# LLM Implementation Prompt: Fix Swarm Attack System

## Your Role

You are a team of expert software architects implementing critical fixes to the Swarm Attack multi-agent development system. The system currently has bugs that cause the CoderAgent to rewrite entire files instead of making targeted changes, wasting tokens and breaking existing tests.

## Expert Panel

Approach this task as these experts working together:

1. **Systems Architect** - Reviews overall design, ensures changes don't break existing flows
2. **Agent Expert** - Deep knowledge of LLM prompt engineering for code generation
3. **Testing Expert** - Ensures all changes are testable and don't introduce regressions
4. **Integration Expert** - Ensures all components work together after changes

## Instructions

1. **First, review each spec section** and identify any gaps, conflicts, or improvements
2. **Output your review** as a brief critique (max 200 words per section)
3. **Then implement** the changes, outputting complete file contents
4. **Run tests** after each major change to verify no regressions

---

## SPEC 1: Coder Agent Preservation (CRITICAL)

### Problem
The coder agent rewrites entire files instead of making targeted changes because:
- No "preserve existing code" instruction in SKILL.md
- Existing implementation only read on retry, not first attempt
- No distinction between "add" vs "replace" operations

### Changes Required

#### 1.1 Update `swarm_attack/skills/coder/SKILL.md`

Add this section after "## Interface Contracts (CRITICAL)":

```markdown
---

## PRESERVING EXISTING CODE (CRITICAL)

When modifying existing files, you MUST preserve working code. Rewriting entire files is **FORBIDDEN** except for initial creation.

### Rule 1: Read Before Write

**ALWAYS** check if the file already exists before outputting it:
1. Check if the file already exists
2. Identify which methods/classes need modification
3. Preserve all methods you are NOT changing

### Rule 2: Targeted Modifications Only

When fixing failing tests:
- **DO NOT** rewrite working methods
- **DO NOT** remove or replace code unrelated to the failing test
- **DO NOT** change function signatures unless tests require it
- **DO** make minimal, surgical changes to fix the specific failure

### Rule 3: Add vs Replace Operations

**ADD operation** (file does not exist):
- Create complete file with all required classes/functions

**MODIFY operation** (file already exists):
- Preserve ALL existing methods that are working
- Only modify the specific method/class causing the test failure

### Anti-Patterns to AVOID

```python
# WRONG - Rewriting entire file to fix one method
# FILE: src/auth/user.py
class User:
    # Completely rewritten from scratch, lost helper methods!
    def authenticate(self):
        return True

# CORRECT - Preserving existing code, modifying only what's needed
# FILE: src/auth/user.py
# Existing methods preserved
class User:
    def validate_email(self, email: str) -> bool:
        """PRESERVED - working method."""
        return "@" in email

    def authenticate(self, password: str) -> bool:
        """MODIFIED - fixed to handle empty password."""
        if not password:  # <-- FIX: added null check
            return False
        return self.check_password(password)
```

### Code Modification Checklist

Before outputting any file that already exists:
1. [ ] I read the existing file content
2. [ ] I identified ONLY the method(s) that need fixing
3. [ ] I preserved all other methods verbatim
4. [ ] I kept the same file structure/organization
5. [ ] I did NOT remove any working functionality
```

#### 1.2 Update `swarm_attack/agents/coder.py`

**Change 1: Read existing implementation on FIRST attempt (not just retries)**

Find this code around line 1123:
```python
existing_implementation: dict[str, str] = {}
if retry_number > 0:
    existing_implementation = self._read_existing_implementation(...)
```

Change to:
```python
# CRITICAL: Always read existing implementation to preserve working code
existing_implementation: dict[str, str] = {}
existing_implementation = self._read_existing_implementation(
    test_content, expected_modules
)
if existing_implementation:
    self._log("coder_existing_impl", {
        "retry_number": retry_number,
        "existing_files": list(existing_implementation.keys()),
        "total_existing_lines": sum(
            content.count('\n') for content in existing_implementation.values()
        ),
    })
```

**Change 2: Update `_format_existing_implementation` to add stronger warnings**

Update the method to include `is_first_attempt` parameter and show stronger warnings:
```python
def _format_existing_implementation(self, existing: dict[str, str], is_first_attempt: bool = True) -> str:
    if not existing:
        return ""

    if is_first_attempt:
        lines = [
            "## EXISTING IMPLEMENTATION (MUST PRESERVE)",
            "",
            "**WARNING: These files already exist in the codebase.**",
            "**DO NOT rewrite these files from scratch.**",
            "",
            "You MUST:",
            "1. Read and understand this existing code",
            "2. Keep ALL working methods intact",
            "3. Only ADD new methods or MODIFY specific broken methods",
            "",
        ]
    else:
        lines = [
            "## YOUR PREVIOUS IMPLEMENTATION (ITERATE, DON'T REWRITE)",
            "",
        ]
    # ... rest of method
```

**Change 3: Add overwrite detection logging**

In the file writing loop (around line 1192), add similarity check:
```python
if not is_new:
    existing_content = read_file(full_path)
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, existing_content, content).quick_ratio()

    if similarity < 0.5 and existing_content.count('\n') > 50:
        self._log("coder_large_overwrite_warning", {
            "file_path": file_path,
            "similarity_ratio": round(similarity, 2),
            "warning": "Large file being significantly rewritten",
        }, level="warning")
```

---

## SPEC 2: Baseline Test Validation (CRITICAL)

### Problem
The orchestrator doesn't run existing tests BEFORE the coder starts. If tests are already broken, the coder gets blamed for regressions it didn't cause.

### Changes Required

#### 2.1 Add `BaselineResult` dataclass to `swarm_attack/orchestrator.py`

```python
@dataclass
class BaselineResult:
    """Result from baseline test validation."""
    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    pre_existing_failures: list[dict[str, Any]]
    duration_seconds: float
    test_files_checked: list[str]
    skipped_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "pre_existing_failures": self.pre_existing_failures,
            "duration_seconds": self.duration_seconds,
            "test_files_checked": self.test_files_checked,
            "skipped_reason": self.skipped_reason,
        }
```

#### 2.2 Add `_run_baseline_check()` method to `Orchestrator` class

```python
def _run_baseline_check(self, feature_id: str, issue_number: int) -> BaselineResult:
    """Run baseline test validation before coder starts."""
    self._log("baseline_check_start", {"feature_id": feature_id, "issue_number": issue_number})

    # Collect test files from DONE issues
    test_files_to_run = self._get_regression_test_files(feature_id)

    if not test_files_to_run:
        return BaselineResult(
            passed=True, tests_run=0, tests_passed=0, tests_failed=0,
            pre_existing_failures=[], duration_seconds=0.0,
            test_files_checked=[], skipped_reason="No test files to validate"
        )

    # Run pytest on collected files
    exit_code, output = self._verifier._run_pytest(
        test_files=[Path(f) for f in test_files_to_run]
    )

    parsed = self._verifier._parse_pytest_output(output)
    baseline_passed = exit_code == 0

    pre_existing_failures = []
    if not baseline_passed:
        pre_existing_failures = self._verifier._parse_pytest_failures(output)

    return BaselineResult(
        passed=baseline_passed,
        tests_run=parsed["tests_run"],
        tests_passed=parsed["tests_passed"],
        tests_failed=parsed["tests_failed"],
        pre_existing_failures=pre_existing_failures,
        duration_seconds=parsed["duration_seconds"],
        test_files_checked=test_files_to_run,
    )
```

#### 2.3 Integrate into `_run_implementation_cycle()`

Add baseline check at the beginning of the method (only on first attempt):
```python
# BASELINE CHECK (only on retry_number == 0)
baseline_result: Optional[BaselineResult] = None
if retry_number == 0:
    baseline_result = self._run_baseline_check(feature_id, issue_number)

    if not baseline_result.passed and not baseline_result.skipped_reason:
        self._log("baseline_check_abort", {
            "pre_existing_failures": len(baseline_result.pre_existing_failures)
        }, level="error")

        return (
            False, None,
            AgentResult.failure_result(
                f"Baseline check failed: {len(baseline_result.pre_existing_failures)} "
                f"pre-existing test failure(s). Fix these before implementing."
            ),
            total_cost,
        )

    context["baseline_result"] = baseline_result.to_dict()
```

---

## SPEC 3: Issue Creator Improvements (HIGH)

### Problem
Issues are poorly specified for automated implementation - no preservation directives, no CREATE vs UPDATE specification.

### Changes Required

#### 3.1 Update `swarm_attack/skills/issue-creator/SKILL.md`

Add these sections after "Sizing Guidelines":

```markdown
---

## FILE OPERATIONS (REQUIRED)

Every issue body MUST explicitly declare file operations.

### Required Format

```markdown
## File Operations

**CREATE:**
- `path/to/new_file.py` - Purpose

**UPDATE:**
- `path/to/existing.py` (preserve: method_a, method_b, all fields)
```

### Rules

1. Every issue MUST have at least one file operation
2. UPDATE operations MUST include a preservation list
3. Test files follow implementation files

---

## PRESERVATION DIRECTIVES (REQUIRED for UPDATE)

```markdown
## Preservation Directive

**DO NOT modify:**
- `__init__` method signature
- Existing helper methods

**ONLY add:**
- New method: `new_method_name()`
- New field: `new_field: type = default`
```

---

## PRE-FLIGHT VALIDATION (REQUIRED)

Before outputting any issue, validate:

| Check | Limit | Action |
|-------|-------|--------|
| Acceptance criteria | <= 8 | Split if exceeded |
| Methods to implement | <= 6 | Split if exceeded |
| Files to modify | <= 4 | Split if exceeded |

**HARD REJECT if missing:**
- [ ] `## File Operations` section
- [ ] Preservation list for UPDATE operations
- [ ] `## Acceptance Criteria` with checkboxes
```

---

## SPEC 4: Split Oversized Issues (HIGH)

### Issues to Split

The following issues in `specs/chief-of-staff-v2/issues.json` must be split:

| Original | Criteria | Split Into |
|----------|----------|------------|
| Issue #5 | 11 | 5a (DailyGoal fields), 5b (config), 5c (budget checks) |
| Issue #7 | 13 | 7a (core), 7b (triggers), 7c (resolution) |
| Issue #10 | 13 | 10a (base), 10b (error tracking), 10c (escalation) |
| Issue #12 | 21 | 12a (Episode), 12b (logging), 12c (PreferenceLearner), 12d (integration) |

See full split specifications in the expert analysis documents.

---

## Implementation Order

1. **Phase 1A**: Update `coder/SKILL.md` with preservation section
2. **Phase 1B**: Update `coder.py` to read existing on first attempt
3. **Phase 1C**: Add baseline check to orchestrator
4. **Phase 2**: Update `issue-creator/SKILL.md`
5. **Phase 3**: Split oversized issues in `issues.json`
6. **Phase 4**: Run tests, verify all 279 tests still pass

---

## Validation Checklist

After implementation, verify:

- [ ] `pytest tests/generated/chief-of-staff/` passes (279 tests)
- [ ] No new warnings in coder logs about large overwrites
- [ ] Baseline check runs before coder on new implementation attempts
- [ ] SKILL.md changes are syntactically valid markdown
- [ ] No circular imports introduced

---

## BEGIN IMPLEMENTATION

Review each spec section above. For each:

1. **Critique** (100-200 words): What could be improved? Any gaps?
2. **Implement**: Output the complete modified file contents
3. **Test**: Verify changes work

Start with SPEC 1 (Coder Preservation) as it's the most critical fix.
