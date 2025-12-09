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
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack import __version__
from swarm_attack.config import ConfigError, SwarmConfig, load_config
from swarm_attack.models import FeaturePhase, RunState, TaskStage
from swarm_attack.orchestrator import Orchestrator
from swarm_attack.state_store import StateStore, get_store
from swarm_attack.utils.fs import copy_file, ensure_dir, file_exists, read_file, safe_write

# Create Typer app
app = typer.Typer(
    name="swarm-attack",
    help="Autonomous AI-powered feature development - run from any project directory",
    add_completion=False,
    no_args_is_help=True,
)

# Rich console for output
console = Console()

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
    FeaturePhase.BLOCKED: ("Blocked", "red bold"),
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
    TaskStage.BLOCKED: ("Blocked", "red"),
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

    if blocked > 0:
        return f"{done}/{total} ({blocked} blocked)"
    return f"{done}/{total}"


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
    """
    try:
        return load_config()
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

    return SwarmConfig(
        repo_root=".",
        specs_dir="specs",
        swarm_dir=".swarm",
        github=GitHubConfig(repo=""),
        claude=ClaudeConfig(),
        spec_debate=SpecDebateConfig(),
        sessions=SessionConfig(),
        tests=TestRunnerConfig(command=""),
        git=GitConfig(),
    )


def _show_all_features(store: StateStore) -> None:
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

        table.add_row(
            feature_id,
            _format_phase(state.phase),
            _get_task_summary(state),
            _format_cost(state.cost_total_usd),
            updated,
        )

    console.print(table)

    # Show total cost if any
    if total_cost > 0:
        console.print(f"\n[dim]Total cost:[/dim] [yellow]${total_cost:.2f}[/yellow]")


def _show_feature_detail(store: StateStore, feature_id: str) -> None:
    """Display detailed status for a specific feature."""
    state = store.load(feature_id)

    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Header panel with feature info
    phase_text = _format_phase(state.phase)

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
        ready = len(state.ready_tasks)
        total = len(state.tasks)

        summary_parts = [f"[green]{done}[/green]/{total} done"]
        if ready > 0:
            summary_parts.append(f"[cyan]{ready}[/cyan] ready")
        if blocked > 0:
            summary_parts.append(f"[red]{blocked}[/red] blocked")

        console.print(f"\n[dim]Tasks:[/dim] {', '.join(summary_parts)}")
    else:
        console.print("\n[dim]No tasks yet.[/dim]")


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"swarm-attack version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
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
    AI-powered agents.
    """
    pass


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
        _show_all_features(store)
    else:
        _show_feature_detail(store, feature_id)


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
        console.print(f"  [cyan]feature-swarm run {feature_id}[/cyan]")
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
        console.print(f"  2. Run: [cyan]feature-swarm run {feature_id}[/cyan]")


@app.command()
def run(
    feature_id: str = typer.Argument(
        ...,
        help="Feature ID to run the spec pipeline for.",
    ),
) -> None:
    """
    Run the spec debate pipeline for a feature.

    Starts the Author -> Critic -> Moderator loop to generate
    and refine an engineering specification from the PRD.
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

    # Run the orchestrator
    orchestrator = Orchestrator(config, state_store=store)

    with console.status("[yellow]Running spec pipeline...[/yellow]"):
        result = orchestrator.run_spec_pipeline(feature_id)

    # Display results
    console.print()

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
                f"  [cyan]feature-swarm approve {feature_id}[/cyan]",
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
                f"Scores: {result.final_scores}\n\n"
                "The spec is not improving. Human intervention may be needed.\n"
                f"Review the spec at: specs/{feature_id}/spec-draft.md",
                title="Pipeline Stalemate",
                border_style="yellow",
            )
        )
        raise typer.Exit(1)
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

    # Update phase
    state.update_phase(FeaturePhase.SPEC_APPROVED)
    store.save(state)

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
        ActionType.RUN_SPEC_PIPELINE: f"feature-swarm run {feature_id}",
        ActionType.AWAIT_SPEC_APPROVAL: f"feature-swarm approve {feature_id}",
        ActionType.RUN_ISSUE_PIPELINE: "(Issue pipeline not yet implemented)",
        ActionType.AWAIT_ISSUE_GREENLIGHT: f"feature-swarm greenlight {feature_id}",
        ActionType.SELECT_ISSUE: f"(Implementation agents not yet implemented)",
        ActionType.RESUME_SESSION: f"(Implementation agents not yet implemented)",
        ActionType.RUN_IMPLEMENTATION: f"(Implementation agents not yet implemented)",
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
    1. Interrupted sessions that need recovery
    2. Blocked issues that may need attention

    Use this to manually trigger recovery without running the full smart CLI.
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

    config = _get_config_or_default()
    _init_swarm_directory(config)

    store = get_store(config)
    session_manager = SessionManager(config, store)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

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


# Entry point for the CLI
def cli_main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    cli_main()
