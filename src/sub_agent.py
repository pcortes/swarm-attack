"""SubAgentRunner - Spawns sub-agents using Claude CLI.

This module provides:
- SubAgentResult dataclass for capturing spawn results
- SubAgentRunner class for spawning sub-agents with skill loading
- Context injection for placeholder replacement in skill prompts
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Optional, Protocol


class SkillLoaderProtocol(Protocol):
    """Protocol for skill loader interface."""

    def load_skill(self, skill_name: str) -> Any: ...


class SubAgentError(Exception):
    """Raised when a sub-agent operation fails."""

    def __init__(self, message: str, skill_name: str = "") -> None:
        super().__init__(message)
        self.skill_name = skill_name


@dataclass
class SubAgentResult:
    """
    Result from a sub-agent spawn invocation.

    Captures success status, output, cost, and any error.

    Fields:
    - success: bool - Whether the invocation succeeded
    - output: str - The response output from the sub-agent
    - cost_usd: float - Cost in USD (default 0.0)
    - error: Optional[str] - Error message if failed
    """

    success: bool
    output: str
    cost_usd: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "cost_usd": self.cost_usd,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubAgentResult":
        """Deserialize from dictionary."""
        return cls(
            success=data["success"],
            output=data["output"],
            cost_usd=data.get("cost_usd", 0.0),
            error=data.get("error"),
        )


@dataclass
class SubAgentRunner:
    """
    Runner that spawns sub-agents using Claude CLI.

    Executes skill prompts with context injection using the Claude CLI.
    Supports skill loading, placeholder replacement, and JSON output parsing.

    Interface Contract:
    - __init__(self, config, skill_loader) - Initialize with config and skill loader
    - spawn(self, skill_name: str, context: dict, timeout: int = 120) -> SubAgentResult
    - _inject_context(self, prompt: str, context: dict) -> str - Replace placeholders
    """

    config: dict[str, Any]
    skill_loader: Any  # SkillLoaderProtocol

    def _get_binary(self) -> str:
        """Get the Claude binary path from config."""
        claude_config = self.config.get("claude", {})
        return claude_config.get("binary", "claude")

    def _get_default_timeout(self) -> int:
        """Get the default timeout from config."""
        claude_config = self.config.get("claude", {})
        return claude_config.get("timeout_seconds", 120)

    def _get_default_max_turns(self) -> int:
        """Get the default max turns from config."""
        claude_config = self.config.get("claude", {})
        return claude_config.get("max_turns", 5)

    def _inject_context(self, prompt: str, context: dict[str, Any]) -> str:
        """
        Replace placeholders in prompt with context values.

        Uses {placeholder} syntax. Missing keys are left unchanged.

        Args:
            prompt: The prompt template with {placeholders}
            context: Dict mapping placeholder names to values

        Returns:
            Prompt with placeholders replaced by context values
        """
        result = prompt
        for key, value in context.items():
            placeholder = "{" + key + "}"
            result = result.replace(placeholder, str(value))
        return result

    def _build_command(
        self,
        prompt: str,
        max_turns: int,
    ) -> list[str]:
        """
        Build the CLI command for Claude.

        Uses `claude --print PROMPT --output-format json --max-turns N`

        Args:
            prompt: The prompt to send to Claude
            max_turns: Maximum conversation turns

        Returns:
            List of command arguments
        """
        binary = self._get_binary()

        cmd = [
            binary,
            "--print",
            "--output-format", "json",
            "--max-turns", str(max_turns),
            "--",
            prompt,
        ]

        return cmd

    def _parse_output(self, stdout: str) -> tuple[str, float]:
        """
        Parse JSON output from Claude CLI.

        Args:
            stdout: Raw stdout from the CLI

        Returns:
            Tuple of (response_text, cost_usd)
        """
        try:
            data = json.loads(stdout)
            text = data.get("result", "")
            cost = data.get("total_cost_usd", 0.0)
            return text, cost
        except json.JSONDecodeError:
            # Return raw output if not valid JSON
            return stdout.strip(), 0.0

    def spawn(
        self,
        skill_name: str,
        context: dict[str, Any],
        timeout: int = 120,
    ) -> SubAgentResult:
        """
        Spawn a sub-agent to execute a skill.

        Loads the skill, injects context into the prompt, and executes
        via Claude CLI as a subprocess.

        Args:
            skill_name: Name of the skill to load
            context: Dict of context values to inject into the prompt
            timeout: Timeout in seconds (default 120)

        Returns:
            SubAgentResult with success status, output, cost, and any error
        """
        # Load the skill
        try:
            skill = self.skill_loader.load_skill(skill_name)
        except Exception as e:
            return SubAgentResult(
                success=False,
                output="",
                cost_usd=0.0,
                error=f"Failed to load skill '{skill_name}': {str(e)}",
            )

        # Get skill content and metadata
        skill_content = skill.content
        skill_metadata = getattr(skill, "metadata", {}) or {}

        # Inject context into prompt
        prompt = self._inject_context(skill_content, context)

        # Determine max_turns from skill metadata or config
        max_turns = skill_metadata.get("max_turns", self._get_default_max_turns())

        # Build command
        cmd = self._build_command(prompt, max_turns)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Check for errors
            if proc.returncode != 0:
                error_msg = proc.stderr.strip() if proc.stderr else f"Claude CLI failed with exit code {proc.returncode}"
                return SubAgentResult(
                    success=False,
                    output="",
                    cost_usd=0.0,
                    error=error_msg,
                )

            # Parse output
            output_text, cost_usd = self._parse_output(proc.stdout)

            return SubAgentResult(
                success=True,
                output=output_text,
                cost_usd=cost_usd,
                error=None,
            )

        except subprocess.TimeoutExpired:
            return SubAgentResult(
                success=False,
                output="",
                cost_usd=0.0,
                error=f"Timeout after {timeout} seconds",
            )

        except FileNotFoundError:
            binary = self._get_binary()
            return SubAgentResult(
                success=False,
                output="",
                cost_usd=0.0,
                error=f"Claude CLI not found: {binary}",
            )

        except Exception as e:
            return SubAgentResult(
                success=False,
                output="",
                cost_usd=0.0,
                error=f"Unexpected error: {str(e)}",
            )