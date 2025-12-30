"""Main Typer app definition and routing.

This is the canonical entry point for the CLI. The app, callback, and
sub-app registrations are all defined here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from swarm_attack import __version__
from swarm_attack.cli.common import get_console, set_project_dir

# Create Typer app
app = typer.Typer(
    name="swarm-attack",
    help="Autonomous AI-powered feature development - run from any project directory",
    add_completion=False,
)

# Rich console for output - use singleton from common module
console = get_console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"swarm-attack version {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    project: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Project directory to operate on (default: current directory)",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """
    Swarm Attack - Autonomous feature development orchestrator.

    Automates software development from PRD to shipped code using
    AI-powered agents. Use --project/-p to operate on a different project directory.
    """
    if project:
        # Validate that the project directory exists
        project_path = Path(project)
        if not project_path.is_dir():
            console.print(f"[red]Error: Project directory not found: {project}[/red]")
            raise typer.Exit(1)
        set_project_dir(str(project_path.absolute()))

    # If no subcommand and no --help, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


# =========================================================================
# Sub-App Registration
# =========================================================================

# Import and register feature commands
from swarm_attack.cli.feature import app as feature_app

app.add_typer(feature_app, name="feature")

# Import and register bug commands
from swarm_attack.cli.bug import app as bug_app

app.add_typer(bug_app, name="bug")

# Import and register admin commands
from swarm_attack.cli.admin import app as admin_app

app.add_typer(admin_app, name="admin")

# Import and register chief-of-staff commands
from swarm_attack.cli.chief_of_staff import app as cos_app

app.add_typer(cos_app, name="cos")

# Import and register QA commands
from swarm_attack.cli.qa_commands import app as qa_app

app.add_typer(qa_app, name="qa")

# Import and register approval commands
from swarm_attack.cli.approval import app as approval_app

app.add_typer(approval_app, name="approval")


# =========================================================================
# Entry Point
# =========================================================================


# =========================================================================
# Backwards-Compatible Aliases
# =========================================================================
# Import cli_legacy to register top-level aliases like `swarm-attack status`
# This must come AFTER app and sub-apps are defined
import swarm_attack.cli_legacy  # noqa: F401, E402


def cli_main() -> None:
    """Entry point for the CLI."""
    app()


__all__ = ["app", "cli_main"]
