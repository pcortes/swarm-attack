"""Static bug detector wrapping analysis tools.

StaticBugDetector provides a unified interface to run static analysis
tools (pytest, mypy, ruff) and collect their findings as StaticBugReport
instances.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import TYPE_CHECKING

from .models import StaticAnalysisResult, StaticBugReport

if TYPE_CHECKING:
    from typing import Literal

logger = logging.getLogger(__name__)


class StaticBugDetector:
    """Wrapper for static analysis tools.

    Runs static analysis tools and converts their output to StaticBugReport
    instances. Tools that are not installed are gracefully skipped.

    Example:
        detector = StaticBugDetector()
        bugs = detector.detect_from_tests("tests/")
        for bug in bugs:
            print(f"{bug.file_path}:{bug.line_number}: {bug.message}")
    """

    def _tool_available(self, tool: str) -> bool:
        """Check if a tool is available on the system.

        Args:
            tool: Name of the tool to check (e.g., "pytest", "mypy", "ruff")

        Returns:
            True if the tool is available, False otherwise
        """
        return shutil.which(tool) is not None

    def _map_pytest_severity(
        self, longrepr: str
    ) -> Literal["critical", "moderate", "minor"]:
        """Map pytest failure type to severity level.

        Args:
            longrepr: The long representation string from pytest

        Returns:
            Severity level based on the error type
        """
        # Exceptions (non-assertion errors) are critical
        if "AssertionError" not in longrepr:
            # Check for common exception types that indicate critical issues
            critical_indicators = [
                "TypeError",
                "AttributeError",
                "ImportError",
                "ModuleNotFoundError",
                "NameError",
                "RuntimeError",
                "ValueError",
                "KeyError",
                "IndexError",
                "ZeroDivisionError",
                "FileNotFoundError",
                "PermissionError",
                "OSError",
                "Exception",
                "Error",
            ]
            for indicator in critical_indicators:
                if indicator in longrepr:
                    return "critical"

        # Assertion errors are moderate (expected failures during testing)
        if "AssertionError" in longrepr:
            return "moderate"

        # Default to moderate for unclassified failures
        return "moderate"

    def _extract_error_code(self, longrepr: str) -> str:
        """Extract an error code from pytest failure representation.

        Args:
            longrepr: The long representation string from pytest

        Returns:
            Error code string (e.g., "AssertionError", "TypeError")
        """
        # Look for common Python exception types
        error_types = [
            "AssertionError",
            "TypeError",
            "AttributeError",
            "ImportError",
            "ModuleNotFoundError",
            "NameError",
            "RuntimeError",
            "ValueError",
            "KeyError",
            "IndexError",
            "ZeroDivisionError",
            "FileNotFoundError",
            "PermissionError",
            "OSError",
            "Exception",
        ]

        for error_type in error_types:
            if error_type in longrepr:
                return error_type

        return "TestFailure"

    def _parse_pytest_json(self, json_data: dict) -> list[StaticBugReport]:
        """Parse pytest JSON report output into StaticBugReport instances.

        Args:
            json_data: Parsed JSON from pytest --json-report output

        Returns:
            List of StaticBugReport instances for each test failure
        """
        bugs: list[StaticBugReport] = []

        tests = json_data.get("tests", [])
        for test in tests:
            outcome = test.get("outcome", "")
            if outcome not in ("failed", "error"):
                continue

            # Extract location information
            nodeid = test.get("nodeid", "")
            # nodeid format: "tests/test_foo.py::test_bar" or "tests/test_foo.py::TestClass::test_method"
            file_path = nodeid.split("::")[0] if "::" in nodeid else nodeid

            # Get line number from call or setup phase
            lineno = test.get("lineno", 0)

            # Get failure details
            call_info = test.get("call", {})
            longrepr = call_info.get("longrepr", "")

            # If call phase has no info, try setup phase
            if not longrepr:
                setup_info = test.get("setup", {})
                longrepr = setup_info.get("longrepr", "")

            # Handle longrepr being a dict (structured representation)
            if isinstance(longrepr, dict):
                longrepr = longrepr.get("reprcrash", {}).get("message", str(longrepr))
            elif not isinstance(longrepr, str):
                longrepr = str(longrepr)

            # Extract error code and determine severity
            error_code = self._extract_error_code(longrepr)
            severity = self._map_pytest_severity(longrepr)

            # Build a concise message
            crash_info = call_info.get("crash", {})
            message = crash_info.get("message", "") if crash_info else ""
            if not message:
                # Fallback: use first line of longrepr or nodeid
                message = longrepr.split("\n")[0][:200] if longrepr else f"Test failed: {nodeid}"

            bug = StaticBugReport(
                source="pytest",
                file_path=file_path,
                line_number=lineno,
                error_code=error_code,
                message=message,
                severity=severity,
            )
            bugs.append(bug)

        return bugs

    def detect_from_tests(self, path: str | None = None) -> list[StaticBugReport]:
        """Run pytest and detect test failures.

        Runs pytest with --json-report to get structured output, then
        parses the results into StaticBugReport instances.

        Args:
            path: Optional path to test file or directory. If None, runs
                pytest on the current directory.

        Returns:
            List of StaticBugReport instances for each test failure.
            Returns empty list if pytest is not available or if all tests pass.
        """
        if not self._tool_available("pytest"):
            logger.warning("pytest not available, skipping test detection")
            return []

        # Build command
        cmd = ["pytest", "--json-report", "--json-report-file=-", "-q"]
        if path:
            cmd.append(path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # pytest outputs JSON to stdout when using --json-report-file=-
            stdout = result.stdout

            # Find JSON in output (it may be mixed with other output)
            json_start = stdout.find("{")
            if json_start == -1:
                logger.warning("No JSON output found from pytest")
                return []

            json_str = stdout[json_start:]

            try:
                json_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse pytest JSON output: {e}")
                return []

            return self._parse_pytest_json(json_data)

        except subprocess.TimeoutExpired:
            logger.warning("pytest timed out after 300 seconds")
            return []
        except subprocess.SubprocessError as e:
            logger.warning(f"Failed to run pytest: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error running pytest: {e}")
            return []

    def _map_mypy_severity(
        self, severity: str
    ) -> Literal["critical", "moderate", "minor"]:
        """Map mypy severity level to StaticBugReport severity.

        Args:
            severity: The severity string from mypy JSON output

        Returns:
            Mapped severity level for StaticBugReport
        """
        # mypy severity levels: error, note
        # error -> moderate (type errors are important but not crashes)
        # note -> minor (informational)
        if severity == "error":
            return "moderate"
        elif severity == "note":
            return "minor"
        # Default to moderate for unknown severities
        return "moderate"

    def _parse_mypy_json(self, output: str) -> list[StaticBugReport]:
        """Parse mypy JSON output into StaticBugReport instances.

        mypy with --output=json outputs one JSON object per line.

        Args:
            output: Raw stdout from mypy --output=json

        Returns:
            List of StaticBugReport instances for each type error
        """
        bugs: list[StaticBugReport] = []

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                # Skip non-JSON lines (e.g., summary lines)
                continue

            # mypy JSON format has: file, line, column, severity, message, code
            file_path = entry.get("file", "")
            line_number = entry.get("line", 0)
            severity_str = entry.get("severity", "error")
            message = entry.get("message", "")
            error_code = entry.get("code", "unknown")

            # Skip entries without file information
            if not file_path:
                continue

            severity = self._map_mypy_severity(severity_str)

            bug = StaticBugReport(
                source="mypy",
                file_path=file_path,
                line_number=line_number,
                error_code=error_code if error_code else "unknown",
                message=message,
                severity=severity,
            )
            bugs.append(bug)

        return bugs

    def detect_from_types(self, path: str | None = None) -> list[StaticBugReport]:
        """Run mypy and detect type errors.

        Runs mypy with --output=json to get structured output, then
        parses the results into StaticBugReport instances.

        Args:
            path: Optional path to file or directory. If None, runs
                mypy on the current directory.

        Returns:
            List of StaticBugReport instances for each type error.
            Returns empty list if mypy is not available or if no errors found.
        """
        if not self._tool_available("mypy"):
            logger.warning("mypy not available, skipping type detection")
            return []

        # Build command
        cmd = ["mypy", "--output=json"]
        if path:
            cmd.append(path)
        else:
            cmd.append(".")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            # mypy outputs JSON to stdout when using --output=json
            stdout = result.stdout

            if not stdout.strip():
                # No output means no errors
                return []

            return self._parse_mypy_json(stdout)

        except subprocess.TimeoutExpired:
            logger.warning("mypy timed out after 300 seconds")
            return []
        except subprocess.SubprocessError as e:
            logger.warning(f"Failed to run mypy: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error running mypy: {e}")
            return []

    def _map_ruff_severity(
        self, code: str
    ) -> Literal["critical", "moderate", "minor"]:
        """Map ruff error code to severity level.

        Ruff codes follow a pattern where the first letter indicates the category:
        - E: pycodestyle errors (syntax/style issues)
        - F: pyflakes errors (logical errors)
        - W: pycodestyle warnings (style warnings)
        - C: complexity/convention
        - B: bugbear (likely bugs)
        - I: isort
        - N: pep8-naming
        - S: bandit security
        - And many more...

        Args:
            code: The ruff error code (e.g., "E501", "F401", "W293")

        Returns:
            Severity level based on the error category
        """
        if not code:
            return "minor"

        prefix = code[0].upper()

        # Critical: Security issues
        if prefix == "S":
            return "critical"

        # Moderate: Errors, likely bugs, and logical issues
        # E: pycodestyle errors, F: pyflakes, B: bugbear
        if prefix in ("E", "F", "B"):
            return "moderate"

        # Minor: Warnings, style, naming, complexity
        # W: warnings, C: complexity, I: isort, N: naming, etc.
        return "minor"

    def _parse_ruff_json(self, json_data: list) -> list[StaticBugReport]:
        """Parse ruff JSON output into StaticBugReport instances.

        Args:
            json_data: Parsed JSON array from ruff --output-format=json

        Returns:
            List of StaticBugReport instances for each lint issue
        """
        bugs: list[StaticBugReport] = []

        for item in json_data:
            # Extract fields from ruff JSON format
            # Ruff JSON item structure:
            # {
            #   "code": "E501",
            #   "message": "Line too long (120 > 88)",
            #   "filename": "path/to/file.py",
            #   "location": {"row": 10, "column": 1},
            #   ...
            # }
            code = item.get("code", "")
            message = item.get("message", "")
            filename = item.get("filename", "")

            # Get line number from location
            location = item.get("location", {})
            line_number = location.get("row", 0)

            severity = self._map_ruff_severity(code)

            bug = StaticBugReport(
                source="ruff",
                file_path=filename,
                line_number=line_number,
                error_code=code,
                message=message,
                severity=severity,
            )
            bugs.append(bug)

        return bugs

    def detect_from_lint(self, path: str | None = None) -> list[StaticBugReport]:
        """Run ruff and detect lint issues.

        Runs ruff with --output-format=json to get structured output, then
        parses the results into StaticBugReport instances.

        Args:
            path: Optional path to file or directory to lint. If None, runs
                ruff on the current directory.

        Returns:
            List of StaticBugReport instances for each lint issue.
            Returns empty list if ruff is not available or if no issues found.
        """
        if not self._tool_available("ruff"):
            logger.warning("ruff not available, skipping lint detection")
            return []

        # Build command
        cmd = ["ruff", "check", "--output-format=json"]
        if path:
            cmd.append(path)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minute timeout
            )

            # ruff outputs JSON to stdout
            stdout = result.stdout.strip()

            if not stdout:
                # No output means no issues found
                return []

            try:
                json_data = json.loads(stdout)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse ruff JSON output: {e}")
                return []

            # Ruff outputs a JSON array
            if not isinstance(json_data, list):
                logger.warning("ruff output is not a JSON array")
                return []

            return self._parse_ruff_json(json_data)

        except subprocess.TimeoutExpired:
            logger.warning("ruff timed out after 120 seconds")
            return []
        except subprocess.SubprocessError as e:
            logger.warning(f"Failed to run ruff: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error running ruff: {e}")
            return []

    def _deduplicate_bugs(
        self, bugs: list[StaticBugReport]
    ) -> list[StaticBugReport]:
        """Remove duplicate bugs that appear in multiple tools.

        Bugs are considered duplicates if they have the same file path and
        line number. When duplicates are found, the first occurrence is kept
        (based on tool order: pytest, mypy, ruff).

        Args:
            bugs: List of bugs from all tools combined

        Returns:
            Deduplicated list of bugs
        """
        seen: set[tuple[str, int]] = set()
        unique_bugs: list[StaticBugReport] = []

        for bug in bugs:
            key = (bug.file_path, bug.line_number)
            if key not in seen:
                seen.add(key)
                unique_bugs.append(bug)

        return unique_bugs

    def detect_all(self, path: str | None = None) -> StaticAnalysisResult:
        """Run all available static analysis tools and combine results.

        Runs pytest, mypy, and ruff in sequence, collecting all detected bugs.
        Tools that are not installed are gracefully skipped and recorded in
        tools_skipped. Duplicate bugs (same file and line) are removed.

        Args:
            path: Optional path to file or directory to analyze. If None,
                runs on the current directory.

        Returns:
            StaticAnalysisResult containing all bugs found, which tools ran,
            and which tools were skipped.

        Example:
            detector = StaticBugDetector()
            result = detector.detect_all("src/")
            print(f"Found {len(result.bugs)} bugs")
            print(f"Tools run: {result.tools_run}")
            print(f"Tools skipped: {result.tools_skipped}")
        """
        all_bugs: list[StaticBugReport] = []
        tools_run: list[str] = []
        tools_skipped: list[str] = []

        # Run pytest
        if self._tool_available("pytest"):
            pytest_bugs = self.detect_from_tests(path)
            all_bugs.extend(pytest_bugs)
            tools_run.append("pytest")
        else:
            tools_skipped.append("pytest")

        # Run mypy
        if self._tool_available("mypy"):
            mypy_bugs = self.detect_from_types(path)
            all_bugs.extend(mypy_bugs)
            tools_run.append("mypy")
        else:
            tools_skipped.append("mypy")

        # Run ruff
        if self._tool_available("ruff"):
            ruff_bugs = self.detect_from_lint(path)
            all_bugs.extend(ruff_bugs)
            tools_run.append("ruff")
        else:
            tools_skipped.append("ruff")

        # Deduplicate bugs
        unique_bugs = self._deduplicate_bugs(all_bugs)

        return StaticAnalysisResult(
            bugs=unique_bugs,
            tools_run=tools_run,
            tools_skipped=tools_skipped,
        )
