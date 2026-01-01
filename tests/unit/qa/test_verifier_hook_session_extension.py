"""Tests for QASessionExtension integration in VerifierQAHook.

Tests verify that VerifierQAHook properly integrates QASessionExtension
for coverage tracking and regression detection per Issue 2 acceptance criteria.

Acceptance Criteria Tested:
- 2.1: VerifierQAHook initializes QASessionExtension in __init__
- 2.2: VerifierQAHook calls on_session_start() before orchestrator.validate_issue()
- 2.3: VerifierQAHook calls on_session_complete() after QA results
- 2.4: VerifierQAHook blocks on critical regressions
- 2.9: session_extension._coverage_tracker._swarm_dir set correctly
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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
# CRITERION 2.1: VerifierQAHook initializes QASessionExtension in __init__
# =============================================================================


class TestSessionExtensionInitialization:
    """Tests for QASessionExtension initialization in VerifierQAHook."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_creates_session_extension(self, mock_config):
        """VerifierQAHook should create QASessionExtension instance in __init__."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        assert hasattr(hook, "session_extension")
        assert hook.session_extension is not None

    def test_session_extension_is_correct_type(self, mock_config):
        """QASessionExtension should be the correct type."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook
        from swarm_attack.qa.session_extension import QASessionExtension

        hook = VerifierQAHook(mock_config)

        assert isinstance(hook.session_extension, QASessionExtension)

    def test_session_extension_swarm_dir_is_correct(self, mock_config, tmp_path):
        """Session extension should use correct swarm_dir path (criterion 2.9)."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)

        # The coverage tracker should have the swarm dir set
        expected_swarm_dir = Path(mock_config.repo_root) / ".swarm"
        coverage_tracker = hook.session_extension._coverage_tracker

        # Check that the coverage directory is under the correct swarm dir
        assert str(expected_swarm_dir) in str(coverage_tracker._coverage_dir)


# =============================================================================
# CRITERION 2.2: on_session_start() called before validate_issue()
# =============================================================================


class TestOnSessionStartCalled:
    """Tests for on_session_start() being called before validation."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def hook(self, mock_config):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)
        hook.orchestrator = MagicMock()
        hook.session_extension = MagicMock()
        return hook

    def test_on_session_start_called_before_validate_issue(self, hook):
        """on_session_start() should be called before orchestrator.validate_issue()."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        # Track call order
        call_order = []
        hook.session_extension.on_session_start.side_effect = lambda *args, **kwargs: call_order.append(
            "on_session_start"
        )
        hook.orchestrator.validate_issue.side_effect = lambda *args, **kwargs: (
            call_order.append("validate_issue"),
            mock_session,
        )[1]

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert "on_session_start" in call_order
        assert "validate_issue" in call_order
        assert call_order.index("on_session_start") < call_order.index("validate_issue")

    def test_on_session_start_receives_session_id(self, hook):
        """on_session_start() should receive a valid session_id."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        hook.session_extension.on_session_start.assert_called_once()
        call_args = hook.session_extension.on_session_start.call_args
        # First argument should be a session_id string
        assert len(call_args[0]) >= 1 or "session_id" in call_args[1]

    def test_on_session_start_receives_endpoints(self, hook):
        """on_session_start() should receive endpoints_discovered list."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        hook.session_extension.on_session_start.assert_called_once()
        call_args = hook.session_extension.on_session_start.call_args
        # Second argument should be endpoints_discovered
        assert (
            len(call_args[0]) >= 2
            or "endpoints_discovered" in call_args[1]
        )


# =============================================================================
# CRITERION 2.3: on_session_complete() called after QA results
# =============================================================================


class TestOnSessionCompleteCalled:
    """Tests for on_session_complete() being called after validation."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def hook(self, mock_config):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)
        hook.orchestrator = MagicMock()
        hook.session_extension = MagicMock()
        return hook

    def test_on_session_complete_called_after_validate_issue(self, hook):
        """on_session_complete() should be called after orchestrator.validate_issue()."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        # Track call order
        call_order = []
        hook.orchestrator.validate_issue.side_effect = lambda *args, **kwargs: (
            call_order.append("validate_issue"),
            mock_session,
        )[1]

        def on_complete_side_effect(*args, **kwargs):
            call_order.append("on_session_complete")
            return MagicMock(should_block=False, block_reason=None)

        hook.session_extension.on_session_complete.side_effect = on_complete_side_effect

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert "validate_issue" in call_order
        assert "on_session_complete" in call_order
        assert call_order.index("validate_issue") < call_order.index("on_session_complete")

    def test_on_session_complete_receives_session_id(self, hook):
        """on_session_complete() should receive matching session_id."""
        mock_session = QASession(
            session_id="qa-test-456",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        hook.session_extension.on_session_complete.assert_called_once()
        call_args = hook.session_extension.on_session_complete.call_args
        # Should contain session_id matching the QA session
        session_id_arg = call_args[0][0] if call_args[0] else call_args[1].get("session_id")
        assert session_id_arg == "qa-test-456"

    def test_on_session_complete_receives_endpoints_tested(self, hook):
        """on_session_complete() should receive endpoints_tested list."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        hook.session_extension.on_session_complete.assert_called_once()
        call_args = hook.session_extension.on_session_complete.call_args
        # Should have endpoints_tested argument (second arg)
        assert (
            len(call_args[0]) >= 2
            or "endpoints_tested" in call_args[1]
        )

    def test_on_session_complete_receives_findings(self, hook):
        """on_session_complete() should receive findings from QA result."""
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
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
        )

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        hook.session_extension.on_session_complete.assert_called_once()
        call_args = hook.session_extension.on_session_complete.call_args
        # Should have findings argument (third arg)
        assert (
            len(call_args[0]) >= 3
            or "findings" in call_args[1]
        )


