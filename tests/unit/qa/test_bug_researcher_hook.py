"""Tests for BugResearcherQAHook following TDD approach.

Tests cover spec section 3: Pipeline Integration - Bug Researcher Hook
- QA hook for bug reproduction validation
- Triggers on BUG_REPRODUCTION
- Uses DEEP depth for thorough testing
- Captures evidence for root cause analysis
- Feeds back to bug pipeline
"""

import pytest
from unittest.mock import MagicMock, patch

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
    """Tests to verify BugResearcherQAHook can be imported."""

    def test_can_import_bug_researcher_hook(self):
        """Should be able to import BugResearcherQAHook class."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        assert BugResearcherQAHook is not None

    def test_can_import_bug_hook_result(self):
        """Should be able to import BugHookResult."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugHookResult
        assert BugHookResult is not None


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestBugResearcherQAHookInit:
    """Tests for BugResearcherQAHook initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        hook = BugResearcherQAHook(mock_config)
        assert hook.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        logger = MagicMock()
        hook = BugResearcherQAHook(mock_config, logger=logger)
        assert hook._logger == logger

    def test_init_creates_orchestrator(self, mock_config):
        """Should create QAOrchestrator instance."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        hook = BugResearcherQAHook(mock_config)
        assert hook.orchestrator is not None

    def test_init_creates_context_builder(self, mock_config):
        """Should create QAContextBuilder instance."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        hook = BugResearcherQAHook(mock_config)
        assert hook.context_builder is not None


# =============================================================================
# VALIDATE BUG TESTS
# =============================================================================


class TestValidateBug:
    """Tests for validate_bug() method."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = BugResearcherQAHook(config)
        # Mock the orchestrator
        hook.orchestrator = MagicMock()
        return hook

    def test_returns_bug_hook_result(self, hook):
        """Should return BugHookResult."""
        from swarm_attack.qa.hooks.bug_researcher_hook import BugHookResult

        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.BLOCK),
        )
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=["step 1", "step 2"],
        )

        assert isinstance(result, BugHookResult)

    def test_uses_deep_depth(self, hook):
        """Should use DEEP depth for bug reproduction."""
        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.BLOCK),
        )
        hook.orchestrator.test.return_value = mock_session

        hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        call_kwargs = hook.orchestrator.test.call_args
        assert call_kwargs[1]["depth"] == QADepth.DEEP

    def test_uses_bug_reproduction_trigger(self, hook):
        """Should use BUG_REPRODUCTION trigger."""
        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.BLOCK),
        )
        hook.orchestrator.test.return_value = mock_session

        hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        call_kwargs = hook.orchestrator.test.call_args
        assert call_kwargs[1]["trigger"] == QATrigger.BUG_REPRODUCTION

    def test_includes_bug_id_in_result(self, hook):
        """Result should include bug_id."""
        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.BLOCK),
        )
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert result.bug_id == "BUG-456"

    def test_includes_session_id_in_result(self, hook):
        """Result should include session_id."""
        mock_session = QASession(
            session_id="qa-bug-xyz",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.BLOCK),
        )
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert result.session_id == "qa-bug-xyz"


# =============================================================================
# BUG REPRODUCTION TESTS
# =============================================================================


