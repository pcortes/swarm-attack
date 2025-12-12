"""
Bug Moderator Agent for Bug Bash pipeline.

This agent applies critic feedback to improve root cause analysis and fix plans,
and determines whether another round of debate is needed.

Uses Claude CLI for applying feedback and improving analysis.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError

if TYPE_CHECKING:
    from swarm_attack.bug_models import FixPlan, RootCauseAnalysis
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore

logger = logging.getLogger(__name__)


class BugModeratorAgent(BaseAgent):
    """
    Agent that applies critic feedback to improve root cause analysis and fix plans.

    Operates in two modes:
    - "root_cause": Improves root cause analysis based on critic feedback
    - "fix_plan": Improves fix plan based on critic feedback

    Uses Claude CLI for generating improvements.
    """

    name = "bug_moderator"

    # 10 minute timeout per debate round for thorough improvement
    DEBATE_TIMEOUT_SECONDS = 600

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Bug Moderator agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompts: dict[str, str] = {}

    def _load_skill_prompt(self, mode: Literal["root_cause", "fix_plan"]) -> str:
        """Load and cache the skill prompt for the given mode."""
        skill_name = f"bug-{mode.replace('_', '-')}-moderator"
        if skill_name not in self._skill_prompts:
            self._skill_prompts[skill_name] = self.load_skill(skill_name)
        return self._skill_prompts[skill_name]

    def _build_root_cause_prompt(
        self,
        bug_id: str,
        root_cause: RootCauseAnalysis,
        review: dict[str, Any],
        bug_description: str,
        reproduction_summary: str,
        round_number: int,
    ) -> str:
        """Build the prompt for improving root cause analysis."""
        skill_prompt = self._load_skill_prompt("root_cause")

        return f"""{skill_prompt}

---

## Context for This Task

**Bug ID:** {bug_id}
**Round Number:** {round_number}

**Bug Description:**
{bug_description}

**Reproduction Summary:**
{reproduction_summary}

**Current Root Cause Analysis:**

```json
{json.dumps(root_cause.to_dict(), indent=2)}
```

**Critic Review (from independent reviewer):**

```json
{json.dumps(review, indent=2)}
```

---

## Your Task

1. Address the issues identified in the critic review
2. Improve the root cause analysis with better evidence and reasoning
3. Output the improved analysis and a rubric self-assessment

## CRITICAL OUTPUT FORMAT

You MUST output in EXACTLY this format. Do NOT deviate:

<<<ANALYSIS_START>>>
{{
  "summary": "Brief summary of root cause (max 100 chars)",
  "execution_trace": ["step1", "step2", "step3", ...],
  "root_cause_file": "path/to/file.py",
  "root_cause_line": 123,
  "root_cause_code": "the problematic code snippet",
  "root_cause_explanation": "detailed explanation of why this causes the bug",
  "why_not_caught": "explanation of why existing tests didn't catch this",
  "confidence": "high|medium|low",
  "alternative_hypotheses": ["hypothesis1 that was considered and ruled out", ...]
}}
<<<ANALYSIS_END>>>

<<<RUBRIC_START>>>
{{
  "round": {round_number},
  "previous_scores": {json.dumps(review.get("scores", {}))},
  "current_scores": {{"evidence_quality": 0.0, "hypothesis_correctness": 0.0, "completeness": 0.0, "alternative_consideration": 0.0}},
  "improvements": ["list of improvements made"],
  "remaining_issues": ["any issues not yet addressed"],
  "issues_addressed": 0,
  "issues_remaining": 0,
  "continue_debate": true,
  "ready_for_approval": false
}}
<<<RUBRIC_END>>>

## CRITICAL: YOU MUST OUTPUT TEXT

**THIS IS THE MOST IMPORTANT INSTRUCTION:**
- You MUST output the analysis and rubric as TEXT in your response
- Do NOT use any tools like Write, Edit, or Bash
- Your ONLY job is to OUTPUT TEXT with the markers

## Format Rules

