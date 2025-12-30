"""Tests for orchestrator critic retry logic.

This test suite verifies that the orchestrator retries critic failures
up to MAX_CRITIC_RETRIES before blocking the feature.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from pathlib import Path

from swarm_attack.orchestrator import Orchestrator
from swarm_attack.models import FeaturePhase


class TestCriticRetryLogic:
    """Test that critic failures trigger retries before blocking."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create an orchestrator with mocked dependencies."""
        mock_config = MagicMock()
        mock_config.repo_root = Path("/tmp")
        mock_config.specs_path = MagicMock()
        mock_config.specs_path.__truediv__ = MagicMock(return_value=Path("/tmp/specs"))
        mock_config.swarm_path = Path("/tmp/.swarm")
        mock_config.state_path = Path("/tmp/.swarm/state")
        mock_config.sessions_path = Path("/tmp/.swarm/sessions")
        mock_config.spec_debate = MagicMock()
        mock_config.spec_debate.max_rounds = 5
        mock_config.spec_debate.timeout_seconds = 900
        mock_config.spec_debate.rubric_thresholds = {
            "clarity": 0.8,
            "coverage": 0.8,
            "architecture": 0.8,
            "risk": 0.7,
        }

        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.config = mock_config
        orchestrator.logger = None
        orchestrator._state_store = None
        orchestrator._progress_callback = None
        orchestrator._session_manager = None
        orchestrator._github_client = None
        orchestrator._log = MagicMock()
        orchestrator._emit_progress = MagicMock()
        orchestrator._update_phase = MagicMock()
        orchestrator._build_rejection_context_for_critic = MagicMock(return_value="")
        orchestrator._save_scores = MagicMock()
        orchestrator._save_critic_feedback = MagicMock()
        orchestrator._check_approval_threshold = MagicMock(return_value=False)

        # Mock file system operations
        orchestrator._get_spec_path = MagicMock(return_value=Path("/tmp/specs/test-feature/spec-draft.md"))

        return orchestrator

    @pytest.fixture
    def mock_author(self):
        """Mock spec author agent."""
        mock = MagicMock()
        mock.run.return_value = MagicMock(
            success=True,
            output={},
            cost_usd=0.5,
            errors=[]
        )
        mock.reset = MagicMock()
        return mock

    @pytest.fixture
    def mock_moderator(self):
        """Mock spec moderator agent."""
        mock = MagicMock()
        mock.run.return_value = MagicMock(
            success=True,
            output={},
            cost_usd=0.5,
            errors=[]
        )
        mock.reset = MagicMock()
        return mock

    def test_critic_retries_on_failure(self, mock_orchestrator, mock_author, mock_moderator):
        """Critic should retry up to MAX_CRITIC_RETRIES before failing."""
        # Mock critic that fails twice then succeeds
        mock_critic = MagicMock()
        fail_result = MagicMock(
            success=False,
            errors=["Codex error: rate limit"],
            cost_usd=0.1,
            output={}
        )
        success_result = MagicMock(
            success=True,
            output={
                "scores": {
                    "clarity": 0.9,
                    "coverage": 0.9,
                    "architecture": 0.9,
                    "risk": 0.9
                },
                "issues": [],
                "recommendation": "approve",
                "issue_counts": {"critical": 0, "major": 0, "minor": 0}
            },
            cost_usd=0.1,
            errors=[]
        )
        mock_critic.run.side_effect = [fail_result, fail_result, success_result]
        mock_critic.reset = MagicMock()

        mock_orchestrator._critic = mock_critic
        mock_orchestrator._author = mock_author
        mock_orchestrator._moderator = mock_moderator

        # Run the pipeline
        result = mock_orchestrator.run_spec_pipeline("test-feature")

        # Verify critic was called 3 times (2 failures + 1 success)
        assert mock_critic.run.call_count == 3

        # Verify retry was logged
        retry_logs = [
            call_args for call_args in mock_orchestrator._log.call_args_list
            if call_args[0][0] == "critic_retry"
        ]
        assert len(retry_logs) == 2  # Two retry attempts logged

        # Verify feature was not blocked (because it eventually succeeded)
        block_calls = [
            call_args for call_args in mock_orchestrator._update_phase.call_args_list
            if call_args[0][1] == FeaturePhase.BLOCKED
        ]
        assert len(block_calls) == 0

    def test_critic_blocks_after_max_retries(self, mock_orchestrator, mock_author, mock_moderator):
        """Critic should block feature after MAX_CRITIC_RETRIES exhausted."""
        # Mock critic that always fails
        mock_critic = MagicMock()
        fail_result = MagicMock(
            success=False,
            errors=["Codex error: persistent failure"],
            cost_usd=0.1,
            output={}
        )
        mock_critic.run.return_value = fail_result
        mock_critic.reset = MagicMock()

        mock_orchestrator._critic = mock_critic
        mock_orchestrator._author = mock_author
        mock_orchestrator._moderator = mock_moderator

        # Run the pipeline
        result = mock_orchestrator.run_spec_pipeline("test-feature")

        # Verify critic was called MAX_CRITIC_RETRIES + 1 times (3 total: initial + 2 retries)
        assert mock_critic.run.call_count == 3

        # Verify feature was blocked
        mock_orchestrator._update_phase.assert_called_with("test-feature", FeaturePhase.BLOCKED)

        # Verify result indicates failure
        assert result.status == "failure"
        assert "failed after 3 attempts" in result.error.lower()

    def test_critic_no_retry_on_success(self, mock_orchestrator, mock_author, mock_moderator):
        """Critic should not retry if first attempt succeeds."""
        mock_critic = MagicMock()
        success_result = MagicMock(
            success=True,
            output={
                "scores": {
                    "clarity": 0.9,
                    "coverage": 0.9,
                    "architecture": 0.9,
                    "risk": 0.9
                },
                "issues": [],
                "recommendation": "approve",
                "issue_counts": {"critical": 0, "major": 0, "minor": 0}
            },
            cost_usd=0.1,
            errors=[]
        )
        mock_critic.run.return_value = success_result
        mock_critic.reset = MagicMock()

        mock_orchestrator._critic = mock_critic
        mock_orchestrator._author = mock_author
        mock_moderator.reset = MagicMock()
        mock_orchestrator._moderator = mock_moderator

        # Run the pipeline
        result = mock_orchestrator.run_spec_pipeline("test-feature")

        # Verify critic was called only once
        assert mock_critic.run.call_count == 1

        # Verify no retry logs
        retry_logs = [
            call_args for call_args in mock_orchestrator._log.call_args_list
            if call_args[0][0] == "critic_retry"
        ]
        assert len(retry_logs) == 0

    def test_critic_retry_logs_attempts(self, mock_orchestrator, mock_author, mock_moderator):
        """Each retry attempt should be logged with proper context."""
        mock_critic = MagicMock()
        fail_result = MagicMock(
            success=False,
            errors=["Codex error"],
            cost_usd=0.1,
            output={}
        )
        success_result = MagicMock(
            success=True,
            output={
                "scores": {
                    "clarity": 0.9,
                    "coverage": 0.9,
                    "architecture": 0.9,
                    "risk": 0.9
                },
                "issues": [],
                "recommendation": "approve",
                "issue_counts": {"critical": 0, "major": 0, "minor": 0}
            },
            cost_usd=0.1,
            errors=[]
        )
        mock_critic.run.side_effect = [fail_result, success_result]
        mock_critic.reset = MagicMock()

        mock_orchestrator._critic = mock_critic
        mock_orchestrator._author = mock_author
        mock_orchestrator._moderator = mock_moderator

        # Run the pipeline
        result = mock_orchestrator.run_spec_pipeline("test-feature")

        # Find retry log calls
        retry_logs = [
            call_args for call_args in mock_orchestrator._log.call_args_list
            if call_args[0][0] == "critic_retry"
        ]

        # Verify retry log was called once
        assert len(retry_logs) == 1

        # Verify log contains proper context
        log_data = retry_logs[0][0][1]
        assert log_data["feature_id"] == "test-feature"
        assert log_data["attempt"] == 1
        assert log_data["max_retries"] == 2
        assert "error" in log_data

    def test_critic_cost_accumulates_across_retries(self, mock_orchestrator, mock_author, mock_moderator):
        """Cost should accumulate across all retry attempts."""
        mock_critic = MagicMock()
        fail_result = MagicMock(
            success=False,
            errors=["Codex error"],
            cost_usd=0.1,
            output={}
        )
        success_result = MagicMock(
            success=True,
            output={
                "scores": {
                    "clarity": 0.9,
                    "coverage": 0.9,
                    "architecture": 0.9,
                    "risk": 0.9
                },
                "issues": [],
                "recommendation": "approve",
                "issue_counts": {"critical": 0, "major": 0, "minor": 0}
            },
            cost_usd=0.1,
            errors=[]
        )
        mock_critic.run.side_effect = [fail_result, fail_result, success_result]
        mock_critic.reset = MagicMock()

        mock_orchestrator._critic = mock_critic
        mock_orchestrator._author = mock_author
        mock_moderator.cost_usd = 0.5
        mock_orchestrator._moderator = mock_moderator

        # Run the pipeline
        result = mock_orchestrator.run_spec_pipeline("test-feature")

        # Verify cost includes all three critic attempts (0.1 each = 0.3 total from critic)
        # Note: actual total will include author/moderator costs too
        assert result.total_cost_usd >= 0.3


