"""Tests for FeaturePipelineQAIntegration following TDD approach.

Tests cover spec section 5.2.1:
- Post-verification QA integration
- Skip QA with skip_qa flag
- Block on critical QA findings
- Create bugs for critical/moderate findings
- Log warnings but continue on WARN recommendation
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass
from typing import Optional

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
    """Tests to verify FeaturePipelineQAIntegration can be imported."""

    def test_can_import_feature_pipeline_integration(self):
        """Should be able to import FeaturePipelineQAIntegration class."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        assert FeaturePipelineQAIntegration is not None

    def test_can_import_qa_integration_result(self):
        """Should be able to import QAIntegrationResult dataclass."""
        from swarm_attack.qa.integrations.feature_pipeline import QAIntegrationResult
        assert QAIntegrationResult is not None

    def test_qa_integration_result_has_required_fields(self):
        """QAIntegrationResult should have required fields."""
        from swarm_attack.qa.integrations.feature_pipeline import QAIntegrationResult

        result = QAIntegrationResult()
        assert hasattr(result, "session_id")
        assert hasattr(result, "recommendation")
        assert hasattr(result, "should_block")
        assert hasattr(result, "block_reason")
        assert hasattr(result, "created_bugs")
        assert hasattr(result, "findings_summary")
        assert hasattr(result, "error")


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestFeaturePipelineQAIntegrationInit:
    """Tests for FeaturePipelineQAIntegration initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        integration = FeaturePipelineQAIntegration(mock_config)
        assert integration.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        logger = MagicMock()
        integration = FeaturePipelineQAIntegration(mock_config, logger=logger)
        assert integration._logger == logger

    def test_init_creates_orchestrator(self, mock_config):
        """Should create QAOrchestrator instance."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        integration = FeaturePipelineQAIntegration(mock_config)
        assert hasattr(integration, "orchestrator")
        assert integration.orchestrator is not None


# =============================================================================
# run_post_verification_qa() TESTS
# =============================================================================


class TestRunPostVerificationQA:
    """Tests for run_post_verification_qa() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        return FeaturePipelineQAIntegration(mock_config)

    def test_returns_qa_integration_result(self, integration):
        """Should return QAIntegrationResult."""
        from swarm_attack.qa.integrations.feature_pipeline import QAIntegrationResult

        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            assert isinstance(result, QAIntegrationResult)

    def test_skips_qa_when_skip_qa_true(self, integration):
        """Should skip QA and return PASS when skip_qa=True."""
        from swarm_attack.qa.integrations.feature_pipeline import QAIntegrationResult

        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
            skip_qa=True,
        )

        assert result.recommendation == QARecommendation.PASS
        assert result.should_block is False
        assert result.session_id is None

    def test_runs_qa_when_skip_qa_false(self, integration):
        """Should run QA when skip_qa=False (default)."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            mock_validate.assert_called_once()
            assert result.session_id == "qa-test-123"

    def test_uses_standard_depth_by_default(self, integration):
        """Should use STANDARD depth by default."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_validate.return_value = mock_session

            integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/utils.py"],  # Non-high-risk file
            )

            call_args = mock_validate.call_args
            assert call_args.kwargs.get("depth") == QADepth.STANDARD or \
                   call_args[1].get("depth") == QADepth.STANDARD or \
                   (len(call_args[0]) >= 3 and call_args[0][2] == QADepth.STANDARD)

    def test_escalates_to_deep_for_high_risk_files(self, integration):
        """Should escalate to DEEP depth for high-risk files."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_validate.return_value = mock_session

            # Files with auth, payment, or security in path are high-risk
            integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/auth.py"],  # High-risk
            )

            call_args = mock_validate.call_args
            # Check that depth is DEEP for high-risk files
            depth_arg = call_args.kwargs.get("depth") or (
                call_args[0][2] if len(call_args[0]) >= 3 else None
            )
            assert depth_arg == QADepth.DEEP

    def test_sets_session_id_in_result(self, integration):
        """Should include session_id in result."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-456"
            mock_session.result = QAResult(recommendation=QARecommendation.PASS)
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            assert result.session_id == "qa-test-456"

    def test_sets_recommendation_from_qa_result(self, integration):
        """Should set recommendation from QA result."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(recommendation=QARecommendation.WARN)
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            assert result.recommendation == QARecommendation.WARN

    def test_includes_findings_summary(self, integration):
        """Should include findings summary in result."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Error",
            description="Error",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )

        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.BLOCK,
                findings=[finding],
                critical_count=1,
                moderate_count=0,
                minor_count=0,
            )
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            assert "critical" in result.findings_summary
            assert result.findings_summary["critical"] == 1

    def test_handles_orchestrator_errors_gracefully(self, integration):
        """Should handle orchestrator errors gracefully."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_validate.side_effect = Exception("Orchestrator failed")

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            # Should not raise, but return error in result
            assert result.error is not None
            assert "Orchestrator failed" in result.error


# =============================================================================
# should_block_commit() TESTS
# =============================================================================


