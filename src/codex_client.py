"""
Codex CLI wrapper for COO (Chief Operating Officer).

This module provides a Python interface to the OpenAI Codex CLI,
adapted for COO configuration patterns:
- CodexResult dataclass with success, text, cost_usd, error fields
- CodexCliRunner class for executing prompts
- JSONL streaming output parsing
- Graceful error handling with failure results (no exceptions)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


class Logger(Protocol):
    """Protocol for logger interface."""
    def log(self, event_type: str, data: Optional[dict] = None, level: str = "info") -> None: ...
    def info(self, event_type: str, data: Optional[dict] = None) -> None: ...
    def debug(self, event_type: str, data: Optional[dict] = None) -> None: ...
    def error(self, event_type: str, data: Optional[dict] = None) -> None: ...


@dataclass
class CodexResult:
    """
    Result from a Codex CLI invocation.

    Captures success status, response text, cost, and any error.

    Interface Contract fields:
    - success: bool - Whether the invocation succeeded
    - text: str - The response text from Codex
    - cost_usd: float - Estimated cost in USD (default 0.0)
    - error: Optional[str] - Error message if failed
    """

    success: bool
    text: str
    cost_usd: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "text": self.text,
            "cost_usd": self.cost_usd,
            "error": self.error,
        }


@dataclass
class CodexCliRunner:
    """
    Runner for the OpenAI Codex CLI, adapted for COO configuration.

    Executes prompts using `codex exec` and parses JSONL output.
    Returns CodexResult with success/failure status instead of raising exceptions.

    Interface Contract:
    - __init__(self, config, logger=None) - Initialize with COO config
    - run(self, prompt: str, timeout: int = 300) -> CodexResult - Execute Codex with prompt
    """

    config: dict[str, Any]
    logger: Optional[Any] = None

    def _get_binary(self) -> str:
        """Get the Codex binary path from config."""
        codex_config = self.config.get("codex", {})
        return codex_config.get("binary", "codex")

    def _get_default_timeout(self) -> int:
        """Get the default timeout from config."""
        codex_config = self.config.get("codex", {})
        return codex_config.get("timeout_seconds", 300)

    def _build_command(
        self,
        prompt: str,
        *,
        sandbox_mode: str = "read-only",
    ) -> list[str]:
        """
        Build the CLI command for codex exec.

        Args:
            prompt: The prompt to send to Codex
            sandbox_mode: Sandbox mode ("read-only", "workspace-write", etc.)

        Returns:
            List of command arguments
        """
        binary = self._get_binary()

        cmd = [
            binary,
            "exec",
            "--sandbox", sandbox_mode,
            "--skip-git-repo-check",
            "--", prompt,
        ]

        return cmd

    def _parse_jsonl_output(self, stdout: str) -> str:
        """
        Parse JSONL streaming output from Codex CLI.

        Codex outputs JSONL events. We need to extract the response text
        from turn.completed or item.completed events.

        Args:
            stdout: Raw stdout containing JSONL events

        Returns:
            The extracted response text
        """
        response_text = ""

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                event_type = event.get("type", "")

                # Extract response from turn.completed
                if event_type == "turn.completed":
                    response_text = event.get("last_message", "")

                # Also check item.completed for output
                if event_type == "item.completed":
                    item = event.get("item", {})
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for c in content:
                            if c.get("type") == "output_text":
                                response_text = c.get("text", response_text)

            except json.JSONDecodeError:
                # Skip non-JSON lines
                continue

        return response_text

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self.logger:
            if hasattr(self.logger, "log"):
                self.logger.log(event_type, data, level=level)
            elif level == "info" and hasattr(self.logger, "info"):
                self.logger.info(event_type, data)
            elif level == "debug" and hasattr(self.logger, "debug"):
                self.logger.debug(event_type, data)
            elif level == "error" and hasattr(self.logger, "error"):
                self.logger.error(event_type, data)

    def run(
        self,
        prompt: str,
        timeout: int = 300,
    ) -> CodexResult:
        """
        Execute a prompt using the Codex CLI.

        Args:
            prompt: The prompt to send to Codex
            timeout: Timeout in seconds (default 300)

        Returns:
            CodexResult with success status, response text, and any error
        """
        cmd = self._build_command(prompt)

        self._log("codex_invocation_start", {
            "prompt_length": len(prompt),
            "timeout": timeout,
        })

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Check for errors
            if proc.returncode != 0:
                error_msg = proc.stderr.strip() if proc.stderr else f"Codex CLI failed with exit code {proc.returncode}"
                self._log("codex_invocation_error", {
                    "returncode": proc.returncode,
                    "stderr": error_msg[:500],
                }, level="error")

                return CodexResult(
                    success=False,
                    text="",
                    cost_usd=0.0,
                    error=error_msg,
                )

            # Parse the JSONL output
            response_text = self._parse_jsonl_output(proc.stdout)

            if not response_text:
                # Try to get text from stdout directly if JSONL parsing failed
                response_text = proc.stdout.strip()

            self._log("codex_invocation_complete", {
                "response_length": len(response_text),
            })

            return CodexResult(
                success=True,
                text=response_text,
                cost_usd=0.0,  # Cost tracking not implemented yet
                error=None,
            )

        except subprocess.TimeoutExpired:
            self._log("codex_invocation_timeout", {
                "timeout_seconds": timeout,
            }, level="error")

            return CodexResult(
                success=False,
                text="",
                cost_usd=0.0,
                error=f"Codex CLI timed out after {timeout} seconds",
            )

        except FileNotFoundError:
            binary = self._get_binary()
            error_msg = f"Codex CLI not found: {binary}"
            self._log("codex_cli_not_found", {
                "binary": binary,
            }, level="error")

            return CodexResult(
                success=False,
                text="",
                cost_usd=0.0,
                error=error_msg,
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._log("codex_invocation_unexpected_error", {
                "error": str(e),
            }, level="error")

            return CodexResult(
                success=False,
                text="",
                cost_usd=0.0,
                error=error_msg,
            )


def run_codex(
    prompt: str,
    config: dict[str, Any],
    *,
    timeout: int = 300,
    logger: Optional[Any] = None,
) -> CodexResult:
    """
    Convenience function to run a Codex prompt.

    Args:
        prompt: The prompt to send to Codex
        config: COO config dictionary
        timeout: Timeout in seconds (default 300)
        logger: Optional logger for recording operations

    Returns:
        CodexResult with response and status
    """
    runner = CodexCliRunner(
        config=config,
        logger=logger,
    )
    return runner.run(prompt, timeout=timeout)