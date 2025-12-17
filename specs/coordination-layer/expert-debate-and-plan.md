# Expert Debate: Agentic Coordination Layer for Swarm Attack

## AUDIT FINDINGS (2025-12-17)

### Executive Summary

A comprehensive code audit revealed **critical gaps** between the original specification and the current implementation. The "thick agent" architecture (where coder does everything) bypasses the intended handoff protocol, leading to context loss, orphaned artifacts, and silent failures.

---

## Current State Assessment

### What EXISTS Today

| Capability | Status | Code Location | How It Works |
|------------|--------|---------------|--------------|
| Test path convention | `_get_default_test_path()` | `agents/coder.py:142`, `agents/verifier.py:56` | Computes `tests/generated/{feature_id}/test_issue_{N}.py` |
| Module registry handoff | Partial | `orchestrator.py:1359-1361` | `module_registry` passes completed modules from prior issues |
| Verifier runs tests | Working | `agents/verifier.py:61-133` | Runs pytest and checks pass/fail |
| Retry on failure | Working | `orchestrator.py:1369-1371` | `max_retries` + `previous_failures` passed to coder |
| State machine phases | Working | `state_machine.py` | `FeaturePhase` enum with transitions |
| Session checkpoints | Working | `session_manager.py` | `checkpoint()` records agent completion |
| Test file existence check | Verifier only | `agents/verifier.py:453-456` | `file_exists(test_path)` before running pytest |

### What's MISSING (Critical Gaps)

| Gap | Impact | Root Cause |
|-----|--------|------------|
| **No explicit test_path injection to coder** | Coder calculates own path, may not match test-writer | Context dict missing `test_path` key |
| **No gate after test-writer** | Tests may not exist/parse when coder runs | No validation between agents |
| **No deterministic pre-coder check** | Agent invents code when test missing | Trust is implicit, not verified |
| **No GitHub issue status updates** | Issues stay in wrong state | `update_issue_status()` not called |
| **No semantic spec validation** | Tests may not match original spec | Only pytest pass/fail checked |
| **Coder writes tests too** | Duplicates/overrides test-writer work | Thick agent design |

---

## Architecture Analysis: The "Thick Agent" Problem

### Current Flow (Problematic)

```
orchestrator._run_implementation_cycle()
    │
    ├── context = {
    │       "feature_id": feature_id,
    │       "issue_number": issue_number,
    │       "regression_test_files": [...],      # For regression
    │       "retry_number": retry_number,
    │       "test_failures": previous_failures,
    │       "module_registry": module_registry,  # From prior issues
    │   }
    │
    │   ⚠️  NO test_path IN CONTEXT!
    │
    ├── coder.run(context)
    │       │
    │       └── Internally: test_path = self._get_default_test_path(...)
    │                       ⚠️  ASSUMES tests exist at convention path
    │
    └── verifier.run(context)
            │
            └── test_path = context.get("test_path") or self._get_default_test_path(...)
                            ⚠️  ALSO computes own path
```

### The Critical Gap

**Line 1363-1374 of `orchestrator.py`:**
```python
context = {
    "feature_id": feature_id,
    "issue_number": issue_number,
    "regression_test_files": regression_test_files,
    "retry_number": retry_number,
    "test_failures": previous_failures or [],
    "module_registry": module_registry,
}
# ⚠️ WHERE IS test_path?!
```

The coder computes its own `test_path` at `agents/coder.py:142-149`:
```python
def _get_default_test_path(
    self, feature_id: str, issue_number: int
) -> Path:
    tests_dir = Path(self.config.repo_root) / "tests" / "generated" / feature_id
    return tests_dir / f"test_issue_{issue_number}.py"
```

