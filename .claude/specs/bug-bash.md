# Bug Bash System Specification

## Overview

Bug Bash is a standalone bug investigation and fix planning pipeline for the swarm-attack CLI. This system helps developers investigate bugs, identify root causes, plan fixes, and optionally implement them after human approval.

Unlike the feature pipeline (PRD → Spec → Issues → Code), Bug Bash starts with a problem and works backward to find and fix the cause.

```
Bug Report → Reproduction → Root Cause Analysis → Fix Plan → [Approval] → Implementation
```

---

## Key Principles

1. **Analysis before action**: Deep investigation before any code changes
2. **Human approval gate**: No implementation without explicit approval
3. **Evidence-based**: Every conclusion backed by code references and test output
4. **Standalone**: Works independently of the feature pipeline
5. **Incremental**: Can stop at any phase (research only, analysis only, plan only)

---

## Use Cases

1. **External bug report**: User reports "X doesn't work" - need to reproduce, find root cause, plan fix
2. **Test failure investigation**: Tests failing but unclear why - need deep analysis
3. **Production incident**: Something broke - need to trace through code to find cause
4. **Code review finding**: Reviewer says "this looks wrong" - need to confirm and scope fix

---

## Data Models

### BugPhase Enum

```python
class BugPhase(Enum):
    """Phases of bug investigation."""
    CREATED = "created"                    # Bug report submitted
    REPRODUCING = "reproducing"            # Researcher working
    REPRODUCED = "reproduced"              # Bug confirmed
    NOT_REPRODUCIBLE = "not_reproducible"  # Could not reproduce
    ANALYZING = "analyzing"                # Root cause analysis in progress
    ANALYZED = "analyzed"                  # Root cause identified
    PLANNING = "planning"                  # Fix plan in progress
    PLANNED = "planned"                    # Fix plan ready for approval
    APPROVED = "approved"                  # Human approved the fix plan
    IMPLEMENTING = "implementing"          # Fix being implemented
    VERIFYING = "verifying"               # Running verification tests
    FIXED = "fixed"                       # Bug fixed and verified
    WONT_FIX = "wont_fix"                 # Decided not to fix
    BLOCKED = "blocked"                   # Investigation blocked
```

### BugReport

```python
@dataclass
class BugReport:
    """Initial bug report from user."""
    description: str                       # User's description of the bug
    test_path: Optional[str] = None        # Path to failing test (if provided)
    github_issue: Optional[int] = None     # GitHub issue number (if provided)
    error_message: Optional[str] = None    # Error message (if provided)
    stack_trace: Optional[str] = None      # Stack trace (if provided)
    steps_to_reproduce: list[str] = field(default_factory=list)
```

### ReproductionResult

```python
@dataclass
class ReproductionResult:
    """Output from Bug Researcher agent."""
    confirmed: bool                        # Was bug reproduced?
    reproduction_steps: list[str]          # Steps to reproduce
    test_output: Optional[str] = None      # Captured test output
    error_message: Optional[str] = None    # Captured error
    stack_trace: Optional[str] = None      # Captured stack trace
    affected_files: list[str] = field(default_factory=list)
    related_code_snippets: dict[str, str] = field(default_factory=dict)
    confidence: str = "medium"             # high/medium/low
    notes: str = ""                        # Additional observations
```

### RootCauseAnalysis

```python
@dataclass
class RootCauseAnalysis:
    """Output from Root Cause Analyzer agent."""
    summary: str                           # One-line summary
    execution_trace: list[str]             # Step-by-step trace
    root_cause_file: str                   # File containing the bug
    root_cause_line: Optional[int] = None  # Line number (if identified)
    root_cause_code: str = ""              # The problematic code
    root_cause_explanation: str = ""       # Why this causes the bug
    why_not_caught: str = ""               # Why existing tests missed it
    confidence: str = "medium"             # high/medium/low
    alternative_hypotheses: list[str] = field(default_factory=list)
```

### FileChange

```python
@dataclass
class FileChange:
    """A single file change in the fix plan."""
    file_path: str
    change_type: str                       # "modify", "create", "delete"
    current_code: Optional[str] = None     # Existing code (for modify)
    proposed_code: Optional[str] = None    # New code
    explanation: str = ""                  # Why this change
```

### TestCase

```python
@dataclass
class TestCase:
    """A test case to verify the fix."""
    name: str                              # test_function_name
    description: str                       # What it tests
    test_code: str                         # The actual test code
    category: str = "regression"           # "regression", "edge_case", "integration"
```

