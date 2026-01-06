"""QA Agent CLI commands.

Implements spec section 4: CLI Specification
- qa test: Test a specific area of the codebase
- qa validate: Validate an implemented issue
- qa health: Run system health check
- qa report: View QA reports
- qa bugs: List QA-discovered bugs
- qa create-bugs: Create Bug Bash entries from QA findings
- qa auto-fix: Run detection-fix loop (Issue 11)
- qa auto-watch: Watch mode with auto-fix on changes (Issue 11)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from swarm_attack.qa.auto_fix import AutoFixOrchestrator
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from swarm_attack.cli.common import get_config_or_default, get_console
from swarm_attack.qa.models import QADepth, QARecommendation, QAStatus
from swarm_attack.qa.orchestrator import QAOrchestrator

# Create QA command group
app = typer.Typer(
    name="qa",
    help="Adaptive QA testing commands",
    no_args_is_help=True,
)

console = get_console()


def _get_orchestrator() -> QAOrchestrator:
    """Get configured QA orchestrator."""
    config = get_config_or_default()
    return QAOrchestrator(config)


def _format_recommendation(rec: QARecommendation) -> str:
    """Format recommendation with color."""
    if rec == QARecommendation.PASS:
        return "[green]PASS[/green]"
    elif rec == QARecommendation.WARN:
        return "[yellow]WARN[/yellow]"
    else:  # BLOCK
        return "[red]BLOCK[/red]"


def _format_status(status: QAStatus) -> str:
    """Format status with color."""
    if status == QAStatus.COMPLETED:
        return "[green]COMPLETED[/green]"
    elif status == QAStatus.COMPLETED_PARTIAL:
        return "[yellow]PARTIAL[/yellow]"
    elif status == QAStatus.RUNNING:
        return "[cyan]RUNNING[/cyan]"
    elif status == QAStatus.FAILED:
        return "[red]FAILED[/red]"
    elif status == QAStatus.BLOCKED:
        return "[red]BLOCKED[/red]"
    else:
        return f"[dim]{status.value}[/dim]"


def _format_severity(severity: str) -> str:
    """Format severity with color."""
    if severity == "critical":
        return "[red]CRITICAL[/red]"
    elif severity == "moderate":
        return "[yellow]MODERATE[/yellow]"
    else:
        return "[dim]MINOR[/dim]"


@app.command()
def test(
    target: str = typer.Argument(
        ...,
        help="What to test (file path, endpoint, or description)",
    ),
    depth: str = typer.Option(
        "standard",
        "--depth",
        "-d",
        help="Testing depth level: shallow, standard, or deep",
    ),
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        "-u",
        help="Base URL for API (default: auto-detect)",
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        "-t",
        help="Timeout in seconds",
    ),
) -> None:
    """
    Test a specific area of the codebase.

    TARGET can be:
    - A file path: src/api/users.py
    - An endpoint: /api/users
    - A description: "user authentication"
    - A feature: feature:auth-flow
    """
    try:
        orchestrator = _get_orchestrator()

        console.print(f"[cyan]Starting QA test:[/cyan] {target}")
        console.print(f"[dim]Depth:[/dim] {depth}")
        if base_url:
            console.print(f"[dim]Base URL:[/dim] {base_url}")
        console.print()

        # Convert depth string to enum
        depth_enum = QADepth(depth)

        with console.status("[yellow]Running QA tests...[/yellow]"):
            session = orchestrator.test(
                target=target,
                depth=depth_enum,
                base_url=base_url,
                timeout=timeout,
            )

        # Display results
        result = session.result
        if result is None:
            console.print("[red]Error:[/red] No results returned")
            raise typer.Exit(1)

        # Build result panel
        lines = [
            f"[bold]Session:[/bold] {session.session_id}",
            f"[bold]Status:[/bold] {_format_status(session.status)}",
            f"[bold]Recommendation:[/bold] {_format_recommendation(result.recommendation)}",
            "",
            f"[bold]Tests:[/bold] {result.tests_run} run, {result.tests_passed} passed, {result.tests_failed} failed",
        ]

        if result.findings:
            lines.append("")
            lines.append(f"[bold]Findings:[/bold] {len(result.findings)}")
            for finding in result.findings[:5]:
                lines.append(f"  {_format_severity(finding.severity)} {finding.title}")
            if len(result.findings) > 5:
                lines.append(f"  ... and {len(result.findings) - 5} more")

        border_style = "green" if result.recommendation == QARecommendation.PASS else "yellow" if result.recommendation == QARecommendation.WARN else "red"

        console.print(Panel(
            "\n".join(lines),
            title="QA Test Results",
            border_style=border_style,
        ))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def validate(
    feature: str = typer.Argument(
        ...,
        help="Feature ID to validate",
    ),
    issue: int = typer.Argument(
        ...,
        help="Issue number to validate",
    ),
    depth: str = typer.Option(
        "standard",
        "--depth",
        "-d",
        help="Testing depth level: shallow, standard, or deep",
    ),
) -> None:
    """
    Validate an implemented issue with behavioral tests.

    Runs QA tests against a specific issue implementation to verify
    it meets requirements and doesn't introduce regressions.
    """
    try:
        orchestrator = _get_orchestrator()

        console.print(f"[cyan]Validating issue:[/cyan] {feature} #{issue}")
        console.print(f"[dim]Depth:[/dim] {depth}")
        console.print()

        depth_enum = QADepth(depth)

        with console.status("[yellow]Running validation...[/yellow]"):
            session = orchestrator.validate_issue(
                feature_id=feature,
                issue_number=issue,
                depth=depth_enum,
            )

        result = session.result
        if result is None:
            console.print("[red]Error:[/red] No results returned")
            raise typer.Exit(1)

        # Determine validation status
        is_valid = result.recommendation == QARecommendation.PASS

        lines = [
            f"[bold]Session:[/bold] {session.session_id}",
            f"[bold]Feature:[/bold] {feature}",
            f"[bold]Issue:[/bold] #{issue}",
            "",
            f"[bold]Status:[/bold] {'[green]VALID[/green]' if is_valid else '[red]INVALID[/red]'}",
            f"[bold]Recommendation:[/bold] {_format_recommendation(result.recommendation)}",
            "",
            f"[bold]Tests:[/bold] {result.tests_run} run, {result.tests_passed} passed, {result.tests_failed} failed",
        ]

        if result.findings:
            lines.append("")
            lines.append(f"[bold]Issues Found:[/bold] {len(result.findings)}")
            for finding in result.findings[:3]:
                lines.append(f"  {_format_severity(finding.severity)} {finding.title}")

        border_style = "green" if is_valid else "red"

        console.print(Panel(
            "\n".join(lines),
            title="Validation Results",
            border_style=border_style,
        ))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def health(
    base_url: Optional[str] = typer.Option(
        None,
        "--base-url",
        "-u",
        help="Base URL for API (default: auto-detect)",
    ),
) -> None:
    """
    Run a quick health check on all endpoints.

    Performs shallow testing to verify basic system health.
    """
    try:
        orchestrator = _get_orchestrator()

        console.print("[cyan]Running health check...[/cyan]")
        if base_url:
            console.print(f"[dim]Base URL:[/dim] {base_url}")
        console.print()

        with console.status("[yellow]Checking endpoints...[/yellow]"):
            session = orchestrator.health_check(base_url=base_url)

        result = session.result
        if result is None:
            console.print("[red]Error:[/red] No results returned")
            raise typer.Exit(1)

        # Determine health status
        is_healthy = result.recommendation == QARecommendation.PASS

        if is_healthy:
            console.print(Panel(
                f"[bold green]HEALTHY[/bold green]\n\n"
                f"Tests: {result.tests_run} run, {result.tests_passed} passed\n"
                f"Session: {session.session_id}",
                title="Health Check",
                border_style="green",
            ))
        else:
            lines = [
                "[bold red]UNHEALTHY[/bold red]",
                "",
                f"Tests: {result.tests_run} run, {result.tests_passed} passed, {result.tests_failed} failed",
                f"Session: {session.session_id}",
            ]
            if result.findings:
                lines.append("")
                lines.append("Issues:")
                for finding in result.findings[:5]:
                    lines.append(f"  {_format_severity(finding.severity)} {finding.endpoint}: {finding.title}")

            console.print(Panel(
                "\n".join(lines),
                title="Health Check",
                border_style="red",
            ))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def report(
    session_id: Optional[str] = typer.Argument(
        None,
        help="Session ID to show report for (omit to list sessions)",
    ),
    since: Optional[str] = typer.Option(
        None,
        "--since",
        help="Filter sessions since date (YYYY-MM-DD)",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """
    View QA reports.

    Without session_id: lists recent sessions.
    With session_id: shows detailed report for that session.
    """
    try:
        orchestrator = _get_orchestrator()

        if session_id is None:
            # List sessions
            sessions = orchestrator.list_sessions(limit=20)

            if as_json:
                console.print(json.dumps({"sessions": sessions}, indent=2))
                return

            if not sessions:
                console.print("[dim]No QA sessions found[/dim]")
                return

            table = Table(title="Recent QA Sessions")
            table.add_column("Session ID", style="cyan")
            table.add_column("Status", justify="center")

            for sid in sessions:
                session = orchestrator.get_session(sid)
                if session:
                    status = _format_status(session.status)
                    table.add_row(sid, status)
                else:
                    table.add_row(sid, "[dim]?[/dim]")

            console.print(table)

        else:
            # Show specific session
            session = orchestrator.get_session(session_id)

            if session is None:
                console.print(f"[red]Error:[/red] Session not found: {session_id}")
                raise typer.Exit(1)

            if as_json:
                console.print(json.dumps(session.to_dict(), indent=2))
                return

            result = session.result
            lines = [
                f"[bold]Session:[/bold] {session.session_id}",
                f"[bold]Trigger:[/bold] {session.trigger.value}",
                f"[bold]Depth:[/bold] {session.depth.value}",
                f"[bold]Status:[/bold] {_format_status(session.status)}",
            ]

            if session.started_at:
                lines.append(f"[bold]Started:[/bold] {session.started_at}")
            if session.completed_at:
                lines.append(f"[bold]Completed:[/bold] {session.completed_at}")

            if result:
                lines.append("")
                lines.append(f"[bold]Recommendation:[/bold] {_format_recommendation(result.recommendation)}")
                lines.append(f"[bold]Tests:[/bold] {result.tests_run} run, {result.tests_passed} passed, {result.tests_failed} failed")

                if result.findings:
                    lines.append("")
                    lines.append(f"[bold]Findings ({len(result.findings)}):[/bold]")
                    for finding in result.findings:
                        lines.append(f"  {_format_severity(finding.severity)} [{finding.finding_id}] {finding.title}")
                        lines.append(f"    [dim]{finding.endpoint}[/dim]")

            if session.error:
                lines.append("")
                lines.append(f"[red]Error:[/red] {session.error}")

            console.print(Panel(
                "\n".join(lines),
                title=f"QA Report: {session_id}",
                border_style="cyan",
            ))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def bugs(
    session: Optional[str] = typer.Option(
        None,
        "--session",
        "-s",
        help="Filter by session ID",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        help="Filter by severity: critical, moderate, or minor",
    ),
) -> None:
    """
    List QA-discovered bugs.

    Shows findings from QA sessions that represent potential bugs.
    """
    try:
        orchestrator = _get_orchestrator()

        findings = orchestrator.get_findings(
            session_id=session,
            severity=severity,
        )

        if not findings:
            console.print("[dim]No bugs found[/dim]")
            return

        table = Table(title="QA-Discovered Bugs")
        table.add_column("ID", style="cyan")
        table.add_column("Severity", justify="center")
        table.add_column("Endpoint")
        table.add_column("Title")

        for finding in findings:
            sev_display = _format_severity(finding.severity)
            table.add_row(
                finding.finding_id,
                sev_display,
                finding.endpoint,
                finding.title[:40] + "..." if len(finding.title) > 40 else finding.title,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(findings)} bug(s)[/dim]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("create-bugs")
def create_bugs(
    session_id: str = typer.Argument(
        ...,
        help="Session ID to create bugs from",
    ),
    severity_threshold: str = typer.Option(
        "moderate",
        "--severity-threshold",
        help="Minimum severity for bug creation: critical, moderate, or minor",
    ),
) -> None:
    """
    Create Bug Bash entries from QA findings.

    Converts QA findings into bug reports that can be processed
    by the Bug Bash pipeline.
    """
    try:
        orchestrator = _get_orchestrator()

        console.print(f"[cyan]Creating bugs from session:[/cyan] {session_id}")
        console.print(f"[dim]Severity threshold:[/dim] {severity_threshold}")
        console.print()

        bug_ids = orchestrator.create_bug_investigations(
            session_id=session_id,
            severity_threshold=severity_threshold,
        )

        if not bug_ids:
            console.print("[dim]No bugs created (no findings above threshold)[/dim]")
            return

        console.print(Panel(
            f"[green]Created {len(bug_ids)} bug(s):[/green]\n\n" +
            "\n".join(f"  - {bid}" for bid in bug_ids),
            title="Bugs Created",
            border_style="green",
        ))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _get_auto_fix_orchestrator() -> "AutoFixOrchestrator":
    """Get configured AutoFixOrchestrator.

    Returns:
        Configured AutoFixOrchestrator instance.
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator
    from swarm_attack.qa.auto_fix import AutoFixOrchestrator
    from swarm_attack.static_analysis.detector import StaticBugDetector

    config = get_config_or_default()
    bug_orchestrator = BugOrchestrator(config)
    detector = StaticBugDetector()

    return AutoFixOrchestrator(
        bug_orchestrator=bug_orchestrator,
        detector=detector,
        config=config.auto_fix,
    )


