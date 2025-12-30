# Swarm Attack - Complete AI COO System Setup Guide

> **For LLMs and Developers**: This guide provides everything needed to set up and use Swarm Attack in a new repository. Copy this to your project or reference it when onboarding.

---

## Part 1: What is Swarm Attack?

Swarm Attack is an AI COO (Chief Operating Officer) system that automates software development workflows:
- **Specification** → Spec debate with SpecAuthor, SpecCritic, SpecModerator
- **Implementation** → TDD-driven coding with full context agents
- **Verification** → Automated testing and validation
- **Human Oversight** → Risk-aware checkpoints at critical decision points

**Key Philosophy:** "Thick-agent model" - agents have full context to eliminate handoff losses. The system aims for autonomous execution while maintaining human control over risky decisions.

---

## Part 2: Fresh Install Setup

### Step 1: Install

```bash
# Clone the repo
git clone https://github.com/your-org/swarm-attack.git
cd swarm-attack

# Install dependencies
pip install -e .

# Verify installation
swarm-attack --help
```

### Step 2: Set Environment Variables

```bash
# Required: Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-your-key-here"

# Required for GitHub integration (needs 'repo' scope)
export GITHUB_TOKEN="ghp_your-token-here"
```

### Step 3: Create config.yaml

Create `config.yaml` in your project root:

```yaml
# ===========================================
# Swarm Attack Configuration
# ===========================================

# GitHub Integration (required for issue creation)
github:
  owner: "your-github-org"        # Your GitHub org or username
  repo: "your-repo-name"          # Your repository name

# Test Configuration (adjust to your project)
tests:
  command: "pytest"               # Test runner command
  path: "tests/"                  # Test directory

# Chief of Staff Settings
chief_of_staff:
  autopilot:
    execution_strategy: "continue_on_block"  # or "sequential", "parallel_safe"
    budget_usd: 25.0                         # Daily budget limit
    risk_checkpoint_threshold: 0.5           # Pause above this risk score
    risk_block_threshold: 0.8                # Block above this risk score
    auto_approve_low_risk: true              # Skip checkpoints for low-risk
    max_recovery_attempts: 2                 # Auto-retries before checkpoint
    checkpoint_timeout_seconds: 300          # Auto-select after timeout

# Spec Debate Settings (optional)
spec_debate:
  max_rounds: 3                   # Max debate iterations
  min_score: 7.0                  # Minimum approval score (1-10)
```

### Step 4: Initialize Directory Structure

```bash
# Create required directories
mkdir -p .claude/prds
mkdir -p specs
mkdir -p .swarm

# Verify setup
swarm-attack status
```

### Step 5: Copy Skills (REQUIRED)

Skills are the prompts that power Swarm Attack's agents. **Without skills, the agents cannot function.**

```bash
# Copy default skills from swarm-attack to your project
# Adjust the path if swarm-attack is installed elsewhere
cp -r /path/to/swarm-attack/default-skills .claude/skills
```

Example if swarm-attack is on Desktop:
```bash
cp -r ~/Desktop/swarm-attack/default-skills .claude/skills
```

Verify skills are copied:
```bash
ls .claude/skills/
# Should show: bug-researcher, coder, feature-spec-author, etc.
```

**Important:** The `default-skills/` directory contains the distributable skill set. Your project needs these in `.claude/skills/` for the agents to work.

### What You Start With (Clean State)

| Directory | Contents | Purpose |
|-----------|----------|---------|
| `.swarm/state/` | Empty | Feature state tracking |
| `.swarm/bugs/` | Empty | Bug investigation state |
| `.swarm/sessions/` | Empty | Autopilot session history |
| `.swarm/chief-of-staff/` | Empty | Daily logs, checkpoints |
| `specs/` | Empty | Generated specifications |
| `.claude/prds/` | Empty | Your PRDs go here |

**You inherit nothing** - no specs, issues, or state from other projects.

---

## Part 3: Core Commands

### Status & Information

