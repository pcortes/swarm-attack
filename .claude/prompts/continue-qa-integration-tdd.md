# Expert Team Prompt: Implement QA Pipeline Integration via TDD

You are an expert team of software engineers implementing the QA Agent pipeline integration using TDD for the Adaptive QA Agent system.

---

## Project Context

**Worktree**: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Spec**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a multi-agent QA system that provides adaptive behavioral testing. The core agents and CLI are complete. Now we need to integrate QA into the existing swarm-attack pipelines.

---

## What's Already Complete ✓

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| models.py | `swarm_attack/qa/models.py` | 20 tests | ✓ Complete |
| BehavioralTesterAgent | `swarm_attack/qa/agents/behavioral.py` | 33 tests | ✓ Complete |
| ContractValidatorAgent | `swarm_attack/qa/agents/contract.py` | 45 tests | ✓ Complete |
| RegressionScannerAgent | `swarm_attack/qa/agents/regression.py` | 53 tests | ✓ Complete |
| QAOrchestrator | `swarm_attack/qa/orchestrator.py` | 65 tests | ✓ Complete |
| Skill SKILL.md files | `.claude/skills/qa-*` | N/A | ✓ Complete |
| QA CLI Commands | `swarm_attack/cli/qa_commands.py` | 37 tests | ✓ Complete |

**Total passing tests: 253**

---

## What Needs Implementation Now

Review spec sections 3, 7, 8, 9 for the following components:

### Priority 1: QA Context Builder (Section 7)

| Component | File | Test File |
|-----------|------|-----------|
| QAContextBuilder | `swarm_attack/qa/context_builder.py` | `tests/unit/qa/test_context_builder.py` |

**Requirements:**
- Parse spec/issue content to extract test requirements
- Discover API schemas (OpenAPI, type hints, docstrings)
- Analyze consumer code to find callers
- Extract git diff context for regression testing
- Build QAContext with all gathered information

```python
class QAContextBuilder:
    def build_context(
        self,
        trigger: QATrigger,
        target: str,
        feature_id: Optional[str] = None,
        issue_number: Optional[int] = None,
        bug_id: Optional[str] = None,
    ) -> QAContext:
        """Build complete QA context from available sources."""
        ...

    def discover_endpoints(self, target: str) -> list[QAEndpoint]:
        """Discover API endpoints from code/specs."""
        ...

    def extract_schemas(self, endpoints: list[QAEndpoint]) -> dict[str, Any]:
        """Extract response schemas for endpoints."""
        ...

    def find_consumers(self, endpoints: list[QAEndpoint]) -> dict[str, list[str]]:
        """Find code that calls each endpoint."""
        ...
```

### Priority 2: Depth Selector (Section 8)

| Component | File | Test File |
|-----------|------|-----------|
| DepthSelector | `swarm_attack/qa/depth_selector.py` | `tests/unit/qa/test_depth_selector.py` |

**Requirements:**
- Select depth based on trigger type (post-verify→standard, bug→deep, health→shallow)
- Escalate depth for high-risk code changes
- Consider time and cost budgets
- Support manual depth override

```python
class DepthSelector:
    def select_depth(
        self,
        trigger: QATrigger,
        context: QAContext,
        risk_score: float = 0.5,
        time_budget_minutes: Optional[int] = None,
        cost_budget_usd: Optional[float] = None,
    ) -> QADepth:
        """Select appropriate testing depth."""
        ...

    def calculate_risk_score(self, context: QAContext) -> float:
        """Calculate risk score from context."""
        ...
```

### Priority 3: Pipeline Integration Hooks (Section 3)

| Component | File | Test File |
|-----------|------|-----------|
| VerifierQAHook | `swarm_attack/qa/hooks/verifier_hook.py` | `tests/unit/qa/test_verifier_hook.py` |
| BugResearcherQAHook | `swarm_attack/qa/hooks/bug_hook.py` | `tests/unit/qa/test_bug_hook.py` |

**Requirements:**
- Post-verification QA hook that runs after Verifier completes
- Bug reproduction hook for BugResearcher agent
- Integration with existing agent pipelines
- Graceful degradation if QA fails

---

## TDD Process (MUST FOLLOW)

1. **Write tests FIRST** in the test file
2. Run tests to confirm they fail
3. Implement the minimum code to make tests pass
4. Refactor if needed
5. Run full test suite to ensure no regressions

```bash
# Run tests for specific component
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
PYTHONPATH=. python -m pytest tests/unit/qa/test_context_builder.py -v

# Run all QA tests
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/unit/cli/test_qa_commands.py -v

# Run full test suite (should be 253+ tests)
PYTHONPATH=. python -m pytest tests/unit/ -v --tb=short
```

