"""Chief of Staff CLI commands.

Provides CLI commands for the Chief of Staff agent:
- checkin: Quick mid-day status check
- wrapup: End-of-day summary
- history: Review past daily logs
- next --all: Cross-feature recommendations
- progress: Show current progress snapshot
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from swarm_attack.cli.common import get_console, get_project_dir
from swarm_attack.chief_of_staff.daily_log import (
    DailyLogManager,
    DailySummary,
    DecisionType,
)
from swarm_attack.chief_of_staff.state_gatherer import StateGatherer
from swarm_attack.chief_of_staff.goal_tracker import (
    GoalTracker,
    GoalStatus,
    GoalPriority,
    DailyGoal,
)

# Create Typer app for chief-of-staff commands
app = typer.Typer(
    name="cos",
    help="Chief of Staff commands for daily workflow management",
)


def _get_daily_log_manager() -> DailyLogManager:
    """Get configured DailyLogManager."""
    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
    base_path = project_dir / ".swarm" / "chief-of-staff" / "daily-log"
    return DailyLogManager(base_path)


def _get_state_gatherer() -> StateGatherer:
    """Get configured StateGatherer."""
    # StateGatherer takes a config, but can work with a minimal one
    class MinimalConfig:
        pass
    return StateGatherer(MinimalConfig())


def _get_progress_tracker():
    """Get configured ProgressTracker."""
    from swarm_attack.chief_of_staff.progress import ProgressTracker

    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
    base_path = project_dir / ".swarm" / "chief-of-staff" / "progress"
    return ProgressTracker(base_path)


def _format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string (e.g., "1h 30min" or "45min").
    """
    if seconds == 0:
        return "0min"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}min"
        return f"{hours}h"
    return f"{minutes}min"


def _parse_duration_string(duration: str) -> int:
    """Parse duration string to minutes.

    Args:
        duration: Duration string like '2h', '90m', or '1h30m'.

    Returns:
        Duration in minutes.

    Raises:
        ValueError: If the format is invalid.
    """
    import re

    # Check for negative values
    if duration.startswith('-'):
        raise ValueError("Duration cannot be negative")

    # Match patterns like 2h, 90m, 1h30m
    hours_match = re.search(r'(\d+)h', duration.lower())
    mins_match = re.search(r'(\d+)m', duration.lower())

    if not hours_match and not mins_match:
        raise ValueError(f"Invalid duration format: {duration}")

    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(mins_match.group(1)) if mins_match else 0

    return hours * 60 + minutes


