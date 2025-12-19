# Agents and Skills Catalog

## Overview

Swarm Attack is an autonomous AI-powered multi-agent development automation system that orchestrates Claude Code agents to handle feature development and bug fixing pipelines.

### Architecture: Skill-Based Agents

Agents in Swarm Attack are powered by **skills**—specialized Claude prompts that define their behavior, tools, and expertise. This architecture enables:

- **Separation of concerns**: Skills define what an agent does (prompt + allowed tools), while agent classes handle execution orchestration
- **Reusability**: Skills can be shared across different workflows
- **Maintainability**: Prompt engineering is centralized in skill files, not scattered in code
- **Transparency**: Skills are readable markdown files in `.claude/skills/` and `swarm_attack/skills/`

### Skill Anatomy

Each skill is a directory containing a `SKILL.md` file with:
- **Frontmatter**: Name, description, and allowed tools
- **System prompt**: Instructions for Claude on how to perform the task
- **Output format**: Structured JSON or text format specifications
- **Examples**: Demonstrations of expected behavior

Skills are located in:
- `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/skills/` - Production skills
- `/Users/philipjcortes/Desktop/swarm-attack/.claude/skills/` - Claude Code integration skills

---

## Skills Catalog

### Feature Development Skills

#### feature-spec-author
**Purpose**: Draft detailed engineering specs from an approved PRD
**Allowed Tools**: Read, Glob, Write
**Key Behaviors**:
- Explores existing codebase to find reusable infrastructure
- Enforces lean, startup-focused spec generation
- Prohibits over-engineering (no caching layers, feature flags, microservices for small scale)
- Generates specs with: Overview, Implementation approach, Data models, API design, Implementation tasks, Testing strategy
- Emphasizes basic quality (error handling, type hints, validation) without enterprise complexity

#### feature-spec-critic
**Purpose**: Review and score engineering specs against a startup-focused quality rubric
**Allowed Tools**: Read, Glob, Write
**Key Behaviors**:
- Scores specs on 4 dimensions: Clarity (0.0-1.0), Coverage, Architecture, Risk
- Penalizes over-engineering patterns aggressively
- Flags critical issues for: over-engineering, missing requirements, unnecessary infrastructure
- Accepts basic quality patterns (try/except, timeouts, validation)
- Returns structured JSON with scores, issues, and recommendation (APPROVE/REVISE/REJECT)

#### feature-spec-moderator
**Purpose**: Chief Architect review - critically evaluate peer feedback and maintain spec simplicity
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Reviews critic feedback and decides: ACCEPT, REJECT, DEFER, or PARTIAL
- Enforces startup philosophy (100 users vs 10M users)
- Auto-accepts basic quality suggestions
- Auto-rejects enterprise patterns (A/B testing, feature flags, caching layers)
- Outputs dispositions for each issue and updated spec with rubric scores
- Determines if ready for approval or needs another debate round

#### issue-creator
**Purpose**: Generate GitHub issues from an approved engineering specification
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Breaks down specs into atomic, implementable GitHub issues
- Enforces sizing limits: ≤8 acceptance criteria, ≤6 methods per issue
- Includes Interface Contracts for internal features (from_dict, to_dict patterns)
- Adds File Operations section (CREATE/UPDATE with preservation directives)
- Structures issues with: Description, Acceptance Criteria, Technical Notes, Labels, Size estimate, Dependencies, Order
- Validates issues fit within LLM implementation window (~15 turns)

#### issue-validator
**Purpose**: Validate generated GitHub issues for completeness and implementability
**Allowed Tools**: Read
**Key Behaviors**:
- Evaluates each issue for: title quality, description clarity, acceptance criteria, scope appropriateness, technical context
- Flags issues with severity levels: error (blocks implementation) or warning (should address)
- Identifies common problems: vague criteria, missing context, too large, unclear scope
- Returns JSON with implementability assessment for each issue

#### complexity-gate
**Purpose**: Estimate issue complexity before implementation to prevent timeouts
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Estimates LLM turns needed for implementation (5-40 range)
- Uses three-tier strategy: instant pass (≤5 criteria), instant fail (>12 criteria), LLM estimation (borderline)
- Returns complexity score (0.0-1.0), estimated turns, and needs_split flag
- Triggers auto-split when: >8 acceptance criteria, >6 methods, multiple subsystems, config + implementation + integration
- Saves expensive implementation tokens by catching oversized issues early

#### issue-splitter
**Purpose**: Split complex issues into smaller, implementable sub-issues
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Called automatically when ComplexityGate determines an issue needs splitting
- Creates 2-4 smaller sub-issues that each fit in <20 LLM turns
- Uses splitting strategies: by layer, by operation, by criteria groups, by phase
- Each sub-issue has 3-5 acceptance criteria maximum
- Returns JSON array of sub-issues with titles, bodies, and size estimates

