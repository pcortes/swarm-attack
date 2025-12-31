# Test-Implementation Alignment - Expert Team Prompt

**Working Directory:** `/Users/philipjcortes/Desktop/swarm-attack`
**Date:** 2025-12-23
**Branch:** `fix/bug-bash-2025-12-20`
**Spec:** `specs/test-implementation-alignment/spec-final.md`

---

## FIRST: Verify Your Working Directory

**Before reading further, run these commands:**

```bash
cd /Users/philipjcortes/Desktop/swarm-attack
pwd      # Must show: /Users/philipjcortes/Desktop/swarm-attack
git status
```

**STOP if you're not in the correct directory.**

---

<mission>
You are orchestrating a Team of Specialized Experts to align 48 failing generated tests
with actual implementation using strict Test-Driven Development (TDD) methodology.

Reference: Read `specs/test-implementation-alignment/spec-final.md` for full context.

Goal: All 48 failing tests + 2146 existing tests passing.
</mission>

<team_structure>
| Expert | Role | Responsibility |
|--------|------|----------------|
| RootCauseAnalyzer | Investigation | Analyze test expectations vs implementation |
| InterfaceDesigner | Contract Definition | Define minimal interfaces to satisfy tests |
| TestEngineer | RED Phase | Verify tests fail for expected reasons |
| Coder | GREEN Phase | Implement minimal fixes to pass tests |
| Integrator | Wiring | Ensure new code integrates without regressions |
| Reviewer | Validation | Run full test suite, verify no regressions |
</team_structure>

<background_context>
<codebase_state>
- Total Tests: ~2200
- Currently Passing: 2146
- Failing: 48 (in 8 test files)
- Errors: 6
</codebase_state>

<key_files>
- Goal Tracker: `swarm_attack/chief_of_staff/goal_tracker.py`
- Autopilot Runner: `swarm_attack/chief_of_staff/autopilot_runner.py`
- Checkpoints: `swarm_attack/chief_of_staff/checkpoints.py`
- Config: `swarm_attack/chief_of_staff/config.py`
- Critics: `swarm_attack/chief_of_staff/critics.py`
</key_files>

<failing_test_files>
- `tests/generated/chief-of-staff/test_chief_of_staff_issue_6.py` (9 failures)
- `tests/generated/chief-of-staff/test_chief_of_staff_issue_7.py` (4 failures)
- `tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py` (16 failures)
- `tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_12.py` (5 failures)
- `tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_15.py` (6 failures)
- `tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_16.py` (3 failures)
- `tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_29.py` (1 failure)
- `tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_30.py` (4 failures)
</failing_test_files>
</background_context>

---

## Issue Breakdown

<issue id="1" priority="P0" category="config">
<title>AutopilotConfig.execution_strategy Missing</title>
<test_file>tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_30.py</test_file>
<failures>4</failures>

<expected_interface>
```python
class AutopilotConfig:
    execution_strategy: str = "sequential"

    @classmethod
    def from_dict(cls, data: dict) -> "AutopilotConfig":
        # Should handle missing/empty autopilot sections
        pass
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/config.py</implementation_file>

<acceptance_criteria>
- [ ] `execution_strategy` field exists with default "sequential"
- [ ] `from_dict` handles missing autopilot section
- [ ] `from_dict` handles empty autopilot section
- [ ] All 4 tests pass
</acceptance_criteria>
</issue>

---

<issue id="2" priority="P0" category="dataclass">
<title>CheckpointTrigger Dataclass Mismatch</title>
<test_file>tests/generated/chief-of-staff/test_chief_of_staff_issue_7.py</test_file>
<failures>4</failures>

<expected_interface>
```python
@dataclass
class CheckpointTrigger:
    trigger_type: str
    threshold: float
    current_value: float
    message: str

    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointTrigger": ...
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/checkpoints.py</implementation_file>

<acceptance_criteria>
- [ ] CheckpointTrigger has required fields
- [ ] `to_dict()` returns dict with all fields
- [ ] `from_dict()` creates instance from dict
- [ ] Roundtrip (to_dict -> from_dict) preserves data
</acceptance_criteria>
</issue>

---

<issue id="3" priority="P1" category="interface">
<title>GoalTracker.daily_log_manager Integration</title>
<test_file>tests/generated/chief-of-staff/test_chief_of_staff_issue_6.py</test_file>
<failures>9</failures>

