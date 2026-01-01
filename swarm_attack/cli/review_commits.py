"""CLI command for commit quality review."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import click

from swarm_attack.commit_review.discovery import discover_commits
from swarm_attack.commit_review.categorizer import categorize_commit
from swarm_attack.commit_review.dispatcher import AgentDispatcher
from swarm_attack.commit_review.synthesis import synthesize_findings
from swarm_attack.commit_review.report import ReportGenerator
from swarm_attack.commit_review.tdd_generator import TDDPlanGenerator
from swarm_attack.commit_review.models import Severity, Verdict


@click.command("review-commits")
@click.option(
    "--since",
    default="24 hours ago",
    help="Time range for commits (git date format)",
)
@click.option(
    "--branch",
    default=None,
    help="Branch to review (default: current)",
)
@click.option(
    "--output",
    type=click.Choice(["markdown", "xml", "json"]),
    default="markdown",
    help="Output format",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Fail on any medium+ severity issue",
)
@click.option(
    "--save",
    type=click.Path(),
    default=None,
    help="Save report to file path",
)
@click.pass_context
def review_commits(
    ctx,
    since: str,
    branch: Optional[str],
    output: str,
    strict: bool,
    save: Optional[str],
):
    """Review recent commits with expert panel analysis.

    Runs a multi-agent review of commits, analyzing for:
    - Production reliability issues
    - Test coverage gaps
    - Code quality concerns
    - Documentation problems
    - Architectural issues

    Each finding includes evidence (file:line) and TDD fix plans.
    """
    # Get repo path from context or current directory
    repo_path = ctx.obj.get("repo_path", os.getcwd()) if ctx.obj else os.getcwd()

    try:
        result = run_review(
            repo_path=repo_path,
            since=since,
            branch=branch,
            output_format=output,
        )

        # Handle strict mode
        if strict and hasattr(result, "has_medium_or_higher"):
            if result.has_medium_or_higher:
                click.echo(result.content)
                ctx.exit(1)

        # Output result
        if isinstance(result, str):
            click.echo(result)
        else:
            click.echo(result.content if hasattr(result, "content") else str(result))

        # Save if requested
        if save:
            save_path = Path(save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            content = result if isinstance(result, str) else getattr(result, "content", str(result))
            save_path.write_text(content)
            click.echo(f"\nReport saved to: {save}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)


def run_review(
    repo_path: str,
    since: str = "24 hours ago",
    branch: Optional[str] = None,
    output_format: str = "markdown",
) -> str:
    """Run the commit review pipeline.

    Args:
        repo_path: Path to git repository
        since: Time range for commits
        branch: Optional branch filter
        output_format: Output format (markdown, xml, json)

    Returns:
        Formatted report string
    """
    # 1. Discover commits
    try:
        commits = discover_commits(repo_path, since=since, branch=branch)
    except RuntimeError as e:
        if output_format == "json":
            import json
            return json.dumps({
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "repo_path": repo_path,
                "branch": branch or "current",
                "since": since,
                "overall_score": 0.0,
                "summary": f"Error discovering commits: {e}",
                "commit_reviews": [],
            }, indent=2)
        return f"# Review Report\n\nError discovering commits: {e}"

    if not commits:
        if output_format == "json":
            import json
            return json.dumps({
                "generated_at": __import__("datetime").datetime.now().isoformat(),
                "repo_path": repo_path,
                "branch": branch or "current",
                "since": since,
                "overall_score": 1.0,
                "summary": f"No commits found in the last {since}",
                "commit_reviews": [],
            }, indent=2)
        return f"# Review Report\n\nNo commits found in the last {since}."

    # 2. Categorize commits
    categories = [categorize_commit(c) for c in commits]

    # 3. Dispatch agents (async)
    findings = asyncio.run(_async_dispatch(commits, categories))

    # 4. Synthesize findings
    report = synthesize_findings(
        findings,
        repo_path=repo_path,
        branch=branch or "current",
        since=since,
    )

    # 5. Generate TDD plans for actionable findings
    generator = TDDPlanGenerator()
    for review in report.commit_reviews:
        for finding in review.findings:
            if finding.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL):
                plan = generator.generate_plan(finding)
                if plan:
                    review.tdd_plans.append(plan)

    # 6. Generate report
    report_gen = ReportGenerator()
    return report_gen.generate(report, format=output_format)


async def _async_dispatch(commits, categories):
    """Run dispatcher asynchronously."""
    dispatcher = AgentDispatcher()
    return await dispatcher.dispatch(commits, categories)


# Allow running as standalone script
if __name__ == "__main__":
    review_commits()
