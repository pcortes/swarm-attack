# Swarm Attack

Autonomous AI-powered multi-agent development automation system. Orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

## What It Does

### Feature Swarm Pipeline
```
PRD → Spec → Issues → Tests → Code → Verify → Commit
```

### Bug Bash Pipeline
```
Bug Report → Reproduce → Analyze → Plan → Approve → Fix → Verify
```

Swarm Attack coordinates multiple AI agents (Claude + Codex) to:

**Feature Development:**
1. **Generate specs** from your PRD using SpecAuthor agent
2. **Review & improve** specs through SpecCritic/SpecModerator debate
3. **Create GitHub issues** from approved specs
4. **Write tests** (TDD) with TestWriter agent
5. **Implement code** with Coder agent
6. **Verify & commit** with Verifier agent

**Bug Investigation:**
1. **Reproduce bugs** with BugResearcher agent
2. **Analyze root cause** with debate-validated analysis
3. **Generate fix plans** with risk assessment
4. **Apply fixes** after human approval
5. **Verify fixes** by running tests

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

# Codex CLI (requires OpenAI ChatGPT subscription)
npm install -g @openai/codex

# Authenticate both
claude auth login
codex auth
```

### Verify Setup
```bash
claude --version
claude doctor
codex --version
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

codex:
  binary: "codex"
  model: "gpt-5.1-codex"
  timeout_seconds: 120

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
│   ├── specs/              # Generated specs
│   │   └── my-feature/
│   │       ├── spec-draft.md
│   │       ├── spec-review.json
│   │       └── spec-rubric.json
│   └── skills/             # Agent skill definitions
│       ├── feature-spec-author/
│       ├── feature-spec-critic/
│       └── ...
└── .swarm/                 # State tracking
    └── state.json
```

## The Debate Pipeline

```
┌────────────┐     ┌────────────┐     ┌────────────┐
│ SpecAuthor │ ──▶ │ SpecCritic │ ──▶ │SpecModerator│
│  (Claude)  │     │  (Codex)   │     │  (Claude)   │
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

## License

MIT