<expected_interface>
```python
class GoalTracker:
    def __init__(self, daily_log_manager: Optional[DailyLogManager] = None):
        self.daily_log_manager = daily_log_manager

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set goals and save to daily log if manager provided."""
        pass

    def reconcile_with_state(
        self,
        feature_states: dict[str, FeaturePhase],
        bug_states: dict[str, BugPhase],
    ) -> None:
        """Update goal statuses based on external state."""
        pass
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/goal_tracker.py</implementation_file>

<acceptance_criteria>
- [ ] `__init__` accepts optional `daily_log_manager`
- [ ] `daily_log_manager` attribute is accessible
- [ ] `set_goals()` persists to daily log when manager provided
- [ ] `reconcile_with_state()` updates goal statuses
</acceptance_criteria>
</issue>

---

<issue id="4" priority="P1" category="methods">
<title>AutopilotRunner Session Methods</title>
<test_file>tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py</test_file>
<failures>16</failures>

<expected_interface>
```python
class AutopilotRunner:
    def start(
        self,
        goals: list[DailyGoal],
        dry_run: bool = False,
        on_checkpoint: Optional[Callable] = None,
    ) -> AutopilotSession:
        """Start executing goals."""
        pass

    def resume(self, session_id: str) -> AutopilotSession:
        """Resume paused session. Raises if not found/not paused."""
        pass

    def cancel(self, session_id: str) -> bool:
        """Cancel session. Returns False if not found."""
        pass

    def list_paused_sessions(self) -> list[AutopilotSession]:
        """List all paused sessions."""
        pass

    def describe_goal(self, goal: DailyGoal) -> str:
        """Human description: 'Feature: X' or 'Bug: Y' or 'Manual: Z'."""
        pass
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/autopilot_runner.py</implementation_file>

<acceptance_criteria>
- [ ] `start()` creates session and executes goals
- [ ] `start()` with `dry_run=True` doesn't execute
- [ ] `resume()` continues paused session
- [ ] `resume()` raises for non-existent session
- [ ] `cancel()` marks session cancelled
- [ ] `list_paused_sessions()` returns paused sessions
- [ ] `describe_goal()` returns appropriate description
- [ ] Checkpoint callbacks work
</acceptance_criteria>
</issue>

---

<issue id="5" priority="P1" category="integration">
<title>Checkpoint Integration in AutopilotRunner</title>
<test_file>tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_12.py</test_file>
<failures>5</failures>

<expected_interface>
```python
class AutopilotRunner:
    def check_before_execution(self, goal: DailyGoal) -> Optional[Checkpoint]:
        """Check if checkpoint needed before executing goal."""
        pass

    # start() should:
    # 1. Call check_before_execution() for each goal
    # 2. Pause if checkpoint requires approval
    # 3. Call on_checkpoint callback when pausing
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/autopilot_runner.py</implementation_file>

<acceptance_criteria>
- [ ] `check_before_execution()` returns checkpoint when needed
- [ ] Execution pauses when checkpoint pending
- [ ] `on_checkpoint` callback is invoked
- [ ] Full integration with CheckpointSystem works
</acceptance_criteria>
</issue>

---

<issue id="6" priority="P2" category="new_class">
<title>PreferenceLearner Class</title>
<test_file>tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_15.py</test_file>
<failures>6</failures>

<expected_interface>
```python
# NEW FILE: swarm_attack/chief_of_staff/preference_learner.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class PreferenceSignal:
    trigger: str
    decision: str  # "approved" | "rejected"
    timestamp: datetime
    context: Optional[dict] = None

class PreferenceLearner:
    def __init__(self):
        self._signals: list[PreferenceSignal] = []

    def record_decision(
        self,
        trigger: str,
        approved: bool,
        context: Optional[dict] = None,
    ) -> PreferenceSignal:
        """Record checkpoint decision, return signal."""
        pass

    def get_signals_by_trigger(self, trigger: str) -> list[PreferenceSignal]:
        """Get all signals for a trigger type."""
        pass

    def get_approval_rate(self, trigger: str) -> Optional[float]:
        """Approval rate 0.0-1.0, or None if no data."""
        pass
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/preference_learner.py (NEW)</implementation_file>

<acceptance_criteria>
- [ ] PreferenceSignal dataclass exists
- [ ] PreferenceLearner class exists
- [ ] `record_decision()` creates and stores signal
- [ ] `record_decision()` classifies approval/rejection
- [ ] `get_signals_by_trigger()` filters correctly
- [ ] `get_approval_rate()` calculates correctly
- [ ] `get_approval_rate()` returns None when no data
</acceptance_criteria>
</issue>

---

<issue id="7" priority="P2" category="new_class">
<title>TestCritic Class</title>
<test_file>tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_16.py</test_file>
<failures>3</failures>

<expected_interface>
```python
# Add to swarm_attack/chief_of_staff/critics.py

class TestCritic:
    """Critic focused on test quality."""

    def __init__(self, focus: str = "coverage"):
        self.focus = focus

    @property
    def name(self) -> str:
        return f"TestCritic:{self.focus}"
```
</expected_interface>

<implementation_file>swarm_attack/chief_of_staff/critics.py</implementation_file>

<acceptance_criteria>
- [ ] TestCritic class exists
- [ ] `focus` attribute set in __init__
- [ ] `name` property returns "TestCritic:{focus}"
- [ ] Edge cases handled (empty focus, special chars)
</acceptance_criteria>
</issue>

