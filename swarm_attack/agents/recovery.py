"""
Recovery Agent for Feature Swarm.

This agent handles failures that occur during the implementation pipeline.
It analyzes errors, determines if automatic recovery is possible, and either
generates a recovery plan or escalates to human intervention.

The agent integrates with VerifierAgent's failure analysis when available,
avoiding duplicate LLM calls when possible.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.memory.store import MemoryStore
    from swarm_attack.state_store import StateStore


class RecoveryAgent(BaseAgent):
    """
    Agent that analyzes failures and generates recovery plans.

    This agent uses LLM to analyze failure context and determine
    the best path forward - either automatic recovery or human intervention.

    When VerifierAgent's failure analysis is available in the context,
    this agent uses it directly instead of making duplicate LLM calls.
    """

    name = "recovery"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
        memory_store: Optional["MemoryStore"] = None,
    ) -> None:
        """Initialize the Recovery agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._max_retries = config.retry.max_retries
        self._memory_store = memory_store

    def _classify_failure(self, context: dict[str, Any]) -> str:
        """
        Classify the failure type from context.

        Args:
            context: The context dictionary containing failure_type.

        Returns:
            The failure type string.
        """
        return context.get("failure_type", "error")

    def _has_verifier_analysis(self, context: dict[str, Any]) -> bool:
        """
        Check if VerifierAgent already provided analysis.

        Args:
            context: The context dictionary.

        Returns:
            True if valid verifier analysis exists, False otherwise.
        """
        verifier_analysis = context.get("verifier_analysis")
        if not verifier_analysis:
            return False

        # Check for required fields in the analysis
        return "root_cause" in verifier_analysis

    def _parse_llm_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse LLM response for recovery analysis.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Dictionary with parsed analysis or error info.
        """
        # Try to extract JSON from the response
        # Handle cases where LLM wraps JSON in markdown code blocks
        json_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL
        )
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(
                r'\{[^{}]*"root_cause"[^{}]*\}', response_text, re.DOTALL
            )
            if json_match:
                json_str = json_match.group(0)
            else:
                # Try to find any JSON object
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
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
        self, context: dict[str, Any]
    ) -> tuple[dict[str, Any], float]:
        """
        Use LLM to analyze failure and generate recovery plan.

        Args:
            context: The run context with failure details.

        Returns:
            Tuple of (analysis_dict, cost_usd).
        """
        if not self._llm:
            return {"error": "No LLM runner configured for failure analysis"}, 0.0

        try:
            # Load skill prompt
            skill_prompt = self.load_skill("recovery")
        except SkillNotFoundError:
            # Fall back to inline prompt if skill file not found
            skill_prompt = """Analyze this failure and respond with JSON:
{
  "root_cause": "description",
  "recoverable": true/false,
  "recovery_plan": "steps or null",
  "human_instructions": "instructions or null",
  "suggested_actions": [],
  "escalation_reason": "reason or null"
}"""

        # Build analysis prompt with context
        error_output = context.get("error_output", "")
        # Truncate very long error output
        if len(error_output) > 5000:
            error_output = error_output[:5000] + "\n... (truncated)"

        prompt = f"""{skill_prompt}

## Failure Context

**Feature ID**: {context.get('feature_id')}
**Issue Number**: {context.get('issue_number')}
**Failure Type**: {context.get('failure_type')}
**Retry Count**: {context.get('retry_count', 0)}

