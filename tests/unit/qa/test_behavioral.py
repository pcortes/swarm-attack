"""Tests for BehavioralTesterAgent following TDD approach.

Tests cover spec sections 4.1, 10.1-10.5, 10.7:
- Service startup with health endpoint fallback
- Port availability checking
- Retry with exponential backoff
- 429 rate limit detection
- ServiceStartupResult enum (not exceptions)
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import socket
import time

from swarm_attack.qa.models import (
    ServiceStartupResult, QAContext, QAEndpoint, QADepth,
    ResilienceConfig, QAFinding,
)
from swarm_attack.qa.agents.behavioral import (
    BehavioralTesterAgent,
    check_port_available,
    HealthEndpointNotFoundError,
)


class TestCheckPortAvailable:
    """Tests for check_port_available() function (Section 10.1)."""

    def test_port_available_returns_true(self):
        """Available port should return True."""
        # Use a high port that's unlikely to be in use
        assert check_port_available(59999) is True

    def test_port_in_use_returns_false(self):
        """Port in use should return False."""
        # Create a socket and bind to a port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', 59998))
            sock.listen(1)
            # Now the port is in use
            assert check_port_available(59998) is False
        finally:
            sock.close()

    def test_port_available_handles_host_parameter(self):
        """Should accept custom host parameter."""
        assert check_port_available(59997, host='127.0.0.1') is True


class TestBehavioralTesterAgentInit:
    """Tests for BehavioralTesterAgent initialization."""

    def test_agent_has_correct_name(self):
        """Agent should have correct name for logging."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = BehavioralTesterAgent(config)
        assert agent.name == "behavioral_tester"

    def test_agent_default_health_endpoints(self):
        """Agent should have default health endpoint fallback list."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = BehavioralTesterAgent(config)
        expected = ["/health", "/healthz", "/api/health", "/_health", "/"]
        assert agent.health_endpoints == expected

    def test_agent_default_startup_timeout(self):
        """Agent should have 60s startup timeout (Section 10.1)."""
        config = MagicMock()
        config.repo_root = "/tmp/test"
        agent = BehavioralTesterAgent(config)
        assert agent.startup_timeout_seconds == 60


class TestServiceStartup:
    """Tests for start_service() method (Section 10.1)."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_start_service_returns_success_when_healthy(self, agent):
        """Should return SUCCESS when health check passes."""
        with patch.object(agent, '_try_health_endpoints') as mock_health:
            mock_health.return_value = "/health"
            with patch.object(agent, '_start_service_process') as mock_start:
                mock_start.return_value = True
                result = agent.start_service("http://localhost:8000")
                assert result == ServiceStartupResult.SUCCESS

    def test_start_service_returns_no_health_endpoint_after_timeout(self, agent):
        """Should return NO_HEALTH_ENDPOINT when no endpoint responds after timeout."""
        with patch.object(agent, '_try_health_endpoints') as mock_health:
            mock_health.return_value = None  # Never healthy - no endpoint responds
            with patch.object(agent, '_start_service_process') as mock_start:
                mock_start.return_value = True
                with patch('time.time') as mock_time:
                    # Simulate timeout by making time.time() return values that exceed timeout
                    mock_time.side_effect = [0, 0, 61]  # start, check, exceed timeout
                    result = agent.start_service("http://localhost:8000")
                    # When no health endpoint responds, return NO_HEALTH_ENDPOINT
                    assert result == ServiceStartupResult.NO_HEALTH_ENDPOINT

    def test_start_service_returns_timeout_when_stability_check_fails(self, agent):
        """Should return TIMEOUT when stability check fails repeatedly."""
        with patch.object(agent, '_start_service_process') as mock_start:
            mock_start.return_value = True
            with patch('swarm_attack.qa.agents.behavioral.check_port_available') as mock_port:
                mock_port.return_value = True
                with patch.object(agent, '_try_health_endpoints') as mock_health:
                    # Health endpoint found initially
                    mock_health.return_value = "/health"
                    with patch.object(agent, '_verify_service_stability') as mock_stable:
                        # But stability check keeps failing
                        mock_stable.return_value = False
                        with patch('time.time') as mock_time:
                            mock_time.side_effect = [0, 0, 0, 61]
                            result = agent.start_service("http://localhost:8000")
                            assert result == ServiceStartupResult.TIMEOUT

    def test_start_service_returns_port_conflict(self, agent):
        """Should return PORT_CONFLICT when port is in use."""
        with patch('swarm_attack.qa.agents.behavioral.check_port_available') as mock_port:
            mock_port.return_value = False
            result = agent.start_service("http://localhost:8000")
            assert result == ServiceStartupResult.PORT_CONFLICT

    def test_start_service_returns_startup_crashed(self, agent):
        """Should return STARTUP_CRASHED when process fails to start."""
        with patch.object(agent, '_start_service_process') as mock_start:
            mock_start.return_value = False  # Failed to start
            with patch('swarm_attack.qa.agents.behavioral.check_port_available') as mock_port:
                mock_port.return_value = True
                result = agent.start_service("http://localhost:8000")
                assert result == ServiceStartupResult.STARTUP_CRASHED

    def test_start_service_returns_no_health_endpoint(self, agent):
        """Should return NO_HEALTH_ENDPOINT when no health endpoint found."""
        with patch.object(agent, '_start_service_process') as mock_start:
            mock_start.return_value = True
            with patch('swarm_attack.qa.agents.behavioral.check_port_available') as mock_port:
                mock_port.return_value = True
                with patch.object(agent, '_try_health_endpoints') as mock_health:
                    mock_health.return_value = None  # No endpoint works
                    with patch('time.time') as mock_time:
                        mock_time.side_effect = [0, 0, 61]  # Simulate timeout
                        result = agent.start_service("http://localhost:8000")
                        assert result == ServiceStartupResult.NO_HEALTH_ENDPOINT


