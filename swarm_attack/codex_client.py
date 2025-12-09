"""
Codex CLI wrapper for Feature Swarm.

This module provides a Python interface to the OpenAI Codex CLI:
- CodexCliRunner class for executing prompts
- JSONL streaming output parsing
- Error classification and handling
- Graceful failure with user notifications

IMPORTANT: Codex CLI has a known bug where it crashes on rate limits
(GitHub issue #690). This client includes defensive handling for this.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

from swarm_attack.errors import (
    CodexAuthError,
    ErrorClassifier,
    LLMError,
    LLMErrorType,
    RateLimitError,
    get_user_action_message,
)

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger


class CodexInvocationError(LLMError):
    """Raised when Codex CLI invocation fails."""
    pass


class CodexTimeoutError(CodexInvocationError):
    """Raised when Codex CLI times out."""

    def __init__(self, message: str, timeout_seconds: int) -> None:
        super().__init__(
            message,
            error_type=LLMErrorType.TIMEOUT,
            recoverable=True,
        )
        self.timeout_seconds = timeout_seconds


@dataclass
class CodexResult:
    """
    Result from a Codex CLI invocation.

    Captures the response text, metadata, and raw output.
    """

    text: str
    thread_id: str = ""
    duration_ms: int = 0
    raw_events: list[dict] = None

    def __post_init__(self):
        if self.raw_events is None:
            self.raw_events = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "thread_id": self.thread_id,
            "duration_ms": self.duration_ms,
            "raw_events": self.raw_events,
        }


@dataclass
class CodexCliRunner:
    """
    Runner for the OpenAI Codex CLI.

    Executes prompts using `codex exec` and parses JSONL output.
    Includes error classification and graceful failure handling.

    IMPORTANT: This runner is designed to handle the Codex rate limit
    crash bug by checkpointing state before execution.
    """

    config: SwarmConfig
    logger: Optional[SwarmLogger] = None
    checkpoint_callback: Optional[Callable[[], None]] = None

    def _build_command(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        sandbox_mode: str = "read-only",
        working_dir: Optional[str] = None,
    ) -> list[str]:
        """
        Build the CLI command for codex exec.

        Args:
            prompt: The prompt to send to Codex
            model: Model to use (e.g., "gpt-5", "gpt-5.1-codex")
            sandbox_mode: Sandbox mode ("read-only", "workspace-write", etc.)
            working_dir: Working directory for the command

        Returns:
            List of command arguments
        """
        binary = getattr(self.config, 'codex', None)
        if binary and hasattr(binary, 'binary'):
            binary = binary.binary
        else:
            binary = "codex"

        cmd = [
            binary,
            "exec",
        ]

        # Add model if specified
        if model:
            cmd.extend(["--model", model])

        # Add sandbox mode
        cmd.extend(["--sandbox", sandbox_mode])

        # Add working directory if specified
        if working_dir:
            cmd.extend(["--cd", working_dir])

        # Skip git repo check - allows running in tmp directories and non-git folders
        cmd.append("--skip-git-repo-check")

        # Use -- separator to prevent prompts starting with --- (YAML frontmatter)
        # from being interpreted as command-line options
        cmd.extend(["--", prompt])

        return cmd

    def _parse_jsonl_output(self, stdout: str) -> tuple[str, str, list[dict]]:
        """
        Parse JSONL streaming output from Codex CLI.

        Codex outputs JSONL events. We need to extract:
        - thread_id from thread.started
        - last_message from turn.completed

        Args:
            stdout: Raw stdout containing JSONL events

        Returns:
            Tuple of (response_text, thread_id, events)
        """
        events = []
        thread_id = ""
        response_text = ""

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue

            try:
                event = json.loads(line)
                events.append(event)

                event_type = event.get("type", "")

                # Extract thread_id
                if event_type == "thread.started":
                    thread_id = event.get("thread_id", "")

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

        return response_text, thread_id, events

    def _log(
        self,
        event_type: str,
        data: Optional[dict] = None,
        level: str = "info",
    ) -> None:
        """Log an event if logger is configured."""
        if self.logger:
            self.logger.log(event_type, data, level=level)

    def _classify_and_raise(
        self,
        stderr: str,
        stdout: str,
        returncode: int,
    ) -> None:
        """
        Classify an error and raise appropriate exception.

        Args:
            stderr: Standard error output
            stdout: Standard output
            returncode: Process return code

        Raises:
            Appropriate LLMError subclass
        """
        error_type = ErrorClassifier.classify_codex_error(
            stderr=stderr,
            stdout=stdout,
            returncode=returncode,
        )

        if error_type == LLMErrorType.AUTH_REQUIRED:
            raise CodexAuthError(
                "Codex authentication required",
                stderr=stderr,
            )

        if error_type == LLMErrorType.RATE_LIMIT:
            raise RateLimitError(
                "Codex rate limit reached",
                stderr=stderr,
            )

        # Default to generic invocation error
        raise CodexInvocationError(
            f"Codex CLI failed (exit {returncode}): {stderr[:200]}",
            error_type=error_type,
            stderr=stderr,
            returncode=returncode,
        )

    def run(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        sandbox_mode: str = "read-only",
        working_dir: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CodexResult:
        """
        Execute a prompt using the Codex CLI.

        IMPORTANT: If a checkpoint_callback is configured, it will be
        called BEFORE execution to save state (protection against
        rate limit crashes).

        Args:
            prompt: The prompt to send to Codex
            model: Model to use (overrides config)
            sandbox_mode: Sandbox mode (default: read-only)
            working_dir: Working directory (defaults to repo_root)
            timeout: Timeout in seconds (overrides config)

        Returns:
            CodexResult with response and metadata

        Raises:
            CodexAuthError: If authentication fails
            RateLimitError: If rate limit is hit
            CodexTimeoutError: If command times out
            CodexInvocationError: For other failures
        """
        # Checkpoint before execution (critical for rate limit crash bug)
        if self.checkpoint_callback:
            try:
                self.checkpoint_callback()
            except Exception as e:
                self._log(
                    "codex_checkpoint_warning",
                    {"error": str(e)},
                    level="warning",
                )

        # Get config values with fallbacks
        codex_config = getattr(self.config, 'codex', None)
        default_model = None
        default_timeout = 120

        if codex_config:
            default_model = getattr(codex_config, 'model', None)
            default_timeout = getattr(codex_config, 'timeout_seconds', 120)

        actual_model = model or default_model
        timeout_seconds = timeout or default_timeout
        cwd = working_dir or self.config.repo_root

        cmd = self._build_command(
            prompt,
            model=actual_model,
            sandbox_mode=sandbox_mode,
            working_dir=working_dir,
        )

        self._log("codex_invocation_start", {
            "prompt_length": len(prompt),
            "model": actual_model,
            "sandbox_mode": sandbox_mode,
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

            # Check for errors first
            if proc.returncode != 0:
                self._log("codex_invocation_error", {
                    "returncode": proc.returncode,
                    "stderr": proc.stderr[:500] if proc.stderr else "",
                }, level="error")

                self._classify_and_raise(
                    stderr=proc.stderr,
                    stdout=proc.stdout,
                    returncode=proc.returncode,
                )

            # Parse the JSONL output
            response_text, thread_id, events = self._parse_jsonl_output(proc.stdout)

            if not response_text:
                # Try to get text from stdout directly if JSONL parsing failed
                # This handles the case where output isn't proper JSONL
                response_text = proc.stdout.strip()

            result = CodexResult(
                text=response_text,
                thread_id=thread_id,
                raw_events=events,
            )

            self._log("codex_invocation_complete", {
                "thread_id": thread_id,
                "response_length": len(response_text),
            })

            return result

        except subprocess.TimeoutExpired:
            self._log("codex_invocation_timeout", {
                "timeout_seconds": timeout_seconds,
            }, level="error")
            raise CodexTimeoutError(
                f"Codex CLI timed out after {timeout_seconds} seconds",
                timeout_seconds=timeout_seconds,
            )

    def run_with_graceful_failure(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> tuple[Optional[CodexResult], Optional[LLMError]]:
        """
        Execute a prompt with graceful error handling.

        Instead of raising exceptions, returns the result or error.
        Useful for pipelines that want to handle errors gracefully.

        Args:
            prompt: The prompt to send to Codex
            **kwargs: Additional arguments passed to run()

        Returns:
            Tuple of (result, error) - one will always be None
        """
        try:
            result = self.run(prompt, **kwargs)
            return result, None
        except LLMError as e:
            self._log("codex_graceful_failure", {
                "error_type": e.error_type.name,
                "requires_user_action": e.requires_user_action,
            }, level="error")
            return None, e

    def print_error_and_stop(self, error: LLMError) -> None:
        """
        Print user-friendly error message and indicate stop.

        Use this when an error requires user action.

        Args:
            error: The error that occurred
        """
        message = get_user_action_message(error)
        print(message)


# Convenience function for quick invocations
def run_codex(
    prompt: str,
    config: SwarmConfig,
    *,
    model: Optional[str] = None,
    logger: Optional[SwarmLogger] = None,
    checkpoint_callback: Optional[Callable[[], None]] = None,
) -> CodexResult:
    """
    Convenience function to run a Codex prompt.

    Args:
        prompt: The prompt to send to Codex
        config: SwarmConfig with CLI configuration
        model: Optional model override
        logger: Optional logger for recording operations
        checkpoint_callback: Optional callback to save state before execution

    Returns:
        CodexResult with response and metadata
    """
    runner = CodexCliRunner(
        config=config,
        logger=logger,
        checkpoint_callback=checkpoint_callback,
    )
    return runner.run(prompt, model=model)
