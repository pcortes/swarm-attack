# Swarm Attack

**Working Directory:** `/Users/philipjcortes/Desktop/swarm-attack`
**Branch:** `master`

---

## FIRST: Verify Your Working Directory

**Before reading further, run these commands:**

```bash
cd /Users/philipjcortes/Desktop/swarm-attack
pwd      # Must show: /Users/philipjcortes/Desktop/swarm-attack
git branch   # Must show: * master
```

**STOP if you're not in the correct worktree.**

---

## COO Integration

This project is managed by the COO (Chief Operating Officer) agent at `/Users/philipjcortes/coo`. All specs and prompts should follow COO archival conventions.

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

### Research Commands (Open Source Librarian)

| Command | Description |
|---------|-------------|
| `research "query"` | Research external libraries with evidence-backed responses |
| `research --depth quick "query"` | Quick lookup (less thorough) |
| `research --depth thorough "query"` | Deep comprehensive research |
| `research --library NAME "query"` | Focus on specific library |
| `research --type TYPE "query"` | Override request type (conceptual, implementation, context, comprehensive) |

**Note:** Options must come before the query argument.

**Example:**
```bash
# Basic research
swarm-attack research "How do I use pydantic validators?"

# Focused search (options must come before query)
swarm-attack research --library tenacity --depth quick "retry logic"

# Implementation details
swarm-attack research --library httpx --type implementation "connection pooling"
```

**Key Files:**
| File | Purpose |
|------|---------|
| `.claude/skills/open-source-librarian/SKILL.md` | Agent skill prompt |
| `swarm_attack/agents/librarian.py` | Agent implementation |
| `swarm_attack/cli/research.py` | CLI command handler |
| `docs/LIBRARIAN.md` | Full documentation |

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
6. **Fixing** - Applying fix via BugFixerAgent (intelligent Claude CLI-based editing)
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
| `swarm_attack/agents/bug_fixer.py` | BugFixerAgent for applying approved fixes |
| `swarm_attack/debate.py` | Spec debate logic |
| `swarm_attack/models/*.py` | Data models and state |
| `.claude/skills/coder/SKILL.md` | Implementation Agent prompt |
| `.claude/skills/bug-fixer/SKILL.md` | BugFixerAgent prompt |
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
| **BugFixerAgent** | Applies approved fix plans via Claude CLI |

## Agent Research Capability (v0.4.2)

All agents now have access to codebase exploration tools by default. This enables intelligent context gathering during LLM execution.

### BaseAgent DEFAULT_TOOLS

BaseAgent defines default tools available to all agents:

```python
class BaseAgent(ABC):
    # Default tools available to all agents (codebase exploration)
    DEFAULT_TOOLS: list[str] = ["Read", "Glob", "Grep"]

    @classmethod
    def get_tools(cls) -> list[str]:
        """Get the default tools for this agent type."""
        return cls.DEFAULT_TOOLS.copy()
```

### Tool Set Configuration

Agent-specific tool sets are managed via `swarm_attack/agents/tool_sets.py`:

```python
from swarm_attack.agents.tool_sets import get_tools_for_agent

# Get tools for a specific agent
tools = get_tools_for_agent("CoderAgent")  # Returns ["Read", "Glob", "Grep"]
tools = get_tools_for_agent("IssueCreatorAgent")  # Returns ["Read", "Glob", "Grep"]
```

### Agent Integration

Agents that need codebase exploration use `get_tools_for_agent()`:

**ComplexityGateAgent:**
```python
from swarm_attack.agents.tool_sets import get_tools_for_agent
allowed_tools = get_tools_for_agent("ComplexityGateAgent")
result = self.llm.run(prompt, allowed_tools=allowed_tools)
```

