"""QA commands for ad-hoc testing and reporting.

Commands for the QA pipeline: probe, report, bugs.
This module should NOT import heavy modules at the top level - use lazy imports inside functions.
"""
from __future__ import annotations

import json
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


# Alias for backwards compatibility
app = qa_app
