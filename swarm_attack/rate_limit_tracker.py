"""Rate limit tracking for preemptive API call limiting.

Provides RateLimitTracker class that tracks API call timestamps over a rolling
1-minute window for preemptive rate limiting. Default limit is 20 calls/minute
(Claude Max rate limit).

Usage:
    tracker = RateLimitTracker(calls_per_minute_limit=20)

    # Before making API call
    should_wait, wait_seconds = tracker.should_delay()
    if should_wait:
        time.sleep(wait_seconds)

    # After making API call
    tracker.record_call()
"""

from dataclasses import dataclass, field
import time


@dataclass
class RateLimitTracker:
    """Tracks API call frequency for preemptive rate limiting.

    Uses a rolling 1-minute window to track call timestamps and determine
    if a delay is needed before making another API call.

    Attributes:
        calls_per_minute_limit: Maximum calls allowed per minute.
            Default is 20 (Claude Max limit). Set to 0 to disable preemption.
    """

    calls_per_minute_limit: int = 20  # Claude Max default, 0 to disable
    _timestamps: list[float] = field(default_factory=list)

    def record_call(self) -> None:
        """Record an API call timestamp.

        Adds the current timestamp to the internal list and cleans up
        any timestamps older than 60 seconds.
        """
        self._timestamps.append(time.time())
        self._cleanup_old_timestamps()

    def should_delay(self) -> tuple[bool, float]:
        """Check if a delay is needed before making another API call.

        Returns:
            A tuple of (should_delay, suggested_delay_seconds).

            If limit is 0, preemption is disabled - always returns (False, 0.0).
            If under the limit, returns (False, 0.0).
            If at or over the limit, returns (True, wait_time) where wait_time
            is the number of seconds until the oldest call ages out of the
            60-second window.
        """
        if self.calls_per_minute_limit == 0:
            return (False, 0.0)

        self._cleanup_old_timestamps()

        if len(self._timestamps) >= self.calls_per_minute_limit:
            oldest = min(self._timestamps)
            wait_time = 60.0 - (time.time() - oldest)
            return (True, max(0.0, wait_time))

        return (False, 0.0)

    def cleanup(self) -> None:
        """Public method to clean up old timestamps.

        Removes timestamps older than 60 seconds from the internal list.
        This is called automatically by record_call() and should_delay(),
        but can be called manually if needed.
        """
        self._cleanup_old_timestamps()

    def _cleanup_old_timestamps(self) -> None:
        """Remove timestamps older than 60 seconds."""
        cutoff = time.time() - 60.0
        self._timestamps = [t for t in self._timestamps if t > cutoff]
