# Swarm Attack: User Guide

**A step-by-step guide to automating feature development and bug fixing.**

---

## Table of Contents

1. [What is Swarm Attack?](#1-what-is-swarm-attack)
2. [Prerequisites & Setup](#2-prerequisites--setup)
3. [The Feature Lifecycle](#3-the-feature-lifecycle)
4. [Quick Start: Your First Feature](#4-quick-start-your-first-feature)
5. [Command Reference](#5-command-reference)
6. [Understanding the Dashboard](#6-understanding-the-dashboard)
7. [Human Checkpoints](#7-human-checkpoints)
8. [Handling Failures & Recovery](#8-handling-failures--recovery)
9. [Best Practices](#9-best-practices)
10. [Troubleshooting](#10-troubleshooting)
11. [Bug Bash: Automated Bug Investigation](#11-bug-bash-automated-bug-investigation)

---

## 1. What is Swarm Attack?

Swarm Attack is an **AI-powered multi-agent automation system** that handles both feature development and bug fixing. It orchestrates the entire process from idea to shipped code.

### Feature Swarm Pipeline
```
YOUR IDEA → PRD → ENGINEERING SPEC → GITHUB ISSUES → TESTS → CODE → DONE
              ↑           ↑                ↑
           You write   You approve    You greenlight
```

### Bug Bash Pipeline
```
BUG REPORT → REPRODUCE → ANALYZE → FIX PLAN → APPROVE → FIX → VERIFY
                                       ↑
                                  You approve
```

### Key Benefits

- **One Command**: Just run `swarm-attack` and it figures out what to do next
- **Automated Spec Writing**: AI drafts engineering specs from your PRD
- **Automated Bug Investigation**: AI reproduces, analyzes, and plans bug fixes
- **Quality Gates**: Independent AI review through debate system
- **TDD Approach**: Tests are written before code, ensuring reliability
- **Recovery Built-in**: If something fails, the system knows how to recover

### How It Works

Swarm Attack uses **multiple specialized AI agents** powered by Claude:
- **Claude** (via Claude Code CLI) - Writes specs, code, and analyzes bugs
- **Claude Agents** - Different Claude instances review and critique work
- **Debate System** - Author-Critic rounds ensure quality analysis

This multi-agent approach ensures independent validation of all AI-generated content.

---

## 2. Prerequisites & Setup

### 2.1 Required Software

Before using Swarm Attack, ensure you have:

| Software | Purpose | How to Get It |
|----------|---------|---------------|
| Python 3.10+ | Runs Swarm Attack | `brew install python` or python.org |
| Git | Version control | `brew install git` |
| Claude Code CLI | AI spec writing & coding | `npx -y @anthropic/claude-cli@latest bootstrap` |
| GitHub CLI (gh) | GitHub integration | `brew install gh` |

### 2.2 Required Subscriptions

| Service | Plan Needed | Cost |
|---------|-------------|------|
| Claude | Claude Code Max | ~$100-200/month |
| GitHub | Any (free works) | Free |

### 2.3 Environment Setup

1. **Set up GitHub authentication:**
   ```bash
   # Login to GitHub CLI
   gh auth login

   # Export your GitHub token
   export GITHUB_TOKEN=$(gh auth token)
   ```

2. **Set up Anthropic authentication:**
   ```bash
   # Export your Anthropic API key
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

3. **Install Swarm Attack:**
   ```bash
   # From the repo root
   pip install -e .
   ```

### 2.4 Project Configuration

Create a `config.yaml` file in your repository root:

```yaml
# Swarm Attack Configuration

# Paths
repo_root: .
specs_dir: .claude/specs
swarm_dir: .swarm

# GitHub configuration (required)
github:
  repo: "your-org/your-repo"        # Your GitHub repository
  token_env_var: "GITHUB_TOKEN"     # Environment variable with PAT

# Claude Code CLI configuration
claude:
  binary: "claude"
  max_turns: 6
  timeout_seconds: 300

# Test framework configuration (required)
tests:
  command: "pytest"                 # Your test command
  args: ["-v", "--tb=short"]

# Git configuration
git:
  base_branch: "main"
  feature_branch_pattern: "feature/{feature_slug}"
  use_worktrees: true

# Quality thresholds for spec approval
spec_debate:
  max_rounds: 5
  rubric_thresholds:
    clarity: 0.8
    coverage: 0.8
    architecture: 0.8
    risk: 0.7
```

---

## 3. The Feature Lifecycle

Every feature goes through these phases:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FEATURE LIFECYCLE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. NO_PRD              You need to write a PRD                     │
│      │                                                               │
│      ▼                                                               │
│  2. PRD_READY           PRD exists, ready for spec generation       │
│      │                                                               │
│      ▼  ← AI runs spec debate (Author → Critic → revisions)        │
│  3. SPEC_IN_PROGRESS    AI is writing/improving the spec            │
│      │                                                               │
│      ▼                                                               │
│  4. SPEC_NEEDS_APPROVAL ★ YOU review and approve the spec           │
│      │                                                               │
│      ▼                                                               │
│  5. SPEC_APPROVED       Spec approved, creating GitHub issues       │
│      │                                                               │
│      ▼                                                               │
│  6. READY_TO_IMPLEMENT  ★ YOU greenlight issues for implementation  │
│      │                                                               │
│      ▼  ← AI implements (write tests → write code → verify)        │
│  7. IMPLEMENTING        AI is implementing issues one by one        │
│      │                                                               │
│      ▼                                                               │
│  8. COMPLETE            All done! Ready to merge.                   │
│                                                                      │
│  ★ = Human checkpoint (requires your action)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Quick Start: Your First Feature

### Step 1: Initialize the Feature

```bash
# Create a new feature called "user-notifications"
swarm-attack feature init user-notifications
```

This creates:
- A PRD template at `.claude/prds/user-notifications.md`
- Feature state in `.swarm/state/`

### Step 2: Write Your PRD

Edit the PRD file at `.claude/prds/user-notifications.md`:

```markdown
# PRD: User Notifications

## Overview
Add a notification system that alerts users when important events occur.

## Problem Statement
Users currently have no way to know when actions they care about happen
(new comments, mentions, status changes).

## Requirements
1. Real-time notifications for mentions
2. Notification preferences per user
3. In-app notification center
4. Email digest option (daily/weekly)

## Success Criteria
- Users receive notifications within 5 seconds of event
- Users can customize which notifications they receive
- 95% of users find the notification center intuitive

## Out of Scope
- Push notifications (mobile) - future phase
- SMS notifications
```

### Step 3: Run the Spec Pipeline

```bash
# Run Swarm Attack - it will automatically start the spec pipeline
swarm-attack feature run user-notifications
```

**What happens:**
1. **SpecAuthor** (Claude) reads your PRD and writes an engineering spec
2. **SpecCritic** (Claude) reviews the spec and scores it on:
   - Clarity (0-1)
   - Coverage (0-1)
   - Architecture (0-1)
   - Risk assessment (0-1)
3. If scores are below thresholds, **SpecModerator** improves the spec
4. Loop continues until spec passes or reaches max rounds

You'll see output like:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Feature: user-notifications
Status:  SPEC_IN_PROGRESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Round 1/5...
  ✓ Author generated spec
  ✓ Critic reviewed: clarity=0.75, coverage=0.82, arch=0.68, risk=0.80
  → Below threshold, improving...

Round 2/5...
  ✓ Moderator improved spec
  ✓ Critic reviewed: clarity=0.88, coverage=0.90, arch=0.85, risk=0.82
  ✓ All thresholds met!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pipeline Complete
Cost: $0.12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next step: Review the spec at:
  .claude/specs/user-notifications/spec-draft.md

Then approve with:
  swarm-attack feature approve user-notifications
```

### Step 4: Review and Approve the Spec

Open and review `.claude/specs/user-notifications/spec-draft.md`. When satisfied:

```bash
swarm-attack feature approve user-notifications
```

### Step 5: Let Implementation Run

```bash
# Continue running - it will create issues and implement them
swarm-attack feature smart user-notifications
```

The system will:
1. Create GitHub issues from the spec (with Interface Contracts)
2. Prioritize issues by dependencies and value
3. For each issue, the **Implementation Agent** (thick-agent TDD):
   - Reads context (issue, spec, integration points)
   - Writes tests first (RED phase)
   - Implements code to pass tests (GREEN phase)
   - Iterates until all tests pass
   - Runs full test suite for regressions
4. Verifier validates and creates git commit
5. Mark issues as done when complete

### Step 6: Review and Merge

When all issues are done, review the feature branch and merge:

```bash
# See what was done
swarm-attack feature status user-notifications

# Review the commits
git log feature/user-notifications

# Merge when ready
git checkout main
git merge feature/user-notifications
```

---

## 5. Command Reference

### Feature Commands

| Command | Description |
|---------|-------------|
| `swarm-attack feature` | Show dashboard of all features |
| `swarm-attack feature status` | Same as above - show all features |
| `swarm-attack feature status <feature>` | Show detailed status of one feature |
| `swarm-attack feature init <feature>` | Create a new feature |
| `swarm-attack feature run <feature>` | Run the spec pipeline |
| `swarm-attack feature approve <feature>` | Approve a spec |
| `swarm-attack feature reject <feature>` | Reject a spec (optionally re-run) |
| `swarm-attack feature smart <feature>` | Smart mode - auto-detect next action |
| `swarm-attack feature next <feature>` | Show what would happen next |
| `swarm-attack feature recover <feature>` | Handle interrupted sessions |

### Chief of Staff (CoS) Commands

| Command | Description |
|---------|-------------|
| `swarm-attack cos standup` | Morning standup - review status and plan day |
| `swarm-attack cos checkin` | Mid-day check-in - review progress |
| `swarm-attack cos wrapup` | End of day wrap-up - summarize work |
| `swarm-attack cos autopilot` | Run full autonomous development cycle |
| `swarm-attack cos status` | Show current CoS status and metrics |

### Bug Commands

| Command | Description |
|---------|-------------|
| `swarm-attack bug list` | List all bug investigations |
| `swarm-attack bug init "desc" --id ID --test PATH -e "error"` | Create bug |
| `swarm-attack bug analyze <bug-id>` | Run full analysis pipeline |
| `swarm-attack bug status <bug-id>` | Show detailed bug status |
| `swarm-attack bug approve <bug-id>` | Approve fix plan |
| `swarm-attack bug fix <bug-id>` | Execute approved fix |
| `swarm-attack bug reject <bug-id>` | Reject (won't fix) |
| `swarm-attack bug unblock <bug-id>` | Unblock stuck bug |

### Admin Commands

| Command | Description |
|---------|-------------|
| `swarm-attack admin config` | Show current configuration |
| `swarm-attack admin validate` | Validate environment and setup |
| `swarm-attack admin clean` | Clean up stale state files |

### Smart Mode (`swarm-attack feature smart`)

The `smart` command is the primary way to use Feature Swarm. It:
1. Checks for interrupted sessions → offers recovery options
2. Checks for blocked issues → offers retry options
3. Determines the next action based on current state
4. Executes that action

```bash
# Just run this repeatedly until your feature is done
swarm-attack feature smart user-notifications
```

### Examples

```bash
# See all your features
swarm-attack feature status

# Start working on a feature (does the right thing)
swarm-attack feature smart user-auth

# Check what would happen next without doing it
swarm-attack feature next user-auth

# Recover from a crash/interruption
swarm-attack feature recover user-auth

# Re-run spec generation after rejection
swarm-attack feature reject user-auth --rerun

# Run CoS autopilot for autonomous development
swarm-attack cos autopilot
```

---

## 6. Understanding the Dashboard

When you run `swarm-attack feature status`, you see:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Feature Swarm Status                            │
├───────────────────┬──────────────────────┬────────┬────────┬────────┤
│ Feature           │ Phase                │ Tasks  │ Cost   │Updated │
├───────────────────┼──────────────────────┼────────┼────────┼────────┤
│ user-auth         │ Complete             │ 5/5    │ $0.45  │ Nov 25 │
│ user-notifications│ Ready to Implement   │ 0/3    │ $0.12  │ Nov 26 │
│ dark-mode         │ Spec Needs Approval  │ -      │ $0.08  │ Nov 26 │
│ api-v2            │ Blocked              │ 2/6(1) │ $0.32  │ Nov 24 │
└───────────────────┴──────────────────────┴────────┴────────┴────────┘

Total cost: $0.97
```

### Column Meanings

| Column | Meaning |
|--------|---------|
| Feature | The feature slug/identifier |
| Phase | Current lifecycle phase (see section 3) |
| Tasks | Done/Total (blocked shown in parentheses) |
| Cost | Total LLM cost for this feature |
| Updated | Last activity date |

### Phase Colors

| Color | Meaning |
|-------|---------|
| Green | Complete or approved |
| Cyan | In progress (implementing) |
| Yellow | Waiting for human action |
| Red | Blocked - needs attention |
| Dim | Not started |

---

## 7. Human Checkpoints

There are **three points** where Feature Swarm stops and waits for you:

### Checkpoint 1: PRD Creation

**When:** Feature initialized but no PRD exists
**Action:** Write your PRD at `.claude/prds/<feature>.md`

The PRD should include:
- Overview of the feature
- Problem statement
- Requirements (numbered list)
- Success criteria
- Out of scope items

### Checkpoint 2: Spec Approval

**When:** Spec pipeline complete, phase is `SPEC_NEEDS_APPROVAL`
**Action:** Review `.claude/specs/<feature>/spec-draft.md` and either:

```bash
# If the spec looks good
swarm-attack feature approve <feature>

# If changes are needed
# Option A: Edit the spec manually, then approve
# Option B: Re-run the pipeline
swarm-attack feature reject <feature> --rerun
```

**What to look for in the spec:**
- Does the architecture make sense?
- Are all requirements covered?
- Is the implementation plan reasonable?
- Are risks identified and mitigated?
- Is the testing strategy comprehensive?

### Checkpoint 3: Issue Greenlight

**When:** Issues created, phase is `ISSUES_NEED_REVIEW`
**Action:** Review the GitHub issues and greenlight implementation

```bash
# Review issues on GitHub
gh issue list --label "feature:<feature-slug>"

# When ready to proceed
swarm-attack feature greenlight <feature>
```

**What to check:**
- Are issues properly scoped?
- Are dependencies correct?
- Is the priority order sensible?

---

## 8. Handling Failures & Recovery

### Interrupted Sessions

If Feature Swarm crashes or you close your terminal mid-session:

```bash
# Check for interrupted work
swarm-attack feature recover <feature>
```

You'll see options:
- **[R]esume**: Continue from the last checkpoint
- **[B]ackup & restart**: Stash changes, start fresh on this issue
- **[S]kip**: Mark the issue as blocked, move to next

### Blocked Issues

An issue becomes "blocked" after 3 failed implementation attempts.

```bash
# See blocked issues
swarm-attack feature status <feature>

# Offers to retry blocked issues
swarm-attack feature smart <feature>
```

**When an issue is blocked:**
1. Review the error in `.swarm/sessions/`
2. The RecoveryAgent provides analysis of what went wrong
3. You can manually fix the issue and mark it ready
4. Or break it into smaller issues

### Rollback

If something went wrong and you need to undo:

```bash
# See what commits were made
git log feature/<feature-slug>

# Revert the last session's commits
swarm-attack feature rollback <feature>
```

---

## 9. Best Practices

### Writing Good PRDs

1. **Be specific** - Vague requirements lead to vague specs
2. **Number your requirements** - Makes them trackable as issues
3. **Define success criteria** - How do we know it's done?
4. **List what's out of scope** - Prevents scope creep
5. **Keep it focused** - One feature per PRD

### Feature Naming

Use kebab-case slugs that are:
- Descriptive: `user-authentication` not `auth`
- Unique: No duplicates
- Short but clear: `dark-mode` not `implement-dark-mode-theme-switching`

### Workflow Tips

1. **Run `smart` repeatedly** - It always knows what to do next
2. **Check status often** - `swarm-attack feature status <feature>`
3. **Don't ignore blocked issues** - They indicate real problems
4. **Review specs carefully** - Garbage in, garbage out
5. **Start small** - Your first feature should be simple

### Cost Management

- Each spec pipeline costs ~$0.10-0.20
- Each issue implementation costs ~$0.05-0.15
- A typical feature costs $0.50-2.00 total
- Check `swarm-attack feature status` to see cumulative costs

---

## 10. Troubleshooting

### "Claude CLI not found"

```bash
# Verify Claude is installed
which claude

# If not found, install it
npx -y @anthropic/claude-cli@latest bootstrap

# Verify it works
claude --version
```

### "ANTHROPIC_API_KEY not set"

```bash
# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Add to your shell profile for persistence
echo 'export ANTHROPIC_API_KEY="your-key"' >> ~/.zshrc
```

### "GitHub token not set"

```bash
# Login to GitHub CLI
gh auth login

# Export the token
export GITHUB_TOKEN=$(gh auth token)
```

### "Feature not found"

```bash
# List all features
swarm-attack feature status

# If the feature doesn't exist, create it
swarm-attack feature init <feature-name>
```

### "Spec pipeline keeps failing"

1. Check the logs: `.swarm/logs/`
2. Verify your PRD is well-formed
3. Check Claude CLI is authenticated
4. Try running with `--dry-run` to see what would happen

### "Tests keep failing during implementation"

1. Review the test file created by the Implementation Agent
2. Check if tests are reasonable for the requirements
3. Review the Implementation Agent's code attempt
4. Consider breaking the issue into smaller pieces

### "Session stuck"

```bash
# Force recovery mode
swarm-attack feature recover <feature>

# Or manually clean up
rm -rf .swarm/locks/<feature>/
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SWARM ATTACK QUICK REFERENCE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  START A FEATURE                                                     │
│  ───────────────                                                     │
│  swarm-attack feature init my-feature     # Create feature          │
│  # Edit .claude/prds/my-feature.md        # Write your PRD          │
│  swarm-attack feature run my-feature      # Generate spec           │
│                                                                      │
│  DAILY WORKFLOW                                                      │
│  ──────────────                                                      │
│  swarm-attack feature status              # See all features        │
│  swarm-attack feature smart my-feature    # Do the next thing       │
│  swarm-attack cos autopilot               # Autonomous development  │
│                                                                      │
│  HUMAN CHECKPOINTS                                                   │
│  ─────────────────                                                   │
│  swarm-attack feature approve my-feature  # Approve spec            │
│  swarm-attack feature reject my-feature   # Reject spec             │
│  swarm-attack feature greenlight my-feat  # Start implementation    │
│                                                                      │
│  BUG FIXING                                                          │
│  ──────────                                                          │
│  swarm-attack bug init "desc" --id ID --test PATH -e "error"        │
│  swarm-attack bug analyze my-bug-id       # Analyze bug             │
│  swarm-attack bug approve my-bug-id       # Approve fix plan        │
│  swarm-attack bug fix my-bug-id           # Apply fix               │
│                                                                      │
│  RECOVERY                                                            │
│  ────────                                                            │
│  swarm-attack feature recover my-feature  # Handle interruptions    │
│  swarm-attack feature rollback my-feature # Undo last session       │
│                                                                      │
│  KEY FILES                                                           │
│  ─────────                                                           │
│  .claude/prds/<feature>.md            # Your PRD                    │
│  .claude/specs/<feature>/spec-draft.md # Generated spec             │
│  .swarm/state/<feature>.json          # Feature state               │
│  .swarm/bugs/<bug-id>/                # Bug investigation           │
│  .swarm/sessions/                     # Session history             │
│  config.yaml                          # Project configuration       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Bug Bash: Automated Bug Investigation

Bug Bash is Swarm Attack's automated bug investigation and fixing pipeline.

### The Bug Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BUG LIFECYCLE                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Created           Bug initialized with description and test      │
│      │                                                               │
│      ▼                                                               │
│  2. Reproducing       Running test to confirm bug exists             │
│      │                                                               │
│      ▼                                                               │
│  3. Analyzing         LLM analyzing root cause with debate           │
│      │                                                               │
│      ▼                                                               │
│  4. Planned           Fix plan generated and debated                 │
│      │                                                               │
│      ▼                                                               │
│  5. Approved   ★      Human approved the fix plan                    │
│      │                                                               │
│      ▼                                                               │
│  6. Fixing            Applying fix via Claude Code                   │
│      │                                                               │
│      ▼                                                               │
│  7. Fixed             Bug resolved, tests passing                    │
│                                                                      │
│  ★ = Human checkpoint                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Quick Start: Your First Bug Fix

#### Step 1: Initialize a Bug Investigation

When you have a failing test:

```bash
swarm-attack bug init "Description of the bug" \
  --id my-bug-id \
  --test tests/path/to_test.py::TestClass::test_method \
  -e "Error message from the failure"
```

#### Step 2: Run the Analysis Pipeline

```bash
swarm-attack bug analyze my-bug-id
```

This runs three phases:
1. **Reproduce** - Confirms the bug by running the failing test
2. **Analyze** - LLM analyzes root cause with debate validation
3. **Plan** - Generates a comprehensive fix plan

#### Step 3: Review and Approve

```bash
# Check status
swarm-attack bug status my-bug-id

# Review the generated fix plan
cat .swarm/bugs/my-bug-id/fix-plan.md

# Approve for implementation
swarm-attack bug approve my-bug-id
```

The fix plan includes:
- Summary of the fix
- Risk assessment (low/medium/high)
- Proposed code changes with before/after
- Test cases to add
- Potential side effects
- Rollback plan

#### Step 4: Apply the Fix

```bash
swarm-attack bug fix my-bug-id
```

### Bug Commands

| Command | Description |
|---------|-------------|
| `swarm-attack bug list` | List all bug investigations |
| `swarm-attack bug init "desc" --id ID --test PATH -e "error"` | Create bug |
| `swarm-attack bug analyze <bug-id>` | Run full analysis pipeline |
| `swarm-attack bug status <bug-id>` | Show detailed bug status |
| `swarm-attack bug approve <bug-id>` | Approve fix plan |
| `swarm-attack bug approve <bug-id> --yes` | Approve without prompt |
| `swarm-attack bug fix <bug-id>` | Execute approved fix |
| `swarm-attack bug reject <bug-id>` | Reject (won't fix) |
| `swarm-attack bug unblock <bug-id>` | Unblock stuck bug |

### Bug Files

After analysis, you'll find these files in `.swarm/bugs/<bug-id>/`:

| File | Contents |
|------|----------|
| `state.json` | Bug investigation state |
| `report.md` | Initial bug report |
| `reproduction.md` | Reproduction results |
| `root-cause-analysis.md` | Root cause analysis |
| `fix-plan.md` | Approved fix plan |

### Cost Breakdown

Bug analysis uses multiple agents with debate validation:

| Agent | Typical Cost |
|-------|--------------|
| bug_researcher | $0.10-0.15 |
| root_cause_analyzer | $0.08-0.12 |
| root_cause_debate | $0.08-0.12 |
| fix_planner | $0.08-0.12 |
| fix_plan_debate | $0.08-0.12 |
| **Total** | **$0.40-0.60** |

---

## 12. Testing v0.3.0 Features

This section provides manual testing instructions for all v0.3.0 features.

### 12.1 Test Auto-Approval System

```bash
# Create a test feature
swarm-attack init test-auto-approval
# Edit .claude/prds/test-auto-approval.md with a simple PRD

# Run spec debate (should take 2+ rounds)
swarm-attack run test-auto-approval

# Check if auto-approval triggers (score >= 0.85)
swarm-attack status test-auto-approval
# Look for: "Auto-approved: Yes" or manual approval prompt

# Test manual override
swarm-attack approve test-auto-approval --manual
# Should require explicit approval even if threshold met

# Test auto mode
swarm-attack approve test-auto-approval --auto
# Should auto-approve if thresholds met
```

**Verify:**
- [ ] Specs with score >= 0.85 after 2 rounds auto-approve
- [ ] `--manual` flag forces human approval
- [ ] `--auto` flag enables auto-approval

### 12.2 Test Event Infrastructure

```python
# Run in Python REPL
from swarm_attack.events.bus import get_event_bus, EventType
from swarm_attack.events.types import SwarmEvent

bus = get_event_bus()

# Test subscription
events_received = []
def handler(event):
    events_received.append(event)
    print(f"Received: {event.event_type}")

bus.subscribe(EventType.IMPL_COMPLETED, handler)

# Test emission
bus.emit(SwarmEvent(
    event_type=EventType.IMPL_COMPLETED,
    feature_id="test-feature",
    issue_number=1,
    source_agent="test",
))

assert len(events_received) == 1
print("EventBus works!")
```

```python
# Test persistence
from swarm_attack.events.persistence import EventPersistence
from swarm_attack.config import SwarmConfig

config = SwarmConfig.load()
persistence = EventPersistence(config)

# Query recent events
events = persistence.get_recent(limit=10)
print(f"Found {len(events)} recent events")

# Query by feature
events = persistence.get_by_feature("test-feature")
print(f"Found {len(events)} events for test-feature")
```

**Verify:**
- [ ] Events are received by subscribers
- [ ] Events are persisted to `.swarm/events/events-YYYY-MM-DD.jsonl`
- [ ] Events can be queried by feature

### 12.3 Test Session Initialization Protocol

```python
from swarm_attack.session_initializer import SessionInitializer
from swarm_attack.config import SwarmConfig

config = SwarmConfig.load()
initializer = SessionInitializer(config)

# Test initialization
result = initializer.initialize_session(
    feature_id="test-feature",
    issue_number=1,
)

print(f"Working directory verified: {result.working_dir_verified}")
print(f"Issue loaded: {result.issue_loaded}")
print(f"Baseline tests: {result.baseline_test_count}")
```

```python
# Test progress logging
from swarm_attack.progress_logger import ProgressLogger

logger = ProgressLogger(config, "test-feature")
logger.log_session_start(issue_number=1)
logger.log_checkpoint("Tests written", {"test_count": 5})
logger.log_session_end(success=True)

# Check progress file
# cat .swarm/features/test-feature/progress.txt
```

**Verify:**
- [ ] 5-step initialization completes
- [ ] Progress logged to `.swarm/features/{id}/progress.txt`
- [ ] Verification status saved to `.swarm/features/{id}/verification.json`

### 12.4 Test Universal Context Builder

```python
from swarm_attack.universal_context_builder import UniversalContextBuilder
from swarm_attack.config import SwarmConfig
from swarm_attack.state_store import StateStore

config = SwarmConfig.load()
state_store = StateStore(config)
builder = UniversalContextBuilder(config, state_store)

# Build context for different agents
coder_ctx = builder.build_context_for_agent("coder", "test-feature", 1)
verifier_ctx = builder.build_context_for_agent("verifier", "test-feature", 1)

print(f"Coder token budget: {coder_ctx.token_count}")
print(f"Verifier token budget: {verifier_ctx.token_count}")

# Coder should have more context
assert coder_ctx.token_count > verifier_ctx.token_count
print("Token budgets correct!")
```

**Verify:**
- [ ] Coder gets ~15,000 tokens of context
- [ ] Verifier gets ~3,000 tokens of context
- [ ] Context includes project instructions, module registry

### 12.5 Test QA Session Extension

```python
from swarm_attack.qa.session_extension import QASessionExtension
from swarm_attack.qa.coverage_tracker import CoverageTracker
from swarm_attack.qa.regression_detector import RegressionDetector
from swarm_attack.config import SwarmConfig

config = SwarmConfig.load()
extension = QASessionExtension(config)

# Simulate session start
extension.on_session_start("test-feature")

# Check baseline captured
tracker = CoverageTracker(config)
baseline = tracker.get_latest_baseline("test-feature")
print(f"Baseline captured: {baseline is not None}")

# Simulate session complete (no regressions)
result = extension.on_session_complete("test-feature")
print(f"Should block: {result.should_block}")
print(f"Block reason: {result.block_reason}")
```

**Verify:**
- [ ] Coverage baseline captured at session start
- [ ] Regressions detected if tests fail
- [ ] Session blocked on critical regressions

### 12.6 Test Schema Drift Prevention

```python
from swarm_attack.agents.coder import CoderAgent
from swarm_attack.state_store import StateStore
from swarm_attack.config import SwarmConfig
from swarm_attack.models import IssueOutput, TaskRef, TaskStage, RunState, FeaturePhase
from pathlib import Path
import tempfile

config = SwarmConfig.load()
state_store = StateStore(config)

# Create a temp directory with a "modified" file
with tempfile.TemporaryDirectory() as tmp:
    # Create file with classes
    models_dir = Path(tmp) / "models"
    models_dir.mkdir()
    (models_dir / "user.py").write_text('''
@dataclass
class User:
    user_id: str
    name: str
''')

    # Test extraction from modified file
    coder = CoderAgent(config)
    outputs = coder._extract_outputs(
        files={},  # No new files
        files_modified=["models/user.py"],
        base_path=Path(tmp),
    )

    print(f"Classes found: {outputs.classes_defined}")
    assert "models/user.py" in outputs.classes_defined
    assert "User" in outputs.classes_defined["models/user.py"]
    print("Modified file tracking works!")
```

**Verify:**
- [ ] Classes extracted from modified files (not just created)
- [ ] Module registry includes modified file classes
- [ ] Coder prompt shows existing classes with source code

### 12.7 Run Automated Tests

```bash
# Run all v0.3.0 feature tests
PYTHONPATH=. pytest tests/unit/test_auto_approval.py -v
PYTHONPATH=. pytest tests/unit/test_events.py -v
PYTHONPATH=. pytest tests/unit/test_session_initializer.py -v
PYTHONPATH=. pytest tests/unit/test_universal_context_builder.py -v
PYTHONPATH=. pytest tests/unit/qa/test_session_extension.py -v
PYTHONPATH=. pytest tests/integration/test_context_flow_fixes.py -v

# Run all at once
PYTHONPATH=. pytest tests/unit/test_auto_approval.py \
    tests/unit/test_events.py \
    tests/unit/test_session_initializer.py \
    tests/unit/test_universal_context_builder.py \
    tests/unit/qa/test_session_extension.py \
    tests/integration/test_context_flow_fixes.py \
    -v --tb=short
```

**Expected Results:**
- Auto-approval: 22 tests passing
- Events: 26 tests passing
- Session init: 18 tests passing
- Universal context: 20 tests passing
- QA session: 15 tests passing
- Context flow: 9 tests passing
- **Total: 110+ tests passing**

---

## Getting Help

- **CLAUDE.md**: See `CLAUDE.md` for system overview
- **Implementation Plan**: See `IMPLEMENTATION_PLAN.md` for architecture
- **GitHub Issues**: Report bugs at the repo's issue tracker

```bash
swarm-attack --help
swarm-attack bug --help
```

---

*This guide was written for Swarm Attack v0.3.0. Commands and behavior may change in future versions.*
