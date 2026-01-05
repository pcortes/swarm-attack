"""ContextMonitor - context window monitoring via Claude Code statusline.

This module provides context window usage monitoring with warning levels
and handoff suggestions for the swarm-attack autopilot orchestration system.

Key features:
- Warning levels: 70% (INFO), 80% (WARN), 90% (CRITICAL)
- Handoff suggestion at 85%+ with command hint
- Works via Claude Code statusline API (no bash)
- Pure Python, cross-platform compatible
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ContextLevel(Enum):
    """Severity levels for context window usage.

    Values are ordered by severity: OK < INFO < WARN < CRITICAL.
    """

    OK = 0
    INFO = 1
    WARN = 2
    CRITICAL = 3


@dataclass
class ContextStatus:
    """Status information about context window usage.

    Attributes:
        percentage: Current usage as a percentage (0.0-100.0)
        level: Severity level (OK, INFO, WARN, CRITICAL)
        warning_message: Human-readable warning message (None if OK)
        should_handoff: Whether a handoff should be suggested
        handoff_command: Command hint for handoff (None if not needed)
    """

    percentage: float
    level: ContextLevel
    warning_message: Optional[str]
    should_handoff: bool
    handoff_command: Optional[str]


class ContextMonitor:
    """Monitor context window usage and provide statusline integration.

    This class monitors context window usage levels and provides
    formatted output for the Claude Code statusline API. It is
    pure Python and does not use subprocess, os.system, or bash.

    Attributes:
        info_threshold: Threshold for INFO level (default 0.70)
        warn_threshold: Threshold for WARN level (default 0.80)
        critical_threshold: Threshold for CRITICAL level (default 0.90)
        handoff_threshold: Threshold for suggesting handoff (default 0.85)
    """

    def __init__(
        self,
        info_threshold: float = 0.70,
        warn_threshold: float = 0.80,
        critical_threshold: float = 0.90,
        handoff_threshold: float = 0.85,
    ):
        """Initialize the ContextMonitor with configurable thresholds.

        Args:
            info_threshold: Usage level to trigger INFO warning (default 0.70)
            warn_threshold: Usage level to trigger WARN warning (default 0.80)
            critical_threshold: Usage level to trigger CRITICAL warning (default 0.90)
            handoff_threshold: Usage level to suggest handoff (default 0.85)
        """
        self.info_threshold = info_threshold
        self.warn_threshold = warn_threshold
        self.critical_threshold = critical_threshold
        self.handoff_threshold = handoff_threshold

    def check_usage(self, usage: float) -> ContextStatus:
        """Check context window usage and return status.

        Args:
            usage: Usage as a float from 0.0 to 1.0 (e.g., 0.75 = 75%)

        Returns:
            ContextStatus with level, percentage, and handoff information

        Raises:
            ValueError: If usage is negative (optional behavior)
        """
        # Handle edge cases - clamp to valid range
        if usage < 0:
            usage = 0.0
        elif usage > 1.0:
            usage = 1.0

        # Convert to percentage
        percentage = usage * 100.0

        # Determine level based on thresholds
        if usage >= self.critical_threshold:
            level = ContextLevel.CRITICAL
            warning_message = f"CRITICAL: Context at {percentage:.0f}% - immediate handoff recommended"
        elif usage >= self.warn_threshold:
            level = ContextLevel.WARN
            warning_message = f"WARNING: Context at {percentage:.0f}% - consider handoff soon"
        elif usage >= self.info_threshold:
            level = ContextLevel.INFO
            warning_message = f"INFO: Context at {percentage:.0f}% - monitoring"
        else:
            level = ContextLevel.OK
            warning_message = None

        # Determine if handoff should be suggested
        should_handoff = usage >= self.handoff_threshold
        handoff_command = None

        if should_handoff:
            handoff_command = "/checkpoint save - persist current state for handoff"

        return ContextStatus(
            percentage=percentage,
            level=level,
            warning_message=warning_message,
            should_handoff=should_handoff,
            handoff_command=handoff_command,
        )

    def format_for_statusline(self, status: ContextStatus) -> str:
        """Format status for statusline display.

        Args:
            status: ContextStatus to format

        Returns:
            Concise string for statusline display
        """
        level_indicators = {
            ContextLevel.OK: "",
            ContextLevel.INFO: "[i]",
            ContextLevel.WARN: "[!]",
            ContextLevel.CRITICAL: "[!!!]",
        }

        indicator = level_indicators.get(status.level, "")
        base_text = f"Context: {status.percentage:.0f}%"

        if indicator:
            base_text = f"{indicator} {base_text}"

        # Add handoff hint if needed
        if status.should_handoff:
            base_text += " - handoff suggested"

        return base_text

    def get_statusline_data(self, usage: float) -> dict:
        """Get statusline data as dictionary for API integration.

        Args:
            usage: Usage as a float from 0.0 to 1.0

        Returns:
            Dictionary with all status fields plus formatted string
        """
        status = self.check_usage(usage)
        formatted = self.format_for_statusline(status)

        return {
            "percentage": status.percentage,
            "level": status.level.name,
            "warning_message": status.warning_message,
            "should_handoff": status.should_handoff,
            "handoff_command": status.handoff_command,
            "formatted": formatted,
        }
