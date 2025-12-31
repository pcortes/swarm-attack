"""Report generation in multiple formats."""

import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Literal

from swarm_attack.commit_review.models import (
    ReviewReport,
    CommitReview,
    Finding,
    Verdict,
    TDDPlan,
)


class ReportGenerator:
    """Generates review reports in multiple formats."""

    def generate(
        self,
        report: ReviewReport,
        format: Literal["xml", "json", "markdown"] = "markdown",
    ) -> str:
        """Generate report in specified format.

        Args:
            report: The ReviewReport to format
            format: Output format (xml, json, markdown)

        Returns:
            Formatted report string
        """
        if format == "xml":
            return self.to_xml(report)
        elif format == "json":
            return self.to_json(report)
        else:
            return self.to_markdown(report)

    def to_xml(self, report: ReviewReport) -> str:
        """Generate XML report.

        Args:
            report: The ReviewReport to format

        Returns:
            XML string
        """
        root = ET.Element("review_report")

        # Metadata
        metadata = ET.SubElement(root, "metadata")
        ET.SubElement(metadata, "generated_at").text = report.generated_at
        ET.SubElement(metadata, "repo_path").text = report.repo_path
        ET.SubElement(metadata, "branch").text = report.branch
        ET.SubElement(metadata, "since").text = report.since
        ET.SubElement(metadata, "overall_score").text = str(report.overall_score)

        # Commit reviews
        reviews_elem = ET.SubElement(root, "commit_reviews")
        for review in report.commit_reviews:
            review_elem = ET.SubElement(reviews_elem, "commit_review")
            ET.SubElement(review_elem, "sha").text = review.commit_sha
            ET.SubElement(review_elem, "message").text = review.message
            ET.SubElement(review_elem, "author").text = review.author
            ET.SubElement(review_elem, "score").text = str(review.score)
            ET.SubElement(review_elem, "verdict").text = review.verdict.value

            findings_elem = ET.SubElement(review_elem, "findings")
            for finding in review.findings:
                finding_elem = ET.SubElement(findings_elem, "finding")
                ET.SubElement(finding_elem, "expert").text = finding.expert
                ET.SubElement(finding_elem, "severity").text = finding.severity.value
                ET.SubElement(finding_elem, "category").text = finding.category
                ET.SubElement(finding_elem, "description").text = finding.description
                ET.SubElement(finding_elem, "evidence").text = finding.evidence

            if review.tdd_plans:
                plans_elem = ET.SubElement(review_elem, "tdd_plans")
                for plan in review.tdd_plans:
                    plan_elem = ET.SubElement(plans_elem, "tdd_plan")
                    ET.SubElement(plan_elem, "finding_id").text = plan.finding_id
                    ET.SubElement(plan_elem, "red_phase").text = plan.red_phase
                    ET.SubElement(plan_elem, "green_phase").text = plan.green_phase
                    ET.SubElement(plan_elem, "refactor_phase").text = plan.refactor_phase

        # Summary
        summary_elem = ET.SubElement(root, "summary")
        summary_elem.text = report.summary

        # Pretty print
        xml_str = ET.tostring(root, encoding="unicode")
        parsed = minidom.parseString(xml_str)
        return parsed.toprettyxml(indent="  ")

    def to_json(self, report: ReviewReport) -> str:
        """Generate JSON report.

        Args:
            report: The ReviewReport to format

        Returns:
            JSON string
        """
        data = {
            "generated_at": report.generated_at,
            "repo_path": report.repo_path,
            "branch": report.branch,
            "since": report.since,
            "overall_score": report.overall_score,
            "summary": report.summary,
            "commit_reviews": [
                {
                    "commit_sha": review.commit_sha,
                    "message": review.message,
                    "author": review.author,
                    "score": review.score,
                    "verdict": review.verdict.value,
                    "findings": [
                        {
                            "expert": f.expert,
                            "severity": f.severity.value,
                            "category": f.category,
                            "description": f.description,
                            "evidence": f.evidence,
                        }
                        for f in review.findings
                    ],
                    "tdd_plans": [
                        {
                            "finding_id": p.finding_id,
                            "red_phase": p.red_phase,
                            "green_phase": p.green_phase,
                            "refactor_phase": p.refactor_phase,
                        }
                        for p in review.tdd_plans
                    ],
                }
                for review in report.commit_reviews
            ],
        }
        return json.dumps(data, indent=2)

    def to_markdown(self, report: ReviewReport) -> str:
        """Generate Markdown report.

        Args:
            report: The ReviewReport to format

        Returns:
            Markdown string
        """
        lines = []

        # Header
        lines.append("# Commit Quality Review")
        lines.append("")
        lines.append(f"**Generated:** {report.generated_at}")
        lines.append(f"**Repository:** {report.repo_path}")
        lines.append(f"**Branch:** {report.branch}")
        lines.append(f"**Since:** {report.since}")
        lines.append(f"**Overall Score:** {report.overall_score:.2f}")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(report.summary)
        lines.append("")

        if not report.commit_reviews:
            lines.append("No commits to review.")
            return "\n".join(lines)

        # Commit reviews
        lines.append("## Commit Reviews")
        lines.append("")

        for review in report.commit_reviews:
            verdict_emoji = {
                Verdict.LEAVE: "✅",
                Verdict.FIX: "⚠️",
                Verdict.REVERT: "❌",
            }[review.verdict]

            lines.append(f"### {verdict_emoji} {review.commit_sha}")
            lines.append("")
            if review.message:
                lines.append(f"**Message:** {review.message}")
            if review.author:
                lines.append(f"**Author:** {review.author}")
            lines.append(f"**Score:** {review.score:.2f}")
            lines.append(f"**Verdict:** {review.verdict.value.upper()}")
            lines.append("")

            if review.findings:
                lines.append("#### Findings")
                lines.append("")
                for finding in review.findings:
                    severity_emoji = {
                        "low": "🔵",
                        "medium": "🟡",
                        "high": "🟠",
                        "critical": "🔴",
                    }.get(finding.severity.value, "⚪")

                    lines.append(f"- {severity_emoji} **{finding.severity.value.upper()}** ({finding.expert})")
                    lines.append(f"  - {finding.description}")
                    lines.append(f"  - Evidence: `{finding.evidence}`")
                    lines.append("")

            if review.tdd_plans:
                lines.append("#### TDD Fix Plans")
                lines.append("")
                for plan in review.tdd_plans:
                    lines.append(f"##### Plan {plan.finding_id}")
                    lines.append("")
                    lines.append("**Red Phase (Failing Test):**")
                    lines.append("```")
                    lines.append(plan.red_phase)
                    lines.append("```")
                    lines.append("")
                    lines.append("**Green Phase (Minimal Fix):**")
                    lines.append("```")
                    lines.append(plan.green_phase)
                    lines.append("```")
                    lines.append("")
                    lines.append("**Refactor Phase:**")
                    lines.append("```")
                    lines.append(plan.refactor_phase)
                    lines.append("```")
                    lines.append("")

        return "\n".join(lines)
