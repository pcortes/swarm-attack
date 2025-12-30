# Implementation Prompt: Minimum Viable Jarvis

Copy this prompt to have an expert team implement the Jarvis MVP spec.

---

## THE PROMPT

```
You are a team of expert engineers implementing the "Minimum Viable Jarvis" feature for swarm-attack, an autonomous AI development system.

## Your Mission

Transform Chief of Staff from a "supervised task executor" into an "opinionated autonomous partner" by implementing ~415 lines of new/modified code across 6 files.

## Context

The swarm-attack codebase already has:
- AutopilotRunner - Sequential goal execution with recovery
- CheckpointSystem - 6-trigger checkpoint detection
- EpisodeStore - Episode storage with find_similar()
- PreferenceLearner - Signal extraction with find_similar_decisions()
- ProgressTracker - Real-time progress snapshots
- RecoveryManager - 4-level recovery hierarchy

**Your job is to WIRE THESE TOGETHER with intelligence, not rebuild them.**

## The Spec

Read the full spec at: specs/jarvis-mvp/spec.md

## Implementation Order

Execute in this EXACT order to ensure dependencies are satisfied:

### Step 1: RiskScoringEngine (NEW FILE)
Create: `swarm_attack/chief_of_staff/risk_scoring.py`

Requirements:
- RiskAssessment dataclass with score (0.0-1.0), factors dict, recommendation, rationale
- RiskScoringEngine class with score() method
- 5 weighted factors: cost (30%), scope (25%), reversibility (20%), precedent (15%), confidence (10%)
- Thresholds: 0.5 = checkpoint, 0.8 = block
- Integration with EpisodeStore.find_similar() for precedent scoring
- Integration with PreferenceLearner.find_similar_decisions() for confidence scoring

Test by running:
```bash
PYTHONPATH=. python -c "
from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority

engine = RiskScoringEngine()
goal = DailyGoal(
    goal_id='test',
    description='Delete old accounts',
    priority=GoalPriority.HIGH,
    estimated_minutes=30,
    estimated_cost_usd=5.0,
)
result = engine.score(goal, {'session_budget': 25.0, 'spent_usd': 0.0})
print(f'Score: {result.score:.2f}, Recommendation: {result.recommendation}')
print(f'Factors: {result.factors}')
print(f'Rationale: {result.rationale}')
"
```

### Step 2: PreFlightChecker (NEW FILE)
Create: `swarm_attack/chief_of_staff/preflight.py`

Requirements:
- PreFlightIssue dataclass with severity, category, message, suggested_action
- PreFlightResult dataclass with passed, issues, risk_assessment, requires_checkpoint, auto_approved
- PreFlightChecker class with validate() method
- Budget check: fail if estimated_cost > remaining budget
- Dependency check: fail if any dependency is blocked or incomplete
- Risk check: integrate with RiskScoringEngine
- Auto-approve if risk < 0.3, checkpoint if 0.3-0.8, block if > 0.8

Test by running:
```bash
PYTHONPATH=. python -c "
from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
from swarm_attack.chief_of_staff.preflight import PreFlightChecker
from swarm_attack.chief_of_staff.goal_tracker import DailyGoal, GoalPriority

engine = RiskScoringEngine()
checker = PreFlightChecker(engine)

# Should fail - over budget
goal = DailyGoal(
    goal_id='test',
    description='Expensive task',
    priority=GoalPriority.HIGH,
    estimated_minutes=60,
    estimated_cost_usd=30.0,
)
result = checker.validate(goal, {'session_budget': 25.0, 'spent_usd': 0.0})
print(f'Passed: {result.passed}, Summary: {result.summary()}')
"
```

### Step 3: Config Updates (MODIFY)
Modify: `swarm_attack/chief_of_staff/config.py`

Add to AutopilotConfig (or ChiefOfStaffConfig):
```python
# Execution strategy
execution_strategy: ExecutionStrategy = ExecutionStrategy.CONTINUE_ON_BLOCK

# Risk thresholds
risk_checkpoint_threshold: float = 0.5
risk_block_threshold: float = 0.8

# Auto-approve
auto_approve_low_risk: bool = True
```

Ensure ExecutionStrategy enum exists with SEQUENTIAL and CONTINUE_ON_BLOCK values.

### Step 4: AutopilotRunner Integration (MODIFY)
Modify: `swarm_attack/chief_of_staff/autopilot_runner.py`

Requirements:
1. Import RiskScoringEngine and PreFlightChecker
2. Initialize them in __init__ with episode_store and preference_learner
3. Add _get_ready_goals() method that filters goals by completed/blocked status and dependencies
4. Add _select_next() method that picks highest priority (P1>P2>P3, cheaper first)
5. Modify start() to:
   - Track completed and blocked sets
   - Loop while ready goals exist
   - Run preflight before each goal
   - If preflight fails: mark blocked, continue with others
   - If preflight requires checkpoint: pause for approval
   - If goal execution fails: mark blocked, continue with others (CONTINUE_ON_BLOCK)
   - Update ProgressTracker after each goal

Key code pattern:
```python
while True:
    ready_goals = self._get_ready_goals(goals, completed, blocked)
    if not ready_goals:
        break

    goal = self._select_next(ready_goals)
    preflight = self.preflight.validate(goal, context)

    if not preflight.passed:
        blocked.add(goal.goal_id)
        continue

    if preflight.requires_checkpoint:
        # Create checkpoint, await approval
        ...

    result = self._execute_goal(goal)
    if result.success:
        completed.add(goal.goal_id)
    else:
        blocked.add(goal.goal_id)
        # Continue with others instead of breaking!
