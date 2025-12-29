"""Feature workflow commands.

Commands for feature initialization, spec debate, and implementation pipelines.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack.cli.common import (
    get_config_or_default,
    get_console,
    get_prd_path,
    get_spec_dir,
    init_swarm_directory,
)
from swarm_attack.cli.display import (
    format_cost,
    format_phase,
    format_stage,
    generate_completion_report,
    get_effective_phase,
    show_all_features,
    show_feature_detail,
)
from swarm_attack.models import FeaturePhase, TaskStage

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.models import RunState
    from swarm_attack.state_store import StateStore

# Create feature command group
app = typer.Typer(
    name="feature",
    help="Feature development workflow commands",
    no_args_is_help=False,
)

console = get_console()


# =============================================================================
# Internal Pipeline Functions
# =============================================================================


def _run_spec_pipeline(
    config: "SwarmConfig",
    store: "StateStore",
    state: "RunState",
    feature_id: str,
) -> None:
    """Run the spec debate pipeline."""
    import time

    from swarm_attack.orchestrator import Orchestrator
    from swarm_attack.utils.fs import file_exists

    # Check PRD exists
    prd_path = get_prd_path(config, feature_id)
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}",
                title="Pipeline Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


def _run_implementation(
    config: "SwarmConfig",
    store: "StateStore",
    state: "RunState",
    feature_id: str,
    issue_number: Optional[int] = None,
) -> None:
    """Run the implementation pipeline for an issue."""
    from swarm_attack.orchestrator import Orchestrator
    from swarm_attack.session_manager import SessionManager

    # Check if specified issue is already DONE or SKIPPED (avoid re-running completed work)
    if issue_number is not None:
        task = next((t for t in state.tasks if t.issue_number == issue_number), None)
        if task and task.stage == TaskStage.DONE:
            console.print(f"[green]Issue #{issue_number} is already completed.[/green]")
            console.print(f"[dim]Title: {task.title}[/dim]")
            console.print(f"[dim]Use 'swarm-attack run {feature_id}' to auto-select next available issue.[/dim]")
            raise typer.Exit(0)
        elif task and task.stage == TaskStage.SKIPPED:
            console.print(f"[yellow]Issue #{issue_number} was skipped.[/yellow]")
            console.print(f"[dim]Title: {task.title}[/dim]")
            console.print(f"[dim]Use 'swarm-attack unblock {feature_id}' to reset if needed.[/dim]")
            raise typer.Exit(0)

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
                f"Cost: {format_cost(result.cost_usd)}\n"
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
                f"Cost: {format_cost(result.cost_usd)}\n\n"
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
            report = generate_completion_report(state, feature_id)
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
                f"Cost: {format_cost(result.cost_usd)}",
                title="Implementation Failed",
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


# =============================================================================
# Feature Commands
# =============================================================================


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
    from swarm_attack.state_store import get_store

    # Get config (or defaults)
    config = get_config_or_default()

    # Ensure .swarm directory exists
    init_swarm_directory(config)

    # Get state store
    store = get_store(config)

    if feature_id is None:
        show_all_features(store, config, console, get_prd_path)
    else:
        show_feature_detail(store, feature_id, config, console, get_prd_path)


@app.command()
def events(
    feature_id: str = typer.Argument(..., help="Feature ID to show events for"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of events to show"),
    issue: Optional[int] = typer.Option(None, "--issue", "-i", help="Filter by issue number"),
) -> None:
    """
    Show event log for a feature.

    Displays timeline of swarm events for debugging and auditing.
    """
    from swarm_attack.event_logger import get_event_logger

    config = get_config_or_default()
    event_logger = get_event_logger(config)

    if issue is not None:
        events_list = event_logger.get_issue_timeline(feature_id, issue)
        title = f"Events for {feature_id} Issue #{issue}"
    else:
        events_list = event_logger.get_recent_events(feature_id, limit)
        title = f"Recent Events for {feature_id}"

    if not events_list:
        console.print(f"[dim]No events found for feature '{feature_id}'[/dim]")
        return

    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("Event", style="cyan")
    table.add_column("Issue", justify="center")
    table.add_column("Details")

    for event in events_list:
        ts = event.get("ts", "")[:19].replace("T", " ")
        event_type = event.get("event", "unknown")
        issue_num = str(event.get("issue", "-"))

        details_parts = []
        for key, value in event.items():
            if key not in ("ts", "event", "issue"):
                if isinstance(value, list):
                    details_parts.append(f"{key}={len(value)}")
                elif isinstance(value, str) and len(value) > 40:
                    details_parts.append(f"{key}={value[:40]}...")
                else:
                    details_parts.append(f"{key}={value}")
        details = ", ".join(details_parts[:3])

        table.add_row(ts, event_type, issue_num, details)

    console.print(table)


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
    from swarm_attack.state_store import get_store
    from swarm_attack.utils.fs import ensure_dir, file_exists, safe_write
    from swarm_attack.validation.input_validator import InputValidator, ValidationError

    # BUG-1, BUG-3: Validate feature_id (path traversal, empty, format)
    result = InputValidator.validate_feature_id(feature_id)
    if isinstance(result, ValidationError):
        console.print(f"[red]Error:[/red] {result.message}")
        console.print(f"  Expected: {result.expected}")
        console.print(f"  Got: {result.got}")
        if result.hint:
            console.print(f"  Hint: {result.hint}")
        raise typer.Exit(1)

    config = get_config_or_default()
    init_swarm_directory(config)

    store = get_store(config)

    # Check if feature already exists
    existing = store.load(feature_id)
    if existing is not None:
        console.print(f"[yellow]Warning:[/yellow] Feature '{feature_id}' already exists.")
        console.print(f"  Phase: {format_phase(existing.phase)}")
        raise typer.Exit(0)

    # Check if PRD exists
    prd_path = get_prd_path(config, feature_id)
    prd_exists = file_exists(prd_path)

    # Determine initial phase
    initial_phase = FeaturePhase.PRD_READY if prd_exists else FeaturePhase.NO_PRD

    # Create feature
    store.create_feature(feature_id, initial_phase)

    console.print(f"[green]Created feature:[/green] {feature_id}")

    if prd_exists:
        console.print(f"[dim]PRD found at:[/dim] {prd_path}")
        console.print(f"[dim]Phase:[/dim] {format_phase(initial_phase)}")
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
        console.print(f"[dim]Phase:[/dim] {format_phase(initial_phase)}")
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
    prd_path_arg: Optional[str] = typer.Option(
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

    This command allows engineers who write specs outside the normal PRD -> SpecAuthor
    flow to use the debate pipeline (SpecCritic -> SpecModerator) for quality review.

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
    from swarm_attack.orchestrator import Orchestrator
    from swarm_attack.validation.input_validator import InputValidator, ValidationError

    # Validate feature_id
    result = InputValidator.validate_feature_id(feature_id)
    if isinstance(result, ValidationError):
        console.print(f"[red]Error:[/red] {result.message}")
        console.print(f"  Expected: {result.expected}")
        console.print(f"  Got: {result.got}")
        if result.hint:
            console.print(f"  Hint: {result.hint}")
        raise typer.Exit(1)
    from swarm_attack.state_store import get_store
    from swarm_attack.utils.fs import ensure_dir, safe_write

    config = get_config_or_default()
    init_swarm_directory(config)

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
        console.print(f"[yellow]Warning:[/yellow] Feature '{feature_id}' exists in phase {format_phase(existing.phase)}")
        console.print("  Use --force to overwrite (not implemented), or choose a different feature ID.")
        raise typer.Exit(1)

    # Handle PRD - either use provided or generate stub
    target_prd_path = get_prd_path(config, feature_id)
    ensure_dir(target_prd_path.parent)

    if prd_path_arg:
        prd_file = Path(prd_path_arg).expanduser().resolve()
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
    target_spec_dir = get_spec_dir(config, feature_id)
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

    # Run debate pipeline (critic -> moderator)
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}\n"
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
                f"Cost: {format_cost(result.total_cost_usd)}",
                title="Debate Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


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
    from swarm_attack.state_store import get_store
    from swarm_attack.validation.input_validator import InputValidator, ValidationError

    # Validate feature_id
    result = InputValidator.validate_feature_id(feature_id)
    if isinstance(result, ValidationError):
        console.print(f"[red]Error:[/red] {result.message}")
        console.print(f"  Expected: {result.expected}")
        console.print(f"  Got: {result.got}")
        if result.hint:
            console.print(f"  Hint: {result.hint}")
        raise typer.Exit(1)

    config = get_config_or_default()
    init_swarm_directory(config)

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
        console.print(f"[yellow]Feature is in phase: {format_phase(state.phase)}[/yellow]")
        console.print("  Cannot run pipeline in this phase.")
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
    from swarm_attack.state_store import get_store
    from swarm_attack.utils.fs import file_exists, read_file, safe_write

    config = get_config_or_default()
    init_swarm_directory(config)

    store = get_store(config)

    # Check feature exists
    state = store.load(feature_id)
    if state is None:
        console.print(f"[red]Error:[/red] Feature '{feature_id}' not found.")
        raise typer.Exit(1)

    # Check phase
    if state.phase != FeaturePhase.SPEC_NEEDS_APPROVAL:
        console.print(
            f"[yellow]Warning:[/yellow] Feature is in phase '{format_phase(state.phase)}', "
            f"not SPEC_NEEDS_APPROVAL."
        )
        console.print("  Proceeding anyway...")

    # Check spec-draft.md exists
    spec_dir = get_spec_dir(config, feature_id)
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
            f"'{format_phase(verified_state.phase) if verified_state else 'None'}'."
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
    console.print(f"[dim]Phase:[/dim] {format_phase(state.phase)}")


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
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)

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
        console.print(f"[dim]Phase:[/dim] {format_phase(state.phase)}")
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
    import json

    from swarm_attack.models import TaskRef
    from swarm_attack.state_store import get_store
    from swarm_attack.utils.fs import read_file

    config = get_config_or_default()
    init_swarm_directory(config)

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
            f"[yellow]Warning:[/yellow] Feature is in phase '{format_phase(state.phase)}', "
            f"expected ISSUES_NEED_REVIEW or SPEC_APPROVED."
        )
        console.print("  Proceeding anyway...")

    # Check if issues.json exists
    issues_path = config.specs_path / feature_id / "issues.json"
    if not issues_path.exists():
        console.print(f"[red]Error:[/red] No issues found at {issues_path}")
        console.print("  Run 'swarm-attack issues {feature_id}' first to create issues.")
        raise typer.Exit(1)

    # CRITICAL FIX: Sync state from git BEFORE merging issues.json
    # This prevents re-implementing issues that are already committed to git
    # but not reflected in state (e.g., due to state file corruption or race conditions)
    synced = store.sync_state_from_git(feature_id)
    if synced:
        console.print(f"[dim]Synced {len(synced)} issue(s) from git history: {synced}[/dim]")
        # Reload state after sync to get updated stages
        state = store.load(feature_id)
        if state is None:
            console.print(f"[red]Error:[/red] State corrupted after git sync.")
            raise typer.Exit(1)

    # Load issues.json and populate tasks in state
    try:
        issues_content = read_file(issues_path)
        issues_data = json.loads(issues_content)
        issues_list = issues_data.get("issues", [])

        # MERGE strategy: preserve existing task progress (DONE status, outputs, commits)
        # Build a map of existing progress by issue_number
        existing_progress = {t.issue_number: t for t in state.tasks}
        preserved_count = 0

        new_tasks = []
        for issue in issues_list:
            issue_num = issue.get("order", 0)
            deps = issue.get("dependencies", [])

            # Check if we have existing progress for this issue
            existing = existing_progress.get(issue_num)

            if existing and existing.stage in (TaskStage.DONE, TaskStage.SKIPPED):
                # Preserve completed/skipped task progress
                # Update metadata from issues.json but keep stage and outputs
                existing.title = issue.get("title", existing.title)
                existing.dependencies = deps
                existing.estimated_size = issue.get("estimated_size", existing.estimated_size)
                new_tasks.append(existing)
                preserved_count += 1
            else:
                # Create new task or reset non-completed task
                initial_stage = TaskStage.READY if not deps else TaskStage.BACKLOG

                task = TaskRef(
                    issue_number=issue_num,
                    stage=initial_stage,
                    title=issue.get("title", "Untitled"),
                    dependencies=deps,
                    estimated_size=issue.get("estimated_size", "medium"),
                )
                new_tasks.append(task)

        state.tasks = new_tasks

        console.print(f"[dim]Loaded {len(state.tasks)} tasks from issues.json[/dim]")
        if preserved_count > 0:
            console.print(f"[dim]Preserved progress for {preserved_count} completed/skipped tasks[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load issues: {e}")
        raise typer.Exit(1)

    # Update phase to READY_TO_IMPLEMENT
    state.update_phase(FeaturePhase.READY_TO_IMPLEMENT)
    store.save(state)

    console.print(f"[green]Issues greenlighted![/green]")
    console.print(f"[dim]Phase:[/dim] {format_phase(state.phase)}")
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
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)

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
            f"[yellow]Warning:[/yellow] Feature is in phase '{format_phase(state.phase)}', "
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
                f"Cost: {format_cost(creator_result.cost_usd)}",
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
                f"Cost: {format_cost(total_cost)}",
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
                f"Cost: {format_cost(total_cost)}\n\n"
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
                f"Cost: {format_cost(total_cost)}\n\n"
                f"Problems:\n{problem_lines}\n\n"
                f"[cyan]Next step:[/cyan] Review issues at:\n"
                f"  specs/{feature_id}/issues.json\n\n"
                f"Then greenlight with:\n"
                f"  [cyan]swarm-attack greenlight {feature_id}[/cyan]",
                title="Issues Need Review",
                border_style="yellow",
            )
        )


@app.command(name="next")
def next_action(
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
        ActionType,
        StateMachine,
        StateMachineError,
    )
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)

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
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)

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