If test-writer put tests elsewhere (or didn't create them), coder won't know.

---

## Edge Cases NOT Handled

| Edge Case | Current Behavior | Should Do |
|-----------|-----------------|-----------|
| Test file doesn't exist | Coder writes new tests (or fails) | **GATE**: Block with error message |
| Test file has syntax error | Coder/verifier crashes | **GATE**: `py_compile` check first |
| Test file has 0 tests | Verifier says "0 passed" (success?) | **GATE**: `pytest --collect-only` |
| Tests pass but don't match spec | Marked as done | **Semantic LLM validation** |
| GitHub issue not updated | Stuck in wrong state | **Deterministic status update** |
| Agent outputs wrong file path | Files in wrong place | **Parse + validate output paths** |
| Session interrupted mid-agent | Lock orphaned | Stale lock cleanup (exists now) |
| Test-writer and coder disagree on path | Context loss | **Single source of truth** |

---

## The Problem Statement

**Observed Failures:**
1. Agent writes tests in unexpected location -> next agent can't find them -> makes up code
2. GitHub issues not marked done/progressed correctly
3. Context loss between agents (what was done, where, why)
4. Artifacts created but not discoverable by subsequent agents
5. Work "completed" but not validated before handoff

**Root Cause:** No deterministic handoff protocol between agents. Each agent operates in isolation, hoping the next one figures out what happened.

---

## Expert Panel Debate

### Expert 1: Systems Architect (Distributed Systems Background)

**Perspective:** This is a classic distributed systems coordination problem. You need a **Transaction Coordinator** pattern.

**Recommendation:**
```
Agent A (test-writer)
    |
    v
+-------------------------------------+
|  TRANSACTION COORDINATOR            |
|  1. Validate artifacts exist        |
|  2. Record artifact locations       |
|  3. Update issue state atomically   |
|  4. Prepare context for next agent  |
|  5. COMMIT or ROLLBACK              |
+-------------------------------------+
    |
    v
Agent B (coder)
```

**Key Insight:** Never let an agent "complete" without the coordinator acknowledging receipt of artifacts. This is like a database transaction - either everything commits or nothing does.

**Implementation:** Add a `handoff.json` manifest that each agent MUST produce:
```json
{
  "agent": "test-writer",
  "issue": 4,
  "artifacts_created": [
    {"type": "test_file", "path": "tests/generated/chief-of-staff/test_issue_4.py"},
    {"type": "fixture", "path": "tests/fixtures/issue_4_data.json"}
  ],
  "next_agent_context": {
    "test_file_location": "tests/generated/chief-of-staff/test_issue_4.py",
    "classes_to_implement": ["DailyLogManager"],
    "dependencies": ["pathlib", "datetime"]
  },
  "github_issue_updates": {
    "close": false,
    "add_labels": ["tests-written"],
    "remove_labels": ["ready"],
    "comment": "Tests written at tests/generated/chief-of-staff/test_issue_4.py"
  }
}
```

---

### Expert 2: ML/AI Researcher (LLM Orchestration Specialist)

**Perspective:** The problem isn't coordination - it's **context window management**. Agents lose context because you're not propagating the right information.

**Recommendation:** Implement a **Context Accumulator** pattern.

**Key Insight:** Each agent should receive:
1. **What was done** (previous agent's output summary)
2. **Where artifacts are** (explicit file paths, not "find the tests")
3. **What to do next** (derived from issue + previous work)
4. **Validation criteria** (how to know if YOUR work is correct)

**Implementation:** Create a `session_context.md` that grows with each agent:

```markdown
# Session Context for Issue #4: DailyLogManager

## Completed Steps

### Step 1: Test Generation (COMPLETE)
- **Agent:** test-writer
- **Timestamp:** 2025-12-17T02:30:00Z
- **Artifacts:**
  - `tests/generated/chief-of-staff/test_issue_4.py` (47 lines, 5 test cases)
- **Test Classes:** TestDailyLogManager
- **Test Methods:**
  - test_creates_log_directory
  - test_appends_entry
  - test_retrieves_entries_by_date
  - test_handles_missing_directory
  - test_rotates_logs_weekly

### Step 2: Implementation (IN PROGRESS)
- **Agent:** coder
- **Input:** See artifacts from Step 1
- **Expected Output:**
  - `chief_of_staff/daily_log.py` containing class `DailyLogManager`
- **Validation:** All tests in `test_issue_4.py` must pass

## Current Agent Instructions

You are implementing `DailyLogManager`.

**CRITICAL:** The tests are at `tests/generated/chief-of-staff/test_issue_4.py`.
Do NOT create new tests. Do NOT guess the test location.

Read the test file FIRST, then implement the class to pass those tests.
```

**Why This Works:** The LLM doesn't have to "remember" or "find" anything. The context document tells it exactly what exists and where.

---

### Expert 3: DevOps Engineer (CI/CD Pipeline Expert)

**Perspective:** Treat agent handoffs like CI/CD pipeline stages. Each stage has **gates** and **artifacts**.

**Recommendation:** Implement **Pipeline Gates** with artifact validation.

```
+---------------+     +---------------+     +---------------+
|  test-writer  |---->|    GATE 1     |---->|    coder      |
+---------------+     | - file exists |     +---------------+
                      | - syntax ok   |            |
                      | - >0 tests    |            v
                      +---------------+     +---------------+
                                            |    GATE 2     |
                      +---------------+     | - impl exists |
                      |   verifier    |<----| - tests pass  |
                      +---------------+     +---------------+
```

**Key Insight:** Gates are NOT LLM calls. They're deterministic Python checks:

```python
class Gate:
    def validate_test_writer_output(self, issue_number: int) -> GateResult:
        test_path = f"tests/generated/{feature_id}/test_issue_{issue_number}.py"

        # Check 1: File exists
        if not Path(test_path).exists():
            return GateResult(passed=False, error=f"Test file not found: {test_path}")

        # Check 2: Syntax valid
        result = subprocess.run(["python", "-m", "py_compile", test_path])
        if result.returncode != 0:
            return GateResult(passed=False, error="Test file has syntax errors")

        # Check 3: Has test cases
        result = subprocess.run(["pytest", "--collect-only", "-q", test_path], capture_output=True)
        if "0 tests collected" in result.stdout.decode():
            return GateResult(passed=False, error="Test file has no test cases")

        return GateResult(passed=True, artifacts={"test_path": test_path})
```

**Implementation:** Add gates to your orchestrator flow:
```python
# In orchestrator.py
def run_issue_session(self, ...):
    # Run test-writer agent
    test_result = self._run_test_writer(issue)

    # GATE 1: Validate test-writer output (NOT an LLM call)
    gate1 = self._validate_test_artifacts(issue)
    if not gate1.passed:
        self._mark_issue_blocked(issue, gate1.error)
        return

    # Run coder agent WITH explicit artifact paths from gate
    coder_context = self._build_coder_context(issue, gate1.artifacts)
    impl_result = self._run_coder(issue, coder_context)

    # GATE 2: Validate implementation
    gate2 = self._validate_implementation(issue)
    if not gate2.passed:
        self._retry_or_block(issue, gate2.error)
        return

    # Run verifier...
```

---

### Expert 4: Product Manager (Workflow Automation Expert)

**Perspective:** You're treating GitHub issues as passive data stores. They should be **active workflow artifacts**.

**Recommendation:** Make issues the **single source of truth** for handoff.

**Key Insight:** Every agent should:
1. **Read** the issue for context (what to do, where previous work is)
2. **Update** the issue with what it did (artifact paths, decisions made)
3. **Transition** the issue to next state (label changes, assignment)

**Implementation:** Standardized issue comment format:

```markdown
## Agent Report: test-writer

### Status: COMPLETE

### Artifacts Created
| Type | Path | Validation |
|------|------|------------|
| Test File | `tests/generated/chief-of-staff/test_issue_4.py` | 5 tests collected |
| Fixture | `tests/fixtures/issue_4.json` | Valid JSON |

### Context for Next Agent
- **Implementation Target:** `chief_of_staff/daily_log.py`
- **Class to Implement:** `DailyLogManager`
- **Required Methods:** `create_entry()`, `get_entries()`, `rotate_logs()`

### Validation Criteria
```bash
pytest tests/generated/chief-of-staff/test_issue_4.py -v
# Expected: 5 passed
```

### Next Steps
1. Coder agent should READ `tests/generated/chief-of-staff/test_issue_4.py`
2. Coder agent should CREATE `chief_of_staff/daily_log.py`
3. Coder agent should RUN tests and iterate until passing

---
*Automated by Feature Swarm at 2025-12-17T02:30:00Z*
```

**Why This Works:** The GitHub issue becomes the handoff document. Next agent reads the issue, finds exactly what it needs.

---

### Expert 5: Reliability Engineer (SRE Background)

**Perspective:** You need **observability** before you can fix coordination. You don't know what's failing because you can't see it.

**Recommendation:** Add structured logging and a **coordination dashboard**.

**Key Insight:** Every handoff should emit events that you can query:

```python
def log_handoff(self, from_agent: str, to_agent: str, issue: int, artifacts: dict):
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "agent_handoff",
        "from_agent": from_agent,
        "to_agent": to_agent,
        "issue_number": issue,
        "artifacts": artifacts,
        "artifacts_valid": self._validate_artifacts(artifacts),
        "context_size_bytes": len(json.dumps(artifacts)),
    }
    self._emit_event(event)
```

**Implementation:** Create `.swarm/events/{feature_id}/events.jsonl`:
```jsonl
{"ts":"2025-12-17T02:30:00Z","event":"agent_start","agent":"test-writer","issue":4}
{"ts":"2025-12-17T02:35:00Z","event":"artifact_created","path":"tests/generated/.../test_issue_4.py"}
{"ts":"2025-12-17T02:35:01Z","event":"agent_complete","agent":"test-writer","issue":4,"status":"success"}
{"ts":"2025-12-17T02:35:02Z","event":"gate_check","gate":"test_validation","passed":true}
{"ts":"2025-12-17T02:35:03Z","event":"agent_start","agent":"coder","issue":4,"context":{"test_path":"..."}}
```

**Why This Works:** When something fails, you can trace exactly what happened:
```bash
# What did test-writer create?
grep '"agent":"test-writer"' events.jsonl | grep '"event":"artifact_created"'

# Did the gate pass?
grep '"gate":"test_validation"' events.jsonl

# What context did coder receive?
grep '"agent":"coder"' events.jsonl | grep '"event":"agent_start"' | jq .context
```

---

## Consensus Recommendation

After debate, the experts agree on a **layered approach**:

### Layer 1: Deterministic Gates (Non-LLM)
- File existence checks
- Syntax validation (pytest --collect-only, python -m py_compile)
- Artifact manifest validation
- **Cost:** Zero LLM tokens

### Layer 2: Context Accumulator (Document-based)
- `session_context.md` grows with each agent
- Explicit artifact paths, not "find the tests"
- **Cost:** Adds ~500 tokens per handoff

### Layer 3: LLM Validation (Semantic Check)
- Optional pass to verify "does the test match the spec?"
- Run AFTER deterministic gates pass
- **Cost:** ~2000 tokens per handoff

### Layer 4: GitHub Issue Updates (Source of Truth)
- Structured comments with artifact locations
- Label transitions for workflow state
- **Cost:** Zero LLM tokens (API calls only)

---

## Implementation Plan

### IMMEDIATE: Quick Win (1-2 hours)

**File:** `swarm_attack/orchestrator.py` - Add test_path to context

```python
# In _run_implementation_cycle(), around line 1363:
test_path = Path(self.config.repo_root) / "tests" / "generated" / feature_id / f"test_issue_{issue_number}.py"

context = {
    "feature_id": feature_id,
    "issue_number": issue_number,
    "test_path": str(test_path),  # <-- ADD THIS
    "regression_test_files": regression_test_files,
    "retry_number": retry_number,
    "test_failures": previous_failures or [],
    "module_registry": module_registry,
}

# ALSO add existence check:
if not test_path.exists():
    self._log("test_file_missing", {
        "feature_id": feature_id,
        "issue_number": issue_number,
        "expected_path": str(test_path),
    }, level="error")
    return False, AgentResult.failure_result(f"Test file not found: {test_path}"), 0.0
```

### Phase 1: Deterministic Gates

**File:** `swarm_attack/gates.py`

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Optional
import re

@dataclass
class GateResult:
    passed: bool
    error: Optional[str] = None
    artifacts: Optional[dict] = None

class ValidationGates:
    """Deterministic validation gates between agent phases."""

    def __init__(self, config):
        self.config = config
        self.test_dir = Path(config.repo_root) / "tests" / "generated"
        self.impl_dir = Path(config.repo_root)

    def validate_tests_written(self, feature_id: str, issue_number: int) -> GateResult:
        """Gate after test-writer: verify tests exist and parse."""
        test_path = self.test_dir / feature_id / f"test_issue_{issue_number}.py"

        # Check 1: File exists
        if not test_path.exists():
            return GateResult(
                passed=False,
                error=f"GATE FAILED: Test file not found at {test_path}"
            )

        # Check 2: Syntax valid
        result = subprocess.run(
            ["python", "-m", "py_compile", str(test_path)],
            capture_output=True,
            timeout=30
        )
        if result.returncode != 0:
            return GateResult(
                passed=False,
                error=f"GATE FAILED: Syntax error in {test_path}: {result.stderr.decode()}"
            )

        # Check 3: Has test cases
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", str(test_path)],
            capture_output=True,
            timeout=60
        )
        output = result.stdout.decode()
        if "0 items" in output or "no tests" in output.lower() or result.returncode != 0:
            return GateResult(
                passed=False,
                error=f"GATE FAILED: No tests found in {test_path}"
            )

        # Extract test count
        match = re.search(r"(\d+) items?", output)
        test_count = int(match.group(1)) if match else 0

        return GateResult(
            passed=True,
            artifacts={
                "test_path": str(test_path),
                "test_count": test_count,
            }
        )

    def validate_implementation(self, feature_id: str, issue_number: int,
                                 test_path: str) -> GateResult:
        """Gate after coder: verify implementation exists and tests pass."""

        # Check 1: Test file still exists
        if not Path(test_path).exists():
            return GateResult(
                passed=False,
                error=f"GATE FAILED: Test file disappeared: {test_path}"
            )

        # Check 2: Run tests
        result = subprocess.run(
            ["pytest", test_path, "-v", "--tb=short"],
            capture_output=True,
            timeout=120,
            cwd=self.config.repo_root
        )

        stdout = result.stdout.decode()
        stderr = result.stderr.decode()

        if result.returncode != 0:
            return GateResult(
                passed=False,
                error=f"GATE FAILED: Tests failed\n{stdout}\n{stderr}",
                artifacts={
                    "test_output": stdout,
                    "test_errors": stderr,
                }
            )

        return GateResult(
            passed=True,
            artifacts={
                "test_path": test_path,
                "test_output": stdout,
            }
        )

    def validate_artifact_exists(self, path: str) -> GateResult:
        """Simple check that a file exists."""
        if Path(path).exists():
            return GateResult(passed=True, artifacts={"path": path})
        return GateResult(passed=False, error=f"Artifact not found: {path}")
```

### Phase 2: Context Accumulator

**File:** `swarm_attack/context_manager.py`

```python
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
import json

class ContextAccumulator:
    """Manages handoff context between agents."""

    def __init__(self, swarm_path: Path, feature_id: str):
        self.context_dir = swarm_path / "context" / feature_id
        self.context_file = self.context_dir / "session_context.json"
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if self.context_file.exists():
            self.context = json.loads(self.context_file.read_text())
        else:
            self.context = {"steps": [], "artifacts": {}, "current_step": None}

    def _save(self) -> None:
        self.context_file.write_text(json.dumps(self.context, indent=2))

    def record_agent_completion(
        self,
        agent: str,
        issue_number: int,
        artifacts: dict[str, Any],
        next_agent_context: dict[str, Any]
    ) -> None:
        """Record what an agent did and prepare context for next agent."""
        step = {
            "agent": agent,
            "issue_number": issue_number,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "artifacts": artifacts,
            "next_agent_context": next_agent_context,
        }
        self.context["steps"].append(step)
        self.context["artifacts"].update(artifacts)
        self._save()

    def get_context_for_agent(self, agent: str, issue_number: int) -> dict[str, Any]:
        """Get accumulated context for an agent starting work."""
        # Find the most recent step for this issue
        relevant_steps = [s for s in self.context["steps"]
                         if s["issue_number"] == issue_number]

        if not relevant_steps:
            return {"previous_work": None, "artifacts": {}, "instructions": {}}

        last_step = relevant_steps[-1]

        return {
            "previous_work": {
                "agent": last_step["agent"],
                "artifacts": last_step["artifacts"],
            },
            "artifacts": self.context["artifacts"],
            "instructions": last_step.get("next_agent_context", {}),
        }

    def build_agent_prompt_context(self, agent: str, issue_number: int) -> str:
        """Build a prompt section with context for the agent."""
        ctx = self.get_context_for_agent(agent, issue_number)

        if not ctx["previous_work"]:
            return ""

        lines = [
            "## Context from Previous Agent",
            "",
            f"**Previous Agent:** {ctx['previous_work']['agent']}",
            "",
            "**Artifacts Created:**",
        ]

        for key, value in ctx["previous_work"]["artifacts"].items():
            lines.append(f"- `{key}`: `{value}`")

        if ctx.get("instructions"):
            lines.extend([
                "",
                "**Instructions for You:**",
            ])
            for key, value in ctx["instructions"].items():
                lines.append(f"- {key}: {value}")

        lines.extend([
            "",
            "---",
            "**CRITICAL:** Use the artifact paths above. Do NOT search for files.",
            "Do NOT create new test files if tests already exist.",
            "Do NOT guess file locations - use the explicit paths provided.",
            "",
        ])

        return "\n".join(lines)
```

### Phase 3: Orchestrator Integration

**Modify:** `swarm_attack/orchestrator.py`

```python
# Add to imports
from .gates import ValidationGates, GateResult
from .context_manager import ContextAccumulator

# Add to __init__
self._gates = ValidationGates(self.config)
self._context: Optional[ContextAccumulator] = None

# Modify _run_implementation_cycle to include gates
def _run_implementation_cycle(
    self,
    feature_id: str,
    issue_number: int,
    session_id: str,
    retry_number: int = 0,
    previous_failures: Optional[list[dict[str, Any]]] = None,
) -> tuple[bool, AgentResult, float]:
    """Run one implementation cycle with gates."""

    # Initialize context accumulator if needed
    if self._context is None:
        self._context = ContextAccumulator(self.config.swarm_path, feature_id)

    # Compute expected test path
    test_path = Path(self.config.repo_root) / "tests" / "generated" / feature_id / f"test_issue_{issue_number}.py"

    # GATE 0: Check if test file exists before running coder
    if not test_path.exists():
        error = f"Test file not found at {test_path}. Test-writer may not have run."
        self._log("gate_test_missing", {"test_path": str(test_path), "issue": issue_number}, level="error")
        return False, AgentResult.failure_result(error), 0.0

    # GATE 1: Validate test file (syntax, has tests)
    gate1 = self._gates.validate_tests_written(feature_id, issue_number)
    if not gate1.passed:
        self._log("gate1_failed", {"error": gate1.error, "issue": issue_number}, level="error")
        return False, AgentResult.failure_result(gate1.error), 0.0

    # Record test-writer completion (if not already recorded)
    self._context.record_agent_completion(
        agent="test-writer",
        issue_number=issue_number,
        artifacts={"test_path": str(test_path), "test_count": gate1.artifacts.get("test_count", 0)},
        next_agent_context={
            "action": "implement code to pass tests",
            "test_file_to_satisfy": str(test_path),
        }
    )

    # Build context for coder with explicit test path
    agent_prompt_context = self._context.build_agent_prompt_context("coder", issue_number)

    # Get regression test files and module registry (existing code)
    regression_test_files = self._get_regression_test_files(feature_id)
    module_registry: dict[str, Any] = {}
    if self._state_store:
        module_registry = self._state_store.get_module_registry(feature_id)

    # Build context WITH explicit test_path
    context = {
        "feature_id": feature_id,
        "issue_number": issue_number,
        "test_path": str(test_path),  # <-- CRITICAL ADDITION
        "test_count": gate1.artifacts.get("test_count", 0),
        "regression_test_files": regression_test_files,
        "retry_number": retry_number,
        "test_failures": previous_failures or [],
        "module_registry": module_registry,
        "agent_prompt_context": agent_prompt_context,  # <-- CONTEXT INJECTION
    }
    total_cost = 0.0

    # Run coder (existing code)
    coder_result: Optional[AgentResult] = None
    if self._coder:
        self._coder.reset()
        coder_result = self._coder.run(context)
        total_cost += coder_result.cost_usd

        if self._session_manager:
            self._session_manager.checkpoint(
                session_id, "coder", "complete", cost_usd=coder_result.cost_usd
            )

        if not coder_result.success:
            return False, coder_result, total_cost

    # GATE 2: Validate implementation (tests pass)
    gate2 = self._gates.validate_implementation(feature_id, issue_number, str(test_path))
    if not gate2.passed:
        self._log("gate2_failed", {"error": gate2.error, "issue": issue_number}, level="warning")
        # Don't return failure immediately - let verifier handle retry logic

    # Run verifier (existing code)
    if self._verifier:
        self._verifier.reset()
        verifier_result = self._verifier.run(context)
        total_cost += verifier_result.cost_usd

        if self._session_manager:
            self._session_manager.checkpoint(
                session_id, "verifier", "complete", cost_usd=verifier_result.cost_usd
            )

        # Save issue outputs on success (existing code)
        if verifier_result.success and coder_result and coder_result.output:
            issue_outputs = coder_result.output.get("issue_outputs")
            if issue_outputs and self._state_store:
                self._state_store.save_issue_outputs(
                    feature_id, issue_number, issue_outputs
                )

            # Record successful coder completion
            self._context.record_agent_completion(
                agent="coder",
                issue_number=issue_number,
                artifacts=issue_outputs or {},
                next_agent_context={"status": "implementation_complete"}
            )

        return verifier_result.success, verifier_result, total_cost

    return False, AgentResult.failure_result("No verifier agent configured"), total_cost
```

### Phase 4: GitHub Issue Updates

**Add method to orchestrator:**

```python
def _format_handoff_comment(self, agent: str, artifacts: dict) -> str:
    """Format a standardized handoff comment for GitHub issue."""
    lines = [
        f"## Agent Report: {agent}",
        "",
        "### Artifacts Created",
        "| Type | Path | Status |",
        "|------|------|--------|",
    ]

    for key, value in artifacts.items():
        status = "Exists" if Path(value).exists() else "Missing"
        lines.append(f"| {key} | `{value}` | {status} |")

    lines.extend([
        "",
        "### Validation",
        "```",
        f"Gate check: PASSED",
        f"Artifacts verified: {len(artifacts)}",
        "```",
        "",
        "---",
        f"*Feature Swarm at {datetime.utcnow().isoformat()}Z*",
    ])

    return "\n".join(lines)

def _add_issue_comment(self, issue_number: int, comment: str) -> None:
    """Add a comment to the GitHub issue tracking this work."""
    # Use gh CLI or GitHub API
    # This creates an audit trail in the issue itself
    pass
```

---

## File Structure After Implementation

```
swarm_attack/
├── gates.py                    # NEW: Deterministic validation gates
├── context_manager.py          # NEW: Context accumulation
├── orchestrator.py             # MODIFIED: Integrate gates + context
├── agents/
│   ├── coder.py               # MODIFIED: Read test_path from context
│   └── verifier.py            # MODIFIED: Use test_path from context
└── ...

.swarm/
├── context/
│   └── {feature_id}/
│       └── session_context.json  # NEW: Accumulated context
├── events/
│   └── {feature_id}/
│       └── events.jsonl         # NEW: Event log
└── ...
```

---

## Success Criteria

After implementation, these failure modes should be eliminated:

| Failure Mode | Before | After |
|--------------|--------|-------|
| Tests in wrong location | Agent guesses, fails | Gate blocks, error message shows expected path |
| Next agent can't find tests | Makes up code | Context explicitly provides `test_path` |
| Issue not marked done | Silent failure | Gate updates issue state atomically |
| Work "done" but artifacts missing | Next agent confused | Gate blocks until artifacts exist |
| Context lost between agents | Each agent starts fresh | `session_context.json` accumulates |
| Tests don't match spec | Silently passes | Semantic LLM validation (Layer 3) |

---

## Test Cases for Gates (TDD)

### `tests/unit/test_gates.py`

```python
import pytest
from pathlib import Path
from swarm_attack.gates import ValidationGates, GateResult

@pytest.fixture
def gates(tmp_path, monkeypatch):
    """Create ValidationGates with tmp_path as repo root."""
    class MockConfig:
        repo_root = str(tmp_path)
    return ValidationGates(MockConfig())

# Test 1: GateResult dataclass
def test_gate_result_passed():
    result = GateResult(passed=True, artifacts={"test_path": "/foo/bar.py"})
    assert result.passed is True
    assert result.error is None
    assert result.artifacts["test_path"] == "/foo/bar.py"

def test_gate_result_failed():
    result = GateResult(passed=False, error="File not found")
    assert result.passed is False
    assert result.error == "File not found"

# Test 2: validate_tests_written - file not found
def test_validate_tests_written_file_not_found(gates):
    result = gates.validate_tests_written("nonexistent-feature", 999)
    assert result.passed is False
    assert "not found" in result.error.lower()

# Test 3: validate_tests_written - syntax error
def test_validate_tests_written_syntax_error(tmp_path, gates):
    test_file = tmp_path / "tests" / "generated" / "my-feature" / "test_issue_1.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_broken(\n")  # Invalid syntax

    result = gates.validate_tests_written("my-feature", 1)
    assert result.passed is False
    assert "syntax" in result.error.lower() or "GATE FAILED" in result.error

