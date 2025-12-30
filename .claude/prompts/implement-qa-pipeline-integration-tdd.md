# Expert Team Prompt: Implement QA Pipeline & COS Integration via TDD

You are an expert team of software engineers implementing the QA Agent pipeline integration and Chief of Staff integration using TDD for the Adaptive QA Agent system.

---

## Project Context

**Worktree**: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Spec**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a multi-agent QA system that provides adaptive behavioral testing. The core agents, CLI, context builder, depth selector, and pipeline hooks are complete. Now we need to integrate QA into the existing swarm-attack pipelines and Chief of Staff autopilot.

---

## What's Already Complete ✓

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| models.py | `swarm_attack/qa/models.py` | 20 tests | ✓ Complete |
| BehavioralTesterAgent | `swarm_attack/qa/agents/behavioral.py` | 33 tests | ✓ Complete |
| ContractValidatorAgent | `swarm_attack/qa/agents/contract.py` | 45 tests | ✓ Complete |
| RegressionScannerAgent | `swarm_attack/qa/agents/regression.py` | 53 tests | ✓ Complete |
| QAOrchestrator | `swarm_attack/qa/orchestrator.py` | 65 tests | ✓ Complete |
| QAContextBuilder | `swarm_attack/qa/context_builder.py` | 51 tests | ✓ Complete |
| DepthSelector | `swarm_attack/qa/depth_selector.py` | 47 tests | ✓ Complete |
| VerifierQAHook | `swarm_attack/qa/hooks/verifier_hook.py` | 30 tests | ✓ Complete |
| BugResearcherQAHook | `swarm_attack/qa/hooks/bug_researcher_hook.py` | 23 tests | ✓ Complete |
| Skill SKILL.md files | `.claude/skills/qa-*` | N/A | ✓ Complete |
| QA CLI Commands | `swarm_attack/cli/qa_commands.py` | 37 tests | ✓ Complete |

**Total passing tests: 367**

---

## What Needs Implementation Now

Review spec sections 5.2 (Modifications to Existing Files) for the following integrations:

### Priority 1: Feature Pipeline Integration (Section 5.2.1)

| Component | File | Test File |
|-----------|------|-----------|
| FeaturePipelineQAIntegration | `swarm_attack/qa/integrations/feature_pipeline.py` | `tests/unit/qa/test_feature_pipeline_integration.py` |

**Requirements:**
- Integrate QA validation after Verifier passes
- Skip QA with `skip_qa` flag
- Block on critical QA findings
- Create bugs for critical/moderate findings
- Log warnings but continue on WARN recommendation

```python
class FeaturePipelineQAIntegration:
    def run_post_verification_qa(
        self,
        feature_id: str,
        issue_number: int,
        verified_files: list[str],
        skip_qa: bool = False,
    ) -> QAIntegrationResult:
        """Run QA after successful verification."""
        ...

    def should_block_commit(
        self,
        qa_result: QASession,
    ) -> tuple[bool, str]:
        """Determine if QA findings should block commit."""
        ...

    def create_bugs_from_findings(
        self,
        session_id: str,
        severity_threshold: str = "moderate",
    ) -> list[str]:
        """Create bug investigations from QA findings."""
        ...
```

### Priority 2: Bug Pipeline Integration (Section 5.2.2)

| Component | File | Test File |
|-----------|------|-----------|
| BugPipelineQAIntegration | `swarm_attack/qa/integrations/bug_pipeline.py` | `tests/unit/qa/test_bug_pipeline_integration.py` |

**Requirements:**
- Enhance bug reproduction with behavioral tests
- Run DEEP QA on affected area when BugResearcher fails to reproduce
- Provide evidence for RootCauseAnalyzer
- Extract reproduction steps from QA findings

```python
class BugPipelineQAIntegration:
    def enhance_reproduction(
        self,
        bug_id: str,
        bug_description: str,
        error_message: Optional[str] = None,
        affected_endpoints: Optional[list[str]] = None,
    ) -> BugReproductionResult:
        """Attempt behavioral reproduction of a bug."""
        ...

    def get_rca_evidence(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """Extract evidence for root cause analysis."""
        ...
```

### Priority 3: Chief of Staff Integration (Sections 5.2.3, 5.2.4)

| Component | File | Test File |
|-----------|------|-----------|
| QAGoalTypes | `swarm_attack/qa/integrations/cos_goals.py` | `tests/unit/qa/test_cos_goals.py` |
| QAAutopilotRunner | `swarm_attack/qa/integrations/cos_autopilot.py` | `tests/unit/qa/test_cos_autopilot.py` |

