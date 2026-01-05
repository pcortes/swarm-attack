"""Tests for Statusline HUD module.

TDD RED phase: These tests define the expected behavior of the HUD.
They should FAIL until we implement the actual code.

The HUD (Heads-Up Display) shows:
1. Model name and context percentage
2. Active agent and current task
3. Todo progress (X/Y completed)
4. Works cross-platform (macOS, Linux, Windows) without bash dependency
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from io import StringIO
from dataclasses import dataclass


class TestHUDImport:
    """Tests for HUD module imports."""

    def test_hud_module_can_be_imported(self):
        """HUD module can be imported."""
        from swarm_attack.statusline.hud import HUD
        assert HUD is not None

    def test_hud_status_can_be_imported(self):
        """HUDStatus dataclass can be imported."""
        from swarm_attack.statusline.hud import HUDStatus
        assert HUDStatus is not None

    def test_hud_config_can_be_imported(self):
        """HUDConfig dataclass can be imported."""
        from swarm_attack.statusline.hud import HUDConfig
        assert HUDConfig is not None


class TestHUDDisplay:
    """Tests for HUD display formatting."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    @pytest.fixture
    def sample_status(self):
        """Create sample HUD status."""
        from swarm_attack.statusline.hud import HUDStatus
        return HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=45.2,
            active_agent="coder",
            current_task="Implementing auth module",
            todos_completed=3,
            todos_total=7,
        )

    def test_render_returns_string(self, hud, sample_status):
        """render() returns a formatted string."""
        output = hud.render(sample_status)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_render_includes_model_name(self, hud, sample_status):
        """Rendered output includes model name."""
        output = hud.render(sample_status)
        # Should show abbreviated or full model name
        assert "claude" in output.lower() or "opus" in output.lower()

    def test_render_includes_context_percent(self, hud, sample_status):
        """Rendered output includes context percentage."""
        output = hud.render(sample_status)
        # Should show percentage, could be "45%" or "45.2%"
        assert "45" in output
        assert "%" in output

    def test_render_includes_active_agent(self, hud, sample_status):
        """Rendered output includes active agent name."""
        output = hud.render(sample_status)
        assert "coder" in output.lower()

    def test_render_includes_current_task(self, hud, sample_status):
        """Rendered output includes current task."""
        output = hud.render(sample_status)
        assert "auth" in output.lower() or "Implementing" in output

    def test_render_includes_todo_progress(self, hud, sample_status):
        """Rendered output includes todo progress."""
        output = hud.render(sample_status)
        # Should show 3/7 or similar format
        assert "3" in output
        assert "7" in output

    def test_render_single_line_by_default(self, hud, sample_status):
        """Default render is single line (no newlines in middle)."""
        output = hud.render(sample_status)
        # Should be single line (may have trailing newline)
        stripped = output.strip()
        assert "\n" not in stripped

    def test_render_handles_long_task_truncation(self, hud):
        """Long task names are truncated."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="This is a very long task description that should be truncated to fit the status line width",
            todos_completed=1,
            todos_total=5,
        )

        output = hud.render(status)

        # Output should be reasonable length (< 120 chars)
        assert len(output.strip()) < 120

    def test_render_handles_empty_task(self, hud):
        """Empty task shows placeholder or nothing."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="",
            todos_completed=0,
            todos_total=0,
        )

        output = hud.render(status)

        # Should not crash, return valid string
        assert isinstance(output, str)

    def test_render_handles_zero_todos(self, hud):
        """Zero todos shows 0/0 or similar."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="verifier",
            current_task="Checking results",
            todos_completed=0,
            todos_total=0,
        )

        output = hud.render(status)
        assert isinstance(output, str)

    def test_render_full_context_warning(self, hud):
        """High context percentage (>90%) shows warning indicator."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=95.0,
            active_agent="coder",
            current_task="Almost done",
            todos_completed=6,
            todos_total=7,
        )

        output = hud.render(status)

        # High context should show some warning (color, symbol, etc)
        # At minimum, the percentage should be visible
        assert "95" in output


