# LLM Implementation Prompt: Complexity Gate for Swarm Attack

## Your Role

You are implementing the **Complexity Gate** feature for Swarm Attack, an AI-powered multi-agent development automation system. This is a critical coordination layer improvement that prevents issue implementation timeouts.

---

## System Context: What is Swarm Attack?

Swarm Attack orchestrates Claude Code agents to automate feature development:

```
PRD → Spec Debate → Issues → Implementation → Verify → Done
```

### Key Agents in the Pipeline

| Agent | Purpose |
|-------|---------|
| **IssueCreator** | Creates GitHub issues from approved specs |
| **CoderAgent** | Implements issues using TDD (tests + code + iteration) |
| **VerifierAgent** | Runs tests to verify implementations |
| **Orchestrator** | Coordinates the full pipeline |

### Thick-Agent Architecture

The CoderAgent is a "thick" agent that handles the full TDD cycle in a single context window:
1. Read context (issue, spec, integration points)
2. Write tests first (RED phase)
3. Implement code (GREEN phase)
4. Iterate until tests pass

The CoderAgent uses `max_turns` to limit conversation turns with the LLM. Currently set to 10, which is insufficient for complex issues.

---

## The Problem You're Solving

### Symptom
Issue #7 in `chief-of-staff-v2` times out. The CoderAgent exhausts `max_turns=10` before completing implementation.

### Root Cause
Issue #7 requires implementing 8+ methods with 12+ acceptance criteria—too much for 10 LLM turns. The issue creator generates issues without considering the coder's execution capacity. There's no validation between issue creation and implementation.

### Evidence
From `specs/chief-of-staff-v2/issues.json`, Issue #7:
```json
{
  "title": "Implement CheckpointSystem with trigger detection",
  "estimated_size": "medium",
  "dependencies": [6],
  "order": 7
}
```

The issue body includes:
- 6 trigger types to detect (UX_CHANGE, COST_SINGLE, COST_CUMULATIVE, ARCHITECTURE, SCOPE_CHANGE, HICCUP)
- 8+ methods to implement
- Config changes
- Async operations
- Unit tests for each trigger

This is NOT a "medium" issue—it's at least 2-3 issues worth of work.

---

## The Solution: Complexity Gate

### Architecture Overview

```
Issue Creator → Complexity Gate → [OK] → CoderAgent (with adjusted max_turns)
                      ↓
                 [Too Complex]
                      ↓
              Return with split suggestions (or auto-decompose in Phase 3)
```

### Phase 1: Quick Fixes (Implement First)

1. **Increase CoderAgent max_turns**: 10 → 20
   - File: `swarm_attack/agents/coder.py` line 1155
   - Change: `max_turns=10` → `max_turns=20`

2. **Enhance Issue Creator prompt**: Add explicit sizing guidelines
   - File: `swarm_attack/skills/issue-creator/SKILL.md`
   - Add sizing constraints (see spec below)

### Phase 2: Complexity Gate Agent

New agent that runs BEFORE CoderAgent to estimate complexity and decide if the issue needs splitting.

**Key Design Decisions:**
- Uses Haiku model (cheap, fast) for estimation—NOT the same model that will implement
- Tiered approach: heuristics first, LLM only for borderline cases
- Returns actionable split suggestions, not just "too big"

---

## Codebase Structure

```
swarm_attack/
├── agents/
│   ├── base.py              # BaseAgent class (inherit from this)
│   ├── coder.py             # CoderAgent - THE FILE TO MODIFY FOR PHASE 1
│   ├── verifier.py          # VerifierAgent
│   ├── issue_creator.py     # IssueCreatorAgent
│   ├── issue_validator.py   # IssueValidatorAgent (REFERENCE for patterns)
│   ├── gate.py              # GateAgent (REFERENCE for gate pattern)
│   └── complexity_gate.py   # NEW FILE FOR PHASE 2
├── skills/
│   ├── issue-creator/
│   │   └── SKILL.md         # MODIFY FOR PHASE 1
│   ├── issue-validator/
│   │   └── SKILL.md         # REFERENCE
│   └── complexity-gate/
│       └── SKILL.md         # NEW FILE FOR PHASE 2
├── orchestrator.py          # MODIFY FOR PHASE 2 (integrate gate)
├── config.py                # Configuration classes
├── models.py                # Data models
└── llm_clients.py           # LLM client wrappers
```

