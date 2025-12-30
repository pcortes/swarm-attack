# Spec: Test-Implementation Alignment for Chief of Staff

**Feature ID:** `test-implementation-alignment`
**Date:** 2025-12-23
**Status:** APPROVED

---

## 1. Overview

### 1.1 Purpose

Align 48 failing generated tests with actual implementation in the Chief of Staff module. The tests were auto-generated from specs but the implementations diverged or were never completed.

### 1.2 Problem Statement

Generated tests expect interfaces that don't exist:
- `GoalTracker.daily_log_manager` attribute
- `AutopilotRunner.start()`, `resume()`, `cancel()` methods
- `CheckpointTrigger` dataclass with specific fields
- `AutopilotConfig.execution_strategy` field
- `PreferenceLearner` class
- `TestCritic` in critics module

### 1.3 Success Criteria

- All 48 failing tests pass
- No regressions in passing tests (2146+)
- TDD approach: verify test expectations, then implement
- Use frozen dates where datetime comparisons occur

---

## 2. Root Cause Analysis

### 2.1 Failure Categories

| Category | Files | Failures | Root Cause |
|----------|-------|----------|------------|
| GoalTracker | issue_6 | 9 | Missing `daily_log_manager` integration |
| AutopilotRunner | issue_10 | 16 | Missing `start()`, `resume()`, session methods |
| CheckpointTrigger | issue_7 | 4 | Missing/incompatible dataclass |
| Checkpoint Integration | issue_12 | 5 | Missing `check_before_execution()` |
| PreferenceLearner | issue_15 | 6 | Class doesn't exist |
| TestCritic | issue_16 | 3 | Missing critic type |
| Budget Handling | issue_29 | 1 | Budget exceeded logic |
| ExecutionStrategy | issue_30 | 4 | Missing config field |

### 2.2 Decision Matrix

For each category, decide:
1. **Implement** - Add missing functionality to match tests
2. **Adjust Tests** - Tests expect wrong interface, fix tests
3. **Delete Tests** - Feature was descoped, remove tests

---

## 3. Implementation Plan

### 3.1 Priority Order

1. **P0 - Quick Wins** (adjust tests/small fixes)
   - CheckpointTrigger field alignment (issue_7)
   - AutopilotConfig.execution_strategy (issue_30)

2. **P1 - Interface Additions** (add missing attributes)
   - GoalTracker.daily_log_manager (issue_6)
   - AutopilotRunner session methods (issue_10)

3. **P2 - New Classes** (implement missing classes)
   - PreferenceLearner (issue_15)
   - TestCritic (issue_16)

4. **P3 - Integration** (wire everything together)
   - Checkpoint integration (issue_12)
   - Budget handling (issue_29)

### 3.2 File Mapping

| Issue | Test File | Implementation File |
|-------|-----------|---------------------|
| 6 | `test_chief_of_staff_issue_6.py` | `goal_tracker.py` |
| 7 | `test_chief_of_staff_issue_7.py` | `checkpoints.py` |
| 10 | `test_chief_of_staff_issue_10.py` | `autopilot_runner.py` |
| 12 | `test_chief_of_staff_v2_issue_12.py` | `autopilot_runner.py` |
| 15 | `test_chief_of_staff_v2_issue_15.py` | `preference_learner.py` (new) |
| 16 | `test_chief_of_staff_v3_issue_16.py` | `critics.py` |
| 29 | `test_chief_of_staff_v3_issue_29.py` | `autopilot_runner.py` |
| 30 | `test_chief_of_staff_v3_issue_30.py` | `config.py` |

---

## 4. Interface Contracts

### 4.1 GoalTracker (issue_6)

```python
# swarm_attack/chief_of_staff/goal_tracker.py

class GoalTracker:
    def __init__(self, daily_log_manager: Optional[DailyLogManager] = None):
        self.daily_log_manager = daily_log_manager
        # ... existing init

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set goals and persist to daily log."""
        self._goals = goals
        if self.daily_log_manager:
            self.daily_log_manager.save_goals(goals)

    def reconcile_with_state(self, feature_states: dict, bug_states: dict) -> None:
        """Update goal statuses based on external state."""
        pass
```

### 4.2 AutopilotRunner Session Methods (issue_10)

```python
# swarm_attack/chief_of_staff/autopilot_runner.py

class AutopilotRunner:
    def start(
        self,
        goals: list[DailyGoal],
        dry_run: bool = False,
        on_checkpoint: Optional[Callable] = None,
    ) -> AutopilotSession:
        """Start autopilot execution of goals."""
        pass

    def resume(self, session_id: str) -> AutopilotSession:
        """Resume a paused session."""
        pass

    def cancel(self, session_id: str) -> bool:
        """Cancel a session."""
        pass

    def list_paused_sessions(self) -> list[AutopilotSession]:
        """List all paused sessions."""
        pass

    def describe_goal(self, goal: DailyGoal) -> str:
        """Human-readable description of goal."""
        pass
```

### 4.3 AutopilotConfig (issue_30)

