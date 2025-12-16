# Swarm Attack - PM Quick Start Guide

A step-by-step guide for PMs using Swarm Attack to automate feature development.

---

## 1. Prerequisites (One-Time Setup)

### Install the AI CLIs

```bash
# Claude CLI - Install from https://docs.anthropic.com/claude-code
# (Requires Anthropic Max subscription)

# Codex CLI - Install via npm
npm install -g @openai/codex
```

### Authenticate Both CLIs

```bash
# Authenticate Claude
claude auth login

# Verify Claude is working
claude doctor

# Authenticate Codex
codex auth

# Verify Codex is working
codex --version
```

### Install Swarm Attack

```bash
# Clone the repo
git clone https://github.com/pcortes/swarm-attack.git ~/Desktop/swarm-attack

# Install as global CLI
cd ~/Desktop/swarm-attack
pip install -e .

# Verify it works
swarm-attack --version
# Should output: swarm-attack version 0.1.0
```

---

## 2. Set Up Your Project

Navigate to any project where you want to use Swarm Attack:

```bash
cd ~/Desktop/coach-automation   # or any project
```

### Create the Config File

Create `config.yaml` in your project root:

```yaml
# config.yaml
github:
  repo: "pcortes/coach-automation"  # Your GitHub repo

tests:
  command: "pytest"                  # Your test command
  args: ["-v"]

# Optional: customize these
claude:
  max_turns: 6
  timeout_seconds: 300

codex:
  model: "gpt-5.1-codex"

spec_debate:
  max_rounds: 5
```

### Copy the Skills (Agent Instructions)

```bash
# Copy default skills to your project
cp -r ~/Desktop/swarm-attack/default-skills .claude/skills
```

Your project should now have:
```
your-project/
├── config.yaml           # ← You just created this
├── .claude/
│   └── skills/           # ← You just copied this
│       ├── feature-spec-author/
│       ├── feature-spec-critic/
│       └── ...
└── ... your existing code
```

---

## 3. Verify Everything Works

```bash
# Check swarm-attack can see your project
swarm-attack status
```

You should see:
```
╭─────────────── Swarm Attack Status ───────────────╮
│ No features found.                                │
│                                                   │
│ Get started by creating a feature:                │
│   swarm-attack init <feature-name>                │
╰───────────────────────────────────────────────────╯
```

---

## 4. Create Your First Feature

### Step 1: Initialize the Feature

```bash
swarm-attack init user-authentication
```

This creates:
- `.claude/prds/user-authentication.md` (PRD template)
- `.swarm/state.json` (tracks feature progress)

### Step 2: Write Your PRD

Edit `.claude/prds/user-authentication.md`:

```markdown
# PRD: User Authentication

## Overview
Add JWT-based user authentication to the API.

## Problem Statement
Currently the API has no authentication. Any client can access any endpoint.

## Requirements
1. Users can register with email/password
2. Users can login and receive a JWT token
3. Protected endpoints require valid JWT
4. Tokens expire after 24 hours

## Success Criteria
- All auth endpoints return proper HTTP status codes
- Invalid tokens are rejected with 401
- Unit tests cover all auth flows

## Out of Scope
- Social login (Google, GitHub)
- Password reset flow
- Multi-factor authentication
```

### Step 3: Run the Spec Pipeline

```bash
swarm-attack run user-authentication
```

This starts the **spec debate loop**:
1. **SpecAuthor** (Claude) generates initial engineering spec
2. **SpecCritic** (Codex) reviews and scores it
3. **SpecModerator** (Claude) improves based on feedback
4. Loop continues until scores pass thresholds

Watch the terminal for progress. This typically takes 2-5 minutes.

### Step 4: Check Status

```bash
swarm-attack status user-authentication
```

Shows detailed status:
```
Feature: user-authentication
Phase: Spec Needs Approval
Rounds: 3
Scores:
  clarity: 0.88
  coverage: 0.85
  architecture: 0.82
  risk: 0.80
```

### Step 5: Review and Approve

Look at the generated spec:
```bash
cat .claude/specs/user-authentication/spec-draft.md
```