---

## Implementation Spec

### Phase 1: Quick Fixes

#### 1.1 Increase max_turns in CoderAgent

**File:** `swarm_attack/agents/coder.py`

Find this code around line 1150-1156:
```python
result = self.llm.run(
    prompt,
    allowed_tools=[],
    max_turns=10,
)
```

Change to:
```python
# Allow complex issues to complete - 20 turns for medium/large issues
# Gate validation (Phase 2) will adjust this dynamically
max_turns = context.get("max_turns_override", 20)
result = self.llm.run(
    prompt,
    allowed_tools=[],
    max_turns=max_turns,
)
```

#### 1.2 Add Sizing Guidelines to Issue Creator

**File:** `swarm_attack/skills/issue-creator/SKILL.md`

Add this section after the existing content:

```markdown
## Sizing Guidelines (CRITICAL)

Each issue must be completable by an LLM coder in ~15 conversation turns.

**Sizing Heuristics:**
| Size | Acceptance Criteria | Files | Lines of Code | Methods |
|------|---------------------|-------|---------------|---------|
| Small | 1-4 | 1-2 | ~50 | 1-2 |
| Medium | 5-8 | 2-3 | ~150 | 3-5 |
| Large | 9-12 | 4-6 | ~300 | 6-8 |

**HARD LIMIT: If an issue has >8 acceptance criteria or >6 methods to implement, you MUST split it.**

**Split Strategies:**
1. By layer: data model → API → UI
2. By operation: CRUD operations as separate issues
3. By trigger/case: Split 6 triggers into 2 issues of 3 each
4. By phase: setup/config → core logic → integration

**Example - BAD (too large):**
"Implement CheckpointSystem with trigger detection"
- 6 trigger types
- 8 methods
- Config changes
- 12+ acceptance criteria

**Example - GOOD (properly split):**
Issue 7a: "Implement trigger detection helpers"
- _detect_triggers() method
- 6 trigger type checks (case-insensitive tag matching)
- 4 acceptance criteria

Issue 7b: "Implement checkpoint creation"
- _create_checkpoint(), _build_context(), _build_options(), _build_recommendation()
- 5 acceptance criteria

Issue 7c: "Implement CheckpointSystem public API"
- check_before_execution(), resolve_checkpoint(), update_daily_cost(), reset_daily_cost()
- Config changes (checkpoint_cost_single, checkpoint_cost_daily)
- 5 acceptance criteria
```

### Phase 2: Complexity Gate Agent

#### 2.1 Create ComplexityGateAgent

**File:** `swarm_attack/agents/complexity_gate.py`

