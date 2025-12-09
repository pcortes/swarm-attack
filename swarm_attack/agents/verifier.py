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
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.utils.fs import file_exists

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
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
    ) -> None:
        """Initialize the Verifier agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._test_timeout = config.tests.timeout_seconds

    def _get_default_test_path(self, feature_id: str, issue_number: int) -> Path:
        """Get the default path for generated tests."""
        tests_dir = Path(self.config.repo_root) / "tests" / "generated" / feature_id
        return tests_dir / f"test_issue_{issue_number}.py"

    def _run_pytest(
        self,
        test_path: Optional[Path] = None,
        timeout: Optional[int] = None,
        run_all: bool = False,
    ) -> tuple[int, str]:
        """
        Run pytest on the specified test file or full test suite.

        Args:
            test_path: Path to the test file to run. Ignored if run_all=True.
            timeout: Optional timeout in seconds.
            run_all: If True, run full test suite for regression detection.

        Returns:
            Tuple of (exit_code, combined_output).

        Raises:
            TimeoutError: If pytest times out.
            OSError: If pytest cannot be executed.
        """
        timeout = timeout or self._test_timeout

        # Build pytest command
        if run_all:
            # Run full test suite for regression detection
            cmd = ["pytest", "-v", "--tb=short", "-q"]
        else:
            # Run specific test file
            cmd = ["pytest", str(test_path), "-v", "--tb=short"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.config.repo_root,
            )

            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr

            return result.returncode, output

        except subprocess.TimeoutExpired as e:
            raise TimeoutError(f"Test timed out after {timeout} seconds") from e

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
        }

        # Step 2: Run regression check if issue tests passed and enabled
        regression_passed = True
        if issue_tests_passed and check_regressions:
            self._log("verifier_regression_check", {
                "feature_id": feature_id,
                "issue_number": issue_number,
            })

            try:
                regression_exit_code, regression_output = self._run_pytest(run_all=True)
                regression_parsed = self._parse_pytest_output(regression_output)
                regression_passed = regression_exit_code == 0 and regression_parsed["tests_failed"] == 0

                result_output["regression_check"] = {
                    "tests_run": regression_parsed["tests_run"],
                    "tests_passed": regression_parsed["tests_passed"],
                    "tests_failed": regression_parsed["tests_failed"],
                    "duration_seconds": regression_parsed["duration_seconds"],
                    "passed": regression_passed,
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
