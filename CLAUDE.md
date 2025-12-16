# Swarm Attack

Autonomous AI-powered multi-agent development automation system. Orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

## System Overview

Swarm Attack provides two main pipelines:

### 1. Feature Swarm Pipeline
```
PRD → Spec Debate → Issues → Implementation → Verify → Done
```

Automates feature development from product requirements to working code:
- **SpecAuthor** generates engineering specs from PRDs
- **SpecCritic** reviews specs and scores them
- **SpecModerator** improves specs based on feedback
- **IssueCreator** creates GitHub issues with Interface Contracts
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

**New Pipeline (Thick-Agent):**
```
Issue Creator → Implementation Agent (Coder) → Verifier
                        ↓
            Single context window handles:
            1. Read context (issue, spec, integration points)
            2. Write tests (RED phase)
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
| `approve <feature>` | Approve spec |
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
| `bug approve <bug-id>` | Approve fix plan |
| `bug fix <bug-id>` | Execute approved fix |
| `bug reject <bug-id>` | Reject bug (won't fix) |
| `bug unblock <bug-id>` | Unblock stuck bug |

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
| `swarm_attack/debate.py` | Spec debate logic |
| `swarm_attack/models/*.py` | Data models and state |
| `.claude/skills/coder/SKILL.md` | Implementation Agent prompt |

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
| **IssueCreator** | Creates GitHub issues with Interface Contracts |
| **Implementation Agent** | TDD in single context (tests + code + iteration) |
| **Verifier** | Validates implementations and creates commits |
| **BugResearcher** | Reproduces bugs and gathers evidence |
| **RootCauseAnalyzer** | Identifies root cause of bugs |
| **FixPlanner** | Generates comprehensive fix plans |