class TestHealthEndpointFallback:
    """Tests for health endpoint fallback chain (Section 10.1)."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_tries_health_endpoint_first(self, agent):
        """Should try /health first."""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            result = agent._try_health_endpoints("http://localhost:8000")
            mock_get.assert_called_with(
                "http://localhost:8000/health",
                timeout=5
            )
            assert result == "/health"

    def test_falls_back_to_healthz(self, agent):
        """Should try /healthz if /health fails."""
        with patch('requests.get') as mock_get:
            def side_effect(url, **kwargs):
                if "/health" in url and "/healthz" not in url:
                    raise Exception("Connection refused")
                response = MagicMock()
                response.status_code = 200
                return response
            mock_get.side_effect = side_effect
            result = agent._try_health_endpoints("http://localhost:8000")
            assert result == "/healthz"

    def test_tries_all_endpoints_in_order(self, agent):
        """Should try all endpoints: /health, /healthz, /api/health, /_health, /"""
        with patch('requests.get') as mock_get:
            calls = []
            def side_effect(url, **kwargs):
                calls.append(url)
                raise Exception("Connection refused")
            mock_get.side_effect = side_effect
            result = agent._try_health_endpoints("http://localhost:8000")
            assert result is None
            expected_paths = ["/health", "/healthz", "/api/health", "/_health", "/"]
            for path in expected_paths:
                assert any(path in call for call in calls)

    def test_accepts_2xx_status_codes(self, agent):
        """Should accept any 2xx status code as healthy."""
        for status in [200, 201, 204]:
            with patch('requests.get') as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = status
                mock_get.return_value = mock_response
                result = agent._try_health_endpoints("http://localhost:8000")
                assert result == "/health"

    def test_rejects_non_2xx_status(self, agent):
        """Should reject non-2xx status codes."""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response
            # Only / endpoint should accept non-200 as it means "server is running"
            result = agent._try_health_endpoints("http://localhost:8000")
            # Should fall through to root path
            assert result in [None, "/"]


class TestRetryWithBackoff:
    """Tests for retry with exponential backoff (Section 10.7)."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_retries_on_connection_error(self, agent):
        """Should retry requests on connection errors."""
        call_count = [0]
        with patch('requests.request') as mock_request:
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] < 3:
                    raise ConnectionError("Connection refused")
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {}
                return response
            mock_request.side_effect = side_effect

            resilience = ResilienceConfig(max_retries=3)
            result = agent._make_request_with_retry(
                "GET", "http://localhost:8000/api/test",
                resilience=resilience
            )
            assert call_count[0] == 3

    def test_exponential_backoff_timing(self, agent):
        """Should use exponential backoff between retries."""
        delays = []
        original_sleep = time.sleep

        with patch('requests.request') as mock_request:
            mock_request.side_effect = ConnectionError("fail")
            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda x: delays.append(x)
                resilience = ResilienceConfig(
                    max_retries=3,
                    retry_backoff_seconds=1.0
                )
                try:
                    agent._make_request_with_retry(
                        "GET", "http://localhost:8000/test",
                        resilience=resilience
                    )
                except:
                    pass
                # Should have delays of 1.0, 2.0 (exponential)
                assert len(delays) == 2  # 3 attempts = 2 delays
                assert delays[0] == 1.0
                assert delays[1] == 2.0


