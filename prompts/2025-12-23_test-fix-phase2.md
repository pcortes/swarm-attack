# Swarm Attack Test Fix Phase 2 - TDD Implementation

**Working Directory:** `/Users/philipjcortes/Desktop/swarm-attack`
**Date:** 2025-12-23
**Branch:** `fix/test-alignment-2025-12-23`

---

## FIRST: Verify Your Working Directory

**Before reading further, run these commands:**

```bash
cd /Users/philipjcortes/Desktop/swarm-attack
pwd      # Must show: /Users/philipjcortes/Desktop/swarm-attack
git status   # Check current state
git checkout -b fix/test-alignment-2025-12-23
```

**STOP if you're not in the correct directory.**

---

<mission>
You are orchestrating a Team of Specialized Experts to fix 23 remaining test failures
using strict Test-Driven Development (TDD) methodology.

These are TEST ALIGNMENT issues - the tests were generated from specs but the
implementation evolved differently. You must decide for each failure whether to:
1. Fix the TEST to match the implementation (preferred for behavior changes)
2. Fix the IMPLEMENTATION to match the spec (for missing features)

Goal: All 2,200 tests passing after fixes are applied.
Current: 2,177 passed, 23 failed
</mission>

<team_structure>
| Expert | Role | Responsibility |
|--------|------|----------------|
| Architect | Interface Analysis | Compare test expectations vs actual implementation |
| TestEngineer | RED Phase | Verify tests fail for right reasons, fix test expectations |
| Coder | GREEN Phase | Implement missing features if tests are correct |
| Integrator | Wiring | Ensure fixes don't break existing functionality |
| Reviewer | Validation | Run full test suite, verify no regressions |
</team_structure>

<background_context>
<codebase_state>
- Total Tests: 2,200
- Currently Passing: 2,177 (99.0%)
- Failing: 23
- Last Fix Phase: 2025-12-23 (fixed 25 tests)
</codebase_state>

<key_files>
- AutopilotRunner: `swarm_attack/chief_of_staff/autopilot_runner.py`
- Checkpoints: `swarm_attack/chief_of_staff/checkpoints.py`
- Config: `swarm_attack/chief_of_staff/config.py`
- GoalTracker: `swarm_attack/chief_of_staff/goal_tracker.py`
</key_files>
</background_context>

---

## Failure Categories

### Category A: AutopilotRunner Missing Methods (6 failures)
**File:** `tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py`

Tests expect these methods that don't exist on `AutopilotRunner`:
- `_describe_goal(goal)` - Returns human-readable description
- `list_paused_sessions()` - Returns list of paused sessions
- `cancel(session_id)` - Cancels a session

<decision_required>
**Option 1 (IMPLEMENT):** Add these methods to AutopilotRunner
**Option 2 (REMOVE TESTS):** Delete tests if features not needed
</decision_required>

<affected_tests>
- test_describe_goal_feature
- test_describe_goal_bug
- test_describe_goal_manual
- test_list_paused_sessions
- test_cancel_session
- test_cancel_nonexistent_session
</affected_tests>

---

### Category B: AutopilotRunner Start/Resume Behavior (10 failures)
**File:** `tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py`

Tests expect specific behaviors that don't match implementation:

| Test | Expected | Actual |
|------|----------|--------|
| test_start_creates_session | session_id starts with "auto-" | UUID format |
| test_start_executes_all_goals | 3 goals executed | 2 goals executed |
| test_start_dry_run | 0 goals executed | 2 goals executed |
| test_cost_trigger | Trigger fires at threshold | None returned |
| test_approval_trigger | Trigger fires for approval | None returned |
| test_high_risk_trigger | Trigger fires for risk | None returned |
| test_checkpoint_callback | Callback called once | Never called |
| test_resume_paused_session | State is PAUSED | State is COMPLETED |
| test_resume_not_found | Returns None | Implementation differs |
| test_resume_not_paused | Error raised | Implementation differs |

<decision_required>
**Analysis needed:** Compare test expectations with actual implementation behavior.
Fix tests to match reality OR implement missing trigger/checkpoint logic.
</decision_required>

---

### Category C: Checkpoint Integration (5 failures)
**Files:**
- `tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_12.py`
- `tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_6.py`

Tests expect:
- `check_before_execution()` called for each goal
- Execution pauses when checkpoint requires approval
- `on_checkpoint` callback invoked when pausing
- `Checkpoint` has `trigger` field

<affected_tests>
- test_pauses_when_checkpoint_requires_approval
- test_execution_breaks_when_checkpoint_pending
- test_on_checkpoint_called_when_pausing
- test_full_integration_with_triggers
- test_has_trigger_field
</affected_tests>

