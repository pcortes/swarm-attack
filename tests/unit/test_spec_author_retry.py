"""Tests for SpecAuthor retry handling with DebateRetryHandler.

TDD RED phase tests for wrapping SpecAuthor with DebateRetryHandler in
run_spec_pipeline method. These tests should FAIL initially because
SpecAuthor is not yet wrapped with retry logic.

Key requirements:
- run_spec_pipeline should use DebateRetryHandler for SpecAuthor calls
- Rate limit errors should trigger retry with exponential backoff
- Auth errors should fail immediately without retry
- Retry attempts should be logged
- System should work without retry if retry is disabled
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call, PropertyMock
from dataclasses import dataclass, field
from typing import Optional
import logging
import tempfile

from swarm_attack.errors import (
    LLMError,
    LLMErrorType,
    RateLimitError,
    ClaudeAuthError,
)
from swarm_attack.debate_retry import DebateRetryHandler, RetryResult


# ============================================================================
# Test fixtures
# ============================================================================

@dataclass
class MockAgentResult:
    """Mock agent result for testing."""
    success: bool
    output: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    errors: Optional[list] = None


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock SwarmConfig with required attributes."""
    config = MagicMock()
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.swarm_path = tmp_path / ".swarm"
    config.github = MagicMock()
    config.github.repo = "test/repo"

    # Tests config
    config.tests = MagicMock()
    config.tests.timeout_seconds = 300

    # Retry config
    config.retry = MagicMock()
    config.retry.max_retries = 3
    config.retry.backoff_seconds = 5

    # Spec debate config
    config.spec_debate = MagicMock()
    config.spec_debate.max_rounds = 3
    config.spec_debate.success_threshold = 0.85
    config.spec_debate.intra_round_delay_seconds = 0
    config.spec_debate.inter_round_delay_seconds = 0
    config.spec_debate.stalemate_threshold = 2
    config.spec_debate.consecutive_stalemate_threshold = 2
    config.spec_debate.disagreement_rounds_threshold = 3
    config.spec_debate.rubric_thresholds = {
        "completeness": 0.8,
        "clarity": 0.8,
        "testability": 0.8,
    }

    # Debate retry config with defaults
    config.debate_retry = MagicMock()
    config.debate_retry.max_retries = 3
    config.debate_retry.backoff_base_seconds = 30.0
    config.debate_retry.backoff_multiplier = 2.0
    config.debate_retry.max_backoff_seconds = 300.0

    # Create necessary directories
    (tmp_path / ".swarm").mkdir(parents=True, exist_ok=True)
    (tmp_path / "specs").mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def mock_state_store(tmp_path):
    """Create a mock StateStore."""
    from swarm_attack.models import FeaturePhase

    store = MagicMock()
    state = MagicMock()
    state.phase = FeaturePhase.PRD_READY
    state.prd_path = str(tmp_path / ".claude" / "prds" / "test-feature.md")
    store.load.return_value = state
    return store


@pytest.fixture
def mock_author():
    """Create a mock SpecAuthorAgent."""
    author = MagicMock()
    author.reset = MagicMock()
    author.run = MagicMock(return_value=MockAgentResult(
        success=True,
        output={"spec_path": "/tmp/spec.md"},
        cost_usd=0.01,
    ))
    return author


@pytest.fixture
def mock_critic():
    """Create a mock SpecCriticAgent."""
    critic = MagicMock()
    critic.reset = MagicMock()
    critic.run = MagicMock(return_value=MockAgentResult(
        success=True,
        output={
            "scores": {"overall": 0.9},
            "issues": [],
            "recommendation": "APPROVE",
        },
        cost_usd=0.01,
    ))
    return critic


@pytest.fixture
def mock_moderator():
    """Create a mock SpecModeratorAgent."""
    moderator = MagicMock()
    moderator.reset = MagicMock()
    moderator.run = MagicMock(return_value=MockAgentResult(
        success=True,
        output={"disposition_counts": {}},
        cost_usd=0.01,
    ))
    return moderator