### FixPlan

```python
@dataclass
class FixPlan:
    """Output from Fix Planner agent."""
    summary: str                           # One-line summary of fix
    changes: list[FileChange]              # Files to change
    test_cases: list[TestCase]             # Tests to add
    risk_level: str = "low"                # "low", "medium", "high"
    risk_explanation: str = ""             # Why this risk level
    scope: str = ""                        # e.g., "1 file, 5 lines"
    side_effects: list[str] = field(default_factory=list)
    rollback_plan: str = ""                # How to undo if needed
    estimated_effort: str = ""             # e.g., "15 minutes"
```

### ImplementationResult

```python
@dataclass
class ImplementationResult:
    """Output from fix implementation."""
    success: bool
    files_changed: list[str]
    tests_passed: int
    tests_failed: int
    commit_hash: Optional[str] = None
    error: Optional[str] = None
```

### BugState

```python
@dataclass
class BugState:
    """Complete state of a bug investigation."""
    bug_id: str                            # Unique identifier
    phase: BugPhase
    created_at: datetime
    updated_at: datetime

    # Input
    report: BugReport

    # Outputs from each phase
    reproduction: Optional[ReproductionResult] = None
    root_cause: Optional[RootCauseAnalysis] = None
    fix_plan: Optional[FixPlan] = None
    implementation: Optional[ImplementationResult] = None

    # Metadata
    cost_usd: float = 0.0
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    notes: list[str] = field(default_factory=list)
```

---

## File Storage Structure

```
.swarm/bugs/{bug_id}/
├── state.json              # BugState serialized
├── report.md               # Human-readable bug report
├── reproduction.md         # Reproduction results
├── root-cause-analysis.md  # Root cause analysis
├── fix-plan.md            # Proposed fix plan
├── test-cases.py          # Generated test code
└── session.log            # Agent conversation logs
```

---

## Agent Specifications

### Agent 1: Bug Researcher

**Purpose**: Confirm the bug exists and gather evidence for analysis.

**Skill File**: `default-skills/bug-researcher/SKILL.md`

**Allowed Tools**: Read, Glob, Grep, Bash

**Process**:
1. Understand the bug report
2. Attempt reproduction (run test or create minimal repro)
3. Capture evidence (output, errors, stack traces)
4. Scan for affected code
5. Document findings

**Input Context**:
- Bug description
- Test path (if provided)
- Error message (if provided)
- Stack trace (if provided)

**Output JSON**:
```json
{
  "confirmed": true,
  "reproduction_steps": ["step 1", "step 2"],
  "test_output": "...",
  "error_message": "...",
  "stack_trace": "...",
  "affected_files": ["path/to/file.py"],
  "related_code_snippets": {
    "path/to/file.py:45": "code snippet..."
  },
  "confidence": "high",
  "notes": "Additional observations..."
}
```

**Skill Prompt**:
```markdown
# Bug Researcher

You are an expert QA engineer and debugger. Your job is to investigate a bug report and confirm whether the bug exists, gather evidence, and document reproduction steps.

## Your Mission

Given a bug report, you must:
1. **Reproduce the bug** - Confirm it actually happens
2. **Gather evidence** - Capture output, errors, stack traces
3. **Identify scope** - Find affected files and code paths
4. **Document clearly** - Write reproduction steps anyone can follow

## Process

### Step 1: Understand the Report
Read the bug report carefully. What is expected vs actual behavior?

### Step 2: Attempt Reproduction
If a test path is provided, run it:
```bash
pytest {test_path} -v 2>&1
```

If no test, try to reproduce based on description or write a minimal reproduction script.

### Step 3: Capture Evidence
For each reproduction attempt, capture:
- Full command output
- Error messages (exact text)
- Stack traces (full trace)
- Relevant log entries

### Step 4: Scan for Affected Code
Use Glob and Grep to find:
- Files mentioned in stack traces
- Functions mentioned in error messages
- Related code that might be affected

### Step 5: Document Findings
Output structured JSON with all findings.

## Important Guidelines

1. **Be thorough**: Run tests multiple times to confirm consistency
2. **Capture everything**: More evidence is better for root cause analysis
3. **Don't fix yet**: Your job is investigation, not implementation
4. **Note environment**: Record Python version, OS, dependencies if relevant
5. **Check recent changes**: Use `git log` to see if recent commits might be related
```

---

### Agent 2: Root Cause Analyzer

