# Complexity Gate: Pre-Execution Issue Sizing Validation

## Problem Statement

Complex issues in Swarm Attack exceed the CoderAgent's `max_turns=10` limit, causing timeouts. Example: Issue #7 in `chief-of-staff-v2` requires implementing 8+ methods with 12+ acceptance criteria—too much for a single LLM invocation.

**Root Cause**: The issue creator generates issues without considering the coder's execution capacity. There's no validation gate between issue creation and implementation.

## Solution Overview

Implement a **Complexity Gate** that validates issues before execution and triggers automatic decomposition when issues are too complex.

```
Issue Creator → Complexity Gate → [OK] → CoderAgent
                      ↓
                 [Too Complex]
                      ↓
              Issue Decomposer → New Child Issues → Gate
```

## Architecture

### Phase 1: Quick Fixes (Immediate)

1. **Increase CoderAgent max_turns**: 10 → 20
2. **Enhance Issue Creator prompt**: Add explicit sizing guidelines

### Phase 2: Complexity Gate Agent (This Week)

New agent that runs BEFORE CoderAgent:

```python
class ComplexityGateAgent(BaseAgent):
    """
    Pre-execution complexity check using cheap LLM (Haiku).
    Estimates turns needed and triggers decomposition if too complex.
    """

    name = "complexity_gate"
    MODEL = "haiku"  # Cheap, fast estimation

    # Thresholds
    MAX_ACCEPTANCE_CRITERIA = 10
    MAX_ESTIMATED_TURNS = 20
    MAX_METHODS_TO_IMPLEMENT = 6
```

**Gate Decision Flow:**
1. Count acceptance criteria (heuristic, no LLM)
2. Count methods to implement (regex pattern matching)
3. If borderline, use Haiku for refined estimation
4. Return: `{needs_split: bool, estimated_turns: int, split_suggestions: list}`

### Phase 3: Issue Decomposer Agent (Future)

Agent that splits complex issues into 2-4 smaller child issues:

```python
class IssueDecomposerAgent(BaseAgent):
    """
    Splits a complex issue into smaller child issues.
    Preserves dependencies and creates new dependency chain.
    """

    name = "issue_decomposer"
```

## Implementation Details

### File Locations

| Component | Path |
|-----------|------|
| Complexity Gate Agent | `swarm_attack/agents/complexity_gate.py` |
| Gate Skill Prompt | `swarm_attack/skills/complexity-gate/SKILL.md` |
| Issue Decomposer Agent | `swarm_attack/agents/issue_decomposer.py` |
| Decomposer Skill Prompt | `swarm_attack/skills/issue-decomposer/SKILL.md` |
| Orchestrator Integration | `swarm_attack/orchestrator.py` |
| Config Changes | `swarm_attack/config.py` |

### Complexity Gate Agent Interface

```python
@dataclass
class ComplexityEstimate:
    """Result of complexity estimation."""
    estimated_turns: int
    complexity_score: float  # 0.0 - 1.0
    needs_split: bool
    split_suggestions: list[str]  # Empty if needs_split=False
    confidence: float  # 0.0 - 1.0
    reasoning: str


class ComplexityGateAgent(BaseAgent):
    name = "complexity_gate"

    def estimate_complexity(
        self,
        issue: dict[str, Any],
        spec_content: Optional[str] = None,
    ) -> ComplexityEstimate:
        """
        Estimate complexity of an issue before execution.

        Uses tiered approach:
        1. Heuristic check (free, instant)
        2. LLM estimation if borderline (cheap Haiku call)

        Args:
            issue: Issue dict with title, body, acceptance criteria
            spec_content: Optional spec for additional context

        Returns:
            ComplexityEstimate with decision and suggestions
        """
        pass

    def _heuristic_check(self, issue: dict) -> Optional[ComplexityEstimate]:
        """Fast heuristic check without LLM."""
        pass

    def _count_acceptance_criteria(self, body: str) -> int:
        """Count checkboxes in issue body."""
        pass

    def _count_methods_to_implement(self, body: str) -> int:
        """Count method signatures mentioned."""
        pass

    def _llm_estimate(self, issue: dict) -> ComplexityEstimate:
        """Use Haiku for refined estimation."""
        pass
```

