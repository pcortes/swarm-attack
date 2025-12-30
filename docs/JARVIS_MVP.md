# Jarvis MVP: Intelligent Automation

The Jarvis MVP brings intelligent, risk-aware automation to Swarm Attack's Chief of Staff orchestration layer. It enables the system to make smart decisions about when to auto-approve goals, when to pause for checkpoints, and when to block risky operations entirely.

## Overview

Jarvis MVP consists of four integrated components:

1. **Risk Scoring Engine** - Calculates nuanced risk scores using 5 weighted factors
2. **PreFlight Checker** - Validates goals BEFORE execution starts
3. **Intelligent Checkpoint System** - Makes smart decisions about when to pause vs continue
4. **Self-Healing System** - Enables intelligent recovery from failures with LLM-powered analysis and interactive checkpoints

Together, these components enable the Chief of Staff to work more autonomously while maintaining safety guardrails and recovering gracefully from errors.

## Risk Scoring Engine

Location: `swarm_attack/chief_of_staff/risk_scoring.py`

### How It Works

The Risk Scoring Engine evaluates every goal using **5 weighted factors** to produce a risk score from 0.0 (safe) to 1.0 (risky):

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| **cost** | 30% | Budget impact as % of remaining funds |
| **scope** | 25% | Number of files affected + core path involvement |
| **reversibility** | 20% | Can this operation be undone? |
| **precedent** | 15% | Have we done similar work successfully before? |
| **confidence** | 10% | Based on past approval/rejection patterns |

### Risk Calculation

```python
# Example: A goal to "delete production database tables"
factors = {
    "cost": 0.4,           # 40% of remaining budget
    "scope": 0.6,          # Affects 8 core database files
    "reversibility": 1.0,  # IRREVERSIBLE (contains "delete")
    "precedent": 0.7,      # No similar successful work
    "confidence": 0.5,     # Unknown outcome
}

# Weighted score
risk_score = (0.4 * 0.30) + (0.6 * 0.25) + (1.0 * 0.20) + (0.7 * 0.15) + (0.5 * 0.10)
risk_score = 0.12 + 0.15 + 0.20 + 0.105 + 0.05 = 0.625
```

### Decision Thresholds

The risk score determines the recommendation:

| Score Range | Recommendation | Action |
|-------------|----------------|--------|
| 0.0 - 0.5 | **proceed** | Auto-approve (if enabled) |
| 0.5 - 0.8 | **checkpoint** | Pause for human review |
| 0.8 - 1.0 | **block** | Execution prevented |

**Default Thresholds:**
- `risk_checkpoint_threshold: 0.5` - Checkpoint required above this
- `risk_block_threshold: 0.8` - Execution blocked above this

### Factor Details

#### 1. Cost Factor (30%)

Measures budget impact as a fraction of remaining funds:

```python
# 30% of remaining budget = 0.5 risk
# 60% of remaining budget = 1.0 risk
cost_ratio = estimated_cost / remaining_budget
cost_score = min(1.0, cost_ratio / 0.6)
```

**Example:**
- Remaining budget: $15
- Goal estimate: $9
- Cost ratio: 60%
- Cost score: 1.0 (high risk)

#### 2. Scope Factor (25%)

Based on number of files and core path involvement:

```python
# 10+ files = 1.0 base score
file_score = min(1.0, num_files / 10)

# +0.3 if affects core paths:
# core/, models/, api/, auth/, database/
if affects_core:
    file_score = min(1.0, file_score + 0.3)
```

**Example:**
- 5 files affected
- 2 are in `core/models/`
- Base score: 0.5
- Core bonus: +0.3
- Scope score: 0.8 (high risk)

#### 3. Reversibility Factor (20%)

Detects irreversible operations by keywords:

```python
# Irreversible: delete, drop, remove, destroy, reset, migrate
if any(keyword in description):
    return 1.0  # Maximum risk

# External/publish: deploy, publish, push, release, send, email
if any(external_keyword in description):
    return 0.7  # High risk

# Everything else
return 0.2  # Low risk (reversible via git)
```

**Examples:**
- "Delete old database tables" → 1.0 (irreversible)
- "Deploy to production" → 0.7 (external)
- "Refactor authentication logic" → 0.2 (reversible)

