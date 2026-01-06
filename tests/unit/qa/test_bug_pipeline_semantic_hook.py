"""Unit tests for SemanticTesterAgent hook in BugOrchestrator.fix() (TDD).

These tests verify that the SemanticTesterAgent is integrated into the
bug fix pipeline, running semantic validation before pytest verification.

Test scenarios:
- Semantic tester is called before pytest verification in fix()
- FAIL verdict sends bug back to ANALYZING phase
- PASS/PARTIAL verdict continues to pytest verification
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from pathlib import Path

from swarm_attack.bug_models import (
    BugPhase,
    BugState,
    BugReport,
    RootCauseAnalysis,
    FixPlan,
    FileChange,
    ApprovalRecord,
)
from swarm_attack.bug_orchestrator import BugOrchestrator
from swarm_attack.agents.base import AgentResult


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.bug_bash = MagicMock()
    config.bug_bash.debate = MagicMock()
    config.bug_bash.debate.enabled = False
    return config


@pytest.fixture
def mock_state_store(tmp_path):
    """Create a mock state store."""
    store = MagicMock()
    store.base_path = tmp_path / ".swarm" / "bugs"
    return store


@pytest.fixture
def approved_bug_state():
    """Create an approved bug state ready for fix."""
    state = BugState.create(
        bug_id="bug-test-semantic-001",
        description="Test bug for semantic validation",
        test_path="tests/test_something.py",
    )
    state.phase = BugPhase.APPROVED
    state.root_cause = RootCauseAnalysis(
        summary="Missing validation in function X",
        execution_trace="trace",
        root_cause_file="src/module.py",
        root_cause_line=42,
        root_cause_code="def buggy_func():",
        root_cause_explanation="Missing check",
        why_not_caught="No tests covered this case",
        confidence=0.85,
    )
    state.fix_plan = FixPlan(
        summary="Add validation check",
        changes=[
            FileChange(
                file_path="src/module.py",
                change_type="modify",
                current_code="def buggy_func():",
                proposed_code="def buggy_func():\n    validate()",
                explanation="Add validation",
            )
        ],
        test_cases=[],
        risk_level="low",
        risk_explanation="Simple change",
    )
    state.approval_record = ApprovalRecord.create(
        approved_by="test_user",
        fix_plan=state.fix_plan,
    )
    return state


@pytest.fixture
def orchestrator(mock_config, mock_state_store):
    """Create a BugOrchestrator with mocked dependencies."""
    return BugOrchestrator(
        config=mock_config,
        logger=None,
        state_store=mock_state_store,
    )


# =============================================================================
# TEST: Semantic Tester Integration in fix() Method
# =============================================================================


class TestSemanticTesterCalledBeforePytest:
    """Tests that semantic tester is called before pytest in fix()."""

    def test_semantic_tester_called_during_fix(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Semantic tester should be called before pytest verification."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        # Track call order
        call_order = []

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                def track_subprocess(*args, **kwargs):
                    call_order.append("subprocess")
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
                    return result

                mock_subprocess.side_effect = track_subprocess
                mock_agent.run.side_effect = lambda ctx: (
                    call_order.append("semantic_tester"),
                    AgentResult(
                        success=True,
                        output={"verdict": "PASS"},
                        errors=[],
                        cost_usd=0.0,
                    ),
                )[1]

                orchestrator.fix("bug-test-semantic-001")

                # Verify semantic tester was called
                MockSemanticTester.assert_called_once()
                mock_agent.run.assert_called_once()

                # Verify call order: semantic_tester before subprocess (pytest)
                assert call_order == ["semantic_tester", "subprocess"], \
                    f"Expected semantic_tester before subprocess, got: {call_order}"

    def test_semantic_tester_receives_correct_context(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Semantic tester should receive fix context with bug info."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PASS"},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = MagicMock(
                    returncode=0, stdout="", stderr=""
                )

                orchestrator.fix("bug-test-semantic-001")

                # Verify context passed to semantic tester
                call_args = mock_agent.run.call_args
                context = call_args[0][0] if call_args[0] else call_args.kwargs.get("context", {})

                # Context should include changes and expected behavior
                assert "changes" in context
                assert "expected_behavior" in context
                assert "test_scope" in context


# =============================================================================
# TEST: FAIL Verdict Handling
# =============================================================================


class TestSemanticFailVerdictHandling:
    """Tests for handling FAIL verdict from semantic tester."""

    def test_fail_verdict_transitions_to_analyzing(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """FAIL verdict should transition bug back to ANALYZING phase."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=False,
                output={"verdict": "FAIL", "issues": [{"description": "Test failed"}]},
                errors=["Semantic validation failed"],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            result = orchestrator.fix("bug-test-semantic-001")

            # Verify bug transitioned to ANALYZING (or BLOCKED for re-planning)
            assert result.success is False
            # The bug should be blocked or in analyzing state
            assert result.phase in (BugPhase.ANALYZING, BugPhase.BLOCKED)

    def test_fail_verdict_includes_semantic_feedback(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """FAIL verdict error should include semantic tester feedback."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=False,
                output={"verdict": "FAIL"},
                errors=["Fix does not address root cause"],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            result = orchestrator.fix("bug-test-semantic-001")

            assert result.success is False
            assert result.error is not None
            assert "semantic" in result.error.lower() or "Fix does not address" in result.error

    def test_fail_verdict_skips_pytest(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """FAIL verdict should skip pytest verification entirely."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=False,
                output={"verdict": "FAIL"},
                errors=["Semantic validation failed"],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                orchestrator.fix("bug-test-semantic-001")

                # Pytest should NOT be called when semantic test fails
                mock_subprocess.assert_not_called()


# =============================================================================
# TEST: PASS/PARTIAL Verdict Handling
# =============================================================================


class TestSemanticPassPartialVerdictHandling:
    """Tests for handling PASS/PARTIAL verdicts from semantic tester."""

    def test_pass_verdict_continues_to_pytest(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """PASS verdict should continue to pytest verification."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PASS"},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = MagicMock(
                    returncode=0, stdout="", stderr=""
                )

                result = orchestrator.fix("bug-test-semantic-001")

                # Pytest should be called after semantic pass
                mock_subprocess.assert_called()

    def test_partial_verdict_continues_to_pytest(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """PARTIAL verdict should continue to pytest verification."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PARTIAL", "recommendations": ["Consider edge cases"]},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = MagicMock(
                    returncode=0, stdout="", stderr=""
                )

                result = orchestrator.fix("bug-test-semantic-001")

                # Pytest should be called after semantic partial pass
                mock_subprocess.assert_called()

    def test_pass_and_pytest_success_leads_to_fixed(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """PASS verdict + pytest success should result in FIXED phase."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PASS"},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = MagicMock(
                    returncode=0, stdout="Tests passed", stderr=""
                )

                result = orchestrator.fix("bug-test-semantic-001")

                assert result.success is True
                assert result.phase == BugPhase.FIXED


# =============================================================================
# TEST: Edge Cases
# =============================================================================


class TestSemanticTesterEdgeCases:
    """Edge case tests for semantic tester integration."""

    def test_semantic_tester_exception_is_handled(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Exception from semantic tester should be handled gracefully."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.side_effect = Exception("Semantic tester crashed")
            MockSemanticTester.return_value = mock_agent

            result = orchestrator.fix("bug-test-semantic-001")

            # Should handle exception and return blocked/error
            assert result.success is False
            assert result.phase == BugPhase.BLOCKED
            assert "error" in result.error.lower() or "semantic" in result.error.lower()

    def test_semantic_tester_timeout_is_handled(
        self, orchestrator, approved_bug_state, mock_state_store
    ):
        """Timeout from semantic tester should be handled gracefully."""
        mock_state_store.load.return_value = approved_bug_state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=False,
                output={"verdict": "FAIL", "issues": [{"description": "Timeout"}]},
                errors=["Test timed out"],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            result = orchestrator.fix("bug-test-semantic-001")

            assert result.success is False

    def test_semantic_tester_with_no_test_path(
        self, orchestrator, mock_state_store, mock_config
    ):
        """Bug without test_path should still run semantic tester."""
        state = BugState.create(
            bug_id="bug-no-test-path",
            description="Bug without test path",
            test_path=None,  # No test path
        )
        state.phase = BugPhase.APPROVED
        state.root_cause = RootCauseAnalysis(
            summary="Issue found",
            execution_trace="trace",
            root_cause_file="src/file.py",
            root_cause_line=10,
            root_cause_code="code",
            root_cause_explanation="explanation",
            why_not_caught="reason",
            confidence=0.8,
        )
        state.fix_plan = FixPlan(
            summary="Fix it",
            changes=[],
            test_cases=[],
            risk_level="low",
        )
        state.approval_record = ApprovalRecord.create(
            approved_by="user",
            fix_plan=state.fix_plan,
        )

        mock_state_store.load.return_value = state
        mock_state_store.exists.return_value = True

        with patch(
            "swarm_attack.bug_orchestrator.SemanticTesterAgent"
        ) as MockSemanticTester:
            mock_agent = MagicMock()
            mock_agent.run.return_value = AgentResult(
                success=True,
                output={"verdict": "PASS"},
                errors=[],
                cost_usd=0.0,
            )
            MockSemanticTester.return_value = mock_agent

            result = orchestrator.fix("bug-no-test-path")

            # Semantic tester should still be called
            MockSemanticTester.assert_called_once()
            mock_agent.run.assert_called_once()
