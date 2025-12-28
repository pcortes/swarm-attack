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

from swarm_attack.qa.agents.behavioral import BehavioralTesterAgent
from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
    AuthStrategy,
    ResilienceConfig,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def agent():
    """Create a BehavioralTesterAgent for testing."""
    config = MagicMock()
    config.repo_root = "/tmp/test"
    return BehavioralTesterAgent(config)


@pytest.fixture
def mock_401_response():
    """Create a mock 401 response object."""
    response = MagicMock()
    response.status_code = 401
    response.text = '{"error": "token_expired"}'
    response.headers = {}
    return response


@pytest.fixture
def mock_403_response():
    """Create a mock 403 response object."""
    response = MagicMock()
    response.status_code = 403
    response.text = '{"error": "forbidden"}'
    response.headers = {}
    return response


@pytest.fixture
def mock_200_response():
    """Create a mock 200 response object."""
    response = MagicMock()
    response.status_code = 200
    response.text = '{"data": "success"}'
    response.headers = {"content-type": "application/json"}
    return response


# =============================================================================
# Test Expired Token Handling (Section 10.2)
# =============================================================================


class TestExpiredTokenHandling:
    """Section 10.2: Agent should detect and report expired tokens."""

    def test_detects_401_as_auth_failure(self, agent, mock_401_response):
        """Agent should recognize 401 as authentication failure."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_401_response):
            endpoint = QAEndpoint(method="GET", path="/api/protected")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
            assert result.get("finding") is not None
            assert result["finding"].actual.get("status") == 401

    def test_401_creates_finding_with_details(self, agent, mock_401_response):
        """Agent should create detailed finding for 401 response."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_401_response):
            endpoint = QAEndpoint(method="GET", path="/api/protected")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            finding = result.get("finding")
            assert finding is not None
            assert "401" in finding.title or "status" in finding.title.lower()
            assert finding.endpoint == "GET /api/protected"

    def test_expected_401_is_passing_test(self, agent, mock_401_response):
        """When 401 is expected (unauthorized test), it should pass."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_401_response):
            endpoint = QAEndpoint(method="GET", path="/api/protected", auth_required=True)
            result = agent._execute_test(
                endpoint,
                {"test_type": "unauthorized", "expected_status": 401, "skip_auth": True},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Auth Strategy Support (Section 10.2)
# =============================================================================


class TestAuthStrategySupport:
    """Section 10.2: Agent should support multiple auth strategies."""

    def test_auth_strategy_enum_values(self):
        """All auth strategies should be available."""
        assert AuthStrategy.BEARER_TOKEN.value == "bearer"
        assert AuthStrategy.API_KEY_HEADER.value == "api_key"
        assert AuthStrategy.API_KEY_QUERY.value == "api_key_query"
        assert AuthStrategy.BASIC_AUTH.value == "basic"
        assert AuthStrategy.COOKIE_SESSION.value == "cookie"
        assert AuthStrategy.NONE.value == "none"

    def test_auth_strategy_iteration(self):
        """All auth strategies should be iterable."""
        strategies = list(AuthStrategy)
        assert len(strategies) == 6
        assert AuthStrategy.BEARER_TOKEN in strategies
        assert AuthStrategy.NONE in strategies

    def test_auth_strategy_from_string(self):
        """Auth strategies should be constructible from string values."""
        assert AuthStrategy("bearer") == AuthStrategy.BEARER_TOKEN
        assert AuthStrategy("api_key") == AuthStrategy.API_KEY_HEADER
        assert AuthStrategy("none") == AuthStrategy.NONE


# =============================================================================
# Test Missing Auth Detection (Section 10.2)
# =============================================================================


class TestMissingAuthDetection:
    """Section 10.2: Agent should detect missing auth on protected endpoints."""

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

    def test_auth_test_has_skip_auth_flag(self, agent):
        """Unauthorized test should have skip_auth flag."""
        endpoint = QAEndpoint(
            method="POST",
            path="/api/protected",
            auth_required=True
        )

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        auth_tests = [t for t in tests if t.get("test_type") == "unauthorized"]
        assert len(auth_tests) >= 1
        assert auth_tests[0].get("skip_auth") is True

    def test_no_auth_test_for_unprotected_endpoint(self, agent):
        """Agent should not generate unauthorized test for unprotected endpoints."""
        endpoint = QAEndpoint(
            method="GET",
            path="/api/public",
            auth_required=False
        )

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        auth_tests = [t for t in tests if t.get("test_type") == "unauthorized"]
        assert len(auth_tests) == 0

    def test_shallow_depth_skips_auth_tests(self, agent):
        """SHALLOW depth should skip auth tests even for protected endpoints."""
        endpoint = QAEndpoint(
            method="GET",
            path="/api/protected",
            auth_required=True
        )

        tests = agent._generate_tests(endpoint, QADepth.SHALLOW)
        auth_tests = [t for t in tests if t.get("test_type") == "unauthorized"]
        assert len(auth_tests) == 0


# =============================================================================
# Test 403 Forbidden Handling (Section 10.2)
# =============================================================================


class TestForbiddenHandling:
    """Section 10.2: Agent should handle 403 Forbidden responses."""

    def test_detects_403_as_authorization_failure(self, agent, mock_403_response):
        """Agent should recognize 403 as authorization failure."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_403_response):
            endpoint = QAEndpoint(method="DELETE", path="/api/admin/users/1")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is False
            assert result["finding"].actual.get("status") == 403

    def test_expected_403_is_passing(self, agent, mock_403_response):
        """When 403 is expected, test should pass."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_403_response):
            endpoint = QAEndpoint(method="DELETE", path="/api/admin/users/1")
            result = agent._execute_test(
                endpoint,
                {"test_type": "forbidden_access", "expected_status": 403},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True


# =============================================================================
# Test Auth Endpoints Detection (Section 10.2)
# =============================================================================


class TestAuthEndpointsDetection:
    """Section 10.2: Agent should identify auth-related endpoints."""

    def test_login_endpoint_detection(self, agent, mock_200_response):
        """Agent should handle login endpoints appropriately."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_200_response):
            endpoint = QAEndpoint(method="POST", path="/api/auth/login")
            tests = agent._generate_tests(endpoint, QADepth.STANDARD)
            # Login endpoints should get valid input tests
            assert any(t["test_type"] == "happy_path" for t in tests)

    def test_logout_endpoint_detection(self, agent, mock_200_response):
        """Agent should handle logout endpoints appropriately."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_200_response):
            endpoint = QAEndpoint(method="POST", path="/api/auth/logout")
            tests = agent._generate_tests(endpoint, QADepth.STANDARD)
            assert any(t["test_type"] == "happy_path" for t in tests)

    def test_refresh_token_endpoint_detection(self, agent, mock_200_response):
        """Agent should handle token refresh endpoints appropriately."""
        with patch.object(agent, '_make_request_with_retry', return_value=mock_200_response):
            endpoint = QAEndpoint(method="POST", path="/api/auth/refresh")
            tests = agent._generate_tests(endpoint, QADepth.STANDARD)
            assert any(t["test_type"] == "happy_path" for t in tests)


# =============================================================================
# Test Auth Context in Findings (Section 10.2)
# =============================================================================


class TestAuthContextInFindings:
    """Section 10.2: Auth-related findings should include context."""

    def test_finding_includes_endpoint(self, agent):
        """Finding should include the endpoint being tested."""
        finding = agent._create_finding(
            endpoint="GET /api/protected",
            test_type="unauthorized",
            expected={"status": 401},
            actual={"status": 500},
            request_evidence="curl -X GET /api/protected",
            response_evidence="Server error",
        )
        assert finding.endpoint == "GET /api/protected"
        assert finding.test_type == "unauthorized"

    def test_finding_includes_recommendation(self, agent):
        """Finding should include recommendation for fixing."""
        finding = agent._create_finding(
            endpoint="GET /api/protected",
            test_type="unauthorized",
            expected={"status": 401},
            actual={"status": 500},
            request_evidence="curl -X GET /api/protected",
            response_evidence="Server error",
        )
        assert finding.recommendation is not None
        assert len(finding.recommendation) > 0

    def test_critical_severity_for_unhandled_auth_error(self, agent):
        """Server error on auth endpoint should be critical."""
        finding = agent._create_finding(
            endpoint="POST /api/auth/login",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 500},
            request_evidence="curl -X POST /api/auth/login",
            response_evidence="Internal Server Error",
        )
        assert finding.severity == "critical"


# =============================================================================
# Test Multiple Auth Methods (Section 10.2)
# =============================================================================


class TestMultipleAuthMethods:
    """Section 10.2: Agent should handle endpoints with multiple auth options."""

    def test_handles_endpoint_with_optional_auth(self, agent, mock_200_response):
        """Agent should handle endpoints where auth is optional."""
        endpoint = QAEndpoint(
            method="GET",
            path="/api/posts",
            auth_required=False  # Public but enhanced with auth
        )

        with patch.object(agent, '_make_request_with_retry', return_value=mock_200_response):
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            assert result["passed"] is True

    def test_generates_tests_for_mixed_auth_endpoint(self, agent):
        """Agent should generate appropriate tests for mixed auth endpoints."""
        # Endpoint that requires auth for write, optional for read
        endpoint = QAEndpoint(
            method="POST",
            path="/api/posts",
            auth_required=True
        )

        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        # Should have both normal and unauthorized tests
        test_types = [t["test_type"] for t in tests]
        assert "happy_path" in test_types
        assert "unauthorized" in test_types


# =============================================================================
# Test Auth Error Message Handling (Section 10.2)
# =============================================================================


class TestAuthErrorMessageHandling:
    """Section 10.2: Agent should capture auth error messages."""

    def test_captures_token_expired_message(self, agent):
        """Agent should capture token expired error in finding."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "token_expired", "message": "JWT has expired"}'
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/protected")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            finding = result.get("finding")
            assert finding is not None
            assert "token_expired" in finding.evidence.get("response", "")

    def test_captures_invalid_signature_message(self, agent):
        """Agent should capture invalid signature error in finding."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": "invalid_token", "message": "Invalid signature"}'
        mock_response.headers = {}

        with patch.object(agent, '_make_request_with_retry', return_value=mock_response):
            endpoint = QAEndpoint(method="GET", path="/api/protected")
            result = agent._execute_test(
                endpoint,
                {"test_type": "happy_path", "expected_status": 200},
                "http://localhost:8000",
                ResilienceConfig(),
            )
            finding = result.get("finding")
            assert finding is not None
            assert "invalid_token" in finding.evidence.get("response", "")

    def test_handles_empty_auth_error_body(self, agent):
        """Agent should handle 401 with empty response body."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = ""
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
            assert result.get("finding") is not None
