"""
CLI interface for Swarm Attack.

This module provides the command-line interface using Typer with Rich output:
- `swarm-attack status` - Show all features dashboard
- `swarm-attack status <feature>` - Show detailed feature status
- `swarm-attack init <feature>` - Initialize a new feature
- `swarm-attack run <feature>` - Run the spec debate pipeline
- `swarm-attack smart <feature>` - Smart CLI with recovery flow
- `swarm-attack approve <feature>` - Approve a spec
- `swarm-attack reject <feature>` - Reject a spec
- `swarm-attack --version` - Show version
- `swarm-attack --help` - Show help
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack import __version__
from swarm_attack.config import ConfigError, SwarmConfig, load_config
from swarm_attack.models import FeaturePhase, RunState, TaskRef, TaskStage
from swarm_attack.orchestrator import Orchestrator
from swarm_attack.state_store import StateStore, get_store
from swarm_attack.utils.fs import copy_file, ensure_dir, file_exists, read_file, safe_write

# Create Typer app
app = typer.Typer(
    name="swarm-attack",
    help="Autonomous AI-powered feature development - run from any project directory",
    add_completion=False,
)

# Rich console for output
console = Console()

# Global project directory override (set via --project flag)
_project_dir: Optional[str] = None


def _get_project_dir() -> Optional[str]:
    """Get the project directory override if set."""
    return _project_dir


# Note: The main callback is defined later in the file (search for @app.callback)
# to consolidate --project and --version options in one place

# Phase display names and colors
PHASE_DISPLAY = {
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
STAGE_DISPLAY = {
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


def _format_phase(phase: FeaturePhase) -> Text:
    """Format a phase enum as colored text."""
    display_name, style = PHASE_DISPLAY.get(phase, (phase.name, "white"))
    return Text(display_name, style=style)


def _format_stage(stage: TaskStage) -> Text:
    """Format a task stage enum as colored text."""
    display_name, style = STAGE_DISPLAY.get(stage, (stage.name, "white"))
    return Text(display_name, style=style)


def _format_cost(cost_usd: float) -> str:
    """Format cost as a string with dollar sign."""
    if cost_usd == 0:
        return "-"
    return f"${cost_usd:.2f}"


def _get_task_summary(state: RunState) -> str:
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


def _generate_completion_report(state: RunState, feature_id: str) -> str:
    """
    Generate a completion report for a feature.

    Called when no more tasks are available (all done, blocked, or skipped).
    """
    from .models import TaskStage  # Import for dependency check

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
    lines.append(f"✅ Completed: {len(done)}")
    if blocked:
        lines.append(f"❌ Blocked: {len(blocked)}")
    if skipped:
        lines.append(f"⏭️  Skipped: {len(skipped)}")
    lines.append(f"💰 Total Cost: {_format_cost(state.cost_total_usd)}")
    lines.append("")

    # Blocked issues need attention - with reasons
    if blocked:
        lines.append("[yellow]Issues needing attention (BLOCKED):[/yellow]")
        for task in blocked:
            lines.append(f"  • #{task.issue_number}: {task.title}")
            if task.blocked_reason:
                lines.append(f"    └─ [dim]{task.blocked_reason}[/dim]")
        lines.append("")

    # Skipped issues - show which deps are blocked
    if skipped:
        lines.append("[magenta]Issues skipped (dependency blocked):[/magenta]")
        for task in skipped:
            lines.append(f"  • #{task.issue_number}: {task.title}")
            # Show deps with their status
            dep_status = []
            for dep in task.dependencies:
                stage = task_stages.get(dep)
                if stage == TaskStage.BLOCKED:
                    dep_status.append(f"#{dep} ❌")
                elif stage == TaskStage.DONE:
                    dep_status.append(f"#{dep} ✅")
                elif stage == TaskStage.SKIPPED:
                    dep_status.append(f"#{dep} ⏭️")
                else:
                    dep_status.append(f"#{dep}")
            lines.append(f"    └─ deps: {', '.join(dep_status)}")
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
        lines.append("[green]🎉 All issues completed successfully![/green]")

    return "\n".join(lines)


def _init_swarm_directory(config: SwarmConfig) -> None:
    """Initialize the .swarm directory structure if it doesn't exist."""
    ensure_dir(config.swarm_path)
    ensure_dir(config.state_path)
    ensure_dir(config.sessions_path)
    ensure_dir(config.logs_path)


def _load_config_safe() -> Optional[SwarmConfig]:
    """
    Load config, returning None if not found (allows running without config).

    For status command, we can work with just the .swarm directory.
    Uses the global --project flag if set.
    """
    try:
        return load_config(repo_root=_get_project_dir())
    except ConfigError:
        # No config file - use defaults
        return None


def _get_config_or_default() -> SwarmConfig:
    """Get config or create a default config for basic operations."""
    config = _load_config_safe()
    if config is not None:
        return config

    # Create a minimal default config for basic operations
    from swarm_attack.config import (
        ClaudeConfig,
        GitConfig,
        GitHubConfig,
        SessionConfig,
        SpecDebateConfig,
        TestRunnerConfig,
    )

    # Use project directory override if set, otherwise current directory
    effective_repo_root = _get_project_dir() or "."

    return SwarmConfig(
        repo_root=effective_repo_root,
        specs_dir="specs",
        swarm_dir=".swarm",
        github=GitHubConfig(repo=""),
        claude=ClaudeConfig(),
        spec_debate=SpecDebateConfig(),
        sessions=SessionConfig(),
        tests=TestRunnerConfig(command=""),
        git=GitConfig(),
    )


def _get_effective_phase(state: RunState, config: SwarmConfig) -> FeaturePhase:
    """
    Get the effective phase, checking disk for PRD if needed.

    If state shows NO_PRD but PRD file exists on disk, returns PRD_READY.
    This handles the case where PRD was created outside of swarm-attack.
    """
    if state.phase == FeaturePhase.NO_PRD:
        prd_path = _get_prd_path(config, state.feature_id)
        if file_exists(prd_path):
            return FeaturePhase.PRD_READY
    return state.phase


def _show_all_features(store: StateStore, config: SwarmConfig) -> None:
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
        effective_phase = _get_effective_phase(state, config)

        table.add_row(
            feature_id,
            _format_phase(effective_phase),
            _get_task_summary(state),
            _format_cost(state.cost_total_usd),
            updated,
        )

    console.print(table)

    # Show total cost if any
    if total_cost > 0:
        console.print(f"\n[dim]Total cost:[/dim] [yellow]${total_cost:.2f}[/yellow]")


def _show_feature_detail(store: StateStore, feature_id: str, config: SwarmConfig) -> None:
    """Display detailed status for a specific feature."""
    state = store.load(feature_id)

    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Get effective phase (checks disk for PRD if needed)
    effective_phase = _get_effective_phase(state, config)

    # Header panel with feature info
    phase_text = _format_phase(effective_phase)

    info_lines = [
        f"[bold]Feature:[/bold] {state.feature_id}",
        "",
        f"[bold]Phase:[/bold] {phase_text}",
        f"[bold]Created:[/bold] {state.created_at[:19].replace('T', ' ')}",
        f"[bold]Updated:[/bold] {state.updated_at[:19].replace('T', ' ')}",
        f"[bold]Total Cost:[/bold] {_format_cost(state.cost_total_usd)}",
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
            cost_table.add_row(phase_name, _format_cost(cost))

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
                _format_stage(task.stage),
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
    global _project_dir
    if project:
        # Validate that the project directory exists
        project_path = Path(project)
        if not project_path.is_dir():
            console.print(f"[red]Error: Project directory not found: {project}[/red]")
            raise typer.Exit(1)
        _project_dir = str(project_path.absolute())

    # If no subcommand and no --help, show help
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)


@app.command()
def status(
    feature_id: Optional[str] = typer.Argument(
        None,
        help="Feature ID to show detailed status for. If omitted, shows all features.",
    ),
) -> None:
    """
    Show feature status dashboard or detailed feature status.

    Without arguments, displays a table of all features.
    With a feature ID, displays detailed status for that feature.
    """
    # Get config (or defaults)
    config = _get_config_or_default()

    # Ensure .swarm directory exists
    _init_swarm_directory(config)

    # Get state store
    store = get_store(config)

    if feature_id is None:
        _show_all_features(store, config)
    else:
        _show_feature_detail(store, feature_id, config)


def _get_prd_path(config: SwarmConfig, feature_id: str) -> Path:
    """Get the path to the PRD file for a feature."""
    return Path(config.repo_root) / ".claude" / "prds" / f"{feature_id}.md"


def _get_spec_dir(config: SwarmConfig, feature_id: str) -> Path:
    """Get the spec directory for a feature."""
    return config.specs_path / feature_id


