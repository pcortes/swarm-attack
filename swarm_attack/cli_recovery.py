"""
CLI Recovery Flow for Feature Swarm.

This module handles:
- Detecting interrupted sessions on startup
- Displaying recovery options (Resume, Backup & restart, Skip)
- Handling each recovery option appropriately
- Detecting blocked issues that may need attention
- Displaying blocked issues with recovery instructions

The recovery flow is invoked at CLI startup when:
1. Interrupted sessions are detected (status="active" or "interrupted")
2. Blocked issues exist that may need human attention

Recovery Options:
1. Resume: Continue from last checkpoint
2. Backup & restart: Git stash changes, rollback session, start fresh
3. Skip: Mark issue as blocked, continue to next issue
"""

from __future__ import annotations

import subprocess
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from swarm_attack.models import CheckpointData, SessionState, TaskRef, TaskStage

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.session_manager import SessionManager
    from swarm_attack.state_store import StateStore


# Console for output
console = Console()


class RecoveryOption(Enum):
    """Recovery options for interrupted sessions."""
    RESUME = auto()
    BACKUP_RESTART = auto()
    SKIP = auto()


# =============================================================================
# Interrupted Session Detection
# =============================================================================


def check_interrupted_sessions(
    feature_id: str,
    config: SwarmConfig,
    state_store: StateStore,
) -> list[SessionState]:
    """
    Check for any interrupted sessions that need recovery.

    An interrupted session has status="active" or "interrupted" but
    hasn't been updated recently (the process that owned it is gone).

    Args:
        feature_id: The feature identifier.
        config: SwarmConfig with paths and settings.
        state_store: StateStore for loading sessions.

    Returns:
        List of interrupted SessionState objects.
    """
    interrupted = []
    session_ids = state_store.list_sessions(feature_id)

    for session_id in session_ids:
        try:
            session = state_store.load_session(feature_id, session_id)
            if session is not None and session.status in ("active", "interrupted"):
                interrupted.append(session)
        except Exception:
            # Skip corrupted session files
            continue

    return interrupted


# =============================================================================
# Recovery Options Display
# =============================================================================


def format_session_info(session: SessionState) -> str:
    """
    Format session information for display.

    Args:
        session: The SessionState to format.

    Returns:
        Formatted string with session details.
    """
    lines = [
        f"Feature: {session.feature_id}",
        f"Issue: #{session.issue_number}",
        f"Session: {session.session_id}",
        f"Started: {session.started_at[:19].replace('T', ' ')}",
        f"Status: {session.status}",
    ]

    if session.checkpoints:
        last_cp = session.checkpoints[-1]
        lines.append(f"Last checkpoint: {last_cp.agent} ({last_cp.status})")

    return "\n".join(lines)


def format_checkpoint_info(checkpoints: list[CheckpointData]) -> str:
    """
    Format checkpoint information for display.

    Args:
        checkpoints: List of CheckpointData objects.

    Returns:
        Formatted string with checkpoint details.
    """
    if not checkpoints:
        return "No checkpoints"

    lines = []
    for i, cp in enumerate(checkpoints, 1):
        cp_line = f"{i}. {cp.agent}: {cp.status}"
        if cp.commit:
            cp_line += f" (commit: {cp.commit[:7]})"
        lines.append(cp_line)

    return "\n".join(lines)


def display_recovery_options(
    session: SessionState,
    config: SwarmConfig,
) -> str:
    """
    Display recovery options and get user choice.

    Args:
        session: The interrupted SessionState.
        config: SwarmConfig.

    Returns:
        User's choice: "resume", "backup", or "skip"
    """
    # Determine next agent after resume
    resume_agent = get_resume_agent(session.checkpoints)

    # Build panel content
    info_lines = [
        f"[bold]Feature:[/bold] {session.feature_id}",
        f"[bold]Issue:[/bold] #{session.issue_number}",
        f"[bold]Session:[/bold] {session.session_id}",
        f"[bold]Started:[/bold] {session.started_at[:19].replace('T', ' ')}",
    ]

    if session.checkpoints:
        last_cp = session.checkpoints[-1]
        info_lines.append(f"[bold]Last checkpoint:[/bold] {last_cp.agent} ({last_cp.status})")

    info_lines.extend([
        "",
        "[bold]What would you like to do?[/bold]",
        "",
        f"[1] Resume - Continue from {resume_agent} stage",
        "[2] Backup & Restart - Stash changes, start fresh",
        "[3] Skip - Mark issue blocked, move to next",
    ])

    console.print(Panel(
        "\n".join(info_lines),
        title="⚠️  Interrupted Session Detected",
        border_style="yellow",
    ))

    # Get user choice
    choice = Prompt.ask(
        "Select an option",
        choices=["1", "2", "3"],
        default="1",
    )

    choice_map = {
        "1": "resume",
        "2": "backup",
        "3": "skip",
    }

    return choice_map.get(choice, "resume")