- Do NOT wrap the JSON in markdown code fences
- Do NOT add explanations outside the markers
- The analysis JSON must be valid JSON
- Fill in the rubric with your actual assessment scores and details
- Be thorough - take your time to get this right
"""

    def _build_fix_plan_prompt(
        self,
        bug_id: str,
        fix_plan: FixPlan,
        review: dict[str, Any],
        bug_description: str,
        root_cause_summary: str,
        round_number: int,
    ) -> str:
        """Build the prompt for improving fix plan."""
        skill_prompt = self._load_skill_prompt("fix_plan")

        return f"""{skill_prompt}

---

## Context for This Task

**Bug ID:** {bug_id}
**Round Number:** {round_number}

**Bug Description:**
{bug_description}

**Root Cause Summary:**
{root_cause_summary}

**Current Fix Plan:**

```json
{json.dumps(fix_plan.to_dict(), indent=2)}
```

**Critic Review (from independent reviewer):**

```json
{json.dumps(review, indent=2)}
```

---

## Your Task

1. Address the issues identified in the critic review
2. Improve the fix plan with better code changes and test coverage
3. Output the improved plan and a rubric self-assessment

## CRITICAL OUTPUT FORMAT

You MUST output in EXACTLY this format. Do NOT deviate:

<<<PLAN_START>>>
{{
  "summary": "Brief summary of the fix approach",
  "changes": [
    {{
      "file_path": "path/to/file.py",
      "change_type": "modify|create|delete",
      "current_code": "existing code to replace (for modify)",
      "proposed_code": "new code",
      "explanation": "why this change is needed"
    }}
  ],
  "test_cases": [
    {{
      "name": "test_name",
      "description": "what the test verifies",
      "test_code": "def test_name():\\n    ...",
      "category": "regression|edge_case|integration"
    }}
  ],
  "risk_level": "low|medium|high",
  "risk_explanation": "why this risk level",
  "scope": "what parts of the codebase are affected",
  "side_effects": ["potential side effect 1", ...],
  "rollback_plan": "how to revert if needed",
  "estimated_effort": "small|medium|large"
}}
<<<PLAN_END>>>

<<<RUBRIC_START>>>
{{
  "round": {round_number},
  "previous_scores": {json.dumps(review.get("scores", {}))},
  "current_scores": {{"correctness": 0.0, "completeness": 0.0, "risk_assessment": 0.0, "test_coverage": 0.0, "side_effect_analysis": 0.0}},
  "improvements": ["list of improvements made"],
  "remaining_issues": ["any issues not yet addressed"],
  "issues_addressed": 0,
  "issues_remaining": 0,
  "continue_debate": true,
  "ready_for_approval": false
}}
<<<RUBRIC_END>>>

## CRITICAL: YOU MUST OUTPUT TEXT

**THIS IS THE MOST IMPORTANT INSTRUCTION:**
- You MUST output the plan and rubric as TEXT in your response
- Do NOT use any tools like Write, Edit, or Bash
- Your ONLY job is to OUTPUT TEXT with the markers

## Format Rules

