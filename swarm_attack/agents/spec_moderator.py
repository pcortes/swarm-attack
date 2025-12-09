"""
Spec Moderator Agent for Feature Swarm.

This agent applies critic feedback to improve a spec draft and determines
whether another round of debate is needed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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


class SpecModeratorAgent(BaseAgent):
    """
    Agent that applies critic feedback to improve specs.

    Reads spec-draft.md and spec-review.json, applies feedback to improve
    the spec, and writes the updated spec along with a new rubric assessment.
    """

    name = "spec_moderator"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Spec Moderator agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

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
        """Get the path to the review file."""
        return self._get_spec_dir(feature_id) / "spec-review.json"

    def _get_rubric_path(self, feature_id: str) -> Path:
        """Get the path to the rubric output file."""
        return self._get_spec_dir(feature_id) / "spec-rubric.json"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("feature-spec-moderator")
        return self._skill_prompt

    def _build_prompt(
        self,
        feature_id: str,
        spec_content: str,
        review_content: dict[str, Any],
        prd_content: str,
        round_number: int,
    ) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}
**Round Number:** {round_number}

**PRD Content:**

```markdown
{prd_content}
```

**Current Spec Draft:**

```markdown
{spec_content}
```

**Critic Review:**

```json
{json.dumps(review_content, indent=2)}
```

**Output Paths:**
- Updated spec: specs/{feature_id}/spec-draft.md
- Rubric assessment: specs/{feature_id}/spec-rubric.json

---

## Your Task

1. Address the issues identified in the critic review
2. Rewrite the spec draft with improvements
3. Create a rubric assessment JSON

Output the UPDATED SPEC CONTENT first, followed by a separator "---RUBRIC---",
then the rubric JSON.

Example output format:
```
# Engineering Spec: Feature Name

[Full updated spec content here...]

---RUBRIC---
{{
  "round": 2,
  "current_scores": {{"clarity": 0.9, ...}},
  ...
}}
```

Do not use code fences around the spec content. The rubric JSON should be raw JSON without code fences.
"""

    def _parse_response(self, text: str) -> tuple[str, dict[str, Any]]:
        """
        Parse the response to extract spec content and rubric JSON.

        Returns:
            Tuple of (spec_content, rubric_dict)
        """
        # Look for the separator
        separator = "---RUBRIC---"
        if separator in text:
            parts = text.split(separator, 1)
            spec_content = parts[0].strip()
            rubric_text = parts[1].strip()
        else:
            # Try to find JSON at the end of the response
            import re

            # Look for JSON object
            json_match = re.search(r"\{[^{}]*\"round\"[^{}]*\}", text, re.DOTALL)
            if json_match:
                rubric_text = json_match.group(0)
                spec_content = text[: json_match.start()].strip()
            else:
                # No rubric found, return the whole thing as spec
                return text.strip(), {}

        # Parse rubric JSON
        try:
            # Handle markdown code fences
            if rubric_text.startswith("```"):
                rubric_text = re.sub(r"```json?\s*", "", rubric_text)
                rubric_text = re.sub(r"\s*```", "", rubric_text)

            rubric = json.loads(rubric_text)
            return spec_content, rubric
        except json.JSONDecodeError:
            # Try to extract just the JSON object
            start = rubric_text.find("{")
            end = rubric_text.rfind("}")
            if start != -1 and end != -1:
                try:
                    rubric = json.loads(rubric_text[start : end + 1])
                    return spec_content, rubric
                except json.JSONDecodeError:
                    pass

            return spec_content, {}

    def _create_default_rubric(
        self,
        round_number: int,
        previous_scores: dict[str, float],
    ) -> dict[str, Any]:
        """Create a default rubric if parsing fails."""
        return {
            "round": round_number,
            "previous_scores": previous_scores,
            "current_scores": previous_scores.copy(),
            "improvements": [],
            "remaining_issues": [],
            "issues_addressed": 0,
            "issues_remaining": 0,
            "continue_debate": True,
            "ready_for_approval": False,
        }

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Apply critic feedback to improve the spec.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - round: The current debate round number (default: 1)

        Returns:
            AgentResult with:
                - success: True if spec was improved
                - output: Dict with updated scores and continue_debate flag
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        round_number = context.get("round", 1)

        self._log(
            "spec_moderator_start", {"feature_id": feature_id, "round": round_number}
        )
        self.checkpoint("started")

        # Check required files exist
        spec_path = self._get_spec_draft_path(feature_id)
        review_path = self._get_review_path(feature_id)
        prd_path = self._get_prd_path(feature_id)

        for path, name in [
            (spec_path, "spec draft"),
            (review_path, "spec review"),
            (prd_path, "PRD"),
        ]:
            if not file_exists(path):
                error = f"{name} not found at {path}"
                self._log("spec_moderator_error", {"error": error}, level="error")
                return AgentResult.failure_result(error)

        # Read all required files
        try:
            spec_content = read_file(spec_path)
            review_content = json.loads(read_file(review_path))
            prd_content = read_file(prd_path)
        except Exception as e:
            error = f"Failed to read files: {e}"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("spec_moderator_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("files_loaded")

        # Build prompt and invoke Claude
        prompt = self._build_prompt(
            feature_id, spec_content, review_content, prd_content, round_number
        )

        try:
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob", "Write"],
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Get previous scores for default rubric creation
        previous_scores = review_content.get("scores", {})
        rubric_path = self._get_rubric_path(feature_id)

        # Check if Claude already wrote the spec file via Write tool
        # This handles the case where result.text is conversational
        updated_spec = ""
        rubric: dict[str, Any] = {}

        # First, try to get spec from the file Claude may have written
        if file_exists(spec_path):
            try:
                file_content = read_file(spec_path)
                # Check if file was updated (different from original spec_content)
                # and has meaningful content
                if file_content and len(file_content.strip()) > 50:
                    if file_content.strip() != spec_content.strip():
                        # Claude updated the file via Write tool
                        updated_spec = file_content
                        self._log("spec_moderator_using_written_file", {
                            "spec_path": str(spec_path),
                            "content_length": len(updated_spec),
                        })
            except Exception:
                pass  # Fall back to parsing result.text

        # Similarly, check if Claude wrote the rubric file
        if file_exists(rubric_path):
            try:
                rubric_content = read_file(rubric_path)
                if rubric_content and rubric_content.strip():
                    rubric = json.loads(rubric_content)
                    self._log("spec_moderator_using_written_rubric", {
                        "rubric_path": str(rubric_path),
                    })
            except (json.JSONDecodeError, Exception):
                pass  # Fall back to parsing result.text

        # If we didn't get spec from file, try parsing result.text
        if not updated_spec:
            parsed_spec, parsed_rubric = self._parse_response(result.text)
            if parsed_spec and len(parsed_spec.strip()) > 50:
                updated_spec = parsed_spec
            if parsed_rubric and not rubric:
                rubric = parsed_rubric

        # Final validation: we need a valid spec
        if not updated_spec or len(updated_spec.strip()) < 50:
            error = "Failed to extract updated spec from response"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # If no rubric was parsed or found, create a default one
        if not rubric:
            rubric = self._create_default_rubric(round_number, previous_scores)

        # Ensure rubric has required fields
        rubric["round"] = round_number
        rubric["previous_scores"] = previous_scores
        rubric["updated_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

        # Write updated spec (may be a no-op if Claude already wrote it)
        try:
            safe_write(spec_path, updated_spec)
        except Exception as e:
            error = f"Failed to write updated spec: {e}"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Write rubric (may be a no-op if Claude already wrote it)
        try:
            ensure_dir(rubric_path.parent)
            safe_write(rubric_path, json.dumps(rubric, indent=2))
        except Exception as e:
            error = f"Failed to write rubric: {e}"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("files_written", cost_usd=0)

        # Determine if we should continue
        current_scores = rubric.get("current_scores", previous_scores)
        continue_debate = rubric.get("continue_debate", True)
        ready_for_approval = rubric.get("ready_for_approval", False)

        # Success
        self._log(
            "spec_moderator_complete",
            {
                "feature_id": feature_id,
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
                "spec_path": str(spec_path),
                "rubric_path": str(rubric_path),
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
