"""Tests for StaticBugReport and StaticAnalysisResult data models.

Issue 1: Create StaticBugReport and StaticAnalysisResult data models
"""

import pytest
from typing import Literal

from swarm_attack.static_analysis.models import (
    StaticBugReport,
    StaticAnalysisResult,
)


class TestStaticBugReportFields:
    """Tests for StaticBugReport fields."""

    def test_static_bug_report_has_source_field(self):
        """StaticBugReport should have a source field."""
        report = StaticBugReport(
            source="pytest",
            file_path="tests/test_example.py",
            line_number=42,
            error_code="E001",
            message="Test failure",
            severity="moderate",
        )
        assert hasattr(report, "source")
        assert report.source == "pytest"

    def test_static_bug_report_has_file_path_field(self):
        """StaticBugReport should have a file_path field."""
        report = StaticBugReport(
            source="mypy",
            file_path="src/module.py",
            line_number=10,
            error_code="error",
            message="Type error",
            severity="critical",
        )
        assert hasattr(report, "file_path")
        assert report.file_path == "src/module.py"

    def test_static_bug_report_has_line_number_field(self):
        """StaticBugReport should have a line_number field."""
        report = StaticBugReport(
            source="ruff",
            file_path="src/main.py",
            line_number=123,
            error_code="F401",
            message="Unused import",
            severity="minor",
        )
        assert hasattr(report, "line_number")
        assert report.line_number == 123

    def test_static_bug_report_has_error_code_field(self):
        """StaticBugReport should have an error_code field."""
        report = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=5,
            error_code="AssertionError",
            message="Assertion failed",
            severity="critical",
        )
        assert hasattr(report, "error_code")
        assert report.error_code == "AssertionError"

    def test_static_bug_report_has_message_field(self):
        """StaticBugReport should have a message field."""
        report = StaticBugReport(
            source="mypy",
            file_path="lib/utils.py",
            line_number=50,
            error_code="error",
            message="Incompatible types in assignment",
            severity="moderate",
        )
        assert hasattr(report, "message")
        assert report.message == "Incompatible types in assignment"

    def test_static_bug_report_has_severity_field(self):
        """StaticBugReport should have a severity field."""
        report = StaticBugReport(
            source="ruff",
            file_path="src/api.py",
            line_number=1,
            error_code="E501",
            message="Line too long",
            severity="minor",
        )
        assert hasattr(report, "severity")
        assert report.severity == "minor"


class TestStaticBugReportSourceValues:
    """Tests for StaticBugReport source field Literal values."""

    def test_source_accepts_pytest(self):
        """Source field should accept 'pytest'."""
        report = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="E001",
            message="Test",
            severity="moderate",
        )
        assert report.source == "pytest"

    def test_source_accepts_mypy(self):
        """Source field should accept 'mypy'."""
        report = StaticBugReport(
            source="mypy",
            file_path="src/module.py",
            line_number=1,
            error_code="error",
            message="Test",
            severity="moderate",
        )
        assert report.source == "mypy"

    def test_source_accepts_ruff(self):
        """Source field should accept 'ruff'."""
        report = StaticBugReport(
            source="ruff",
            file_path="src/utils.py",
            line_number=1,
            error_code="F401",
            message="Test",
            severity="moderate",
        )
        assert report.source == "ruff"


class TestStaticBugReportSeverityValues:
    """Tests for StaticBugReport severity field Literal values."""

    def test_severity_accepts_critical(self):
        """Severity field should accept 'critical'."""
        report = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=1,
            error_code="E001",
            message="Test failure",
            severity="critical",
        )
        assert report.severity == "critical"

    def test_severity_accepts_moderate(self):
        """Severity field should accept 'moderate'."""
        report = StaticBugReport(
            source="mypy",
            file_path="src/module.py",
            line_number=1,
            error_code="error",
            message="Type mismatch",
            severity="moderate",
        )
        assert report.severity == "moderate"

    def test_severity_accepts_minor(self):
        """Severity field should accept 'minor'."""
        report = StaticBugReport(
            source="ruff",
            file_path="src/utils.py",
            line_number=1,
            error_code="F401",
            message="Unused import",
            severity="minor",
        )
        assert report.severity == "minor"


