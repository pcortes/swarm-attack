"""Display helpers and formatters for the CLI.

Contains Rich formatting utilities for phases, stages, costs, and feature displays.
This module should NOT import from feature/bug/admin modules to avoid circular imports.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack.models import FeaturePhase, RunState, TaskStage

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.state_store import StateStore

# Phase display names and colors
PHASE_DISPLAY: dict[FeaturePhase, tuple[str, str]] = {
    FeaturePhase.NO_PRD: ("No PRD", "dim"),
    FeaturePhase.PRD_READY: ("PRD Ready", "blue"),
    FeaturePhase.SPEC_IN_PROGRESS: ("Spec In Progress", "yellow"),
    FeaturePhase.SPEC_NEEDS_APPROVAL: ("Spec Needs Approval", "yellow bold"),
    FeaturePhase.SPEC_APPROVED: ("Spec Approved", "green"),
    FeaturePhase.ISSUES_CREATING: ("Creating Issues", "yellow"),
    FeaturePhase.ISSUES_VALIDATING: ("Validating Issues", "yellow"),
    FeaturePhase.ISSUES_NEED_REVIEW: ("Issues Need Review", "yellow bold"),
    FeaturePhase.READY_TO_IMPLEMENT: ("Ready to Implement", "cyan"),
    FeaturePhase.IMPLEMENTING: ("Implementing", "cyan bold"),
    FeaturePhase.COMPLETE: ("Complete", "green bold"),
    FeaturePhase.BLOCKED: ("Review Needed", "yellow bold"),
}

# Task stage display names
STAGE_DISPLAY: dict[TaskStage, tuple[str, str]] = {
    TaskStage.BACKLOG: ("Backlog", "dim"),
    TaskStage.NEEDS_REVISION: ("Needs Revision", "yellow"),
    TaskStage.READY: ("Ready", "cyan"),
    TaskStage.IN_PROGRESS: ("In Progress", "cyan bold"),
    TaskStage.INTERRUPTED: ("Interrupted", "yellow bold"),
    TaskStage.VERIFYING: ("Verifying", "blue"),
    TaskStage.DONE: ("Done", "green"),
    TaskStage.BLOCKED: ("Review Needed", "yellow"),
    TaskStage.SKIPPED: ("Skipped", "magenta"),
}

# Bug phase display names and colors
BUG_PHASE_DISPLAY: dict[str, tuple[str, str]] = {
    "created": ("Created", "dim"),
    "reproducing": ("Reproducing", "yellow"),
    "reproduced": ("Reproduced", "green"),
    "not_reproducible": ("Not Reproducible", "dim"),
    "analyzing": ("Analyzing", "yellow"),
    "analyzed": ("Analyzed", "green"),
    "planning": ("Planning", "yellow"),
    "planned": ("Planned", "cyan bold"),
    "approved": ("Approved", "green"),
    "wont_fix": ("Won't Fix", "dim"),
    "implementing": ("Implementing", "yellow"),
    "verifying": ("Verifying", "yellow"),
    "fixed": ("Fixed", "green bold"),
    "blocked": ("Review Needed", "yellow bold"),
}


def format_phase(phase: FeaturePhase) -> Text:
    """Format a phase enum as colored text."""
    display_name, style = PHASE_DISPLAY.get(phase, (phase.name, "white"))
    return Text(display_name, style=style)


def format_stage(stage: TaskStage) -> Text:
    """Format a task stage enum as colored text."""
    display_name, style = STAGE_DISPLAY.get(stage, (stage.name, "white"))
    return Text(display_name, style=style)


def format_bug_phase(phase_value: str) -> Text:
    """Format a bug phase as colored text."""
    display_name, style = BUG_PHASE_DISPLAY.get(phase_value, (phase_value, "white"))
    return Text(display_name, style=style)


def format_cost(cost_usd: float) -> str:
    """Format cost as a string with dollar sign."""
    if cost_usd == 0:
        return "-"
    return f"${cost_usd:.2f}"


def get_task_summary(state: RunState) -> str:
    """Get a summary of tasks by stage."""
    if not state.tasks:
        return "-"

    done = len(state.done_tasks)
    total = len(state.tasks)
    blocked = len(state.blocked_tasks)
    skipped = len(state.skipped_tasks)

    parts = [f"{done}/{total} done"]
    if blocked > 0:
        parts.append(f"{blocked} blocked")
    if skipped > 0:
        parts.append(f"{skipped} skipped")

    return ", ".join(parts)


def generate_completion_report(state: RunState, feature_id: str) -> str:
    """
    Generate a completion report for a feature.

    Called when no more tasks are available (all done, blocked, or skipped).
    """
    done = state.done_tasks
    blocked = state.blocked_tasks
    skipped = state.skipped_tasks
    total = len(state.tasks)

    # Build lookup for task stages
    task_stages = {t.issue_number: t.stage for t in state.tasks}

    lines = []
    lines.append(f"[bold]Feature Completion Report: {feature_id}[/bold]\n")

    # Summary
    lines.append(f"Total Issues: {total}")
    lines.append(f"Done: {len(done)}")
    if blocked:
        lines.append(f"Blocked: {len(blocked)}")
    if skipped:
        lines.append(f"Skipped: {len(skipped)}")
    lines.append(f"Total Cost: {format_cost(state.cost_total_usd)}")
    lines.append("")

    # Blocked issues need attention - with reasons
    if blocked:
        lines.append("[yellow]Issues needing attention (BLOCKED):[/yellow]")
        for task in blocked:
            lines.append(f"  - #{task.issue_number}: {task.title}")
            if task.blocked_reason:
                lines.append(f"    Reason: [dim]{task.blocked_reason}[/dim]")
        lines.append("")

    # Skipped issues - show which deps are blocked
    if skipped:
        lines.append("[magenta]Issues skipped (dependency blocked):[/magenta]")
        for task in skipped:
            lines.append(f"  - #{task.issue_number}: {task.title}")
            # Show deps with their status
            dep_status = []
            for dep in task.dependencies:
                stage = task_stages.get(dep)
                if stage == TaskStage.BLOCKED:
                    dep_status.append(f"#{dep} BLOCKED")
                elif stage == TaskStage.DONE:
                    dep_status.append(f"#{dep} DONE")
                elif stage == TaskStage.SKIPPED:
                    dep_status.append(f"#{dep} SKIPPED")
                else:
                    dep_status.append(f"#{dep}")
            lines.append(f"    deps: {', '.join(dep_status)}")
        lines.append("")

    # Next steps - more specific
    if blocked or skipped:
        lines.append("[cyan]Next steps:[/cyan]")
        if blocked:
            # Suggest fixing the first blocked issue
            first_blocked = blocked[0]
            lines.append(f"  1. Fix #{first_blocked.issue_number}: {first_blocked.title}")
            if first_blocked.blocked_reason:
                lines.append(f"     ({first_blocked.blocked_reason})")
        lines.append(f"  2. Run: swarm-attack recover {feature_id}")
        lines.append(f"  3. Or retry specific issue: swarm-attack run {feature_id} --issue N")
    else:
        lines.append("[green]All issues completed successfully![/green]")

    return "\n".join(lines)


def get_effective_phase(
    state: RunState,
    config: "SwarmConfig",
    prd_path_func: callable,
) -> FeaturePhase:
    """
    Get the effective phase, checking disk for PRD if needed.

    If state shows NO_PRD but PRD file exists on disk, returns PRD_READY.
    This handles the case where PRD was created outside of swarm-attack.
    """
    from swarm_attack.utils.fs import file_exists

    if state.phase == FeaturePhase.NO_PRD:
        prd_path = prd_path_func(config, state.feature_id)
        if file_exists(prd_path):
            return FeaturePhase.PRD_READY
    return state.phase


def show_all_features(
    store: "StateStore",
    config: "SwarmConfig",
    console: Console,
    prd_path_func: callable,
) -> None:
    """Display table of all features with their phases."""
    feature_ids = store.list_features()

    if not feature_ids:
        console.print(
            Panel(
                "[dim]No features found.[/dim]\n\n"
                "Get started by creating a feature:\n"
                "  [cyan]swarm-attack init <feature-name>[/cyan]",
                title="Swarm Attack Status",
                border_style="dim",
            )
        )
        return

    # Build the table
    table = Table(
        title="Swarm Attack Status",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Feature", style="cyan", no_wrap=True)
    table.add_column("Phase", no_wrap=True)
    table.add_column("Tasks", justify="center")
    table.add_column("Cost", justify="right")
    table.add_column("Updated", style="dim")

    total_cost = 0.0

    for feature_id in sorted(feature_ids):
        state = store.load(feature_id)
        if state is None:
            continue

        total_cost += state.cost_total_usd

        # Format updated_at as relative or short date
        updated = state.updated_at[:10] if state.updated_at else "-"

        # Get effective phase (checks disk for PRD if needed)
        effective_phase = get_effective_phase(state, config, prd_path_func)

        table.add_row(
            feature_id,
            format_phase(effective_phase),
            get_task_summary(state),
            format_cost(state.cost_total_usd),
            updated,
        )

    console.print(table)

    # Show total cost if any
    if total_cost > 0:
        console.print(f"\n[dim]Total cost:[/dim] [yellow]${total_cost:.2f}[/yellow]")


def show_feature_detail(
    store: "StateStore",
    feature_id: str,
    config: "SwarmConfig",
    console: Console,
    prd_path_func: callable,
) -> None:
    """Display detailed status for a specific feature."""
    import typer

    state = store.load(feature_id)

    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Auto-sync state from git for accurate status
    # This ensures completed issues are shown correctly even if state drifted
    synced = store.sync_state_from_git(feature_id)
    if synced:
        console.print(f"[dim]Synced {len(synced)} issue(s) from git history: {synced}[/dim]")
        # Reload state after sync
        state = store.load(feature_id)
        if state is None:
            console.print(f"[red]Error:[/red] State corrupted after git sync.")
            raise typer.Exit(1)

    # Get effective phase (checks disk for PRD if needed)
    effective_phase = get_effective_phase(state, config, prd_path_func)

    # Header panel with feature info
    phase_text = format_phase(effective_phase)

    info_lines = [
        f"[bold]Feature:[/bold] {state.feature_id}",
        "",
        f"[bold]Phase:[/bold] {phase_text}",
        f"[bold]Created:[/bold] {state.created_at[:19].replace('T', ' ')}",
        f"[bold]Updated:[/bold] {state.updated_at[:19].replace('T', ' ')}",
        f"[bold]Total Cost:[/bold] {format_cost(state.cost_total_usd)}",
    ]

    if state.current_session:
        info_lines.append(f"[bold]Active Session:[/bold] {state.current_session}")

    console.print(
        Panel(
            "\n".join(info_lines),
            title=f"Feature: {feature_id}",
            border_style="cyan",
        )
    )

    # Cost breakdown by phase
    if state.cost_by_phase:
        cost_table = Table(
            title="Cost by Phase",
            show_header=True,
            header_style="bold",
        )
        cost_table.add_column("Phase")
        cost_table.add_column("Cost", justify="right")

        for phase_name, cost in sorted(state.cost_by_phase.items()):
            cost_table.add_row(phase_name, format_cost(cost))

        console.print()
        console.print(cost_table)

    # Tasks table
    if state.tasks:
        tasks_table = Table(
            title="Tasks",
            show_header=True,
            header_style="bold",
        )
        tasks_table.add_column("#", justify="right", style="dim")
        tasks_table.add_column("Title", no_wrap=False)
        tasks_table.add_column("Stage", no_wrap=True)
        tasks_table.add_column("Size", justify="center")
        tasks_table.add_column("Deps", justify="center", style="dim")

        for task in state.tasks:
            deps = ",".join(str(d) for d in task.dependencies) if task.dependencies else "-"
            tasks_table.add_row(
                str(task.issue_number),
                task.title,
                format_stage(task.stage),
                task.estimated_size,
                deps,
            )

        console.print()
        console.print(tasks_table)

        # Summary
        done = len(state.done_tasks)
        blocked = len(state.blocked_tasks)
        skipped = len(state.skipped_tasks)
        ready = len(state.ready_tasks)
        total = len(state.tasks)

        summary_parts = [f"[green]{done}[/green]/{total} done"]
        if ready > 0:
            summary_parts.append(f"[cyan]{ready}[/cyan] ready")
        if blocked > 0:
            summary_parts.append(f"[red]{blocked}[/red] blocked")
        if skipped > 0:
            summary_parts.append(f"[magenta]{skipped}[/magenta] skipped")

        console.print(f"\n[dim]Tasks:[/dim] {', '.join(summary_parts)}")
    else:
        console.print("\n[dim]No tasks yet.[/dim]")
