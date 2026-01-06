"""Tests for RateLimitTracker - preemptive rate limiting for API calls.

TDD tests (RED phase) for RateLimitTracker class that tracks API call frequency
for preemptive rate limiting. Claude Max allows ~20 calls/minute.

These tests should FAIL initially because RateLimitTracker does not exist yet.

Key requirements:
- RateLimitTracker should be importable from swarm_attack.rate_limit_tracker
- Default calls_per_minute_limit is 20 (Claude Max limit)
- record_call() adds timestamp to internal list
- should_delay() returns (should_wait, wait_seconds) tuple
- Cleans up timestamps older than 60 seconds
- Integrates with DebateRetryHandler via rate_limiter parameter
- Configurable via rate_limit_calls_per_minute in DebateRetryConfig
- Zero limit disables preemption
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Optional
import tempfile
import os
import time


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def mock_time():
    """Mock time.time() for deterministic testing."""
    with patch('time.time') as mock:
        mock.return_value = 1000.0  # Start at timestamp 1000
        yield mock


@pytest.fixture
def sample_yaml_config_with_rate_limit():
    """Sample YAML config with rate_limit_calls_per_minute."""
    return """
github:
  repo: "test/repo"

tests:
  command: "pytest"

debate_retry:
  max_retries: 3
  backoff_base_seconds: 30.0
  backoff_multiplier: 2.0
  max_backoff_seconds: 300.0
  rate_limit_calls_per_minute: 15
"""


# ============================================================================
# Test: RateLimitTracker can be imported
# ============================================================================

class TestRateLimitTrackerCanBeImported:
    """Test that RateLimitTracker is importable from the correct module."""

    def test_rate_limit_tracker_can_be_imported(self):
        """RateLimitTracker should be importable from swarm_attack.rate_limit_tracker."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        assert RateLimitTracker is not None

        # Should be instantiable
        tracker = RateLimitTracker()
        assert tracker is not None


# ============================================================================
# Test: Tracker has calls_per_minute_limit config
# ============================================================================

class TestTrackerHasCallsPerMinuteLimitConfig:
    """Test that RateLimitTracker has calls_per_minute_limit attribute."""

    def test_tracker_has_calls_per_minute_limit_config(self):
        """Tracker should have calls_per_minute_limit attribute with default 20."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()

        assert hasattr(tracker, 'calls_per_minute_limit')
        assert tracker.calls_per_minute_limit == 20  # Claude Max default

    def test_tracker_accepts_custom_limit(self):
        """Tracker should accept custom calls_per_minute_limit."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=10)

        assert tracker.calls_per_minute_limit == 10


# ============================================================================
# Test: Tracker records call timestamps
# ============================================================================

class TestTrackerRecordsCallTimestamps:
    """Test that record_call() adds timestamp to internal list."""

    def test_tracker_records_call_timestamps(self, mock_time):
        """record_call() should add current timestamp to internal list."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()

        # Initially empty
        assert len(tracker._timestamps) == 0

        # Record a call
        mock_time.return_value = 1000.0
        tracker.record_call()

        assert len(tracker._timestamps) == 1
        assert tracker._timestamps[0] == 1000.0

    def test_tracker_records_multiple_calls(self, mock_time):
        """record_call() should accumulate multiple timestamps."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()

        # Record multiple calls at different times
        mock_time.return_value = 1000.0
        tracker.record_call()

        mock_time.return_value = 1001.0
        tracker.record_call()

        mock_time.return_value = 1002.0
        tracker.record_call()

        assert len(tracker._timestamps) == 3
        assert tracker._timestamps == [1000.0, 1001.0, 1002.0]


# ============================================================================
# Test: should_delay returns False when under limit
# ============================================================================

class TestShouldDelayReturnsFalseWhenUnderLimit:
    """Test that should_delay() returns (False, 0.0) when under the limit."""

    def test_should_delay_returns_false_when_under_limit(self, mock_time):
        """should_delay() should return (False, 0.0) when call count is under limit."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=20)

        mock_time.return_value = 1000.0

        # Record 10 calls (under 20 limit)
        for _ in range(10):
            tracker.record_call()

        should_wait, wait_seconds = tracker.should_delay()

        assert should_wait is False
        assert wait_seconds == 0.0

    def test_should_delay_returns_false_when_empty(self):
        """should_delay() should return (False, 0.0) when no calls recorded."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()

        should_wait, wait_seconds = tracker.should_delay()

        assert should_wait is False
        assert wait_seconds == 0.0