@app.command()
def init(
    feature_id: str = typer.Argument(
        ...,
        help="Unique identifier for the new feature (e.g., 'user-auth', 'dark-mode').",
    ),
) -> None:
    """
    Initialize a new feature.

    Creates the feature in the state store and optionally creates a PRD template.
    If a PRD already exists at .claude/prds/<feature_id>.md, sets phase to PRD_READY.
    """
    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Check if feature already exists
    existing = store.load(feature_id)
    if existing is not None:
        console.print(f"[yellow]Warning:[/yellow] Feature '{feature_id}' already exists.")
        console.print(f"  Phase: {_format_phase(existing.phase)}")
        raise typer.Exit(0)

    # Check if PRD exists
    prd_path = _get_prd_path(config, feature_id)
    prd_exists = file_exists(prd_path)

    # Determine initial phase
    initial_phase = FeaturePhase.PRD_READY if prd_exists else FeaturePhase.NO_PRD

    # Create feature
    store.create_feature(feature_id, initial_phase)

    console.print(f"[green]Created feature:[/green] {feature_id}")

    if prd_exists:
        console.print(f"[dim]PRD found at:[/dim] {prd_path}")
        console.print(f"[dim]Phase:[/dim] {_format_phase(initial_phase)}")
        console.print("\n[cyan]Next step:[/cyan] Run the spec pipeline with:")
        console.print(f"  [cyan]swarm-attack run {feature_id}[/cyan]")
    else:
        # Create PRD template
        prd_dir = prd_path.parent
        ensure_dir(prd_dir)

        prd_template = f"""# PRD: {feature_id}

## Overview
<!-- Brief description of the feature -->

## Problem Statement
<!-- What problem does this feature solve? -->

## Requirements
<!-- List of requirements -->
1.

## Success Criteria
<!-- How do we know when this is complete? -->
-

## Out of Scope
<!-- What is explicitly NOT included -->
-
"""
        safe_write(prd_path, prd_template)

        console.print(f"[dim]Created PRD template at:[/dim] {prd_path}")
        console.print(f"[dim]Phase:[/dim] {_format_phase(initial_phase)}")
        console.print("\n[cyan]Next steps:[/cyan]")
        console.print(f"  1. Edit the PRD at {prd_path}")
        console.print(f"  2. Run: [cyan]swarm-attack run {feature_id}[/cyan]")


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
    """
    Import an external spec and optionally run the debate pipeline.

    This command allows engineers who write specs outside the normal PRD → SpecAuthor
    flow to use the debate pipeline (SpecCritic → SpecModerator) for quality review.

    The imported spec is placed in specs/<feature>/spec-draft.md.
    If no PRD is provided, a stub PRD is generated from the spec overview.

    Examples:
        # Import spec and run debate
        swarm-attack import-spec my-feature --spec ~/my-spec.md

        # Import with existing PRD
        swarm-attack import-spec my-feature --spec ~/my-spec.md --prd ~/my-prd.md

        # Import without debate (just copy)
        swarm-attack import-spec my-feature --spec ~/my-spec.md --no-debate
    """
    import re
    from pathlib import Path

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Validate spec file exists
    spec_file = Path(spec_path).expanduser().resolve()
    if not spec_file.exists():
        console.print(f"[red]Error:[/red] Spec file not found at {spec_file}")
        raise typer.Exit(1)

    # Read spec content
    try:
        spec_content = spec_file.read_text()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to read spec: {e}")
        raise typer.Exit(1)

    # Validate spec has some content
    if len(spec_content.strip()) < 100:
        console.print(f"[red]Error:[/red] Spec file is too short (< 100 chars)")
        raise typer.Exit(1)

    # Check/create feature
    existing = store.load(feature_id)
    if existing is not None and existing.phase not in [FeaturePhase.NO_PRD, FeaturePhase.PRD_READY, FeaturePhase.BLOCKED]:
        console.print(f"[yellow]Warning:[/yellow] Feature '{feature_id}' exists in phase {_format_phase(existing.phase)}")
        console.print("  Use --force to overwrite (not implemented), or choose a different feature ID.")
        raise typer.Exit(1)

    # Handle PRD - either use provided or generate stub
    target_prd_path = _get_prd_path(config, feature_id)
    ensure_dir(target_prd_path.parent)

    if prd_path:
        prd_file = Path(prd_path).expanduser().resolve()
        if not prd_file.exists():
            console.print(f"[red]Error:[/red] PRD file not found at {prd_file}")
            raise typer.Exit(1)
        prd_content = prd_file.read_text()
        safe_write(target_prd_path, prd_content)
        console.print(f"[dim]Copied PRD to:[/dim] {target_prd_path}")
    else:
        # Generate stub PRD from spec
        prd_stub = _generate_prd_stub_from_spec(feature_id, spec_content)
        safe_write(target_prd_path, prd_stub)
        console.print(f"[dim]Generated PRD stub at:[/dim] {target_prd_path}")

    # Copy spec to target location
    target_spec_dir = _get_spec_dir(config, feature_id)
    ensure_dir(target_spec_dir)
    target_spec_path = target_spec_dir / "spec-draft.md"
    safe_write(target_spec_path, spec_content)
    console.print(f"[dim]Imported spec to:[/dim] {target_spec_path}")

    # Create/update feature state
    if existing is None:
        store.create_feature(feature_id, FeaturePhase.SPEC_IN_PROGRESS)
        console.print(f"[green]Created feature:[/green] {feature_id}")
    else:
        existing.update_phase(FeaturePhase.SPEC_IN_PROGRESS)
        store.save(existing)
        console.print(f"[green]Updated feature:[/green] {feature_id}")

    if not debate:
        # Just import, skip debate
        state = store.load(feature_id)
        if state:
            state.update_phase(FeaturePhase.SPEC_NEEDS_APPROVAL)
            store.save(state)

        console.print(
            Panel(
                f"[green]Spec imported successfully![/green]\n\n"
                f"Spec: {target_spec_path}\n"
                f"PRD: {target_prd_path}\n\n"
                f"[cyan]Next step:[/cyan] Review and approve:\n"
                f"  [cyan]swarm-attack approve {feature_id}[/cyan]",
                title="Import Complete",
                border_style="green",
            )
        )
        return

    # Run debate pipeline (critic → moderator)
    console.print()
    console.print(f"[cyan]Running debate pipeline for imported spec...[/cyan]")
    console.print()

    # Set phase to SPEC_IN_PROGRESS before running debate
    state = store.load(feature_id)
    if state:
        state.update_phase(FeaturePhase.SPEC_IN_PROGRESS)
        store.save(state)

    orchestrator = Orchestrator(config, state_store=store)

    # Run debate starting from critic (skip author since we have spec)
    with console.status("[yellow]Running spec debate...[/yellow]"):
        result = orchestrator.run_spec_debate_only(feature_id)

    console.print()

    if result.status == "success":
        console.print(
            Panel(
                f"[green]Spec debate completed successfully![/green]\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n\n"
                f"[cyan]Next step:[/cyan] Review the spec at:\n"
                f"  {target_spec_path}\n\n"
                f"Then approve with:\n"
                f"  [cyan]swarm-attack approve {feature_id}[/cyan]",
                title="Debate Complete",
                border_style="green",
            )
        )
    elif result.status == "stalemate":
        console.print(
            Panel(
                f"[yellow]Spec debate reached stalemate.[/yellow]\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n"
                f"{result.message or ''}\n\n"
                f"Review the spec at: {target_spec_path}",
                title="Debate Stalemate",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)
    elif result.status == "disagreement":
        # Build rejected issues summary
        rejected_summary = ""
        if result.rejected_issues:
            rejected_summary = "\n[bold]Rejected Issues:[/bold]\n"
            for issue in result.rejected_issues[:5]:  # Show first 5
                rejected_summary += f"  - {issue.get('original_issue', 'Unknown')}\n"
                if issue.get("reasoning"):
                    rejected_summary += f"    [dim]Reason: {issue['reasoning'][:80]}...[/dim]\n"
            if len(result.rejected_issues) > 5:
                rejected_summary += f"  ... and {len(result.rejected_issues) - 5} more\n"

        console.print(
            Panel(
                f"[yellow]Spec debate reached disagreement.[/yellow]\n\n"
                f"The architect rejected critic feedback that keeps being raised.\n"
                f"Human review is required to arbitrate.\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n"
                f"{rejected_summary}\n"
                f"Review the spec and dispositions at:\n"
                f"  {target_spec_path}\n"
                f"  specs/{feature_id}/spec-dispositions.json\n\n"
                f"Then approve or reject:\n"
                f"  [cyan]swarm-attack approve {feature_id}[/cyan]\n"
                f"  [cyan]swarm-attack reject {feature_id}[/cyan]",
                title="Disagreement - Human Review Needed",
                border_style="yellow",
            )
        )
        raise typer.Exit(2)  # Different exit code for disagreement
    else:
        console.print(
            Panel(
                f"[red]Spec debate failed.[/red]\n\n"
                f"Error: {result.error}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}",
                title="Debate Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def _generate_prd_stub_from_spec(feature_id: str, spec_content: str) -> str:
    """
    Generate a minimal PRD stub from spec content.

    Extracts the overview/purpose section if present, otherwise creates a minimal stub.
    """
    import re

    # Try to extract overview from spec
    overview_match = re.search(
        r'##?\s*(?:1\.?\s*)?Overview.*?\n(.*?)(?=\n##|\Z)',
        spec_content,
        re.IGNORECASE | re.DOTALL
    )

    if overview_match:
        overview_text = overview_match.group(1).strip()
        # Limit to first 500 chars
        if len(overview_text) > 500:
            overview_text = overview_text[:500] + "..."
    else:
        overview_text = "(Extracted from imported spec)"

    # Try to extract purpose
    purpose_match = re.search(
        r'###?\s*(?:1\.1\.?\s*)?Purpose.*?\n(.*?)(?=\n###|\n##|\Z)',
        spec_content,
        re.IGNORECASE | re.DOTALL
    )

    if purpose_match:
        purpose_text = purpose_match.group(1).strip()
    else:
        purpose_text = overview_text

    return f"""# PRD: {feature_id}

*This PRD was auto-generated from an imported spec.*

## Overview

{purpose_text}

## Requirements

(See imported spec for detailed requirements)

## Success Criteria

(See imported spec for success criteria)

## Notes

This PRD was generated to support the spec debate pipeline for an externally-authored spec.
The full specification can be found in the spec file.
"""


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
    """
    Run the appropriate pipeline for a feature based on its phase.

    For PRD_READY/SPEC_IN_PROGRESS: Runs the spec debate pipeline.
    For READY_TO_IMPLEMENT/IMPLEMENTING: Runs the implementation pipeline.
    """
    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        console.print(f"  Create it with: [cyan]swarm-attack init {feature_id}[/cyan]")
        raise typer.Exit(1)

    # Determine which pipeline to run based on phase
    spec_phases = [
        FeaturePhase.NO_PRD,
        FeaturePhase.PRD_READY,
        FeaturePhase.SPEC_IN_PROGRESS,
    ]
    impl_phases = [
        FeaturePhase.READY_TO_IMPLEMENT,
        FeaturePhase.IMPLEMENTING,
    ]

    if state.phase in spec_phases:
        _run_spec_pipeline(config, store, state, feature_id)
    elif state.phase in impl_phases:
        _run_implementation(config, store, state, feature_id, issue)
    elif state.phase == FeaturePhase.SPEC_APPROVED:
        console.print(f"[yellow]Feature is in SPEC_APPROVED phase.[/yellow]")
        console.print(f"  Run 'swarm-attack issues {feature_id}' to create issues first.")
        raise typer.Exit(1)
    elif state.phase == FeaturePhase.ISSUES_NEED_REVIEW:
        console.print(f"[yellow]Feature has issues awaiting review.[/yellow]")
        console.print(f"  Run 'swarm-attack greenlight {feature_id}' to approve issues first.")
        raise typer.Exit(1)
    elif state.phase == FeaturePhase.COMPLETE:
        console.print(f"[green]Feature is already complete![/green]")
        raise typer.Exit(0)
    elif state.phase == FeaturePhase.BLOCKED:
        console.print(f"[red]Feature is blocked and needs human intervention.[/red]")
        console.print(f"  Check status with: swarm-attack status {feature_id}")
        raise typer.Exit(1)
    else:
        console.print(f"[yellow]Feature is in phase: {_format_phase(state.phase)}[/yellow]")
        console.print("  Cannot run pipeline in this phase.")
        raise typer.Exit(1)


def _run_spec_pipeline(
    config: SwarmConfig,
    store: StateStore,
    state: RunState,
    feature_id: str,
) -> None:
    """Run the spec debate pipeline."""
    # Check PRD exists
    prd_path = _get_prd_path(config, feature_id)
    if not file_exists(prd_path):
        console.print(f"[red]Error:[/red] PRD not found at {prd_path}")
        console.print("  Create the PRD file before running the spec pipeline.")
        raise typer.Exit(1)

    # Update phase to PRD_READY if it was NO_PRD
    if state.phase == FeaturePhase.NO_PRD:
        state.update_phase(FeaturePhase.PRD_READY)
        store.save(state)

    console.print(f"[cyan]Starting spec pipeline for:[/cyan] {feature_id}")
    console.print(f"[dim]PRD:[/dim] {prd_path}")
    console.print()

    import time
    start_time = time.time()

    # Heartbeat state for long operations
    heartbeat_stop = threading.Event()
    heartbeat_start_time: list[float] = []  # Use list to allow mutation in closure
    heartbeat_operation: list[str] = []

    def heartbeat_thread():
        """Background thread that prints elapsed time every 60 seconds."""
        while not heartbeat_stop.is_set():
            heartbeat_stop.wait(60)  # Wait 60 seconds or until stopped
            if not heartbeat_stop.is_set() and heartbeat_start_time:
                elapsed = int(time.time() - heartbeat_start_time[0])
                minutes = elapsed // 60
                seconds = elapsed % 60
                op = heartbeat_operation[0] if heartbeat_operation else "Processing"
                console.print(f"[dim]   Still {op.lower()}... ({minutes}m {seconds}s elapsed)[/dim]")

    def start_heartbeat(operation: str):
        """Start the heartbeat timer."""
        heartbeat_start_time.clear()
        heartbeat_start_time.append(time.time())
        heartbeat_operation.clear()
        heartbeat_operation.append(operation)
        heartbeat_stop.clear()

    def stop_heartbeat():
        """Stop the heartbeat timer."""
        heartbeat_stop.set()
        heartbeat_start_time.clear()
        heartbeat_operation.clear()

    # Start heartbeat thread
    hb_thread = threading.Thread(target=heartbeat_thread, daemon=True)
    hb_thread.start()

    # Progress callback for real-time output
    def on_progress(event: str, data: dict) -> None:
        if event == "author_start":
            console.print("[yellow]-> Generating spec draft...[/yellow]")
            start_heartbeat("generating")
        elif event == "author_complete":
            stop_heartbeat()
            spec_path = data.get("spec_path", "")
            cost = data.get("cost_usd", 0)
            console.print(f"[green]   Wrote spec-draft.md[/green] (${cost:.2f})")
        elif event == "critic_start":
            round_num = data.get("round", 1)
            console.print(f"[yellow]-> Running critic review (round {round_num})...[/yellow]")
            start_heartbeat("reviewing")
        elif event == "critic_complete":
            stop_heartbeat()
            rec = data.get("recommendation", "")
            scores = data.get("scores", {})
            cost = data.get("cost_usd", 0)
            avg_score = sum(scores.values()) / len(scores) if scores else 0
            console.print(f"[green]   Review complete[/green] (avg: {avg_score:.2f}, ${cost:.2f})")
        elif event == "moderator_start":
            round_num = data.get("round", 1)
            console.print(f"[yellow]-> Debate round {round_num}...[/yellow]")
            start_heartbeat("thinking")
        elif event == "moderator_complete":
            stop_heartbeat()
            accepted = data.get("accepted", 0)
            rejected = data.get("rejected", 0)
            cost = data.get("cost_usd", 0)
            console.print(f"[green]   Round complete[/green] ({accepted} accepted, {rejected} rejected, ${cost:.2f})")

    # Run the orchestrator with progress callback
    orchestrator = Orchestrator(config, state_store=store, progress_callback=on_progress)
    result = orchestrator.run_spec_pipeline(feature_id)

    # Calculate and display elapsed time
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    console.print()
    console.print(f"[dim]Duration:[/dim] {minutes}m {seconds}s")

    if result.status == "success":
        console.print(
            Panel(
                f"[green]Spec pipeline completed successfully![/green]\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n\n"
                f"[cyan]Next step:[/cyan] Review the spec at:\n"
                f"  specs/{feature_id}/spec-draft.md\n\n"
                f"Then approve with:\n"
                f"  [cyan]swarm-attack approve {feature_id}[/cyan]",
                title="Pipeline Complete",
                border_style="green",
            )
        )
    elif result.status == "stalemate":
        console.print(
            Panel(
                f"[yellow]Spec pipeline reached stalemate.[/yellow]\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n"
                f"{result.message or ''}\n\n"
                "The spec is not improving. Human intervention may be needed.\n"
                f"Review the spec at: specs/{feature_id}/spec-draft.md",
                title="Pipeline Stalemate",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)
    elif result.status == "disagreement":
        # Build rejected issues summary
        rejected_summary = ""
        if result.rejected_issues:
            rejected_summary = "\n[bold]Rejected Issues:[/bold]\n"
            for issue in result.rejected_issues[:5]:
                rejected_summary += f"  - {issue.get('original_issue', 'Unknown')}\n"
                if issue.get("reasoning"):
                    rejected_summary += f"    [dim]Reason: {issue['reasoning'][:80]}...[/dim]\n"
            if len(result.rejected_issues) > 5:
                rejected_summary += f"  ... and {len(result.rejected_issues) - 5} more\n"

        console.print(
            Panel(
                f"[yellow]Spec pipeline reached disagreement.[/yellow]\n\n"
                f"The architect rejected critic feedback that keeps being raised.\n"
                f"Human review is required to arbitrate.\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n"
                f"{rejected_summary}\n"
                f"Review the spec and dispositions at:\n"
                f"  specs/{feature_id}/spec-draft.md\n"
                f"  specs/{feature_id}/spec-dispositions.json\n\n"
                f"Then approve or reject:\n"
                f"  [cyan]swarm-attack approve {feature_id}[/cyan]\n"
                f"  [cyan]swarm-attack reject {feature_id}[/cyan]",
                title="Disagreement - Human Review Needed",
                border_style="yellow",
            )
        )
        raise typer.Exit(2)
    elif result.status == "timeout":
        console.print(
            Panel(
                f"[yellow]Spec pipeline reached max rounds.[/yellow]\n\n"
                f"Rounds: {result.rounds_completed}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}\n"
                f"Scores: {result.final_scores}\n\n"
                f"Review the spec at: specs/{feature_id}/spec-draft.md",
                title="Pipeline Timeout",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)
    else:
        # Failure
        console.print(
            Panel(
                f"[red]Spec pipeline failed.[/red]\n\n"
                f"Error: {result.error}\n"
                f"Cost: {_format_cost(result.total_cost_usd)}",
                title="Pipeline Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def _run_implementation(
    config: SwarmConfig,
    store: StateStore,
    state: RunState,
    feature_id: str,
    issue_number: Optional[int] = None,
) -> None:
    """Run the implementation pipeline for an issue."""
    from swarm_attack.session_manager import SessionManager

    # Update phase to IMPLEMENTING if it was READY_TO_IMPLEMENT
    if state.phase == FeaturePhase.READY_TO_IMPLEMENT:
        state.update_phase(FeaturePhase.IMPLEMENTING)
        store.save(state)

    console.print(f"[cyan]Starting implementation for:[/cyan] {feature_id}")
    if issue_number:
        console.print(f"[dim]Issue:[/dim] #{issue_number}")
    else:
        console.print(f"[dim]Issue:[/dim] (auto-select next available)")
    console.print()

    # Create session manager and orchestrator
    session_manager = SessionManager(config, store)
    orchestrator = Orchestrator(config, state_store=store)

    # Inject session manager into orchestrator
    orchestrator._session_manager = session_manager

    with console.status("[yellow]Running implementation...[/yellow]"):
        result = orchestrator.run_issue_session(feature_id, issue_number)

    # Display results
    console.print()

    if result.status == "success":
        console.print(
            Panel(
                f"[green]Implementation completed successfully![/green]\n\n"
                f"Issue: #{result.issue_number}\n"
                f"Tests Written: {result.tests_written}\n"
                f"Tests Passed: {result.tests_passed}\n"
                f"Commits: {', '.join(result.commits) if result.commits else 'None'}\n"
                f"Cost: {_format_cost(result.cost_usd)}\n"
                f"Retries: {result.retries}\n\n"
                f"[cyan]Next step:[/cyan] Run again to implement next issue:\n"
                f"  [cyan]swarm-attack run {feature_id}[/cyan]",
                title="Implementation Complete",
                border_style="green",
            )
        )
    elif result.status == "blocked":
        console.print(
            Panel(
                f"[yellow]Implementation blocked after max retries.[/yellow]\n\n"
                f"Issue: #{result.issue_number}\n"
                f"Tests Written: {result.tests_written}\n"
                f"Tests Passed: {result.tests_passed}\n"
                f"Tests Failed: {result.tests_failed}\n"
                f"Retries: {result.retries}\n"
                f"Cost: {_format_cost(result.cost_usd)}\n\n"
                f"Error: {result.error}\n\n"
                f"[dim]Issue marked as blocked. Run 'swarm-attack recover {feature_id}' for options.[/dim]",
                title="Implementation Blocked",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)
    elif result.error and "No issue available" in result.error:
        # No more tasks - show completion report
        # Reload state to get latest (including newly skipped tasks)
        state = store.load(feature_id)
        if state:
            report = _generate_completion_report(state, feature_id)
            console.print(
                Panel(
                    report,
                    title="Feature Progress Report",
                    border_style="cyan",
                )
            )

            # Check if feature is complete
            if len(state.done_tasks) == len(state.tasks):
                state.update_phase(FeaturePhase.COMPLETE)
                store.save(state)
        else:
            console.print("[yellow]No more issues available to work on.[/yellow]")
    else:
        # Failed
        console.print(
            Panel(
                f"[red]Implementation failed.[/red]\n\n"
                f"Issue: #{result.issue_number}\n"
                f"Error: {result.error}\n"
                f"Cost: {_format_cost(result.cost_usd)}",
                title="Implementation Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


@app.command()
def approve(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to approve the spec for.",
    ),
) -> None:
    """
    Approve a spec that is ready for approval.

    Copies spec-draft.md to spec-final.md and updates the phase
    to SPEC_APPROVED.
    """
    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Check phase
    if state.phase != FeaturePhase.SPEC_NEEDS_APPROVAL:
        console.print(
            f"[yellow]Warning:[/yellow] Feature is in phase '{_format_phase(state.phase)}', "
            f"not SPEC_NEEDS_APPROVAL."
        )
        console.print("  Proceeding anyway...")

    # Check spec-draft.md exists
    spec_dir = _get_spec_dir(config, feature_id)
    draft_path = spec_dir / "spec-draft.md"
    final_path = spec_dir / "spec-final.md"

    if not file_exists(draft_path):
        console.print(f"[red]Error:[/red] Spec draft not found at {draft_path}")
        raise typer.Exit(1)

    # Copy draft to final
    draft_content = read_file(draft_path)
    safe_write(final_path, draft_content)

    # Update phase using StateStore.update_phase for atomic operation
    # This loads fresh state, updates, and saves in one operation
    state = store.update_phase(feature_id, FeaturePhase.SPEC_APPROVED)

    # Verify the save by re-reading the state file
    verified_state = store.load(feature_id)
    if verified_state is None or verified_state.phase != FeaturePhase.SPEC_APPROVED:
        console.print(
            f"[red]Warning:[/red] Phase verification failed! "
            f"Expected SPEC_APPROVED but file shows "
            f"'{_format_phase(verified_state.phase) if verified_state else 'None'}'."
        )
        console.print(
            "[yellow]This may indicate a race condition with a background process.[/yellow]"
        )
        console.print(
            f"  Retrying save with fresh state..."
        )
        # Retry: load fresh, update, save
        fresh_state = store.load(feature_id)
        if fresh_state:
            fresh_state.update_phase(FeaturePhase.SPEC_APPROVED)
            store.save(fresh_state)
            # Verify again
            final_state = store.load(feature_id)
            if final_state and final_state.phase == FeaturePhase.SPEC_APPROVED:
                console.print("[green]Retry successful![/green]")
                state = final_state
            else:
                console.print(
                    "[red]Retry failed. Please stop background processes and try again.[/red]"
                )
                raise typer.Exit(1)

    console.print(f"[green]Spec approved![/green]")
    console.print(f"[dim]Final spec:[/dim] {final_path}")
    console.print(f"[dim]Phase:[/dim] {_format_phase(state.phase)}")


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
    """
    Reject a spec that needs approval.

    Without --rerun, keeps the current state (you can manually edit and re-approve).
    With --rerun, resets phase to PRD_READY to allow running the pipeline again.
    """
    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    if rerun:
        # Reset to PRD_READY
        state.update_phase(FeaturePhase.PRD_READY)
        store.save(state)

        console.print(f"[yellow]Spec rejected.[/yellow] Phase reset to PRD_READY.")
        console.print(f"\n[cyan]To re-run the spec pipeline:[/cyan]")
        console.print(f"  [cyan]feature-swarm run {feature_id}[/cyan]")
    else:
        # Keep current state
        console.print(f"[yellow]Spec rejected.[/yellow] Current state preserved.")
        console.print(f"[dim]Phase:[/dim] {_format_phase(state.phase)}")
        console.print(f"\n[dim]Options:[/dim]")
        console.print(f"  - Edit the spec and re-approve: [cyan]feature-swarm approve {feature_id}[/cyan]")
        console.print(f"  - Re-run the pipeline: [cyan]feature-swarm reject {feature_id} --rerun[/cyan]")


@app.command()
def greenlight(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to greenlight for implementation.",
    ),
) -> None:
    """
    Greenlight issues for implementation.

    After issues have been created and reviewed, use this command to
    approve them and move to the implementation phase.
    """
    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Check phase - should be ISSUES_NEED_REVIEW or SPEC_APPROVED (if issues were created)
    valid_phases = [FeaturePhase.ISSUES_NEED_REVIEW, FeaturePhase.SPEC_APPROVED]
    if state.phase not in valid_phases:
        console.print(
            f"[yellow]Warning:[/yellow] Feature is in phase '{_format_phase(state.phase)}', "
            f"expected ISSUES_NEED_REVIEW or SPEC_APPROVED."
        )
        console.print("  Proceeding anyway...")

    # Check if issues.json exists
    issues_path = config.specs_path / feature_id / "issues.json"
    if not issues_path.exists():
        console.print(f"[red]Error:[/red] No issues found at {issues_path}")
        console.print("  Run 'swarm-attack issues {feature_id}' first to create issues.")
        raise typer.Exit(1)

    # Load issues.json and populate tasks in state
    import json
    try:
        issues_content = read_file(issues_path)
        issues_data = json.loads(issues_content)
        issues_list = issues_data.get("issues", [])

        # Clear existing tasks and load from issues.json
        state.tasks = []
        for issue in issues_list:
            # Determine initial stage based on dependencies
            deps = issue.get("dependencies", [])
            initial_stage = TaskStage.READY if not deps else TaskStage.BACKLOG

            task = TaskRef(
                issue_number=issue.get("order", 0),
                stage=initial_stage,
                title=issue.get("title", "Untitled"),
                dependencies=deps,
                estimated_size=issue.get("estimated_size", "medium"),
            )
            state.tasks.append(task)

        console.print(f"[dim]Loaded {len(state.tasks)} tasks from issues.json[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load issues: {e}")
        raise typer.Exit(1)

    # Update phase to READY_TO_IMPLEMENT
    state.update_phase(FeaturePhase.READY_TO_IMPLEMENT)
    store.save(state)

    console.print(f"[green]Issues greenlighted![/green]")
    console.print(f"[dim]Phase:[/dim] {_format_phase(state.phase)}")
    console.print(f"\n[cyan]Next step:[/cyan] Run implementation with:")
    console.print(f"  [cyan]swarm-attack run {feature_id}[/cyan]")


@app.command()
def issues(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to create issues for.",
    ),
) -> None:
    """
    Create GitHub issues from an approved spec.

    Reads the spec-final.md and generates implementable GitHub issues
    with titles, descriptions, acceptance criteria, and dependencies.
    """
    from swarm_attack.agents import IssueCreatorAgent, IssueValidatorAgent

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        console.print(f"  Create it with: [cyan]swarm-attack init {feature_id}[/cyan]")
        raise typer.Exit(1)

    # Check spec-final.md exists
    spec_path = config.specs_path / feature_id / "spec-final.md"
    if not spec_path.exists():
        console.print(f"[red]Error:[/red] Approved spec not found at {spec_path}")
        console.print("  Run 'swarm-attack approve {feature_id}' first to approve the spec.")
        raise typer.Exit(1)

    # Check phase
    if state.phase != FeaturePhase.SPEC_APPROVED:
        console.print(
            f"[yellow]Warning:[/yellow] Feature is in phase '{_format_phase(state.phase)}', "
            f"expected SPEC_APPROVED."
        )
        console.print("  Proceeding anyway...")

    console.print(f"[cyan]Creating issues for:[/cyan] {feature_id}")
    console.print(f"[dim]Spec:[/dim] {spec_path}")
    console.print()

    # Update phase to ISSUES_CREATING
    state.update_phase(FeaturePhase.ISSUES_CREATING)
    store.save(state)

    # Run IssueCreatorAgent
    issue_creator = IssueCreatorAgent(config, state_store=store)

    with console.status("[yellow]Creating issues from spec...[/yellow]"):
        creator_result = issue_creator.run({"feature_id": feature_id})

    if not creator_result.success:
        console.print(
            Panel(
                f"[red]Issue creation failed.[/red]\n\n"
                f"Error: {creator_result.errors[0] if creator_result.errors else 'Unknown error'}\n"
                f"Cost: {_format_cost(creator_result.cost_usd)}",
                title="Issue Creation Failed",
                border_style="red",
            )
        )
        state.update_phase(FeaturePhase.BLOCKED)
        store.save(state)
        raise typer.Exit(1)

    issues_count = creator_result.output.get("count", 0)
    console.print(f"[green]Created {issues_count} issues[/green]")

    # Update phase to ISSUES_VALIDATING
    state.update_phase(FeaturePhase.ISSUES_VALIDATING)
    store.save(state)

    # Run IssueValidatorAgent
    issue_validator = IssueValidatorAgent(config, state_store=store)

    with console.status("[yellow]Validating issues...[/yellow]"):
        validator_result = issue_validator.run({"feature_id": feature_id})

    total_cost = creator_result.cost_usd + validator_result.cost_usd

    if not validator_result.success:
        console.print(
            Panel(
                f"[red]Issue validation failed.[/red]\n\n"
                f"Error: {validator_result.errors[0] if validator_result.errors else 'Unknown error'}\n"
                f"Cost: {_format_cost(total_cost)}",
                title="Issue Validation Failed",
                border_style="red",
            )
        )
        state.update_phase(FeaturePhase.BLOCKED)
        store.save(state)
        raise typer.Exit(1)

    # Update phase to ISSUES_NEED_REVIEW
    state.update_phase(FeaturePhase.ISSUES_NEED_REVIEW)
    state.add_cost(total_cost, "ISSUES")
    store.save(state)

    # Display results
    is_valid = validator_result.output.get("valid", False)
    summary = validator_result.output.get("summary", "")
    problems = validator_result.output.get("problems", [])

    if is_valid:
        console.print(
            Panel(
                f"[green]Issues created and validated successfully![/green]\n\n"
                f"Issues: {issues_count}\n"
                f"Cost: {_format_cost(total_cost)}\n\n"
                f"[cyan]Next step:[/cyan] Review issues at:\n"
                f"  specs/{feature_id}/issues.json\n\n"
                f"Then greenlight with:\n"
                f"  [cyan]swarm-attack greenlight {feature_id}[/cyan]",
                title="Issues Ready",
                border_style="green",
            )
        )
    else:
        # Show validation problems
        problem_lines = "\n".join(
            f"  - [{p.get('severity', 'warning')}] Issue #{p.get('issue_order', '?')}: {p.get('description', 'Unknown')}"
            for p in problems[:5]  # Show first 5 problems
        )
        if len(problems) > 5:
            problem_lines += f"\n  ... and {len(problems) - 5} more"

        console.print(
            Panel(
                f"[yellow]Issues created but have validation warnings.[/yellow]\n\n"
                f"Issues: {issues_count}\n"
                f"Summary: {summary}\n"
                f"Cost: {_format_cost(total_cost)}\n\n"
                f"Problems:\n{problem_lines}\n\n"
                f"[cyan]Next step:[/cyan] Review issues at:\n"
                f"  specs/{feature_id}/issues.json\n\n"
                f"Then greenlight with:\n"
                f"  [cyan]swarm-attack greenlight {feature_id}[/cyan]",
                title="Issues Need Review",
                border_style="yellow",
            )
        )


@app.command()
def next(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to determine the next action for.",
    ),
) -> None:
    """
    Determine and display the next action for a feature.

    Uses the smart state machine to analyze the current state and
    determine what should happen next.
    """
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_machine import (
        StateMachine,
        StateMachineError,
        ActionType,
    )

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)
    session_manager = SessionManager(config, store)
    sm = StateMachine(config, store, session_manager)

    try:
        action = sm.get_next_action(feature_id)
    except StateMachineError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Display action info based on type
    action_styles = {
        ActionType.AWAIT_PRD: ("yellow", "Waiting for PRD"),
        ActionType.RUN_SPEC_PIPELINE: ("cyan", "Run Spec Pipeline"),
        ActionType.AWAIT_SPEC_APPROVAL: ("yellow", "Awaiting Spec Approval"),
        ActionType.RUN_ISSUE_PIPELINE: ("cyan", "Run Issue Pipeline"),
        ActionType.AWAIT_ISSUE_GREENLIGHT: ("yellow", "Awaiting Issue Greenlight"),
        ActionType.SELECT_ISSUE: ("cyan", "Select Issue"),
        ActionType.RESUME_SESSION: ("yellow", "Resume Session"),
        ActionType.RUN_IMPLEMENTATION: ("cyan", "Run Implementation"),
        ActionType.COMPLETE: ("green", "Complete"),
        ActionType.AWAIT_HUMAN_HELP: ("red", "Needs Human Help"),
    }

    style, action_name = action_styles.get(
        action.action_type, ("white", action.action_type.name)
    )

    # Build the output panel
    lines = [
        f"[bold]Feature:[/bold] {action.feature_id}",
        f"[bold]Action:[/bold] [{style}]{action_name}[/{style}]",
    ]

    if action.issue_number is not None:
        lines.append(f"[bold]Issue:[/bold] #{action.issue_number}")

    if action.session_id is not None:
        lines.append(f"[bold]Session:[/bold] {action.session_id}")

    if action.message:
        lines.append("")
        lines.append(f"[dim]{action.message}[/dim]")

    # Add suggested next command
    command_suggestions = {
        ActionType.AWAIT_PRD: f"Create PRD at .claude/prds/{feature_id}.md",
        ActionType.RUN_SPEC_PIPELINE: f"swarm-attack run {feature_id}",
        ActionType.AWAIT_SPEC_APPROVAL: f"swarm-attack approve {feature_id}",
        ActionType.RUN_ISSUE_PIPELINE: f"swarm-attack issues {feature_id}",
        ActionType.AWAIT_ISSUE_GREENLIGHT: f"swarm-attack greenlight {feature_id}",
        ActionType.SELECT_ISSUE: f"swarm-attack run {feature_id}",
        ActionType.RESUME_SESSION: f"swarm-attack run {feature_id}",
        ActionType.RUN_IMPLEMENTATION: f"swarm-attack run {feature_id}",
        ActionType.COMPLETE: "All done!",
        ActionType.AWAIT_HUMAN_HELP: "Review the feature status and resolve blockers",
    }

    suggestion = command_suggestions.get(action.action_type)
    if suggestion:
        lines.append("")
        lines.append(f"[cyan]Next step:[/cyan] {suggestion}")

    console.print(
        Panel(
            "\n".join(lines),
            title="Next Action",
            border_style=style,
        )
    )


@app.command()
def smart(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to run the smart CLI for.",
    ),
) -> None:
    """
    Smart CLI with automatic recovery flow.

    Checks for interrupted sessions and blocked issues before proceeding.
    On startup:
    1. Detects interrupted sessions and offers recovery options
    2. Checks for blocked issues that may need attention
    3. Determines the next action using the state machine

    Recovery options for interrupted sessions:
    - Resume: Continue from last checkpoint
    - Backup & restart: Git stash changes, start fresh
    - Skip: Mark issue blocked, move to next
    """
    from swarm_attack.cli_recovery import (
        check_blocked_issues,
        check_interrupted_sessions,
        display_blocked_issues,
        display_recovery_options,
        handle_backup_restart,
        handle_resume,
        handle_skip,
        offer_blocked_issue_retry,
    )
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_machine import (
        ActionType,
        StateMachine,
        StateMachineError,
    )

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)
    session_manager = SessionManager(config, store)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        console.print(f"  Create it with: [cyan]swarm-attack init {feature_id}[/cyan]")
        raise typer.Exit(1)

    # =========================================================================
    # Step 1: Check for interrupted sessions
    # =========================================================================
    interrupted = check_interrupted_sessions(feature_id, config, store)

    if interrupted:
        for session in interrupted:
            choice = display_recovery_options(session, config)

            if choice == "resume":
                result = handle_resume(session, config, store, session_manager)
                console.print(f"\n[green]Resuming session {result['session_id']}[/green]")
                console.print(f"  Restarting from: {result['resume_from']}")
                # In a full implementation, this would call the orchestrator
                # to resume the session from the determined agent
                console.print("\n[dim]Session resumed. Orchestrator would continue from here.[/dim]")
                return

            elif choice == "backup":
                result = handle_backup_restart(session, config, store, session_manager)
                console.print(f"\n[yellow]Backed up and reset.[/yellow]")
                console.print(f"  Issue #{result['issue_number']} ready for fresh start.")
                # Continue to normal flow after backup

            elif choice == "skip":
                result = handle_skip(session, config, store, session_manager)
                console.print(f"\n[yellow]Skipped issue #{result['skipped_issue']}[/yellow]")
                console.print("  Issue marked as blocked. Continuing to next issue...")
                # Continue checking for more interrupted sessions or proceed

    # =========================================================================
    # Step 2: Check for blocked issues
    # =========================================================================
    blocked = check_blocked_issues(feature_id, config, store)

    if blocked:
        display_blocked_issues(blocked, config)

        # Offer to retry blocked issues
        for task in blocked:
            if offer_blocked_issue_retry(task, config):
                # Mark as ready
                state = store.load(feature_id)
                if state:
                    for t in state.tasks:
                        if t.issue_number == task.issue_number:
                            t.stage = TaskStage.READY
                            break
                    store.save(state)
                console.print(f"[green]Issue #{task.issue_number} marked as ready.[/green]")

    # =========================================================================
    # Step 3: Determine next action using state machine
    # =========================================================================
    sm = StateMachine(config, store, session_manager)

    try:
        action = sm.get_next_action(feature_id)
    except StateMachineError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Display action info based on type
    action_styles = {
        ActionType.AWAIT_PRD: ("yellow", "Waiting for PRD"),
        ActionType.RUN_SPEC_PIPELINE: ("cyan", "Run Spec Pipeline"),
        ActionType.AWAIT_SPEC_APPROVAL: ("yellow", "Awaiting Spec Approval"),
        ActionType.RUN_ISSUE_PIPELINE: ("cyan", "Run Issue Pipeline"),
        ActionType.AWAIT_ISSUE_GREENLIGHT: ("yellow", "Awaiting Issue Greenlight"),
        ActionType.SELECT_ISSUE: ("cyan", "Select Issue"),
        ActionType.RESUME_SESSION: ("yellow", "Resume Session"),
        ActionType.RUN_IMPLEMENTATION: ("cyan", "Run Implementation"),
        ActionType.COMPLETE: ("green", "Complete"),
        ActionType.AWAIT_HUMAN_HELP: ("red", "Needs Human Help"),
    }

    style, action_name = action_styles.get(
        action.action_type, ("white", action.action_type.name)
    )

    # Build the output panel
    lines = [
        f"[bold]Feature:[/bold] {action.feature_id}",
        f"[bold]Action:[/bold] [{style}]{action_name}[/{style}]",
    ]

    if action.issue_number is not None:
        lines.append(f"[bold]Issue:[/bold] #{action.issue_number}")

    if action.session_id is not None:
        lines.append(f"[bold]Session:[/bold] {action.session_id}")

    if action.message:
        lines.append("")
        lines.append(f"[dim]{action.message}[/dim]")

    console.print(
        Panel(
            "\n".join(lines),
            title="Smart CLI - Next Action",
            border_style=style,
        )
    )


@app.command()
def recover(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to run recovery for.",
    ),
) -> None:
    """
    Run recovery flow only - check for interrupted sessions and blocked issues.

    This command checks for:
    1. Spec pipeline blocked states (timeout after success)
    2. Interrupted sessions that need recovery
    3. Blocked issues that may need attention

    Use this to manually trigger recovery without running the full smart CLI.
    """
    from swarm_attack.cli_recovery import (
        check_blocked_issues,
        check_interrupted_sessions,
        check_spec_pipeline_blocked,
        display_blocked_issues,
        display_recovery_options,
        display_spec_recovery_options,
        handle_backup_restart,
        handle_resume,
        handle_skip,
        handle_spec_retry,
        handle_spec_unblock,
        offer_blocked_issue_retry,
    )
    from swarm_attack.session_manager import SessionManager

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)
    session_manager = SessionManager(config, store)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Check for spec pipeline blocked state first
    if state.phase == FeaturePhase.BLOCKED:
        spec_recovery = check_spec_pipeline_blocked(feature_id, config, store)

        if spec_recovery and spec_recovery.get("files_found", {}).get("spec_draft"):
            console.print(f"[yellow]Feature is blocked - checking spec pipeline state...[/yellow]\n")

            choice = display_spec_recovery_options(spec_recovery, config)

            if choice == "unblock":
                result = handle_spec_unblock(feature_id, config, store)
                if result["success"]:
                    console.print(f"\n[green]Feature unblocked![/green]")
                    console.print(f"  Phase: {result['old_phase']} → {result['new_phase']}")
                    console.print(f"\n[cyan]Next step:[/cyan] swarm-attack approve {feature_id}")
                else:
                    console.print(f"\n[red]Failed to unblock:[/red] {result.get('error')}")
                return

            elif choice == "retry":
                result = handle_spec_retry(feature_id, config, store)
                if result["success"]:
                    console.print(f"\n[yellow]Feature reset to PRD_READY.[/yellow]")
                    console.print(f"\n[cyan]Next step:[/cyan] {result['next_step']}")
                else:
                    console.print(f"\n[red]Failed to reset:[/red] {result.get('error')}")
                return

            elif choice == "skip":
                console.print("\n[dim]Feature left in BLOCKED state.[/dim]")
                return

    # Check for interrupted sessions
    interrupted = check_interrupted_sessions(feature_id, config, store)

    if interrupted:
        console.print(f"[yellow]Found {len(interrupted)} interrupted session(s).[/yellow]\n")

        for session in interrupted:
            choice = display_recovery_options(session, config)

            if choice == "resume":
                result = handle_resume(session, config, store, session_manager)
                console.print(f"\n[green]Session {result['session_id']} resumed.[/green]")
                console.print(f"  Restart from: {result['resume_from']}")

            elif choice == "backup":
                result = handle_backup_restart(session, config, store, session_manager)
                console.print(f"\n[yellow]Session backed up and reset.[/yellow]")
                console.print(f"  Issue #{result['issue_number']} ready for fresh start.")

            elif choice == "skip":
                result = handle_skip(session, config, store, session_manager)
                console.print(f"\n[yellow]Issue #{result['skipped_issue']} skipped and blocked.[/yellow]")
    else:
        console.print("[green]No interrupted sessions found.[/green]\n")

    # Check for blocked issues
    blocked = check_blocked_issues(feature_id, config, store)

    if blocked:
        display_blocked_issues(blocked, config)

        for task in blocked:
            if offer_blocked_issue_retry(task, config):
                state = store.load(feature_id)
                if state:
                    for t in state.tasks:
                        if t.issue_number == task.issue_number:
                            t.stage = TaskStage.READY
                            break
                    store.save(state)
                console.print(f"[green]Issue #{task.issue_number} marked as ready.[/green]")
    else:
        console.print("[green]No blocked issues found.[/green]")


