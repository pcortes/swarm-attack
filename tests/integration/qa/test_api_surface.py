"""API Surface Tests.

Verifies the public API is stable and documented.
These tests serve as living documentation of the public interfaces.

Priority 11: API Documentation Tests
"""

import inspect
from datetime import datetime, timezone
from typing import Any, Optional, get_type_hints
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.qa.models import (
    AuthStrategy,
    QABug,
    QAContext,
    QADepth,
    QAEndpoint,
    QAFinding,
    QALimits,
    QARecommendation,
    QAResult,
    QASafetyConfig,
    QASession,
    QAStatus,
    QATrigger,
    ResilienceConfig,
    ServiceStartupResult,
    TestDataConfig,
)
from swarm_attack.qa.orchestrator import QAOrchestrator
from swarm_attack.qa.context_builder import QAContextBuilder, EndpointDiscoveryError
from swarm_attack.qa.depth_selector import DepthSelector
from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook, VerifierHookResult
from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook, BugHookResult


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


# =============================================================================
# TEST: QA ORCHESTRATOR PUBLIC API
# =============================================================================


class TestOrchestratorAPI:
    """Tests for QAOrchestrator public API."""

    def test_init_signature(self):
        """__init__ should accept config, logger, and limits."""
        sig = inspect.signature(QAOrchestrator.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "config" in params
        assert "logger" in params
        assert "limits" in params

    def test_test_method_signature(self):
        """test() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.test)
        params = list(sig.parameters.keys())

        # Required parameters
        assert "self" in params
        assert "target" in params

        # Optional parameters
        assert "depth" in params
        assert "trigger" in params
        assert "base_url" in params
        assert "timeout" in params

    def test_test_method_returns_qa_session(self, mock_config, mock_logger, tmp_path):
        """test() method should return QASession."""
        mock_config.repo_root = str(tmp_path)
        (tmp_path / ".swarm" / "qa").mkdir(parents=True)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)
                    result = orchestrator.test("/api/users")

                    assert isinstance(result, QASession)

    def test_validate_issue_method_signature(self):
        """validate_issue() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.validate_issue)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "feature_id" in params
        assert "issue_number" in params
        assert "depth" in params

    def test_validate_issue_returns_qa_session(self, mock_config, mock_logger, tmp_path):
        """validate_issue() method should return QASession."""
        mock_config.repo_root = str(tmp_path)
        (tmp_path / ".swarm" / "qa").mkdir(parents=True)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)
                    result = orchestrator.validate_issue("test-feature", 1)

                    assert isinstance(result, QASession)

    def test_health_check_method_signature(self):
        """health_check() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.health_check)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "base_url" in params

    def test_health_check_returns_qa_session(self, mock_config, mock_logger, tmp_path):
        """health_check() method should return QASession."""
        mock_config.repo_root = str(tmp_path)
        (tmp_path / ".swarm" / "qa").mkdir(parents=True)

        with patch("swarm_attack.qa.orchestrator.BehavioralTesterAgent") as mock_bta:
            with patch("swarm_attack.qa.orchestrator.ContractValidatorAgent") as mock_cva:
                with patch("swarm_attack.qa.orchestrator.RegressionScannerAgent") as mock_rsa:
                    mock_agent = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.output = {"tests_run": 1, "tests_passed": 1, "tests_failed": 0}
                    mock_agent.run.return_value = mock_result

                    mock_bta.return_value = mock_agent
                    mock_cva.return_value = mock_agent
                    mock_rsa.return_value = mock_agent

                    orchestrator = QAOrchestrator(mock_config, mock_logger)
                    result = orchestrator.health_check()

                    assert isinstance(result, QASession)

    def test_dispatch_agents_signature(self):
        """dispatch_agents() should have correct signature."""
        sig = inspect.signature(QAOrchestrator.dispatch_agents)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "depth" in params
        assert "context" in params

    def test_get_session_method_signature(self):
        """get_session() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.get_session)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "session_id" in params

    def test_list_sessions_method_signature(self):
        """list_sessions() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.list_sessions)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "limit" in params

    def test_get_findings_method_signature(self):
        """get_findings() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.get_findings)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "session_id" in params
        assert "severity" in params

    def test_create_bug_investigations_method_signature(self):
        """create_bug_investigations() method should have correct signature."""
        sig = inspect.signature(QAOrchestrator.create_bug_investigations)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "session_id" in params
        assert "severity_threshold" in params