#### 4. Precedent Factor (15%)

Checks episode history for similar past work:

```python
similar_episodes = find_similar(description, k=5)

if no similar episodes:
    return 0.6  # Slightly risky (unknown territory)

success_rate = successes / total_similar
return 1.0 - success_rate  # High success = low risk
```

**Example:**
- Found 5 similar episodes
- 4 succeeded, 1 failed
- Success rate: 80%
- Precedent score: 0.2 (low risk)

#### 5. Confidence Factor (10%)

Based on past approval/rejection patterns:

```python
similar_decisions = find_similar_decisions(goal, k=3)

if no history:
    return 0.5  # Unknown

approval_rate = approvals / total_decisions
return 1.0 - approval_rate  # High approval = low risk
```

**Example:**
- Found 3 similar decisions
- All 3 were approved
- Approval rate: 100%
- Confidence score: 0.0 (very low risk)

## PreFlight Checker

Location: `swarm_attack/chief_of_staff/preflight.py`

### What It Does

The PreFlight Checker validates goals **before execution starts**, catching issues early and enabling intelligent checkpoint decisions.

### Validation Checks

The checker runs three validation checks:

#### 1. Budget Sufficiency

```python
# Critical: Estimated cost exceeds remaining budget
if estimated > remaining:
    severity = "critical"
    message = f"Estimated ${estimated:.2f} exceeds remaining ${remaining:.2f}"
    suggested_action = "Increase budget or reduce scope"

# Warning: Will use >80% of remaining budget
if estimated > remaining * 0.8:
    severity = "warning"
    message = f"Will use {estimated/remaining*100:.0f}% of remaining budget"
    suggested_action = "Consider reserving budget for other goals"
```

#### 2. Dependency Availability

```python
for dep_id in goal.dependencies:
    # Critical: Dependency is blocked
    if dep_id in blocked_goals:
        severity = "critical"
        message = f"Depends on blocked goal: {dep_id}"
        suggested_action = "Resolve blocker first or remove dependency"

    # Critical: Dependency not completed
    if dep_id not in completed_goals:
        severity = "critical"
        message = f"Depends on incomplete goal: {dep_id}"
        suggested_action = "Complete dependency first"
```

#### 3. Risk Assessment

Runs the Risk Scoring Engine and includes the assessment in the result.

### PreFlight Results

The checker returns a `PreFlightResult` with:

```python
@dataclass
class PreFlightResult:
    passed: bool                    # Can execution proceed?
    issues: list[PreFlightIssue]    # Any warnings/errors found
    risk_assessment: RiskAssessment # Risk analysis
    requires_checkpoint: bool       # Should we pause for approval?
    auto_approved: bool            # Was this auto-approved?
```

### Decision Flow

```
PreFlight Validation
        ↓
Has critical issues? ──Yes──> BLOCKED (passed=False)
        ↓ No
Risk score >= 0.8? ──Yes──> BLOCKED (requires_checkpoint=True)
        ↓ No
Risk score >= 0.5? ──Yes──> CHECKPOINT (requires_checkpoint=True)
        ↓ No
    AUTO-APPROVE (auto_approved=True)
```

## Self-Healing System (IMPLEMENTED)

The Self-Healing system enables intelligent recovery from execution failures through LLM-powered analysis and user-guided decisions.

### Components

#### 1. CheckpointUX (`checkpoint_ux.py`)

**Status: IMPLEMENTED**

Location: `swarm_attack/chief_of_staff/checkpoint_ux.py`

Provides **interactive checkpoint approval workflow** with formatted display and validated user input. During autopilot execution, checkpoints display blocking prompts that wait for immediate user response:

```
⚠️  HICCUP Checkpoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[context about the issue]

Options:
  [1] Proceed - Continue (recommended)
  [2] Skip - Skip this goal
  [3] Pause - Pause for manual review

Select option: _
```

**How to respond:**
- Press **Enter** to select the recommended option (default)
- Type **1, 2, or 3** to choose a specific option
- Invalid input will reprompt

**Classes:**

