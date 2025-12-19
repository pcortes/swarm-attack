"""
Root Cause Analyzer Agent for Bug Bash.

This agent analyzes reproduction evidence to identify the root cause
of bugs by tracing execution and forming hypotheses.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.bug_models import RootCauseAnalysis, ValidationError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError

if TYPE_CHECKING:
    from swarm_attack.bug_models import BugReport, ReproductionResult
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class RootCauseAnalyzerAgent(BaseAgent):
    """
    Agent that analyzes bugs to find root cause.

    Takes reproduction evidence and traces execution to identify
    exactly where and why the bug occurs.
    """

    name = "root_cause_analyzer"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Root Cause Analyzer agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("root-cause-analyzer")
        return self._skill_prompt

    def _build_prompt(
        self,
        bug_id: str,
        report: BugReport,
        reproduction: ReproductionResult,
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

        if report.error_message:
            prompt += f"**Reported Error Message:**\n```\n{report.error_message}\n```\n\n"

        prompt += "---\n\n### Reproduction Results\n\n"
        prompt += f"**Confirmed:** {'Yes' if reproduction.confirmed else 'No'}\n"
        prompt += f"**Confidence:** {reproduction.confidence}\n"
        prompt += f"**Attempts:** {reproduction.attempts}\n\n"

        prompt += "**Reproduction Steps:**\n"
        for i, step in enumerate(reproduction.reproduction_steps, 1):
            prompt += f"{i}. {step}\n"
        prompt += "\n"

        if reproduction.affected_files:
            prompt += "**Affected Files:**\n"
            for f in reproduction.affected_files:
                prompt += f"- `{f}`\n"
            prompt += "\n"

        if reproduction.error_message:
            prompt += f"**Error Message:**\n```\n{reproduction.error_message}\n```\n\n"

        if reproduction.stack_trace:
            prompt += f"**Stack Trace:**\n```\n{reproduction.stack_trace}\n```\n\n"

        if reproduction.test_output:
            # Truncate very long test output
            output = reproduction.test_output
            if len(output) > 5000:
                output = output[:5000] + "\n... [truncated] ..."
            prompt += f"**Test Output:**\n```\n{output}\n```\n\n"

        if reproduction.related_code_snippets:
            prompt += "**Code Snippets:**\n\n"
            for path, code in reproduction.related_code_snippets.items():
                prompt += f"**{path}:**\n```python\n{code}\n```\n\n"

        if reproduction.notes:
            prompt += f"**Reproduction Notes:**\n{reproduction.notes}\n\n"

        prompt += """---

## Your Task

1. Trace execution through the call chain
2. Identify exactly where the bug originates (not just where it manifests)
3. Explain why this causes the observed behavior
4. Document why existing tests didn't catch it
5. Output your analysis as JSON in the exact format specified

Remember: This is READ-ONLY analysis - do not execute code.
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
        """Validate the root cause analysis data."""
        errors = []

        if "summary" not in data:
            errors.append("Missing required field: summary")
        elif len(data["summary"]) > 100:
            errors.append(f"summary must be at most 100 characters, got {len(data['summary'])}")

        if "execution_trace" not in data or not data["execution_trace"]:
            errors.append("execution_trace must have at least 1 entry")
        elif len(data["execution_trace"]) < 3:
            errors.append(f"execution_trace must have at least 3 steps, got {len(data['execution_trace'])}")

        if "root_cause_file" not in data or not data["root_cause_file"]:
            errors.append("Missing required field: root_cause_file")

        if "root_cause_code" not in data or not data["root_cause_code"]:
            errors.append("Missing required field: root_cause_code")

        if "root_cause_explanation" not in data or not data["root_cause_explanation"]:
            errors.append("Missing required field: root_cause_explanation")

        if "confidence" not in data:
            errors.append("Missing required field: confidence")
        elif data["confidence"] not in ("high", "medium", "low"):
            errors.append(f"confidence must be high, medium, or low, got: {data['confidence']}")

        return errors

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Execute the root cause analysis workflow.

        Args:
            context: Dictionary containing:
                - bug_id: The bug identifier (required)
                - report: BugReport object (required)
                - reproduction: ReproductionResult object (required)
                - timeout_seconds: Timeout for analysis (optional, default 300)

        Returns:
            AgentResult with:
                - success: True if analysis completed
                - output: RootCauseAnalysis object
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        bug_id = context.get("bug_id")
        report = context.get("report")
        reproduction = context.get("reproduction")

        if not bug_id:
            return AgentResult.failure_result("Missing required context: bug_id")
        if not report:
            return AgentResult.failure_result("Missing required context: report")
        if not reproduction:
            return AgentResult.failure_result("Missing required context: reproduction")

        self._log("root_cause_analyzer_start", {"bug_id": bug_id})
        self.checkpoint("started")

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("root_cause_analyzer_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("skill_loaded")

        # Build prompt and invoke Claude (read-only tools)
        prompt = self._build_prompt(bug_id, report, reproduction)

        try:
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob", "Grep"],  # No Bash - read-only analysis
                max_turns=15,  # Analysis needs exploration time
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("root_cause_analyzer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("root_cause_analyzer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse response
        data = self._extract_json(result.text)
        if data is None:
            error = "Failed to parse JSON from LLM response"
            self._log(
                "root_cause_analyzer_parse_error",
                {"error": error, "response": result.text[:500]},
                level="error",
            )
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate result
        validation_errors = self._validate_result(data)
        if validation_errors:
            error = f"Validation failed: {'; '.join(validation_errors)}"
            self._log("root_cause_analyzer_validation_error", {"errors": validation_errors}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Create RootCauseAnalysis
        try:
            analysis = RootCauseAnalysis(
                summary=data.get("summary", ""),
                execution_trace=data.get("execution_trace", []),
                root_cause_file=data.get("root_cause_file", ""),
                root_cause_line=data.get("root_cause_line"),
                root_cause_code=data.get("root_cause_code", ""),
                root_cause_explanation=data.get("root_cause_explanation", ""),
                why_not_caught=data.get("why_not_caught", ""),
                confidence=data.get("confidence", "medium"),
                alternative_hypotheses=data.get("alternative_hypotheses", []),
            )

            # Validate the analysis object
            model_errors = analysis.validate()
            if model_errors:
                raise ValidationError(f"Model validation failed: {'; '.join(model_errors)}")

        except Exception as e:
            error = f"Failed to create RootCauseAnalysis: {e}"
            self._log("root_cause_analyzer_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("result_created")

        # Success
        self._log(
            "root_cause_analyzer_complete",
            {
                "bug_id": bug_id,
                "root_cause_file": analysis.root_cause_file,
                "confidence": analysis.confidence,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output=analysis,
            cost_usd=cost,
        )
