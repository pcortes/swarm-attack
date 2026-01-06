"""
Issue Creator Agent for Feature Swarm.

This agent reads an approved engineering specification and generates
GitHub issues for implementation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError
from swarm_attack.events.types import EventType
from swarm_attack.llm_clients import ClaudeInvocationError, ClaudeTimeoutError
from swarm_attack.utils.fs import ensure_dir, file_exists, read_file, safe_write

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore


class IssueCreatorAgent(BaseAgent):
    """
    Agent that generates GitHub issues from engineering specs.

    Reads a spec-final.md from specs/<feature>/ and generates a list of
    GitHub issues with titles, bodies, labels, dependencies, and sizing.
    Outputs to specs/<feature>/issues.json.
    """

    name = "issue_creator"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Issue Creator agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def _get_spec_path(self, feature_id: str) -> Path:
        """Get the path to the spec-final.md file."""
        return self.config.specs_path / feature_id / "spec-final.md"

    def _get_issues_path(self, feature_id: str) -> Path:
        """Get the path to the output issues.json file."""
        return self.config.specs_path / feature_id / "issues.json"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt, stripping YAML frontmatter.

        The skill file may contain YAML frontmatter with metadata like
        'allowed-tools: Read,Glob'. Since we run with allowed_tools=[]
        (no tools - we output JSON directly), this frontmatter in the prompt
        can confuse Claude into attempting tool use, burning through max_turns.

        We strip the frontmatter to avoid this confusion.
        """
        if self._skill_prompt is None:
            content, _ = self.load_skill_with_metadata("issue-creator")
            self._skill_prompt = content
        return self._skill_prompt

    def _build_prompt(self, feature_id: str, spec_content: str) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}

**Engineering Spec Content:**

```markdown
{spec_content}
```

---

## Your Task

Generate GitHub issues from the engineering specification above.

IMPORTANT: You MUST output the JSON directly as your final response. Do not use any tools to write files.
Just analyze the spec and print the JSON to stdout.

Output ONLY valid JSON (no markdown code fence, no extra text, no explanation) with this structure:

{{
  "feature_id": "{feature_id}",
  "generated_at": "<ISO timestamp>",
  "issues": [
    {{
      "title": "Short descriptive title",
      "body": "## Description\\n...\\n\\n## Acceptance Criteria\\n- [ ] ...",
      "labels": ["enhancement", "backend"],
      "estimated_size": "small|medium|large",
      "dependencies": [],
      "order": 1,
      "automation_type": "automated|manual"
    }}
  ]
}}

Requirements:
1. Each issue should be atomic and implementable in isolation (given dependencies)
2. Order issues by implementation order (1 = first)
3. Dependencies reference the order number of prerequisite issues
4. Size: small (~1-2 hours), medium (~half day), large (~1+ day)
5. Include relevant labels (enhancement, bug, backend, frontend, api, database, etc.)
6. Body should include Description, Acceptance Criteria, and any relevant context
7. automation_type: "automated" for code tasks, "manual" for tasks requiring human action
   - Use "manual" for: visual testing, simulator verification, user acceptance, QA review
   - Use "automated" for: code implementation, API work, database changes, automated tests

