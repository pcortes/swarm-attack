# Expert Team Prompt: Continue Adaptive QA Agent TDD Implementation

You are an expert team of software engineers continuing the TDD implementation of the Adaptive QA Agent system for the swarm-attack project.

---

## Project Context

**Worktree**: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Spec**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a multi-agent QA system that integrates into swarm-attack's development automation pipeline. The system has three specialized sub-agents coordinated by a QA Orchestrator.

---

## What's Already Complete ✓

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| models.py | `swarm_attack/qa/models.py` | `tests/unit/qa/test_models.py` (20 tests) | ✓ Complete |
| BehavioralTesterAgent | `swarm_attack/qa/agents/behavioral.py` | `tests/unit/qa/test_behavioral.py` (33 tests) | ✓ Complete |
| ContractValidatorAgent | `swarm_attack/qa/agents/contract.py` | `tests/unit/qa/test_contract.py` (45 tests) | ✓ Complete |
| Skill SKILL.md files | `.claude/skills/qa-*` | N/A | ✓ Complete |

**Total passing tests: 98**

---

## What Needs Implementation (Priority Order)

| # | Component | File | Spec Sections | Test File |
|---|-----------|------|---------------|-----------|
| 1 | **RegressionScannerAgent** | `swarm_attack/qa/agents/regression.py` | 4.3, 10.9 | `tests/unit/qa/test_regression.py` |
| 2 | **QAOrchestrator** | `swarm_attack/qa/orchestrator.py` | 6, 10.10-10.12 | `tests/unit/qa/test_orchestrator.py` |
| 3 | **DepthSelector** | `swarm_attack/qa/depth_selector.py` | 5, 9 | `tests/unit/qa/test_depth_selector.py` |
| 4 | **CLI Commands** | `swarm_attack/cli/qa.py` | 7 | `tests/unit/cli/test_qa.py` |

---

## TDD Process (MUST FOLLOW)

1. **Write tests FIRST** in the test file
2. Run tests to confirm they fail
3. Implement the minimum code to make tests pass
4. Refactor if needed
5. Run full test suite to ensure no regressions

```bash
# Run tests for a specific component
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
PYTHONPATH=. python -m pytest tests/unit/qa/test_regression.py -v

# Run all QA tests
PYTHONPATH=. python -m pytest tests/unit/qa/ -v
```

---

## Implementation Patterns (from existing code)

### Agent Base Pattern
```python
from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.qa.models import QADepth, QAEndpoint, QAFinding, QALimits

class MyAgent(BaseAgent):
    name: str = "my_agent"

    def __init__(self, config: SwarmConfig, logger: Optional[SwarmLogger] = None, **kwargs):
        super().__init__(config, logger, **kwargs)
        self._finding_counter = 0

    def run(self, context: dict[str, Any]) -> AgentResult:
        # Implementation
        return AgentResult.success_result(output=results)
```

### Import Pattern
```python
from swarm_attack.qa.models import (
    QAContext, QAEndpoint, QAFinding, QADepth, QALimits,
    QATrigger, QAStatus, QARecommendation, ResilienceConfig,
)
```

### Test Fixture Pattern
```python
@pytest.fixture
def agent(self):
    from swarm_attack.qa.agents.regression import RegressionScannerAgent
    config = MagicMock()
    config.repo_root = "/tmp/test"
    return RegressionScannerAgent(config)
```

---

## Key Spec Requirements by Component

### RegressionScannerAgent (Section 4.3, 10.9)

**Core Methods:**
- `analyze_diff(context)` - Analyze git diff to find affected files
- `map_changes_to_endpoints(changed_files)` - Map file changes to affected endpoints
- `prioritize_endpoints(impact_map)` - Score endpoints by priority (0-100)
- `select_regression_suite(priorities)` - Select tests based on priority thresholds

**Priority Scoring (Section 4.3):**
- Direct change to endpoint handler: 100
- Model change used by endpoint: 80
- Service change called by endpoint: 60
- Utility change used indirectly: 40
- Config change affecting endpoint: 30

**Git Edge Cases (Section 10.9):**
- Handle dirty worktree
- Handle detached HEAD
- Handle missing main/master branch
- Handle shallow clone
- Handle uncommitted new files