class TestShouldBlockCommit:
    """Tests for should_block_commit() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        return FeaturePipelineQAIntegration(mock_config)

    def test_blocks_on_block_recommendation(self, integration):
        """Should return (True, reason) when recommendation is BLOCK."""
        qa_result = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.BLOCK,
                critical_count=2,
            ),
        )

        should_block, reason = integration.should_block_commit(qa_result)

        assert should_block is True
        assert reason is not None
        assert len(reason) > 0

    def test_does_not_block_on_warn(self, integration):
        """Should return (False, None) when recommendation is WARN."""
        qa_result = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.WARN,
                moderate_count=1,
            ),
        )

        should_block, reason = integration.should_block_commit(qa_result)

        assert should_block is False

    def test_does_not_block_on_pass(self, integration):
        """Should return (False, None) when recommendation is PASS."""
        qa_result = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )

        should_block, reason = integration.should_block_commit(qa_result)

        assert should_block is False

    def test_returns_clear_reason_when_blocking(self, integration):
        """Should return clear, descriptive reason when blocking."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server returns 500 error",
            description="Critical error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix server",
        )

        qa_result = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.BLOCK,
                critical_count=1,
                findings=[finding],
            ),
        )

        should_block, reason = integration.should_block_commit(qa_result)

        assert should_block is True
        assert "critical" in reason.lower() or "1" in reason

    def test_handles_session_without_result(self, integration):
        """Should handle session without result gracefully."""
        qa_result = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.FAILED,
            context=QAContext(),
            result=None,
        )

        should_block, reason = integration.should_block_commit(qa_result)

        # When no result, should not block (fail open)
        assert should_block is False

    def test_handles_failed_session_status(self, integration):
        """Should handle failed session status appropriately."""
        qa_result = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.FAILED,
            context=QAContext(),
            result=None,
            error="Agent crashed",
        )

        should_block, reason = integration.should_block_commit(qa_result)

        # Failed sessions should not block (fail open for graceful degradation)
        assert should_block is False


# =============================================================================
# create_bugs_from_findings() TESTS
# =============================================================================


class TestCreateBugsFromFindings:
    """Tests for create_bugs_from_findings() method."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        return FeaturePipelineQAIntegration(mock_config)

    def test_creates_bugs_for_critical_findings(self, integration):
        """Should create bugs for critical findings."""
        with patch.object(
            integration.orchestrator, "create_bug_investigations"
        ) as mock_create:
            mock_create.return_value = ["qa-bug-001", "qa-bug-002"]

            bug_ids = integration.create_bugs_from_findings(
                session_id="qa-test-123",
                severity_threshold="critical",
            )

            mock_create.assert_called_once_with(
                session_id="qa-test-123",
                severity_threshold="critical",
            )
            assert bug_ids == ["qa-bug-001", "qa-bug-002"]

    def test_creates_bugs_for_moderate_findings_when_threshold_allows(
        self, integration
    ):
        """Should create bugs for moderate findings when threshold is moderate."""
        with patch.object(
            integration.orchestrator, "create_bug_investigations"
        ) as mock_create:
            mock_create.return_value = ["qa-bug-001"]

            bug_ids = integration.create_bugs_from_findings(
                session_id="qa-test-123",
                severity_threshold="moderate",
            )

            mock_create.assert_called_once_with(
                session_id="qa-test-123",
                severity_threshold="moderate",
            )

    def test_returns_created_bug_ids(self, integration):
        """Should return list of created bug IDs."""
        with patch.object(
            integration.orchestrator, "create_bug_investigations"
        ) as mock_create:
            mock_create.return_value = ["qa-bug-001", "qa-bug-002", "qa-bug-003"]

            bug_ids = integration.create_bugs_from_findings(
                session_id="qa-test-123",
                severity_threshold="moderate",
            )

            assert isinstance(bug_ids, list)
            assert len(bug_ids) == 3

    def test_handles_empty_findings_gracefully(self, integration):
        """Should return empty list when no findings match threshold."""
        with patch.object(
            integration.orchestrator, "create_bug_investigations"
        ) as mock_create:
            mock_create.return_value = []

            bug_ids = integration.create_bugs_from_findings(
                session_id="qa-test-123",
                severity_threshold="critical",
            )

            assert bug_ids == []

    def test_uses_moderate_threshold_by_default(self, integration):
        """Should use 'moderate' as default severity threshold."""
        with patch.object(
            integration.orchestrator, "create_bug_investigations"
        ) as mock_create:
            mock_create.return_value = []

            integration.create_bugs_from_findings(session_id="qa-test-123")

            call_args = mock_create.call_args
            assert call_args.kwargs.get("severity_threshold") == "moderate" or (
                len(call_args[0]) >= 2 and call_args[0][1] == "moderate"
            )

    def test_handles_orchestrator_errors_gracefully(self, integration):
        """Should handle orchestrator errors gracefully."""
        with patch.object(
            integration.orchestrator, "create_bug_investigations"
        ) as mock_create:
            mock_create.side_effect = Exception("Failed to create bugs")

            bug_ids = integration.create_bugs_from_findings(
                session_id="qa-test-123",
                severity_threshold="moderate",
            )

            # Should return empty list on error, not raise
            assert bug_ids == []


# =============================================================================
# HIGH-RISK FILE DETECTION TESTS
# =============================================================================


class TestHighRiskFileDetection:
    """Tests for high-risk file detection logic."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        return FeaturePipelineQAIntegration(mock_config)

    def test_detects_auth_files_as_high_risk(self, integration):
        """Files with 'auth' in path should be high-risk."""
        assert integration._is_high_risk_file("src/api/auth.py") is True
        assert integration._is_high_risk_file("src/services/authentication.py") is True
        assert integration._is_high_risk_file("auth/login.py") is True

    def test_detects_payment_files_as_high_risk(self, integration):
        """Files with 'payment' in path should be high-risk."""
        assert integration._is_high_risk_file("src/api/payment.py") is True
        assert integration._is_high_risk_file("src/services/payments.py") is True
        assert integration._is_high_risk_file("billing/payment_processor.py") is True

    def test_detects_security_files_as_high_risk(self, integration):
        """Files with 'security' in path should be high-risk."""
        assert integration._is_high_risk_file("src/security/crypto.py") is True
        assert integration._is_high_risk_file("src/utils/security_utils.py") is True

    def test_detects_crypto_files_as_high_risk(self, integration):
        """Files with 'crypto' in path should be high-risk."""
        assert integration._is_high_risk_file("src/utils/crypto.py") is True
        assert integration._is_high_risk_file("src/encryption.py") is True

    def test_normal_files_are_not_high_risk(self, integration):
        """Normal utility files should not be high-risk."""
        assert integration._is_high_risk_file("src/utils/helpers.py") is False
        assert integration._is_high_risk_file("src/api/users.py") is False
        assert integration._is_high_risk_file("src/models/item.py") is False

    def test_checks_all_files_for_high_risk(self, integration):
        """Should detect high-risk if ANY file in list is high-risk."""
        files = [
            "src/utils/helpers.py",
            "src/api/users.py",
            "src/api/auth.py",  # High-risk
        ]
        assert integration._has_high_risk_files(files) is True

    def test_returns_false_when_no_high_risk_files(self, integration):
        """Should return False when no high-risk files."""
        files = [
            "src/utils/helpers.py",
            "src/api/users.py",
            "src/models/item.py",
        ]
        assert integration._has_high_risk_files(files) is False


