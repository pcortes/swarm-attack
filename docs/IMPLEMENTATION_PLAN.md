# Feature Swarm: Implementation Plan

## 1. Spec Summary

### 1.1 Core Concept

Feature Swarm is a Python CLI orchestrator that automates the full software development lifecycle from PRD to shipped code. It uses a state-aware "smart CLI" design where a single command (`feature-swarm`) reads current state and automatically determines the next action. The system coordinates Claude Code CLI for LLM operations, CCPM for project management, and GitHub for issue tracking, while enforcing atomic "one issue per session" work units for clean rollback and context management.

### 1.2 Key Components

| Component | Purpose | Complexity |
|-----------|---------|------------|
| Smart CLI (cli.py) | State-aware command interface that determines next action | High |
| State Machine (state_machine.py) | Tracks feature phases and determines transitions | Medium |
| Session Manager (session_manager.py) | Manages one-issue-per-session workflow with checkpoints | High |
| Orchestrator (orchestrator.py) | Coordinates agent execution and pipeline flow | High |
| Data Models (models.py) | Core data structures (enums, dataclasses) | Low |
| Configuration (config.py) | Load and validate config.yaml | Low |
| State Store (state_store.py) | Persist/load feature state to JSON files | Medium |
| Logger (logger.py) | Structured JSONL event logging | Low |
| LLM Clients (llm_clients.py) | Claude Code CLI subprocess wrapper | Medium |
| Spec Author Agent | Writes engineering spec from PRD | Medium |
| Spec Critic Agent | Reviews spec, scores rubric, finds issues | Medium |
| Spec Moderator Agent | Applies feedback, finalizes spec | Medium |
| Issue Validator Agent | Validates issues are implementable | Medium |
| Prioritization Agent | Determines issue order based on deps/value | Medium |
| Coder Agent (Implementation Agent) | TDD workflow: writes tests + implements code in single context | Medium |
| Verifier Agent | Runs tests, checks for regressions | Medium |
| Recovery Agent | Handles failures, generates recovery plans | High |
| Edge Case Handlers (edge_cases.py) | Retry logic, recovery plans | Medium |
| GitHub Client (github_client.py) | GitHub API interactions | Medium |
| CCPM Adapter (ccpm_adapter.py) | Interface with CCPM CLI | Medium |

### 1.3 Critical Dependencies

**External:**
- Claude Code CLI (`claude` binary) with `--output-format json` headless mode
- CCPM (slash commands via Claude Code headless: `/pm:prd-parse`, `/pm:epic-oneshot`, `/pm:epic-sync`)
- GitHub REST API with PAT (Personal Access Token)
- Python 3.10+
- Git with worktree support

**Internal:**
- models.py → foundation for all modules
- config.py → used by cli, agents, clients
- state_store.py → used by cli, orchestrator, session_manager
- llm_clients.py → used by all agents (parses JSON envelope with cost tracking)

---

## 2. Architecture Decisions

### 2.1 Decisions Made in Spec

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| One issue per session | Atomic rollback, clean context management | Slower throughput (one command per issue) |
| State-aware smart CLI | Single command simplicity, no memorization needed | Complex state machine logic |
| Human checkpoints (spec, greenlight) | Critical decisions need human judgment | Pauses automation flow |
| JSON state files in .swarm/ | Human-readable, git-trackable | Not as fast as SQLite |
| Checkpoint-based recovery | Resume from any failure point | Extra disk writes |
| 30-minute stale session timeout | Auto-recovery from abandoned sessions | May be too aggressive |
| 3 max implementation retries | Balance between persistence and blocking | May waste tokens on unsolvable issues |
| JSONL event logs | Appendable, streamable, structured | Larger file size than binary |
| Spec debate with rubric thresholds | Objective quality gates | May reject good specs on technicality |

### 2.2 Decisions Clarified (Previously Open Questions - NOW RESOLVED)

| Question | Decision | Implementation Impact |
|----------|----------|----------------------|
| **CCPM Integration** | CLI/slash-command only via Claude Code headless. PRD creation is always human/interactive. Post-PRD uses `/pm:prd-parse`, `/pm:epic-oneshot`, `/pm:epic-sync` | ccpm_adapter.py invokes `claude -p "/pm:..." --output-format json` |
| **Claude Code Output** | `--output-format json` everywhere. Parse JSON envelope: `{type, subtype, total_cost_usd, result, session_id, num_turns, duration_ms}` | llm_clients.py extracts `.result` and `.total_cost_usd` from every call |
| **GitHub Auth** | REST API with PAT stored in `GITHUB_TOKEN` env var. CCPM keeps using `gh` internally | github_client.py uses `requests`/`httpx`, not `gh` CLI |
| **Test Framework** | Explicit `tests.command` in config.yaml. Optional `feature-swarm detect-tests` helper | verifier.py reads `config.tests.command`, no magic detection |
| **Multi-repo** | V1 is single-repo only | No cross-repo state, single `github.repo` in config |
| **Cost Tracking** | Yes - track and surface per feature/session/agent | RunState gets `cost_total_usd`, `cost_by_agent` fields; CLI shows costs |
| **Skill Files** | `.claude/skills/<skill-name>/SKILL.md` with Anthropic's official format (YAML frontmatter + markdown) | Each agent = one Skill directory with `SKILL.md` |
| **Git Branches** | One branch per **feature**: `feature/<feature-slug>`. Issues map to commits, not branches. Optional worktree per feature for isolation. | session_manager.py creates feature branch + optional worktree |

### 2.3 Remaining Assumptions (Low Risk)

| Gap | Assumption | Risk if Wrong |
|-----|------------|---------------|
| Concurrent users | Single user only for v1 | Low - can add locking later |
| Python version | 3.10+ (dataclasses, type hints) | Low - reasonable minimum |
| Package manager | Poetry or pip, user's choice | Low - standard patterns |
| Terminal UI | Rich library for beautiful output | Low - easy to change |
| Issue number assignment | GitHub assigns, we track | Low - standard GitHub behavior |

---

## 3. Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DEPENDENCY GRAPH                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  models.py ──────────────────────────────────────────────────────────────┐  │
│      │                                                                   │  │
│      ▼                                                                   │  │
│  config.py ────────► state_store.py ────────► logger.py                  │  │
│      │                     │                      │                      │  │
│      │                     │                      │                      │  │
│      ▼                     ▼                      ▼                      │  │
│  github_client.py    ccpm_adapter.py        llm_clients.py               │  │
│      │                     │                      │                      │  │
│      └─────────────────────┼──────────────────────┘                      │  │
│                            │                                             │  │
│                            ▼                                             │  │
│                      agent_base.py                                       │  │
│                            │                                             │  │
│      ┌──────────┬──────────┼──────────┬──────────┬──────────┐            │  │
│      ▼          ▼          ▼          ▼          ▼          ▼            │  │
│  spec_      spec_      spec_      issue_    prioriti-   recovery_        │  │
│  author     critic     moderator  validator  zation      agent           │  │
│      │          │          │          │          │          │            │  │
│      └──────────┴──────────┴──────────┴──────────┴──────────┘            │  │
│                            │                                             │  │
│                            ▼                                             │  │
│             ┌──────────────┼──────────────┐                              │  │
│             ▼              ▼              ▼                              │  │
│        coder (TDD)     verifier    edge_cases.py                         │  │
│             │              │              │                              │  │
│             └──────────────┴──────────────┘                              │  │
│                            │                                             │  │
│                            ▼                                             │  │
│                    session_manager.py                                    │  │
│                            │                                             │  │
│                            ▼                                             │  │
│                    orchestrator.py                                       │  │
│                            │                                             │  │
│                            ▼                                             │  │
│                    state_machine.py                                      │  │
│                            │                                             │  │
│                            ▼                                             │  │
│                        cli.py                                            │  │
│                                                                          │  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Issues Breakdown

### Milestone 1: Foundation
*Goal: Basic infrastructure that everything else depends on*

#### Issue 1: Core Data Models

```yaml
title: "Implement core data models (models.py)"
priority: P0
size: small (1-2 hours)
dependencies: none

description: |
  Create the foundational data structures for the entire system.
  These models define the vocabulary used across all modules.

files:
  - feature_swarm/models.py

acceptance_criteria:
  - [ ] FeaturePhase enum with all 12 states (NO_PRD through BLOCKED)
  - [ ] TaskStage enum with all 8 states (BACKLOG through BLOCKED)
  - [ ] RunState dataclass with fields: feature_id, phase, tasks, current_session, created_at, updated_at, cost_total_usd, cost_by_phase (dict[str, float])
  - [ ] TaskRef dataclass with fields: issue_number, stage, title, dependencies, estimated_size, business_value_score, technical_risk_score
  - [ ] SessionState dataclass with fields: session_id, feature_id, issue_number, started_at, status, checkpoints, ended_at, end_status, cost_usd, worktree_path, commits (list[str] - hashes created this session)
  - [ ] CheckpointData dataclass with fields: agent, status, commit, timestamp, cost_usd
  - [ ] ClaudeResult dataclass with fields: text, total_cost_usd, num_turns, duration_ms, session_id, raw (full JSON)
  - [ ] All models are JSON-serializable (via dataclasses_json or custom encoder)
  - [ ] Unit tests for serialization round-trip

spec_reference: "Section 3.1, 3.2, 7.3"

integration_points:
  - Used by: state_store, cli, all agents, session_manager
  - Uses: nothing (leaf node)

test_strategy: |
  - Unit tests for enum values exist and have expected names
  - Unit tests for dataclass defaults
  - Test JSON serialization/deserialization round-trip
  - Test with edge cases (empty lists, None values)
```

#### Issue 2: Configuration Loading

```yaml
title: "Implement configuration loading (config.py)"
priority: P0
size: small (1-2 hours)
dependencies: [1]

description: |
  Load and validate config.yaml, resolve environment variables,
  provide SwarmConfig dataclass with typed fields.

  IMPORTANT: Test framework is explicit in config, not auto-detected.
  Git branch pattern and worktree settings are configured here.

files:
  - feature_swarm/config.py
  - config.yaml.example

acceptance_criteria:
  - [ ] Load config.yaml from repo root (or specified path)
  - [ ] Resolve environment variables (${GITHUB_TOKEN}, etc.)
  - [ ] SwarmConfig dataclass with typed fields matching spec section 10.1
  - [ ] Nested config classes:
    - GitHubConfig: repo, token_env_var
    - ClaudeConfig: binary, max_turns, timeout_seconds
    - SpecDebateConfig: max_rounds, rubric_thresholds
    - SessionConfig: stale_timeout_minutes, max_implementation_retries
    - TestsConfig: command (required), args (list), autodetect (bool, default false)
    - GitConfig: base_branch, feature_branch_pattern, use_worktrees, worktrees_root
  - [ ] Validation errors for missing required fields (github.repo, tests.command)
  - [ ] Default values: max_rounds=5, stale_timeout_minutes=30, feature_branch_pattern="feature/{feature_slug}"
  - [ ] get_config() function that loads and caches config
  - [ ] Unit tests

spec_reference: "Section 10.1"

integration_points:
  - Used by: cli, github_client, llm_clients, ccpm_adapter, agents, session_manager
  - Uses: models.py (for config-related types if any)

test_strategy: |
  - Test loading valid config file
  - Test missing required fields raises ConfigError (github.repo, tests.command)
  - Test env var resolution (${VAR} syntax)
  - Test default values applied correctly
  - Test git config defaults (base_branch="main", feature_branch_pattern="feature/{feature_slug}")
  - Test invalid YAML raises clear error

example_config: |
  # config.yaml
  repo_root: .
  specs_dir: specs
  swarm_dir: .swarm

  github:
    repo: "owner/repo"
    token_env_var: "GITHUB_TOKEN"

  claude:
    binary: "claude"
    max_turns: 6
    timeout_seconds: 300

  tests:
    command: "pytest"
    args: ["-q", "--tb=short"]
    autodetect: false

  git:
    base_branch: "main"
    feature_branch_pattern: "feature/{feature_slug}"  # One branch per feature, not per issue
    use_worktrees: true                                # Optional worktree per feature
    worktrees_root: ".swarm/worktrees"

  spec_debate:
    max_rounds: 5
    rubric_thresholds:
      clarity: 0.8
      coverage: 0.8
      architecture: 0.8
      risk: 0.7

  sessions:
    stale_timeout_minutes: 30
    max_implementation_retries: 3
```

