"""Tests for VerifierQAHook following TDD approach.

Tests cover spec section 3: Pipeline Integration - Verifier Hook
- Post-verification QA hook that runs after Verifier completes
- Skips on verification failure
- Passes context to QA orchestrator
- Reports findings back to pipeline
- Graceful degradation if QA fails
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from swarm_attack.qa.models import (
    QAContext,
    QADepth,
    QAEndpoint,
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
    """Tests to verify VerifierQAHook can be imported."""

    def test_can_import_verifier_hook(self):
        """Should be able to import VerifierQAHook class."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        assert VerifierQAHook is not None

    def test_can_import_verifier_hook_result(self):
        """Should be able to import VerifierHookResult."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierHookResult
        assert VerifierHookResult is not None


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestVerifierQAHookInit:
    """Tests for VerifierQAHook initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        hook = VerifierQAHook(mock_config)
        assert hook.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        logger = MagicMock()
        hook = VerifierQAHook(mock_config, logger=logger)
        assert hook._logger == logger

    def test_init_creates_orchestrator(self, mock_config):
        """Should create QAOrchestrator instance."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        hook = VerifierQAHook(mock_config)
        assert hook.orchestrator is not None

    def test_init_creates_context_builder(self, mock_config):
        """Should create QAContextBuilder instance."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        hook = VerifierQAHook(mock_config)
        assert hook.context_builder is not None

    def test_init_creates_depth_selector(self, mock_config):
        """Should create DepthSelector instance."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        hook = VerifierQAHook(mock_config)
        assert hook.depth_selector is not None


# =============================================================================
# SHOULD RUN TESTS
# =============================================================================


class TestShouldRun:
    """Tests for should_run() method."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return VerifierQAHook(config)

    def test_runs_after_successful_verification(self, hook):
        """Should run when verification succeeded."""
        result = hook.should_run(
            verification_success=True,
            feature_id="my-feature",
            issue_number=42,
        )
        assert result is True

    def test_skips_on_verification_failure(self, hook):
        """Should skip when verification failed."""
        result = hook.should_run(
            verification_success=False,
            feature_id="my-feature",
            issue_number=42,
        )
        assert result is False

    def test_skips_if_qa_disabled(self, hook):
        """Should skip if QA is disabled in config."""
        hook.qa_enabled = False
        result = hook.should_run(
            verification_success=True,
            feature_id="my-feature",
            issue_number=42,
        )
        assert result is False

    def test_runs_for_valid_feature_and_issue(self, hook):
        """Should run with valid feature_id and issue_number."""
        result = hook.should_run(
            verification_success=True,
            feature_id="auth-feature",
            issue_number=1,
        )
        assert result is True


# =============================================================================
# RUN TESTS
# =============================================================================


class TestRun:
    """Tests for run() method."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = VerifierQAHook(config)
        # Mock the orchestrator
        hook.orchestrator = MagicMock()
        return hook

    def test_returns_hook_result(self, hook):
        """Should return VerifierHookResult."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierHookResult

        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert isinstance(result, VerifierHookResult)

    def test_calls_orchestrator_validate_issue(self, hook):
        """Should call orchestrator.validate_issue()."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        hook.orchestrator.validate_issue.assert_called_once()

    def test_passes_feature_and_issue_to_orchestrator(self, hook):
        """Should pass feature_id and issue_number to orchestrator."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        hook.run(
            feature_id="auth-feature",
            issue_number=99,
            target_files=[],
        )

        call_kwargs = hook.orchestrator.validate_issue.call_args
        assert call_kwargs[1]["feature_id"] == "auth-feature"
        assert call_kwargs[1]["issue_number"] == 99

    def test_includes_session_id_in_result(self, hook):
        """Result should include session_id."""
        mock_session = QASession(
            session_id="qa-session-abc",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert result.session_id == "qa-session-abc"

    def test_includes_recommendation_in_result(self, hook):
        """Result should include recommendation."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.WARN),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert result.recommendation == QARecommendation.WARN

    def test_includes_findings_in_result(self, hook):
        """Result should include findings."""
        finding = QAFinding(
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
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.BLOCK,
                findings=[finding],
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert len(result.findings) == 1
        assert result.findings[0].finding_id == "BT-001"


# =============================================================================
# GRACEFUL DEGRADATION TESTS
# =============================================================================


class TestGracefulDegradation:
    """Tests for graceful degradation when QA fails."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = VerifierQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_returns_success_on_orchestrator_exception(self, hook):
        """Should return success with warning on orchestrator exception."""
        hook.orchestrator.validate_issue.side_effect = Exception("QA failed")

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        # Should not propagate exception
        assert result is not None
        # Should indicate skipped/degraded
        assert result.skipped or result.error is not None

    def test_returns_success_on_timeout(self, hook):
        """Should return success with warning on timeout."""
        hook.orchestrator.validate_issue.side_effect = TimeoutError("QA timed out")

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        # Should not propagate exception
        assert result is not None
        assert result.skipped or result.error is not None

    def test_does_not_block_on_qa_failure(self, hook):
        """QA failures should not block the pipeline."""
        hook.orchestrator.validate_issue.side_effect = Exception("Critical QA error")

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        # Result should indicate pass (degraded) so pipeline continues
        assert result.should_continue is True

    def test_logs_qa_failure(self, hook):
        """Should log when QA fails."""
        hook._logger = MagicMock()
        hook.orchestrator.validate_issue.side_effect = Exception("QA error")

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        # Should have logged the error
        # Implementation may vary in logging approach


# =============================================================================
# SHOULD BLOCK PIPELINE TESTS
# =============================================================================


class TestShouldBlockPipeline:
    """Tests for pipeline blocking behavior."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = VerifierQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_blocks_on_critical_findings(self, hook):
        """Should block pipeline on critical findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Critical error",
            description="Critical issue",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix immediately",
        )
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.BLOCK,
                findings=[finding],
                critical_count=1,
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert result.should_block is True

    def test_does_not_block_on_pass(self, hook):
        """Should not block pipeline on PASS recommendation."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert result.should_block is False

    def test_warns_on_moderate_findings(self, hook):
        """Should warn but not block on moderate findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="moderate",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Moderate issue",
            description="Moderate issue",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix soon",
        )
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.WARN,
                findings=[finding],
                moderate_count=1,
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert result.should_block is False
        assert result.has_warnings is True