```python
# swarm_attack/chief_of_staff/config.py

class AutopilotConfig:
    execution_strategy: str = "sequential"  # "sequential" | "parallel"

    @classmethod
    def from_dict(cls, data: dict) -> "AutopilotConfig":
        autopilot = data.get("autopilot", {})
        return cls(
            execution_strategy=autopilot.get("execution_strategy", "sequential"),
            # ... existing fields
        )
```

### 4.4 PreferenceLearner (issue_15)

```python
# swarm_attack/chief_of_staff/preference_learner.py (NEW FILE)

from dataclasses import dataclass
from typing import Optional
from datetime import datetime

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
        """Record a checkpoint decision."""
        pass

    def get_signals_by_trigger(self, trigger: str) -> list[PreferenceSignal]:
        """Get all signals for a trigger type."""
        pass

    def get_approval_rate(self, trigger: str) -> Optional[float]:
        """Get approval rate for trigger (None if no data)."""
        pass
```

### 4.5 TestCritic (issue_16)

```python
# swarm_attack/chief_of_staff/critics.py

class TestCritic:
    """Critic focused on test quality and coverage."""

    def __init__(self, focus: str = "coverage"):
        self.focus = focus

    @property
    def name(self) -> str:
        return f"TestCritic:{self.focus}"
```

### 4.6 CheckpointTrigger (issue_7)

```python
# swarm_attack/chief_of_staff/checkpoints.py

@dataclass
class CheckpointTrigger:
    trigger_type: str  # "cost" | "approval" | "high_risk"
    threshold: float
    current_value: float
    message: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointTrigger":
        return cls(**data)
```

---

## 5. TDD Protocol

### 5.1 Phase 1: RED (Verify Failures)

```bash
# Run each test file to confirm failures
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_6.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_7.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff/test_chief_of_staff_issue_10.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_12.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff-v2/test_chief_of_staff_v2_issue_15.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_16.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_29.py -v
PYTHONPATH=. pytest tests/generated/chief-of-staff-v3/test_chief_of_staff_v3_issue_30.py -v
```

### 5.2 Phase 2: GREEN (Implement)

For each issue:
1. Read the test file carefully
2. Implement minimal code to pass tests
3. Run tests after each change
4. Commit when all tests in file pass

### 5.3 Phase 3: REFACTOR

```bash
# Full test suite
PYTHONPATH=. pytest tests/ -v --tb=short
```

---

## 6. Date Handling

### 6.1 Pattern

Use `datetime.now()` wrapped in a helper for testability:

```python
# swarm_attack/chief_of_staff/time_utils.py

from datetime import datetime, date

def get_current_datetime() -> datetime:
    """Get current datetime (mockable in tests)."""
    return datetime.now()

def get_current_date() -> date:
    """Get current date (mockable in tests)."""
    return date.today()
```

### 6.2 Test Pattern

```python
from unittest.mock import patch
from datetime import datetime

def test_with_frozen_time():
    frozen_time = datetime(2025, 12, 23, 10, 0, 0)
    with patch('swarm_attack.chief_of_staff.time_utils.get_current_datetime',
               return_value=frozen_time):
        # test code
        pass
```

---

## 7. Acceptance Criteria

- [ ] issue_6: 9 tests pass (GoalTracker)
- [ ] issue_7: 4 tests pass (CheckpointTrigger)
- [ ] issue_10: 16 tests pass (AutopilotRunner)
- [ ] issue_12: 5 tests pass (Checkpoint integration)
- [ ] issue_15: 6 tests pass (PreferenceLearner)
- [ ] issue_16: 3 tests pass (TestCritic)
- [ ] issue_29: 1 test passes (Budget handling)
- [ ] issue_30: 4 tests pass (ExecutionStrategy)
- [ ] Total: 48 new tests passing
- [ ] No regressions in existing 2146+ tests

---

## 8. Constraints

- **TDD Required**: Verify test failure before implementing
- **Minimal Changes**: Implement only what tests require
- **Pattern Matching**: Follow existing code patterns
- **One Issue at a Time**: Complete full cycle per issue
- **Commit After Each Issue**: Atomic commits
- **No Hardcoded Dates**: Use time_utils helpers

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tests expect impossible interface | Medium | High | Review tests, adjust if needed |
| Breaking existing functionality | Low | High | Run full suite after each change |
| Circular imports | Medium | Medium | Use TYPE_CHECKING imports |
| Async/sync mismatch | Medium | Medium | Match existing patterns |

---

## 10. Appendix: Test File Locations

```
tests/generated/chief-of-staff/
├── test_chief_of_staff_issue_6.py   # GoalTracker
├── test_chief_of_staff_issue_7.py   # CheckpointTrigger
└── test_chief_of_staff_issue_10.py  # AutopilotRunner

tests/generated/chief-of-staff-v2/
├── test_chief_of_staff_v2_issue_12.py  # Checkpoint integration
└── test_chief_of_staff_v2_issue_15.py  # PreferenceLearner

tests/generated/chief-of-staff-v3/
├── test_chief_of_staff_v3_issue_16.py  # TestCritic
├── test_chief_of_staff_v3_issue_29.py  # Budget handling
└── test_chief_of_staff_v3_issue_30.py  # ExecutionStrategy
```