```python
"""
Complexity Gate Agent for Feature Swarm.

Pre-execution complexity check that estimates whether an issue is too complex
for the CoderAgent to complete within max_turns. Uses cheap LLM (Haiku) for
estimation to avoid burning expensive Opus tokens on doomed attempts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


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
    """
    Pre-execution complexity check using tiered estimation.

    Strategy:
    1. Heuristic check (free, instant) for obvious cases
    2. LLM estimation (cheap Haiku) for borderline cases

    This prevents expensive Opus tokens being wasted on issues that will
    inevitably timeout due to complexity.
    """

    name = "complexity_gate"

    # Thresholds (tunable based on observed coder performance)
    MAX_ACCEPTANCE_CRITERIA = 10
    MAX_METHODS = 6
    MAX_ESTIMATED_TURNS = 20

    # Heuristic thresholds for instant decisions (no LLM needed)
    INSTANT_PASS_CRITERIA = 5
    INSTANT_PASS_METHODS = 3
    INSTANT_FAIL_CRITERIA = 12
    INSTANT_FAIL_METHODS = 8

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Complexity Gate agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def estimate_complexity(
        self,
        issue: dict[str, Any],
        spec_content: Optional[str] = None,
    ) -> ComplexityEstimate:
        """
        Estimate complexity of an issue before execution.

        Uses tiered approach:
        1. Heuristic check (free, instant) for obvious cases
        2. LLM estimation (cheap Haiku) for borderline cases

        Args:
            issue: Issue dict with title, body, labels, estimated_size
            spec_content: Optional spec for additional context

        Returns:
            ComplexityEstimate with decision and suggestions
        """
        # Extract metrics from issue
        body = issue.get("body", "")
        title = issue.get("title", "")
        estimated_size = issue.get("estimated_size", "medium")

        criteria_count = self._count_acceptance_criteria(body)
        method_count = self._count_methods_to_implement(body)

        self._log("complexity_gate_metrics", {
            "title": title,
            "criteria_count": criteria_count,
            "method_count": method_count,
            "estimated_size": estimated_size,
        })

        # Tier 1: Instant pass (obviously simple)
        if criteria_count <= self.INSTANT_PASS_CRITERIA and method_count <= self.INSTANT_PASS_METHODS:
            return ComplexityEstimate(
                estimated_turns=10,
                complexity_score=0.3,
                needs_split=False,
                split_suggestions=[],
                confidence=0.95,
                reasoning=f"Simple issue: {criteria_count} criteria, {method_count} methods",
            )

        # Tier 2: Instant fail (obviously too complex)
        if criteria_count > self.INSTANT_FAIL_CRITERIA or method_count > self.INSTANT_FAIL_METHODS:
            suggestions = self._generate_split_suggestions(issue, criteria_count, method_count)
            return ComplexityEstimate(
                estimated_turns=35,
                complexity_score=0.9,
                needs_split=True,
                split_suggestions=suggestions,
                confidence=0.95,
                reasoning=f"Too complex: {criteria_count} criteria, {method_count} methods exceeds limits",
            )

        # Tier 3: Borderline - use LLM for refined estimation
        return self._llm_estimate(issue, criteria_count, method_count, spec_content)

    def _count_acceptance_criteria(self, body: str) -> int:
        """Count checkboxes in issue body (acceptance criteria)."""
        # Match markdown checkboxes: - [ ] or - [x]
        pattern = r"- \[[x ]\]"
        matches = re.findall(pattern, body, re.IGNORECASE)
        return len(matches)

    def _count_methods_to_implement(self, body: str) -> int:
        """
        Count method signatures mentioned in issue body.

        Looks for patterns like:
        - `method_name()` or `method_name(args)`
        - `def method_name`
        - `async def method_name`
        - Method names in acceptance criteria
        """
        patterns = [
            r"`(\w+)\([^)]*\)`",  # `method_name()` or `method_name(args)`
            r"(?:async\s+)?def\s+(\w+)",  # def method_name or async def method_name
            r"implement\s+`?(\w+)`?",  # implement method_name
        ]

        methods = set()
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            methods.update(m.lower() for m in matches)

        # Filter out common false positives
        false_positives = {"self", "cls", "none", "true", "false", "dict", "list", "str", "int", "float"}
        methods = methods - false_positives

        return len(methods)

    def _generate_split_suggestions(
        self,
        issue: dict[str, Any],
        criteria_count: int,
        method_count: int,
    ) -> list[str]:
        """Generate actionable split suggestions based on issue content."""
        suggestions = []
        body = issue.get("body", "").lower()

        # Check for trigger patterns (like CheckpointSystem)
        trigger_matches = re.findall(r"(\w+)_trigger|trigger[_\s](\w+)", body, re.IGNORECASE)
        if len(trigger_matches) >= 4:
            suggestions.append(
                f"Split by trigger type: Group {len(trigger_matches)} triggers into 2-3 issues of ~3 triggers each"
            )

        # Check for CRUD patterns
        crud_patterns = ["create", "read", "update", "delete", "get", "set", "add", "remove"]
        crud_found = [p for p in crud_patterns if p in body]
        if len(crud_found) >= 3:
            suggestions.append(
                "Split by operation: Separate CRUD operations into distinct issues"
            )

        # Check for layer patterns
        layer_patterns = ["model", "api", "endpoint", "ui", "frontend", "backend", "database", "config"]
        layers_found = [p for p in layer_patterns if p in body]
        if len(layers_found) >= 2:
            suggestions.append(
                f"Split by layer: Separate {', '.join(layers_found[:3])} into distinct issues"
            )

        # Generic fallback
        if not suggestions:
            if method_count > 6:
                suggestions.append(
                    f"Split by method groups: {method_count} methods → 2-3 issues of ~3 methods each"
                )
            if criteria_count > 8:
                suggestions.append(
                    f"Split by acceptance criteria: {criteria_count} criteria → 2-3 issues of ~4 criteria each"
                )

        return suggestions or ["Consider breaking this issue into smaller, focused pieces"]

    def _llm_estimate(
        self,
        issue: dict[str, Any],
        criteria_count: int,
        method_count: int,
        spec_content: Optional[str] = None,
    ) -> ComplexityEstimate:
        """
        Use LLM for refined complexity estimation on borderline cases.

        Uses Haiku model for cost efficiency.
        """
        if not self._llm:
            # No LLM available - use heuristic fallback
            estimated_turns = 10 + (criteria_count * 1.5) + (method_count * 2)
            needs_split = estimated_turns > self.MAX_ESTIMATED_TURNS
            return ComplexityEstimate(
                estimated_turns=int(estimated_turns),
                complexity_score=min(estimated_turns / 30, 1.0),
                needs_split=needs_split,
                split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
                confidence=0.6,
                reasoning="Heuristic estimate (no LLM available)",
            )

        # Build prompt for Haiku
        prompt = self._build_estimation_prompt(issue, criteria_count, method_count, spec_content)

        try:
            # Use Haiku for cheap estimation
            result = self._llm.run(
                prompt,
                allowed_tools=[],
                max_turns=1,
                model="haiku",  # Cheap, fast model
            )

            # Parse response
            return self._parse_estimation_response(result.text, criteria_count, method_count, issue)

        except Exception as e:
            self._log("complexity_gate_llm_error", {"error": str(e)}, level="warning")
            # Fallback to heuristic
            estimated_turns = 10 + (criteria_count * 1.5) + (method_count * 2)
            needs_split = estimated_turns > self.MAX_ESTIMATED_TURNS
            return ComplexityEstimate(
                estimated_turns=int(estimated_turns),
                complexity_score=min(estimated_turns / 30, 1.0),
                needs_split=needs_split,
                split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
                confidence=0.5,
                reasoning=f"Heuristic fallback after LLM error: {e}",
            )

    def _build_estimation_prompt(
        self,
        issue: dict[str, Any],
        criteria_count: int,
        method_count: int,
        spec_content: Optional[str] = None,
    ) -> str:
        """Build prompt for LLM complexity estimation."""
        spec_section = ""
        if spec_content:
            # Truncate large specs
            truncated = spec_content[:3000] if len(spec_content) > 3000 else spec_content
            spec_section = f"\n\n**Spec Context (truncated):**\n{truncated}"

        return f"""Estimate the complexity of implementing this GitHub issue.

**Issue Title:** {issue.get('title', 'Unknown')}

**Issue Body:**
{issue.get('body', 'No body')}

**Metrics Detected:**
- Acceptance Criteria: {criteria_count}
- Methods to Implement: {method_count}
- Estimated Size: {issue.get('estimated_size', 'medium')}
{spec_section}

**Your Task:**
Estimate how many LLM conversation turns a skilled coder would need to implement this issue,
including writing tests and iterating on failures.

Return ONLY a JSON object (no markdown, no explanation):
{{
  "estimated_turns": <number 5-40>,
  "complexity_score": <float 0.0-1.0>,
  "needs_split": <boolean>,
  "reasoning": "<one sentence explanation>"
}}

Guidelines:
- Simple getter/setter: 5-8 turns
- Standard CRUD method: 8-12 turns
- Complex logic with edge cases: 12-18 turns
- Multiple interconnected methods: 18-25 turns
- System with many triggers/handlers: 25-35 turns

If needs_split is true, the issue exceeds reasonable single-issue complexity."""

    def _parse_estimation_response(
        self,
        response: str,
        criteria_count: int,
        method_count: int,
        issue: dict[str, Any],
    ) -> ComplexityEstimate:
        """Parse LLM response into ComplexityEstimate."""
        import json

        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                needs_split = data.get("needs_split", False)
                return ComplexityEstimate(
                    estimated_turns=data.get("estimated_turns", 15),
                    complexity_score=data.get("complexity_score", 0.5),
                    needs_split=needs_split,
                    split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
                    confidence=0.8,
                    reasoning=data.get("reasoning", "LLM estimate"),
                )
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback if parsing fails
        estimated_turns = 10 + (criteria_count * 1.5) + (method_count * 2)
        needs_split = estimated_turns > self.MAX_ESTIMATED_TURNS
        return ComplexityEstimate(
            estimated_turns=int(estimated_turns),
            complexity_score=min(estimated_turns / 30, 1.0),
            needs_split=needs_split,
            split_suggestions=self._generate_split_suggestions(issue, criteria_count, method_count) if needs_split else [],
            confidence=0.5,
            reasoning="Heuristic fallback after parse error",
        )

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Run complexity estimation for an issue.

        Args:
            context: Dictionary containing:
                - issue: The issue dict to evaluate
                - spec_content: Optional spec content for context

        Returns:
            AgentResult with complexity estimate in output.
        """
        issue = context.get("issue")
        if not issue:
            return AgentResult.failure_result("Missing required context: issue")

        spec_content = context.get("spec_content")

        estimate = self.estimate_complexity(issue, spec_content)

        self._log("complexity_gate_result", {
            "issue_title": issue.get("title", "Unknown"),
            "estimated_turns": estimate.estimated_turns,
            "needs_split": estimate.needs_split,
            "confidence": estimate.confidence,
        })

        return AgentResult.success_result(
            output={
                "estimated_turns": estimate.estimated_turns,
                "complexity_score": estimate.complexity_score,
                "needs_split": estimate.needs_split,
                "split_suggestions": estimate.split_suggestions,
                "confidence": estimate.confidence,
                "reasoning": estimate.reasoning,
            },
            cost_usd=self._total_cost,
        )
```

