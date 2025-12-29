# Swarm Attack

Autonomous AI-powered multi-agent development automation system. Orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

## What It Does

### Feature Swarm Pipeline
```
PRD → Spec Debate → Issues → Complexity Gate → Implementation → Verify → Commit
```

### Bug Bash Pipeline
```
Bug Report → Reproduce → Analyze → Plan → Approve → Fix → Verify
```

Swarm Attack coordinates multiple AI agents to:

**Feature Development:**
1. **Generate specs** from your PRD using SpecAuthor agent
2. **Review & improve** specs through SpecCritic/SpecModerator debate
3. **Create GitHub issues** from approved specs (with Interface Contracts and sizing guidelines)
4. **Validate complexity** with ComplexityGate (prevents timeouts on oversized issues)
5. **Implement features** with Implementation Agent (TDD in single context, dynamic max_turns)
6. **Verify & commit** with Verifier agent

**Bug Investigation:**
1. **Reproduce bugs** with BugResearcher agent
2. **Analyze root cause** with debate-validated analysis
3. **Generate fix plans** with risk assessment
4. **Apply fixes** after human approval
5. **Verify fixes** by running tests

## Architecture: Thick-Agent Model

Swarm Attack uses a **thick-agent** architecture for implementation:

### Why Thick-Agent?

The previous **thin-agent** pipeline (`Issue Creator → Test Writer → Coder → Verifier`) had a critical flaw: **context loss at each handoff (~40% per transition)**.

**Old Pipeline Problems:**
- Test Writer couldn't see what code would call the implementation
- Coder couldn't iterate with tests—had to get them right first try
- Missing interface methods (e.g., `from_dict()`) because no agent saw the full picture

**New Pipeline Solution:**
```
Issue Creator → Complexity Gate → Implementation Agent (Coder) → Verifier
                      ↓                    ↓
               Validates sizing     Single context window handles:
               before burning       1. Read context (issue, spec, integration points)
               expensive tokens     2. Write tests (RED phase)
                                    3. Implement code (GREEN phase)
                                    4. Iterate until tests pass
```

The **Implementation Agent** is a "thick" agent with full context—it sees the issue, spec, integration points, tests, and implementation all at once. This eliminates handoff losses and enables real TDD iteration.

## Installation

```bash
cd ~/Desktop/swarm-attack
pip install -e .
```

Now `swarm-attack` works from any directory.

## Prerequisites

### Required CLIs
```bash
# Claude CLI (requires Anthropic Max subscription)
# Install from: https://docs.anthropic.com/claude-code

# Authenticate
claude auth login
```

### Verify Setup
```bash
claude --version
claude doctor
```

## Quick Start

### 1. Initialize your project
```bash
cd ~/my-project
swarm-attack setup    # Creates config.yaml and .claude/skills/
```

### 2. Write a PRD
```bash
swarm-attack init my-feature   # Creates .claude/prds/my-feature.md
# Edit the PRD with your requirements
```

### 3. Run the full pipeline
```bash
swarm-attack run my-feature      # Generate spec through debate pipeline
swarm-attack approve my-feature  # Approve the spec
swarm-attack issues my-feature   # Create GitHub issues from spec
swarm-attack greenlight my-feature  # Enable implementation
swarm-attack run my-feature      # Implement issues (auto-selects next)
```

### 4. Check status
```bash
swarm-attack status            # Dashboard of all features
swarm-attack status my-feature # Detailed feature status
```

### 5. Bug Bash (investigate and fix bugs)
```bash
# Initialize a bug investigation
swarm-attack bug init "Description of the bug" \
  --id bug-id \
  --test tests/path/to/failing_test.py::TestClass::test_method \
  -e "Error message from failure"

# Run the full analysis pipeline (reproduce -> analyze -> plan)
swarm-attack bug analyze bug-id

# Review the fix plan
swarm-attack bug status bug-id
cat .swarm/bugs/bug-id/fix-plan.md

# Approve and apply the fix
swarm-attack bug approve bug-id
swarm-attack bug fix bug-id

# List all bugs
swarm-attack bug list
```

## Commands

### Feature Commands

| Command | Description |
|---------|-------------|
| `swarm-attack status` | Show all features dashboard |
| `swarm-attack status <feature>` | Show detailed feature status |
| `swarm-attack init <feature>` | Create PRD template |
| `swarm-attack run <feature>` | Run pipeline (spec or implementation based on phase) |
| `swarm-attack run <feature> --issue N` | Run specific issue implementation |
| `swarm-attack approve <feature>` | Approve spec for implementation |
| `swarm-attack reject <feature>` | Reject spec with feedback |
| `swarm-attack issues <feature>` | Create GitHub issues from approved spec |
| `swarm-attack greenlight <feature>` | Enable implementation phase |
| `swarm-attack smart <feature>` | Interactive mode with recovery |
| `swarm-attack recover <feature>` | Recover from blocked/interrupted state |
| `swarm-attack unblock <feature>` | Unblock a stuck feature |
| `swarm-attack import-spec <feature>` | Import external spec file |

