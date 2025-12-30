# Continue QA E2E Integration Testing via TDD

## Current State

The Adaptive QA Agent core implementation is complete:

### Completed Components (531+ QA tests passing)

| Component | File | Tests | Status |
|-----------|------|-------|--------|
| QA Models | `swarm_attack/qa/models.py` | ~50 tests | ✓ Complete |
| QA Orchestrator | `swarm_attack/qa/orchestrator.py` | ~60 tests | ✓ Complete |
| Behavioral Agent | `swarm_attack/qa/agents/behavioral.py` | ~50 tests | ✓ Complete |
| Contract Agent | `swarm_attack/qa/agents/contract.py` | ~45 tests | ✓ Complete |
| Regression Agent | `swarm_attack/qa/agents/regression.py` | ~40 tests | ✓ Complete |
| Context Builder | `swarm_attack/qa/context_builder.py` | ~30 tests | ✓ Complete |
| Depth Selector | `swarm_attack/qa/depth_selector.py` | ~25 tests | ✓ Complete |
| Feature Pipeline Integration | `swarm_attack/qa/integrations/feature_pipeline.py` | 37 tests | ✓ Complete |
| Bug Pipeline Integration | `swarm_attack/qa/integrations/bug_pipeline.py` | 28 tests | ✓ Complete |
| COS Goals | `swarm_attack/qa/integrations/cos_goals.py` | 28 tests | ✓ Complete |
| COS Autopilot | `swarm_attack/qa/integrations/cos_autopilot.py` | 33 tests | ✓ Complete |
| QA Config | `swarm_attack/qa/qa_config.py` | 38 tests | ✓ Complete |
| Verifier Hook | `swarm_attack/qa/hooks/verifier_hook.py` | 32 tests | ✓ Complete |
| Bug Researcher Hook | `swarm_attack/qa/hooks/bug_researcher_hook.py` | 23 tests | ✓ Complete |
| CLI Commands | `swarm_attack/cli/qa_commands.py` | 37 tests | ✓ Complete |

---

## Priority 5: E2E Integration Tests

Write end-to-end integration tests that verify the full flow works correctly.

### Reference Spec: Section 7 - End-to-End Scenarios

The spec describes these scenarios that should be tested:

1. **Feature Pipeline E2E** (Section 7.1)
   - User submits code → Verifier passes → QA runs → Findings reported
   - Test with mock service that returns varied responses

2. **Bug Reproduction E2E** (Section 7.2)
   - Bug reported → BugResearcher fails → QA enhances → Root cause identified
   - Test with reproducible vs non-reproducible bugs

3. **Health Check E2E** (Section 7.3)
   - Scheduled health check → QA shallow scan → Report generated
   - Test with healthy vs unhealthy service states

4. **Regression Detection E2E** (Section 7.4)
   - Code change → Regression scan → Affected endpoints identified
   - Test with breaking vs non-breaking changes

### Test File Location

Create: `tests/integration/qa/test_qa_e2e.py`

### TDD Requirements

1. Write ALL tests first in `test_qa_e2e.py`
2. Tests should fail initially (showing spec coverage)
3. Then implement any missing glue code to make them pass

### Test Structure

