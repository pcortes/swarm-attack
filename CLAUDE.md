# Swarm Attack

Autonomous AI-powered multi-agent development automation system. Orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

## System Overview

Swarm Attack provides two main pipelines:

### 1. Feature Swarm Pipeline
```
PRD → Spec Debate → Issues → Tests → Code → Verify → Done
```

Automates feature development from product requirements to working code:
- **SpecAuthor** generates engineering specs from PRDs
- **SpecCritic** reviews specs and scores them
- **SpecModerator** improves specs based on feedback
- **TestWriter** creates tests before code (TDD)
- **Coder** implements features to pass tests
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
- **Coder** implements approved fixes

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
│   │   ├── coder/
│   │   ├── test-writer/
│   │   ├── verifier/
│   │   ├── feature-spec-author/
│   │   ├── feature-spec-critic/
│   │   ├── feature-spec-moderator/
│   │   ├── bug-researcher/
│   │   ├── root-cause-analyzer/
│   │   ├── fix-planner/
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
6. **Fixing** - Applying fix via Claude Code
7. **Fixed** - Bug resolved, tests passing

## Key Files

| File | Purpose |
|------|---------|
| `swarm_attack/cli.py` | CLI entry point |
| `swarm_attack/orchestrator.py` | Feature pipeline orchestration |
| `swarm_attack/bug_orchestrator.py` | Bug bash orchestration |
| `swarm_attack/agents/*.py` | Individual agent implementations |
| `swarm_attack/debate.py` | Spec debate logic |
| `swarm_attack/models/*.py` | Data models and state |

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