# ============================================================================
# Test: should_delay returns True when at limit
# ============================================================================

class TestShouldDelayReturnsTrueWhenAtLimit:
    """Test that should_delay() returns (True, wait_time) when at the limit."""

    def test_should_delay_returns_true_when_at_limit(self, mock_time):
        """should_delay() should return (True, wait_time) when at limit."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=20)

        mock_time.return_value = 1000.0

        # Record exactly 20 calls (at limit)
        for _ in range(20):
            tracker.record_call()

        should_wait, wait_seconds = tracker.should_delay()

        assert should_wait is True
        assert wait_seconds > 0.0

    def test_should_delay_returns_true_when_over_limit(self, mock_time):
        """should_delay() should return (True, wait_time) when over limit."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=5)

        mock_time.return_value = 1000.0

        # Record 10 calls (over 5 limit)
        for _ in range(10):
            tracker.record_call()

        should_wait, wait_seconds = tracker.should_delay()

        assert should_wait is True
        assert wait_seconds > 0.0


# ============================================================================
# Test: should_delay suggests correct wait time
# ============================================================================

class TestShouldDelaySuggestsCorrectWaitTime:
    """Test that wait time is time until oldest call ages out of the window."""

    def test_should_delay_suggests_correct_wait_time(self, mock_time):
        """Wait time should be time until oldest call ages out (60s window)."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=5)

        # Record 5 calls at t=1000
        mock_time.return_value = 1000.0
        for _ in range(5):
            tracker.record_call()

        # Now at t=1030 (30 seconds later), check delay
        mock_time.return_value = 1030.0

        should_wait, wait_seconds = tracker.should_delay()

        assert should_wait is True
        # Oldest call at t=1000 will age out at t=1060
        # At t=1030, need to wait 30 more seconds
        assert wait_seconds == pytest.approx(30.0, abs=0.1)

    def test_should_delay_wait_time_decreases_over_time(self, mock_time):
        """Wait time should decrease as time passes."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=3)

        # Record 3 calls at t=1000
        mock_time.return_value = 1000.0
        for _ in range(3):
            tracker.record_call()

        # At t=1040 (40s later), wait time should be 20s
        mock_time.return_value = 1040.0
        _, wait_at_40 = tracker.should_delay()
        assert wait_at_40 == pytest.approx(20.0, abs=0.1)

        # At t=1050 (50s later), wait time should be 10s
        mock_time.return_value = 1050.0
        _, wait_at_50 = tracker.should_delay()
        assert wait_at_50 == pytest.approx(10.0, abs=0.1)


# ============================================================================
# Test: Tracker cleans old timestamps
# ============================================================================

class TestTrackerCleansOldTimestamps:
    """Test that cleanup removes timestamps older than 60 seconds."""

    def test_tracker_cleans_old_timestamps(self, mock_time):
        """cleanup() should remove timestamps older than 60 seconds."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()

        # Record calls at t=1000
        mock_time.return_value = 1000.0
        tracker.record_call()
        tracker.record_call()

        # Record call at t=1030
        mock_time.return_value = 1030.0
        tracker.record_call()

        assert len(tracker._timestamps) == 3

        # Cleanup at t=1065 (65s after first calls)
        mock_time.return_value = 1065.0
        tracker.cleanup()

        # Calls at t=1000 should be removed (>60s old)
        # Call at t=1030 should remain (only 35s old)
        assert len(tracker._timestamps) == 1
        assert tracker._timestamps[0] == 1030.0

    def test_cleanup_is_called_during_should_delay(self, mock_time):
        """should_delay() should trigger cleanup of old timestamps."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=2)

        # Record 2 calls at t=1000
        mock_time.return_value = 1000.0
        tracker.record_call()
        tracker.record_call()

        # At t=1000, should be at limit
        should_wait, _ = tracker.should_delay()
        assert should_wait is True

        # At t=1061 (61s later), old calls should be cleaned up
        mock_time.return_value = 1061.0
        should_wait, _ = tracker.should_delay()

        # Should no longer be at limit after cleanup
        assert should_wait is False
        assert len(tracker._timestamps) == 0


