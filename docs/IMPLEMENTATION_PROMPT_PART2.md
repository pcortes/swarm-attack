# Implementation Prompt Part 2: Auth & Response Validation Tests

Continue the QA Agent implementation by adding the remaining edge case tests for authentication flows and response validation.

---

## Context

### Previous Work Completed
The following items have been completed:

| Item | Status | Notes |
|------|--------|-------|
| Missing QATrigger enum values | DONE | Added `SCHEDULED_HEALTH`, `SPEC_COMPLIANCE` |
| Export ContractValidatorAgent | DONE | Now exported from `__init__.py` |
| Request generation edge case tests (10.4) | DONE | `test_request_generation_edge_cases.py` |
| Database state edge case tests (10.6) | DONE | `test_database_state_edge_cases.py` |

### Remaining Work

| Priority | Gap | Effort | Reference |
|----------|-----|--------|-----------|
| HIGH | Auth flow tests (10.2) | 4 hrs | Section 10.2 of spec |
| HIGH | Response validation tests (10.5) | 4 hrs | Section 10.5 of spec |
| MEDIUM | Integration tests for CLI | 2 hrs | Verify CLI commands work |
| LOW | End-to-end manual verification | 1 hr | curl tests, formatting |

---

## Branch

Continue work on `feature/adaptive-qa-agent`

---

## Agent 3: Auth & Response Validation Tests

### Mission

Add comprehensive tests for Section 10.2 (Authentication Edge Cases) and Section 10.5 (Response Validation Failures).

### Reference Files

**Original Spec** (`/Users/philipjcortes/Desktop/swarm-attack/docs/ADAPTIVE_QA_AGENT_DESIGN.md`):
- **Section 10.2** (lines ~1420-1460): Authentication Edge Cases
- **Section 10.5** (lines ~1520-1540): Response Validation Failures

### TDD Steps for Auth Tests (10.2)

Create `/Users/philipjcortes/Desktop/swarm-attack-qa-agent/tests/unit/qa/test_auth_edge_cases.py`:

```python
"""Tests for authentication edge cases (Section 10.2).

Tests cover spec section 10.2: Authentication Edge Cases
- Expired bearer token handling
- OAuth token refresh flow
- Missing auth header detection
- API key placement (header vs query)
- Auth strategy switching
"""

import pytest
from unittest.mock import MagicMock, patch
import requests

from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    AuthStrategy,
    ResilienceConfig,
)


class TestExpiredTokenHandling:
    """Section 10.2: Agent should detect and report expired tokens."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_detects_401_as_auth_failure(self, agent):
        """Agent should recognize 401 as authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "token_expired"}'
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/protected")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
            assert "401" in str(result.get("finding", {}).actual.get("status", ""))


class TestAuthStrategySupport:
    """Section 10.2: Agent should support multiple auth strategies."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_auth_strategy_enum_values(self):
        """All auth strategies should be available."""
        assert AuthStrategy.BEARER_TOKEN.value == "bearer"
        assert AuthStrategy.API_KEY_HEADER.value == "api_key"
        assert AuthStrategy.API_KEY_QUERY.value == "api_key_query"
        assert AuthStrategy.BASIC_AUTH.value == "basic"
        assert AuthStrategy.COOKIE_SESSION.value == "cookie"
        assert AuthStrategy.NONE.value == "none"


class TestMissingAuthDetection:
    """Section 10.2: Agent should detect missing auth on protected endpoints."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_generates_auth_test_for_protected_endpoint(self, agent):
        """Agent should generate unauthorized test for auth_required endpoints."""
        endpoint = QAEndpoint(
            method="GET",
            path="/api/protected",
            auth_required=True
        )

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        auth_tests = [t for t in tests if t.get("test_type") == "unauthorized"]
        assert len(auth_tests) >= 1
```

### TDD Steps for Response Validation Tests (10.5)

Create `/Users/philipjcortes/Desktop/swarm-attack-qa-agent/tests/unit/qa/test_response_validation_edge_cases.py`:

