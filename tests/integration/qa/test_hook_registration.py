"""Hook Registration Tests.

Tests that QA hooks are properly integrated into the pipeline.
- Hook registration and initialization
- Hook triggering at correct times
- Context passing to hooks
- Error handling and graceful degradation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook, VerifierHookResult
from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook, BugHookResult
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
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config():
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = "/tmp/test-project"
    config.specs_path = MagicMock()
    config.specs_path.__truediv__ = MagicMock(return_value=MagicMock())
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock()
    logger.log = MagicMock()
    return logger


@pytest.fixture
def sample_finding():
    """Create a sample QA finding."""
    return QAFinding(
        finding_id="BT-001",
        severity="critical",
        category="behavioral",
        endpoint="GET /api/users",
        test_type="happy_path",
        title="Server error on GET /api/users",
        description="Endpoint returns 500 instead of 200",
        expected={"status": 200},
        actual={"status": 500},
        evidence={"request": "curl -X GET http://localhost:8000/api/users"},
        recommendation="Fix server error handling",
    )


@pytest.fixture
def passing_session():
    """Create a passing QA session."""
    context = QAContext(base_url="http://localhost:8000")
    result = QAResult(
        tests_run=5,
        tests_passed=5,
        tests_failed=0,
        endpoints_tested=["/api/users"],
        recommendation=QARecommendation.PASS,
        findings=[],
    )
    session = QASession(
        session_id="qa-20241226-120000",
        trigger=QATrigger.POST_VERIFICATION,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=context,
        result=result,
    )
    session.started_at = datetime.now(timezone.utc).isoformat()
    session.completed_at = datetime.now(timezone.utc).isoformat()
    return session


@pytest.fixture
def failing_session(sample_finding):
    """Create a failing QA session with findings."""
    context = QAContext(base_url="http://localhost:8000")
    result = QAResult(
        tests_run=5,
        tests_passed=2,
        tests_failed=3,
        endpoints_tested=["/api/users"],
        recommendation=QARecommendation.BLOCK,
        findings=[sample_finding],
    )
    session = QASession(
        session_id="qa-20241226-130000",
        trigger=QATrigger.POST_VERIFICATION,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=context,
        result=result,
    )
    session.started_at = datetime.now(timezone.utc).isoformat()
    session.completed_at = datetime.now(timezone.utc).isoformat()
    return session


@pytest.fixture
def warning_session():
    """Create a QA session with warnings."""
    context = QAContext(base_url="http://localhost:8000")
    result = QAResult(
        tests_run=5,
        tests_passed=4,
        tests_failed=1,
        endpoints_tested=["/api/users"],
        recommendation=QARecommendation.WARN,
        findings=[],
    )
    session = QASession(
        session_id="qa-20241226-140000",
        trigger=QATrigger.POST_VERIFICATION,
        depth=QADepth.STANDARD,
        status=QAStatus.COMPLETED,
        context=context,
        result=result,
    )
    session.started_at = datetime.now(timezone.utc).isoformat()
    session.completed_at = datetime.now(timezone.utc).isoformat()
    return session


# =============================================================================
# VERIFIER HOOK REGISTRATION TESTS
# =============================================================================


class TestVerifierHookRegistration:
    """Tests for Verifier hook registration."""

    def test_hook_registered_post_verification(self, mock_config, mock_logger):
        """Hook should be registered to run after verification."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder"):
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector"):
                    hook = VerifierQAHook(mock_config, mock_logger)

                    # Verify hook is initialized and ready to run
                    assert hook.config == mock_config
                    assert hook._logger == mock_logger
                    assert hook.qa_enabled is True
                    assert hook.orchestrator is not None
                    assert hook.context_builder is not None
                    assert hook.depth_selector is not None

    def test_hook_receives_verification_context(
        self, mock_config, mock_logger, passing_session
    ):
        """Hook should receive full verification context."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.return_value = passing_session
                    mock_orch.create_bug_investigations.return_value = []
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_context = QAContext(base_url="http://localhost:8000")
                    mock_ctx.build_context.return_value = mock_context
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)

                    result = hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                        base_url="http://localhost:8000",
                    )

                    # Verify context was built with correct parameters
                    mock_ctx.build_context.assert_called_once()
                    call_kwargs = mock_ctx.build_context.call_args.kwargs
                    assert call_kwargs["trigger"] == QATrigger.POST_VERIFICATION
                    assert call_kwargs["feature_id"] == "my-feature"
                    assert call_kwargs["issue_number"] == 42

    def test_hook_skipped_on_verification_failure(self, mock_config, mock_logger):
        """Hook should not run if verification failed."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder"):
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector"):
                    hook = VerifierQAHook(mock_config, mock_logger)

                    # Check if hook should run when verification failed
                    should_run = hook.should_run(
                        verification_success=False,
                        feature_id="my-feature",
                        issue_number=42,
                    )

                    assert should_run is False

    def test_hook_runs_on_verification_success(self, mock_config, mock_logger):
        """Hook should run when verification passed."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder"):
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector"):
                    hook = VerifierQAHook(mock_config, mock_logger)

                    # Check if hook should run when verification passed
                    should_run = hook.should_run(
                        verification_success=True,
                        feature_id="my-feature",
                        issue_number=42,
                    )

                    assert should_run is True

    def test_hook_disabled_skip(self, mock_config, mock_logger):
        """Hook should not run when QA is disabled."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder"):
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector"):
                    hook = VerifierQAHook(mock_config, mock_logger)
                    hook.qa_enabled = False

                    should_run = hook.should_run(
                        verification_success=True,
                        feature_id="my-feature",
                        issue_number=42,
                    )

                    assert should_run is False

    def test_hook_returns_pass_result(
        self, mock_config, mock_logger, passing_session
    ):
        """Hook should return PASS when QA passes."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.return_value = passing_session
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)

                    result = hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    assert result.recommendation == QARecommendation.PASS
                    assert result.should_block is False
                    assert result.should_continue is True

    def test_hook_returns_block_result(
        self, mock_config, mock_logger, failing_session
    ):
        """Hook should return BLOCK when QA fails critically."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.return_value = failing_session
                    mock_orch.create_bug_investigations.return_value = ["bug-001"]
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)

                    result = hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    assert result.recommendation == QARecommendation.BLOCK
                    assert result.should_block is True
                    assert result.should_continue is False
                    assert "bug-001" in result.created_bugs

    def test_hook_returns_warn_result(
        self, mock_config, mock_logger, warning_session
    ):
        """Hook should return WARN and allow continuation."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.return_value = warning_session
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)

                    result = hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    assert result.recommendation == QARecommendation.WARN
                    assert result.has_warnings is True
                    assert result.should_continue is True

    def test_hook_handles_timeout_gracefully(self, mock_config, mock_logger):
        """Hook should handle timeout and allow continuation."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.side_effect = TimeoutError("QA timed out")
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)

                    result = hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    # Should not block on timeout
                    assert result.skipped is True
                    assert result.should_continue is True
                    assert "timed out" in result.error.lower()

    def test_hook_handles_exception_gracefully(self, mock_config, mock_logger):
        """Hook should handle exceptions and allow continuation."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.side_effect = Exception("Network error")
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)

                    result = hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    # Graceful degradation - don't block
                    assert result.skipped is True
                    assert result.should_continue is True
                    assert result.error is not None


# =============================================================================
# BUG RESEARCHER HOOK REGISTRATION TESTS
# =============================================================================


class TestBugResearcherHookRegistration:
    """Tests for BugResearcher hook registration."""

    def test_hook_registered_on_reproduction_failure(self, mock_config, mock_logger):
        """Hook should be registered for reproduction failures."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config, mock_logger)

                # Verify hook is initialized
                assert hook.config == mock_config
                assert hook._logger == mock_logger
                assert hook.orchestrator is not None
                assert hook.context_builder is not None

    def test_hook_receives_bug_context(
        self, mock_config, mock_logger, failing_session
    ):
        """Hook should receive bug details."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.return_value = failing_session
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_context = QAContext(base_url="http://localhost:8000")
                mock_ctx.build_context.return_value = mock_context
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)

                result = hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1", "Step 2"],
                    affected_files=["src/api/users.py"],
                    base_url="http://localhost:8000",
                )

                # Verify context was built with bug trigger
                mock_ctx.build_context.assert_called_once()
                call_kwargs = mock_ctx.build_context.call_args.kwargs
                assert call_kwargs["trigger"] == QATrigger.BUG_REPRODUCTION
                assert call_kwargs["bug_id"] == "BUG-123"

    def test_hook_provides_enhanced_reproduction(
        self, mock_config, mock_logger, failing_session
    ):
        """Hook should provide enhanced reproduction data."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.return_value = failing_session
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)

                result = hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1", "Step 2"],
                )

                # Should provide enhanced data
                assert result.bug_id == "BUG-123"
                assert result.session_id is not None
                assert result.is_reproducible is True  # BLOCK = reproducible
                assert len(result.findings) > 0
                assert isinstance(result.evidence, dict)
                assert isinstance(result.root_cause_hints, list)

    def test_hook_uses_deep_testing(self, mock_config, mock_logger, failing_session):
        """Hook should use DEEP depth for bug reproduction."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.return_value = failing_session
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)

                result = hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1"],
                )

                # Verify DEEP depth was used
                mock_orch.test.assert_called_once()
                call_kwargs = mock_orch.test.call_args.kwargs
                assert call_kwargs.get("depth") == QADepth.DEEP

    def test_hook_bug_not_reproducible(
        self, mock_config, mock_logger, passing_session
    ):
        """Hook should indicate bug is not reproducible when tests pass."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.return_value = passing_session
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)

                result = hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1"],
                )

                assert result.is_reproducible is False

    def test_hook_handles_timeout(self, mock_config, mock_logger):
        """Hook should handle timeout gracefully."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.side_effect = TimeoutError("Validation timed out")
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)

                result = hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1"],
                )

                assert result.is_inconclusive is True
                assert "timed out" in result.error.lower()

    def test_hook_handles_exception(self, mock_config, mock_logger):
        """Hook should handle exceptions gracefully."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.side_effect = Exception("Network error")
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)

                result = hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1"],
                )

                assert result.is_inconclusive is True
                assert result.error is not None


