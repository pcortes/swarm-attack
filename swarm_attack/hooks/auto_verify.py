"""AutoVerifyHook module for automated test and lint verification.

This module provides a PostToolUse hook that automatically runs tests and linting
after file modifications. It implements the spec section 2.2: Auto-Verify Hook.

Key features:
- PostToolUse hook that runs tests, lint after changes
- Triggers on file writes and git commits
- Runs pytest on test files after code changes
- Runs ruff/flake8 on modified Python files
- Fails loudly if tests break (no silent failures)
- Creates verification record in .swarm/verification/
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import logging
import re
import subprocess


class VerificationError(Exception):
    """Exception raised when verification fails.

    Attributes:
        message: Description of what failed.
        result: The VerificationResult with failure details.
    """

    def __init__(self, message: str, result: Optional["VerificationResult"] = None):
        self.result = result
        super().__init__(message)


@dataclass
class VerificationResult:
    """Result of a verification operation.

    Attributes:
        success: Whether all verification checks passed.
        tests_passed: Number of tests that passed.
        tests_failed: Number of tests that failed.
        lint_errors: Number of linting errors found.
        output: Combined output from test/lint runs.
        error: Error message if verification failed.
        errors: List of all errors encountered.
    """

    success: bool
    tests_passed: int = 0
    tests_failed: int = 0
    lint_errors: int = 0
    output: str = ""
    error: Optional[str] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class VerificationRecord:
    """Record of a verification run stored in .swarm/verification/.

    Attributes:
        timestamp: ISO format timestamp of the verification.
        modified_files: List of files that were modified.
        success: Whether verification passed.
        test_result: Dict with test results (passed, failed, etc).
        lint_result: Dict with lint results (errors, etc).
    """

    timestamp: str
    modified_files: List[str]
    success: bool
    test_result: Optional[Dict[str, Any]] = None
    lint_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "timestamp": self.timestamp,
            "modified_files": self.modified_files,
            "success": self.success,
            "test_result": self.test_result,
            "lint_result": self.lint_result,
        }

    def to_json(self) -> str:
        """Serialize record to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class AutoVerifyHook:
    """PostToolUse hook that runs pytest and ruff after file changes.

    This hook automatically verifies code changes by running tests and linting.
    It triggers on Python file writes and git commits, failing loudly if
    verification fails.

    Attributes:
        config: SwarmConfig with test configuration.
        linter: Name of linter to use ('ruff' or 'flake8').
        _logger: Logger for info/warnings.
    """

    def __init__(
        self,
        config: Any,
        logger: Optional[logging.Logger] = None,
        linter: str = "ruff",
    ):
        """Initialize AutoVerifyHook.

        Args:
            config: SwarmConfig with test configuration (tests.command, tests.args, etc).
            logger: Optional logger for warnings/info.
            linter: Linter to use - 'ruff' (default) or 'flake8'.
        """
        self.config = config
        self._logger = logger or logging.getLogger(__name__)
        self.linter = linter

    def _ensure_verification_dir(self) -> Path:
        """Ensure .swarm/verification/ directory exists.

        Returns:
            Path to verification directory.
        """
        verification_dir = Path(self.config.swarm_path) / "verification"
        verification_dir.mkdir(parents=True, exist_ok=True)
        return verification_dir

    def _parse_test_output(self, stdout: str) -> tuple[int, int]:
        """Parse pytest output to extract passed/failed counts.

        Args:
            stdout: stdout from pytest run.

        Returns:
            Tuple of (passed, failed) counts.
        """
        passed = 0
        failed = 0

        # Look for patterns like "5 passed", "1 failed, 4 passed"
        passed_match = re.search(r"(\d+)\s+passed", stdout)
        failed_match = re.search(r"(\d+)\s+failed", stdout)

        if passed_match:
            passed = int(passed_match.group(1))
        if failed_match:
            failed = int(failed_match.group(1))

        return passed, failed

    def _parse_lint_output(self, stdout: str, returncode: int) -> int:
        """Parse linter output to extract error count.

        Args:
            stdout: stdout from linter run.
            returncode: Exit code from linter.

        Returns:
            Number of lint errors found.
        """
        if returncode == 0:
            return 0

        # Count lines that look like errors (file:line:col: code)
        error_pattern = re.compile(r"^[^:]+:\d+:\d+:", re.MULTILINE)
        matches = error_pattern.findall(stdout)
        return max(len(matches), 1)  # At least 1 if returncode != 0

    def run_tests(self, test_files: List[str]) -> VerificationResult:
        """Execute pytest on the given test files.

        Args:
            test_files: List of test file paths to run.

        Returns:
            VerificationResult with test run results.
        """
        cmd = [
            self.config.tests.command,
            *self.config.tests.args,
            *test_files,
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.config.repo_root,
                timeout=self.config.tests.timeout_seconds,
                capture_output=True,
                text=True,
            )

            passed, failed = self._parse_test_output(result.stdout)
            success = result.returncode == 0

            return VerificationResult(
                success=success,
                tests_passed=passed,
                tests_failed=failed,
                output=result.stdout,
                error=result.stderr if not success else None,
            )

        except subprocess.TimeoutExpired as e:
            return VerificationResult(
                success=False,
                output="",
                error=f"Test timeout after {e.timeout} seconds",
            )
        except FileNotFoundError as e:
            return VerificationResult(
                success=False,
                output="",
                error=f"Test runner not found: {e}",
            )

    def run_linter(self, files: List[str]) -> VerificationResult:
        """Execute linter on the given files.

        Args:
            files: List of file paths to lint.

        Returns:
            VerificationResult with lint results.
        """
        # Filter to Python files only
        python_files = [f for f in files if f.endswith(".py")]

        if not python_files:
            return VerificationResult(
                success=True,
                lint_errors=0,
                output="",
            )

        cmd = [self.linter, "check", *python_files]

        try:
            result = subprocess.run(
                cmd,
                cwd=self.config.repo_root,
                capture_output=True,
                text=True,
                timeout=60,  # Linting should be fast
            )

            lint_errors = self._parse_lint_output(result.stdout, result.returncode)
            success = result.returncode == 0

            return VerificationResult(
                success=success,
                lint_errors=lint_errors,
                output=result.stdout,
                error=result.stderr if not success else None,
            )

        except FileNotFoundError as e:
            return VerificationResult(
                success=False,
                output="",
                error=f"Linter not found: {e}",
            )
        except subprocess.TimeoutExpired:
            return VerificationResult(
                success=False,
                output="",
                error="Linter timeout",
            )

    def _save_verification_record(
        self,
        modified_files: List[str],
        test_result: VerificationResult,
        lint_result: VerificationResult,
        overall_success: bool,
    ) -> None:
        """Save verification record to .swarm/verification/.

        Args:
            modified_files: Files that were verified.
            test_result: Result from running tests.
            lint_result: Result from running linter.
            overall_success: Whether overall verification passed.
        """
        verification_dir = self._ensure_verification_dir()

        timestamp = datetime.now().isoformat()
        record = VerificationRecord(
            timestamp=timestamp,
            modified_files=modified_files,
            success=overall_success,
            test_result={
                "passed": test_result.tests_passed,
                "failed": test_result.tests_failed,
                "success": test_result.success,
                "output": test_result.output[:1000],  # Truncate large output
            },
            lint_result={
                "errors": lint_result.lint_errors,
                "success": lint_result.success,
                "output": lint_result.output[:1000],  # Truncate large output
            },
        )

        # Generate unique filename with timestamp
        safe_timestamp = timestamp.replace(":", "-").replace(".", "-")
        filename = f"verification-{safe_timestamp}.json"
        filepath = verification_dir / filename

        with open(filepath, "w") as f:
            f.write(record.to_json())

    def verify(
        self,
        modified_files: List[str],
        test_files: List[str],
        fail_fast: bool = True,
    ) -> VerificationResult:
        """Run verification on modified files.

        This method runs tests and linting, optionally failing fast on first error.

        Args:
            modified_files: List of files that were modified.
            test_files: List of test files to run.
            fail_fast: If True, raise VerificationError on first failure.
                      If False, collect all errors and return result.

        Returns:
            VerificationResult with combined results.

        Raises:
            VerificationError: If verification fails and fail_fast=True.
        """
        errors = []

        # Run tests first
        test_result = self.run_tests(test_files)

        if not test_result.success:
            error_msg = f"Tests failed: {test_result.tests_failed} failures"
            if test_result.output:
                error_msg += f"\n{test_result.output}"
            errors.append(error_msg)

            if self._logger:
                self._logger.error(f"Verification failed: {error_msg}")

            if fail_fast:
                # Still save record before raising
                self._save_verification_record(
                    modified_files,
                    test_result,
                    VerificationResult(success=True),  # Lint not run
                    overall_success=False,
                )
                raise VerificationError(
                    f"test failures: {test_result.tests_failed} failed",
                    result=test_result,
                )

        # Run linter
        lint_result = self.run_linter(modified_files)

        if not lint_result.success:
            error_msg = f"Lint errors: {lint_result.lint_errors} errors"
            if lint_result.output:
                error_msg += f"\n{lint_result.output}"
            errors.append(error_msg)

            if self._logger:
                self._logger.error(f"Verification failed: {error_msg}")

            if fail_fast:
                # Save record before raising
                self._save_verification_record(
                    modified_files,
                    test_result,
                    lint_result,
                    overall_success=False,
                )
                raise VerificationError(
                    f"lint failures: {lint_result.lint_errors} errors",
                    result=lint_result,
                )

        # Determine overall success
        overall_success = test_result.success and lint_result.success

        # Save verification record
        self._save_verification_record(
            modified_files, test_result, lint_result, overall_success
        )

        # Build combined result
        return VerificationResult(
            success=overall_success,
            tests_passed=test_result.tests_passed,
            tests_failed=test_result.tests_failed,
            lint_errors=lint_result.lint_errors,
            output=f"{test_result.output}\n{lint_result.output}".strip(),
            error="; ".join(errors) if errors else None,
            errors=errors,
        )

    def should_trigger(self, event_type: str, file_path: Optional[str]) -> bool:
        """Determine if verification should trigger for this event.

        Args:
            event_type: Type of event ('file_write', 'git_commit', etc).
            file_path: Path to the file involved (may be None for git_commit).

        Returns:
            True if verification should run.
        """
        # Always trigger on git commits
        if event_type == "git_commit":
            return True

        # Only trigger on file_write for Python files
        if event_type == "file_write" and file_path:
            # Skip non-Python files
            if not file_path.endswith(".py"):
                return False

            # Skip __pycache__ and .pyc files
            if "__pycache__" in file_path or file_path.endswith(".pyc"):
                return False

            return True

        return False

    def on_post_tool_use(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: Dict[str, Any],
    ) -> Optional[VerificationResult]:
        """PostToolUse hook handler.

        Called after a tool is used. Triggers verification for file writes.

        Args:
            tool_name: Name of the tool that was used.
            tool_args: Arguments passed to the tool.
            tool_result: Result from the tool execution.

        Returns:
            VerificationResult if verification was triggered, None otherwise.
        """
        # Only trigger on Write tool
        if tool_name != "Write":
            return None

        file_path = tool_args.get("file_path", "")

        # Check if we should trigger verification
        if not self.should_trigger("file_write", file_path):
            return None

        # For simplicity, run tests related to the modified file
        # In a real implementation, this would use test discovery
        modified_files = [file_path]

        # Infer test files from source file path
        test_files = []
        if file_path.startswith("src/") or file_path.startswith("swarm_attack/"):
            # Map source to test file
            base_name = Path(file_path).stem
            test_files = [f"tests/test_{base_name}.py"]
        elif file_path.startswith("tests/"):
            test_files = [file_path]

        if not test_files:
            # Run all tests if we can't determine specific ones
            test_files = ["tests/"]

        try:
            return self.verify(
                modified_files=modified_files,
                test_files=test_files,
                fail_fast=False,  # Don't raise in hook context
            )
        except VerificationError as e:
            self._logger.error(f"Verification failed: {e}")
            return e.result


__all__ = [
    "AutoVerifyHook",
    "VerificationResult",
    "VerificationRecord",
    "VerificationError",
]