@app.command("standup")
def standup_command(
    since: Optional[str] = typer.Option(None, "--since", "-s", help="Filter to changes since datetime (ISO format)"),
    github: bool = typer.Option(False, "--github", "-g", help="Include GitHub state (slower)"),
) -> None:
    """Morning standup briefing.

    Provides interactive morning briefing with:
    - Yesterday's plan vs actual comparison
    - Repository health summary
    - Items needing attention
    - Recommended tasks for today
    """
    console = get_console()

    try:
        dlm = _get_daily_log_manager()
        gatherer = _get_state_gatherer()
        tracker = GoalTracker(dlm)

        # Parse since datetime if provided
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                console.print(f"[red]Invalid datetime format: {since}[/red]")
                console.print("Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
                raise typer.Exit(1)

        # Get current state
        console.print("[dim]Gathering repository state...[/dim]")
        snapshot = gatherer.gather(include_github=github)

        console.print()
        console.print(Panel(
            f"[bold]Morning Standup[/bold] - {date.today().isoformat()}",
            style="cyan",
        ))

        # Section 1: Yesterday's Plan vs Actual
        comparison = tracker.compare_plan_vs_actual()
        console.print("\n[bold]Yesterday's Plan vs Actual:[/bold]")

        if comparison["total_planned"] > 0:
            rate = comparison["completion_rate"] * 100
            console.print(f"  Completed: {comparison['total_completed']}/{comparison['total_planned']} ({rate:.0f}%)")
            console.print(f"  Estimated: {comparison['estimated_minutes']}min | Actual: {comparison['actual_minutes']}min")

            if comparison["incomplete_goals"]:
                console.print(f"  [yellow]Incomplete: {len(comparison['incomplete_goals'])} goals[/yellow]")
        else:
            console.print("  [dim]No plan recorded for yesterday.[/dim]")

        # Section 2: Repository Health
        console.print("\n[bold]Repository Health:[/bold]")
        console.print(f"  Branch: {snapshot.git.current_branch}")
        console.print(f"  Tests: {snapshot.tests.total_tests} tests")
        console.print(f"  Features: {len(snapshot.features)} ({len([f for f in snapshot.features if f.phase == 'IMPLEMENTING'])} in progress)")
        console.print(f"  Bugs: {len(snapshot.bugs)} tracked")
        console.print(f"  Cost Today: ${snapshot.cost_today:.2f} | Week: ${snapshot.cost_weekly:.2f}")

        if snapshot.git.modified_files:
            console.print(f"  [yellow]Uncommitted: {len(snapshot.git.modified_files)} files[/yellow]")

        # Section 3: Items Needing Attention
        console.print("\n[bold]Attention Items:[/bold]")
        attention_count = 0

        # Check for specs needing approval
        specs_pending = [s for s in snapshot.specs if s.review_status == "pending"]
        if specs_pending:
            for spec in specs_pending:
                console.print(f"  [yellow]APPROVAL[/yellow] Spec '{spec.name}' ready for review")
                attention_count += 1

        # Check for blocked features
        blocked_features = [f for f in snapshot.features if f.phase == "SPEC_NEEDS_APPROVAL"]
        if blocked_features:
            for f in blocked_features:
                console.print(f"  [red]BLOCKED[/red] Feature '{f.feature_id}' waiting for approval")
                attention_count += 1

        # Check for interrupted sessions
        if snapshot.interrupted_sessions:
            for session in snapshot.interrupted_sessions:
                console.print(f"  [yellow]INTERRUPTED[/yellow] Session '{session.session_id}' for {session.feature_id}")
                attention_count += 1

        if attention_count == 0:
            console.print("  [green]No urgent items.[/green]")

        # Section 4: Recommended Tasks
        console.print("\n[bold]Recommended Tasks:[/bold]")
        recommendations = tracker.generate_recommendations(snapshot)

        if recommendations:
            # Show top 4 recommendations
            for i, rec in enumerate(recommendations[:4], 1):
                priority_color = {
                    "P1": "red",
                    "P2": "yellow",
                    "P3": "blue",
                }.get(rec.priority.value, "white")
                console.print(f"  {i}. [{priority_color}][{rec.priority.value}][/{priority_color}] {rec.action}")
                console.print(f"     [dim]{rec.reason}[/dim]")
        else:
            console.print("  [dim]No recommendations at this time.[/dim]")

        # Section 5: Carryover Goals
        carryover = tracker.get_carryover_goals()
        if carryover:
            console.print("\n[bold]Carryover from Yesterday:[/bold]")
            for g in carryover:
                console.print(f"  - {g.description} (~{g.estimated_minutes}min)")

        # Interactive goal selection
        console.print("\n[bold]Set Today's Goals:[/bold]")

        # Combine carryover and recommendations into goal options
        goal_options = []

        # Add carryover goals
        for g in carryover[:2]:
            goal_options.append({
                "description": g.description,
                "priority": g.priority.value if hasattr(g.priority, 'value') else g.priority,
                "estimated_minutes": g.estimated_minutes,
                "linked_feature": g.linked_feature,
                "linked_bug": g.linked_bug,
            })

        # Add top recommendations as potential goals
        for rec in recommendations[:3]:
            goal_options.append({
                "description": rec.action,
                "priority": "high" if rec.priority.value == "P1" else "medium" if rec.priority.value == "P2" else "low",
                "estimated_minutes": 60,  # Default estimate
                "linked_feature": rec.linked_item if not rec.linked_item.startswith("bug") else None,
                "linked_bug": rec.linked_item if rec.linked_item.startswith("bug") else None,
            })

        if goal_options:
            console.print("\nSuggested goals (select by number, comma-separated):")
            for i, opt in enumerate(goal_options[:4], 1):
                console.print(f"  {i}. {opt['description']} (~{opt['estimated_minutes']}min) [{opt['priority']}]")

            console.print("  0. Skip goal setting for now")
            console.print()

            selection = typer.prompt("Select goals", default="0")

            if selection != "0":
                selected_indices = [int(x.strip()) - 1 for x in selection.split(",") if x.strip().isdigit()]
                selected_goals = []

                for idx in selected_indices:
                    if 0 <= idx < len(goal_options):
                        opt = goal_options[idx]
                        goal = DailyGoal(
                            goal_id=f"goal-{date.today().isoformat()}-{idx+1}",
                            description=opt["description"],
                            priority=GoalPriority(opt["priority"]),
                            estimated_minutes=opt["estimated_minutes"],
                            linked_feature=opt.get("linked_feature"),
                            linked_bug=opt.get("linked_bug"),
                        )
                        selected_goals.append(goal)

                if selected_goals:
                    tracker.set_goals(selected_goals)
                    console.print(f"\n[green]✓ Set {len(selected_goals)} goals for today.[/green]")
        else:
            console.print("  [dim]No goals suggested. Use 'swarm-attack cos next --all' to see recommendations.[/dim]")

        # Record standup in daily log
        from swarm_attack.chief_of_staff.daily_log import StandupSession

        standup = StandupSession(
            timestamp=datetime.now(),
            completed_yesterday=[g.description for g in tracker.get_yesterday_goals() if g.status == GoalStatus.COMPLETE],
            planned_today=[g.description for g in tracker.get_today_goals()],
            blockers=[f.feature_id for f in blocked_features],
        )
        dlm.add_standup(standup)

        console.print("\n[dim]Standup recorded in daily log.[/dim]")
        console.print()

    except Exception as e:
        import traceback
        console.print(f"[red]Error during standup:[/red]")
        console.print(f"[red]{type(e).__name__}: {e}[/red]")
        console.print()
        console.print("[dim]Full traceback:[/dim]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command("checkin")
def checkin_command() -> None:
    """Quick mid-day status check.

    Shows current goal progress, new blockers, and cost spent today.
    Designed to complete in <10 seconds.
    """
    console = get_console()

    try:
        dlm = _get_daily_log_manager()
        gatherer = _get_state_gatherer()
        tracker = GoalTracker(dlm)

        # Get current state (skip expensive GitHub calls)
        snapshot = gatherer.gather(include_github=False)

        # Get today's goals
        goals = tracker.get_today_goals()

        # Calculate progress
        total_goals = len(goals)
        completed = sum(1 for g in goals if g.status == GoalStatus.COMPLETE)
        in_progress = sum(1 for g in goals if g.status == GoalStatus.IN_PROGRESS)
        blocked = sum(1 for g in goals if g.status == GoalStatus.BLOCKED)

        # Display checkin panel
        console.print()
        console.print(Panel(
            f"[bold]Mid-Day Check-in[/bold] - {date.today().isoformat()}",
            style="blue",
        ))

        # Goal progress
        if total_goals > 0:
            progress_pct = (completed / total_goals) * 100
            console.print(f"\n[bold]Goals:[/bold] {completed}/{total_goals} complete ({progress_pct:.0f}%)")
            if in_progress:
                console.print(f"  In progress: {in_progress}")
            if blocked:
                console.print(f"  [red]Blocked: {blocked}[/red]")
        else:
            console.print("\n[yellow]No goals set for today.[/yellow]")

        # Cost info
        console.print(f"\n[bold]Cost Today:[/bold] ${snapshot.cost_today:.2f}")
        console.print(f"[bold]Cost This Week:[/bold] ${snapshot.cost_weekly:.2f}")

        # Show blockers if any
        if blocked > 0:
            console.print("\n[bold red]Blocked Goals:[/bold red]")
            for g in goals:
                if g.status == GoalStatus.BLOCKED:
                    console.print(f"  - {g.description}")
                    if g.notes:
                        console.print(f"    [dim]{g.notes}[/dim]")

        # Show interrupted sessions
        if snapshot.interrupted_sessions:
            console.print(f"\n[yellow]Interrupted Sessions: {len(snapshot.interrupted_sessions)}[/yellow]")

        console.print()

    except Exception as e:
        console.print(f"[red]Error during checkin: {e}[/red]")
        raise typer.Exit(1)


@app.command("wrapup")
def wrapup_command() -> None:
    """End-of-day summary.

    Shows goal completion rate, key accomplishments, blockers,
    carryover goals for tomorrow, and total cost for the day.
    """
    console = get_console()

    try:
        dlm = _get_daily_log_manager()
        gatherer = _get_state_gatherer()
        tracker = GoalTracker(dlm)

        # Get today's goals
        goals = tracker.get_today_goals()
        snapshot = gatherer.gather(include_github=False)

        console.print()
        console.print(Panel(
            f"[bold]End of Day Wrap-up[/bold] - {date.today().isoformat()}",
            style="green",
        ))

        # Goal completion
        total_goals = len(goals)
        completed = [g for g in goals if g.status == GoalStatus.COMPLETE]
        blocked = [g for g in goals if g.status == GoalStatus.BLOCKED]
        pending = [g for g in goals if g.status == GoalStatus.PENDING]
        in_progress = [g for g in goals if g.status == GoalStatus.IN_PROGRESS]

        if total_goals > 0:
            completion_rate = (len(completed) / total_goals) * 100
            console.print(f"\n[bold]Completion Rate:[/bold] {len(completed)}/{total_goals} ({completion_rate:.0f}%)")
        else:
            console.print("\n[yellow]No goals were set for today.[/yellow]")

        # Key accomplishments
        if completed:
            console.print("\n[bold green]Accomplishments:[/bold green]")
            for g in completed:
                time_info = ""
                if g.actual_minutes is not None:
                    time_info = f" ({g.actual_minutes}min)"
                console.print(f"  [green]✓[/green] {g.description}{time_info}")

        # Blockers for tomorrow
        if blocked:
            console.print("\n[bold red]Blockers:[/bold red]")
            for g in blocked:
                console.print(f"  [red]![/red] {g.description}")
                if g.notes:
                    console.print(f"    [dim]{g.notes}[/dim]")

        # Carryover goals
        carryover = pending + in_progress
        if carryover:
            console.print("\n[bold yellow]Carryover for Tomorrow:[/bold yellow]")
            for g in carryover:
                status_icon = "-" if g.status == GoalStatus.IN_PROGRESS else " "
                console.print(f"  [{status_icon}] {g.description} (~{g.estimated_minutes}min)")

        # Cost summary
        console.print(f"\n[bold]Today's Cost:[/bold] ${snapshot.cost_today:.2f}")

        # Save summary to daily log
        highlights = [g.description for g in completed]
        challenges = [g.description for g in blocked]
        tomorrow_priorities = [g.description for g in carryover]

        summary = DailySummary(
            highlights=highlights,
            challenges=challenges,
            tomorrow_priorities=tomorrow_priorities,
        )
        dlm.set_summary(summary)

        console.print("\n[dim]Summary saved to daily log.[/dim]")
        console.print()

    except Exception as e:
        console.print(f"[red]Error during wrapup: {e}[/red]")
        raise typer.Exit(1)


@app.command("history")
def history_command(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to show"),
    weekly: bool = typer.Option(False, "--weekly", "-w", help="Show weekly summary"),
    decisions: bool = typer.Option(False, "--decisions", help="Show decision log"),
    decision_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by decision type"),
) -> None:
    """Review past daily logs and decisions.

    Shows last 7 days by default. Use --weekly for weekly summary
    or --decisions to view the decision log.
    """
    console = get_console()

    try:
        dlm = _get_daily_log_manager()

        console.print()

        if decisions:
            # Show decision log
            console.print(Panel("[bold]Decision Log[/bold]", style="magenta"))

            dtype = None
            if decision_type:
                try:
                    dtype = DecisionType(decision_type.lower())
                except ValueError:
                    console.print(f"[red]Invalid decision type: {decision_type}[/red]")
                    console.print(f"Valid types: {', '.join(t.value for t in DecisionType)}")
                    raise typer.Exit(1)

            since = datetime.now() - timedelta(days=days)
            decisions_list = dlm.get_decisions(since=since, decision_type=dtype)

            if not decisions_list:
                console.print("\n[dim]No decisions found in the specified period.[/dim]")
            else:
                for d in decisions_list:
                    date_str = d.timestamp.strftime("%Y-%m-%d %H:%M")
                    console.print(f"\n[bold]{date_str}[/bold] [{d.decision_type.value}]")
                    console.print(f"  {d.description}")
                    if d.reasoning:
                        console.print(f"  [dim]Reason: {d.reasoning}[/dim]")

        elif weekly:
            # Show weekly summary
            today = date.today()
            week_num = today.isocalendar()[1]
            year = today.year

            console.print(Panel(f"[bold]Weekly Summary - Week {week_num}, {year}[/bold]", style="cyan"))

            summary_md = dlm.generate_weekly_summary(week_num, year)
            console.print(summary_md)

        else:
            # Show daily history
            console.print(Panel(f"[bold]Daily History - Last {days} Days[/bold]", style="blue"))

            logs = dlm.get_history(days)

            if not logs:
                console.print("\n[dim]No daily logs found.[/dim]")
            else:
                table = Table()
                table.add_column("Date", style="cyan")
                table.add_column("Goals", justify="center")
                table.add_column("Completion", justify="center")
                table.add_column("Highlights")

                for log in logs:
                    date_str = log.date.isoformat()
                    total = len(log.goals)
                    completed = sum(1 for g in log.goals if g.status == "complete")

                    if total > 0:
                        rate = f"{completed}/{total} ({(completed/total)*100:.0f}%)"
                    else:
                        rate = "-"

                    highlights = ""
                    if log.summary and log.summary.highlights:
                        highlights = log.summary.highlights[0][:40]
                        if len(log.summary.highlights) > 1:
                            highlights += f" (+{len(log.summary.highlights)-1})"

                    table.add_row(date_str, str(total), rate, highlights)

                console.print()
                console.print(table)

        console.print()

    except Exception as e:
        console.print(f"[red]Error showing history: {e}[/red]")
        raise typer.Exit(1)


@app.command("next")
def next_command(
    all_features: bool = typer.Option(False, "--all", "-a", help="Show cross-feature recommendations"),
) -> None:
    """Show recommended next actions.

    Use --all to see recommendations across all features, bugs, and specs.
    """
    console = get_console()

    try:
        dlm = _get_daily_log_manager()
        gatherer = _get_state_gatherer()
        tracker = GoalTracker(dlm)

        # Get current state
        snapshot = gatherer.gather(include_github=False)

        console.print()

        if all_features:
            console.print(Panel("[bold]Cross-Feature Recommendations[/bold]", style="green"))

            recommendations = tracker.generate_recommendations(snapshot)

            if not recommendations:
                console.print("\n[dim]No recommendations at this time.[/dim]")
            else:
                # Group by priority
                p1 = [r for r in recommendations if r.priority.value == "P1"]
                p2 = [r for r in recommendations if r.priority.value == "P2"]
                p3 = [r for r in recommendations if r.priority.value == "P3"]

                if p1:
                    console.print("\n[bold red]P1 - Blockers & Approvals[/bold red]")
                    for r in p1:
                        console.print(f"  [red]![/red] {r.action}")
                        console.print(f"      [dim]{r.reason} ({r.linked_item})[/dim]")

                if p2:
                    console.print("\n[bold yellow]P2 - In Progress[/bold yellow]")
                    for r in p2:
                        console.print(f"  [-] {r.action}")
                        console.print(f"      [dim]{r.reason} ({r.linked_item})[/dim]")

                if p3:
                    console.print("\n[bold blue]P3 - New Work[/bold blue]")
                    for r in p3:
                        console.print(f"  [ ] {r.action}")
                        console.print(f"      [dim]{r.reason} ({r.linked_item})[/dim]")

                # Show actionable commands
                console.print("\n[bold]Quick Commands:[/bold]")
                if p1:
                    for r in p1[:2]:
                        if "spec" in r.action.lower():
                            console.print(f"  swarm-attack feature approve {r.linked_item}")
                        elif "bug" in r.linked_item.lower():
                            console.print(f"  swarm-attack bug approve {r.linked_item}")
                if p2:
                    for r in p2[:2]:
                        if r.linked_item.startswith("bug"):
                            console.print(f"  swarm-attack bug run {r.linked_item}")
                        else:
                            console.print(f"  swarm-attack run {r.linked_item}")
        else:
            # Show current goals/next actions
            console.print(Panel("[bold]Next Actions[/bold]", style="blue"))

            goals = tracker.get_today_goals()
            pending = [g for g in goals if g.status in (GoalStatus.PENDING, GoalStatus.IN_PROGRESS)]

            if not pending:
                console.print("\n[dim]No pending goals. Run 'swarm-attack cos next --all' for recommendations.[/dim]")
            else:
                for g in pending:
                    status_icon = "-" if g.status == GoalStatus.IN_PROGRESS else " "
                    priority_color = {
                        "high": "red",
                        "medium": "yellow",
                        "low": "blue",
                    }.get(g.priority.value if hasattr(g.priority, 'value') else g.priority, "white")

                    console.print(f"  [{status_icon}] [{priority_color}]{g.description}[/{priority_color}] (~{g.estimated_minutes}min)")

        console.print()

    except Exception as e:
        console.print(f"[red]Error getting recommendations: {e}[/red]")
        raise typer.Exit(1)


@app.command("progress")
def progress_command(
    history: bool = typer.Option(False, "--history", "-H", help="Show progress history over time"),
) -> None:
    """Show current progress snapshot.

    Displays the current Chief of Staff execution progress including:
    - Goals completed/total with percentage
    - Cost spent
    - Duration
    - Current goal (if any)
    - Blockers (if any)

    Use --history to see timestamped progress history entries.
    """
    console = get_console()

    try:
        tracker = _get_progress_tracker()

        # Try to load progress from disk
        tracker.load()

        console.print()

        if history:
            # Show progress history
            console.print(Panel(
                f"[bold]Progress History[/bold] - {date.today().isoformat()}",
                style="cyan",
            ))

            history_entries = tracker.get_history()

            if not history_entries:
                console.print("\n[dim]No progress history available.[/dim]")
                console.print("[dim]Run 'swarm-attack cos autopilot' to start execution.[/dim]")
                console.print()
                return

            # Create a table for history
            table = Table()
            table.add_column("Timestamp", style="cyan")
            table.add_column("Progress", justify="center")
            table.add_column("Cost", justify="right")
            table.add_column("Duration", justify="right")
            table.add_column("Goal/Status")

            for snapshot in history_entries:
                # Format timestamp (extract just the time portion if same day)
                try:
                    ts = datetime.fromisoformat(snapshot.timestamp.replace("Z", "+00:00"))
                    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, AttributeError):
                    ts_str = snapshot.timestamp[:19] if snapshot.timestamp else "?"

                # Format progress
                pct = snapshot.completion_percent
                pct_color = "green" if pct >= 75 else "yellow" if pct >= 50 else "red"
                progress_str = f"{snapshot.goals_completed}/{snapshot.goals_total} [{pct_color}]({pct:.0f}%)[/{pct_color}]"

                # Format cost
                cost_str = f"${snapshot.cost_usd:.2f}"

                # Format duration
                duration_str = _format_duration(snapshot.duration_seconds)

                # Format goal/status
                status_str = ""
                if snapshot.current_goal:
                    status_str = snapshot.current_goal[:30]
                    if len(snapshot.current_goal) > 30:
                        status_str += "..."
                if snapshot.blockers:
                    if status_str:
                        status_str += " "
                    status_str += f"[red]({len(snapshot.blockers)} blocker(s))[/red]"

                table.add_row(ts_str, progress_str, cost_str, duration_str, status_str)

            console.print()
            console.print(table)
            console.print(f"\n[dim]Total entries: {len(history_entries)}[/dim]")

        else:
            # Show current progress snapshot (original behavior)
            console.print(Panel(
                f"[bold]Progress Snapshot[/bold] - {date.today().isoformat()}",
                style="cyan",
            ))

            current = tracker.get_current()

            if current is None:
                console.print("\n[dim]No progress data available.[/dim]")
                console.print("[dim]Run 'swarm-attack cos autopilot' to start execution.[/dim]")
                console.print()
                return

            # Goals progress
            pct = current.completion_percent
            pct_color = "green" if pct >= 75 else "yellow" if pct >= 50 else "red"
            console.print(f"\n[bold]Goals:[/bold] {current.goals_completed}/{current.goals_total} [{pct_color}]({pct:.0f}%)[/{pct_color}]")

            # Cost spent
            console.print(f"[bold]Cost Spent:[/bold] ${current.cost_usd:.2f}")

            # Duration
            duration_str = _format_duration(current.duration_seconds)
            console.print(f"[bold]Duration:[/bold] {duration_str}")

            # Current goal
            if current.current_goal:
                console.print(f"\n[bold]Current Goal:[/bold]")
                console.print(f"  [blue]{current.current_goal}[/blue]")

            # Blockers
            if current.blockers:
                console.print(f"\n[bold red]Blockers ({len(current.blockers)}):[/bold red]")
                for blocker in current.blockers:
                    console.print(f"  [red]![/red] {blocker}")

            # Timestamp
            console.print(f"\n[dim]Last updated: {current.timestamp}[/dim]")

        console.print()

    except Exception as e:
        console.print(f"[red]Error showing progress: {e}[/red]")
        raise typer.Exit(1)


def _get_autopilot_runner():
    """Get configured AutopilotRunner with real orchestrators."""
    from swarm_attack.chief_of_staff.autopilot_runner import AutopilotRunner
    from swarm_attack.chief_of_staff.autopilot_store import AutopilotSessionStore
    from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
    from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig
    from swarm_attack.cli.common import get_config_or_default, init_swarm_directory
    from swarm_attack.state_store import get_store
    from swarm_attack.orchestrator import Orchestrator
    from swarm_attack.bug_orchestrator import BugOrchestrator

    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()

    # Chief of Staff config for autopilot settings
    cos_config = ChiefOfStaffConfig()
    checkpoint_system = CheckpointSystem(cos_config)
    session_store = AutopilotSessionStore(project_dir)

    # Swarm config for orchestrators
    swarm_config = get_config_or_default()
    init_swarm_directory(swarm_config)
    store = get_store(swarm_config)

    # Create orchestrators for real execution
    orchestrator = Orchestrator(swarm_config, state_store=store)
    bug_orchestrator = BugOrchestrator(swarm_config)

    return AutopilotRunner(
        config=cos_config,
        checkpoint_system=checkpoint_system,
        session_store=session_store,
        orchestrator=orchestrator,
        bug_orchestrator=bug_orchestrator,
    )


@app.command("autopilot")
def autopilot_command(
    budget: float = typer.Option(10.0, "--budget", "-b", help="Budget limit in USD"),
    duration: str = typer.Option("2h", "--duration", "-d", help="Duration limit (e.g., 2h, 90m)"),
    until: Optional[str] = typer.Option(None, "--until", "-u", help="Stop trigger keyword"),
    resume_id: Optional[str] = typer.Option(None, "--resume", "-r", help="Resume paused session by ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be executed without running"),
    list_sessions: bool = typer.Option(False, "--list", "-l", help="List paused sessions"),
    cancel_id: Optional[str] = typer.Option(None, "--cancel", help="Cancel a session by ID"),
) -> None:
    """Run autopilot to execute today's goals.

    Autopilot executes goals with budget/time limits and checkpoint gates.
    It pauses for approvals, high-risk actions, and budget/time limits.

    Examples:
        swarm-attack cos autopilot                    # Run with defaults
        swarm-attack cos autopilot -b 5.0 -d 1h      # Custom budget/duration
        swarm-attack cos autopilot --until approval   # Stop at first approval
        swarm-attack cos autopilot --resume <id>      # Resume paused session
        swarm-attack cos autopilot --list             # List paused sessions
        swarm-attack cos autopilot --cancel <id>      # Cancel a session
    """
    from swarm_attack.validation.input_validator import InputValidator, ValidationError

    console = get_console()

    # BUG-7, BUG-16: Validate budget (must be positive, non-zero)
    budget_result = InputValidator.validate_positive_float(budget, "Budget")
    if isinstance(budget_result, ValidationError):
        console.print(f"[red]Error:[/red] {budget_result.message}")
        console.print(f"  Expected: {budget_result.expected}")
        console.print(f"  Got: {budget_result.got}")
        if budget_result.hint:
            console.print(f"  Hint: {budget_result.hint}")
        raise typer.Exit(1)

    # BUG-8: Validate duration format and value
    # Parse duration to validate it's not negative
    try:
        duration_minutes = _parse_duration_string(duration)
        if duration_minutes <= 0:
            console.print(f"[red]Error:[/red] Duration must be positive")
            console.print(f"  Expected: positive duration like '2h' or '90m'")
            console.print(f"  Got: {duration}")
            raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid duration format: {duration}")
        console.print(f"  Expected: duration like '2h', '90m', or '1h30m'")
        console.print(f"  Hint: Use format like '2h' for 2 hours or '90m' for 90 minutes")
        raise typer.Exit(1)

    try:
        runner = _get_autopilot_runner()
        dlm = _get_daily_log_manager()
        tracker = GoalTracker(dlm)

        # Handle --list flag
        if list_sessions:
            console.print()
            console.print(Panel("[bold]Paused Autopilot Sessions[/bold]", style="yellow"))

            paused = runner.list_paused_sessions()
            if not paused:
                console.print("\n[dim]No paused sessions.[/dim]")
            else:
                table = Table()
                table.add_column("Session ID", style="cyan")
                table.add_column("Created", style="dim")
                table.add_column("Progress", justify="center")
                table.add_column("State")

                for session in paused:
                    created = session.created_at.strftime("%Y-%m-%d %H:%M") if session.created_at else "?"
                    progress = f"{len(session.completed_issues)}/{session.current_issue or 0 + 1}"
                    table.add_row(
                        session.session_id,
                        created,
                        progress,
                        f"[yellow]{session.state.value}[/yellow]",
                    )

                console.print()
                console.print(table)

            console.print()
            return

        # Handle --cancel flag
        if cancel_id:
            success = runner.cancel(cancel_id)
            if success:
                console.print(f"\n[green]✓ Cancelled session: {cancel_id}[/green]")
            else:
                console.print(f"\n[red]Session not found: {cancel_id}[/red]")
                raise typer.Exit(1)
            return

        # Handle --resume flag
        if resume_id:
            console.print()
            console.print(Panel(f"[bold]Resuming Session[/bold] {resume_id}", style="blue"))

            try:
                result = runner.resume(resume_id)
            except ValueError as e:
                console.print(f"\n[red]{e}[/red]")
                raise typer.Exit(1)

            _display_autopilot_result(console, result)
            return

        # Normal autopilot run
        console.print()
        console.print(Panel("[bold]Autopilot Mode[/bold]", style="green"))
        console.print(f"\n[dim]Budget: ${budget:.2f} | Duration: {duration} | Stop trigger: {until or 'none'}[/dim]")

        # Get today's goals
        goals = tracker.get_today_goals()

        if not goals:
            console.print("\n[yellow]No goals set for today.[/yellow]")
            console.print("Use 'swarm-attack cos standup' to set goals first.")
            return

        pending_goals = [g for g in goals if g.status in (GoalStatus.PENDING, GoalStatus.IN_PROGRESS)]

        if not pending_goals:
            console.print("\n[green]All goals already complete![/green]")
            return

        console.print(f"\n[bold]Goals to execute:[/bold] {len(pending_goals)}")
        for i, g in enumerate(pending_goals, 1):
            console.print(f"  {i}. {g.description} (~{g.estimated_minutes}min)")

        if dry_run:
            console.print("\n[yellow]Dry run - no execution[/yellow]")
            return

        # Parse duration to minutes
        duration_minutes = runner._parse_duration(duration)

        # Execute
        console.print("\n[dim]Starting autopilot...[/dim]")

        def on_goal_start(goal):
            console.print(f"\n[blue]→ Starting:[/blue] {goal.description}")

        def on_goal_complete(goal, result):
            if result.success:
                console.print(f"  [green]✓ Complete[/green] (${result.cost_usd:.2f})")
            else:
                console.print(f"  [red]✗ Failed:[/red] {result.error}")

        def on_checkpoint(trigger):
            console.print(f"\n[yellow]⚠ Checkpoint triggered:[/yellow] {trigger.trigger_type}")
            console.print(f"  Reason: {trigger.reason}")
            console.print(f"  Action: {trigger.action}")

        # Temporarily set callbacks
        runner.on_goal_start = on_goal_start
        runner.on_goal_complete = on_goal_complete
        runner.on_checkpoint = on_checkpoint

        result = runner.start(
            goals=pending_goals,
            budget_usd=budget,
            duration_minutes=duration_minutes,
            stop_trigger=until,
            dry_run=False,
        )

        _display_autopilot_result(console, result)

    except Exception as e:
        console.print(f"[red]Error during autopilot: {e}[/red]")
        raise typer.Exit(1)


def _display_autopilot_result(console: Console, result) -> None:
    """Display autopilot run result."""
    from swarm_attack.chief_of_staff.autopilot import AutopilotState

    console.print()

    if result.session.state == AutopilotState.COMPLETED:
        console.print(Panel("[bold green]Autopilot Complete[/bold green]", style="green"))
    elif result.session.state == AutopilotState.PAUSED:
        console.print(Panel("[bold yellow]Autopilot Paused[/bold yellow]", style="yellow"))
    elif result.session.state == AutopilotState.FAILED:
        console.print(Panel("[bold red]Autopilot Failed[/bold red]", style="red"))
    else:
        console.print(Panel(f"[bold]Autopilot: {result.session.state.value}[/bold]"))

    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Session ID: {result.session.session_id}")
    console.print(f"  Goals: {result.goals_completed}/{result.goals_total} completed")
    console.print(f"  Cost: ${result.total_cost_usd:.2f}")
    console.print(f"  Duration: {result.duration_seconds}s")

    if result.trigger:
        console.print(f"\n[yellow]Paused due to:[/yellow] {result.trigger.trigger_type}")
        console.print(f"  {result.trigger.reason}")
        console.print(f"\nTo resume: swarm-attack cos autopilot --resume {result.session.session_id}")

    if result.error:
        console.print(f"\n[red]Error:[/red] {result.error}")

    console.print()


def _get_checkpoint_store():
    """Get configured CheckpointStore."""
    from swarm_attack.chief_of_staff.checkpoints import CheckpointStore

    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
    base_path = project_dir / ".swarm" / "chief-of-staff" / "checkpoints"
    return CheckpointStore(base_path)


def _get_checkpoint_system():
    """Get configured CheckpointSystem."""
    from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem, CheckpointStore
    from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig

    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
    base_path = project_dir / ".swarm" / "chief-of-staff" / "checkpoints"

    config = ChiefOfStaffConfig()
    store = CheckpointStore(base_path)
    return CheckpointSystem(config=config, store=store)


@app.command("checkpoints")
def checkpoints_command() -> None:
    """List all pending checkpoints.

    Shows pending checkpoints that require human approval.
    """
    import asyncio

    console = get_console()

    try:
        store = _get_checkpoint_store()

        # BUG-15: Auto-cleanup stale checkpoints (8+ days) when viewing
        # This prevents stale hiccup checkpoints from cluttering the list
        removed = store.cleanup_stale_checkpoints_sync(max_age_days=8)
        if removed:
            console.print(f"[dim]Cleaned up {len(removed)} stale checkpoint(s).[/dim]")

        # Run async operation synchronously
        pending = asyncio.run(store.list_pending())

        console.print()
        console.print(Panel("[bold]Pending Checkpoints[/bold]", style="yellow"))

        if not pending:
            console.print("\n[dim]No pending checkpoints.[/dim]")
        else:
            for checkpoint in pending:
                # Display checkpoint info
                console.print(f"\n[bold cyan]{checkpoint.checkpoint_id}[/bold cyan]")
                console.print(f"  [bold]Trigger:[/bold] {checkpoint.trigger.value}")
                console.print(f"  [bold]Goal ID:[/bold] {checkpoint.goal_id}")
                console.print(f"  [bold]Created:[/bold] {checkpoint.created_at}")
                console.print(f"  [bold]Context:[/bold] {checkpoint.context[:100]}{'...' if len(checkpoint.context) > 100 else ''}")

                # Show options with recommendations
                console.print(f"  [bold]Options:[/bold]")
                for opt in checkpoint.options:
                    rec_marker = " [green](recommended)[/green]" if opt.is_recommended else ""
                    console.print(f"    - {opt.label}: {opt.description}{rec_marker}")

                console.print(f"  [bold]Recommendation:[/bold] {checkpoint.recommendation}")

        console.print()

    except Exception as e:
        console.print(f"[red]Error listing checkpoints: {e}[/red]")
        raise typer.Exit(1)


@app.command("approve")
def approve_command(
    checkpoint_id: str = typer.Argument(..., help="The checkpoint ID to approve"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Approval notes"),
) -> None:
    """Approve a pending checkpoint.

    Approves a checkpoint and allows execution to proceed.

    Examples:
        swarm-attack cos approve chk-abc123
        swarm-attack cos approve chk-abc123 --notes "Reviewed and approved"
    """
    import asyncio

    console = get_console()

    try:
        system = _get_checkpoint_system()

        # Resolve the checkpoint with "Proceed" option
        try:
            checkpoint = asyncio.run(
                system.resolve_checkpoint(
                    checkpoint_id=checkpoint_id,
                    chosen_option="Proceed",
                    notes=notes or "",
                )
            )
            console.print(f"\n[green]✓ Approved checkpoint: {checkpoint_id}[/green]")
            console.print(f"  Status: {checkpoint.status}")
            if notes:
                console.print(f"  Notes: {notes}")
            console.print()

        except KeyError:
            console.print(f"\n[red]Checkpoint not found: {checkpoint_id}[/red]")
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error approving checkpoint: {e}[/red]")
        raise typer.Exit(1)


@app.command("reject")
def reject_command(
    checkpoint_id: str = typer.Argument(..., help="The checkpoint ID to reject"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Rejection reason"),
) -> None:
    """Reject a pending checkpoint.

    Rejects a checkpoint and prevents execution from proceeding.

    Examples:
        swarm-attack cos reject chk-abc123
        swarm-attack cos reject chk-abc123 --notes "Too risky, need more review"
    """
    import asyncio

    console = get_console()

    try:
        system = _get_checkpoint_system()

        # Resolve the checkpoint with "Skip" option (rejection)
        try:
            checkpoint = asyncio.run(
                system.resolve_checkpoint(
                    checkpoint_id=checkpoint_id,
                    chosen_option="Skip",
                    notes=notes or "",
                )
            )
            console.print(f"\n[yellow]✗ Rejected checkpoint: {checkpoint_id}[/yellow]")
            console.print(f"  Status: {checkpoint.status}")
            if notes:
                console.print(f"  Notes: {notes}")
            console.print()

        except KeyError:
            console.print(f"\n[red]Checkpoint not found: {checkpoint_id}[/red]")
            raise typer.Exit(1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error rejecting checkpoint: {e}[/red]")
        raise typer.Exit(1)


def _get_feedback_store():
    """Get configured FeedbackStore."""
    from swarm_attack.chief_of_staff.feedback import FeedbackStore

    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
    base_path = project_dir / ".swarm" / "feedback"
    return FeedbackStore(base_path)


@app.command("feedback-list")
def feedback_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum entries to show"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
) -> None:
    """List recorded feedback.

    Shows human feedback entries recorded from checkpoint decisions.
    Use --limit to control how many entries are shown.
    Use --tag to filter by a specific tag.

    Examples:
        swarm-attack cos feedback-list
        swarm-attack cos feedback-list -n 5
        swarm-attack cos feedback-list --tag security
    """
    console = get_console()

    try:
        store = _get_feedback_store()
        store.load()

        all_feedback = store.get_all()

        console.print()
        console.print(Panel("[bold]Feedback Entries[/bold]", style="blue"))

        if not all_feedback:
            console.print("\n[dim]No feedback entries recorded.[/dim]")
            console.print()
            return

        # Filter by tag if specified
        if tag:
            filtered = [
                fb for fb in all_feedback
                if tag.lower() in [t.lower() for t in (fb.applies_to or [])]
            ]
        else:
            filtered = all_feedback

        if not filtered:
            console.print(f"\n[dim]No feedback entries with tag '{tag}'.[/dim]")
            console.print()
            return

        # Apply limit (show most recent first)
        to_show = filtered[-limit:] if len(filtered) > limit else filtered
        to_show = list(reversed(to_show))  # Most recent first

        table = Table()
        table.add_column("ID", style="cyan")
        table.add_column("Timestamp", style="dim")
        table.add_column("Type", style="yellow")
        table.add_column("Content")
        table.add_column("Tags", style="green")

        for fb in to_show:
            # Format timestamp
            ts = fb.timestamp
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%d %H:%M")
            else:
                ts_str = str(ts)[:16]

            # Truncate content if too long
            content = fb.content or ""
            if len(content) > 50:
                content = content[:47] + "..."

            # Format tags
            tags_str = ", ".join(fb.applies_to or [])

            table.add_row(
                fb.checkpoint_id,
                ts_str,
                fb.feedback_type,
                content,
                tags_str,
            )

        console.print()
        console.print(table)
        console.print(f"\n[dim]Showing {len(to_show)} of {len(filtered)} entries.[/dim]")
        console.print()

    except Exception as e:
        console.print(f"[red]Error listing feedback: {e}[/red]")
        raise typer.Exit(1)


@app.command("feedback-add")
def feedback_add(
    text: str = typer.Argument(..., help="The feedback text"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Tag for the feedback"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="Additional context"),
) -> None:
    """Add new feedback.

    Records human feedback for future reference. Feedback can be tagged
    and associated with context for easier retrieval.

    Examples:
        swarm-attack cos feedback-add "Prefer shorter function names"
        swarm-attack cos feedback-add "Security review needed" --tag security
        swarm-attack cos feedback-add "Performance issue" -t performance -c "During load test"
    """
    import uuid
    from swarm_attack.chief_of_staff.feedback import HumanFeedback

    console = get_console()

    try:
        store = _get_feedback_store()
        store.load()

        # Generate a checkpoint ID for manually added feedback
        checkpoint_id = f"manual-{uuid.uuid4().hex[:8]}"

        # Build the content (include context if provided)
        content = text
        if context:
            content = f"{text}\n\nContext: {context}"

        # Build tags list
        tags = []
        if tag:
            tags.append(tag)
        tags.append("manual")  # Mark as manually added

        # Create feedback entry
        feedback = HumanFeedback(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.now(),
            feedback_type="guidance",  # Default type for manual feedback
            content=content,
            applies_to=tags,
            expires_at=None,  # Manual feedback doesn't expire
        )

        # Save to store
        store.save(feedback)

        console.print()
        console.print(f"[green]Feedback added successfully.[/green]")
        console.print(f"  ID: {checkpoint_id}")
        if tag:
            console.print(f"  Tag: {tag}")
        console.print()

    except Exception as e:
        console.print(f"[red]Error adding feedback: {e}[/red]")
        raise typer.Exit(1)


@app.command("feedback-clear")
def feedback_clear(
    before: Optional[str] = typer.Option(None, "--before", help="Clear before date YYYY-MM-DD"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
    all_feedback: bool = typer.Option(False, "--all", help="Clear all feedback"),
) -> None:
    """Clear feedback entries.

    Clears feedback entries based on filters. At least one filter must be specified
    for safety:
    - --all: Clear all entries (requires confirmation)
    - --tag: Clear entries with specific tag
    - --before: Clear entries before a specific date

    Filters can be combined for more specific clearing.

    Examples:
        swarm-attack cos feedback-clear --all
        swarm-attack cos feedback-clear --tag security
        swarm-attack cos feedback-clear --before 2025-01-01
        swarm-attack cos feedback-clear --tag testing --before 2025-01-15
    """
    console = get_console()

    try:
        # Require at least one filter for safety
        if not (all_feedback or tag or before):
            console.print("[red]Error: Must specify at least one filter option[/red]")
            console.print("  Use --all to clear everything, or --tag/--before to filter")
            raise typer.Exit(1)

        store = _get_feedback_store()
        store.load()

        all_entries = store.get_all()
        original_count = len(all_entries)

        if original_count == 0:
            console.print("\n[dim]No feedback entries to clear.[/dim]")
            console.print()
            return

        # Parse before date if provided
        before_date = None
        if before:
            try:
                before_date = datetime.fromisoformat(before)
                # If only date provided (no time), set to end of day
                if before_date.hour == 0 and before_date.minute == 0:
                    before_date = before_date.replace(hour=23, minute=59, second=59)
            except ValueError:
                console.print(f"[red]Error: Invalid date format: {before}[/red]")
                console.print("  Use format: YYYY-MM-DD")
                raise typer.Exit(1)

        # Filter entries to keep
        entries_to_keep = []
        cleared_count = 0

        for fb in all_entries:
            should_clear = True

            # Check tag filter
            if tag:
                fb_tags = [t.lower() for t in (fb.applies_to or [])]
                if tag.lower() not in fb_tags:
                    should_clear = False

            # Check date filter
            if before_date and should_clear:
                fb_timestamp = fb.timestamp
                if isinstance(fb_timestamp, str):
                    fb_timestamp = datetime.fromisoformat(fb_timestamp.replace("Z", "+00:00"))
                if fb_timestamp >= before_date:
                    should_clear = False

            if should_clear:
                cleared_count += 1
            else:
                entries_to_keep.append(fb)

        # If using --all flag, require confirmation
        if all_feedback and cleared_count > 0:
            console.print(f"\n[yellow]Warning:[/yellow] This will clear {cleared_count} feedback entries.")
            confirm = typer.confirm("Are you sure you want to continue?")
            if not confirm:
                console.print("\n[dim]Operation cancelled.[/dim]")
                console.print()
                return

        # Handle case where nothing matches
        if cleared_count == 0:
            console.print("\n[dim]No feedback entries matched the filter criteria.[/dim]")
            console.print()
            return

        # Save the filtered list
        store._feedback = entries_to_keep
        store.save()

        console.print()
        console.print(f"[green]Cleared {cleared_count} feedback entries.[/green]")
        console.print(f"  Remaining: {len(entries_to_keep)}")
        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error clearing feedback: {e}[/red]")
        raise typer.Exit(1)


def _get_campaign_store():
    """Get configured CampaignStore."""
    from swarm_attack.chief_of_staff.campaigns import CampaignStore

    project_dir_str = get_project_dir()
    project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
    base_path = project_dir / ".swarm" / "chief-of-staff"
    return CampaignStore(base_path)


def _get_campaign_executor():
    """Get configured CampaignExecutor."""
    from swarm_attack.chief_of_staff.campaign_executor import CampaignExecutor
    from swarm_attack.chief_of_staff.config import ChiefOfStaffConfig

    config = ChiefOfStaffConfig()
    campaign_store = _get_campaign_store()
    autopilot_runner = _get_autopilot_runner()

    return CampaignExecutor(
        config=config,
        campaign_store=campaign_store,
        autopilot_runner=autopilot_runner,
    )


def _get_campaign_planner():
    """Get configured CampaignPlanner."""
    from swarm_attack.chief_of_staff.campaign_planner import CampaignPlanner

    campaign_store = _get_campaign_store()
    return CampaignPlanner(campaign_store=campaign_store)


@app.command("campaign-create")
def campaign_create(
    name: str = typer.Argument(..., help="Name of the campaign"),
    deadline: str = typer.Option(..., "--deadline", "-d", help="Deadline YYYY-MM-DD"),
    description: str = typer.Option("", "--description", help="Campaign description"),
) -> None:
    """Create a new campaign.

    Creates a campaign for multi-day feature development or bug fixing.

    Examples:
        swarm-attack cos campaign-create "Q1 Feature Sprint" --deadline 2025-01-31
        swarm-attack cos campaign-create "Bug Bash" -d 2025-01-15 --description "Fix critical bugs"
    """
    import asyncio
    from swarm_attack.chief_of_staff.campaigns import Campaign, CampaignState

    console = get_console()

    try:
        # Parse deadline
        try:
            deadline_date = date.fromisoformat(deadline)
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid deadline format: {deadline}")
            console.print("  Expected format: YYYY-MM-DD (e.g., 2025-01-31)")
            raise typer.Exit(1)

        # Validate deadline is in the future
        if deadline_date <= date.today():
            console.print("[yellow]Warning:[/yellow] Deadline is not in the future")

        # Generate campaign ID from name
        campaign_id = name.lower().replace(" ", "-")

        # Create campaign
        campaign = Campaign(
            id=campaign_id,
            name=name,
            description=description,
            state=CampaignState.PLANNING,
            start_date=date.today(),
            planned_days=(deadline_date - date.today()).days,
        )

        # Save campaign
        store = _get_campaign_store()
        asyncio.run(store.save(campaign))

        console.print()
        console.print(f"[green]Campaign created successfully.[/green]")
        console.print(f"  ID: {campaign_id}")
        console.print(f"  Name: {name}")
        console.print(f"  Deadline: {deadline}")
        console.print(f"  Duration: {campaign.planned_days} days")
        console.print(f"  State: {campaign.state.value}")
        console.print()
        console.print("[dim]Next steps:[/dim]")
        console.print(f"  1. Plan the campaign: swarm-attack cos campaign-plan {campaign_id}")
        console.print(f"  2. Start execution: swarm-attack cos campaign-run {campaign_id}")

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error creating campaign: {e}[/red]")
        raise typer.Exit(1)


@app.command("campaign-list")
def campaign_list() -> None:
    """List all campaigns.

    Shows all campaigns with their status, progress, and cost.
    """
    import asyncio
    from swarm_attack.chief_of_staff.campaigns import CampaignState

    console = get_console()

    try:
        store = _get_campaign_store()
        campaigns = asyncio.run(store.list_all())

        console.print()
        console.print(Panel("[bold]Campaigns[/bold]", style="cyan"))

        if not campaigns:
            console.print("\n[dim]No campaigns found.[/dim]")
            console.print("[dim]Create one with: swarm-attack cos campaign-create <name> --deadline YYYY-MM-DD[/dim]")
            console.print()
            return

        table = Table()
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("State", style="yellow")
        table.add_column("Progress", justify="center")
        table.add_column("Days", justify="center")
        table.add_column("Cost", justify="right")

        for campaign in campaigns:
            # Determine state color
            state_str = campaign.state.value
            if campaign.state == CampaignState.ACTIVE:
                state_str = f"[green]{state_str}[/green]"
            elif campaign.state == CampaignState.PAUSED:
                state_str = f"[yellow]{state_str}[/yellow]"
            elif campaign.state == CampaignState.COMPLETED:
                state_str = f"[blue]{state_str}[/blue]"
            elif campaign.state == CampaignState.FAILED:
                state_str = f"[red]{state_str}[/red]"

            # Calculate progress
            if campaign.planned_days > 0:
                progress_pct = (campaign.current_day / campaign.planned_days) * 100
                progress_str = f"{campaign.current_day}/{campaign.planned_days} ({progress_pct:.0f}%)"
            else:
                progress_str = f"{campaign.current_day}/?"

            # Format cost
            cost_str = f"${campaign.spent_usd:.2f}"

            # Check if behind
            days_behind = campaign.days_behind()
            days_str = str(campaign.planned_days)
            if days_behind > 0:
                days_str = f"{campaign.planned_days} [red](-{days_behind})[/red]"

            table.add_row(
                campaign.id or campaign.campaign_id,
                campaign.name,
                state_str,
                progress_str,
                days_str,
                cost_str,
            )

        console.print()
        console.print(table)
        console.print()

    except Exception as e:
        console.print(f"[red]Error listing campaigns: {e}[/red]")
        raise typer.Exit(1)


@app.command("campaign-status")
def campaign_status(
    campaign_id: str = typer.Argument(..., help="The campaign ID"),
) -> None:
    """Show campaign status.

    Displays detailed status of a campaign including milestones,
    day plans, and progress.

    Examples:
        swarm-attack cos campaign-status my-campaign
    """
    import asyncio

    console = get_console()

    try:
        store = _get_campaign_store()
        campaign = asyncio.run(store.load(campaign_id))

        if campaign is None:
            console.print(f"\n[red]Campaign not found: {campaign_id}[/red]")
            raise typer.Exit(1)

        console.print()
        console.print(Panel(f"[bold]Campaign: {campaign.name}[/bold]", style="cyan"))

        # Basic info
        console.print(f"\n[bold]ID:[/bold] {campaign.id or campaign.campaign_id}")
        console.print(f"[bold]State:[/bold] {campaign.state.value}")
        console.print(f"[bold]Description:[/bold] {campaign.description or 'No description'}")

        # Progress
        console.print(f"\n[bold]Progress:[/bold]")
        if campaign.planned_days > 0:
            progress_pct = (campaign.current_day / campaign.planned_days) * 100
            console.print(f"  Day {campaign.current_day}/{campaign.planned_days} ({progress_pct:.0f}%)")
        else:
            console.print(f"  Day {campaign.current_day}")
        console.print(f"  Start Date: {campaign.start_date}")

        # Check if behind
        days_behind = campaign.days_behind()
        if days_behind > 0:
            console.print(f"  [red]Days Behind: {days_behind}[/red]")

        # Cost
        console.print(f"\n[bold]Cost:[/bold] ${campaign.spent_usd:.2f}")
        if campaign.total_budget_usd > 0:
            console.print(f"  Budget: ${campaign.total_budget_usd:.2f}")
            remaining = campaign.total_budget_usd - campaign.spent_usd
            console.print(f"  Remaining: ${remaining:.2f}")

        # Milestones
        if campaign.milestones:
            console.print(f"\n[bold]Milestones:[/bold]")
            for m in campaign.milestones:
                status_icon = "[green]v[/green]" if m.completed else "[ ]"
                console.print(f"  {status_icon} {m.description or m.name}")

        # Day plans
        if campaign.day_plans:
            console.print(f"\n[bold]Day Plans:[/bold]")
            today = date.today()
            for dp in campaign.day_plans[:5]:  # Show first 5
                day_marker = "[cyan]>[/cyan]" if dp.date == today else " "
                status_color = "green" if dp.status == "complete" else "yellow" if dp.status == "in_progress" else "dim"
                console.print(f"  {day_marker} Day {dp.day_number} ({dp.date}): [{status_color}]{dp.status}[/{status_color}]")
                for goal in dp.goals[:3]:  # Show first 3 goals
                    console.print(f"      - {goal}")
                if len(dp.goals) > 3:
                    console.print(f"      [dim]... and {len(dp.goals) - 3} more[/dim]")
            if len(campaign.day_plans) > 5:
                console.print(f"  [dim]... and {len(campaign.day_plans) - 5} more days[/dim]")

        # Needs replan warning
        if campaign.needs_replan():
            console.print(f"\n[yellow]Warning:[/yellow] Campaign may need replanning (>30% behind)")
            console.print(f"  Run: swarm-attack cos campaign-replan {campaign_id}")

        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error getting campaign status: {e}[/red]")
        raise typer.Exit(1)


@app.command("campaign-run")
def campaign_run(
    campaign_id: str = typer.Argument(..., help="The campaign ID to run"),
) -> None:
    """Run today's goals for a campaign.

    Executes the day plan for today using the autopilot runner.

    Examples:
        swarm-attack cos campaign-run my-campaign
    """
    import asyncio

    console = get_console()

    try:
        executor = _get_campaign_executor()

        console.print()
        console.print(Panel(f"[bold]Running Campaign: {campaign_id}[/bold]", style="green"))
        console.print("[dim]Executing today's goals...[/dim]")

        try:
            result = asyncio.run(executor.execute_day(campaign_id))
        except ValueError as e:
            console.print(f"\n[red]Error: {e}[/red]")
            raise typer.Exit(1)

        # Display results
        console.print(f"\n[bold]Execution Complete[/bold]")
        console.print(f"  Goals Completed: {result.goals_completed}")

        if result.goals_blocked:
            console.print(f"  [yellow]Goals Blocked: {len(result.goals_blocked)}[/yellow]")
            for goal_id in result.goals_blocked[:5]:
                console.print(f"    - {goal_id}")
            if len(result.goals_blocked) > 5:
                console.print(f"    [dim]... and {len(result.goals_blocked) - 5} more[/dim]")

        console.print(f"  Cost: ${result.cost_usd:.2f}")

        if result.needs_replan:
            console.print(f"\n[yellow]Note:[/yellow] Campaign needs replanning (>30% behind)")
            console.print(f"  Run: swarm-attack cos campaign-replan {campaign_id}")

        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error running campaign: {e}[/red]")
        raise typer.Exit(1)


@app.command("campaign-replan")
def campaign_replan(
    campaign_id: str = typer.Argument(..., help="The campaign ID to replan"),
) -> None:
    """Replan a campaign based on progress.

    Regenerates day plans based on current progress and remaining work.

    Examples:
        swarm-attack cos campaign-replan my-campaign
    """
    import asyncio

    console = get_console()

    try:
        store = _get_campaign_store()

        # Load campaign
        campaign = asyncio.run(store.load(campaign_id))
        if campaign is None:
            console.print(f"\n[red]Campaign not found: {campaign_id}[/red]")
            raise typer.Exit(1)

        console.print()
        console.print(Panel(f"[bold]Replanning Campaign: {campaign.name}[/bold]", style="yellow"))

        # Show current state
        console.print(f"\n[bold]Current State:[/bold]")
        console.print(f"  Day {campaign.current_day}/{campaign.planned_days}")
        days_behind = campaign.days_behind()
        if days_behind > 0:
            console.print(f"  [red]Days Behind: {days_behind}[/red]")

        # Replan using campaign planner
        planner = _get_campaign_planner()

        console.print("\n[dim]Generating new plan...[/dim]")

        try:
            updated_campaign = asyncio.run(planner.replan(campaign_id))
        except Exception as e:
            console.print(f"\n[red]Replanning failed: {e}[/red]")
            raise typer.Exit(1)

        # Show updated plan
        console.print(f"\n[green]Replanning complete.[/green]")
        console.print(f"  New day plans: {len(updated_campaign.day_plans)}")

        if updated_campaign.day_plans:
            console.print(f"\n[bold]Updated Day Plans:[/bold]")
            for dp in updated_campaign.day_plans[:3]:
                console.print(f"  Day {dp.day_number} ({dp.date}): {len(dp.goals)} goals")
            if len(updated_campaign.day_plans) > 3:
                console.print(f"  [dim]... and {len(updated_campaign.day_plans) - 3} more days[/dim]")

        console.print()

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error replanning campaign: {e}[/red]")
        raise typer.Exit(1)