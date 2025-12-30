# Phase 2C: Memory-Powered UX Implementation

You are an Expert Review Panel of specialized AI agents tasked with:
1. REVIEW the Memory-Powered UX proposal (Phase 2C)
2. DEBATE integration approach, risks, and alternatives
3. APPROVE or REJECT with clear rationale
4. IMPLEMENT if approved (following TDD methodology)

---

## Review Panel Composition

| Agent                | Role                         | Focus Area                                      |
|----------------------|------------------------------|-------------------------------------------------|
| Architect            | Lead reviewer, system design | Integration seams, coupling, API stability      |
| UX Specialist        | User experience              | Information display, cognitive load, actionability |
| Performance Engineer | Efficiency analysis          | Query overhead, memory growth, latency          |
| Pragmatist           | Reality check                | Minimal changes, backwards compatibility        |
| Champion             | Advocate                     | Value demonstration, concrete use cases         |

---

## Context: Phase 2A + 2B Complete

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
    outcome: str | None  # "success", "failure", "blocked", "applied"
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

def get_global_memory_store() -> MemoryStore: ...  # Singleton accessor
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

### Key Design Decisions from Phase 2B:

1. **Constructor injection** - `memory_store=None` for backwards compatibility
2. **Immediate save()** - Data integrity over batch optimization
3. **Context truncation** - 500 chars for context, 200 chars for notes

---

## Proposal Under Review

### Issue C1: Similar Past Decisions in CheckpointUX

**Category:** High Value, Low Effort

**Problem Statement:**
When a checkpoint is presented to the user, they have no context about how they've
handled similar situations before. This leads to inconsistent decision-making.

**Solution:**
Before displaying a checkpoint, query memory for similar past decisions and show them
as context to help the user decide.

**Target Experience:**
```
⚠️  HICCUP Checkpoint
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Goal failed after retries.
Error: Import failed in test suite

Similar Past Decisions:
  • ✓ Approved - HICCUP: Import error in utils module (2 days ago)
  • ✓ Approved - HICCUP: Test flakiness resolved on retry (5 days ago)
  • ✗ Rejected - HICCUP: Missing dependency in requirements (1 week ago)

Options:
  [1] Proceed - Continue execution (recommended)
  [2] Skip - Skip this goal
  [3] Pause - Pause for manual review

Recommendation: Proceed - Similar errors were resolved by continuing
```

---

### Issue C2: Pre-Implementation Schema Warnings in CoderAgent

**Category:** High Value, Low Effort

**Problem Statement:**
When CoderAgent is about to implement an issue, it has no knowledge of past schema
drift problems. If a class name caused conflicts before, we should warn upfront.

**Solution:**
Before CoderAgent runs, query memory for schema drift entries related to classes
that might be created. If found, inject a warning into the context.

**Target Experience:**
```
## ⚠️ Schema Drift Warnings

The following classes have caused conflicts in past implementations:

| Class Name        | Previous Conflict                          | Recommendation              |
|-------------------|--------------------------------------------|-----------------------------|
| AutopilotSession  | Existed in autopilot_runner.py (Issue #15) | Import, don't recreate      |
| DailyGoal         | Existed in goal_tracker.py (Issue #8)      | Import, don't recreate      |

**Action:** Import these from their existing locations instead of recreating them.
```

---

## Proposed Changes

### Integration 1: CheckpointUX (checkpoint_ux.py)

