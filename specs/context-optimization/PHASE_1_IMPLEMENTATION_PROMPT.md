# Phase 1: Issue-to-Issue Context Implementation

You are an Expert Review Panel of specialized AI agents tasked with:
1. REVIEW the Phase 1 Context Optimization proposal
2. DEBATE integration approach, risks, and alternatives
3. APPROVE or REJECT with clear rationale
4. IMPLEMENT if approved (following TDD methodology)

---

## Review Panel Composition

| Agent                | Role                         | Focus Area                                      |
|----------------------|------------------------------|-------------------------------------------------|
| Architect            | Lead reviewer, system design | Integration seams, coupling, API stability      |
| Context Specialist   | Context flow expert          | Information loss, prompt engineering, token usage |
| Performance Engineer | Efficiency analysis          | Storage overhead, query latency, file I/O       |
| Pragmatist           | Reality check                | Minimal changes, backwards compatibility        |
| Champion             | Advocate                     | Value demonstration, concrete use cases         |

---

## Context: Phase 2A + 2B + 2C Complete

### Phase 2A: MemoryStore (DONE)

```python
# swarm_attack/memory/store.py - IMPLEMENTED
@dataclass
class MemoryEntry:
    id: str
    category: str  # "checkpoint_decision", "schema_drift", "test_failure"
    feature_id: str
    issue_number: int | None
    content: dict[str, Any]
    outcome: str | None
    created_at: str
    tags: list[str]
    hit_count: int = 0

class MemoryStore:
    def add(self, entry: MemoryEntry) -> None: ...
    def query(self, category=None, feature_id=None, tags=None, limit=10) -> list[MemoryEntry]: ...
    def find_similar(self, content: dict, category=None, limit=5) -> list[MemoryEntry]: ...
    def save(self) -> None: ...
    @classmethod
    def load(cls, store_path=None) -> "MemoryStore": ...
```

Storage: `.swarm/memory/memories.json`
Tests: 20 tests passing in `tests/unit/test_memory_store.py`

### Phase 2B: Integration Points (DONE)

```python
# CheckpointSystem now records decisions
CheckpointSystem.__init__(config=None, store=None, memory_store=None)
# resolve_checkpoint() writes to memory: trigger, context, decision, notes

# VerifierAgent now records schema drift
VerifierAgent.__init__(config, logger=None, llm_runner=None, state_store=None, memory_store=None)
# run() writes to memory when schema_conflicts detected
```

Tests: 17 tests passing in `tests/integration/test_memory_integration.py`

### Phase 2C: Memory-Powered UX (DONE)

```python
# PreferenceLearner now queries MemoryStore
PreferenceLearner.__init__(memory_store: MemoryStore | None = None)
# find_similar_decisions() queries memory for past checkpoint decisions

# CheckpointUX now shows relative time
CheckpointUX._format_age(timestamp: str) -> str  # "2 days ago"
# _format_similar_decisions() includes age in output

# CoderAgent now shows schema warnings
CoderAgent.__init__(..., memory_store: MemoryStore | None = None)
# _extract_potential_classes(issue_body) -> list[str]
# _get_schema_warnings(classes) -> list[dict]
# _format_schema_warnings(warnings) -> str
```

Tests: 28 tests passing in `tests/integration/test_checkpoint_ux_memory.py` and `tests/integration/test_coder_schema_warnings.py`

---

## Phase 1 Proposal Under Review

### The Core Problem

**Issue-to-Issue Context Loss:**

Currently, when implementing Issue #2, the CoderAgent has NO visibility into what Issue #1 created:
- What files were created?
- What classes/functions exist?
- What the semantic summary was?

This leads to:
1. **Duplicate class definitions** - Issue #2 recreates `AutopilotSession` that Issue #1 already created
2. **Import failures** - Issue #2 tries to import from non-existent paths
3. **Wasted tokens** - LLM burns context re-discovering what prior issues built

### Proposed Solution: Three Features

---

## Feature 1: Module Registry

**Category:** High Value, Medium Effort

**Problem Statement:**
When Issue N+1 starts, it has no knowledge of what files/classes Issue N created. This causes duplicate definitions and import errors.

**Solution:**
Track what files and classes each issue creates. Make this available to subsequent issues.

**Target Experience:**
```
## Available Modules from Prior Issues

**Issue #1 created:**
- `swarm_attack/models/session.py`
  - Classes: AutopilotSession, SessionState
  - Functions: create_session

**Issue #2 created:**
- `swarm_attack/models/goal.py`
  - Classes: DailyGoal, GoalStatus

You may import from these modules in your implementation.
```

