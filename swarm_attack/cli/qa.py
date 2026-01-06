"""QA commands for ad-hoc testing and reporting.

Commands for the QA pipeline: probe, report, bugs, semantic-test, regression-status, regression.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

import json
import subprocess
from enum import Enum
from pathlib import Path
from typing import Optional, List

import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from swarm_attack.cli.common import get_console

# Create QA command group
qa_app = typer.Typer(
    name="qa",
    help="QA testing commands for ad-hoc endpoint testing and reporting",
    no_args_is_help=True,
)

console = get_console()


@qa_app.command("probe")
def probe_command(
    url: str = typer.Argument(
        ...,
        help="URL to probe (e.g., http://localhost:8080/api/health)",
    ),
    method: str = typer.Option(
        "GET",
        "--method",
        "-m",
        help="HTTP method to use (GET, POST, PUT, DELETE, etc.)",
    ),
    expect: Optional[int] = typer.Option(
        None,
        "--expect",
        "-e",
        help="Expected HTTP status code",
    ),
    header: Optional[List[str]] = typer.Option(
        None,
        "--header",
        "-H",
        help="Custom header in 'Name: Value' format (can be repeated)",
    ),
    body: Optional[str] = typer.Option(
        None,
        "--body",
        "-b",
        help="Request body (JSON)",
    ),
    timeout: float = typer.Option(
        30.0,
        "--timeout",
        "-t",
        help="Request timeout in seconds",
    ),
) -> None:
    """
    Probe an HTTP endpoint and display the response.

    A lightweight command for ad-hoc endpoint testing without
    requiring full QA session setup.

    Example:
        swarm-attack qa probe http://localhost:8080/api/health
        swarm-attack qa probe http://localhost:8080/api/users --method POST --body '{"name": "test"}'
        swarm-attack qa probe http://localhost:8080/api/health --expect 200
    """
    import httpx

    # Parse headers
    headers = {}
    if header:
        for h in header:
            if ":" in h:
                key, value = h.split(":", 1)
                headers[key.strip()] = value.strip()

    # Parse body
    json_body = None
    if body:
        try:
            json_body = json.loads(body)
        except json.JSONDecodeError:
            # Use as raw string if not valid JSON
            pass

    # Make request
    try:
        method_upper = method.upper()
        request_func = getattr(httpx, method_upper.lower(), httpx.get)

        kwargs = {
            "url": url,
            "headers": headers,
            "timeout": timeout,
        }

        if json_body is not None and method_upper in ("POST", "PUT", "PATCH"):
            kwargs["json"] = json_body
        elif body and method_upper in ("POST", "PUT", "PATCH"):
            kwargs["content"] = body

        response = request_func(**kwargs)

        # Build result display
        status_code = response.status_code
        elapsed = response.elapsed.total_seconds()

        # Determine if status matches expectation
        status_style = "green" if status_code < 400 else "red"
        if expect is not None:
            if status_code == expect:
                match_text = "[green]PASS[/green]"
            else:
                match_text = f"[red]FAIL[/red] (expected {expect})"
                status_style = "red"
        else:
            match_text = ""

        # Build info lines
        info_lines = [
            f"[bold]URL:[/bold] {url}",
            f"[bold]Method:[/bold] {method_upper}",
            f"[bold]Status:[/bold] [{status_style}]{status_code}[/{status_style}] {match_text}",
            f"[bold]Time:[/bold] {elapsed:.3f}s",
        ]

        if response.headers.get("content-type"):
            info_lines.append(f"[bold]Content-Type:[/bold] {response.headers['content-type']}")

        # Show response preview
        response_text = response.text[:500]
        if len(response.text) > 500:
            response_text += "... (truncated)"

        if response_text:
            info_lines.append("")
            info_lines.append("[bold]Response:[/bold]")
            info_lines.append(response_text)

        border_style = "green" if (expect is None or status_code == expect) and status_code < 400 else "red"

        console.print(
            Panel(
                "\n".join(info_lines),
                title="Probe Result",
                border_style=border_style,
            )
        )

    except Exception as e:
        console.print(
            Panel(
                f"[red]Error:[/red] {str(e)}\n\n"
                f"URL: {url}\n"
                f"Method: {method}",
                title="Probe Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)


@qa_app.command("report")
def report_command(
    session_id: Optional[str] = typer.Argument(
        None,
        help="Session ID to show report for. If omitted, shows all sessions.",
    ),
) -> None:
    """
    Show QA session report with test counts, findings, and duration.

    Displays an enhanced table with Tests, Findings, Duration, and Depth columns.

    Example:
        swarm-attack qa report
        swarm-attack qa report qa-session-abc123
    """
    from swarm_attack.cli.display import format_qa_session_table
    from swarm_attack.qa.session_store import QASessionStore
    from swarm_attack.cli.common import get_config_or_default

    config = get_config_or_default()
    store = QASessionStore(config.repo_root)

    if session_id:
        # Show single session
        session = store.load(session_id)
        if session is None:
            console.print(f"[red]Error:[/red] Session '{session_id}' not found.")
            raise typer.Exit(1)

        table = format_qa_session_table([session])
        console.print(table)
    else:
        # Show all sessions
        sessions = store.list_sessions()
        if not sessions:
            console.print(
                Panel(
                    "[dim]No QA sessions found.[/dim]\n\n"
                    "Start a QA session or probe an endpoint:\n"
                    "  [cyan]swarm-attack qa probe http://localhost:8080/api/health[/cyan]",
                    title="QA Sessions",
                    border_style="dim",
                )
            )
            return

        # Load all session data
        session_objects = []
        for sid in sessions:
            session = store.load(sid)
            if session:
                session_objects.append(session)

        table = format_qa_session_table(session_objects)
        console.print(table)


@qa_app.command("bugs")
def bugs_command(
    session_id: Optional[str] = typer.Option(
        None,
        "--session",
        "-s",
        help="Filter bugs by session ID.",
    ),
    severity: Optional[str] = typer.Option(
        None,
        "--severity",
        help="Filter by severity (critical, moderate, minor).",
    ),
) -> None:
    """
    List QA findings/bugs with session context and suggested actions.

    Displays findings with Session, Timestamp columns and action suggestions.

    Example:
        swarm-attack qa bugs
        swarm-attack qa bugs --session qa-session-abc123
        swarm-attack qa bugs --severity critical
    """
    from swarm_attack.cli.display import format_qa_bugs_table, get_action_suggestion
    from swarm_attack.qa.session_store import QASessionStore
    from swarm_attack.cli.common import get_config_or_default

    config = get_config_or_default()
    store = QASessionStore(config.repo_root)

    # Collect all findings
    all_findings = []
    sessions = store.list_sessions()

    for sid in sessions:
        if session_id and sid != session_id:
            continue

        session = store.load(sid)
        if session and session.result and session.result.findings:
            for finding in session.result.findings:
                # Attach session context if not already set
                if not finding.session_id:
                    finding.session_id = sid
                if not finding.created_at:
                    finding.created_at = session.created_at
                all_findings.append(finding)

    # Filter by severity
    if severity:
        severity_lower = severity.lower()
        all_findings = [f for f in all_findings if f.severity == severity_lower]

    if not all_findings:
        console.print(
            Panel(
                "[dim]No QA findings found.[/dim]\n\n"
                "Run a QA session to discover issues:\n"
                "  [cyan]swarm-attack qa probe http://localhost:8080/api/health[/cyan]",
                title="QA Findings",
                border_style="dim",
            )
        )
        return

    # Display findings table
    table = format_qa_bugs_table(all_findings)
    console.print(table)

    # Show action summary
    critical = len([f for f in all_findings if f.severity == "critical"])
    moderate = len([f for f in all_findings if f.severity == "moderate"])
    minor = len([f for f in all_findings if f.severity == "minor"])

    if critical > 0:
        console.print(f"\n[red]{get_action_suggestion('critical')}[/red]")
    elif moderate > 0:
        console.print(f"\n[yellow]{get_action_suggestion('moderate')}[/yellow]")
    else:
        console.print(f"\n[dim]{get_action_suggestion('minor')}[/dim]")


# ============================================================================
# Semantic Testing Commands
# ============================================================================


# SemanticScope enum for CLI (mirrors the one in semantic_tester.py)
class SemanticScopeCLI(str, Enum):
    """Scope for semantic testing (CLI version)."""
    CHANGES_ONLY = "changes_only"
    AFFECTED = "affected"
    FULL_SYSTEM = "full_system"


@qa_app.command("semantic-test")
def semantic_test_command(
    changes: Optional[str] = typer.Option(
        None,
        "--changes",
        "-c",
        help="Git diff or changes to test (if omitted, uses git diff HEAD~1)",
    ),
    expected: Optional[str] = typer.Option(
        None,
        "--expected",
        "-e",
        help="Expected behavior description",
    ),
    scope: SemanticScopeCLI = typer.Option(
        SemanticScopeCLI.CHANGES_ONLY,
        "--scope",
        "-s",
        help="Testing scope: changes_only, affected, or full_system",
    ),
    project: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Run semantic testing using Claude Code CLI.

    Analyzes code changes semantically to determine what tests need to run
    and validates that the changes work as expected.

    Examples:
        swarm-attack qa semantic-test
        swarm-attack qa semantic-test --expected "User login should work"
        swarm-attack qa semantic-test --scope affected --project /path/to/project
    """
    from swarm_attack.cli.common import get_config_or_default

    config = get_config_or_default()

    # Get changes from git if not provided
    if not changes:
        try:
            result = subprocess.run(
                ["git", "diff", "HEAD~1"],
                capture_output=True,
                text=True,
                cwd=project,
                timeout=30,
            )
            changes = result.stdout or "No changes detected"
        except subprocess.TimeoutExpired:
            console.print("[red]Error:[/red] Git diff timed out")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Error getting git diff:[/red] {e}")
            changes = "Unable to detect changes"

    # Build context for semantic testing
    context = {
        "changes": changes,
        "expected_behavior": expected or "Feature should work as designed",
        "test_scope": scope.value,
        "project_root": str(Path(project).resolve()),
    }

    console.print(Panel(
        f"[bold]Scope:[/bold] {scope.value}\n"
        f"[bold]Expected:[/bold] {context['expected_behavior']}\n"
        f"[bold]Project:[/bold] {context['project_root']}\n\n"
        f"[bold]Changes Preview:[/bold]\n{changes[:500]}{'...' if len(changes) > 500 else ''}",
        title="Semantic Test Configuration",
        border_style="cyan",
    ))

    # Try to use SemanticTesterAgent if available
    try:
        from swarm_attack.qa.agents.semantic_tester import SemanticTesterAgent, SemanticScope

        with console.status("[yellow]Running semantic testing...[/yellow]"):
            agent = SemanticTesterAgent(config)
            # Convert CLI scope to agent scope
            agent_scope = SemanticScope(scope.value)
            context["test_scope"] = agent_scope
            result = agent.run(context)

        if result.success:
            output = result.output or {}
            verdict = output.get("verdict", "UNKNOWN")
            verdict_color = "green" if verdict == "PASS" else "yellow" if verdict == "PARTIAL" else "red"

            evidence = output.get("evidence", [])
            evidence_text = ""
            if evidence:
                evidence_text = "\n\n[bold]Evidence:[/bold]\n" + "\n".join(
                    f"  - {e.get('description', 'N/A')} (confidence: {e.get('confidence', 0):.0%})"
                    for e in evidence[:5]
                )

            console.print(Panel(
                f"[{verdict_color}]Semantic testing: {verdict}[/{verdict_color}]" +
                evidence_text +
                (f"\n\n[dim]Full output:[/dim]\n{json.dumps(output, indent=2)[:1000]}" if output else ""),
                title="Result",
                border_style=verdict_color,
            ))

            if verdict == "FAIL":
                raise typer.Exit(1)
        else:
            error_text = "\n".join(f"  - {e}" for e in result.errors) if result.errors else "Unknown error"
            console.print(Panel(
                f"[red]Semantic testing FAILED[/red]\n\n{error_text}",
                title="Result",
                border_style="red",
            ))
            raise typer.Exit(1)

    except ImportError:
        # SemanticTesterAgent not yet implemented - use fallback
        console.print("[yellow]Note:[/yellow] SemanticTesterAgent not yet implemented.")
        console.print("[dim]Using fallback analysis...[/dim]\n")

        # Fallback: Run basic regression scanner analysis
        try:
            from swarm_attack.qa.agents.regression import RegressionScannerAgent

            scanner = RegressionScannerAgent(config)
            scanner_result = scanner.run({"git_diff": changes, "endpoints": []})

            if scanner_result.success:
                output = scanner_result.output or {}
                console.print(Panel(
                    f"[bold]Files analyzed:[/bold] {output.get('files_analyzed', 0)}\n"
                    f"[bold]Endpoints affected:[/bold] {output.get('endpoints_affected', 0)}\n\n"
                    f"[green]Analysis complete[/green] - Review manually",
                    title="Fallback Analysis",
                    border_style="yellow",
                ))
            else:
                console.print(Panel(
                    f"[red]Analysis failed[/red]\n{scanner_result.errors}",
                    title="Fallback Analysis",
                    border_style="red",
                ))
                raise typer.Exit(1)

        except Exception as e:
            console.print(f"[red]Error during fallback analysis:[/red] {e}")
            raise typer.Exit(1)