#### Issue 3: Structured Logging

```yaml
title: "Implement structured logging (logger.py)"
priority: P0
size: small (1-2 hours)
dependencies: [2]

description: |
  Create JSONL event logging for debugging and audit trail.
  Logs go to .swarm/logs/<feature>-<date>.jsonl

files:
  - feature_swarm/logger.py

acceptance_criteria:
  - [ ] SwarmLogger class with log(event_type, data) method
  - [ ] Writes to .swarm/logs/<feature>-YYYY-MM-DD.jsonl
  - [ ] Each line is valid JSON with timestamp, event_type, data
  - [ ] Log levels: debug, info, warn, error
  - [ ] Context manager for session-scoped logging
  - [ ] get_logger(feature_id) factory function
  - [ ] Unit tests

spec_reference: "Section 9 (directory structure)"

integration_points:
  - Used by: ALL modules for logging
  - Uses: config.py (for swarm_dir path)

test_strategy: |
  - Test log file creation
  - Test JSONL format is valid
  - Test multiple logs append correctly
  - Test log rotation (new file per day)
```

#### Issue 4: State Store

```yaml
title: "Implement state persistence (state_store.py)"
priority: P0
size: medium (2-3 hours)
dependencies: [1, 2, 3]

description: |
  Persist and load feature state to JSON files in .swarm/state/.
  Handle corruption gracefully and provide CRUD operations.

files:
  - feature_swarm/state_store.py

acceptance_criteria:
  - [ ] StateStore class with load(feature_id), save(state), list_features() methods
  - [ ] State saved to .swarm/state/<feature>.json
  - [ ] Atomic writes (write to temp, then rename)
  - [ ] Handle missing state file (return None or default)
  - [ ] Handle corrupted JSON (log error, return None, offer recovery)
  - [ ] create_feature(feature_id) initializes new feature state
  - [ ] update_phase(feature_id, new_phase) convenience method
  - [ ] Unit tests including corruption handling

spec_reference: "Section 9 (directory structure), Section 7.3"

integration_points:
  - Used by: cli, orchestrator, session_manager
  - Uses: models.py (RunState), config.py (paths), logger.py

test_strategy: |
  - Test save/load round-trip
  - Test atomic write (no partial files)
  - Test corrupted file handling
  - Test list_features returns correct list
  - Test create_feature initializes correctly
```

#### Issue 5: File System Utilities

```yaml
title: "Implement file system utilities (utils/fs.py)"
priority: P0
size: small (1 hour)
dependencies: [2]

description: |
  Common file system operations used throughout the system.
  Safe directory creation, path resolution, file existence checks.

files:
  - feature_swarm/utils/__init__.py
  - feature_swarm/utils/fs.py

acceptance_criteria:
  - [ ] ensure_dir(path) - create directory if not exists
  - [ ] safe_write(path, content) - atomic write with temp file
  - [ ] resolve_repo_path(relative) - resolve relative to repo root
  - [ ] file_exists(path) - check file existence
  - [ ] read_file(path) - read with encoding handling
  - [ ] list_files(dir, pattern) - glob pattern matching
  - [ ] Unit tests

spec_reference: "Section 9 (directory structure)"

integration_points:
  - Used by: state_store, logger, spec agents
  - Uses: config.py (repo_root)

test_strategy: |
  - Test ensure_dir creates nested directories
  - Test safe_write is atomic
  - Test path resolution
```

#### Issue 6: Claude Code CLI Wrapper

```yaml
title: "Implement Claude Code CLI wrapper (llm_clients.py)"
priority: P0
size: medium (2-3 hours)
dependencies: [2, 3]

description: |
  Wrapper for invoking Claude Code CLI in headless mode with --output-format json.
  Parse the JSON envelope to extract result and cost tracking data.

  CRITICAL: All Claude calls use --output-format json and parse the envelope:
  {
    "type": "result",
    "subtype": "success",
    "total_cost_usd": 0.003,
    "is_error": false,
    "duration_ms": 1234,
    "duration_api_ms": 800,
    "num_turns": 6,
    "result": "The response text here...",
    "session_id": "abc123"
  }

files:
  - feature_swarm/llm_clients.py

acceptance_criteria:
  - [ ] ClaudeCliRunner class with run(prompt, **kwargs) → ClaudeResult method
  - [ ] ALWAYS use --output-format json (not --print-last-response)
  - [ ] Support --max-turns configuration from config
  - [ ] Support --allowedTools for restricting tool access per agent
  - [ ] Parse JSON envelope and extract:
    - result (primary response text)
    - total_cost_usd (for cost tracking)
    - num_turns, duration_ms, session_id (for logging)
  - [ ] Return ClaudeResult dataclass with all fields
  - [ ] Timeout handling with graceful termination (SIGTERM then SIGKILL)
  - [ ] On non-zero exit: raise ClaudeInvocationError with stderr
  - [ ] Log every invocation with cost to JSONL
  - [ ] Unit tests with mocked subprocess

spec_reference: "Section 10.1 (claude config), References (Headless Mode)"

integration_points:
  - Used by: ALL agents, ccpm_adapter
  - Uses: config.py (claude binary, max_turns, timeout), logger.py, models.py (ClaudeResult)

test_strategy: |
  - Test successful invocation returns ClaudeResult with all fields
  - Test cost is extracted from envelope
  - Test timeout handling with graceful shutdown
  - Test JSON parse errors raise clear exception
  - Test non-zero exit raises ClaudeInvocationError
  - Test stderr is captured for debugging

implementation_example: |
  def run_claude(prompt: str, *, max_turns: int | None = None,
                 allowed_tools: list[str] | None = None) -> ClaudeResult:
      turns = max_turns or config.claude.max_turns

      cmd = [
          config.claude.binary,
          "-p", prompt,
          "--output-format", "json",
          "--max-turns", str(turns),
      ]
      if allowed_tools:
          cmd.extend(["--allowedTools", ",".join(allowed_tools)])

      proc = subprocess.run(
          cmd, capture_output=True, text=True,
          cwd=config.repo_root,
          timeout=config.claude.timeout_seconds,
      )

      if proc.returncode != 0:
          raise ClaudeInvocationError(proc.stderr.strip() or "Claude CLI failed")

      data = json.loads(proc.stdout)
      return ClaudeResult(
          text=data.get("result", ""),
          total_cost_usd=data.get("total_cost_usd", 0.0),
          num_turns=data.get("num_turns"),
          duration_ms=data.get("duration_ms"),
          session_id=data.get("session_id"),
          raw=data,
      )
```

#### Issue 7: CLI Skeleton with Status Command

```yaml
title: "Implement CLI skeleton with status command (cli.py)"
priority: P0
size: medium (2-3 hours)
dependencies: [1, 2, 3, 4]

description: |
  Create the Typer CLI skeleton with the status command.
  This establishes the CLI structure that other features build on.

files:
  - feature_swarm/cli.py
  - feature_swarm/__init__.py
  - feature_swarm/__main__.py
  - pyproject.toml (CLI entry point)

acceptance_criteria:
  - [ ] Typer app with `feature-swarm` as main command
  - [ ] `feature-swarm status` shows all features dashboard
  - [ ] `feature-swarm status <feature>` shows detailed status
  - [ ] Beautiful terminal output with Rich library
  - [ ] --version flag
  - [ ] --help auto-generated
  - [ ] Handle missing .swarm/ directory gracefully (init it)
  - [ ] Unit/integration tests

spec_reference: "Section 2.1, 2.4, 13"

integration_points:
  - Used by: user (entry point)
  - Uses: state_store, config, logger

test_strategy: |
  - Test status with no features
  - Test status with multiple features in various phases
  - Test detailed status shows all fields
  - Test CLI help output
```

---

### Milestone 2: Spec Pipeline
*Goal: Generate engineering specs from PRDs through debate*

#### Issue 8: Agent Base Class

```yaml
title: "Implement agent base class (agents/base.py)"
priority: P1
size: small (1-2 hours)
dependencies: [6, 4]

description: |
  Create the base class that all agents inherit from.
  Provides common functionality: logging, state access, LLM invocation.

files:
  - feature_swarm/agents/__init__.py
  - feature_swarm/agents/base.py

acceptance_criteria:
  - [ ] BaseAgent abstract class with run(context) method
  - [ ] Access to logger, state_store, llm_client via constructor
  - [ ] load_skill(skill_name) method to read skill prompts
  - [ ] checkpoint() method to save progress
  - [ ] Common error handling with retry decorator
  - [ ] Agent result dataclass (success, output, errors)
  - [ ] Unit tests

spec_reference: "Section 4.1"

integration_points:
  - Used by: ALL agent implementations
  - Uses: llm_clients, state_store, logger, config

test_strategy: |
  - Test abstract methods enforced
  - Test skill loading from .claude/skills/
  - Test checkpoint creates valid checkpoint data
```

#### Issue 9: Spec Author Agent

```yaml
title: "Implement Spec Author agent (agents/spec_author.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8]

description: |
  Agent that reads PRD and generates initial engineering spec draft.
  Outputs to specs/<feature>/spec-draft.md

files:
  - feature_swarm/agents/spec_author.py
  - .claude/skills/spec_author/prompt.md (skill prompt)

acceptance_criteria:
  - [ ] SpecAuthorAgent extends BaseAgent
  - [ ] read PRD from .claude/prds/<feature>.md
  - [ ] Invoke Claude with spec author skill prompt
  - [ ] Write output to specs/<feature>/spec-draft.md
  - [ ] Return structured result with success/failure
  - [ ] Handle missing PRD gracefully
  - [ ] Unit tests with mocked LLM

spec_reference: "Section 4.1, 5.1"

integration_points:
  - Used by: orchestrator (spec pipeline)
  - Uses: agent_base, llm_clients

test_strategy: |
  - Test with valid PRD produces spec
  - Test missing PRD returns error
  - Test output file created in correct location
```

#### Issue 10: Spec Critic Agent