**Interface Contract:**

```python
# File: swarm_attack/context/module_registry.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json


@dataclass
class ModuleEntry:
    """A module (file) created by an issue."""
    file_path: str
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    created_by_issue: int = 0
    feature_id: str = ""
    timestamp: str = ""  # ISO format

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "file_path": self.file_path,
            "classes": self.classes,
            "functions": self.functions,
            "created_by_issue": self.created_by_issue,
            "feature_id": self.feature_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleEntry":
        """Deserialize from dictionary."""
        return cls(
            file_path=data.get("file_path", ""),
            classes=data.get("classes", []),
            functions=data.get("functions", []),
            created_by_issue=data.get("created_by_issue", 0),
            feature_id=data.get("feature_id", ""),
            timestamp=data.get("timestamp", ""),
        )


class ModuleRegistry:
    """Tracks modules created across issues within a feature."""

    def __init__(self, feature_id: str, state_dir: Optional[Path] = None):
        """Initialize registry for a feature.

        Args:
            feature_id: The feature identifier.
            state_dir: Base directory for state files. Defaults to .swarm/state/
        """
        pass

    def register_module(
        self,
        file_path: str,
        created_by_issue: int,
        classes: Optional[list[str]] = None,
        functions: Optional[list[str]] = None,
    ) -> ModuleEntry:
        """Register a new module created by an issue.

        Args:
            file_path: Relative path to the file.
            created_by_issue: Issue number that created this module.
            classes: List of class names defined in the module.
            functions: List of function names defined in the module.

        Returns:
            The created ModuleEntry.
        """
        pass

    def get_modules_for_issue(self, issue_number: int) -> list[ModuleEntry]:
        """Get modules created by a specific issue."""
        pass

    def get_all_modules(self) -> list[ModuleEntry]:
        """Get all registered modules for the feature."""
        pass

    def get_available_imports(self, for_issue: int) -> dict[str, list[str]]:
        """Get imports available to an issue (from prior issues).

        Args:
            for_issue: The issue number requesting available imports.

        Returns:
            Dict mapping file_path to list of importable names.
            Example: {"models/session.py": ["AutopilotSession", "SessionState"]}
        """
        pass

    def format_for_prompt(self, for_issue: int) -> str:
        """Format registry as context string for LLM prompt.

        Args:
            for_issue: Issue number that will receive this context.

        Returns:
            Markdown-formatted string showing available modules.
        """
        pass

    def save(self) -> None:
        """Persist registry to state file."""
        pass

    @classmethod
    def load(cls, feature_id: str, state_dir: Optional[Path] = None) -> "ModuleRegistry":
        """Load existing registry from state file."""
        pass
```

**Storage Location:** `.swarm/state/{feature_id}/module_registry.json`

---

## Feature 2: Completion Tracker

**Category:** High Value, Medium Effort

**Problem Statement:**
Issue N+1 doesn't know the *semantic intent* of what Issue N implemented. File paths aren't enough - we need summaries.

**Solution:**
Record completion summaries after each issue. Show these to subsequent issues.

**Target Experience:**
```
## What Prior Issues Implemented

### Issue #1: Create session management
Created the core session lifecycle with start/stop/resume capabilities.
- Created: `swarm_attack/models/session.py`
- Classes: AutopilotSession, SessionState
- Test: `tests/unit/test_session.py`

### Issue #2: Add goal tracking
Implemented daily goal creation and progress tracking.
- Created: `swarm_attack/models/goal.py`
- Modified: `swarm_attack/models/session.py` (added goal_ids field)
- Classes: DailyGoal, GoalStatus
- Test: `tests/unit/test_goal.py`

Build upon these implementations. Do not recreate existing functionality.
```

**Interface Contract:**

