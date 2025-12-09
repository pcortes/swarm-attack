"""
Error classification for Feature Swarm LLM clients.

This module provides:
- LLMErrorType enum for categorizing errors
- ErrorClassifier for detecting error types from CLI output
- Custom exception classes with error type information
"""

from __future__ import annotations

import re
from enum import Enum, auto
from typing import Optional


class LLMErrorType(Enum):
    """
    Classification of LLM CLI errors.

    Used to determine appropriate handling strategy (retry, stop, notify user, etc.)
    """

    # Authentication errors - require user action
    AUTH_REQUIRED = auto()      # Not logged in at all
    AUTH_EXPIRED = auto()       # Session expired mid-task

    # Rate limiting - may be recoverable
    RATE_LIMIT = auto()         # Hit usage limits (no retry-after info)
    RATE_LIMIT_TIMED = auto()   # Hit limits with known reset time

    # Server errors - usually recoverable with retry
    SERVER_OVERLOADED = auto()  # 529/503 errors
    SERVER_ERROR = auto()       # Other 5xx errors

    # Client errors
    TIMEOUT = auto()            # Command timed out
    CLI_CRASH = auto()          # CLI crashed unexpectedly
    CLI_NOT_FOUND = auto()      # CLI binary not installed
    JSON_PARSE_ERROR = auto()   # Output not valid JSON

    # Unknown
    UNKNOWN = auto()            # Unclassified error


class LLMError(Exception):
    """
    Base exception for LLM client errors.

    Includes error type classification for handling decisions.
    """

    def __init__(
        self,
        message: str,
        error_type: LLMErrorType = LLMErrorType.UNKNOWN,
        stderr: str = "",
        returncode: int = -1,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.stderr = stderr
        self.returncode = returncode
        self.recoverable = recoverable

    @property
    def requires_user_action(self) -> bool:
        """Check if this error requires user intervention."""
        return self.error_type in (
            LLMErrorType.AUTH_REQUIRED,
            LLMErrorType.AUTH_EXPIRED,
            LLMErrorType.CLI_NOT_FOUND,
        )

    @property
    def should_retry(self) -> bool:
        """Check if this error is worth retrying."""
        return self.error_type in (
            LLMErrorType.RATE_LIMIT,
            LLMErrorType.RATE_LIMIT_TIMED,
            LLMErrorType.SERVER_OVERLOADED,
            LLMErrorType.SERVER_ERROR,
            LLMErrorType.TIMEOUT,
        )


class ClaudeAuthError(LLMError):
    """Raised when Claude Code CLI authentication fails."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(
            message,
            error_type=LLMErrorType.AUTH_REQUIRED,
            stderr=stderr,
            recoverable=False,
        )


class CodexAuthError(LLMError):
    """Raised when Codex CLI authentication fails."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(
            message,
            error_type=LLMErrorType.AUTH_REQUIRED,
            stderr=stderr,
            recoverable=False,
        )


class RateLimitError(LLMError):
    """Raised when rate limit is hit."""

    def __init__(
        self,
        message: str,
        stderr: str = "",
        retry_after_seconds: Optional[int] = None,
    ) -> None:
        error_type = (
            LLMErrorType.RATE_LIMIT_TIMED
            if retry_after_seconds
            else LLMErrorType.RATE_LIMIT
        )
        super().__init__(
            message,
            error_type=error_type,
            stderr=stderr,
            recoverable=True,
        )
        self.retry_after_seconds = retry_after_seconds


class CLINotFoundError(LLMError):
    """Raised when CLI binary is not found."""

    def __init__(self, cli_name: str) -> None:
        super().__init__(
            f"{cli_name} CLI not found. Please install it first.",
            error_type=LLMErrorType.CLI_NOT_FOUND,
            recoverable=False,
        )
        self.cli_name = cli_name