**Requirements:**
- Add QA_VALIDATION and QA_HEALTH goal types
- Execute QA validation goals in autopilot
- Execute health check goals (shallow depth)
- Track QA sessions linked to goals

```python
class QAGoalTypes(Enum):
    QA_VALIDATION = "qa_validation"
    QA_HEALTH = "qa_health"

@dataclass
class QAGoal:
    goal_type: QAGoalTypes
    linked_feature: Optional[str] = None
    linked_issue: Optional[int] = None
    linked_qa_session: Optional[str] = None


class QAAutopilotRunner:
    def execute_qa_validation_goal(
        self,
        goal: QAGoal,
    ) -> GoalExecutionResult:
        """Execute a QA validation goal."""
        ...

    def execute_qa_health_goal(
        self,
        goal: QAGoal,
    ) -> GoalExecutionResult:
        """Execute a QA health check goal."""
        ...
```

### Priority 4: QA Configuration (Section 5.2.5)

| Component | File | Test File |
|-----------|------|-----------|
| QAConfig | `swarm_attack/qa/qa_config.py` | `tests/unit/qa/test_qa_config.py` |

**Requirements:**
- QA enable/disable flag
- Default depth and timeouts
- Cost limits
- Integration flags (post_verify_qa, block_on_critical, enhance_bug_repro)
- Load from config.yaml

```python
@dataclass
class QAConfig:
    enabled: bool = True
    default_depth: QADepth = QADepth.STANDARD
    timeout_seconds: int = 120
    max_cost_usd: float = 2.0
    auto_create_bugs: bool = True
    bug_severity_threshold: str = "moderate"
    base_url: Optional[str] = None

    # Depth-specific timeouts
    shallow_timeout: int = 30
    standard_timeout: int = 120
    deep_timeout: int = 300

    # Integration flags
    post_verify_qa: bool = True
    block_on_critical: bool = True
    enhance_bug_repro: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> QAConfig:
        """Load from config dictionary."""
        ...
```

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
PYTHONPATH=. python -m pytest tests/unit/qa/test_feature_pipeline_integration.py -v

# Run all QA tests
PYTHONPATH=. python -m pytest tests/unit/qa/ -v

