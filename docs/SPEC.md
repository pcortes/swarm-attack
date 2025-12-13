# Feature Swarm: Complete Engineering Specification

**Version:** 3.1
**Last Updated:** 2025-11-26
**Status:** Final

---

## 0. Philosophy

### 0.1 One Command to Rule Them All

```bash
# This is all you need to remember
feature-swarm

# It figures out what to do based on current state
```

The CLI is **state-aware**. It reads your current situation and does the right thing:
- No features? Prompts you to create a PRD
- PRD exists but no spec? Runs spec generation
- Spec needs approval? Asks you to approve
- Issues need validation? Validates them
- Ready to implement? Picks the next issue and works on it
- Interrupted session? Offers recovery options
- Everything done? Celebrates with you

### 0.2 Core Principles

1. **Smart by Default**: The system knows what to do next
2. **One Issue Per Session**: Atomic units of work, clean rollback
3. **Human Checkpoints**: Spec approval and issue greenlight require human
4. **Graceful Recovery**: Every failure has a recovery path
5. **State is Truth**: Everything is persisted, resumable across sessions

---

## 1. What This System Does

Feature Swarm is a **Python orchestrator** that takes you from idea to shipped code:

```
IDEA → PRD → SPEC → ISSUES → TESTS → CODE → DONE
       ↑      ↑       ↑
    Human  Human   Human
    Input  Approval Greenlight
```

It coordinates:
- **Claude Code CLI** for spec writing/implementation (uses Max subscription)
- **OpenAI Codex CLI** for independent review/critique (uses ChatGPT subscription)
- **CCPM** for PRD/Epic/Issue management
- **GitHub** as the persistent backlog
- **Specialized agents** for each phase

### 1.1 Multi-LLM Architecture (Subscription-Based)

Feature Swarm uses **TWO different LLMs** via their CLI tools, both using flat-rate subscriptions (no API keys):

| LLM | CLI Tool | Auth Method | Used For |
|-----|----------|-------------|----------|
| Claude | `claude -p` | Claude Code Max subscription | Writing specs, generating code |
| Codex (GPT-5) | `codex exec` | ChatGPT Plus/Pro subscription | Independent review/critique |

**Why Two LLMs?** We don't want Claude reviewing its own work. Codex provides independent validation of Claude's output.

**Cost Model:** Flat monthly subscriptions instead of per-token API charges:
- Claude Code Max: $100-200/month (unlimited within rate limits)
- ChatGPT Plus/Pro: $20-200/month (unlimited within rate limits)

---

## 2. The Smart CLI

### 2.1 Primary Command

```bash
$ feature-swarm

# Or with a specific feature
$ feature-swarm user-auth-jwt
```

### 2.2 What It Does (State Machine)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SMART CLI DECISION TREE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  $ feature-swarm [feature-slug]                                             │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ No feature specified?                                               │    │
│  │ → Show dashboard of all features and their status                   │    │
│  │ → Prompt: "Which feature?" or "Create new?"                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Check: Does .claude/prds/<feature>.md exist?                        │    │
│  │                                                                     │    │
│  │ NO → "PRD missing. Let's create it."                                │    │
│  │      → Open Claude Code interactively                               │    │
│  │      → Run /pm:prd-new <feature>                                    │    │
│  │      → Exit after PRD created                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Check: Is there an interrupted session?                             │    │
│  │                                                                     │    │
│  │ YES → "Found interrupted work on issue #43"                         │    │
│  │       → Offer: [R]esume, [B]ackup & restart, [S]kip                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Check current phase, do the right thing:                            │    │
│  │                                                                     │    │
│  │ PRD_READY          → Run spec generation                            │    │
│  │ SPEC_DRAFTING      → Continue spec debate                           │    │
│  │ SPEC_NEEDS_APPROVAL→ "Review spec at X. Approve? [Y/n]"             │    │
│  │ SPEC_APPROVED      → Create issues via CCPM                         │    │
│  │ ISSUES_CREATED     → Validate issues                                │    │
│  │ ISSUES_NEED_REVIEW → "Review validation. Greenlight? [Y/n]"         │    │
│  │ READY_TO_IMPLEMENT → Pick next issue, implement it                  │    │
│  │ COMPLETE           → "All done! Ready to merge."                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Example Session