# Test 4: validate_tests_written - no tests
def test_validate_tests_written_no_tests(tmp_path, gates):
    test_file = tmp_path / "tests" / "generated" / "my-feature" / "test_issue_1.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("# Empty file, no tests\nx = 1\n")

    result = gates.validate_tests_written("my-feature", 1)
    assert result.passed is False
    assert "no test" in result.error.lower() or "GATE FAILED" in result.error

# Test 5: validate_tests_written - success
def test_validate_tests_written_success(tmp_path, gates):
    test_file = tmp_path / "tests" / "generated" / "my-feature" / "test_issue_1.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("""
def test_example():
    assert 1 == 1

def test_another():
    assert True
""")

    result = gates.validate_tests_written("my-feature", 1)
    assert result.passed is True
    assert result.artifacts["test_path"] == str(test_file)
    assert result.artifacts["test_count"] >= 2

# Test 6: validate_implementation - tests pass
def test_validate_implementation_success(tmp_path, gates):
    test_file = tmp_path / "test_passing.py"
    test_file.write_text("def test_pass(): assert True")

    result = gates.validate_implementation("feature", 1, str(test_file))
    assert result.passed is True

# Test 7: validate_implementation - tests fail
def test_validate_implementation_failure(tmp_path, gates):
    test_file = tmp_path / "test_failing.py"
    test_file.write_text("def test_fail(): assert False")

    result = gates.validate_implementation("feature", 1, str(test_file))
    assert result.passed is False
    assert "failed" in result.error.lower() or "FAILED" in result.artifacts.get("test_output", "")
```

### `tests/unit/test_context_manager.py`

```python
import pytest
from pathlib import Path
from swarm_attack.context_manager import ContextAccumulator

# Test 1: Initialize creates directory
def test_context_accumulator_creates_directory(tmp_path):
    ctx = ContextAccumulator(tmp_path, "my-feature")
    assert (tmp_path / "context" / "my-feature").exists()

# Test 2: Record and retrieve agent completion
def test_record_agent_completion(tmp_path):
    ctx = ContextAccumulator(tmp_path, "my-feature")
    ctx.record_agent_completion(
        agent="test-writer",
        issue_number=4,
        artifacts={"test_path": "tests/generated/my-feature/test_issue_4.py"},
        next_agent_context={"action": "implement DailyLogManager"}
    )

    context = ctx.get_context_for_agent("coder", 4)
    assert context["previous_work"]["agent"] == "test-writer"
    assert context["artifacts"]["test_path"] == "tests/generated/my-feature/test_issue_4.py"
    assert context["instructions"]["action"] == "implement DailyLogManager"

# Test 3: Context persists across instances
def test_context_persists(tmp_path):
    ctx1 = ContextAccumulator(tmp_path, "my-feature")
    ctx1.record_agent_completion("test-writer", 4, {"path": "/a/b.py"}, {})

    ctx2 = ContextAccumulator(tmp_path, "my-feature")  # New instance
    context = ctx2.get_context_for_agent("coder", 4)
    assert context["previous_work"]["agent"] == "test-writer"

# Test 4: Build prompt context includes critical warning
def test_build_agent_prompt_context(tmp_path):
    ctx = ContextAccumulator(tmp_path, "my-feature")
    ctx.record_agent_completion(
        agent="test-writer",
        issue_number=4,
        artifacts={"test_path": "tests/generated/my-feature/test_issue_4.py"},
        next_agent_context={"target_file": "my_module/daily_log.py"}
    )

    prompt = ctx.build_agent_prompt_context("coder", 4)

    assert "test-writer" in prompt
    assert "tests/generated/my-feature/test_issue_4.py" in prompt
    assert "CRITICAL" in prompt
    assert "Do NOT" in prompt

# Test 5: Empty context returns gracefully
def test_empty_context(tmp_path):
    ctx = ContextAccumulator(tmp_path, "my-feature")
    context = ctx.get_context_for_agent("coder", 999)
    assert context["previous_work"] is None

    prompt = ctx.build_agent_prompt_context("coder", 999)
    assert prompt == ""
```

---

## Appendix: Why Not Just One LLM Call?

You might think: "Why not just have an LLM check if everything is correct?"

**Problems with LLM-only validation:**
1. **Cost:** Every handoff costs ~2000 tokens
2. **Latency:** 2-5 seconds per check
3. **Reliability:** LLM might say "looks good" when file doesn't exist
4. **Hallucination:** LLM might "remember" a file that was never created

**The right balance:**
- Deterministic gates: "Does the file exist? Does it parse?"
- LLM validation: "Does the test match the spec semantically?"

Use deterministic checks for **existence/syntax**, LLM for **semantics**.

---

## Appendix: Coder Agent Changes

The coder agent (`agents/coder.py`) should be updated to **read test_path from context** instead of computing its own:

```python
# In coder.py, modify to use context test_path
def run(self, context: dict[str, Any]) -> AgentResult:
    # ... existing setup ...

    # Use test_path from context if provided
    test_path_str = context.get("test_path")
    if test_path_str:
        test_path = Path(test_path_str)
    else:
        # Fallback to default (but log warning)
        test_path = self._get_default_test_path(feature_id, issue_number)
        self._log("test_path_fallback", {
            "computed_path": str(test_path),
            "warning": "test_path not in context, using default"
        }, level="warning")

    # Inject agent prompt context if provided
    agent_prompt_context = context.get("agent_prompt_context", "")
    if agent_prompt_context:
        # Prepend to system prompt or add to context
        pass  # Implementation depends on prompt structure
```

---

## Edge Cases & Error Handling (Expert Panel Debate)

### Update: 2025-12-17 - Live Testing Findings

During hands-on PM testing of the swarm system, we discovered critical edge cases that need handling. Below is an expert panel debate on each failure mode and recommended solutions.

---

### Edge Case Category 1: Session & Lock Management

#### EC-1.1: Stale Session Blocking New Work

**Observed Failure:**
```
Session 'sess_20251217_005307_460604' is already active for feature
'chief-of-staff' (working on issue #5)
```

But issue #5 is marked DONE in state file, yet session thinks it's active.

**Expert Debate:**

| Expert | Perspective | Recommendation |
|--------|-------------|----------------|
| **SRE** | This is a distributed systems split-brain problem | Implement session heartbeat with TTL |
| **DevOps** | Session state and task state are out of sync | Single source of truth - session manager IS the authority |
| **Architect** | Lock files without expiry cause orphans | Add timestamp + auto-expire after 4 hours |

**Consensus Solution:**
```python
class SessionManager:
    SESSION_TTL_HOURS = 4  # Sessions expire after 4 hours of inactivity

    def is_session_stale(self, session_id: str) -> bool:
        """Check if session is stale (no activity for TTL period)."""
        session = self.get_session(session_id)
        if not session:
            return True

        last_checkpoint = session.checkpoints[-1] if session.checkpoints else None
        last_activity = last_checkpoint.timestamp if last_checkpoint else session.started_at

        age = datetime.utcnow() - datetime.fromisoformat(last_activity.replace('Z', ''))
        return age.total_seconds() > (self.SESSION_TTL_HOURS * 3600)

    def cleanup_stale_sessions(self, feature_id: str) -> list[str]:
        """Auto-cleanup stale sessions, return list of cleaned session IDs."""
        cleaned = []
        for session in self._get_sessions_for_feature(feature_id):
            if session.status == "active" and self.is_session_stale(session.session_id):
                self._mark_session_interrupted(session.session_id, reason="stale_timeout")
                cleaned.append(session.session_id)
        return cleaned
```

**Recovery Behavior:**
1. Before starting new work, check for stale sessions
2. Auto-cleanup sessions older than TTL
3. Log cleanup events for audit trail
4. CLI: Add `--force` flag to override session lock

---

#### EC-1.2: Session State Mismatch (Task DONE but Session Active)

**Root Cause:** Session completes verifier checkpoint but process dies before marking session complete.

**Solution:**
```python
def _finalize_session_on_task_done(self, session_id: str, issue_number: int):
    """Ensure session is closed when task is marked DONE."""
    session = self._session_manager.get_session(session_id)

    # If verifier completed successfully, session should be closed
    verifier_checkpoint = next(
        (c for c in session.checkpoints if c.agent == "verifier" and c.status == "complete"),
        None
    )

    if verifier_checkpoint:
        self._session_manager.end_session(
            session_id,
            status="complete",
            end_status="success"
        )
```

**Invariant to Enforce:**
- `task.stage == DONE` implies `session.status != "active"`
- Add validation in state machine transitions

---

#### EC-1.3: Multiple Concurrent Runs on Same Feature

**Failure Mode:** Two terminals run `swarm-attack run chief-of-staff`, both try to work on same issue.

**Current Behavior:** Second run fails with lock error (good) but error message is confusing.

**Improved Handling:**
```python
class LockManager:
    def acquire_issue_lock(self, feature_id: str, issue_number: int) -> LockResult:
        lock_path = self._get_lock_path(feature_id, issue_number)

        if lock_path.exists():
            lock_info = json.loads(lock_path.read_text())
            return LockResult(
                acquired=False,
                error=f"Issue #{issue_number} is locked by session '{lock_info['session_id']}' "
                      f"(PID: {lock_info['pid']}, started: {lock_info['started_at']}). "
                      f"Use 'swarm-attack recover {feature_id}' to handle this.",
                lock_holder=lock_info
            )

        # Write lock with metadata
        lock_info = {
            "session_id": self._current_session_id,
            "pid": os.getpid(),
            "started_at": datetime.utcnow().isoformat() + "Z",
            "hostname": socket.gethostname(),
        }
        lock_path.write_text(json.dumps(lock_info))
        return LockResult(acquired=True)
```

---

### Edge Case Category 2: Agent Handoff Failures

#### EC-2.1: Test File Written to Wrong Location

**Failure:** Test-writer puts file at `tests/test_foo.py` instead of `tests/generated/{feature}/test_issue_{N}.py`.

**Detection (Gate):**
```python
def validate_test_location(self, feature_id: str, issue_number: int) -> GateResult:
    expected_path = self._get_expected_test_path(feature_id, issue_number)

    # Check expected location first
    if expected_path.exists():
        return GateResult(passed=True, artifacts={"test_path": str(expected_path)})

    # Search for test file that might be in wrong place
    possible_locations = [
        f"tests/test_issue_{issue_number}.py",
        f"tests/{feature_id}/test_issue_{issue_number}.py",
        f"test_issue_{issue_number}.py",
    ]

    for alt_path in possible_locations:
        if Path(alt_path).exists():
            return GateResult(
                passed=False,
                error=f"Test file found at '{alt_path}' but expected at '{expected_path}'. "
                      f"Moving file automatically.",
                artifacts={"actual_path": alt_path, "expected_path": str(expected_path)},
                recoverable=True,
                recovery_action="move_file"
            )

    return GateResult(
        passed=False,
        error=f"Test file not found at expected location: {expected_path}",
        recoverable=False
    )
```

**Auto-Recovery:**
```python
def _recover_misplaced_test(self, gate_result: GateResult) -> bool:
    """Move test file to correct location if recoverable."""
    if gate_result.recoverable and gate_result.recovery_action == "move_file":
        actual = Path(gate_result.artifacts["actual_path"])
        expected = Path(gate_result.artifacts["expected_path"])

        expected.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(actual, expected)

        self._log("test_file_auto_moved", {
            "from": str(actual),
            "to": str(expected),
        })
        return True
    return False
```

---

#### EC-2.2: Coder Creates Duplicate Tests

**Failure:** Coder agent writes new tests because it didn't see existing ones, overwriting test-writer's work.

**Prevention (in Coder prompt):**
```python
CODER_SYSTEM_PROMPT = """
## CRITICAL RULES