# =============================================================================
# TEST: CONTEXT BUILDER PUBLIC API
# =============================================================================


class TestContextBuilderAPI:
    """Tests for QAContextBuilder public API."""

    def test_init_signature(self):
        """__init__ should accept config and logger."""
        sig = inspect.signature(QAContextBuilder.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "config" in params
        assert "logger" in params

    def test_build_context_method_signature(self):
        """build_context() method should have correct signature."""
        sig = inspect.signature(QAContextBuilder.build_context)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "trigger" in params
        assert "target" in params
        assert "feature_id" in params
        assert "issue_number" in params
        assert "bug_id" in params
        assert "base_url" in params
        assert "explicit_endpoints" in params

    def test_build_context_returns_qa_context(self, mock_config, mock_logger):
        """build_context() should return QAContext."""
        builder = QAContextBuilder(mock_config, mock_logger)
        result = builder.build_context(
            trigger=QATrigger.USER_COMMAND,
            target="/api/users",
        )

        assert isinstance(result, QAContext)

    def test_discover_endpoints_method_signature(self):
        """discover_endpoints() method should have correct signature."""
        sig = inspect.signature(QAContextBuilder.discover_endpoints)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "target" in params

    def test_discover_endpoints_required_method_exists(self):
        """discover_endpoints_required() method should exist."""
        assert hasattr(QAContextBuilder, "discover_endpoints_required")
        assert callable(getattr(QAContextBuilder, "discover_endpoints_required"))

    def test_extract_schemas_method_signature(self):
        """extract_schemas() method should have correct signature."""
        sig = inspect.signature(QAContextBuilder.extract_schemas)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "endpoints" in params

    def test_find_consumers_method_signature(self):
        """find_consumers() method should have correct signature."""
        sig = inspect.signature(QAContextBuilder.find_consumers)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "endpoints" in params


# =============================================================================
# TEST: DEPTH SELECTOR PUBLIC API
# =============================================================================


class TestDepthSelectorAPI:
    """Tests for DepthSelector public API."""

    def test_init_signature(self):
        """__init__ should accept config and logger."""
        sig = inspect.signature(DepthSelector.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "config" in params
        assert "logger" in params

    def test_select_depth_method_signature(self):
        """select_depth() method should have correct signature."""
        sig = inspect.signature(DepthSelector.select_depth)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "trigger" in params
        assert "context" in params
        assert "risk_score" in params
        assert "time_budget_minutes" in params
        assert "cost_budget_usd" in params
        assert "override_depth" in params

    def test_select_depth_returns_qa_depth(self, mock_config, mock_logger):
        """select_depth() should return QADepth."""
        selector = DepthSelector(mock_config, mock_logger)
        context = QAContext()

        result = selector.select_depth(
            trigger=QATrigger.USER_COMMAND,
            context=context,
        )

        assert isinstance(result, QADepth)

    def test_calculate_risk_score_method_signature(self):
        """calculate_risk_score() method should have correct signature."""
        sig = inspect.signature(DepthSelector.calculate_risk_score)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "context" in params

    def test_calculate_risk_score_returns_float(self, mock_config, mock_logger):
        """calculate_risk_score() should return float between 0 and 1."""
        selector = DepthSelector(mock_config, mock_logger)
        context = QAContext()

        result = selector.calculate_risk_score(context)

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_get_estimated_cost_method_signature(self):
        """get_estimated_cost() method should have correct signature."""
        sig = inspect.signature(DepthSelector.get_estimated_cost)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "depth" in params

    def test_get_estimated_time_method_signature(self):
        """get_estimated_time() method should have correct signature."""
        sig = inspect.signature(DepthSelector.get_estimated_time)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "depth" in params

    def test_class_constants_exist(self):
        """Class constants should be defined."""
        assert hasattr(DepthSelector, "HIGH_RISK_PATTERNS")
        assert hasattr(DepthSelector, "DEPTH_COSTS")
        assert hasattr(DepthSelector, "DEPTH_TIMES")

        assert isinstance(DepthSelector.HIGH_RISK_PATTERNS, list)
        assert isinstance(DepthSelector.DEPTH_COSTS, dict)
        assert isinstance(DepthSelector.DEPTH_TIMES, dict)


# =============================================================================
# TEST: QA MODELS PUBLIC API
# =============================================================================


class TestModelsAPI:
    """Tests for QA models public API."""

    def test_qa_session_required_fields(self):
        """QASession should have required fields."""
        # These fields should be in the dataclass
        hints = get_type_hints(QASession)

        assert "session_id" in hints
        assert "trigger" in hints
        assert "depth" in hints
        assert "status" in hints
        assert "context" in hints

    def test_qa_session_serialization(self):
        """QASession should serialize to dict correctly."""
        context = QAContext(base_url="http://localhost:8000")
        session = QASession(
            session_id="test-session-001",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=context,
        )

        result = session.to_dict()

        assert isinstance(result, dict)
        assert result["session_id"] == "test-session-001"
        assert result["trigger"] == "user_command"
        assert result["depth"] == "standard"
        assert result["status"] == "completed"
        assert "context" in result

    def test_qa_session_deserialization(self):
        """QASession should deserialize from dict correctly."""
        data = {
            "session_id": "test-session-001",
            "trigger": "user_command",
            "depth": "standard",
            "status": "completed",
            "context": {
                "base_url": "http://localhost:8000",
                "target_files": [],
            },
        }

        session = QASession.from_dict(data)

        assert isinstance(session, QASession)
        assert session.session_id == "test-session-001"
        assert session.trigger == QATrigger.USER_COMMAND
        assert session.depth == QADepth.STANDARD
        assert session.status == QAStatus.COMPLETED

    def test_qa_finding_required_fields(self):
        """QAFinding should have required fields."""
        hints = get_type_hints(QAFinding)

        assert "finding_id" in hints
        assert "severity" in hints
        assert "category" in hints
        assert "endpoint" in hints
        assert "test_type" in hints
        assert "title" in hints
        assert "description" in hints
        assert "expected" in hints
        assert "actual" in hints
        assert "evidence" in hints
        assert "recommendation" in hints

    def test_qa_finding_serialization(self):
        """QAFinding should serialize to dict correctly."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server error",
            description="Test description",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl http://localhost/api/users"},
            recommendation="Fix the bug",
        )

        result = finding.to_dict()

        assert isinstance(result, dict)
        assert result["finding_id"] == "BT-001"
        assert result["severity"] == "critical"
        assert result["category"] == "behavioral"
        assert result["endpoint"] == "GET /api/users"

    def test_qa_finding_deserialization(self):
        """QAFinding should deserialize from dict correctly."""
        data = {
            "finding_id": "BT-001",
            "severity": "critical",
            "category": "behavioral",
            "endpoint": "GET /api/users",
            "test_type": "happy_path",
            "title": "Server error",
            "description": "Test description",
            "expected": {"status": 200},
            "actual": {"status": 500},
            "evidence": {"request": "curl"},
            "recommendation": "Fix it",
        }

        finding = QAFinding.from_dict(data)

        assert isinstance(finding, QAFinding)
        assert finding.finding_id == "BT-001"
        assert finding.severity == "critical"

    def test_qa_result_required_fields(self):
        """QAResult should have expected fields with defaults."""
        result = QAResult()

        assert result.tests_run == 0
        assert result.tests_passed == 0
        assert result.tests_failed == 0
        assert isinstance(result.findings, list)
        assert result.recommendation == QARecommendation.PASS

    def test_qa_result_serialization(self):
        """QAResult should serialize to dict correctly."""
        result = QAResult(
            tests_run=10,
            tests_passed=8,
            tests_failed=2,
            critical_count=1,
            recommendation=QARecommendation.BLOCK,
        )

        data = result.to_dict()

        assert isinstance(data, dict)
        assert data["tests_run"] == 10
        assert data["tests_passed"] == 8
        assert data["tests_failed"] == 2
        assert data["recommendation"] == "block"

    def test_qa_context_fields(self):
        """QAContext should have expected fields."""
        hints = get_type_hints(QAContext)

        assert "feature_id" in hints
        assert "issue_number" in hints
        assert "bug_id" in hints
        assert "target_files" in hints
        assert "target_endpoints" in hints
        assert "base_url" in hints

    def test_qa_context_serialization(self):
        """QAContext should serialize to dict correctly."""
        context = QAContext(
            feature_id="test-feature",
            issue_number=1,
            base_url="http://localhost:8000",
            target_endpoints=[QAEndpoint(method="GET", path="/api/users")],
        )

        data = context.to_dict()

        assert isinstance(data, dict)
        assert data["feature_id"] == "test-feature"
        assert data["issue_number"] == 1
        assert len(data["target_endpoints"]) == 1

    def test_qa_endpoint_fields(self):
        """QAEndpoint should have expected fields."""
        endpoint = QAEndpoint(method="GET", path="/api/users")

        assert endpoint.method == "GET"
        assert endpoint.path == "/api/users"
        assert hasattr(endpoint, "auth_required")
        assert hasattr(endpoint, "schema")

    def test_qa_limits_defaults(self):
        """QALimits should have sensible defaults."""
        limits = QALimits()

        assert limits.max_cost_usd > 0
        assert limits.warn_cost_usd > 0
        assert limits.session_timeout_minutes > 0
        assert limits.max_endpoints_shallow > 0
        assert limits.max_endpoints_standard > 0
        assert limits.max_endpoints_deep > 0

    def test_qa_bug_fields(self):
        """QABug should have expected fields."""
        hints = get_type_hints(QABug)

        assert "bug_id" in hints
        assert "source_finding" in hints
        assert "qa_session" in hints
        assert "title" in hints
        assert "description" in hints
        assert "severity" in hints
        assert "endpoint" in hints
        assert "reproduction_steps" in hints

    def test_qa_bug_to_bug_report(self):
        """QABug.to_bug_report() should produce valid dict."""
        bug = QABug(
            bug_id="qa-bug-001",
            source_finding="BT-001",
            qa_session="qa-session-001",
            title="Server Error",
            description="500 error on GET",
            severity="critical",
            endpoint="GET /api/users",
            reproduction_steps=["Send GET request", "Check response"],
            expected_behavior="200 OK",
            actual_behavior="500 Internal Server Error",
            evidence={"error_message": "Database connection failed"},
        )

        report = bug.to_bug_report()

        assert isinstance(report, dict)
        assert "description" in report
        assert "error_message" in report
        assert "steps_to_reproduce" in report


# =============================================================================
# TEST: ENUM VALUES
# =============================================================================


class TestEnumValues:
    """Tests for enum value stability."""

    def test_qa_trigger_values(self):
        """QATrigger should have expected values."""
        assert QATrigger.POST_VERIFICATION.value == "post_verification"
        assert QATrigger.BUG_REPRODUCTION.value == "bug_reproduction"
        assert QATrigger.USER_COMMAND.value == "user_command"
        assert QATrigger.PRE_MERGE.value == "pre_merge"

    def test_qa_depth_values(self):
        """QADepth should have expected values."""
        assert QADepth.SHALLOW.value == "shallow"
        assert QADepth.STANDARD.value == "standard"
        assert QADepth.DEEP.value == "deep"
        assert QADepth.REGRESSION.value == "regression"

    def test_qa_status_values(self):
        """QAStatus should have expected values."""
        assert QAStatus.PENDING.value == "pending"
        assert QAStatus.RUNNING.value == "running"
        assert QAStatus.COMPLETED.value == "completed"
        assert QAStatus.COMPLETED_PARTIAL.value == "partial"
        assert QAStatus.BLOCKED.value == "blocked"
        assert QAStatus.FAILED.value == "failed"

    def test_qa_recommendation_values(self):
        """QARecommendation should have expected values."""
        assert QARecommendation.PASS.value == "pass"
        assert QARecommendation.WARN.value == "warn"
        assert QARecommendation.BLOCK.value == "block"

    def test_auth_strategy_values(self):
        """AuthStrategy should have expected values."""
        assert AuthStrategy.BEARER_TOKEN.value == "bearer"
        assert AuthStrategy.API_KEY_HEADER.value == "api_key"
        assert AuthStrategy.API_KEY_QUERY.value == "api_key_query"
        assert AuthStrategy.BASIC_AUTH.value == "basic"
        assert AuthStrategy.COOKIE_SESSION.value == "cookie"
        assert AuthStrategy.NONE.value == "none"

    def test_service_startup_result_values(self):
        """ServiceStartupResult should have expected values."""
        assert ServiceStartupResult.SUCCESS.value == "success"
        assert ServiceStartupResult.TIMEOUT.value == "timeout"
        assert ServiceStartupResult.PORT_CONFLICT.value == "port_conflict"


# =============================================================================
# TEST: HOOKS PUBLIC API
# =============================================================================


class TestHooksAPI:
    """Tests for hooks public API."""

    def test_verifier_hook_init_signature(self):
        """VerifierQAHook.__init__ should accept config and logger."""
        sig = inspect.signature(VerifierQAHook.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "config" in params
        assert "logger" in params

    def test_verifier_hook_should_run_signature(self):
        """VerifierQAHook.should_run() should have correct signature."""
        sig = inspect.signature(VerifierQAHook.should_run)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "verification_success" in params
        assert "feature_id" in params
        assert "issue_number" in params

    def test_verifier_hook_result_fields(self):
        """VerifierHookResult should have expected fields."""
        result = VerifierHookResult()

        assert hasattr(result, "session_id")
        assert hasattr(result, "recommendation")
        assert hasattr(result, "findings")
        assert hasattr(result, "should_block")
        assert hasattr(result, "should_continue")
        assert hasattr(result, "has_warnings")
        assert hasattr(result, "skipped")
        assert hasattr(result, "error")

    def test_verifier_hook_result_defaults(self):
        """VerifierHookResult should have sensible defaults."""
        result = VerifierHookResult()

        assert result.session_id is None
        assert result.recommendation == QARecommendation.PASS
        assert result.findings == []
        assert result.should_block is False
        assert result.should_continue is True
        assert result.skipped is False
        assert result.error is None

    def test_bug_researcher_hook_init_signature(self):
        """BugResearcherQAHook.__init__ should accept config and logger."""
        sig = inspect.signature(BugResearcherQAHook.__init__)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "config" in params
        assert "logger" in params

    def test_bug_researcher_hook_validate_bug_signature(self):
        """BugResearcherQAHook.validate_bug() should have correct signature."""
        sig = inspect.signature(BugResearcherQAHook.validate_bug)
        params = list(sig.parameters.keys())

        assert "self" in params
        assert "bug_id" in params
        assert "endpoint" in params
        assert "reproduction_steps" in params
        assert "affected_files" in params
        assert "base_url" in params

    def test_bug_hook_result_fields(self):
        """BugHookResult should have expected fields."""
        result = BugHookResult()

        assert hasattr(result, "bug_id")
        assert hasattr(result, "session_id")
        assert hasattr(result, "is_reproducible")
        assert hasattr(result, "is_inconclusive")
        assert hasattr(result, "findings")
        assert hasattr(result, "evidence")
        assert hasattr(result, "root_cause_hints")
        assert hasattr(result, "error")

    def test_bug_hook_result_defaults(self):
        """BugHookResult should have sensible defaults."""
        result = BugHookResult()

        assert result.bug_id == ""
        assert result.session_id is None
        assert result.is_reproducible is None
        assert result.is_inconclusive is False
        assert result.findings == []
        assert result.evidence == {}
        assert result.root_cause_hints == []
        assert result.error is None


# =============================================================================
# TEST: CONFIG DATACLASSES
# =============================================================================


class TestConfigDataclasses:
    """Tests for configuration dataclasses."""

    def test_test_data_config_defaults(self):
        """TestDataConfig should have sensible defaults."""
        config = TestDataConfig()

        assert config.mode == "shared"
        assert config.prefix == "qa_test_"
        assert config.cleanup_on_success is True
        assert config.cleanup_on_failure is False

    def test_resilience_config_defaults(self):
        """ResilienceConfig should have sensible defaults."""
        config = ResilienceConfig()

        assert config.request_timeout_seconds > 0
        assert config.connect_timeout_seconds > 0
        assert config.max_retries >= 0
        assert config.retry_backoff_seconds > 0
        assert isinstance(config.retry_on_status, list)
        assert config.requests_per_second > 0

    def test_qa_safety_config_defaults(self):
        """QASafetyConfig should have sensible defaults."""
        config = QASafetyConfig()

        assert config.detect_production is True
        assert isinstance(config.production_url_patterns, list)
        assert config.allow_mutations_in_prod is False
        assert config.allow_deep_tests_in_prod is False
        assert config.redact_tokens_in_logs is True


# =============================================================================
# TEST: EXCEPTION CLASSES
# =============================================================================


class TestExceptionClasses:
    """Tests for exception classes."""

    def test_endpoint_discovery_error_exists(self):
        """EndpointDiscoveryError should be importable."""
        assert EndpointDiscoveryError is not None
        assert issubclass(EndpointDiscoveryError, Exception)

    def test_endpoint_discovery_error_message(self):
        """EndpointDiscoveryError should accept message."""
        error = EndpointDiscoveryError("Test message")
        assert "Test message" in str(error)


# =============================================================================
# TEST: TYPE ANNOTATIONS
# =============================================================================


class TestTypeAnnotations:
    """Tests for type annotation correctness."""

    def test_orchestrator_test_return_type(self):
        """QAOrchestrator.test should be annotated to return QASession."""
        hints = get_type_hints(QAOrchestrator.test)
        assert hints.get("return") == QASession

    def test_orchestrator_validate_issue_return_type(self):
        """QAOrchestrator.validate_issue should be annotated to return QASession."""
        hints = get_type_hints(QAOrchestrator.validate_issue)
        assert hints.get("return") == QASession

    def test_orchestrator_health_check_return_type(self):
        """QAOrchestrator.health_check should be annotated to return QASession."""
        hints = get_type_hints(QAOrchestrator.health_check)
        assert hints.get("return") == QASession

    def test_context_builder_build_context_return_type(self):
        """QAContextBuilder.build_context should be annotated to return QAContext."""
        hints = get_type_hints(QAContextBuilder.build_context)
        assert hints.get("return") == QAContext

    def test_depth_selector_select_depth_return_type(self):
        """DepthSelector.select_depth should be annotated to return QADepth."""
        hints = get_type_hints(DepthSelector.select_depth)
        assert hints.get("return") == QADepth