**Purpose**: Trace execution to find exactly where and why the bug occurs.

**Skill File**: `default-skills/root-cause-analyzer/SKILL.md`

**Allowed Tools**: Read, Glob, Grep

**Process**:
1. Review reproduction evidence
2. Trace execution path from entry to failure
3. Form and test hypotheses
4. Pinpoint exact root cause
5. Explain why this wasn't caught

**Input Context**:
- Bug ID
- ReproductionResult from Bug Researcher

**Output JSON**:
```json
{
  "summary": "Password special characters are stripped by over-aggressive sanitization",
  "execution_trace": [
    "1. User calls login('user@example.com', 'p@ss!')",
    "2. login() calls validate(password) at auth/login.py:45",
    "3. validate() calls sanitize(password) at auth/validate.py:23",
    "4. sanitize() applies regex that strips '!' character",
    "5. Password becomes 'pss', hash comparison fails"
  ],
  "root_cause_file": "src/utils/sanitize.py",
  "root_cause_line": 23,
  "root_cause_code": "return re.sub(r'[^a-zA-Z0-9]', '', value)",
  "root_cause_explanation": "The regex pattern [^a-zA-Z0-9] removes ALL non-alphanumeric characters including valid password special characters.",
  "why_not_caught": "Existing tests only use alphanumeric passwords. No test covers special characters.",
  "confidence": "high",
  "alternative_hypotheses": [
    "Initially considered hash algorithm mismatch, but ruled out by tracing"
  ]
}
```

**Skill Prompt**:
```markdown
# Root Cause Analyzer

You are an expert debugger and code analyst. Given reproduction evidence, your job is to trace through the code and identify the exact root cause of the bug.

## Your Mission

1. **Trace execution**: Follow the code path from entry to failure
2. **Identify divergence**: Find where actual behavior differs from expected
3. **Pinpoint cause**: Identify the specific line(s) causing the issue
4. **Explain why**: Describe why this code causes the observed behavior
5. **Note gaps**: Explain why existing tests didn't catch this

## Process

### Step 1: Review Evidence
Study the reproduction report - stack trace shows call path, error shows symptom.

### Step 2: Trace Execution
Starting from entry point, trace through each function:
1. Read each function in the call path
2. Note data flow (what values are passed)
3. Identify assumptions each function makes
4. Find where assumptions are violated

### Step 3: Form Hypotheses
Based on tracing, form hypotheses and test each by reading more code.

### Step 4: Pinpoint Root Cause
Identify exact file, line number, the specific code that's wrong, and why.

### Step 5: Explain the Gap
Why wasn't this caught? Missing test coverage? Edge case? Recent regression?

## Analysis Techniques

### Reading Stack Traces
```
Traceback (most recent call last):
  File "src/auth/login.py", line 45, in validate    ← Start here
    sanitized = sanitize(password)
  File "src/utils/sanitize.py", line 23, in sanitize  ← Bug here
    return re.sub(r'[^a-zA-Z0-9]', '', value)
```

### Data Flow Analysis
Trace what happens to each variable through the call chain.

### Hypothesis Testing
Form hypothesis, find evidence to confirm or refute, eliminate until one remains.

## Important Guidelines

1. **Follow the evidence**: Don't guess - trace through actual code
2. **Be specific**: "Line 23 does X" not "somewhere in the file"
3. **Explain causation**: Not just what's wrong, but WHY it causes the symptom
4. **Consider context**: Why was this code written this way originally?
5. **Stay focused**: Identify THE root cause, not every issue you notice
```

---

### Agent 3: Fix Planner

**Purpose**: Design a minimal, safe fix for the identified root cause.

**Skill File**: `default-skills/fix-planner/SKILL.md`

**Allowed Tools**: Read, Glob, Grep

**Process**:
1. Review root cause analysis
2. Design minimal fix
3. Identify all files needing changes
4. Write test cases
5. Assess risk

**Input Context**:
- Bug ID
- ReproductionResult
- RootCauseAnalysis

