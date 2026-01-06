"""Analyze CLI commands for static analysis.

Implements the `swarm-attack analyze` sub-app for running static analysis tools
(pytest, mypy, ruff) and displaying results.

Commands:
- analyze all: Run all detectors and display results
- analyze all --create-bugs: Also create BugState entries
- analyze tests: Run pytest only
- analyze types: Run mypy only
- analyze lint: Run ruff only
- analyze lint --fix: Run ruff --fix
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from swarm_attack.cli.common import get_config_or_default, get_console
from swarm_attack.static_analysis.detector import StaticBugDetector
from swarm_attack.static_analysis.models import StaticAnalysisResult, StaticBugReport

if TYPE_CHECKING:
    pass

# Create analyze command group
app = typer.Typer(
    name="analyze",
    help="Static analysis commands (pytest, mypy, ruff)",
    no_args_is_help=True,
)

console = get_console()


def _format_severity(severity: str) -> str:
    """Format severity with color."""
    if severity == "critical":
        return "[red]CRITICAL[/red]"
    elif severity == "moderate":
        return "[yellow]MODERATE[/yellow]"
    else:
        return "[dim]MINOR[/dim]"


def _format_source(source: str) -> str:
    """Format source tool with color."""
    if source == "pytest":
        return "[cyan]pytest[/cyan]"
    elif source == "mypy":
        return "[magenta]mypy[/magenta]"
    elif source == "ruff":
        return "[blue]ruff[/blue]"
    return source


def _display_bugs_by_severity(bugs: list[StaticBugReport], console: Console) -> None:
    """Display bugs grouped by severity in Rich tables."""
    if not bugs:
        console.print("[green]No bugs found![/green]")
        return

    # Group bugs by severity
    critical_bugs = [b for b in bugs if b.severity == "critical"]
    moderate_bugs = [b for b in bugs if b.severity == "moderate"]
    minor_bugs = [b for b in bugs if b.severity == "minor"]

    # Display critical bugs first
    if critical_bugs:
        table = Table(title="[red]Critical Bugs[/red]", show_lines=True)
        table.add_column("Source", style="cyan", width=8)
        table.add_column("File", style="dim")
        table.add_column("Line", justify="right", width=6)
        table.add_column("Code", width=15)
        table.add_column("Message")

        for bug in critical_bugs:
            table.add_row(
                bug.source,
                bug.file_path,
                str(bug.line_number),
                bug.error_code,
                bug.message[:60] + "..." if len(bug.message) > 60 else bug.message,
            )
        console.print(table)
        console.print()

    # Display moderate bugs
    if moderate_bugs:
        table = Table(title="[yellow]Moderate Bugs[/yellow]", show_lines=True)
        table.add_column("Source", style="cyan", width=8)
        table.add_column("File", style="dim")
        table.add_column("Line", justify="right", width=6)
        table.add_column("Code", width=15)
        table.add_column("Message")

        for bug in moderate_bugs:
            table.add_row(
                bug.source,
                bug.file_path,
                str(bug.line_number),
                bug.error_code,
                bug.message[:60] + "..." if len(bug.message) > 60 else bug.message,
            )
        console.print(table)
        console.print()

    # Display minor bugs
    if minor_bugs:
        table = Table(title="[dim]Minor Bugs[/dim]", show_lines=True)
        table.add_column("Source", style="cyan", width=8)
        table.add_column("File", style="dim")
        table.add_column("Line", justify="right", width=6)
        table.add_column("Code", width=15)
        table.add_column("Message")

        for bug in minor_bugs:
            table.add_row(
                bug.source,
                bug.file_path,
                str(bug.line_number),
                bug.error_code,
                bug.message[:60] + "..." if len(bug.message) > 60 else bug.message,
            )
        console.print(table)
        console.print()


def _display_summary(result: StaticAnalysisResult, console: Console) -> None:
    """Display summary panel."""
    bugs = result.bugs
    critical_count = len([b for b in bugs if b.severity == "critical"])
    moderate_count = len([b for b in bugs if b.severity == "moderate"])
    minor_count = len([b for b in bugs if b.severity == "minor"])

    lines = [
        f"[bold]Total bugs:[/bold] {len(bugs)}",
        f"  [red]Critical:[/red] {critical_count}",
        f"  [yellow]Moderate:[/yellow] {moderate_count}",
        f"  [dim]Minor:[/dim] {minor_count}",
        "",
        f"[bold]Tools run:[/bold] {', '.join(result.tools_run) or 'none'}",
    ]

    if result.tools_skipped:
        lines.append(f"[bold]Tools skipped:[/bold] {', '.join(result.tools_skipped)}")

    border_style = "red" if critical_count > 0 else "yellow" if moderate_count > 0 else "green"

    console.print(Panel(
        "\n".join(lines),
        title="Analysis Summary",
        border_style=border_style,
    ))


def _create_bugs_from_reports(bugs: list[StaticBugReport], console: Console) -> list[str]:
    """Create BugState entries from static analysis reports.

    Args:
        bugs: List of static bug reports to create bugs from
        console: Console for output

    Returns:
        List of created bug IDs
    """
    from swarm_attack.bug_orchestrator import BugOrchestrator

    config = get_config_or_default()
    orchestrator = BugOrchestrator(config)
    created_ids: list[str] = []

    for bug in bugs:
        # Build description for bug
        description = f"[{bug.source}] {bug.error_code}: {bug.message}"

        # Use file path and line number as part of bug ID
        bug_id = f"static-{bug.source}-{bug.file_path.replace('/', '-').replace('.', '-')}-L{bug.line_number}"
        # Truncate if too long
        if len(bug_id) > 50:
            bug_id = bug_id[:50]

        result = orchestrator.init_bug(
            description=description,
            bug_id=bug_id,
            test_path=bug.file_path if bug.source == "pytest" else None,
            error_message=bug.message,
        )

        if result.success:
            created_ids.append(bug_id)
        else:
            # Bug may already exist, skip silently
            pass

    return created_ids


@app.command("all")
def analyze_all(
    path: str = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to analyze (default: current directory)",
    ),
    create_bugs: bool = typer.Option(
        False,
        "--create-bugs",
        help="Create BugState entries for discovered bugs",
    ),
) -> None:
    """
    Run all static analysis detectors (pytest, mypy, ruff).

    Displays bugs grouped by severity with summary statistics.
    Use --create-bugs to create Bug Bash entries for each bug found.
    """
    try:
        detector = StaticBugDetector()

        console.print("[cyan]Running all static analysis tools...[/cyan]")
        console.print()

        with console.status("[yellow]Analyzing...[/yellow]"):
            result = detector.detect_all(path)

        # Display bugs by severity
        _display_bugs_by_severity(result.bugs, console)

        # Display summary
        _display_summary(result, console)

        # Create bugs if requested
        if create_bugs and result.bugs:
            console.print()
            console.print("[cyan]Creating Bug Bash entries...[/cyan]")
            created_ids = _create_bugs_from_reports(result.bugs, console)

            if created_ids:
                console.print(Panel(
                    f"[green]Created {len(created_ids)} bug(s):[/green]\n\n" +
                    "\n".join(f"  - {bid}" for bid in created_ids[:10]) +
                    (f"\n  ... and {len(created_ids) - 10} more" if len(created_ids) > 10 else ""),
                    title="Bugs Created",
                    border_style="green",
                ))
            else:
                console.print("[dim]No new bugs created (may already exist)[/dim]")

        # Exit with appropriate code
        if result.bugs:
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("tests")
def analyze_tests(
    path: str = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to test file or directory (default: current directory)",
    ),
) -> None:
    """
    Run pytest and display test failures.

    Runs pytest with JSON output to detect test failures and displays
    them grouped by severity.
    """
    try:
        detector = StaticBugDetector()

        console.print("[cyan]Running pytest...[/cyan]")
        console.print()

        with console.status("[yellow]Running tests...[/yellow]"):
            bugs = detector.detect_from_tests(path)

        # Display bugs
        _display_bugs_by_severity(bugs, console)

        # Summary
        if bugs:
            critical_count = len([b for b in bugs if b.severity == "critical"])
            moderate_count = len([b for b in bugs if b.severity == "moderate"])
            minor_count = len([b for b in bugs if b.severity == "minor"])

            console.print(Panel(
                f"[bold]Test failures:[/bold] {len(bugs)}\n"
                f"  [red]Critical:[/red] {critical_count}\n"
                f"  [yellow]Moderate:[/yellow] {moderate_count}\n"
                f"  [dim]Minor:[/dim] {minor_count}",
                title="pytest Summary",
                border_style="red" if critical_count > 0 else "yellow" if moderate_count > 0 else "green",
            ))
            raise typer.Exit(1)
        else:
            console.print(Panel(
                "[green]All tests passed![/green]",
                title="pytest Summary",
                border_style="green",
            ))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("types")
def analyze_types(
    path: str = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to analyze (default: current directory)",
    ),
) -> None:
    """
    Run mypy and display type errors.

    Runs mypy with JSON output to detect type errors and displays
    them grouped by severity.
    """
    try:
        detector = StaticBugDetector()

        console.print("[cyan]Running mypy...[/cyan]")
        console.print()

        with console.status("[yellow]Type checking...[/yellow]"):
            bugs = detector.detect_from_types(path)

        # Display bugs
        _display_bugs_by_severity(bugs, console)

        # Summary
        if bugs:
            moderate_count = len([b for b in bugs if b.severity == "moderate"])
            minor_count = len([b for b in bugs if b.severity == "minor"])

            console.print(Panel(
                f"[bold]Type errors:[/bold] {len(bugs)}\n"
                f"  [yellow]Moderate:[/yellow] {moderate_count}\n"
                f"  [dim]Minor:[/dim] {minor_count}",
                title="mypy Summary",
                border_style="yellow" if moderate_count > 0 else "dim",
            ))
            raise typer.Exit(1)
        else:
            console.print(Panel(
                "[green]No type errors![/green]",
                title="mypy Summary",
                border_style="green",
            ))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("lint")
def analyze_lint(
    path: str = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to lint (default: current directory)",
    ),
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Automatically fix linting issues where possible",
    ),
) -> None:
    """
    Run ruff and display lint issues.

    Runs ruff with JSON output to detect lint issues and displays
    them grouped by severity. Use --fix to auto-fix issues.
    """
    try:
        detector = StaticBugDetector()

        if fix:
            console.print("[cyan]Running ruff --fix...[/cyan]")
            console.print()

            # Run ruff fix directly
            cmd = ["ruff", "check", "--fix"]
            if path:
                cmd.append(path)

            with console.status("[yellow]Fixing lint issues...[/yellow]"):
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            if result.returncode == 0:
                console.print(Panel(
                    "[green]Lint issues fixed successfully![/green]",
                    title="ruff --fix Summary",
                    border_style="green",
                ))
            else:
                # Still show remaining issues
                console.print("[yellow]Some issues may remain after auto-fix[/yellow]")
                console.print()

        console.print("[cyan]Running ruff...[/cyan]")
        console.print()

        with console.status("[yellow]Linting...[/yellow]"):
            bugs = detector.detect_from_lint(path)

        # Display bugs
        _display_bugs_by_severity(bugs, console)

        # Summary
        if bugs:
            critical_count = len([b for b in bugs if b.severity == "critical"])
            moderate_count = len([b for b in bugs if b.severity == "moderate"])
            minor_count = len([b for b in bugs if b.severity == "minor"])

            console.print(Panel(
                f"[bold]Lint issues:[/bold] {len(bugs)}\n"
                f"  [red]Critical (security):[/red] {critical_count}\n"
                f"  [yellow]Moderate:[/yellow] {moderate_count}\n"
                f"  [dim]Minor:[/dim] {minor_count}",
                title="ruff Summary",
                border_style="red" if critical_count > 0 else "yellow" if moderate_count > 0 else "dim",
            ))
            raise typer.Exit(1)
        else:
            console.print(Panel(
                "[green]No lint issues![/green]",
                title="ruff Summary",
                border_style="green",
            ))

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