# Run full test suite (should be 367+ tests)
PYTHONPATH=. python -m pytest tests/unit/ -v --tb=short
```

---

## Test Categories to Write

### For FeaturePipelineQAIntegration:
1. **Post-Verification QA Tests**
   - Runs QA after successful verification
   - Skips QA when skip_qa=True
   - Uses STANDARD depth by default
   - Escalates to DEEP for high-risk files
2. **Blocking Decision Tests**
   - Blocks on BLOCK recommendation
   - Does not block on WARN
   - Does not block on PASS
   - Returns clear reason when blocking
3. **Bug Creation Tests**
   - Creates bugs for critical findings
   - Creates bugs for moderate findings when threshold allows
   - Returns created bug IDs
   - Handles empty findings gracefully

### For BugPipelineQAIntegration:
1. **Enhanced Reproduction Tests**
   - Uses DEEP depth for bug reproduction
   - Includes bug description in context
   - Includes affected endpoints
   - Returns reproduction status
2. **Evidence Extraction Tests**
   - Extracts request/response evidence
   - Extracts stack traces if available
   - Provides reproduction steps from findings
   - Formats for RootCauseAnalyzer consumption

### For Chief of Staff Integration:
1. **Goal Type Tests**
   - Recognizes QA_VALIDATION goal type
   - Recognizes QA_HEALTH goal type
   - Links goals to features/issues
   - Tracks linked QA sessions
2. **Autopilot Execution Tests**
   - Executes validation goals with correct depth
   - Executes health goals with SHALLOW depth
   - Returns success/failure correctly
   - Tracks cost and duration
   - Handles QA failures gracefully

### For QAConfig:
1. **Default Values Tests**
   - Has sensible defaults
   - Enabled by default
   - STANDARD depth by default
2. **Loading Tests**
   - Loads from dictionary
   - Handles missing keys
   - Validates values
3. **Integration Flag Tests**
   - Controls post-verify QA
   - Controls blocking behavior
   - Controls bug reproduction enhancement

---

## Files to Reference

**Existing implementations for patterns:**
- `swarm_attack/qa/orchestrator.py` - QAOrchestrator patterns
- `swarm_attack/qa/hooks/verifier_hook.py` - Hook patterns
- `swarm_attack/bug_orchestrator.py` - Bug pipeline patterns
- `swarm_attack/chief_of_staff/autopilot_runner.py` - Autopilot patterns
- `swarm_attack/chief_of_staff/goal_tracker.py` - Goal tracking patterns
- `swarm_attack/config.py` - Config loading patterns

**Existing tests for patterns:**
- `tests/unit/qa/test_orchestrator.py` - Mock and fixture patterns
- `tests/unit/qa/test_verifier_hook.py` - Hook testing patterns
- `tests/unit/qa/test_bug_researcher_hook.py` - Bug hook patterns

**Spec sections to read:**
- Section 5.2.1: Feature Pipeline modifications
- Section 5.2.2: Bug Pipeline modifications
- Section 5.2.3-5.2.4: Chief of Staff modifications
- Section 5.2.5: Configuration

---

## Key Implementation Notes

1. **Use existing components:**
   - `QAOrchestrator` for running tests
   - `VerifierQAHook` for post-verification
   - `BugResearcherQAHook` for bug reproduction
   - `DepthSelector` for depth selection
   - `QAContextBuilder` for context

2. **Follow existing patterns:**
   - Integration classes are thin wrappers
   - Use dependency injection for config and logger
   - Return dataclass results

3. **Error handling:**
   - Integration failures should not break the main pipeline
   - Use graceful degradation
   - Log errors but don't raise to caller
   - Return partial results when possible

4. **The goal tracker uses dataclasses** and enums for goal types

5. **Config is loaded from config.yaml** and merged with defaults

---

## Result Dataclasses to Create

```python
@dataclass
class QAIntegrationResult:
    """Result of running QA in a pipeline integration."""
    session_id: Optional[str] = None
    recommendation: QARecommendation = QARecommendation.PASS
    should_block: bool = False
    block_reason: Optional[str] = None
    created_bugs: list[str] = field(default_factory=list)
    findings_summary: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class BugReproductionResult:
    """Result of QA-enhanced bug reproduction."""
    session_id: Optional[str] = None
    is_reproduced: bool = False
    reproduction_steps: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    root_cause_hints: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class GoalExecutionResult:
    """Result of executing a QA goal."""
    success: bool = False
    session_id: Optional[str] = None
    cost_usd: float = 0.0
    duration_seconds: int = 0
    findings_count: int = 0
    error: Optional[str] = None
```

---

## Directory Structure to Create

```
swarm_attack/qa/
├── integrations/
│   ├── __init__.py
│   ├── feature_pipeline.py     # FeaturePipelineQAIntegration
│   ├── bug_pipeline.py         # BugPipelineQAIntegration
│   ├── cos_goals.py            # QAGoalTypes, QAGoal
│   └── cos_autopilot.py        # QAAutopilotRunner
└── qa_config.py                # QAConfig

tests/unit/qa/
├── test_feature_pipeline_integration.py
├── test_bug_pipeline_integration.py
├── test_cos_goals.py
├── test_cos_autopilot.py
└── test_qa_config.py
```

---

## Verification Checklist

Before marking complete, verify:

- [ ] All new tests pass: `PYTHONPATH=. python -m pytest tests/unit/qa/test_<component>.py -v`
- [ ] No regressions: Previous 367 tests still pass
- [ ] Components follow spec section 5.2
- [ ] Error handling is graceful (no exceptions to caller)
- [ ] Code follows existing patterns in the codebase
- [ ] Integration with existing pipelines is clean
- [ ] QAConfig can be loaded from config.yaml

---

## Instructions

1. Read spec section 5.2 for detailed requirements
2. Create the `integrations/` directory structure
3. Start with **FeaturePipelineQAIntegration** (Priority 1)
4. **Write comprehensive tests FIRST** in `tests/unit/qa/test_feature_pipeline_integration.py`
5. Run tests to confirm they fail
6. Implement `swarm_attack/qa/integrations/feature_pipeline.py` to make tests pass
7. Run full test suite to verify no regressions
8. Move to Priority 2 (BugPipelineQAIntegration), repeat TDD process
9. Move to Priority 3 (COS Integration), repeat TDD process
10. Move to Priority 4 (QAConfig), repeat TDD process
11. Pause for review after each component

**Important:** Follow TDD strictly. Write tests first, then implement. Each component should be completed before moving to the next.