1. **NEVER create new test files.** Tests already exist at the path provided in context.
2. If you cannot find tests at the specified path, STOP and report the error.
3. Do NOT modify test files unless explicitly asked for test fixes.

## Test File Location

The tests for this issue are at: {test_path}

Read this file FIRST before writing any implementation code.
"""
```

**Validation (Post-Coder Gate):**
```python
def validate_tests_unchanged(self, test_path: str, original_hash: str) -> GateResult:
    """Verify coder didn't modify/overwrite test file."""
    current_hash = self._hash_file(test_path)

    if current_hash != original_hash:
        # Check if changes are additions (ok) or modifications (bad)
        diff = self._get_diff(test_path, original_hash)
        if self._is_destructive_change(diff):
            return GateResult(
                passed=False,
                error="Coder modified test file. This is not allowed.",
                artifacts={"diff": diff}
            )

    return GateResult(passed=True)
```

---

#### EC-2.3: Implementation Creates Files in Wrong Module

**Failure:** Coder creates `daily_log.py` in project root instead of `chief_of_staff/daily_log.py`.

**Detection:**
```python
def validate_implementation_location(
    self, feature_id: str, issue_number: int, expected_module: str
) -> GateResult:
    """Verify implementation files are in correct module."""
    # Parse coder output for files created
    created_files = self._parse_coder_output_files()

    for file_path in created_files:
        if not file_path.startswith(expected_module):
            return GateResult(
                passed=False,
                error=f"File '{file_path}' should be in module '{expected_module}'",
                recoverable=True,
                recovery_action="suggest_move"
            )

    return GateResult(passed=True)