class TestRateLimitDetection:
    """Tests for 429 rate limit detection (Section 10.7)."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_detects_429_status(self, agent):
        """Should detect 429 Too Many Requests."""
        with patch('requests.request') as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.headers = {}
            mock_request.return_value = mock_response

            resilience = ResilienceConfig(retry_on_status=[429])
            is_rate_limited, response = agent._check_rate_limit(mock_response, resilience)
            assert is_rate_limited is True

    def test_respects_retry_after_header(self, agent):
        """Should respect Retry-After header value."""
        with patch('requests.request') as mock_request:
            call_count = [0]
            delays = []

            def side_effect(*args, **kwargs):
                call_count[0] += 1
                response = MagicMock()
                if call_count[0] == 1:
                    response.status_code = 429
                    response.headers = {"Retry-After": "5"}
                else:
                    response.status_code = 200
                    response.headers = {}
                    response.json.return_value = {}
                return response

            mock_request.side_effect = side_effect

            with patch('time.sleep') as mock_sleep:
                mock_sleep.side_effect = lambda x: delays.append(x)
                resilience = ResilienceConfig(
                    retry_on_status=[429],
                    respect_retry_after=True
                )
                result = agent._make_request_with_retry(
                    "GET", "http://localhost:8000/test",
                    resilience=resilience
                )
                # Should have waited 5 seconds as per Retry-After header
                assert 5 in delays or 5.0 in delays

    def test_retries_on_502_503_504(self, agent):
        """Should retry on 502, 503, 504 status codes."""
        for status in [502, 503, 504]:
            call_count = [0]
            with patch('requests.request') as mock_request:
                def side_effect(*args, **kwargs):
                    call_count[0] += 1
                    response = MagicMock()
                    if call_count[0] < 2:
                        response.status_code = status
                        response.headers = {}
                    else:
                        response.status_code = 200
                        response.headers = {}
                        response.json.return_value = {}
                    return response

                mock_request.side_effect = side_effect
                resilience = ResilienceConfig(retry_on_status=[429, 502, 503, 504])
                result = agent._make_request_with_retry(
                    "GET", "http://localhost:8000/test",
                    resilience=resilience
                )
                assert call_count[0] == 2


class TestBehavioralTestExecution:
    """Tests for actual behavioral test execution."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_generates_happy_path_tests(self, agent):
        """Should generate happy path tests for endpoints."""
        endpoint = QAEndpoint(method="GET", path="/api/users")
        tests = agent._generate_tests(endpoint, QADepth.SHALLOW)
        # Shallow should only have happy path
        assert len(tests) >= 1
        assert any(t["test_type"] == "happy_path" for t in tests)

    def test_generates_error_cases_for_standard_depth(self, agent):
        """Should generate error cases for standard depth."""
        endpoint = QAEndpoint(method="POST", path="/api/users")
        tests = agent._generate_tests(endpoint, QADepth.STANDARD)
        test_types = [t["test_type"] for t in tests]
        assert "happy_path" in test_types
        assert "error_case" in test_types or "invalid_input" in test_types

    def test_generates_security_probes_for_deep_depth(self, agent):
        """Should generate security probes for deep depth."""
        endpoint = QAEndpoint(method="POST", path="/api/users")
        tests = agent._generate_tests(endpoint, QADepth.DEEP)
        test_types = [t["test_type"] for t in tests]
        assert "security_probe" in test_types or any("security" in t for t in test_types)


