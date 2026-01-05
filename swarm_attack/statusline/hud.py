"""StatuslineHUD - Heads-Up Display for Claude Code statusline.

This module provides a HUD (Heads-Up Display) that shows:
1. Model name and context percentage
2. Active agent and current task
3. Todo progress (X/Y completed)
4. Works cross-platform (macOS, Linux, Windows) without bash dependency

Key features:
- Pure Python implementation (no subprocess, os.system, or bash)
- Configurable display options (emoji, colors, task truncation)
- Respects NO_COLOR environment variable
- Single-line output for statusline integration
"""

from dataclasses import dataclass, field
from typing import Optional, TextIO
import os
import sys


@dataclass
class HUDConfig:
    """Configuration for HUD display.

    Attributes:
        use_emoji: Whether to include emoji characters (default True)
        use_colors: Whether to use ANSI color codes (default True)
        max_task_length: Maximum task description length before truncation (default 40)
        show_context_percent: Whether to show context percentage (default True)
    """

    use_emoji: bool = True
    use_colors: bool = True
    max_task_length: int = 40
    show_context_percent: bool = True


@dataclass
class HUDStatus:
    """Status information for HUD display.

    Attributes:
        model_name: Name of the Claude model (e.g., "claude-opus-4-5-20251101")
        context_percent: Current context window usage as percentage (0.0-100.0)
        active_agent: Name of the currently active agent (e.g., "coder")
        current_task: Description of the current task
        todos_completed: Number of completed todos
        todos_total: Total number of todos
    """

    model_name: str
    context_percent: float
    active_agent: str = ""
    current_task: str = ""
    todos_completed: int = 0
    todos_total: int = 0


class HUD:
    """Heads-Up Display for Claude Code statusline.

    This class provides a cross-platform HUD that displays model info,
    context usage, agent status, and todo progress. It is pure Python
    and does not use subprocess, os.system, or bash.

    Attributes:
        config: HUDConfig for display options
    """

    def __init__(self, config: Optional[HUDConfig] = None):
        """Initialize the HUD with optional configuration.

        Args:
            config: HUDConfig for display options (uses defaults if None)
        """
        self.config = config or HUDConfig()

        # Check for NO_COLOR environment variable
        if os.environ.get("NO_COLOR"):
            self.config.use_colors = False

    def render(self, status: HUDStatus) -> str:
        """Render the HUD status as a single-line string.

        Args:
            status: HUDStatus containing all display information

        Returns:
            Formatted single-line string for statusline display
        """
        parts = []

        # Model name
        model_str = self.format_model_name(status.model_name)
        parts.append(model_str)

        # Context percentage (if enabled)
        if self.config.show_context_percent:
            context_str = self.format_context_percent(status.context_percent)
            parts.append(context_str)

        # Active agent
        if status.active_agent:
            agent_str = self.format_agent(status.active_agent)
            parts.append(agent_str)

        # Current task (truncated if needed)
        if status.current_task:
            task_str = self._truncate_task(status.current_task)
            parts.append(task_str)

        # Todo progress
        progress_str = self.format_progress(status.todos_completed, status.todos_total)
        if progress_str:
            parts.append(progress_str)

        return " | ".join(parts)

    def refresh(self, status: HUDStatus, stream: Optional[TextIO] = None) -> None:
        """Refresh the HUD display by writing to a stream.

        Args:
            status: HUDStatus containing all display information
            stream: Output stream (defaults to sys.stdout)
        """
        if stream is None:
            stream = sys.stdout

        output = self.render(status)
        stream.write(output)
        stream.write("\n")

    def format_model_name(self, model_name: str) -> str:
        """Format the model name for display.

        Args:
            model_name: Full model name (e.g., "claude-opus-4-5-20251101")

        Returns:
            Formatted model name (e.g., "Opus 4.5")
        """
        if not model_name:
            return "unknown"

        model_lower = model_name.lower()

        # Parse common model patterns
        if "opus" in model_lower:
            if "4-5" in model_lower or "4.5" in model_lower:
                return "Opus 4.5"
            return "Opus"
        elif "sonnet" in model_lower:
            if "4" in model_lower:
                return "Sonnet 4"
            elif "3-5" in model_lower or "3.5" in model_lower:
                return "Sonnet 3.5"
            return "Sonnet"
        elif "haiku" in model_lower:
            if "3-5" in model_lower or "3.5" in model_lower:
                return "Haiku 3.5"
            return "Haiku"

        # Unknown model - return first part
        parts = model_name.split("-")
        if len(parts) > 1:
            return parts[1].capitalize() if parts[1] else model_name
        return model_name

    def format_context_percent(self, percent: float) -> str:
        """Format context percentage for display.

        Args:
            percent: Context usage percentage (0.0-100.0)

        Returns:
            Formatted percentage string (e.g., "45%")
        """
        # Clamp to valid range
        clamped = max(0.0, min(100.0, percent))

        # Format as integer percentage
        return f"{clamped:.0f}%"

    def format_agent(self, agent_name: Optional[str]) -> str:
        """Format agent name for display.

        Args:
            agent_name: Name of the active agent

        Returns:
            Formatted agent string
        """
        if not agent_name:
            return "idle"

        # Capitalize first letter
        formatted = agent_name.strip()
        if formatted:
            formatted = formatted[0].upper() + formatted[1:] if len(formatted) > 1 else formatted.upper()

        return formatted

    def format_progress(self, completed: int, total: int) -> str:
        """Format todo progress for display.

        Args:
            completed: Number of completed todos
            total: Total number of todos

        Returns:
            Formatted progress string (e.g., "3/7")
        """
        if total == 0:
            return "0/0"

        prefix = ""
        suffix = ""

        if self.config.use_emoji:
            if completed == total and total > 0:
                prefix = ""
                suffix = ""
            elif completed == 0:
                prefix = ""
                suffix = ""

        return f"{prefix}{completed}/{total}{suffix}"

    def _truncate_task(self, task: str) -> str:
        """Truncate task description to configured maximum length.

        Args:
            task: Full task description

        Returns:
            Truncated task (with ellipsis if truncated)
        """
        max_len = self.config.max_task_length

        if len(task) <= max_len:
            return task

        # Truncate with ellipsis
        return task[: max_len - 3] + "..."