```yaml
title: "Implement Spec Critic agent (agents/spec_critic.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8]

description: |
  Agent that reviews spec draft, scores rubric, identifies issues.
  Outputs to specs/<feature>/spec-review.json

files:
  - feature_swarm/agents/spec_critic.py
  - .claude/skills/spec_critic/prompt.md (skill prompt)

acceptance_criteria:
  - [ ] SpecCriticAgent extends BaseAgent
  - [ ] Read spec-draft.md and PRD for review
  - [ ] Score rubric dimensions: clarity, coverage, architecture, risk (0-1)
  - [ ] Identify issues as critical, moderate, or minor
  - [ ] Write output to specs/<feature>/spec-review.json
  - [ ] Return structured review result
  - [ ] Unit tests with mocked LLM

spec_reference: "Section 4.1, 5.2"

integration_points:
  - Used by: orchestrator (spec pipeline)
  - Uses: agent_base, llm_clients

test_strategy: |
  - Test produces valid rubric scores
  - Test identifies issues correctly
  - Test JSON output is valid
```

#### Issue 11: Spec Moderator Agent

```yaml
title: "Implement Spec Moderator agent (agents/spec_moderator.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8]

description: |
  Agent that applies critic feedback to improve spec.
  Updates spec-draft.md and produces spec-rubric.json

files:
  - feature_swarm/agents/spec_moderator.py
  - .claude/skills/spec_moderator/prompt.md (skill prompt)

acceptance_criteria:
  - [ ] SpecModeratorAgent extends BaseAgent
  - [ ] Read spec-draft.md and spec-review.json
  - [ ] Apply feedback to improve spec
  - [ ] Write updated spec-draft.md
  - [ ] Write final rubric to spec-rubric.json
  - [ ] Determine if another round needed
  - [ ] Unit tests with mocked LLM

spec_reference: "Section 4.1, 5.1"

integration_points:
  - Used by: orchestrator (spec pipeline)
  - Uses: agent_base, llm_clients

test_strategy: |
  - Test applies feedback correctly
  - Test rubric updated after moderation
  - Test round determination logic
```

#### Issue 12: Spec Debate Orchestration

```yaml
title: "Implement spec debate orchestration (orchestrator.py - spec pipeline)"
priority: P1
size: medium (3-4 hours)
dependencies: [9, 10, 11]

description: |
  Orchestrate the spec debate loop: author → critic → moderator → repeat.
  Implement stopping conditions from spec.

files:
  - feature_swarm/orchestrator.py (partial - spec methods)

acceptance_criteria:
  - [ ] run_spec_pipeline(feature_id) method
  - [ ] Loop: SpecAuthor → SpecCritic → SpecModerator
  - [ ] Check stopping conditions after each round:
    - All rubric scores >= thresholds AND <3 moderate AND 0 critical → SUCCESS
    - Score improvement < 0.05 → STALEMATE
    - max_rounds reached → TIMEOUT
  - [ ] Update feature phase as pipeline progresses
  - [ ] Log each round's scores
  - [ ] Return pipeline result (success/stalemate/timeout)
  - [ ] Integration tests

spec_reference: "Section 5.2"

integration_points:
  - Used by: cli (when phase is PRD_READY or SPEC_IN_PROGRESS)
  - Uses: spec agents, state_store, logger, config (thresholds)

test_strategy: |
  - Test successful convergence in <5 rounds
  - Test stalemate detection
  - Test timeout after max_rounds
  - Test state transitions correct
```

#### Issue 13: CLI Spec Approval Flow

```yaml
title: "Implement spec approval flow in CLI"
priority: P1
size: small (2 hours)
dependencies: [7, 12]

description: |
  When phase is SPEC_NEEDS_APPROVAL, prompt user to review and approve.
  Update phase to SPEC_APPROVED on approval.

files:
  - feature_swarm/cli.py (update)

acceptance_criteria:
  - [ ] Detect SPEC_NEEDS_APPROVAL phase
  - [ ] Display spec location and summary
  - [ ] Prompt: "Review spec at X. Approve? [Y/n]"
  - [ ] On approval: update phase to SPEC_APPROVED
  - [ ] On rejection: offer to re-run debate or exit
  - [ ] Copy spec-draft.md to spec-final.md on approval
  - [ ] Unit tests

spec_reference: "Section 2.2, 2.3"

integration_points:
  - Used by: user (via CLI)
  - Uses: state_store, orchestrator

test_strategy: |
  - Test approval updates phase
  - Test rejection offers options
  - Test spec-final.md created
```

---

### Milestone 3: Issue Management
*Goal: Create and validate issues via CCPM*

#### Issue 14: GitHub Client

```yaml
title: "Implement GitHub REST API client (github_client.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [2, 3]

description: |
  Client for GitHub REST API operations using PAT (Personal Access Token).

  IMPORTANT: Feature Swarm uses REST API directly, NOT gh CLI.
  CCPM continues to use gh internally - we treat it as a black box.

  Token is read from environment variable specified in config (default: GITHUB_TOKEN).

files:
  - feature_swarm/github_client.py

acceptance_criteria:
  - [ ] GitHubClient class initialized from config (repo, token from env var)
  - [ ] Uses requests or httpx for HTTP calls
  - [ ] Base URL: https://api.github.com
  - [ ] Auth header: "Authorization: Bearer {token}"
  - [ ] Issue operations:
    - create_issue(title, body, labels) → issue_number
    - update_issue(number, body=None, state=None, labels=None)
    - get_issue(number) → GitHubIssue dataclass
    - list_issues(labels=None, state=None) → list[GitHubIssue]
    - add_comment(number, body)
    - close_issue(number) - convenience method
  - [ ] PR operations (for future):
    - create_pr(title, head, base, body) → pr_number
  - [ ] Rate limit handling:
    - Check X-RateLimit-Remaining header
    - If <10 remaining, wait for X-RateLimit-Reset
    - Exponential backoff on 429 responses
  - [ ] Error handling:
    - 401: raise AuthenticationError
    - 404: raise NotFoundError
    - 422: raise ValidationError (with details)
  - [ ] Unit tests with mocked responses

spec_reference: "Section 10.1 (github config)"

integration_points:
  - Used by: issue_validator, session_manager, orchestrator
  - Uses: config.py (github.repo, github.token_env_var), logger.py

test_strategy: |
  - Test CRUD operations with mocked responses
  - Test rate limit detection and backoff
  - Test 401 raises AuthenticationError
  - Test 404 raises NotFoundError
  - Test 429 triggers retry with backoff
  - Test token loaded from correct env var

implementation_note: |
  # Protocol for future extensibility
  class GitHubProvider(Protocol):
      def get_issue(self, number: int) -> GitHubIssue: ...
      def list_issues(self, query: str) -> list[GitHubIssue]: ...
      def update_issue(self, number: int, **fields) -> None: ...
      def create_pr(self, *, title: str, head: str, base: str, body: str) -> int: ...

  # Could later add GhCliProvider if needed, but REST is default
```

#### Issue 15: CCPM Adapter

```yaml
title: "Implement CCPM adapter via Claude Code headless (ccpm_adapter.py)"
priority: P1
size: medium (3-4 hours)
dependencies: [2, 3, 6, 14]

description: |
  Adapter to invoke CCPM slash commands via Claude Code headless mode.

  CRITICAL DESIGN DECISION:
  - CCPM is CLI/slash-command only - no Python API
  - PRD creation is ALWAYS human/interactive (never automated)
  - Post-PRD operations use headless Claude with /pm:* commands

  Integration pattern:
    claude -p "/pm:epic-oneshot ${FEATURE_SLUG}" \
      --output-format json \
      --allowedTools "Bash,Read,Github" \
      --max-turns 6

  Feature Swarm parses the JSON envelope, then reads files CCPM generated
  from .claude/epics/<feature>/ or parses created GH issue numbers.

files:
  - feature_swarm/ccpm_adapter.py

acceptance_criteria:
  - [ ] CCPMAdapter class using ClaudeCliRunner internally
  - [ ] PRD operations (human-only, adapter just checks existence):
    - check_prd_exists(feature_id) → bool
    - get_prd_path(feature_id) → Path (.claude/prds/<feature>.md)
  - [ ] Epic operations (headless):
    - parse_prd(feature_id) - invoke /pm:prd-parse <prd-file>
    - create_epic(feature_id) - invoke /pm:epic-oneshot <feature>
    - sync_epic(feature_id) - invoke /pm:epic-sync
  - [ ] Issue discovery:
    - get_created_issues(feature_id) → list[int] - parse from epic files or GH
    - Uses file polling with wait_for_file() for CCPM-generated files
  - [ ] File polling:
    - wait_for_file(path, timeout, stability_seconds) - wait for file to exist and stabilize
  - [ ] Cost tracking: aggregate costs from all Claude calls
  - [ ] Error handling:
    - CCPMCommandError for slash command failures
    - CCPMTimeoutError for file polling timeout
  - [ ] Unit tests with mocked ClaudeCliRunner

spec_reference: "Section 1, References (CCPM)"

integration_points:
  - Used by: orchestrator (issue creation)
  - Uses: llm_clients.py (ClaudeCliRunner), config.py, logger.py, github_client.py

test_strategy: |
  - Test /pm:prd-parse invocation (mocked Claude)
  - Test /pm:epic-oneshot invocation (mocked Claude)
  - Test file polling with timeout
  - Test issue number extraction from epic files
  - Test cost aggregation across multiple calls

ccpm_commands: |
  # Commands we invoke via headless Claude:
  /pm:prd-parse <prd-file>      # Parse PRD, prepare for epic creation
  /pm:epic-oneshot <feature>    # Create epic and issues in one shot
  /pm:epic-sync                 # Sync epic to GitHub issues

  # Commands that remain human/interactive (NOT automated):
  /pm:prd-new <feature>         # Create new PRD (requires human input)
```

#### Issue 16: Issue Validator Agent

```yaml
title: "Implement Issue Validator agent (agents/issue_validator.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8, 14]

description: |
  Agent that validates issues are implementable.
  Scores clarity, acceptance criteria, size, dependencies, test strategy.

files:
  - feature_swarm/agents/issue_validator.py
  - .claude/skills/issue_validator/prompt.md

acceptance_criteria:
  - [ ] IssueValidatorAgent extends BaseAgent
  - [ ] Fetch issues from GitHub
  - [ ] Score each issue on 5 criteria (0-1 each)
  - [ ] Determine greenlight status (all >= 0.7)
  - [ ] Write results to specs/<feature>/issue-validation.json
  - [ ] Return validation summary
  - [ ] Unit tests with mocked LLM and GitHub

spec_reference: "Section 6.1, 6.2, 6.3"

integration_points:
  - Used by: orchestrator (issue validation)
  - Uses: agent_base, github_client, llm_clients

test_strategy: |
  - Test valid issues pass
  - Test invalid issues fail with reasons
  - Test JSON output format
```

#### Issue 17: Issue Creation Orchestration

