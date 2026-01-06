"""RegressionReporter - Generates markdown reports for regression test runs."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from swarm_attack.qa.agents.semantic_tester import SemanticTestResult, SemanticVerdict


@dataclass
class RegressionReport:
    """Report from a regression test run."""
    timestamp: datetime
    results: list[SemanticTestResult]
    overall_verdict: SemanticVerdict
    duration_seconds: float = 0.0
    files_tested: list[str] = field(default_factory=list)


class RegressionReporter:
    """Generates markdown reports for regression test runs."""

    def __init__(self, report_dir: Path):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(self, report: RegressionReport) -> str:
        """Generate markdown report from regression results."""
        lines = [
            f"# Regression Test Report",
            f"",
            f"**Date:** {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Duration:** {report.duration_seconds:.1f}s",
            f"**Overall Verdict:** {report.overall_verdict.value}",
            f"**Files Tested:** {len(report.files_tested)}",
            f"",
            f"## Summary",
            f"",
        ]

        # Count verdicts
        pass_count = sum(1 for r in report.results if r.verdict == SemanticVerdict.PASS)
        fail_count = sum(1 for r in report.results if r.verdict == SemanticVerdict.FAIL)
        partial_count = sum(1 for r in report.results if r.verdict == SemanticVerdict.PARTIAL)

        lines.extend([
            f"- PASS: {pass_count}",
            f"- FAIL: {fail_count}",
            f"- PARTIAL: {partial_count}",
            f"",
        ])

        # Group findings by severity
        all_issues = []
        for result in report.results:
            all_issues.extend(result.issues)

        critical = [i for i in all_issues if i.severity == "critical"]
        major = [i for i in all_issues if i.severity == "major"]
        minor = [i for i in all_issues if i.severity == "minor"]

        if critical:
            lines.append("## Critical Issues")
            lines.append("")
            for issue in critical:
                lines.append(f"### {issue.location}")
                lines.append(f"{issue.description}")
                lines.append(f"**Suggestion:** {issue.suggestion}")
                lines.append("")

        if major:
            lines.append("## Major Issues")
            lines.append("")
            for issue in major:
                lines.append(f"- **{issue.location}**: {issue.description}")
            lines.append("")

        if minor:
            lines.append("## Minor Issues")
            lines.append("")
            for issue in minor:
                lines.append(f"- {issue.location}: {issue.description}")
            lines.append("")

        # Recommendations
        all_recommendations = []
        for result in report.results:
            all_recommendations.extend(result.recommendations)

        if all_recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for rec in set(all_recommendations):
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def save_report(self, report: RegressionReport) -> Path:
        """Generate and save report to file."""
        content = self.generate_report(report)
        filename = f"{report.timestamp.strftime('%Y-%m-%d-%H%M%S')}.md"
        report_path = self.report_dir / filename
        report_path.write_text(content)
        return report_path
