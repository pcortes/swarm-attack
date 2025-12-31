"""Backwards-compatible CLI aliases.

This module defines top-level command aliases to maintain backwards compatibility.
For example, `swarm-attack status` works in addition to `swarm-attack feature status`.

Note: This module is imported by cli/app.py after the main app is defined.
"""
from __future__ import annotations

from typing import Optional

import typer

# Import app from cli.app - this works because cli/app.py imports us
# AFTER the app object is created
from swarm_attack.cli.app import app


# =========================================================================
# Backwards-Compatible Top-Level Aliases for Admin Commands
# =========================================================================
# These aliases ensure existing scripts continue to work when calling
# commands like `swarm-attack cleanup` instead of `swarm-attack admin cleanup`


@app.command()
def cleanup(
    feature_id: Optional[str] = typer.Argument(
        None,
        help="Feature to clean up (or all features if omitted).",
    ),
    stale_sessions: bool = typer.Option(
        False,
        "--stale-sessions",
        "-s",
        help="Clean up stale sessions (older than 4 hours).",
    ),
    orphan_locks: bool = typer.Option(
        False,
        "--orphan-locks",
        "-l",
        help="Clean up orphan lock files.",
    ),
    all_cleanup: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Run all cleanup operations.",
    ),
) -> None:
    """Clean up stale sessions and orphan locks."""
    from swarm_attack.cli.admin import cleanup as admin_cleanup
    admin_cleanup(feature_id, stale_sessions, orphan_locks, all_cleanup)


@app.command()
def unlock(
    feature_id: str = typer.Argument(
        ...,
        help="Feature identifier.",
    ),
    issue: int = typer.Option(
        ...,
        "--issue",
        "-i",
        help="Issue number to unlock.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force unlock without confirmation.",
    ),
) -> None:
    """Force-unlock a stuck issue."""
    from swarm_attack.cli.admin import unlock as admin_unlock
    admin_unlock(feature_id, issue, force)


@app.command("reset")
def reset_issue(
    feature_id: str = typer.Argument(
        ...,
        help="Feature identifier.",
    ),
    issue: int = typer.Option(
        ...,
        "--issue",
        "-i",
        help="Issue number to reset.",
    ),
    hard: bool = typer.Option(
        False,
        "--hard",
        help="Hard reset - also delete generated test files.",
    ),
) -> None:
    """Reset an issue to READY state (or BACKLOG with --hard)."""
    from swarm_attack.cli.admin import reset_issue as admin_reset_issue
    admin_reset_issue(feature_id, issue, hard)


@app.command()
def diagnose(
    feature_id: str = typer.Argument(
        ...,
        help="Feature to diagnose.",
    ),
) -> None:
    """Show detailed diagnostics and recovery options for a feature."""
    from swarm_attack.cli.admin import diagnose as admin_diagnose
    admin_diagnose(feature_id)


@app.command()
def recover(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to run recovery for.",
    ),
) -> None:
    """Run recovery flow only - check for interrupted sessions and blocked issues."""
    from swarm_attack.cli.admin import recover as admin_recover
    admin_recover(feature_id)


@app.command()
def unblock(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to unblock.",
    ),
    phase: Optional[str] = typer.Option(
        None,
        "--phase",
        "-p",
        help="Target phase to set (e.g., PRD_READY, SPEC_NEEDS_APPROVAL).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force unblock without verification checks.",
    ),
    clear_locks: bool = typer.Option(
        False,
        "--clear-locks",
        help="Clear ALL issue locks for this feature.",
    ),
) -> None:
    """Unblock a feature that is stuck in BLOCKED state."""
    from swarm_attack.cli.admin import unblock as admin_unblock
    admin_unblock(feature_id, phase, force, clear_locks)


# =========================================================================
# Backwards-Compatible Top-Level Aliases for Feature Commands
# =========================================================================
# These aliases ensure existing scripts continue to work when calling
# commands like `swarm-attack status` instead of `swarm-attack feature status`