```python
# File: swarm_attack/chief_of_staff/checkpoint_ux.py

class CheckpointUX:
    def __init__(self, memory_store: MemoryStore | None = None):
        self._memory = memory_store  # NEW: Optional memory store

    def _get_similar_decisions(
        self,
        checkpoint: Checkpoint,
        limit: int = 3,
    ) -> list[dict]:
        """Query memory for similar past checkpoint decisions.

        Args:
            checkpoint: The current checkpoint being displayed.
            limit: Maximum number of similar decisions to return.

        Returns:
            List of dicts with keys: trigger, context_snippet, decision, outcome, age
        """
        if self._memory is None:
            return []

        similar = self._memory.find_similar(
            content={
                "trigger": checkpoint.trigger.value,
                "context": checkpoint.context[:200],
            },
            category="checkpoint_decision",
            limit=limit,
        )

        results = []
        for entry in similar:
            results.append({
                "trigger": entry.content.get("trigger"),
                "context_snippet": entry.content.get("context", "")[:50] + "...",
                "decision": entry.content.get("decision"),
                "outcome": entry.outcome,
                "age": self._format_age(entry.created_at),
            })
        return results

    def _format_similar_decisions(self, similar: list[dict]) -> str:
        """Format similar decisions for display."""
        if not similar:
            return ""

        lines = ["\nSimilar Past Decisions:"]
        for s in similar:
            icon = "✓" if s["decision"] == "Proceed" else "✗"
            status = "Approved" if s["decision"] == "Proceed" else "Rejected"
            lines.append(f"  • {icon} {status} - {s['trigger']}: {s['context_snippet']} ({s['age']})")

        return "\n".join(lines)

    def display_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Display checkpoint with similar past decisions."""
        # ... existing display logic ...

        # NEW: Add similar decisions section
        similar = self._get_similar_decisions(checkpoint)
        similar_text = self._format_similar_decisions(similar)

        # Insert similar_text after context, before options
        return formatted_output + similar_text + options_text
```

### Integration 2: CoderAgent Context (coder.py)

```python
# File: swarm_attack/agents/coder.py

class CoderAgent(BaseAgent):
    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
        memory_store: Optional[MemoryStore] = None,  # NEW
    ):
        super().__init__(config, logger, llm_runner, state_store)
        self._memory = memory_store  # NEW

    def _get_schema_warnings(
        self,
        classes_to_create: list[str],
    ) -> list[dict]:
        """Query memory for past schema drift related to these classes.

        Args:
            classes_to_create: List of class names that might be created.

        Returns:
            List of dicts with keys: class_name, existing_file, existing_issue
        """
        if self._memory is None or not classes_to_create:
            return []

        warnings = []
        for class_name in classes_to_create:
            similar = self._memory.find_similar(
                content={"class_name": class_name},
                category="schema_drift",
                limit=1,
            )
            if similar:
                entry = similar[0]
                warnings.append({
                    "class_name": entry.content.get("class_name"),
                    "existing_file": entry.content.get("existing_file"),
                    "existing_issue": entry.content.get("existing_issue"),
                })
        return warnings

    def _format_schema_warnings(self, warnings: list[dict]) -> str:
        """Format schema warnings for injection into prompt."""
        if not warnings:
            return ""

        lines = [
            "## ⚠️ Schema Drift Warnings",
            "",
            "The following classes have caused conflicts in past implementations:",
            "",
            "| Class Name | Previous Conflict | Recommendation |",
            "|------------|-------------------|----------------|",
        ]

        for w in warnings:
            lines.append(
                f"| {w['class_name']} | Existed in {w['existing_file']} (Issue #{w['existing_issue']}) | Import, don't recreate |"
            )

        lines.extend([
            "",
            "**Action:** Import these from their existing locations instead of recreating them.",
            "",
        ])

        return "\n".join(lines)

    def run(self, context: dict[str, Any]) -> AgentResult:
        # ... existing context loading ...

        # NEW: Get schema warnings if issue mentions potential classes
        potential_classes = self._extract_potential_classes(context.get("issue_body", ""))
        schema_warnings = self._get_schema_warnings(potential_classes)
        warning_text = self._format_schema_warnings(schema_warnings)

        # Inject warnings into prompt context
        enhanced_context = context.copy()
        if warning_text:
            enhanced_context["schema_warnings"] = warning_text

        # ... rest of run() ...
```

---

## Review Protocol

### Phase 1: INDIVIDUAL ASSESSMENT

**Architect Assessment:**
- Are CheckpointUX and CoderAgent the right integration points?
- Is optional injection (memory_store=None) consistent with Phase 2B pattern?
- What's the impact on existing callers?
- Should memory be passed through config instead of constructor?

**UX Specialist Assessment:**
- Is "Similar Past Decisions" placement optimal (after context, before options)?
- Is 3 similar decisions the right limit? (cognitive load)
- Should we show age in relative terms ("2 days ago") or absolute dates?
- For schema warnings, is markdown table format appropriate for CLI output?

