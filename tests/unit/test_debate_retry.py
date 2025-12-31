"""Tests for debate retry logic with auth and rate limiting errors.

TDD tests for DebateRetryHandler that adds retry logic to debate agent calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Optional

from swarm_attack.errors import (
    LLMError,
    LLMErrorType,
    CodexAuthError,
    RateLimitError,
)


# ============================================================================
# Test fixtures
# ============================================================================

@dataclass
class MockAgentResult:
    """Mock agent result for testing."""
    success: bool
    output: dict
    cost_usd: float = 0.0
    errors: Optional[list] = None


@pytest.fixture
def mock_agent():
    """Create a mock agent with configurable run behavior."""
    agent = Mock()
    agent.reset = Mock()
    return agent


@pytest.fixture
def rate_limit_error():
    """Create a rate limit error."""
    return RateLimitError("Rate limit exceeded. Please wait.")


@pytest.fixture
def auth_error():
    """Create an auth error."""
    return CodexAuthError("Not logged in. Please run `codex login`")


@pytest.fixture
def timeout_error():
    """Create a timeout error."""
    return LLMError(
        "Codex CLI timed out after 300 seconds",
        error_type=LLMErrorType.TIMEOUT,
        recoverable=True,
    )


# ============================================================================
# Test: DebateRetryHandler exists and has expected interface
# ============================================================================

class TestDebateRetryHandlerInterface:
    """Test that DebateRetryHandler has the expected interface."""

    def test_handler_can_be_imported(self):
        """DebateRetryHandler should be importable from debate module."""
        from swarm_attack.debate_retry import DebateRetryHandler
        assert DebateRetryHandler is not None

    def test_handler_has_run_with_retry_method(self):
        """Handler should have run_with_retry method."""
        from swarm_attack.debate_retry import DebateRetryHandler
        handler = DebateRetryHandler()
        assert hasattr(handler, 'run_with_retry')

    def test_handler_accepts_max_retries_config(self):
        """Handler should accept max_retries configuration."""
        from swarm_attack.debate_retry import DebateRetryHandler
        handler = DebateRetryHandler(max_retries=5)
        assert handler.max_retries == 5

    def test_handler_accepts_backoff_config(self):
        """Handler should accept backoff configuration."""
        from swarm_attack.debate_retry import DebateRetryHandler
        handler = DebateRetryHandler(
            backoff_base_seconds=2.0,
            backoff_multiplier=3.0,
        )
        assert handler.backoff_base_seconds == 2.0
        assert handler.backoff_multiplier == 3.0


# ============================================================================
# Test: Successful agent calls pass through
# ============================================================================

class TestSuccessfulCalls:
    """Test that successful agent calls work normally."""

    def test_successful_call_returns_result(self, mock_agent):
        """Successful agent call should return result without retry."""
        from swarm_attack.debate_retry import DebateRetryHandler

        expected_result = MockAgentResult(
            success=True,
            output={"scores": {"completeness": 0.9}},
            cost_usd=0.05,
        )
        mock_agent.run.return_value = expected_result

        handler = DebateRetryHandler()
        result = handler.run_with_retry(mock_agent, {"feature_id": "test"})

        assert result.success is True
        assert result.output["scores"]["completeness"] == 0.9
        assert mock_agent.run.call_count == 1

    def test_successful_call_does_not_sleep(self, mock_agent):
        """Successful call should not trigger any sleep/backoff."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.return_value = MockAgentResult(
            success=True, output={}, cost_usd=0.01
        )

        handler = DebateRetryHandler()
        with patch('time.sleep') as mock_sleep:
            handler.run_with_retry(mock_agent, {})
            mock_sleep.assert_not_called()


# ============================================================================
# Test: Rate limit errors trigger retry with backoff
# ============================================================================

class TestRateLimitRetry:
    """Test retry behavior for rate limit errors."""

    def test_rate_limit_retries_up_to_max(self, mock_agent, rate_limit_error):
        """Rate limit should retry up to max_retries times."""
        from swarm_attack.debate_retry import DebateRetryHandler

        # Fail with rate limit every time
        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(max_retries=3)
        with patch('time.sleep'):
            result = handler.run_with_retry(mock_agent, {})

        # Should have tried 1 + 3 retries = 4 total
        assert mock_agent.run.call_count == 4
        assert result.success is False

    def test_rate_limit_uses_exponential_backoff(self, mock_agent, rate_limit_error):
        """Rate limit should use exponential backoff between retries."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(
            max_retries=3,
            backoff_base_seconds=1.0,
            backoff_multiplier=2.0,
        )

        sleep_times = []
        with patch('time.sleep', side_effect=lambda t: sleep_times.append(t)):
            handler.run_with_retry(mock_agent, {})

        # Should be: 1.0, 2.0, 4.0 (exponential backoff)
        assert sleep_times == [1.0, 2.0, 4.0]

    def test_rate_limit_succeeds_after_retry(self, mock_agent, rate_limit_error):
        """Rate limit should succeed if retry works."""
        from swarm_attack.debate_retry import DebateRetryHandler

        success_result = MockAgentResult(success=True, output={"ok": True})

        # Fail twice, then succeed
        mock_agent.run.side_effect = [
            rate_limit_error,
            rate_limit_error,
            success_result,
        ]

        handler = DebateRetryHandler(max_retries=3)
        with patch('time.sleep'):
            result = handler.run_with_retry(mock_agent, {})

        assert result.success is True
        assert mock_agent.run.call_count == 3


# ============================================================================
# Test: Auth errors fail immediately (no retry)
# ============================================================================

class TestAuthErrorNoRetry:
    """Test that auth errors fail immediately without retry."""

    def test_auth_error_fails_immediately(self, mock_agent, auth_error):
        """Auth error should not retry - fail immediately."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = auth_error

        handler = DebateRetryHandler(max_retries=3)
        result = handler.run_with_retry(mock_agent, {})

        # Should only try once - no retries for auth
        assert mock_agent.run.call_count == 1
        assert result.success is False

    def test_auth_error_includes_user_message(self, mock_agent, auth_error):
        """Auth error result should include helpful user message."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = auth_error

        handler = DebateRetryHandler()
        result = handler.run_with_retry(mock_agent, {})

        assert result.success is False
        assert "codex login" in str(result.errors[0]).lower() or "auth" in str(result.errors[0]).lower()

    def test_auth_error_does_not_sleep(self, mock_agent, auth_error):
        """Auth error should not trigger any sleep."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = auth_error

        handler = DebateRetryHandler()
        with patch('time.sleep') as mock_sleep:
            handler.run_with_retry(mock_agent, {})
            mock_sleep.assert_not_called()


