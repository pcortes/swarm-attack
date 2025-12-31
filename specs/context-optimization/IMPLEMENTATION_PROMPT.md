# Context Optimization Implementation Spec

## Mission

You are the **Tech Lead** governing a team of specialized agents to implement context optimization features for swarm-attack. All implementation follows strict TDD methodology.

---

## Team Structure

### Agent Roles

| Agent | Responsibility | Invocation |
|-------|----------------|------------|
| **Architect** | Design interfaces, define contracts, identify integration points | Use for design decisions |
| **TestWriter** | Write failing tests FIRST (RED phase) | Before any implementation |
| **Coder** | Implement minimal code to pass tests (GREEN phase) | After tests exist |
| **Reviewer** | Validate implementation, check patterns, ensure no regressions | After each feature |
| **Cataloger** | Document deferred work with clear specs | For non-implemented items |

### Workflow Protocol

```
For each feature:
1. Architect → Design interface contracts
2. TestWriter → Write failing tests (RED)
3. Coder → Implement (GREEN)
4. Reviewer → Validate + run full test suite
5. Loop until all tests pass
```

---

## Phase 1: HIGH IMPACT - IMPLEMENT NOW

### Feature 1: Nested Skill Agents Structure

**Goal:** Enable `{skill}/agents/` pattern for modular skill composition

**Interface Contract:**

```python
# File: swarm_attack/skill_loader.py

class SkillLoader:
    """Loads skills and their nested subagents."""

    def load_skill(self, skill_name: str) -> SkillDefinition:
        """Load main skill from .claude/skills/{skill_name}/SKILL.md"""
        pass

    def load_subagent(self, skill_name: str, agent_name: str) -> SkillDefinition:
        """Load nested agent from .claude/skills/{skill_name}/agents/{agent_name}/SKILL.md"""
        pass

    def list_subagents(self, skill_name: str) -> list[str]:
        """List available subagents for a skill."""
        pass

    def has_subagents(self, skill_name: str) -> bool:
        """Check if skill has nested agents directory."""
        pass


@dataclass
class SkillDefinition:
    """Parsed skill with metadata."""
    name: str
    content: str  # Full SKILL.md content
    metadata: dict  # Parsed YAML frontmatter
    subagents: list[str]  # Available nested agents (empty if none)
    path: Path  # Source file path
```

**Pattern Reference:** See existing `swarm_attack/agents/base.py:load_skill()` method

**Acceptance Criteria:**
1. [ ] `SkillLoader.load_skill()` returns `SkillDefinition` with parsed metadata
2. [ ] `SkillLoader.load_subagent()` loads from `{skill}/agents/{agent}/SKILL.md`
3. [ ] `SkillLoader.list_subagents()` returns agent names from `{skill}/agents/` directory
4. [ ] `SkillDefinition.subagents` populated when skill has nested agents
5. [ ] Graceful handling when `agents/` directory doesn't exist
6. [ ] Backward compatible with existing `BaseAgent.load_skill()` usage

**Test File:** `tests/unit/test_skill_loader.py`

**Implementation Notes:**
- Extract skill loading logic from `BaseAgent` into dedicated `SkillLoader` class
- Parse YAML frontmatter using existing pattern in codebase
- Directory structure: `.claude/skills/{skill}/agents/{subagent}/SKILL.md`

---

### Feature 2: Module Registry for Issue-to-Issue Context

**Goal:** Track what files/classes each issue creates, available to subsequent issues

**Interface Contract:**

