"""
Bug Fixer Agent for applying fix plans intelligently.

This agent uses Claude CLI to apply fix plans instead of dumb string replacement.
It reads files first, uses the Edit tool for changes, and validates syntax.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError

if TYPE_CHECKING:
    from swarm_attack.bug_models import FixPlan
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.state_store import StateStore
    from swarm_attack.memory.store import MemoryStore


@dataclass
class BugFixerResult:
    """Result from the bug fixer agent."""

    success: bool
    files_changed: list[str] = field(default_factory=list)
    syntax_verified: bool = False
    error: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "files_changed": self.files_changed,
            "syntax_verified": self.syntax_verified,
            "error": self.error,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BugFixerResult:
        """Create from dictionary."""
        return cls(
            success=data.get("success", False),
            files_changed=data.get("files_changed", []),
            syntax_verified=data.get("syntax_verified", False),
            error=data.get("error", ""),
            notes=data.get("notes", ""),
        )


class BugFixerAgent(BaseAgent):
    """
    Agent that applies fix plans using Claude CLI.

    Unlike the old string-replace approach, this agent:
    1. Reads files before editing
    2. Uses the Edit tool for changes
    3. Ensures proper formatting (blank lines, indentation)
    4. Validates syntax after changes
    """

    name = "bug_fixer"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
        memory_store: Optional["MemoryStore"] = None,
    ) -> None:
        """Initialize the Bug Fixer agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None
        self._memory_store = memory_store

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("bug-fixer")
        return self._skill_prompt

    def _format_fix_plan_markdown(self, fix_plan: FixPlan) -> str:
        """Format the fix plan as markdown for the prompt."""
        lines = [
            f"## Summary",
            f"{fix_plan.summary}",
            "",
            f"## Risk Level: {fix_plan.risk_level}",
            f"{fix_plan.risk_explanation}" if fix_plan.risk_explanation else "",
            "",
            "## File Changes",
            "",
        ]

        for i, change in enumerate(fix_plan.changes, 1):
            lines.append(f"### Change {i}: `{change.file_path}`")
            lines.append(f"**Type:** {change.change_type}")
            lines.append(f"**Explanation:** {change.explanation}")
            lines.append("")

            if change.current_code:
                lines.append("**Current Code:**")
                lines.append("```python")
                lines.append(change.current_code)
                lines.append("```")
                lines.append("")

            if change.proposed_code:
                lines.append("**Proposed Code:**")
                lines.append("```python")
                lines.append(change.proposed_code)
                lines.append("```")
                lines.append("")

        if fix_plan.test_cases:
            lines.append("## Test Cases to Verify")
            lines.append("")
            for tc in fix_plan.test_cases:
                lines.append(f"- **{tc.name}**: {tc.description}")
            lines.append("")

        return "\n".join(lines)

    def _build_prompt(self, fix_plan: FixPlan, bug_id: str) -> str:
        """Build the full prompt for Claude CLI."""
        skill_prompt = self._load_skill_prompt()
        fix_plan_markdown = self._format_fix_plan_markdown(fix_plan)

        # Replace the placeholder in the skill prompt
        prompt = skill_prompt.replace("{fix_plan_markdown}", fix_plan_markdown)

        # Add bug ID context
        prompt = f"## Bug ID: {bug_id}\n\n{prompt}"

        return prompt

    def _call_claude_cli(self, prompt: str) -> dict[str, Any]:
        """
        Call Claude CLI synchronously.

        Args:
            prompt: The prompt to send to Claude.

        Returns:
            Parsed JSON response dict from Claude CLI.

        Raises:
            RuntimeError: On non-zero exit code.
            subprocess.TimeoutExpired: On timeout.
            json.JSONDecodeError: On invalid JSON response.
        """
        result = subprocess.run(
            [
                "claude",
                "--print",
                "--output-format", "json",
                "-p", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(self.config.repo_root),
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        return json.loads(result.stdout)

    def _parse_result(self, response: dict[str, Any]) -> BugFixerResult:
        """
        Parse Claude CLI response into BugFixerResult.

        Args:
            response: Parsed JSON from Claude CLI.

        Returns:
            BugFixerResult with extracted data.
        """
        result_text = response.get("result", "")

        if not result_text:
            return BugFixerResult(
                success=False,
                error="Empty response from Claude CLI",
            )

        # Try to parse the result as JSON
        try:
            # The result might be the raw JSON or embedded in text
            result_data = json.loads(result_text)
            return BugFixerResult(
                success=result_data.get("success", False),
                files_changed=result_data.get("files_changed", []),
                syntax_verified=result_data.get("syntax_verified", False),
                error=result_data.get("error", ""),
                notes=result_data.get("notes", ""),
            )
        except json.JSONDecodeError:
            # Try to find JSON in the text
            import re
            json_match = re.search(r'\{[\s\S]*?"success"[\s\S]*?\}', result_text)
            if json_match:
                try:
                    result_data = json.loads(json_match.group())
                    return BugFixerResult(
                        success=result_data.get("success", False),
                        files_changed=result_data.get("files_changed", []),
                        syntax_verified=result_data.get("syntax_verified", False),
                        error=result_data.get("error", ""),
                        notes=result_data.get("notes", ""),
                    )
                except json.JSONDecodeError:
                    pass

            return BugFixerResult(
                success=False,
                error=f"Failed to parse JSON from response: {result_text[:200]}",
            )

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Apply a fix plan to the codebase.

        Args:
            context: Dictionary containing:
                - fix_plan: FixPlan object with changes to apply
                - bug_id: Bug identifier

        Returns:
            AgentResult with success/failure and files changed.
        """
        # Validate required context
        fix_plan = context.get("fix_plan")
        if fix_plan is None:
            return AgentResult.failure_result("Missing required context: fix_plan")

        bug_id = context.get("bug_id")
        if bug_id is None:
            return AgentResult.failure_result("Missing required context: bug_id")

        self._log("bug_fixer_start", {
            "bug_id": bug_id,
            "changes_count": len(fix_plan.changes),
        })

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            return AgentResult.failure_result(str(e))

        # Build and send prompt to Claude CLI
        prompt = self._build_prompt(fix_plan, bug_id)

        try:
            response = self._call_claude_cli(prompt)
        except subprocess.TimeoutExpired:
            return AgentResult.failure_result(
                f"Claude CLI timed out while applying fix for {bug_id}"
            )
        except RuntimeError as e:
            return AgentResult.failure_result(str(e))
        except json.JSONDecodeError as e:
            return AgentResult.failure_result(
                f"Invalid JSON response from Claude CLI: {e}"
            )

        # Parse result
        fixer_result = self._parse_result(response)

        self._log("bug_fixer_complete", {
            "bug_id": bug_id,
            "success": fixer_result.success,
            "files_changed": fixer_result.files_changed,
            "syntax_verified": fixer_result.syntax_verified,
        })

        if fixer_result.success:
            return AgentResult.success_result(
                output={
                    "files_changed": fixer_result.files_changed,
                    "syntax_verified": fixer_result.syntax_verified,
                    "notes": fixer_result.notes,
                },
            )
        else:
            return AgentResult.failure_result(
                fixer_result.error or "Fix application failed"
            )