```bash
swarm-attack status                      # Dashboard view of all features
swarm-attack status <feature>            # Detailed status of one feature
```

### Chief of Staff (Daily Workflow)

```bash
# Daily routine
swarm-attack cos standup                 # Morning briefing
swarm-attack cos standup --github        # Include GitHub issues/PRs
swarm-attack cos autopilot --budget 25   # Run autonomous execution
swarm-attack cos progress --watch        # Monitor progress in real-time
swarm-attack cos checkin                 # Mid-day status check
swarm-attack cos wrapup                  # End of day summary

# Goal management
swarm-attack cos goals                   # View current goals
swarm-attack cos goals --add "goal"      # Add new goal
swarm-attack cos goals --complete <id>   # Mark goal complete

# Checkpoint management
swarm-attack cos checkpoints             # List pending checkpoints
swarm-attack cos approve <id>            # Approve checkpoint
swarm-attack cos reject <id>             # Reject checkpoint
swarm-attack cos approve <id> --notes "reason"
```

### Feature Pipeline

```bash
# Initialize feature from PRD
swarm-attack init <feature>              # Create PRD template

# Spec debate
swarm-attack run <feature>               # Run spec generation
swarm-attack approve <feature>           # Approve final spec
swarm-attack reject <feature>            # Reject with feedback

# Implementation
swarm-attack issues <feature>            # Create GitHub issues
swarm-attack greenlight <feature>        # Enable implementation
swarm-attack run <feature>               # Implement all issues
swarm-attack run <feature> --issue N     # Implement specific issue

# Recovery
swarm-attack recover <feature>           # Handle interruptions
swarm-attack unblock <feature>           # Unblock stuck feature
```

### Bug Bash Pipeline

```bash
# Initialize
swarm-attack bug init "description" --id bug-id --test tests/path.py -e "error"

# Analyze (Reproduce → RootCause → Plan)
swarm-attack bug analyze <bug-id>
swarm-attack bug status <bug-id>

# Approve and fix
swarm-attack bug approve <bug-id>
swarm-attack bug fix <bug-id>
swarm-attack bug reject <bug-id>         # Won't fix
swarm-attack bug unblock <bug-id>

# List all bugs
swarm-attack bug list
```

---

## Part 4: Checkpoint System

### What Are Checkpoints?

Checkpoints are human decision points where the system pauses for your input. They trigger based on risk assessment.

### Checkpoint Triggers

| Trigger | When It Fires |
|---------|---------------|
| `COST_SINGLE` | Single action exceeds cost threshold |
| `COST_CUMULATIVE` | Daily spending exceeds budget |
| `UX_CHANGE` | User-facing changes detected |
| `ARCHITECTURE` | Structural/architectural changes |
| `SCOPE_CHANGE` | Deviation from approved plan |
| `HICCUP` | Errors or blockers encountered |

### Enhanced Checkpoint Display

When a checkpoint triggers, you see rich context:

```
⚠️  HICCUP Checkpoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Session Progress:
  Goals: 2/4 completed (current: Fix authentication bug...)
  Budget: $10.00 / $25.00 spent ($15.00 remaining, 40% used)
  Estimated runway: ~3 more goals at current burn rate

Goal encountered error after 2 retries.
Goal: Implement authentication system
Error: ImportError: cannot import name 'hash_password'

Similar Past Decisions:
  • ✓ Approved - HICCUP: Previous error, proceeded successfully
  • ✗ Rejected - HICCUP: Goal failed with timeout

Options:
  [1] Proceed - Continue (recommended)
      Pros: May succeed on retry, Maintains progress momentum
      Cons: May fail again, Consumes budget on uncertain outcome
      Cost impact: +$3.00
      Risk: 🟡 Medium
  [2] Skip - Skip this goal
      Pros: Saves budget, Avoids repeated failures
      Cons: Goal remains incomplete
      Cost impact: No cost
      Risk: 🟢 Low
  [3] Pause - Pause for manual review
      Pros: Full manual control
      Cons: Stops automation
      Cost impact: No cost
      Risk: 🟢 Low

Recommendation: Proceed based on similar past success (70% approval rate)

Select option: _
```