```python
# File: swarm_attack/context/module_registry.py

@dataclass
class ModuleEntry:
    """A module (file) created by an issue."""
    file_path: str
    classes: list[str]
    functions: list[str]
    created_by_issue: int
    feature_id: str
    timestamp: str  # ISO format


class ModuleRegistry:
    """Tracks modules created across issues within a feature."""

    def __init__(self, feature_id: str, state_dir: Path = None):
        """Initialize registry for a feature."""
        pass

    def register_module(
        self,
        file_path: str,
        created_by_issue: int,
        classes: list[str] = None,
        functions: list[str] = None
    ) -> None:
        """Register a new module created by an issue."""
        pass

    def get_modules_for_issue(self, issue_number: int) -> list[ModuleEntry]:
        """Get modules created by a specific issue."""
        pass

    def get_all_modules(self) -> list[ModuleEntry]:
        """Get all registered modules for the feature."""
        pass

    def get_available_imports(self, for_issue: int) -> dict[str, list[str]]:
        """
        Get imports available to an issue (from prior issues).
        Returns: {file_path: [class_names, function_names]}
        """
        pass

    def format_for_prompt(self, for_issue: int) -> str:
        """Format registry as context string for LLM prompt."""
        pass

    def save(self) -> None:
        """Persist registry to state file."""
        pass

    @classmethod
    def load(cls, feature_id: str, state_dir: Path = None) -> "ModuleRegistry":
        """Load existing registry from state file."""
        pass
```

**Storage Location:** `.swarm/state/{feature_id}/module_registry.json`

**Pattern Reference:** See `swarm_attack/state_store.py` for persistence patterns

**Acceptance Criteria:**
1. [ ] `register_module()` adds entry with file, classes, functions, issue number
2. [ ] `get_available_imports()` returns only modules from issues < current issue
3. [ ] `format_for_prompt()` produces clear context string for LLM
4. [ ] Registry persists to JSON and loads correctly
5. [ ] Empty registry handled gracefully (new features)
6. [ ] Integration with `ContextBuilder` (see Feature 3)

**Test File:** `tests/unit/test_module_registry.py`

**Example Output (format_for_prompt):**
```
## Available Modules from Prior Issues

**Issue #1 created:**
- `swarm_attack/models/issue_output.py`
  - Classes: IssueOutput, TaskStage
  - Functions: parse_issue_body

**Issue #2 created:**
- `swarm_attack/validators/issue_validator.py`
  - Classes: IssueValidator
  - Functions: validate_acceptance_criteria, validate_interface_contract

You may import from these modules in your implementation.
```

---

### Feature 3: Completed Summaries Injection

**Goal:** Each issue sees what prior issues implemented (completion summaries)

**Interface Contract:**

```python
# File: swarm_attack/context/completion_tracker.py

@dataclass
class CompletionSummary:
    """Summary of a completed issue."""
    issue_number: int
    feature_id: str
    title: str
    completion_summary: str  # What was implemented (1-3 sentences)
    files_created: list[str]
    files_modified: list[str]
    classes_defined: dict[str, list[str]]  # {file_path: [class_names]}
    functions_defined: dict[str, list[str]]  # {file_path: [function_names]}
    test_file: str | None
    completed_at: str  # ISO timestamp


class CompletionTracker:
    """Tracks completion summaries across issues."""

    def __init__(self, feature_id: str, state_dir: Path = None):
        pass

    def record_completion(
        self,
        issue_number: int,
        title: str,
        summary: str,
        files_created: list[str] = None,
        files_modified: list[str] = None,
        classes_defined: dict[str, list[str]] = None,
        functions_defined: dict[str, list[str]] = None,
        test_file: str = None
    ) -> CompletionSummary:
        """Record completion of an issue."""
        pass

    def get_completed_summaries(self, before_issue: int = None) -> list[CompletionSummary]:
        """Get summaries of completed issues, optionally filtered."""
        pass

    def format_for_prompt(self, for_issue: int) -> str:
        """Format summaries as context for LLM prompt."""
        pass

    def save(self) -> None:
        """Persist to state file."""
        pass

    @classmethod
    def load(cls, feature_id: str, state_dir: Path = None) -> "CompletionTracker":
        """Load existing tracker."""
        pass


# Integration point
class ContextBuilder:
    """Builds context for agent prompts. MODIFY EXISTING CLASS."""

    def build_coder_context(
        self,
        feature_id: str,
        issue_number: int,
        issue_body: str,
        # NEW PARAMETERS:
        module_registry: ModuleRegistry = None,
        completion_tracker: CompletionTracker = None,
    ) -> dict:
        """
        Build full context for CoderAgent.

        Returns dict with keys:
        - project_instructions: str
        - issue_body: str
        - available_modules: str  # NEW: from ModuleRegistry
        - completed_summaries: str  # NEW: from CompletionTracker
        - feature_id: str
        - issue_number: int
        """
        pass
```