# =============================================================================
# Resume Handler
# =============================================================================


def get_resume_agent(checkpoints: list[CheckpointData]) -> str:
    """
    Determine which agent to resume from based on checkpoints.

    The agent order is: test_writer -> coder -> verifier

    If last checkpoint is:
    - "complete": resume from next agent
    - "in_progress" or "failed": resume from same agent

    Args:
        checkpoints: List of CheckpointData from the session.

    Returns:
        Agent name to resume from ("test_writer", "coder", or "verifier").
    """
    agent_order = ["test_writer", "coder", "verifier"]

    if not checkpoints:
        return "test_writer"

    last_checkpoint = checkpoints[-1]
    agent = last_checkpoint.agent
    status = last_checkpoint.status

    # If in_progress or failed, resume from same agent
    if status in ("in_progress", "failed"):
        return agent

    # If complete, move to next agent
    if status == "complete":
        try:
            current_idx = agent_order.index(agent)
            if current_idx + 1 < len(agent_order):
                return agent_order[current_idx + 1]
            # All agents complete, but session wasn't ended - restart verifier
            return "verifier"
        except ValueError:
            # Unknown agent, start from beginning
            return "test_writer"

    # Default to the agent at the last checkpoint
    return agent


def build_resume_context(session: SessionState) -> dict[str, Any]:
    """
    Build context for resuming a session.

    Args:
        session: The SessionState to resume.

    Returns:
        Context dictionary for the orchestrator.
    """
    return {
        "session_id": session.session_id,
        "feature_id": session.feature_id,
        "issue_number": session.issue_number,
        "resume_from": get_resume_agent(session.checkpoints),
        "checkpoints": [cp.to_dict() for cp in session.checkpoints],
        "commits": session.commits,
        "cost_usd": session.cost_usd,
    }


def handle_resume(
    session: SessionState,
    config: SwarmConfig,
    state_store: StateStore,
    session_manager: SessionManager,
) -> dict[str, Any]:
    """
    Resume from last checkpoint.

    Args:
        session: The interrupted SessionState.
        config: SwarmConfig.
        state_store: StateStore.
        session_manager: SessionManager.

    Returns:
        Result dictionary with resume information.
    """
    # Resume the session
    resumed = session_manager.resume_session(session.session_id)

    return {
        "session_id": resumed.session_id,
        "feature_id": resumed.feature_id,
        "issue_number": resumed.issue_number,
        "resume_from": get_resume_agent(resumed.checkpoints),
        "status": "resumed",
    }


# =============================================================================
# Backup & Restart Handler
# =============================================================================


def handle_backup_restart(
    session: SessionState,
    config: SwarmConfig,
    state_store: StateStore,
    session_manager: SessionManager,
) -> dict[str, Any]:
    """
    Backup changes and restart fresh.

    Steps:
    1. Git stash any uncommitted changes
    2. Rollback session commits
    3. End the interrupted session
    4. Allow starting a fresh session

    Args:
        session: The interrupted SessionState.
        config: SwarmConfig.
        state_store: StateStore.
        session_manager: SessionManager.

    Returns:
        Result dictionary indicating fresh start is possible.
    """
    # Step 1: Git stash any uncommitted changes
    subprocess.run(
        ["git", "stash", "push", "-m", f"feature-swarm-backup-{session.session_id}"],
        capture_output=True,
        text=True,
        cwd=config.repo_root,
    )

    # Step 2: Rollback session commits if any
    if session.commits:
        session_manager.rollback_session(session.session_id)

    # Step 3: End the interrupted session
    try:
        session_manager.end_session(session.session_id, "backed_up")
    except Exception:
        # Session may have been in weird state, mark as interrupted and end
        pass

    return {
        "can_start_fresh": True,
        "issue_number": session.issue_number,
        "feature_id": session.feature_id,
        "stash_created": True,
        "status": "backed_up",
    }