```

---

### Edge Case Category 3: State Machine Transitions

#### EC-3.1: Phase Stuck After Failure

**Failure:** Feature stuck in IMPLEMENTING phase even after all retries exhausted.

**Solution:** Add explicit BLOCKED transition:
```python
class StateMachine:
    def handle_implementation_failure(
        self, feature_id: str, issue_number: int, error: str, retry_count: int
    ) -> FeaturePhase:
        """Determine next phase after implementation failure."""

        if retry_count < self.max_retries:
            # Stay in IMPLEMENTING, retry will happen
            return FeaturePhase.IMPLEMENTING

        # Max retries exceeded - transition to BLOCKED
        self._mark_issue_blocked(issue_number, error)

        # Check if other issues can proceed
        ready_issues = self._get_ready_issues(feature_id)
        if ready_issues:
            return FeaturePhase.IMPLEMENTING  # Continue with other issues

        # All issues blocked or waiting on blocked deps
        return FeaturePhase.BLOCKED
```

---

#### EC-3.2: Dependency Chain Blocked

**Failure:** Issue #9 depends on #5, #6, #8. If #5 blocks, #9 should not be attempted.

**Current Behavior:** Prioritization agent might still pick #9.

**Solution:**
```python
def _get_ready_issues(self, feature_id: str) -> list[TaskRef]:
    """Get issues ready for work, respecting blocked dependencies."""
    state = self._state_store.get_state(feature_id)
    ready = []

    for task in state.tasks:
        if task.stage != TaskStage.READY:
            continue

        # Check all dependencies
        deps_satisfied = True
        for dep_num in task.dependencies:
            dep_task = self._get_task(state, dep_num)
            if dep_task.stage == TaskStage.BLOCKED:
                # Dependency is blocked - mark this task as SKIPPED
                self._mark_task_skipped(
                    feature_id, task.issue_number,
                    f"Dependency #{dep_num} is blocked"
                )
                deps_satisfied = False
                break
            elif dep_task.stage != TaskStage.DONE:
                deps_satisfied = False
                break

        if deps_satisfied:
            ready.append(task)

    return ready
