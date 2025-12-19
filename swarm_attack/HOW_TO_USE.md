# Feature Swarm: How-To Guide for New Users

A step-by-step guide for PMs and Engineers to use Feature Swarm for automated feature development.

## What is Feature Swarm?

Feature Swarm is a multi-agent AI system that automates the software development lifecycle:
- **PRD → Spec → Issues → Code → Tests → Commit**

It uses Claude CLI and Codex CLI to run specialized AI agents that collaborate to implement features from product requirements.

---

## Prerequisites

### 1. Install Required CLIs

```bash
# Install Claude CLI (requires Anthropic Max subscription)
# Follow: https://docs.anthropic.com/claude-code

# Install Codex CLI (requires OpenAI ChatGPT subscription)
npm install -g @openai/codex
```

### 2. Authenticate

```bash
# Authenticate Claude CLI
claude auth login

# Verify authentication
claude doctor

# Authenticate Codex CLI
codex auth
```

### 3. Verify Setup

```bash
# Test Claude CLI
claude --version
echo "Hello" | claude -p "Say hi back"

# Test Codex CLI
codex --version
```

---

## The Feature Development Lifecycle

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. PRD     │ → │  2. Spec    │ → │  3. Issues  │ → │  4. Code    │
│  (You Write)│    │  (AI Writes)│    │  (AI Creates)│   │  (AI Writes)│
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                         ↓                                      ↓
                   ┌─────────────┐                       ┌─────────────┐
                   │  Review &   │                       │  Tests &    │
                   │  Approval   │                       │  Commit     │
                   └─────────────┘                       └─────────────┘
```

---

## Step 1: Write Your PRD

### What is a PRD?
A Product Requirements Document describing what you want to build.

### Where to Put It
```
.claude/prds/<feature-id>.md
```

### PRD Template

```markdown
# PRD: <Feature Name>

## Overview
What are we building and why?

## Requirements
1. Requirement 1
2. Requirement 2
3. Requirement 3

## Success Criteria
- How do we know it's done?
- What should work?

## Out of Scope
- What we're NOT building
```

### Example PRD

```markdown
# PRD: User Authentication

## Overview
Implement secure user authentication with email/password login.

## Requirements
1. User can register with email and password
2. User can log in and receive JWT token
3. Protected routes require valid token
4. Password reset via email

## Success Criteria
- User can complete registration flow
- Login returns valid JWT
- Invalid credentials return 401
- Tests pass

## Out of Scope
- Social OAuth (Google, GitHub)
- Multi-factor authentication
```

### What to Look For
- Clear, specific requirements
- Measurable success criteria
- Defined scope boundaries

---

## Step 2: Run the Spec Pipeline

### What Happens
Three AI agents collaborate:
1. **Spec Author** - Drafts an engineering specification
2. **Spec Critic** - Reviews and scores the spec
3. **Spec Moderator** - Revises based on feedback

### Command
```bash
cd your-project
python -m swarm_attack spec <feature-id>
```

### Example
```bash
python -m swarm_attack spec user-authentication
```

### Output Files Created
```
specs/<feature-id>/
├── spec-draft.md      # The engineering specification
├── spec-review.json   # Critic's scores and feedback
└── spec-final.md      # Final approved spec (after approval)
```

### What to Look For in the Spec

**Good spec characteristics:**
- Clear architecture overview
- Specific implementation steps
- Test strategy with concrete test cases
- Risk assessment with mitigations
- File/function names specified

**Red flags:**
- Vague requirements ("make it fast")
- Missing test strategy
- No error handling consideration
- Architecture doesn't match codebase

### Review the Scores
```json
{
  "scores": {
    "clarity": 0.85,      // Is it clear what to build?
    "coverage": 0.90,     // Does it cover all PRD requirements?
    "architecture": 0.80, // Is the design sound?
    "risk": 0.75          // Are risks identified?
  },
  "recommendation": "APPROVE"  // or "REVISE"
}
```

**Score thresholds:**
- All scores should be ≥ 0.8 for approval
- If any score is low, review that section

---

## Step 3: Approve the Spec

### Review Checklist
- [ ] Architecture matches existing codebase patterns
- [ ] Implementation plan is realistic
- [ ] Test cases cover edge cases
- [ ] Risks are addressed
- [ ] No security concerns

### Approve
```bash
python -m swarm_attack approve <feature-id>
```

### Or Request Changes
If the spec needs work, edit `specs/<feature-id>/spec-draft.md` and re-run the spec pipeline.

---

## Step 4: Create Issues

### What Happens
The system breaks down the spec into implementable GitHub issues.

### Command
```bash
python -m swarm_attack issues <feature-id>
```

### Output
- Creates GitHub issues in your repo
- Links issues to the feature
- Sets dependencies between issues

### What to Look For
- Issues are appropriately sized (small = 1-2 hours, medium = half day)
- Dependencies make sense
- Issue descriptions are clear

---

## Step 5: Greenlight Implementation

### Review Issues First
```bash
# List issues for the feature
python -m swarm_attack status <feature-id>
```

### Greenlight
```bash
python -m swarm_attack greenlight <feature-id>
```

---

## Step 6: Run Implementation

### What Happens
For each issue, agents collaborate:
1. **Coder (Implementation Agent)** - Full TDD workflow: writes tests, implements code, iterates until passing
2. **Verifier** - Runs tests and validates

### Command
```bash
# Run next available issue
python -m swarm_attack run <feature-id>

