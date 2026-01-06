"""Tests for StaticBugDetector with mocked subprocess calls."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.static_analysis.detector import StaticBugDetector
from swarm_attack.static_analysis.models import StaticAnalysisResult, StaticBugReport


class TestToolAvailable:
    """Tests for _tool_available method."""

    def test_tool_available_when_present(self):
        """Should return True when tool is found via shutil.which."""
        detector = StaticBugDetector()
        with patch("shutil.which", return_value="/usr/bin/pytest"):
            assert detector._tool_available("pytest") is True

    def test_tool_available_when_missing(self):
        """Should return False when tool is not found."""
        detector = StaticBugDetector()
        with patch("shutil.which", return_value=None):
            assert detector._tool_available("nonexistent-tool") is False

    def test_tool_available_checks_correct_tool(self):
        """Should pass correct tool name to shutil.which."""
        detector = StaticBugDetector()
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/mypy"
            detector._tool_available("mypy")
            mock_which.assert_called_once_with("mypy")


class TestMapPytestSeverity:
    """Tests for _map_pytest_severity method."""

    def test_assertion_error_maps_to_moderate(self):
        """AssertionError should map to moderate severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("AssertionError: expected 5 got 4") == "moderate"

    def test_type_error_maps_to_critical(self):
        """TypeError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("TypeError: got str expected int") == "critical"

    def test_attribute_error_maps_to_critical(self):
        """AttributeError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("AttributeError: no attribute 'foo'") == "critical"

    def test_import_error_maps_to_critical(self):
        """ImportError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("ImportError: cannot import name 'foo'") == "critical"

    def test_runtime_error_maps_to_critical(self):
        """RuntimeError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("RuntimeError: something went wrong") == "critical"

    def test_value_error_maps_to_critical(self):
        """ValueError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("ValueError: invalid value") == "critical"

    def test_key_error_maps_to_critical(self):
        """KeyError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("KeyError: 'missing_key'") == "critical"

    def test_file_not_found_maps_to_critical(self):
        """FileNotFoundError should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("FileNotFoundError: [Errno 2] No such file") == "critical"

    def test_generic_exception_maps_to_critical(self):
        """Generic Exception should map to critical severity."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("Exception: something bad") == "critical"

    def test_mixed_assertion_and_exception_uses_assertion(self):
        """When both AssertionError and another error present, should be moderate."""
        detector = StaticBugDetector()
        # AssertionError takes precedence (it's checked explicitly)
        longrepr = "AssertionError: assert True == False"
        assert detector._map_pytest_severity(longrepr) == "moderate"

    def test_unknown_error_defaults_to_moderate(self):
        """Unknown error patterns should default to moderate."""
        detector = StaticBugDetector()
        assert detector._map_pytest_severity("Something completely unknown") == "moderate"


class TestExtractErrorCode:
    """Tests for _extract_error_code method."""

    def test_extracts_assertion_error(self):
        """Should extract AssertionError from longrepr."""
        detector = StaticBugDetector()
        assert detector._extract_error_code("AssertionError: expected 1 got 2") == "AssertionError"

    def test_extracts_type_error(self):
        """Should extract TypeError from longrepr."""
        detector = StaticBugDetector()
        assert detector._extract_error_code("TypeError: unsupported operand") == "TypeError"

    def test_extracts_import_error(self):
        """Should extract ImportError from longrepr."""
        detector = StaticBugDetector()
        assert detector._extract_error_code("ImportError: No module named 'foo'") == "ImportError"

    def test_unknown_returns_test_failure(self):
        """Unknown error types should return TestFailure."""
        detector = StaticBugDetector()
        assert detector._extract_error_code("Something went wrong") == "TestFailure"

    def test_multiple_errors_returns_first_match(self):
        """When multiple error types present, returns first matching."""
        detector = StaticBugDetector()
        # AssertionError comes before TypeError in the list
        longrepr = "AssertionError raised after catching TypeError"
        assert detector._extract_error_code(longrepr) == "AssertionError"


