# Swarm Attack

Autonomous AI-powered feature development CLI. Run from any project directory to orchestrate multi-agent development pipelines.

## What It Does

```
PRD → Spec → Issues → Tests → Code → Verify → Commit
```

Swarm Attack coordinates multiple AI agents (Claude + Codex) to:
1. **Generate specs** from your PRD using SpecAuthor agent
2. **Review & improve** specs through SpecCritic/SpecModerator debate
3. **Create GitHub issues** from approved specs
4. **Write tests** (TDD) with TestWriter agent
5. **Implement code** with Coder agent
6. **Verify & commit** with Verifier agent

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

## Commands

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
| `swarm-attack setup` | Initialize project with config |

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
