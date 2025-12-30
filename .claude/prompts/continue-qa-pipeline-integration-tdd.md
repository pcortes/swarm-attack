# Expert Team Prompt: Continue QA Pipeline Integration via TDD

You are an expert team of software engineers continuing the implementation of the QA Agent pipeline integration and Chief of Staff integration using TDD for the Adaptive QA Agent system.

---

## Project Context

**Worktree**: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Spec**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a multi-agent QA system that provides adaptive behavioral testing. The core agents, CLI, context builder, depth selector, and pipeline hooks are complete. We are integrating QA into the existing swarm-attack pipelines and Chief of Staff autopilot.

---

## Work Already Completed ✓

### Priority 1: FeaturePipelineQAIntegration ✓ DONE
| Component | File | Tests | Status |
|-----------|------|-------|--------|
| QAIntegrationResult | `swarm_attack/qa/integrations/feature_pipeline.py` | 37 tests | ✓ Complete |
| FeaturePipelineQAIntegration | `swarm_attack/qa/integrations/feature_pipeline.py` | 37 tests | ✓ Complete |

**Implemented methods:**
- `run_post_verification_qa()` - Run QA after successful verification
- `should_block_commit()` - Determine if QA findings should block commit
- `create_bugs_from_findings()` - Create bug investigations from QA findings
- `_is_high_risk_file()` / `_has_high_risk_files()` - Detect high-risk files for depth escalation

### Priority 2: BugPipelineQAIntegration ✓ DONE
| Component | File | Tests | Status |
|-----------|------|-------|--------|
| BugReproductionResult | `swarm_attack/qa/integrations/bug_pipeline.py` | 28 tests | ✓ Complete |
| BugPipelineQAIntegration | `swarm_attack/qa/integrations/bug_pipeline.py` | 28 tests | ✓ Complete |

**Implemented methods:**
- `enhance_reproduction()` - Attempt behavioral reproduction of a bug with DEEP depth
- `get_rca_evidence()` - Extract evidence for RootCauseAnalyzer
- `_extract_reproduction_steps()` - Extract reproduction steps from findings
- `_extract_evidence()` - Extract all evidence from findings
- `_extract_root_cause_hints()` - Extract root cause hints

**Total passing tests so far: 65 new tests (37 + 28)**

---

## What Needs Implementation Now

### Priority 3: Chief of Staff Integration (Sections 5.2.3, 5.2.4)

| Component | File | Test File |
|-----------|------|-----------|
| QAGoalTypes | `swarm_attack/qa/integrations/cos_goals.py` | `tests/unit/qa/test_cos_goals.py` |
| QAGoal | `swarm_attack/qa/integrations/cos_goals.py` | `tests/unit/qa/test_cos_goals.py` |
| QAAutopilotRunner | `swarm_attack/qa/integrations/cos_autopilot.py` | `tests/unit/qa/test_cos_autopilot.py` |

**Requirements:**
- Add QA_VALIDATION and QA_HEALTH goal types
- Execute QA validation goals in autopilot
- Execute health check goals (shallow depth)
- Track QA sessions linked to goals

**Stub classes already exist** - you need to replace them with full implementations.

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
    description: Optional[str] = None


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
PYTHONPATH=. python -m pytest tests/unit/qa/test_cos_goals.py -v

# Run all new integration tests
PYTHONPATH=. python -m pytest tests/unit/qa/test_feature_pipeline_integration.py tests/unit/qa/test_bug_pipeline_integration.py tests/unit/qa/test_cos_goals.py tests/unit/qa/test_cos_autopilot.py tests/unit/qa/test_qa_config.py -v