@app.command()
def status(
    feature_id: Optional[str] = typer.Argument(
        None,
        help="Feature ID to show detailed status for. If omitted, shows all features.",
    ),
) -> None:
    """Show feature status dashboard or detailed feature status."""
    from swarm_attack.cli.feature import status as feature_status
    feature_status(feature_id)


@app.command()
def events(
    feature_id: str = typer.Argument(..., help="Feature ID to show events for"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of events to show"),
    issue: Optional[int] = typer.Option(None, "--issue", "-i", help="Filter by issue number"),
) -> None:
    """Show event log for a feature."""
    from swarm_attack.cli.feature import events as feature_events
    feature_events(feature_id, limit, issue)


@app.command()
def init(
    feature_id: str = typer.Argument(
        ...,
        help="Unique identifier for the new feature (e.g., 'user-auth', 'dark-mode').",
    ),
) -> None:
    """Initialize a new feature."""
    from swarm_attack.cli.feature import init as feature_init
    feature_init(feature_id)


@app.command("import-spec")
def import_spec(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID for the imported spec.",
    ),
    spec_path: str = typer.Option(
        ...,
        "--spec",
        "-s",
        help="Path to the external spec file to import.",
    ),
    prd_path: Optional[str] = typer.Option(
        None,
        "--prd",
        "-p",
        help="Path to optional PRD file. If not provided, a stub PRD will be generated.",
    ),
    debate: bool = typer.Option(
        True,
        "--debate/--no-debate",
        help="Run the debate pipeline (critic + moderator) after importing.",
    ),
) -> None:
    """Import an external spec and optionally run the debate pipeline."""
    from swarm_attack.cli.feature import import_spec as feature_import_spec
    feature_import_spec(feature_id, spec_path, prd_path, debate)


@app.command()
def run(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to run pipeline for.",
    ),
    issue: Optional[int] = typer.Option(
        None,
        "--issue",
        "-i",
        help="Specific issue number to implement (only for implementation phase).",
    ),
) -> None:
    """Run the appropriate pipeline for a feature based on its phase."""
    from swarm_attack.cli.feature import run as feature_run
    feature_run(feature_id, issue)


@app.command()
def approve(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to approve the spec for.",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Enable auto-approval mode (disable manual mode).",
    ),
    manual: bool = typer.Option(
        False,
        "--manual",
        help="Enable manual mode (require human approval for all decisions).",
    ),
) -> None:
    """Approve a spec that is ready for approval."""
    from swarm_attack.cli.feature import approve as feature_approve
    feature_approve(feature_id, auto, manual)


@app.command()
def reject(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to reject the spec for.",
    ),
    rerun: bool = typer.Option(
        False,
        "--rerun",
        help="Reset phase to PRD_READY to allow re-running the spec pipeline.",
    ),
) -> None:
    """Reject a spec that needs approval."""
    from swarm_attack.cli.feature import reject as feature_reject
    feature_reject(feature_id, rerun)


@app.command()
def greenlight(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to greenlight for implementation.",
    ),
) -> None:
    """Greenlight issues for implementation."""
    from swarm_attack.cli.feature import greenlight as feature_greenlight
    feature_greenlight(feature_id)


@app.command()
def issues(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to create issues for.",
    ),
) -> None:
    """Create GitHub issues from an approved spec."""
    from swarm_attack.cli.feature import issues as feature_issues
    feature_issues(feature_id)


@app.command(name="next")
def next_action(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to determine the next action for.",
    ),
) -> None:
    """Determine and display the next action for a feature."""
    from swarm_attack.cli.feature import next_action as feature_next_action
    feature_next_action(feature_id)


@app.command()
def smart(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to run the smart CLI for.",
    ),
) -> None:
    """Smart CLI with automatic recovery flow."""
    from swarm_attack.cli.feature import smart as feature_smart
    feature_smart(feature_id)