```yaml
title: "Implement issue creation orchestration"
priority: P1
size: medium (2-3 hours)
dependencies: [15, 16]

description: |
  Orchestrate: CCPM creates issues → validator validates → greenlight prompt.

files:
  - feature_swarm/orchestrator.py (update - issue methods)

acceptance_criteria:
  - [ ] run_issue_creation(feature_id) method
  - [ ] Invoke CCPM to create issues
  - [ ] Track created issue numbers in state
  - [ ] Update phase to ISSUES_CREATED
  - [ ] run_issue_validation(feature_id) method
  - [ ] Invoke IssueValidatorAgent
  - [ ] Update phase to ISSUES_NEED_REVIEW
  - [ ] Integration tests

spec_reference: "Section 6"

integration_points:
  - Used by: cli (when phase is SPEC_APPROVED or ISSUES_CREATED)
  - Uses: ccpm_adapter, issue_validator, state_store

test_strategy: |
  - Test full issue creation flow
  - Test validation after creation
  - Test phase transitions
```

#### Issue 18: CLI Greenlight Flow

```yaml
title: "Implement greenlight flow in CLI"
priority: P1
size: small (2 hours)
dependencies: [7, 17]

description: |
  When phase is ISSUES_NEED_REVIEW, prompt user to greenlight.

files:
  - feature_swarm/cli.py (update)

acceptance_criteria:
  - [ ] Detect ISSUES_NEED_REVIEW phase
  - [ ] Display validation summary
  - [ ] Show any issues that failed validation
  - [ ] Prompt: "Greenlight implementation? [Y/n]"
  - [ ] On approval: update phase to READY_TO_IMPLEMENT
  - [ ] On rejection: offer to re-validate or exit
  - [ ] Unit tests

spec_reference: "Section 2.2"

integration_points:
  - Used by: user (via CLI)
  - Uses: state_store, orchestrator

test_strategy: |
  - Test greenlight updates phase
  - Test rejection shows failed issues
```

---

### Milestone 4: Implementation Pipeline
*Goal: Implement issues through test-first development*

#### Issue 19: Session Manager

```yaml
title: "Implement session manager with feature-branch git strategy (session_manager.py)"
priority: P1
size: high (5-6 hours)
dependencies: [4, 14]

description: |
  Manages one-issue-per-session workflow with checkpoints and recovery.

  GIT STRATEGY (branch per feature, commits per issue):
  - One branch per FEATURE: feature/<feature-slug>
  - Issues map to COMMITS, not branches
  - Each session creates commits tagged with issue number
  - Rollback = revert commits for specific issue
  - Optional worktree per feature for isolation

  This aligns with CCPM's epic/worktree pattern and avoids branch explosion.

files:
  - feature_swarm/session_manager.py

acceptance_criteria:
  - [ ] SessionManager class
  - [ ] Feature branch management:
    - ensure_feature_branch(feature_id) - create feature/<slug> if not exists
    - get_feature_branch(feature_id) → branch name
    - Optional: create_worktree(feature_id) if config.git.use_worktrees
  - [ ] Session lifecycle:
    - start_session(feature_id, issue_number) → session_id
    - checkpoint(session_id, agent, status, commit_hash=None)
    - end_session(session_id, status)
  - [ ] Issue tracking via commits:
    - Commits tagged in message: "feat(<feature>): <msg> (#<issue_number>)"
    - Session stores list of commit hashes created
    - get_commits_for_issue(feature_id, issue_number) → list[str]
  - [ ] Recovery:
    - get_interrupted_sessions(feature_id) → list
    - rollback_session(session_id) - revert commits from that session
    - rollback_issue(feature_id, issue_number) - revert all commits for issue
  - [ ] Locking:
    - claim_issue(issue_number) - lock issue (prevent concurrent work)
    - release_issue(issue_number) - unlock
    - detect_stale_sessions(timeout_minutes)
  - [ ] Session files in .swarm/sessions/<feature>/sess_*.json:
    - session_id, feature_id, issue_number
    - started_at, status, checkpoints
    - commits: list[str] (hashes created this session)
    - worktree_path (if using worktrees)
  - [ ] Unit tests

spec_reference: "Section 7"

integration_points:
  - Used by: orchestrator, cli (recovery)
  - Uses: state_store, logger, github_client, config (git settings)

test_strategy: |
  - Test feature branch creation
  - Test session lifecycle (start → checkpoint → commit → end)
  - Test commit message tagging with issue number
  - Test rollback_session reverts correct commits
  - Test rollback_issue finds all commits for that issue
  - Test interrupted session detection
  - Test stale session timeout
  - Test issue locking prevents concurrent work
  - Test worktree creation (optional)

git_commit_format: |
  # Commit messages follow conventional commits + issue tag:
  feat(user-auth-jwt): add token refresh tests (#45)
  feat(user-auth-jwt): implement token refresh endpoint (#45)
  fix(user-auth-jwt): handle expired token edge case (#45)

  # This allows:
  # - Easy filtering: git log --grep="#45"
  # - Automated rollback of specific issues
  # - Clear audit trail
```

#### Issue 20: Prioritization Agent ✅ COMPLETE

```yaml
title: "Implement Prioritization agent (agents/prioritization.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8, 14]
status: COMPLETE

description: |
  Determines which issue to work on next based on dependencies and value.

files:
  - feature_swarm/agents/prioritization.py ✅
  - tests/unit/test_prioritization_agent.py ✅ (30 tests)

acceptance_criteria:
  - [x] PrioritizationAgent extends BaseAgent
  - [x] get_next_issue(state) → TaskRef or None
  - [x] Filter blocked issues (dependencies not met)
  - [x] Score by: dependencies met, size, business value, technical risk
  - [x] Return highest-scored ready issue
  - [x] Handle empty ready queue
  - [x] Unit tests (30 tests)

spec_reference: "Section 4.2"

integration_points:
  - Used by: orchestrator, cli
  - Uses: agent_base, state_store

test_strategy: |
  - Test priority ordering ✅
  - Test dependency filtering ✅
  - Test empty queue handling ✅

implementation_notes: |
  PrioritizationAgent uses a deterministic scoring algorithm (no LLM needed):
  - Filters out blocked issues
  - Scores remaining by size, business value, and technical risk
  - Returns highest-priority ready issue
```

#### Issue 21: Test Writer Agent ✅ COMPLETE → DEPRECATED

> **ARCHITECTURE CHANGE (Dec 2025):** TestWriterAgent was removed in the thick-agent cutover.
> Test writing is now part of CoderAgent (Implementation Agent) which handles the complete
> TDD workflow (tests + code + iteration) in a single context window to eliminate handoff losses.
> See: specs/thick-agent-cutover/spec.md

```yaml
title: "[DEPRECATED] Implement Test Writer agent (agents/test_writer.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8]
status: DEPRECATED - Merged into CoderAgent

description: |
  [HISTORICAL] Agent that writes failing tests for an issue before implementation.
  This functionality is now part of CoderAgent's TDD workflow.

files:
  - feature_swarm/agents/test_writer.py  # DELETED
  - tests/unit/test_test_writer_agent.py # DELETED
```

#### Issue 22: Coder Agent ✅ COMPLETE → UPDATED (Implementation Agent)

> **ARCHITECTURE CHANGE (Dec 2025):** CoderAgent is now the "Implementation Agent" with full TDD workflow.
> It writes tests AND implements code in a single context window (thick-agent architecture).

```yaml
title: "Implement Coder agent (agents/coder.py) - Implementation Agent with TDD"
priority: P1
size: medium (2-3 hours)
dependencies: [8]
status: COMPLETE + ENHANCED

description: |
  Implementation Agent (formerly just "Coder") that handles the complete TDD workflow:
  1. Read context (issue, spec, integration points)
  2. Write tests first (RED phase)
  3. Implement code (GREEN phase)
  4. Iterate until all tests pass

files:
  - feature_swarm/agents/coder.py ✅
  - tests/unit/test_coder_agent.py ✅ (31 tests)

acceptance_criteria:
  - [x] CoderAgent extends BaseAgent
  - [x] Read issue, tests, existing code
  - [x] Generate implementation using Claude
  - [x] Write implementation files
  - [x] Checkpoint after implementation
  - [x] Return list of modified files
  - [x] Unit tests with mocked LLM (31 tests)

spec_reference: "Section 4.1"

integration_points:
  - Used by: orchestrator (issue session)
  - Uses: agent_base, llm_clients, session_manager

test_strategy: |
  - Test generates implementation ✅
  - Test checkpoint created ✅

implementation_notes: |
  CoderAgent implements code to make tests pass via Claude CLI:
  - Reads test files and implements code
  - Supports skill prompts
  - Checkpoint support for recovery
  - Multiple file output support
```

#### Issue 23: Verifier Agent ✅ COMPLETE

```yaml
title: "Implement Verifier agent (agents/verifier.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8]
status: COMPLETE

description: |
  Agent that runs tests and verifies implementation is correct.
  Optionally uses LLM for intelligent failure analysis (analyze_failures=True).

files:
  - feature_swarm/agents/verifier.py ✅
  - .claude/skills/verifier/SKILL.md ✅
  - tests/unit/test_verifier_agent.py ✅ (55 tests)

acceptance_criteria:
  - [x] VerifierAgent extends BaseAgent
  - [x] Detect test runner from config or project
  - [x] Run tests for the issue
  - [x] Parse test results
  - [x] Check for regressions (run full test suite)
  - [x] Return verification result (pass/fail with details)
  - [x] Unit tests (55 tests)
  - [x] LLM-powered failure analysis (optional, via analyze_failures context param)

spec_reference: "Section 4.1"

integration_points:
  - Used by: orchestrator (issue session)
  - Uses: agent_base, config, llm_clients (optional for failure analysis)

test_strategy: |
  - Test passes when tests pass
  - Test fails when tests fail
  - Test regression detection
  - Test LLM failure analysis (with mocked LLM)

implementation_notes: |
  VerifierAgent has three operational modes:
  1. Basic: Run issue tests only (check_regressions=False, analyze_failures=False)
  2. Full: Run issue tests + regression check (check_regressions=True, default)
  3. Smart: Run tests + LLM analysis on failure (analyze_failures=True)

  Context parameters:
  - feature_id: str (required)
  - issue_number: int (required)
  - test_path: str (optional, defaults to tests/generated/{feature_id}/test_issue_{n}.py)
  - check_regressions: bool (default True) - run full test suite after issue tests
  - analyze_failures: bool (default False) - use LLM to analyze failures

  Output includes:
  - tests_run, tests_passed, tests_failed, duration_seconds
  - test_output (raw pytest output)
  - regression_check (if enabled)
  - failure_analysis (if enabled and tests failed) with root_cause, recoverable, suggested_fix
```

#### Issue 24: Issue Session Orchestration ✅ COMPLETE

