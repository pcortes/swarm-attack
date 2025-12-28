"""Tests for BugPipelineQAIntegration following TDD approach.

Tests cover spec section 5.2.2:
- Enhance bug reproduction with behavioral tests
- Run DEEP QA on affected area when BugResearcher fails to reproduce
- Provide evidence for RootCauseAnalyzer
- Extract reproduction steps from QA findings
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Any

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAFinding,
    QARecommendation,
    QAResult,
    QASession,
    QAStatus,
    QATrigger,
)


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify BugPipelineQAIntegration can be imported."""

    def test_can_import_bug_pipeline_integration(self):
        """Should be able to import BugPipelineQAIntegration class."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        assert BugPipelineQAIntegration is not None

    def test_can_import_bug_reproduction_result(self):
        """Should be able to import BugReproductionResult dataclass."""
        from swarm_attack.qa.integrations.bug_pipeline import BugReproductionResult
        assert BugReproductionResult is not None

    def test_bug_reproduction_result_has_required_fields(self):
        """BugReproductionResult should have required fields."""
        from swarm_attack.qa.integrations.bug_pipeline import BugReproductionResult

        result = BugReproductionResult()
        assert hasattr(result, "session_id")
        assert hasattr(result, "is_reproduced")
        assert hasattr(result, "reproduction_steps")
        assert hasattr(result, "evidence")
        assert hasattr(result, "root_cause_hints")
        assert hasattr(result, "error")


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestBugPipelineQAIntegrationInit:
    """Tests for BugPipelineQAIntegration initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        integration = BugPipelineQAIntegration(mock_config)
        assert integration.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        logger = MagicMock()
        integration = BugPipelineQAIntegration(mock_config, logger=logger)
        assert integration._logger == logger

    def test_init_creates_orchestrator(self, mock_config):
        """Should create QAOrchestrator instance."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        integration = BugPipelineQAIntegration(mock_config)
        assert hasattr(integration, "orchestrator")
        assert integration.orchestrator is not None


# =============================================================================
# enhance_reproduction() TESTS
# =============================================================================


class TestEnhanceReproduction:
    """Tests for enhance_reproduction() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        return BugPipelineQAIntegration(mock_config)

    def test_returns_bug_reproduction_result(self, integration):
        """Should return BugReproductionResult."""
        from swarm_attack.qa.integrations.bug_pipeline import BugReproductionResult

        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500 on special characters",
            )

            assert isinstance(result, BugReproductionResult)

    def test_uses_deep_depth_for_bug_reproduction(self, integration):
        """Should use DEEP depth for bug reproduction."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_test.return_value = mock_session

            integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
            )

            call_args = mock_test.call_args
            depth_arg = call_args.kwargs.get("depth") or (
                call_args[0][1] if len(call_args[0]) >= 2 else None
            )
            assert depth_arg == QADepth.DEEP

    def test_uses_bug_reproduction_trigger(self, integration):
        """Should use BUG_REPRODUCTION trigger."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_test.return_value = mock_session

            integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
            )

            call_args = mock_test.call_args
            trigger_arg = call_args.kwargs.get("trigger")
            assert trigger_arg == QATrigger.BUG_REPRODUCTION

    def test_sets_is_reproduced_when_tests_fail(self, integration):
        """Should set is_reproduced=True when QA finds failing tests."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 on emoji input",
            description="Server error on emoji",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl -X PUT ..."},
            recommendation="Fix input handling",
        )

        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.BLOCK,
                tests_run=5,
                tests_passed=3,
                tests_failed=2,
                findings=[finding],
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
            )

            assert result.is_reproduced is True

    def test_sets_is_reproduced_false_when_no_failures(self, integration):
        """Should set is_reproduced=False when no tests fail."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_run=5,
                tests_passed=5,
                tests_failed=0,
                findings=[],
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
            )

            assert result.is_reproduced is False

    def test_includes_session_id(self, integration):
        """Should include session_id in result."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-456"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API error",
            )

            assert result.session_id == "qa-bug-456"

    def test_extracts_reproduction_steps_from_findings(self, integration):
        """Should extract reproduction steps from QA findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 on emoji input",
            description="Server returns 500 when name contains emoji",
            expected={"status": 200},
            actual={"status": 500},
            evidence={
                "request": 'curl -X PUT localhost/api/users/1 -d \'{"name": "John 🎉"}\'',
                "response": '{"error": "Internal Server Error"}',
            },
            recommendation="Fix input handling",
        )

        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.BLOCK,
                tests_failed=1,
                findings=[finding],
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
            )

            assert len(result.reproduction_steps) > 0

    def test_includes_affected_endpoints_in_target(self, integration):
        """Should include affected endpoints when provided."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_test.return_value = mock_session

            integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
                affected_endpoints=["/api/users", "/api/users/{id}"],
            )

            call_args = mock_test.call_args
            target_arg = call_args.kwargs.get("target") or call_args[0][0]
            # Target should contain endpoint info
            assert "/api/users" in target_arg or "users" in target_arg.lower()

    def test_includes_error_message_in_context(self, integration):
        """Should include error message when provided."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-bug-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_failed=0,
            )
            mock_test.return_value = mock_session

            integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
                error_message="NullPointerException at UserService.java:45",
            )

            # The error message should be used to inform the test target
            call_args = mock_test.call_args
            target_arg = call_args.kwargs.get("target") or call_args[0][0]
            assert len(target_arg) > 0  # Should have formed a target

    def test_handles_orchestrator_errors_gracefully(self, integration):
        """Should handle orchestrator errors gracefully."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_test.side_effect = Exception("Orchestrator failed")

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500",
            )

            # Should not raise, but return error in result
            assert result.error is not None
            assert "Orchestrator failed" in result.error
            assert result.is_reproduced is False


# =============================================================================
# get_rca_evidence() TESTS
# =============================================================================


class TestGetRCAEvidence:
    """Tests for get_rca_evidence() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        return BugPipelineQAIntegration(mock_config)

    def test_returns_dict(self, integration):
        """Should return a dictionary."""
        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            assert isinstance(result, dict)

    def test_extracts_request_response_evidence(self, integration):
        """Should extract request/response evidence from findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 error",
            description="Server error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={
                "request": 'curl -X PUT localhost/api/users/1 -d \'{"name": "John 🎉"}\'',
                "response": '{"error": "Internal Server Error"}',
            },
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[finding],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Should have requests and responses
            assert "requests" in result or "evidence" in result
            assert len(result) > 0

    def test_extracts_stack_traces_if_available(self, integration):
        """Should extract stack traces from evidence if available."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 error",
            description="Server error with stack trace",
            expected={"status": 200},
            actual={"status": 500},
            evidence={
                "request": "curl ...",
                "response": '{"error": "Internal Server Error"}',
                "stack_trace": "at UserService.updateUser(UserService.java:123)",
            },
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[finding],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Should include stack trace info
            assert "stack_traces" in result or any(
                "stack" in str(v).lower() for v in result.values() if v
            )

    def test_provides_reproduction_steps(self, integration):
        """Should provide reproduction steps from findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 error",
            description="Server error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={
                "request": 'curl -X PUT localhost/api/users/1 -d \'{"name": "Test"}\'',
            },
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[finding],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            assert "reproduction_steps" in result or "findings" in result

    def test_formats_for_root_cause_analyzer(self, integration):
        """Should format evidence for RootCauseAnalyzer consumption."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 error",
            description="Server error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl ..."},
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[finding],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Should have structured format suitable for RCA
            assert "endpoints_affected" in result or "findings" in result

    def test_handles_missing_session_gracefully(self, integration):
        """Should handle missing session gracefully."""
        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_get.return_value = None

            result = integration.get_rca_evidence(session_id="nonexistent")

            # Should return empty dict or error indicator
            assert result == {} or "error" in result

    def test_handles_session_without_result(self, integration):
        """Should handle session without result gracefully."""
        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = None
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Should return empty dict or minimal info
            assert isinstance(result, dict)


