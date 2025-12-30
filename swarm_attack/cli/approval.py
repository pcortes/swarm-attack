"""
CLI commands for auto-approval system.

Provides human override commands:
- veto: Revoke an auto-approved item
- manual: Enable manual approval mode
- auto: Re-enable auto-approval mode
- approval-status: Check approval status
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from swarm_attack.cli.common import get_console, get_project_dir, get_config_or_default

# Create sub-app for approval commands
app = typer.Typer(
    name="approval",
    help="Auto-approval management commands",
    add_completion=False,
)

console: Console = get_console()


def _get_state_store():
    """Get state store instance."""
    from swarm_attack.state_store import get_store
    config = get_config_or_default(get_project_dir())
    return get_store(config)


def _get_bug_store():
    """Get bug state store instance."""
    from swarm_attack.bug_state_store import get_bug_store
    return get_bug_store()


@app.command("veto")
def veto_command(
    feature: Optional[str] = typer.Option(None, "--feature", "-f", help="Feature to veto"),
    bug: Optional[str] = typer.Option(None, "--bug", "-b", help="Bug to veto"),
    reason: str = typer.Option(..., "--reason", "-r", help="Reason for the veto"),
) -> None:
    """
    Veto an auto-approved item.

    Use this to revert an auto-approval and require manual review.

    Examples:
        swarm-attack approval veto --feature my-feature --reason "Need architecture review"
        swarm-attack approval veto --bug bug-123 --reason "Too risky for auto-approval"
    """
    if feature and bug:
        console.print("[red]Error: Specify either --feature or --bug, not both[/red]")
        raise typer.Exit(1)

    if not feature and not bug:
        console.print("[red]Error: Must specify --feature or --bug[/red]")
        raise typer.Exit(1)

    try:
        if feature:
            store = _get_state_store()
            store.veto_approval(feature, reason)
            console.print(f"[yellow]Vetoed: {feature}[/yellow]")
            console.print(f"Reason: {reason}")
            console.print("Feature reverted to SPEC_NEEDS_APPROVAL phase.")
        elif bug:
            store = _get_bug_store()
            store.veto_approval(bug, reason)
            console.print(f"[yellow]Vetoed: {bug}[/yellow]")
            console.print(f"Reason: {reason}")
            console.print("Bug reverted to PLANNED phase.")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("manual")
def manual_mode_command(
    feature: Optional[str] = typer.Option(None, "--feature", "-f", help="Feature to set manual mode"),
    all_features: bool = typer.Option(False, "--all", help="Apply to all features"),
) -> None:
    """
    Enable manual approval mode (disable auto-approval).

    When manual mode is enabled, the feature will not be auto-approved
    even if quality thresholds are met.

    Examples:
        swarm-attack approval manual --feature my-feature
        swarm-attack approval manual --all
    """
    if not feature and not all_features:
        console.print("[red]Error: Must specify --feature or --all[/red]")
        raise typer.Exit(1)

    try:
        store = _get_state_store()

        if all_features:
            # Set manual mode for all features
            features = store.list_features()
            for f_id in features:
                store.set_manual_mode(f_id, True)
            console.print(f"[yellow]Manual mode enabled for {len(features)} features[/yellow]")
        elif feature:
            store.set_manual_mode(feature, True)
            console.print(f"[yellow]Manual mode enabled for {feature}[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("auto")
def auto_mode_command(
    feature: Optional[str] = typer.Option(None, "--feature", "-f", help="Feature to set auto mode"),
    all_features: bool = typer.Option(False, "--all", help="Apply to all features"),
) -> None:
    """
    Re-enable auto-approval mode.

    When auto mode is enabled, the feature can be auto-approved
    when quality thresholds are met.

    Examples:
        swarm-attack approval auto --feature my-feature
        swarm-attack approval auto --all
    """
    if not feature and not all_features:
        console.print("[red]Error: Must specify --feature or --all[/red]")
        raise typer.Exit(1)

    try:
        store = _get_state_store()

        if all_features:
            # Set auto mode for all features
            features = store.list_features()
            for f_id in features:
                store.set_manual_mode(f_id, False)
            console.print(f"[green]Auto mode enabled for {len(features)} features[/green]")
        elif feature:
            store.set_manual_mode(feature, False)
            console.print(f"[green]Auto mode enabled for {feature}[/green]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("status")
def approval_status_command(
    feature: str = typer.Argument(..., help="Feature to check"),
) -> None:
    """
    Check approval status for a feature.

    Shows current phase, manual mode status, and last debate scores.

    Examples:
        swarm-attack approval status my-feature
    """
    try:
        store = _get_state_store()
        state = store.load(feature)

        if state is None:
            console.print(f"[red]Feature '{feature}' not found[/red]")
            raise typer.Exit(1)

        console.print(f"[bold]Feature:[/bold] {feature}")
        console.print(f"[bold]Phase:[/bold] {state.phase.name}")

        manual_mode = getattr(state, "manual_mode", False)
        if manual_mode:
            console.print("[yellow]Manual Mode: ENABLED (auto-approval disabled)[/yellow]")
        else:
            console.print("[green]Manual Mode: DISABLED (auto-approval enabled)[/green]")

        # Show debate scores if available
        scores = getattr(state, "debate_scores", [])
        if scores:
            console.print("\n[bold]Recent Debate Scores:[/bold]")
            for i, score in enumerate(scores[-3:], 1):  # Show last 3 rounds
                avg = getattr(score, "average", 0.0)
                console.print(f"  Round {len(scores) - 3 + i}: {avg:.2f}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