@app.command()
def unblock(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to unblock.",
    ),
    phase: str = typer.Option(
        None,
        "--phase",
        "-p",
        help="Target phase to set (e.g., PRD_READY, SPEC_NEEDS_APPROVAL). If not specified, auto-detects based on files.",
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
        help="Clear ALL issue locks for this feature. Use when locks are stale after process interruption.",
    ),
) -> None:
    """
    Unblock a feature that is stuck in BLOCKED state.

    This command analyzes the feature's files to determine the appropriate
    recovery action. It handles cases like:
    - Spec pipeline timeout after successful completion
    - Failed spec debate that needs retry
    - Implementation issues that need attention
    - Stale issue locks after Ctrl+C or process crash

    Use --phase to force a specific target phase, or let the command
    auto-detect based on file analysis.

    Use --clear-locks to force-clear all issue locks when they persist
    after process interruption (Ctrl+C, kill, crash).
    """
    from swarm_attack.cli_recovery import (
        check_spec_pipeline_blocked,
        handle_spec_retry,
        handle_spec_unblock,
    )
    from swarm_attack.session_manager import SessionManager

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)

    # Handle --clear-locks flag
    if clear_locks:
        session_manager = SessionManager(config, store)
        cleared = session_manager.clear_all_locks(feature_id)
        if cleared:
            console.print(f"[green]Cleared {len(cleared)} lock(s) for feature '{feature_id}':[/green]")
            for issue_num in cleared:
                console.print(f"  - Issue #{issue_num}")
        else:
            console.print(f"[dim]No locks found for feature '{feature_id}'[/dim]")
        return

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Check if feature is actually blocked
    if state.phase != FeaturePhase.BLOCKED:
        console.print(f"[yellow]Feature is not blocked.[/yellow]")
        console.print(f"  Current phase: {_format_phase(state.phase)}")
        if not force:
            raise typer.Exit(0)

    # If phase specified, use it directly
    if phase:
        phase_upper = phase.upper()
        result = handle_spec_unblock(feature_id, config, store, phase_upper)

        if result["success"]:
            console.print(f"[green]Feature unblocked![/green]")
            console.print(f"  Phase: {result['old_phase']} → {result['new_phase']}")
        else:
            console.print(f"[red]Failed to unblock:[/red] {result.get('error')}")
            raise typer.Exit(1)
        return

    # Auto-detect appropriate phase based on file analysis
    spec_recovery = check_spec_pipeline_blocked(feature_id, config, store)

    if spec_recovery is None:
        console.print(f"[red]Error:[/red] Could not analyze feature state.")
        raise typer.Exit(1)

    # Display analysis
    console.print(Panel(
        f"[bold]Feature:[/bold] {feature_id}\n"
        f"[bold]Analysis:[/bold] {spec_recovery['reason']}\n"
        f"[bold]Can recover:[/bold] {'Yes' if spec_recovery['can_recover'] else 'No'}\n"
        f"[bold]Recommended:[/bold] {spec_recovery.get('recommended_action', 'Unknown')}",
        title="Feature Analysis",
        border_style="cyan",
    ))

    if spec_recovery["can_recover"]:
        # Files indicate success - unblock to SPEC_NEEDS_APPROVAL
        result = handle_spec_unblock(feature_id, config, store, "SPEC_NEEDS_APPROVAL")

        if result["success"]:
            console.print(f"\n[green]Feature unblocked![/green]")
            console.print(f"  Phase: {result['old_phase']} → {result['new_phase']}")
            console.print(f"\n[cyan]Next step:[/cyan] swarm-attack approve {feature_id}")
        else:
            console.print(f"\n[red]Failed to unblock:[/red] {result.get('error')}")
            raise typer.Exit(1)

    elif spec_recovery.get("recommended_action") == "retry_spec_pipeline":
        # Reset to PRD_READY to allow retry
        result = handle_spec_retry(feature_id, config, store)

        if result["success"]:
            console.print(f"\n[yellow]Feature reset to PRD_READY.[/yellow]")
            console.print(f"\n[cyan]Next step:[/cyan] {result['next_step']}")
        else:
            console.print(f"\n[red]Failed to reset:[/red] {result.get('error')}")
            raise typer.Exit(1)

    else:
        console.print(f"\n[yellow]Could not determine automatic recovery action.[/yellow]")
        console.print(f"  Use --phase to manually specify target phase:")
        console.print(f"    swarm-attack unblock {feature_id} --phase PRD_READY")
        console.print(f"    swarm-attack unblock {feature_id} --phase SPEC_NEEDS_APPROVAL")