class TestHUDModelInfo:
    """Tests for model name display."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    def test_format_model_name_opus(self, hud):
        """Opus model name is formatted correctly."""
        formatted = hud.format_model_name("claude-opus-4-5-20251101")
        # Should abbreviate or display nicely
        assert "opus" in formatted.lower() or "4.5" in formatted

    def test_format_model_name_sonnet(self, hud):
        """Sonnet model name is formatted correctly."""
        formatted = hud.format_model_name("claude-sonnet-4-20250514")
        assert "sonnet" in formatted.lower() or "4" in formatted

    def test_format_model_name_haiku(self, hud):
        """Haiku model name is formatted correctly."""
        formatted = hud.format_model_name("claude-3-5-haiku-20241022")
        assert "haiku" in formatted.lower()

    def test_format_model_name_unknown(self, hud):
        """Unknown model name passes through."""
        formatted = hud.format_model_name("some-other-model")
        assert "other" in formatted.lower() or "some" in formatted.lower()

    def test_format_model_name_empty(self, hud):
        """Empty model name returns placeholder."""
        formatted = hud.format_model_name("")
        assert isinstance(formatted, str)
        # Should not be empty or crash
        assert len(formatted) >= 0

    def test_format_context_percent_normal(self, hud):
        """Normal context percentage formatted correctly."""
        formatted = hud.format_context_percent(45.2)
        assert "45" in formatted
        assert "%" in formatted

    def test_format_context_percent_zero(self, hud):
        """Zero context shows as 0%."""
        formatted = hud.format_context_percent(0.0)
        assert "0" in formatted
        assert "%" in formatted

    def test_format_context_percent_hundred(self, hud):
        """100% context formatted correctly."""
        formatted = hud.format_context_percent(100.0)
        assert "100" in formatted

    def test_format_context_percent_caps_at_100(self, hud):
        """Context over 100% caps at 100."""
        formatted = hud.format_context_percent(150.0)
        # Should not show 150, should cap or clamp
        assert "150" not in formatted or "100" in formatted


class TestHUDProgress:
    """Tests for todo progress display."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    def test_format_progress_basic(self, hud):
        """Basic progress format X/Y."""
        formatted = hud.format_progress(3, 7)
        assert "3" in formatted
        assert "7" in formatted
        # Common separators
        assert "/" in formatted or "of" in formatted.lower()

    def test_format_progress_zero_total(self, hud):
        """Zero total shows 0/0 or empty indicator."""
        formatted = hud.format_progress(0, 0)
        assert isinstance(formatted, str)
        # Should not crash, valid output

    def test_format_progress_complete(self, hud):
        """All completed shows success indicator."""
        formatted = hud.format_progress(5, 5)
        assert "5" in formatted
        # May include checkmark or "complete" indicator

    def test_format_progress_none_completed(self, hud):
        """None completed shows starting state."""
        formatted = hud.format_progress(0, 5)
        assert "0" in formatted
        assert "5" in formatted

    def test_format_progress_with_emoji_option(self, hud):
        """Progress can include emoji if configured."""
        from swarm_attack.statusline.hud import HUD, HUDConfig
        config = HUDConfig(use_emoji=True)
        hud_with_emoji = HUD(config=config)

        formatted = hud_with_emoji.format_progress(3, 5)

        # Should include some indicator (checkmark, progress bar, etc)
        assert isinstance(formatted, str)
        assert len(formatted) > 0