# =============================================================================
# Skip Handler
# =============================================================================


def handle_skip(
    session: SessionState,
    config: SwarmConfig,
    state_store: StateStore,
    session_manager: SessionManager,
) -> dict[str, Any]:
    """
    Skip issue and mark as blocked.

    Steps:
    1. Mark the issue as BLOCKED in state
    2. End the session with "skipped" status
    3. Release the issue lock

    Args:
        session: The interrupted SessionState.
        config: SwarmConfig.
        state_store: StateStore.
        session_manager: SessionManager.

    Returns:
        Result dictionary indicating to continue to next issue.
    """
    feature_id = session.feature_id
    issue_number = session.issue_number

    # Step 1: Mark issue as BLOCKED in state
    state = state_store.load(feature_id)
    if state:
        for task in state.tasks:
            if task.issue_number == issue_number:
                task.stage = TaskStage.BLOCKED
                break
        state_store.save(state)

    # Step 2: End session with "skipped" status
    try:
        session_manager.end_session(session.session_id, "skipped")
    except Exception:
        # Session may already be ended or in weird state
        pass

    # Step 3: Release issue lock
    session_manager.release_issue(feature_id, issue_number)

    return {
        "continue_to_next": True,
        "skipped_issue": issue_number,
        "feature_id": feature_id,
        "status": "skipped",
    }


# =============================================================================
# Blocked Issue Detection
# =============================================================================


def check_blocked_issues(
    feature_id: str,
    config: SwarmConfig,
    state_store: StateStore,
) -> list[TaskRef]:
    """
    Check for blocked issues that may need attention.

    Args:
        feature_id: The feature identifier.
        config: SwarmConfig.
        state_store: StateStore.

    Returns:
        List of blocked TaskRef objects.
    """
    state = state_store.load(feature_id)
    if state is None:
        return []

    return [task for task in state.tasks if task.stage == TaskStage.BLOCKED]


def check_blocked_dependencies_satisfied(
    feature_id: str,
    state_store: StateStore,
) -> list[TaskRef]:
    """
    Check if any blocked issues have their dependencies now satisfied.

    Args:
        feature_id: The feature identifier.
        state_store: StateStore.

    Returns:
        List of TaskRef objects that could potentially be unblocked.
    """
    state = state_store.load(feature_id)
    if state is None:
        return []

    # Get done issue numbers
    done_issues = {task.issue_number for task in state.tasks if task.stage == TaskStage.DONE}

    # Find blocked tasks whose dependencies are now satisfied
    unblockable = []
    for task in state.tasks:
        if task.stage == TaskStage.BLOCKED and task.dependencies:
            # Check if all dependencies are done
            if all(dep in done_issues for dep in task.dependencies):
                unblockable.append(task)

    return unblockable


def format_blocked_issue_info(
    task: TaskRef,
    reason: str = "Unknown",
    last_error: Optional[str] = None,
) -> str:
    """
    Format blocked issue information for display.

    Args:
        task: The blocked TaskRef.
        reason: Reason the issue is blocked.
        last_error: Last error message if available.

    Returns:
        Formatted string with blocked issue details.
    """
    lines = [
        f"Issue #{task.issue_number} - {task.title}",
        "-" * 40,
        f"Blocked: {reason}",
    ]

    if last_error:
        lines.append(f"Last error: {last_error}")

    return "\n".join(lines)