### Bug Commands

| Command | Description |
|---------|-------------|
| `swarm-attack bug list` | List all bug investigations |
| `swarm-attack bug init "desc" --id ID --test PATH -e "error"` | Create bug investigation |
| `swarm-attack bug analyze <bug-id>` | Run full analysis (reproduce → analyze → plan) |
| `swarm-attack bug status <bug-id>` | Show bug investigation status |
| `swarm-attack bug approve <bug-id>` | Approve fix plan for implementation |
| `swarm-attack bug fix <bug-id>` | Execute the approved fix |
| `swarm-attack bug reject <bug-id>` | Reject bug (won't fix) |
| `swarm-attack bug unblock <bug-id>` | Unblock a stuck bug |

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

spec_debate:
  max_rounds: 5
  success_threshold: 0.85
```

## Project Structure

When you run swarm-attack in a project, it creates:

```
your-project/
├── config.yaml              # Swarm Attack config
├── .claude/
│   ├── prds/               # Your PRDs go here
│   │   └── my-feature.md
│   ├── specs/              # Generated specs (legacy)
│   └── skills/             # Agent skill definitions
│       ├── coder/          # Implementation Agent (TDD)
│       ├── verifier/
│       ├── issue-creator/
│       ├── issue-splitter/ # Auto-splits complex issues
│       ├── complexity-gate/
│       ├── feature-spec-author/
│       ├── feature-spec-critic/
│       ├── feature-spec-moderator/
│       └── ...
├── specs/                  # Generated specs
│   └── my-feature/
│       ├── spec-draft.md
│       └── spec-final.md
├── tests/
│   └── generated/          # Generated test files
│       └── my-feature/
│           └── test_issue_1.py
└── .swarm/                 # State tracking
    ├── state/
    │   └── my-feature.json
    └── bugs/
        └── bug-id/
            ├── state.json
            └── fix-plan.md
```

## The Debate Pipeline

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│ SpecAuthor │ ──▶ │ SpecCritic │ ──▶ │SpecModerator│
│  (Claude)  │     │  (Claude)  │     │  (Claude)   │
└────────────┘     └────────────┘     └─────┬──────┘
                                            │
                        ┌───────────────────┘
                        ▼
              Score >= 0.85? ──Yes──▶ Ready for Approval
                   │
                  No
                   │
                   ▼
              Round < 5? ──Yes──▶ Back to Critic
                   │
                  No
                   │
                   ▼
              Stalemate (manual intervention)
```

## Implementation Pipeline (Thick-Agent TDD)

```
┌──────────────────────────────────────────────────────┐
│            Implementation Agent (Coder)               │
├──────────────────────────────────────────────────────┤
│  Phase 1: Read Context                                │
│  - Read issue with Interface Contract                 │
│  - Read spec/PRD for broader context                  │
│  - Find integration points (who calls this code?)     │
│  - Find pattern references (existing similar code)    │
├──────────────────────────────────────────────────────┤
│  Phase 2: Write Tests First (RED)                     │
│  - Create tests/generated/{feature}/test_issue_N.py   │
│  - Tests verify interface contracts                   │
│  - Tests should FAIL initially                        │
├──────────────────────────────────────────────────────┤
│  Phase 3: Run Tests (Expect Failure)                  │
│  - pytest tests/generated/{feature}/test_issue_N.py   │
│  - Verify failures are for right reasons              │
├──────────────────────────────────────────────────────┤
│  Phase 4: Implement Code (GREEN)                      │
│  - Write minimal code to pass tests                   │
│  - Follow existing patterns in codebase               │
│  - Include all interface methods                      │
├──────────────────────────────────────────────────────┤
│  Phase 5: Iterate Until Tests Pass                    │
│  - Run tests, fix failures                            │
│  - Maximum 5 iteration cycles                         │
├──────────────────────────────────────────────────────┤
│  Phase 6: Run Full Test Suite                         │
│  - pytest tests/ -v                                   │
│  - All tests must pass (no regressions)               │
├──────────────────────────────────────────────────────┤
│  Phase 7: Mark Complete                               │
│  - All tests pass                                     │
│  - Interface contracts satisfied                      │
└──────────────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│                    Verifier                           │
│  - Runs full test suite                               │
│  - Validates implementation meets spec                │
│  - Creates commit if all passes                       │
└──────────────────────────────────────────────────────┘
```

## Interface Contracts

Issues created by Swarm Attack include **Interface Contracts** that specify exactly what methods must be implemented:

```markdown
## Interface Contract (REQUIRED)

**Required Methods:**
- `from_dict(cls, data: dict) -> ClassName`
- `to_dict(self) -> dict`

**Pattern Reference:** See `swarm_attack/config.py:BugBashConfig`
```

This ensures the Implementation Agent knows the exact interface requirements before writing tests and code.

## Recovery & Troubleshooting

If a feature gets stuck in BLOCKED state (e.g., due to timeout after successful completion):

```bash
# Auto-detect and recover
swarm-attack unblock my-feature

# Or use interactive recovery
swarm-attack recover my-feature

# Force a specific phase
swarm-attack unblock my-feature --phase SPEC_NEEDS_APPROVAL
```

The `unblock` command analyzes spec files on disk to determine if the debate actually succeeded despite the timeout, and automatically transitions to the correct phase.

### Debug Mode

```bash
# Enable debug output
SWARM_DEBUG=1 swarm-attack run my-feature

# Check feature state
cat .swarm/state/my-feature.json | python -m json.tool

# Check bug state
swarm-attack bug status bug-id
```

## Agent Overview

| Agent | Purpose |
|-------|---------|
| **SpecAuthor** | Generates engineering specs from PRDs |
| **SpecCritic** | Reviews specs and scores them |
| **SpecModerator** | Improves specs based on feedback |
| **IssueCreator** | Creates GitHub issues with Interface Contracts and sizing guidelines |
| **ComplexityGate** | Estimates issue complexity; triggers auto-split for oversized issues |
| **IssueSplitter** | Automatically splits complex issues into 2-4 smaller sub-issues |
| **Implementation Agent** | TDD in single context (tests + code + iteration) with dynamic max_turns |
| **Verifier** | Validates implementations, detects schema drift, and creates commits |
| **BugResearcher** | Reproduces bugs and gathers evidence |
| **RootCauseAnalyzer** | Identifies root cause of bugs |
| **FixPlanner** | Generates comprehensive fix plans |

## Complexity Gate & Auto-Split

The Complexity Gate prevents implementation timeouts by validating issue complexity before burning expensive tokens.

**Sizing Limits:**
| Size | Acceptance Criteria | Methods |
|------|---------------------|---------|
| Small | 1-4 | 1-2 |
| Medium | 5-8 | 3-5 |
| Large | 9-12 | 6-8 |
| **Too Large** | >12 | >8 |

### Auto-Split (NEW)

When an issue exceeds complexity limits, the system **automatically splits it** into smaller sub-issues:

```
ComplexityGate detects: needs_split=True
         ↓
IssueSplitterAgent creates 2-4 sub-issues
         ↓
Parent issue marked as SPLIT
         ↓
Dependencies rewired to child issues
         ↓
Implementation continues with first sub-issue
```

**Split Strategies:**
- **By Layer**: Separate model/API/UI components
- **By Operation**: Separate CRUD operations
- **By Criteria**: Group related acceptance criteria
- **By Phase**: Separate setup/core/integration

**Task States:**
| State | Meaning |
|-------|---------|
| READY | Can be worked on |
| IN_PROGRESS | Currently being implemented |
| DONE | Successfully completed |
| BLOCKED | Failed after retries |
| SKIPPED | Dependency was blocked |
| **SPLIT** | Too complex, split into child issues |

**Parent-Child Relationship:**
```
Before split:
  #3 → #5 → #8

After split (#5 → #10, #11, #12):
  #3 → #10 → #11 → #12 → #8
```
- First child inherits parent's dependencies
- Children are chained sequentially
- Dependents rewired to last child

## Input Validation

Swarm Attack validates all user inputs to prevent security issues and ensure data integrity.

### Feature & Bug IDs

- Must be lowercase alphanumeric with hyphens (e.g., `my-feature`, `bug-123`)
- Maximum 64 characters
- Cannot contain path traversal sequences (`..`, `/`, `\`)
- Cannot contain shell metacharacters (`$`, backticks, `|`, `;`, etc.)

### Budget & Duration

- Budget must be positive (> 0)
- Duration format: `2h`, `90m`, `1h30m`
- Duration must be positive

### Issue Numbers

- Must be positive integers (>= 1)
- Validated in `TaskRef` model and CLI commands

### Validation Errors

When validation fails, you'll see detailed error messages:

```
ValidationError: Budget must be positive
  Expected: float > 0
  Got: 0.0
  Hint: Provide a positive budget value (e.g., 10.0)
```

## Schema Drift Detection

The Verifier agent detects **schema drift** - when implementations create duplicate class definitions across different modules.

### How It Works

1. Tracks all classes defined in the codebase via `module_registry`
2. When verifying new code, checks if new classes conflict with existing ones
3. Uses AST parsing to detect legitimate subclasses (allowed) vs duplicates (blocked)

### Example

```python
# models/user.py
class User:  # Original definition
    pass

# services/user.py
class User:  # SCHEMA DRIFT - duplicate class name
    pass

# services/admin.py
class AdminUser(User):  # ALLOWED - subclass of existing class
    pass
```

The Verifier will fail with a schema conflict error for the duplicate, but allow the subclass.

## License

MIT