```python
@dataclass
class CheckpointDecision:
    checkpoint_id: str
    chosen_option: str
    notes: str = ""
```

**CheckpointUX Methods:**

- `format_checkpoint(checkpoint: Checkpoint) -> str` - Formats checkpoint data for display with trigger type, context, and numbered options
- `get_decision(checkpoint: Checkpoint, allow_notes: bool) -> CheckpointDecision` - Gets user input with validation (1/2/3 or Enter for default)
- `prompt_and_wait(checkpoint: Checkpoint) -> CheckpointDecision` - Main entry point that displays formatted checkpoint and blocks until user decides

**Usage Example:**

```python
from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

checkpoint_ux = CheckpointUX()
checkpoint_data = {
    "id": "cp_123",
    "goal": "Refactor authentication module",
    "trigger": "ARCHITECTURE",
    "risk_score": 0.65,
    "estimated_cost": 8.50,
    "files_affected": ["auth/", "api/", "tests/"]
}

# Display formatted checkpoint and wait for decision
decision = checkpoint_ux.prompt_and_wait(checkpoint_data)

if decision.approved:
    print(f"Approved: {decision.notes}")
else:
    print(f"Rejected: {decision.notes}")
```

**Display Format:**

```
CHECKPOINT REQUIRED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Goal: Refactor authentication module
Trigger: ARCHITECTURE
Risk Score: 0.65 (MEDIUM)

Cost Impact:
  Estimated: $8.50
  Remaining Budget: $15.00
  Percentage: 57%

Files Affected:
  - auth/
  - api/
  - tests/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Options:
  [a] Approve - Continue with this goal
  [r] Reject - Skip this goal
  [s] Skip for now - Defer decision

Your choice (a/r/s):
```

#### 2. Level2Analyzer (`level2_recovery.py`)

**Status: IMPLEMENTED**

Location: `swarm_attack/chief_of_staff/level2_recovery.py`

Provides LLM-powered recovery suggestions when goals fail or encounter errors.

**Enums and Classes:**

```python
class RecoveryActionType(Enum):
    ALTERNATIVE = "alternative"     # Suggest alternative approach
    DIAGNOSTICS = "diagnostics"     # Run diagnostic commands
    UNBLOCK = "unblock"            # Steps to unblock
    ESCALATE = "escalate"          # Escalate to human

@dataclass
class RecoveryAction:
    action_type: RecoveryActionType
    description: str
    steps: List[str]
    estimated_cost: float
    confidence: float
```

**Level2Analyzer Methods:**

- `analyze(goal: Dict, error: str, context: Dict) -> RecoveryAction` - Async method that calls Claude API for intelligent recovery suggestion
- `_build_prompt(goal, error, context) -> str` - Constructs detailed prompt with goal, error, and repo context
- `_parse_response(response: str) -> RecoveryAction` - Parses JSON response into RecoveryAction

**Usage Example:**

```python
from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer
import asyncio

async def recover_from_failure():
    analyzer = Level2Analyzer(
        anthropic_api_key="sk-...",
        model="claude-opus-4"
    )

    goal = {
        "id": "goal_123",
        "description": "Add database migration for user table",
        "estimated_cost": 2.0
    }

    error = "ModuleNotFoundError: No module named 'alembic'"

    context = {
        "repo_path": "/path/to/repo",
        "recent_commits": ["abc123: Add user model"],
        "files_modified": ["models/user.py"]
    }

    action = await analyzer.analyze(goal, error, context)

    print(f"Action Type: {action.action_type.value}")
    print(f"Description: {action.description}")
    print(f"Confidence: {action.confidence:.0%}")
    print("\nSteps:")
    for i, step in enumerate(action.steps, 1):
        print(f"{i}. {step}")

asyncio.run(recover_from_failure())
```

**Example Output:**

```
Action Type: alternative
Description: Install missing dependency and retry migration
Confidence: 85%

Steps:
1. Install alembic: pip install alembic
2. Verify installation: alembic --version
3. Initialize alembic if needed: alembic init migrations
4. Retry original migration command
```

**Recovery Action Types:**