def display_blocked_issues(
    blocked: list[TaskRef],
    config: SwarmConfig,
) -> None:
    """
    Display blocked issues with recovery information.

    Args:
        blocked: List of blocked TaskRef objects.
        config: SwarmConfig.
    """
    if not blocked:
        return

    table = Table(
        title="🚫 Blocked Issues Requiring Attention",
        show_header=True,
        header_style="bold",
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Title", no_wrap=False)
    table.add_column("Dependencies", justify="center")

    for task in blocked:
        deps = ",".join(str(d) for d in task.dependencies) if task.dependencies else "-"
        table.add_row(
            str(task.issue_number),
            task.title,
            deps,
        )

    console.print(table)
    console.print()


def offer_blocked_issue_retry(
    task: TaskRef,
    config: SwarmConfig,
) -> bool:
    """
    Offer to retry a blocked issue.

    Args:
        task: The blocked TaskRef.
        config: SwarmConfig.

    Returns:
        True if user wants to retry, False otherwise.
    """
    console.print(f"\n[bold]Issue #{task.issue_number}[/bold] - {task.title}")
    return Confirm.ask("Retry this issue?", default=False)


# =============================================================================
# Recovery Instructions Display
# =============================================================================


def format_recovery_instructions(recovery_output: dict[str, Any]) -> str:
    """
    Format recovery instructions from RecoveryAgent output.

    Args:
        recovery_output: Output from RecoveryAgent.

    Returns:
        Formatted string with recovery instructions.
    """
    lines = []

    if recovery_output.get("human_instructions"):
        lines.append("[bold]Recovery Suggestion:[/bold]")
        lines.append(recovery_output["human_instructions"])

    if recovery_output.get("suggested_actions"):
        lines.append("")
        lines.append("[bold]Suggested Actions:[/bold]")
        for i, action in enumerate(recovery_output["suggested_actions"], 1):
            lines.append(f"  {i}. {action}")

    return "\n".join(lines) if lines else "No specific recovery instructions available."


def format_human_intervention_steps(recovery_output: dict[str, Any]) -> str:
    """
    Format human intervention steps from RecoveryAgent output.

    Args:
        recovery_output: Output from RecoveryAgent.

    Returns:
        Formatted string with human intervention steps.
    """
    lines = []

    if recovery_output.get("human_instructions"):
        lines.append(recovery_output["human_instructions"])

    if recovery_output.get("suggested_actions"):
        lines.append("")
        lines.append("Steps to resolve:")
        for i, action in enumerate(recovery_output["suggested_actions"], 1):
            lines.append(f"  {i}. {action}")

    return "\n".join(lines) if lines else "Manual intervention required."


def format_actionable_steps(suggested_actions: list[str]) -> str:
    """
    Format actionable next steps.

    Args:
        suggested_actions: List of suggested action strings.

    Returns:
        Formatted string with numbered steps.
    """
    if not suggested_actions:
        return "No specific actions suggested."

    lines = ["[bold]Next Steps:[/bold]"]
    for i, action in enumerate(suggested_actions, 1):
        lines.append(f"  {i}. {action}")

    return "\n".join(lines)


# =============================================================================
# CLI Integration
# =============================================================================


def run_recovery_flow(
    feature_id: str,
    config: SwarmConfig,
    state_store: StateStore,
    session_manager: SessionManager,
) -> Optional[dict[str, Any]]:
    """
    Run the full recovery flow for a feature.

    This is the main entry point for CLI recovery. It:
    1. Checks for interrupted sessions
    2. Displays recovery options and handles user choice
    3. Checks for blocked issues
    4. Returns status to the CLI

    Args:
        feature_id: The feature identifier.
        config: SwarmConfig.
        state_store: StateStore.
        session_manager: SessionManager.

    Returns:
        Result dictionary or None if no recovery needed.
    """
    # Check for interrupted sessions
    interrupted = check_interrupted_sessions(feature_id, config, state_store)

    if interrupted:
        for session in interrupted:
            choice = display_recovery_options(session, config)

            if choice == "resume":
                result = handle_resume(session, config, state_store, session_manager)
                return {"action": "resume", **result}

            elif choice == "backup":
                result = handle_backup_restart(session, config, state_store, session_manager)
                # Continue to normal flow after backup
                return {"action": "backup", **result}

            elif choice == "skip":
                result = handle_skip(session, config, state_store, session_manager)
                # Continue checking for more interrupted sessions or blocked issues

    # Check for blocked issues
    blocked = check_blocked_issues(feature_id, config, state_store)

    if blocked:
        display_blocked_issues(blocked, config)

        # Check if any can be unblocked
        unblockable = check_blocked_dependencies_satisfied(feature_id, state_store)
        if unblockable:
            console.print("\n[green]Some blocked issues may now be ready:[/green]")
            for task in unblockable:
                if offer_blocked_issue_retry(task, config):
                    # Mark as ready
                    state = state_store.load(feature_id)
                    if state:
                        for t in state.tasks:
                            if t.issue_number == task.issue_number:
                                t.stage = TaskStage.READY
                                break
                        state_store.save(state)
                    return {"action": "retry", "issue_number": task.issue_number}

    return None  # No recovery needed
