"""Tests for QA models following TDD approach."""

import pytest
from swarm_attack.qa.models import (
    ServiceStartupResult, AuthStrategy, QAStatus, QADepth, QATrigger,
    QARecommendation, TestDataConfig, ResilienceConfig, QALimits,
    QASafetyConfig, QAEndpoint, QAFinding, QAContext, QAResult,
    QASession, QABug,
)


class TestEnums:
    def test_service_startup_result_enum(self):
        assert ServiceStartupResult.SUCCESS.value == "success"
        assert ServiceStartupResult.TIMEOUT.value == "timeout"
        assert ServiceStartupResult.PORT_CONFLICT.value == "port_conflict"
        assert ServiceStartupResult.DOCKER_UNAVAILABLE.value == "docker_unavailable"
        assert ServiceStartupResult.STARTUP_CRASHED.value == "startup_crashed"
        assert ServiceStartupResult.NO_HEALTH_ENDPOINT.value == "no_health_endpoint"

    def test_auth_strategy_enum(self):
        assert AuthStrategy.BEARER_TOKEN.value == "bearer"
        assert AuthStrategy.API_KEY_HEADER.value == "api_key"
        assert AuthStrategy.API_KEY_QUERY.value == "api_key_query"
        assert AuthStrategy.BASIC_AUTH.value == "basic"
        assert AuthStrategy.COOKIE_SESSION.value == "cookie"
        assert AuthStrategy.NONE.value == "none"

    def test_qa_status_enum(self):
        assert QAStatus.PENDING.value == "pending"
        assert QAStatus.RUNNING.value == "running"
        assert QAStatus.COMPLETED.value == "completed"
        assert QAStatus.COMPLETED_PARTIAL.value == "partial"
        assert QAStatus.BLOCKED.value == "blocked"
        assert QAStatus.FAILED.value == "failed"

    def test_qa_depth_enum(self):
        assert QADepth.SHALLOW.value == "shallow"
        assert QADepth.STANDARD.value == "standard"
        assert QADepth.DEEP.value == "deep"
        assert QADepth.REGRESSION.value == "regression"

    def test_qa_trigger_enum(self):
        assert QATrigger.POST_VERIFICATION.value == "post_verification"
        assert QATrigger.BUG_REPRODUCTION.value == "bug_reproduction"
        assert QATrigger.USER_COMMAND.value == "user_command"
        assert QATrigger.PRE_MERGE.value == "pre_merge"

    def test_qa_recommendation_enum(self):
        assert QARecommendation.PASS.value == "pass"
        assert QARecommendation.WARN.value == "warn"
        assert QARecommendation.BLOCK.value == "block"


class TestTestDataConfig:
    def test_default_values(self):
        config = TestDataConfig()
        assert config.mode == "shared"
        assert config.prefix == "qa_test_"
        assert config.cleanup_on_success is True
        assert config.cleanup_on_failure is False


class TestResilienceConfig:
    def test_default_values(self):
        config = ResilienceConfig()
        assert config.request_timeout_seconds == 30
        assert config.connect_timeout_seconds == 5
        assert config.max_retries == 2
        assert config.retry_on_status == [429, 502, 503, 504]
        assert config.requests_per_second == 10.0
        assert config.verify_ssl is True


class TestQALimits:
    def test_default_values(self):
        limits = QALimits()
        assert limits.max_cost_usd == 5.0
        assert limits.warn_cost_usd == 2.0
        assert limits.max_endpoints_shallow == 100
        assert limits.max_endpoints_standard == 50
        assert limits.max_endpoints_deep == 20
        assert limits.session_timeout_minutes == 30


class TestQASafetyConfig:
    def test_default_values(self):
        config = QASafetyConfig()
        assert config.detect_production is True
        assert r".*\.prod\..*" in config.production_url_patterns
        assert config.allow_mutations_in_prod is False
        assert config.redact_tokens_in_logs is True
        assert config.readonly_mode is False


class TestQAEndpoint:
    def test_basic_endpoint(self):
        endpoint = QAEndpoint(method="GET", path="/api/users")
        assert endpoint.method == "GET"
        assert endpoint.path == "/api/users"
        assert endpoint.auth_required is False


class TestQAFinding:
    def test_basic_finding(self):
        finding = QAFinding(
            finding_id="QA-001", severity="critical", category="behavioral",
            endpoint="GET /api/users", test_type="happy_path",
            title="500 error", description="Test", expected={},
            actual={}, evidence={}, recommendation="Fix",
        )
        assert finding.finding_id == "QA-001"
        assert finding.confidence == 0.9

    def test_finding_to_dict(self):
        finding = QAFinding(
            finding_id="QA-001", severity="moderate", category="contract",
            endpoint="POST /api/users", test_type="schema",
            title="Test", description="Test", expected={},
            actual={}, evidence={}, recommendation="Fix",
        )
        data = finding.to_dict()
        assert data["finding_id"] == "QA-001"