**Output JSON**:
```json
{
  "summary": "Add field_type parameter to sanitize() to preserve password special characters",
  "changes": [
    {
      "file_path": "src/utils/sanitize.py",
      "change_type": "modify",
      "current_code": "def sanitize(value):\n    return re.sub(r'[^a-zA-Z0-9]', '', value)",
      "proposed_code": "def sanitize(value, field_type='text'):\n    if field_type == 'password':\n        return value\n    return re.sub(r'[^a-zA-Z0-9@._-]', '', value)",
      "explanation": "Add field_type parameter with default 'text' for backward compatibility."
    }
  ],
  "test_cases": [
    {
      "name": "test_login_with_special_characters_succeeds",
      "description": "Verify users can log in with passwords containing special characters",
      "test_code": "def test_login_with_special_characters_succeeds():\n    user = create_user('test@example.com', 'P@ssw0rd!')\n    result = login('test@example.com', 'P@ssw0rd!')\n    assert result.success is True",
      "category": "regression"
    }
  ],
  "risk_level": "low",
  "risk_explanation": "Small scope, additive change, backward compatible.",
  "scope": "2 files, ~10 lines changed",
  "side_effects": ["Audit other callers of sanitize()"],
  "rollback_plan": "Revert the two file changes. No data migration needed.",
  "estimated_effort": "15 minutes implementation, 10 minutes testing"
}
```

**Skill Prompt**:
```markdown
# Fix Planner

You are an expert software architect and engineer. Given a root cause analysis, your job is to design a minimal, safe, and complete fix plan.

## Your Mission

1. **Design the fix**: Minimal changes to address root cause
2. **Identify all changes**: Every file that needs modification
3. **Write test cases**: Tests to verify fix and prevent regression
4. **Assess risk**: Potential side effects and mitigation
5. **Plan rollback**: How to undo if something goes wrong

## Principles

### Minimal Change
- Fix the bug, nothing more
- Don't refactor unrelated code
- Don't add features
- Don't "improve" working code

### Complete Fix
- Address the root cause, not just symptoms
- Consider all code paths affected
- Handle edge cases the fix might introduce

### Safe Fix
- Prefer additive changes over modifications
- Maintain backward compatibility
- Don't break existing functionality

## Risk Assessment Criteria

**LOW risk**:
- Single file change
- Additive change (new code, not modifying existing)
- Well-isolated function
- Comprehensive test coverage exists

**MEDIUM risk**:
- Multiple file changes
- Modifying existing logic
- Shared utility function
- Some test coverage exists

**HIGH risk**:
- Core system component
- Many callers affected
- Complex state changes
- Limited test coverage
- Data migration needed

## Important Guidelines

1. **Be specific**: Exact code, not descriptions of code
2. **Be complete**: Include ALL files that need changes
3. **Be conservative**: Minimal changes, maximum safety
4. **Test thoroughly**: More tests for higher risk
5. **Document reasoning**: Explain WHY each change is needed
```

---

## CLI Commands

### `swarm-attack bug init`

Initialize a bug investigation.

```bash
# From description
swarm-attack bug init "Login fails with special characters"

# From failing test
swarm-attack bug init --test tests/test_auth.py::test_special_chars

# From GitHub issue
swarm-attack bug init --github-issue 123

# With custom ID
swarm-attack bug init "Login bug" --id login-special-chars
```

**Behavior**:
1. Generate bug_id if not provided
2. Create BugState with CREATED phase
3. Save to `.swarm/bugs/{bug_id}/state.json`
4. Create initial `report.md`
5. Print next steps

---

### `swarm-attack bug analyze`

Run the analysis pipeline.

```bash
# Full analysis (reproduce → analyze → plan)
swarm-attack bug analyze login-special-chars

# Stop at reproduction
swarm-attack bug analyze login-special-chars --stop-at reproduce

# Stop at root cause analysis
swarm-attack bug analyze login-special-chars --stop-at analyze
```

**Behavior**:
1. Load BugState
2. Run Bug Researcher → update state → write `reproduction.md`
3. If confirmed, run Root Cause Analyzer → update state → write `root-cause-analysis.md`
4. Run Fix Planner → update state → write `fix-plan.md` and `test-cases.py`
5. Print status and next steps

---

### `swarm-attack bug status`

Show bug investigation status.

```bash
# Show all bugs
swarm-attack bug status

# Show specific bug
swarm-attack bug status login-special-chars
```

**Output for specific bug**:
```
╭───────────────────── Bug: login-special-chars ─────────────────────╮
│ Phase: PLANNED (awaiting approval)                                  │
│ Created: 2025-12-10 14:30:00                                       │
│ Cost: $0.18                                                        │
│                                                                    │
│ Reproduction: CONFIRMED (high confidence)                          │
│ Root Cause: src/utils/sanitize.py:23                              │
│   Regex [^a-zA-Z0-9] strips password special characters            │
│                                                                    │
│ Fix Plan:                                                          │
│   Files: 2 (sanitize.py, validate.py)                             │
│   Risk: LOW                                                        │
│   Tests: 3 new test cases                                          │
│                                                                    │
│ Next: swarm-attack bug approve login-special-chars                │
╰────────────────────────────────────────────────────────────────────╯
```