class TestFindingGeneration:
    """Tests for QAFinding generation from test failures."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_creates_finding_on_status_mismatch(self, agent):
        """Should create finding when actual status differs from expected."""
        finding = agent._create_finding(
            endpoint="POST /api/users",
            test_type="happy_path",
            expected={"status": 201},
            actual={"status": 200},
            request_evidence="curl -X POST ...",
            response_evidence='{"id": 1}'
        )
        assert finding.severity in ["critical", "moderate", "minor"]
        assert finding.endpoint == "POST /api/users"
        assert finding.expected == {"status": 201}
        assert finding.actual == {"status": 200}

    def test_assigns_critical_severity_for_5xx(self, agent):
        """Should assign critical severity for 5xx errors."""
        finding = agent._create_finding(
            endpoint="GET /api/users",
            test_type="happy_path",
            expected={"status": 200},
            actual={"status": 500},
            request_evidence="curl ...",
            response_evidence="Internal Server Error"
        )
        assert finding.severity == "critical"

    def test_assigns_moderate_severity_for_wrong_status(self, agent):
        """Should assign moderate severity for wrong success status."""
        finding = agent._create_finding(
            endpoint="POST /api/users",
            test_type="happy_path",
            expected={"status": 201},
            actual={"status": 200},
            request_evidence="curl ...",
            response_evidence='{}'
        )
        assert finding.severity == "moderate"


class TestAgentRun:
    """Tests for the main run() method."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_run_returns_agent_result(self, agent):
        """Should return AgentResult from run()."""
        context = {
            "base_url": "http://localhost:8000",
            "endpoints": [QAEndpoint(method="GET", path="/api/test")],
            "depth": QADepth.SHALLOW,
        }
        with patch.object(agent, 'start_service') as mock_start:
            mock_start.return_value = ServiceStartupResult.SUCCESS
            with patch.object(agent, '_run_tests') as mock_tests:
                mock_tests.return_value = {
                    "tests_run": 1,
                    "tests_passed": 1,
                    "tests_failed": 0,
                    "findings": [],
                }
                result = agent.run(context)
                assert hasattr(result, 'success')
                assert hasattr(result, 'output')

    def test_run_blocked_on_startup_failure(self, agent):
        """Should return blocked result on startup failure."""
        context = {
            "base_url": "http://localhost:8000",
            "endpoints": [QAEndpoint(method="GET", path="/api/test")],
            "depth": QADepth.SHALLOW,
        }
        with patch.object(agent, 'start_service') as mock_start:
            mock_start.return_value = ServiceStartupResult.PORT_CONFLICT
            result = agent.run(context)
            assert result.success is False
            assert "port" in result.error.lower() or "blocked" in result.error.lower()

    def test_run_includes_findings_in_output(self, agent):
        """Should include findings in output."""
        context = {
            "base_url": "http://localhost:8000",
            "endpoints": [QAEndpoint(method="GET", path="/api/test")],
            "depth": QADepth.SHALLOW,
            "skip_service_start": True,
        }
        test_finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/test",
            test_type="happy_path",
            title="500 Error",
            description="Server returned 500",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl ...", "response": "error"},
            recommendation="Fix server error",
        )
        with patch.object(agent, '_run_tests') as mock_tests:
            mock_tests.return_value = {
                "tests_run": 1,
                "tests_passed": 0,
                "tests_failed": 1,
                "findings": [test_finding],
            }
            result = agent.run(context)
            assert result.output is not None
            assert "findings" in result.output
            assert len(result.output["findings"]) == 1


class TestServiceStabilityCheck:
    """Tests for post-startup stability check (Section 10.1)."""

    @pytest.fixture
    def agent(self):
        config = MagicMock()
        config.repo_root = "/tmp/test"
        return BehavioralTesterAgent(config)

    def test_verifies_service_still_running_after_startup(self, agent):
        """Should verify service is still running 2-3 seconds after startup."""
        with patch.object(agent, '_try_health_endpoints') as mock_health:
            call_count = [0]
            def side_effect(base_url):
                call_count[0] += 1
                return "/health"
            mock_health.side_effect = side_effect

            with patch('time.sleep'):
                agent._verify_service_stability("http://localhost:8000")
                # Should call health check at least twice (initial + stability check)
                assert call_count[0] >= 2

    def test_returns_false_if_service_crashes_after_startup(self, agent):
        """Should return False if service crashes after initial health check."""
        with patch.object(agent, '_try_health_endpoints') as mock_health:
            call_count = [0]
            def side_effect(base_url):
                call_count[0] += 1
                if call_count[0] == 1:
                    return "/health"  # Initial check passes
                return None  # Stability check fails
            mock_health.side_effect = side_effect

            with patch('time.sleep'):
                stable = agent._verify_service_stability("http://localhost:8000")
                assert stable is False