| Type | When Used | Example |
|------|-----------|---------|
| `ALTERNATIVE` | Known workaround exists | "Use SQLAlchemy's create_all() instead of Alembic" |
| `DIAGNOSTICS` | Need more information | "Run `pytest --collect-only` to see which tests are discovered" |
| `UNBLOCK` | Clear steps to fix | "Install missing dependency: pip install requests" |
| `ESCALATE` | Human intervention needed | "Requires production database credentials" |

### Integration with RecoveryManager

The Level2Analyzer integrates with the existing RecoveryManager:

```python
from swarm_attack.chief_of_staff.recovery import RecoveryManager
from swarm_attack.chief_of_staff.level2_recovery import Level2Analyzer

# Initialize with Level 2 support
level2 = Level2Analyzer(api_key="sk-...", model="claude-opus-4")
recovery_mgr = RecoveryManager(level2_analyzer=level2)

# On failure, RecoveryManager can escalate to Level 2
result = await recovery_mgr.handle_failure(goal, error, context)
```

### Integration with AutopilotRunner

The CheckpointUX integrates with AutopilotRunner for interactive approvals:

```python
from swarm_attack.chief_of_staff.autopilot_runner import AutopilotRunner
from swarm_attack.chief_of_staff.checkpoint_ux import CheckpointUX

runner = AutopilotRunner(
    config=config,
    state_manager=state_mgr,
    checkpoint_ux=CheckpointUX()
)

# When checkpoint is triggered, AutopilotRunner uses checkpoint_ux
# to display formatted checkpoint and wait for user decision
await runner.execute_goals(goals)
```

### Test Coverage

**Implemented Tests:** 29 total

**checkpoint_ux.py tests** (`tests/chief_of_staff/test_checkpoint_ux.py`):
- Test checkpoint formatting with all fields
- Test user input validation (approve/reject/skip)
- Test prompt_and_wait full workflow
- Test decision dataclass creation
- Test display formatting edge cases

**level2_recovery.py tests** (`tests/chief_of_staff/test_level2_recovery.py`):
- Test all RecoveryActionType values
- Test RecoveryAction dataclass
- Test analyze() method with mocked API responses
- Test prompt building with various contexts
- Test JSON response parsing
- Test error handling for malformed responses
- Test confidence scoring
- Test async behavior

**Run tests:**

```bash
# All self-healing tests
PYTHONPATH=. pytest tests/chief_of_staff/test_checkpoint_ux.py -v
PYTHONPATH=. pytest tests/chief_of_staff/test_level2_recovery.py -v

# Specific test
PYTHONPATH=. pytest tests/chief_of_staff/test_level2_recovery.py::test_analyze_alternative_action -v
```

### Configuration

Add self-healing options to `config.yaml`:

```yaml
chief_of_staff:
  autopilot:
    # Enable Level 2 recovery
    enable_level2_recovery: true

    # Level 2 recovery model
    level2_model: "claude-opus-4"

    # Interactive checkpoints
    enable_checkpoint_ux: true

    # Auto-retry after recovery suggestion
    auto_retry_after_recovery: false  # Default: require manual approval
```

### Future Enhancements

Planned improvements to Self-Healing:

1. **Recovery History** - Track successful recovery actions to build precedent
2. **Automatic Retries** - Auto-apply high-confidence recovery actions
3. **Recovery Metrics** - Dashboard showing recovery success rates
4. **Multi-Step Recovery** - Chain multiple recovery actions together
5. **Recovery Templates** - Predefined recovery patterns for common failures

## Configuration Options

Add these to your `config.yaml` under the `chief_of_staff.autopilot` section:

```yaml
chief_of_staff:
  autopilot:
    # Execution strategy (default: continue_on_block)
    execution_strategy: "continue_on_block"  # or "sequential", "parallel_safe"

    # Risk thresholds
    risk_checkpoint_threshold: 0.5  # Score > this requires checkpoint
    risk_block_threshold: 0.8       # Score > this blocks execution

    # Auto-approve behavior
    auto_approve_low_risk: true     # Skip checkpoint for low-risk goals

    # Checkpoint budget (limits interruptions)
    checkpoint_budget: 3            # Max checkpoints before auto-logging

    # Context in checkpoints
    show_similar_decisions: true    # Show past similar decisions
```