### How to Respond

- Press **Enter** to select the recommended option
- Type **1**, **2**, or **3** to choose a specific option
- Invalid input will reprompt

The system learns from your decisions to improve future recommendations.

---

## Part 5: Risk Scoring Engine

### 5-Factor Weighted Model

Every action is scored for risk (0.0 to 1.0):

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| **Cost** | 30% | Budget impact as % of remaining funds |
| **Scope** | 25% | Files affected, core path involvement |
| **Reversibility** | 20% | Can operation be undone? (delete/deploy = high) |
| **Precedent** | 15% | Success rate of similar past work |
| **Confidence** | 10% | Historical approval/rejection patterns |

### Decision Thresholds

| Score Range | Action | Description |
|-------------|--------|-------------|
| < 0.5 | Auto-approve | Low risk, proceed automatically |
| 0.5 - 0.8 | Checkpoint | Medium risk, pause for human decision |
| > 0.8 | Block | High risk, require explicit approval |

### Examples

```
"Add logging to utils.py"        → 0.15 risk (auto-approve)
"Refactor authentication module" → 0.55 risk (checkpoint)
"Delete production database"     → 0.95 risk (blocked)
```

---

## Part 6: Self-Healing Recovery

### Automatic Recovery Flow

Before showing you a checkpoint, the system attempts automatic recovery:

```
Goal fails with error
    ↓
Level 1: Simple retry (transient failures)
    ↓
If still failing...
    ↓
Level 2: LLM-guided recovery
    ↓
LLM suggests: ALTERNATIVE, DIAGNOSTICS, UNBLOCK, or ESCALATE
    ↓
If ALTERNATIVE: Retry with hint (max 2 attempts)
    ↓
If still failing: Interactive checkpoint prompt
```

### Level 2 Recovery Actions

| Action | What Happens |
|--------|--------------|
| `ALTERNATIVE` | Try different approach with LLM-suggested hint |
| `DIAGNOSTICS` | Run diagnostic commands to gather info |
| `UNBLOCK` | Provide specific unblocking guidance |
| `ESCALATE` | Trigger immediate human checkpoint |

Most issues resolve automatically. You only see checkpoints for hard blockers.

---

## Part 7: Execution Strategies

### Available Strategies

```bash
# Sequential (default) - execute in order, stop on any block
swarm-attack cos autopilot --strategy sequential

# Continue-on-block - skip blocked goals, continue with ready ones
swarm-attack cos autopilot --strategy continue_on_block

# Parallel-safe - run independent goals in parallel when safe
swarm-attack cos autopilot --strategy parallel_safe
```

### When to Use Each

| Strategy | Best For |
|----------|----------|
| `sequential` | Dependent tasks, strict ordering needed |
| `continue_on_block` | Mixed independent/dependent goals |
| `parallel_safe` | Many independent tasks, maximize throughput |

---

## Part 8: File Structure

### Project Layout

```
your-project/
├── config.yaml                  # Swarm configuration
├── CLAUDE.md                    # Claude Code reference (READ THIS)
├── .claude/
│   └── prds/                    # Your PRDs go here
│       └── my-feature.md
├── specs/                       # Generated specifications
│   └── my-feature/
│       ├── spec-draft.md
│       └── spec-final.md
├── .swarm/                      # Swarm state (auto-managed)
│   ├── state/                   # Feature state files
│   ├── bugs/                    # Bug investigation state
│   ├── sessions/                # Autopilot sessions
│   ├── chief-of-staff/          # Daily logs, checkpoints
│   └── locks/                   # Concurrency locks
├── swarm_attack/                # Swarm Attack package
│   └── chief_of_staff/          # Chief of Staff modules
├── prompts/                     # LLM prompt templates
└── tests/                       # Your test suite
```