```yaml
title: "Implement issue session orchestration"
priority: P1
size: high (4-5 hours)
dependencies: [19, 20, 21, 22, 23]
status: COMPLETE

description: |
  Orchestrate: claim issue → write tests → implement → verify → complete.

files:
  - feature_swarm/orchestrator.py ✅ (run_issue_session method added)
  - tests/unit/test_orchestrator.py ✅ (35 new tests, 66 total)

acceptance_criteria:
  - [x] run_issue_session(feature_id, issue_number=None) method
  - [x] If no issue_number, use PrioritizationAgent
  - [x] Start session, claim issue
  - [x] Run CoderAgent (Implementation Agent) with TDD workflow
  - [x] Run CoderAgent with checkpoint
  - [x] Run VerifierAgent
  - [x] On success: mark issue DONE, end session
  - [x] On failure: retry up to max_implementation_retries
  - [x] After max retries: mark BLOCKED
  - [x] Git commit on success
  - [x] Update GitHub issue status
  - [x] Unit tests (35 new tests across 8 categories)

spec_reference: "Section 7.2"

integration_points:
  - Used by: cli (when phase is READY_TO_IMPLEMENT)
  - Uses: session_manager, all implementation agents, github_client

test_strategy: |
  - Test successful session flow ✅
  - Test retry on failure ✅
  - Test blocking after max retries ✅
  - Test checkpoint creation ✅

implementation_notes: |
  IssueSessionResult dataclass tracks:
  - status: "success", "failed", "blocked"
  - issue_number, session_id, tests_written/passed/failed
  - commits (list of git hashes), cost_usd, retries, error

  Helper methods implemented:
  - _select_issue(): Uses PrioritizationAgent when no issue specified
  - _run_implementation_cycle(): Executes coder → verifier cycle
  - _create_commit(): Creates git commit with proper message format
  - _mark_task_done(): Updates task stage to DONE in state
  - _mark_task_blocked(): Updates task stage to BLOCKED in state

  Test Categories (35 tests):
  1. IssueSessionResult dataclass tests (3 tests)
  2. Issue Session Initialization (4 tests)
  3. Agent Execution Flow (5 tests)
  4. Success Path (6 tests)
  5. Retry Logic (5 tests)
  6. Failure Handling (5 tests)
  7. Git Integration (2 tests)
  8. Cost Tracking (2 tests)
  9. Edge Cases (3 tests)
```

---

### Milestone 5: Recovery & Edge Cases
*Goal: Handle errors gracefully and enable recovery*

#### Issue 25: Edge Case Handlers ✅ COMPLETE

```yaml
title: "Implement edge case handlers (edge_cases.py)"
priority: P1
size: medium (3-4 hours)
dependencies: [4, 6, 14]
status: COMPLETE

description: |
  Implement handlers for automatic recovery scenarios.

files:
  - feature_swarm/edge_cases.py ✅
  - tests/unit/test_edge_cases.py ✅ (74 tests)

acceptance_criteria:
  - [x] RetryHandler class with exponential backoff
  - [x] NetworkTimeoutHandler - retry 3x
  - [x] GitHubRateLimitHandler - wait or checkpoint
  - [x] ContextExhaustedHandler - checkpoint and exit
  - [x] TestFailureHandler - retry up to 3x
  - [x] StateInconsistencyHandler - reconcile from git
  - [x] StaleSessionHandler - claim after timeout
  - [x] Each handler logs its actions
  - [x] Unit tests (74 tests)
  - [x] EdgeCaseDispatcher routes errors to appropriate handlers

spec_reference: "Section 8.1"

integration_points:
  - Used by: orchestrator, session_manager, agents
  - Uses: state_store, logger, config

test_strategy: |
  - Test retry logic with backoff
  - Test rate limit handling
  - Test checkpoint on context exhaustion

implementation_notes: |
  Edge Case Handlers provide deterministic, rule-based recovery:

  Handler Interface:
  - HandlerResult dataclass with action, message, retry_after_seconds, context
  - BaseHandler abstract class with can_handle() and handle() methods
  - RetryHandler base class with exponential backoff support

  Handlers Implemented:
  1. NetworkTimeoutHandler - Retries ConnectionError/TimeoutError 3x with backoff
  2. GitHubRateLimitHandler - Waits <5min for reset, checkpoints >5min
  3. ContextExhaustedHandler - Creates checkpoint with resume instructions
  4. TestFailureHandler - Tracks retries per issue, escalates after max
  5. StateInconsistencyHandler - Reconciles state from git history
  6. StaleSessionHandler - Claims sessions after stale_timeout_minutes

  EdgeCaseDispatcher - Routes errors to first matching handler
  - Returns None if no handler matches (error goes to RecoveryAgent)

  Custom Exceptions:
  - GitHubRateLimitError (with reset_at, remaining)
  - ContextExhaustedError
  - TestFailureError
  - StateInconsistencyError
  - SessionLockError (with session_id, locked_at)
```

#### Issue 26: Recovery Agent ✅ COMPLETE

```yaml
title: "Implement Recovery agent (agents/recovery.py)"
priority: P1
size: medium (2-3 hours)
dependencies: [8, 25]
status: COMPLETE

description: |
  Agent that handles failures requiring LLM analysis to recover.
  Integrates with VerifierAgent's failure analysis when available.

files:
  - feature_swarm/agents/recovery.py ✅
  - .claude/skills/recovery/SKILL.md ✅
  - tests/unit/test_recovery_agent.py ✅ (62 tests)

acceptance_criteria:
  - [x] RecoveryAgent extends BaseAgent
  - [x] analyze_failure(session, error) → recovery plan
  - [x] Determine if automatic recovery possible
  - [x] Generate human-readable recovery instructions
  - [x] Suggest fixes for common issues
  - [x] Integrates with VerifierAgent's failure analysis
  - [x] Unit tests with mocked LLM (62 tests)

spec_reference: "Section 4.1, 8.2"

integration_points:
  - Used by: orchestrator, cli (recovery flow)
  - Uses: agent_base, llm_clients

test_strategy: |
  - Test generates recovery plans
  - Test identifies recoverable vs non-recoverable
  - Test integration with VerifierAgent analysis
  - Test max retry limit handling
  - Test all failure types (test_failure, git_conflict, auth_failure, network_failure)

implementation_notes: |
  RecoveryAgent leverages VerifierAgent's failure_analysis when available:
  - If verifier_analysis present in context, uses it directly (no LLM call)
  - Otherwise, performs its own LLM analysis
  - Determines recoverability based on failure type + retry count
  - Generates recovery_plan for recoverable failures
  - Generates human_instructions for non-recoverable failures
  - Tracks LLM costs via checkpoints
```

#### Issue 27: CLI Recovery Flow ✅ COMPLETE

```yaml
title: "Implement recovery flow in CLI"
priority: P1
size: medium (3 hours)
dependencies: [7, 19, 26]
status: COMPLETE

description: |
  Handle interrupted sessions and blocked issues in CLI.

files:
  - feature_swarm/cli_recovery.py ✅ (new module)
  - feature_swarm/cli.py ✅ (updated with smart/recover commands)
  - tests/unit/test_cli_recovery.py ✅ (38 tests)

acceptance_criteria:
  - [x] Detect interrupted sessions on startup
  - [x] Display recovery options: Resume, Backup & restart, Skip
  - [x] Handle Resume: continue from checkpoint
  - [x] Handle Backup: git stash, restart fresh
  - [x] Handle Skip: mark issue blocked, continue
  - [x] Detect blocked issues that may be unblocked
  - [x] Display blocked issues needing human help
  - [x] Unit tests (38 tests)

spec_reference: "Section 8.3"

integration_points:
  - Used by: user (via CLI)
  - Uses: session_manager, recovery_agent, state_store

test_strategy: |
  - Test recovery option display ✅
  - Test resume from checkpoint ✅
  - Test backup and restart ✅

implementation_notes: |
  New module feature_swarm/cli_recovery.py with:
  - check_interrupted_sessions() - Detects interrupted/active sessions
  - display_recovery_options() - Shows recovery menu with Rich UI
  - handle_resume() - Resumes from last checkpoint
  - handle_backup_restart() - Git stash, rollback, restart fresh
  - handle_skip() - Marks issue blocked, continues to next
  - check_blocked_issues() - Finds blocked tasks
  - display_blocked_issues() - Shows blocked issues table
  - offer_blocked_issue_retry() - Offers retry for blocked issues

  CLI commands added:
  - feature-swarm smart <feature> - Full smart CLI with recovery flow
  - feature-swarm recover <feature> - Recovery-only mode
```

---

### Milestone 6: Smart CLI
*Goal: Complete the state-aware CLI experience*

#### Issue 28: Smart CLI State Machine ✅ COMPLETE

```yaml
title: "Implement smart CLI state machine (state_machine.py)"
priority: P1
size: medium (3-4 hours)
dependencies: [4, 12, 17, 24]
status: COMPLETE

description: |
  Central state machine that determines next action based on current phase.

files:
  - feature_swarm/state_machine.py ✅
  - tests/unit/test_state_machine.py ✅ (36 tests)

acceptance_criteria:
  - [x] StateMachine class
  - [x] get_next_action(feature_id) → Action enum
  - [x] Action enum: AWAIT_PRD, RUN_SPEC_PIPELINE, AWAIT_SPEC_APPROVAL, RUN_ISSUE_PIPELINE, AWAIT_ISSUE_GREENLIGHT, SELECT_ISSUE, RESUME_SESSION, RUN_IMPLEMENTATION, COMPLETE, AWAIT_HUMAN_HELP
  - [x] Handle each FeaturePhase correctly
  - [x] Check for interrupted sessions first
  - [x] Check for blocked issues
  - [x] Return appropriate action with context
  - [x] Unit tests for all phase transitions (36 tests)

spec_reference: "Section 2.2"

integration_points:
  - Used by: cli (main entry point)
  - Uses: state_store, session_manager

test_strategy: |
  - Test each phase maps to correct action ✅
  - Test interrupted session detection ✅
  - Test blocked issue detection ✅

implementation_notes: |
  StateMachine maps FeaturePhases to Actions:
  - NO_PRD → AWAIT_PRD
  - PRD_READY → RUN_SPEC_PIPELINE
  - SPEC_NEEDS_APPROVAL → AWAIT_SPEC_APPROVAL
  - SPEC_APPROVED → RUN_ISSUE_PIPELINE
  - ISSUES_NEED_REVIEW → AWAIT_ISSUE_GREENLIGHT
  - READY_TO_IMPLEMENT → SELECT_ISSUE or RESUME_SESSION
  - IMPLEMENTING → RUN_IMPLEMENTATION
  - COMPLETE → COMPLETE
  - BLOCKED → AWAIT_HUMAN_HELP
```

#### Issue 29: Smart CLI Main Command ✅ COMPLETE

```yaml
title: "Implement smart CLI main command"
priority: P1
size: high (4-5 hours)
dependencies: [13, 18, 27, 28]
status: COMPLETE

description: |
  Complete the main `feature-swarm` command that does the right thing.

files:
  - feature_swarm/cli.py ✅ (smart and recover commands added)
  - tests/unit/test_cli.py ✅

acceptance_criteria:
  - [x] Main command uses StateMachine to determine action
  - [x] No feature specified: show dashboard, prompt selection
  - [x] Feature specified: determine and execute action
  - [x] Display current status before action
  - [x] Confirmation prompt for expensive operations
  - [x] Execute appropriate orchestrator method
  - [x] Handle all Actions from state machine
  - [x] Beautiful Rich terminal output
  - [x] Integration tests

spec_reference: "Section 2.1, 2.2, 2.3"

integration_points:
  - Used by: user (main entry point)
  - Uses: state_machine, orchestrator, all other modules

test_strategy: |
  - Test no feature shows dashboard ✅
  - Test each action type executes correctly ✅
  - Test confirmation prompts ✅

implementation_notes: |
  CLI commands implemented:
  - feature-swarm status [feature] - Dashboard or detailed status
  - feature-swarm init <feature> - Initialize new feature
  - feature-swarm run <feature> - Run spec pipeline
  - feature-swarm approve <feature> - Approve spec
  - feature-swarm reject <feature> - Reject spec
  - feature-swarm next <feature> - Determine next action
  - feature-swarm smart <feature> - Full smart CLI with recovery
  - feature-swarm recover <feature> - Recovery-only mode
```