```python
"""E2E Integration Tests for QA Agent System.

Tests the full flow from trigger to report for all scenarios:
- Feature pipeline integration
- Bug reproduction enhancement
- Health check execution
- Regression detection
"""

class TestFeaturePipelineE2E:
    """E2E tests for feature pipeline QA integration."""

    def test_verifier_pass_triggers_qa(self):
        """After Verifier passes, QA should run automatically."""

    def test_qa_findings_block_commit_on_critical(self):
        """Critical QA findings should block commit."""

    def test_qa_findings_warn_on_moderate(self):
        """Moderate QA findings should warn but not block."""

    def test_bugs_created_from_findings(self):
        """Bugs should be created from critical/moderate findings."""

    def test_skip_qa_flag_honored(self):
        """skip_qa flag should bypass QA validation."""


class TestBugReproductionE2E:
    """E2E tests for bug reproduction enhancement."""

    def test_enhances_failing_reproduction(self):
        """QA should enhance when BugResearcher fails to reproduce."""

    def test_provides_rca_evidence(self):
        """QA findings should provide evidence for RootCauseAnalyzer."""

    def test_extracts_reproduction_steps(self):
        """Should extract concrete reproduction steps from findings."""


class TestHealthCheckE2E:
    """E2E tests for health check functionality."""

    def test_shallow_health_check_completes(self):
        """Health check should complete with shallow depth."""

    def test_reports_unhealthy_endpoints(self):
        """Should report failing endpoints in health check."""

    def test_generates_health_report(self):
        """Should generate health report document."""


class TestRegressionDetectionE2E:
    """E2E tests for regression detection."""

    def test_identifies_affected_endpoints(self):
        """Should identify endpoints affected by code changes."""

    def test_runs_targeted_tests(self):
        """Should run targeted tests on affected endpoints."""

    def test_detects_breaking_changes(self):
        """Should detect API breaking changes in diff."""


class TestCOSIntegrationE2E:
    """E2E tests for Chief of Staff autopilot integration."""

    def test_validation_goal_executes(self):
        """QA validation goal should execute in autopilot."""

    def test_health_goal_executes(self):
        """QA health goal should execute in autopilot."""

    def test_goal_results_tracked(self):
        """Goal execution results should be tracked."""
```

---

## Priority 6: Real HTTP Validation (Optional Enhancement)

Currently, agents use mocked HTTP responses. For real-world validation:

### Test File Location

Create: `tests/integration/qa/test_real_http.py`

### Scope

- Use pytest fixtures with a real test server (FastAPI/Flask)
- Test actual HTTP request/response validation
- Verify behavioral tests against running service
- Test contract validation with real schemas

### Implementation Notes

```python
"""Real HTTP validation tests.

Uses a test server fixture to validate actual HTTP behavior.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

@pytest.fixture
def test_app():
    """Create test FastAPI application."""
    app = FastAPI()

    @app.get("/api/users/{user_id}")
    def get_user(user_id: int):
        if user_id == 404:
            raise HTTPException(status_code=404)
        return {"id": user_id, "name": f"User {user_id}"}

    return app

@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)

class TestRealHTTPBehavioral:
    """Test behavioral validation with real HTTP."""

    def test_happy_path_validation(self, test_client):
        """Should validate happy path against real server."""

    def test_error_path_validation(self, test_client):
        """Should validate error handling against real server."""


class TestRealHTTPContract:
    """Test contract validation with real HTTP."""

    def test_schema_validation(self, test_client):
        """Should validate response schema against contract."""

    def test_breaking_change_detection(self, test_client):
        """Should detect breaking changes in API."""
```

---

## Implementation Order

Follow strict TDD:

1. **Write E2E tests** in `tests/integration/qa/test_qa_e2e.py`
2. **Run tests** - verify they fail initially
3. **Implement glue code** if needed to make tests pass
4. **Verify all tests pass**

Then optionally:

5. **Write real HTTP tests** in `tests/integration/qa/test_real_http.py`
6. **Implement test server fixtures**
7. **Verify integration with real HTTP**

---

## Verification

After implementation, run:

```bash
# Run all QA tests
PYTHONPATH=. python -m pytest tests/unit/qa/ tests/integration/qa/ -v

# Verify no regressions
PYTHONPATH=. python -m pytest tests/unit/ -v
```

Expected: All tests pass, including new E2E tests.

---

## Notes

- E2E tests may need longer timeouts (use `@pytest.mark.timeout(60)`)
- Use `tmp_path` fixture for file-based tests
- Mock external services where appropriate
- Focus on testing integration points, not re-testing unit logic
