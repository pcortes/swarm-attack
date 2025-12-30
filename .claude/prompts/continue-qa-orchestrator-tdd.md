# Expert Team Prompt: Implement QAOrchestrator TDD

You are an expert team of software engineers implementing the QAOrchestrator using TDD for the Adaptive QA Agent system.

---

## Project Context

**Worktree**: `/Users/philipjcortes/Desktop/swarm-attack-qa-agent`
**Spec**: `/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`

This is a multi-agent QA system. The QAOrchestrator coordinates three specialized sub-agents.

---

## What's Already Complete ✓

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| models.py | `swarm_attack/qa/models.py` | 20 tests | ✓ Complete |
| BehavioralTesterAgent | `swarm_attack/qa/agents/behavioral.py` | 33 tests | ✓ Complete |
| ContractValidatorAgent | `swarm_attack/qa/agents/contract.py` | 45 tests | ✓ Complete |
| RegressionScannerAgent | `swarm_attack/qa/agents/regression.py` | 53 tests | ✓ Complete |
| Skill SKILL.md files | `.claude/skills/qa-*` | N/A | ✓ Complete |

**Total passing tests: 151**

---

## What Needs Implementation Now

| Component | File | Spec Sections | Test File |
|-----------|------|---------------|-----------|
| **QAOrchestrator** | `swarm_attack/qa/orchestrator.py` | 6, 10.10-10.12 | `tests/unit/qa/test_orchestrator.py` |

---

## TDD Process (MUST FOLLOW)

1. **Write tests FIRST** in the test file
2. Run tests to confirm they fail
3. Implement the minimum code to make tests pass
4. Refactor if needed
5. Run full test suite to ensure no regressions

```bash
# Run tests for orchestrator
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
PYTHONPATH=. python -m pytest tests/unit/qa/test_orchestrator.py -v

# Run all QA tests
PYTHONPATH=. python -m pytest tests/unit/qa/ -v
```

---

## QAOrchestrator Requirements (Spec Sections 6, 10.10-10.12)

### Core Methods

```python
class QAOrchestrator:
    def __init__(self, config: SwarmConfig, logger: Optional[SwarmLogger] = None):
        ...

    def test(
        self,
        target: str,
        depth: QADepth = QADepth.STANDARD,
        trigger: QATrigger = QATrigger.USER_COMMAND,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ) -> QASession:
        """Main entry point for QA testing."""
        ...

    def validate_issue(
        self,
        feature_id: str,
        issue_number: int,
        depth: QADepth = QADepth.STANDARD,
    ) -> QASession:
        """Validate an implemented issue with behavioral tests."""
        ...

    def health_check(self, base_url: Optional[str] = None) -> QASession:
        """Run shallow health check on all endpoints."""
        ...

    def dispatch_agents(
        self,
        depth: QADepth,
        context: QAContext,
    ) -> dict[str, Any]:
        """Route to appropriate sub-agents based on depth."""
        ...

    def get_session(self, session_id: str) -> Optional[QASession]:
        """Retrieve a QA session by ID."""
        ...

    def list_sessions(self, limit: int = 20) -> list[str]:
        """List recent QA session IDs."""
        ...

    def get_findings(
        self,
        session_id: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[QAFinding]:
        """Get findings, optionally filtered."""
        ...

    def create_bug_investigations(
        self,
        session_id: str,
        severity_threshold: str = "moderate",
    ) -> list[str]:
        """Create Bug Bash entries from QA findings."""
        ...
```

### Depth-based Dispatch (Section 6)

| Depth | Agents Dispatched |
|-------|------------------|
| SHALLOW | BehavioralTester only (happy path) |
| STANDARD | BehavioralTester + ContractValidator |
| DEEP | All three agents + security probes |
| REGRESSION | RegressionScanner + targeted BehavioralTester |

### Cost/Limit Enforcement (Section 10.10)

```python
@dataclass
class QALimits:
    max_cost_usd: float = 5.0
    warn_cost_usd: float = 2.0
    max_endpoints_shallow: int = 100
    max_endpoints_standard: int = 50
    max_endpoints_deep: int = 20
    session_timeout_minutes: int = 30
```

- Check `max_cost_usd` before/during execution
- Check `session_timeout_minutes`
- Emit warning at `warn_cost_usd` threshold
- Stop early if limits exceeded

### Graceful Degradation (Section 10.12)

| Scenario | Status | Reason |
|----------|--------|--------|
| Infrastructure failures | `BLOCKED` | service_startup_failed, etc. |
| Stopped early | `COMPLETED_PARTIAL` | cost_limit, timeout, rate_limited |
| Agent errors | Continue with others | Track in `skipped_reasons` |

