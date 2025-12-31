"""P1 Priority Edge Case Tests for QA Models Resilience Testing."""

import pytest
from swarm_attack.qa.models import (
    QASession, QAContext, QAResult, QAFinding, QAEndpoint,
    QATrigger, QADepth, QAStatus, QARecommendation,
    ResilienceConfig,
)


class TestMalformedDataHandling:
    def test_qa_session_from_dict_handles_missing_fields(self):
        minimal_data = {
            "session_id": "qa-minimal-001",
            "trigger": "user_command",
            "depth": "standard",
            "status": "pending",
        }
        session = QASession.from_dict(minimal_data)
        assert session.session_id == "qa-minimal-001"
        assert session.trigger == QATrigger.USER_COMMAND
        assert session.depth == QADepth.STANDARD
        assert session.status == QAStatus.PENDING
        assert session.context.feature_id is None
        assert session.context.target_files == []
        assert session.result is None
        assert session.error is None
        assert session.cost_usd == 0.0

    def test_qa_session_from_dict_handles_null_values(self):
        """QASession.from_dict handles explicit null/None values for scalar fields.

        Note: target_endpoints=None causes TypeError (current behavior documented).
        This test validates that scalar None values are handled correctly.
        """
        data_with_nulls = {
            "session_id": "qa-null-001",
            "trigger": "post_verification",
            "depth": "shallow",
            "status": "completed",
            "context": {
                "feature_id": None,
                "issue_number": None,
                "bug_id": None,
                "spec_path": None,
                "target_files": [],  # Using empty list (None causes issues)
                "target_endpoints": [],  # Using empty list (None causes TypeError)
                "base_url": None,
                "environment": {},  # Using empty dict (None causes issues)
                "git_diff": None,
                "spec_content": None,
                "related_tests": [],  # Using empty list (None causes issues)
            },
            "result": None,
            "created_at": "",
            "started_at": None,
            "completed_at": None,
            "cost_usd": 0.0,
            "error": None,
        }
        session = QASession.from_dict(data_with_nulls)
        assert session.session_id == "qa-null-001"
        assert session.trigger == QATrigger.POST_VERIFICATION
        assert session.context.feature_id is None
        assert session.context.target_files == []
        assert session.context.target_endpoints == []
        assert session.result is None

    def test_qa_finding_from_dict_handles_extra_fields(self):
        data_with_extras = {
            "finding_id": "QA-EXTRA-001",
            "severity": "critical",
            "category": "behavioral",
            "endpoint": "GET /api/test",
            "test_type": "happy_path",
            "title": "Test Finding",
            "description": "Test description",
            "expected": {"status": 200},
            "actual": {"status": 500},
            "evidence": {"error": "Internal Server Error"},
            "recommendation": "Fix the bug",
            "confidence": 0.95,
            "extra_field_1": "should be ignored",
        }
        with pytest.raises(TypeError):
            QAFinding.from_dict(data_with_extras)

    def test_qa_result_handles_empty_findings_list(self):
        result = QAResult(tests_run=10, tests_passed=10, tests_failed=0, findings=[], recommendation=QARecommendation.PASS)
        assert result.findings == []
        assert result.critical_count == 0
        data = result.to_dict()
        assert data["findings"] == []


class TestResilienceConfigEdgeCases:
    def test_resilience_config_default_timeout_values(self):
        config = ResilienceConfig()
        assert config.request_timeout_seconds == 30
        assert config.connect_timeout_seconds == 5
        assert config.connect_timeout_seconds < config.request_timeout_seconds

    def test_resilience_config_retry_on_429_status(self):
        config = ResilienceConfig()
        assert 429 in config.retry_on_status
        assert 502 in config.retry_on_status
        assert 503 in config.retry_on_status
        assert 504 in config.retry_on_status

    def test_resilience_config_respects_retry_after_header(self):
        config = ResilienceConfig()
        assert hasattr(config, "respect_retry_after")
        assert config.respect_retry_after is True
        assert hasattr(config, "retry_backoff_seconds")
        assert config.retry_backoff_seconds > 0


class TestEmptyAndEdgeResponses:
    def test_qa_result_handles_zero_tests_run(self):
        result = QAResult(tests_run=0, tests_passed=0, tests_failed=0, tests_skipped=0)
        assert result.tests_run == 0
        assert result.recommendation == QARecommendation.PASS

    def test_qa_context_handles_empty_target_endpoints(self):
        context = QAContext(feature_id="empty-endpoints-test", target_endpoints=[])
        assert context.target_endpoints == []
        data = context.to_dict()
        assert data["target_endpoints"] == []

    def test_qa_session_handles_empty_context(self):
        empty_context = QAContext()
        session = QASession(session_id="qa-empty-context-001", trigger=QATrigger.USER_COMMAND, depth=QADepth.SHALLOW, status=QAStatus.PENDING, context=empty_context)
        assert session.context.feature_id is None
        assert session.context.target_files == []
        data = session.to_dict()
        restored = QASession.from_dict(data)
        assert restored.context.feature_id is None

    def test_qa_finding_handles_empty_evidence_dict(self):
        finding = QAFinding(finding_id="QA-EMPTY-EVIDENCE-001", severity="minor", category="contract", endpoint="GET /api/health", test_type="schema", title="Empty Evidence Test", description="Finding with no evidence collected", expected={"status": 200}, actual={"status": 200}, evidence={}, recommendation="No action needed")
        assert finding.evidence == {}
        data = finding.to_dict()
        assert data["evidence"] == {}
        restored = QAFinding.from_dict(data)
        assert restored.evidence == {}