class TestParsePytestJson:
    """Tests for _parse_pytest_json method."""

    def test_empty_tests_returns_empty_list(self):
        """Empty test list should return empty bug list."""
        detector = StaticBugDetector()
        json_data = {"tests": []}
        assert detector._parse_pytest_json(json_data) == []

    def test_passed_tests_return_empty_list(self):
        """Passed tests should not generate bug reports."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {"nodeid": "tests/test_foo.py::test_bar", "outcome": "passed", "lineno": 10},
                {"nodeid": "tests/test_foo.py::test_baz", "outcome": "passed", "lineno": 20},
            ]
        }
        assert detector._parse_pytest_json(json_data) == []

    def test_failed_test_creates_bug_report(self):
        """Failed test should create a StaticBugReport."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "failed",
                    "lineno": 15,
                    "call": {
                        "longrepr": "AssertionError: expected 5 got 4",
                        "crash": {"message": "assert 5 == 4"},
                    },
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].source == "pytest"
        assert bugs[0].file_path == "tests/test_foo.py"
        assert bugs[0].line_number == 15
        assert bugs[0].error_code == "AssertionError"
        assert bugs[0].severity == "moderate"

    def test_error_outcome_creates_bug_report(self):
        """Error outcome should also create a StaticBugReport."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "error",
                    "lineno": 5,
                    "call": {
                        "longrepr": "ImportError: No module named 'missing'",
                    },
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].error_code == "ImportError"
        assert bugs[0].severity == "critical"

    def test_skipped_tests_ignored(self):
        """Skipped tests should not create bug reports."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {"nodeid": "tests/test_foo.py::test_bar", "outcome": "skipped", "lineno": 10}
            ]
        }
        assert detector._parse_pytest_json(json_data) == []

    def test_multiple_failures_creates_multiple_reports(self):
        """Multiple failures should create multiple bug reports."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_a.py::test_one",
                    "outcome": "failed",
                    "lineno": 10,
                    "call": {"longrepr": "AssertionError"},
                },
                {
                    "nodeid": "tests/test_b.py::test_two",
                    "outcome": "failed",
                    "lineno": 20,
                    "call": {"longrepr": "TypeError"},
                },
                {"nodeid": "tests/test_c.py::test_three", "outcome": "passed", "lineno": 30},
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert len(bugs) == 2
        assert bugs[0].file_path == "tests/test_a.py"
        assert bugs[1].file_path == "tests/test_b.py"

    def test_nodeid_with_class_extracts_file_path(self):
        """Nodeid with class should extract just the file path."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::TestClass::test_method",
                    "outcome": "failed",
                    "lineno": 25,
                    "call": {"longrepr": "AssertionError"},
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert bugs[0].file_path == "tests/test_foo.py"

    def test_dict_longrepr_extracts_message(self):
        """Dict-style longrepr should extract reprcrash message."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "failed",
                    "lineno": 10,
                    "call": {
                        "longrepr": {
                            "reprcrash": {"message": "AssertionError: expected True"},
                        }
                    },
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].error_code == "AssertionError"

    def test_setup_phase_failure(self):
        """Setup phase failure should be handled when call phase is empty."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "error",
                    "lineno": 5,
                    "call": {},
                    "setup": {"longrepr": "ImportError: fixture not found"},
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].error_code == "ImportError"

    def test_missing_lineno_defaults_to_zero(self):
        """Missing lineno should default to 0."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "failed",
                    "call": {"longrepr": "AssertionError"},
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        assert bugs[0].line_number == 0

    def test_no_tests_key_returns_empty(self):
        """Missing tests key should return empty list."""
        detector = StaticBugDetector()
        json_data = {"summary": {"passed": 0, "failed": 0}}
        assert detector._parse_pytest_json(json_data) == []


class TestDetectFromTests:
    """Tests for detect_from_tests method with mocked subprocess."""

    def test_returns_empty_when_pytest_not_available(self):
        """Should return empty list when pytest is not installed."""
        detector = StaticBugDetector()
        with patch.object(detector, "_tool_available", return_value=False):
            result = detector.detect_from_tests()
            assert result == []

    def test_calls_pytest_with_correct_args(self):
        """Should call pytest with --json-report flags."""
        detector = StaticBugDetector()
        json_output = json.dumps({"tests": []})

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_tests()
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "pytest" in call_args
                assert "--json-report" in call_args
                assert "--json-report-file=-" in call_args

    def test_passes_path_to_pytest(self):
        """Should pass path argument to pytest command."""
        detector = StaticBugDetector()
        json_output = json.dumps({"tests": []})

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_tests("tests/specific/")
                call_args = mock_run.call_args[0][0]
                assert "tests/specific/" in call_args

    def test_parses_failed_tests_from_output(self):
        """Should parse failed tests from pytest JSON output."""
        detector = StaticBugDetector()
        json_output = json.dumps({
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "failed",
                    "lineno": 15,
                    "call": {
                        "longrepr": "AssertionError: expected True",
                        "crash": {"message": "assert True == False"},
                    },
                }
            ]
        })

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=1)
                bugs = detector.detect_from_tests()
                assert len(bugs) == 1
                assert bugs[0].source == "pytest"
                assert bugs[0].file_path == "tests/test_foo.py"

    def test_handles_mixed_output_with_json(self):
        """Should find JSON in mixed stdout output."""
        detector = StaticBugDetector()
        json_data = {"tests": []}
        # Simulate pytest output with text before JSON
        mixed_output = "collected 5 items\n\n" + json.dumps(json_data)

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=mixed_output, returncode=0)
                bugs = detector.detect_from_tests()
                assert bugs == []

    def test_returns_empty_on_no_json_output(self):
        """Should return empty list when no JSON in output."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="no json here", returncode=0)
                bugs = detector.detect_from_tests()
                assert bugs == []

    def test_returns_empty_on_invalid_json(self):
        """Should return empty list when JSON is invalid."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="{invalid json", returncode=0)
                bugs = detector.detect_from_tests()
                assert bugs == []

    def test_returns_empty_on_timeout(self):
        """Should return empty list when pytest times out."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
                bugs = detector.detect_from_tests()
                assert bugs == []

    def test_returns_empty_on_subprocess_error(self):
        """Should return empty list on subprocess errors."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.SubprocessError("failed to run")
                bugs = detector.detect_from_tests()
                assert bugs == []

    def test_returns_empty_on_unexpected_exception(self):
        """Should return empty list on unexpected exceptions."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = RuntimeError("unexpected error")
                bugs = detector.detect_from_tests()
                assert bugs == []

    def test_uses_capture_output_and_text(self):
        """Should run subprocess with capture_output=True and text=True."""
        detector = StaticBugDetector()
        json_output = json.dumps({"tests": []})

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_tests()
                _, kwargs = mock_run.call_args
                assert kwargs["capture_output"] is True
                assert kwargs["text"] is True

    def test_sets_timeout(self):
        """Should set a timeout on subprocess run."""
        detector = StaticBugDetector()
        json_output = json.dumps({"tests": []})

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_tests()
                _, kwargs = mock_run.call_args
                assert "timeout" in kwargs
                assert kwargs["timeout"] == 300