#### coder
**Purpose**: Implementation Agent with full TDD workflow in a single context window
**Allowed Tools**: Read, Glob, Bash, Write, Edit
**Key Behaviors**:
- Handles complete implementation cycle: read context → write tests → implement code → iterate until passing
- Thick agent architecture eliminates context loss from handoffs
- Follows TDD workflow: Phase 1 (Read context), Phase 2 (Write tests first), Phase 3 (Run tests expecting failure), Phase 4 (Implement code), Phase 5 (Iterate until passing), Phase 6 (Run full test suite), Phase 7 (Mark complete)
- Enforces Interface Contracts (from_dict, to_dict methods)
- Preserves existing code when modifying files (surgical changes only)
- Outputs files using text markers (# FILE: path/to/file.ext)
- Follows existing codebase patterns

#### verifier
**Purpose**: Analyze test failures and suggest fixes for Feature Swarm verification
**Allowed Tools**: Read, Glob, Grep
**Key Behaviors**:
- Analyzes test output to identify failures and root cause
- Determines if failures are recoverable by retrying with CoderAgent
- Recoverable: missing imports, typos, simple logic errors
- Not recoverable: architecture issues, missing dependencies, environment problems
- Returns JSON with: root_cause, recoverable flag, suggested_fix, affected_files

#### recovery
**Purpose**: Analyze implementation failures and generate recovery plans
**Allowed Tools**: Read, Glob, Grep
**Key Behaviors**:
- Classifies failure types: test_failure, timeout, error, git_conflict, auth_failure, network_failure
- Assesses recoverability (automatic retry vs human intervention)
- Generates specific recovery plans for recoverable failures
- Provides step-by-step human instructions for non-recoverable issues
- Returns JSON with root cause, recovery plan, and escalation reason if needed

### Bug Investigation Skills

#### bug-researcher
**Purpose**: Reproduce bugs and gather evidence for root cause analysis
**Allowed Tools**: Read, Glob, Grep, Bash
**Key Behaviors**:
- Attempts to reproduce bugs from bug reports
- Runs tests and captures full output, error messages, stack traces
- Identifies affected files from stack traces
- Collects code snippets from relevant areas
- Documents reproduction steps clearly
- Returns JSON with: confirmed flag, reproduction steps, test output, error message, stack trace, affected files, code snippets, confidence level (high/medium/low)

#### root-cause-analyzer
**Purpose**: Analyze reproduction evidence to identify the root cause of bugs
**Allowed Tools**: Read, Glob, Grep
**Key Behaviors**:
- Traces execution through call chain to find where behavior diverges
- Distinguishes between where bug manifests vs where it originates
- Forms and tests hypotheses methodically
- Explains why existing tests didn't catch the bug
- Returns JSON with: summary, execution trace, root cause file/line/code, explanation, why not caught, confidence level, alternative hypotheses considered

#### fix-planner
**Purpose**: Design fix plans based on root cause analysis
**Allowed Tools**: Read, Glob, Grep
**Key Behaviors**:
- Designs minimal fix that addresses root cause
- Specifies exact code changes with before/after code
- Creates test cases to verify fix and prevent regression (≥2 tests: regression + edge case)
- Assesses risk level (low/medium/high) with rollback plan
- Returns JSON with: summary, file changes (current/proposed code), test cases, risk assessment, side effects, rollback plan

#### bug-fix-plan-critic
**Purpose**: Review bug fix plans for correctness and completeness
**Allowed Tools**: Read, Glob, Grep
**Key Behaviors**:
- Evaluates fix plans against root cause analysis
- Checks if fix addresses root cause without side effects
- Validates test coverage for regression prevention
- Returns structured feedback similar to feature-spec-critic

#### bug-fix-plan-moderator
**Purpose**: Apply critic feedback to improve fix plans
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Reviews critic feedback on fix plans
- Decides which suggestions to accept/reject
- Updates fix plan based on valid feedback
- Similar workflow to feature-spec-moderator

#### bug-root-cause-critic
**Purpose**: Review root cause analysis for accuracy
**Allowed Tools**: Read, Glob, Grep
**Key Behaviors**:
- Validates execution traces are complete and accurate
- Checks if root cause explanation is supported by evidence
- Identifies gaps in analysis
- Returns structured feedback

#### bug-root-cause-moderator
**Purpose**: Apply critic feedback to improve root cause analysis
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Reviews critic feedback on root cause analysis
- Updates analysis based on valid feedback
- Ensures analysis is evidence-based and thorough

### Additional Skills

#### summarizer
**Purpose**: Generate summaries of swarm execution sessions
**Allowed Tools**: Read, Glob
**Key Behaviors**:
- Summarizes feature development or bug fixing sessions
- Extracts key decisions, issues encountered, and outcomes
- Used for daily logs and status reporting

---

## Agents

Agents are Python classes that orchestrate skill execution. They inherit from `BaseAgent` and use the Claude CLI runner to execute skills.

### Base Infrastructure

#### BaseAgent
**File**: `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/agents/base.py`
**Purpose**: Abstract base class for all agents
**Key Features**:
- Skill loading from `swarm_attack/skills/<name>/SKILL.md`
- Checkpoint support for progress tracking
- Retry decorator for transient failures
- Standardized logging via `SwarmLogger`
- Cost tracking for LLM API calls
- Returns `AgentResult` dataclass with success/failure, output, errors, cost

#### AgentResult
**Purpose**: Standardized return type for all agents
**Fields**:
- `success: bool` - Whether execution succeeded
- `output: Any` - Agent output data
- `errors: list[str]` - Error messages
- `cost_usd: float` - Cost of LLM API calls

### Feature Development Agents

#### SpecAuthorAgent
**Skill**: feature-spec-author
**Orchestrates**: Spec generation from PRD
**Key Methods**:
- `run(prd_path, spec_output_path)` - Generates spec from PRD

#### SpecCriticAgent
**Skill**: feature-spec-critic
**Orchestrates**: Spec review and scoring
**Key Methods**:
- `run(spec_path, prd_path)` - Reviews spec and returns scores/issues

#### SpecModeratorAgent
**Skill**: feature-spec-moderator
**Orchestrates**: Spec improvement via critic feedback
**Key Methods**:
- `run(spec_path, prd_path, critique_path)` - Applies feedback to spec

#### IssueCreatorAgent
**Skill**: issue-creator
**Orchestrates**: GitHub issue generation from specs
**Key Methods**:
- `run(spec_path)` - Generates issues JSON from approved spec

#### IssueValidatorAgent
**Skill**: issue-validator
**Orchestrates**: Issue quality validation
**Key Methods**:
- `run(issues_json)` - Validates generated issues

#### ComplexityGateAgent
**Skill**: complexity-gate
**Orchestrates**: Complexity estimation before implementation
**Key Methods**:
- `run(issue_title, issue_body)` - Estimates complexity and determines if split needed
- Uses three-tier strategy to minimize LLM costs

#### IssueSplitterAgent
**Skill**: issue-splitter
**Orchestrates**: Complex issue splitting
**Key Methods**:
- `run(issue_title, issue_body, split_suggestions)` - Splits issue into sub-issues

#### CoderAgent
**Skill**: coder
**Orchestrates**: Full TDD implementation cycle
**Key Methods**:
- `run(issue_data, spec_path, feature_id)` - Implements issue with tests
- Thick agent that handles entire test-code-verify loop in single context

#### VerifierAgent
**Skill**: verifier
**Orchestrates**: Test execution and failure analysis
**Key Methods**:
- `run(test_output, feature_id, issue_number)` - Analyzes test failures

#### RecoveryAgent
**Skill**: recovery
**Orchestrates**: Failure recovery planning
**Key Methods**:
- `run(failure_data)` - Generates recovery plan or escalation

### Bug Investigation Agents

#### BugResearcherAgent
**Skill**: bug-researcher
**Orchestrates**: Bug reproduction and evidence gathering
**Key Methods**:
- `run(bug_report)` - Reproduces bug and collects evidence

#### RootCauseAnalyzerAgent
**Skill**: root-cause-analyzer
**Orchestrates**: Root cause identification
**Key Methods**:
- `run(reproduction_evidence)` - Analyzes evidence to find root cause

#### FixPlannerAgent
**Skill**: fix-planner
**Orchestrates**: Fix plan design
**Key Methods**:
- `run(root_cause_analysis)` - Creates fix plan with tests

#### BugCriticAgent
**Skill**: bug-root-cause-critic or bug-fix-plan-critic
**Orchestrates**: Quality review of bug analysis/plans
**Key Methods**:
- `run(analysis_or_plan)` - Reviews and scores bug work

#### BugModeratorAgent
**Skill**: bug-root-cause-moderator or bug-fix-plan-moderator
**Orchestrates**: Feedback application for bug work
**Key Methods**:
- `run(work, critique)` - Applies feedback to improve analysis/plan

### Supporting Agents

#### PrioritizationAgent
**Orchestrates**: Next issue selection
**Key Methods**:
- `run(issues_list)` - Selects which issue to work on next based on dependencies and priority

#### GateAgent
**Orchestrates**: General-purpose gating/validation
**Key Methods**:
- `run(gate_config)` - Validates conditions before proceeding

#### SummarizerAgent
**Skill**: summarizer
**Orchestrates**: Session summary generation
**Key Methods**:
- `run(session_data)` - Generates summary of work completed

---

## Integration Points

### Workflow Orchestration

Agents are orchestrated by pipeline managers in `/Users/philipjcortes/Desktop/swarm-attack/swarm_attack/`:

1. **Feature Swarm Pipeline** (`feature_swarm.py`):
   ```
   PRD → SpecAuthor → SpecCritic/SpecModerator (debate) → Approve
   → IssueCreator → IssueValidator → ComplexityGate → IssueSplitter (if needed)
   → CoderAgent → VerifierAgent → RecoveryAgent (if failures) → Commit
   ```

2. **Bug Bash Pipeline** (`bug_bash.py`):
   ```
   Bug Report → BugResearcher → RootCauseAnalyzer/Critic/Moderator (debate)
   → FixPlanner/Critic/Moderator (debate) → Approve → CoderAgent → VerifierAgent
   ```

### State Management

Agents interact with:
- **StateStore**: Persists agent outputs and checkpoints in `.swarm/`
- **SwarmLogger**: Centralized logging for all agent activities
- **SwarmConfig**: Configuration loaded from `config.yaml`

### Claude CLI Integration

All agents use `ClaudeCliRunner` to execute skills via the Claude Code CLI:
- Skills are loaded as system prompts
- Tools are restricted per skill definition
- Costs are tracked via CLI output parsing
- Timeouts and retries handled automatically

### File System Layout

```
swarm_attack/
├── skills/              # Production skill definitions
│   ├── feature-spec-author/SKILL.md
│   ├── coder/SKILL.md
│   └── ...
├── agents/              # Python agent orchestrators
│   ├── base.py
│   ├── spec_author.py
│   ├── coder.py
│   └── ...
└── orchestrators/       # Pipeline managers
    ├── feature_swarm.py
    └── bug_bash.py

.claude/
└── skills/              # Claude Code integration skills
    ├── feature-spec-author/SKILL.md
    └── ...

.swarm/
├── features/            # Feature state and outputs
├── bugs/                # Bug investigation state
└── sessions/            # Session logs and checkpoints
```

---

## Key Design Principles

1. **Thick-Agent Architecture**: CoderAgent has full context (issue + spec + tests + code) to eliminate handoff losses
2. **Startup-Focused**: Skills enforce lean development—no premature optimization or enterprise patterns
3. **Debate-Driven Quality**: Critic/Moderator pairs ensure quality through adversarial review
4. **Complexity Gating**: Issues are validated for size before expensive implementation
5. **Interface Contracts**: Issues specify required methods to prevent integration bugs
6. **Preservation Directives**: Updates to existing code are surgical, not wholesale rewrites
7. **Test-Driven**: Coder agent writes tests first, then implements to pass them
8. **Recoverable Failures**: Verifier and Recovery agents automatically fix simple failures

---

## Usage Examples

### Running a Feature Pipeline
```bash
# Generate spec from PRD
swarm-attack run my-feature

# After spec approval, generate issues
swarm-attack issues my-feature

# Enable implementation
swarm-attack greenlight my-feature

# Implement next issue (ComplexityGate → Coder → Verifier)
swarm-attack run my-feature
```

### Running Bug Investigation
```bash
# Initialize bug
swarm-attack bug init "Login fails with special chars" --test tests/test_auth.py::test_login

# Run full analysis pipeline
swarm-attack bug analyze bug-123

# Review and approve fix
swarm-attack bug approve bug-123

# Apply fix
swarm-attack bug fix bug-123
```

---

## Adding New Agents/Skills

To add a new agent:

1. Create skill definition in `swarm_attack/skills/<skill-name>/SKILL.md`
2. Create agent class in `swarm_attack/agents/<agent_name>.py` inheriting from `BaseAgent`
3. Implement `run()` method to orchestrate skill execution
4. Add agent to `swarm_attack/agents/__init__.py`
5. Integrate into appropriate pipeline orchestrator

Example minimal agent:
```python
from swarm_attack.agents.base import BaseAgent, AgentResult

class MyAgent(BaseAgent):
    name = "my-agent"

    def run(self, context: dict) -> AgentResult:
        # Execute skill and return result
        result = self._run_skill("my-skill", context)
        return AgentResult.success_result(output=result)
```