**Storage Location:** `.swarm/state/{feature_id}/completions.json`

**Pattern Reference:**
- See `swarm_attack/context_builder.py` for existing context building
- See `swarm_attack/agents/coder.py` for where context is consumed

**Acceptance Criteria:**
1. [ ] `record_completion()` stores all metadata about completed issue
2. [ ] `get_completed_summaries(before_issue=N)` returns only issues < N
3. [ ] `format_for_prompt()` produces clear context for LLM
4. [ ] Integrates with existing `ContextBuilder.build_coder_context()`
5. [ ] CoderAgent receives completed summaries in its context
6. [ ] Verifier calls `record_completion()` after successful verification

**Test File:** `tests/unit/test_completion_tracker.py`

**Example Output (format_for_prompt):**
```
## What Prior Issues Implemented

### Issue #1: Create IssueOutput dataclass
Created the core data model for issue outputs with serialization support.
- Created: `swarm_attack/models/issue_output.py`
- Classes: IssueOutput, TaskStage
- Test: `tests/unit/test_issue_output.py`

### Issue #2: Add issue validation
Implemented validation for acceptance criteria and interface contracts.
- Created: `swarm_attack/validators/issue_validator.py`
- Modified: `swarm_attack/models/issue_output.py` (added validation hooks)
- Classes: IssueValidator
- Functions: validate_acceptance_criteria, validate_interface_contract
- Test: `tests/unit/test_issue_validator.py`

Build upon these implementations. Do not recreate existing functionality.
```

---

## Integration Requirements

### Wiring It All Together

After implementing Features 1-3, wire them into the existing pipeline:

**1. Update `CoderAgent.run()`:**
```python
# In swarm_attack/agents/coder.py

def run(self, context: dict) -> AgentResult:
    feature_id = context["feature_id"]
    issue_number = context["issue_number"]

    # NEW: Load registries
    module_registry = ModuleRegistry.load(feature_id)
    completion_tracker = CompletionTracker.load(feature_id)

    # NEW: Build enhanced context
    enhanced_context = self.context_builder.build_coder_context(
        feature_id=feature_id,
        issue_number=issue_number,
        issue_body=context["issue_body"],
        module_registry=module_registry,
        completion_tracker=completion_tracker,
    )

    # ... rest of implementation
```

**2. Update `VerifierAgent.run()` to record completions:**
```python
# In swarm_attack/agents/verifier.py

def run(self, context: dict) -> AgentResult:
    # ... existing verification logic ...

    if verification_passed:
        # NEW: Record completion
        tracker = CompletionTracker.load(feature_id)
        tracker.record_completion(
            issue_number=issue_number,
            title=issue_title,
            summary=self._generate_summary(result),
            files_created=result.files_created,
            # ... etc
        )
        tracker.save()

        # NEW: Update module registry
        registry = ModuleRegistry.load(feature_id)
        for file_path in result.files_created:
            registry.register_module(
                file_path=file_path,
                created_by_issue=issue_number,
                classes=self._extract_classes(file_path),
            )
        registry.save()
```

**Acceptance Criteria for Integration:**
1. [ ] CoderAgent receives module registry context in prompt
2. [ ] CoderAgent receives completion summaries in prompt
3. [ ] VerifierAgent records completion after successful verification
4. [ ] VerifierAgent updates module registry with created files
5. [ ] End-to-end: Issue N+1 sees what Issue N created

**Integration Test File:** `tests/integration/test_context_flow.py`

---

## Phase 2: PERSISTENT MEMORY LAYER

### Phase 2A: Memory Store Foundation ✅ COMPLETE

**Status:** Implemented and tested (2025-12-21)

**What Was Built:**
```python
# File: swarm_attack/memory/store.py

@dataclass
class MemoryEntry:
    id: str
    category: str  # "checkpoint_decision", "schema_drift", "test_failure"
    feature_id: str
    issue_number: int | None
    content: dict[str, Any]
    outcome: str | None  # "success", "failure", "blocked", "applied"
    created_at: str
    tags: list[str]
    hit_count: int = 0  # For value measurement

class MemoryStore:
    def add(self, entry: MemoryEntry) -> None: ...
    def query(self, category=None, feature_id=None, tags=None, limit=10) -> list[MemoryEntry]: ...
    def find_similar(self, content: dict, category=None, limit=5) -> list[MemoryEntry]: ...
    def save(self) -> None: ...
    def get_stats(self) -> dict[str, Any]: ...
    @classmethod
    def load(cls, store_path=None) -> "MemoryStore": ...

def get_global_memory_store() -> MemoryStore:
    """Singleton accessor for production convenience."""
    ...
```