class ErrorClassifier:
    """
    Classifies errors from Claude and Codex CLI output.

    Uses pattern matching on stderr/stdout to determine error type.
    """

    # Claude error patterns
    CLAUDE_AUTH_PATTERNS = [
        r"unauthorized",
        r"not\s+logged\s+in",
        r"login\s+required",
        r"authentication\s+required",
        r"please\s+log\s+in",
        r"401",
    ]

    CLAUDE_RATE_LIMIT_PATTERNS = [
        r"rate.?limit",
        r"usage\s+limit\s+reached",
        r"too\s+many\s+requests",
        r"429",
        r"rate_limit_error",
    ]

    CLAUDE_OVERLOAD_PATTERNS = [
        r"529",
        r"overloaded",
        r"overloaded_error",
        r"503",
        r"service\s+unavailable",
    ]

    # Codex error patterns
    CODEX_AUTH_PATTERNS = [
        r"not\s+logged\s+in",
        r"login\s+required",
        r"invalid\s+session",
        r"session\s+expired",
        r"unauthorized",
        r"authentication",
        r"please\s+run\s+`codex\s+login`",
    ]

    CODEX_RATE_LIMIT_PATTERNS = [
        r"rate.?limit",
        r"rate_limit_exceeded",
        r"too\s+many\s+requests",
        r"429",
    ]

    CODEX_OVERLOAD_PATTERNS = [
        r"503",
        r"529",
        r"5\d\d",
        r"service\s+unavailable",
        r"server\s+error",
    ]

    @classmethod
    def classify_claude_error(
        cls,
        stderr: str,
        stdout: str = "",
        returncode: int = -1,
    ) -> LLMErrorType:
        """
        Classify a Claude CLI error based on output.

        Args:
            stderr: Standard error output from CLI
            stdout: Standard output from CLI
            returncode: Process return code

        Returns:
            LLMErrorType classification
        """
        combined = f"{stderr} {stdout}".lower()

        # Check auth errors first (most important for user action)
        if cls._matches_any(combined, cls.CLAUDE_AUTH_PATTERNS):
            return LLMErrorType.AUTH_REQUIRED

        # Check rate limiting
        if cls._matches_any(combined, cls.CLAUDE_RATE_LIMIT_PATTERNS):
            return LLMErrorType.RATE_LIMIT

        # Check server overload
        if cls._matches_any(combined, cls.CLAUDE_OVERLOAD_PATTERNS):
            return LLMErrorType.SERVER_OVERLOADED

        # Non-zero exit without specific pattern
        if returncode != 0:
            return LLMErrorType.CLI_CRASH

        return LLMErrorType.UNKNOWN

    @classmethod
    def classify_codex_error(
        cls,
        stderr: str,
        stdout: str = "",
        returncode: int = -1,
    ) -> LLMErrorType:
        """
        Classify a Codex CLI error based on output.

        Args:
            stderr: Standard error output from CLI
            stdout: Standard output from CLI
            returncode: Process return code

        Returns:
            LLMErrorType classification
        """
        combined = f"{stderr} {stdout}".lower()

        # Check auth errors first
        if cls._matches_any(combined, cls.CODEX_AUTH_PATTERNS):
            return LLMErrorType.AUTH_REQUIRED

        # Check rate limiting
        if cls._matches_any(combined, cls.CODEX_RATE_LIMIT_PATTERNS):
            return LLMErrorType.RATE_LIMIT

        # Check server overload
        if cls._matches_any(combined, cls.CODEX_OVERLOAD_PATTERNS):
            return LLMErrorType.SERVER_OVERLOADED

        # Non-zero exit without specific pattern
        if returncode != 0:
            return LLMErrorType.CLI_CRASH

        return LLMErrorType.UNKNOWN

    @classmethod
    def _matches_any(cls, text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the given patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    @classmethod
    def create_error(
        cls,
        error_type: LLMErrorType,
        message: str,
        stderr: str = "",
        returncode: int = -1,
    ) -> LLMError:
        """
        Create an appropriate exception for the given error type.

        Args:
            error_type: The classified error type
            message: Human-readable error message
            stderr: Raw stderr output
            returncode: Process return code

        Returns:
            Appropriate LLMError subclass
        """
        if error_type == LLMErrorType.AUTH_REQUIRED:
            return ClaudeAuthError(message, stderr)

        if error_type == LLMErrorType.RATE_LIMIT:
            return RateLimitError(message, stderr)

        if error_type == LLMErrorType.CLI_NOT_FOUND:
            return CLINotFoundError("unknown")

        return LLMError(
            message,
            error_type=error_type,
            stderr=stderr,
            returncode=returncode,
            recoverable=error_type in (
                LLMErrorType.RATE_LIMIT,
                LLMErrorType.RATE_LIMIT_TIMED,
                LLMErrorType.SERVER_OVERLOADED,
                LLMErrorType.SERVER_ERROR,
                LLMErrorType.TIMEOUT,
            ),
        )


def get_user_action_message(error: LLMError) -> str:
    """
    Generate a user-friendly message explaining how to fix the error.

    Args:
        error: The LLM error that occurred

    Returns:
        Formatted message with instructions for the user
    """
    if error.error_type == LLMErrorType.AUTH_REQUIRED:
        if isinstance(error, CodexAuthError):
            return """
╔══════════════════════════════════════════════════════════════╗
║  CODEX CLI AUTHENTICATION REQUIRED                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Feature Swarm needs Codex CLI to be authenticated.          ║
║                                                              ║
║  To fix this, run:                                          ║
║                                                              ║
║    codex login                                               ║
║                                                              ║
║  Select "Sign in with ChatGPT" and log in with your         ║
║  ChatGPT Plus/Pro subscription.                             ║
║                                                              ║
║  Then re-run your command.                                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        else:
            return """
╔══════════════════════════════════════════════════════════════╗
║  CLAUDE CODE AUTHENTICATION REQUIRED                         ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Feature Swarm needs Claude Code CLI to be authenticated.    ║
║                                                              ║
║  To fix this, run:                                          ║
║                                                              ║
║    claude                                                    ║
║                                                              ║
║  This will open the Claude Code CLI. Log in with your       ║
║  Claude Max subscription.                                   ║
║                                                              ║
║  Then re-run your command.                                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

    if error.error_type == LLMErrorType.CLI_NOT_FOUND:
        cli_name = getattr(error, 'cli_name', 'the CLI')
        if 'codex' in cli_name.lower():
            return f"""
╔══════════════════════════════════════════════════════════════╗
║  CODEX CLI NOT INSTALLED                                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Feature Swarm requires the Codex CLI to be installed.       ║
║                                                              ║
║  To install, run one of:                                    ║
║                                                              ║
║    npm i -g @openai/codex                                   ║
║    brew install --cask codex                                ║
║                                                              ║
║  Then authenticate with:                                    ║
║                                                              ║
║    codex login                                               ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        else:
            return f"""
╔══════════════════════════════════════════════════════════════╗
║  CLAUDE CODE CLI NOT INSTALLED                               ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  Feature Swarm requires the Claude Code CLI.                 ║
║                                                              ║
║  To install, run:                                           ║
║                                                              ║
║    npm i -g @anthropic-ai/claude-code                       ║
║                                                              ║
║  Then authenticate by running:                              ║
║                                                              ║
║    claude                                                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

    if error.error_type in (LLMErrorType.RATE_LIMIT, LLMErrorType.RATE_LIMIT_TIMED):
        return """
╔══════════════════════════════════════════════════════════════╗
║  RATE LIMIT REACHED                                          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  You've hit the usage limit for your subscription.           ║
║                                                              ║
║  Options:                                                   ║
║  1. Wait a few minutes and try again                        ║
║  2. Switch to a different account if available              ║
║                                                              ║
║  Your progress has been saved. Re-run your command          ║
║  when ready.                                                ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

    return f"""
╔══════════════════════════════════════════════════════════════╗
║  LLM ERROR OCCURRED                                          ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  An error occurred: {str(error)[:40]:<40} ║
║                                                              ║
║  Error type: {error.error_type.name:<46} ║
║                                                              ║
║  Please check the logs for more details.                    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