# =========================================================================
# Bug Bash Commands
# =========================================================================

# Create bug command group
bug_app = typer.Typer(
    name="bug",
    help="Bug investigation commands for Bug Bash pipeline",
    no_args_is_help=True,
)
app.add_typer(bug_app, name="bug")

# Bug phase display names and colors
BUG_PHASE_DISPLAY = {
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


def _format_bug_phase(phase_value: str) -> Text:
    """Format a bug phase as colored text."""
    display_name, style = BUG_PHASE_DISPLAY.get(phase_value, (phase_value, "white"))
    return Text(display_name, style=style)


@bug_app.command("init")
def bug_init(
    description: str = typer.Argument(
        ...,
        help="Description of the bug to investigate.",
    ),
    bug_id: Optional[str] = typer.Option(
        None,
        "--id",
        help="Custom bug ID. If not provided, one will be generated.",
    ),
    test: Optional[str] = typer.Option(
        None,
        "--test",
        "-t",
        help="Path to failing test (e.g., tests/test_example.py::test_func).",
    ),
    issue: Optional[int] = typer.Option(
        None,
        "--issue",
        "-i",
        help="GitHub issue number associated with this bug.",
    ),
    error: Optional[str] = typer.Option(
        None,
        "--error",
        "-e",
        help="Error message to include in the bug report.",
    ),
) -> None:
    """
    Initialize a new bug investigation.

    Creates a bug in the state store with the provided description and
    any additional context like test path, error message, or GitHub issue.

    Example:
        swarm-attack bug init "Test fails intermittently" --test tests/test_auth.py::test_login
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    result = orchestrator.init_bug(
        description=description,
        bug_id=bug_id,
        test_path=test,
        github_issue=issue,
        error_message=error,
    )

    if result.success:
        console.print(
            Panel(
                f"[green]Bug investigation created![/green]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n\n"
                f"[cyan]Next step:[/cyan] Run analysis with:\n"
                f"  [cyan]swarm-attack bug analyze {result.bug_id}[/cyan]",
                title="Bug Created",
                border_style="green",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


@bug_app.command("analyze")
def bug_analyze(
    bug_id: str = typer.Argument(
        ...,
        help="Bug ID to analyze.",
    ),
    max_cost: float = typer.Option(
        10.0,
        "--max-cost",
        help="Maximum cost in USD before aborting.",
    ),
) -> None:
    """
    Run the full analysis pipeline: Reproduce -> Analyze -> Plan.

    The pipeline runs through reproduction, root cause analysis, and fix planning.
    It stops at the PLANNED phase, requiring human approval before implementation.

    Example:
        swarm-attack bug analyze bug-test-fails-2024
    """
    from typing import Optional

    from rich.live import Live
    from rich.table import Table

    from swarm_attack.bug_models import CostLimitExceededError
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    console.print(f"[cyan]Analyzing bug:[/cyan] {bug_id}")
    console.print()

    # Track progress state
    progress_state = {"step": "", "num": 0, "total": 3, "detail": ""}

    def progress_callback(step: str, num: int, total: int, detail: Optional[str]) -> None:
        """Update progress display."""
        progress_state["step"] = step
        progress_state["num"] = num
        progress_state["total"] = total
        progress_state["detail"] = detail or ""

    def make_progress_table() -> Table:
        """Create progress display table."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="cyan", no_wrap=True)
        table.add_column(style="white")

        step = progress_state["step"]
        num = progress_state["num"]
        total = progress_state["total"]
        detail = progress_state["detail"]

        if step:
            table.add_row(
                f"[yellow]Step {num}/{total}:[/yellow]",
                f"[bold]{step}[/bold]"
            )
            if detail:
                table.add_row("", f"[dim]{detail}[/dim]")

        return table

    try:
        with Live(make_progress_table(), refresh_per_second=4, console=console) as live:
            def live_progress_callback(step: str, num: int, total: int, detail: Optional[str]) -> None:
                progress_callback(step, num, total, detail)
                live.update(make_progress_table())

            result = orchestrator.analyze(
                bug_id,
                max_cost_usd=max_cost,
                progress_callback=live_progress_callback,
            )
    except CostLimitExceededError as e:
        console.print(f"[red]Cost limit exceeded:[/red] {e}")
        raise typer.Exit(1)

    console.print()

    if result.success:
        if result.phase.value == "planned":
            console.print(
                Panel(
                    f"[green]Analysis complete![/green]\n\n"
                    f"Bug ID: {result.bug_id}\n"
                    f"Phase: {_format_bug_phase(result.phase.value)}\n"
                    f"Cost: {_format_cost(result.cost_usd)}\n\n"
                    f"{result.message}\n\n"
                    f"[cyan]Review the fix plan at:[/cyan]\n"
                    f"  .swarm/bugs/{result.bug_id}/fix-plan.md\n\n"
                    f"[cyan]Then approve with:[/cyan]\n"
                    f"  [cyan]swarm-attack bug approve {result.bug_id}[/cyan]",
                    title="Analysis Complete",
                    border_style="green",
                )
            )
        elif result.phase.value == "not_reproducible":
            console.print(
                Panel(
                    f"[yellow]Bug could not be reproduced.[/yellow]\n\n"
                    f"Bug ID: {result.bug_id}\n"
                    f"Cost: {_format_cost(result.cost_usd)}\n\n"
                    f"See reproduction attempts at:\n"
                    f"  .swarm/bugs/{result.bug_id}/reproduction.md\n\n"
                    f"Options:\n"
                    f"  - Mark as won't fix: swarm-attack bug reject {result.bug_id} --reason 'Cannot reproduce'\n"
                    f"  - Retry with more info: swarm-attack bug analyze {result.bug_id}",
                    title="Not Reproducible",
                    border_style="yellow",
                )
            )
    else:
        console.print(
            Panel(
                f"[red]Analysis failed.[/red]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n"
                f"Cost: {_format_cost(result.cost_usd)}\n"
                f"Error: {result.error}",
                title="Analysis Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


@bug_app.command("status")
def bug_status(
    bug_id: Optional[str] = typer.Argument(
        None,
        help="Bug ID to show status for. If omitted, shows all bugs.",
    ),
) -> None:
    """
    Show bug investigation status.

    Without arguments, displays a table of all bug investigations.
    With a bug ID, displays detailed status for that investigation.

    Example:
        swarm-attack bug status
        swarm-attack bug status bug-test-fails-2024
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    if bug_id is None:
        # List all bugs
        bug_ids = orchestrator.list_bugs()

        if not bug_ids:
            console.print(
                Panel(
                    "[dim]No bug investigations found.[/dim]\n\n"
                    "Get started by creating a bug investigation:\n"
                    "  [cyan]swarm-attack bug init 'Description of the bug'[/cyan]",
                    title="Bug Bash Status",
                    border_style="dim",
                )
            )
            return

        # Build table
        table = Table(
            title="Bug Investigations",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Bug ID", style="cyan", no_wrap=True)
        table.add_column("Phase", no_wrap=True)
        table.add_column("Cost", justify="right")
        table.add_column("Updated", style="dim")

        total_cost = 0.0

        for bid in sorted(bug_ids):
            state = orchestrator.get_status(bid)
            if state is None:
                continue

            total_cost += state.total_cost_usd
            updated = state.updated_at[:10] if state.updated_at else "-"

            table.add_row(
                bid,
                _format_bug_phase(state.phase.value),
                _format_cost(state.total_cost_usd),
                updated,
            )

        console.print(table)

        if total_cost > 0:
            console.print(f"\n[dim]Total cost:[/dim] [yellow]${total_cost:.2f}[/yellow]")

    else:
        # Show specific bug
        state = orchestrator.get_status(bug_id)

        if state is None:
            console.print(f"[red]Error:[/red] Bug '{bug_id}' not found.")
            raise typer.Exit(1)

        # Header panel
        info_lines = [
            f"[bold]Bug ID:[/bold] {state.bug_id}",
            f"[bold]Phase:[/bold] {_format_bug_phase(state.phase.value)}",
            f"[bold]Created:[/bold] {state.created_at[:19].replace('T', ' ')}",
            f"[bold]Updated:[/bold] {state.updated_at[:19].replace('T', ' ')}",
            f"[bold]Total Cost:[/bold] {_format_cost(state.total_cost_usd)}",
        ]

        if state.blocked_reason:
            info_lines.append(f"\n[red]Blocked:[/red] {state.blocked_reason}")

        if state.rejection_reason:
            info_lines.append(f"\n[dim]Rejection:[/dim] {state.rejection_reason}")

        console.print(
            Panel(
                "\n".join(info_lines),
                title=f"Bug: {bug_id}",
                border_style="cyan",
            )
        )

        # Bug report
        console.print("\n[bold]Bug Report:[/bold]")
        console.print(f"  {state.report.description}")
        if state.report.test_path:
            console.print(f"  [dim]Test:[/dim] {state.report.test_path}")
        if state.report.github_issue:
            console.print(f"  [dim]GitHub Issue:[/dim] #{state.report.github_issue}")

        # Reproduction summary
        if state.reproduction:
            console.print(f"\n[bold]Reproduction:[/bold]")
            console.print(f"  Confirmed: {'Yes' if state.reproduction.confirmed else 'No'}")
            console.print(f"  Confidence: {state.reproduction.confidence}")
            if state.reproduction.affected_files:
                console.print(f"  Affected files: {len(state.reproduction.affected_files)}")

        # Root cause summary
        if state.root_cause:
            console.print(f"\n[bold]Root Cause:[/bold]")
            console.print(f"  {state.root_cause.summary}")
            console.print(f"  [dim]File:[/dim] {state.root_cause.root_cause_file}")

        # Fix plan summary
        if state.fix_plan:
            console.print(f"\n[bold]Fix Plan:[/bold]")
            console.print(f"  {state.fix_plan.summary}")
            console.print(f"  Changes: {len(state.fix_plan.changes)} files")
            console.print(f"  Tests: {len(state.fix_plan.test_cases)} test cases")
            console.print(f"  Risk: {state.fix_plan.risk_level}")

        # Approval
        if state.approval_record:
            console.print(f"\n[bold]Approval:[/bold]")
            console.print(f"  Approved by: {state.approval_record.approved_by}")
            console.print(f"  Approved at: {state.approval_record.approved_at[:19]}")

        # Cost breakdown
        if state.costs:
            console.print(f"\n[bold]Cost Breakdown:[/bold]")
            for cost in state.costs:
                console.print(f"  {cost.agent_name}: ${cost.cost_usd:.2f}")


@bug_app.command("approve")
def bug_approve(
    bug_id: str = typer.Argument(
        ...,
        help="Bug ID to approve for implementation.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt.",
    ),
) -> None:
    """
    Approve a fix plan for implementation.

    This is the human gate before implementation proceeds.
    Displays the fix plan summary and asks for confirmation.

    Example:
        swarm-attack bug approve bug-test-fails-2024
    """
    from pathlib import Path

    from rich.markdown import Markdown
    from rich.prompt import Confirm

    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = _get_config_or_default()
    _init_swarm_directory(config)

    # Read and display the fix plan
    fix_plan_path = Path(config.repo_root) / ".swarm" / "bugs" / bug_id / "fix-plan.md"
    if not fix_plan_path.exists():
        console.print(f"[red]Error:[/red] Fix plan not found at {fix_plan_path}")
        console.print("Run 'swarm-attack bug analyze' first to generate a fix plan.")
        raise typer.Exit(1)

    fix_plan_content = fix_plan_path.read_text()

    # Display the fix plan
    console.print()
    console.print(Panel(
        Markdown(fix_plan_content),
        title=f"Fix Plan: {bug_id}",
        border_style="cyan",
    ))
    console.print()

    # Ask for confirmation unless --yes flag is provided
    if not yes:
        confirmed = Confirm.ask(
            "[yellow]Approve this fix plan for implementation?[/yellow]",
            default=False,
        )
        if not confirmed:
            console.print("[dim]Fix plan not approved. No changes made.[/dim]")
            raise typer.Exit(0)

    orchestrator = BugOrchestrator(config)

    result = orchestrator.approve(bug_id)

    if result.success:
        console.print(
            Panel(
                f"[green]Fix plan approved![/green]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n\n"
                f"{result.message}\n\n"
                f"[cyan]Next step:[/cyan] Run implementation with:\n"
                f"  [cyan]swarm-attack bug fix {result.bug_id}[/cyan]",
                title="Approved",
                border_style="green",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


@bug_app.command("fix")
def bug_fix(
    bug_id: str = typer.Argument(
        ...,
        help="Bug ID to fix (must be approved first).",
    ),
    max_cost: float = typer.Option(
        10.0,
        "--max-cost",
        help="Maximum cost in USD for implementation.",
    ),
) -> None:
    """
    Execute the approved fix plan.

    REQUIRES prior approval via 'swarm-attack bug approve'.
    This applies the planned code changes and runs verification tests.

    Example:
        swarm-attack bug fix bug-test-fails-2024
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator
    from swarm_attack.bug_models import ApprovalRequiredError

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    console.print(f"[cyan]Implementing fix for:[/cyan] {bug_id}")
    console.print()

    try:
        with console.status("[yellow]Applying fix...[/yellow]"):
            result = orchestrator.fix(bug_id, max_cost_usd=max_cost)
    except ApprovalRequiredError as e:
        console.print(f"[red]Approval required:[/red] {e}")
        console.print(f"\n[cyan]First approve the fix plan with:[/cyan]")
        console.print(f"  [cyan]swarm-attack bug approve {bug_id}[/cyan]")
        raise typer.Exit(1)

    console.print()

    if result.success:
        console.print(
            Panel(
                f"[green]Bug fixed![/green]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n\n"
                f"{result.message}",
                title="Fixed",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                f"[red]Fix failed.[/red]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n"
                f"Error: {result.error}",
                title="Fix Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


@bug_app.command("list")
def bug_list(
    phase: Optional[str] = typer.Option(
        None,
        "--phase",
        "-p",
        help="Filter by phase (e.g., planned, approved, blocked).",
    ),
) -> None:
    """
    List all bug investigations.

    Optionally filter by phase.

    Example:
        swarm-attack bug list
        swarm-attack bug list --phase planned
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator
    from swarm_attack.bug_models import BugPhase

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    # Parse phase filter
    phase_filter = None
    if phase:
        try:
            phase_filter = BugPhase(phase.lower())
        except ValueError:
            valid_phases = [p.value for p in BugPhase]
            console.print(f"[red]Invalid phase:[/red] {phase}")
            console.print(f"Valid phases: {', '.join(valid_phases)}")
            raise typer.Exit(1)

    bug_ids = orchestrator.list_bugs(phase_filter)

    if not bug_ids:
        if phase_filter:
            console.print(f"[dim]No bugs in phase '{phase_filter.value}'.[/dim]")
        else:
            console.print("[dim]No bug investigations found.[/dim]")
        return

    # Build table
    table = Table(
        title="Bug Investigations" + (f" ({phase_filter.value})" if phase_filter else ""),
        show_header=True,
        header_style="bold",
    )
    table.add_column("Bug ID", style="cyan", no_wrap=True)
    table.add_column("Phase", no_wrap=True)
    table.add_column("Cost", justify="right")
    table.add_column("Updated", style="dim")

    for bid in sorted(bug_ids):
        state = orchestrator.get_status(bid)
        if state is None:
            continue

        updated = state.updated_at[:10] if state.updated_at else "-"

        table.add_row(
            bid,
            _format_bug_phase(state.phase.value),
            _format_cost(state.total_cost_usd),
            updated,
        )

    console.print(table)


@bug_app.command("reject")
def bug_reject(
    bug_id: str = typer.Argument(
        ...,
        help="Bug ID to reject.",
    ),
    reason: str = typer.Option(
        ...,
        "--reason",
        "-r",
        help="Reason for rejecting the bug (required).",
    ),
) -> None:
    """
    Reject a bug (won't fix).

    Marks the bug as won't fix with a reason. Use this when:
    - Bug cannot be reproduced after investigation
    - Fix is not worth the effort
    - Bug is actually expected behavior
    - Bug will be addressed differently

    Example:
        swarm-attack bug reject bug-test-fails-2024 --reason "Cannot reproduce - test flake"
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    result = orchestrator.reject(bug_id, reason)

    if result.success:
        console.print(
            Panel(
                f"[yellow]Bug rejected.[/yellow]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n"
                f"Reason: {reason}",
                title="Won't Fix",
                border_style="yellow",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


@bug_app.command("unblock")
def bug_unblock_cmd(
    bug_id: str = typer.Argument(
        ...,
        help="Bug ID to unblock.",
    ),
) -> None:
    """
    Unblock a bug stuck in BLOCKED state.

    Resets the bug to CREATED phase for re-analysis.

    Example:
        swarm-attack bug unblock bug-test-fails-2024
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = _get_config_or_default()
    _init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    result = orchestrator.unblock(bug_id)

    if result.success:
        console.print(
            Panel(
                f"[green]Bug unblocked![/green]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {_format_bug_phase(result.phase.value)}\n\n"
                f"{result.message}",
                title="Unblocked",
                border_style="green",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


# =============================================================================
# Recovery Commands - Production Error Handling
# =============================================================================


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
    """
    Clean up stale sessions and orphan locks.

    Examples:
        swarm-attack cleanup my-feature --stale-sessions
        swarm-attack cleanup --all
        swarm-attack cleanup my-feature --orphan-locks
    """
    from swarm_attack.recovery import LockManager, HealthChecker
    from swarm_attack.session_manager import SessionManager

    config = _get_config_or_default()
    _init_swarm_directory(config)
    store = get_store(config)

    # If --all, enable both cleanup types
    if all_cleanup:
        stale_sessions = True
        orphan_locks = True

    # Validate at least one cleanup type is specified
    if not stale_sessions and not orphan_locks:
        console.print("[yellow]Warning:[/yellow] No cleanup type specified.")
        console.print("  Use --stale-sessions, --orphan-locks, or --all")
        raise typer.Exit(1)

    total_cleaned = 0

    # Get features to clean
    if feature_id:
        features = [feature_id]
    else:
        features = store.list_features()

    if not features:
        console.print("[dim]No features found to clean up.[/dim]")
        raise typer.Exit(0)

    # Clean up stale sessions
    if stale_sessions:
        console.print("[cyan]Cleaning up stale sessions...[/cyan]")
        session_manager = SessionManager(config, store)

        for fid in features:
            try:
                cleaned = session_manager.cleanup_stale_sessions(fid)
                if cleaned:
                    console.print(f"  [green]Cleaned {len(cleaned)} stale session(s) for {fid}[/green]")
                    total_cleaned += len(cleaned)
            except Exception as e:
                console.print(f"  [red]Error cleaning sessions for {fid}: {e}[/red]")

    # Clean up orphan locks
    if orphan_locks:
        console.print("[cyan]Cleaning up orphan locks...[/cyan]")
        locks_dir = config.swarm_path / "locks"
        lock_manager = LockManager(locks_dir)

        for fid in features:
            try:
                cleaned_issues = lock_manager.cleanup_stale_locks(fid)
                if cleaned_issues:
                    console.print(f"  [green]Cleaned locks for issues {cleaned_issues} in {fid}[/green]")
                    total_cleaned += len(cleaned_issues)
            except Exception as e:
                console.print(f"  [red]Error cleaning locks for {fid}: {e}[/red]")

    console.print()
    if total_cleaned > 0:
        console.print(f"[green]Cleanup complete:[/green] {total_cleaned} item(s) cleaned.")
    else:
        console.print("[dim]No items needed cleanup.[/dim]")


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
    """
    Force-unlock a stuck issue.

    Use this when an issue is stuck due to a crashed process or orphan lock.
    The lock will be released regardless of who holds it.

    Examples:
        swarm-attack unlock my-feature --issue 5
        swarm-attack unlock my-feature --issue 5 --force
    """
    from swarm_attack.recovery import LockManager

    config = _get_config_or_default()
    _init_swarm_directory(config)

    locks_dir = config.swarm_path / "locks"
    lock_manager = LockManager(locks_dir)

    # Check if lock exists
    lock_info = lock_manager.get_lock_holder(feature_id, issue)
    if not lock_info:
        console.print(f"[yellow]No lock found for {feature_id} issue #{issue}[/yellow]")
        raise typer.Exit(0)

    # Show current lock holder
    console.print(f"[bold]Lock holder for {feature_id} issue #{issue}:[/bold]")
    console.print(f"  Session: {lock_info.session_id}")
    console.print(f"  PID: {lock_info.pid}")
    console.print(f"  Host: {lock_info.hostname}")
    console.print(f"  Started: {lock_info.started_at}")
    console.print()

    # Confirm unless --force
    if not force:
        confirm = typer.confirm(
            "Are you sure you want to force-unlock this issue? "
            "This may cause conflicts if the process is still running."
        )
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Force release
    success = lock_manager.force_release(feature_id, issue)
    if success:
        console.print(f"[green]Successfully unlocked {feature_id} issue #{issue}[/green]")
    else:
        console.print(f"[red]Failed to unlock issue #{issue}[/red]")
        raise typer.Exit(1)


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
    """
    Reset an issue to READY state (or BACKLOG with --hard).

    Use this to retry a failed or blocked issue. Clears:
    - Task stage (to READY or BACKLOG)
    - Any active locks
    - Associated session (if exists)

    Examples:
        swarm-attack reset my-feature --issue 5
        swarm-attack reset my-feature --issue 5 --hard
    """
    from swarm_attack.recovery import LockManager

    config = _get_config_or_default()
    _init_swarm_directory(config)
    store = get_store(config)

    # Load state
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Find the task
    task = None
    for t in state.tasks:
        if t.issue_number == issue:
            task = t
            break

    if task is None:
        console.print(f"[red]Error:[/red] Issue #{issue} not found in feature '{feature_id}'.")
        raise typer.Exit(1)

    console.print(f"[bold]Resetting issue #{issue}:[/bold] {task.title}")
    console.print(f"  Current stage: {_format_stage(task.stage)}")
    console.print()

    # Determine target stage
    target_stage = TaskStage.BACKLOG if hard else TaskStage.READY
    console.print(f"  Target stage: {_format_stage(target_stage)}")

    # Release any locks
    locks_dir = config.swarm_path / "locks"
    lock_manager = LockManager(locks_dir)
    lock_info = lock_manager.get_lock_holder(feature_id, issue)
    if lock_info:
        lock_manager.force_release(feature_id, issue)
        console.print(f"  [dim]Released lock held by session {lock_info.session_id}[/dim]")

    # Update task stage
    task.stage = target_stage
    task.failure_reason = None

    # Clear any retry count if present
    if hasattr(task, "retry_count"):
        task.retry_count = 0

    # Save state
    store.save(state)
    console.print()
    console.print(f"[green]Issue #{issue} reset to {target_stage.name}[/green]")

    if hard:
        console.print("[dim]Note: Generated test files were not deleted (manual cleanup may be needed)[/dim]")


@app.command()
def diagnose(
    feature_id: str = typer.Argument(
        ...,
        help="Feature to diagnose.",
    ),
) -> None:
    """
    Show detailed diagnostics and recovery options for a feature.

    Runs health checks and displays:
    - Feature state and phase
    - Task status summary
    - Active locks
    - Stale sessions
    - Recovery suggestions

    Examples:
        swarm-attack diagnose my-feature
    """
    from swarm_attack.recovery import LockManager, HealthChecker, PreflightChecker
    from swarm_attack.session_manager import SessionManager

    config = _get_config_or_default()
    _init_swarm_directory(config)
    store = get_store(config)

    # Load state
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Header
    console.print(Panel(
        f"[bold]Diagnostics for: {feature_id}[/bold]",
        border_style="cyan",
    ))

    # Feature overview
    console.print()
    console.print("[bold cyan]Feature Status:[/bold cyan]")
    console.print(f"  Phase: {_format_phase(state.phase)}")
    console.print(f"  Updated: {state.updated_at[:19].replace('T', ' ')}")
    console.print(f"  Total Cost: {_format_cost(state.cost_total_usd)}")

    # Task summary
    if state.tasks:
        console.print()
        console.print("[bold cyan]Task Summary:[/bold cyan]")
        done = len(state.done_tasks)
        ready = len(state.ready_tasks)
        blocked = len(state.blocked_tasks)
        skipped = len(state.skipped_tasks)
        in_progress = len([t for t in state.tasks if t.stage == TaskStage.IN_PROGRESS])

        console.print(f"  Total: {len(state.tasks)}")
        console.print(f"  Done: [green]{done}[/green]")
        console.print(f"  Ready: [cyan]{ready}[/cyan]")
        console.print(f"  In Progress: [yellow]{in_progress}[/yellow]")
        console.print(f"  Blocked: [red]{blocked}[/red]")
        console.print(f"  Skipped: [magenta]{skipped}[/magenta]")

        # Show blocked tasks with reasons
        if blocked > 0:
            console.print()
            console.print("[bold yellow]Blocked Tasks:[/bold yellow]")
            for t in state.blocked_tasks:
                reason = getattr(t, "failure_reason", "Unknown reason")
                console.print(f"  #{t.issue_number}: {t.title}")
                console.print(f"    [dim]Reason: {reason}[/dim]")

    # Check for active locks
    console.print()
    console.print("[bold cyan]Active Locks:[/bold cyan]")
    locks_dir = config.swarm_path / "locks"
    lock_manager = LockManager(locks_dir)
    locks = lock_manager.list_locks(feature_id)

    if locks:
        for lock in locks:
            is_stale = lock_manager._is_lock_stale(lock)
            stale_marker = " [yellow](STALE)[/yellow]" if is_stale else ""
            console.print(f"  Issue #{lock.issue_number}:{stale_marker}")
            console.print(f"    Session: {lock.session_id}")
            console.print(f"    PID: {lock.pid} on {lock.hostname}")
            console.print(f"    Started: {lock.started_at}")
    else:
        console.print("  [dim]No active locks[/dim]")

    # Run health checks
    console.print()
    console.print("[bold cyan]Health Checks:[/bold cyan]")
    session_manager = SessionManager(config, store)
    health_checker = HealthChecker(config, session_manager, store)
    report = health_checker.run_health_checks()

    for check_name, result in report.checks.items():
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        console.print(f"  {check_name}: {status}")
        if not result.passed:
            console.print(f"    [dim]{result.message}[/dim]")

    # Recovery suggestions
    console.print()
    console.print("[bold cyan]Recovery Suggestions:[/bold cyan]")
    suggestions = []

    # Check for stale locks
    stale_locks = [l for l in locks if lock_manager._is_lock_stale(l)]
    if stale_locks:
        issues = [str(l.issue_number) for l in stale_locks]
        suggestions.append(f"Clean stale locks: swarm-attack cleanup {feature_id} --orphan-locks")

    # Check for blocked tasks
    if state.blocked_tasks:
        for t in state.blocked_tasks[:3]:  # Show first 3
            suggestions.append(f"Reset blocked issue: swarm-attack reset {feature_id} --issue {t.issue_number}")

    # Check for in-progress tasks without locks (orphaned)
    in_progress_tasks = [t for t in state.tasks if t.stage == TaskStage.IN_PROGRESS]
    for t in in_progress_tasks:
        if not lock_manager.get_lock_holder(feature_id, t.issue_number):
            suggestions.append(
                f"Orphaned in-progress task #{t.issue_number}: "
                f"swarm-attack reset {feature_id} --issue {t.issue_number}"
            )

    # Health check failures
    stale_sessions_check = report.checks.get("stale_sessions")
    if stale_sessions_check and not stale_sessions_check.passed:
        suggestions.append(f"Clean stale sessions: swarm-attack cleanup {feature_id} --stale-sessions")

    if suggestions:
        for suggestion in suggestions:
            console.print(f"  [cyan]>[/cyan] {suggestion}")
    else:
        console.print("  [green]No issues detected - feature is healthy[/green]")


# Entry point for the CLI
def cli_main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    cli_main()