# Or run specific issue
python -m swarm_attack run <feature-id> --issue 123
```

### The Retry Feedback Loop

When tests fail, the system automatically retries with **targeted feedback**:

1. **Verifier** extracts specific failure details from pytest output
2. **Coder** receives on retry:
   - Which tests failed with exact error messages
   - The existing implementation to iterate on
   - Instructions to make targeted fixes, not rewrites

This typically resolves issues in 1-2 retries instead of 3 blind attempts.

### What to Look For

**During implementation:**
- Watch the session output for errors
- Check that tests are meaningful (not just `assert True`)
- Verify code follows project conventions

**After implementation:**
- Review the commit: `git log -1 -p`
- Run tests manually: `pytest tests/`
- Check code quality

---

## Step 7: Monitor Progress

### Check Status
```bash
python -m swarm_attack status <feature-id>
```

### Status Output
```
Feature: user-authentication
Phase: IMPLEMENTING
Cost: $0.45

Tasks:
  #1 [DONE]    Create user model
  #2 [DONE]    Implement registration endpoint
  #3 [RUNNING] Add JWT token generation
  #4 [READY]   Implement login endpoint
  #5 [BLOCKED] Password reset flow
```

### Understanding Task States
| State | Meaning | Action |
|-------|---------|--------|
| BACKLOG | Not ready yet | Wait for dependencies |
| READY | Can be worked on | Will be picked up next |
| IN_PROGRESS | Currently being worked | Monitor output |
| DONE | Successfully completed | Review commit |
| BLOCKED | Failed after retries | Manual intervention needed |
| SKIPPED | Dependency was blocked | Review blocked dependency |
| **SPLIT** | Too complex, auto-split into children | Work on child issues instead |

---

## Handling Problems

### Issue: "Skill not found"
**Cause:** Missing skill file in `.claude/skills/`

**Fix:** Ensure all required skills exist:
```bash
ls .claude/skills/
# Should include:
# - feature-spec-author/SKILL.md
# - feature-spec-critic/SKILL.md
# - feature-spec-moderator/SKILL.md
# - coder/SKILL.md (Implementation Agent with TDD)
# - verifier/SKILL.md
# - recovery/SKILL.md
# - complexity-gate/SKILL.md
# - issue-splitter/SKILL.md (auto-splits complex issues)
```

### Issue: "Empty spec generated"
**Cause:** Claude didn't write to file

**Fix:** Check skill prompt includes explicit Write tool instruction

### Issue: "Tests failing after implementation"
**Action:**
1. Check the test file: Are tests reasonable?
2. Check the implementation: Does it match spec?
3. Run manually: `pytest tests/ -v`

### Issue: "Task stuck in BLOCKED"
**Action:**
1. Check the error message in session state
2. Review the recovery agent's analysis
3. Manually fix the issue or update the spec

### Issue: "Feature stuck in BLOCKED after spec debate"
**Cause:** The spec debate may have completed successfully but the process timed out before updating the state.

**Fix:**
```bash
# Auto-detect and recover
swarm-attack unblock my-feature

# Or use interactive recovery
swarm-attack recover my-feature

