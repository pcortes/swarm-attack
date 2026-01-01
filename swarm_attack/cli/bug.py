"""Bug investigation workflow commands.

Commands for the Bug Bash pipeline: init, analyze, approve, fix, etc.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack.cli.common import get_config_or_default, get_console, init_swarm_directory
from swarm_attack.cli.display import format_bug_phase, format_cost

if TYPE_CHECKING:
    pass

# Create bug command group
app = typer.Typer(
    name="bug",
    help="Bug investigation commands for Bug Bash pipeline",
    no_args_is_help=True,
)

console = get_console()


@app.command("init")
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
    from swarm_attack.validation.input_validator import InputValidator, ValidationError

    # BUG-9: Validate description is not empty
    if not description or not description.strip():
        console.print("[red]Error:[/red] Bug description cannot be empty")
        console.print("  Expected: non-empty description of the bug")
        console.print(f"  Got: {repr(description)}")
        console.print("  Hint: Provide a brief description of the bug to investigate")
        raise typer.Exit(1)

    # Validate bug_id if provided
    if bug_id is not None:
        result = InputValidator.validate_bug_id(bug_id)
        if isinstance(result, ValidationError):
            console.print(f"[red]Error:[/red] {result.message}")
            console.print(f"  Expected: {result.expected}")
            console.print(f"  Got: {result.got}")
            if result.hint:
                console.print(f"  Hint: {result.hint}")
            raise typer.Exit(1)

    # BUG-10: Validate issue number if provided
    if issue is not None:
        issue_result = InputValidator.validate_positive_int(issue, "Issue number")
        if isinstance(issue_result, ValidationError):
            console.print(f"[red]Error:[/red] {issue_result.message}")
            console.print(f"  Expected: {issue_result.expected}")
            console.print(f"  Got: {issue_result.got}")
            if issue_result.hint:
                console.print(f"  Hint: {issue_result.hint}")
            raise typer.Exit(1)

    config = get_config_or_default()
    init_swarm_directory(config)

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
                f"Phase: {format_bug_phase(result.phase.value)}\n\n"
                f"[cyan]Next step:[/cyan] Run analysis with:\n"
                f"  [cyan]swarm-attack bug analyze {result.bug_id}[/cyan]",
                title="Bug Created",
                border_style="green",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


@app.command("analyze")
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
    from typing import Optional as OptionalType

    from rich.live import Live
    from rich.table import Table as LiveTable

    from swarm_attack.bug_models import CostLimitExceededError
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = get_config_or_default()
    init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    console.print(f"[cyan]Analyzing bug:[/cyan] {bug_id}")
    console.print()

    # Track progress state
    progress_state = {"step": "", "num": 0, "total": 3, "detail": ""}

    def progress_callback(step: str, num: int, total: int, detail: OptionalType[str]) -> None:
        """Update progress display."""
        progress_state["step"] = step
        progress_state["num"] = num
        progress_state["total"] = total
        progress_state["detail"] = detail or ""

    def make_progress_table() -> LiveTable:
        """Create progress display table."""
        table = LiveTable(show_header=False, box=None, padding=(0, 1))
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
            def live_progress_callback(step: str, num: int, total: int, detail: OptionalType[str]) -> None:
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
                    f"Phase: {format_bug_phase(result.phase.value)}\n"
                    f"Cost: {format_cost(result.cost_usd)}\n\n"
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
                    f"Cost: {format_cost(result.cost_usd)}\n\n"
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
                f"Phase: {format_bug_phase(result.phase.value)}\n"
                f"Cost: {format_cost(result.cost_usd)}\n"
                f"Error: {result.error}",
                title="Analysis Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


@app.command("status")
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

    config = get_config_or_default()
    init_swarm_directory(config)

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
                format_bug_phase(state.phase.value),
                format_cost(state.total_cost_usd),
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
            f"[bold]Phase:[/bold] {format_bug_phase(state.phase.value)}",
            f"[bold]Created:[/bold] {state.created_at[:19].replace('T', ' ')}",
            f"[bold]Updated:[/bold] {state.updated_at[:19].replace('T', ' ')}",
            f"[bold]Total Cost:[/bold] {format_cost(state.total_cost_usd)}",
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


@app.command("approve")
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
    auto: bool = typer.Option(
        False,
        "--auto",
        help="Enable auto-approval mode for this bug fix.",
    ),
    manual: bool = typer.Option(
        False,
        "--manual",
        help="Enable manual mode (require human approval for all decisions).",
    ),
) -> None:
    """
    Approve a fix plan for implementation.

    This is the human gate before implementation proceeds.
    Displays the fix plan summary and asks for confirmation.

    Use --auto to enable auto-approval mode for routine decisions.
    Use --manual to force manual mode (all decisions require human approval).

    Example:
        swarm-attack bug approve bug-test-fails-2024
    """
    from pathlib import Path

    from rich.markdown import Markdown
    from rich.prompt import Confirm

    from swarm_attack.auto_approval import BugAutoApprover
    from swarm_attack.bug_orchestrator import BugOrchestrator
    from swarm_attack.bug_state_store import BugStateStore
    from swarm_attack.event_logger import get_event_logger

    # Check for mutually exclusive flags
    if auto and manual:
        console.print("[red]Error:[/red] Cannot use both --auto and --manual flags together.")
        raise typer.Exit(1)

    config = get_config_or_default()
    init_swarm_directory(config)

    # Read and display the fix plan
    fix_plan_path = Path(config.repo_root) / ".swarm" / "bugs" / bug_id / "fix-plan.md"
    if not fix_plan_path.exists():
        console.print(f"[red]Error:[/red] Fix plan not found at {fix_plan_path}")
        console.print("Run 'swarm-attack bug analyze' first to generate a fix plan.")
        raise typer.Exit(1)

    fix_plan_content = fix_plan_path.read_text()

    # Handle --auto mode: try auto-approval first
    if auto:
        console.print("[green]Auto-approval mode enabled.[/green]")

        bug_store = BugStateStore(config)
        event_logger = get_event_logger(config)

        approver = BugAutoApprover(bug_store, event_logger)
        auto_result = approver.auto_approve_if_ready(bug_id)

        if auto_result.approved:
            console.print(f"[green]{auto_result.reason}[/green]")
            console.print(f"[dim]Confidence:[/dim] {auto_result.confidence:.2f}")
            console.print(
                Panel(
                    f"[green]Fix plan auto-approved![/green]\n\n"
                    f"Bug ID: {bug_id}\n"
                    f"Reason: {auto_result.reason}\n\n"
                    f"[cyan]Next step:[/cyan] Run implementation with:\n"
                    f"  [cyan]swarm-attack bug fix {bug_id}[/cyan]",
                    title="Auto-Approved",
                    border_style="green",
                )
            )
            return
        else:
            console.print(f"[yellow]Auto-approval not triggered:[/yellow] {auto_result.reason}")
            console.print("  Proceeding with manual approval...")

    elif manual:
        console.print("[yellow]Manual mode enabled - human approval required.[/yellow]")

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
                f"Phase: {format_bug_phase(result.phase.value)}\n\n"
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


@app.command("fix")
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
    from swarm_attack.bug_models import ApprovalRequiredError
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = get_config_or_default()
    init_swarm_directory(config)

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
                f"Phase: {format_bug_phase(result.phase.value)}\n\n"
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
                f"Phase: {format_bug_phase(result.phase.value)}\n"
                f"Error: {result.error}",
                title="Fix Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


@app.command("list")
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
    from swarm_attack.bug_models import BugPhase
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = get_config_or_default()
    init_swarm_directory(config)

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
            format_bug_phase(state.phase.value),
            format_cost(state.total_cost_usd),
            updated,
        )

    console.print(table)


@app.command("reject")
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

    config = get_config_or_default()
    init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    result = orchestrator.reject(bug_id, reason)

    if result.success:
        console.print(
            Panel(
                f"[yellow]Bug rejected.[/yellow]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {format_bug_phase(result.phase.value)}\n"
                f"Reason: {reason}",
                title="Won't Fix",
                border_style="yellow",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)


@app.command("unblock")
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

    config = get_config_or_default()
    init_swarm_directory(config)

    orchestrator = BugOrchestrator(config)

    result = orchestrator.unblock(bug_id)

    if result.success:
        console.print(
            Panel(
                f"[green]Bug unblocked![/green]\n\n"
                f"Bug ID: {result.bug_id}\n"
                f"Phase: {format_bug_phase(result.phase.value)}\n\n"
                f"{result.message}",
                title="Unblocked",
                border_style="green",
            )
        )
    else:
        console.print(f"[red]Error:[/red] {result.error}")
        raise typer.Exit(1)
