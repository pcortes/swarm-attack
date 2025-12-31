"""Tests for report generation functionality."""

import pytest
import xml.etree.ElementTree as ET
import json

from swarm_attack.commit_review.report import ReportGenerator
from swarm_attack.commit_review.models import (
    ReviewReport,
    CommitReview,
    Finding,
    Severity,
    Verdict,
    TDDPlan,
)


class TestReportGenerator:
    """Tests for ReportGenerator."""

    def _make_report(self) -> ReviewReport:
        """Helper to create a ReviewReport for testing."""
        finding1 = Finding(
            commit_sha="abc123",
            expert="Dr. Elena Vasquez",
            severity=Severity.MEDIUM,
            category="production_reliability",
            description="Bug fix without production evidence",
            evidence="fix.py:45",
        )
        finding2 = Finding(
            commit_sha="abc123",
            expert="Marcus Chen",
            severity=Severity.LOW,
            category="test_coverage",
            description="Test coverage dropped by 2%",
            evidence="tests/test_fix.py:10",
        )

        review = CommitReview(
            commit_sha="abc123",
            message="fix: handle edge case",
            author="Dev User",
            findings=[finding1, finding2],
            score=0.7,
            verdict=Verdict.FIX,
            tdd_plans=[
                TDDPlan(
                    finding_id="f1",
                    red_phase="Write test for production scenario",
                    green_phase="Add production evidence check",
                    refactor_phase="Extract to reusable validator",
                ),
            ],
        )

        return ReviewReport(
            generated_at="2025-12-31T12:00:00",
            repo_path="/path/to/repo",
            branch="main",
            since="24 hours ago",
            commit_reviews=[review],
            overall_score=0.7,
            summary="1 commit reviewed, 1 needs fixes",
        )

    def test_generate_xml_report(self):
        """Output is valid XML with required sections."""
        generator = ReportGenerator()
        report = self._make_report()

        xml_output = generator.to_xml(report)

        # Should be valid XML
        root = ET.fromstring(xml_output)

        # Should have required sections
        assert root.tag == "review_report"
        assert root.find("metadata") is not None
        assert root.find("commit_reviews") is not None
        assert root.find("summary") is not None

    def test_generate_markdown_report(self):
        """Output is valid markdown with required sections."""
        generator = ReportGenerator()
        report = self._make_report()

        md_output = generator.to_markdown(report)

        # Should have title
        assert "# Commit Quality Review" in md_output

        # Should have commit section
        assert "abc123" in md_output

        # Should have findings
        assert "Dr. Elena Vasquez" in md_output

        # Should have verdict
        assert "FIX" in md_output

    def test_generate_json_report(self):
        """Output is valid JSON with required fields."""
        generator = ReportGenerator()
        report = self._make_report()

        json_output = generator.to_json(report)

        # Should be valid JSON
        data = json.loads(json_output)

        # Should have required fields
        assert "generated_at" in data
        assert "commit_reviews" in data
        assert "overall_score" in data
        assert "summary" in data

    def test_report_includes_evidence(self):
        """Each finding includes file:line evidence."""
        generator = ReportGenerator()
        report = self._make_report()

        # Check markdown
        md_output = generator.to_markdown(report)
        assert "fix.py:45" in md_output
        assert "tests/test_fix.py:10" in md_output

        # Check XML
        xml_output = generator.to_xml(report)
        assert "fix.py:45" in xml_output

        # Check JSON
        json_output = generator.to_json(report)
        data = json.loads(json_output)
        findings = data["commit_reviews"][0]["findings"]
        assert any(f["evidence"] == "fix.py:45" for f in findings)

    def test_report_includes_tdd_plans(self):
        """Report includes TDD fix plans for actionable issues."""
        generator = ReportGenerator()
        report = self._make_report()

        md_output = generator.to_markdown(report)

        # Should have TDD section
        assert "TDD" in md_output or "Red" in md_output or "Green" in md_output

        # Should include the plan content
        assert "production evidence" in md_output.lower() or "test for production" in md_output.lower()

    def test_empty_report(self):
        """Handles empty report gracefully."""
        generator = ReportGenerator()
        report = ReviewReport(
            generated_at="2025-12-31T12:00:00",
            repo_path="/path/to/repo",
            branch="main",
            since="24 hours ago",
            commit_reviews=[],
            overall_score=1.0,
            summary="No commits to review",
        )

        md_output = generator.to_markdown(report)

        assert "No commits to review" in md_output or "0 commits" in md_output.lower()

    def test_output_format_selection(self):
        """Can select output format."""
        generator = ReportGenerator()
        report = self._make_report()

        # Should support different formats
        xml = generator.generate(report, format="xml")
        assert xml.startswith("<?xml") or xml.startswith("<review")

        md = generator.generate(report, format="markdown")
        assert "#" in md

        js = generator.generate(report, format="json")
        json.loads(js)  # Should be valid JSON
