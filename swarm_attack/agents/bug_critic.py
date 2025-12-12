"""
Bug Critic Agent for Bug Bash pipeline.

This agent reviews root cause analysis and fix plans, scoring them against
quality rubrics and identifying issues that need to be addressed.

IMPORTANT: Uses Codex CLI for independent review (not Claude), to avoid
Claude reviewing its own work. Stops and tells user to login if Codex
authentication fails.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.codex_client import (
    CodexCliRunner,
    CodexInvocationError,
    CodexTimeoutError,
)
from swarm_attack.errors import CodexAuthError, LLMError, get_user_action_message

if TYPE_CHECKING:
    from swarm_attack.bug_models import FixPlan, RootCauseAnalysis
    from swarm_attack.config import SwarmConfig
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class BugCriticAgent(BaseAgent):
    """
    Agent that reviews root cause analysis and fix plans.

    Uses Codex CLI (not Claude) for independent review to avoid self-review bias.
    Operates in two modes:
    - "root_cause": Reviews root cause analysis
    - "fix_plan": Reviews fix plan

    If Codex authentication fails, stops immediately and tells user to run
    `codex login`.
    """

    name = "bug_critic"

    # 10 minute timeout per debate round for thorough analysis
    DEBATE_TIMEOUT_SECONDS = 600

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        codex_runner: Optional[CodexCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the Bug Critic agent.

        Args:
            config: SwarmConfig with paths and settings.
            logger: Optional logger for recording operations.
            codex_runner: Optional Codex runner (created if not provided).
            state_store: Optional state store for persistence.
        """
        # Pass None for llm_runner since we use Codex
        super().__init__(config, logger, None, state_store)
        self._codex = codex_runner
        self._skill_prompts: dict[str, str] = {}

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

    def _load_skill_prompt(self, mode: Literal["root_cause", "fix_plan"]) -> str:
        """Load and cache the skill prompt for the given mode."""
        skill_name = f"bug-{mode.replace('_', '-')}-critic"
        if skill_name not in self._skill_prompts:
            self._skill_prompts[skill_name] = self.load_skill(skill_name)
        return self._skill_prompts[skill_name]

    def _build_root_cause_prompt(
        self,
        bug_id: str,
        root_cause: RootCauseAnalysis,
        bug_description: str,
        reproduction_summary: str,
    ) -> str:
        """Build the prompt for root cause analysis review."""
        skill_prompt = self._load_skill_prompt("root_cause")

        return f"""{skill_prompt}

---

## Context for This Task

**Bug ID:** {bug_id}

**Bug Description:**
{bug_description}

**Reproduction Summary:**
{reproduction_summary}

**Root Cause Analysis to Review:**

```json
{json.dumps(root_cause.to_dict(), indent=2)}
```

---

## Your Task

Review the root cause analysis thoroughly. Take your time - this is critical.
Score each dimension from 0.0 to 1.0:
- evidence_quality: Is there concrete evidence supporting the hypothesis?
- hypothesis_correctness: Does the identified cause actually explain the bug?
- completeness: Are all aspects of the bug explained?
- alternative_consideration: Were other hypotheses considered and ruled out?

Identify all issues with severity (critical, moderate, minor).
Output ONLY valid JSON matching the schema in the skill instructions.
Do not include any markdown code fences or explanatory text - just the raw JSON.
"""

    def _build_fix_plan_prompt(
        self,
        bug_id: str,
        fix_plan: FixPlan,
        root_cause_summary: str,
        bug_description: str,
    ) -> str:
        """Build the prompt for fix plan review."""
        skill_prompt = self._load_skill_prompt("fix_plan")

        return f"""{skill_prompt}

---

## Context for This Task

**Bug ID:** {bug_id}

**Bug Description:**
{bug_description}

**Root Cause Summary:**
{root_cause_summary}

**Fix Plan to Review:**

```json
{json.dumps(fix_plan.to_dict(), indent=2)}
```

---

## Your Task

Review the fix plan thoroughly. Take your time - this is critical.
Score each dimension from 0.0 to 1.0:
- correctness: Will the fix actually solve the bug?
- completeness: Are all necessary changes included?
- risk_assessment: Is the risk level accurate?
- test_coverage: Do test cases cover the fix adequately?
- side_effect_analysis: Are potential side effects identified?

Identify all issues with severity (critical, moderate, minor).
Output ONLY valid JSON matching the schema in the skill instructions.
Do not include any markdown code fences or explanatory text - just the raw JSON.
"""

    def _parse_review_json(self, text: str) -> dict[str, Any]:
        """
        Parse the review JSON from Codex's response.

        Handles cases where the response may contain markdown code fences.
        """
        import re

        # Try to parse as-is first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code fence
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")

    def _validate_root_cause_review(self, review: dict[str, Any]) -> list[str]:
        """Validate the root cause review structure."""
        errors = []

        if "scores" not in review:
            errors.append("Missing 'scores' field")
        else:
            scores = review["scores"]
            required_dims = [
                "evidence_quality",
                "hypothesis_correctness",
                "completeness",
                "alternative_consideration",
            ]
            for dim in required_dims:
                if dim not in scores:
                    errors.append(f"Missing score dimension: {dim}")
                elif not isinstance(scores[dim], (int, float)):
                    errors.append(f"Invalid score type for {dim}: {type(scores[dim])}")
                elif not 0.0 <= scores[dim] <= 1.0:
                    errors.append(f"Score out of range for {dim}: {scores[dim]}")

        if "issues" not in review:
            errors.append("Missing 'issues' field")
        elif not isinstance(review["issues"], list):
            errors.append("'issues' must be a list")

        return errors

    def _validate_fix_plan_review(self, review: dict[str, Any]) -> list[str]:
        """Validate the fix plan review structure."""
        errors = []

        if "scores" not in review:
            errors.append("Missing 'scores' field")
        else:
            scores = review["scores"]
            required_dims = [
                "correctness",
                "completeness",
                "risk_assessment",
                "test_coverage",
                "side_effect_analysis",
            ]
            for dim in required_dims:
                if dim not in scores:
                    errors.append(f"Missing score dimension: {dim}")
                elif not isinstance(scores[dim], (int, float)):
                    errors.append(f"Invalid score type for {dim}: {type(scores[dim])}")
                elif not 0.0 <= scores[dim] <= 1.0:
                    errors.append(f"Score out of range for {dim}: {scores[dim]}")

        if "issues" not in review:
            errors.append("Missing 'issues' field")
        elif not isinstance(review["issues"], list):
            errors.append("'issues' must be a list")

        return errors

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Review root cause analysis or fix plan.

        Args:
            context: Dictionary containing:
                - bug_id: The bug identifier (required)
                - mode: "root_cause" or "fix_plan" (required)
                - root_cause: RootCauseAnalysis object (for root_cause mode)
                - fix_plan: FixPlan object (for fix_plan mode)
                - bug_description: Bug description string
                - reproduction_summary: Summary of reproduction (for root_cause mode)
                - root_cause_summary: Summary of root cause (for fix_plan mode)

        Returns:
            AgentResult with:
                - success: True if review was generated
                - output: Dict with scores, issues, and recommendation
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation (0 for Codex subscription)
        """
        bug_id = context.get("bug_id")
        mode = context.get("mode")

        if not bug_id:
            return AgentResult.failure_result("Missing required context: bug_id")
        if mode not in ("root_cause", "fix_plan"):
            return AgentResult.failure_result(
                f"Invalid mode: {mode}. Must be 'root_cause' or 'fix_plan'"
            )

        self._log("bug_critic_start", {"bug_id": bug_id, "mode": mode})
        self.checkpoint("started")

        # Load skill prompt
        try:
            self._load_skill_prompt(mode)
        except SkillNotFoundError as e:
            self._log("bug_critic_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        # Build prompt based on mode
        if mode == "root_cause":
            root_cause = context.get("root_cause")
            if not root_cause:
                return AgentResult.failure_result(
                    "Missing required context: root_cause"
                )
            prompt = self._build_root_cause_prompt(
                bug_id=bug_id,
                root_cause=root_cause,
                bug_description=context.get("bug_description", ""),
                reproduction_summary=context.get("reproduction_summary", ""),
            )
            validate_fn = self._validate_root_cause_review
        else:  # fix_plan mode
            fix_plan = context.get("fix_plan")
            if not fix_plan:
                return AgentResult.failure_result("Missing required context: fix_plan")
            prompt = self._build_fix_plan_prompt(
                bug_id=bug_id,
                fix_plan=fix_plan,
                root_cause_summary=context.get("root_cause_summary", ""),
                bug_description=context.get("bug_description", ""),
            )
            validate_fn = self._validate_fix_plan_review

        self.checkpoint("prompt_built")

        # Invoke Codex with 10 minute timeout
        try:
            result = self.codex.run(prompt, timeout=self.DEBATE_TIMEOUT_SECONDS)
            cost = 0.0  # Codex uses flat-rate subscription
        except CodexAuthError as e:
            # CRITICAL: Stop and tell user to login
            error_msg = get_user_action_message(e)
            self._log("bug_critic_auth_error", {"error": str(e)}, level="error")
            print(error_msg)
            return AgentResult.failure_result(
                "Codex authentication required. Please run 'codex login' and try again."
            )
        except CodexTimeoutError as e:
            error = f"Codex timed out after {self.DEBATE_TIMEOUT_SECONDS}s: {e}"
            self._log("bug_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except LLMError as e:
            if e.requires_user_action:
                error_msg = get_user_action_message(e)
                self._log("bug_critic_user_action_required", {"error": str(e)}, level="error")
                print(error_msg)
            error = f"Codex error: {e}"
            self._log("bug_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except CodexInvocationError as e:
            error = f"Codex invocation error: {e}"
            self._log("bug_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse review JSON from response
        try:
            review = self._parse_review_json(result.text)
        except ValueError as e:
            error = f"Failed to parse review JSON: {e}"
            self._log("bug_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate review structure
        validation_errors = validate_fn(review)
        if validation_errors:
            error = f"Invalid review structure: {', '.join(validation_errors)}"
            self._log("bug_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Add metadata to review
        review["bug_id"] = bug_id
        review["mode"] = mode
        review["reviewed_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Count issues by severity
        issues = review.get("issues", [])
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")
        moderate_count = sum(1 for i in issues if i.get("severity") == "moderate")
        minor_count = sum(1 for i in issues if i.get("severity") == "minor")

        # Success
        self._log(
            "bug_critic_complete",
            {
                "bug_id": bug_id,
                "mode": mode,
                "scores": review["scores"],
                "critical_issues": critical_count,
                "moderate_issues": moderate_count,
                "minor_issues": minor_count,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output={
                "scores": review["scores"],
                "issues": issues,
                "issue_counts": {
                    "critical": critical_count,
                    "moderate": moderate_count,
                    "minor": minor_count,
                },
                "summary": review.get("summary", ""),
                "recommendation": review.get("recommendation", "REVISE"),
            },
            cost_usd=cost,
        )