Remember: Print the JSON directly. Do not write to files. Do not wrap in markdown code blocks.
"""

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """
        Parse JSON from LLM response with robust extraction.

        Handles various response formats:
        - Raw JSON
        - JSON wrapped in markdown code fences
        - JSON with prose before/after
        - Empty responses (raises clear error)

        Raises:
            json.JSONDecodeError: If no valid JSON can be extracted
        """
        if not text or not text.strip():
            raise json.JSONDecodeError(
                "Empty response from LLM - no JSON to parse",
                text or "",
                0
            )

        text = text.strip()

        # Strategy 1: Try raw JSON parsing first (fastest path)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code fence (```json ... ```)
        code_fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(code_fence_pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find JSON object with "issues" key (handles prose before/after)
        # Look for { ... "issues": [ ... ] ... }
        issues_pattern = r'\{[^{}]*"issues"\s*:\s*\[[^\]]*\](?:[^{}]*|\{[^{}]*\})*\}'
        match = re.search(issues_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Strategy 4: Find any JSON object that starts with { and ends with }
        # This handles cases where there's explanation text before/after
        brace_start = text.find('{')
        if brace_start != -1:
            # Find matching closing brace by counting braces
            brace_count = 0
            for i, char in enumerate(text[brace_start:], start=brace_start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_candidate = text[brace_start:i + 1]
                        try:
                            return json.loads(json_candidate)
                        except json.JSONDecodeError:
                            pass
                        break

        # All strategies failed - raise with helpful context
        preview = text[:500] + "..." if len(text) > 500 else text
        raise json.JSONDecodeError(
            f"Failed to extract JSON from LLM response. "
            f"Response preview: {preview}",
            text,
            0
        )

    # Keywords that indicate a task requires manual/human intervention
    MANUAL_KEYWORDS = [
        "manually test",
        "manual test",
        "visual inspection",
        "verify on simulator",
        "verify on emulator",
        "user acceptance",
        "qa review",
        "human review",
        "manually verify",
        "visual verification",
        "manual verification",
        "ui review",
        "ux review",
        "demo to",
        "present to",
    ]

    def _detect_automation_type(self, issue_body: str, issue_title: str) -> str:
        """
        Detect if an issue requires manual work based on keywords.

        Args:
            issue_body: The issue body/description text.
            issue_title: The issue title text.

        Returns:
            "manual" if keywords indicate human intervention required,
            "automated" otherwise.
        """
        combined = (issue_body + " " + issue_title).lower()
        for keyword in self.MANUAL_KEYWORDS:
            if keyword in combined:
                return "manual"
        return "automated"

    def _validate_issues(self, data: dict[str, Any]) -> list[str]:
        """
        Validate the issues data structure.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        if "issues" not in data:
            errors.append("Missing 'issues' field in response")
            return errors

        issues = data["issues"]
        if not isinstance(issues, list):
            errors.append("'issues' must be a list")
            return errors

        required_fields = ["title", "body", "labels", "estimated_size", "dependencies", "order"]
        valid_automation_types = {"automated", "manual"}

        for i, issue in enumerate(issues):
            for field in required_fields:
                if field not in issue:
                    errors.append(f"Issue {i + 1} missing required field: {field}")

            # Validate automation_type if present
            auto_type = issue.get("automation_type")
            if auto_type and auto_type not in valid_automation_types:
                errors.append(f"Issue {i + 1} invalid automation_type: {auto_type}")

        return errors

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Generate GitHub issues from an engineering spec.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)

        Returns:
            AgentResult with:
                - success: True if issues were generated
                - output: Dict with issues_path, issues list, and count
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        self._log("issue_creator_start", {"feature_id": feature_id})
        self.checkpoint("started")

        # Check if spec-final.md exists
        spec_path = self._get_spec_path(feature_id)
        if not file_exists(spec_path):
            error = f"Spec not found at {spec_path}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Read spec content
        try:
            spec_content = read_file(spec_path)
        except Exception as e:
            error = f"Failed to read spec: {e}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("issue_creator_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("spec_loaded")

        # Build prompt and invoke Claude
        prompt = self._build_prompt(feature_id, spec_content)

        try:
            # Get allowed tools for IssueCreatorAgent
            from swarm_attack.agents.tool_sets import get_tools_for_agent
            allowed_tools = get_tools_for_agent("IssueCreatorAgent")

            # Use max_turns=1 to ensure single-turn response
            result = self.llm.run(
                prompt,
                allowed_tools=allowed_tools,
                max_turns=1,
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Parse JSON response
        try:
            issues_data = self._parse_json_response(result.text)
        except json.JSONDecodeError as e:
            error = f"Failed to parse JSON response: {e}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Validate issues structure
        validation_errors = self._validate_issues(issues_data)
        if validation_errors:
            error = f"Invalid issues data: {'; '.join(validation_errors)}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        # Ensure feature_id and generated_at are set
        if "feature_id" not in issues_data:
            issues_data["feature_id"] = feature_id
        if "generated_at" not in issues_data:
            issues_data["generated_at"] = (
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )

        # Post-process: ensure automation_type is set for all issues
        # Use keyword detection as fallback if LLM didn't provide it
        for issue in issues_data.get("issues", []):
            if "automation_type" not in issue:
                issue["automation_type"] = self._detect_automation_type(
                    issue.get("body", ""),
                    issue.get("title", ""),
                )

        # Write issues.json
        issues_path = self._get_issues_path(feature_id)
        try:
            ensure_dir(issues_path.parent)
            safe_write(issues_path, json.dumps(issues_data, indent=2))
        except Exception as e:
            error = f"Failed to write issues.json: {e}"
            self._log("issue_creator_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("issues_written", cost_usd=0)

        # Success
        issues_list = issues_data["issues"]
        self._log(
            "issue_creator_complete",
            {
                "feature_id": feature_id,
                "issues_path": str(issues_path),
                "issue_count": len(issues_list),
                "cost_usd": cost,
            },
        )

        # AC 3.1: Emit ISSUE_CREATED event after writing issues.json
        self._emit_event(
            event_type=EventType.ISSUE_CREATED,
            feature_id=feature_id,
            payload={
                "issue_count": len(issues_list),
                "output_path": str(issues_path),
            },
        )

        return AgentResult.success_result(
            output={
                "issues_path": str(issues_path),
                "issues": issues_list,
                "count": len(issues_list),
            },
            cost_usd=cost,
        )