class TestQAContext:
    def test_default_context(self):
        context = QAContext()
        assert context.feature_id is None
        assert context.target_files == []
        assert context.target_endpoints == []


class TestQAResult:
    def test_default_result(self):
        result = QAResult()
        assert result.tests_run == 0
        assert result.recommendation == QARecommendation.PASS
        assert result.skipped_reasons == {}
        assert result.partial_completion_reason is None

    def test_result_with_partial_completion(self):
        result = QAResult(
            tests_run=10,
            skipped_reasons={"contract": "no_consumers"},
            partial_completion_reason="cost_limit",
        )
        assert result.skipped_reasons == {"contract": "no_consumers"}
        assert result.partial_completion_reason == "cost_limit"


class TestQASession:
    def test_basic_session(self):
        context = QAContext(feature_id="test")
        session = QASession(
            session_id="qa-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.PENDING,
            context=context,
        )
        assert session.session_id == "qa-123"
        assert "T" in session.created_at

    def test_session_to_dict(self):
        context = QAContext(feature_id="test")
        session = QASession(
            session_id="qa-001",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=context,
        )
        data = session.to_dict()
        assert data["session_id"] == "qa-001"
        assert data["trigger"] == "post_verification"

    def test_qa_session_roundtrip_preserves_all_context_fields(self):
        """Bug #1: Test that QASession serialization preserves all context fields."""
        # Create session with ALL context fields populated
        context = QAContext(
            feature_id="test-feature",
            issue_number=123,
            bug_id="bug-456",
            spec_path="/path/to/spec.md",
            target_files=["src/api.py", "src/models.py"],
            target_endpoints=[
                QAEndpoint(method="GET", path="/api/users", auth_required=True),
                QAEndpoint(method="POST", path="/api/users", auth_required=True),
            ],
            base_url="http://localhost:8765",
            environment={"ENV": "test", "DEBUG": "true"},
            git_diff="diff --git a/file.py",
            spec_content="# Spec content here",
            related_tests=["test_api.py", "test_models.py"],
        )

        session = QASession(
            session_id="qa-20251227-123456",
            trigger=QATrigger.USER_COMMAND,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=context,
            result=QAResult(
                tests_run=5,
                tests_passed=4,
                tests_failed=1,
                recommendation=QARecommendation.WARN,
            ),
        )

        # Round-trip through serialization
        data = session.to_dict()
        restored = QASession.from_dict(data)

        # Assert ALL context fields are preserved
        assert restored.context.feature_id == "test-feature"
        assert restored.context.issue_number == 123
        assert restored.context.bug_id == "bug-456"
        assert restored.context.spec_path == "/path/to/spec.md"
        assert restored.context.target_files == ["src/api.py", "src/models.py"]
        assert len(restored.context.target_endpoints) == 2
        assert restored.context.target_endpoints[0].method == "GET"
        assert restored.context.target_endpoints[0].path == "/api/users"
        assert restored.context.target_endpoints[0].auth_required is True
        assert restored.context.base_url == "http://localhost:8765"
        assert restored.context.environment == {"ENV": "test", "DEBUG": "true"}
        assert restored.context.git_diff == "diff --git a/file.py"
        assert restored.context.spec_content == "# Spec content here"
        assert restored.context.related_tests == ["test_api.py", "test_models.py"]


class TestQABug:
    def test_basic_bug(self):
        bug = QABug(
            bug_id="BUG-001", source_finding="QA-001", qa_session="qa-123",
            title="500 error", description="Test", severity="critical",
            endpoint="GET /api/users", reproduction_steps=["curl"],
            expected_behavior="200", actual_behavior="500",
            evidence={"error_message": "fail"},
        )
        assert bug.bug_id == "BUG-001"

    def test_bug_to_bug_report(self):
        bug = QABug(
            bug_id="BUG-002", source_finding="QA-002", qa_session="qa-456",
            title="Missing field", description="User ID missing",
            severity="moderate", endpoint="POST /api/users",
            reproduction_steps=["Create user", "Check response"],
            expected_behavior="id field", actual_behavior="no id",
            evidence={"error_message": "Field not found"},
        )
        report = bug.to_bug_report()
        assert "Missing field" in report["description"]
        assert report["steps_to_reproduce"] == ["Create user", "Check response"]
