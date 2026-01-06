"""Unit tests for Semantic Tester hook in Feature Pipeline (TDD).

Tests the integration of SemanticTesterAgent into the feature pipeline
orchestrator.py, running post-implementation and pre-verification.

Test cases:
- Semantic tester is called after verifier passes
- FAIL verdict blocks commit and creates bug
- PARTIAL verdict logs warning but allows commit
- PASS verdict allows commit normally
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass


# =============================================================================
# IMPORT TESTS
# =============================================================================


class TestImports:
    """Tests to verify semantic hook can be imported."""

    def test_can_import_semantic_tester_agent(self):
        """Should be able to import SemanticTesterAgent."""
        from swarm_attack.qa.agents.semantic_tester import SemanticTesterAgent
        assert SemanticTesterAgent is not None

    def test_can_import_semantic_verdict(self):
        """Should be able to import SemanticVerdict enum."""
        from swarm_attack.qa.agents.semantic_tester import SemanticVerdict
        assert SemanticVerdict is not None

    def test_can_import_semantic_hook(self):
        """Should be able to import SemanticTestHook."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        assert SemanticTestHook is not None

    def test_can_import_hook_result(self):
        """Should be able to import SemanticHookResult."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticHookResult
        assert SemanticHookResult is not None


# =============================================================================
# HOOK INITIALIZATION TESTS
# =============================================================================


class TestSemanticHookInit:
    """Tests for SemanticTestHook initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return config

    def test_init_with_config(self, mock_config):
        """Should initialize with SwarmConfig."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        hook = SemanticTestHook(mock_config)
        assert hook.config == mock_config

    def test_init_accepts_logger(self, mock_config):
        """Should accept optional logger."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        logger = MagicMock()
        hook = SemanticTestHook(mock_config, logger=logger)
        assert hook._logger == logger

    def test_init_creates_semantic_tester(self, mock_config):
        """Should create SemanticTesterAgent instance."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        hook = SemanticTestHook(mock_config)
        assert hook.semantic_tester is not None

    def test_init_creates_regression_scheduler(self, mock_config):
        """Should create RegressionScheduler instance."""
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        hook = SemanticTestHook(mock_config)
        assert hook.regression_scheduler is not None


# =============================================================================
# SHOULD RUN TESTS
# =============================================================================


class TestShouldRun:
    """Tests for should_run() method."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    def test_runs_after_verifier_success(self, hook):
        """Should run when verifier passed."""
        result = hook.should_run(
            verifier_passed=True,
            feature_id="my-feature",
            issue_number=42,
        )
        assert result is True

    def test_skips_on_verifier_failure(self, hook):
        """Should skip when verifier failed."""
        result = hook.should_run(
            verifier_passed=False,
            feature_id="my-feature",
            issue_number=42,
        )
        assert result is False

    def test_skips_if_disabled(self, hook):
        """Should skip if semantic testing is disabled."""
        hook.enabled = False
        result = hook.should_run(
            verifier_passed=True,
            feature_id="my-feature",
            issue_number=42,
        )
        assert result is False


# =============================================================================
# RUN TESTS - FAIL VERDICT
# =============================================================================


