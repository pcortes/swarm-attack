"""
Spec Moderator Agent for Feature Swarm.

This agent applies critic feedback to improve a spec draft and determines
whether another round of debate is needed.

Uses a multi-strategy fallback parser for resilient LLM response extraction.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write

logger = logging.getLogger(__name__)

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

---

## Your Task

1. Address the issues identified in the critic review
2. Rewrite the spec draft with improvements
3. Create a rubric assessment JSON

## CRITICAL OUTPUT FORMAT

You MUST output in EXACTLY this format. Do NOT deviate:

<<<SPEC_START>>>
# Engineering Spec: {feature_id}

[Your complete updated spec content here]
<<<SPEC_END>>>

<<<RUBRIC_START>>>
{{
  "round": {round_number},
  "previous_scores": {json.dumps(review_content.get("scores", {}))},
  "current_scores": {{"clarity": 0.0, "coverage": 0.0, "architecture": 0.0, "risk": 0.0}},
  "improvements": [],
  "remaining_issues": [],
  "issues_addressed": 0,
  "issues_remaining": 0,
  "continue_debate": true,
  "ready_for_approval": false
}}
<<<RUBRIC_END>>>

## CRITICAL: YOU MUST OUTPUT TEXT

**THIS IS THE MOST IMPORTANT INSTRUCTION:**
- You MUST output the spec and rubric as TEXT in your response
- Do NOT use any tools like Write, Edit, or Bash
- The Write tool is NOT available to you
- Your ONLY job is to OUTPUT TEXT with the markers

If you try to use tools or don't output text, the task will FAIL.

## Format Rules

- Do NOT wrap the spec in markdown code fences
- Do NOT add explanations outside the markers
- Do NOT modify the marker format (<<<SPEC_START>>>, etc.)
- The rubric JSON must be valid JSON (no trailing commas, proper quotes)
- Fill in the rubric with your actual assessment scores and details

## Example of Correct Output

<<<SPEC_START>>>
# Engineering Spec: My Feature

## Overview
This spec describes...

## Requirements
1. First requirement
2. Second requirement

<<<SPEC_END>>>

<<<RUBRIC_START>>>
{{"round": 1, "current_scores": {{"clarity": 0.8}}}}
<<<RUBRIC_END>>>
"""

    # =========================================================================
    # Multi-Strategy Fallback Parser
    # =========================================================================

    def _normalize_response(self, text: str) -> str:
        """Strip common LLM conversational wrappers and artifacts."""
        if not text:
            return ""

        # Patterns for conversational prefixes to strip
        prefix_patterns = [
            r"^(Here's|Here is|I've|I have|Below is|I'll)[^:]*:\s*\n",
            r"^(Sure|Certainly|Of course|Absolutely)[^.]*\.\s*\n",
            r"^(Let me|I will|I'm going to)[^.]*\.\s*\n",
        ]

        # Patterns for conversational suffixes to strip
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

    def _try_delimiter_extraction(self, text: str) -> tuple[str | None, dict | None]:
        """
        Strategy 1: Extract using <<<SPEC_START>>> / <<<RUBRIC_START>>> markers.
        This is the primary/preferred method.
        """
        spec_match = re.search(
            r"<<<SPEC_START>>>\s*(.*?)\s*<<<SPEC_END>>>", text, re.DOTALL
        )
        rubric_match = re.search(
            r"<<<RUBRIC_START>>>\s*(.*?)\s*<<<RUBRIC_END>>>", text, re.DOTALL
        )

        spec_content = spec_match.group(1).strip() if spec_match else None
        rubric_content = None

        if rubric_match:
            rubric_content = self._extract_json_permissive(rubric_match.group(1))

        return spec_content, rubric_content

    def _try_separator_parsing(self, text: str) -> tuple[str | None, dict | None]:
        """
        Strategy 2: Look for ---RUBRIC--- style separators (fuzzy matching).
        Fallback for when LLM uses old format.
        """
        separators = [
            "---RUBRIC---",
            "--- RUBRIC ---",
            "---rubric---",
            "## RUBRIC",
            "## Rubric",
            "**RUBRIC**",
            "RUBRIC:",
        ]

        for sep in separators:
            if sep in text:
                parts = text.split(sep, 1)
                spec_content = parts[0].strip()
                rubric_content = self._extract_json_permissive(parts[1])
                if spec_content:
                    return spec_content, rubric_content

        return None, None

    def _try_json_block_extraction(self, text: str) -> tuple[str | None, dict | None]:
        """
        Strategy 3: Find JSON block containing rubric, treat everything before as spec.
        Works when LLM skips separator entirely.
        """
        # Look for JSON with "round" key (rubric signature)
        json_patterns = [
            r'\{\s*"round"\s*:.*?\}(?=\s*$|\s*```|\s*<<<)',  # JSON at end
            r'\{\s*"round"\s*:[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Nested JSON with round
        ]

        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                spec_content = text[: match.start()].strip()
                rubric_content = self._extract_json_permissive(match.group(0))
                if spec_content and len(spec_content) > 100:
                    return spec_content, rubric_content

        return None, None

    def _try_markdown_fence_extraction(
        self, text: str
    ) -> tuple[str | None, dict | None]:
        """
        Strategy 4: Extract from markdown code fences.
        Handles cases where LLM wraps everything in fences.
        """
        # Look for markdown spec block
        spec_match = re.search(
            r"```(?:markdown)?\s*(#[^`]+?)```", text, re.DOTALL | re.IGNORECASE
        )
        rubric_match = re.search(r"```(?:json)?\s*(\{[^`]+?\})```", text, re.DOTALL)

        spec_content = spec_match.group(1).strip() if spec_match else None
        rubric_content = None

        if rubric_match:
            rubric_content = self._extract_json_permissive(rubric_match.group(1))

        return spec_content, rubric_content

    def _try_header_extraction(self, text: str) -> tuple[str | None, dict | None]:
        """
        Strategy 5: Look for '# Engineering Spec' header and extract from there.
        Works when spec starts with expected header but no delimiters.
        """
        # Find where the spec starts
        header_patterns = [
            r"(#\s*Engineering Spec[^\n]*\n.*)",
            r"(#\s*Feature Spec[^\n]*\n.*)",
            r"(#\s*Technical Spec[^\n]*\n.*)",
        ]

        for pattern in header_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                # Try to find where rubric JSON starts
                json_start = self._find_last_json_object_start(content)
                if json_start and json_start > 100:
                    spec_content = content[:json_start].strip()
                    rubric_content = self._extract_json_permissive(content[json_start:])
                    return spec_content, rubric_content
                elif len(content) > 100:
                    return content.strip(), None

        return None, None

    def _find_last_json_object_start(self, text: str) -> int | None:
        """Find the start position of the last JSON object in text."""
        # Find all { positions and work backwards
        last_valid_start = None

        for i in range(len(text) - 1, -1, -1):
            if text[i] == "{":
                # Check if this could be start of rubric JSON
                snippet = text[i : i + 50]
                if '"round"' in snippet or '"current_scores"' in snippet:
                    last_valid_start = i
                    break

        return last_valid_start

    def _extract_json_permissive(self, text: str) -> dict | None:
        """
        Extract JSON even when wrapped in markdown or with minor issues.
        Handles common LLM JSON formatting problems.
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
            # Remove trailing commas before } or ]
            (r",\s*([}\]])", r"\1"),
            # Fix single quotes to double quotes
            (r"'([^']*)':", r'"\1":'),
            # Remove JS-style comments
            (r"//[^\n]*\n", "\n"),
        ]

        fixed_json = json_str
        for pattern, replacement in fixes:
            fixed_json = re.sub(pattern, replacement, fixed_json)

        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError:
            return None

    def _validate_spec(self, spec: str | None, original: str) -> str | None:
        """
        Validate extracted spec content.
        Returns None if validation fails.
        """
        if not spec:
            return None

        # Must have minimum length
        if len(spec.strip()) < 100:
            logger.debug("Spec validation failed: too short (%d chars)", len(spec))
            return None

        # Must not be just JSON (that would be rubric, not spec)
        stripped = spec.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            logger.debug("Spec validation failed: appears to be JSON")
            return None

        # Must contain expected spec markers (heuristic)
        expected_markers = ["#", "spec", "feature", "##", "requirement"]
        if not any(m.lower() in spec.lower() for m in expected_markers):
            logger.debug("Spec validation failed: missing expected markers")
            return None

        # Should be different from original (actual update occurred)
        if spec.strip() == original.strip():
            logger.debug("Spec validation warning: identical to original")
            # Don't fail, but log - LLM may have made no changes

        return spec

    def _parse_response(
        self, text: str, original_spec: str = ""
    ) -> tuple[str | None, dict | None]:
        """
        Parse the response using multi-strategy fallback.

        Tries strategies in order:
        1. Delimiter extraction (<<<SPEC_START>>> markers)
        2. Separator parsing (---RUBRIC---)
        3. JSON block extraction
        4. Markdown fence extraction
        5. Header-based extraction

        Returns:
            Tuple of (spec_content, rubric_dict) - either may be None
        """
        if not text:
            return None, None

        # Normalize first
        normalized = self._normalize_response(text)

        # Strategy chain
        strategies = [
            ("delimiter", self._try_delimiter_extraction),
            ("separator", self._try_separator_parsing),
            ("json_block", self._try_json_block_extraction),
            ("markdown_fence", self._try_markdown_fence_extraction),
            ("header", self._try_header_extraction),
        ]

        spec_content: str | None = None
        rubric_content: dict | None = None

        for name, strategy in strategies:
            try:
                result_spec, result_rubric = strategy(normalized)

                # Accept spec if valid and we don't have one yet
                if result_spec and not spec_content:
                    validated = self._validate_spec(result_spec, original_spec)
                    if validated:
                        spec_content = validated
                        logger.info(f"Extracted spec using strategy: {name}")

                # Accept rubric if valid and we don't have one yet
                if result_rubric and not rubric_content:
                    rubric_content = result_rubric
                    logger.info(f"Extracted rubric using strategy: {name}")

                # Stop if we have both
                if spec_content and rubric_content:
                    break

            except Exception as e:
                logger.debug(f"Strategy {name} raised exception: {e}")
                continue

        # If no spec found in normalized, try original text as last resort
        if not spec_content:
            for name, strategy in strategies:
                try:
                    result_spec, result_rubric = strategy(text)
                    if result_spec:
                        validated = self._validate_spec(result_spec, original_spec)
                        if validated:
                            spec_content = validated
                            logger.info(
                                f"Extracted spec using strategy {name} on raw text"
                            )
                            if result_rubric and not rubric_content:
                                rubric_content = result_rubric
                            break
                except Exception:
                    continue

        return spec_content, rubric_content

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
            # Allow Read/Glob for context but NOT Write
            # Write tool causes Claude to not output text, breaking extraction
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob"],
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

        # DEBUG: Dump raw response to file for inspection
        debug_path = self._get_spec_dir(feature_id) / "debug-response.txt"
        debug_raw_path = self._get_spec_dir(feature_id) / "debug-raw.json"
        try:
            safe_write(debug_path, result.text or "EMPTY RESPONSE")
            safe_write(debug_raw_path, json.dumps(result.raw, indent=2, default=str))
            logger.info(f"Wrote debug response to {debug_path}")
        except Exception as e:
            logger.warning(f"Failed to write debug response: {e}")

        # Get previous scores for default rubric creation
        previous_scores = review_content.get("scores", {})
        rubric_path = self._get_rubric_path(feature_id)

        # Parse response using multi-strategy fallback
        # Pass original spec for validation (to detect if it actually changed)
        updated_spec, rubric = self._parse_response(result.text, spec_content)

        # Log parsing result for debugging
        self._log(
            "spec_moderator_parse_result",
            {
                "spec_extracted": updated_spec is not None,
                "spec_length": len(updated_spec) if updated_spec else 0,
                "rubric_extracted": rubric is not None,
                "response_length": len(result.text) if result.text else 0,
            },
        )

        # Final validation: we need a valid spec
        if not updated_spec or len(updated_spec.strip()) < 100:
            # Log the raw response for debugging
            self._log(
                "spec_moderator_extraction_failed",
                {
                    "response_preview": (
                        result.text[:500] if result.text else "empty"
                    ),
                },
                level="error",
            )
            error = "Failed to extract updated spec from response"
            self._log("spec_moderator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Convert rubric to dict if None
        rubric = rubric or {}

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