**Storage:** `.swarm/memory/memories.json`

**Tests:** 20 unit tests in `tests/unit/test_memory_store.py`

---

### Phase 2B: Memory Integration Points ✅ COMPLETE

**Status:** Implemented and tested (2025-12-21)

**What Was Built:**

1. **CheckpointSystem Integration** (`checkpoints.py:867-929`)
   - Added `memory_store` parameter to `CheckpointSystem.__init__`
   - `resolve_checkpoint()` records decisions to memory layer
   - Records: trigger type, context (truncated to 500 chars), decision, notes

2. **VerifierAgent Integration** (`verifier.py:645-690`)
   - Added `memory_store` parameter to `VerifierAgent.__init__`
   - Schema drift detection records conflicts to memory layer
   - Records: class_name, existing_file, new_file, existing_issue

**Tests:** 17 integration tests in `tests/integration/test_memory_integration.py`

**Design Decisions Made:**

| Decision | Rationale |
|----------|-----------|
| Constructor injection over singleton | Preserves testability; `get_global_memory_store()` for production convenience |
| Memory recording in `run()` not `_check_duplicate_classes()` | Keeps memory at orchestration level, not deep in utility methods |
| Immediate `save()` after `add()` | Data integrity over batch optimization; <100ms overhead acceptable |
| Context truncation (500 chars, notes 200 chars) | Prevents storage bloat while preserving useful context |
| Optional `memory_store=None` parameter | Backwards compatible; existing callers unchanged |

**Learnings:**

1. **Test file existence matters for VerifierAgent tests** - The agent returns early if `test_issue_{N}.py` doesn't exist, before schema drift detection runs
2. **`find_similar()` uses keyword matching** - Returns entries sharing keywords, not exact matches; tests should use `any()` not `all()`
3. **TYPE_CHECKING imports** - Use conditional imports to avoid circular dependencies

---

### Phase 2C: Memory-Powered UX ✅ COMPLETE

**Status:** Implemented and tested (2025-12-22)

**What Was Built:**

1. **PreferenceLearner Memory Integration** (`episodes.py`)
   - Added `memory_store` parameter to `PreferenceLearner.__init__`
   - Added `_query_memory_for_decisions()` for persistent decision history
   - Added `_query_signals_for_decisions()` for legacy in-memory fallback
   - `find_similar_decisions()` now queries MemoryStore for past checkpoint decisions

2. **CheckpointUX Relative Time Display** (`checkpoint_ux.py`)
   - Added `_format_age()` helper method for human-readable timestamps
   - Updated `_format_similar_decisions()` to show "(2 days ago)" format

3. **CoderAgent Schema Warnings** (`coder.py`)
   - Added `memory_store` parameter to `CoderAgent.__init__`
   - Added `_extract_potential_classes()` to find class names in issue body
   - Added `_get_schema_warnings()` to query memory for past schema drift
   - Added `_format_schema_warnings()` for simple CLI-friendly warnings

**Tests:** 28 integration tests passing in:
- `tests/integration/test_checkpoint_ux_memory.py`
- `tests/integration/test_coder_schema_warnings.py`

**Example Output (Similar Past Decisions):**
```
Similar Past Decisions:
  • ✓ Approved - HICCUP: Import error in utils module... (2 days ago)
  • ✗ Rejected - HICCUP: Missing dependency in requirements... (5 days ago)
```

**Example Output (Schema Warnings):**
```
## Schema Drift Warnings

- `AutopilotSession` already exists in `autopilot_runner.py` (Issue #15) - import it instead
```

**See:** `PHASE_2C_IMPLEMENTATION_PROMPT.md` for original spec

---

### Catalog Entry 1: Embedding-Based Similarity (Deferred)

**Category:** Medium Value, Medium Effort