@app.command("auto-fix")
def auto_fix(
    target: Optional[str] = typer.Argument(
        None,
        help="Path to analyze (file or directory). Defaults to current directory.",
    ),
    max_iterations: int = typer.Option(
        3,
        "--max-iterations",
        "-m",
        help="Maximum number of detection-fix iterations",
    ),
    approve_all: bool = typer.Option(
        False,
        "--approve-all",
        "-a",
        help="Auto-approve all fixes (including critical bugs)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Run detection only, show what would be fixed without making changes",
    ),
) -> None:
    """
    Run automatic bug detection and fixing loop.

    Detects bugs using static analysis (pytest, mypy, ruff), creates bug
    investigations, and attempts to fix them through the bug bash pipeline.
    Repeats until all bugs are fixed or max-iterations is reached.

    Examples:
        swarm-attack qa auto-fix                    # Fix current directory
        swarm-attack qa auto-fix src/api/           # Fix specific path
        swarm-attack qa auto-fix --max-iterations 5 # Up to 5 iterations
        swarm-attack qa auto-fix --approve-all      # Auto-approve all fixes
        swarm-attack qa auto-fix --dry-run          # Show what would be fixed
    """
    try:
        orchestrator = _get_auto_fix_orchestrator()

        console.print("[cyan]Starting auto-fix detection loop...[/cyan]")
        if target:
            console.print(f"[dim]Target:[/dim] {target}")
        console.print(f"[dim]Max iterations:[/dim] {max_iterations}")
        console.print(f"[dim]Auto-approve:[/dim] {approve_all}")
        if dry_run:
            console.print("[yellow]DRY RUN MODE - No fixes will be applied[/yellow]")
        console.print()

        with console.status("[yellow]Running detection-fix loop...[/yellow]"):
            result = orchestrator.run(
                target=target,
                max_iterations=max_iterations,
                auto_approve=approve_all,
                dry_run=dry_run,
            )

        # Build result display
        lines = [
            f"[bold]Bugs Found:[/bold] {result.bugs_found}",
            f"[bold]Bugs Fixed:[/bold] {result.bugs_fixed}",
            f"[bold]Iterations:[/bold] {result.iterations_run}",
        ]

        if result.checkpoints_triggered > 0:
            lines.append(f"[bold]Checkpoints Triggered:[/bold] {result.checkpoints_triggered}")

        if result.dry_run:
            lines.append("")
            lines.append("[yellow]DRY RUN - No fixes were applied[/yellow]")

        if result.success:
            lines.append("")
            lines.append("[bold green]SUCCESS - Codebase is clean![/bold green]")
            border_style = "green"
            title = "Auto-Fix Complete"
        else:
            lines.append("")
            if result.bugs_found == 0:
                lines.append("[green]No bugs detected[/green]")
                border_style = "green"
            else:
                lines.append(f"[yellow]Incomplete - {result.bugs_found - result.bugs_fixed} bugs remaining[/yellow]")
                border_style = "yellow"
            title = "Auto-Fix Results"

        if result.errors:
            lines.append("")
            lines.append(f"[bold red]Errors ({len(result.errors)}):[/bold red]")
            for error in result.errors[:5]:
                lines.append(f"  [red]- {error}[/red]")
            if len(result.errors) > 5:
                lines.append(f"  [dim]... and {len(result.errors) - 5} more[/dim]")
            border_style = "red"

        console.print(Panel(
            "\n".join(lines),
            title=title,
            border_style=border_style,
        ))

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("auto-watch")
def auto_watch(
    target: Optional[str] = typer.Argument(
        None,
        help="Path to watch (file or directory). Defaults to current directory.",
    ),
    approve_all: bool = typer.Option(
        False,
        "--approve-all",
        "-a",
        help="Auto-approve all fixes (full autopilot mode)",
    ),
) -> None:
    """
    Watch mode: continuously monitor for changes and auto-fix.

    Watches the target path for file changes and automatically runs the
    detection-fix loop when changes are detected. Press Ctrl+C to stop.

    Examples:
        swarm-attack qa auto-watch                  # Watch current directory
        swarm-attack qa auto-watch src/             # Watch specific path
        swarm-attack qa auto-watch --approve-all   # Full autopilot mode
    """
    try:
        orchestrator = _get_auto_fix_orchestrator()

        console.print("[cyan]Starting watch mode...[/cyan]")
        if target:
            console.print(f"[dim]Watching:[/dim] {target}")
        else:
            console.print("[dim]Watching:[/dim] current directory")
        console.print(f"[dim]Auto-approve:[/dim] {approve_all}")
        console.print("[dim]Press Ctrl+C to stop[/dim]")
        console.print()

        orchestrator.watch(
            target=target,
            auto_approve=approve_all,
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