```python
"""Tests for response validation edge cases (Section 10.5).

Tests cover spec section 10.5: Response Validation Failures
- Malformed JSON response handling
- Non-UTF8 response handling
- Streaming response handling
- Response size limits
- Empty response body handling
"""

import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    ResilienceConfig,
)


class TestMalformedJSONResponse:
    """Section 10.5: Agent should handle malformed JSON responses."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_handles_invalid_json_response(self, agent):
        """Agent should handle responses with invalid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "{ invalid json }"
        mock_response.headers = {"content-type": "application/json"}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/data")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            # Should pass since status code matches
            assert result["passed"] is True


class TestEmptyResponseHandling:
    """Section 10.5: Agent should handle empty response bodies."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_handles_204_no_content(self, agent):
        """Agent should handle 204 No Content responses correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.text = ""
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="DELETE", path="/api/items/1")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 204},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


class TestLargeResponseHandling:
    """Section 10.5: Agent should handle large responses."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_truncates_large_response_in_evidence(self, agent):
        """Agent should truncate large responses in evidence."""
        large_response = "x" * 10000
        finding = agent._create_finding(
            endpoint="GET /api/large",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 500},
            request_evidence="curl -X GET ...",
            response_evidence=large_response,
        )
        # Evidence should be truncated (500 chars in the implementation)
        assert len(finding.evidence.get("response", "")) <= 500
```

---

## Verification Commands

After implementing tests, run:

```bash
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent

# Run all new edge case tests
PYTHONPATH=. python -m pytest tests/unit/qa/test_request_generation_edge_cases.py -v
PYTHONPATH=. python -m pytest tests/unit/qa/test_database_state_edge_cases.py -v
PYTHONPATH=. python -m pytest tests/unit/qa/test_auth_edge_cases.py -v
PYTHONPATH=. python -m pytest tests/unit/qa/test_response_validation_edge_cases.py -v

# Run full QA test suite
PYTHONPATH=. python -m pytest tests/unit/qa/ -v

# Verify all tests still pass
PYTHONPATH=. python -m pytest tests/ -v --tb=short
```

---

## Manual System Verification

After tests pass, verify the system manually:

```bash
# 1. Verify imports work
python -c "
from swarm_attack.qa.agents import ContractValidatorAgent, EndpointDiscoveryError
from swarm_attack.qa.models import QATrigger
print('QATrigger values:', [t.value for t in QATrigger])
print('ContractValidatorAgent imported successfully')
"

# 2. Test CLI qa commands (if implemented)
cd /Users/philipjcortes/Desktop/swarm-attack-qa-agent
swarm-attack qa --help

# 3. Run a quick health check
# (Requires a running API service)
# swarm-attack qa health --base-url http://localhost:8000
```

---

## Success Criteria

- [ ] All new tests pass
- [ ] Existing tests still pass (531+ tests)
- [ ] ContractValidatorAgent importable from `swarm_attack.qa.agents`
- [ ] QATrigger has `SCHEDULED_HEALTH` and `SPEC_COMPLIANCE` values
- [ ] Coverage remains >= 80%
- [ ] No regressions in existing functionality

---

## File Summary

### Created/Modified Files

| File | Action | Purpose |
|------|--------|---------|
| `swarm_attack/qa/models.py` | Modified | Added SCHEDULED_HEALTH, SPEC_COMPLIANCE |
| `swarm_attack/qa/agents/__init__.py` | Modified | Export ContractValidatorAgent |
| `tests/unit/qa/test_request_generation_edge_cases.py` | Created | Section 10.4 tests |
| `tests/unit/qa/test_database_state_edge_cases.py` | Created | Section 10.6 tests |

### Files to Create

| File | Purpose |
|------|---------|
| `tests/unit/qa/test_auth_edge_cases.py` | Section 10.2 tests |
| `tests/unit/qa/test_response_validation_edge_cases.py` | Section 10.5 tests |

---

*Ready to continue implementation. Start with auth edge cases.*