**Performance Engineer Assessment:**
- What's the query overhead for find_similar() on each checkpoint?
- Should we cache similar decisions for the session?
- Memory growth impact of adding more categories?

**Pragmatist Assessment:**
- Is this the simplest way to surface memory to users?
- Could we use existing PreferenceLearner instead of raw memory queries?
- Are there simpler alternatives to markdown tables for CLI?

**Champion Assessment:**
- What's the concrete value of showing similar decisions?
- How does this reduce decision fatigue?
- What's the expected consistency improvement in checkpoint decisions?

---

### Phase 2: STRUCTURED DEBATE

**Round 1: Champion presents the case**
> "Similar Past Decisions directly addresses decision fatigue. Currently, users see the
> same HICCUP checkpoint type repeatedly and make inconsistent choices. By showing
> 'You approved 3 similar HICCUP errors before', we create decision momentum.
>
> Schema warnings prevent wasted tokens. If the LLM is about to recreate a class
> that caused conflicts before, we catch it BEFORE burning 50k tokens, not after."

**Round 2: UX Specialist challenges**
> "Three similar decisions might be too many for quick scanning. Consider:
> 1. Show only the MOST similar decision (limit=1) with high confidence
> 2. Or show up to 3 but only if confidence > 0.7
>
> For schema warnings, markdown tables don't render well in plain terminals.
> Consider a simpler format:
> ```
> ⚠️ AutopilotSession already exists in autopilot_runner.py - import it instead
> ⚠️ DailyGoal already exists in goal_tracker.py - import it instead
> ```"

**Round 3: Pragmatist adjudicates**
> "The existing `PreferenceLearner` in `checkpoint_ux.py` already queries for similar
> decisions. We should EXTEND that class rather than adding parallel memory queries.
>
> PreferenceLearner.find_similar_decisions() already exists - modify it to use
> MemoryStore as its backing store, keeping the same API."

**Round 4: Architect synthesizes**
> "APPROVE with modifications:
>
> 1. **CheckpointUX:** Modify existing `PreferenceLearner` to optionally use MemoryStore
>    - Keep existing API: `find_similar_decisions(checkpoint) -> list[SimilarDecision]`
>    - Add `memory_store` parameter to `PreferenceLearner.__init__`
>    - If memory_store provided, query it; else fall back to existing behavior
>
> 2. **CoderAgent:** Add `memory_store` parameter following Phase 2B pattern
>    - Simplify warning format per UX Specialist feedback
>    - Extract potential class names from issue body using regex
>
> 3. **Limit similar decisions to 3** - cognitive load acceptable for important decisions"

---

## Phase 3: DECISION

**APPROVAL CRITERIA:**
- Integration points align with existing architecture
- No breaking changes to existing APIs
- Memory injection is optional (backwards compatible)
- Test coverage for new behavior
- Follows Phase 2B patterns (constructor injection, optional memory)

**DECISION FORMAT:**
APPROVED / APPROVED_WITH_MODIFICATIONS / REJECTED

Rationale: <2-3 sentences>

If approved, proceed to Implementation Phase.

---

## Implementation Phase (If Approved)

### TDD Approach for Phase 2C

#### Test File 1: tests/integration/test_checkpoint_ux_memory.py

```python
"""Integration tests for CheckpointUX -> MemoryStore integration."""

class TestSimilarDecisionsDisplay:
    """Tests for displaying similar past decisions in CheckpointUX."""

    def test_checkpoint_shows_similar_decisions_from_memory(self):
        """Checkpoint display should include similar past decisions."""
        pass

    def test_similar_decisions_limited_to_three(self):
        """At most 3 similar decisions should be shown."""
        pass

    def test_similar_decisions_show_trigger_type(self):
        """Each similar decision should show its trigger type."""
        pass

    def test_similar_decisions_show_outcome(self):
        """Each similar decision should show approved/rejected."""
        pass

    def test_similar_decisions_show_relative_age(self):
        """Each similar decision should show age like '2 days ago'."""
        pass

    def test_no_similar_decisions_when_memory_empty(self):
        """No similar decisions section when memory has no matches."""
        pass

    def test_works_without_memory_store(self):
        """Existing behavior preserved when memory_store=None."""
        pass


class TestPreferenceLearnerMemoryIntegration:
    """Tests for PreferenceLearner using MemoryStore."""

    def test_preference_learner_accepts_memory_store(self):
        """PreferenceLearner should accept memory_store parameter."""
        pass

    def test_preference_learner_queries_memory_for_similar(self):
        """find_similar_decisions should query MemoryStore."""
        pass

    def test_preference_learner_falls_back_without_memory(self):
        """Without memory_store, should use existing behavior."""
        pass
```

