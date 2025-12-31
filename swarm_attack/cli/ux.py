"""CLI UX utilities for consistent behavior across commands.

Provides:
- Interactive mode detection
- Consistent error formatting
- Semantic exit codes
- Non-interactive fallbacks
"""
from __future__ import annotations

import sys
from typing import Any, Optional, TypeVar

import typer

# Semantic exit codes
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 1      # Bad input, missing files, invalid arguments
EXIT_SYSTEM_ERROR = 2    # API failures, timeouts, internal errors
EXIT_BLOCKED = 3         # Needs human intervention

T = TypeVar("T")


def is_interactive() -> bool:
    """Check if running in interactive terminal.

    Returns True if both stdin and stdout are connected to a tty.
    Returns False in pipes, CI, or when redirected.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def prompt_or_default(
    prompt: str,
    default: T,
    *,
    require_interactive: bool = False,
    type: Optional[type] = None,
) -> T:
    """Prompt user if interactive, otherwise use default.

    Args:
        prompt: The prompt message to display
        default: Default value if non-interactive or user accepts default
        require_interactive: If True, exit with error in non-interactive mode
        type: Type to cast the response to (for typer.prompt)

    Returns:
        User's response or default value

    Raises:
        typer.Exit: If require_interactive=True and not in interactive mode
    """
    if is_interactive():
        return typer.prompt(prompt, default=default, type=type)

    if require_interactive:
        typer.echo(
            format_error(
                "INTERACTIVE_REQUIRED",
                "This command requires interactive input",
                hint="Run in a terminal or provide all required arguments"
            ),
            err=True
        )
        raise typer.Exit(EXIT_USER_ERROR)

    return default


def confirm_or_default(
    prompt: str,
    default: bool = False,
    *,
    require_interactive: bool = False,
) -> bool:
    """Confirm with user if interactive, otherwise use default.

    Args:
        prompt: The confirmation prompt
        default: Default if non-interactive
        require_interactive: If True, exit with error in non-interactive mode

    Returns:
        True if confirmed, False otherwise
    """
    if is_interactive():
        return typer.confirm(prompt, default=default)

    if require_interactive:
        typer.echo(
            format_error(
                "CONFIRMATION_REQUIRED",
                "This action requires confirmation",
                hint="Run in a terminal or use --yes flag"
            ),
            err=True
        )
        raise typer.Exit(EXIT_USER_ERROR)

    return default


def format_error(
    code: str,
    message: str,
    *,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    hint: Optional[str] = None,
) -> str:
    """Format error message consistently.

    Standard format:
        Error: [CODE] Message
          Expected: ...
          Got: ...
          Hint: ...

    Args:
        code: Error code (e.g., "INVALID_INPUT", "NOT_FOUND")
        message: Human-readable error description
        expected: What was expected (optional)
        got: What was received (optional)
        hint: How to fix the issue (optional)

    Returns:
        Formatted error string
    """
    lines = [f"Error: [{code}] {message}"]

    if expected:
        lines.append(f"  Expected: {expected}")
    if got:
        lines.append(f"  Got: {got}")
    if hint:
        lines.append(f"  Hint: {hint}")

    return "\n".join(lines)


def exit_with_error(
    code: str,
    message: str,
    *,
    expected: Optional[str] = None,
    got: Optional[str] = None,
    hint: Optional[str] = None,
    exit_code: int = EXIT_USER_ERROR,
) -> None:
    """Print formatted error and exit.

    Args:
        code: Error code
        message: Error message
        expected: What was expected
        got: What was received
        hint: How to fix
        exit_code: Exit code (default: EXIT_USER_ERROR)
    """
    typer.echo(
        format_error(code, message, expected=expected, got=got, hint=hint),
        err=True
    )
    raise typer.Exit(exit_code)
