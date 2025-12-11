"""
Test Writer Agent for Feature Swarm.

This agent generates unit tests for a specific issue using the Claude CLI.
It reads the issue content and spec context, then generates comprehensive
test code that covers all acceptance criteria.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class TestWriterAgent(BaseAgent):
    """
    Agent that generates unit tests for a specific issue.

    Reads an issue from issues.json and the spec-final.md, then uses Claude
    to generate comprehensive tests covering the acceptance criteria.
    """

    name = "test_writer"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Test Writer agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def _get_spec_path(self, feature_id: str) -> Path:
        """Get the path to the spec-final.md file."""
        return self.config.specs_path / feature_id / "spec-final.md"

    def _get_issues_path(self, feature_id: str) -> Path:
        """Get the path to the issues.json file."""
        return self.config.specs_path / feature_id / "issues.json"

    def _get_default_test_path(self, feature_id: str, issue_number: int) -> Path:
        """Get the default path for generated tests."""
        tests_dir = Path(self.config.repo_root) / "tests" / "generated" / feature_id
        return tests_dir / f"test_issue_{issue_number}.py"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("test-writer")
        return self._skill_prompt

    def _load_issues(self, feature_id: str) -> dict[str, Any]:
        """Load the issues.json file for a feature."""
        issues_path = self._get_issues_path(feature_id)
        if not file_exists(issues_path):
            raise FileNotFoundError(f"Issues file not found at {issues_path}")

        content = read_file(issues_path)
        return json.loads(content)

    def _find_issue(
        self, issues_data: dict[str, Any], issue_number: int
    ) -> Optional[dict[str, Any]]:
        """Find a specific issue by its order number."""
        issues = issues_data.get("issues", [])
        for issue in issues:
            if issue.get("order") == issue_number:
                return issue
        return None

    def _build_prompt(
        self,
        feature_id: str,
        issue: dict[str, Any],
        spec_content: str,
    ) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}

**Issue to Write Tests For:**

Title: {issue.get('title', 'Unknown')}

{issue.get('body', 'No description')}

**Labels:** {', '.join(issue.get('labels', []))}
**Estimated Size:** {issue.get('estimated_size', 'medium')}

**Engineering Spec Context:**

```markdown
{spec_content}
```

---

## Your Task

Generate comprehensive unit tests for the issue above.

CRITICAL TDD RULES - MUST FOLLOW:
1. Tests MUST use Path.cwd() to check real project files, NOT tmp_path
2. Tests MUST FAIL initially before the Coder implements the code
3. DO NOT create fixtures that write files then assert they exist - that's self-mocking
4. Import from real module paths (lib.*, src.*) that the Coder will create

Requirements:
1. Write pytest-style test code
2. Cover all acceptance criteria from the issue body
3. Include positive and negative test cases
4. Use descriptive test function names
5. Add docstrings explaining what each test verifies
6. Use Path.cwd() for file existence checks, NOT tmp_path
7. Structure tests logically (can use test classes if appropriate)

Output ONLY the Python test code. Do not include explanations outside of code comments.
If you need to explain anything, do so in docstrings or comments within the code.
"""

    def _extract_code(self, text: str) -> str:
        """
        Extract Python code from LLM response.

        Handles both plain code and code wrapped in markdown fences.
        """
        # Try to extract code from markdown code fences
        code_fence_pattern = r"```(?:python)?\s*([\s\S]*?)\s*```"
        matches = re.findall(code_fence_pattern, text)

        if matches:
            # Combine all code blocks
            return "\n\n".join(matches)

        # If no code fences, assume the entire response is code
        return text.strip()

    def _count_tests(self, code: str) -> int:
        """Count the number of test functions in the generated code."""
        # Match both standalone test functions and test methods in classes
        # Pattern: def test_something( or async def test_something(
        pattern = r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\("
        matches = re.findall(pattern, code, re.MULTILINE)
        return len(matches)

    def _validate_tests_for_self_mocking(self, code: str) -> list[str]:
        """
        Validate generated tests for self-mocking anti-patterns.

        Self-mocking tests create their own fixtures (e.g., write files to tmp_path)
        and then assert those fixtures exist. These tests always pass and break TDD.

        Returns list of warnings found.
        """
        warnings = []
        lines = code.split('\n')

        # Track if we see tmp_path usage combined with write operations and existence checks
        has_tmp_path = "tmp_path" in code
        has_write_text = ".write_text(" in code
        has_mkdir = ".mkdir(" in code
        has_exists_check = ".exists()" in code or ".is_dir()" in code or ".is_file()" in code

        # Pattern 1: tmp_path + write_text/mkdir + exists assertion = self-mocking
        if has_tmp_path and (has_write_text or has_mkdir) and has_exists_check:
            warnings.append(
                "SELF-MOCKING DETECTED: Tests use tmp_path to create files/directories, "
                "then assert they exist. This always passes and breaks TDD. "
                "Tests should check REAL project paths using Path.cwd(), not tmp_path fixtures."
            )

        # Pattern 2: Check for missing real path usage
        # Good tests should use Path.cwd() to check real project files
        has_path_cwd = "Path.cwd()" in code or "Path(__file__)" in code
        has_real_imports = (
            "from lib." in code or
            "from src." in code or
            "import lib." in code or
            "import src." in code
        )

        # If no real paths and no real imports, tests might not be testing implementation
        if not has_path_cwd and not has_real_imports:
            # Check if tests are purely unit tests on passed-in data (which is OK)
            # vs tests that should be checking file existence (which need Path.cwd())
            file_check_indicators = [
                "exists()", "is_dir()", "is_file()",
                "pubspec", "main.dart", ".yaml", ".dart"
            ]
            if any(indicator in code for indicator in file_check_indicators):
                warnings.append(
                    "NO REAL PATH USAGE: Tests check file existence but don't use Path.cwd() "
                    "or import from real module paths. Tests should verify files exist at "
                    "actual project locations, not in temporary fixtures."
                )

        # Pattern 3: Count ratio of tmp_path methods vs test methods
        # High tmp_path usage is a red flag
        tmp_path_def_count = len(re.findall(r'def\s+test_\w+\s*\([^)]*tmp_path', code))
        total_test_count = self._count_tests(code)

        if total_test_count > 0 and tmp_path_def_count > 0:
            tmp_path_ratio = tmp_path_def_count / total_test_count
            if tmp_path_ratio > 0.5:
                warnings.append(
                    f"HIGH tmp_path USAGE: {tmp_path_def_count}/{total_test_count} tests "
                    f"({tmp_path_ratio:.0%}) use tmp_path fixtures. For TDD to work, tests "
                    "should fail initially by checking real implementation paths, not temp fixtures."
                )

        return warnings

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Generate unit tests for a specific issue.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - issue_number: The issue order number (required)
                - test_path: Optional custom path for test file

        Returns:
            AgentResult with:
                - success: True if tests were generated
                - output: Dict with test_path, tests_generated, etc.
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        issue_number = context.get("issue_number")
        if issue_number is None:
            return AgentResult.failure_result("Missing required context: issue_number")

        self._log("test_writer_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })
        self.checkpoint("started")

        # Check if spec exists
        spec_path = self._get_spec_path(feature_id)
        if not file_exists(spec_path):
            error = f"Spec not found at {spec_path}"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Read spec content
        try:
            spec_content = read_file(spec_path)
        except Exception as e:
            error = f"Failed to read spec: {e}"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Load issues
        try:
            issues_data = self._load_issues(feature_id)
        except FileNotFoundError as e:
            error = str(e)
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except json.JSONDecodeError as e:
            error = f"Failed to parse issues.json: {e}"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Find the specific issue
        issue = self._find_issue(issues_data, issue_number)
        if not issue:
            error = f"Issue {issue_number} not found in issues.json"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("context_loaded")

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("test_writer_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        # Build prompt and invoke Claude
        prompt = self._build_prompt(feature_id, issue, spec_content)

        try:
            result = self.llm.run(
                prompt,
                allowed_tools=[],  # No tools - all context is in prompt, just generate code
                max_turns=1,  # Single turn - output code directly
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Extract test code from response
        test_code = self._extract_code(result.text)

        # Validate that we got actual test code (Fix 6B)
        if not test_code.strip():
            error = "Claude did not output test code. Response may have been empty or consumed by tool use."
            self._log("test_writer_error", {"error": error, "result_text_len": len(result.text)}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        tests_generated = self._count_tests(test_code)

        if tests_generated == 0:
            error = f"No test functions found in generated code ({len(test_code)} chars). Expected 'def test_*' functions."
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate tests for self-mocking anti-patterns (Bug 7 fix)
        validation_warnings = self._validate_tests_for_self_mocking(test_code)
        if validation_warnings:
            self._log("test_writer_warnings", {
                "warnings": validation_warnings,
                "tests_generated": tests_generated,
            }, level="warning")

            # Check if self-mocking is severe (more than 50% of tests use tmp_path)
            # In that case, fail and force regeneration
            self_mock_detected = any("SELF-MOCKING DETECTED" in w for w in validation_warnings)
            high_tmp_path = any("HIGH tmp_path USAGE" in w for w in validation_warnings)

            if self_mock_detected or high_tmp_path:
                error = (
                    "Tests appear to be self-mocking (creating fixtures then asserting they exist). "
                    "This breaks TDD - tests must FAIL initially until Coder implements the code. "
                    f"Warnings: {'; '.join(validation_warnings)}"
                )
                self._log("test_writer_error", {"error": error}, level="error")
                return AgentResult.failure_result(error, cost_usd=cost)

        # Determine test file path
        test_path_str = context.get("test_path")
        if test_path_str:
            test_path = Path(test_path_str)
        else:
            test_path = self._get_default_test_path(feature_id, issue_number)

        # Write test file
        try:
            ensure_dir(test_path.parent)
            safe_write(test_path, test_code)
        except Exception as e:
            error = f"Failed to write test file: {e}"
            self._log("test_writer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("tests_written", cost_usd=0)

        # Success
        self._log(
            "test_writer_complete",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "test_path": str(test_path),
                "tests_generated": tests_generated,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output={
                "feature_id": feature_id,
                "issue_number": issue_number,
                "test_path": str(test_path),
                "tests_generated": tests_generated,
                "issue_title": issue.get("title", ""),
            },
            cost_usd=cost,
        )