@qa_app.command("regression-status")
def regression_status_command(
    project: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Show regression scheduler status.

    Displays the current state of the regression scheduler including
    issues until next regression, commits until regression, and last
    regression results.

    Example:
        swarm-attack qa regression-status
        swarm-attack qa regression-status --project /path/to/project
    """
    from swarm_attack.qa.regression_detector import RegressionDetector

    project_path = Path(project).resolve()
    swarm_dir = project_path / ".swarm"

    if not swarm_dir.exists():
        console.print(Panel(
            "[yellow]No .swarm directory found[/yellow]\n\n"
            "Run a QA session first to initialize the regression tracking system.",
            title="Regression Status",
            border_style="yellow",
        ))
        return

    # Try to use RegressionScheduler if available
    try:
        from swarm_attack.qa.regression_scheduler import RegressionScheduler, RegressionSchedulerConfig

        scheduler = RegressionScheduler(RegressionSchedulerConfig(), project_path)
        status = scheduler.get_status()

        console.print(Panel(
            f"[bold]Issues until regression:[/bold] {status.get('issues_until_regression', 'N/A')}\n"
            f"[bold]Commits until regression:[/bold] {status.get('commits_until_regression', 'N/A')}\n"
            f"[bold]Last regression:[/bold] {status.get('last_regression') or 'Never'}\n"
            f"[bold]Last result:[/bold] {status.get('last_result') or 'N/A'}",
            title="Regression Scheduler Status",
            border_style="cyan",
        ))

    except ImportError:
        # RegressionScheduler not yet implemented - use RegressionDetector fallback
        console.print("[yellow]Note:[/yellow] RegressionScheduler not yet implemented.")
        console.print("[dim]Using RegressionDetector fallback...[/dim]\n")

        detector = RegressionDetector(swarm_dir)
        baselines_dir = swarm_dir / "qa" / "baselines"

        # Check for baseline
        latest_baseline = baselines_dir / "latest.json" if baselines_dir.exists() else None
        has_baseline = latest_baseline and latest_baseline.exists()

        if has_baseline:
            try:
                with latest_baseline.open() as f:
                    baseline_data = json.load(f)
                baseline_session = baseline_data.get("session_id", "Unknown")
                findings_count = len(baseline_data.get("findings", []))

                console.print(Panel(
                    f"[bold]Baseline established:[/bold] Yes\n"
                    f"[bold]Baseline session:[/bold] {baseline_session}\n"
                    f"[bold]Baseline findings:[/bold] {findings_count}\n\n"
                    "[dim]Full scheduler not available - showing baseline info only[/dim]",
                    title="Regression Status (Limited)",
                    border_style="cyan",
                ))
            except Exception as e:
                console.print(f"[red]Error reading baseline:[/red] {e}")
                raise typer.Exit(1)
        else:
            console.print(Panel(
                "[bold]Baseline established:[/bold] No\n\n"
                "Run a full QA session to establish a baseline:\n"
                "  [cyan]swarm-attack qa probe http://localhost:8080/api/health[/cyan]",
                title="Regression Status",
                border_style="yellow",
            ))


@qa_app.command("regression")
def regression_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force regression run even if thresholds not met",
    ),
    check_only: bool = typer.Option(
        False,
        "--check",
        help="Only check if regression is needed, don't run",
    ),
    project: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project root directory",
    ),
    baseline: Optional[str] = typer.Option(
        None,
        "--baseline",
        "-b",
        help="Specific baseline session ID to compare against",
    ),
) -> None:
    """
    Force or check regression testing.

    Either checks if regression testing is needed based on thresholds,
    or forces a regression run to compare current state against baseline.

    Examples:
        swarm-attack qa regression --check
        swarm-attack qa regression --force
        swarm-attack qa regression --baseline qa-session-abc123
    """
    from swarm_attack.qa.regression_detector import RegressionDetector

    project_path = Path(project).resolve()
    swarm_dir = project_path / ".swarm"

    if not swarm_dir.exists():
        console.print("[red]Error:[/red] No .swarm directory found. Run a QA session first.")
        raise typer.Exit(1)

    detector = RegressionDetector(swarm_dir)
    baselines_dir = swarm_dir / "qa" / "baselines"

    # Check for baseline
    latest_baseline = baselines_dir / "latest.json" if baselines_dir.exists() else None
    has_baseline = latest_baseline and latest_baseline.exists()

    if not has_baseline:
        console.print(Panel(
            "[yellow]No baseline established[/yellow]\n\n"
            "Run a full QA session first to establish a baseline:\n"
            "  [cyan]swarm-attack qa probe http://localhost:8080/api/health[/cyan]\n\n"
            "Then run regression again to compare.",
            title="Regression Check",
            border_style="yellow",
        ))
        return

    # Try to use RegressionScheduler if available
    try:
        from swarm_attack.qa.regression_scheduler import RegressionScheduler, RegressionSchedulerConfig

        scheduler = RegressionScheduler(RegressionSchedulerConfig(), project_path)

        if check_only:
            status = scheduler.get_status()
            needs_regression = (
                status.get('issues_until_regression', 999) <= 0 or
                status.get('commits_until_regression', 999) <= 0
            )

            if needs_regression:
                console.print(Panel(
                    "[yellow]Regression testing needed[/yellow]\n\n"
                    f"Issues until regression: {status.get('issues_until_regression', 'N/A')}\n"
                    f"Commits until regression: {status.get('commits_until_regression', 'N/A')}\n\n"
                    "Run [cyan]swarm-attack qa regression --force[/cyan] to execute",
                    title="Regression Check",
                    border_style="yellow",
                ))
            else:
                console.print(Panel(
                    "[green]No regression needed yet[/green]\n\n"
                    f"Issues until regression: {status.get('issues_until_regression', 'N/A')}\n"
                    f"Commits until regression: {status.get('commits_until_regression', 'N/A')}",
                    title="Regression Check",
                    border_style="green",
                ))
            return

        if force:
            console.print("[cyan]Running forced regression...[/cyan]")
            result = scheduler.run_regression(force=True)

            if result.get("success"):
                console.print(Panel(
                    f"[green]Regression complete[/green]\n\n"
                    f"New findings: {result.get('new_findings', 0)}\n"
                    f"Fixed findings: {result.get('fixed_findings', 0)}\n"
                    f"Severity: {result.get('severity', 'N/A')}",
                    title="Regression Result",
                    border_style="green",
                ))
            else:
                console.print(Panel(
                    f"[red]Regression failed[/red]\n\n{result.get('error', 'Unknown error')}",
                    title="Regression Result",
                    border_style="red",
                ))
                raise typer.Exit(1)

    except ImportError:
        # RegressionScheduler not yet implemented - use RegressionDetector fallback
        console.print("[yellow]Note:[/yellow] RegressionScheduler not yet implemented.")
        console.print("[dim]Using RegressionDetector fallback...[/dim]\n")

        if check_only:
            console.print(Panel(
                "[yellow]Check mode requires full scheduler[/yellow]\n\n"
                "The RegressionScheduler is not yet implemented.\n"
                "Use [cyan]swarm-attack qa regression --force[/cyan] to run a manual comparison.",
                title="Regression Check",
                border_style="yellow",
            ))
            return

        if force:
            # Manual regression using detector
            console.print("[cyan]Running manual regression comparison...[/cyan]\n")

            # Load baseline
            try:
                with latest_baseline.open() as f:
                    baseline_data = json.load(f)

                baseline_findings = baseline_data.get("findings", [])

                # For now, we don't have current findings - would need to run QA session
                console.print(Panel(
                    f"[bold]Baseline session:[/bold] {baseline_data.get('session_id', 'Unknown')}\n"
                    f"[bold]Baseline findings:[/bold] {len(baseline_findings)}\n\n"
                    "[dim]To perform full regression comparison:[/dim]\n"
                    "1. Run a new QA session to collect current findings\n"
                    "2. Compare results manually or implement RegressionScheduler\n\n"
                    "[green]Baseline data loaded successfully[/green]",
                    title="Regression (Manual Mode)",
                    border_style="cyan",
                ))

            except Exception as e:
                console.print(f"[red]Error loading baseline:[/red] {e}")
                raise typer.Exit(1)
        else:
            console.print(Panel(
                "[dim]Use --force to run regression or --check to check status[/dim]",
                title="Regression",
                border_style="dim",
            ))


@qa_app.command("metrics")
def metrics_command(
    project: str = typer.Option(
        ".",
        "--project",
        "-p",
        help="Project root directory",
    ),
) -> None:
    """
    Show semantic QA metrics.

    Displays aggregated metrics from semantic testing including:
    - Total tests run
    - Pass/fail/partial rates
    - Average execution time
    - Coverage by depth (unit, integration, semantic)
    - True/false positive rates

    Example:
        swarm-attack qa metrics
        swarm-attack qa metrics --project /path/to/project
    """
    from swarm_attack.qa.metrics import SemanticQAMetrics

    project_path = Path(project).resolve()
    metrics_file = project_path / ".swarm" / "qa" / "metrics.json"

    # Load metrics
    metrics = SemanticQAMetrics(metrics_file=metrics_file)
    summary = metrics.get_summary()

    # Check if we have any data
    if summary["total_tests"] == 0:
        console.print(Panel(
            "[dim]No semantic QA metrics found.[/dim]\n\n"
            "Run semantic tests to start collecting metrics:\n"
            "  [cyan]swarm-attack qa semantic-test[/cyan]",
            title="Semantic QA Metrics",
            border_style="dim",
        ))
        return

    # Build metrics table
    table = Table(title="Semantic QA Metrics Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    # Add summary rows
    table.add_row("Total Tests", str(summary["total_tests"]))
    table.add_row("Pass Rate", f"{summary['pass_rate']:.1%}")
    table.add_row("Fail Rate", f"{summary['fail_rate']:.1%}")
    table.add_row("Partial Rate", f"{summary['partial_rate']:.1%}")
    table.add_row("Avg Execution Time", f"{summary['avg_execution_time_ms']:.1f} ms")

    # Add true/false positive rates if available
    if summary["true_positive_rate"] > 0 or summary["false_positive_rate"] > 0:
        table.add_row("True Positive Rate", f"{summary['true_positive_rate']:.1%}")
        table.add_row("False Positive Rate", f"{summary['false_positive_rate']:.1%}")

    console.print(table)

    # Show coverage by depth if available
    if summary["coverage_by_depth"]:
        depth_table = Table(title="Coverage by Depth", show_header=True, header_style="bold cyan")
        depth_table.add_column("Depth", style="bold")
        depth_table.add_column("Count", justify="right")

        for depth, count in sorted(summary["coverage_by_depth"].items()):
            depth_table.add_row(depth.capitalize(), str(count))

        console.print("")
        console.print(depth_table)


# Alias for backwards compatibility
app = qa_app
