"""
Issue Validator Agent for Feature Swarm.

This agent validates generated GitHub issues for completeness,
dependency correctness, and implementability.

IMPORTANT: Uses Codex CLI for implementability validation (independent review),
while structural/dependency validation is done locally without LLM.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.codex_client import (
    CodexCliRunner,
    CodexInvocationError,
    CodexTimeoutError,
)
from swarm_attack.errors import LLMError, get_user_action_message
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class IssueValidatorAgent(BaseAgent):
    """
    Agent that validates generated GitHub issues.

    Uses Codex CLI (not Claude) for implementability validation to avoid self-review.

    Performs validation on issues.json from specs/<feature>/:
    - Structural validation (required fields) - done locally
    - Dependency validation (no cycles, valid references) - done locally
    - Implementability validation (via Codex) - independent review

    Outputs validation report to specs/<feature>/issues-validation.json.
    """

    name = "issue_validator"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        codex_runner: Optional[CodexCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the Issue Validator agent.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            codex_runner: Optional Codex runner (created if not provided).
            state_store: Optional state store for persistence.
        """
        # Pass None for llm_runner since we use Codex
        super().__init__(config, logger, None, state_store)
        self._codex = codex_runner
        self._skill_prompt: Optional[str] = None

    @property
    def codex(self) -> CodexCliRunner:
        """Get the Codex runner (lazy initialization)."""
        if self._codex is None:
            self._codex = CodexCliRunner(
                config=self.config,
                logger=self.logger,
                checkpoint_callback=lambda: self.checkpoint("pre_codex_call"),
            )
        return self._codex

    def _get_issues_path(self, feature_id: str) -> Path:
        """Get the path to the issues.json file."""
        return self.config.specs_path / feature_id / "issues.json"

    def _get_validation_path(self, feature_id: str) -> Path:
        """Get the path to the output validation report."""
        return self.config.specs_path / feature_id / "issues-validation.json"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("issue-validator")
        return self._skill_prompt

    def _validate_structure(self, issues_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Validate structural requirements of issues.

        Returns list of problems found (empty if valid).
        """
        problems = []
        required_fields = ["title", "body", "labels", "estimated_size", "dependencies", "order"]

        if "issues" not in issues_data:
            problems.append({
                "issue_order": 0,
                "severity": "error",
                "type": "missing_issues_array",
                "description": "issues.json missing 'issues' array",
            })
            return problems

        issues = issues_data.get("issues", [])
        if not isinstance(issues, list):
            problems.append({
                "issue_order": 0,
                "severity": "error",
                "type": "invalid_issues_type",
                "description": "'issues' must be an array",
            })
            return problems

        for issue in issues:
            order = issue.get("order", "?")
            for field in required_fields:
                if field not in issue:
                    problems.append({
                        "issue_order": order,
                        "severity": "error",
                        "type": "missing_required_field",
                        "description": f"Issue {order} missing required field: {field}",
                    })

        return problems

    def _validate_dependencies(self, issues_data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Validate dependency relationships between issues.

        Checks for:
        - References to non-existent issues
        - Self-references
        - Circular dependencies

        Returns list of problems found.
        """
        problems = []
        issues = issues_data.get("issues", [])

        # Build order -> issue mapping
        order_to_issue = {issue.get("order"): issue for issue in issues}
        valid_orders = set(order_to_issue.keys())

        # Check each issue's dependencies
        for issue in issues:
            order = issue.get("order", 0)
            deps = issue.get("dependencies", [])

            for dep in deps:
                # Check for self-reference
                if dep == order:
                    problems.append({
                        "issue_order": order,
                        "severity": "error",
                        "type": "self_dependency",
                        "description": f"Issue {order} has a circular dependency on itself",
                    })
                # Check for missing dependency
                elif dep not in valid_orders:
                    problems.append({
                        "issue_order": order,
                        "severity": "error",
                        "type": "missing_dependency",
                        "description": f"Issue {order} references dependency {dep} which doesn't exist",
                    })

        # Check for cycles using DFS
        cycle_problems = self._detect_cycles(issues)
        problems.extend(cycle_problems)

        return problems

    def _detect_cycles(self, issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect circular dependencies using depth-first search.

        Returns list of cycle problems found.
        """
        problems = []

        # Build adjacency list
        graph: dict[int, list[int]] = defaultdict(list)
        for issue in issues:
            order = issue.get("order", 0)
            deps = issue.get("dependencies", [])
            # Dependencies point TO this issue, so the edge is dep -> order
            # But for cycle detection, we want to find if following deps leads back
            # So we store order -> deps (what this issue depends on)
            for dep in deps:
                graph[order].append(dep)

        visited: set[int] = set()
        rec_stack: set[int] = set()

        def dfs(node: int, path: list[int]) -> Optional[list[int]]:
            """Returns cycle path if found, None otherwise."""
            if node in rec_stack:
                # Found cycle
                return path + [node]
            if node in visited:
                return None

            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                cycle = dfs(neighbor, path + [node])
                if cycle:
                    return cycle

            rec_stack.remove(node)
            return None

        # Check for cycles starting from each node
        for issue in issues:
            order = issue.get("order", 0)
            if order not in visited:
                cycle = dfs(order, [])
                if cycle:
                    # Extract just the cycle portion
                    cycle_start = cycle[-1]
                    cycle_start_idx = cycle.index(cycle_start)
                    actual_cycle = cycle[cycle_start_idx:]

                    problems.append({
                        "issue_order": actual_cycle[0],
                        "severity": "error",
                        "type": "dependency_cycle",
                        "description": f"Circular dependency detected: {' -> '.join(map(str, actual_cycle))}",
                    })
                    # Only report one cycle
                    break

        return problems

    def _build_prompt(self, feature_id: str, issues: list[dict[str, Any]]) -> str:
        """Build the full prompt for GPT-5 to validate issues."""
        skill_prompt = self._load_skill_prompt()

        issues_json = json.dumps(issues, indent=2)

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}

**Issues to Validate:**

```json
{issues_json}
```

---

## Your Task

Review each issue for implementability and completeness.

Return ONLY valid JSON (no markdown code fence) with this structure:

{{
  "issues_reviewed": [
    {{
      "order": 1,
      "implementable": true,
      "issues": []
    }},
    {{
      "order": 2,
      "implementable": false,
      "issues": [
        {{
          "severity": "warning",
          "type": "vague_acceptance_criteria",
          "description": "Acceptance criteria could be more specific about..."
        }}
      ]
    }}
  ],
  "overall_assessment": "Brief summary of validation results"
}}

Severity levels: "error" (blocks implementation), "warning" (should fix)
Issue types: "vague_acceptance_criteria", "missing_context", "too_large", "unclear_scope", "missing_error_handling"
"""

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """
        Parse JSON from LLM response.

        Handles responses that may be wrapped in markdown code fences.
        """
        # Try to extract JSON from code fence
        code_fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(code_fence_pattern, text)
        if match:
            json_str = match.group(1)
        else:
            json_str = text.strip()

        return json.loads(json_str)

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Validate generated GitHub issues.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)

        Returns:
            AgentResult with:
                - success: True if validation completed (not necessarily passed)
                - output: Dict with valid, validation_path, problems, summary, passed, failed
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        self._log("issue_validator_start", {"feature_id": feature_id})
        self.checkpoint("started")

        # Check if issues.json exists
        issues_path = self._get_issues_path(feature_id)
        if not file_exists(issues_path):
            error = f"Issues not found at {issues_path}"
            self._log("issue_validator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Read issues.json
        try:
            issues_content = read_file(issues_path)
            issues_data = json.loads(issues_content)
        except json.JSONDecodeError as e:
            error = f"Failed to parse issues.json: {e}"
            self._log("issue_validator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except Exception as e:
            error = f"Failed to read issues.json: {e}"
            self._log("issue_validator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("issues_loaded")

        # Collect all problems
        all_problems: list[dict[str, Any]] = []

        # Step 1: Structural validation
        structural_problems = self._validate_structure(issues_data)
        all_problems.extend(structural_problems)

        # Step 2: Dependency validation (only if structural validation passed basic checks)
        issues = issues_data.get("issues", [])
        if issues and isinstance(issues, list):
            dep_problems = self._validate_dependencies(issues_data)
            all_problems.extend(dep_problems)

        # If there are structural or dependency errors, skip LLM validation
        has_errors = any(p["severity"] == "error" for p in all_problems)

        cost = 0.0
        llm_problems: list[dict[str, Any]] = []

        if not has_errors and issues:
            # Step 3: Codex-based validation for implementability
            try:
                self._load_skill_prompt()
            except SkillNotFoundError as e:
                self._log("issue_validator_error", {"error": str(e)}, level="error")
                return AgentResult.failure_result(str(e))

            prompt = self._build_prompt(feature_id, issues)

            try:
                result = self.codex.run(prompt)
                cost = 0.0  # Codex uses flat-rate subscription

                # Parse LLM response
                try:
                    llm_result = self._parse_json_response(result.text)

                    # Extract problems from LLM response
                    for reviewed in llm_result.get("issues_reviewed", []):
                        for issue in reviewed.get("issues", []):
                            llm_problems.append({
                                "issue_order": reviewed.get("order", 0),
                                "severity": issue.get("severity", "warning"),
                                "type": issue.get("type", "unknown"),
                                "description": issue.get("description", ""),
                            })

                except json.JSONDecodeError:
                    # If LLM response isn't valid JSON, just note it but continue
                    self._log(
                        "issue_validator_warning",
                        {"warning": "Could not parse Codex validation response"},
                        level="warning"
                    )

            except CodexTimeoutError as e:
                error = f"Codex timed out: {e}"
                self._log("issue_validator_error", {"error": error}, level="error")
                return AgentResult.failure_result(error)
            except LLMError as e:
                # Handle auth and other errors gracefully
                if e.requires_user_action:
                    error_msg = get_user_action_message(e)
                    self._log("issue_validator_auth_error", {"error": str(e)}, level="error")
                    print(error_msg)  # Show user the action message
                error = f"Codex error: {e}"
                self._log("issue_validator_error", {"error": error}, level="error")
                return AgentResult.failure_result(error)
            except CodexInvocationError as e:
                error = f"Codex invocation error: {e}"
                self._log("issue_validator_error", {"error": error}, level="error")
                return AgentResult.failure_result(error)

        self.checkpoint("validation_complete", cost_usd=cost)

        # Combine all problems
        all_problems.extend(llm_problems)

        # Calculate pass/fail counts
        issues_checked = len(issues) if isinstance(issues, list) else 0
        failed_orders = set(p["issue_order"] for p in all_problems if p["severity"] == "error")
        passed_count = issues_checked - len(failed_orders)
        failed_count = len(failed_orders)

        # Determine overall validity
        is_valid = len(all_problems) == 0

        # Generate summary
        if is_valid:
            summary = f"All {issues_checked} issues passed validation"
        else:
            error_count = sum(1 for p in all_problems if p["severity"] == "error")
            warning_count = sum(1 for p in all_problems if p["severity"] == "warning")
            summary = f"Found {error_count} errors and {warning_count} warnings across {issues_checked} issues"

        # Build validation report
        validation_report = {
            "feature_id": feature_id,
            "validated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "valid": is_valid,
            "summary": summary,
            "problems": all_problems,
            "issues_checked": issues_checked,
            "passed": passed_count,
            "failed": failed_count,
        }

        # Write validation report
        validation_path = self._get_validation_path(feature_id)
        try:
            ensure_dir(validation_path.parent)
            safe_write(validation_path, json.dumps(validation_report, indent=2))
        except Exception as e:
            error = f"Failed to write validation report: {e}"
            self._log("issue_validator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("report_written", cost_usd=0)

        # Success
        self._log(
            "issue_validator_complete",
            {
                "feature_id": feature_id,
                "valid": is_valid,
                "issues_checked": issues_checked,
                "problems_found": len(all_problems),
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output={
                "valid": is_valid,
                "validation_path": str(validation_path),
                "problems": all_problems,
                "summary": summary,
                "issues_checked": issues_checked,
                "passed": passed_count,
                "failed": failed_count,
            },
            cost_usd=cost,
        )