class TestStaticBugReportCreation:
    """Tests verifying StaticBugReport objects are created correctly."""

    def test_bug_report_has_all_required_fields(self):
        """StaticBugReport should have all required fields set."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_example.py::test_function",
                    "outcome": "failed",
                    "lineno": 42,
                    "call": {
                        "longrepr": "ValueError: invalid input",
                        "crash": {"message": "ValueError: invalid input"},
                    },
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        bug = bugs[0]

        assert isinstance(bug, StaticBugReport)
        assert bug.source == "pytest"
        assert bug.file_path == "tests/test_example.py"
        assert bug.line_number == 42
        assert bug.error_code == "ValueError"
        assert bug.message == "ValueError: invalid input"
        assert bug.severity == "critical"

    def test_bug_report_serialization_roundtrip(self):
        """StaticBugReport should survive serialization roundtrip."""
        detector = StaticBugDetector()
        json_data = {
            "tests": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "outcome": "failed",
                    "lineno": 10,
                    "call": {
                        "longrepr": "AssertionError: x != y",
                        "crash": {"message": "assert x == y"},
                    },
                }
            ]
        }
        bugs = detector._parse_pytest_json(json_data)
        bug = bugs[0]

        # Serialize and deserialize
        data = bug.to_dict()
        restored = StaticBugReport.from_dict(data)

        assert restored.source == bug.source
        assert restored.file_path == bug.file_path
        assert restored.line_number == bug.line_number
        assert restored.error_code == bug.error_code
        assert restored.message == bug.message
        assert restored.severity == bug.severity


class TestMapMypySeverity:
    """Tests for _map_mypy_severity method."""

    def test_error_maps_to_moderate(self):
        """mypy 'error' severity should map to moderate."""
        detector = StaticBugDetector()
        assert detector._map_mypy_severity("error") == "moderate"

    def test_note_maps_to_minor(self):
        """mypy 'note' severity should map to minor."""
        detector = StaticBugDetector()
        assert detector._map_mypy_severity("note") == "minor"

    def test_unknown_severity_defaults_to_moderate(self):
        """Unknown severity should default to moderate."""
        detector = StaticBugDetector()
        assert detector._map_mypy_severity("warning") == "moderate"
        assert detector._map_mypy_severity("unknown") == "moderate"


class TestParseMypyJson:
    """Tests for _parse_mypy_json method."""

    def test_empty_output_returns_empty_list(self):
        """Empty output should return empty bug list."""
        detector = StaticBugDetector()
        assert detector._parse_mypy_json("") == []
        assert detector._parse_mypy_json("   \n  \n  ") == []

    def test_single_error_creates_bug_report(self):
        """Single mypy error should create a StaticBugReport."""
        detector = StaticBugDetector()
        output = '{"file": "src/foo.py", "line": 10, "column": 5, "severity": "error", "message": "Incompatible return value type", "code": "return-value"}'
        bugs = detector._parse_mypy_json(output)
        assert len(bugs) == 1
        assert bugs[0].source == "mypy"
        assert bugs[0].file_path == "src/foo.py"
        assert bugs[0].line_number == 10
        assert bugs[0].error_code == "return-value"
        assert bugs[0].message == "Incompatible return value type"
        assert bugs[0].severity == "moderate"

    def test_note_severity_creates_minor_bug(self):
        """mypy note should create a minor severity bug."""
        detector = StaticBugDetector()
        output = '{"file": "src/foo.py", "line": 15, "column": 1, "severity": "note", "message": "See https://mypy.readthedocs.io/en/stable/", "code": null}'
        bugs = detector._parse_mypy_json(output)
        assert len(bugs) == 1
        assert bugs[0].severity == "minor"
        assert bugs[0].error_code == "unknown"  # null code becomes "unknown"

    def test_multiple_errors_creates_multiple_reports(self):
        """Multiple mypy errors should create multiple bug reports."""
        detector = StaticBugDetector()
        output = """{"file": "src/a.py", "line": 10, "column": 5, "severity": "error", "message": "Error 1", "code": "arg-type"}
{"file": "src/b.py", "line": 20, "column": 10, "severity": "error", "message": "Error 2", "code": "assignment"}
{"file": "src/c.py", "line": 30, "column": 15, "severity": "note", "message": "Note 1", "code": "note"}"""
        bugs = detector._parse_mypy_json(output)
        assert len(bugs) == 3
        assert bugs[0].file_path == "src/a.py"
        assert bugs[0].error_code == "arg-type"
        assert bugs[1].file_path == "src/b.py"
        assert bugs[1].error_code == "assignment"
        assert bugs[2].file_path == "src/c.py"
        assert bugs[2].severity == "minor"

    def test_skips_non_json_lines(self):
        """Should skip non-JSON lines in output."""
        detector = StaticBugDetector()
        output = """Some summary text
{"file": "src/foo.py", "line": 10, "column": 5, "severity": "error", "message": "Type error", "code": "type-arg"}
Found 1 error in 1 file"""
        bugs = detector._parse_mypy_json(output)
        assert len(bugs) == 1
        assert bugs[0].file_path == "src/foo.py"

    def test_skips_entries_without_file(self):
        """Should skip entries without file information."""
        detector = StaticBugDetector()
        output = '{"line": 10, "column": 5, "severity": "error", "message": "Error", "code": "arg-type"}'
        bugs = detector._parse_mypy_json(output)
        assert bugs == []

    def test_handles_empty_file_path(self):
        """Should skip entries with empty file path."""
        detector = StaticBugDetector()
        output = '{"file": "", "line": 10, "column": 5, "severity": "error", "message": "Error", "code": "arg-type"}'
        bugs = detector._parse_mypy_json(output)
        assert bugs == []

    def test_missing_fields_use_defaults(self):
        """Missing optional fields should use defaults."""
        detector = StaticBugDetector()
        output = '{"file": "src/foo.py"}'
        bugs = detector._parse_mypy_json(output)
        assert len(bugs) == 1
        assert bugs[0].line_number == 0
        assert bugs[0].error_code == "unknown"
        assert bugs[0].message == ""
        assert bugs[0].severity == "moderate"  # default from missing severity

    def test_null_code_becomes_unknown(self):
        """null error code should become 'unknown'."""
        detector = StaticBugDetector()
        output = '{"file": "src/foo.py", "line": 10, "column": 5, "severity": "error", "message": "Error", "code": null}'
        bugs = detector._parse_mypy_json(output)
        assert len(bugs) == 1
        assert bugs[0].error_code == "unknown"


class TestDetectFromTypes:
    """Tests for detect_from_types method with mocked subprocess."""

    def test_returns_empty_when_mypy_not_available(self):
        """Should return empty list when mypy is not installed."""
        detector = StaticBugDetector()
        with patch.object(detector, "_tool_available", return_value=False):
            result = detector.detect_from_types()
            assert result == []

    def test_calls_mypy_with_correct_args(self):
        """Should call mypy with --output=json flag."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                detector.detect_from_types()
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "mypy" in call_args
                assert "--output=json" in call_args

    def test_passes_path_to_mypy(self):
        """Should pass path argument to mypy command."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                detector.detect_from_types("src/specific/")
                call_args = mock_run.call_args[0][0]
                assert "src/specific/" in call_args

    def test_uses_current_directory_when_no_path(self):
        """Should use '.' when no path is provided."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                detector.detect_from_types()
                call_args = mock_run.call_args[0][0]
                assert "." in call_args

    def test_parses_type_errors_from_output(self):
        """Should parse type errors from mypy JSON output."""
        detector = StaticBugDetector()
        json_output = '{"file": "src/foo.py", "line": 15, "column": 5, "severity": "error", "message": "Incompatible types", "code": "arg-type"}'

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=1)
                bugs = detector.detect_from_types()
                assert len(bugs) == 1
                assert bugs[0].source == "mypy"
                assert bugs[0].file_path == "src/foo.py"
                assert bugs[0].error_code == "arg-type"

    def test_returns_empty_on_no_output(self):
        """Should return empty list when mypy has no output."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                bugs = detector.detect_from_types()
                assert bugs == []

    def test_returns_empty_on_whitespace_only_output(self):
        """Should return empty list when mypy output is whitespace only."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="   \n  ", returncode=0)
                bugs = detector.detect_from_types()
                assert bugs == []

    def test_returns_empty_on_timeout(self):
        """Should return empty list when mypy times out."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd="mypy", timeout=300)
                bugs = detector.detect_from_types()
                assert bugs == []

    def test_returns_empty_on_subprocess_error(self):
        """Should return empty list on subprocess errors."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.SubprocessError("failed to run")
                bugs = detector.detect_from_types()
                assert bugs == []

    def test_returns_empty_on_unexpected_exception(self):
        """Should return empty list on unexpected exceptions."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = RuntimeError("unexpected error")
                bugs = detector.detect_from_types()
                assert bugs == []

    def test_uses_capture_output_and_text(self):
        """Should run subprocess with capture_output=True and text=True."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                detector.detect_from_types()
                _, kwargs = mock_run.call_args
                assert kwargs["capture_output"] is True
                assert kwargs["text"] is True

    def test_sets_timeout(self):
        """Should set a timeout on subprocess run."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                detector.detect_from_types()
                _, kwargs = mock_run.call_args
                assert "timeout" in kwargs
                assert kwargs["timeout"] == 300

    def test_handles_multiple_errors_in_output(self):
        """Should handle multiple JSON lines in mypy output."""
        detector = StaticBugDetector()
        json_output = """{"file": "src/a.py", "line": 10, "column": 5, "severity": "error", "message": "Error 1", "code": "arg-type"}
{"file": "src/b.py", "line": 20, "column": 10, "severity": "error", "message": "Error 2", "code": "return-value"}"""

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=1)
                bugs = detector.detect_from_types()
                assert len(bugs) == 2
                assert bugs[0].file_path == "src/a.py"
                assert bugs[1].file_path == "src/b.py"


class TestMypyBugReportCreation:
    """Tests verifying StaticBugReport objects are created correctly for mypy."""

    def test_bug_report_has_all_required_fields(self):
        """StaticBugReport from mypy should have all required fields set."""
        detector = StaticBugDetector()
        output = '{"file": "src/example.py", "line": 42, "column": 10, "severity": "error", "message": "Argument 1 has incompatible type", "code": "arg-type"}'
        bugs = detector._parse_mypy_json(output)
        bug = bugs[0]

        assert isinstance(bug, StaticBugReport)
        assert bug.source == "mypy"
        assert bug.file_path == "src/example.py"
        assert bug.line_number == 42
        assert bug.error_code == "arg-type"
        assert bug.message == "Argument 1 has incompatible type"
        assert bug.severity == "moderate"

    def test_bug_report_serialization_roundtrip(self):
        """StaticBugReport from mypy should survive serialization roundtrip."""
        detector = StaticBugDetector()
        output = '{"file": "src/foo.py", "line": 10, "column": 5, "severity": "error", "message": "Type mismatch", "code": "assignment"}'
        bugs = detector._parse_mypy_json(output)
        bug = bugs[0]

        # Serialize and deserialize
        data = bug.to_dict()
        restored = StaticBugReport.from_dict(data)

        assert restored.source == bug.source
        assert restored.file_path == bug.file_path
        assert restored.line_number == bug.line_number
        assert restored.error_code == bug.error_code
        assert restored.message == bug.message
        assert restored.severity == bug.severity


class TestMapRuffSeverity:
    """Tests for _map_ruff_severity method."""

    def test_error_code_e_maps_to_moderate(self):
        """E (pycodestyle error) codes should map to moderate."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("E501") == "moderate"
        assert detector._map_ruff_severity("E101") == "moderate"
        assert detector._map_ruff_severity("E999") == "moderate"

    def test_error_code_f_maps_to_moderate(self):
        """F (pyflakes) codes should map to moderate."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("F401") == "moderate"
        assert detector._map_ruff_severity("F841") == "moderate"
        assert detector._map_ruff_severity("F811") == "moderate"

    def test_error_code_b_maps_to_moderate(self):
        """B (bugbear) codes should map to moderate."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("B001") == "moderate"
        assert detector._map_ruff_severity("B006") == "moderate"

    def test_error_code_s_maps_to_critical(self):
        """S (security/bandit) codes should map to critical."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("S101") == "critical"
        assert detector._map_ruff_severity("S105") == "critical"
        assert detector._map_ruff_severity("S608") == "critical"

    def test_error_code_w_maps_to_minor(self):
        """W (warning) codes should map to minor."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("W291") == "minor"
        assert detector._map_ruff_severity("W293") == "minor"
        assert detector._map_ruff_severity("W505") == "minor"

    def test_error_code_c_maps_to_minor(self):
        """C (complexity) codes should map to minor."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("C901") == "minor"
        assert detector._map_ruff_severity("C408") == "minor"

    def test_error_code_i_maps_to_minor(self):
        """I (isort) codes should map to minor."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("I001") == "minor"
        assert detector._map_ruff_severity("I002") == "minor"

    def test_error_code_n_maps_to_minor(self):
        """N (pep8-naming) codes should map to minor."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("N801") == "minor"
        assert detector._map_ruff_severity("N802") == "minor"

    def test_empty_code_defaults_to_minor(self):
        """Empty code should default to minor."""
        detector = StaticBugDetector()
        assert detector._map_ruff_severity("") == "minor"

    def test_lowercase_code_handled(self):
        """Lowercase codes should be handled correctly."""
        detector = StaticBugDetector()
        # The method converts to uppercase, so lowercase should work
        assert detector._map_ruff_severity("e501") == "moderate"
        assert detector._map_ruff_severity("s101") == "critical"
        assert detector._map_ruff_severity("w291") == "minor"


class TestParseRuffJson:
    """Tests for _parse_ruff_json method."""

    def test_empty_array_returns_empty_list(self):
        """Empty JSON array should return empty bug list."""
        detector = StaticBugDetector()
        assert detector._parse_ruff_json([]) == []

    def test_single_issue_creates_bug_report(self):
        """Single ruff issue should create a StaticBugReport."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "E501",
                "message": "Line too long (120 > 88)",
                "filename": "src/foo.py",
                "location": {"row": 10, "column": 89},
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].source == "ruff"
        assert bugs[0].file_path == "src/foo.py"
        assert bugs[0].line_number == 10
        assert bugs[0].error_code == "E501"
        assert bugs[0].message == "Line too long (120 > 88)"
        assert bugs[0].severity == "moderate"

    def test_security_issue_creates_critical_bug(self):
        """Security issue (S prefix) should create critical severity bug."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "S105",
                "message": "Possible hardcoded password",
                "filename": "src/config.py",
                "location": {"row": 25, "column": 1},
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].severity == "critical"
        assert bugs[0].error_code == "S105"

    def test_warning_creates_minor_bug(self):
        """Warning (W prefix) should create minor severity bug."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "W293",
                "message": "Blank line contains whitespace",
                "filename": "src/foo.py",
                "location": {"row": 15, "column": 1},
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].severity == "minor"

    def test_multiple_issues_creates_multiple_reports(self):
        """Multiple ruff issues should create multiple bug reports."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "E501",
                "message": "Line too long",
                "filename": "src/a.py",
                "location": {"row": 10, "column": 1},
            },
            {
                "code": "F401",
                "message": "Unused import",
                "filename": "src/b.py",
                "location": {"row": 5, "column": 1},
            },
            {
                "code": "W291",
                "message": "Trailing whitespace",
                "filename": "src/c.py",
                "location": {"row": 20, "column": 1},
            },
        ]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 3
        assert bugs[0].file_path == "src/a.py"
        assert bugs[0].error_code == "E501"
        assert bugs[1].file_path == "src/b.py"
        assert bugs[1].error_code == "F401"
        assert bugs[2].file_path == "src/c.py"
        assert bugs[2].error_code == "W291"

    def test_missing_location_defaults_to_zero(self):
        """Missing location should default line number to 0."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "E501",
                "message": "Line too long",
                "filename": "src/foo.py",
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].line_number == 0

    def test_missing_row_in_location_defaults_to_zero(self):
        """Missing row in location should default to 0."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "E501",
                "message": "Line too long",
                "filename": "src/foo.py",
                "location": {"column": 89},
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].line_number == 0

    def test_missing_fields_use_defaults(self):
        """Missing optional fields should use empty string defaults."""
        detector = StaticBugDetector()
        json_data = [{}]
        bugs = detector._parse_ruff_json(json_data)
        assert len(bugs) == 1
        assert bugs[0].file_path == ""
        assert bugs[0].line_number == 0
        assert bugs[0].error_code == ""
        assert bugs[0].message == ""
        assert bugs[0].severity == "minor"  # empty code defaults to minor


class TestDetectFromLint:
    """Tests for detect_from_lint method with mocked subprocess."""

    def test_returns_empty_when_ruff_not_available(self):
        """Should return empty list when ruff is not installed."""
        detector = StaticBugDetector()
        with patch.object(detector, "_tool_available", return_value=False):
            result = detector.detect_from_lint()
            assert result == []

    def test_calls_ruff_with_correct_args(self):
        """Should call ruff with check --output-format=json."""
        detector = StaticBugDetector()
        json_output = json.dumps([])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_lint()
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "ruff" in call_args
                assert "check" in call_args
                assert "--output-format=json" in call_args

    def test_passes_path_to_ruff(self):
        """Should pass path argument to ruff command."""
        detector = StaticBugDetector()
        json_output = json.dumps([])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_lint("src/specific/")
                call_args = mock_run.call_args[0][0]
                assert "src/specific/" in call_args

    def test_runs_on_current_directory_when_no_path(self):
        """Should not pass extra path when none provided."""
        detector = StaticBugDetector()
        json_output = json.dumps([])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_lint()
                call_args = mock_run.call_args[0][0]
                # Should only have ruff, check, and --output-format=json
                assert len(call_args) == 3

    def test_parses_lint_issues_from_output(self):
        """Should parse lint issues from ruff JSON output."""
        detector = StaticBugDetector()
        json_output = json.dumps([
            {
                "code": "F401",
                "message": "'os' imported but unused",
                "filename": "src/foo.py",
                "location": {"row": 1, "column": 8},
            }
        ])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=1)
                bugs = detector.detect_from_lint()
                assert len(bugs) == 1
                assert bugs[0].source == "ruff"
                assert bugs[0].file_path == "src/foo.py"
                assert bugs[0].error_code == "F401"

    def test_returns_empty_on_no_output(self):
        """Should return empty list when ruff has no output."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=0)
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_returns_empty_on_whitespace_only_output(self):
        """Should return empty list when ruff output is whitespace only."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="   \n  ", returncode=0)
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_returns_empty_on_invalid_json(self):
        """Should return empty list when JSON is invalid."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="{invalid json", returncode=1)
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_returns_empty_on_non_array_json(self):
        """Should return empty list when JSON is not an array."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout='{"key": "value"}', returncode=1)
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_returns_empty_on_timeout(self):
        """Should return empty list when ruff times out."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd="ruff", timeout=120)
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_returns_empty_on_subprocess_error(self):
        """Should return empty list on subprocess errors."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.SubprocessError("failed to run")
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_returns_empty_on_unexpected_exception(self):
        """Should return empty list on unexpected exceptions."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = RuntimeError("unexpected error")
                bugs = detector.detect_from_lint()
                assert bugs == []

    def test_uses_capture_output_and_text(self):
        """Should run subprocess with capture_output=True and text=True."""
        detector = StaticBugDetector()
        json_output = json.dumps([])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_lint()
                _, kwargs = mock_run.call_args
                assert kwargs["capture_output"] is True
                assert kwargs["text"] is True

    def test_sets_timeout(self):
        """Should set a 120 second timeout on subprocess run."""
        detector = StaticBugDetector()
        json_output = json.dumps([])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=0)
                detector.detect_from_lint()
                _, kwargs = mock_run.call_args
                assert "timeout" in kwargs
                assert kwargs["timeout"] == 120

    def test_handles_multiple_issues_in_output(self):
        """Should handle multiple lint issues in ruff output."""
        detector = StaticBugDetector()
        json_output = json.dumps([
            {
                "code": "E501",
                "message": "Line too long",
                "filename": "src/a.py",
                "location": {"row": 10, "column": 89},
            },
            {
                "code": "F401",
                "message": "Unused import",
                "filename": "src/b.py",
                "location": {"row": 1, "column": 1},
            },
        ])

        with patch.object(detector, "_tool_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=json_output, returncode=1)
                bugs = detector.detect_from_lint()
                assert len(bugs) == 2
                assert bugs[0].file_path == "src/a.py"
                assert bugs[1].file_path == "src/b.py"


class TestRuffBugReportCreation:
    """Tests verifying StaticBugReport objects are created correctly for ruff."""

    def test_bug_report_has_all_required_fields(self):
        """StaticBugReport from ruff should have all required fields set."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "F401",
                "message": "'os' imported but unused",
                "filename": "src/example.py",
                "location": {"row": 42, "column": 8},
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        bug = bugs[0]

        assert isinstance(bug, StaticBugReport)
        assert bug.source == "ruff"
        assert bug.file_path == "src/example.py"
        assert bug.line_number == 42
        assert bug.error_code == "F401"
        assert bug.message == "'os' imported but unused"
        assert bug.severity == "moderate"

    def test_bug_report_serialization_roundtrip(self):
        """StaticBugReport from ruff should survive serialization roundtrip."""
        detector = StaticBugDetector()
        json_data = [
            {
                "code": "S105",
                "message": "Possible hardcoded password",
                "filename": "src/config.py",
                "location": {"row": 10, "column": 1},
            }
        ]
        bugs = detector._parse_ruff_json(json_data)
        bug = bugs[0]

        # Serialize and deserialize
        data = bug.to_dict()
        restored = StaticBugReport.from_dict(data)

        assert restored.source == bug.source
        assert restored.file_path == bug.file_path
        assert restored.line_number == bug.line_number
        assert restored.error_code == bug.error_code
        assert restored.message == bug.message
        assert restored.severity == bug.severity


class TestDeduplicateBugs:
    """Tests for _deduplicate_bugs method."""

    def test_empty_list_returns_empty(self):
        """Empty bug list should return empty list."""
        detector = StaticBugDetector()
        result = detector._deduplicate_bugs([])
        assert result == []

    def test_single_bug_returns_same(self):
        """Single bug should be returned unchanged."""
        detector = StaticBugDetector()
        bug = StaticBugReport(
            source="pytest",
            file_path="test.py",
            line_number=10,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        result = detector._deduplicate_bugs([bug])
        assert len(result) == 1
        assert result[0] is bug

    def test_no_duplicates_returns_all(self):
        """List with no duplicates should return all bugs."""
        detector = StaticBugDetector()
        bugs = [
            StaticBugReport(
                source="pytest",
                file_path="test_a.py",
                line_number=10,
                error_code="AssertionError",
                message="Test 1 failed",
                severity="moderate",
            ),
            StaticBugReport(
                source="mypy",
                file_path="test_b.py",
                line_number=20,
                error_code="arg-type",
                message="Type error",
                severity="moderate",
            ),
            StaticBugReport(
                source="ruff",
                file_path="test_c.py",
                line_number=30,
                error_code="E501",
                message="Line too long",
                severity="minor",
            ),
        ]
        result = detector._deduplicate_bugs(bugs)
        assert len(result) == 3

    def test_removes_duplicates_same_file_and_line(self):
        """Bugs with same file and line should be deduplicated."""
        detector = StaticBugDetector()
        bugs = [
            StaticBugReport(
                source="pytest",
                file_path="src/foo.py",
                line_number=10,
                error_code="AssertionError",
                message="Test failed",
                severity="moderate",
            ),
            StaticBugReport(
                source="mypy",
                file_path="src/foo.py",
                line_number=10,
                error_code="arg-type",
                message="Type error on same line",
                severity="moderate",
            ),
        ]
        result = detector._deduplicate_bugs(bugs)
        assert len(result) == 1
        # First occurrence (pytest) should be kept
        assert result[0].source == "pytest"

    def test_keeps_first_occurrence(self):
        """Should keep the first occurrence when duplicates found."""
        detector = StaticBugDetector()
        bugs = [
            StaticBugReport(
                source="ruff",
                file_path="src/foo.py",
                line_number=10,
                error_code="E501",
                message="Line too long",
                severity="minor",
            ),
            StaticBugReport(
                source="pytest",
                file_path="src/foo.py",
                line_number=10,
                error_code="AssertionError",
                message="Test failed",
                severity="moderate",
            ),
        ]
        result = detector._deduplicate_bugs(bugs)
        assert len(result) == 1
        # First occurrence (ruff) should be kept
        assert result[0].source == "ruff"

    def test_same_file_different_lines_not_duplicates(self):
        """Same file but different lines should not be deduplicated."""
        detector = StaticBugDetector()
        bugs = [
            StaticBugReport(
                source="pytest",
                file_path="src/foo.py",
                line_number=10,
                error_code="AssertionError",
                message="Test 1 failed",
                severity="moderate",
            ),
            StaticBugReport(
                source="pytest",
                file_path="src/foo.py",
                line_number=20,
                error_code="AssertionError",
                message="Test 2 failed",
                severity="moderate",
            ),
        ]
        result = detector._deduplicate_bugs(bugs)
        assert len(result) == 2

    def test_same_line_different_files_not_duplicates(self):
        """Same line but different files should not be deduplicated."""
        detector = StaticBugDetector()
        bugs = [
            StaticBugReport(
                source="pytest",
                file_path="src/foo.py",
                line_number=10,
                error_code="AssertionError",
                message="Test failed in foo",
                severity="moderate",
            ),
            StaticBugReport(
                source="pytest",
                file_path="src/bar.py",
                line_number=10,
                error_code="AssertionError",
                message="Test failed in bar",
                severity="moderate",
            ),
        ]
        result = detector._deduplicate_bugs(bugs)
        assert len(result) == 2

    def test_multiple_duplicates_keeps_first_each(self):
        """Multiple groups of duplicates should each keep first."""
        detector = StaticBugDetector()
        bugs = [
            # Group 1: src/foo.py:10
            StaticBugReport(
                source="pytest",
                file_path="src/foo.py",
                line_number=10,
                error_code="AssertionError",
                message="Pytest error",
                severity="moderate",
            ),
            StaticBugReport(
                source="mypy",
                file_path="src/foo.py",
                line_number=10,
                error_code="arg-type",
                message="Mypy error",
                severity="moderate",
            ),
            # Group 2: src/bar.py:20
            StaticBugReport(
                source="ruff",
                file_path="src/bar.py",
                line_number=20,
                error_code="E501",
                message="Ruff error",
                severity="minor",
            ),
            StaticBugReport(
                source="mypy",
                file_path="src/bar.py",
                line_number=20,
                error_code="return-value",
                message="Mypy error 2",
                severity="moderate",
            ),
            # Unique: src/baz.py:30
            StaticBugReport(
                source="ruff",
                file_path="src/baz.py",
                line_number=30,
                error_code="F401",
                message="Unused import",
                severity="moderate",
            ),
        ]
        result = detector._deduplicate_bugs(bugs)
        assert len(result) == 3
        assert result[0].file_path == "src/foo.py"
        assert result[0].source == "pytest"
        assert result[1].file_path == "src/bar.py"
        assert result[1].source == "ruff"
        assert result[2].file_path == "src/baz.py"


class TestDetectAll:
    """Tests for detect_all method."""

    def test_returns_static_analysis_result(self):
        """Should return a StaticAnalysisResult instance."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=False):
            result = detector.detect_all()
            assert isinstance(result, StaticAnalysisResult)

    def test_all_tools_available_and_run(self):
        """When all tools available, all should be run."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[]):
                with patch.object(detector, "detect_from_types", return_value=[]):
                    with patch.object(detector, "detect_from_lint", return_value=[]):
                        result = detector.detect_all()
                        assert result.tools_run == ["pytest", "mypy", "ruff"]
                        assert result.tools_skipped == []

    def test_no_tools_available(self):
        """When no tools available, all should be skipped."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=False):
            result = detector.detect_all()
            assert result.tools_run == []
            assert result.tools_skipped == ["pytest", "mypy", "ruff"]
            assert result.bugs == []

    def test_some_tools_available(self):
        """Should track which tools ran vs skipped."""
        detector = StaticBugDetector()

        def tool_available(tool):
            return tool in ("pytest", "ruff")

        with patch.object(detector, "_tool_available", side_effect=tool_available):
            with patch.object(detector, "detect_from_tests", return_value=[]):
                with patch.object(detector, "detect_from_lint", return_value=[]):
                    result = detector.detect_all()
                    assert result.tools_run == ["pytest", "ruff"]
                    assert result.tools_skipped == ["mypy"]

    def test_combines_bugs_from_all_tools(self):
        """Should combine bugs from all tools."""
        detector = StaticBugDetector()

        pytest_bug = StaticBugReport(
            source="pytest",
            file_path="test_foo.py",
            line_number=10,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        mypy_bug = StaticBugReport(
            source="mypy",
            file_path="src/foo.py",
            line_number=20,
            error_code="arg-type",
            message="Type error",
            severity="moderate",
        )
        ruff_bug = StaticBugReport(
            source="ruff",
            file_path="src/bar.py",
            line_number=30,
            error_code="E501",
            message="Line too long",
            severity="minor",
        )

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[pytest_bug]):
                with patch.object(detector, "detect_from_types", return_value=[mypy_bug]):
                    with patch.object(detector, "detect_from_lint", return_value=[ruff_bug]):
                        result = detector.detect_all()
                        assert len(result.bugs) == 3
                        assert result.bugs[0].source == "pytest"
                        assert result.bugs[1].source == "mypy"
                        assert result.bugs[2].source == "ruff"

    def test_deduplicates_bugs(self):
        """Should deduplicate bugs from different tools."""
        detector = StaticBugDetector()

        # Same file and line from pytest and mypy
        pytest_bug = StaticBugReport(
            source="pytest",
            file_path="src/foo.py",
            line_number=10,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )
        mypy_bug = StaticBugReport(
            source="mypy",
            file_path="src/foo.py",
            line_number=10,
            error_code="arg-type",
            message="Type error on same line",
            severity="moderate",
        )

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[pytest_bug]):
                with patch.object(detector, "detect_from_types", return_value=[mypy_bug]):
                    with patch.object(detector, "detect_from_lint", return_value=[]):
                        result = detector.detect_all()
                        assert len(result.bugs) == 1
                        # pytest runs first, so its bug is kept
                        assert result.bugs[0].source == "pytest"

    def test_passes_path_to_all_detectors(self):
        """Should pass path argument to all detector methods."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[]) as mock_tests:
                with patch.object(detector, "detect_from_types", return_value=[]) as mock_types:
                    with patch.object(detector, "detect_from_lint", return_value=[]) as mock_lint:
                        detector.detect_all("src/specific/")
                        mock_tests.assert_called_once_with("src/specific/")
                        mock_types.assert_called_once_with("src/specific/")
                        mock_lint.assert_called_once_with("src/specific/")

    def test_passes_none_path_to_detectors(self):
        """Should pass None path to detectors when no path provided."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[]) as mock_tests:
                with patch.object(detector, "detect_from_types", return_value=[]) as mock_types:
                    with patch.object(detector, "detect_from_lint", return_value=[]) as mock_lint:
                        detector.detect_all()
                        mock_tests.assert_called_once_with(None)
                        mock_types.assert_called_once_with(None)
                        mock_lint.assert_called_once_with(None)

    def test_only_runs_available_tools(self):
        """Should only call detector methods for available tools."""
        detector = StaticBugDetector()

        def tool_available(tool):
            return tool == "mypy"

        with patch.object(detector, "_tool_available", side_effect=tool_available):
            with patch.object(detector, "detect_from_tests", return_value=[]) as mock_tests:
                with patch.object(detector, "detect_from_types", return_value=[]) as mock_types:
                    with patch.object(detector, "detect_from_lint", return_value=[]) as mock_lint:
                        detector.detect_all()
                        mock_tests.assert_not_called()
                        mock_types.assert_called_once()
                        mock_lint.assert_not_called()

    def test_handles_empty_results_from_all_tools(self):
        """Should handle empty results from all tools."""
        detector = StaticBugDetector()

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[]):
                with patch.object(detector, "detect_from_types", return_value=[]):
                    with patch.object(detector, "detect_from_lint", return_value=[]):
                        result = detector.detect_all()
                        assert result.bugs == []
                        assert result.tools_run == ["pytest", "mypy", "ruff"]

    def test_result_serialization_roundtrip(self):
        """StaticAnalysisResult should survive serialization roundtrip."""
        detector = StaticBugDetector()

        bug = StaticBugReport(
            source="pytest",
            file_path="test_foo.py",
            line_number=10,
            error_code="AssertionError",
            message="Test failed",
            severity="moderate",
        )

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[bug]):
                with patch.object(detector, "detect_from_types", return_value=[]):
                    with patch.object(detector, "detect_from_lint", return_value=[]):
                        result = detector.detect_all()

                        # Serialize and deserialize
                        data = result.to_dict()
                        restored = StaticAnalysisResult.from_dict(data)

                        assert restored.tools_run == result.tools_run
                        assert restored.tools_skipped == result.tools_skipped
                        assert len(restored.bugs) == len(result.bugs)
                        assert restored.bugs[0].source == result.bugs[0].source

    def test_multiple_bugs_per_tool(self):
        """Should handle multiple bugs from each tool."""
        detector = StaticBugDetector()

        pytest_bugs = [
            StaticBugReport(
                source="pytest",
                file_path="test_a.py",
                line_number=10,
                error_code="AssertionError",
                message="Test 1",
                severity="moderate",
            ),
            StaticBugReport(
                source="pytest",
                file_path="test_b.py",
                line_number=20,
                error_code="TypeError",
                message="Test 2",
                severity="critical",
            ),
        ]
        mypy_bugs = [
            StaticBugReport(
                source="mypy",
                file_path="src/c.py",
                line_number=30,
                error_code="arg-type",
                message="Type 1",
                severity="moderate",
            ),
        ]
        ruff_bugs = [
            StaticBugReport(
                source="ruff",
                file_path="src/d.py",
                line_number=40,
                error_code="E501",
                message="Lint 1",
                severity="minor",
            ),
            StaticBugReport(
                source="ruff",
                file_path="src/e.py",
                line_number=50,
                error_code="F401",
                message="Lint 2",
                severity="moderate",
            ),
        ]

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=pytest_bugs):
                with patch.object(detector, "detect_from_types", return_value=mypy_bugs):
                    with patch.object(detector, "detect_from_lint", return_value=ruff_bugs):
                        result = detector.detect_all()
                        assert len(result.bugs) == 5
                        # Verify order: pytest, mypy, ruff
                        assert result.bugs[0].source == "pytest"
                        assert result.bugs[1].source == "pytest"
                        assert result.bugs[2].source == "mypy"
                        assert result.bugs[3].source == "ruff"
                        assert result.bugs[4].source == "ruff"

    def test_preserves_tool_order_in_results(self):
        """Should preserve tool order: pytest, mypy, ruff."""
        detector = StaticBugDetector()

        # Create bugs with distinctive files so we can track order
        pytest_bug = StaticBugReport(
            source="pytest",
            file_path="pytest_file.py",
            line_number=1,
            error_code="AssertionError",
            message="Pytest",
            severity="moderate",
        )
        mypy_bug = StaticBugReport(
            source="mypy",
            file_path="mypy_file.py",
            line_number=2,
            error_code="arg-type",
            message="Mypy",
            severity="moderate",
        )
        ruff_bug = StaticBugReport(
            source="ruff",
            file_path="ruff_file.py",
            line_number=3,
            error_code="E501",
            message="Ruff",
            severity="minor",
        )

        with patch.object(detector, "_tool_available", return_value=True):
            with patch.object(detector, "detect_from_tests", return_value=[pytest_bug]):
                with patch.object(detector, "detect_from_types", return_value=[mypy_bug]):
                    with patch.object(detector, "detect_from_lint", return_value=[ruff_bug]):
                        result = detector.detect_all()
                        assert result.bugs[0].file_path == "pytest_file.py"
                        assert result.bugs[1].file_path == "mypy_file.py"
                        assert result.bugs[2].file_path == "ruff_file.py"
