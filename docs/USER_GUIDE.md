# Feature Swarm: User Guide for Product Managers

**A step-by-step guide to automating feature development from idea to shipped code.**

---

## Table of Contents

1. [What is Feature Swarm?](#1-what-is-feature-swarm)
2. [Prerequisites & Setup](#2-prerequisites--setup)
3. [The Feature Lifecycle](#3-the-feature-lifecycle)
4. [Quick Start: Your First Feature](#4-quick-start-your-first-feature)
5. [Command Reference](#5-command-reference)
6. [Understanding the Dashboard](#6-understanding-the-dashboard)
7. [Human Checkpoints](#7-human-checkpoints)
8. [Handling Failures & Recovery](#8-handling-failures--recovery)
9. [Best Practices](#9-best-practices)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. What is Feature Swarm?

Feature Swarm is an **AI-powered automation tool** that takes your feature ideas from concept to working code. It orchestrates the entire development process:

```
YOUR IDEA → PRD → ENGINEERING SPEC → GITHUB ISSUES → TESTS → CODE → DONE
              ↑           ↑                ↑
           You write   You approve    You greenlight
```

### Key Benefits

- **One Command**: Just run `feature-swarm` and it figures out what to do next
- **Automated Spec Writing**: AI drafts engineering specs from your PRD
- **Quality Gates**: Independent AI review ensures specs meet quality standards
- **TDD Approach**: Tests are written before code, ensuring reliability
- **Recovery Built-in**: If something fails, the system knows how to recover

### How It Works

Feature Swarm uses **two different AI systems** for checks and balances:
- **Claude** (via Claude Code CLI) - Writes specs and code
- **Codex/GPT** (via Codex CLI) - Reviews and critiques Claude's work

This "two LLM" approach ensures independent validation of all AI-generated content.

---

## 2. Prerequisites & Setup

### 2.1 Required Software

Before using Feature Swarm, ensure you have:

| Software | Purpose | How to Get It |
|----------|---------|---------------|
| Python 3.10+ | Runs Feature Swarm | `brew install python` or python.org |
| Git | Version control | `brew install git` |
| Claude Code CLI | AI spec writing & coding | `npm install -g @anthropic/claude-code` |
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

3. **Install Feature Swarm:**
   ```bash
   # From the repo root
   pip install -e .
   ```

### 2.4 Project Configuration

Create a `config.yaml` file in your repository root:

```yaml
# Feature Swarm Configuration

# Paths
repo_root: .
specs_dir: specs
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
feature-swarm init user-notifications
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
# Run Feature Swarm - it will automatically start the spec pipeline
feature-swarm run user-notifications
```

**What happens:**
1. **SpecAuthor** (Claude) reads your PRD and writes an engineering spec
2. **SpecCritic** (Codex) reviews the spec and scores it on:
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
  specs/user-notifications/spec-draft.md

Then approve with:
  feature-swarm approve user-notifications
```

### Step 4: Review and Approve the Spec

Open and review `specs/user-notifications/spec-draft.md`. When satisfied:

```bash
feature-swarm approve user-notifications
```

### Step 5: Let Implementation Run

```bash
# Continue running - it will create issues and implement them
feature-swarm smart user-notifications
```

The system will:
1. Create GitHub issues from the spec
2. Prioritize issues by dependencies and value
3. For each issue:
   - Write tests first (TDD)
   - Implement code to pass tests
   - Verify all tests pass
   - Create a git commit
4. Mark issues as done when complete

### Step 6: Review and Merge

When all issues are done, review the feature branch and merge:

```bash
# See what was done
feature-swarm status user-notifications

# Review the commits
git log feature/user-notifications

# Merge when ready
git checkout main
git merge feature/user-notifications
```

---

## 5. Command Reference

### Primary Commands

| Command | Description |
|---------|-------------|
| `feature-swarm` | Show dashboard of all features |
| `feature-swarm status` | Same as above - show all features |
| `feature-swarm status <feature>` | Show detailed status of one feature |
| `feature-swarm init <feature>` | Create a new feature |
| `feature-swarm run <feature>` | Run the spec pipeline |
| `feature-swarm approve <feature>` | Approve a spec |
| `feature-swarm reject <feature>` | Reject a spec (optionally re-run) |
| `feature-swarm smart <feature>` | Smart mode - auto-detect next action |
| `feature-swarm next <feature>` | Show what would happen next |
| `feature-swarm recover <feature>` | Handle interrupted sessions |

### Smart Mode (`feature-swarm smart`)

The `smart` command is the primary way to use Feature Swarm. It:
1. Checks for interrupted sessions → offers recovery options
2. Checks for blocked issues → offers retry options
3. Determines the next action based on current state
4. Executes that action

```bash
# Just run this repeatedly until your feature is done
feature-swarm smart user-notifications
```

### Examples

```bash
# See all your features
feature-swarm status

# Start working on a feature (does the right thing)
feature-swarm smart user-auth

# Check what would happen next without doing it
feature-swarm next user-auth

# Recover from a crash/interruption
feature-swarm recover user-auth

# Re-run spec generation after rejection
feature-swarm reject user-auth --rerun
```

---

## 6. Understanding the Dashboard

When you run `feature-swarm status`, you see:

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
**Action:** Review `specs/<feature>/spec-draft.md` and either:

```bash
# If the spec looks good
feature-swarm approve <feature>

# If changes are needed
# Option A: Edit the spec manually, then approve
# Option B: Re-run the pipeline
feature-swarm reject <feature> --rerun
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
feature-swarm greenlight <feature>
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
feature-swarm recover <feature>
```

You'll see options:
- **[R]esume**: Continue from the last checkpoint
- **[B]ackup & restart**: Stash changes, start fresh on this issue
- **[S]kip**: Mark the issue as blocked, move to next

### Blocked Issues

An issue becomes "blocked" after 3 failed implementation attempts.

```bash
# See blocked issues
feature-swarm status <feature>

# Offers to retry blocked issues
feature-swarm smart <feature>
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
feature-swarm rollback <feature>
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
2. **Check status often** - `feature-swarm status <feature>`
3. **Don't ignore blocked issues** - They indicate real problems
4. **Review specs carefully** - Garbage in, garbage out
5. **Start small** - Your first feature should be simple

### Cost Management

- Each spec pipeline costs ~$0.10-0.20
- Each issue implementation costs ~$0.05-0.15
- A typical feature costs $0.50-2.00 total
- Check `feature-swarm status` to see cumulative costs

---

## 10. Troubleshooting

### "Claude CLI not found"

```bash
# Verify Claude is installed
which claude

# If not found, install it
npm install -g @anthropic/claude-code

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
feature-swarm status

# If the feature doesn't exist, create it
feature-swarm init <feature-name>
```

### "Spec pipeline keeps failing"

1. Check the logs: `.swarm/logs/`
2. Verify your PRD is well-formed
3. Check Claude CLI is authenticated
4. Try running with `--dry-run` to see what would happen

### "Tests keep failing during implementation"

1. Review the test file created by TestWriterAgent
2. Check if tests are reasonable for the requirements
3. Review the CoderAgent's implementation attempt
4. Consider breaking the issue into smaller pieces

### "Session stuck"

```bash
# Force recovery mode
feature-swarm recover <feature>

# Or manually clean up
rm -rf .swarm/locks/<feature>/
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FEATURE SWARM QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  START A FEATURE                                                     │
│  ───────────────                                                     │
│  feature-swarm init my-feature     # Create feature                 │
│  # Edit .claude/prds/my-feature.md # Write your PRD                 │
│  feature-swarm run my-feature      # Generate spec                  │
│                                                                      │
│  DAILY WORKFLOW                                                      │
│  ──────────────                                                      │
│  feature-swarm status              # See all features               │
│  feature-swarm smart my-feature    # Do the next thing              │
│                                                                      │
│  HUMAN CHECKPOINTS                                                   │
│  ─────────────────                                                   │
│  feature-swarm approve my-feature  # Approve spec                   │
│  feature-swarm reject my-feature   # Reject spec                    │
│  feature-swarm greenlight my-feat  # Start implementation           │
│                                                                      │
│  RECOVERY                                                            │
│  ────────                                                            │
│  feature-swarm recover my-feature  # Handle interruptions           │
│  feature-swarm rollback my-feature # Undo last session              │
│                                                                      │
│  KEY FILES                                                           │
│  ─────────                                                           │
│  .claude/prds/<feature>.md         # Your PRD                       │
│  specs/<feature>/spec-draft.md     # Generated spec                 │
│  .swarm/state/<feature>.json       # Feature state                  │
│  .swarm/sessions/                  # Session history                │
│  config.yaml                       # Project configuration          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Getting Help

- **Feature Swarm Spec**: See `FEATURE_SWARM_SPEC.md` for technical details
- **Implementation Plan**: See `IMPLEMENTATION_PLAN.md` for architecture
- **GitHub Issues**: Report bugs at the repo's issue tracker

---

*This guide was written for Feature Swarm v1.0. Commands and behavior may change in future versions.*