### Configuration Reference

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `execution_strategy` | string | `"continue_on_block"` | How to handle blocked goals: `"sequential"` (stop on first block), `"continue_on_block"` (skip blocked, continue), `"parallel_safe"` (run independent goals in parallel) |
| `risk_checkpoint_threshold` | float | `0.5` | Risk score threshold for requiring checkpoint |
| `risk_block_threshold` | float | `0.8` | Risk score threshold for blocking execution |
| `auto_approve_low_risk` | bool | `true` | Auto-approve goals with risk < checkpoint threshold |
| `checkpoint_budget` | int | `3` | Maximum checkpoints per session before switching to auto-log mode |
| `show_similar_decisions` | bool | `true` | Include past similar decisions in checkpoint context |

### Execution Strategies Explained

#### Sequential (Old Behavior)
```yaml
execution_strategy: "sequential"
```

Stops on the first blocked or failed goal. Conservative but can stall progress.

**Example:**
```
Goal 1: ✓ Complete
Goal 2: ✗ BLOCKED (high risk)
Goal 3: ⏸ Not attempted (execution stopped)
```

#### Continue on Block (Default)
```yaml
execution_strategy: "continue_on_block"
```

Skips blocked goals and continues with remaining work. Maximizes progress while respecting safety.

**Example:**
```
Goal 1: ✓ Complete
Goal 2: ⚠ SKIPPED (blocked by high risk)
Goal 3: ✓ Complete
Goal 4: ⚠ SKIPPED (depends on Goal 2)
Goal 5: ✓ Complete
```

#### Parallel Safe
```yaml
execution_strategy: "parallel_safe"
```

Runs independent goals in parallel when safe. Fastest but requires careful dependency management.

## Progress Watch Mode

Monitor Chief of Staff execution in real-time:

```bash
swarm-attack cos progress --watch
```

This refreshes every 5 seconds and shows:
- Goals completed/total with percentage
- Current goal being executed
- Budget spent/remaining
- Time elapsed
- Checkpoint count

**Example Output:**
```
Chief of Staff Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Goals: 12/20 (60%) ████████████░░░░░░░░
Budget: $18.50 / $25.00 (74%)
Time: 45m / 120m
Checkpoints: 2 / 3

Current: Implement user authentication endpoint
Status: IN_PROGRESS (3m elapsed)
Risk: 0.35 (LOW - auto-approved)

Recent:
  ✓ Create user model (2m, $1.20, auto-approved)
  ✓ Add database migration (1m, $0.80, auto-approved)
  ⚠ Configure production database (CHECKPOINT - awaiting approval)
```

Press `Ctrl+C` to exit watch mode.

## Use Cases

### Use Case 1: Low-Risk Routine Work

**Scenario:** Adding a new API endpoint with tests

```python
goal = DailyGoal(
    description="Add GET /api/users endpoint with pagination",
    estimated_cost_usd=2.0,
)

# Risk factors:
# - cost: 2.0 / 15.0 = 13% → 0.22 score
# - scope: 3 files (api/, tests/, models/) → 0.6 score (includes core)
# - reversibility: 0.2 (reversible via git)
# - precedent: 0.2 (80% success on similar API work)
# - confidence: 0.1 (90% approval rate)

# Total risk: (0.22*0.30) + (0.6*0.25) + (0.2*0.20) + (0.2*0.15) + (0.1*0.10)
#           = 0.066 + 0.15 + 0.04 + 0.03 + 0.01 = 0.296

# Decision: PROCEED (auto-approved, risk < 0.5)
```

The system executes immediately without human intervention.

### Use Case 2: Medium-Risk Structural Change

**Scenario:** Refactoring authentication system

```python
goal = DailyGoal(
    description="Refactor authentication to use JWT tokens",
    estimated_cost_usd=8.0,
)

# Risk factors:
# - cost: 8.0 / 15.0 = 53% → 0.88 score
# - scope: 12 files (auth/, api/, models/, tests/) → 1.0 score
# - reversibility: 0.2 (reversible)
# - precedent: 0.5 (no similar work found)
# - confidence: 0.4 (60% approval on auth changes)

# Total risk: (0.88*0.30) + (1.0*0.25) + (0.2*0.20) + (0.5*0.15) + (0.4*0.10)
#           = 0.264 + 0.25 + 0.04 + 0.075 + 0.04 = 0.669

# Decision: CHECKPOINT (requires human review, 0.5 < risk < 0.8)
```