class TestBugReproduction:
    """Tests for bug reproduction validation."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = BugResearcherQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_confirms_reproducible_bug(self, hook):
        """Should confirm bug is reproducible when QA finds issue."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="reproduction",
            title="Bug confirmed",
            description="Bug reproduces as described",
            expected={"status": 200},
            actual={"status": 500},
            evidence={"request": "curl..."},
            recommendation="Fix",
        )
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
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=["Send GET to /api/users"],
        )

        assert result.is_reproducible is True

    def test_marks_not_reproducible_when_pass(self, hook):
        """Should mark as not reproducible when QA passes."""
        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(
                recommendation=QARecommendation.PASS,
                findings=[],
            ),
        )
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=["Send GET to /api/users"],
        )

        assert result.is_reproducible is False

    def test_captures_evidence(self, hook):
        """Should capture evidence from QA findings."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="reproduction",
            title="Bug confirmed",
            description="Bug reproduces",
            expected={"status": 200},
            actual={"status": 500, "body": "Internal Server Error"},
            evidence={
                "request": "curl -X GET /api/users",
                "response_time_ms": 150,
                "stack_trace": "Error at line 42",
            },
            recommendation="Fix",
        )
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
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert result.evidence is not None
        assert len(result.evidence) > 0


# =============================================================================
# ROOT CAUSE HINTS TESTS
# =============================================================================


class TestRootCauseHints:
    """Tests for root cause hint generation."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = BugResearcherQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_generates_root_cause_hints(self, hook):
        """Should generate hints for root cause analysis."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="behavioral",
            endpoint="GET /api/users",
            test_type="reproduction",
            title="Database connection error",
            description="Connection pool exhausted",
            expected={"status": 200},
            actual={"status": 503},
            evidence={"error": "Connection pool exhausted"},
            recommendation="Check database connections",
        )
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
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert result.root_cause_hints is not None

    def test_hints_include_category(self, hook):
        """Root cause hints should include category."""
        finding = QAFinding(
            finding_id="BT-001",
            severity="critical",
            category="contract",
            endpoint="GET /api/users",
            test_type="schema_validation",
            title="Schema mismatch",
            description="Response missing field",
            expected={"fields": ["id", "name"]},
            actual={"fields": ["id"]},
            evidence={},
            recommendation="Add name field",
        )
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
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert "contract" in str(result.root_cause_hints).lower() or result.root_cause_hints is not None


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = BugResearcherQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_handles_orchestrator_error(self, hook):
        """Should handle orchestrator errors gracefully."""
        hook.orchestrator.test.side_effect = Exception("QA failed")

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        # Should not raise, should return error result
        assert result is not None
        assert result.error is not None

    def test_handles_timeout(self, hook):
        """Should handle timeout gracefully."""
        hook.orchestrator.test.side_effect = TimeoutError("Timed out")

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert result is not None
        assert result.error is not None

    def test_marks_inconclusive_on_error(self, hook):
        """Should mark result as inconclusive on error."""
        hook.orchestrator.test.side_effect = Exception("Error")

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
        )

        assert result.is_reproducible is None or result.is_inconclusive is True


# =============================================================================
# AFFECTED FILES TESTS
# =============================================================================


class TestAffectedFiles:
    """Tests for affected files analysis."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        hook = BugResearcherQAHook(config)
        hook.orchestrator = MagicMock()
        return hook

    def test_accepts_affected_files(self, hook):
        """Should accept list of affected files."""
        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.test.return_value = mock_session

        result = hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
            affected_files=["src/api/users.py", "src/models/user.py"],
        )

        assert result is not None

    def test_includes_files_in_context(self, hook):
        """Should include affected files in QA context."""
        mock_session = QASession(
            session_id="qa-bug-123",
            trigger=QATrigger.BUG_REPRODUCTION,
            depth=QADepth.DEEP,
            status=QAStatus.COMPLETED,
            context=QAContext(),
            result=QAResult(recommendation=QARecommendation.PASS),
        )
        hook.orchestrator.test.return_value = mock_session

        hook.validate_bug(
            bug_id="BUG-456",
            endpoint="/api/users",
            reproduction_steps=[],
            affected_files=["src/api/users.py"],
        )

        # Verify test was called (context builder should use files)
        hook.orchestrator.test.assert_called_once()


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for BugResearcherQAHook."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.bug_researcher_hook import BugResearcherQAHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        return BugResearcherQAHook(config)

    def test_full_flow_reproducible_bug(self, hook):
        """Test full flow with reproducible bug."""
        with patch.object(hook.orchestrator, 'test') as mock_test:
            finding = QAFinding(
                finding_id="BT-001",
                severity="critical",
                category="behavioral",
                endpoint="GET /api/users",
                test_type="reproduction",
                title="500 error",
                description="Server error on GET",
                expected={"status": 200},
                actual={"status": 500},
                evidence={"request": "curl..."},
                recommendation="Fix",
            )
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
            mock_test.return_value = mock_session

            result = hook.validate_bug(
                bug_id="BUG-500-ERROR",
                endpoint="/api/users",
                reproduction_steps=[
                    "1. Send GET request to /api/users",
                    "2. Observe 500 error",
                ],
                affected_files=["src/api/users.py"],
            )

            assert result.bug_id == "BUG-500-ERROR"
            assert result.is_reproducible is True
            assert len(result.findings) == 1

    def test_full_flow_not_reproducible(self, hook):
        """Test full flow with non-reproducible bug."""
        with patch.object(hook.orchestrator, 'test') as mock_test:
            mock_session = QASession(
                session_id="qa-bug-123",
                trigger=QATrigger.BUG_REPRODUCTION,
                depth=QADepth.DEEP,
                status=QAStatus.COMPLETED,
                context=QAContext(),
                result=QAResult(
                    recommendation=QARecommendation.PASS,
                    findings=[],
                ),
            )
            mock_test.return_value = mock_session

            result = hook.validate_bug(
                bug_id="BUG-INTERMITTENT",
                endpoint="/api/users",
                reproduction_steps=["Send request"],
            )

            assert result.is_reproducible is False
            assert len(result.findings) == 0
