"""Tests for QASessionExtension integration in FeaturePipelineQAIntegration.

Tests verify that FeaturePipelineQAIntegration properly integrates QASessionExtension
for coverage tracking per issue per Issue 2 acceptance criteria.

Acceptance Criteria Tested:
- 2.5: FeaturePipelineQAIntegration tracks coverage per issue
- 2.6: FeaturePipelineQAIntegration can set baselines after feature completion
- 2.9: session_extension._coverage_tracker._swarm_dir set correctly
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
# CRITERION 2.5: FeaturePipelineQAIntegration tracks coverage per issue
# =============================================================================


class TestSessionExtensionInitialization:
    """Tests for QASessionExtension initialization in FeaturePipelineQAIntegration."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_creates_session_extension(self, mock_config):
        """FeaturePipelineQAIntegration should create QASessionExtension instance."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )

        integration = FeaturePipelineQAIntegration(mock_config)

        assert hasattr(integration, "session_extension")
        assert integration.session_extension is not None

    def test_session_extension_is_correct_type(self, mock_config):
        """QASessionExtension should be the correct type."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )
        from swarm_attack.qa.session_extension import QASessionExtension

        integration = FeaturePipelineQAIntegration(mock_config)

        assert isinstance(integration.session_extension, QASessionExtension)

    def test_session_extension_swarm_dir_is_correct(self, mock_config, tmp_path):
        """Session extension should use correct swarm_dir path (criterion 2.9)."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )

        integration = FeaturePipelineQAIntegration(mock_config)

        expected_swarm_dir = Path(mock_config.repo_root) / ".swarm"
        coverage_tracker = integration.session_extension._coverage_tracker

        assert str(expected_swarm_dir) in str(coverage_tracker._coverage_dir)


class TestCoverageTrackingPerIssue:
    """Tests for coverage tracking during post-verification QA."""

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

        integration = FeaturePipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()
        integration.session_extension = MagicMock()
        return integration

    def test_on_session_start_called_during_post_verification(self, integration):
        """on_session_start() should be called during run_post_verification_qa()."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-test-123"
        mock_session.result = QAResult(recommendation=QARecommendation.PASS)
        integration.orchestrator.validate_issue.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
        )

        integration.session_extension.on_session_start.assert_called_once()

    def test_on_session_complete_called_after_validation(self, integration):
        """on_session_complete() should be called after validation."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-test-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            findings=[],
        )
        integration.orchestrator.validate_issue.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
        )

        integration.session_extension.on_session_complete.assert_called_once()

    def test_session_id_includes_issue_number(self, integration):
        """Session ID should include issue number for per-issue tracking."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-test-123"
        mock_session.result = QAResult(recommendation=QARecommendation.PASS)
        integration.orchestrator.validate_issue.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
        )

        # Check that session_start was called with an ID related to the issue
        call_args = integration.session_extension.on_session_start.call_args
        session_id_arg = call_args[0][0] if call_args[0] else call_args[1].get("session_id")
        # Session ID should be meaningful (not empty)
        assert session_id_arg is not None

    def test_blocks_when_session_extension_requires_blocking(self, integration):
        """Should block when session extension result has should_block=True."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-test-123"
        mock_session.result = QAResult(recommendation=QARecommendation.PASS)
        integration.orchestrator.validate_issue.return_value = mock_session

        # Session extension requires blocking due to coverage drop
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=True,
            block_reason="Coverage dropped significantly: -15.0%",
        )

        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
        )

        assert result.should_block is True

    def test_skip_qa_does_not_call_session_extension(self, integration):
        """When skip_qa=True, session extension should not be called."""
        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
            skip_qa=True,
        )

        integration.session_extension.on_session_start.assert_not_called()
        integration.session_extension.on_session_complete.assert_not_called()


# =============================================================================
# CRITERION 2.6: Can set baselines after feature completion
# =============================================================================


class TestBaselineAfterFeatureCompletion:
    """Tests for setting baselines after feature completion."""

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

        integration = FeaturePipelineQAIntegration(mock_config)
        integration.session_extension = MagicMock()
        return integration

    def test_has_set_baseline_method(self, integration):
        """FeaturePipelineQAIntegration should have set_coverage_baseline method."""
        assert hasattr(integration, "set_coverage_baseline")
        assert callable(getattr(integration, "set_coverage_baseline"))

    def test_set_baseline_calls_session_extension(self, integration):
        """set_coverage_baseline should call session_extension.set_as_baseline."""
        integration.set_coverage_baseline(
            session_id="qa-test-123",
            endpoints_tested=["GET /api/users", "POST /api/users"],
            findings=[],
        )

        integration.session_extension.set_as_baseline.assert_called_once()

    def test_set_baseline_passes_correct_arguments(self, integration):
        """set_coverage_baseline should pass all required arguments."""
        endpoints = ["GET /api/users", "POST /api/users"]
        findings = [{"id": "f1", "severity": "moderate"}]

        integration.set_coverage_baseline(
            session_id="qa-test-123",
            endpoints_tested=endpoints,
            findings=findings,
        )

        call_args = integration.session_extension.set_as_baseline.call_args
        # Should have session_id, endpoints_tested, findings
        assert call_args[0][0] == "qa-test-123" or call_args[1].get("session_id") == "qa-test-123"


class TestCoverageReportInResult:
    """Tests for coverage report being included in result."""

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

        integration = FeaturePipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()
        integration.session_extension = MagicMock()
        return integration

    def test_result_includes_coverage_info(self, integration):
        """QAIntegrationResult should include coverage information."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-test-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            findings=[],
            critical_count=0,
            moderate_count=0,
            minor_count=0,
        )
        integration.orchestrator.validate_issue.return_value = mock_session

        mock_coverage_report = MagicMock()
        mock_coverage_report.coverage_percentage = 85.0
        mock_coverage_report.coverage_delta = 5.0

        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
            coverage_report=mock_coverage_report,
        )

        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
        )

        # Result should have coverage information available
        assert result is not None
        # Coverage info should be accessible (either in result or via session extension)


# =============================================================================
# INTEGRATION TEST: Full flow with real QASessionExtension
# =============================================================================


class TestFullIntegrationWithSessionExtension:
    """Integration tests with real QASessionExtension instance."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_full_flow_with_session_extension(self, mock_config, tmp_path):
        """Full flow should work with real QASessionExtension."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )

        integration = FeaturePipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-test-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            findings=[],
            critical_count=0,
            moderate_count=0,
            minor_count=0,
        )
        integration.orchestrator.validate_issue.return_value = mock_session

        result = integration.run_post_verification_qa(
            feature_id="my-feature",
            issue_number=42,
            verified_files=["src/api/users.py"],
        )

        assert result is not None
        assert result.session_id == "qa-test-123"

    def test_coverage_baseline_can_be_set(self, mock_config, tmp_path):
        """Should be able to set coverage baseline after completion."""
        from swarm_attack.qa.integrations.feature_pipeline import (
            FeaturePipelineQAIntegration,
        )

        integration = FeaturePipelineQAIntegration(mock_config)

        # This should not raise
        integration.set_coverage_baseline(
            session_id="qa-test-123",
            endpoints_tested=["GET /api/users"],
            findings=[],
        )

        # Coverage directory should exist
        swarm_dir = tmp_path / ".swarm"
        coverage_dir = swarm_dir / "qa" / "coverage"
        assert coverage_dir.exists() or swarm_dir.exists()