**Description:** Replace keyword-based `find_similar()` with semantic embeddings

**Proposed Approach:**
- Add embedding generation for memory content
- Store embeddings alongside entries
- Use cosine similarity for semantic search

**Dependencies:** Phase 2C complete, evaluate if keyword matching is insufficient

**Estimated Scope:** 2-3 issues

**Spec Location:** `specs/context-optimization/EMBEDDING_SIMILARITY_SPEC.md` (to be written)

---

### Catalog Entry 2: Formalized Agent Contracts

**Category:** ~~High Value, Medium Effort~~ **IMPLEMENTED** (2025-12-22)

**Description:** Add TypedDict/Pydantic validation for all agent input/output

**Proposed Approach:**
- Define `AgentInput` and `AgentOutput` base types
- Each agent declares its contract schema
- Runtime validation before/after agent execution

**Dependencies:** None (can be done independently)

**Estimated Scope:** 2-3 issues

**Spec Location:** `specs/context-optimization/AGENT_CONTRACTS_SPEC.md` (to be written)

<implementation_note>
**IMPLEMENTED: 2025-12-22**

**Files Created:**
- `swarm_attack/contracts.py` - TypedDict-based contracts for all agents
- `tests/unit/test_agent_contracts.py` - 25 unit tests (all passing)

**What Was Implemented:**
1. 5 agent contracts (Coder, Verifier, IssueCreator, SpecAuthor, SpecCritic)
2. `ContractValidator` class with `validate_input()` and `validate_output()` methods
3. `ContractValidationError` exception with detailed error messages
4. `AGENT_CONTRACTS` registry with `get_contract()` and `register_contract()` functions
5. Required/optional key detection using `NotRequired` type hints
6. Type checking for primitive types and generic collections

**Integration Status:** Contracts defined but not yet wired into agent execution.
Next step would be to add validation calls in `BaseAgent.run()` for automatic contract enforcement.
</implementation_note>

---

### Catalog Entry 3: Intelligent Merge Resolution