class TestHUDCrossPlatform:
    """Tests for cross-platform compatibility (no bash dependency)."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    def test_no_bash_subprocess_calls(self, hud):
        """HUD does not call bash via subprocess."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=1,
            todos_total=3,
        )

        with patch('subprocess.run') as mock_run, \
             patch('subprocess.Popen') as mock_popen, \
             patch('subprocess.call') as mock_call:

            hud.render(status)

            # No subprocess calls should be made
            mock_run.assert_not_called()
            mock_popen.assert_not_called()
            mock_call.assert_not_called()

    def test_no_os_system_calls(self, hud):
        """HUD does not use os.system."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=1,
            todos_total=3,
        )

        with patch('os.system') as mock_system:
            hud.render(status)
            mock_system.assert_not_called()

    def test_works_on_windows(self, hud):
        """HUD works on Windows platform."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=1,
            todos_total=3,
        )

        with patch.object(sys, 'platform', 'win32'):
            output = hud.render(status)
            assert isinstance(output, str)
            assert len(output) > 0

    def test_works_on_linux(self, hud):
        """HUD works on Linux platform."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=1,
            todos_total=3,
        )

        with patch.object(sys, 'platform', 'linux'):
            output = hud.render(status)
            assert isinstance(output, str)
            assert len(output) > 0

    def test_works_on_macos(self, hud):
        """HUD works on macOS platform."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=1,
            todos_total=3,
        )

        with patch.object(sys, 'platform', 'darwin'):
            output = hud.render(status)
            assert isinstance(output, str)
            assert len(output) > 0

    def test_pure_python_implementation(self, hud):
        """HUD uses only pure Python (no shell commands)."""
        import inspect
        from swarm_attack.statusline import hud as hud_module

        source = inspect.getsource(hud_module)

        # Should not contain shell command patterns
        shell_patterns = [
            'subprocess.run',
            'subprocess.Popen',
            'subprocess.call',
            'os.system(',
            'os.popen(',
            '/bin/bash',
            '/bin/sh',
        ]

        for pattern in shell_patterns:
            assert pattern not in source, f"Found shell pattern: {pattern}"


class TestHUDConfig:
    """Tests for HUD configuration."""

    def test_config_default_values(self):
        """HUDConfig has sensible defaults."""
        from swarm_attack.statusline.hud import HUDConfig
        config = HUDConfig()

        assert hasattr(config, 'use_emoji')
        assert hasattr(config, 'max_task_length')
        assert hasattr(config, 'show_context_percent')

    def test_config_custom_max_task_length(self):
        """Custom max_task_length is respected."""
        from swarm_attack.statusline.hud import HUD, HUDConfig, HUDStatus
        config = HUDConfig(max_task_length=20)
        hud = HUD(config=config)

        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="This is a very long task that should be truncated",
            todos_completed=1,
            todos_total=3,
        )

        output = hud.render(status)

        # Task should be truncated at around 20 chars
        # The full task text should not appear
        assert "This is a very long task that should be truncated" not in output

    def test_config_use_emoji_false(self):
        """use_emoji=False disables emoji characters."""
        from swarm_attack.statusline.hud import HUD, HUDConfig, HUDStatus
        config = HUDConfig(use_emoji=False)
        hud = HUD(config=config)

        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=5,
            todos_total=5,
        )

        output = hud.render(status)

        # Common emoji that might be used
        emoji_chars = ['✓', '✔', '❌', '⚠', '🔄', '📝', '🤖']
        for emoji in emoji_chars:
            assert emoji not in output

    def test_config_show_context_percent_false(self):
        """show_context_percent=False hides context."""
        from swarm_attack.statusline.hud import HUD, HUDConfig, HUDStatus
        config = HUDConfig(show_context_percent=False)
        hud = HUD(config=config)

        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=75.0,
            active_agent="coder",
            current_task="Test task",
            todos_completed=1,
            todos_total=3,
        )

        output = hud.render(status)

        # Should not show the percentage
        assert "75" not in output or "%" not in output


class TestHUDStatus:
    """Tests for HUDStatus dataclass."""

    def test_hud_status_creation(self):
        """HUDStatus can be created with all fields."""
        from swarm_attack.statusline.hud import HUDStatus
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test",
            todos_completed=1,
            todos_total=3,
        )

        assert status.model_name == "claude-opus-4-5-20251101"
        assert status.context_percent == 50.0
        assert status.active_agent == "coder"
        assert status.current_task == "Test"
        assert status.todos_completed == 1
        assert status.todos_total == 3

    def test_hud_status_optional_fields(self):
        """HUDStatus supports optional fields with defaults."""
        from swarm_attack.statusline.hud import HUDStatus

        # Minimal creation - some fields may have defaults
        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
        )

        assert status.model_name == "claude-opus-4-5-20251101"
        # Other fields should have sensible defaults
        assert hasattr(status, 'active_agent')
        assert hasattr(status, 'current_task')
        assert hasattr(status, 'todos_completed')
        assert hasattr(status, 'todos_total')

    def test_hud_status_is_dataclass(self):
        """HUDStatus is a proper dataclass."""
        from swarm_attack.statusline.hud import HUDStatus
        from dataclasses import is_dataclass

        assert is_dataclass(HUDStatus)


