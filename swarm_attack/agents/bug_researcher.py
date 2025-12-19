"""
Bug Researcher Agent for Bug Bash.

This agent attempts to reproduce bugs and gather evidence for analysis.
It runs tests, captures output, and identifies affected files.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.bug_models import ReproductionResult, ValidationError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError

if TYPE_CHECKING:
    from swarm_attack.bug_models import BugReport
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class BugResearcherAgent(BaseAgent):
    """
    Agent that reproduces bugs and gathers evidence.

    Takes a bug report and attempts to reproduce the bug, capturing
    test output, error messages, stack traces, and affected files.
    """

    name = "bug_researcher"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Bug Researcher agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("bug-researcher")
        return self._skill_prompt

    def _build_prompt(self, bug_id: str, report: BugReport) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        prompt = f"""{skill_prompt}

---

## Bug Report Context

**Bug ID:** {bug_id}

**Description:**
{report.description}

"""

        if report.test_path:
            prompt += f"**Test Path:** `{report.test_path}`\n\n"

        if report.github_issue:
            prompt += f"**GitHub Issue:** #{report.github_issue}\n\n"

        if report.error_message:
            prompt += f"**Error Message:**\n```\n{report.error_message}\n```\n\n"

        if report.stack_trace:
            prompt += f"**Stack Trace:**\n```\n{report.stack_trace}\n```\n\n"

        if report.steps_to_reproduce:
            prompt += "**Steps to Reproduce:**\n"
            for i, step in enumerate(report.steps_to_reproduce, 1):
                prompt += f"{i}. {step}\n"
            prompt += "\n"

        prompt += """---

## Your Task

1. Attempt to reproduce this bug
2. Gather all evidence (test output, errors, stack traces)
3. Identify affected files
4. Collect relevant code snippets
5. Output your findings as JSON in the exact format specified

Remember: Output ONLY valid JSON, no other text.
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
        """Validate the reproduction result data."""
        errors = []

        if "confirmed" not in data:
            errors.append("Missing required field: confirmed")
        if "reproduction_steps" not in data or not data["reproduction_steps"]:
            errors.append("reproduction_steps must have at least 1 entry")
        if "confidence" not in data:
            errors.append("Missing required field: confidence")
        elif data["confidence"] not in ("high", "medium", "low"):
            errors.append(f"confidence must be high, medium, or low, got: {data['confidence']}")
        if "attempts" not in data:
            errors.append("Missing required field: attempts")

        # If confirmed, must have affected_files
        if data.get("confirmed") and not data.get("affected_files"):
            errors.append("affected_files must have at least 1 entry when confirmed")

        return errors

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute the bug reproduction workflow.

        Args:
            context: Dictionary containing:
                - bug_id: The bug identifier (required)
                - report: BugReport object (required)
                - max_attempts: Max reproduction attempts (optional, default 3)
                - timeout_seconds: Timeout for reproduction (optional, default 300)

        Returns:
            AgentResult with:
                - success: True if reproduction attempt completed
                - output: ReproductionResult object
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        bug_id = context.get("bug_id")
        report = context.get("report")

        if not bug_id:
            return AgentResult.failure_result("Missing required context: bug_id")
        if not report:
            return AgentResult.failure_result("Missing required context: report")

        self._log("bug_researcher_start", {"bug_id": bug_id})
        self.checkpoint("started")

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("bug_researcher_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("skill_loaded")

        # Build prompt and invoke Claude
        prompt = self._build_prompt(bug_id, report)

        try:
            # Bug researcher needs many turns to run tests, read files, reproduce bugs
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob", "Grep", "Bash"],
                max_turns=100,  # Complex bugs need extensive exploration
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("bug_researcher_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("bug_researcher_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse response
        data = self._extract_json(result.text)
        if data is None:
            error = "Failed to parse JSON from LLM response"
            self._log(
                "bug_researcher_parse_error",
                {"error": error, "response": result.text[:500]},
                level="error",
            )
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate result
        validation_errors = self._validate_result(data)
        if validation_errors:
            error = f"Validation failed: {'; '.join(validation_errors)}"
            self._log("bug_researcher_validation_error", {"errors": validation_errors}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Create ReproductionResult
        try:
            reproduction = ReproductionResult(
                confirmed=data.get("confirmed", False),
                reproduction_steps=data.get("reproduction_steps", []),
                test_output=data.get("test_output"),
                error_message=data.get("error_message"),
                stack_trace=data.get("stack_trace"),
                affected_files=data.get("affected_files", []),
                related_code_snippets=data.get("related_code_snippets", {}),
                confidence=data.get("confidence", "medium"),
                notes=data.get("notes", ""),
                attempts=data.get("attempts", 1),
                environment=data.get("environment", {}),
            )

            # Validate the reproduction result object
            model_errors = reproduction.validate()
            if model_errors:
                raise ValidationError(f"Model validation failed: {'; '.join(model_errors)}")

        except Exception as e:
            error = f"Failed to create ReproductionResult: {e}"
            self._log("bug_researcher_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("result_created")

        # Success
        self._log(
            "bug_researcher_complete",
            {
                "bug_id": bug_id,
                "confirmed": reproduction.confirmed,
                "confidence": reproduction.confidence,
                "affected_files": len(reproduction.affected_files),
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output=reproduction,
            cost_usd=cost,
        )