---

<issue id="8" priority="P3" category="logic">
<title>Budget Exceeded Handling</title>
<test_file>tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_29.py</test_file>
<failures>1</failures>

<expected_behavior>
`_execute_goals_continue_on_block()` should stop when budget exceeded.
</expected_behavior>

<implementation_file>swarm_attack/chief_of_staff/autopilot_runner.py</implementation_file>

<acceptance_criteria>
- [ ] Method checks remaining budget before each goal
- [ ] Stops execution when budget exceeded
- [ ] Returns partial results for completed goals
</acceptance_criteria>
</issue>

---

## TDD Protocol

<tdd_protocol>
<phase name="RED" order="1">
**For each issue, RootCauseAnalyzer + TestEngineer do:**

1. Read the test file to understand expectations
2. Read implementation file to understand current state
3. Run tests to confirm they fail as expected
4. Document the gap between test and implementation

```bash
# Example for Issue #1
PYTHONPATH=. pytest tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_30.py -v
# Expected: 4 FAILURES
```
</phase>

<phase name="GREEN" order="2">
**InterfaceDesigner + Coder implement:**

1. Design minimal interface changes
2. Implement only what's needed to pass tests
3. Run tests after each change
4. Iterate until all tests pass

```bash
PYTHONPATH=. pytest tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_30.py -v
# Expected: 4 PASSED
```
</phase>

<phase name="REFACTOR" order="3">
**Integrator + Reviewer verify:**

1. Run full test suite
2. Check for regressions
3. Ensure code follows patterns

```bash
PYTHONPATH=. pytest tests/ -v --tb=short
# Expected: 2194+ passed, 0 failed
```
</phase>

<phase name="COMMIT" order="4">
```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: Issue #N - [brief description]

- Implemented [what was done]
- Tests: [X] passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
EOF
)"
```
</phase>
</tdd_protocol>

---

## Execution Order

| Order | Issue | Reason |
|-------|-------|--------|
| 1 | #1 (issue_30) | Config change, no dependencies |
| 2 | #2 (issue_7) | Dataclass fix, no dependencies |
| 3 | #7 (issue_16) | Simple new class |
| 4 | #6 (issue_15) | New class, no dependencies |
| 5 | #3 (issue_6) | GoalTracker interface |
| 6 | #4 (issue_10) | AutopilotRunner methods |
| 7 | #5 (issue_12) | Checkpoint integration |
| 8 | #8 (issue_29) | Budget logic (last) |

---

## Date Handling Pattern

<date_pattern>
**DO NOT use `datetime.now()` or `date.today()` directly in code.**

Use the time utilities helper:

```python
# swarm_attack/chief_of_staff/time_utils.py
from datetime import datetime, date

def get_current_datetime() -> datetime:
    return datetime.now()

def get_current_date() -> date:
    return date.today()
```

**In tests, mock the helper:**

```python
from unittest.mock import patch
from datetime import datetime

FROZEN_TIME = datetime(2025, 12, 23, 10, 0, 0)

def test_something():
    with patch(
        'swarm_attack.chief_of_staff.time_utils.get_current_datetime',
        return_value=FROZEN_TIME
    ):
        # Test code here
        pass
```
</date_pattern>

---

## Success Criteria

<success_criteria>
```bash
# Must pass
PYTHONPATH=. pytest tests/ -v --tb=short

# Expected output
# collected ~2200 items
# ...
# 2194+ passed, 0 failed
```

Additionally:
- [ ] All 48 previously failing tests now pass
- [ ] No regressions in existing 2146 tests
- [ ] All new code follows existing patterns
- [ ] Date handling uses time_utils helper
- [ ] Atomic commits per issue
</success_criteria>

---

## Constraints

<constraints>
- **TDD Required**: Verify test failure BEFORE implementing
- **Minimal Changes**: Implement ONLY what tests require
- **Pattern Matching**: Follow existing code patterns
- **One Issue at a Time**: Complete full TDD cycle before next
- **Commit After Each**: Small, atomic commits
- **No Date Hardcoding**: Use time_utils helpers
- **No Breaking Changes**: Preserve existing interfaces
</constraints>

---

## Output Format

<output_format>
After completing each issue:

```json
{
  "issue_id": 1,
  "test_file": "test_chief_of_staff_v3_issue_30.py",
  "status": "fixed",
  "files_modified": ["swarm_attack/chief_of_staff/config.py"],
  "files_created": [],
  "tests_fixed": 4,
  "commit_hash": "abc1234"
}
```

After all issues fixed:

```json
{
  "total_issues_fixed": 8,
  "total_tests_fixed": 48,
  "total_tests": 2194,
  "tests_passing": 2194,
  "pass_rate": "100%",
  "regressions": 0,
  "branch": "fix/bug-bash-2025-12-20"
}
```
</output_format>