```python
# File: swarm_attack/context/completion_tracker.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json


@dataclass
class CompletionSummary:
    """Summary of a completed issue."""
    issue_number: int
    feature_id: str
    title: str
    completion_summary: str  # What was implemented (1-3 sentences)
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    classes_defined: dict[str, list[str]] = field(default_factory=dict)  # {file_path: [class_names]}
    functions_defined: dict[str, list[str]] = field(default_factory=dict)
    test_file: Optional[str] = None
    completed_at: str = ""  # ISO timestamp

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        pass

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompletionSummary":
        """Deserialize from dictionary."""
        pass


class CompletionTracker:
    """Tracks completion summaries across issues."""

    def __init__(self, feature_id: str, state_dir: Optional[Path] = None):
        """Initialize tracker for a feature."""
        pass

    def record_completion(
        self,
        issue_number: int,
        title: str,
        summary: str,
        files_created: Optional[list[str]] = None,
        files_modified: Optional[list[str]] = None,
        classes_defined: Optional[dict[str, list[str]]] = None,
        functions_defined: Optional[dict[str, list[str]]] = None,
        test_file: Optional[str] = None,
    ) -> CompletionSummary:
        """Record completion of an issue.

        Args:
            issue_number: The completed issue number.
            title: Issue title.
            summary: 1-3 sentence description of what was implemented.
            files_created: List of files created by this issue.
            files_modified: List of files modified by this issue.
            classes_defined: Dict of {file_path: [class_names]}.
            functions_defined: Dict of {file_path: [function_names]}.
            test_file: Path to the test file for this issue.

        Returns:
            The created CompletionSummary.
        """
        pass

    def get_completed_summaries(self, before_issue: Optional[int] = None) -> list[CompletionSummary]:
        """Get summaries of completed issues.

        Args:
            before_issue: If provided, only return summaries for issues < this number.

        Returns:
            List of CompletionSummary objects.
        """
        pass

    def format_for_prompt(self, for_issue: int) -> str:
        """Format summaries as context for LLM prompt.

        Args:
            for_issue: Issue number that will receive this context.

        Returns:
            Markdown-formatted string showing prior completions.
        """
        pass

    def save(self) -> None:
        """Persist to state file."""
        pass

    @classmethod
    def load(cls, feature_id: str, state_dir: Optional[Path] = None) -> "CompletionTracker":
        """Load existing tracker."""
        pass
```

**Storage Location:** `.swarm/state/{feature_id}/completions.json`

---

## Feature 3: Context Builder Integration

**Category:** High Value, Low Effort (if Features 1-2 done)

**Problem Statement:**
CoderAgent currently builds its context without module registry or completion summaries. We need to wire these in.

**Solution:**
Extend `ContextBuilder` to include module registry and completion tracker data in prompts.

**Interface Contract:**

```python
# File: swarm_attack/context_builder.py (MODIFY EXISTING)

class ContextBuilder:
    """Builds context for agent prompts."""

    def __init__(self, config: SwarmConfig):
        """Initialize context builder."""
        pass

    def get_module_registry(self, feature_id: str) -> ModuleRegistry:
        """Get or create module registry for feature."""
        pass

    def get_completion_tracker(self, feature_id: str) -> CompletionTracker:
        """Get or create completion tracker for feature."""
        pass

    def get_completed_summaries(self, feature_id: str, for_issue: int) -> list[dict[str, Any]]:
        """Get completed summaries for issues before for_issue.

        Used by CoderAgent to see what prior issues implemented.

        Returns:
            List of dicts with keys: issue_number, title, completion_summary,
            files_created, classes_defined, etc.
        """
        pass

    def format_issue_context(
        self,
        feature_id: str,
        issue_number: int,
        issue_body: str,
    ) -> str:
        """Format full context for an issue implementation.

        Includes:
        - Project instructions (CLAUDE.md)
        - Available modules from prior issues
        - Completion summaries from prior issues
        - The issue body itself

        Returns:
            Complete context string for LLM prompt.
        """
        pass
```

---

## Integration Points

### 1. CoderAgent Integration

```python
# In swarm_attack/agents/coder.py - MODIFY run() method

def run(self, context: dict[str, Any]) -> AgentResult:
    feature_id = context.get("feature_id")
    issue_number = context.get("issue_number")

    # EXISTING: Load completed summaries (already implemented in Phase 2C prep)
    completed_summaries = context.get("completed_summaries", [])

    # NEW: Also load module registry for available imports
    from swarm_attack.context_builder import ContextBuilder
    ctx_builder = ContextBuilder(self.config)
    module_registry = ctx_builder.get_module_registry(feature_id)
    available_imports = module_registry.format_for_prompt(for_issue=issue_number)

    # Inject into prompt building...
```

### 2. VerifierAgent Integration

