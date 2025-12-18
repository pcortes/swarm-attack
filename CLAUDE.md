# Swarm Attack

Autonomous AI-powered multi-agent development automation system. Orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

## System Overview

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
| `swarm_attack/agents/complexity_gate.py` | Complexity Gate Agent |
| `swarm_attack/debate.py` | Spec debate logic |
| `swarm_attack/models/*.py` | Data models and state |
| `.claude/skills/coder/SKILL.md` | Implementation Agent prompt |
| `swarm_attack/skills/complexity-gate/SKILL.md` | Complexity Gate prompt |

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