```

---

#### EC-3.3: Circular Dependency Detection

**Failure:** Issues accidentally depend on each other in a cycle.

**Validation:**
```python
def validate_no_circular_deps(self, tasks: list[TaskRef]) -> Optional[str]:
    """Detect circular dependencies in task graph."""
    # Build adjacency list
    graph = {t.issue_number: t.dependencies for t in tasks}

    # Topological sort with cycle detection
    visited = set()
    rec_stack = set()

    def has_cycle(node: int, path: list[int]) -> Optional[list[int]]:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for dep in graph.get(node, []):
            if dep not in visited:
                result = has_cycle(dep, path)
                if result:
                    return result
            elif dep in rec_stack:
                # Found cycle
                cycle_start = path.index(dep)
                return path[cycle_start:] + [dep]

        rec_stack.remove(node)
        path.pop()
        return None

    for node in graph:
        if node not in visited:
            cycle = has_cycle(node, [])
            if cycle:
                return f"Circular dependency detected: {' -> '.join(map(str, cycle))}"

    return None
```

---

### Edge Case Category 4: External Failures

#### EC-4.1: LLM API Timeout

**Failure:** Claude API call times out mid-agent execution.

**Handling:**
```python
class ResilientLLMRunner:
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 300  # 5 minutes
    BACKOFF_MULTIPLIER = 2

    def run_with_retry(self, prompt: str, **kwargs) -> ClaudeResult:
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = self._run_single(prompt, timeout=self.TIMEOUT_SECONDS, **kwargs)
                return result
            except TimeoutError as e:
                last_error = e
                wait_time = (self.BACKOFF_MULTIPLIER ** attempt) * 10
                self._log("llm_timeout_retry", {
                    "attempt": attempt + 1,
                    "wait_seconds": wait_time,
                })
                time.sleep(wait_time)
            except RateLimitError as e:
                last_error = e
                # Extract retry-after from response
                wait_time = e.retry_after or 60
                self._log("llm_rate_limit", {"wait_seconds": wait_time})
                time.sleep(wait_time)

        # All retries exhausted
        return ClaudeResult(
            success=False,
            error=f"LLM call failed after {self.MAX_RETRIES} retries: {last_error}"
        )