# Force a specific phase if auto-detect fails
swarm-attack unblock my-feature --phase SPEC_NEEDS_APPROVAL
```

The `unblock` command analyzes the spec files on disk. If `spec-rubric.json` shows `ready_for_approval: true` and all scores meet thresholds, it automatically transitions to `SPEC_NEEDS_APPROVAL`.

### Issue: "Task marked as SPLIT"
**Cause:** The issue was too complex (>12 acceptance criteria or >8 methods) and was automatically split into smaller sub-issues.

**What Happens:**
1. ComplexityGateAgent detects the issue is too large
2. IssueSplitterAgent creates 2-4 smaller sub-issues
3. Parent issue is marked as SPLIT
4. Child issues are added to the task list
5. Dependencies are rewired automatically

**What to Do:**
- Check the status to see the child issues
- Implementation will continue with the child issues
- No manual intervention needed

```bash
# Check status to see child issues
swarm-attack status my-feature

# Example output:
# #5  [SPLIT]    Create user auth system      → #10, #11, #12
# #10 [READY]    └─ Create User model
# #11 [BACKLOG]  └─ Create Auth service        (deps: #10)
# #12 [BACKLOG]  └─ Create login endpoint      (deps: #11)
```

---

## Auto-Split Feature

When an issue exceeds complexity limits, the system automatically splits it:

```
ComplexityGate: "Issue too complex (estimated 35 turns)"
         ↓
IssueSplitterAgent analyzes and creates sub-issues
         ↓
State updated:
  - Parent: SPLIT stage
  - Children: READY/BACKLOG stage
  - Dependencies: Rewired
         ↓
Implementation continues with first child issue
```

### How Dependencies Are Rewired

```
Before split (issue #5 depends on #3, issue #8 depends on #5):
  #3 → #5 → #8

After split (#5 → #10, #11, #12):
  #3 → #10 → #11 → #12 → #8
       ↑                   ↑
  First child inherits    Last child becomes
  parent's deps           new dependency
```

### Split Strategies

The splitter uses these strategies based on issue content:
- **By Layer**: Separate model, API, UI components
- **By Operation**: Separate CRUD operations
- **By Criteria**: Group related acceptance criteria
- **By Phase**: Separate setup, core, integration work

---

## Cost Tracking

### View Costs
```bash
python -m swarm_attack status <feature-id>
```

### Typical Costs
| Phase | Approximate Cost |
|-------|-----------------|
| Spec Pipeline (3 agents, 2 rounds) | $0.10 - $0.30 |
| Issue Creation | $0.05 - $0.15 |
| Per Issue Implementation | $0.10 - $0.50 |
| **Total Feature (5 issues)** | **$0.50 - $2.00** |

---

## Best Practices

### For PMs Writing PRDs
1. Be specific about requirements
2. Include concrete examples
3. Define clear success criteria
4. List what's out of scope
5. Consider edge cases

### For Engineers Reviewing Specs
1. Check architecture matches codebase
2. Verify test strategy is comprehensive
3. Look for security considerations
4. Ensure error handling is specified
5. Validate file paths are correct

### For Everyone
1. Start with small features to learn the system
2. Review AI output - it's not always correct
3. Use version control - review commits before pushing
4. Monitor costs during development
5. Document any manual fixes needed

---

## Quick Reference

```bash
# Full workflow
swarm-attack init my-feature               # Create feature + PRD template
swarm-attack run my-feature                # Generate spec through debate
swarm-attack approve my-feature            # Approve spec
swarm-attack issues my-feature             # Create issues from spec
swarm-attack greenlight my-feature         # Enable implementation phase
swarm-attack run my-feature                # Implement next available issue
swarm-attack run my-feature --issue 3      # Implement specific issue
swarm-attack status my-feature             # Check progress

# Recovery commands
swarm-attack recover my-feature            # Interactive recovery flow
swarm-attack unblock my-feature            # Auto-detect and unblock
swarm-attack unblock my-feature --phase PRD_READY  # Force specific phase

# Useful commands
swarm-attack --help                        # Show all commands
swarm-attack status                        # List all features
```

---

## Troubleshooting Checklist

- [ ] Claude CLI authenticated: `claude doctor`
- [ ] Codex CLI authenticated: `codex auth`
- [ ] Skill files exist in `.claude/skills/`
- [ ] PRD exists in `.claude/prds/<feature-id>.md`
- [ ] Git repo is clean (no uncommitted changes)
- [ ] Working in correct directory

---

## Getting Help

- Check logs in `.swarm/logs/`
- Review state in `.swarm/state/<feature-id>.json`
- Check session details in `.swarm/sessions/<feature-id>/`