**IssueCreatorAgent:**
```python
from swarm_attack.agents.tool_sets import get_tools_for_agent
allowed_tools = get_tools_for_agent("IssueCreatorAgent")
result = self.llm.run(prompt, allowed_tools=allowed_tools)
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/agents/base.py` | BaseAgent.DEFAULT_TOOLS, get_tools() class method |
| `swarm_attack/agents/tool_sets.py` | get_tools_for_agent() function |
| `tests/unit/test_tool_sets.py` | Tool set unit tests |
| `tests/integration/test_agent_research.py` | Integration tests |

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

## Bug Fixer Agent (v0.4.0)

Intelligent LLM-based agent that applies fix plans to the codebase using Claude CLI for smart code editing.

### Why BugFixerAgent?

The previous implementation used brittle string replacement (`content.replace(current_code, proposed_code)`) which failed when:
- Whitespace didn't match exactly
- Proposed code had formatting issues (missing blank lines)
- Current code didn't exist in file exactly as expected

BugFixerAgent fixes this by using Claude CLI to intelligently apply changes.

### Key Features

| Feature | Description |
|---------|-------------|
| **Read First** | Reads files before editing to understand context |
| **Edit Tool** | Uses Edit tool instead of blind string replacement |
| **Formatting** | Ensures proper blank lines and indentation |
| **Syntax Validation** | Validates Python syntax after each change |
| **Graceful Adaptation** | Handles files that have drifted from expected state |

### Workflow

1. **Load Skill Prompt** - Load `.claude/skills/bug-fixer/SKILL.md`
2. **Format Fix Plan** - Convert FixPlan to markdown with all changes
3. **Build Prompt** - Inject fix plan into skill template
4. **Call Claude CLI** - Execute with `--print --output-format json`
5. **Parse Result** - Extract success, files_changed, syntax_verified
6. **Return AgentResult** - Success with files changed or failure with error

### Integration with Bug Orchestrator

```python
# In bug_orchestrator.fix():
fixer = BugFixerAgent(self.config, logger=self._logger)
fixer_result = fixer.run({
    "fix_plan": state.fix_plan,
    "bug_id": bug_id,
})
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/agents/bug_fixer.py` | BugFixerAgent implementation |
| `.claude/skills/bug-fixer/SKILL.md` | Skill prompt with detailed instructions |
| `tests/unit/test_bug_fixer.py` | Comprehensive unit tests (21 tests) |

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

**Current State:** Complete - all components implemented and functional.

| Component | Status | Notes |
|-----------|--------|-------|
| Models (`models.py`) | ✅ Complete | Finding, Severity, CommitInfo, etc. |
| Discovery (`discovery.py`) | ✅ Complete | Git log parsing |
| Categorizer (`categorizer.py`) | ✅ Complete | Commit classification |
| Prompts (`prompts.py`) | ✅ Complete | 5 expert prompts |
| Dispatcher helpers | ✅ Complete | `_parse_findings()`, `_call_claude_cli()` |
| Dispatcher `_run_agent()` | ✅ Complete | Calls Claude CLI via asyncio.to_thread |
| Synthesis (`synthesis.py`) | ✅ Complete | Score calculation, verdict |
| Report (`report.py`) | ✅ Complete | XML/JSON/Markdown output |
| CLI (`review_commits.py`) | ✅ Complete | Command registered |

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

## Codex CLI Error Handling (v0.4.1)

Robust error classification and auth handling for Codex CLI invocations.

### Auth Classification Control

The `CodexCliRunner` supports configurable auth error handling via `skip_auth_classification`:

```python
from swarm_attack.codex_client import CodexCliRunner

# Default: auth errors raise CodexAuthError
runner = CodexCliRunner(config=config)

# Skip auth classification: auth errors raise InvocationError instead
runner = CodexCliRunner(config=config, skip_auth_classification=True)
```

**Use cases:**
- Set `skip_auth_classification=True` when preflight auth checks are disabled
- Useful in CI environments or with pre-authenticated sessions

### Error Classification Rules

The error classifier follows strict rules to avoid false positives:

| Rule | Behavior |
|------|----------|
| **Success returncode (0)** | Never triggers any error classification |
| **Check stderr only** | Ignores stdout (which may contain PRDs/specs mentioning "authentication") |
| **Specific patterns** | Uses anchored patterns like `Token exchange error`, not generic `authentication` |

### Auth Error Patterns (stderr only)

```python
# Matched patterns:
"not logged in"
"login required"
"invalid session"
"session expired"
"please run `codex login`"
"AuthenticationError:"
"401 Unauthorized"
"Token exchange error"
```

### Rate Limit Patterns (stderr only)

```python
# Matched patterns:
"rate limit exceeded"    # More specific than just "rate limit"
"rate_limit_exceeded"
"too many requests"
"429"
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/codex_client.py` | CodexCliRunner with skip_auth_classification |
| `swarm_attack/errors.py` | ErrorClassifier with pattern matching |
| `tests/unit/test_codex_error_classification.py` | False positive prevention tests |
| `tests/unit/test_codex_auth_patterns.py` | Auth pattern tests |

## Memory System (Phase 5)

Persistent cross-session learning system with pattern detection, recommendations, and semantic search.

See `docs/MEMORY.md` for full documentation.

### Components

| Component | Purpose |
|-----------|---------|
| **MemoryStore** | Core JSON persistence layer |
| **PatternDetector** | Detects recurring issues (schema drift, fixes, failure clusters) |
| **RecommendationEngine** | Provides contextual suggestions based on history |
| **SemanticSearch** | Weighted keyword search with category boosting |
| **MemoryIndex** | O(1) inverted index for fast lookups |

### Agent Integration

**CoderAgent** receives historical recommendations:
- Extracts class names from issue body
- Queries memory for prior schema drift conflicts
- Injects warnings into prompt

**VerifierAgent** records patterns:
- Records success/failure patterns to memory
- Links patterns to fixes for future recommendations
- Tags entries with `schema_drift` and class names

### CLI Commands

```bash
# Basic commands
swarm-attack memory stats                    # Show statistics
swarm-attack memory list --category schema_drift  # List entries
swarm-attack memory prune --older-than 30    # Remove old entries

# Phase 5 commands
swarm-attack memory patterns                 # Detect patterns
swarm-attack memory patterns --category schema_drift  # Filter by category
swarm-attack memory recommend schema_drift --context '{"class_name": "MyClass"}'
swarm-attack memory search "MyClass error"   # Semantic search
swarm-attack memory search "error" --category schema_drift --limit 5

# Persistence commands
swarm-attack memory save backup.json         # Save to file
swarm-attack memory load backup.json         # Load from file
swarm-attack memory export drift.json --category schema_drift
swarm-attack memory import drift.json        # Merge entries
swarm-attack memory compress                 # Deduplicate entries
swarm-attack memory analytics                # Show analytics report
```

### Configuration

```yaml
memory:
  file_path: .swarm/memory/store.json  # Default location
```

---

## Context Flow & Schema Drift Prevention (v0.3.0)

Prevents duplicate class definitions across issues by tracking what each issue creates or modifies.

### How It Works

1. **CoderAgent** extracts classes from both created AND modified files
2. **StateStore** saves class definitions in module registry
3. **Next issue** receives rich context showing existing classes with source code
4. **Coder prompt** includes "DO NOT RECREATE" warnings with import statements

### Memory-Based Pre-Implementation Warnings (v0.4.2)

CoderAgent and VerifierAgent now integrate with `MemoryStore` for cross-session schema drift learning:

**CoderAgent** (`memory_store` parameter):
- `_extract_potential_classes(issue_body)` - Extracts class names from issue body (Interface Contract, Acceptance Criteria)
- `_get_schema_warnings(class_names)` - Queries memory store for prior schema drift conflicts
- `_format_schema_warnings(warnings)` - Formats warnings for prompt injection

