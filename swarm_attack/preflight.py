"""
Pre-flight checks for Feature Swarm.

This module validates that LLM CLIs are:
- Installed and accessible
- Authenticated (where detectable)
- Ready to use before starting pipelines

The key philosophy is: detect problems early and stop with clear
user instructions, rather than failing mid-pipeline.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from swarm_attack.errors import (
    CLINotFoundError,
    ClaudeAuthError,
    CodexAuthError,
    LLMError,
    LLMErrorType,
    get_user_action_message,
)


@dataclass
class AuthStatus:
    """Status of CLI authentication check."""

    is_authenticated: bool
    email: Optional[str] = None
    error_message: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class PreFlightResult:
    """Result of all pre-flight checks."""

    success: bool
    claude_installed: bool = False
    claude_auth: Optional[AuthStatus] = None
    codex_installed: bool = False
    codex_auth: Optional[AuthStatus] = None
    errors: list[LLMError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def get_user_messages(self) -> list[str]:
        """Get user-friendly error messages for all errors."""
        return [get_user_action_message(e) for e in self.errors]


class PreFlightChecker:
    """
    Validates that LLM CLIs are ready for use.

    Performs checks:
    - CLI binary exists (via shutil.which)
    - Claude auth: quick test invocation
    - Codex auth: codex login status + JWT email extraction
    """

    def __init__(
        self,
        claude_binary: str = "claude",
        codex_binary: str = "codex",
        timeout_seconds: int = 30,
    ) -> None:
        """
        Initialize the pre-flight checker.

        Args:
            claude_binary: Path or name of Claude CLI binary
            codex_binary: Path or name of Codex CLI binary
            timeout_seconds: Timeout for auth checks
        """
        self.claude_binary = claude_binary
        self.codex_binary = codex_binary
        self.timeout_seconds = timeout_seconds

    def check_claude_installed(self) -> bool:
        """Check if Claude CLI is installed."""
        return shutil.which(self.claude_binary) is not None

    def check_codex_installed(self) -> bool:
        """Check if Codex CLI is installed."""
        return shutil.which(self.codex_binary) is not None

    def check_claude_auth(self) -> AuthStatus:
        """
        Check if Claude CLI is authenticated.

        Uses a minimal test invocation since claude doesn't have
        a dedicated auth status command.

        Returns:
            AuthStatus with authentication state
        """
        if not self.check_claude_installed():
            return AuthStatus(
                is_authenticated=False,
                error_message="Claude CLI not installed",
            )

        try:
            # Run a minimal prompt to check auth
            # Using a simple echo-like prompt that should complete quickly
            result = subprocess.run(
                [
                    self.claude_binary,
                    "-p", "respond with just: ok",
                    "--output-format", "json",
                    "--max-turns", "1",
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            # Check for auth-related errors in output
            combined = f"{result.stderr} {result.stdout}".lower()

            # Auth error patterns
            auth_patterns = [
                "unauthorized",
                "not logged in",
                "login required",
                "authentication required",
                "please log in",
                "401",
            ]

            for pattern in auth_patterns:
                if pattern in combined:
                    return AuthStatus(
                        is_authenticated=False,
                        error_message="Authentication required",
                        details={"stderr": result.stderr, "stdout": result.stdout},
                    )

            # Success if we got a valid response
            if result.returncode == 0:
                return AuthStatus(
                    is_authenticated=True,
                    details={"check_method": "test_invocation"},
                )

            # Non-zero exit but no auth pattern - might be other error
            return AuthStatus(
                is_authenticated=False,
                error_message=f"Claude CLI check failed (exit {result.returncode})",
                details={"stderr": result.stderr, "returncode": result.returncode},
            )

        except subprocess.TimeoutExpired:
            return AuthStatus(
                is_authenticated=False,
                error_message="Claude auth check timed out",
                details={"timeout_seconds": self.timeout_seconds},
            )
        except Exception as e:
            return AuthStatus(
                is_authenticated=False,
                error_message=f"Claude auth check failed: {e}",
            )

    def check_codex_auth(self) -> AuthStatus:
        """
        Check if Codex CLI is authenticated.

        Uses `codex login status` and parses JWT for email.

        Returns:
            AuthStatus with authentication state and email if available
        """
        if not self.check_codex_installed():
            return AuthStatus(
                is_authenticated=False,
                error_message="Codex CLI not installed",
            )

        try:
            # Use codex login status command
            result = subprocess.run(
                [self.codex_binary, "login", "status"],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )

            if result.returncode != 0:
                return AuthStatus(
                    is_authenticated=False,
                    error_message="Not logged in to Codex",
                    details={"stderr": result.stderr},
                )

            # Check for "Logged in" in output
            if "logged in" not in result.stdout.lower():
                return AuthStatus(
                    is_authenticated=False,
                    error_message="Not logged in to Codex",
                    details={"stdout": result.stdout},
                )

            # Try to extract email from JWT
            email = self._extract_codex_email()

            return AuthStatus(
                is_authenticated=True,
                email=email,
                details={
                    "status_output": result.stdout.strip(),
                    "email_extracted": email is not None,
                },
            )

        except subprocess.TimeoutExpired:
            return AuthStatus(
                is_authenticated=False,
                error_message="Codex auth check timed out",
            )
        except Exception as e:
            return AuthStatus(
                is_authenticated=False,
                error_message=f"Codex auth check failed: {e}",
            )

    def _extract_codex_email(self) -> Optional[str]:
        """
        Extract email from Codex auth JWT.

        Reads ~/.codex/auth.json and decodes the id_token JWT payload.

        Returns:
            Email address if found, None otherwise
        """
        try:
            auth_path = Path.home() / ".codex" / "auth.json"
            if not auth_path.exists():
                return None

            with open(auth_path) as f:
                auth_data = json.load(f)

            tokens = auth_data.get("tokens", {})
            id_token = tokens.get("id_token")

            if not id_token:
                return None

            # JWT is three base64-encoded parts separated by dots
            # We want the payload (middle part)
            parts = id_token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload (add padding if needed)
            payload_b64 = parts[1]
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_json = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_json)

            return payload.get("email")

        except Exception:
            return None

    def check_codex_token_freshness(self) -> Optional[datetime]:
        """
        Check when Codex token was last refreshed.

        Returns:
            Last refresh datetime if available, None otherwise
        """
        try:
            auth_path = Path.home() / ".codex" / "auth.json"
            if not auth_path.exists():
                return None

            with open(auth_path) as f:
                auth_data = json.load(f)

            last_refresh = auth_data.get("last_refresh")
            if not last_refresh:
                return None

            # Parse ISO format
            return datetime.fromisoformat(last_refresh.replace("Z", "+00:00"))

        except Exception:
            return None

    def check_all(
        self,
        require_claude: bool = True,
        require_codex: bool = True,
    ) -> PreFlightResult:
        """
        Run all pre-flight checks.

        Args:
            require_claude: Whether Claude is required (fail if not ready)
            require_codex: Whether Codex is required (fail if not ready)

        Returns:
            PreFlightResult with all check results
        """
        errors: list[LLMError] = []

        # Check Claude
        claude_installed = self.check_claude_installed()
        claude_auth = None

        if require_claude:
            if not claude_installed:
                errors.append(CLINotFoundError("claude"))
            else:
                claude_auth = self.check_claude_auth()
                if not claude_auth.is_authenticated:
                    errors.append(
                        ClaudeAuthError(
                            claude_auth.error_message or "Claude authentication failed"
                        )
                    )

        # Check Codex
        codex_installed = self.check_codex_installed()
        codex_auth = None

        if require_codex:
            if not codex_installed:
                errors.append(CLINotFoundError("codex"))
            else:
                codex_auth = self.check_codex_auth()
                if not codex_auth.is_authenticated:
                    errors.append(
                        CodexAuthError(
                            codex_auth.error_message or "Codex authentication failed"
                        )
                    )

        return PreFlightResult(
            success=len(errors) == 0,
            claude_installed=claude_installed,
            claude_auth=claude_auth,
            codex_installed=codex_installed,
            codex_auth=codex_auth,
            errors=errors,
        )


def run_preflight_checks(
    require_claude: bool = True,
    require_codex: bool = True,
    claude_binary: str = "claude",
    codex_binary: str = "codex",
) -> PreFlightResult:
    """
    Convenience function to run pre-flight checks.

    Args:
        require_claude: Whether Claude is required
        require_codex: Whether Codex is required
        claude_binary: Claude CLI binary name/path
        codex_binary: Codex CLI binary name/path

    Returns:
        PreFlightResult with check results
    """
    checker = PreFlightChecker(
        claude_binary=claude_binary,
        codex_binary=codex_binary,
    )
    return checker.check_all(
        require_claude=require_claude,
        require_codex=require_codex,
    )


def print_preflight_errors(result: PreFlightResult) -> None:
    """
    Print user-friendly error messages for preflight failures.

    Args:
        result: PreFlightResult to display errors for
    """
    if not result.has_errors:
        print("All pre-flight checks passed.")
        return

    for message in result.get_user_messages():
        print(message)