If it looks good:
```bash
swarm-attack approve user-authentication
```

If you want changes:
```bash
swarm-attack reject user-authentication --reason "Need more detail on token refresh"
```

---

## 5. Command Reference

| Command | What It Does |
|---------|--------------|
| `swarm-attack status` | Dashboard of all features |
| `swarm-attack status <feature>` | Detailed feature status |
| `swarm-attack init <feature>` | Create new feature + PRD template |
| `swarm-attack run <feature>` | Run pipeline (spec or implementation based on phase) |
| `swarm-attack run <feature> --issue N` | Run specific issue implementation |
| `swarm-attack approve <feature>` | Approve spec for implementation |
| `swarm-attack reject <feature>` | Reject spec with feedback |
| `swarm-attack issues <feature>` | Create GitHub issues from approved spec |
| `swarm-attack greenlight <feature>` | Enable implementation phase |
| `swarm-attack smart <feature>` | Interactive mode with recovery |
| `swarm-attack recover <feature>` | Recover from blocked state |
| `swarm-attack unblock <feature>` | Unblock a stuck feature |
| `swarm-attack --help` | Show all commands |

---

## 6. The Full Pipeline (What Happens)

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR WORKFLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Write PRD          You write .claude/prds/my-feature.md     │
│       ↓                                                         │
│  2. swarm-attack run   Kicks off the AI agents                  │
│       ↓                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SPEC DEBATE (automatic)                                 │   │
│  │  ┌──────────┐    ┌──────────┐    ┌────────────┐        │   │
│  │  │  Author  │ →  │  Critic  │ →  │ Moderator  │        │   │
│  │  │ (Claude) │    │ (Codex)  │    │  (Claude)  │        │   │
│  │  └──────────┘    └──────────┘    └─────┬──────┘        │   │
│  │                                        │               │   │
│  │                    Score < 0.85? ──────┘               │   │
│  │                         │                              │   │
│  │                    Score >= 0.85                       │   │
│  │                         ↓                              │   │
│  │                  Spec Ready for Review                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│       ↓                                                         │
│  3. swarm-attack approve   You review and approve               │
│       ↓                                                         │
│  4. swarm-attack issues    Creates GitHub issues from spec      │
│       ↓                                                         │
│  5. swarm-attack greenlight  Enables implementation phase       │
│       ↓                                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  IMPLEMENTATION (automatic, per issue)                   │   │
│  │  ┌──────────────────────────┐   ┌──────────┐            │   │
│  │  │  Coder (Implementation)  │ → │ Verifier │            │   │
│  │  │  TDD: tests + code       │   │ (pytest) │            │   │
│  │  │       (Claude)           │   │          │            │   │
│  │  └──────────────────────────┘   └────┬─────┘            │   │
│  │                                      │                  │   │
│  │          Tests fail? ────────────────┘                  │   │
│  │               │         (retry with failure feedback)   │   │
│  │          Tests pass                                     │   │
│  │               ↓                                         │   │
│  │         Issue marked DONE                               │   │
│  └─────────────────────────────────────────────────────────┘   │
│       ↓                                                         │
│  6. swarm-attack run       Repeat for each issue                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6b. How the Retry Feedback Loop Works

When tests fail during implementation, the system automatically retries with **targeted feedback**:

1. **Verifier** parses pytest output to extract specific failures:
   - Test name and class
   - File and line number
   - Exact assertion error message

2. **Orchestrator** passes this to Coder on retry:
   - Which tests failed and why
   - The existing implementation code
   - Retry attempt number

3. **Coder** receives a prompt like:
   ```
   ⚠️ RETRY ATTEMPT #2

   TEST FAILURES FROM PREVIOUS RUN:
   1. test_has_scroll_controller (line 124)
      Error: AssertionError: Widget must use ScrollController

   YOUR PREVIOUS IMPLEMENTATION:
   [existing code shown here]

   Focus on fixing THESE SPECIFIC failures. Do not rewrite working code.
   ```

4. **Result**: Coder makes targeted fixes instead of rewriting everything.

This typically resolves issues in 1-2 retries instead of failing after 3 blind attempts.

