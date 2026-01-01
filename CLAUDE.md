# Swarm Attack QA Agent

**Working Directory:** `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Branch:** `feature/adaptive-qa-agent`

---

## FIRST: Verify Your Working Directory

**Before reading further, run these commands:**

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
pwd      # Must show: /Users/philipjcortes/Desktop/swarm-attack-qa-agent
git branch   # Must show: * feature/adaptive-qa-agent
```

**STOP if you're not in the correct worktree.**

---

## COO Integration

This project is managed by the COO (Chief Operating Officer) agent at `/Users/philipjcortes/Desktop/coo`. All specs and prompts should follow COO archival conventions.

### Implementation Rules

1. **Must be TDD** - Write failing tests before implementing
2. **Expert Team Definition Required** - Every prompt MUST have `<team_structure>` with QA experts
3. **Test Coverage Focus** - QA specs must include coverage requirements
4. **Integration Testing Required** - Must test interaction with parent swarm-attack system

---

---

## IMPORTANT: Manual Testing Required

**After implementing ANY new feature or fix, you MUST run manual tests.**

See: `.claude/prompts/expert-tester.md` for the full testing protocol.

### Quick Test Checklist
```bash
# 1. Run automated tests for your changes
PYTHONPATH=. pytest tests/unit/test_<your_module>.py -v

# 2. Run integration tests
PYTHONPATH=. pytest tests/integration/ -v --tb=short

# 3. Test imports work
python3 -c "from swarm_attack.<your_module> import <YourClass>; print('OK')"

# 4. Create timestamped test report
mkdir -p .swarm/qa/test-reports
# Save findings to: .swarm/qa/test-reports/<feature>-YYYYMMDD-HHMMSS.md
```

**DO NOT consider your implementation complete until manual tests pass.**

---

## System Overview

Autonomous AI-powered multi-agent development automation system. Orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

Swarm Attack provides two main pipelines:

### 1. Feature Swarm Pipeline
```
PRD → Spec Debate → Issues → Complexity Gate → Implementation → Verify → Done
```

Automates feature development from product requirements to working code:
- **SpecAuthor** generates engineering specs from PRDs
- **SpecCritic** reviews specs and scores them
- **SpecModerator** improves specs based on feedback
- **IssueCreator** creates GitHub issues with Interface Contracts and sizing guidelines
- **ComplexityGate** validates issue sizing before implementation (prevents timeout)
- **Implementation Agent** handles full TDD cycle (tests + code + iteration)
- **Verifier** runs tests and validates implementations

### 2. Bug Bash Pipeline
```
Bug Report → Reproduce → Analyze → Plan → Approve → Fix → Verify
```

Automates bug investigation and fixing:
- **BugResearcher** reproduces bugs and gathers evidence
- **RootCauseAnalyzer** identifies the root cause
- **Debate System** validates analysis through Author-Critic rounds
- **FixPlanner** generates comprehensive fix plans
- **Implementation Agent** applies approved fixes

## Architecture: Thick-Agent Model

### Why Thick-Agent?

The previous **thin-agent** pipeline had a critical flaw: **context loss at each handoff (~40% per transition)**.

**Old Pipeline (Removed):**
```
Issue Creator → Test Writer → Coder → Verifier
     (4 separate context windows, ~40% context loss per handoff)
```

**New Pipeline (Thick-Agent with Complexity Gate):**
```
Issue Creator → Complexity Gate → Implementation Agent (Coder) → Verifier
                      ↓                    ↓
               Validates sizing     Single context window handles:
               before burning       1. Read context (issue, spec, integration points)
               expensive tokens     2. Write tests (RED phase)
                                    3. Implement code (GREEN phase)
                                    4. Iterate until tests pass
```

The **Implementation Agent** is a "thick" agent with full context—it sees everything at once. This eliminates handoff losses and enables real TDD iteration.

## Quick Start

```bash
# Install
pip install -e .

# Feature development
swarm-attack init my-feature          # Create PRD template
swarm-attack run my-feature           # Run spec debate
swarm-attack approve my-feature       # Approve spec
swarm-attack issues my-feature        # Create GitHub issues
swarm-attack greenlight my-feature    # Enable implementation
swarm-attack run my-feature           # Implement issues

# Bug fixing
swarm-attack bug init "description" --id bug-id --test tests/path.py -e "error"
swarm-attack bug analyze bug-id       # Reproduce + Analyze + Plan
swarm-attack bug approve bug-id       # Approve fix plan
swarm-attack bug fix bug-id           # Apply fix
```