#### 2.2 Create Complexity Gate Skill Prompt

**File:** `swarm_attack/skills/complexity-gate/SKILL.md`

```markdown
---
name: complexity-gate
description: >
  Estimate issue complexity before implementation to prevent timeouts.
  Uses cheap estimation to save expensive implementation tokens.
allowed-tools: []
---

# Complexity Gate

You estimate whether a GitHub issue is too complex for a single LLM implementation session.

## Task

Given an issue's title, body, and acceptance criteria, estimate:
1. How many LLM turns the implementation would take
2. Whether the issue needs to be split into smaller pieces

## Complexity Guidelines

| Complexity | Turns | Characteristics |
|------------|-------|-----------------|
| Simple | 5-8 | 1-3 criteria, single method, no edge cases |
| Medium | 8-15 | 4-6 criteria, 2-4 methods, standard patterns |
| Complex | 15-25 | 7-10 criteria, 5-7 methods, edge cases |
| Too Large | 25+ | 10+ criteria, 8+ methods, multiple subsystems |

## Output Format

Return ONLY JSON (no markdown, no explanation):

```json
{
  "estimated_turns": 15,
  "complexity_score": 0.5,
  "needs_split": false,
  "reasoning": "Standard CRUD with 5 methods, well-defined interface"
}
```

## Red Flags (likely needs split)

- More than 8 acceptance criteria
- More than 6 methods to implement
- Multiple enum types or trigger handlers
- Changes to config + implementation + tests
- "Implement X with Y integration" (two things at once)
```