@pytest.fixture
def rate_limit_error():
    """Create a rate limit error."""
    return RateLimitError("Rate limit exceeded. Please wait.")


@pytest.fixture
def auth_error():
    """Create an authentication error."""
    return ClaudeAuthError("Not logged in. Please run: claude login")


# ============================================================================
# Test: run_spec_pipeline uses DebateRetryHandler for SpecAuthor
# ============================================================================

class TestSpecAuthorUsesRetryHandler:
    """Test that run_spec_pipeline wraps SpecAuthor with DebateRetryHandler."""

    @patch('swarm_attack.orchestrator.get_event_bus')
    @patch('swarm_attack.orchestrator.EventLogger')
    def test_spec_author_uses_retry_handler(
        self,
        mock_event_logger,
        mock_get_event_bus,
        mock_config,
        mock_state_store,
        mock_author,
        mock_critic,
        mock_moderator,
    ):
        """Orchestrator's run_spec_pipeline should use DebateRetryHandler for author.

        The SpecAuthor call should be wrapped with the retry handler, just like
        critic and moderator are. This test verifies the retry handler is invoked.
        """
        from swarm_attack.orchestrator import Orchestrator

        # Setup mocks for infrastructure
        mock_bus = MagicMock()
        mock_get_event_bus.return_value = mock_bus

        # Create orchestrator with mocks
        orchestrator = Orchestrator(
            config=mock_config,
            author=mock_author,
            critic=mock_critic,
            moderator=mock_moderator,
            state_store=mock_state_store,
        )

        # Track calls to the retry handler
        original_handler = orchestrator._debate_retry_handler
        calls_to_run_with_retry = []

        def tracking_run_with_retry(agent, context):
            calls_to_run_with_retry.append((agent, context))
            # Return a successful result
            return RetryResult(
                success=True,
                output=agent.run(context).output if hasattr(agent.run(context), 'output') else {},
                cost_usd=0.01,
            )

        orchestrator._debate_retry_handler.run_with_retry = MagicMock(
            side_effect=tracking_run_with_retry
        )

        result = orchestrator.run_spec_pipeline("test-feature")

        # The retry handler should have been called for author
        # Look for a call where the first arg is the author agent
        author_calls = [
            c for c in calls_to_run_with_retry
            if c[0] is mock_author
        ]

        assert len(author_calls) >= 1, (
            "Expected DebateRetryHandler.run_with_retry to be called for "
            "SpecAuthor, but it was not. SpecAuthor should be wrapped with "
            "retry logic like critic and moderator."
        )


# ============================================================================
# Test: Rate limit error triggers retry with backoff
# ============================================================================

class TestSpecAuthorRetriesOnRateLimit:
    """Test that rate limit errors trigger retry with exponential backoff."""

    @patch('swarm_attack.orchestrator.get_event_bus')
    @patch('swarm_attack.orchestrator.EventLogger')
    @patch('swarm_attack.debate_retry.time.sleep')
    def test_spec_author_retries_on_rate_limit(
        self,
        mock_sleep,
        mock_event_logger,
        mock_get_event_bus,
        mock_config,
        mock_state_store,
        mock_author,
        mock_critic,
        mock_moderator,
        rate_limit_error,
    ):
        """Rate limit error should trigger retry with backoff.

        When SpecAuthor hits a rate limit, the retry handler should:
        1. Catch the RateLimitError
        2. Wait with exponential backoff
        3. Retry the call
        """
        from swarm_attack.orchestrator import Orchestrator

        # Setup mocks
        mock_bus = MagicMock()
        mock_get_event_bus.return_value = mock_bus

        # Configure author to fail with rate limit, then succeed
        success_result = MockAgentResult(
            success=True,
            output={"spec_path": "/tmp/spec.md"},
            cost_usd=0.01,
        )
        mock_author.run.side_effect = [rate_limit_error, success_result]

        orchestrator = Orchestrator(
            config=mock_config,
            author=mock_author,
            critic=mock_critic,
            moderator=mock_moderator,
            state_store=mock_state_store,
        )

        result = orchestrator.run_spec_pipeline("test-feature")

        # Author should have been called twice (once failed, once succeeded)
        assert mock_author.run.call_count == 2, (
            f"Expected author.run to be called 2 times (1 fail + 1 retry), "
            f"got {mock_author.run.call_count}. SpecAuthor should retry on rate limit."
        )

        # Should have slept at least once (backoff before retry)
        assert mock_sleep.call_count >= 1, (
            "Expected at least one sleep call for backoff, but none occurred. "
            "SpecAuthor should use exponential backoff on rate limit retry."
        )

        # First backoff should be the base (30s by default)
        first_sleep_call = mock_sleep.call_args_list[0]
        assert first_sleep_call[0][0] == mock_config.debate_retry.backoff_base_seconds, (
            f"First backoff should be {mock_config.debate_retry.backoff_base_seconds}s, "
            f"got {first_sleep_call[0][0]}s"
        )