```bash
$ feature-swarm user-auth-jwt

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Feature: user-auth-jwt
Status:  READY_TO_IMPLEMENT (3/6 issues done)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next up: Issue #45 - Implement token refresh endpoint

This session will:
  1. Write tests for token refresh
  2. Implement the endpoint
  3. Verify all tests pass
  4. Mark issue as done

Estimated time: 5-10 minutes
Estimated cost: ~$0.05

Continue? [Y/n] _
```

### 2.4 Escape Hatches (When You Need Control)

```bash
# Override automatic behavior
feature-swarm user-auth-jwt --phase spec      # Force run spec phase
feature-swarm user-auth-jwt --issue 47        # Work on specific issue
feature-swarm user-auth-jwt --skip-validation # Skip issue validation
feature-swarm user-auth-jwt --dry-run         # Show what would happen

# Utilities
feature-swarm status                          # Dashboard of all features
feature-swarm status user-auth-jwt            # Detailed status of one feature
feature-swarm logs user-auth-jwt              # View logs
feature-swarm rollback user-auth-jwt          # Undo last session's work
```

---

## 3. Feature Lifecycle

### 3.1 Phases

```python
class FeaturePhase(Enum):
    # Setup
    NO_PRD = auto()                  # Need to create PRD interactively
    PRD_READY = auto()               # PRD exists, ready for spec

    # Specification
    SPEC_IN_PROGRESS = auto()        # Spec debate running
    SPEC_NEEDS_APPROVAL = auto()     # Spec ready for human review
    SPEC_APPROVED = auto()           # Human approved spec

    # Issue Creation
    ISSUES_CREATING = auto()         # CCPM creating issues
    ISSUES_VALIDATING = auto()       # Validator checking issues
    ISSUES_NEED_REVIEW = auto()      # Validation done, needs greenlight
    READY_TO_IMPLEMENT = auto()      # Greenlit, ready to work

    # Implementation
    IMPLEMENTING = auto()            # Work in progress

    # Completion
    COMPLETE = auto()                # All issues done

    # Error states
    BLOCKED = auto()                 # Needs human intervention
```

### 3.2 Task Stages

```python
class TaskStage(Enum):
    # Pre-implementation
    BACKLOG = auto()                 # Created but not ready
    NEEDS_REVISION = auto()          # Failed validation
    READY = auto()                   # Ready to be picked up

    # Implementation
    IN_PROGRESS = auto()             # Currently being worked on
    INTERRUPTED = auto()             # Session interrupted

    # Verification
    VERIFYING = auto()               # Tests running

    # Completion
    DONE = auto()                    # Complete and verified
    BLOCKED = auto()                 # Needs human help
```

---

## 4. Agents

### 4.1 Agent Overview

| Agent | When It Runs | What It Does | LLM |
|-------|--------------|--------------|-----|
| **SpecAuthorAgent** | SPEC_IN_PROGRESS | Writes engineering spec from PRD | Claude CLI |
| **SpecCriticAgent** | SPEC_IN_PROGRESS | Reviews spec, scores rubric, finds issues | **Codex CLI** |
| **SpecModeratorAgent** | SPEC_IN_PROGRESS | Applies critic feedback, finalizes spec | Claude CLI |
| **IssueValidatorAgent** | ISSUES_VALIDATING | Validates issues are implementable | **Codex CLI** |
| **PrioritizationAgent** | READY_TO_IMPLEMENT | Determines issue order based on deps/value | Claude CLI |
| **TestWriterAgent** | IN_PROGRESS | Writes failing tests for issue | Claude CLI |
| **CoderAgent** | IN_PROGRESS | Implements code to pass tests | Claude CLI |
| **VerifierAgent** | VERIFYING | Runs tests, checks for regressions | Claude CLI |
| **RecoveryAgent** | On errors | Handles failures, generates recovery plans | Claude CLI |

### 4.2 LLM Client Architecture

```python
# ClaudeCliRunner - For creative/implementation tasks
# Uses: claude -p "prompt" --output-format json
class ClaudeCliRunner:
    """Runs Claude Code CLI in headless mode (uses Max subscription)."""
    def run(self, prompt: str, ...) -> ClaudeResult

# CodexCliRunner - For review/critique tasks
# Uses: codex exec "prompt" --json
class CodexCliRunner:
    """Runs OpenAI Codex CLI in exec mode (uses ChatGPT subscription)."""
    def run(self, prompt: str, ...) -> CodexResult
```