---

### `swarm-attack bug approve`

Approve a fix plan for implementation.

```bash
swarm-attack bug approve login-special-chars
```

**Behavior**:
1. Verify bug is in PLANNED phase
2. Set phase to APPROVED
3. Record approval timestamp
4. Print next steps

---

### `swarm-attack bug fix`

Implement the approved fix.

```bash
# Implement fix
swarm-attack bug fix login-special-chars

# Preview changes without applying
swarm-attack bug fix login-special-chars --dry-run
```

**Behavior**:
1. Verify bug is in APPROVED phase
2. Apply code changes from fix plan
3. Write test cases to test file
4. Run verification tests
5. If all pass, mark FIXED
6. If tests fail, mark BLOCKED with reason

---

### `swarm-attack bug list`

List all bug investigations.

```bash
# List all
swarm-attack bug list

# Filter by phase
swarm-attack bug list --phase planned

# Limit results
swarm-attack bug list --limit 10
```

---

### `swarm-attack bug reject`

Reject/close a bug as won't fix.

```bash
swarm-attack bug reject login-special-chars --reason "By design"
```

---

## Report Templates

### `report.md`

```markdown
# Bug Report: {bug_id}

**Created**: {timestamp}
**Status**: {phase}

## Description
{description}

## Source
- Test: {test_path or "N/A"}
- GitHub Issue: #{github_issue or "N/A"}

## Initial Information

### Error Message
```
{error_message or "Not provided"}
```

### Stack Trace
```
{stack_trace or "Not provided"}
```

### Steps to Reproduce
{steps_to_reproduce or "Not provided"}
```

### `reproduction.md`

```markdown
# Reproduction Report: {bug_id}

**Status**: {CONFIRMED / NOT REPRODUCIBLE}
**Confidence**: {confidence}
**Cost**: ${cost}

## Reproduction Steps
1. {step1}
2. {step2}

## Evidence

### Test Output
```
{test_output}
```

### Error Message
```
{error_message}
```

### Stack Trace
```
{stack_trace}
```

## Affected Files
| File | Relevance |
|------|-----------|
| {file1} | {reason} |

## Related Code

### `{file_path}:{line}`
```python
{code_snippet}
```

## Notes
{notes}
```

### `root-cause-analysis.md`

```markdown
# Root Cause Analysis: {bug_id}

**Confidence**: {confidence}
**Cost**: ${cost}

## Summary
{summary}

## Execution Trace
1. {trace_step_1}
2. {trace_step_2}

## Root Cause

**File**: `{root_cause_file}`
**Line**: {root_cause_line}

### Problematic Code
```python
{root_cause_code}
```

### Explanation
{root_cause_explanation}

## Why This Wasn't Caught
{why_not_caught}

## Alternative Hypotheses Considered
{alternative_hypotheses}
```

### `fix-plan.md`

```markdown
# Fix Plan: {bug_id}

**Risk Level**: {risk_level}
**Scope**: {scope}
**Estimated Effort**: {estimated_effort}
**Cost**: ${cost}

## Summary
{summary}

## Changes Required

### 1. `{file_path}` ({change_type})

**Current Code**:
```python
{current_code}
```

**Proposed Code**:
```python
{proposed_code}
```

**Explanation**: {explanation}

## Test Cases to Add

### `{test_name}` ({category})
{description}

```python
{test_code}
```

## Risk Assessment

**Level**: {risk_level}
{risk_explanation}

### Potential Side Effects
{side_effects}

### Rollback Plan
{rollback_plan}

---

## Approval

```bash
swarm-attack bug approve {bug_id}
swarm-attack bug fix {bug_id}
```
```

---

## BugOrchestrator Class