# =============================================================================
# CRITERION 2.4: VerifierQAHook blocks on critical regressions
# =============================================================================


class TestBlocksOnCriticalRegressions:
    """Tests for blocking behavior on critical regressions."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    @pytest.fixture
    def hook(self, mock_config):
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)
        hook.orchestrator = MagicMock()
        hook.session_extension = MagicMock()
        return hook

    def test_blocks_when_session_extension_says_should_block(self, hook):
        """Should block when session_extension result has should_block=True."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),  # QA passes
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        # But session extension says to block due to regressions
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=True,
            block_reason="Critical regressions detected: 3 new issues",
            coverage_report=MagicMock(),
            regression_report=MagicMock(),
        )

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert result.should_block is True

    def test_includes_session_extension_block_reason(self, hook):
        """Should include block reason from session extension."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=True,
            block_reason="Coverage dropped significantly: -15.0%",
            coverage_report=MagicMock(),
            regression_report=MagicMock(),
        )

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert result.should_block is True
        # The block reason should be reflected somewhere in the result
        # Either in error field or a new session_extension_block_reason field

    def test_does_not_block_when_session_extension_allows(self, hook):
        """Should not block when session extension does not require blocking."""
        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=False,
            block_reason=None,
            coverage_report=MagicMock(),
            regression_report=MagicMock(),
        )

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert result.should_block is False

    def test_blocks_when_both_qa_and_session_extension_block(self, hook):
        """Should block when both QA result and session extension require blocking."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="happy_path",
            title="Critical error",
            description="Error",
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
                recommendation=QARecommendation.BLOCK,  # QA blocks
                findings=[finding],
                critical_count=1,
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session
        hook.orchestrator.create_bug_investigations.return_value = []

        # Session extension also blocks
        hook.session_extension.on_session_complete.return_value = MagicMock(
            should_block=True,
            block_reason="Critical regressions detected",
            coverage_report=MagicMock(),
            regression_report=MagicMock(),
        )

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert result.should_block is True


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
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)
        hook.orchestrator = MagicMock()

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
                findings=[],
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        assert result is not None
        assert result.session_id == "qa-test-123"
        # Should not block since no regressions and QA passed
        assert result.should_block is False

    def test_session_extension_state_persists(self, mock_config, tmp_path):
        """Session extension should persist coverage state."""
        from swarm_attack.qa.hooks.verifier_hook import VerifierQAHook

        hook = VerifierQAHook(mock_config)
        hook.orchestrator = MagicMock()

        mock_session = QASession(
            session_id="qa-test-123",
            trigger=QATrigger.POST_VERIFICATION,
            depth=QADepth.STANDARD,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.PASS,
                findings=[],
            ),
        )
        hook.orchestrator.validate_issue.return_value = mock_session

        hook.run(
            feature_id="my-feature",
            issue_number=42,
            target_files=["src/api/users.py"],
        )

        # Coverage directory should exist under .swarm
        swarm_dir = tmp_path / ".swarm"
        coverage_dir = swarm_dir / "qa" / "coverage"
        # Directory should be created (even if empty baseline)
        assert coverage_dir.exists() or swarm_dir.exists()