**VerifierAgent** (`memory_store` parameter):
- Records schema drift conflicts to memory store when detected
- Enables cross-session learning - conflicts in one session inform future sessions
- Tags entries with `schema_drift` and class name for queryability

**Usage:**
```python
from swarm_attack.memory.store import MemoryStore

memory = MemoryStore(config)
coder = CoderAgent(config, memory_store=memory)
verifier = VerifierAgent(config, memory_store=memory)
```

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

### Parsing Modified Files from LLM Response (v0.4.1)

The `_parse_modified_files()` method extracts file paths from LLM response text:

```python
# Supported markers:
"# MODIFIED FILE: path/to/file.py"
"#MODIFIED FILE: path/to/file.py"  # no space
"Modified: `path/to/file.py`"
"Modified: path/to/file.py"
"Updated: `path/to/file.py`"
"Updated: path/to/file.py"
```

**Features:**
- Handles whitespace variations
- Deduplicates file paths
- Filters to Python files by default (`python_only=True`)

### Extended Language Support (v0.4.1)

Class extraction now supports additional patterns:

| Language | Patterns Supported |
|----------|-------------------|
| **Python** | `class Foo`, nested classes (any indentation) |
| **TypeScript** | `class`, `export class`, `abstract class`, `export abstract class` |
| **Dart** | `class`, `abstract class` |

### Empty Output Validation (v0.4.1)

CoderAgent rejects empty file outputs to prevent marking issues as "Done" with no implementation:

```python
# Validation logic:
real_files = {k: v for k, v in files.items() if not k.endswith('.gitkeep')}
if not real_files:
    # Logs "coder_no_files_generated"
    # Emits IMPL_FAILED event
    # Returns failure result
```

### Stdlib Module Whitelist (v0.4.1)

The following modules are recognized as stdlib (not flagged as external dependencies):

```python
STDLIB_MODULES = frozenset([
    '__future__', 'abc', 'asyncio', 'collections', 'copy', 'dataclasses',
    'datetime', 'enum', 'functools', 'importlib', 'inspect', 'io',
    'itertools', 'json', 'logging', 'math', 'os', 'pathlib', 'pickle',
    'random', 're', 'shutil', 'string', 'sys', 'tempfile', 'time',
    'traceback', 'typing', 'unittest', 'uuid', 'warnings', 'contextlib',
    'threading', 'multiprocessing', 'subprocess', 'socket', 'struct',
    'textwrap', 'hashlib', 'base64', 'argparse', 'configparser',
    # ... and more
])
```

### Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/agents/coder.py:_extract_outputs()` | Extracts classes from created + modified files |
| `swarm_attack/agents/coder.py:_parse_modified_files()` | Parses modified file markers from LLM response |
| `swarm_attack/agents/coder.py:_extract_classes_from_content()` | Multi-language class extraction |
| `swarm_attack/state_store.py:get_module_registry()` | Builds registry including modified files |
| `swarm_attack/context_builder.py` | Formats rich context with source code |

## Autopilot Orchestration System (v0.5.0)

Comprehensive autopilot infrastructure with safety guards, session continuity, automated verification, and COO integration. Implemented via 8 parallel subagents following TDD (690 tests).

### Component Overview

| Phase | Component | Tests | Purpose |
|-------|-----------|-------|---------|
| 1 | SafetyNetHook | 87 | Blocks destructive commands |
| 1 | ContinuityLedger | 57 | Session state persistence |
| 1 | HandoffManager | 30 | Session handoff between agents |
| 1 | ContextMonitor | 40 | Context window monitoring |
| 2 | AutoVerifyHook | 68 | Auto-runs pytest/ruff after changes |
| 2 | PVIPipeline | 82 | Plan-Verify-Implement pipeline |
| 2 | CommandHistory | 56 | Command history with secret redaction |
| 3 | StatuslineHUD | 52 | Real-time statusline HUD |
| 3 | DashboardStatusView | 53 | Dashboard at .swarm/status.json |
| 4 | ModelVariants | 55 | Model configuration (opus/sonnet/haiku) |
| 4 | PrioritySync | 55 | Syncs with COO priorities |
| 4 | SpecArchival | 38 | Archives specs to COO |