The system pauses and presents:
- Risk breakdown showing why it scored 0.669
- Similar past decisions (if available)
- Suggested action: "Review scope - affects 12 core files"

Human approves or rejects based on context.

### Use Case 3: High-Risk Dangerous Operation

**Scenario:** Deleting deprecated database tables

```python
goal = DailyGoal(
    description="Delete deprecated user_sessions and auth_tokens tables",
    estimated_cost_usd=1.0,
)

# Risk factors:
# - cost: 1.0 / 15.0 = 7% → 0.12 score
# - scope: 2 files (migrations/, database/) → 0.5 score
# - reversibility: 1.0 (IRREVERSIBLE - contains "delete")
# - precedent: 0.8 (no similar deletions succeeded)
# - confidence: 0.7 (30% approval on delete operations)

# Total risk: (0.12*0.30) + (0.5*0.25) + (1.0*0.20) + (0.8*0.15) + (0.7*0.10)
#           = 0.036 + 0.125 + 0.20 + 0.12 + 0.07 = 0.551

# Decision: CHECKPOINT (0.5 < risk < 0.8)
```

But if the description was "Drop production database and reset schema":

```python
# Risk factors would include:
# - reversibility: 1.0 (irreversible)
# - precedent: 1.0 (no successful precedent)
# Total risk would exceed 0.8

# Decision: BLOCK (execution prevented entirely)
```

The system refuses to execute and logs:
```
BLOCKED: Risk score 0.85 exceeds block threshold
Rationale: Contains irreversible operations; No similar successful precedent
Suggested: Break into smaller tasks or get explicit approval
```

### Use Case 4: Budget Management

**Scenario:** Checkpoint budget limits interruptions

```python
# Session config
autopilot:
  checkpoint_budget: 3  # Max 3 checkpoints before auto-logging

# During execution:
# Checkpoint 1: Medium-risk DB migration → PAUSED for approval
# Checkpoint 2: Medium-risk API refactor → PAUSED for approval
# Checkpoint 3: Medium-risk auth change → PAUSED for approval

# Budget exhausted!
# Checkpoint 4: Medium-risk email service → AUTO-LOGGED (not paused)
#   System logs the checkpoint but continues execution
#   Review checkpoint log after session completes
```

This prevents excessive interruptions while maintaining audit trail.

## Best Practices

### 1. Tune Thresholds for Your Team

Start with defaults and adjust based on your risk tolerance:

```yaml
# Conservative team (pause more often)
autopilot:
  risk_checkpoint_threshold: 0.4  # Lower threshold
  risk_block_threshold: 0.7
  auto_approve_low_risk: false    # Review everything

# Aggressive team (maximize autonomy)
autopilot:
  risk_checkpoint_threshold: 0.6  # Higher threshold
  risk_block_threshold: 0.85
  auto_approve_low_risk: true
  checkpoint_budget: 5            # More checkpoints allowed
```

### 2. Review Checkpoint Logs

After sessions with checkpoint budget exhaustion:

```bash
# Check what was auto-logged
cat .swarm/chief-of-staff/daily-log/YYYY-MM-DD.md | grep "CHECKPOINT (auto-logged)"
```

Review these decisions to ensure quality.

### 3. Use Continue-on-Block for Parallel Work

When you have independent goals:

```yaml
execution_strategy: "continue_on_block"
```

This maximizes progress even if some goals are blocked:
- Frontend work continues even if backend is blocked
- Documentation continues even if implementation is blocked
- Tests continue even if deployment is blocked

### 4. Monitor Risk Score Trends

Track risk scores over time to identify patterns:

### 5. Build Precedent Database

The system learns from successful episodes:
- More successful precedents → lower precedent factor → lower risk
- More approvals → lower confidence factor → lower risk

Complete similar work successfully to train the system.

## Technical Details

### Integration Points

The Jarvis MVP components integrate with:

1. **AutopilotRunner** - Calls PreFlightChecker before executing each goal to gate execution
2. **CheckpointSystem** - Pauses on traditional triggers (UX/cost/architecture/scope/hiccup); risk gating happens in pre-flight, not inside checkpoints
3. **EpisodeStore** - Provides historical data for precedent factor (when available)
4. **PreferenceLearner** - Provides approval patterns for confidence factor (when available)

### Performance

Risk scoring is **fast**:
- Typical calculation: < 10ms
- No external API calls
- Runs in-memory with local data

Preflight checks are **cheap**:
- Budget check: O(1)
- Dependency check: O(n) where n = dependencies
- Risk assessment: < 10ms

Total preflight overhead: **< 20ms per goal**

### Data Storage

Risk assessments are stored in episode metadata:

Pre-flight decisions are evaluated in-memory before each goal is executed. Persisting
risk assessments alongside episodes is a future enhancement; current integration
gates execution but does not yet write the assessment to episode logs.

## Troubleshooting

### Issue: Too Many Checkpoints

**Symptom:** System pauses too frequently for approval

**Solutions:**
1. Increase `risk_checkpoint_threshold`:
   ```yaml
   risk_checkpoint_threshold: 0.6  # Was 0.5
   ```

2. Increase `checkpoint_budget`:
   ```yaml
   checkpoint_budget: 5  # Was 3
   ```

3. Break goals into smaller pieces to reduce scope factor

### Issue: Not Enough Safety

**Symptom:** System auto-approves risky work

**Solutions:**
1. Decrease `risk_checkpoint_threshold`:
   ```yaml
   risk_checkpoint_threshold: 0.4  # Was 0.5
   ```

2. Disable auto-approve:
   ```yaml
   auto_approve_low_risk: false
   ```

3. Review episode history to improve precedent scoring

### Issue: Blocked Goals You Want to Execute

**Symptom:** Goals blocked by high risk score (>0.8)

**Solutions:**
1. Break goal into smaller sub-goals:
   - "Refactor auth system" → "Add JWT token model", "Update login endpoint", "Add token refresh"
   - Smaller goals have lower scope and cost factors

2. Increase `risk_block_threshold` (use caution):
   ```yaml
   risk_block_threshold: 0.85  # Was 0.8
   ```

3. Get explicit approval and manually execute:
   ```bash
   # Review the blocked goal
   swarm-attack cos status

   # Execute with explicit approval
   swarm-attack cos execute --goal-id=blocked-goal-id --force
   ```

### Issue: Poor Precedent Scoring

**Symptom:** Unknown/new work always gets high precedent scores

**Solutions:**
1. Build episode history by completing similar work:
   - Each successful episode improves future precedent scores
   - System learns what "similar" means from descriptions

2. Import historical episodes:
   ```bash
   swarm-attack cos import-episodes --from-git-history
   ```

3. Manually seed precedent database with successful patterns

## Future Enhancements

Planned improvements to Jarvis MVP:

1. **Machine Learning Risk Models** - Train on historical data to improve factor weights
2. **Custom Factor Weights** - Per-team configuration of factor importance
3. **Risk Visualization** - Dashboard showing risk trends over time
4. **Smart Batching** - Group similar low-risk goals for batch approval
5. **Learning from Rejections** - Improve confidence scoring from rejection patterns
6. **Integration with GitHub** - Pull PR review patterns into confidence factor
7. **Cost Prediction** - Better estimation using historical episode costs

## Summary

The Jarvis MVP transforms Chief of Staff from a simple orchestrator into an **intelligent automation partner**:

- **Risk Scoring Engine** provides nuanced 5-factor risk assessment
- **PreFlight Checker** validates goals before execution starts
- **Intelligent Checkpoints** balance autonomy with safety
- **Self-Healing System** enables intelligent recovery from failures with LLM-powered analysis

Together, these enable:
- Faster execution (auto-approve low-risk work)
- Better safety (block dangerous operations)
- Less interruption (checkpoint budget management)
- Smarter decisions (learning from history)
- Intelligent recovery (self-diagnose and suggest fixes)

Configure thresholds to match your team's risk tolerance and watch Swarm Attack work more intelligently.