- Do NOT wrap the JSON in markdown code fences
- Do NOT add explanations outside the markers
- The plan JSON must be valid JSON
- Fill in the rubric with your actual assessment scores and details
- Be thorough - take your time to get this right
"""

    # =========================================================================
    # Multi-Strategy Fallback Parser (adapted from SpecModeratorAgent)
    # =========================================================================

    def _normalize_response(self, text: str) -> str:
        """Strip common LLM conversational wrappers and artifacts."""
        if not text:
            return ""

        prefix_patterns = [
            r"^(Here's|Here is|I've|I have|Below is|I'll)[^:]*:\s*\n",
            r"^(Sure|Certainly|Of course|Absolutely)[^.]*\.\s*\n",
            r"^(Let me|I will|I'm going to)[^.]*\.\s*\n",
        ]

        suffix_patterns = [
            r"\n*(Let me know|Hope this helps|Feel free|If you have)[^.]*\.?\s*$",
            r"\n*(Is there anything|Would you like)[^?]*\?\s*$",
        ]

        result = text
        for pattern in prefix_patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)
        for pattern in suffix_patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result.strip()

    def _try_delimiter_extraction(
        self, text: str, content_marker: str
    ) -> tuple[dict | None, dict | None]:
        """
        Strategy 1: Extract using <<<MARKER_START>>> / <<<RUBRIC_START>>> markers.
        """
        start_marker = f"<<<{content_marker}_START>>>"
        end_marker = f"<<<{content_marker}_END>>>"

        content_match = re.search(
            rf"{start_marker}\s*(.*?)\s*{end_marker}", text, re.DOTALL
        )
        rubric_match = re.search(
            r"<<<RUBRIC_START>>>\s*(.*?)\s*<<<RUBRIC_END>>>", text, re.DOTALL
        )

        content = None
        rubric = None

        if content_match:
            content = self._extract_json_permissive(content_match.group(1))

        if rubric_match:
            rubric = self._extract_json_permissive(rubric_match.group(1))

        return content, rubric

    def _extract_json_permissive(self, text: str) -> dict | None:
        """
        Extract JSON even when wrapped in markdown or with minor issues.
        """
        if not text:
            return None

        # Strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```\s*$", "", text)

        # Find JSON object boundaries using bracket matching
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        end = -1

        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == -1:
            return None

        json_str = text[start : end + 1]

        # Try direct parse first
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Try fixing common issues
        fixes = [
            (r",\s*([}\]])", r"\1"),  # Remove trailing commas
            (r"'([^']*)':", r'"\1":'),  # Single quotes to double
            (r"//[^\n]*\n", "\n"),  # Remove JS comments
        ]

        fixed_json = json_str
        for pattern, replacement in fixes:
            fixed_json = re.sub(pattern, replacement, fixed_json)

        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError:
            return None

    def _parse_response(
        self, text: str, mode: Literal["root_cause", "fix_plan"]
    ) -> tuple[dict | None, dict | None]:
        """
        Parse the response using multi-strategy fallback.

        Returns:
            Tuple of (content_dict, rubric_dict) - either may be None
        """
        if not text:
            return None, None

        normalized = self._normalize_response(text)

        # Determine content marker based on mode
        content_marker = "ANALYSIS" if mode == "root_cause" else "PLAN"

        # Try delimiter extraction first (primary strategy)
        content, rubric = self._try_delimiter_extraction(normalized, content_marker)

        if content is not None:
            logger.info(f"Extracted {mode} content using delimiter strategy")

        if rubric is not None:
            logger.info("Extracted rubric using delimiter strategy")

        # If delimiter failed, try raw text
        if content is None:
            content, rubric_alt = self._try_delimiter_extraction(text, content_marker)
            if content is not None:
                logger.info(f"Extracted {mode} content using delimiter on raw text")
            if rubric is None and rubric_alt is not None:
                rubric = rubric_alt

        return content, rubric

    def _create_default_rubric(
        self,
        round_number: int,
        previous_scores: dict[str, float],
        mode: Literal["root_cause", "fix_plan"],
    ) -> dict[str, Any]:
        """Create a default rubric if parsing fails."""
        if mode == "root_cause":
            score_keys = [
                "evidence_quality",
                "hypothesis_correctness",
                "completeness",
                "alternative_consideration",
            ]
        else:
            score_keys = [
                "correctness",
                "completeness",
                "risk_assessment",
                "test_coverage",
                "side_effect_analysis",
            ]

        current_scores = {k: previous_scores.get(k, 0.5) for k in score_keys}

        return {
            "round": round_number,
            "previous_scores": previous_scores,
            "current_scores": current_scores,
            "improvements": [],
            "remaining_issues": [],
            "issues_addressed": 0,
            "issues_remaining": 0,
            "continue_debate": True,
            "ready_for_approval": False,
        }

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Apply critic feedback to improve analysis or fix plan.

        Args:
            context: Dictionary containing:
                - bug_id: The bug identifier (required)
                - mode: "root_cause" or "fix_plan" (required)
                - root_cause: RootCauseAnalysis object (for root_cause mode)
                - fix_plan: FixPlan object (for fix_plan mode)
                - review: Dict with critic's review (scores, issues)
                - bug_description: Bug description string
                - reproduction_summary: Summary of reproduction (for root_cause mode)
                - root_cause_summary: Summary of root cause (for fix_plan mode)
                - round: Current debate round number (default: 1)

        Returns:
            AgentResult with:
                - success: True if improvement was generated
                - output: Dict with improved content and rubric
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        bug_id = context.get("bug_id")
        mode = context.get("mode")
        round_number = context.get("round", 1)

        if not bug_id:
            return AgentResult.failure_result("Missing required context: bug_id")
        if mode not in ("root_cause", "fix_plan"):
            return AgentResult.failure_result(
                f"Invalid mode: {mode}. Must be 'root_cause' or 'fix_plan'"
            )

        review = context.get("review", {})
        if not review:
            return AgentResult.failure_result("Missing required context: review")

        self._log(
            "bug_moderator_start", {"bug_id": bug_id, "mode": mode, "round": round_number}
        )
        self.checkpoint("started")

        # Load skill prompt
        try:
            self._load_skill_prompt(mode)
        except SkillNotFoundError as e:
            self._log("bug_moderator_error", {"error": str(e)}, level="error")
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
                review=review,
                bug_description=context.get("bug_description", ""),
                reproduction_summary=context.get("reproduction_summary", ""),
                round_number=round_number,
            )
        else:  # fix_plan mode
            fix_plan = context.get("fix_plan")
            if not fix_plan:
                return AgentResult.failure_result("Missing required context: fix_plan")
            prompt = self._build_fix_plan_prompt(
                bug_id=bug_id,
                fix_plan=fix_plan,
                review=review,
                bug_description=context.get("bug_description", ""),
                root_cause_summary=context.get("root_cause_summary", ""),
                round_number=round_number,
            )

        self.checkpoint("prompt_built")

        # Invoke Claude with 10 minute timeout
        try:
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob"],  # Allow context reading
                timeout=self.DEBATE_TIMEOUT_SECONDS,
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out after {self.DEBATE_TIMEOUT_SECONDS}s: {e}"
            self._log("bug_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("bug_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Get previous scores for default rubric creation
        previous_scores = review.get("scores", {})

        # Parse response
        content, rubric = self._parse_response(result.text, mode)

        # Log parsing result
        self._log(
            "bug_moderator_parse_result",
            {
                "content_extracted": content is not None,
                "rubric_extracted": rubric is not None,
                "response_length": len(result.text) if result.text else 0,
            },
        )

        # We need valid content
        if not content:
            self._log(
                "bug_moderator_extraction_failed",
                {"response_preview": (result.text[:500] if result.text else "empty")},
                level="error",
            )
            error = f"Failed to extract improved {mode} from response"
            self._log("bug_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # If no rubric parsed, create default
        if not rubric:
            rubric = self._create_default_rubric(round_number, previous_scores, mode)

        # Ensure rubric has required fields
        rubric["round"] = round_number
        rubric["previous_scores"] = previous_scores
        rubric["updated_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Determine if we should continue
        current_scores = rubric.get("current_scores", previous_scores)
        continue_debate = rubric.get("continue_debate", True)
        ready_for_approval = rubric.get("ready_for_approval", False)

        # Success
        self._log(
            "bug_moderator_complete",
            {
                "bug_id": bug_id,
                "mode": mode,
                "round": round_number,
                "previous_scores": previous_scores,
                "current_scores": current_scores,
                "continue_debate": continue_debate,
                "ready_for_approval": ready_for_approval,
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output={
                "improved_content": content,
                "round": round_number,
                "previous_scores": previous_scores,
                "current_scores": current_scores,
                "continue_debate": continue_debate,
                "ready_for_approval": ready_for_approval,
                "improvements": rubric.get("improvements", []),
                "remaining_issues": rubric.get("remaining_issues", []),
            },
            cost_usd=cost,
        )