class TestRunFailVerdict:
    """Tests for run() with FAIL verdict."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    @patch("subprocess.run")
    def test_fail_verdict_blocks_commit(self, mock_subprocess, hook):
        """FAIL verdict should block commit."""
        from swarm_attack.agents.base import AgentResult

        # Mock git diff
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        # Mock semantic tester to return FAIL
        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=False,
            output={
                "verdict": "FAIL",
                "issues": [{"severity": "critical", "description": "Bug found"}],
            },
            errors=["Bug found"],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        assert result.should_block is True
        assert result.verdict == "FAIL"

    @patch("subprocess.run")
    def test_fail_verdict_sets_block_reason(self, mock_subprocess, hook):
        """FAIL verdict should provide block reason."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=False,
            output={
                "verdict": "FAIL",
                "issues": [{"severity": "critical", "description": "Semantic test failed"}],
            },
            errors=["Semantic test failed"],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        assert result.block_reason is not None
        assert "semantic" in result.block_reason.lower() or "fail" in result.block_reason.lower()

    @patch("subprocess.run")
    def test_fail_verdict_creates_bug(self, mock_subprocess, hook, tmp_path):
        """FAIL verdict should create a bug issue."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=False,
            output={
                "verdict": "FAIL",
                "issues": [{"severity": "critical", "description": "Bug found", "location": "file.py:10"}],
            },
            errors=["Bug found"],
        ))

        # Mock the bug creation
        hook.create_bug = Mock(return_value="BUG-123")

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        # Verify bug was created
        hook.create_bug.assert_called_once()
        assert result.created_bug_id is not None


# =============================================================================
# RUN TESTS - PARTIAL VERDICT
# =============================================================================


class TestRunPartialVerdict:
    """Tests for run() with PARTIAL verdict."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    @patch("subprocess.run")
    def test_partial_verdict_allows_commit(self, mock_subprocess, hook):
        """PARTIAL verdict should allow commit."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,  # PARTIAL is considered partial success
            output={
                "verdict": "PARTIAL",
                "issues": [{"severity": "minor", "description": "Minor issue"}],
                "recommendations": ["Consider fixing this"],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        assert result.should_block is False
        assert result.verdict == "PARTIAL"

    @patch("subprocess.run")
    def test_partial_verdict_logs_warning(self, mock_subprocess, hook):
        """PARTIAL verdict should log a warning."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PARTIAL",
                "issues": [{"severity": "minor", "description": "Minor issue"}],
                "recommendations": ["Consider fixing this"],
            },
            errors=[],
        ))

        # Track log calls
        hook._logger = MagicMock()

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        # Verify warning was logged
        warning_calls = [call for call in hook._logger.log.call_args_list
                        if len(call.args) >= 1 and "warning" in str(call).lower()]
        assert len(warning_calls) > 0 or result.warning is not None

    @patch("subprocess.run")
    def test_partial_verdict_includes_recommendations(self, mock_subprocess, hook):
        """PARTIAL verdict should include recommendations."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={
                "verdict": "PARTIAL",
                "issues": [],
                "recommendations": ["Consider adding more tests"],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        assert result.recommendations is not None
        assert len(result.recommendations) > 0


# =============================================================================
# RUN TESTS - PASS VERDICT
# =============================================================================


class TestRunPassVerdict:
    """Tests for run() with PASS verdict."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    @patch("subprocess.run")
    def test_pass_verdict_allows_commit(self, mock_subprocess, hook):
        """PASS verdict should allow commit."""
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
                "evidence": [{"description": "All tests passed", "source": "pytest", "confidence": 0.95}],
                "issues": [],
                "recommendations": [],
            },
            errors=[],
        ))

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        assert result.should_block is False
        assert result.verdict == "PASS"

    @patch("subprocess.run")
    def test_pass_verdict_no_bug_created(self, mock_subprocess, hook):
        """PASS verdict should not create any bug."""
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

        hook.create_bug = Mock()

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        hook.create_bug.assert_not_called()
        assert result.created_bug_id is None

    @patch("subprocess.run")
    def test_pass_verdict_records_commit_for_regression(self, mock_subprocess, hook):
        """PASS verdict should record commit with regression scheduler."""
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

        hook.regression_scheduler.record_issue_committed = Mock(return_value=False)

        result = hook.run(
            feature_id="my-feature",
            issue_number=42,
        )

        hook.regression_scheduler.record_issue_committed.assert_called_once()


# =============================================================================
# CONTEXT BUILDING TESTS
# =============================================================================


class TestContextBuilding:
    """Tests for building semantic test context."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    @patch("subprocess.run")
    def test_gets_staged_diff(self, mock_subprocess, hook):
        """Should get staged diff for testing."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff --git a/file.py b/file.py\n+new code",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []},
            errors=[],
        ))

        hook.run(feature_id="my-feature", issue_number=42)

        # Verify git diff was called
        git_calls = [call for call in mock_subprocess.call_args_list
                    if "git" in str(call) and "diff" in str(call)]
        assert len(git_calls) > 0

    @patch("subprocess.run")
    def test_passes_issue_context(self, mock_subprocess, hook):
        """Should pass issue context to semantic tester."""
        from swarm_attack.agents.base import AgentResult

        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff output",
            stderr="",
        )

        hook.semantic_tester.run = Mock(return_value=AgentResult(
            success=True,
            output={"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []},
            errors=[],
        ))

        hook.run(feature_id="my-feature", issue_number=42)

        # Verify semantic tester was called with context
        call_args = hook.semantic_tester.run.call_args[0][0]
        assert "changes" in call_args
        assert call_args.get("expected_behavior") or call_args.get("test_scope")


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and graceful degradation."""

    @pytest.fixture
    def hook(self, tmp_path):
        from swarm_attack.qa.hooks.semantic_hook import SemanticTestHook
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.swarm_path = str(tmp_path / ".swarm")
        return SemanticTestHook(config)

    @patch("subprocess.run")
    def test_git_diff_failure_allows_commit(self, mock_subprocess, hook):
        """Git diff failure should not block commit (fail open)."""
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="git error",
        )

        result = hook.run(feature_id="my-feature", issue_number=42)

        assert result.should_block is False
        assert result.error is not None

    @patch("subprocess.run")
    def test_semantic_tester_exception_allows_commit(self, mock_subprocess, hook):
        """Semantic tester exception should not block (fail open)."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="diff output",
            stderr="",
        )

        hook.semantic_tester.run = Mock(side_effect=Exception("Unexpected error"))

        result = hook.run(feature_id="my-feature", issue_number=42)

        assert result.should_block is False
        assert result.error is not None

    @patch("subprocess.run")
    def test_timeout_allows_commit(self, mock_subprocess, hook):
        """Timeout should not block commit (fail open)."""
        import subprocess as sp

        mock_subprocess.side_effect = sp.TimeoutExpired(cmd="git diff", timeout=30)

        result = hook.run(feature_id="my-feature", issue_number=42)

        assert result.should_block is False
        assert result.error is not None