```python
# In swarm_attack/agents/verifier.py - MODIFY run() method

def run(self, context: dict[str, Any]) -> AgentResult:
    # ... existing verification logic ...

    if verification_passed:
        # NEW: Record completion
        from swarm_attack.context.completion_tracker import CompletionTracker
        tracker = CompletionTracker.load(feature_id)
        tracker.record_completion(
            issue_number=issue_number,
            title=issue_title,
            summary=self._generate_completion_summary(result),
            files_created=result.output.get("files_created", []),
            classes_defined=result.output.get("classes_defined", {}),
            test_file=str(test_path),
        )
        tracker.save()

        # NEW: Update module registry
        from swarm_attack.context.module_registry import ModuleRegistry
        registry = ModuleRegistry.load(feature_id)
        for file_path, classes in result.output.get("classes_defined", {}).items():
            registry.register_module(
                file_path=file_path,
                created_by_issue=issue_number,
                classes=classes,
            )
        registry.save()
```

### 3. Orchestrator Integration

```python
# In swarm_attack/orchestrator.py - MODIFY _run_coder() or similar

def _run_coder(self, feature_id: str, issue_number: int, ...):
    # NEW: Get completed summaries for context
    from swarm_attack.context_builder import ContextBuilder
    ctx_builder = ContextBuilder(self.config)
    completed_summaries = ctx_builder.get_completed_summaries(
        feature_id=feature_id,
        for_issue=issue_number,
    )

    # Pass to coder context
    context = {
        "feature_id": feature_id,
        "issue_number": issue_number,
        "completed_summaries": completed_summaries,  # NEW
        # ... other context ...
    }

    return self.coder_agent.run(context)
```

---

## Review Protocol

### Phase 1: INDIVIDUAL ASSESSMENT

**Architect Assessment:**
- Are ModuleRegistry and CompletionTracker the right abstractions?
- Is storing per-feature vs globally correct?
- How does this interact with existing StateStore?
- Should we use MemoryStore instead of separate JSON files?

**Context Specialist Assessment:**
- Is `format_for_prompt()` output optimal for LLM consumption?
- Should we limit context size (e.g., only show last 3 issues)?
- How do we handle very large features with 20+ issues?

**Performance Engineer Assessment:**
- What's the I/O overhead of loading registry on each issue?
- Should we cache registries in memory during a feature run?
- Storage growth with many features?

**Pragmatist Assessment:**
- Is this simpler than modifying existing StateStore?
- Could we just use MemoryStore for this instead of new classes?
- What's the minimum viable implementation?

**Champion Assessment:**
- How much token waste does this prevent?
- What's the expected reduction in duplicate class errors?
- What's the ROI on implementation effort?

---

### Phase 2: STRUCTURED DEBATE

**Round 1: Champion presents the case**
> "Issue-to-issue context loss is the #1 cause of schema drift errors. By showing
> Issue N+1 what Issue N created, we prevent duplicate definitions and enable
> proper imports. This directly reduces token waste from failed builds and retries.
>
> Expected impact: 50-70% reduction in schema drift errors."

**Round 2: Pragmatist challenges**
> "We already have StateStore with module tracking. Why not extend that?
> And MemoryStore already tracks schema drift - could we query that for available
> modules instead of a separate registry?"

**Round 3: Context Specialist adjudicates**
> "StateStore tracks *what* was created but not in a format optimized for LLM
> prompts. MemoryStore records *errors* not *successes*. We need both:
> - Successful creation records (what to import)
> - Semantic summaries (what was the intent)
>
> The separate registry is warranted, but it should integrate with existing
> patterns (same state directory, similar persistence approach)."

**Round 4: Architect synthesizes**
> "APPROVE with modifications:
>
> 1. **ModuleRegistry:** Use `.swarm/state/{feature_id}/` (same as StateStore)
> 2. **CompletionTracker:** Same location, integrates with existing state management
> 3. **Context size limit:** Show at most 5 prior issues (token budget)
> 4. **Integration:** ContextBuilder is the right integration point
> 5. **Caching:** Not needed initially - file I/O is fast enough"

---

## Phase 3: DECISION

**APPROVAL CRITERIA:**
- Solves the core problem (issue-to-issue context loss)
- Follows existing patterns (state storage, persistence)
- Backwards compatible (existing features work without migration)
- Test coverage for new behavior
- Integration doesn't break existing CoderAgent/VerifierAgent

**DECISION FORMAT:**
APPROVED / APPROVED_WITH_MODIFICATIONS / REJECTED

Rationale: <2-3 sentences>

If approved, proceed to Implementation Phase.

---

## Implementation Phase (If Approved)

### TDD Approach for Phase 1

#### Test File 1: tests/unit/test_module_registry.py

