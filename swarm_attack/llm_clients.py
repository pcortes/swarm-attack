"""
Claude Code CLI wrapper for Feature Swarm.

This module provides a Python interface to the Claude Code CLI:
- ClaudeCliRunner class for executing prompts
- JSON output parsing
- Timeout handling with graceful termination
- Cost tracking and logging
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.models import ClaudeResult

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class ClaudeInvocationError(Exception):
    """Raised when Claude CLI invocation fails."""

    def __init__(
        self,
        message: str,
        stderr: str = "",
        returncode: int = -1
    ) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode


class ClaudeTimeoutError(ClaudeInvocationError):
    """Raised when Claude CLI times out."""
    pass


@dataclass
class ClaudeCliRunner:
    """
    Runner for the Claude Code CLI.

    Executes prompts using the Claude Code CLI and parses JSON output.
    """

    config: SwarmConfig
    logger: Optional[SwarmLogger] = None

    def _build_command(
        self,
        prompt: str,
        *,
        max_turns: Optional[int] = None,
        allowed_tools: Optional[list[str]] = None,
        working_dir: Optional[str] = None,
    ) -> list[str]:
        """
        Build the CLI command.

        Args:
            prompt: The prompt to send to Claude.
            max_turns: Maximum conversation turns.
            allowed_tools: List of allowed tools.
            working_dir: Working directory for the command.

        Returns:
            List of command arguments.
        """
        cmd = [
            self.config.claude.binary,
            "--output-format", "json",
            "--max-turns", str(max_turns or self.config.claude.max_turns),
        ]

        # Handle allowed_tools:
        # - None: don't pass --allowedTools (use default tools)
        # - []: pass --allowedTools "" to disable all tools
        # - ["tool1", ...]: pass --allowedTools tool1,tool2,...
        if allowed_tools is not None:
            if allowed_tools:
                cmd.extend(["--allowedTools", ",".join(allowed_tools)])
            else:
                # Empty list means disable all tools
                cmd.extend(["--allowedTools", ""])

        # Use -- separator before positional prompt argument to prevent
        # prompts starting with --- (YAML frontmatter) from being interpreted
        # as command-line options
        cmd.extend(["--", prompt])

        return cmd

    def _parse_output(self, stdout: str) -> dict[str, Any]:
        """
        Parse JSON output from Claude CLI.

        Args:
            stdout: Raw stdout from the CLI.

        Returns:
            Parsed JSON data.

        Raises:
            ClaudeInvocationError: If output is not valid JSON.
        """
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as e:
            raise ClaudeInvocationError(
                f"Failed to parse Claude output as JSON: {e}",
                stderr=stdout[:500]  # Include some of the output for debugging
            )

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info"
    ) -> None:
        """Log an event if logger is configured."""
        if self.logger:
            self.logger.log(event_type, data, level=level)

    def run(
        self,
        prompt: str,
        *,
        max_turns: Optional[int] = None,
        allowed_tools: Optional[list[str]] = None,
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> ClaudeResult:
        """
        Execute a prompt using the Claude CLI.

        Args:
            prompt: The prompt to send to Claude.
            max_turns: Maximum conversation turns (overrides config).
            allowed_tools: List of allowed tools for this invocation.
            working_dir: Working directory (defaults to repo_root).
            timeout: Timeout in seconds (overrides config).

        Returns:
            ClaudeResult with response and metadata.

        Raises:
            ClaudeInvocationError: If the CLI fails.
            ClaudeTimeoutError: If the CLI times out.
        """
        cmd = self._build_command(
            prompt,
            max_turns=max_turns,
            allowed_tools=allowed_tools,
            working_dir=working_dir,
        )

        cwd = working_dir or self.config.repo_root
        timeout_seconds = timeout or self.config.claude.timeout_seconds

        self._log("claude_invocation_start", {
            "prompt_length": len(prompt),
            "max_turns": max_turns or self.config.claude.max_turns,
            "allowed_tools": allowed_tools,
            "timeout": timeout_seconds,
        })

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout_seconds,
            )

            if proc.returncode != 0:
                self._log("claude_invocation_error", {
                    "returncode": proc.returncode,
                    "stderr": proc.stderr[:500] if proc.stderr else "",
                }, level="error")
                raise ClaudeInvocationError(
                    f"Claude CLI exited with code {proc.returncode}",
                    stderr=proc.stderr,
                    returncode=proc.returncode,
                )

            # Parse the JSON output
            data = self._parse_output(proc.stdout)

            # Check for Claude CLI error subtypes (e.g., max_turns exceeded)
            subtype = data.get("subtype", "")
            if subtype.startswith("error_"):
                self._log("claude_invocation_error_subtype", {
                    "subtype": subtype,
                    "num_turns": data.get("num_turns", 0),
                    "cost_usd": data.get("total_cost_usd", 0.0),
                }, level="error")
                raise ClaudeInvocationError(
                    f"Claude CLI returned error: {subtype}",
                    stderr=f"subtype={subtype}, num_turns={data.get('num_turns', 0)}",
                    returncode=0,  # CLI succeeded but Claude hit a limit
                )

            result = ClaudeResult(
                text=data.get("result", ""),
                total_cost_usd=data.get("total_cost_usd", 0.0),
                num_turns=data.get("num_turns", 0),
                duration_ms=data.get("duration_ms", 0),
                session_id=data.get("session_id", ""),
                raw=data,
            )

            self._log("claude_invocation_complete", {
                "cost_usd": result.total_cost_usd,
                "num_turns": result.num_turns,
                "duration_ms": result.duration_ms,
                "session_id": result.session_id,
            })

            return result

        except subprocess.TimeoutExpired:
            self._log("claude_invocation_timeout", {
                "timeout_seconds": timeout_seconds,
            }, level="error")
            raise ClaudeTimeoutError(
                f"Claude CLI timed out after {timeout_seconds} seconds",
                returncode=-1,
            )

    def run_with_context(
        self,
        prompt: str,
        context_files: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> ClaudeResult:
        """
        Execute a prompt with file context.

        Prepends file contents to the prompt for additional context.

        Args:
            prompt: The prompt to send to Claude.
            context_files: List of file paths to include as context.
            **kwargs: Additional arguments passed to run().

        Returns:
            ClaudeResult with response and metadata.
        """
        if not context_files:
            return self.run(prompt, **kwargs)

        context_parts = []
        for file_path in context_files:
            path = Path(file_path)
            if path.exists() and path.is_file():
                try:
                    content = path.read_text()
                    context_parts.append(f"File: {file_path}\n```\n{content}\n```\n")
                except (OSError, UnicodeDecodeError):
                    self._log("context_file_error", {
                        "file": file_path,
                    }, level="warn")

        if context_parts:
            full_prompt = (
                "Context files:\n\n"
                + "\n".join(context_parts)
                + "\n---\n\n"
                + prompt
            )
        else:
            full_prompt = prompt

        return self.run(full_prompt, **kwargs)


# Convenience function for quick invocations
def run_claude(
    prompt: str,
    config: SwarmConfig,
    *,
    max_turns: Optional[int] = None,
    allowed_tools: Optional[list[str]] = None,
    logger: Optional[SwarmLogger] = None,
) -> ClaudeResult:
    """
    Convenience function to run a Claude prompt.

    Args:
        prompt: The prompt to send to Claude.
        config: SwarmConfig with CLI configuration.
        max_turns: Maximum conversation turns.
        allowed_tools: List of allowed tools.
        logger: Optional logger for recording operations.

    Returns:
        ClaudeResult with response and metadata.
    """
    runner = ClaudeCliRunner(config=config, logger=logger)
    return runner.run(prompt, max_turns=max_turns, allowed_tools=allowed_tools)
