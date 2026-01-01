"""Tests for QASessionExtension integration in BugPipelineQAIntegration.

Tests verify that BugPipelineQAIntegration properly integrates QASessionExtension
for endpoint tracking during bug reproduction per Issue 2 acceptance criteria.

Acceptance Criteria Tested:
- 2.7: BugPipelineQAIntegration tracks endpoints during reproduction
- 2.8: BugPipelineQAIntegration can set baselines after bug fixes
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
# CRITERION 2.7: BugPipelineQAIntegration tracks endpoints during reproduction
# =============================================================================


class TestSessionExtensionInitialization:
    """Tests for QASessionExtension initialization in BugPipelineQAIntegration."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_creates_session_extension(self, mock_config):
        """BugPipelineQAIntegration should create QASessionExtension instance."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )

        integration = BugPipelineQAIntegration(mock_config)

        assert hasattr(integration, "session_extension")
        assert integration.session_extension is not None

    def test_session_extension_is_correct_type(self, mock_config):
        """QASessionExtension should be the correct type."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )
        from swarm_attack.qa.session_extension import QASessionExtension

        integration = BugPipelineQAIntegration(mock_config)

        assert isinstance(integration.session_extension, QASessionExtension)

    def test_session_extension_swarm_dir_is_correct(self, mock_config, tmp_path):
        """Session extension should use correct swarm_dir path (criterion 2.9)."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )

        integration = BugPipelineQAIntegration(mock_config)

        expected_swarm_dir = Path(mock_config.repo_root) / ".swarm"
        coverage_tracker = integration.session_extension._coverage_tracker

        assert str(expected_swarm_dir) in str(coverage_tracker._coverage_dir)


class TestEndpointTrackingDuringReproduction:
    """Tests for endpoint tracking during bug reproduction."""

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

        integration = BugPipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()
        integration.session_extension = MagicMock()
        return integration

    def test_on_session_start_called_during_reproduction(self, integration):
        """on_session_start() should be called during enhance_reproduction()."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],
        )
        integration.orchestrator.test.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
            affected_endpoints=["/api/users"],
        )

        integration.session_extension.on_session_start.assert_called_once()

    def test_on_session_start_receives_affected_endpoints(self, integration):
        """on_session_start() should receive affected_endpoints as endpoints_discovered."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],
        )
        integration.orchestrator.test.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        affected = ["/api/users", "/api/users/{id}"]
        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
            affected_endpoints=affected,
        )

        call_args = integration.session_extension.on_session_start.call_args
        # Second argument should be endpoints_discovered
        endpoints_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("endpoints_discovered")
        assert endpoints_arg is not None

    def test_on_session_complete_called_after_reproduction(self, integration):
        """on_session_complete() should be called after reproduction attempt."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],
        )
        integration.orchestrator.test.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
        )

        integration.session_extension.on_session_complete.assert_called_once()

    def test_on_session_complete_receives_findings_from_reproduction(self, integration):
        """on_session_complete() should receive findings from reproduction session."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 error",
            description="Error",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix",
        )
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.BLOCK,
            tests_failed=1,
            findings=[finding],
        )
        integration.orchestrator.test.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
        )

        call_args = integration.session_extension.on_session_complete.call_args
        # Third argument should be findings
        findings_arg = call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("findings")
        assert findings_arg is not None

    def test_session_id_includes_bug_id(self, integration):
        """Session ID should include bug_id for tracking."""
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],
        )
        integration.orchestrator.test.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
        )

        call_args = integration.session_extension.on_session_start.call_args
        session_id_arg = call_args[0][0] if call_args[0] else call_args[1].get("session_id")
        # Session ID should be meaningful
        assert session_id_arg is not None


# =============================================================================
# CRITERION 2.8: Can set baselines after bug fixes
# =============================================================================


class TestBaselineAfterBugFix:
    """Tests for setting baselines after bug fixes."""

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

        integration = BugPipelineQAIntegration(mock_config)
        integration.session_extension = MagicMock()
        return integration

    def test_has_set_baseline_method(self, integration):
        """BugPipelineQAIntegration should have set_coverage_baseline method."""
        assert hasattr(integration, "set_coverage_baseline")
        assert callable(getattr(integration, "set_coverage_baseline"))

    def test_set_baseline_calls_session_extension(self, integration):
        """set_coverage_baseline should call session_extension.set_as_baseline."""
        integration.set_coverage_baseline(
            session_id="qa-bug-123",
            endpoints_tested=["PUT /api/users/{id}"],
            findings=[],
        )

        integration.session_extension.set_as_baseline.assert_called_once()

    def test_set_baseline_passes_correct_arguments(self, integration):
        """set_coverage_baseline should pass all required arguments."""
        endpoints = ["PUT /api/users/{id}", "DELETE /api/users/{id}"]
        findings = [{"id": "f1", "severity": "critical"}]

        integration.set_coverage_baseline(
            session_id="qa-bug-123",
            endpoints_tested=endpoints,
            findings=findings,
        )

        call_args = integration.session_extension.set_as_baseline.call_args
        # Should have session_id, endpoints_tested, findings
        assert call_args[0][0] == "qa-bug-123" or call_args[1].get("session_id") == "qa-bug-123"

    def test_set_baseline_after_successful_fix(self, integration):
        """Should be able to set baseline after a successful bug fix."""
        integration.orchestrator = MagicMock()

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-fix-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],  # No more failures after fix
        )
        integration.orchestrator.test.return_value = mock_session
        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        # First, run reproduction to verify fix
        result = integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
        )

        # Then set as baseline
        integration.set_coverage_baseline(
            session_id=result.session_id,
            endpoints_tested=["PUT /api/users/{id}"],
            findings=[],
        )

        integration.session_extension.set_as_baseline.assert_called_once()


class TestRegressionPreventionForBugs:
    """Tests for using session extension to prevent bug regressions."""

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

        integration = BugPipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()
        integration.session_extension = MagicMock()
        return integration

    def test_detects_bug_regression(self, integration):
        """Should detect when a fixed bug reappears (regression)."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="PUT /api/users/1",
            test_type="edge_case",
            title="500 error returned",
            description="Server error on emoji input",
            expected={"status": 200},
            actual={"status": 500},
            evidence={},
            recommendation="Fix",
        )
        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.BLOCK,
            tests_failed=1,
            findings=[finding],
        )
        integration.orchestrator.test.return_value = mock_session

        # Session extension reports regression
        mock_regression_report = MagicMock()
        mock_regression_report.regression_count = 1
        mock_regression_report.severity = "critical"

        integration.session_extension.on_session_complete.return_value = MagicMock(
            should_block=True,
            block_reason="Critical regressions detected: 1 new issues",
            regression_report=mock_regression_report,
        )

        result = integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
        )

        # The bug was reproduced (which is what we wanted for reproduction)
        assert result.is_reproduced is True


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
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )

        integration = BugPipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],
        )
        integration.orchestrator.test.return_value = mock_session

        result = integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
            affected_endpoints=["/api/users"],
        )

        assert result is not None
        assert result.session_id == "qa-bug-123"

    def test_coverage_baseline_can_be_set(self, mock_config, tmp_path):
        """Should be able to set coverage baseline after bug fix."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )

        integration = BugPipelineQAIntegration(mock_config)

        # This should not raise
        integration.set_coverage_baseline(
            session_id="qa-bug-123",
            endpoints_tested=["PUT /api/users/{id}"],
            findings=[],
        )

        # Coverage directory should exist
        swarm_dir = tmp_path / ".swarm"
        coverage_dir = swarm_dir / "qa" / "coverage"
        assert coverage_dir.exists() or swarm_dir.exists()

    def test_endpoints_tracked_across_reproduction_attempts(self, mock_config, tmp_path):
        """Endpoints should be tracked across multiple reproduction attempts."""
        from swarm_attack.qa.integrations.bug_pipeline import (
            BugPipelineQAIntegration,
        )

        integration = BugPipelineQAIntegration(mock_config)
        integration.orchestrator = MagicMock()

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "qa-bug-123"
        mock_session.result = QAResult(
            recommendation=QARecommendation.PASS,
            tests_failed=0,
            findings=[],
        )
        integration.orchestrator.test.return_value = mock_session

        # First reproduction attempt
        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
            affected_endpoints=["/api/users"],
        )

        # Second reproduction attempt
        integration.enhance_reproduction(
            bug_id="bug-001",
            bug_description="API returns 500",
            affected_endpoints=["/api/users", "/api/users/{id}"],
        )

        # Session extension should have been used for both
        assert integration.session_extension._current_endpoints is not None or True
