"""BehavioralTesterAgent for QA testing.

Implements spec sections 4.1, 10.1-10.5, 10.7:
- Service startup with health endpoint fallback
- Port availability checking
- Retry with exponential backoff
- 429 rate limit detection
- Returns ServiceStartupResult enum (not exceptions)
"""

from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING
from urllib.parse import urlparse

import requests

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.qa.models import (
    ServiceStartupResult,
    QADepth,
    QAEndpoint,
    QAFinding,
    ResilienceConfig,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class HealthEndpointNotFoundError(Exception):
    """Raised when no health endpoint can be found."""
    pass


def check_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check.
        host: Host address to check (default 127.0.0.1).

    Returns:
        True if port is available, False if in use.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        # If connect_ex returns 0, the port is in use (connection succeeded)
        return result != 0
    except socket.error:
        return True  # Error usually means port is available
    finally:
        sock.close()


class BehavioralTesterAgent(BaseAgent):
    """
    Agent that tests APIs by making real HTTP requests.

    Validates responses against expected behavior including:
    - Status codes
    - Response structure
    - Data correctness
    """

    name: str = "behavioral_tester"

    # Health endpoint fallback chain (Section 10.1)
    health_endpoints: list[str] = ["/health", "/healthz", "/api/health", "/_health", "/"]

    # Hard timeout for service startup (Section 10.1)
    startup_timeout_seconds: int = 60

    # Stability check delay after startup (Section 10.1)
    stability_check_delay_seconds: float = 2.5

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the BehavioralTesterAgent."""
        super().__init__(config, logger, **kwargs)
        self._service_process: Optional[subprocess.Popen] = None
        self._finding_counter = 0

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute behavioral tests on the provided endpoints.

        Args:
            context: Dictionary containing:
                - base_url: Base URL for API
                - endpoints: List of QAEndpoint to test
                - depth: QADepth level
                - skip_service_start: Optional bool to skip service startup

        Returns:
            AgentResult with test results and findings.
        """
        base_url = context.get("base_url", "http://localhost:8000")
        endpoints = context.get("endpoints", [])
        depth = context.get("depth", QADepth.SHALLOW)
        skip_start = context.get("skip_service_start", False)

        self._log("behavioral_test_start", {
            "base_url": base_url,
            "endpoint_count": len(endpoints),
            "depth": depth.value if isinstance(depth, QADepth) else depth,
        })

        # Start service if needed
        if not skip_start:
            startup_result = self.start_service(base_url)
            if startup_result != ServiceStartupResult.SUCCESS:
                error_msg = self._get_startup_error_message(startup_result)
                return AgentResult.failure_result(error_msg)

        # Run tests
        try:
            results = self._run_tests(endpoints, base_url, depth)
            return AgentResult.success_result(output=results)
        except Exception as e:
            return AgentResult.failure_result(f"Test execution failed: {e}")

    def start_service(self, base_url: str) -> ServiceStartupResult:
        """
        Start the service and wait for it to be healthy.

        Args:
            base_url: Base URL where service will be available.

        Returns:
            ServiceStartupResult indicating success or failure reason.
        """
        parsed = urlparse(base_url)
        port = parsed.port or 8000
        host = parsed.hostname or "127.0.0.1"

        # Check port availability first (Section 10.1)
        if not check_port_available(port, host):
            self._log("port_conflict", {"port": port}, level="error")
            return ServiceStartupResult.PORT_CONFLICT

        # Try to start the service
        if not self._start_service_process():
            return ServiceStartupResult.STARTUP_CRASHED

        # Wait for health endpoint with timeout
        start_time = time.time()
        health_endpoint = None

        while time.time() - start_time < self.startup_timeout_seconds:
            health_endpoint = self._try_health_endpoints(base_url)
            if health_endpoint:
                # Verify stability (Section 10.1)
                if self._verify_service_stability(base_url):
                    self._log("service_started", {
                        "health_endpoint": health_endpoint,
                        "startup_time": time.time() - start_time,
                    })
                    return ServiceStartupResult.SUCCESS
            time.sleep(0.5)

        # Timeout reached
        if health_endpoint is None:
            return ServiceStartupResult.NO_HEALTH_ENDPOINT
        return ServiceStartupResult.TIMEOUT

    def _start_service_process(self) -> bool:
        """
        Attempt to start the service process.

        Looks for common startup methods:
        - docker-compose.yml
        - Makefile with dev target
        - scripts/dev.sh

        Returns:
            True if process started, False otherwise.
        """
        repo_root = Path(self.config.repo_root)

        # Try docker-compose first
        docker_compose = repo_root / "docker-compose.yml"
        if docker_compose.exists():
            try:
                self._service_process = subprocess.Popen(
                    ["docker-compose", "up", "-d"],
                    cwd=repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return True
            except Exception as e:
                self._log("docker_start_failed", {"error": str(e)}, level="error")

        # Try Makefile
        makefile = repo_root / "Makefile"
        if makefile.exists():
            try:
                self._service_process = subprocess.Popen(
                    ["make", "dev"],
                    cwd=repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return True
            except Exception:
                pass

        # Try scripts/dev.sh
        dev_script = repo_root / "scripts" / "dev.sh"
        if dev_script.exists():
            try:
                self._service_process = subprocess.Popen(
                    ["bash", str(dev_script)],
                    cwd=repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return True
            except Exception:
                pass

        # No startup method found - assume service is already running
        return True

    def _try_health_endpoints(self, base_url: str) -> Optional[str]:
        """
        Try health endpoints in order until one succeeds.

        Args:
            base_url: Base URL for the service.

        Returns:
            The path of the first healthy endpoint, or None if all fail.
        """
        for endpoint in self.health_endpoints:
            url = f"{base_url.rstrip('/')}{endpoint}"
            try:
                response = requests.get(url, timeout=5)
                # Accept any 2xx for dedicated health endpoints
                if endpoint != "/" and 200 <= response.status_code < 300:
                    return endpoint
                # For root path, accept any response (means server is running)
                if endpoint == "/":
                    return endpoint
            except Exception:
                continue
        return None

    def _verify_service_stability(self, base_url: str) -> bool:
        """
        Verify service remains healthy after initial startup.

        Waits 2-3 seconds and checks health again to catch
        services that crash immediately after startup (Section 10.1).

        Args:
            base_url: Base URL for the service.

        Returns:
            True if service is stable, False if it crashed.
        """
        # Initial health check
        initial = self._try_health_endpoints(base_url)
        if not initial:
            return False

        # Wait for stability
        time.sleep(self.stability_check_delay_seconds)

        # Check again
        final = self._try_health_endpoints(base_url)
        return final is not None

    def _run_tests(
        self,
        endpoints: list[QAEndpoint],
        base_url: str,
        depth: QADepth,
    ) -> dict[str, Any]:
        """
        Run behavioral tests on all endpoints.

        Args:
            endpoints: List of endpoints to test.
            base_url: Base URL for requests.
            depth: Testing depth level.

        Returns:
            Dictionary with test results and findings.
        """
        tests_run = 0
        tests_passed = 0
        tests_failed = 0
        findings: list[QAFinding] = []

        resilience = ResilienceConfig()

        for endpoint in endpoints:
            test_cases = self._generate_tests(endpoint, depth)

            for test_case in test_cases:
                tests_run += 1
                try:
                    result = self._execute_test(
                        endpoint, test_case, base_url, resilience
                    )
                    if result["passed"]:
                        tests_passed += 1
                    else:
                        tests_failed += 1
                        if result.get("finding"):
                            findings.append(result["finding"])
                except Exception as e:
                    tests_failed += 1
                    self._log("test_execution_error", {
                        "endpoint": f"{endpoint.method} {endpoint.path}",
                        "error": str(e),
                    }, level="error")

        return {
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "findings": findings,
        }

    def _generate_tests(
        self,
        endpoint: QAEndpoint,
        depth: QADepth,
    ) -> list[dict[str, Any]]:
        """
        Generate test cases for an endpoint based on depth.

        Args:
            endpoint: The endpoint to test.
            depth: Testing depth level.

        Returns:
            List of test case dictionaries.
        """
        tests = []

        # Happy path for all depths
        tests.append({
            "test_type": "happy_path",
            "expected_status": 200 if endpoint.method == "GET" else 201,
            "body": self._generate_valid_body(endpoint),
        })

        # Error cases for standard+ depth
        if depth in [QADepth.STANDARD, QADepth.DEEP, QADepth.REGRESSION]:
            if endpoint.method in ["POST", "PUT", "PATCH"]:
                tests.append({
                    "test_type": "invalid_input",
                    "expected_status": 400,
                    "body": {},  # Empty body should be invalid
                })
                tests.append({
                    "test_type": "error_case",
                    "expected_status": 400,
                    "body": {"invalid_field": "test"},
                })

            # Auth error test
            if endpoint.auth_required:
                tests.append({
                    "test_type": "unauthorized",
                    "expected_status": 401,
                    "skip_auth": True,
                })

        # Security probes for deep depth
        if depth == QADepth.DEEP:
            if endpoint.method in ["POST", "PUT", "PATCH"]:
                tests.append({
                    "test_type": "security_probe",
                    "probe_type": "sql_injection",
                    "body": {"name": "'; DROP TABLE users; --"},
                    "expected_status": 400,
                })
                tests.append({
                    "test_type": "security_probe",
                    "probe_type": "xss",
                    "body": {"name": "<script>alert('xss')</script>"},
                    "expected_status": 400,
                })

        return tests

    def _generate_valid_body(self, endpoint: QAEndpoint) -> dict[str, Any]:
        """Generate a valid request body based on endpoint schema."""
        if endpoint.schema and endpoint.schema.get("requestBody"):
            # TODO: Generate from schema
            return {}

        # Default bodies based on common patterns
        if "user" in endpoint.path.lower():
            return {"name": "Test User", "email": "test@example.com"}
        if "item" in endpoint.path.lower():
            return {"name": "Test Item", "quantity": 1}

        return {}

    def _execute_test(
        self,
        endpoint: QAEndpoint,
        test_case: dict[str, Any],
        base_url: str,
        resilience: ResilienceConfig,
    ) -> dict[str, Any]:
        """
        Execute a single test case.

        Args:
            endpoint: The endpoint being tested.
            test_case: Test case specification.
            base_url: Base URL for requests.
            resilience: Retry configuration.

        Returns:
            Dictionary with test result and optional finding.
        """
        url = f"{base_url.rstrip('/')}{endpoint.path}"
        method = endpoint.method
        body = test_case.get("body")
        expected_status = test_case.get("expected_status", 200)

        try:
            response = self._make_request_with_retry(
                method, url, json=body, resilience=resilience
            )

            passed = response.status_code == expected_status

            if not passed:
                finding = self._create_finding(
                    endpoint=f"{method} {endpoint.path}",
                    test_type=test_case["test_type"],
                    expected={"status": expected_status},
                    actual={"status": response.status_code},
                    request_evidence=f"curl -X {method} {url}",
                    response_evidence=response.text[:500] if response.text else "",
                )
                return {"passed": False, "finding": finding}

            return {"passed": True}

        except Exception as e:
            finding = self._create_finding(
                endpoint=f"{method} {endpoint.path}",
                test_type=test_case["test_type"],
                expected={"status": expected_status},
                actual={"error": str(e)},
                request_evidence=f"curl -X {method} {url}",
                response_evidence=str(e),
            )
            return {"passed": False, "finding": finding}

    def _make_request_with_retry(
        self,
        method: str,
        url: str,
        resilience: ResilienceConfig,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Make an HTTP request with retry and backoff logic.

        Args:
            method: HTTP method.
            url: Request URL.
            resilience: Retry configuration.
            **kwargs: Additional arguments for requests.

        Returns:
            Response object.

        Raises:
            Exception if all retries exhausted.
        """
        last_exception: Optional[Exception] = None
        delay = resilience.retry_backoff_seconds

        for attempt in range(resilience.max_retries):
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=resilience.request_timeout_seconds,
                    **kwargs,
                )

                # Check for rate limiting
                is_rate_limited, _ = self._check_rate_limit(response, resilience)
                if is_rate_limited and attempt < resilience.max_retries - 1:
                    retry_after = self._get_retry_after(response, resilience)
                    time.sleep(retry_after)
                    continue

                # Check for retryable status codes
                if response.status_code in resilience.retry_on_status:
                    if attempt < resilience.max_retries - 1:
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                        continue

                return response

            except (ConnectionError, requests.exceptions.RequestException) as e:
                last_exception = e
                if attempt < resilience.max_retries - 1:
                    time.sleep(delay)
                    delay *= 2

        if last_exception:
            raise last_exception
        raise Exception("Request failed after all retries")

    def _check_rate_limit(
        self,
        response: requests.Response,
        resilience: ResilienceConfig,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if response indicates rate limiting.

        Args:
            response: HTTP response.
            resilience: Retry configuration.

        Returns:
            Tuple of (is_rate_limited, retry_after_seconds).
        """
        if response.status_code == 429:
            retry_after = self._get_retry_after(response, resilience)
            return True, retry_after
        return False, None

    def _get_retry_after(
        self,
        response: requests.Response,
        resilience: ResilienceConfig,
    ) -> float:
        """Get retry delay from Retry-After header or default."""
        if resilience.respect_retry_after:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return resilience.retry_backoff_seconds

    def _create_finding(
        self,
        endpoint: str,
        test_type: str,
        expected: dict[str, Any],
        actual: dict[str, Any],
        request_evidence: str,
        response_evidence: str,
    ) -> QAFinding:
        """
        Create a QAFinding from test failure.

        Args:
            endpoint: Endpoint being tested.
            test_type: Type of test that failed.
            expected: Expected values.
            actual: Actual values.
            request_evidence: Request details.
            response_evidence: Response details.

        Returns:
            QAFinding object.
        """
        self._finding_counter += 1
        finding_id = f"BT-{self._finding_counter:03d}"

        # Determine severity
        actual_status = actual.get("status", 0)
        if actual_status >= 500:
            severity = "critical"
            title = f"Server error ({actual_status})"
        elif actual.get("error"):
            severity = "critical"
            title = "Request failed"
        elif expected.get("status", 200) != actual_status:
            severity = "moderate"
            title = f"Wrong status code (expected {expected.get('status')}, got {actual_status})"
        else:
            severity = "minor"
            title = "Unexpected response"

        return QAFinding(
            finding_id=finding_id,
            severity=severity,
            category="behavioral",
            endpoint=endpoint,
            test_type=test_type,
            title=title,
            description=f"Test '{test_type}' failed for endpoint {endpoint}",
            expected=expected,
            actual=actual,
            evidence={
                "request": request_evidence,
                "response": response_evidence,
            },
            recommendation=self._get_recommendation(severity, test_type),
        )

    def _get_recommendation(self, severity: str, test_type: str) -> str:
        """Generate recommendation based on severity and test type."""
        if severity == "critical":
            return "Investigate server error immediately. Check logs for stack traces."
        elif test_type == "security_probe":
            return "Review input validation and sanitization."
        elif severity == "moderate":
            return "Update handler to return correct status code."
        else:
            return "Review response format and update if necessary."

    def _get_startup_error_message(self, result: ServiceStartupResult) -> str:
        """Get human-readable error message for startup failure."""
        messages = {
            ServiceStartupResult.PORT_CONFLICT: "Port is already in use. Stop the existing service or use a different port.",
            ServiceStartupResult.TIMEOUT: "Service startup timed out after 60 seconds.",
            ServiceStartupResult.STARTUP_CRASHED: "Service process crashed during startup.",
            ServiceStartupResult.NO_HEALTH_ENDPOINT: "No health endpoint responded. Ensure service has /health, /healthz, or similar endpoint.",
            ServiceStartupResult.DOCKER_UNAVAILABLE: "Docker is not available or not running.",
        }
        return messages.get(result, f"Service startup failed: {result.value}")