---

### Category D: Recommendation/Config Issues (2 failures)
**Files:**
- `tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_8.py`
- `tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_29.py`

| Test | Issue |
|------|-------|
| test_only_one_option_is_recommended | TypeError: 'type' object is not iterable |
| test_stops_when_budget_exceeded | Budget check not stopping execution |

---

## TDD Protocol

<tdd_protocol>
<phase name="ANALYZE" order="0">
**For each failure category, Architect does:**

1. Read the failing test to understand expectations
2. Read the implementation to understand actual behavior
3. Decide: FIX TEST or FIX IMPLEMENTATION
4. Document decision with rationale

```bash
# Example: Analyze test_describe_goal_feature
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py::TestAutopilotRunnerHelpers::test_describe_goal_feature -v --tb=long
```
</phase>

<phase name="RED" order="1">
**TestEngineer verifies test fails for right reason:**

1. Run the failing test
2. Confirm the error matches expected failure mode
3. If test expectation is wrong, fix the test
4. If implementation is missing, proceed to GREEN

```bash
# Run specific test
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py::TestAutopilotRunnerHelpers -v --tb=short
```
</phase>

<phase name="GREEN" order="2">
**Coder implements minimal fix:**

1. If fixing TEST: Update assertions to match implementation
2. If fixing IMPLEMENTATION: Add missing method/behavior
3. Run test after each change
4. Iterate until test passes

```bash
# Run after changes
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py -v --tb=short
```
</phase>

<phase name="REFACTOR" order="3">
**Integrator verifies no regressions:**

```bash
# Full test suite
PYTHONPATH=. pytest tests/ -v --tb=short
# Expected: 2200+ tests, all passing
```
</phase>

<phase name="COMMIT" order="4">
**Reviewer creates commit:**

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: Align tests with implementation for Category X

- [What was fixed]
- [Why this approach]

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
| Order | Category | Failures | Approach |
|-------|----------|----------|----------|
| 1 | D | 2 | Quick fixes - type error, budget logic |
| 2 | A | 6 | Decide: implement methods OR remove tests |
| 3 | C | 5 | Checkpoint integration alignment |
| 4 | B | 10 | Behavior alignment (largest group) |
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
# collected 2200 items
# ...
# ========================= 2200 passed in X.XXs =========================
```

Additionally:
- [ ] No regressions in existing functionality
- [ ] All interface contracts satisfied
- [ ] Decisions documented (why test vs implementation fixed)
</success_criteria>

---

## Constraints

<constraints>
- **Analyze Before Fixing**: Understand WHY test fails before changing anything
- **Prefer Test Fixes**: If implementation is working correctly, fix tests to match
- **Minimal Changes**: Don't refactor unrelated code
- **Pattern Matching**: Follow existing code patterns in each file
- **One Category at a Time**: Complete full TDD cycle per category
- **Commit After Each Category**: Small, atomic commits
</constraints>

---

## Pattern References

<pattern_references>
| Pattern | Location | Use For |
|---------|----------|---------|
| AutopilotRunner methods | `swarm_attack/chief_of_staff/autopilot_runner.py` | Category A, B |
| Checkpoint structure | `swarm_attack/chief_of_staff/checkpoints.py` | Category C |
| Test mock patterns | `tests/generated/cos-phase8-recovery/` | Passing test examples |
| GoalExecutionResult | `swarm_attack/chief_of_staff/autopilot_runner.py:135` | Return types |
</pattern_references>

---

## Quick Start Commands

```bash
# See all failures
PYTHONPATH=. pytest tests/ --tb=no -q 2>&1 | grep "^FAILED"

# Run specific test file
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py -v --tb=short

# Run with full traceback for one test
PYTHONPATH=. pytest "tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py::TestAutopilotRunnerHelpers::test_describe_goal_feature" -v --tb=long

# Run full suite
PYTHONPATH=. pytest tests/ -v --tb=short
```

---

<output_format>
After completing each category, report:

```json
{
  "category": "A",
  "approach": "FIX_TESTS" | "FIX_IMPLEMENTATION",
  "rationale": "Why this approach",
  "files_modified": ["path/to/file.py"],
  "tests_fixed": 6,
  "commit_hash": "abc1234"
}
```

After all categories fixed:

```json
{
  "total_tests_fixed": 23,
  "total_tests": 2200,
  "tests_passing": 2200,
  "pass_rate": "100%",
  "branch": "fix/test-alignment-2025-12-23"
}
```
</output_format>