# ============================================================================
# Test: Auth error fails fast without retry
# ============================================================================

class TestSpecAuthorFailsFastOnAuthError:
    """Test that auth errors fail immediately without retry."""

    @patch('swarm_attack.orchestrator.get_event_bus')
    @patch('swarm_attack.orchestrator.EventLogger')
    @patch('swarm_attack.debate_retry.time.sleep')
    def test_spec_author_fails_fast_on_auth_error(
        self,
        mock_sleep,
        mock_event_logger,
        mock_get_event_bus,
        mock_config,
        mock_state_store,
        mock_author,
        mock_critic,
        mock_moderator,
        auth_error,
    ):
        """Auth errors should fail immediately without retry.

        Authentication errors are fatal - retrying won't help. The system
        should fail fast to avoid wasting time on retries.
        """
        from swarm_attack.orchestrator import Orchestrator

        # Setup mocks
        mock_bus = MagicMock()
        mock_get_event_bus.return_value = mock_bus

        # Configure author to fail with auth error
        mock_author.run.side_effect = auth_error

        orchestrator = Orchestrator(
            config=mock_config,
            author=mock_author,
            critic=mock_critic,
            moderator=mock_moderator,
            state_store=mock_state_store,
        )

        result = orchestrator.run_spec_pipeline("test-feature")

        # Author should have been called exactly once (no retry)
        assert mock_author.run.call_count == 1, (
            f"Expected author.run to be called exactly 1 time (no retry on auth error), "
            f"got {mock_author.run.call_count}. Auth errors should fail fast."
        )

        # Should NOT have slept (no backoff for auth errors)
        assert mock_sleep.call_count == 0, (
            f"Expected no sleep calls for auth errors, got {mock_sleep.call_count}. "
            "Auth errors should fail immediately without backoff."
        )

        # Result should indicate failure
        assert result.status == "failure", (
            f"Expected status='failure' for auth error, got '{result.status}'"
        )


# ============================================================================
# Test: Retry attempts are logged
# ============================================================================

class TestSpecAuthorLogsRetryAttempts:
    """Test that retry attempts are logged for observability."""

    @patch('swarm_attack.orchestrator.get_event_bus')
    @patch('swarm_attack.orchestrator.EventLogger')
    @patch('swarm_attack.debate_retry.time.sleep')
    def test_spec_author_logs_retry_attempts(
        self,
        mock_sleep,
        mock_event_logger,
        mock_get_event_bus,
        mock_config,
        mock_state_store,
        mock_author,
        mock_critic,
        mock_moderator,
        rate_limit_error,
        caplog,
    ):
        """Retry attempts should be logged.

        For debugging and monitoring, each retry attempt should be logged
        with appropriate context (attempt number, error type, backoff time).
        """
        from swarm_attack.orchestrator import Orchestrator

        # Setup mocks
        mock_bus = MagicMock()
        mock_get_event_bus.return_value = mock_bus

        # Configure author to fail with rate limit twice, then succeed
        success_result = MockAgentResult(
            success=True,
            output={"spec_path": "/tmp/spec.md"},
            cost_usd=0.01,
        )
        mock_author.run.side_effect = [
            rate_limit_error,
            rate_limit_error,
            success_result,
        ]

        orchestrator = Orchestrator(
            config=mock_config,
            author=mock_author,
            critic=mock_critic,
            moderator=mock_moderator,
            state_store=mock_state_store,
        )

        with caplog.at_level(logging.WARNING):
            result = orchestrator.run_spec_pipeline("test-feature")

        # Should have log entries for retry attempts
        retry_logs = [
            record for record in caplog.records
            if "retry" in record.message.lower() or "transient" in record.message.lower()
        ]

        # At least 2 retry logs (for 2 rate limit errors)
        assert len(retry_logs) >= 2, (
            f"Expected at least 2 retry log entries, got {len(retry_logs)}. "
            f"Log messages: {[r.message for r in caplog.records]}"
        )