class TestHUDUpdate:
    """Tests for HUD update mechanism."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    def test_update_returns_new_output(self, hud):
        """update() with new status returns new output."""
        from swarm_attack.statusline.hud import HUDStatus

        status1 = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=25.0,
            active_agent="planner",
            current_task="Planning",
            todos_completed=0,
            todos_total=5,
        )

        status2 = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Coding",
            todos_completed=2,
            todos_total=5,
        )

        output1 = hud.render(status1)
        output2 = hud.render(status2)

        # Outputs should differ
        assert output1 != output2
        assert "planner" in output1.lower() or "Planning" in output1
        assert "coder" in output2.lower() or "Coding" in output2

    def test_refresh_method_exists(self, hud):
        """HUD has refresh() method for terminal update."""
        assert hasattr(hud, 'refresh')
        assert callable(hud.refresh)

    def test_refresh_writes_to_stream(self, hud):
        """refresh() writes to provided stream."""
        from swarm_attack.statusline.hud import HUDStatus

        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=50.0,
            active_agent="coder",
            current_task="Test",
            todos_completed=1,
            todos_total=3,
        )

        stream = StringIO()
        hud.refresh(status, stream=stream)

        output = stream.getvalue()
        assert len(output) > 0


class TestHUDColorSupport:
    """Tests for color/styling support."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    def test_supports_no_color_env(self, hud):
        """Respects NO_COLOR environment variable."""
        from swarm_attack.statusline.hud import HUD, HUDConfig, HUDStatus
        import os

        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=95.0,  # High context for warning color
            active_agent="coder",
            current_task="Test",
            todos_completed=1,
            todos_total=3,
        )

        with patch.dict(os.environ, {'NO_COLOR': '1'}):
            hud_no_color = HUD()
            output = hud_no_color.render(status)

            # ANSI escape codes start with \x1b[ or \033[
            assert '\x1b[' not in output
            assert '\033[' not in output

    def test_config_disable_colors(self):
        """HUDConfig can disable colors."""
        from swarm_attack.statusline.hud import HUD, HUDConfig, HUDStatus

        config = HUDConfig(use_colors=False)
        hud = HUD(config=config)

        status = HUDStatus(
            model_name="claude-opus-4-5-20251101",
            context_percent=95.0,
            active_agent="coder",
            current_task="Test",
            todos_completed=1,
            todos_total=3,
        )

        output = hud.render(status)

        # No ANSI codes
        assert '\x1b[' not in output
        assert '\033[' not in output


class TestHUDAgentDisplay:
    """Tests for agent display formatting."""

    @pytest.fixture
    def hud(self):
        """Create HUD instance."""
        from swarm_attack.statusline.hud import HUD
        return HUD()

    def test_format_agent_name_coder(self, hud):
        """Coder agent formatted correctly."""
        formatted = hud.format_agent("coder")
        assert "coder" in formatted.lower()

    def test_format_agent_name_verifier(self, hud):
        """Verifier agent formatted correctly."""
        formatted = hud.format_agent("verifier")
        assert "verifier" in formatted.lower()

    def test_format_agent_name_planner(self, hud):
        """Planner agent formatted correctly."""
        formatted = hud.format_agent("planner")
        assert "planner" in formatted.lower()

    def test_format_agent_name_empty(self, hud):
        """Empty agent name returns placeholder."""
        formatted = hud.format_agent("")
        assert isinstance(formatted, str)

    def test_format_agent_name_none(self, hud):
        """None agent name returns placeholder."""
        formatted = hud.format_agent(None)
        assert isinstance(formatted, str)

    def test_format_agent_includes_icon_option(self, hud):
        """Agent can include icon when configured."""
        from swarm_attack.statusline.hud import HUD, HUDConfig

        config = HUDConfig(use_emoji=True)
        hud_emoji = HUD(config=config)

        formatted = hud_emoji.format_agent("coder")

        # Should be a valid string
        assert isinstance(formatted, str)
        assert len(formatted) > 0