**Multi-LLM Pattern:**
- **Creating content** (specs, issues, code) → Claude CLI
- **Reviewing content** (critique, validation) → Codex CLI

### 4.3 Prioritization Agent

The **PrioritizationAgent** determines which issue to work on next:

```python
class PrioritizationAgent:
    """
    Determines issue priority based on:
    1. Dependencies (blocked issues can't be picked)
    2. Business value (from spec/PRD annotations)
    3. Technical risk (complex issues may need human attention)
    4. Size (prefer smaller issues to complete faster)
    """

    def get_next_issue(self, state: RunState) -> TaskRef:
        ready_issues = [t for t in state.tasks if t.stage == TaskStage.READY]

        # Filter out blocked by dependencies
        unblocked = self.filter_unblocked(ready_issues, state)

        # Score and sort
        scored = [(issue, self.score(issue)) for issue in unblocked]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0] if scored else None

    def score(self, issue: TaskRef) -> float:
        """
        Higher score = higher priority
        """
        score = 0.0

        # Dependencies satisfied = +1.0
        if issue.dependencies_met:
            score += 1.0

        # Smaller issues preferred = +0.5 for small, +0.25 for medium
        if issue.estimated_size == 'small':
            score += 0.5
        elif issue.estimated_size == 'medium':
            score += 0.25

        # Higher business value = +0.0 to +1.0
        score += issue.business_value_score

        # Lower technical risk preferred = +0.0 to +0.5
        score += (1.0 - issue.technical_risk_score) * 0.5

        return score
```

---

## 5. Spec Generation & Debate

### 5.1 The Process

```
PRD → SpecAuthor → SpecCritic → SpecModerator → [repeat if needed] → Final Spec
```

### 5.2 Stopping Conditions

```yaml
spec_debate:
    max_rounds: 5
    rubric_thresholds:
        clarity: 0.8
        coverage: 0.8
        architecture: 0.8
        risk: 0.7
    convergence_delta: 0.05
    max_critical_issues: 0
    max_moderate_issues: 3
```

**Stop when:**
1. All rubric scores >= thresholds AND <3 moderate issues AND 0 critical → SUCCESS
2. Score improvement < 0.05 across all dimensions → STALEMATE (needs human)
3. max_rounds reached → TIMEOUT (needs human)

### 5.3 Output Files

```
specs/<feature>/
    spec-draft.md           # Working draft (updated each round)
    spec-final.md           # Final approved spec
    spec-review.json        # Critic's analysis
    spec-rubric.json        # Final scores
```

---

## 6. Issue Validation (Greenlight)

### 6.1 Why This Exists

Before spending tokens on implementation, verify issues are:
- Clear enough to implement
- Right-sized (one session of work)
- Have testable acceptance criteria
- Dependencies correctly identified

### 6.2 Validation Criteria

Each issue is scored 0-1 on:

| Criterion | What It Checks |
|-----------|----------------|
| `clarity` | Is the issue description unambiguous? |
| `acceptance_criteria` | Are there clear, testable criteria? |
| `right_sized` | Can this be done in one session (~30 min)? |
| `dependencies` | Are blockers correctly identified? |
| `test_strategy` | Is it clear how to test this? |

**Greenlight threshold:** All criteria >= 0.7

### 6.3 Validation Output

```json
{
    "validated_at": "2025-11-25T10:30:00Z",
    "greenlight": true,
    "issues": [
        {
            "number": 42,
            "scores": {
                "clarity": 0.9,
                "acceptance_criteria": 0.85,
                "right_sized": 0.8,
                "dependencies": 1.0,
                "test_strategy": 0.9
            },
            "status": "VALID"
        }
    ]
}
```

---

## 7. Session Management

### 7.1 One Issue Per Session

**Core rule:** Each `feature-swarm` invocation works on exactly ONE issue.

