"""
Verifier Agent for Feature Swarm.

This agent runs tests to verify that the implementation from CoderAgent
works correctly. It runs pytest on the generated test files and reports
results.

The agent can optionally use LLM for intelligent failure analysis when
tests fail (enabled via analyze_failures=True in context).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.utils.fs import file_exists

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.memory.store import MemoryStore
    from swarm_attack.state_store import StateStore


class VerifierAgent(BaseAgent):
    """
    Agent that runs tests to verify implementation correctness.

    This is the final step in the TDD cycle - confirming that the
    implementation from CoderAgent makes all tests pass.

    The agent runs pytest directly and parses output. Optionally, when
    tests fail and analyze_failures=True, it uses LLM to analyze the
    failure and suggest fixes.
    """

    name = "verifier"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
        memory_store: Optional[MemoryStore] = None,
    ) -> None:
        """Initialize the Verifier agent.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            llm_runner: Optional Claude CLI runner.
            state_store: Optional state store for persistence.
            memory_store: Optional memory store for recording schema drift events.
        """
        super().__init__(config, logger, llm_runner, state_store)
        self._test_timeout = config.tests.timeout_seconds
        self._memory_store = memory_store

    def _get_default_test_path(self, feature_id: str, issue_number: int) -> Path:
        """Get the default path for generated tests."""
        tests_dir = Path(self.config.repo_root) / "tests" / "generated" / feature_id
        return tests_dir / f"test_issue_{issue_number}.py"

    def _run_pytest(
        self,
        test_path: Optional[Path] = None,
        timeout: Optional[int] = None,
        run_all: bool = False,
        test_files: Optional[list[Path]] = None,
    ) -> tuple[int, str]:
        """
        Run pytest on the specified test file or full test suite.

        Args:
            test_path: Path to the test file to run. Ignored if run_all=True or test_files provided.
            timeout: Optional timeout in seconds.
            run_all: If True, run full test suite for regression detection.
            test_files: Optional list of specific test files to run for regression check.

        Returns:
            Tuple of (exit_code, combined_output).

        Raises:
            TimeoutError: If pytest times out.
            OSError: If pytest cannot be executed.
        """
        timeout = timeout or self._test_timeout

        # Build pytest command
        if test_files:
            # Run specific test files (for targeted regression check of DONE issues only)
            cmd = ["pytest", "-v", "--tb=short"] + [str(f) for f in test_files]
        elif run_all:
            # Run full test suite for regression detection
            cmd = ["pytest", "-v", "--tb=short", "-q"]
        else:
            # Run specific test file
            cmd = ["pytest", str(test_path), "-v", "--tb=short"]

        try:
            # Include repo root in PYTHONPATH so feature packages (e.g., external_dashboard/)
            # can be imported during tests. This is necessary because code may be written
            # to feature-specific directories rather than the main package.
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH", "")
            repo_root_str = str(self.config.repo_root)
            if existing_pythonpath:
                env["PYTHONPATH"] = f"{repo_root_str}:{existing_pythonpath}"
            else:
                env["PYTHONPATH"] = repo_root_str

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.config.repo_root,
                env=env,
            )

            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr

            return result.returncode, output

        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"Test timed out after {timeout} seconds") from e

    def _parse_pytest_failures(self, output: str) -> list[dict[str, Any]]:
        """
        Parse pytest output for detailed failure information.

        Extracts test name, file, line number, and error message for each
        failing test. This information is crucial for CoderAgent to understand
        exactly what needs to be fixed on retry.

        Args:
            output: Raw pytest output.

        Returns:
            List of failure dictionaries:
                - test: Test function name
                - class: Test class name (if any)
                - file: Test file path
                - line: Line number where assertion failed
                - error: Full error message
                - short_message: Brief description of the failure
        """
        failures = []

        if not output.strip():
            return failures

        # Pattern for short summary line:
        # FAILED tests/path/file.py::TestClass::test_name - Error message
        summary_pattern = r'FAILED\s+([\w/._-]+)::(\w+)::(\w+)\s+-\s+(.+)'

        # Find all FAILED lines in short summary
        for match in re.finditer(summary_pattern, output):
            file_path, test_class, test_name, error_msg = match.groups()

            # Try to find line number from traceback
            # Look for the file:line pattern in the traceback section
            line_num = None
            traceback_pattern = rf'{re.escape(file_path)}:(\d+)'
            line_match = re.search(traceback_pattern, output)
            if line_match:
                line_num = int(line_match.group(1))

            failures.append({
                "test": test_name,
                "class": test_class,
                "file": file_path,
                "line": line_num,
                "error": error_msg.strip(),
                "short_message": error_msg.strip()[:100],
            })

        # If no matches with class, try pattern without class:
        # FAILED tests/path/file.py::test_name - Error message
        if not failures:
            no_class_pattern = r'FAILED\s+([\w/._-]+)::(\w+)\s+-\s+(.+)'
            for match in re.finditer(no_class_pattern, output):
                file_path, test_name, error_msg = match.groups()

                # Skip if this looks like a class pattern we missed
                if '::' in file_path:
                    continue

                line_num = None
                traceback_pattern = rf'{re.escape(file_path)}:(\d+)'
                line_match = re.search(traceback_pattern, output)
                if line_match:
                    line_num = int(line_match.group(1))

                failures.append({
                    "test": test_name,
                    "class": None,
                    "file": file_path,
                    "line": line_num,
                    "error": error_msg.strip(),
                    "short_message": error_msg.strip()[:100],
                })

        return failures

    def _parse_pytest_output(self, output: str) -> dict[str, Any]:
        """
        Parse pytest output for test counts and duration.

        Args:
            output: Raw pytest output.

        Returns:
            Dictionary with parsed results:
                - tests_passed: Number of passing tests
                - tests_failed: Number of failing tests
                - tests_run: Total tests run
                - errors: Number of collection/runtime errors
                - skipped: Number of skipped tests
                - duration_seconds: Test duration
        """
        result = {
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_run": 0,
            "errors": 0,
            "skipped": 0,
            "duration_seconds": 0.0,
        }

        if not output.strip():
            return result

        # Pattern: ===== X passed, Y failed, Z error in N.NNs =====
        # Also matches: ===== X passed in N.NNs =====
        # Also matches: ===== X failed in N.NNs =====
        summary_pattern = r"=+\s*([\d\w\s,]+)\s+in\s+([\d.]+)s\s*=+"

        match = re.search(summary_pattern, output)
        if match:
            summary_text = match.group(1)
            duration = match.group(2)

            result["duration_seconds"] = float(duration)

            # Parse counts from summary
            # Match patterns like "5 passed", "2 failed", "1 error", "3 skipped"
            passed_match = re.search(r"(\d+)\s+passed", summary_text)
            failed_match = re.search(r"(\d+)\s+failed", summary_text)
            error_match = re.search(r"(\d+)\s+error", summary_text)
            skipped_match = re.search(r"(\d+)\s+skipped", summary_text)

            if passed_match:
                result["tests_passed"] = int(passed_match.group(1))
            if failed_match:
                result["tests_failed"] = int(failed_match.group(1))
            if error_match:
                result["errors"] = int(error_match.group(1))
            if skipped_match:
                result["skipped"] = int(skipped_match.group(1))

            # Total tests run = passed + failed (skipped don't count)
            result["tests_run"] = result["tests_passed"] + result["tests_failed"]

        # Check for "no tests ran" pattern
        if "no tests ran" in output.lower():
            result["tests_run"] = 0

        # Check for errors pattern (e.g., "1 error in 0.5s")
        error_only_match = re.search(r"=+\s*(\d+)\s+error\s+in", output)
        if error_only_match and result["errors"] == 0:
            result["errors"] = int(error_only_match.group(1))

        return result

    def _parse_analysis_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse LLM response for failure analysis.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Dictionary with parsed analysis or error info.
        """
        # Try to extract JSON from the response
        # Handle cases where LLM wraps JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[^{}]*"root_cause"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Return structured error with raw response
            return {
                "error": "Failed to parse LLM response as JSON",
                "raw_response": response_text[:1000],  # Truncate for safety
            }

    def _is_subclass_of_existing(
        self,
        file_path: str,
        class_name: str,
        existing_class: str,
    ) -> bool:
        """
        Check if a class in a file is a subclass of an existing class.

        Uses AST parsing to examine class inheritance. This allows subclassing
        to proceed without being flagged as schema drift.

        Args:
            file_path: Path to the file containing the class (relative to repo root)
            class_name: Name of the class to check
            existing_class: Name of the existing class it might inherit from

        Returns:
            True if class_name inherits from existing_class, False otherwise.
        """
        import ast

        try:
            full_path = Path(self.config.repo_root) / file_path
            if not full_path.exists():
                return False

            content = full_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    # Check base classes
                    for base in node.bases:
                        base_name = None
                        if isinstance(base, ast.Name):
                            base_name = base.id
                        elif isinstance(base, ast.Attribute):
                            base_name = base.attr

                        if base_name == existing_class:
                            return True

            return False

        except (SyntaxError, OSError, UnicodeDecodeError):
            # If we can't parse, assume not a subclass (safe default)
            return False

    def _check_duplicate_classes(
        self,
        new_classes: dict[str, list[str]],
        registry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Check for duplicate class definitions across modules.

        This prevents schema drift where different issues create conflicting
        class definitions. If Issue #1 creates AutopilotSession in models.py,
        Issue #9 should import it rather than recreating it in autopilot.py.

        Args:
            new_classes: Mapping of file_path -> list of class names being created
            registry: Module registry with structure:
                {"modules": {file_path: {"created_by_issue": int, "classes": [str]}}}

        Returns:
            List of conflict dictionaries, each containing:
                - class_name: The duplicated class name
                - existing_file: Where the class was originally defined
                - new_file: Where the duplicate is being created
                - existing_issue: Issue number that created the original
                - severity: Always "critical" for schema drift
                - message: Human-readable description with "SCHEMA DRIFT DETECTED"
        """
        conflicts = []

        # Handle empty registry
        if not registry or "modules" not in registry:
            return conflicts

        modules = registry.get("modules", {})

        # Build a map of class_name -> (file_path, issue_number) for existing classes
        existing_classes: dict[str, tuple[str, int]] = {}
        for file_path, file_info in modules.items():
            issue_number = file_info.get("created_by_issue")
            for class_name in file_info.get("classes", []):
                existing_classes[class_name] = (file_path, issue_number)

        # Check each new class for conflicts
        for new_file, class_list in new_classes.items():
            for class_name in class_list:
                if class_name in existing_classes:
                    existing_file, existing_issue = existing_classes[class_name]
                    # Same file is OK (modification, not duplication)
                    if existing_file == new_file:
                        continue

                    # Check if it's a subclass of the existing class
                    # Subclassing is allowed - it extends rather than duplicates
                    if self._is_subclass_of_existing(new_file, class_name, class_name):
                        continue

                    # Different file and not a subclass = schema drift
                    conflicts.append({
                        "class_name": class_name,
                        "existing_file": existing_file,
                        "new_file": new_file,
                        "existing_issue": existing_issue,
                        "severity": "critical",
                        "message": (
                            f"SCHEMA DRIFT DETECTED: Class '{class_name}' already exists in "
                            f"'{existing_file}' (created by issue #{existing_issue}). "
                            f"Cannot recreate in '{new_file}' - this will cause runtime errors. "
                            f"Import the existing class instead of redefining it."
                        ),
                    })

        return conflicts

    def _store_schema_drift_in_memory(
        self,
        conflict: dict[str, Any],
        feature_id: str,
        issue_number: Optional[int],
    ) -> None:
        """
        Store a schema drift event in the memory store.

        Records the schema drift for cross-session learning, enabling the system
        to learn from past drift patterns and warn about similar issues.

        Args:
            conflict: Dictionary with conflict details from _check_duplicate_classes.
            feature_id: The feature ID where drift was detected.
            issue_number: The issue number being verified.
        """
        if self._memory_store is None:
            return

        from swarm_attack.memory.store import MemoryEntry

        entry = MemoryEntry(
            id=str(uuid4()),
            category="schema_drift",
            feature_id=feature_id,
            issue_number=issue_number,
            content={
                "class_name": conflict["class_name"],
                "existing_file": conflict["existing_file"],
                "new_file": conflict["new_file"],
                "existing_issue": conflict.get("existing_issue"),
            },
            outcome="blocked",
            created_at=datetime.now().isoformat(),
            tags=["schema_drift", conflict["class_name"]],
        )

        self._memory_store.add(entry)
        self._memory_store.save()

        self._log("schema_drift_stored", {
            "class_name": conflict["class_name"],
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

    def _analyze_failure_with_llm(
        self,
        test_output: str,
        context: dict[str, Any],
        is_regression: bool = False,
    ) -> dict[str, Any]:
        """
        Use LLM to analyze test failure and suggest fixes.

        Only called when tests fail and analyze_failures=True.

        Args:
            test_output: The pytest output showing failures.
            context: The run context with feature_id, issue_number, etc.
            is_regression: Whether this is a regression failure.

        Returns:
            Dictionary with analysis results:
                - root_cause: Description of what went wrong
                - recoverable: Whether automatic recovery is possible
                - suggested_fix: Specific fix suggestion (if recoverable)
                - affected_files: List of files that need changes
        """
        if not self._llm:
            return {"error": "No LLM runner configured for failure analysis"}

        try:
            # Load skill prompt
            skill_prompt = self.load_skill("verifier")
        except SkillNotFoundError:
            # Fall back to inline prompt if skill file not found
            skill_prompt = """Analyze this test failure and respond with JSON:
{
  "root_cause": "description",
  "recoverable": true/false,
  "suggested_fix": "fix or null",
  "affected_files": []
}"""

        # Build analysis prompt
        failure_type = "regression" if is_regression else "issue test"
        prompt = f"""{skill_prompt}

## Test Output ({failure_type} failure)
```
{test_output[:5000]}
```

## Context
- Feature: {context.get('feature_id')}
- Issue: {context.get('issue_number')}
"""

        self._log("verifier_failure_analysis_start", {
            "feature_id": context.get("feature_id"),
            "issue_number": context.get("issue_number"),
            "is_regression": is_regression,
        })

        try:
            # Invoke LLM
            result = self._llm.run(
                prompt=prompt,
                allowed_tools=["Read", "Glob", "Grep"],
            )

            # Track cost via checkpoint (checkpoint adds to _total_cost automatically)
            self.checkpoint("failure_analysis_complete", cost_usd=result.total_cost_usd)

            # Parse response
            analysis = self._parse_analysis_response(result.text)

            self._log("verifier_failure_analysis_complete", {
                "feature_id": context.get("feature_id"),
                "issue_number": context.get("issue_number"),
                "recoverable": analysis.get("recoverable"),
                "cost_usd": result.total_cost_usd,
            })

            return analysis

        except Exception as e:
            self._log("verifier_failure_analysis_error", {
                "error": str(e),
            }, level="error")
            return {
                "error": f"LLM analysis failed: {str(e)}",
            }

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Run tests to verify implementation.

        This agent performs verification in up to three steps:
        1. Run the specific issue's tests to verify the implementation
        2. Run the full test suite to check for regressions (if check_regressions=True)
        3. If tests fail and analyze_failures=True, use LLM to analyze and suggest fixes

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - issue_number: The issue order number (required)
                - test_path: Optional path to test file (defaults to standard location)
                - implementation_files: Optional list of files created by CoderAgent
                - check_regressions: Whether to run full test suite (default: True)
                - regression_test_files: Optional list of test file paths to use for regression
                                         (only tests from DONE issues, not BLOCKED)
                - analyze_failures: Whether to use LLM for failure analysis (default: False)

        Returns:
            AgentResult with:
                - success: True if ALL tests pass (both issue tests and regression check)
                - output: Dict with test results and optional failure_analysis
                - errors: List of any errors encountered
                - cost_usd: LLM cost if failure analysis was performed, else 0.0
        """
        # Validate context
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        issue_number = context.get("issue_number")
        if issue_number is None:
            return AgentResult.failure_result("Missing required context: issue_number")

        check_regressions = context.get("check_regressions", True)
        analyze_failures = context.get("analyze_failures", False)
        regression_test_files = context.get("regression_test_files")  # List of Path objects or None

        self._log("verifier_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "check_regressions": check_regressions,
            "analyze_failures": analyze_failures,
        })
        self.checkpoint("started")

        # Determine test file path
        test_path_str = context.get("test_path")
        if test_path_str:
            test_path = Path(test_path_str)
        else:
            test_path = self._get_default_test_path(feature_id, issue_number)

        # Check if test file exists
        if not file_exists(test_path):
            error = f"Test file not found at {test_path}"
            self._log("verifier_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("context_loaded")

        # Step 0: Check for schema drift (before running tests)
        module_registry = context.get("module_registry")
        new_classes_defined = context.get("new_classes_defined")

        if module_registry and new_classes_defined:
            schema_conflicts = self._check_duplicate_classes(new_classes_defined, module_registry)

            if schema_conflicts:
                # Schema drift detected - fail immediately without running tests
                error_messages = [c["message"] for c in schema_conflicts]
                self._log("verifier_schema_drift", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "conflicts": len(schema_conflicts),
                }, level="error")

                # Store each schema drift event in memory for cross-session learning
                for conflict in schema_conflicts:
                    self._store_schema_drift_in_memory(
                        conflict=conflict,
                        feature_id=feature_id,
                        issue_number=issue_number,
                    )

                return AgentResult(
                    success=False,
                    output={
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "tests_run": 0,
                        "tests_passed": 0,
                        "tests_failed": 0,
                        "schema_conflicts": schema_conflicts,
                    },
                    errors=error_messages,
                    cost_usd=0.0,
                )

        # Step 1: Run issue-specific tests
        try:
            exit_code, output = self._run_pytest(test_path)
        except TimeoutError as e:
            error = str(e)
            self._log("verifier_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except OSError as e:
            error = f"Failed to run pytest: {e}"
            self._log("verifier_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except PermissionError as e:
            error = f"Permission denied running pytest: {e}"
            self._log("verifier_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("issue_tests_complete")

        # Parse the issue test output
        parsed = self._parse_pytest_output(output)
        issue_tests_passed = exit_code == 0 and parsed["tests_failed"] == 0

        # Parse detailed failure information for CoderAgent on retry
        issue_failures = self._parse_pytest_failures(output) if not issue_tests_passed else []

        # Build initial result output
        result_output = {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "tests_run": parsed["tests_run"],
            "tests_passed": parsed["tests_passed"],
            "tests_failed": parsed["tests_failed"],
            "test_output": output,
            "duration_seconds": parsed["duration_seconds"],
            "regression_check": None,
            # NEW: Structured failure data for CoderAgent retry
            "failures": issue_failures,
        }

        # Step 2: Run regression check if issue tests passed and enabled
        regression_passed = True
        if issue_tests_passed and check_regressions:
            self._log("verifier_regression_check", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "targeted_regression": regression_test_files is not None,
                "regression_file_count": len(regression_test_files) if regression_test_files else "all",
            })

            try:
                # If specific test files provided (from DONE issues only), use those
                # Empty list means no DONE issues yet - skip regression check
                # None means fall back to running all tests
                regression_skipped = False

                if regression_test_files is not None and len(regression_test_files) == 0:
                    # No DONE issues yet - skip regression check entirely
                    self._log("verifier_regression_skip", {
                        "reason": "No DONE issues to check regression against",
                    })
                    regression_passed = True
                    regression_skipped = True
                    result_output["regression_check"] = {
                        "skipped": True,
                        "reason": "No DONE issues",
                        "passed": True,
                    }
                elif regression_test_files is not None:
                    # Run targeted regression on DONE issues only
                    regression_exit_code, regression_output = self._run_pytest(
                        test_files=[Path(f) for f in regression_test_files]
                    )
                else:
                    # Fall back to running all tests
                    regression_exit_code, regression_output = self._run_pytest(run_all=True)

                # Only parse results if we actually ran tests
                if not regression_skipped:
                    regression_parsed = self._parse_pytest_output(regression_output)
                    regression_passed = regression_exit_code == 0 and regression_parsed["tests_failed"] == 0

                    # Parse regression failures for debugging
                    regression_failures = self._parse_pytest_failures(regression_output) if not regression_passed else []

                    result_output["regression_check"] = {
                        "tests_run": regression_parsed["tests_run"],
                        "tests_passed": regression_parsed["tests_passed"],
                        "tests_failed": regression_parsed["tests_failed"],
                        "duration_seconds": regression_parsed["duration_seconds"],
                        "passed": regression_passed,
                        # NEW: Structured regression failure data
                        "failures": regression_failures,
                    }

                    if not regression_passed:
                        result_output["regression_output"] = regression_output

            except TimeoutError as e:
                self._log("verifier_regression_timeout", {"error": str(e)}, level="warning")
                result_output["regression_check"] = {
                    "error": str(e),
                    "passed": False,
                }
                regression_passed = False
            except (OSError, PermissionError) as e:
                self._log("verifier_regression_error", {"error": str(e)}, level="warning")
                result_output["regression_check"] = {
                    "error": str(e),
                    "passed": False,
                }
                regression_passed = False

            self.checkpoint("regression_check_complete")

        self.checkpoint("tests_complete")

        # Determine overall success
        success = issue_tests_passed and regression_passed

        # Step 3: If failed and analyze_failures enabled, use LLM
        failure_analysis = None
        if not success and analyze_failures:
            # Determine which output to analyze
            if not issue_tests_passed:
                failure_output = output
                is_regression = False
            else:
                # Regression failure
                failure_output = result_output.get("regression_output", "")
                is_regression = True

            failure_analysis = self._analyze_failure_with_llm(
                failure_output, context, is_regression=is_regression
            )
            result_output["failure_analysis"] = failure_analysis

        self._log(
            "verifier_complete",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "success": success,
                "issue_tests_passed": issue_tests_passed,
                "regression_passed": regression_passed,
                "tests_run": parsed["tests_run"],
                "tests_passed": parsed["tests_passed"],
                "tests_failed": parsed["tests_failed"],
                "duration_seconds": parsed["duration_seconds"],
                "has_failure_analysis": failure_analysis is not None,
            },
        )

        if success:
            return AgentResult.success_result(output=result_output, cost_usd=self._total_cost)
        else:
            # Build appropriate error message
            errors = []
            if not issue_tests_passed:
                # Check for collection errors (ImportError, etc.) which indicate implementation issues
                # These occur when tests can't even be collected due to missing imports
                if parsed.get('errors', 0) > 0 and parsed['tests_run'] == 0:
                    # Extract ImportError details if present in output
                    # Use escaped quotes in regex to avoid parsing issues
                    import_error_match = re.search(
                        r"ImportError:\s*cannot import name ['\"]([^'\"]+)['\"]\s+from\s+['\"]([^'\"]+)['\"]",
                        output
                    )
                    module_not_found_match = re.search(
                        r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]",
                        output
                    )
                    if import_error_match:
                        name, module = import_error_match.groups()
                        errors.append(
                            f"Collection error: cannot import '{name}' from '{module}' - "
                            "implementation may be incomplete (missing class/function definition)"
                        )
                    elif module_not_found_match:
                        module = module_not_found_match.group(1)
                        errors.append(
                            f"Collection error: module '{module}' not found - "
                            "implementation file may be missing"
                        )
                    else:
                        errors.append(
                            f"Collection error: {parsed['errors']} error(s) during test collection - "
                            "tests could not run (check for missing imports or syntax errors)"
                        )
                else:
                    errors.append(f"Issue tests failed: {parsed['tests_failed']} failed, {parsed['tests_passed']} passed")
            if not regression_passed and check_regressions:
                regression_info = result_output.get("regression_check", {})
                if "error" in regression_info:
                    errors.append(f"Regression check error: {regression_info['error']}")
                else:
                    errors.append(
                        f"Regression detected: {regression_info.get('tests_failed', 'unknown')} tests failed in full suite"
                    )

            return AgentResult(
                success=False,
                output=result_output,
                errors=errors,
                cost_usd=self._total_cost,
            )