# ============================================================================
# Test: Tracker integrates with DebateRetryHandler
# ============================================================================

class TestTrackerIntegratesWithDebateRetryHandler:
    """Test that DebateRetryHandler accepts rate_limiter parameter."""

    def test_tracker_integrates_with_debate_retry_handler(self):
        """DebateRetryHandler should accept optional rate_limiter parameter."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()
        handler = DebateRetryHandler(rate_limiter=tracker)

        assert handler.rate_limiter is tracker

    def test_handler_uses_rate_limiter_before_call(self, mock_time):
        """Handler should check rate_limiter.should_delay() before making call."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=1)

        # Record a call to trigger rate limit
        mock_time.return_value = 1000.0
        tracker.record_call()

        handler = DebateRetryHandler(rate_limiter=tracker)

        # Mock agent that succeeds
        mock_agent = Mock()
        mock_agent.run.return_value = Mock(success=True, output={}, cost_usd=0.0)
        mock_agent.reset = Mock()

        # Should delay before calling since at limit
        with patch('time.sleep') as mock_sleep:
            mock_time.return_value = 1030.0  # 30s later
            handler.run_with_retry(mock_agent, {})

            # Should have slept for ~30 seconds (time until oldest ages out)
            mock_sleep.assert_called()
            sleep_time = mock_sleep.call_args[0][0]
            assert sleep_time > 0

    def test_handler_records_call_after_success(self, mock_time):
        """Handler should call rate_limiter.record_call() after successful call."""
        from swarm_attack.debate_retry import DebateRetryHandler
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker()
        handler = DebateRetryHandler(rate_limiter=tracker)

        mock_time.return_value = 1000.0

        # Mock agent that succeeds
        mock_agent = Mock()
        mock_agent.run.return_value = Mock(success=True, output={}, cost_usd=0.0)
        mock_agent.reset = Mock()

        assert len(tracker._timestamps) == 0

        handler.run_with_retry(mock_agent, {})

        # Should have recorded the call
        assert len(tracker._timestamps) == 1


# ============================================================================
# Test: Tracker config from YAML
# ============================================================================

class TestTrackerConfigFromYaml:
    """Test that rate_limit_calls_per_minute can be configured via DebateRetryConfig."""

    def test_tracker_config_from_yaml(self, sample_yaml_config_with_rate_limit):
        """rate_limit_calls_per_minute should be loadable from YAML config."""
        from swarm_attack.config.main import load_config, DebateRetryConfig

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_yaml_config_with_rate_limit)
            f.flush()

            try:
                config = load_config(config_path=f.name)

                # DebateRetryConfig should have rate_limit_calls_per_minute
                assert hasattr(config.debate_retry, 'rate_limit_calls_per_minute')
                assert config.debate_retry.rate_limit_calls_per_minute == 15
            finally:
                os.unlink(f.name)

    def test_debate_retry_config_has_rate_limit_field(self):
        """DebateRetryConfig should have rate_limit_calls_per_minute with default 20."""
        from swarm_attack.config.main import DebateRetryConfig

        config = DebateRetryConfig()

        assert hasattr(config, 'rate_limit_calls_per_minute')
        assert config.rate_limit_calls_per_minute == 20  # Claude Max default


# ============================================================================
# Test: Zero limit disables preemption
# ============================================================================

class TestZeroLimitDisablesPreemption:
    """Test that when limit is 0, should_delay always returns (False, 0.0)."""

    def test_zero_limit_disables_preemption(self, mock_time):
        """When calls_per_minute_limit is 0, should_delay always returns (False, 0.0)."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=0)

        mock_time.return_value = 1000.0

        # Record many calls
        for _ in range(100):
            tracker.record_call()

        should_wait, wait_seconds = tracker.should_delay()

        # Should never delay when limit is 0 (disabled)
        assert should_wait is False
        assert wait_seconds == 0.0

    def test_zero_limit_still_records_calls(self, mock_time):
        """Even with limit=0, record_call() should still track timestamps."""
        from swarm_attack.rate_limit_tracker import RateLimitTracker

        tracker = RateLimitTracker(calls_per_minute_limit=0)

        mock_time.return_value = 1000.0
        tracker.record_call()
        tracker.record_call()

        # Should still record for potential future use or metrics
        assert len(tracker._timestamps) == 2