Why:
- Atomic commits (one issue = one logical unit)
- Clean rollback (if it fails, only one issue affected)
- Context management (LLM doesn't bloat)
- Clear progress (done vs not done)

### 7.2 Session Lifecycle

```
START → Claim Issue → Write Tests → Implement → Verify → END
                ↓           ↓            ↓         ↓
            [interrupt] [interrupt]  [interrupt] [fail]
                ↓           ↓            ↓         ↓
            INTERRUPTED  INTERRUPTED  INTERRUPTED BLOCKED
```

### 7.3 Session State

`.swarm/sessions/<feature>/<session-id>.json`:

```json
{
    "session_id": "sess_20251125_103000",
    "feature_id": "user-auth-jwt",
    "issue_number": 43,
    "started_at": "2025-11-25T10:30:00Z",
    "status": "complete",

    "checkpoints": [
        {"agent": "test_writer", "status": "complete", "commit": "a1b2c3d"},
        {"agent": "coder", "status": "complete", "commit": "e4f5g6h"},
        {"agent": "verifier", "status": "complete"}
    ],

    "ended_at": "2025-11-25T10:42:00Z",
    "end_status": "success"
}
```

### 7.4 Multi-Session Workflow

```bash
# Day 1
$ feature-swarm user-auth-jwt    # Works on issue #42, completes
$ feature-swarm user-auth-jwt    # Works on issue #43, interrupted

# Day 2
$ feature-swarm user-auth-jwt    # Detects interrupted #43, offers recovery
# Choose: Resume
# Completes #43

$ feature-swarm user-auth-jwt    # Works on issue #44, completes

# Day 3
$ feature-swarm user-auth-jwt    # Works on issue #45...
```

---

## 8. Edge Case Handling

### 8.1 What the Orchestrator Handles Automatically

| Situation | Automatic Response |
|-----------|-------------------|
| Network timeout | Retry 3x with backoff |
| GitHub rate limit | Wait for reset if <5min, else checkpoint and exit |
| Context exhausted | Checkpoint, WIP commit, exit gracefully |
| Simple test failure | Retry implementation up to 3x |
| State inconsistency | Reconcile from git history |
| Stale session lock | Claim after 30 min inactive |

### 8.2 What Requires Human Intervention

| Situation | What Happens |
|-----------|--------------|
| Spec approval | Pauses, asks for approval |
| Issue greenlight | Pauses, asks for greenlight |
| 3+ implementation failures | Marks issue BLOCKED, moves on |
| Complex git conflicts | Exits with instructions |
| Issue too large | Recommends split, asks for confirmation |

### 8.3 Recovery Command

When things go wrong, the smart CLI handles it:

```bash
$ feature-swarm user-auth-jwt

⚠️  Found issues requiring attention:

1. Issue #43 - Interrupted Session
   Last checkpoint: coder (in progress)
   Uncommitted changes: YES

   [R] Resume from checkpoint
   [B] Rollback and restart
   [S] Skip (mark blocked)

2. Issue #45 - Tests Failing
   Was marked DONE but tests now fail

   [F] Fix (reopen and retry)
   [I] Ignore (keep as done)

Choice: _
```

---

## 9. Directory Structure

```
repo-root/
├── .claude/
│   ├── CLAUDE.md                    # Project instructions
│   ├── settings.json                # Permissions, hooks
│   ├── prds/
│   │   └── <feature>.md             # PRDs (created by CCPM)
│   ├── epics/
│   │   └── <feature>/
│   │       ├── epic.md              # Epic (created by CCPM)
│   │       └── *.md                 # Task files
│   └── skills/                      # Agent skill definitions
│       ├── spec_author/
│       ├── spec_critic/
│       ├── test_writer/
│       ├── coder/
│       └── verifier/
│
├── specs/
│   └── <feature>/
│       ├── spec-draft.md            # Working spec
│       ├── spec-final.md            # Approved spec
│       ├── spec-review.json         # Critic output
│       ├── spec-rubric.json         # Final scores
│       └── issue-validation.json    # Validation results
│
├── .swarm/
│   ├── state/
│   │   └── <feature>.json           # Feature state
│   ├── sessions/
│   │   └── <feature>/
│   │       └── sess_*.json          # Session records
│   └── logs/
│       └── <feature>-*.jsonl        # Event logs
│
└── config.yaml                      # Swarm configuration
```

---

## 10. Configuration

### 10.1 config.yaml

```yaml
# Paths
repo_root: .
specs_dir: specs
swarm_dir: .swarm

# GitHub
github:
    repo: "owner/repo"
    token_env_var: "GITHUB_TOKEN"

# Claude Code CLI (for creating content)
claude:
    binary: "claude"
    max_turns: 6
    # Uses Max subscription - no API key needed
    # Auth: claude login (one-time setup)

# OpenAI Codex CLI (for reviewing content)
codex:
    binary: "codex"
    # Uses ChatGPT subscription - no API key needed
    # Auth: codex (select "Sign in with ChatGPT")
    sandbox_mode: "read-only"  # Default for review tasks

# Spec debate
spec_debate:
    max_rounds: 5
    rubric_thresholds:
        clarity: 0.8
        coverage: 0.8
        architecture: 0.8
        risk: 0.7

# Issue validation
issue_validation:
    min_score: 0.7

# Sessions
sessions:
    stale_timeout_minutes: 30
    max_implementation_retries: 3
```

---

## 11. Future: Cross-Feature Intelligence (COO Agent)

### 11.1 Vision

A higher-level agent that helps prioritize across ALL features:

```bash
$ feature-swarm analyze

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Weekly Analysis (Nov 18-25)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Completed:
  ✓ user-auth-jwt (6/6 issues) - shipped Monday
  ✓ payment-webhooks (4/4 issues) - shipped Wednesday

In Progress:
  → api-rate-limiting (2/5 issues done)
  → dashboard-redesign (0/8 issues - spec approved)

Blocked:
  ⚠ email-templates (issue #67 blocked 3 days - needs DB schema change)

Recommendations:
  1. Unblock email-templates first (blocking 2 downstream features)
  2. Finish api-rate-limiting (only 3 issues left, high business value)
  3. Start dashboard-redesign after (largest feature, needs focus time)

Today's suggested focus:
  → feature-swarm api-rate-limiting (continue, ~1 hour to complete)
```

### 11.2 How It Works (Design)

```python
class COOAgent:
    """
    Cross-feature analysis and prioritization.
    """

    def analyze_portfolio(self) -> PortfolioAnalysis:
        """
        Analyzes all features and generates recommendations.
        """
        features = self.load_all_features()

        return PortfolioAnalysis(
            completed=self.get_completed_features(features),
            in_progress=self.get_in_progress_features(features),
            blocked=self.get_blocked_features(features),

            # Cross-feature analysis
            dependency_graph=self.build_dependency_graph(features),
            blocking_issues=self.find_blocking_issues(features),

            # Recommendations
            unblock_recommendations=self.recommend_unblocks(features),
            priority_order=self.calculate_priority_order(features),
            today_focus=self.recommend_today_focus(features)
        )

    def calculate_priority_order(self, features: list) -> list:
        """
        Prioritizes features based on:
        1. Blocking other features (unblock first)
        2. Business value (from PRD/spec annotations)
        3. Effort remaining (quick wins vs long hauls)
        4. Team availability (if tracked)
        """
        scored = []
        for feature in features:
            score = 0.0

            # How many features does this block?
            blocking_count = len(self.features_blocked_by(feature))
            score += blocking_count * 2.0

            # Business value
            score += feature.business_value * 1.0

            # Effort remaining (prefer near-complete)
            completion_pct = feature.issues_done / feature.issues_total
            score += completion_pct * 0.5

            scored.append((feature, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in scored]
```

### 11.3 Data Model Extension

```python
@dataclass
class FeatureMetadata:
    """
    Extended metadata for cross-feature analysis.
    """
    feature_id: str
    business_value: float          # 0-1, from PRD
    target_date: Optional[str]     # Deadline if any
    blocked_by: list[str]          # Other feature IDs
    blocks: list[str]              # Features this blocks
    tags: list[str]                # e.g., ["q4-priority", "customer-request"]
```

### 11.4 Future CLI

```bash
# Portfolio view
feature-swarm                      # Shows all features, recommends next action

# Analysis
feature-swarm analyze              # Weekly/daily analysis
feature-swarm analyze --weekly     # Past week summary
feature-swarm analyze --plan-week  # Plan upcoming week

# Cross-feature
feature-swarm priority             # Show priority order
feature-swarm blockers             # Show what's blocking what
```

---

## 12. Implementation Prompt for LLM

```
You are building `feature_swarm`, a Python CLI that orchestrates AI-driven feature development.

KEY PRINCIPLE: The CLI is SMART. One command (`feature-swarm`) figures out what to do.

ARCHITECTURE:
- State machine (FeaturePhase) tracks where each feature is
- One issue per session (atomic, recoverable)
- Checkpoints allow resume from any failure
- Human approval required at spec and greenlight stages

MODULES TO IMPLEMENT:

1. cli.py - Smart CLI with Typer
   - Main command that reads state and does the right thing
   - Escape hatches for manual control (--phase, --issue, etc.)

2. state_machine.py - Determines next action
   - Given current phase, returns what to do next
   - Handles interrupted sessions, blocked issues

3. session_manager.py - Manages work sessions
   - One issue per session enforcement
   - Checkpoint creation
   - Recovery from interrupts

4. agents/ - Specialized agents
   - spec_author, spec_critic, spec_moderator
   - issue_validator
   - prioritization (decides issue order)
   - test_writer, coder, verifier
   - recovery (handles edge cases)

5. edge_cases.py - Error handlers
   - Retry logic for transient failures
   - Recovery plans for each failure type
   - Automatic vs human-required decisions

6. models.py - Data structures
   - FeaturePhase, TaskStage enums
   - RunState, SessionState, TaskRef

7. config.py - Configuration loading

USER EXPERIENCE:
- User runs `feature-swarm` or `feature-swarm <feature>`
- System shows current status and what it will do
- Asks for confirmation on expensive operations
- Human checkpoints at: spec approval, issue greenlight
- On errors: clear message, recovery options

EXAMPLE FLOW:
$ feature-swarm user-auth
→ "Feature user-auth is at SPEC_NEEDS_APPROVAL"
→ "Spec ready at specs/user-auth/spec-final.md"
→ "Approve? [Y/n]"
→ y
→ "Creating issues via CCPM..."
→ "Validating 6 issues..."
→ "All issues valid. Greenlight? [Y/n]"
→ y
→ "Starting work on issue #42..."
→ [implements issue]
→ "Issue #42 complete. 1/6 done."
→ "Run again to continue with #43."
```

---

## 13. Integration Testing Strategy

### 13.1 Philosophy: "Make Sure Shit Works"

Integration tests use **real API calls** to external systems. No mocks for the critical paths. The goal is surgical verification that each integration point actually works.

**Why Real APIs?**
- Mocks can't catch API changes, auth issues, or timeout behavior
- Real calls prove the system works end-to-end
- Cost is minimal (~$1 total for full suite)

### 13.2 External Systems Under Test

| System | Used By | What to Verify |
|--------|---------|----------------|
| **Claude CLI** | All LLM agents | Invocation, response parsing, JSON extraction |
| **Codex CLI** | CodexCliRunner | Invocation, response parsing |
| **Git** | SessionManager, Orchestrator | Commit, branch, stash, reset |
| **GitHub API** | Orchestrator | Issue creation, status updates (can mock) |
| **File System** | StateStore, Agents | Read/write state, specs, checkpoints |
| **Test Runner** | VerifierAgent | Run pytest, capture pass/fail |

### 13.3 Test Phases

#### Phase 1: Foundation Smoke Tests

**File:** `tests/integration/test_foundation_smoke.py`

Fastest, most critical tests. If these fail, nothing else works.

| Test | What It Verifies |
|------|------------------|
| `test_claude_cli_responds` | ClaudeCliRunner returns valid ClaudeResult |
| `test_codex_cli_responds` | CodexCliRunner returns valid response |
| `test_state_store_roundtrip` | Save state → load state → identical |
| `test_session_store_roundtrip` | Save session with checkpoints → load → intact |
| `test_git_operations_basic` | Init repo, add file, commit → hash returned |

**Run time:** ~30 seconds

#### Phase 2: Agent Smoke Tests

**File:** `tests/integration/test_agent_smoke.py`

Each agent tested individually with minimal prompts.

| Test | What It Verifies |
|------|------------------|
| `test_spec_author_generates_spec` | Creates spec file from tiny PRD |
| `test_spec_critic_returns_json` | Returns valid JSON with scores |
| `test_prioritization_agent_selects_correctly` | Deterministic selection works |
| `test_test_writer_generates_tests` | Creates valid Python test file |
| `test_coder_generates_implementation` | Creates implementation from tests |
| `test_verifier_runs_tests` | Correctly reports passing tests |
| `test_verifier_detects_failure` | Correctly reports failing tests |
| `test_recovery_agent_analyzes_failure` | Returns recovery plan |

**Run time:** ~2-3 minutes

#### Phase 3: Pipeline Integration Tests

**File:** `tests/integration/test_pipeline_integration.py`

Multi-component flows tested together.

| Test | What It Verifies |
|------|------------------|
| `test_spec_debate_one_round` | Author → Critic → revision improves spec |
| `test_issue_session_happy_path` | Full session: tests → code → verify → commit |
| `test_issue_session_retry_on_failure` | Retry logic triggers and succeeds |
| `test_session_recovery_from_checkpoint` | Resume continues from checkpoint |
| `test_cli_smart_command_executes` | CLI determines correct action |

**Run time:** ~5 minutes

#### Phase 4: End-to-End Critical Path

**File:** `tests/integration/test_e2e_critical.py`

Full system tests. Slow but definitive proof.

| Test | What It Verifies |
|------|------------------|
| `test_full_feature_tiny` | PRD → Spec → Issues → Implementation → Done |
| `test_blocked_issue_recovery` | 3x failure → blocked → recovery instructions |

**Run time:** ~10-15 minutes

### 13.4 Test Markers

```python
@pytest.mark.integration  # All integration tests
@pytest.mark.slow         # Tests > 30 seconds
@pytest.mark.llm          # Requires LLM API key
@pytest.mark.git          # Requires git
@pytest.mark.e2e          # Full end-to-end
```

### 13.5 Running Integration Tests

```bash
# All integration tests
pytest tests/integration/ -v -m integration

# Quick tests only (no LLM calls)
pytest tests/integration/ -v -m "integration and not llm"

# Foundation smoke only
pytest tests/integration/test_foundation_smoke.py -v

# Skip slow tests
pytest tests/integration/ -v -m "integration and not slow"

# Full E2E (slow, costs ~$0.50)
pytest tests/integration/ -v -m e2e
```

### 13.6 Skip Conditions

Tests automatically skip when prerequisites unavailable:

```python
# Skip if no API key
@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)

# Skip if no git
@pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not available"
)

# Skip if no Claude CLI
@pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="Claude CLI not installed"
)
```

### 13.7 Cost Estimate

| Phase | LLM Calls | Est. Cost |
|-------|-----------|-----------|
| Phase 1 | 2 | $0.02 |
| Phase 2 | 8 | $0.15 |
| Phase 3 | 10 | $0.25 |
| Phase 4 | 15+ | $0.50 |
| **Total** | ~35 | **~$1.00** |

### 13.8 Success Criteria

| Phase | Passing Means |
|-------|---------------|
| Phase 1 | Foundation works - can call LLMs, persist state, use git |
| Phase 2 | Agents work individually with real LLMs |
| Phase 3 | Multi-step pipelines work correctly |
| Phase 4 | Entire system works end-to-end |

### 13.9 What's NOT Covered (Intentionally)

- **GitHub API mocking** - External service, mock acceptable
- **Concurrent sessions** - Complex, defer to later
- **Cost tracking accuracy** - Unit tests sufficient
- **CLI output formatting** - Manual testing
- **Performance/load** - Out of scope

---

## 14. Quick Reference

### 14.1 Commands You Need to Know

```bash
feature-swarm                     # Do the next thing (smart mode)
feature-swarm <feature>           # Work on specific feature
feature-swarm status              # See all features
feature-swarm status <feature>    # See one feature in detail
```

### 14.2 Human Checkpoints

1. **PRD Creation** - Interactive with Claude Code
2. **Spec Approval** - Review and approve the engineering spec
3. **Issue Greenlight** - Confirm issues are ready for implementation
4. **Merge** - Review code and merge to main

### 14.3 What Happens Automatically

- Spec debate (author ↔ critic rounds)
- Issue creation via CCPM
- Issue validation
- Test writing, implementation, verification
- Error recovery and retry
- State persistence and resumption

---

## References

- [Claude Code Headless Mode](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
- [Claude Code with Max Subscription](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
- [OpenAI Codex CLI](https://developers.openai.com/codex/cli)
- [Codex exec (headless mode)](https://github.com/openai/codex/blob/main/docs/exec.md)
- [Codex with ChatGPT Plan](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan)
- [CCPM GitHub](https://github.com/automazeio/ccpm)
- [Building Effective Agents - Anthropic](https://www.anthropic.com/research/building-effective-agents)