```python
"""Unit tests for ModuleRegistry - Issue-to-Issue Context."""

class TestModuleEntry:
    """Tests for ModuleEntry dataclass."""

    def test_module_entry_creation(self):
        """Test creating a ModuleEntry with all fields."""
        pass

    def test_module_entry_to_dict(self):
        """Test serializing ModuleEntry to dictionary."""
        pass

    def test_module_entry_from_dict(self):
        """Test deserializing ModuleEntry from dictionary."""
        pass

    def test_module_entry_roundtrip(self):
        """Test to_dict/from_dict roundtrip preserves data."""
        pass


class TestModuleRegistryBasics:
    """Basic tests for ModuleRegistry."""

    def test_init_creates_empty_registry(self):
        """New registry should have no modules."""
        pass

    def test_register_module_adds_entry(self):
        """register_module should add a ModuleEntry."""
        pass

    def test_register_module_returns_entry(self):
        """register_module should return the created ModuleEntry."""
        pass

    def test_get_all_modules(self):
        """get_all_modules should return all registered modules."""
        pass


class TestModuleRegistryIssueFiltering:
    """Tests for issue-based filtering."""

    def test_get_modules_for_issue(self):
        """get_modules_for_issue should return only that issue's modules."""
        pass

    def test_get_available_imports_excludes_current_issue(self):
        """get_available_imports(for_issue=N) should exclude issue N."""
        pass

    def test_get_available_imports_includes_prior_issues(self):
        """get_available_imports(for_issue=N) should include issues < N."""
        pass


class TestModuleRegistryFormatting:
    """Tests for format_for_prompt()."""

    def test_format_for_prompt_empty_registry(self):
        """Empty registry should return appropriate message."""
        pass

    def test_format_for_prompt_shows_classes(self):
        """Formatted output should show class names."""
        pass

    def test_format_for_prompt_shows_issue_numbers(self):
        """Formatted output should show which issue created each module."""
        pass

    def test_format_for_prompt_excludes_current_issue(self):
        """Format for issue N should not show issue N's modules."""
        pass


class TestModuleRegistryPersistence:
    """Tests for save/load."""

    def test_save_creates_file(self):
        """save() should create the JSON file."""
        pass

    def test_load_restores_registry(self):
        """load() should restore saved registry."""
        pass

    def test_load_nonexistent_returns_empty(self):
        """load() for new feature should return empty registry."""
        pass

    def test_save_load_roundtrip(self):
        """Saved and loaded registry should be equivalent."""
        pass
```

#### Test File 2: tests/unit/test_completion_tracker.py

```python
"""Unit tests for CompletionTracker - Issue Completion Summaries."""

class TestCompletionSummary:
    """Tests for CompletionSummary dataclass."""

    def test_completion_summary_creation(self):
        """Test creating a CompletionSummary with all fields."""
        pass

    def test_completion_summary_to_dict(self):
        """Test serializing CompletionSummary to dictionary."""
        pass

    def test_completion_summary_from_dict(self):
        """Test deserializing CompletionSummary from dictionary."""
        pass


class TestCompletionTrackerBasics:
    """Basic tests for CompletionTracker."""

    def test_init_creates_empty_tracker(self):
        """New tracker should have no completions."""
        pass

    def test_record_completion_adds_summary(self):
        """record_completion should add a CompletionSummary."""
        pass

    def test_record_completion_sets_timestamp(self):
        """record_completion should set completed_at timestamp."""
        pass

    def test_get_completed_summaries_returns_all(self):
        """get_completed_summaries() should return all summaries."""
        pass


class TestCompletionTrackerFiltering:
    """Tests for filtering by issue number."""

    def test_get_completed_summaries_before_issue(self):
        """get_completed_summaries(before_issue=N) should exclude issue N."""
        pass

    def test_get_completed_summaries_sorted_by_issue(self):
        """Summaries should be sorted by issue number."""
        pass


class TestCompletionTrackerFormatting:
    """Tests for format_for_prompt()."""

    def test_format_for_prompt_empty_tracker(self):
        """Empty tracker should return appropriate message."""
        pass

    def test_format_for_prompt_shows_summaries(self):
        """Formatted output should include completion summaries."""
        pass

    def test_format_for_prompt_shows_files_created(self):
        """Formatted output should show files created."""
        pass

    def test_format_for_prompt_shows_classes(self):
        """Formatted output should show classes defined."""
        pass

    def test_format_for_prompt_limits_to_5_issues(self):
        """Format should only show last 5 issues to limit context size."""
        pass


class TestCompletionTrackerPersistence:
    """Tests for save/load."""

    def test_save_creates_file(self):
        """save() should create the JSON file."""
        pass

    def test_load_restores_tracker(self):
        """load() should restore saved tracker."""
        pass

    def test_save_load_roundtrip(self):
        """Saved and loaded tracker should be equivalent."""
        pass
```