**Output Format:**
```python
{
    "agent": "regression_scanner",
    "files_analyzed": 12,
    "endpoints_affected": 5,
    "impact_map": [...],
    "regression_suite": {
        "must_test": [...],    # priority >= 80
        "should_test": [...],  # priority >= 50
        "may_skip": [...]      # priority < 50
    }
}
```

### QAOrchestrator (Section 6, 10.10-10.12)

**Core Methods:**
- `test(target, depth, trigger, base_url, timeout)` - Main entry point
- `validate_issue(feature_id, issue_number, depth)` - Validate implemented issue
- `health_check(base_url)` - Run shallow health check
- `dispatch_agents(depth, context)` - Route to appropriate sub-agents

**Depth-based Dispatch:**
- SHALLOW: BehavioralTester only (happy path)
- STANDARD: BehavioralTester + ContractValidator
- DEEP: All three agents + security probes
- REGRESSION: RegressionScanner + targeted BehavioralTester

**Cost/Limit Enforcement (Section 10.10):**
- Check `QALimits.max_cost_usd` before/during execution
- Check `QALimits.session_timeout_minutes`
- Emit warning at `warn_cost_usd` threshold

**Graceful Degradation (Section 10.12):**
- Return `QAStatus.BLOCKED` for infrastructure failures
- Return `QAStatus.COMPLETED_PARTIAL` when stopped early
- Track `skipped_reasons` in QAResult

### DepthSelector (Section 5, 9)

**Core Method:**
- `select_depth(trigger, risk_score, time_budget, cost_budget)` -> QADepth

**Rules:**
| Trigger | Base Depth | Risk Escalation |
|---------|------------|-----------------|
| POST_VERIFICATION | STANDARD | +1 if high-risk code |
| BUG_REPRODUCTION | DEEP | always DEEP |
| USER_COMMAND | as_specified | respect user choice |
| SCHEDULED_HEALTH | SHALLOW | no escalation |
| PRE_MERGE | REGRESSION | +1 if critical paths |

**Risk Detection:**
- "auth" in path → HIGH RISK
- "payment" in path → HIGH RISK
- Large number of lines changed → escalate

### CLI Commands (Section 7)

**Commands to implement:**
- `swarm-attack qa test <target> [--depth] [--base-url] [--timeout]`
- `swarm-attack qa validate <feature> <issue> [--depth]`
- `swarm-attack qa health [--base-url]`
- `swarm-attack qa report [session_id] [--since] [--json]`
- `swarm-attack qa bugs [--session] [--severity]`
- `swarm-attack qa create-bugs <session_id> [--severity-threshold]`

---

## Files to Reference

**Existing implementations for patterns:**
- `swarm_attack/qa/agents/behavioral.py` - Agent pattern, retry logic, findings
- `swarm_attack/qa/agents/contract.py` - Endpoint discovery, limits enforcement
- `swarm_attack/qa/models.py` - All data models
- `swarm_attack/agents/base.py` - BaseAgent, AgentResult

**Existing tests for patterns:**
- `tests/unit/qa/test_behavioral.py` - Agent testing patterns
- `tests/unit/qa/test_contract.py` - Mock patterns, fixture patterns

---

## Verification Checklist

Before marking a component complete, verify:

- [ ] All tests pass: `PYTHONPATH=. python -m pytest tests/unit/qa/ -v`
- [ ] No regressions: Previous 98 tests still pass
- [ ] Follows spec requirements for the component
- [ ] Uses existing patterns from behavioral.py and contract.py
- [ ] Handles edge cases from Section 10 of spec
- [ ] Has graceful degradation (doesn't crash on edge cases)

---

## Instructions

1. Start with **RegressionScannerAgent** (next in priority)
2. Read spec sections 4.3 and 10.9 carefully
3. Write comprehensive tests FIRST in `tests/unit/qa/test_regression.py`
4. Implement `swarm_attack/qa/agents/regression.py` to make tests pass
5. Run full test suite to verify no regressions
6. Pause for review before moving to next component

**Important:** Follow TDD strictly. Write tests first, then implement.