class TestDebateOnlyCriticRetry:
    """Test critic retry logic in debate-only mode."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create an orchestrator with mocked dependencies."""
        mock_config = MagicMock()
        mock_config.repo_root = Path("/tmp")
        mock_config.specs_path = MagicMock()
        mock_config.specs_path.__truediv__ = MagicMock(return_value=Path("/tmp/specs"))
        mock_config.swarm_path = Path("/tmp/.swarm")
        mock_config.state_path = Path("/tmp/.swarm/state")
        mock_config.sessions_path = Path("/tmp/.swarm/sessions")
        mock_config.spec_debate = MagicMock()
        mock_config.spec_debate.max_rounds = 5
        mock_config.spec_debate.timeout_seconds = 900
        mock_config.spec_debate.rubric_thresholds = {
            "clarity": 0.8,
            "coverage": 0.8,
            "architecture": 0.8,
            "risk": 0.7,
        }

        orchestrator = Orchestrator.__new__(Orchestrator)
        orchestrator.config = mock_config
        orchestrator.logger = None
        orchestrator._state_store = None
        orchestrator._progress_callback = None
        orchestrator._session_manager = None
        orchestrator._github_client = None
        orchestrator._log = MagicMock()
        orchestrator._emit_progress = MagicMock()
        orchestrator._update_phase = MagicMock()
        orchestrator._build_rejection_context_for_critic = MagicMock(return_value="")
        orchestrator._save_scores = MagicMock()
        orchestrator._save_critic_feedback = MagicMock()
        orchestrator._check_approval_threshold = MagicMock(return_value=False)

        # Mock file system operations
        orchestrator._get_spec_path = MagicMock(return_value=Path("/tmp/specs/test-feature/spec-draft.md"))

        return orchestrator

    @pytest.fixture
    def mock_moderator(self):
        """Mock spec moderator agent."""
        mock = MagicMock()
        mock.run.return_value = MagicMock(
            success=True,
            output={},
            cost_usd=0.5,
            errors=[]
        )
        mock.reset = MagicMock()
        return mock

    def test_debate_only_critic_retries(self, mock_orchestrator, mock_moderator):
        """Critic should retry in debate-only mode too."""
        mock_critic = MagicMock()
        fail_result = MagicMock(
            success=False,
            errors=["Codex error"],
            cost_usd=0.1,
            output={}
        )
        success_result = MagicMock(
            success=True,
            output={
                "scores": {
                    "clarity": 0.9,
                    "coverage": 0.9,
                    "architecture": 0.9,
                    "risk": 0.9
                },
                "issues": [],
                "recommendation": "approve",
                "issue_counts": {"critical": 0, "major": 0, "minor": 0}
            },
            cost_usd=0.1,
            errors=[]
        )
        mock_critic.run.side_effect = [fail_result, success_result]
        mock_critic.reset = MagicMock()

        mock_orchestrator._critic = mock_critic
        mock_orchestrator._moderator = mock_moderator

        # Mock spec path to exist
        with patch.object(Path, 'exists', return_value=True):
            # Run debate-only pipeline
            result = mock_orchestrator.run_spec_debate_only("test-feature")

        # Verify critic was retried
        assert mock_critic.run.call_count == 2

        # Verify retry was logged
        retry_logs = [
            call_args for call_args in mock_orchestrator._log.call_args_list
            if call_args[0][0] == "critic_retry"
        ]
        assert len(retry_logs) == 1