#### Issue 30: CLI Escape Hatches

```yaml
title: "Implement CLI escape hatches (override options)"
priority: P2
size: small (2 hours)
dependencies: [29]

description: |
  Add command-line options to override automatic behavior.

files:
  - feature_swarm/cli.py (update)

acceptance_criteria:
  - [ ] --phase option to force specific phase
  - [ ] --issue option to work on specific issue
  - [ ] --skip-validation option
  - [ ] --dry-run option (show what would happen)
  - [ ] These override smart CLI behavior
  - [ ] Unit tests

spec_reference: "Section 2.4"

integration_points:
  - Used by: user (via CLI)
  - Uses: orchestrator

test_strategy: |
  - Test --phase override
  - Test --issue override
  - Test --dry-run output
```

#### Issue 31: CLI Utility Commands

```yaml
title: "Implement CLI utility commands"
priority: P2
size: small (2 hours)
dependencies: [7]

description: |
  Add utility commands: logs, rollback.

files:
  - feature_swarm/cli.py (update)

acceptance_criteria:
  - [ ] `feature-swarm logs <feature>` - view logs
  - [ ] `feature-swarm rollback <feature>` - undo last session
  - [ ] Rollback: git revert, reopen issue, update state
  - [ ] Logs: tail and stream option
  - [ ] Unit tests

spec_reference: "Section 2.4"

integration_points:
  - Used by: user (via CLI)
  - Uses: logger, session_manager, github_client

test_strategy: |
  - Test log viewing
  - Test rollback reverts correctly
```

---

### Milestone 7: Integration Testing & Polish
*Goal: Prove the system works with real API calls*

#### Issue 32: Integration Test Fixtures and Utilities (GitHub #19)

```yaml
title: "Integration Test Fixtures and Utilities"
priority: P1
size: small (1-2 hours)
dependencies: []
status: NOT_STARTED

description: |
  Shared fixtures and utilities for all integration tests.
  Provides consistent setup for real API testing.

files:
  - tests/integration/conftest.py

acceptance_criteria:
  - [ ] Configuration fixtures (integration_config, full_config)
  - [ ] Data fixtures (tiny_prd, tiny_spec, tiny_issue, passing/failing_test_file)
  - [ ] Environment fixtures (git_repo, setup_skills)
  - [ ] Component fixtures (state_store, session_manager, orchestrator)
  - [ ] Skip markers (skip_no_anthropic, skip_no_git, skip_no_claude_cli)
  - [ ] Utility functions (wait_for_file, assert_valid_json)

spec_reference: "Section 13.6"
```

#### Issue 33: Integration Tests Phase 1 - Foundation Smoke (GitHub #15)

```yaml
title: "Integration Tests Phase 1: Foundation Smoke Tests"
priority: P1
size: small (1-2 hours)
dependencies: [32]
status: NOT_STARTED

description: |
  Fastest, most critical tests. If these fail, nothing else works.
  Uses REAL API calls - no mocks.

files:
  - tests/integration/test_foundation_smoke.py

tests:
  - test_claude_cli_responds: ClaudeCliRunner returns valid ClaudeResult
  - test_codex_cli_responds: CodexCliRunner returns valid response
  - test_state_store_roundtrip: Save state → load → identical
  - test_session_store_roundtrip: Save session with checkpoints → load → intact
  - test_git_operations_basic: Init repo, add file, commit → hash returned

acceptance_criteria:
  - [ ] All 5 tests implemented
  - [ ] Tests use real API calls (no mocks for LLM/git)
  - [ ] Tests skip gracefully when prerequisites missing
  - [ ] All tests pass locally
  - [ ] Cost per run: ~$0.02

run_time: ~30 seconds
spec_reference: "Section 13.3 Phase 1"
```

#### Issue 34: Integration Tests Phase 2 - Agent Smoke (GitHub #16)

```yaml
title: "Integration Tests Phase 2: Agent Smoke Tests"
priority: P1
size: medium (2-3 hours)
dependencies: [33]
status: NOT_STARTED

description: |
  Each agent tested individually with minimal prompts.
  Uses REAL LLM calls - no mocks for critical paths.

files:
  - tests/integration/test_agent_smoke.py

tests:
  - test_spec_author_generates_spec: Creates spec file from tiny PRD
  - test_spec_critic_returns_json: Returns valid JSON with scores
  - test_prioritization_agent_selects_correctly: Deterministic selection (no LLM)
  - test_coder_generates_tests_and_implementation: TDD workflow validation
  - test_coder_generates_implementation: Creates implementation from tests
  - test_verifier_runs_tests: Correctly reports passing tests
  - test_verifier_detects_failure: Correctly reports failing tests
  - test_recovery_agent_analyzes_failure: Returns recovery plan

acceptance_criteria:
  - [ ] All 8 tests implemented
  - [ ] Each agent tested with real LLM (except PrioritizationAgent)
  - [ ] Tests use minimal prompts to reduce cost/time
  - [ ] All tests pass locally
  - [ ] Cost per run: ~$0.15

run_time: ~2-3 minutes
spec_reference: "Section 13.3 Phase 2"
```

#### Issue 35: Integration Tests Phase 3 - Pipeline Integration (GitHub #17)

```yaml
title: "Integration Tests Phase 3: Pipeline Integration Tests"
priority: P1
size: medium (2-3 hours)
dependencies: [34]
status: NOT_STARTED

description: |
  Multi-component flows tested together.
  Verifies that agents work correctly in sequence.

files:
  - tests/integration/test_pipeline_integration.py

tests:
  - test_spec_debate_one_round: Author → Critic → revision improves spec
  - test_issue_session_happy_path: Full session - tests → code → verify → commit
  - test_issue_session_retry_on_failure: Retry logic triggers and succeeds
  - test_session_recovery_from_checkpoint: Resume continues from checkpoint
  - test_cli_smart_command_executes: CLI determines correct action

acceptance_criteria:
  - [ ] All 5 tests implemented
  - [ ] Happy path test proves full pipeline works
  - [ ] Recovery test proves checkpoint resumption works
  - [ ] All tests pass locally
  - [ ] Cost per run: ~$0.25

run_time: ~5 minutes
spec_reference: "Section 13.3 Phase 3"
```

#### Issue 36: Integration Tests Phase 4 - E2E Critical Path (GitHub #18)

```yaml
title: "Integration Tests Phase 4: End-to-End Critical Path"
priority: P2
size: medium (2-3 hours)
dependencies: [35]
status: NOT_STARTED

description: |
  Full system tests from PRD to shipped code.
  Slow but definitive proof the system works.

files:
  - tests/integration/test_e2e_critical.py

tests:
  - test_full_feature_tiny: PRD → Spec → Issues → Implementation → Done
  - test_blocked_issue_recovery: 3x failure → blocked → recovery instructions

acceptance_criteria:
  - [ ] Both tests implemented
  - [ ] Full feature test proves complete happy path
  - [ ] Blocked issue test proves failure path works
  - [ ] Tests can run with mocked GitHub (to avoid real issue creation)
  - [ ] All tests pass locally
  - [ ] Cost per run: ~$0.50

run_time: ~10-15 minutes
when_to_run: |
  - Not in CI by default (too slow/expensive)
  - Run manually before releases
  - Run when making significant changes to orchestration

spec_reference: "Section 13.3 Phase 4"
```

#### Issue 37: Documentation

```yaml
title: "Create user documentation"
priority: P2
size: small (2 hours)
dependencies: [36]
status: NOT_STARTED

description: |
  User-facing documentation for installation and usage.

files:
  - docs/getting-started.md
  - docs/configuration.md
  - docs/cli-reference.md
  - README.md

acceptance_criteria:
  - [ ] Installation instructions
  - [ ] Quick start guide
  - [ ] Configuration reference
  - [ ] CLI command reference
  - [ ] Troubleshooting section
  - [ ] Example config.yaml

spec_reference: "Section 10, 14"
```

#### Issue 38: Skill Prompt Templates (Official SKILL.md Format)

```yaml
title: "Create agent skills using Anthropic's official SKILL.md format"
priority: P1
size: medium (4-5 hours)
dependencies: [8]

description: |
  Create skill definitions for all 9 agents using Anthropic's official format.

  SKILL FORMAT: Each skill is a directory with SKILL.md containing:
  - YAML frontmatter (name, description, allowed-tools)
  - Markdown body with instructions and examples

  Directory structure:
  .claude/skills/<skill-name>/SKILL.md

files:
  - .claude/skills/feature-spec-author/SKILL.md
  - .claude/skills/feature-spec-critic/SKILL.md
  - .claude/skills/feature-spec-moderator/SKILL.md
  - .claude/skills/feature-issue-validator/SKILL.md
  - .claude/skills/feature-prioritizer/SKILL.md
  - .claude/skills/coder/SKILL.md  # Implementation Agent with TDD
  - .claude/skills/feature-coder/SKILL.md
  - .claude/skills/feature-verifier/SKILL.md
  - .claude/skills/feature-recovery/SKILL.md

acceptance_criteria:
  - [ ] Each skill follows Anthropic's official SKILL.md format
  - [ ] YAML frontmatter includes:
    - name: kebab-case skill identifier
    - description: What it does AND when to use it (for discovery)
    - allowed-tools: Restrict tool access per agent (optional)
  - [ ] Markdown body includes:
    - ## Instructions (step-by-step)
    - ## Output Format (JSON schema where needed)
    - ## Examples (at least one per skill)
  - [ ] Skills are discoverable by Claude Code
  - [ ] Each agent maps to exactly one skill

spec_reference: "Section 4.1, 9"

integration_points:
  - Used by: all agents via load_skill() in agent_base.py
  - Claude Code auto-discovers skills from .claude/skills/

test_strategy: |
  - Verify YAML frontmatter is valid
  - Manual review for instruction clarity
  - Integration tests verify agents can load skills
  - Test with Claude Code to verify discovery works

example_skill: |
  # .claude/skills/feature-spec-author/SKILL.md
  ---
  name: feature-spec-author
  description: >
    Draft detailed engineering specs from an approved PRD.
    Use when generating or updating the engineering specification
    for a feature, before implementation begins.
  allowed-tools: Read,Glob
  ---

  # Feature Spec Author

  ## Instructions

  1. Read the PRD at `.claude/prds/<feature>.md`
  2. Analyze requirements, constraints, and success criteria
  3. Generate a comprehensive engineering spec covering:
     - Architecture overview
     - Data models
     - API endpoints (if applicable)
     - Dependencies
     - Testing strategy
     - Risks and mitigations
  4. Write output to `specs/<feature>/spec-draft.md`

  ## Output Format

  The spec should be a Markdown document with these sections:
  - ## Overview
  - ## Architecture
  - ## Data Models
  - ## Implementation Plan
  - ## Testing Strategy
  - ## Risks

  ## Examples

  [Include example spec snippet]
```