```

### Step 5: Progress CLI (MODIFY)
Modify: `swarm_attack/cli/chief_of_staff.py`

Update the existing `progress_command` to add:
- --watch flag for live updates (refresh every 5s)
- Visual progress bar using Unicode blocks
- Blockers section showing blocked goals with reasons
- Better formatting with Rich panels and colors

Test by running:
```bash
PYTHONPATH=. swarm-attack cos progress
PYTHONPATH=. swarm-attack cos progress --history
```

### Step 6: Tests (NEW FILE)
Create: `tests/chief_of_staff/test_risk_scoring.py`

Requirements:
- TestRiskScoringEngine class with 3+ test methods
- TestPreFlightChecker class with 3+ test methods
- Test cases:
  - Low risk goal scores low (<0.3) and recommends proceed
  - High cost goal scores high (>0.5) and recommends checkpoint
  - Irreversible keywords (delete, destroy) increase reversibility factor
  - Budget exceeded fails preflight
  - Low risk auto-approves
  - Medium risk requires checkpoint

Run tests:
```bash
PYTHONPATH=. pytest tests/chief_of_staff/test_risk_scoring.py -v
```

## Code Quality Requirements

1. **Type hints everywhere** - Use TYPE_CHECKING imports for circular dependencies
2. **Dataclasses for all data structures** - Not dicts
3. **Docstrings on all public methods** - Explain what, why, and returns
4. **No new dependencies** - Use only what's already in requirements.txt
5. **Match existing patterns** - Look at episodes.py and checkpoints.py for style

## Integration Checklist

After implementing all steps, verify:

```bash
# 1. Tests pass
PYTHONPATH=. pytest tests/chief_of_staff/test_risk_scoring.py -v

# 2. Risk scoring works
PYTHONPATH=. python -c "
from swarm_attack.chief_of_staff.risk_scoring import RiskScoringEngine
print('RiskScoringEngine OK')
"

# 3. PreFlight works
PYTHONPATH=. python -c "
from swarm_attack.chief_of_staff.preflight import PreFlightChecker
print('PreFlightChecker OK')
"

# 4. Progress CLI works
PYTHONPATH=. swarm-attack cos progress

# 5. Full autopilot with continue-on-block
PYTHONPATH=. swarm-attack cos standup  # Set some goals
PYTHONPATH=. swarm-attack cos autopilot --budget 10 --dry-run
```

## Success Criteria

1. **PreFlight blocks over-budget goals** - Goal with cost > remaining budget fails preflight
2. **Risk scoring is meaningful** - "Delete accounts" scores higher than "Update docs"
3. **Continue-on-block works** - When goal A blocks, goals B/C continue if independent
4. **Progress CLI shows real data** - Current goal, completion %, blockers displayed
5. **Low-risk auto-approves** - Risk < 0.3 proceeds without checkpoint
6. **Tests pass** - All test cases in test_risk_scoring.py pass

## What NOT To Do

1. **DO NOT modify EpisodeStore or PreferenceLearner** - They're already implemented correctly
2. **DO NOT add LLM calls** - Risk scoring is heuristic-based, not LLM-based
3. **DO NOT add new CLI commands** - Only modify existing ones
4. **DO NOT add Campaign infrastructure** - Skip issues 7-10 entirely
5. **DO NOT over-engineer** - 415 LOC is the budget, not the minimum

## Files to Create/Modify

| File | Action | LOC Target |
|------|--------|------------|
| swarm_attack/chief_of_staff/risk_scoring.py | CREATE | ~100 |
| swarm_attack/chief_of_staff/preflight.py | CREATE | ~80 |
| swarm_attack/chief_of_staff/config.py | MODIFY | +20 |
| swarm_attack/chief_of_staff/autopilot_runner.py | MODIFY | +75 |
| swarm_attack/cli/chief_of_staff.py | MODIFY | +40 |
| tests/chief_of_staff/test_risk_scoring.py | CREATE | ~80 |

## Existing Files to Reference (DO NOT MODIFY unless specified)

- swarm_attack/chief_of_staff/episodes.py - EpisodeStore, PreferenceLearner patterns
- swarm_attack/chief_of_staff/checkpoints.py - Checkpoint, CheckpointTrigger patterns
- swarm_attack/chief_of_staff/goal_tracker.py - DailyGoal, GoalPriority
- swarm_attack/chief_of_staff/progress.py - ProgressTracker, ProgressSnapshot

## Begin Implementation

Start with Step 1 (RiskScoringEngine). After each step, run the test command to verify before proceeding.

When you encounter decisions not covered by this spec, match the patterns in episodes.py and checkpoints.py.

Good luck. Ship Jarvis.
```

---

## Usage

1. Copy the prompt above (everything between the ``` markers)
2. Paste into Claude or another LLM
3. Attach the spec file: `specs/jarvis-mvp/spec.md`
4. Let it implement step by step
5. Verify each step with the test commands

## Expected Output

The LLM should produce:
- 2 new files (~180 LOC)
- 3 modified files (~135 LOC of changes)
- 1 new test file (~80 LOC)

Total: ~395-420 LOC (within the 440 LOC budget)

## After Implementation

Run the full verification:

```bash
# All tests
PYTHONPATH=. pytest tests/chief_of_staff/ -v

# Smoke test
PYTHONPATH=. swarm-attack cos standup
PYTHONPATH=. swarm-attack cos autopilot --budget 5 --dry-run
PYTHONPATH=. swarm-attack cos progress
```

If all pass, Minimum Viable Jarvis is complete.
