"""
Fix Planner Agent for Bug Bash.

This agent designs fix plans based on root cause analysis,
specifying exact code changes and test cases.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.bug_models import FileChange, FixPlan, TestCase, ValidationError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError

if TYPE_CHECKING:
    from swarm_attack.bug_models import BugReport, ReproductionResult, RootCauseAnalysis
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class FixPlannerAgent(BaseAgent):
    """
    Agent that designs fix plans for bugs.

    Takes root cause analysis and designs specific code changes
    and test cases to fix the bug.
    """

    name = "fix_planner"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
        min_test_cases: int = 2,
    ) -> None:
        """Initialize the Fix Planner agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None
        self._min_test_cases = min_test_cases

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("fix-planner")
        return self._skill_prompt

    def _build_prompt(
        self,
        bug_id: str,
        report: BugReport,
        reproduction: ReproductionResult,
        root_cause: RootCauseAnalysis,
    ) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        prompt = f"""{skill_prompt}

---

## Bug Context

**Bug ID:** {bug_id}

### Original Bug Report

**Description:**
{report.description}

"""

        if report.test_path:
            prompt += f"**Test Path:** `{report.test_path}`\n\n"

        prompt += "---\n\n### Reproduction Summary\n\n"
        prompt += f"**Confirmed:** {'Yes' if reproduction.confirmed else 'No'}\n"
        prompt += f"**Confidence:** {reproduction.confidence}\n\n"

        if reproduction.affected_files:
            prompt += "**Affected Files:**\n"
            for f in reproduction.affected_files:
                prompt += f"- `{f}`\n"
            prompt += "\n"

        if reproduction.error_message:
            prompt += f"**Error Message:**\n```\n{reproduction.error_message}\n```\n\n"

        prompt += "---\n\n### Root Cause Analysis\n\n"
        prompt += f"**Summary:** {root_cause.summary}\n\n"
        prompt += f"**Root Cause File:** `{root_cause.root_cause_file}`\n"
        if root_cause.root_cause_line:
            prompt += f"**Root Cause Line:** {root_cause.root_cause_line}\n"
        prompt += f"**Confidence:** {root_cause.confidence}\n\n"

        prompt += f"**Root Cause Code:**\n```\n{root_cause.root_cause_code}\n```\n\n"
        prompt += f"**Explanation:**\n{root_cause.root_cause_explanation}\n\n"
        prompt += f"**Why Tests Missed It:**\n{root_cause.why_not_caught}\n\n"

        prompt += "**Execution Trace:**\n"
        for i, step in enumerate(root_cause.execution_trace, 1):
            prompt += f"{i}. {step}\n"
        prompt += "\n"

        if root_cause.alternative_hypotheses:
            prompt += "**Alternative Hypotheses Considered:**\n"
            for hyp in root_cause.alternative_hypotheses:
                prompt += f"- {hyp}\n"
            prompt += "\n"

        prompt += f"""---

## Your Task

1. Design the minimal fix that addresses the root cause
2. Specify exact code changes (current code -> proposed code)
3. Create at least {self._min_test_cases} test cases to verify the fix
4. Assess risk and provide a rollback plan
5. Output your fix plan as JSON in the exact format specified

Remember: This is READ-ONLY planning - do not write any files.
Output ONLY valid JSON, no other text.
"""

        return prompt

    def _extract_json(self, text: str) -> Optional[dict]:
        """
        Extract JSON from LLM response.

        Handles cases where JSON is wrapped in markdown code blocks.
        """
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract from code block
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            try:
                return json.loads(text[brace_start : brace_end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _validate_result(self, data: dict) -> list[str]:
        """Validate the fix plan data."""
        errors = []

        if "summary" not in data or not data["summary"]:
            errors.append("Missing required field: summary")

        if "changes" not in data or not data["changes"]:
            errors.append("changes must have at least 1 entry")

        if "test_cases" not in data or not data["test_cases"]:
            errors.append("test_cases must have at least 1 entry")
        elif len(data["test_cases"]) < self._min_test_cases:
            errors.append(f"test_cases must have at least {self._min_test_cases} entries, got {len(data['test_cases'])}")

        if "risk_level" not in data:
            errors.append("Missing required field: risk_level")
        elif data["risk_level"] not in ("low", "medium", "high"):
            errors.append(f"risk_level must be low, medium, or high, got: {data['risk_level']}")

        if "rollback_plan" not in data or not data["rollback_plan"]:
            errors.append("Missing required field: rollback_plan")

        # Validate changes
        for i, change in enumerate(data.get("changes", [])):
            if "file_path" not in change or not change["file_path"]:
                errors.append(f"changes[{i}]: file_path is required")
            if "change_type" not in change:
                errors.append(f"changes[{i}]: change_type is required")
            elif change["change_type"] not in ("modify", "create", "delete"):
                errors.append(f"changes[{i}]: change_type must be modify, create, or delete")

            if change.get("change_type") == "modify" and not change.get("current_code"):
                errors.append(f"changes[{i}]: current_code is required for modify changes")
            if change.get("change_type") in ("modify", "create") and not change.get("proposed_code"):
                errors.append(f"changes[{i}]: proposed_code is required for modify and create changes")

        # Validate test cases
        for i, test in enumerate(data.get("test_cases", [])):
            if "name" not in test or not test["name"]:
                errors.append(f"test_cases[{i}]: name is required")
            if "description" not in test or not test["description"]:
                errors.append(f"test_cases[{i}]: description is required")
            if "test_code" not in test or not test["test_code"]:
                errors.append(f"test_cases[{i}]: test_code is required")

        return errors

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute the fix planning workflow.

        Args:
            context: Dictionary containing:
                - bug_id: The bug identifier (required)
                - report: BugReport object (required)
                - reproduction: ReproductionResult object (required)
                - root_cause: RootCauseAnalysis object (required)
                - timeout_seconds: Timeout for planning (optional, default 300)

        Returns:
            AgentResult with:
                - success: True if planning completed
                - output: FixPlan object
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        bug_id = context.get("bug_id")
        report = context.get("report")
        reproduction = context.get("reproduction")
        root_cause = context.get("root_cause")

        if not bug_id:
            return AgentResult.failure_result("Missing required context: bug_id")
        if not report:
            return AgentResult.failure_result("Missing required context: report")
        if not reproduction:
            return AgentResult.failure_result("Missing required context: reproduction")
        if not root_cause:
            return AgentResult.failure_result("Missing required context: root_cause")

        self._log("fix_planner_start", {"bug_id": bug_id})
        self.checkpoint("started")

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("fix_planner_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("skill_loaded")

        # Build prompt and invoke Claude (read-only tools)
        prompt = self._build_prompt(bug_id, report, reproduction, root_cause)

        try:
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob", "Grep"],  # No Bash - read-only planning
                max_turns=15,  # Planning needs exploration time
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("fix_planner_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("fix_planner_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse response
        data = self._extract_json(result.text)
        if data is None:
            error = "Failed to parse JSON from LLM response"
            self._log(
                "fix_planner_parse_error",
                {"error": error, "response": result.text[:500]},
                level="error",
            )
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate result
        validation_errors = self._validate_result(data)
        if validation_errors:
            error = f"Validation failed: {'; '.join(validation_errors)}"
            self._log("fix_planner_validation_error", {"errors": validation_errors}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Create FixPlan
        try:
            changes = [
                FileChange(
                    file_path=c.get("file_path", ""),
                    change_type=c.get("change_type", "modify"),
                    current_code=c.get("current_code"),
                    proposed_code=c.get("proposed_code"),
                    explanation=c.get("explanation", ""),
                )
                for c in data.get("changes", [])
            ]

            test_cases = [
                TestCase(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    test_code=t.get("test_code", ""),
                    category=t.get("category", "regression"),
                )
                for t in data.get("test_cases", [])
            ]

            fix_plan = FixPlan(
                summary=data.get("summary", ""),
                changes=changes,
                test_cases=test_cases,
                risk_level=data.get("risk_level", "low"),
                risk_explanation=data.get("risk_explanation", ""),
                scope=data.get("scope", ""),
                side_effects=data.get("side_effects", []),
                rollback_plan=data.get("rollback_plan", ""),
                estimated_effort=data.get("estimated_effort", ""),
            )

            # Validate the fix plan object
            model_errors = fix_plan.validate(min_test_cases=self._min_test_cases)
            if model_errors:
                raise ValidationError(f"Model validation failed: {'; '.join(model_errors)}")

        except Exception as e:
            error = f"Failed to create FixPlan: {e}"
            self._log("fix_planner_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("result_created")

        # Success
        self._log(
            "fix_planner_complete",
            {
                "bug_id": bug_id,
                "changes_count": len(fix_plan.changes),
                "test_cases_count": len(fix_plan.test_cases),
                "risk_level": fix_plan.risk_level,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output=fix_plan,
            cost_usd=cost,
        )