```python
class BugOrchestrator:
    """Orchestrates the bug investigation pipeline."""

    def __init__(self, config: SwarmConfig):
        self.config = config
        self.bug_researcher = BugResearcherAgent(config)
        self.root_cause_analyzer = RootCauseAnalyzerAgent(config)
        self.fix_planner = FixPlannerAgent(config)
        self.coder = CoderAgent(config)  # Reuse existing
        self.verifier = VerifierAgent(config)  # Reuse existing

    def run_investigation(
        self,
        bug_id: str,
        stop_at: Optional[str] = None,
    ) -> BugState:
        """Run the bug investigation pipeline."""
        state = self._load_state(bug_id)

        # Phase 1: Reproduction
        if self._should_run_phase(state, BugPhase.REPRODUCING, stop_at):
            state = self._run_reproduction(state)
            if not state.reproduction.confirmed:
                return state

        # Phase 2: Root Cause Analysis
        if self._should_run_phase(state, BugPhase.ANALYZING, stop_at):
            state = self._run_root_cause_analysis(state)

        # Phase 3: Fix Planning
        if self._should_run_phase(state, BugPhase.PLANNING, stop_at):
            state = self._run_fix_planning(state)

        return state

    def implement_fix(self, bug_id: str) -> BugState:
        """Implement an approved fix plan."""
        state = self._load_state(bug_id)

        if state.phase != BugPhase.APPROVED:
            raise ValueError(f"Bug must be APPROVED (current: {state.phase})")

        # Apply changes
        for change in state.fix_plan.changes:
            self._apply_change(change)

        # Write test cases
        self._write_test_cases(state.fix_plan.test_cases)

        # Run verification
        test_result = self._run_verification(state)

        if test_result.all_passed:
            state.phase = BugPhase.FIXED
        else:
            state.phase = BugPhase.BLOCKED
            state.blocked_reason = f"Tests failed: {test_result.failures}"

        self._save_state(state)
        return state
```

---

## File Structure

```
swarm_attack/
├── agents/
│   ├── bug_researcher.py      # NEW
│   ├── root_cause_analyzer.py # NEW
│   ├── fix_planner.py         # NEW
│   ├── coder.py               # Existing (reuse)
│   └── verifier.py            # Existing (reuse)
├── bug_orchestrator.py        # NEW
├── bug_state_store.py         # NEW
├── bug_models.py              # NEW (or add to models.py)
└── cli.py                     # Add bug subcommands

default-skills/
├── bug-researcher/
│   └── SKILL.md               # NEW
├── root-cause-analyzer/
│   └── SKILL.md               # NEW
└── fix-planner/
    └── SKILL.md               # NEW
```

---

## Configuration

Add to `config.yaml`:

```yaml
bug_bash:
  max_reproduction_attempts: 3
  max_analysis_attempts: 2
  reproduction_timeout_seconds: 300
  analysis_timeout_seconds: 300
  planning_timeout_seconds: 300
  auto_approve_low_risk: false
  min_test_cases: 2
```

---

## Integration Points

### Reusable from Existing System
- `CoderAgent` - For applying fix changes
- `VerifierAgent` - For running verification tests
- `LLMClient` - For all agent LLM calls
- `StateStore` pattern - For bug state storage
- File utilities from `utils/fs.py`

### New Components
- `BugResearcherAgent`
- `RootCauseAnalyzerAgent`
- `FixPlannerAgent`
- `BugOrchestrator`
- `BugStateStore`
- CLI `bug` subcommands

---

## Example Workflow

```bash
# 1. Report bug
$ swarm-attack bug init "Login fails when password contains @#$"
Created bug investigation: login-special-chars

# 2. Run analysis
$ swarm-attack bug analyze login-special-chars
[1/3] Reproducing... ✓ Confirmed
[2/3] Analyzing root cause... ✓ Found: sanitize.py:23
[3/3] Planning fix... ✓ 2 files, low risk
Cost: $0.18

# 3. Review
$ swarm-attack bug status login-special-chars
# Shows full status

$ cat .swarm/bugs/login-special-chars/fix-plan.md
# Review the plan

# 4. Approve
$ swarm-attack bug approve login-special-chars
Fix plan approved!

# 5. Implement
$ swarm-attack bug fix login-special-chars
Applying changes... ✓
Running tests... ✓ 3/3 passed
Bug fixed!
```

---

## Implementation Order

1. Data models (`bug_models.py`)
2. State storage (`bug_state_store.py`)
3. Bug Researcher agent + skill
4. Root Cause Analyzer agent + skill
5. Fix Planner agent + skill
6. BugOrchestrator
7. CLI commands
8. Report generation
9. Integration with Coder/Verifier
10. Tests
11. Documentation

---

## Success Criteria

1. All CLI commands work correctly
2. Agents produce accurate, actionable output
3. Approval gate enforced (no implementation without approval)
4. Reuses existing Coder/Verifier for implementation
5. State persists across process restarts
6. Reports are human-readable and useful
7. Unit and integration tests pass