#### 2.3 Integrate Gate into Orchestrator

**File:** `swarm_attack/orchestrator.py`

In `_run_implementation_cycle()`, add gate check before coder. Find the section that runs the coder (around line 1754) and add:

```python
# NEW: Run complexity gate before coder (Phase 2)
if self._complexity_gate is None:
    from swarm_attack.agents.complexity_gate import ComplexityGateAgent
    self._complexity_gate = ComplexityGateAgent(self.config, self.logger)

# Load issue data for gate
issue_data = self._load_issue_from_spec(feature_id, issue_number)
if issue_data:
    gate_result = self._complexity_gate.estimate_complexity(issue_data)
    total_cost += self._complexity_gate.get_total_cost()

    if gate_result.needs_split:
        self._log("complexity_gate_reject", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "estimated_turns": gate_result.estimated_turns,
            "suggestions": gate_result.split_suggestions,
        }, level="warning")

        # Option: Return with split instructions (human handles decomposition)
        return (
            False,
            None,
            AgentResult.failure_result(
                f"Issue too complex (estimated {gate_result.estimated_turns} turns). "
                f"Suggestions: {'; '.join(gate_result.split_suggestions)}"
            ),
            total_cost,
        )

    # Adjust max_turns based on gate estimate
    context["max_turns_override"] = min(gate_result.estimated_turns + 5, 30)
    self._log("complexity_gate_pass", {
        "feature_id": feature_id,
        "issue_number": issue_number,
        "estimated_turns": gate_result.estimated_turns,
        "max_turns_override": context["max_turns_override"],
    })
```