## Error Output
```
{error_output}
```
"""

        self._log(
            "recovery_analysis_start",
            {
                "feature_id": context.get("feature_id"),
                "issue_number": context.get("issue_number"),
                "failure_type": context.get("failure_type"),
            },
        )

        try:
            # Invoke LLM
            result = self._llm.run(
                prompt=prompt,
                allowed_tools=["Read", "Glob", "Grep"],
            )

            # Parse response
            analysis = self._parse_llm_response(result.text)

            self._log(
                "recovery_analysis_complete",
                {
                    "feature_id": context.get("feature_id"),
                    "issue_number": context.get("issue_number"),
                    "recoverable": analysis.get("recoverable"),
                    "cost_usd": result.total_cost_usd,
                },
            )

            return analysis, result.total_cost_usd

        except Exception as e:
            self._log(
                "recovery_analysis_error",
                {"error": str(e)},
                level="error",
            )
            return {"error": f"LLM analysis failed: {str(e)}"}, 0.0

    def _determine_recoverability(
        self, analysis: dict[str, Any], retry_count: int
    ) -> bool:
        """
        Determine if automatic recovery is possible.

        Args:
            analysis: The analysis result (from verifier or LLM).
            retry_count: How many retries have already been attempted.

        Returns:
            True if recovery is possible, False otherwise.
        """
        # If analysis says not recoverable, respect that
        if not analysis.get("recoverable", False):
            return False

        # Even if recoverable, check retry limits
        # Treat negative retry counts as 0
        actual_retry_count = max(0, retry_count)
        if actual_retry_count >= self._max_retries:
            return False

        return True

    def _generate_recovery_plan(self, analysis: dict[str, Any]) -> Optional[str]:
        """
        Generate steps for automatic retry.

        Args:
            analysis: The analysis result.

        Returns:
            Recovery plan string or None.
        """
        return analysis.get("recovery_plan")

    def _generate_human_instructions(
        self, analysis: dict[str, Any], failure_type: str
    ) -> Optional[str]:
        """
        Generate instructions for human intervention.

        Args:
            analysis: The analysis result.
            failure_type: The type of failure.

        Returns:
            Human instructions string or None.
        """
        return analysis.get("human_instructions")

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Analyze failure and generate recovery plan.

        This method performs the following steps:
        1. Validate context
        2. Check for existing VerifierAgent analysis
        3. If no existing analysis, use LLM to analyze
        4. Determine recoverability based on analysis and retry count
        5. Generate recovery plan or human instructions

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - issue_number: The issue order number (required)
                - failure_type: Type of failure (required)
                - error_output: Error/test output from failed run
                - session_id: Failed session ID
                - checkpoints: Checkpoints from failed session
                - retry_count: How many retries already attempted
                - verifier_analysis: Optional analysis from VerifierAgent

        Returns:
            AgentResult with:
                - success: True if recovery plan generated
                - output: Dict with recovery details
                - cost_usd: LLM cost for analysis (if any)
        """
        # Validate required context fields
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        issue_number = context.get("issue_number")
        if issue_number is None:
            return AgentResult.failure_result("Missing required context: issue_number")

        failure_type = context.get("failure_type")
        if not failure_type:
            return AgentResult.failure_result("Missing required context: failure_type")

        retry_count = context.get("retry_count", 0)
        # Handle negative retry counts
        if retry_count < 0:
            retry_count = 0

        self._log(
            "recovery_start",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "failure_type": failure_type,
                "retry_count": retry_count,
            },
        )
        self.checkpoint("started")

        # Classify the failure
        classified_type = self._classify_failure(context)

        # Check if VerifierAgent already analyzed the failure
        cost_usd = 0.0
        if self._has_verifier_analysis(context):
            # Use existing analysis - don't duplicate LLM work
            verifier_analysis = context["verifier_analysis"]
            analysis = {
                "root_cause": verifier_analysis.get("root_cause", "Unknown"),
                "recoverable": verifier_analysis.get("recoverable", False),
                "recovery_plan": verifier_analysis.get("suggested_fix"),
                "human_instructions": None,
                "suggested_actions": [],
                "escalation_reason": None,
            }

            # Add affected files as suggested actions if available
            affected_files = verifier_analysis.get("affected_files", [])
            if affected_files:
                analysis["suggested_actions"] = [
                    f"Check {f}" for f in affected_files
                ]

            self._log(
                "recovery_using_verifier_analysis",
                {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                },
            )
        else:
            # Need to analyze ourselves using LLM
            analysis, cost_usd = self._analyze_failure_with_llm(context)

            # Check for LLM error
            if "error" in analysis:
                self._log(
                    "recovery_error",
                    {"error": analysis["error"]},
                    level="error",
                )
                return AgentResult(
                    success=False,
                    output={
                        "feature_id": feature_id,
                        "issue_number": issue_number,
                        "error": analysis["error"],
                    },
                    errors=[analysis["error"]],
                    cost_usd=cost_usd,
                )

            # Track cost via checkpoint
            self.checkpoint("analysis_complete", cost_usd=cost_usd)

        # Determine recoverability (considering retry limits)
        recoverable = self._determine_recoverability(analysis, retry_count)

        # Override analysis recoverability if we've exceeded retry limits
        escalation_reason = analysis.get("escalation_reason")
        if analysis.get("recoverable") and not recoverable:
            # We hit max retries
            escalation_reason = f"Maximum retry limit ({self._max_retries}) exceeded"
            analysis["recovery_plan"] = None
            analysis["human_instructions"] = (
                f"The issue has failed {retry_count} times. "
                f"Manual investigation is required.\n\n"
                f"Root cause: {analysis.get('root_cause', 'Unknown')}"
            )

        # Build output
        output = {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "recoverable": recoverable,
            "recovery_plan": analysis.get("recovery_plan") if recoverable else None,
            "human_instructions": (
                analysis.get("human_instructions") if not recoverable else None
            ),
            "suggested_actions": analysis.get("suggested_actions", []),
            "root_cause_analysis": analysis.get("root_cause", "Unknown"),
            "escalation_reason": escalation_reason if not recoverable else None,
        }

        self._log(
            "recovery_complete",
            {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "recoverable": recoverable,
                "cost_usd": cost_usd,
            },
        )

        return AgentResult.success_result(output=output, cost_usd=self._total_cost)