---

## Safety & Continuity System (v0.5.0)

Provides session safety nets, state persistence, and handoff capabilities.

### SafetyNetHook

Blocks dangerous commands before execution.

**Blocked Commands:**

| Pattern | Example |
|---------|---------|
| `rm -rf /` variants | Recursive deletion of root/home |
| `git push --force` | Force pushes to protected branches |
| `DROP TABLE` / `TRUNCATE` | SQL destructive commands |
| `chmod/chown -R /` | Recursive permission changes |

**Configuration:** `.claude/safety-net.yaml`

```yaml
enabled: true
block_patterns:
  - 'custom-dangerous-pattern'
allow_patterns:
  - 'rm -rf ./node_modules'  # Safe patterns
```

**Override:** Set `SAFETY_NET_OVERRIDE=1` environment variable (logs warning)

### ContinuityLedger

Tracks session state for handoff and recovery.

**Records:**
- Goals (pending, in_progress, completed)
- Decisions (with rationale and alternatives)
- Blockers (with severity and resolution)
- Handoff notes (for next session)

**Storage:** `.swarm/continuity/{session_id}.json`

### HandoffManager

Automates session handoff generation and injection.

**Workflow:**
1. **PreCompact Hook** - Generate handoff before context compaction
2. **Save** - Persist to `.swarm/handoffs/handoff-{session_id}.json`
3. **SessionStart Hook** - Inject prior session context

### ContextMonitor

Monitors context window usage with warning levels.

| Level | Percentage | Action |
|-------|------------|--------|
| OK | < 70% | Normal operation |
| WARN | 80% | Consider handoff soon |
| CRITICAL | 90% | Immediate handoff recommended |

**Key Files:**

| File | Purpose |
|------|---------|
| `swarm_attack/hooks/safety_net.py` | SafetyNetHook, DestructiveCommandError |
| `swarm_attack/continuity/ledger.py` | ContinuityLedger |
| `swarm_attack/continuity/handoff.py` | HandoffManager, Handoff |
| `swarm_attack/statusline/context_monitor.py` | ContextMonitor, ContextLevel |

---

## Verification & History System (v0.5.0)

Provides automated verification and command history with secret redaction.

### AutoVerifyHook

PostToolUse hook that automatically runs tests and linting after file changes.

**Triggers:**
- Python file writes (`.py` files)
- Git commits

**Verification Steps:**
1. Run pytest on related test files
2. Run ruff/flake8 on modified files
3. Save record to `.swarm/verification/`
4. Raise `VerificationError` if tests fail

### PVIPipeline (Plan-Verify-Implement)

Three-stage pipeline for structured implementation.

```
Plan → Validate → Implement
  ↓       ↓          ↓
Steps  Checks    Gates + Files
```

| Stage | Output | Handoff To |
|-------|--------|------------|
| **Plan** | PlanResult (steps with complexity) | Validate |
| **Validate** | ValidationResult (blocking checks) | Implement |
| **Implement** | ImplementationResult (gates, files) | - |

### CommandHistory

Persistent command history with secret redaction.

**Redacted Patterns:**
- `sk-*` API keys
- `AKIA*` AWS keys
- `ghp_*`, `gho_*` GitHub tokens
- JWT tokens (eyJ...)
- Bearer tokens

**Storage:** `.swarm/history/command_history.json`

**Key Files:**

| File | Purpose |
|------|---------|
| `swarm_attack/hooks/auto_verify.py` | AutoVerifyHook, VerificationResult |
| `swarm_attack/orchestration/pvi_pipeline.py` | PVIPipeline, PlanStage, ValidateStage |
| `swarm_attack/logging/command_history.py` | CommandHistory, redact_secrets |

---