---

## 7. Where Things Live

After running swarm-attack, your project will have:

```
your-project/
├── config.yaml                    # Your config
├── .claude/
│   ├── prds/                      # Your PRDs
│   │   └── user-authentication.md
│   ├── specs/                     # Generated specs
│   │   └── user-authentication/
│   │       ├── spec-draft.md      # The engineering spec
│   │       ├── spec-review.json   # Critic's review
│   │       └── spec-rubric.json   # Scoring rubric
│   └── skills/                    # Agent instructions
└── .swarm/
    └── state.json                 # Feature tracking state
```

---

## 8. Troubleshooting

### "Configuration file not found"
```bash
# Make sure you have config.yaml in your project root
ls config.yaml

# If missing, create it (see step 2)
```

### "Claude CLI not found"
```bash
# Check Claude is installed and authenticated
claude doctor

# If not, install from https://docs.anthropic.com/claude-code
```

### "Codex CLI not found"
```bash
# Install Codex
npm install -g @openai/codex

# Authenticate
codex auth
```

### "Skills not found"
```bash
# Copy default skills
cp -r ~/Desktop/swarm-attack/default-skills .claude/skills
```

### Spec debate stuck or timing out
```bash
# Check what's happening
swarm-attack status my-feature

# Try smart mode for interactive recovery
swarm-attack smart my-feature
```

### Feature stuck in BLOCKED state
```bash
# Auto-detect and recover (recommended)
swarm-attack unblock my-feature

# Or use interactive recovery with options
swarm-attack recover my-feature

# Force a specific phase if needed
swarm-attack unblock my-feature --phase PRD_READY
swarm-attack unblock my-feature --phase SPEC_NEEDS_APPROVAL
```

The `unblock` command checks if the spec files on disk show that the debate
actually completed successfully (e.g., timeout occurred after Claude finished
writing files). If so, it automatically transitions to the correct phase.

---

## 9. Tips for Writing Good PRDs

The better your PRD, the better the generated spec.

**Do:**
- Be specific about requirements
- Include success criteria
- List what's out of scope
- Mention technical constraints

**Don't:**
- Be vague ("make it better")
- Include implementation details
- Skip the out-of-scope section

---

## 10. Bug Bash - Automated Bug Investigation

Swarm Attack also includes a bug investigation pipeline for fixing bugs automatically.

### Step 1: Initialize a Bug Investigation

```bash
# When you have a failing test
swarm-attack bug init "Description of the bug" \
  --id my-bug-id \
  --test tests/path/to_test.py::TestClass::test_method \
  -e "Error message from the failure"
```

### Step 2: Run Analysis Pipeline

```bash
swarm-attack bug analyze my-bug-id
```

This runs:
1. **Reproduce** - Confirms the bug exists by running the failing test
2. **Analyze** - LLM analyzes root cause with debate validation
3. **Plan** - Generates a comprehensive fix plan with risk assessment

### Step 3: Review and Approve

```bash
# Check status
swarm-attack bug status my-bug-id

# Review the fix plan
cat .swarm/bugs/my-bug-id/fix-plan.md

# Approve for implementation
swarm-attack bug approve my-bug-id
```

### Step 4: Apply the Fix

```bash
swarm-attack bug fix my-bug-id
```

### Bug Commands Reference

| Command | Description |
|---------|-------------|
| `swarm-attack bug list` | List all bug investigations |
| `swarm-attack bug init "desc" --id ID --test PATH -e "error"` | Create bug investigation |
| `swarm-attack bug analyze <bug-id>` | Run full analysis pipeline |
| `swarm-attack bug status <bug-id>` | Show bug status |
| `swarm-attack bug approve <bug-id>` | Approve fix plan |
| `swarm-attack bug fix <bug-id>` | Apply the fix |
| `swarm-attack bug reject <bug-id>` | Reject (won't fix) |
| `swarm-attack bug unblock <bug-id>` | Unblock stuck bug |

---

## Need Help?

```bash
swarm-attack --help
swarm-attack run --help
swarm-attack bug --help
```

GitHub: https://github.com/pcortes/swarm-attack