# =============================================================================
# INTEGRATION WORKFLOW TESTS
# =============================================================================


class TestIntegrationWorkflow:
    """End-to-end integration workflow tests."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def integration(self, mock_config):
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        return FeaturePipelineQAIntegration(mock_config)

    def test_full_pass_workflow(self, integration):
        """Should handle full pass workflow correctly."""
        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = MagicMock(spec=QASession)
            mock_session.session_id = "qa-test-123"
            mock_session.result = QAResult(
                recommendation=QARecommendation.PASS,
                tests_run=10,
                tests_passed=10,
                tests_failed=0,
            )
            mock_session.status = QAStatus.COMPLETED
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            assert result.should_block is False
            assert result.recommendation == QARecommendation.PASS

    def test_full_block_workflow(self, integration):
        """Should handle full block workflow correctly."""
        critical_finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Server error",
            description="500 error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix server",
        )

        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = QASession(
                session_id="qa-test-123",
                trigger=QATrigger.POST_VERIFICATION,
                depth=QADepth.STANDARD,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.BLOCK,
                    tests_run=10,
                    tests_passed=8,
                    tests_failed=2,
                    critical_count=1,
                    findings=[critical_finding],
                ),
            )
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            assert result.should_block is True
            assert result.recommendation == QARecommendation.BLOCK
            assert result.block_reason is not None

    def test_full_warn_workflow(self, integration):
        """Should handle full warn workflow correctly (continue with warning)."""
        moderate_finding = QAFinding(
            finding_id="BT-001",
            severity="moderate",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Missing field",
            description="Field missing",
            expected={"fields": ["email"]},
            actual={"fields": []},
            evidence={},
            recommendation="Add field",
        )

        with patch.object(integration.orchestrator, "validate_issue") as mock_validate:
            mock_session = QASession(
                session_id="qa-test-123",
                trigger=QATrigger.POST_VERIFICATION,
                depth=QADepth.STANDARD,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.WARN,
                    tests_run=10,
                    tests_passed=9,
                    tests_failed=1,
                    moderate_count=1,
                    findings=[moderate_finding],
                ),
            )
            mock_validate.return_value = mock_session

            result = integration.run_post_verification_qa(
                feature_id="my-feature",
                issue_number=42,
                verified_files=["src/api/users.py"],
            )

            # Should not block on WARN
            assert result.should_block is False
            assert result.recommendation == QARecommendation.WARN
            # Should have findings in summary
            assert result.findings_summary.get("moderate", 0) == 1
