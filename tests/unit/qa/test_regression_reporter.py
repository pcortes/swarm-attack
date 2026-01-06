"""Unit tests for RegressionReporter (TDD)."""
import pytest
from datetime import datetime
from pathlib import Path

try:
    from swarm_attack.qa.regression_reporter import (
        RegressionReporter,
        RegressionReport,
    )
    from swarm_attack.qa.agents.semantic_tester import (
        SemanticTestResult,
        SemanticVerdict,
        SemanticIssue,
        Evidence,
    )
    IMPORTS_AVAILABLE = True
except ImportError:
    IMPORTS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason="RegressionReporter not yet implemented"
)


class TestRegressionReport:
    """Test RegressionReport dataclass."""

    def test_creates_with_required_fields(self):
        report = RegressionReport(
            timestamp=datetime(2026, 1, 5, 10, 30, 0),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )
        assert report.timestamp == datetime(2026, 1, 5, 10, 30, 0)
        assert report.results == []
        assert report.overall_verdict == SemanticVerdict.PASS

    def test_default_duration_is_zero(self):
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )
        assert report.duration_seconds == 0.0

    def test_default_files_tested_is_empty(self):
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )
        assert report.files_tested == []


class TestRegressionReporterInit:
    """Test RegressionReporter initialization."""

    def test_creates_report_directory(self, tmp_path):
        report_dir = tmp_path / ".swarm" / "qa" / "regression-reports"
        reporter = RegressionReporter(report_dir)
        assert report_dir.exists()

    def test_accepts_existing_directory(self, tmp_path):
        report_dir = tmp_path / "existing"
        report_dir.mkdir(parents=True)
        reporter = RegressionReporter(report_dir)
        assert reporter.report_dir == report_dir


class TestGenerateReport:
    """Test markdown report generation."""

    def test_produces_valid_markdown(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime(2026, 1, 5, 10, 30, 0),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
            duration_seconds=45.5,
        )

        markdown = reporter.generate_report(report)

        assert markdown.startswith("# Regression Test Report")
        assert "**Date:**" in markdown
        assert "**Duration:**" in markdown
        assert "**Overall Verdict:**" in markdown

    def test_includes_date_and_duration(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime(2026, 1, 5, 10, 30, 0),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
            duration_seconds=120.5,
            files_tested=["file1.py", "file2.py", "file3.py"],
        )

        markdown = reporter.generate_report(report)

        assert "2026-01-05 10:30:00" in markdown
        assert "120.5s" in markdown
        assert "**Files Tested:** 3" in markdown

    def test_includes_overall_verdict(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[],
            overall_verdict=SemanticVerdict.FAIL,
        )

        markdown = reporter.generate_report(report)

        assert "**Overall Verdict:** FAIL" in markdown


