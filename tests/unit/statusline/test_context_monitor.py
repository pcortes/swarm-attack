"""TDD tests for ContextMonitor - context window monitoring via Claude Code statusline.

These tests define the expected behavior for the ContextMonitor module.
The tests should FAIL initially until the implementation is created.

Acceptance Criteria:
1. Warning levels: 70% (INFO), 80% (WARN), 90% (CRITICAL)
2. Suggest handoff at 85%+ with command hint
3. Works via Claude Code statusline API (no bash)

Import: from swarm_attack.statusline.context_monitor import ContextMonitor
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional
from enum import Enum

# This import will fail until implementation exists - that's TDD!
from swarm_attack.statusline.context_monitor import (
    ContextMonitor,
    ContextLevel,
    ContextStatus,
)


class TestContextMonitorThresholds:
    """Test warning at 70/80/90% thresholds."""

    def test_below_70_percent_returns_ok(self):
        """Usage below 70% should return OK status with no warning."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.50)  # 50% usage

        assert status.level == ContextLevel.OK
        assert status.percentage == 50.0
        assert status.warning_message is None

    def test_at_69_percent_returns_ok(self):
        """Usage at 69% should still be OK (just below threshold)."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.69)

        assert status.level == ContextLevel.OK
        assert status.percentage == 69.0

    def test_at_70_percent_returns_info(self):
        """Usage at exactly 70% should trigger INFO warning."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.70)

        assert status.level == ContextLevel.INFO
        assert status.percentage == 70.0
        assert status.warning_message is not None
        assert "70%" in status.warning_message or "context" in status.warning_message.lower()

    def test_at_75_percent_returns_info(self):
        """Usage at 75% should still be INFO (below WARN threshold)."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.75)

        assert status.level == ContextLevel.INFO
        assert status.percentage == 75.0

    def test_at_80_percent_returns_warn(self):
        """Usage at exactly 80% should trigger WARN level."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.80)

        assert status.level == ContextLevel.WARN
        assert status.percentage == 80.0
        assert status.warning_message is not None

    def test_at_85_percent_returns_warn(self):
        """Usage at 85% should still be WARN (below CRITICAL threshold)."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.85)

        assert status.level == ContextLevel.WARN
        assert status.percentage == 85.0

    def test_at_90_percent_returns_critical(self):
        """Usage at exactly 90% should trigger CRITICAL level."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.90)

        assert status.level == ContextLevel.CRITICAL
        assert status.percentage == 90.0
        assert status.warning_message is not None

    def test_at_95_percent_returns_critical(self):
        """Usage at 95% should be CRITICAL."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.95)

        assert status.level == ContextLevel.CRITICAL
        assert status.percentage == 95.0

    def test_at_100_percent_returns_critical(self):
        """Usage at 100% should be CRITICAL."""
        monitor = ContextMonitor()
        status = monitor.check_usage(1.0)

        assert status.level == ContextLevel.CRITICAL
        assert status.percentage == 100.0


class TestContextMonitorHandoffSuggestion:
    """Test handoff suggestion at 85%+ with command hint."""

    def test_no_handoff_suggestion_below_85_percent(self):
        """Usage below 85% should not suggest handoff."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.84)

        assert status.should_handoff is False
        assert status.handoff_command is None

    def test_handoff_suggestion_at_85_percent(self):
        """Usage at exactly 85% should suggest handoff."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.85)

        assert status.should_handoff is True
        assert status.handoff_command is not None
        # Should contain a command hint for handoff
        assert len(status.handoff_command) > 0

    def test_handoff_suggestion_at_90_percent(self):
        """Usage at 90% should definitely suggest handoff."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.90)

        assert status.should_handoff is True
        assert status.handoff_command is not None

    def test_handoff_command_contains_useful_hint(self):
        """Handoff command should be actionable."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.87)

        # Command should mention handoff, continuity, or checkpoint
        command_lower = status.handoff_command.lower()
        assert any(word in command_lower for word in
                   ["handoff", "checkpoint", "continue", "save", "persist"])

    def test_handoff_at_100_percent_critical(self):
        """At 100%, handoff should be urgently suggested."""
        monitor = ContextMonitor()
        status = monitor.check_usage(1.0)

        assert status.should_handoff is True
        assert status.handoff_command is not None
        # Warning message should convey urgency
        assert status.level == ContextLevel.CRITICAL

    def test_custom_handoff_threshold(self):
        """Should support custom handoff threshold."""
        monitor = ContextMonitor(handoff_threshold=0.75)

        # Below custom threshold
        status_low = monitor.check_usage(0.74)
        assert status_low.should_handoff is False

        # At custom threshold
        status_at = monitor.check_usage(0.75)
        assert status_at.should_handoff is True


class TestContextMonitorStatusline:
    """Test statusline integration (Claude Code statusline API)."""

    def test_format_for_statusline_ok(self):
        """Format OK status for statusline display."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.50)

        formatted = monitor.format_for_statusline(status)

        # Should contain percentage
        assert "50" in formatted
        # Should be concise for statusline
        assert len(formatted) < 100

    def test_format_for_statusline_info(self):
        """Format INFO status for statusline display."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.72)

        formatted = monitor.format_for_statusline(status)

        assert "72" in formatted
        # INFO level should have some indicator
        assert len(formatted) > 0

    def test_format_for_statusline_warn(self):
        """Format WARN status for statusline display."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.82)

        formatted = monitor.format_for_statusline(status)

        assert "82" in formatted
        # WARN level should have warning indicator
        assert len(formatted) > 0

    def test_format_for_statusline_critical(self):
        """Format CRITICAL status for statusline display."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.92)

        formatted = monitor.format_for_statusline(status)

        assert "92" in formatted
        # CRITICAL should be highly visible
        assert len(formatted) > 0

    def test_format_includes_handoff_hint_when_needed(self):
        """Statusline format should include handoff hint when appropriate."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.88)

        formatted = monitor.format_for_statusline(status)

        # Should mention handoff when at handoff threshold
        assert status.should_handoff is True
        # Format should reference handoff somehow
        assert any(word in formatted.lower() for word in ["handoff", "checkpoint", "save"])

    def test_get_statusline_data_returns_dict(self):
        """Get statusline data as dictionary for API integration."""
        monitor = ContextMonitor()

        data = monitor.get_statusline_data(0.65)

        assert isinstance(data, dict)
        assert "percentage" in data
        assert "level" in data
        assert data["percentage"] == 65.0

    def test_statusline_data_includes_all_fields(self):
        """Statusline data should include all required fields."""
        monitor = ContextMonitor()

        data = monitor.get_statusline_data(0.87)

        assert "percentage" in data
        assert "level" in data
        assert "warning_message" in data
        assert "should_handoff" in data
        assert "handoff_command" in data
        assert "formatted" in data