---

## 5. Integration Matrix

| Module | Reads From | Writes To | Calls | Called By |
|--------|------------|-----------|-------|-----------|
| models.py | - | - | - | ALL |
| config.py | config.yaml, env vars | - | models | cli, agents, clients |
| logger.py | - | .swarm/logs/*.jsonl | config | ALL |
| state_store.py | .swarm/state/*.json | .swarm/state/*.json | models, config, logger | cli, orchestrator, session_mgr |
| utils/fs.py | filesystem | filesystem | config | state_store, logger, agents |
| llm_clients.py | - | - (subprocess) | config, logger | ALL agents |
| github_client.py | GitHub API | GitHub API | config, logger | ccpm_adapter, agents, session_mgr |
| ccpm_adapter.py | - | - (subprocess) | config, logger, github | orchestrator |
| agent_base.py | .claude/skills/* | - | llm_clients, state_store, logger | all agents |
| spec_author.py | .claude/prds/*.md | specs/*/spec-draft.md | agent_base | orchestrator |
| spec_critic.py | specs/*/spec-draft.md | specs/*/spec-review.json | agent_base | orchestrator |
| spec_moderator.py | specs/*/* | specs/*/spec-*.md, spec-rubric.json | agent_base | orchestrator |
| issue_validator.py | GitHub issues | specs/*/issue-validation.json | agent_base, github | orchestrator |
| prioritization.py | state | - | agent_base, state_store | orchestrator |
| coder.py (Implementation Agent) | issues, code, spec | tests + implementation files | agent_base | orchestrator |
| coder.py | issues, tests, code | implementation files | agent_base | orchestrator |
| verifier.py | tests | - | agent_base | orchestrator |
| recovery.py | session, errors | recovery plans | agent_base | orchestrator, cli |
| edge_cases.py | various | various | state_store, logger | orchestrator, session_mgr |
| session_manager.py | .swarm/sessions/* | .swarm/sessions/*, git | state_store, logger, github | orchestrator, cli |
| orchestrator.py | state | state | ALL agents, session_mgr, clients | cli |
| state_machine.py | state | - | state_store, session_mgr | cli |
| cli.py | user input | stdout | ALL | user |

---

## 6. Data Flow Diagrams

### 6.1 Spec Generation Flow

```
User runs `feature-swarm <feature>`
    │
    ▼
CLI checks state → PRD_READY
    │
    ▼
orchestrator.run_spec_pipeline()
    │
    ├──► SpecAuthorAgent.run()
    │        │
    │        ├── Read: .claude/prds/<feature>.md
    │        ├── Call: ClaudeCliRunner.run()
    │        └── Write: specs/<feature>/spec-draft.md
    │
    ├──► SpecCriticAgent.run()
    │        │
    │        ├── Read: spec-draft.md, PRD
    │        ├── Call: ClaudeCliRunner.run()
    │        └── Write: specs/<feature>/spec-review.json
    │
    ├──► SpecModeratorAgent.run()
    │        │
    │        ├── Read: spec-draft.md, spec-review.json
    │        ├── Call: ClaudeCliRunner.run()
    │        └── Write: spec-draft.md (updated), spec-rubric.json
    │
    └──► Check stopping conditions
             │
             ├── SUCCESS → phase = SPEC_NEEDS_APPROVAL
             ├── STALEMATE → phase = BLOCKED (needs human)
             └── CONTINUE → loop back to SpecCritic
```

### 6.2 Issue Creation Flow

```
User runs `feature-swarm <feature>`
    │
    ▼
CLI checks state → SPEC_APPROVED
    │
    ▼
orchestrator.run_issue_creation()
    │
    ├──► CCPMAdapter.create_epic()
    │        └── Invoke: ccpm epic create
    │
    ├──► CCPMAdapter.create_issues()
    │        │
    │        ├── Invoke: ccpm issue create
    │        └── Parse: issue numbers
    │
    ├──► Update state with issue numbers
    │        └── phase = ISSUES_CREATED
    │
    ▼
orchestrator.run_issue_validation()
    │
    ├──► IssueValidatorAgent.run()
    │        │
    │        ├── Fetch: issues from GitHub
    │        ├── Score: each issue on 5 criteria
    │        └── Write: specs/<feature>/issue-validation.json
    │
    └──► Update state
             └── phase = ISSUES_NEED_REVIEW
```

### 6.3 Implementation Session Flow

```
User runs `feature-swarm <feature>`
    │
    ▼
CLI checks state → READY_TO_IMPLEMENT
    │
    ▼
SessionManager.check_interrupted()
    │
    ├── YES → Offer recovery options
    └── NO → Continue
    │
    ▼
PrioritizationAgent.get_next_issue()
    │
    ▼
SessionManager.start_session(issue)
    │
    ├── Create session record
    ├── Claim issue (lock)
    └── Update state
    │
    ▼
orchestrator.run_issue_session(issue)
    │
    ├──► CoderAgent.run(issue)  # TDD workflow in single context
    │        │
    │        ├── Read context, write tests (RED), implement code (GREEN)
    │        └── Checkpoint saved
    │
    ├──► CoderAgent.run(issue)
    │        │
    │        ├── Implement code
    │        └── Checkpoint saved
    │
    ├──► VerifierAgent.run(issue)
    │        │
    │        ├── Run tests
    │        │
    │        ├── PASS → Continue
    │        └── FAIL → Retry (up to 3x) or BLOCKED
    │
    └──► SessionManager.end_session()
             │
             ├── Git commit
             ├── Update GitHub issue (close)
             ├── Update state (issue.stage = DONE)
             └── Release lock
```

---

## 7. Risk Analysis

### 7.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Claude CLI output format changes | Low | High | Pin version, add output validation, integration tests |
| CCPM commands fail silently | Medium | High | Robust file polling, timeout handling, output parsing |
| Context exhaustion mid-session | High | Medium | Checkpoints, WIP commits, graceful exit |
| Claude generates invalid code | Medium | Medium | Verification step, retry with error context |
| Git conflicts during session | Low | Medium | Detect early, provide clear instructions |
| Test framework detection fails | Medium | Low | Explicit config fallback |
| Circular dependencies in issues | Low | Medium | Validate dependency graph before implementation |

### 7.2 Integration Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State gets out of sync with git | Medium | High | Reconciliation on startup, git as source of truth |
| GitHub rate limiting | Medium | Low | Backoff, caching, conditional requests |
| CCPM API changes | Low | Medium | Pin version, adapter pattern |
| Session lock conflicts | Low | Low | Stale timeout, manual override |
| Spec debate never converges | Medium | Medium | Max rounds, stalemate detection, human escalation |

### 7.3 Operational Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| User loses work on crash | Low | High | Checkpoints every agent step |
| Unclear error messages | Medium | Medium | Structured errors with recovery suggestions |
| Configuration errors | Medium | Low | Validation on load, clear error messages |

---

## 8. Testing Strategy

### 8.1 Unit Tests (per module)

| Module | Test File | Key Test Cases |
|--------|-----------|----------------|
| models.py | test_models.py | Enum values, serialization round-trip, defaults |
| config.py | test_config.py | Loading, validation, defaults, env vars |
| logger.py | test_logger.py | JSONL format, rotation, context |
| state_store.py | test_state_store.py | CRUD, atomic writes, corruption handling |
| utils/fs.py | test_fs.py | Dir creation, atomic write, path resolution |
| llm_clients.py | test_llm_clients.py | Invocation, timeout, JSON parsing |
| github_client.py | test_github_client.py | CRUD (mocked), rate limiting |
| ccpm_adapter.py | test_ccpm_adapter.py | Invocation, output parsing |
| agent_base.py | test_agent_base.py | Skill loading, checkpoint |
| spec_*.py | test_spec_agents.py | Agent execution (mocked LLM) |
| issue_validator.py | test_issue_validator.py | Validation scoring |
| prioritization.py | test_prioritization.py | Scoring, filtering |
| coder.py | test_coder.py | Implementation Agent: TDD workflow |
| coder.py | test_coder.py | Implementation generation |
| verifier.py | test_verifier.py | Test execution, result parsing |
| recovery.py | test_recovery.py | Recovery plan generation |
| edge_cases.py | test_edge_cases.py | Each handler |
| session_manager.py | test_session_manager.py | Lifecycle, checkpoints, recovery |
| orchestrator.py | test_orchestrator.py | Pipeline execution |
| state_machine.py | test_state_machine.py | Phase → action mapping |
| cli.py | test_cli.py | Commands, options |

### 8.2 Integration Tests

| Test | Modules Involved | What It Validates |
|------|-----------------|-------------------|
| Spec debate e2e | spec agents, orchestrator | Full debate loop converges |
| Issue creation e2e | ccpm, validator, orchestrator | Issues created and validated |
| Session lifecycle | session_manager, agents | Start → work → end |
| Recovery from interrupt | session_manager, cli | Resume from checkpoint |
| Recovery from failure | edge_cases, recovery | Retry and block correctly |
| State persistence | state_store, orchestrator | State survives restart |

### 8.3 Manual Test Scenarios

1. **Happy path**: PRD → Spec (approved) → Issues (greenlit) → Implementation → Done
2. **Interrupt mid-session**: Kill during CoderAgent, resume next run
3. **Issue fails validation**: One issue scores low, user chooses to revise
4. **Implementation fails 3x**: Issue gets blocked, moves to next
5. **Spec stalemate**: Scores don't improve, escalates to human
6. **Network failure**: GitHub times out, retries succeed
7. **Context exhaustion**: Long implementation checkpoints and exits cleanly

---

## 9. Implementation Sequence

### Phase 1: Foundation (Issues 1-7)

```
┌─────────────────────────────────────────────────────────────────┐
│  #1 models.py                                                    │
│       │                                                         │
│       ▼                                                         │
│  #2 config.py ──────► #3 logger.py                              │
│       │                    │                                    │
│       ▼                    ▼                                    │
│  #5 utils/fs.py ◄──────────┘                                    │
│       │                                                         │
│       ▼                                                         │
│  #4 state_store.py                                              │
│       │                                                         │
│       ▼                                                         │
│  #6 llm_clients.py                                              │
│       │                                                         │
│       ▼                                                         │
│  #7 cli.py (skeleton + status)                                  │
└─────────────────────────────────────────────────────────────────┘

Deliverable: Can run `feature-swarm status` (shows empty state)
```

### Phase 2: Spec Pipeline (Issues 8-13)

```
┌─────────────────────────────────────────────────────────────────┐
│  #8 agent_base.py                                               │
│       │                                                         │
│       ├───────────┬───────────┐                                 │
│       ▼           ▼           ▼                                 │
│  #9 spec_    #10 spec_   #11 spec_                              │
│     author       critic      moderator                          │
│       │           │           │                                 │
│       └───────────┴───────────┘                                 │
│                   │                                             │
│                   ▼                                             │
│           #12 spec debate orchestration                         │
│                   │                                             │
│                   ▼                                             │
│           #13 cli: approval flow                                │
│                                                                 │
│  (parallel) #34 skill prompt templates                          │
└─────────────────────────────────────────────────────────────────┘

Deliverable: Can run `feature-swarm` on a PRD, generates spec, asks for approval
```

### Phase 3: Issue Management (Issues 14-18)

```
┌─────────────────────────────────────────────────────────────────┐
│  #14 github_client.py                                           │
│       │                                                         │
│       ▼                                                         │
│  #15 ccpm_adapter.py                                            │
│       │                                                         │
│       ▼                                                         │
│  #16 issue_validator.py                                         │
│       │                                                         │
│       ▼                                                         │
│  #17 issue creation orchestration                               │
│       │                                                         │
│       ▼                                                         │
│  #18 cli: greenlight flow                                       │
└─────────────────────────────────────────────────────────────────┘

Deliverable: Can create and validate issues from spec
```

### Phase 4: Implementation Pipeline (Issues 19-24)

```
┌─────────────────────────────────────────────────────────────────┐
│  #19 session_manager.py                                         │
│       │                                                         │
│       ▼                                                         │
│  #20 prioritization.py                                          │
│       │                                                         │
│       ├───────────┬───────────┐                                 │
│       ▼           ▼           ▼                                 │
│  #21 test_   #22 coder   #23 verifier                           │
│     writer                                                      │
│       │           │           │                                 │
│       └───────────┴───────────┘                                 │
│                   │                                             │
│                   ▼                                             │
│           #24 issue session orchestration                       │
└─────────────────────────────────────────────────────────────────┘

Deliverable: Can implement a single issue via TDD
```

### Phase 5: Recovery & Edge Cases (Issues 25-27)

```
┌─────────────────────────────────────────────────────────────────┐
│  #25 edge_cases.py                                              │
│       │                                                         │
│       ▼                                                         │
│  #26 recovery_agent.py                                          │
│       │                                                         │
│       ▼                                                         │
│  #27 cli: recovery flow                                         │
└─────────────────────────────────────────────────────────────────┘

Deliverable: System handles failures gracefully
```

### Phase 6: Smart CLI (Issues 28-31)

```
┌─────────────────────────────────────────────────────────────────┐
│  #28 state_machine.py                                           │
│       │                                                         │
│       ▼                                                         │
│  #29 cli: smart main command                                    │
│       │                                                         │
│       ├───────────┐                                             │
│       ▼           ▼                                             │
│  #30 escape   #31 utility                                       │
│     hatches       commands                                      │
└─────────────────────────────────────────────────────────────────┘

Deliverable: Full smart CLI experience
```

### Phase 7: Polish (Issues 32-34)

```
┌─────────────────────────────────────────────────────────────────┐
│  #32 e2e integration tests                                      │
│       │                                                         │
│       ▼                                                         │
│  #33 documentation                                              │
└─────────────────────────────────────────────────────────────────┘

Deliverable: Production-ready release
```

---

## 10. Checklist for Reviewer

The reviewing agent should verify:

### Completeness
- [ ] All spec sections are covered by at least one issue
- [ ] No orphan modules (everything integrates)
- [ ] All data flows are accounted for
- [ ] All 9 agents from spec are implemented

### Feasibility
- [ ] Dependencies are correctly identified
- [ ] No circular dependencies
- [ ] Size estimates are reasonable
- [ ] No issue is too large (>5 hours)

### Integration
- [ ] Module interfaces are clear
- [ ] Data formats are consistent (JSON for state/config)
- [ ] Error handling spans modules correctly
- [ ] Checkpoint/recovery flow is complete

### Testability
- [ ] Each module has a test strategy
- [ ] Integration tests cover critical paths
- [ ] Edge cases are explicitly listed
- [ ] Manual test scenarios defined

### Spec Alignment
- [ ] Issue acceptance criteria match spec requirements
- [ ] No scope creep beyond spec
- [ ] Assumptions are documented
- [ ] Open questions identified

---

## 11. Implementation Status (Updated 2025-11-26)

### Overall Progress: ~90% Complete (Core), Integration Tests Next

| Metric | Value |
|--------|-------|
| Total Issues | 38 |
| Core Complete | 31 |
| Integration Tests | 5 (not started) |
| Polish/Cleanup | 2 (P2) |
| Total Unit Tests | 1,014 |

### Completed Components (31/38 issues)

**Milestone 1: Foundation** ✅ COMPLETE
- Issue 1: Core Data Models ✅
- Issue 2: Configuration Loading ✅
- Issue 3: Structured Logging ✅
- Issue 4: State Store ✅
- Issue 5: File System Utilities ✅
- Issue 6: Claude Code CLI Wrapper ✅
- Issue 7: CLI Skeleton with Status Command ✅

**Milestone 2: Spec Pipeline** ✅ COMPLETE
- Issue 8: Agent Base Class ✅
- Issue 9: Spec Author Agent ✅
- Issue 10: Spec Critic Agent ✅
- Issue 11: Spec Moderator Agent ✅
- Issue 12: Spec Debate Orchestration ✅
- Issue 13: CLI Spec Approval Flow ✅

**Milestone 3: Issue Management** ✅ COMPLETE
- Issue 14: GitHub Client ✅
- Issue 15: CCPM Adapter ✅
- Issue 16: Issue Validator Agent ✅
- Issue 17: Issue Creation Orchestration ✅
- Issue 18: CLI Greenlight Flow ✅

**Milestone 4: Implementation Pipeline** ✅ COMPLETE
- Issue 19: Session Manager ✅ (64 tests)
- Issue 20: Prioritization Agent ✅ (30 tests)
- Issue 21: Test Writer Agent ✅ DEPRECATED (merged into Coder Agent)
- Issue 22: Coder Agent ✅ (31 tests)
- Issue 23: Verifier Agent ✅ (55 tests)
- Issue 24: Issue Session Orchestration ✅ (66 tests)

**Milestone 5: Recovery & Edge Cases** ✅ COMPLETE
- Issue 25: Edge Case Handlers ✅ (74 tests)
- Issue 26: Recovery Agent ✅ (62 tests)
- Issue 27: CLI Recovery Flow ✅ (38 tests)

**Milestone 6: Smart CLI** ✅ COMPLETE
- Issue 28: Smart CLI State Machine ✅ (36 tests)
- Issue 29: Smart CLI Main Command ✅
- Issue 30: CLI Escape Hatches ⚠️ (deferred - P2)
- Issue 31: CLI Utility Commands ⚠️ (deferred - P2)

**Milestone 7: Integration Testing & Polish** ⏳ IN PROGRESS
- Issue 32: Integration Test Fixtures (GitHub #19) ⏳
- Issue 33: Phase 1 - Foundation Smoke (GitHub #15) ⏳
- Issue 34: Phase 2 - Agent Smoke (GitHub #16) ⏳
- Issue 35: Phase 3 - Pipeline Integration (GitHub #17) ⏳
- Issue 36: Phase 4 - E2E Critical Path (GitHub #18) ⏳
- Issue 37: Documentation ⏳
- Issue 38: Skill Prompt Templates ✅ (partial)

### Remaining Work - Priority Order

| GitHub # | Plan Issue | Description | Priority | Effort |
|----------|------------|-------------|----------|--------|
| #19 | 32 | Integration Test Fixtures | P1 | 1-2h |
| #15 | 33 | Phase 1: Foundation Smoke | P1 | 1-2h |
| #16 | 34 | Phase 2: Agent Smoke | P1 | 2-3h |
| #17 | 35 | Phase 3: Pipeline Integration | P1 | 2-3h |
| #18 | 36 | Phase 4: E2E Critical Path | P2 | 2-3h |
| - | 37 | Documentation | P2 | 2h |
| #4 | - | Remove deprecated GPT5Client | P2 | 1h |

### Integration Test Cost Estimate

| Phase | Tests | Est. Cost |
|-------|-------|-----------|
| Phase 1 | 5 | $0.02 |
| Phase 2 | 8 | $0.15 |
| Phase 3 | 5 | $0.25 |
| Phase 4 | 2 | $0.50 |
| **Total** | 20 | **~$1.00** |

---

## 12. Original Plan Summary (for reference)

**All 8 open questions have been resolved** - see Section 2.2 for decisions.

### Key Decisions Made

1. **CCPM**: Headless Claude with `/pm:*` slash commands (PRD stays interactive)
2. **Claude Output**: `--output-format json` everywhere, parse envelope for cost tracking
3. **GitHub**: REST API with PAT (not `gh` CLI)
4. **Tests**: Explicit `tests.command` in config (no auto-detect magic)
5. **Scope**: Single repo only for v1
6. **Costs**: Track and surface per feature/session/agent
7. **Skills**: Official SKILL.md format in `.claude/skills/<name>/SKILL.md`
8. **Git**: One branch per feature (`feature/<slug>`), issues map to commits not branches

### Issue Breakdown by Priority

| Priority | Count | Effort |
|----------|-------|--------|
| P0 (Foundation) | 7 | 12-16 hours |
| P1 (Core Features) | 22 | 55-70 hours |
| P2 (Polish) | 5 | 8-12 hours |

### Issue Breakdown by Size

| Size | Count |
|------|-------|
| Small (1-2 hours) | 11 |
| Medium (2-4 hours) | 18 |
| High (4-6 hours) | 5 |

### Reviewer Instructions

1. Verify all spec sections are covered (use Section mapping in issues)
2. Check dependency graph for cycles or missing links
3. Validate integration points between modules
4. Confirm the 8 resolved decisions align with project goals
5. Flag any gaps or concerns
6. Approve or request changes

---

## 12. Spec Section to Issue Mapping

| Spec Section | Description | Covered By Issues |
|--------------|-------------|-------------------|
| 0.1 | One Command Philosophy | #28, #29 |
| 0.2 | Core Principles | Throughout |
| 1 | What This System Does | Architecture (all issues) |
| 2.1 | Primary Command | #7, #29 |
| 2.2 | State Machine | #28 |
| 2.3 | Example Session | #29 |
| 2.4 | Escape Hatches | #30, #31 |
| 3.1 | Feature Phases | #1 |
| 3.2 | Task Stages | #1 |
| 4.1 | Agent Overview | #8, #9-11, #16, #20-23, #26 |
| 4.2 | Prioritization Agent | #20 |
| 5.1 | Spec Process | #9, #10, #11 |
| 5.2 | Stopping Conditions | #12 |
| 5.3 | Output Files | #9, #10, #11 |
| 6.1 | Why Validation | #16 |
| 6.2 | Validation Criteria | #16 |
| 6.3 | Validation Output | #16 |
| 7.1 | One Issue Per Session | #19, #24 |
| 7.2 | Session Lifecycle | #19 |
| 7.3 | Session State | #1, #19 |
| 7.4 | Multi-Session Workflow | #19, #24 |
| 8.1 | Auto-Handled Edge Cases | #25 |
| 8.2 | Human Intervention | #27 |
| 8.3 | Recovery Command | #27 |
| 9 | Directory Structure | #4, #5 |
| 10.1 | config.yaml | #2 |
| 11 | COO Agent (Future) | Not in scope |
| 12 | Implementation Prompt | Reference only |
| 13 | Quick Reference | #33 (docs) |

---

*Document generated for Feature Swarm v3.0 specification*