#### Test File 3: tests/integration/test_context_flow.py

```python
"""Integration tests for end-to-end context flow."""

class TestContextBuilderIntegration:
    """Tests for ContextBuilder with new context sources."""

    def test_get_completed_summaries_returns_list(self):
        """ContextBuilder.get_completed_summaries should return list of dicts."""
        pass

    def test_completed_summaries_format_for_coder(self):
        """Summaries should be in format CoderAgent expects."""
        pass


class TestCoderAgentReceivesContext:
    """Tests that CoderAgent receives new context."""

    def test_coder_context_includes_available_modules(self):
        """CoderAgent prompt should include available modules section."""
        pass

    def test_coder_context_includes_completion_summaries(self):
        """CoderAgent prompt should include completion summaries."""
        pass


class TestVerifierAgentRecordsCompletion:
    """Tests that VerifierAgent records completions."""

    def test_successful_verification_records_completion(self):
        """After verification passes, completion should be recorded."""
        pass

    def test_successful_verification_updates_registry(self):
        """After verification passes, module registry should be updated."""
        pass


class TestEndToEndContextFlow:
    """End-to-end tests for context propagation."""

    def test_issue_2_sees_issue_1_modules(self):
        """After Issue 1 completes, Issue 2 should see its modules."""
        pass

    def test_issue_2_sees_issue_1_summary(self):
        """After Issue 1 completes, Issue 2 should see its summary."""
        pass
```

---

## Implementation Steps

1. **Create directory structure**
   - `swarm_attack/context/` directory
   - `swarm_attack/context/__init__.py`

2. **Create test files (RED)**
   - `tests/unit/test_module_registry.py`
   - `tests/unit/test_completion_tracker.py`
   - `tests/integration/test_context_flow.py`
   - Run tests - verify they fail

3. **Implement ModuleRegistry** (`swarm_attack/context/module_registry.py`)
   - ModuleEntry dataclass
   - ModuleRegistry class with all methods
   - Run unit tests - verify they pass

4. **Implement CompletionTracker** (`swarm_attack/context/completion_tracker.py`)
   - CompletionSummary dataclass
   - CompletionTracker class with all methods
   - Run unit tests - verify they pass

5. **Modify ContextBuilder** (`swarm_attack/context_builder.py`)
   - Add `get_module_registry()` method
   - Add `get_completion_tracker()` method
   - Add `get_completed_summaries()` method

6. **Modify VerifierAgent** (`swarm_attack/agents/verifier.py`)
   - Record completion after successful verification
   - Update module registry with created files

7. **Modify Orchestrator** (`swarm_attack/orchestrator.py`)
   - Pass completed_summaries to CoderAgent context

8. **Run integration tests - verify they pass (GREEN)**

9. **Run full test suite - verify no regressions**

---

## File Changes Summary

**New Files:**
- `swarm_attack/context/__init__.py`
- `swarm_attack/context/module_registry.py` (~150 lines)
- `swarm_attack/context/completion_tracker.py` (~150 lines)
- `tests/unit/test_module_registry.py`
- `tests/unit/test_completion_tracker.py`
- `tests/integration/test_context_flow.py`

**Modified Files:**
- `swarm_attack/context_builder.py` (~30 lines)
- `swarm_attack/agents/verifier.py` (~20 lines)
- `swarm_attack/orchestrator.py` (~10 lines)

---

## Success Metrics

After Phase 1 implementation:

| Metric                                    | Target | How to Measure                    |
|-------------------------------------------|--------|-----------------------------------|
| Module registry populates after issue     | Yes    | Integration test                  |
| Completion summary recorded after verify  | Yes    | Integration test                  |
| Issue N+1 sees Issue N modules            | Yes    | End-to-end test                   |
| Issue N+1 sees Issue N summary            | Yes    | End-to-end test                   |
| Existing tests still pass                 | 100%   | pytest full suite                 |
| No performance regression                 | <200ms | File I/O timing                   |
| Backwards compatible                      | Yes    | Existing features work            |

---

## Begin Review

Start with Phase 1: Individual Assessments.
Each agent provides their assessment, then proceed to structured debate.
After consensus, proceed to implementation using TDD methodology.