### Key Files to Read

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Primary reference - architecture, commands, patterns |
| `QUICKSTART.md` | PM-friendly workflow guide |
| `README.md` | Full project overview |
| `config.yaml` | Your configuration |
| `.swarm/state/<feature>.json` | Feature state and progress |

---

## Part 9: Common Workflows

### Starting a New Day

```bash
swarm-attack cos standup --github    # See what to work on
swarm-attack cos autopilot --budget 25  # Start autonomous work
swarm-attack cos progress --watch    # Monitor in background
```

### Adding a New Feature

```bash
# 1. Write PRD
cat > .claude/prds/user-auth.md << 'EOF'
# Feature: User Authentication

## Problem
Users cannot log in to the application.

## Solution
Implement JWT-based authentication with login/logout.

## Requirements
- POST /login endpoint
- POST /logout endpoint
- JWT token generation and validation
- Password hashing with bcrypt

## Success Criteria
- [ ] Users can log in with email/password
- [ ] JWT tokens expire after 24 hours
- [ ] Passwords are securely hashed
EOF

# 2. Initialize and run spec debate
swarm-attack init user-auth
swarm-attack run user-auth

# 3. Review and approve spec
cat specs/user-auth/spec-final.md
swarm-attack approve user-auth

# 4. Create GitHub issues
swarm-attack issues user-auth

# 5. Greenlight and implement
swarm-attack greenlight user-auth
swarm-attack run user-auth
```

### Fixing a Bug

```bash
# 1. Initialize investigation
swarm-attack bug init "Login fails with special characters in password" \
  --id login-special-chars \
  --test tests/test_auth.py \
  -e "UnicodeEncodeError"

# 2. Analyze (reproduce, root cause, plan)
swarm-attack bug analyze login-special-chars

# 3. Review and approve fix plan
swarm-attack bug status login-special-chars
swarm-attack bug approve login-special-chars

# 4. Execute fix
swarm-attack bug fix login-special-chars
```

### Using Chief of Staff Without GitHub

```bash
# Add goals manually
swarm-attack cos goals --add "Implement user authentication"
swarm-attack cos goals --add "Write tests for auth module"
swarm-attack cos goals --add "Update API documentation"

# Run autopilot
swarm-attack cos autopilot --budget 25
```

### Recovering from Issues

```bash
# Check what's wrong
swarm-attack status my-feature

# Attempt auto-recovery
swarm-attack recover my-feature

# Manual unblock if needed
swarm-attack unblock my-feature
```

### Discovering Improvement Opportunities

Find work items you might not be aware of:

```bash
# Discover test failures and opportunities (no LLM cost)
swarm-attack cos discover

# Include LLM-powered fix suggestions (~$0.01/suggestion)
swarm-attack cos discover --deep

# Review discovered opportunities
swarm-attack cos backlog

# Accept an opportunity (links to GitHub issue)
# Interactive: select from list, then 'a' to accept

# View all discoveries including rejected
swarm-attack cos backlog --status all
```

**What it discovers:**
- **Test failures**: Failing tests with suggested fixes
- **Stalled work**: Features stuck in progress (coming soon)
- **Code quality**: Complexity hotspots, coverage gaps (coming soon)

**Cost Breakdown:**

| Mode | Cost |
|------|------|
| Basic discovery | $0.00 (rule-based) |
| With `--deep` | ~$0.01 per suggestion |
| With debate (>5 items) | ~$1.50-2.50 total |

---

## Part 10: Interface Contracts & Issue Sizing

### Interface Contracts

When Swarm creates GitHub issues, they include exact method signatures:

```markdown
## Interface Contract (REQUIRED)

**Required Methods:**
- `from_dict(cls, data: dict) -> ClassName`
- `to_dict(self) -> dict`
- `validate(self) -> bool`

**Pattern Reference:** See `swarm_attack/config.py:BugBashConfig`
```

### Issue Sizing (Complexity Gate)

Issues are sized to prevent timeouts:

| Size | Acceptance Criteria | Methods | Max Turns |
|------|---------------------|---------|-----------|
| Small | 1-4 | 1-2 | 10 |
| Medium | 5-8 | 3-5 | 15 |
| Large | 9-12 | 6-8 | 20 |
| Too Large | >12 | >8 | **MUST SPLIT** |

### Split Strategies for Large Issues

1. **By layer**: data model → API → UI
2. **By operation**: CRUD as separate issues
3. **By trigger/case**: Groups of 3
4. **By phase**: setup → core → integration

---

## Part 11: TDD Workflow

Implementation follows a strict 7-phase TDD cycle:

| Phase | Action |
|-------|--------|
| 1. **Read** | Understand context, requirements, existing code |
| 2. **Write Tests** | Create failing tests first (RED) |
| 3. **Run Tests** | Confirm tests fail as expected |
| 4. **Implement** | Write minimum code to pass (GREEN) |
| 5. **Iterate** | Fix remaining failures, refactor |
| 6. **Full Suite** | Run all tests, ensure no regressions |
| 7. **Complete** | Mark done, create commit |

---

## Part 12: Tips for Success

1. **Always check status first**: `swarm-attack status` before starting
2. **Use budget limits**: `--budget 25` prevents runaway costs
3. **Trust the checkpoints**: They protect you from risky changes
4. **Read CLAUDE.md**: It's the authoritative project reference
5. **Check .swarm/state/**: JSON files show exact feature status
6. **Use continue-on-block**: Better for large goal sets
7. **Review similar decisions**: The system learns from your choices
8. **Start small**: Test with a simple feature before complex ones

---

## Part 13: Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `ANTHROPIC_API_KEY not set` | `export ANTHROPIC_API_KEY="sk-ant-..."` |
| `GITHUB_TOKEN not set` | `export GITHUB_TOKEN="ghp_..."` |
| `config.yaml not found` | Create config.yaml in project root |
| Feature stuck in IMPLEMENTING | `swarm-attack recover <feature>` |
| Checkpoint not responding | Press Enter or type 1/2/3 |
| Tests failing | Check `tests/` path in config.yaml |

### Debug Mode

```bash
SWARM_DEBUG=1 swarm-attack run <feature>
```

### Getting Help

```bash
swarm-attack --help              # All commands
swarm-attack cos --help          # Chief of Staff commands
swarm-attack bug --help          # Bug bash commands
swarm-attack <command> --help    # Specific command help
```

---

## Quick Reference Card

```bash
# === DAILY WORKFLOW ===
swarm-attack cos standup                 # Morning briefing
swarm-attack cos autopilot --budget 25   # Run autonomous
swarm-attack cos progress --watch        # Monitor

# === FEATURE PIPELINE ===
swarm-attack init <feature>              # Start feature
swarm-attack run <feature>               # Run spec/implement
swarm-attack approve <feature>           # Approve spec
swarm-attack issues <feature>            # Create issues
swarm-attack greenlight <feature>        # Enable implementation

# === BUG PIPELINE ===
swarm-attack bug init "desc" --id <id>   # Start investigation
swarm-attack bug analyze <id>            # Analyze bug
swarm-attack bug approve <id>            # Approve fix
swarm-attack bug fix <id>                # Execute fix

# === DISCOVERY ===
swarm-attack cos discover                # Find opportunities
swarm-attack cos discover --deep         # With fix suggestions
swarm-attack cos backlog                 # View actionable items
swarm-attack cos backlog --status all    # View all discoveries

# === CHECKPOINTS ===
swarm-attack cos checkpoints             # List pending
swarm-attack cos approve <id>            # Approve
swarm-attack cos reject <id>             # Reject

# === RECOVERY ===
swarm-attack status <feature>            # Check status
swarm-attack recover <feature>           # Auto-recover
swarm-attack unblock <feature>           # Manual unblock
```

---

**You are now ready to use Swarm Attack.**

Start with:
```bash
swarm-attack status
swarm-attack cos standup
```