---

## Test Categories to Write

### For QAContextBuilder:
1. **Initialization Tests** - Can create builder with config
2. **Endpoint Discovery Tests**
   - Discovers endpoints from FastAPI/Flask routes
   - Discovers endpoints from OpenAPI spec
   - Handles missing endpoint definitions
3. **Schema Extraction Tests**
   - Extracts Pydantic model schemas
   - Extracts TypedDict schemas
   - Handles endpoints without schemas
4. **Consumer Analysis Tests**
   - Finds direct API callers
   - Finds indirect callers through services
   - Handles circular dependencies
5. **Context Building Tests**
   - Builds complete context from trigger
   - Includes git diff for regression triggers
   - Includes spec content for validation triggers

### For DepthSelector:
1. **Trigger-Based Selection Tests**
   - POST_VERIFICATION → STANDARD
   - BUG_REPRODUCTION → DEEP
   - USER_COMMAND → uses provided or STANDARD
   - PRE_MERGE → REGRESSION
2. **Risk Escalation Tests**
   - High risk (>0.8) escalates depth by one level
   - Critical files escalate to DEEP
   - Auth/payment code always DEEP
3. **Budget Constraint Tests**
   - Respects time budget
   - Respects cost budget
   - Downgrades depth when constrained

### For Pipeline Hooks:
1. **Verifier Hook Tests**
   - Runs after successful verification
   - Skips on verification failure
   - Passes context to QA orchestrator
   - Reports findings back to pipeline
2. **Bug Hook Tests**
   - Enhances bug reproduction with behavioral tests
   - Provides evidence for RootCauseAnalyzer
   - Handles missing bug context

---

## Files to Reference

**Existing implementations for patterns:**
- `swarm_attack/qa/orchestrator.py` - QAOrchestrator integration patterns
- `swarm_attack/qa/agents/behavioral.py` - Agent implementation patterns
- `swarm_attack/qa/agents/regression.py` - Git/diff analysis patterns
- `swarm_attack/cli/qa_commands.py` - CLI integration patterns

**Existing tests for patterns:**
- `tests/unit/qa/test_orchestrator.py` - Mock and fixture patterns
- `tests/unit/qa/test_regression.py` - Git mocking patterns
- `tests/unit/cli/test_qa_commands.py` - CLI testing patterns

**Spec sections to read:**
- Section 3: Integration Points with Existing Pipelines
- Section 7: QA Context Builder (full data flow)
- Section 8: Depth Selector (rules and thresholds)
- Section 9: Output Formats

---

## Key Implementation Notes

1. **Use existing models** from `swarm_attack/qa/models.py`:
   - QAContext, QADepth, QATrigger, QAEndpoint, QAFinding, QASession

2. **Follow existing patterns:**
   - Agents use `BaseAgent` from `swarm_attack/agents/base.py`
   - Hooks should be lightweight wrappers around QAOrchestrator
   - Use dependency injection for config and logger

3. **Error handling:**
   - QA failures should not block the main pipeline
   - Use graceful degradation (return partial results)
   - Log errors but don't raise to caller

4. **The CLI uses Typer** (not Click as spec shows):
   ```python
   import typer
   from rich.console import Console
   ```

5. **Pre-existing stub modules** were created for missing chief_of_staff components - don't remove them

---

## Verification Checklist

Before marking complete, verify:

- [ ] All new tests pass: `PYTHONPATH=. python -m pytest tests/unit/qa/test_<component>.py -v`
- [ ] No regressions: Previous 253 tests still pass
- [ ] Components follow spec sections 3, 7, 8
- [ ] Error handling is graceful (no exceptions to caller)
- [ ] Code follows existing patterns in the codebase
- [ ] Integration with QAOrchestrator works correctly

---

## Instructions

1. Read spec sections 3, 7, 8 for detailed requirements
2. Start with **QAContextBuilder** (Priority 1)
3. **Write comprehensive tests FIRST** in `tests/unit/qa/test_context_builder.py`
4. Run tests to confirm they fail
5. Implement `swarm_attack/qa/context_builder.py` to make tests pass
6. Run full test suite to verify no regressions
7. Move to Priority 2 (DepthSelector), repeat TDD process
8. Move to Priority 3 (Pipeline Hooks), repeat TDD process
9. Pause for review after each component

**Important:** Follow TDD strictly. Write tests first, then implement. Each component should be completed before moving to the next.