#### Test File 2: tests/integration/test_coder_schema_warnings.py

```python
"""Integration tests for CoderAgent schema drift warnings."""

class TestSchemaWarningsExtraction:
    """Tests for extracting potential class names from issue body."""

    def test_extract_class_names_from_interface_contract(self):
        """Should extract class names from ## Interface Contract section."""
        pass

    def test_extract_class_names_from_acceptance_criteria(self):
        """Should extract class names from acceptance criteria."""
        pass

    def test_no_classes_extracted_from_empty_body(self):
        """Empty issue body should return empty list."""
        pass


class TestSchemaWarningsQuery:
    """Tests for querying memory for schema drift warnings."""

    def test_schema_warning_returned_for_known_drift(self):
        """Should return warning when class caused drift before."""
        pass

    def test_no_warning_when_no_past_drift(self):
        """Should return empty when class has no drift history."""
        pass

    def test_warning_includes_existing_file_path(self):
        """Warning should include where the class already exists."""
        pass

    def test_warning_includes_original_issue_number(self):
        """Warning should include which issue created the class."""
        pass


class TestSchemaWarningsInjection:
    """Tests for injecting warnings into CoderAgent context."""

    def test_warnings_injected_into_context(self):
        """Schema warnings should appear in enhanced context."""
        pass

    def test_no_warnings_section_when_no_drift(self):
        """No warnings section when no schema drift history."""
        pass

    def test_coder_works_without_memory_store(self):
        """Existing behavior preserved when memory_store=None."""
        pass

    def test_warning_format_is_readable(self):
        """Warning format should be simple and readable."""
        pass
```

---

## Implementation Steps

1. **Create test files (RED)**
   - `tests/integration/test_checkpoint_ux_memory.py`
   - `tests/integration/test_coder_schema_warnings.py`
   - Run tests - verify they fail

2. **Modify PreferenceLearner** (`swarm_attack/chief_of_staff/checkpoint_ux.py`)
   - Add `memory_store` parameter to `__init__`
   - Modify `find_similar_decisions()` to query memory
   - Keep existing API unchanged

3. **Modify CheckpointUX display**
   - Format similar decisions with trigger, outcome, age
   - Insert after context, before options

4. **Modify CoderAgent** (`swarm_attack/agents/coder.py`)
   - Add `memory_store` parameter to `__init__`
   - Add `_extract_potential_classes()` method
   - Add `_get_schema_warnings()` method
   - Add `_format_schema_warnings()` method
   - Inject warnings into context in `run()`

5. **Run tests - verify they pass (GREEN)**

6. **Run full test suite - verify no regressions**

---

## File Changes Summary

**Modified Files:**
- `swarm_attack/chief_of_staff/checkpoint_ux.py` (~30 lines)
- `swarm_attack/agents/coder.py` (~50 lines)

**New Files:**
- `tests/integration/test_checkpoint_ux_memory.py`
- `tests/integration/test_coder_schema_warnings.py`

---

## Success Metrics

After Phase 2C implementation:

| Metric                              | Target | How to Measure                    |
|-------------------------------------|--------|-----------------------------------|
| Similar decisions shown in checkpoints | Yes    | Visual inspection + tests         |
| Schema warnings shown before coding | Yes    | Visual inspection + tests         |
| Existing tests still pass           | 100%   | pytest full suite                 |
| No performance regression           | <100ms | Checkpoint display timing         |
| Backwards compatible                | Yes    | Existing code works without memory |

---

## Begin Review

Start with Phase 1: Individual Assessments.
Each agent provides their assessment, then proceed to structured debate.
After consensus, proceed to implementation using TDD methodology.