class TestStaticBugReportSerialization:
    """Tests for StaticBugReport serialization methods."""

    def test_static_bug_report_has_to_dict_method(self):
        """StaticBugReport should have a to_dict method."""
        report = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=42,
            error_code="E001",
            message="Test failure",
            severity="critical",
        )
        assert hasattr(report, "to_dict")
        assert callable(report.to_dict)

    def test_static_bug_report_to_dict_returns_dict(self):
        """StaticBugReport.to_dict() should return a dictionary."""
        report = StaticBugReport(
            source="mypy",
            file_path="src/module.py",
            line_number=10,
            error_code="error",
            message="Type error",
            severity="moderate",
        )
        result = report.to_dict()
        assert isinstance(result, dict)

    def test_static_bug_report_to_dict_includes_all_fields(self):
        """StaticBugReport.to_dict() should include all fields."""
        report = StaticBugReport(
            source="ruff",
            file_path="src/api.py",
            line_number=123,
            error_code="F401",
            message="Unused import",
            severity="minor",
        )
        result = report.to_dict()
        assert result["source"] == "ruff"
        assert result["file_path"] == "src/api.py"
        assert result["line_number"] == 123
        assert result["error_code"] == "F401"
        assert result["message"] == "Unused import"
        assert result["severity"] == "minor"

    def test_static_bug_report_has_from_dict_classmethod(self):
        """StaticBugReport should have a from_dict classmethod."""
        assert hasattr(StaticBugReport, "from_dict")
        assert callable(StaticBugReport.from_dict)

    def test_static_bug_report_from_dict_creates_instance(self):
        """StaticBugReport.from_dict() should create an instance."""
        data = {
            "source": "pytest",
            "file_path": "tests/test.py",
            "line_number": 42,
            "error_code": "E001",
            "message": "Test failure",
            "severity": "critical",
        }
        report = StaticBugReport.from_dict(data)
        assert isinstance(report, StaticBugReport)

    def test_static_bug_report_from_dict_sets_all_fields(self):
        """StaticBugReport.from_dict() should set all fields correctly."""
        data = {
            "source": "mypy",
            "file_path": "src/module.py",
            "line_number": 99,
            "error_code": "error",
            "message": "Incompatible types",
            "severity": "moderate",
        }
        report = StaticBugReport.from_dict(data)
        assert report.source == "mypy"
        assert report.file_path == "src/module.py"
        assert report.line_number == 99
        assert report.error_code == "error"
        assert report.message == "Incompatible types"
        assert report.severity == "moderate"

    def test_static_bug_report_roundtrip(self):
        """StaticBugReport serialization roundtrip preserves data."""
        original = StaticBugReport(
            source="ruff",
            file_path="src/utils.py",
            line_number=50,
            error_code="F841",
            message="Local variable is assigned but never used",
            severity="minor",
        )
        roundtrip = StaticBugReport.from_dict(original.to_dict())
        assert roundtrip.source == original.source
        assert roundtrip.file_path == original.file_path
        assert roundtrip.line_number == original.line_number
        assert roundtrip.error_code == original.error_code
        assert roundtrip.message == original.message
        assert roundtrip.severity == original.severity


class TestStaticAnalysisResultFields:
    """Tests for StaticAnalysisResult fields."""

    def test_static_analysis_result_has_bugs_field(self):
        """StaticAnalysisResult should have a bugs field."""
        result = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        assert hasattr(result, "bugs")
        assert isinstance(result.bugs, list)

    def test_static_analysis_result_has_tools_run_field(self):
        """StaticAnalysisResult should have a tools_run field."""
        result = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest", "mypy"],
            tools_skipped=["ruff"],
        )
        assert hasattr(result, "tools_run")
        assert isinstance(result.tools_run, list)
        assert result.tools_run == ["pytest", "mypy"]

    def test_static_analysis_result_has_tools_skipped_field(self):
        """StaticAnalysisResult should have a tools_skipped field."""
        result = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=["mypy", "ruff"],
        )
        assert hasattr(result, "tools_skipped")
        assert isinstance(result.tools_skipped, list)
        assert result.tools_skipped == ["mypy", "ruff"]

    def test_static_analysis_result_bugs_contains_static_bug_reports(self):
        """StaticAnalysisResult.bugs should contain StaticBugReport instances."""
        bug1 = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=10,
            error_code="E001",
            message="Test failure",
            severity="critical",
        )
        bug2 = StaticBugReport(
            source="ruff",
            file_path="src/module.py",
            line_number=20,
            error_code="F401",
            message="Unused import",
            severity="minor",
        )
        result = StaticAnalysisResult(
            bugs=[bug1, bug2],
            tools_run=["pytest", "ruff"],
            tools_skipped=["mypy"],
        )
        assert len(result.bugs) == 2
        assert all(isinstance(b, StaticBugReport) for b in result.bugs)