## CLI Commands

### Feature Commands

| Command | Description |
|---------|-------------|
| `status` | Show feature dashboard or detailed status |
| `init <feature>` | Create PRD template |
| `run <feature>` | Run pipeline (spec or implementation) |
| `run <feature> --issue N` | Run specific issue |
| `approve <feature> [--auto\|--manual]` | Approve spec |
| `reject <feature>` | Reject spec with feedback |
| `issues <feature>` | Create GitHub issues from spec |
| `greenlight <feature>` | Enable implementation phase |
| `smart <feature>` | Interactive mode with recovery |
| `recover <feature>` | Handle interrupted sessions |
| `unblock <feature>` | Unblock stuck feature |
| `import-spec <feature>` | Import external spec |

### Bug Commands

| Command | Description |
|---------|-------------|
| `bug list` | List all bug investigations |
| `bug init "desc" --id ID --test PATH -e "error"` | Create bug investigation |
| `bug analyze <bug-id>` | Run full analysis pipeline |
| `bug status <bug-id>` | Show bug investigation status |
| `bug approve <bug-id> [--auto\|--manual]` | Approve fix plan |
| `bug fix <bug-id>` | Execute approved fix |
| `bug reject <bug-id>` | Reject bug (won't fix) |
| `bug unblock <bug-id>` | Unblock stuck bug |

### Review Commands

| Command | Description |
|---------|-------------|
| `review-commits` | Review recent commits with expert panel |
| `review-commits --since="1 week ago"` | Review commits from time range |
| `review-commits --branch=NAME` | Review specific branch |
| `review-commits --strict` | Fail on medium+ severity issues |
| `review-commits --output xml\|json\|markdown` | Set output format |
| `review-commits --save PATH` | Save report to file |

## Project Structure

```
your-project/
├── config.yaml                    # Swarm Attack config
├── .claude/
│   ├── prds/                      # Your PRDs
│   │   └── feature-name.md
│   ├── skills/                    # Agent skill definitions
│   │   ├── coder/                 # Implementation Agent (TDD)
│   │   ├── verifier/
│   │   ├── issue-creator/
│   │   ├── feature-spec-author/
│   │   ├── feature-spec-critic/
│   │   ├── feature-spec-moderator/
│   │   └── ...
│   └── specs/                     # Legacy location
├── specs/                         # Generated specs
│   └── feature-name/
│       ├── spec-draft.md
│       └── spec-final.md
├── .swarm/
│   ├── state/                     # Feature state files
│   │   └── feature-name.json
│   └── bugs/                      # Bug investigation state
│       └── bug-id/
│           ├── state.json
│           ├── report.md
│           ├── reproduction.md
│           ├── root-cause-analysis.md
│           └── fix-plan.md
└── tests/
    └── generated/                 # Generated test files
        └── feature-name/
            └── test_issue_1.py
```

## Configuration

Create `config.yaml` in your project root:

```yaml
github:
  repo: "owner/repo"
  token_env_var: "GITHUB_TOKEN"

claude:
  binary: "claude"
  max_turns: 6
  timeout_seconds: 300

tests:
  command: "pytest"
  args: ["-v"]

spec_debate:
  max_rounds: 5
  success_threshold: 0.85
```

## Feature Lifecycle

```
NO_PRD → PRD_READY → SPEC_IN_PROGRESS → SPEC_NEEDS_APPROVAL
                                              ↓
    COMPLETE ← IMPLEMENTING ← READY_TO_IMPLEMENT ← SPEC_APPROVED
```

### Human Checkpoints
1. **PRD Creation** - Write `.claude/prds/<feature>.md`
2. **Spec Approval** - Review and approve generated spec
3. **Issue Greenlight** - Enable implementation to proceed

## Bug Investigation Lifecycle

```
Created → Reproducing → Analyzing → Planned → Approved → Fixing → Fixed
```

### Bug Phases
1. **Created** - Bug initialized with description and test path
2. **Reproducing** - Running test to confirm bug exists
3. **Analyzing** - LLM analyzing root cause with debate
4. **Planned** - Fix plan generated and debated
5. **Approved** - Human approved the fix plan
6. **Fixing** - Applying fix via Implementation Agent
7. **Fixed** - Bug resolved, tests passing

## Implementation Agent (TDD Workflow)

The Implementation Agent uses a 7-phase TDD workflow:

### Phase 1: Read Context First
- Read issue description with Interface Contract
- Read spec/PRD for broader context
- Find integration points (who calls this code?)
- Find pattern references (existing similar code)

### Phase 2: Write Tests First (RED)
- Create `tests/generated/{feature}/test_issue_{N}.py`
- Tests verify interface contracts
- Tests should FAIL initially (no implementation yet)

### Phase 3: Run Tests (Expect Failure)
- Execute: `pytest tests/generated/{feature}/test_issue_{N}.py -v`
- Verify tests fail for the RIGHT reasons

### Phase 4: Implement Code (GREEN)
- Write minimal code to pass tests
- Follow existing patterns in codebase
- Include all interface methods

### Phase 5: Iterate Until Tests Pass
- Run tests after each change
- Fix failures one by one
- Maximum 5 iteration cycles

### Phase 6: Run Full Test Suite
- Execute: `pytest tests/ -v`
- All tests must pass (no regressions)

### Phase 7: Mark Complete
- All new tests pass
- All existing tests pass
- Interface contracts satisfied

## Interface Contracts

Issues include **Interface Contracts** that specify exactly what methods must be implemented:

```markdown
## Interface Contract (REQUIRED)

**Required Methods:**
- `from_dict(cls, data: dict) -> ClassName`
- `to_dict(self) -> dict`

**Pattern Reference:** See `swarm_attack/config.py:BugBashConfig`
```

This ensures the Implementation Agent knows the exact interface requirements before writing tests and code.

## Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/cli.py` | CLI entry point |
| `swarm_attack/orchestrator.py` | Feature pipeline orchestration |
| `swarm_attack/bug_orchestrator.py` | Bug bash orchestration |
| `swarm_attack/agents/*.py` | Individual agent implementations |
| `swarm_attack/agents/coder.py` | Implementation Agent (TDD) |
| `swarm_attack/agents/complexity_gate.py` | Complexity Gate Agent |
| `swarm_attack/debate.py` | Spec debate logic |
| `swarm_attack/models/*.py` | Data models and state |
| `.claude/skills/coder/SKILL.md` | Implementation Agent prompt |
| `swarm_attack/skills/complexity-gate/SKILL.md` | Complexity Gate prompt |
| `swarm_attack/chief_of_staff/campaign_planner.py` | Campaign backward planning |
| `swarm_attack/chief_of_staff/campaign_executor.py` | Daily goal execution |
| `swarm_attack/chief_of_staff/feedback.py` | Feedback storage and retrieval |
| `swarm_attack/cli/chief_of_staff.py` | Chief of Staff CLI commands |

## Complexity Gate

The Complexity Gate prevents implementation timeouts by validating issue complexity before burning expensive Opus tokens.

### How It Works

```
Issue Creator → Complexity Gate → [OK] → Coder (with adjusted max_turns)
                      ↓
                 [Too Complex]
                      ↓
               Return with split suggestions
```

### Sizing Guidelines

Issues must be completable in ~15-20 LLM turns. The gate uses tiered estimation:

| Tier | Criteria | Action |
|------|----------|--------|
| **Instant Pass** | ≤5 acceptance criteria AND ≤3 methods | Pass (no LLM call) |
| **Instant Fail** | >12 criteria OR >8 methods | Fail with split suggestions |
| **Borderline** | Between thresholds | LLM estimation via Haiku |

### Issue Sizing Limits

| Size | Acceptance Criteria | Methods | Max Turns |
|------|---------------------|---------|-----------|
| Small | 1-4 | 1-2 | 10 |
| Medium | 5-8 | 3-5 | 15 |
| Large | 9-12 | 6-8 | 20 |
| **Too Large** | >12 | >8 | **MUST SPLIT** |

### Split Strategies

When an issue is too complex, the gate suggests how to split it:
1. **By layer**: data model → API → UI
2. **By operation**: CRUD operations as separate issues
3. **By trigger/case**: Split multiple triggers into groups of 3
4. **By phase**: setup/config → core logic → integration

## Debugging

```bash
# Enable debug output
SWARM_DEBUG=1 swarm-attack run my-feature

# Check feature state
cat .swarm/state/my-feature.json | python -m json.tool

# Check bug state
swarm-attack bug status bug-id
```

## Recovery

```bash
# Feature stuck
swarm-attack unblock my-feature
swarm-attack unblock my-feature --phase SPEC_NEEDS_APPROVAL

# Bug stuck
swarm-attack bug unblock bug-id
```

## Agent Overview

| Agent | Purpose |
|-------|---------|
| **SpecAuthor** | Generates engineering specs from PRDs |
| **SpecCritic** | Reviews specs and scores them |
| **SpecModerator** | Improves specs based on feedback |
| **IssueCreator** | Creates GitHub issues with Interface Contracts and sizing guidelines |
| **ComplexityGate** | Estimates issue complexity; rejects oversized issues with split suggestions |
| **Implementation Agent** | TDD in single context (tests + code + iteration) with dynamic max_turns |
| **Verifier** | Validates implementations and creates commits |
| **BugResearcher** | Reproduces bugs and gathers evidence |
| **RootCauseAnalyzer** | Identifies root cause of bugs |
| **FixPlanner** | Generates comprehensive fix plans |

## Debate Retry Handler (v0.3.1)

Handles transient errors during spec and bug debate loops with exponential backoff retry.

### Error Categories

| Category | Error Types | Behavior |
|----------|-------------|----------|
| **Transient** | Rate limit (429), Timeout, Server errors (5xx) | Retry up to 3 times with exponential backoff |
| **Fatal** | Auth errors (401), CLI not found | Fail immediately (no retry) |
| **Agent Failure** | Agent returns `success=False` | Pass through (no retry) |

### Backoff Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 3 | Maximum retry attempts |
| `backoff_base_seconds` | 5.0 | Initial delay between retries |
| `backoff_multiplier` | 2.0 | Exponential multiplier (5s → 10s → 20s) |
| `max_backoff_seconds` | 60.0 | Maximum delay cap |

### Usage

The handler is automatically used by:
- `Orchestrator.run_spec_debate_only()` for spec critic/moderator
- `BugOrchestrator._run_root_cause_debate()` for bug debate
- `BugOrchestrator._run_fix_plan_debate()` for fix plan debate

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/debate_retry.py` | DebateRetryHandler implementation |
| `tests/unit/test_debate_retry.py` | Comprehensive unit tests (20 tests) |

## Chief of Staff (Autonomous Development Partner)

An autonomous AI Tech Lead that manages your daily development workflow with minimal intervention.

### Quick Start

```bash
# Morning briefing
swarm-attack cos standup --github

# Run autopilot with budget
swarm-attack cos autopilot --budget 100

# Check pending checkpoints
swarm-attack cos checkpoints

# Approve/reject checkpoints
swarm-attack cos approve <checkpoint-id> --notes "reason"
swarm-attack cos reject <checkpoint-id> --notes "reason"

# Mid-day status
swarm-attack cos checkin

# End of day
swarm-attack cos wrapup
```

### Checkpoint Triggers

The Chief of Staff pauses for human approval when:

| Trigger | Description |
|---------|-------------|
| COST_SINGLE | Single action exceeds cost threshold |
| COST_CUMULATIVE | Cumulative spending exceeds daily budget |
| UX_CHANGE | User-facing changes detected |
| ARCHITECTURE | Structural/architectural changes |
| SCOPE_CHANGE | Deviation from approved plan |
| HICCUP | Unexpected errors or blockers |

### Key Components

| Component | Purpose |
|-----------|---------|
| **StateGatherer** | Collects repo state (features, bugs, git, GitHub) |
| **DailyLogManager** | Manages daily logs, standups, decisions |
| **GoalTracker** | Tracks goals, compares plan vs actual |
| **AutopilotRunner** | Executes goals with checkpoint gates |
| **CheckpointStore** | Persists checkpoint decisions |
| **CampaignPlanner** | Multi-day backward planning from deadlines |
| **CampaignExecutor** | Executes daily campaign goals |
| **FeedbackStore** | Persists human feedback for learning |

### Daily Workflow

```
Morning Standup → Goal Selection → Autopilot Execution
                                        ↓
                              Checkpoint triggered?
                                   ↓        ↓
                                  Yes       No
                                   ↓        ↓
                            Wait for    Continue
                            approval    execution
```

### Bug Triage Protocol

When running Chief of Staff and encountering bugs in the tooling itself:

1. **STOP** - Pause Chief of Staff operations
2. **Analyze** - Use expert agents to root cause the bug
3. **Report** - Present triage report with fix plan
4. **Wait** - Get approval before implementing fixes
5. **Resume** - Continue Chief of Staff operations after fix

See `prompts/CHIEF_OF_STAFF_PROMPT.md` for the full autonomous operation prompt.

### Campaign Management (v0.3.0)

Multi-day campaign planning and execution for extended development efforts.

#### Campaign CLI Commands

| Command | Description |
|---------|-------------|
| `cos campaign-create <name> --deadline YYYY-MM-DD` | Create a new campaign |
| `cos campaign-list` | List all campaigns with status |
| `cos campaign-status <id>` | Show detailed campaign status |
| `cos campaign-run <id>` | Execute today's goals |
| `cos campaign-replan <id>` | Regenerate plans based on progress |

#### Campaign Workflow

```
Create Campaign → Plan (backward from deadline) → Execute Daily → Replan if Behind
```

#### Usage Examples

```bash
# Create a 7-day campaign
swarm-attack cos campaign-create "Q1 Feature Sprint" --deadline 2025-01-31

# Check campaign status
swarm-attack cos campaign-status q1-feature-sprint

# Run today's goals
swarm-attack cos campaign-run q1-feature-sprint

# Replan if behind schedule
swarm-attack cos campaign-replan q1-feature-sprint
```

#### Key Components

| Component | Purpose |
|-----------|---------|
| **CampaignPlanner** | Backward planning from deadline, generates day plans |
| **CampaignExecutor** | Executes daily goals via AutopilotRunner |
| **CampaignStore** | Persists campaign state to `.swarm/chief-of-staff/campaigns/` |

### Feedback Management (v0.3.0)

Record and manage human feedback for continuous improvement.

#### Feedback CLI Commands

| Command | Description |
|---------|-------------|
| `cos feedback-list [-n LIMIT] [-t TAG]` | List recorded feedback |
| `cos feedback-add "text" [-t TAG] [-c CONTEXT]` | Add new feedback |
| `cos feedback-clear --tag TAG` | Clear feedback by tag |
| `cos feedback-clear --before YYYY-MM-DD` | Clear old feedback |
| `cos feedback-clear --all` | Clear all (requires confirmation) |

#### Usage Examples

```bash
# Add feedback with tag
swarm-attack cos feedback-add "Prefer shorter function names" --tag style

# List recent feedback
swarm-attack cos feedback-list -n 5

# Filter by tag
swarm-attack cos feedback-list --tag security

# Clear old feedback
swarm-attack cos feedback-clear --before 2025-01-01

# Clear by tag
swarm-attack cos feedback-clear --tag deprecated
```

#### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/chief_of_staff/feedback.py` | FeedbackStore and HumanFeedback model |
| `swarm_attack/cli/chief_of_staff.py` | CLI commands implementation |

## Auto-Approval System (v0.3.0)

Enables autonomous operation by auto-approving routine decisions while pausing for human review on risky changes.

### Auto-Approvers

| Approver | Threshold | Conditions |
|----------|-----------|------------|
| **SpecAutoApprover** | Score ≥ 0.85 | After 2+ debate rounds |
| **IssueAutoGreenlighter** | Complexity gate passed | Has interface contract, no circular deps |
| **BugAutoApprover** | Confidence ≥ 0.9 | Risk level low/medium, no API breaks |

### CLI Usage

```bash
# Feature approve with auto-approval mode
swarm-attack approve my-feature --auto

# Feature approve with manual mode (requires human approval)
swarm-attack approve my-feature --manual

# Bug approve with auto-approval mode
swarm-attack bug approve bug-id --auto

# Bug approve with manual mode
swarm-attack bug approve bug-id --manual

# Check current mode
swarm-attack status my-feature
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/auto_approval/spec.py` | Spec auto-approval logic |
| `swarm_attack/auto_approval/issue.py` | Issue greenlight logic |
| `swarm_attack/auto_approval/bug.py` | Bug fix auto-approval |
| `swarm_attack/auto_approval/overrides.py` | Manual mode overrides |

## Event Infrastructure (v0.3.0)

Pub/sub event system for agent communication and audit logging.

### Event Types

```python
from swarm_attack.events.types import EventType

# Available event types (28 total):
EventType.SPEC_APPROVED      # Spec passed debate
EventType.SPEC_REJECTED      # Spec failed debate
EventType.ISSUE_CREATED      # GitHub issue created
EventType.ISSUE_READY        # Issue ready for implementation
EventType.IMPL_STARTED       # Coder started work
EventType.IMPL_VERIFIED      # Coder finished successfully
EventType.IMPL_FAILED        # Coder failed
EventType.BUG_ANALYZED       # Root cause identified
EventType.BUG_FIXED          # Bug fix verified
EventType.AUTO_APPROVAL_TRIGGERED  # Auto-approval triggered
EventType.MANUAL_OVERRIDE    # Manual mode override
# ... and more
```

### Using the EventBus

```python
from swarm_attack.events.bus import get_event_bus, EventType

bus = get_event_bus()

# Subscribe to events
def on_impl_complete(event):
    print(f"Issue #{event.issue_number} completed!")

bus.subscribe(EventType.IMPL_VERIFIED, on_impl_complete)

# Emit events (typically done by agents)
bus.emit_phase_transition("my-feature", "IMPLEMENTING", "COMPLETE")
```

### Event Persistence

Events are stored in JSONL format at `.swarm/events/events-YYYY-MM-DD.jsonl`:

```python
from swarm_attack.events.persistence import EventPersistence

persistence = EventPersistence(config)

# Query recent events
events = persistence.get_recent(limit=50)

# Query by feature
events = persistence.get_by_feature("my-feature")
```

## Session Initialization Protocol (v0.3.0)

Standardized 5-step initialization for all agent sessions.

### Protocol Steps

1. **Verify Working Directory** - Confirm correct repo/worktree
2. **Verify Issue Assignment** - Load issue context and dependencies
3. **Run Verification Tests** - Execute pre-existing tests to establish baseline
4. **Load Prior Context** - Get completed summaries and module registry
5. **Initialize Progress Tracking** - Start progress.txt logging

### Components

| Component | Purpose |
|-----------|---------|
| **SessionInitializer** | Orchestrates the 5-step protocol |
| **ProgressLogger** | Append-only logging to `.swarm/features/{id}/progress.txt` |
| **SessionFinalizer** | Ensures all tests pass before marking complete |
| **VerificationTracker** | JSON status at `.swarm/features/{id}/verification.json` |

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/session_initializer.py` | Main initialization logic |
| `swarm_attack/progress_logger.py` | Progress file management |
| `swarm_attack/session_finalizer.py` | Completion verification |
| `swarm_attack/verification_tracker.py` | Verification state tracking |

## Universal Context Builder (v0.3.0)

Provides right-sized context to each agent type with token budget management.

### Agent Context Profiles

| Agent | Token Budget | Depth | Includes |
|-------|--------------|-------|----------|
| **Coder** | 15,000 | full_source | Project instructions, module registry, completed summaries, dependencies |
| **SpecAuthor** | 5,000 | summary | Project instructions, architecture overview, existing modules |
| **SpecCritic** | 3,000 | summary | Project instructions, review guidelines, past feedback |
| **SpecModerator** | 3,000 | summary | Project instructions, review guidelines |
| **IssueCreator** | 4,000 | compact | Project instructions, existing issues, module registry |
| **BugResearcher** | 10,000 | full_source | Project instructions, test structure, recent changes |
| **RootCauseAnalyzer** | 8,000 | full_source | Project instructions, test structure, module registry |
| **FixPlanner** | 5,000 | summary | Project instructions, module registry, completed summaries |
| **Verifier** | 3,000 | compact | Project instructions, test patterns, coverage gaps |
| **ComplexityGate** | 2,000 | compact | Project instructions |

### Usage

```python
from swarm_attack.universal_context_builder import UniversalContextBuilder

builder = UniversalContextBuilder(config, state_store)

# Build context for a specific agent
context = builder.build_context_for_agent(
    agent_type="coder",
    feature_id="my-feature",
    issue_number=3,
)

# Context includes:
# - project_instructions (from CLAUDE.md)
# - module_registry (classes from prior issues)
# - completed_summaries (what prior issues built)
# - test_structure (test file locations)
```

### BaseAgent Integration

All agents can use context injection:

```python
class MyAgent(BaseAgent):
    def run(self, context: dict):
        # Get formatted context for prompt
        context_section = self._get_context_prompt_section()
        prompt = f"{context_section}\n\n{self._build_task_prompt()}"
```

## QA Session Extension (v0.3.0)

Coverage tracking and regression detection for QA workflows.

### Components

| Component | Purpose |
|-----------|---------|
| **CoverageTracker** | Captures test coverage baselines and computes deltas |
| **RegressionDetector** | Detects new test failures vs baseline |
| **QASessionExtension** | Orchestrates coverage + regression checks |

### Blocking Conditions

Sessions are blocked when:
- **Critical regressions** detected (previously passing tests now fail)
- **Coverage drop > 10%** from baseline

### Usage

```python
from swarm_attack.qa.session_extension import QASessionExtension

extension = QASessionExtension(config)

# Start of session - capture baseline
extension.on_session_start(feature_id="my-feature")

# ... run implementation ...

# End of session - check for regressions
result = extension.on_session_complete(feature_id="my-feature")

if result.should_block:
    print(f"Blocked: {result.block_reason}")
else:
    print("Session completed successfully")
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/qa/coverage_tracker.py` | Coverage baseline and delta |
| `swarm_attack/qa/regression_detector.py` | Regression detection |
| `swarm_attack/qa/session_extension.py` | Orchestration |

## Commit Quality Review (v0.3.2)

Multi-agent commit review system with expert panel analysis. Reviews recent commits through specialized engineering directors.

### Implementation Status

**Current State:** Partial implementation - helper methods complete, agent dispatch placeholder.

| Component | Status | Notes |
|-----------|--------|-------|
| Models (`models.py`) | ✅ Complete | Finding, Severity, CommitInfo, etc. |
| Discovery (`discovery.py`) | ✅ Complete | Git log parsing |
| Categorizer (`categorizer.py`) | ✅ Complete | Commit classification |
| Prompts (`prompts.py`) | ✅ Complete | 5 expert prompts |
| Dispatcher helpers | ✅ Complete | `_parse_findings()`, `_call_claude_cli()` |
| Dispatcher `_run_agent()` | ⏳ Placeholder | Returns empty list; needs asyncio.to_thread wiring |
| Synthesis (`synthesis.py`) | ✅ Complete | Score calculation, verdict |
| Report (`report.py`) | ✅ Complete | XML/JSON/Markdown output |
| CLI (`review_commits.py`) | ✅ Complete | Command registered |

**Next Steps:** Wire `_run_agent()` to call `_call_claude_cli()` via `asyncio.to_thread()` and parse response with `_parse_findings()`.

### Expert Panel

| Expert | Title | Focus Area | Category Mapping |
|--------|-------|------------|------------------|
| **Dr. Elena Vasquez** | Director of Site Reliability | Production bug verification, incident correlation, error handling | `BUG_FIX` commits |
| **Marcus Chen** | Director of Quality Engineering | Test coverage, mock accuracy, regression risk | `TEST_CHANGE` commits |
| **Dr. Aisha Patel** | Director of Engineering Excellence | Implementation completeness, dead code, technical debt | `FEATURE` commits |
| **James O'Brien** | Director of Developer Experience | Documentation value, spec traceability, session exhaust detection | `DOCUMENTATION` commits |
| **Dr. Sarah Kim** | Chief Architect | API contracts, interface completeness, architectural consistency | `REFACTOR` commits |

### Expert Skepticism

Each expert applies domain-specific skepticism:

| Expert | Skeptical Of |
|--------|--------------|
| **Dr. Elena Vasquez** | Fixes for 'bugs' without production evidence; speculative fixes without Sentry errors or customer reports |
| **Marcus Chen** | Tests that mock incorrectly (wrong method names, wrong return types); 'test improvements' that reduce coverage |
| **Dr. Aisha Patel** | 'Complete' implementations that are partial; TODO/FIXME comments in 'finished' code |
| **James O'Brien** | Documentation with transient session data; 'comprehensive' docs that will never be referenced |
| **Dr. Sarah Kim** | Changes that break implicit contracts; 'refactoring' that changes behavior |

### CLI Commands

```bash
# Review commits from last 24 hours
swarm-attack review-commits

# Review commits from last week
swarm-attack review-commits --since="1 week ago"

# Review specific branch
swarm-attack review-commits --branch=feature/xyz

# Strict mode (fail on medium+ issues)
swarm-attack review-commits --strict

# Output formats
swarm-attack review-commits --output markdown  # default
swarm-attack review-commits --output xml
swarm-attack review-commits --output json

# Save report to file
swarm-attack review-commits --save report.md
```

### Commit Categories

| Category | Detection | Expert Assigned |
|----------|-----------|-----------------|
| `BUG_FIX` | Message contains `fix:`, `bugfix:`, `hotfix:` | Dr. Elena Vasquez |
| `FEATURE` | Message contains `feat:`, `add:`, `new:`, `implement:` | Dr. Aisha Patel |
| `REFACTOR` | Message contains `refactor:`, `cleanup:`, `restructure:` | Dr. Sarah Kim |
| `TEST_CHANGE` | All changed files are in `tests/` | Marcus Chen |
| `DOCUMENTATION` | All changed files are `.md` | James O'Brien |
| `CHORE` | Message contains `chore:`, `build:`, `ci:`, `deps:` | General review |
| `OTHER` | No clear pattern | General review |

### Severity Levels

| Severity | Score Impact | Description |
|----------|--------------|-------------|
| `LOW` | -0.05 | Minor style or documentation issues |
| `MEDIUM` | -0.15 | Issues that should be addressed |
| `HIGH` | -0.30 | Significant problems requiring fixes |
| `CRITICAL` | -0.50 | Blocking issues, potential reverts |

### Verdicts

| Verdict | Score Threshold | Action |
|---------|-----------------|--------|
| `LEAVE` | ≥ 0.8 | Commit is fine, no action needed |
| `FIX` | 0.5 - 0.8 | Commit has issues that should be fixed |
| `REVERT` | < 0.5 or CRITICAL finding | Commit should be reverted |

### TDD Fix Plans

For medium+ severity findings, the system generates TDD fix plans:

1. **Red Phase** - Failing test to write
2. **Green Phase** - Minimal fix steps
3. **Refactor Phase** - Cleanup suggestions

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/commit_review/models.py` | CommitInfo, CommitCategory, Finding, Severity, Verdict, TDDPlan |
| `swarm_attack/commit_review/discovery.py` | Git log parsing with `discover_commits()` |
| `swarm_attack/commit_review/categorizer.py` | Commit classification |
| `swarm_attack/commit_review/prompts.py` | Expert-specific review prompts (5 directors) |
| `swarm_attack/commit_review/dispatcher.py` | Parallel agent dispatch with asyncio |
| `swarm_attack/commit_review/synthesis.py` | Finding aggregation, scoring, verdict |
| `swarm_attack/commit_review/tdd_generator.py` | TDD fix plan generation |
| `swarm_attack/commit_review/report.py` | XML, JSON, Markdown output |
| `swarm_attack/cli/review_commits.py` | CLI command handler |
| `.claude/skills/commit-quality-review/SKILL.md` | Skill definition |

### COO Integration

The commit quality review integrates with COO's orchestration layer:

**Midday Check-in Integration:**
- Called from `strategic_advisor.py` during midday mode
- Reviews commits since last checkpoint (delta-aware)
- Output appears in `## Commit Quality Review` section
- Checkpoint updated after review completes

**Daily Digest Integration:**
- Called from `consolidated_digest.py` during nightly run
- Reviews all commits from past 24 hours
- Includes portfolio summary across all 5 managed projects
- Projects: desktop-miami, moderndoc, swarm-attack, swarm-attack-qa, coo

**CLI Subprocess Contract:**
```bash
# COO invokes via subprocess:
swarm-attack review-commits --since "{checkpoint_time}" --output json

# Expected JSON output includes:
# - commit_reviews[]: sha, message, score, verdict, findings[]
# - overall_score: float (0.0 - 1.0)
# - summary: string
```

**Graceful Degradation:**
- If `swarm-attack` CLI unavailable, COO logs warning and skips review
- If individual project review fails, others continue (fault isolation)
- Timeout: 300 seconds per project

## Context Flow & Schema Drift Prevention (v0.3.0)

Prevents duplicate class definitions across issues by tracking what each issue creates or modifies.

### How It Works

1. **CoderAgent** extracts classes from both created AND modified files
2. **StateStore** saves class definitions in module registry
3. **Next issue** receives rich context showing existing classes with source code
4. **Coder prompt** includes "DO NOT RECREATE" warnings with import statements

### Module Registry

```python
# What the coder sees in context:
## Existing Classes (MUST IMPORT - DO NOT RECREATE)

### From `swarm_attack/models/session.py` (Issue #1)
**Import:** `from swarm_attack.models.session import AutopilotSession`

**Class `AutopilotSession`:**
```python
@dataclass
class AutopilotSession:
    session_id: str
    feature_id: str
    started_at: str
    goals: list[str] = field(default_factory=list)
```

### Modified File Tracking

When an issue modifies an existing file (adds classes to it), those classes are now tracked:

```python
# Issue #1 modifies models/base.py and adds ConfigParser class
outputs = coder._extract_outputs(
    files={},  # No new files
    files_modified=["models/base.py"],  # Modified existing file
)
# ConfigParser is now in module registry for Issue #2 to see
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/agents/coder.py:_extract_outputs()` | Extracts classes from created + modified files |
| `swarm_attack/state_store.py:get_module_registry()` | Builds registry including modified files |
| `swarm_attack/context_builder.py` | Formats rich context with source code |