# =============================================================================
# EVIDENCE AGGREGATION TESTS
# =============================================================================


class TestEvidenceAggregation:
    """Tests for evidence aggregation from multiple findings."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        return BugPipelineQAIntegration(mock_config)

    def test_aggregates_evidence_from_multiple_findings(self, integration):
        """Should aggregate evidence from all relevant findings."""
        finding1 = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 on emoji",
            description="Error 1",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl -X PUT /api/users/1"},
            recommendation="Fix",
        )
        finding2 = QAFinding(
            finding_id="BT-002",
            severity="critical",
            category="behavioral",
            endpoint="POST /api/users",
            test_type="edge_case",
            title="500 on unicode",
            description="Error 2",
            expected={"status": 201},
            actual={"status": 500},
            evidence={"request": "curl -X POST /api/users"},
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[finding1, finding2],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Should include info from both findings
            findings_count = len(result.get("findings", []))
            endpoints_count = len(result.get("endpoints_affected", []))
            assert findings_count >= 2 or endpoints_count >= 2

    def test_deduplicates_similar_evidence(self, integration):
        """Should deduplicate similar evidence items."""
        # Two findings with same endpoint should not duplicate the endpoint
        finding1 = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="Error 1",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )
        finding2 = QAFinding(
            finding_id="BT-002",
            severity="moderate",
            category="behavioral",
            endpoint="PUT /api/users/1",  # Same endpoint
            test_type="error_case",
            title="Error 2",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = MagicMock(spec=QASession)
            mock_session.result = QAResult(
                findings=[finding1, finding2],
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Endpoints should be deduplicated
            endpoints = result.get("endpoints_affected", [])
            if endpoints:
                unique_endpoints = set(endpoints)
                assert len(endpoints) == len(unique_endpoints)


# =============================================================================
# INTEGRATION WORKFLOW TESTS
# =============================================================================


class TestBugPipelineWorkflow:
    """End-to-end integration workflow tests."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        return BugPipelineQAIntegration(mock_config)

    def test_full_reproduction_workflow(self, integration):
        """Should handle full reproduction workflow correctly."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 on emoji input",
            description="Server returns 500 when name contains emoji",
            expected={"status": 200},
            actual={"status": 500},
            evidence={
                "request": 'curl -X PUT localhost/api/users/1 -d \'{"name": "John 🎉"}\'',
                "response": '{"error": "Internal Server Error"}',
            },
            recommendation="Fix unicode handling",
        )

        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = QASession(
                session_id="qa-bug-123",
                trigger=QATrigger.BUG_REPRODUCTION,
                depth=QADepth.DEEP,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.BLOCK,
                    tests_run=5,
                    tests_passed=3,
                    tests_failed=2,
                    findings=[finding],
                ),
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-001",
                bug_description="API returns 500 when user name contains emoji",
                error_message="500 Internal Server Error",
                affected_endpoints=["/api/users/{id}"],
            )

            assert result.is_reproduced is True
            assert result.session_id == "qa-bug-123"
            assert len(result.reproduction_steps) > 0

    def test_no_reproduction_workflow(self, integration):
        """Should handle case where bug is not reproduced."""
        with patch.object(integration.orchestrator, "test") as mock_test:
            mock_session = QASession(
                session_id="qa-bug-123",
                trigger=QATrigger.BUG_REPRODUCTION,
                depth=QADepth.DEEP,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.PASS,
                    tests_run=10,
                    tests_passed=10,
                    tests_failed=0,
                    findings=[],
                ),
            )
            mock_test.return_value = mock_session

            result = integration.enhance_reproduction(
                bug_id="bug-002",
                bug_description="Intermittent error",
            )

            assert result.is_reproduced is False
            assert result.session_id == "qa-bug-123"
            assert len(result.reproduction_steps) == 0

    def test_rca_evidence_extraction_workflow(self, integration):
        """Should handle full RCA evidence extraction workflow."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 on emoji",
            description="Error on emoji",
            expected={"status": 200},
            actual={"status": 500},
            evidence={
                "request": 'curl -X PUT localhost/api/users/1 -d \'{"name": "🎉"}\'',
                "response": '{"error": "Internal Server Error"}',
                "stack_trace": "UnicodeEncodeError at UserService.py:42",
            },
            recommendation="Fix unicode",
        )

        with patch.object(integration.orchestrator, "get_session") as mock_get:
            mock_session = QASession(
                session_id="qa-bug-123",
                trigger=QATrigger.BUG_REPRODUCTION,
                depth=QADepth.DEEP,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.BLOCK,
                    findings=[finding],
                ),
            )
            mock_get.return_value = mock_session

            result = integration.get_rca_evidence(session_id="qa-bug-123")

            # Should have comprehensive evidence for RCA
            assert isinstance(result, dict)
            assert len(result) > 0