# =============================================================================
# EVIDENCE EXTRACTION TESTS
# =============================================================================


class TestEvidenceExtraction:
    """Tests for evidence extraction from findings."""

    def test_extract_evidence_from_findings(self, mock_config, sample_finding):
        """Should extract evidence from findings."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config)

                evidence = hook._extract_evidence([sample_finding])

                assert "finding_1" in evidence
                assert evidence["finding_1"]["endpoint"] == "GET /api/users"
                assert evidence["finding_1"]["severity"] == "critical"
                assert "finding_1_details" in evidence  # Has additional evidence

    def test_extract_evidence_empty_findings(self, mock_config):
        """Should handle empty findings list."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config)

                evidence = hook._extract_evidence([])

                assert evidence == {}


# =============================================================================
# ROOT CAUSE HINTS TESTS
# =============================================================================


class TestRootCauseHints:
    """Tests for root cause hint generation."""

    def test_generate_hints_from_behavioral_finding(self, mock_config):
        """Should generate behavioral hints."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config)

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
                    evidence={"request": "GET /api/users"},
                    recommendation="Fix the error",
                )

                hints = hook._generate_root_cause_hints([finding])

                # Should include behavioral hint
                assert any("Behavioral issue" in hint for hint in hints)
                # Should include server error hint
                assert any("500" in hint or "Server error" in hint for hint in hints)
                # Should include severity hint
                assert any("Critical" in hint for hint in hints)

    def test_generate_hints_from_contract_finding(self, mock_config):
        """Should generate contract hints."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config)

                finding = QAFinding(
                    finding_id="CT-001",
                    severity="moderate",
                    category="contract",
                    endpoint="GET /api/users",
                    test_type="schema_validation",
                    title="Schema mismatch",
                    description="Response doesn't match schema",
                    expected={"type": "array"},
                    actual={"type": "object"},
                    evidence={"response": "{}"},
                    recommendation="Fix schema",
                )

                hints = hook._generate_root_cause_hints([finding])

                # Should include contract hint
                assert any("Contract violation" in hint for hint in hints)

    def test_generate_hints_from_regression_finding(self, mock_config):
        """Should generate regression hints."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config)

                finding = QAFinding(
                    finding_id="RT-001",
                    severity="moderate",
                    category="regression",
                    endpoint="GET /api/users",
                    test_type="regression",
                    title="Regression detected",
                    description="Behavior changed from previous version",
                    expected={"behavior": "old"},
                    actual={"behavior": "new"},
                    evidence={"diff": "changed"},
                    recommendation="Review changes",
                )

                hints = hook._generate_root_cause_hints([finding])

                # Should include regression hint
                assert any("Regression detected" in hint for hint in hints)

    def test_deduplicates_hints(self, mock_config):
        """Should deduplicate hints."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator"):
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder"):
                hook = BugResearcherQAHook(mock_config)

                # Two identical findings
                finding = QAFinding(
                    finding_id="BT-001",
                    severity="critical",
                    category="behavioral",
                    endpoint="GET /api/users",
                    test_type="happy_path",
                    title="Same error",
                    description="Same description",
                    expected={"status": 200},
                    actual={"status": 500},
                    evidence={"request": "GET /api/users"},
                    recommendation="Same fix",
                )

                hints = hook._generate_root_cause_hints([finding, finding])

                # Count unique hints
                unique_hints = set(hints)
                assert len(hints) == len(unique_hints)