class TestSummarySection:
    """Test summary section with pass/fail counts."""

    def test_counts_pass_results(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        results = [
            SemanticTestResult(verdict=SemanticVerdict.PASS),
            SemanticTestResult(verdict=SemanticVerdict.PASS),
            SemanticTestResult(verdict=SemanticVerdict.FAIL),
        ]
        report = RegressionReport(
            timestamp=datetime.now(),
            results=results,
            overall_verdict=SemanticVerdict.PARTIAL,
        )

        markdown = reporter.generate_report(report)

        assert "- PASS: 2" in markdown
        assert "- FAIL: 1" in markdown

    def test_counts_partial_results(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        results = [
            SemanticTestResult(verdict=SemanticVerdict.PARTIAL),
            SemanticTestResult(verdict=SemanticVerdict.PARTIAL),
        ]
        report = RegressionReport(
            timestamp=datetime.now(),
            results=results,
            overall_verdict=SemanticVerdict.PARTIAL,
        )

        markdown = reporter.generate_report(report)

        assert "- PARTIAL: 2" in markdown

    def test_handles_zero_counts(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )

        markdown = reporter.generate_report(report)

        assert "- PASS: 0" in markdown
        assert "- FAIL: 0" in markdown
        assert "- PARTIAL: 0" in markdown


class TestFindingsGroupedBySeverity:
    """Test findings are grouped by severity."""

    def test_groups_critical_issues(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        result = SemanticTestResult(
            verdict=SemanticVerdict.FAIL,
            issues=[
                SemanticIssue(
                    severity="critical",
                    description="Database connection fails",
                    location="db/connection.py:45",
                    suggestion="Check connection string",
                ),
            ],
        )
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[result],
            overall_verdict=SemanticVerdict.FAIL,
        )

        markdown = reporter.generate_report(report)

        assert "## Critical Issues" in markdown
        assert "Database connection fails" in markdown
        assert "db/connection.py:45" in markdown
        assert "Check connection string" in markdown

    def test_groups_major_issues(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        result = SemanticTestResult(
            verdict=SemanticVerdict.PARTIAL,
            issues=[
                SemanticIssue(
                    severity="major",
                    description="Performance degradation",
                    location="api/handler.py:100",
                    suggestion="Add caching",
                ),
            ],
        )
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[result],
            overall_verdict=SemanticVerdict.PARTIAL,
        )

        markdown = reporter.generate_report(report)

        assert "## Major Issues" in markdown
        assert "Performance degradation" in markdown

    def test_groups_minor_issues(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            issues=[
                SemanticIssue(
                    severity="minor",
                    description="Missing docstring",
                    location="utils.py:10",
                    suggestion="Add docstring",
                ),
            ],
        )
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[result],
            overall_verdict=SemanticVerdict.PASS,
        )

        markdown = reporter.generate_report(report)

        assert "## Minor Issues" in markdown
        assert "Missing docstring" in markdown

    def test_collects_issues_from_multiple_results(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        results = [
            SemanticTestResult(
                verdict=SemanticVerdict.FAIL,
                issues=[
                    SemanticIssue(
                        severity="critical",
                        description="Issue 1",
                        location="file1.py",
                        suggestion="Fix 1",
                    ),
                ],
            ),
            SemanticTestResult(
                verdict=SemanticVerdict.FAIL,
                issues=[
                    SemanticIssue(
                        severity="critical",
                        description="Issue 2",
                        location="file2.py",
                        suggestion="Fix 2",
                    ),
                ],
            ),
        ]
        report = RegressionReport(
            timestamp=datetime.now(),
            results=results,
            overall_verdict=SemanticVerdict.FAIL,
        )

        markdown = reporter.generate_report(report)

        assert "Issue 1" in markdown
        assert "Issue 2" in markdown

    def test_omits_empty_severity_sections(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        result = SemanticTestResult(
            verdict=SemanticVerdict.PASS,
            issues=[
                SemanticIssue(
                    severity="minor",
                    description="Only minor issue",
                    location="file.py",
                    suggestion="Minor fix",
                ),
            ],
        )
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[result],
            overall_verdict=SemanticVerdict.PASS,
        )

        markdown = reporter.generate_report(report)

        assert "## Critical Issues" not in markdown
        assert "## Major Issues" not in markdown
        assert "## Minor Issues" in markdown


class TestRecommendationsSection:
    """Test recommendations are included."""

    def test_includes_recommendations(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        result = SemanticTestResult(
            verdict=SemanticVerdict.PARTIAL,
            recommendations=[
                "Add more unit tests",
                "Consider refactoring the API layer",
            ],
        )
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[result],
            overall_verdict=SemanticVerdict.PARTIAL,
        )

        markdown = reporter.generate_report(report)

        assert "## Recommendations" in markdown
        assert "Add more unit tests" in markdown
        assert "Consider refactoring the API layer" in markdown

    def test_collects_recommendations_from_multiple_results(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        results = [
            SemanticTestResult(
                verdict=SemanticVerdict.PASS,
                recommendations=["Rec 1"],
            ),
            SemanticTestResult(
                verdict=SemanticVerdict.PASS,
                recommendations=["Rec 2"],
            ),
        ]
        report = RegressionReport(
            timestamp=datetime.now(),
            results=results,
            overall_verdict=SemanticVerdict.PASS,
        )

        markdown = reporter.generate_report(report)

        assert "Rec 1" in markdown
        assert "Rec 2" in markdown

    def test_omits_section_if_no_recommendations(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime.now(),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )

        markdown = reporter.generate_report(report)

        assert "## Recommendations" not in markdown

    def test_deduplicates_recommendations(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        results = [
            SemanticTestResult(
                verdict=SemanticVerdict.PASS,
                recommendations=["Same recommendation"],
            ),
            SemanticTestResult(
                verdict=SemanticVerdict.PASS,
                recommendations=["Same recommendation"],
            ),
        ]
        report = RegressionReport(
            timestamp=datetime.now(),
            results=results,
            overall_verdict=SemanticVerdict.PASS,
        )

        markdown = reporter.generate_report(report)

        # Count occurrences - should only appear once (as a list item)
        assert markdown.count("- Same recommendation") == 1


class TestSaveReport:
    """Test report saving."""

    def test_saves_to_timestamped_file(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime(2026, 1, 5, 10, 30, 45),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )

        path = reporter.save_report(report)

        assert path.name == "2026-01-05-103045.md"
        assert path.exists()

    def test_returns_path_to_saved_file(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime(2026, 1, 5, 14, 0, 0),
            results=[],
            overall_verdict=SemanticVerdict.PASS,
        )

        path = reporter.save_report(report)

        assert path.parent == tmp_path
        assert path.suffix == ".md"

    def test_saved_file_contains_report_content(self, tmp_path):
        reporter = RegressionReporter(tmp_path)
        report = RegressionReport(
            timestamp=datetime(2026, 1, 5, 10, 30, 0),
            results=[],
            overall_verdict=SemanticVerdict.FAIL,
            duration_seconds=99.9,
        )

        path = reporter.save_report(report)
        content = path.read_text()

        assert "# Regression Test Report" in content
        assert "**Overall Verdict:** FAIL" in content
        assert "99.9s" in content