# ============================================================================
# Test: Timeout errors trigger retry
# ============================================================================

class TestTimeoutRetry:
    """Test retry behavior for timeout errors."""

    def test_timeout_retries(self, mock_agent, timeout_error):
        """Timeout errors should trigger retry."""
        from swarm_attack.debate_retry import DebateRetryHandler

        success_result = MockAgentResult(success=True, output={})

        # Timeout once, then succeed
        mock_agent.run.side_effect = [timeout_error, success_result]

        handler = DebateRetryHandler(max_retries=2)
        with patch('time.sleep'):
            result = handler.run_with_retry(mock_agent, {})

        assert result.success is True
        assert mock_agent.run.call_count == 2


# ============================================================================
# Test: Agent result failure (not exception) passes through
# ============================================================================

class TestAgentResultFailure:
    """Test handling of agent results that indicate failure (not exceptions)."""

    def test_agent_result_failure_not_retried(self, mock_agent):
        """Agent returning success=False should not be retried (not a transient error)."""
        from swarm_attack.debate_retry import DebateRetryHandler

        fail_result = MockAgentResult(
            success=False,
            output={},
            errors=["Spec too vague to review"],
        )
        mock_agent.run.return_value = fail_result

        handler = DebateRetryHandler(max_retries=3)
        result = handler.run_with_retry(mock_agent, {})

        # Should only try once - this is not a transient error
        assert mock_agent.run.call_count == 1
        assert result.success is False


# ============================================================================
# Test: Integration with error classification
# ============================================================================

class TestErrorClassification:
    """Test that handler uses error classification from recovery module."""

    def test_classifies_rate_limit_as_transient(self, rate_limit_error):
        """Rate limit should be classified as transient (retryable)."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.chief_of_staff.recovery import ErrorCategory

        handler = DebateRetryHandler()
        category = handler._classify_error(rate_limit_error)
        assert category == ErrorCategory.TRANSIENT

    def test_classifies_auth_as_fatal(self, auth_error):
        """Auth error should be classified as fatal (no retry)."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.chief_of_staff.recovery import ErrorCategory

        handler = DebateRetryHandler()
        category = handler._classify_error(auth_error)
        assert category == ErrorCategory.FATAL

    def test_classifies_timeout_as_transient(self, timeout_error):
        """Timeout should be classified as transient (retryable)."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.chief_of_staff.recovery import ErrorCategory

        handler = DebateRetryHandler()
        category = handler._classify_error(timeout_error)
        assert category == ErrorCategory.TRANSIENT


# ============================================================================
# Test: Logging
# ============================================================================

class TestLogging:
    """Test that handler logs retry attempts."""

    def test_logs_retry_attempt(self, mock_agent, rate_limit_error, caplog):
        """Handler should log each retry attempt."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(max_retries=2)
        with patch('time.sleep'):
            handler.run_with_retry(mock_agent, {})

        # Check logs contain retry info
        log_text = caplog.text.lower()
        assert "retry" in log_text or "retrying" in log_text or "attempt" in log_text

    def test_logs_auth_failure(self, mock_agent, auth_error, caplog):
        """Handler should log auth failures clearly."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = auth_error

        handler = DebateRetryHandler()
        handler.run_with_retry(mock_agent, {})

        log_text = caplog.text.lower()
        assert "auth" in log_text or "fatal" in log_text


# ============================================================================
# Test: Max backoff cap
# ============================================================================

class TestMaxBackoffCap:
    """Test that backoff is capped at a maximum value."""

    def test_backoff_capped_at_max(self, mock_agent, rate_limit_error):
        """Backoff should not exceed max_backoff_seconds."""
        from swarm_attack.debate_retry import DebateRetryHandler

        mock_agent.run.side_effect = rate_limit_error

        handler = DebateRetryHandler(
            max_retries=5,
            backoff_base_seconds=10.0,
            backoff_multiplier=10.0,
            max_backoff_seconds=30.0,  # Cap at 30s
        )

        sleep_times = []
        with patch('time.sleep', side_effect=lambda t: sleep_times.append(t)):
            handler.run_with_retry(mock_agent, {})

        # All backoffs should be <= 30
        for t in sleep_times:
            assert t <= 30.0