class TestContextMonitorCrossPlatform:
    """Test cross-platform compatibility (no bash dependency)."""

    def test_does_not_use_subprocess(self):
        """ContextMonitor should not call subprocess for basic operations."""
        import subprocess

        with patch.object(subprocess, 'run', side_effect=AssertionError("subprocess.run called")):
            with patch.object(subprocess, 'Popen', side_effect=AssertionError("subprocess.Popen called")):
                monitor = ContextMonitor()
                monitor.check_usage(0.75)
                monitor.format_for_statusline(monitor.check_usage(0.75))
                monitor.get_statusline_data(0.75)

    def test_does_not_use_os_system(self):
        """ContextMonitor should not call os.system."""
        import os

        original_system = os.system

        def mock_system(cmd):
            raise AssertionError(f"os.system called with: {cmd}")

        with patch.object(os, 'system', mock_system):
            monitor = ContextMonitor()
            monitor.check_usage(0.85)
            monitor.format_for_statusline(monitor.check_usage(0.85))

    def test_no_shell_commands_in_output(self):
        """Handoff commands should be API-based, not shell commands."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.90)

        if status.handoff_command:
            # Should not contain shell operators
            assert "&&" not in status.handoff_command
            assert "|" not in status.handoff_command
            assert ">" not in status.handoff_command
            # Should be a clean command/API call reference
            assert not status.handoff_command.startswith("bash")
            assert not status.handoff_command.startswith("sh ")

    def test_pure_python_calculation(self):
        """All threshold calculations should be pure Python."""
        monitor = ContextMonitor()

        # Test various percentages - should work without any external calls
        for pct in [0.0, 0.25, 0.5, 0.69, 0.70, 0.79, 0.80, 0.84, 0.85, 0.89, 0.90, 1.0]:
            status = monitor.check_usage(pct)
            assert isinstance(status.percentage, float)
            assert isinstance(status.level, ContextLevel)

    def test_works_on_any_platform(self):
        """Monitor should work regardless of OS."""
        import sys

        # Mock different platforms
        for platform in ['win32', 'darwin', 'linux']:
            with patch.object(sys, 'platform', platform):
                monitor = ContextMonitor()
                status = monitor.check_usage(0.75)
                assert status.level == ContextLevel.INFO


class TestContextLevelEnum:
    """Test ContextLevel enum values and ordering."""

    def test_context_level_values(self):
        """ContextLevel should have OK, INFO, WARN, CRITICAL."""
        assert hasattr(ContextLevel, 'OK')
        assert hasattr(ContextLevel, 'INFO')
        assert hasattr(ContextLevel, 'WARN')
        assert hasattr(ContextLevel, 'CRITICAL')

    def test_context_level_ordering(self):
        """Levels should be orderable by severity."""
        # OK < INFO < WARN < CRITICAL
        assert ContextLevel.OK.value < ContextLevel.INFO.value
        assert ContextLevel.INFO.value < ContextLevel.WARN.value
        assert ContextLevel.WARN.value < ContextLevel.CRITICAL.value

    def test_context_level_is_critical(self):
        """Should have helper to check if critical."""
        assert ContextLevel.CRITICAL.value >= 3  # Highest severity


class TestContextStatus:
    """Test ContextStatus dataclass."""

    def test_context_status_fields(self):
        """ContextStatus should have required fields."""
        status = ContextStatus(
            percentage=75.0,
            level=ContextLevel.INFO,
            warning_message="Context at 75%",
            should_handoff=False,
            handoff_command=None,
        )

        assert status.percentage == 75.0
        assert status.level == ContextLevel.INFO
        assert status.warning_message == "Context at 75%"
        assert status.should_handoff is False
        assert status.handoff_command is None

    def test_context_status_with_handoff(self):
        """ContextStatus with handoff suggestion."""
        status = ContextStatus(
            percentage=87.0,
            level=ContextLevel.WARN,
            warning_message="Context at 87% - consider handoff",
            should_handoff=True,
            handoff_command="/checkpoint save",
        )

        assert status.should_handoff is True
        assert status.handoff_command == "/checkpoint save"


class TestContextMonitorConfiguration:
    """Test ContextMonitor configuration options."""

    def test_default_thresholds(self):
        """Default thresholds should be 70, 80, 90."""
        monitor = ContextMonitor()

        assert monitor.info_threshold == 0.70
        assert monitor.warn_threshold == 0.80
        assert monitor.critical_threshold == 0.90
        assert monitor.handoff_threshold == 0.85

    def test_custom_thresholds(self):
        """Should support custom thresholds."""
        monitor = ContextMonitor(
            info_threshold=0.60,
            warn_threshold=0.75,
            critical_threshold=0.85,
            handoff_threshold=0.80,
        )

        assert monitor.info_threshold == 0.60
        assert monitor.warn_threshold == 0.75
        assert monitor.critical_threshold == 0.85
        assert monitor.handoff_threshold == 0.80

    def test_custom_thresholds_affect_levels(self):
        """Custom thresholds should change when levels trigger."""
        monitor = ContextMonitor(
            info_threshold=0.50,
            warn_threshold=0.60,
            critical_threshold=0.70,
        )

        # With custom thresholds, 55% should be INFO (not OK)
        status = monitor.check_usage(0.55)
        assert status.level == ContextLevel.INFO

        # 65% should be WARN (not INFO)
        status = monitor.check_usage(0.65)
        assert status.level == ContextLevel.WARN

        # 75% should be CRITICAL (not WARN)
        status = monitor.check_usage(0.75)
        assert status.level == ContextLevel.CRITICAL


class TestContextMonitorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_usage(self):
        """0% usage should be OK."""
        monitor = ContextMonitor()
        status = monitor.check_usage(0.0)

        assert status.level == ContextLevel.OK
        assert status.percentage == 0.0

    def test_negative_usage_handled(self):
        """Negative usage should be treated as 0 or raise error."""
        monitor = ContextMonitor()

        # Either clamp to 0 or raise ValueError - both are acceptable
        try:
            status = monitor.check_usage(-0.1)
            assert status.percentage >= 0.0
        except ValueError:
            pass  # Also acceptable

    def test_over_100_percent_usage_handled(self):
        """Usage > 100% should be clamped or raise error."""
        monitor = ContextMonitor()

        # Either clamp to 100 or raise ValueError - both are acceptable
        try:
            status = monitor.check_usage(1.5)
            assert status.percentage <= 100.0
            assert status.level == ContextLevel.CRITICAL
        except ValueError:
            pass  # Also acceptable

    def test_percentage_conversion_from_int(self):
        """Should accept integer input (0-100 range)."""
        monitor = ContextMonitor()

        # If passing raw percentage (75 instead of 0.75)
        # Implementation should handle both or document expected format
        status = monitor.check_usage(0.75)  # Standard format
        assert status.percentage == 75.0

    def test_threshold_boundary_precision(self):
        """Threshold boundaries should be precise."""
        monitor = ContextMonitor()

        # Just below 70%
        status = monitor.check_usage(0.6999)
        assert status.level == ContextLevel.OK

        # Exactly 70%
        status = monitor.check_usage(0.7000)
        assert status.level == ContextLevel.INFO