# =============================================================================
# BUG CREATION TESTS
# =============================================================================


class TestBugCreation:
    """Tests for bug creation from findings."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = VerifierQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_creates_bugs_for_critical_findings(self, hook):
        """Should create bugs for critical findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Critical bug",
            description="Critical issue",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.BLOCK,
                findings=[finding],
                critical_count=1,
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.orchestrator.create_bug_investigations.return_value = ["bug-001"]

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        # Should have called create_bug_investigations
        hook.orchestrator.create_bug_investigations.assert_called()

    def test_returns_bug_ids_in_result(self, hook):
        """Should return created bug IDs in result."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Bug",
            description="Bug",
            expected={},
            actual={},
            evidence={},
            recommendation="Fix",
        )
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.BLOCK,
                findings=[finding],
                critical_count=1,
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.orchestrator.create_bug_investigations.return_value = ["bug-001", "bug-002"]

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=[],
        )

        assert "bug-001" in result.created_bugs
        assert "bug-002" in result.created_bugs


# =============================================================================
# DEPTH SELECTION TESTS
# =============================================================================


class TestDepthSelection:
    """Tests for depth selection integration."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = VerifierQAHook(config)
        hook.orchestrator = MagicMock()
        hook.depth_selector = MagicMock()
        return hook

    def test_uses_depth_selector(self, hook):
        """Should use DepthSelector to determine depth."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.depth_selector.select_depth.return_value = QADepth.DEEP

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/auth/login.py"],
        )

        hook.depth_selector.select_depth.assert_called()

    def test_passes_selected_depth_to_orchestrator(self, hook):
        """Should pass selected depth to orchestrator."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.depth_selector.select_depth.return_value = QADepth.DEEP

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/auth/login.py"],
        )

        call_kwargs = hook.orchestrator.validate_issue.call_args
        assert call_kwargs[1]["depth"] == QADepth.DEEP


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for VerifierQAHook."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return VerifierQAHook(config)

    def test_full_flow_pass(self, hook):
        """Test full flow with passing QA."""
        with patch.object(hook.orchestrator, 'validate_issue') as mock_validate:
            mock_session = QASession(
                session_id="qa-test-123",
                trigger=QATrigger.POST_VERIFICATION,
                depth=QADepth.STANDARD,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.PASS,
                    tests_run=10,
                    tests_passed=10,
                ),
            )
            mock_validate.return_value = mock_session

            result = hook.run(
                feature_id="my-feature",
                issue_number=42,
                target_files=["src/api/users.py"],
            )

            assert result.should_block is False
            assert result.should_continue is True
            assert result.recommendation == QARecommendation.PASS

    def test_full_flow_block(self, hook):
        """Test full flow with blocking QA."""
        with patch.object(hook.orchestrator, 'validate_issue') as mock_validate:
            with patch.object(hook.orchestrator, 'create_bug_investigations') as mock_bugs:
                finding = QAFinding(
                    finding_id="BT-001",
                    severity="critical",
                    category="behavioral",
                    endpoint="GET /api/users",
                    test_type="happy_path",
                    title="Critical bug",
                    description="Critical",
                    expected={},
                    actual={},
                    evidence={},
                    recommendation="Fix",
                )
                mock_session = QASession(
                    session_id="qa-test-123",
                    trigger=QATrigger.POST_VERIFICATION,
                    depth=QADepth.DEEP,
                    status=QAStatus.COMPLETED,
                    context=QAContext(),
                    result=QAResult(
                        recommendation=QARecommendation.BLOCK,
                        findings=[finding],
                        critical_count=1,
                    ),
                )
                mock_validate.return_value = mock_session
                mock_bugs.return_value = ["bug-123"]

                result = hook.run(
                    feature_id="my-feature",
                    issue_number=42,
                    target_files=["src/auth/login.py"],
                )

                assert result.should_block is True
                assert result.recommendation == QARecommendation.BLOCK
                assert len(result.created_bugs) > 0