# Run full test suite (should be 430+ tests when complete)
PYTHONPATH=. python -m pytest tests/unit/ -v --tb=short
```

---

## Test Categories to Write

### For Chief of Staff Integration:

1. **Goal Type Tests** (`test_cos_goals.py`)
   - Recognizes QA_VALIDATION goal type
   - Recognizes QA_HEALTH goal type
   - Links goals to features/issues
   - Tracks linked QA sessions
   - QAGoal dataclass has required fields

2. **Autopilot Execution Tests** (`test_cos_autopilot.py`)
   - Executes validation goals with correct depth
   - Executes health goals with SHALLOW depth
   - Returns success/failure correctly
   - Tracks cost and duration
   - Handles QA failures gracefully
   - Links session to goal

### For QAConfig:

1. **Default Values Tests** (`test_qa_config.py`)
   - Has sensible defaults
   - Enabled by default
   - STANDARD depth by default

2. **Loading Tests**
   - Loads from dictionary
   - Handles missing keys with defaults
   - Validates values

3. **Integration Flag Tests**
   - Controls post-verify QA
   - Controls blocking behavior
   - Controls bug reproduction enhancement

---

## Files to Reference

**Existing implementations for patterns:**
- `swarm_attack/qa/orchestrator.py` - QAOrchestrator patterns
- `swarm_attack/qa/integrations/feature_pipeline.py` - Integration patterns (JUST COMPLETED)
- `swarm_attack/qa/integrations/bug_pipeline.py` - Integration patterns (JUST COMPLETED)
- `swarm_attack/config.py` - Config loading patterns

**Existing tests for patterns:**
- `tests/unit/qa/test_orchestrator.py` - Mock and fixture patterns
- `tests/unit/qa/test_feature_pipeline_integration.py` - New integration test patterns
- `tests/unit/qa/test_bug_pipeline_integration.py` - New integration test patterns

**Spec sections to read:**
- Section 5.2.3-5.2.4: Chief of Staff modifications
- Section 5.2.5: Configuration

---

## Result Dataclasses (Already Defined)

```python
# In cos_autopilot.py (already exists as stub)
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

## Directory Structure

```
swarm_attack/qa/
├── integrations/
│   ├── __init__.py              ✓ EXISTS
│   ├── feature_pipeline.py      ✓ COMPLETE (37 tests)
│   ├── bug_pipeline.py          ✓ COMPLETE (28 tests)
│   ├── cos_goals.py             ⚠️ STUB ONLY - NEEDS IMPLEMENTATION
│   └── cos_autopilot.py         ⚠️ STUB ONLY - NEEDS IMPLEMENTATION
└── qa_config.py                 ❌ DOES NOT EXIST - CREATE NEW

tests/unit/qa/
├── test_feature_pipeline_integration.py  ✓ COMPLETE (37 tests)
├── test_bug_pipeline_integration.py      ✓ COMPLETE (28 tests)
├── test_cos_goals.py                     ❌ DOES NOT EXIST - CREATE NEW
├── test_cos_autopilot.py                 ❌ DOES NOT EXIST - CREATE NEW
└── test_qa_config.py                     ❌ DOES NOT EXIST - CREATE NEW
```

---

## Verification Checklist

Before marking complete, verify:

- [ ] All new tests pass: `PYTHONPATH=. python -m pytest tests/unit/qa/test_cos_*.py tests/unit/qa/test_qa_config.py -v`
- [ ] Previous 65 tests still pass: `PYTHONPATH=. python -m pytest tests/unit/qa/test_feature_pipeline_integration.py tests/unit/qa/test_bug_pipeline_integration.py -v`
- [ ] No regressions in other QA tests: `PYTHONPATH=. python -m pytest tests/unit/qa/ -v`
- [ ] Components follow spec sections 5.2.3-5.2.5
- [ ] Error handling is graceful (no exceptions to caller)
- [ ] Code follows existing patterns in feature_pipeline.py and bug_pipeline.py
- [ ] QAConfig can be loaded from dictionary

---

## Instructions

1. Read spec sections 5.2.3-5.2.5 for detailed requirements
2. Start with **Priority 3: COS Goals** (simpler dataclasses)
3. **Write comprehensive tests FIRST** in `tests/unit/qa/test_cos_goals.py`
4. Run tests to confirm they fail
5. Replace stub in `swarm_attack/qa/integrations/cos_goals.py` with full implementation
6. Run tests to confirm they pass
7. Move to **COS Autopilot** - write tests first, then implement
8. Move to **Priority 4: QAConfig** - write tests first, then implement
9. Run full test suite to verify no regressions
10. Update `__init__.py` if needed

**Important:** Follow TDD strictly. Write tests first, then implement. Each component should be completed before moving to the next.

---

## Expected Final Test Count

After completing this work:
- Feature Pipeline Integration: 37 tests ✓
- Bug Pipeline Integration: 28 tests ✓
- COS Goals: ~15-20 tests (estimate)
- COS Autopilot: ~20-25 tests (estimate)
- QA Config: ~15-20 tests (estimate)

**Total new tests: ~115-130 tests**
**Plus existing 367 tests = ~480-500 total tests**