# =============================================================================
# LOGGING TESTS
# =============================================================================


class TestHookLogging:
    """Tests for hook logging."""

    def test_verifier_hook_logs_start(
        self, mock_config, mock_logger, passing_session
    ):
        """Verifier hook should log start."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.return_value = passing_session
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)
                    hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    # Should have logged start
                    log_calls = mock_logger.log.call_args_list
                    event_types = [call[0][0] for call in log_calls]
                    assert "qa_hook_start" in event_types

    def test_verifier_hook_logs_complete(
        self, mock_config, mock_logger, passing_session
    ):
        """Verifier hook should log completion."""
        with patch("swarm_attack.qa.hooks.verifier_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.verifier_hook.QAContextBuilder") as mock_ctx_cls:
                with patch("swarm_attack.qa.hooks.verifier_hook.DepthSelector") as mock_depth_cls:
                    mock_orch = MagicMock()
                    mock_orch.validate_issue.return_value = passing_session
                    mock_orch_cls.return_value = mock_orch

                    mock_ctx = MagicMock()
                    mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                    mock_ctx_cls.return_value = mock_ctx

                    mock_depth = MagicMock()
                    mock_depth.select_depth.return_value = QADepth.STANDARD
                    mock_depth_cls.return_value = mock_depth

                    hook = VerifierQAHook(mock_config, mock_logger)
                    hook.run(
                        feature_id="my-feature",
                        issue_number=42,
                        target_files=["src/api/users.py"],
                    )

                    # Should have logged complete
                    log_calls = mock_logger.log.call_args_list
                    event_types = [call[0][0] for call in log_calls]
                    assert "qa_hook_complete" in event_types

    def test_bug_hook_logs_validation(
        self, mock_config, mock_logger, failing_session
    ):
        """Bug hook should log validation."""
        with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAOrchestrator") as mock_orch_cls:
            with patch("swarm_attack.qa.hooks.bug_researcher_hook.QAContextBuilder") as mock_ctx_cls:
                mock_orch = MagicMock()
                mock_orch.test.return_value = failing_session
                mock_orch_cls.return_value = mock_orch

                mock_ctx = MagicMock()
                mock_ctx.build_context.return_value = QAContext(base_url="http://localhost:8000")
                mock_ctx_cls.return_value = mock_ctx

                hook = BugResearcherQAHook(mock_config, mock_logger)
                hook.validate_bug(
                    bug_id="BUG-123",
                    endpoint="/api/users",
                    reproduction_steps=["Step 1"],
                )

                # Should have logged
                log_calls = mock_logger.log.call_args_list
                event_types = [call[0][0] for call in log_calls]
                assert "bug_validation_start" in event_types
                assert "bug_validation_complete" in event_types


# =============================================================================
# RESULT TYPE TESTS
# =============================================================================


class TestResultTypes:
    """Tests for hook result types."""

    def test_verifier_hook_result_defaults(self):
        """VerifierHookResult should have correct defaults."""
        result = VerifierHookResult()

        assert result.session_id is None
        assert result.recommendation == QARecommendation.PASS
        assert result.findings == []
        assert result.created_bugs == []
        assert result.should_block is False
        assert result.should_continue is True
        assert result.has_warnings is False
        assert result.skipped is False
        assert result.error is None

    def test_bug_hook_result_defaults(self):
        """BugHookResult should have correct defaults."""
        result = BugHookResult()

        assert result.bug_id == ""
        assert result.session_id is None
        assert result.is_reproducible is None
        assert result.is_inconclusive is False
        assert result.findings == []
        assert result.evidence == {}
        assert result.root_cause_hints == []
        assert result.error is None
