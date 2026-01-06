"""Unit tests for SemanticTestHook.run() context parameter (BUG-003).

Tests that the run() method accepts a context parameter for testing arbitrary
changes without needing staged git changes.

TDD Test Case:
- RED: run() should accept context parameter with changes and expected_behavior
- GREEN: Implement context parameter support
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


class TestRunWithContextParameter:
    """Tests for run() with context parameter (BUG-003)."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    def test_run_accepts_context_parameter(self, hook):
        """run() should accept a context parameter."""
        from swarm_attack.agents.base import AgentResult

        # Mock semantic tester to return PASS
        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        # Should NOT raise TypeError about unexpected keyword argument context
        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            context={
                "changes": "diff --git a/file.py",
                "expected_behavior": "Code should work correctly",
            },
        )

        assert result is not None
        assert result.verdict == "PASS"

    @patch("subprocess.run")
    def test_context_bypasses_git_diff(self, mock_subprocess, hook):
        """When context is provided, git diff should NOT be called."""
        from swarm_attack.agents.base import AgentResult

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            context={
                "changes": "diff --git a/file.py",
                "expected_behavior": "Code should work correctly",
            },
        )

        # git diff should NOT be called when context is provided
        mock_subprocess.assert_not_called()
        assert result.verdict == "PASS"

    def test_context_changes_passed_to_semantic_tester(self, hook):
        """Context changes should be passed to semantic tester."""
        from swarm_attack.agents.base import AgentResult

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        custom_changes = "diff --git a/custom.py"
        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            context={
                "changes": custom_changes,
                "expected_behavior": "Custom behavior",
            },
        )

        # Verify the changes from context were passed to semantic tester
        call_args = hook.semantic_tester.run.call_args[0][0]
        assert call_args["changes"] == custom_changes

    def test_context_expected_behavior_passed_to_semantic_tester(self, hook):
        """Context expected_behavior should be passed to semantic tester."""
        from swarm_attack.agents.base import AgentResult

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        custom_behavior = "The function should return a list of items"
        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            context={
                "changes": "diff --git a/file.py",
                "expected_behavior": custom_behavior,
            },
        )

        # Verify the expected_behavior from context was passed to semantic tester
        call_args = hook.semantic_tester.run.call_args[0][0]
        assert call_args["expected_behavior"] == custom_behavior

    def test_context_scope_passed_to_semantic_tester(self, hook):
        """Context scope should be passed to semantic tester."""
        from swarm_attack.agents.base import AgentResult
        from swarm_attack.qa.agents.semantic_tester import SemanticScope

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            context={
                "changes": "diff --git a/file.py",
                "expected_behavior": "Custom behavior",
                "scope": SemanticScope.AFFECTED.value,
            },
        )

        # Verify the scope from context was passed to semantic tester
        call_args = hook.semantic_tester.run.call_args[0][0]
        assert call_args["test_scope"] == SemanticScope.AFFECTED.value

    def test_context_defaults_scope_if_not_provided(self, hook):
        """Context without scope should use default CHANGES_ONLY scope."""
        from swarm_attack.agents.base import AgentResult
        from swarm_attack.qa.agents.semantic_tester import SemanticScope

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
            context={
                "changes": "diff --git a/file.py",
                "expected_behavior": "Custom behavior",
            },
        )

        # Should use default CHANGES_ONLY scope
        call_args = hook.semantic_tester.run.call_args[0][0]
        assert call_args["test_scope"] == SemanticScope.CHANGES_ONLY.value

    @patch("subprocess.run")
    def test_no_context_still_uses_git_diff(self, mock_subprocess, hook):
        """Without context, run() should still use git diff as before."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PASS",
                "evidence": [],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        # git diff should be called when no context is provided
        git_calls = [call for call in mock_subprocess.call_args_list
                    if "git" in str(call) and "diff" in str(call)]
        assert len(git_calls) > 0