**Category:** ~~High Value, Medium Effort~~ **DEFERRED** (problem doesn't exist in current architecture)

**Description:** AI-driven conflict resolution with ~98% token savings

**Proposed Approach:**
- Three-tier merge: auto-merge → conflict-only AI → full-file AI
- Only send conflict regions to LLM (not entire files)
- Parallel processing of multiple conflicting files

**Dependencies:** Git integration, may need new agent type

**Estimated Scope:** 3-4 issues

**Spec Location:** `specs/context-optimization/INTELLIGENT_MERGE_SPEC.md` (to be written)

<deferral_note>
**DEFERRED: 2025-12-22**

**Reason:** Research found this feature solves a non-existent problem.

**Findings:**
1. Swarm Attack operates on a **single branch** (master) - no feature branch merging
2. Issues implemented **sequentially** with locking - no parallel branch work
3. Git operations limited to: `git add`, `git commit`, `git stash`, `git log`
4. **Zero evidence** of merge conflicts in event logs, state files, or episode history
5. Recovery skill correctly marks `git_conflict` as "NOT recoverable" for rare edge cases

**Current Handling:** Adequate. `git_conflict` escalates to human (appropriate for rare scenarios).

**When to Revisit:**
- If parallel branch-based implementation is added (multiple agents working on different branches)
- If multi-repo or fork-based workflows are implemented
- If actual merge conflicts start appearing in production logs
</deferral_note>

---

### Catalog Entry 4: Skill-Wrapping Subagent Experiment

**Category:** Worth Testing

**Description:** Test whether wrapping entire skills in outer subagents saves context

**Proposed Approach:**
- Create wrapper agent that invokes skill
- Measure token usage before/after
- Compare visibility/debuggability

**Dependencies:** Feature 1 (nested skill agents)

**Estimated Scope:** 1 issue (experiment)

**Spec Location:** `specs/context-optimization/SKILL_WRAPPING_EXPERIMENT.md` (to be written)

---

### Catalog Entry 5: Extended Iteration Limits

**Category:** Worth Testing

**Description:** Test whether 10-15 iteration cycles (vs current 5) improves success rate

**Proposed Approach:**
- Make iteration limit configurable per issue complexity
- Track success rate at each iteration depth
- Analyze cost vs. benefit

**Dependencies:** None

**Estimated Scope:** 1 issue (experiment + config)

**Spec Location:** `specs/context-optimization/ITERATION_LIMITS_EXPERIMENT.md` (to be written)

---

### Catalog Entry 6: Extended Thinking for Spec Critic

**Category:** Worth Testing

**Description:** Add extended thinking/self-critique to SpecCriticAgent

**Proposed Approach:**
- Enable extended thinking mode for critic
- Compare spec quality scores before/after
- Measure token cost increase

**Dependencies:** Claude API extended thinking support

**Estimated Scope:** 1 issue (experiment)

**Spec Location:** `specs/context-optimization/EXTENDED_THINKING_EXPERIMENT.md` (to be written)

---

## TDD Execution Protocol

### For Each Feature:

```
1. ARCHITECT PHASE (Design)
   - Define interface contracts (as shown above)
   - Identify integration points
   - Document pattern references

2. RED PHASE (Tests First)
   - Create test file: tests/unit/test_{feature}.py
   - Write tests for ALL acceptance criteria
   - Tests MUST fail initially (no implementation exists)
   - Run: pytest tests/unit/test_{feature}.py -v
   - Verify: All tests fail for the RIGHT reasons

3. GREEN PHASE (Minimal Implementation)
   - Implement ONLY enough code to pass tests
   - Follow existing patterns in codebase
   - No premature optimization
   - Run: pytest tests/unit/test_{feature}.py -v
   - Verify: All tests pass

4. REFACTOR PHASE (Clean Up)
   - Clean up implementation if needed
   - Ensure no code duplication
   - Run: pytest tests/ -v (full suite)
   - Verify: No regressions

5. INTEGRATION PHASE (Wire It Up)
   - Connect to existing codebase
   - Update dependent code
   - Run: pytest tests/ -v
   - Verify: Full suite passes
```

### Test Requirements

- Each feature MUST have dedicated test file
- Tests MUST cover all acceptance criteria
- Tests MUST be runnable in isolation
- Integration tests for cross-feature behavior
- No mocking of the classes being tested (test real behavior)

### Success Criteria

Phase 1 is complete when:
1. [ ] All 3 features implemented with passing tests
2. [ ] Integration wiring complete (CoderAgent, VerifierAgent)
3. [ ] End-to-end test passes (issue N+1 sees issue N context)
4. [ ] No regressions in existing test suite
5. [ ] Code reviewed by Reviewer agent

---

## File Structure After Implementation

```
swarm_attack/
├── context/                      # NEW DIRECTORY
│   ├── __init__.py
│   ├── module_registry.py        # Feature 2
│   └── completion_tracker.py     # Feature 3
├── skill_loader.py               # Feature 1
├── agents/
│   ├── coder.py                  # MODIFIED: uses new context
│   └── verifier.py               # MODIFIED: records completions
└── context_builder.py            # MODIFIED: integrates new context

tests/
├── unit/
│   ├── test_skill_loader.py      # Feature 1 tests
│   ├── test_module_registry.py   # Feature 2 tests
│   └── test_completion_tracker.py # Feature 3 tests
└── integration/
    └── test_context_flow.py      # End-to-end integration

.swarm/state/{feature_id}/
├── module_registry.json          # Feature 2 state
└── completions.json              # Feature 3 state
```

---

## Execution Order

1. **Feature 1: SkillLoader** (no dependencies)
2. **Feature 2: ModuleRegistry** (no dependencies)
3. **Feature 3: CompletionTracker** (no dependencies)
4. **Integration: Wire into CoderAgent** (depends on 2, 3)
5. **Integration: Wire into VerifierAgent** (depends on 2, 3)
6. **End-to-end test** (depends on all above)

Features 1-3 can be implemented in parallel by different agents.
Integration must be sequential after features complete.

---

## Begin Implementation

Start with Feature 1 (SkillLoader):
1. Architect: Confirm interface contract above is complete
2. TestWriter: Create `tests/unit/test_skill_loader.py` with failing tests
3. Coder: Implement `swarm_attack/skill_loader.py`
4. Reviewer: Validate and run full test suite

Proceed to Features 2 and 3, then integration.
