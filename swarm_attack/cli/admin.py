"""Admin and recovery commands.

Commands for cleanup, unlocking, resetting, diagnostics, and recovery.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import typer
from rich.panel import Panel
from rich.table import Table

from swarm_attack.cli.common import get_config_or_default, get_console, init_swarm_directory
from swarm_attack.cli.display import format_cost, format_phase, format_stage
from swarm_attack.models import FeaturePhase, TaskStage

if TYPE_CHECKING:
    pass

# Create admin command group
app = typer.Typer(
    name="admin",
    help="Recovery and admin commands",
    no_args_is_help=True,
)

console = get_console()


# =============================================================================
# Cleanup Command
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
    from swarm_attack.recovery import HealthChecker, LockManager
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)
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


# =============================================================================
# Unlock Command
# =============================================================================


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

    config = get_config_or_default()
    init_swarm_directory(config)

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


# =============================================================================
# Reset Command
# =============================================================================


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
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)
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
    console.print(f"  Current stage: {format_stage(task.stage)}")
    console.print()

    # Determine target stage
    target_stage = TaskStage.BACKLOG if hard else TaskStage.READY
    console.print(f"  Target stage: {format_stage(target_stage)}")

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


# =============================================================================
# Diagnose Command
# =============================================================================


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
    from swarm_attack.recovery import HealthChecker, LockManager, PreflightChecker
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)
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
    console.print(f"  Phase: {format_phase(state.phase)}")
    console.print(f"  Updated: {state.updated_at[:19].replace('T', ' ')}")
    console.print(f"  Total Cost: {format_cost(state.cost_total_usd)}")

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


# =============================================================================
# Recover Command
# =============================================================================


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
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)

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


# =============================================================================
# Unblock Command
# =============================================================================


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
    from swarm_attack.state_store import get_store

    config = get_config_or_default()
    init_swarm_directory(config)

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
        console.print(f"  Current phase: {format_phase(state.phase)}")
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