### Orchestrator Integration

In `_run_implementation_cycle()`, add gate check before coder:

```python
def _run_implementation_cycle(self, ...):
    # NEW: Run complexity gate before coder
    if self._complexity_gate:
        estimate = self._complexity_gate.estimate_complexity(issue_data)

        if estimate.needs_split:
            self._log("complexity_gate_reject", {
                "issue_number": issue_number,
                "estimated_turns": estimate.estimated_turns,
                "suggestions": estimate.split_suggestions,
            })
            # Option A: Return failure with decomposition instructions
            # Option B: Auto-decompose and retry
            return self._handle_complex_issue(feature_id, issue_number, estimate)

        # Adjust max_turns based on estimate
        context["estimated_turns"] = estimate.estimated_turns
        context["max_turns_override"] = min(estimate.estimated_turns + 5, 30)

    # Existing coder flow...
```

### Enhanced Issue Creator Prompt

Add to `swarm_attack/skills/issue-creator/SKILL.md`:

```markdown
## Sizing Guidelines (CRITICAL)

Each issue must be completable by an LLM coder in ~15 conversation turns.

**Sizing Heuristics:**
| Size | Acceptance Criteria | Files | Lines of Code | Methods |
|------|---------------------|-------|---------------|---------|
| Small | 1-4 | 1-2 | ~50 | 1-2 |
| Medium | 5-8 | 2-3 | ~150 | 3-5 |
| Large | 9-12 | 4-6 | ~300 | 6-8 |

**HARD LIMIT: If an issue has >8 acceptance criteria, you MUST split it.**

**Split Strategies:**
1. By layer: data model → API → UI
2. By operation: CRUD operations as separate issues
3. By trigger/case: Split 6 triggers into 2 issues of 3 each
4. By phase: setup/config → core logic → integration

**Example Split:**
BAD: "Implement CheckpointSystem with 6 trigger types and 8 methods"
GOOD:
- Issue 7a: "Implement trigger detection (_detect_triggers with 6 types)"
- Issue 7b: "Implement checkpoint lifecycle (create, build_context, build_options)"
- Issue 7c: "Implement CheckpointSystem public API (check_before_execution, resolve)"
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_complexity_gate.py

class TestComplexityGate:
    def test_simple_issue_passes(self):
        """Issue with 3 acceptance criteria should pass."""

    def test_complex_issue_needs_split(self):
        """Issue with 12 acceptance criteria should need split."""

    def test_heuristic_avoids_llm_for_obvious_cases(self):
        """Heuristic should handle clear cases without LLM call."""

    def test_split_suggestions_are_actionable(self):
        """Suggestions should reference specific parts to split."""
```

### Integration Tests

```python
# tests/integration/test_complexity_gate_integration.py

class TestComplexityGateOrchestration:
    def test_gate_blocks_complex_issue(self):
        """Orchestrator should stop when gate rejects issue."""

    def test_gate_adjusts_max_turns(self):
        """Coder should receive adjusted max_turns from gate estimate."""
```

## Success Metrics

1. **Issue 7 completes** without timeout after Phase 1
2. **No false positives**: Gate doesn't reject issues that would succeed
3. **Cost efficiency**: Gate calls (Haiku) cost <5% of saved failed attempts (Opus)
4. **Decomposition quality**: Split issues complete successfully on first try

## Dependencies

- Existing: `BaseAgent`, `ClaudeCliRunner`, `SwarmConfig`
- New: Haiku model access via Claude CLI

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Gate is too conservative | Start with high thresholds, tune down based on data |
| Gate is too permissive | Log all estimates, compare to actual turns used |
| Decomposition breaks context | Include parent issue summary in child issues |
| Dependency explosion | Limit to 2-4 children per decomposition |

## Timeline

| Phase | Effort | Impact |
|-------|--------|--------|
| Phase 1: Quick fixes | 30 min | Unblocks issue 7 |
| Phase 2: Complexity Gate | 4-6 hours | Proactive prevention |
| Phase 3: Auto-Decomposer | 1-2 days | Full self-healing |