```

---

#### EC-4.2: Git Worktree Corruption

**Failure:** Worktree gets into inconsistent state (e.g., detached HEAD, uncommitted changes blocking checkout).

**Detection & Recovery:**
```python
def validate_worktree_health(self, worktree_path: str) -> WorktreeStatus:
    """Check worktree is in valid state for work."""
    checks = []

    # Check 1: Worktree exists
    if not Path(worktree_path).exists():
        return WorktreeStatus(healthy=False, error="Worktree path does not exist")

    # Check 2: Not detached HEAD
    result = subprocess.run(
        ["git", "-C", worktree_path, "symbolic-ref", "HEAD"],
        capture_output=True
    )
    if result.returncode != 0:
        checks.append("detached_head")

    # Check 3: No uncommitted changes blocking operations
    result = subprocess.run(
        ["git", "-C", worktree_path, "status", "--porcelain"],
        capture_output=True
    )
    if result.stdout.strip():
        checks.append("uncommitted_changes")

    # Check 4: Can fetch from remote
    result = subprocess.run(
        ["git", "-C", worktree_path, "fetch", "--dry-run"],
        capture_output=True,
        timeout=30
    )
    if result.returncode != 0:
        checks.append("fetch_failed")

    if checks:
        return WorktreeStatus(
            healthy=False,
            issues=checks,
            error=f"Worktree issues: {', '.join(checks)}"
        )

    return WorktreeStatus(healthy=True)

def recover_worktree(self, worktree_path: str, issues: list[str]) -> bool:
    """Attempt automatic recovery of worktree issues."""
    for issue in issues:
        if issue == "uncommitted_changes":
            # Stash changes
            subprocess.run(["git", "-C", worktree_path, "stash", "push", "-m", "auto-stash-recovery"])
        elif issue == "detached_head":
            # Checkout the feature branch
            branch = self._get_expected_branch(worktree_path)
            subprocess.run(["git", "-C", worktree_path, "checkout", branch])

    # Re-validate
    status = self.validate_worktree_health(worktree_path)
    return status.healthy
```

---

#### EC-4.3: Disk Space Exhaustion

**Failure:** Running out of disk space mid-implementation.

**Pre-flight Check:**
```python
def check_disk_space(self, min_free_gb: float = 1.0) -> bool:
    """Verify sufficient disk space before starting work."""
    import shutil

    total, used, free = shutil.disk_usage(self.config.repo_root)
    free_gb = free / (1024 ** 3)

    if free_gb < min_free_gb:
        self._log("disk_space_low", {
            "free_gb": free_gb,
            "required_gb": min_free_gb,
        }, level="error")
        return False

    return True