Also add the helper method:

```python
def _load_issue_from_spec(self, feature_id: str, issue_number: int) -> Optional[dict[str, Any]]:
    """Load issue data from issues.json for complexity gate."""
    import json
    issues_path = self.config.specs_path / feature_id / "issues.json"
    if not issues_path.exists():
        return None
    try:
        with open(issues_path) as f:
            data = json.load(f)
        for issue in data.get("issues", []):
            if issue.get("order") == issue_number:
                return issue
    except (json.JSONDecodeError, KeyError):
        pass
    return None
```

---

## Testing Your Implementation

### Phase 1 Tests

```bash
# Test increased max_turns
PYTHONPATH=. pytest tests/unit/test_coder_agent.py -v -k "max_turns"

# Test issue creator sizing (manual)
# Verify SKILL.md changes are present
cat swarm_attack/skills/issue-creator/SKILL.md | grep -A 20 "Sizing Guidelines"
```

### Phase 2 Tests

Create `tests/unit/test_complexity_gate.py`:

```python
import pytest
from swarm_attack.agents.complexity_gate import ComplexityGateAgent, ComplexityEstimate

class TestComplexityGate:
    def test_simple_issue_passes(self):
        """Issue with 3 acceptance criteria should pass without LLM."""
        gate = ComplexityGateAgent(config=mock_config)
        issue = {
            "title": "Add helper method",
            "body": "## Acceptance Criteria\n- [ ] Create method\n- [ ] Add tests\n- [ ] Update docs",
        }
        result = gate.estimate_complexity(issue)
        assert not result.needs_split
        assert result.estimated_turns <= 15
        assert result.confidence >= 0.9  # Heuristic confidence

    def test_complex_issue_needs_split(self):
        """Issue with 12+ criteria should need split."""
        gate = ComplexityGateAgent(config=mock_config)
        criteria = "\n".join([f"- [ ] Criterion {i}" for i in range(15)])
        issue = {
            "title": "Implement entire subsystem",
            "body": f"## Acceptance Criteria\n{criteria}",
        }
        result = gate.estimate_complexity(issue)
        assert result.needs_split
        assert len(result.split_suggestions) > 0

    def test_method_counting(self):
        """Should count methods mentioned in issue body."""
        gate = ComplexityGateAgent(config=mock_config)
        body = """
        Implement these methods:
        - `create_user()` for user creation
        - `update_user(id)` for updates
        - `delete_user(id)` for deletion
        - `get_user(id)` for retrieval
        - `list_users()` for listing
        """
        count = gate._count_methods_to_implement(body)
        assert count == 5
```

---

## Files to Create/Modify Summary

| File | Action | Phase |
|------|--------|-------|
| `swarm_attack/agents/coder.py` | Modify line ~1155 | Phase 1 |
| `swarm_attack/skills/issue-creator/SKILL.md` | Add sizing section | Phase 1 |
| `swarm_attack/agents/complexity_gate.py` | Create new file | Phase 2 |
| `swarm_attack/skills/complexity-gate/SKILL.md` | Create new file | Phase 2 |
| `swarm_attack/orchestrator.py` | Add gate integration | Phase 2 |
| `tests/unit/test_complexity_gate.py` | Create tests | Phase 2 |

---

## Success Criteria

1. **Issue 7 completes** without timeout after Phase 1
2. **Gate catches complex issues** before wasting coder tokens
3. **Split suggestions are actionable** (not just "too big")
4. **No false positives** - gate doesn't reject simple issues
5. **Cost efficient** - gate costs <5% of saved failed attempts

---

## Reference Files to Study

Before implementing, read these files for patterns:

1. `swarm_attack/agents/base.py` - BaseAgent class to inherit from
2. `swarm_attack/agents/gate.py` - Existing gate pattern (pre/post coder)
3. `swarm_attack/agents/issue_validator.py` - Similar validation agent
4. `swarm_attack/orchestrator.py` lines 1634-1820 - `_run_implementation_cycle()`
5. `swarm_attack/llm_clients.py` - How to invoke LLM with different models