class TestStaticAnalysisResultSerialization:
    """Tests for StaticAnalysisResult serialization methods."""

    def test_static_analysis_result_has_to_dict_method(self):
        """StaticAnalysisResult should have a to_dict method."""
        result = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        assert hasattr(result, "to_dict")
        assert callable(result.to_dict)

    def test_static_analysis_result_to_dict_returns_dict(self):
        """StaticAnalysisResult.to_dict() should return a dictionary."""
        result = StaticAnalysisResult(
            bugs=[],
            tools_run=["pytest"],
            tools_skipped=[],
        )
        output = result.to_dict()
        assert isinstance(output, dict)

    def test_static_analysis_result_to_dict_includes_all_fields(self):
        """StaticAnalysisResult.to_dict() should include all fields."""
        bug = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=42,
            error_code="E001",
            message="Test failure",
            severity="critical",
        )
        result = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["pytest", "mypy"],
            tools_skipped=["ruff"],
        )
        output = result.to_dict()
        assert "bugs" in output
        assert "tools_run" in output
        assert "tools_skipped" in output
        assert output["tools_run"] == ["pytest", "mypy"]
        assert output["tools_skipped"] == ["ruff"]

    def test_static_analysis_result_to_dict_serializes_bugs(self):
        """StaticAnalysisResult.to_dict() should serialize bugs as dicts."""
        bug = StaticBugReport(
            source="ruff",
            file_path="src/utils.py",
            line_number=50,
            error_code="F841",
            message="Unused variable",
            severity="minor",
        )
        result = StaticAnalysisResult(
            bugs=[bug],
            tools_run=["ruff"],
            tools_skipped=[],
        )
        output = result.to_dict()
        assert len(output["bugs"]) == 1
        assert isinstance(output["bugs"][0], dict)
        assert output["bugs"][0]["source"] == "ruff"

    def test_static_analysis_result_has_from_dict_classmethod(self):
        """StaticAnalysisResult should have a from_dict classmethod."""
        assert hasattr(StaticAnalysisResult, "from_dict")
        assert callable(StaticAnalysisResult.from_dict)

    def test_static_analysis_result_from_dict_creates_instance(self):
        """StaticAnalysisResult.from_dict() should create an instance."""
        data = {
            "bugs": [],
            "tools_run": ["pytest"],
            "tools_skipped": ["mypy"],
        }
        result = StaticAnalysisResult.from_dict(data)
        assert isinstance(result, StaticAnalysisResult)

    def test_static_analysis_result_from_dict_deserializes_bugs(self):
        """StaticAnalysisResult.from_dict() should deserialize bugs."""
        data = {
            "bugs": [
                {
                    "source": "mypy",
                    "file_path": "src/module.py",
                    "line_number": 10,
                    "error_code": "error",
                    "message": "Type error",
                    "severity": "moderate",
                }
            ],
            "tools_run": ["mypy"],
            "tools_skipped": [],
        }
        result = StaticAnalysisResult.from_dict(data)
        assert len(result.bugs) == 1
        assert isinstance(result.bugs[0], StaticBugReport)
        assert result.bugs[0].source == "mypy"

    def test_static_analysis_result_roundtrip(self):
        """StaticAnalysisResult serialization roundtrip preserves data."""
        bug1 = StaticBugReport(
            source="pytest",
            file_path="tests/test.py",
            line_number=42,
            error_code="E001",
            message="Test failure",
            severity="critical",
        )
        bug2 = StaticBugReport(
            source="ruff",
            file_path="src/api.py",
            line_number=10,
            error_code="F401",
            message="Unused import",
            severity="minor",
        )
        original = StaticAnalysisResult(
            bugs=[bug1, bug2],
            tools_run=["pytest", "ruff"],
            tools_skipped=["mypy"],
        )
        roundtrip = StaticAnalysisResult.from_dict(original.to_dict())
        assert len(roundtrip.bugs) == 2
        assert roundtrip.tools_run == original.tools_run
        assert roundtrip.tools_skipped == original.tools_skipped
        assert roundtrip.bugs[0].source == original.bugs[0].source
        assert roundtrip.bugs[1].message == original.bugs[1].message

    def test_static_analysis_result_from_dict_with_empty_bugs(self):
        """StaticAnalysisResult.from_dict() handles empty bugs list."""
        data = {
            "bugs": [],
            "tools_run": ["pytest", "mypy", "ruff"],
            "tools_skipped": [],
        }
        result = StaticAnalysisResult.from_dict(data)
        assert result.bugs == []
        assert result.tools_run == ["pytest", "mypy", "ruff"]