## UI/Dashboard System (v0.5.0)

Real-time status display and dashboard for autopilot orchestration.

### StatuslineHUD

Heads-Up Display for Claude Code statusline.

**Display Format:**
```
Opus 4.5 | 45% | Coder | Implementing API endpoint... | 3/7
```

| Component | Example |
|-----------|---------|
| Model | Opus 4.5, Sonnet 4, Haiku 3.5 |
| Context | 45% |
| Agent | Coder, Verifier, idle |
| Task | Truncated to 40 chars |
| Progress | 3/7 (completed/total) |

### DashboardStatusView

Writes `.swarm/status.json` on state changes.

**JSON Structure:**
```json
{
  "agents": [{"name": "coder", "status": "active", "current_task": "..."}],
  "tasks": [{"id": "task-1", "title": "...", "status": "done"}],
  "context": {"model": "claude-opus-4-5-20251101", "context_percentage": 45.0},
  "last_update": "2025-12-25T10:30:00Z"
}
```

**Key Files:**

| File | Purpose |
|------|---------|
| `swarm_attack/statusline/hud.py` | HUD, HUDConfig, HUDStatus |
| `swarm_attack/dashboard/status_view.py` | StatusView, AgentEntry, TaskEntry |

---

## COO Integration System (v0.5.0)

Integration with COO (Chief Operating Officer) for priorities, budgets, and archival.

### ModelVariants Configuration

Configure models per project with task queue isolation.

**config.yaml:**
```yaml
model_variants:
  default_model:
    model_id: claude-opus-4-5-20251101
    provider: anthropic

  projects:
    desktop-miami:
      model:
        model_id: claude-sonnet-4-20250514
        max_tokens: 8192
      task_queue:
        max_concurrent_tasks: 2
```

**Providers:** anthropic, openai, azure, bedrock, vertex, custom

### PrioritySync

Synchronizes with COO priority board and enforces budget limits.

**Configuration:**
```yaml
coo:
  coo_path: /Users/philipjcortes/coo
  project_name: swarm-attack
  daily_budget_limit: 100.0
  monthly_budget_limit: 2500.0
  sync_enabled: true
```

### SpecArchival

Archives approved specs to COO with metadata.

**Archived Path Format:**
```
COO/projects/{project}/specs/{YYYY-MM-DD}_{filename}.md
```

**Key Files:**

| File | Purpose |
|------|---------|
| `swarm_attack/config/model_variants.py` | ModelConfig, ModelVariantsConfig |
| `swarm_attack/coo_integration/priority_sync.py` | PrioritySyncManager, COOConfig |
| `swarm_attack/coo_integration/spec_archival.py` | SpecArchiver, ArchivalMetadata |

---

## Autopilot CLI Command (v0.5.0)

Run autopilot to execute today's goals with budget/time limits.

### Usage

```bash
# Run with defaults ($10 budget, 2h duration)
swarm-attack cos autopilot

# Custom budget and duration
swarm-attack cos autopilot -b 5.0 -d 1h

# Stop at first approval checkpoint
swarm-attack cos autopilot --until approval

# Resume a paused session
swarm-attack cos autopilot --resume <session-id>

# List paused sessions
swarm-attack cos autopilot --list

# Dry run (show what would execute)
swarm-attack cos autopilot --dry-run
```

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--budget` | `-b` | 10.0 | Budget limit in USD |
| `--duration` | `-d` | "2h" | Duration limit (e.g., 2h, 90m) |
| `--until` | `-u` | None | Stop at matching checkpoint |
| `--resume` | `-r` | None | Resume paused session by ID |
| `--dry-run` | - | False | Show without executing |
| `--list` | `-l` | False | List paused sessions |
| `--cancel` | - | None | Cancel session by ID |

### Session States

| State | Meaning |
|-------|---------|
| COMPLETED | All goals finished |
| PAUSED | Waiting at checkpoint |
| FAILED | Goal execution failed |