```

---

### Edge Case Category 5: Test Execution Failures

#### EC-5.1: Tests Hang Indefinitely

**Failure:** Test suite has infinite loop or deadlock, pytest never returns.

**Solution:**
```python
def run_tests_with_timeout(self, test_path: str, timeout_seconds: int = 300) -> TestResult:
    """Run tests with hard timeout."""
    try:
        result = subprocess.run(
            ["pytest", test_path, "-v", "--tb=short", "-x"],  # -x stops on first failure
            capture_output=True,
            timeout=timeout_seconds,
            cwd=self.config.repo_root
        )
        return TestResult(
            success=result.returncode == 0,
            stdout=result.stdout.decode(),
            stderr=result.stderr.decode()
        )
    except subprocess.TimeoutExpired:
        # Kill any remaining pytest processes
        subprocess.run(["pkill", "-f", f"pytest.*{test_path}"], capture_output=True)

        return TestResult(
            success=False,
            error=f"Tests timed out after {timeout_seconds} seconds. "
                  "This may indicate an infinite loop or deadlock.",
            timed_out=True
        )
```

---

#### EC-5.2: Flaky Tests (Pass Sometimes, Fail Others)

**Detection:**
```python
def detect_flaky_tests(self, test_path: str, runs: int = 3) -> FlakyTestReport:
    """Run tests multiple times to detect flakiness."""
    results = []

    for i in range(runs):
        result = self.run_tests_with_timeout(test_path)
        results.append({
            "run": i + 1,
            "passed": result.success,
            "failed_tests": self._extract_failed_tests(result.stdout)
        })

    # Analyze results
    all_passed = all(r["passed"] for r in results)
    all_failed = all(not r["passed"] for r in results)

    if not all_passed and not all_failed:
        # Flaky - some passed, some failed
        flaky_tests = set()
        for r in results:
            if r["failed_tests"]:
                flaky_tests.update(r["failed_tests"])

        return FlakyTestReport(
            is_flaky=True,
            flaky_tests=list(flaky_tests),
            pass_rate=sum(1 for r in results if r["passed"]) / runs
        )

    return FlakyTestReport(is_flaky=False)
```

**Handling:**
- If flaky tests detected, mark issue as NEEDS_REVISION with note
- Require explicit human intervention to proceed

---

#### EC-5.3: Test Import Errors

**Failure:** Tests fail to import due to missing dependencies or circular imports.

**Pre-validation:**
```python
def validate_test_imports(self, test_path: str) -> GateResult:
    """Check test file can be imported without errors."""
    result = subprocess.run(
        ["python", "-c", f"import importlib.util; "
                        f"spec = importlib.util.spec_from_file_location('test', '{test_path}'); "
                        f"module = importlib.util.module_from_spec(spec); "
                        f"spec.loader.exec_module(module)"],
        capture_output=True,
        timeout=30
    )

    if result.returncode != 0:
        error = result.stderr.decode()

        # Parse common import errors
        if "ModuleNotFoundError" in error:
            missing_module = self._extract_missing_module(error)
            return GateResult(
                passed=False,
                error=f"Test file has import error: missing module '{missing_module}'",
                recoverable=True,
                recovery_action="install_dependency",
                artifacts={"missing_module": missing_module}
            )
        elif "ImportError" in error and "circular" in error.lower():
            return GateResult(
                passed=False,
                error="Test file has circular import. Fix the module structure.",
                recoverable=False
            )

    return GateResult(passed=True)
```

---

### Error Handling Philosophy

#### Principle 1: Fail Fast, Fail Loud

```python
# BAD: Silent failure
if not test_path.exists():
    return  # Silently continues

# GOOD: Explicit failure with actionable message
if not test_path.exists():
    raise GateError(
        f"Test file not found at {test_path}. "
        f"Expected test-writer to create this file. "
        f"Run 'swarm-attack status {feature_id}' to check task state."
    )
```

#### Principle 2: Always Recoverable State

Every failure should leave the system in a state where:
1. The user can understand what happened
2. The user can take action to fix it
3. Retrying won't cause duplicate work

```python
def safe_agent_execution(self, agent: BaseAgent, context: dict) -> AgentResult:
    """Execute agent with guaranteed state consistency."""
    checkpoint_id = self._create_checkpoint()

    try:
        result = agent.run(context)
        if result.success:
            self._commit_checkpoint(checkpoint_id)
        else:
            self._rollback_to_checkpoint(checkpoint_id)
        return result
    except Exception as e:
        self._rollback_to_checkpoint(checkpoint_id)
        self._log("agent_exception", {
            "agent": agent.name,
            "error": str(e),
            "checkpoint": checkpoint_id,
        }, level="error")
        return AgentResult.failure_result(f"Agent {agent.name} crashed: {e}")
```

#### Principle 3: Idempotent Operations

Running the same command twice should not cause problems:

```python
def run_implementation(self, feature_id: str, issue_number: int):
    """Idempotent implementation run."""
    # Check if already done
    task = self._get_task(feature_id, issue_number)
    if task.stage == TaskStage.DONE:
        self._log("task_already_done", {"issue": issue_number})
        return  # No-op, already complete

    # Check if can resume
    session = self._get_interrupted_session(feature_id, issue_number)
    if session:
        return self._resume_session(session)

    # Check if already in progress elsewhere
    if self._is_locked(feature_id, issue_number):
        raise AlreadyInProgressError(...)

    # Safe to start fresh
    return self._start_new_session(feature_id, issue_number)
```

---

### Recovery Commands

Add these CLI commands for manual recovery:

```bash
# Clear stale sessions older than 4 hours
swarm-attack cleanup --stale-sessions

# Force-unlock a stuck issue
swarm-attack unlock chief-of-staff --issue 5

# Reset issue to READY state (clears session, keeps artifacts)
swarm-attack reset chief-of-staff --issue 5

# Full reset (deletes generated files, resets to BACKLOG)
swarm-attack reset chief-of-staff --issue 5 --hard

# Show recovery options for a feature
swarm-attack diagnose chief-of-staff

# Non-interactive recovery (auto-choose default option)
swarm-attack recover chief-of-staff --auto
```

---

### Monitoring & Alerting

Add health checks that can be run periodically:

```python
def run_health_checks(self) -> HealthReport:
    """Run all health checks and return report."""
    checks = {
        "stale_sessions": self._check_stale_sessions(),
        "orphan_locks": self._check_orphan_locks(),
        "stuck_features": self._check_stuck_features(),
        "disk_space": self._check_disk_space(),
        "worktree_health": self._check_worktree_health(),
    }

    failed_checks = [k for k, v in checks.items() if not v.passed]

    return HealthReport(
        healthy=len(failed_checks) == 0,
        checks=checks,
        summary=f"{len(checks) - len(failed_checks)}/{len(checks)} checks passed"
    )
```

---

*Document updated with edge cases from live testing - 2025-12-17*