### Result Aggregation

Combine results from all agents:
- Deduplicate overlapping findings
- Assign severity (critical/moderate/minor)
- Calculate confidence scores
- Generate recommendation (PASS/WARN/BLOCK)

### Session Management

- Generate session_id: `qa-YYYYMMDD-HHMMSS`
- Store sessions in `.swarm/qa/{session_id}/`
- Track timestamps: created_at, started_at, completed_at
- Track cost_usd

### Output Format

```python
{
    "session_id": "qa-20241226-143022",
    "trigger": "user_command",
    "depth": "standard",
    "status": "completed",
    "target": {
        "endpoints_tested": ["/api/users", "/api/users/{id}"],
        "files_analyzed": ["src/api/users.py"]
    },
    "results": {
        "passed": 12,
        "failed": 2,
        "skipped": 1
    },
    "findings": [...],
    "recommendation": "WARN",
    "confidence": 0.95,
    "cost_usd": 0.15
}
```

---

## Test Categories to Write

1. **Import Tests** - Can import QAOrchestrator
2. **Initialization Tests** - Config, limits, agents created
3. **test() Method Tests**
   - Creates session with correct ID format
   - Sets trigger and depth correctly
   - Dispatches correct agents for each depth
   - Returns QASession with results
   - Handles timeout
   - Handles errors gracefully
4. **validate_issue() Tests**
   - Loads spec and issue context
   - Uses POST_VERIFICATION trigger
   - Returns appropriate recommendation
5. **health_check() Tests**
   - Uses SHALLOW depth
   - Uses SCHEDULED_HEALTH trigger
   - Fast timeout (30 seconds)
6. **dispatch_agents() Tests**
   - SHALLOW: Only BehavioralTester
   - STANDARD: BehavioralTester + ContractValidator
   - DEEP: All three agents
   - REGRESSION: RegressionScanner + BehavioralTester
7. **Cost/Limit Enforcement Tests**
   - Stops at max_cost_usd
   - Stops at session_timeout
   - Warns at warn_cost_usd
   - Respects max_endpoints per depth
8. **Graceful Degradation Tests**
   - Returns BLOCKED on infrastructure failure
   - Returns COMPLETED_PARTIAL when stopped early
   - Continues if one agent fails
   - Tracks skipped_reasons
9. **Result Aggregation Tests**
   - Combines findings from all agents
   - Deduplicates similar findings
   - Calculates correct counts
   - Sets recommendation based on findings
10. **Session Management Tests**
    - get_session() returns correct session
    - list_sessions() returns recent IDs
    - Sessions persisted to disk
11. **get_findings() Tests**
    - Returns all findings
    - Filters by session_id
    - Filters by severity
12. **create_bug_investigations() Tests**
    - Creates bugs for findings above threshold
    - Returns bug IDs
    - Writes bug files

---

## Files to Reference

**Existing implementations for patterns:**
- `swarm_attack/qa/agents/behavioral.py` - Agent pattern
- `swarm_attack/qa/agents/contract.py` - Agent pattern
- `swarm_attack/qa/agents/regression.py` - Agent pattern
- `swarm_attack/qa/models.py` - All data models (QASession, QAResult, QALimits, etc.)

**Existing tests for patterns:**
- `tests/unit/qa/test_behavioral.py` - Agent testing patterns
- `tests/unit/qa/test_contract.py` - Mock patterns
- `tests/unit/qa/test_regression.py` - Fixture patterns

---

## Verification Checklist

Before marking complete, verify:

- [ ] All tests pass: `PYTHONPATH=. python -m pytest tests/unit/qa/test_orchestrator.py -v`
- [ ] No regressions: Previous 151 tests still pass
- [ ] Follows spec requirements for depth dispatch
- [ ] Cost/limit enforcement works
- [ ] Graceful degradation implemented
- [ ] Session management works
- [ ] Uses existing patterns from other agents

---

## Instructions

1. Read existing patterns from `behavioral.py`, `contract.py`, `regression.py`
2. Read models from `swarm_attack/qa/models.py`
3. **Write comprehensive tests FIRST** in `tests/unit/qa/test_orchestrator.py`
4. Run tests to confirm they fail
5. Implement `swarm_attack/qa/orchestrator.py` to make tests pass
6. Run full test suite to verify no regressions
7. Pause for review

**Important:** Follow TDD strictly. Write tests first, then implement.