# ============================================================================
# Test: Backward compatible without retry
# ============================================================================

class TestSpecAuthorBackwardCompatibleWithoutRetry:
    """Test that system works when retry is disabled or not configured."""

    @patch('swarm_attack.orchestrator.get_event_bus')
    @patch('swarm_attack.orchestrator.EventLogger')
    def test_spec_author_backward_compatible_without_retry(
        self,
        mock_event_logger,
        mock_get_event_bus,
        mock_config,
        mock_state_store,
        mock_author,
        mock_critic,
        mock_moderator,
    ):
        """If retry disabled, SpecAuthor should still work.

        When debate_retry is not configured or max_retries=0, the system
        should still function normally (just without retry capability).
        """
        from swarm_attack.orchestrator import Orchestrator

        # Setup mocks
        mock_bus = MagicMock()
        mock_get_event_bus.return_value = mock_bus

        # Remove debate_retry config to test backward compatibility
        mock_config.debate_retry = None

        orchestrator = Orchestrator(
            config=mock_config,
            author=mock_author,
            critic=mock_critic,
            moderator=mock_moderator,
            state_store=mock_state_store,
        )

        result = orchestrator.run_spec_pipeline("test-feature")

        # Should still work
        assert mock_author.run.call_count >= 1, (
            "SpecAuthor should be called even without retry config"
        )

        # Result should be based on author success
        # (may be success or failure depending on full pipeline)
        assert result is not None, "Should return a PipelineResult"

    @patch('swarm_attack.orchestrator.get_event_bus')
    @patch('swarm_attack.orchestrator.EventLogger')
    @patch('swarm_attack.debate_retry.time.sleep')
    def test_spec_author_works_with_zero_retries(
        self,
        mock_sleep,
        mock_event_logger,
        mock_get_event_bus,
        mock_config,
        mock_state_store,
        mock_author,
        mock_critic,
        mock_moderator,
        rate_limit_error,
    ):
        """With max_retries=0, rate limit should fail immediately.

        When retry is explicitly disabled via max_retries=0, the system
        should fail on first error without attempting retries.
        """
        from swarm_attack.orchestrator import Orchestrator

        # Setup mocks
        mock_bus = MagicMock()
        mock_get_event_bus.return_value = mock_bus

        # Configure zero retries
        mock_config.debate_retry.max_retries = 0

        # Configure author to fail with rate limit
        mock_author.run.side_effect = rate_limit_error

        orchestrator = Orchestrator(
            config=mock_config,
            author=mock_author,
            critic=mock_critic,
            moderator=mock_moderator,
            state_store=mock_state_store,
        )

        result = orchestrator.run_spec_pipeline("test-feature")

        # Author should have been called exactly once (no retry with max_retries=0)
        assert mock_author.run.call_count == 1, (
            f"Expected author.run called once with max_retries=0, "
            f"got {mock_author.run.call_count}"
        )

        # Result should indicate failure
        assert result.status == "failure", (
            f"Expected failure status with rate limit and max_retries=0, "
            f"got '{result.status}'"
        )
