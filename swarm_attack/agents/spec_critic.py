"""
Spec Critic Agent for Feature Swarm.

This agent reviews spec drafts, scores them against a quality rubric,
and identifies issues that need to be addressed.

IMPORTANT: Uses Codex CLI for independent review (not Claude), to avoid
Claude reviewing its own work.
"""

from __future__ import annotations

import json
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


class SpecCriticAgent(BaseAgent):
    """
    Agent that reviews and scores engineering specs.

    Uses Codex CLI (not Claude) for independent review to avoid self-review bias.

    Reads a spec draft from specs/<feature>/spec-draft.md and the original PRD,
    then produces a review at specs/<feature>/spec-review.json with rubric
    scores and identified issues.
    """

    name = "spec_critic"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        codex_runner: Optional[CodexCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the Spec Critic agent.

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
            # Invert check_codex_auth: if auth check is disabled, skip classification
            skip_auth = not getattr(
                getattr(self.config, 'preflight', None),
                'check_codex_auth',
                True  # Default to enabled (don't skip)
            )
            self._codex = CodexCliRunner(
                config=self.config,
                logger=self.logger,
                checkpoint_callback=lambda: self.checkpoint("pre_codex_call"),
                skip_auth_classification=skip_auth,
            )
        return self._codex

    def _get_prd_path(self, feature_id: str) -> Path:
        """Get the path to the PRD file."""
        return Path(self.config.repo_root) / ".claude" / "prds" / f"{feature_id}.md"

    def _get_spec_dir(self, feature_id: str) -> Path:
        """Get the spec directory."""
        return self.config.specs_path / feature_id

    def _get_spec_draft_path(self, feature_id: str) -> Path:
        """Get the path to the spec draft file."""
        return self._get_spec_dir(feature_id) / "spec-draft.md"

    def _get_review_path(self, feature_id: str) -> Path:
        """Get the path to the review output file."""
        return self._get_spec_dir(feature_id) / "spec-review.json"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("feature-spec-critic")
        return self._skill_prompt

    def _build_prompt(
        self, feature_id: str, spec_content: str, prd_content: str, rejection_context: str = ""
    ) -> str:
        """Build the full prompt for GPT-5.

        Args:
            feature_id: The feature identifier.
            spec_content: The spec draft markdown content.
            prd_content: The PRD markdown content.
            rejection_context: Prior round rejection context to avoid re-raising.

        Returns:
            Full prompt string for the LLM.
        """
        skill_prompt = self._load_skill_prompt()

        # Build rejection context section if provided
        rejection_section = ""
        if rejection_context:
            rejection_section = f"""
{rejection_context}
"""

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}
{rejection_section}
**PRD Content:**

```markdown
{prd_content}
```

**Spec Draft Content:**

```markdown
{spec_content}
```

**Output Path:** specs/{feature_id}/spec-review.json

---

## Your Task

Review the spec draft against the PRD and generate a comprehensive review.
Score each rubric dimension (clarity, coverage, architecture, risk) from 0.0 to 1.0.
Identify all issues with severity (critical, moderate, minor).
Output ONLY valid JSON matching the schema in the skill instructions.
Do not include any markdown code fences or explanatory text - just the raw JSON.

## Output Schema

Your output JSON MUST include these fields:
```json
{{
  "scores": {{"clarity": 0.0, "coverage": 0.0, "architecture": 0.0, "risk": 0.0}},
  "issues": [...],
  "disputed_issues": [],
  "strengths": [...],
  "summary": "..."
}}
```

**Important:**
- `issues`: Regular issues you've identified (NEW issues not previously rejected)
- `disputed_issues`: ONLY use this if you strongly disagree with a prior rejection
  and have new evidence. See "If You Disagree With a Rejection" above.
"""

    def _parse_review_json(self, text: str) -> dict[str, Any]:
        """
        Parse the review JSON from GPT-5's response.

        Handles cases where the response may contain markdown code fences.
        """
        # Try to parse as-is first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code fence
        import re

        # Match ```json ... ``` or ``` ... ```
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
        # Look for first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from response: {text[:200]}...")

    def _validate_review(self, review: dict[str, Any]) -> list[str]:
        """Validate the review structure and return list of validation errors."""
        errors = []

        # Check required fields
        if "scores" not in review:
            errors.append("Missing 'scores' field")
        else:
            scores = review["scores"]
            required_dimensions = ["clarity", "coverage", "architecture", "risk"]
            for dim in required_dimensions:
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
        Review a spec draft and produce a scored review.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - rejection_context: Prior round rejection context (optional)

        Returns:
            AgentResult with:
                - success: True if review was generated
                - output: Dict with scores, issues, disputed_issues, and review_path
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        # Extract optional rejection context for round 2+
        rejection_context = context.get("rejection_context", "")

        self._log("spec_critic_start", {
            "feature_id": feature_id,
            "has_rejection_context": bool(rejection_context),
        })
        self.checkpoint("started")

        # Check if spec draft exists
        spec_path = self._get_spec_draft_path(feature_id)
        if not file_exists(spec_path):
            error = f"Spec draft not found at {spec_path}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Check if PRD exists
        prd_path = self._get_prd_path(feature_id)
        if not file_exists(prd_path):
            error = f"PRD not found at {prd_path}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Read spec and PRD content
        try:
            spec_content = read_file(spec_path)
            prd_content = read_file(prd_path)
        except Exception as e:
            error = f"Failed to read files: {e}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("spec_critic_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("files_loaded")

        # Build prompt and invoke Codex (with rejection context for round 2+)
        prompt = self._build_prompt(feature_id, spec_content, prd_content, rejection_context)

        try:
            result = self.codex.run(
                prompt,
                timeout=self.config.spec_debate.timeout_seconds,  # 15 min default for large specs
            )
            cost = 0.0  # Codex uses flat-rate subscription
        except CodexTimeoutError as e:
            error = f"Codex timed out: {e}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except LLMError as e:
            # Handle auth and other errors gracefully
            if e.requires_user_action:
                error_msg = get_user_action_message(e)
                self._log("spec_critic_auth_error", {"error": str(e)}, level="error")
                print(error_msg)  # Show user the action message
            error = f"Codex error: {e}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except CodexInvocationError as e:
            error = f"Codex invocation error: {e}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except Exception as e:
            # Catch-all for any unexpected exceptions to prevent pipeline crashes
            error = f"Unexpected error during critic review: {type(e).__name__}: {e}"
            self._log("spec_critic_unexpected_error", {"error": error, "exception_type": type(e).__name__}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse review JSON from response
        try:
            review = self._parse_review_json(result.text)
        except ValueError as e:
            error = f"Failed to parse review JSON: {e}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate review structure
        validation_errors = self._validate_review(review)
        if validation_errors:
            error = f"Invalid review structure: {', '.join(validation_errors)}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Add metadata to review
        review["spec_path"] = str(spec_path)
        review["prd_path"] = str(prd_path)
        review["reviewed_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Write review to file
        review_path = self._get_review_path(feature_id)
        try:
            ensure_dir(review_path.parent)
            safe_write(review_path, json.dumps(review, indent=2))
        except Exception as e:
            error = f"Failed to write review: {e}"
            self._log("spec_critic_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("review_written", cost_usd=0)

        # Count issues by severity
        issues = review.get("issues", [])
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")
        moderate_count = sum(1 for i in issues if i.get("severity") == "moderate")
        minor_count = sum(1 for i in issues if i.get("severity") == "minor")

        # Success
        self._log(
            "spec_critic_complete",
            {
                "feature_id": feature_id,
                "scores": review["scores"],
                "critical_issues": critical_count,
                "moderate_issues": moderate_count,
                "minor_issues": minor_count,
                "cost_usd": cost,
            },
        )

        # Extract disputed issues if any (for escalation to human review)
        disputed_issues = review.get("disputed_issues", [])

        return AgentResult.success_result(
            output={
                "review_path": str(review_path),
                "scores": review["scores"],
                "issues": issues,
                "disputed_issues": disputed_issues,  # NEW: For escalation path
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
