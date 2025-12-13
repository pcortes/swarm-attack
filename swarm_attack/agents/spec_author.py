"""
Spec Author Agent for Feature Swarm.

This agent reads a PRD and generates an engineering specification draft
using the feature-spec-author skill.
"""

from __future__ import annotations

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


class SpecAuthorAgent(BaseAgent):
    """
    Agent that generates engineering specs from PRDs.

    Reads a PRD from .claude/prds/<feature>.md and generates an engineering
    specification draft at specs/<feature>/spec-draft.md.
    """

    name = "spec_author"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """Initialize the Spec Author agent."""
        super().__init__(config, logger, llm_runner, state_store)
        self._skill_prompt: Optional[str] = None

    def _get_prd_path(self, feature_id: str) -> Path:
        """Get the path to the PRD file."""
        return Path(self.config.repo_root) / ".claude" / "prds" / f"{feature_id}.md"

    def _get_spec_dir(self, feature_id: str) -> Path:
        """Get the spec output directory."""
        return self.config.specs_path / feature_id

    def _get_spec_draft_path(self, feature_id: str) -> Path:
        """Get the path to the spec draft file."""
        return self._get_spec_dir(feature_id) / "spec-draft.md"

    def _load_skill_prompt(self) -> str:
        """Load and cache the skill prompt."""
        if self._skill_prompt is None:
            self._skill_prompt = self.load_skill("feature-spec-author")
        return self._skill_prompt

    def _build_prompt(self, feature_id: str, prd_content: str) -> str:
        """Build the full prompt for Claude."""
        skill_prompt = self._load_skill_prompt()

        return f"""{skill_prompt}

---

## Context for This Task

**Feature ID:** {feature_id}

**PRD Content:**

```markdown
{prd_content}
```

**Output Path:** specs/{feature_id}/spec-draft.md

---

## Your Task

Generate a comprehensive engineering specification based on the PRD above.
Follow the output format specified in the skill instructions.
Write the complete spec - do not abbreviate or use placeholders.
"""

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Generate an engineering spec from a PRD.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)

        Returns:
            AgentResult with:
                - success: True if spec was generated
                - output: Dict with spec_path and content preview
                - errors: List of any errors encountered
                - cost_usd: Cost of the LLM invocation
        """
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        self._log("spec_author_start", {"feature_id": feature_id})
        self.checkpoint("started")

        # Check if PRD exists
        prd_path = self._get_prd_path(feature_id)
        if not file_exists(prd_path):
            error = f"PRD not found at {prd_path}"
            self._log("spec_author_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Read PRD content
        try:
            prd_content = read_file(prd_path)
        except Exception as e:
            error = f"Failed to read PRD: {e}"
            self._log("spec_author_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        # Load skill prompt
        try:
            self._load_skill_prompt()
        except SkillNotFoundError as e:
            self._log("spec_author_error", {"error": str(e)}, level="error")
            return AgentResult.failure_result(str(e))

        self.checkpoint("prd_loaded")

        # Build prompt and invoke Claude
        prompt = self._build_prompt(feature_id, prd_content)

        try:
            # Use a higher max_turns for comprehensive PRDs that require
            # more exploration and spec writing
            result = self.llm.run(
                prompt,
                allowed_tools=["Read", "Glob", "Write"],
                max_turns=25,  # Comprehensive PRDs need many turns for exploration + spec writing
                timeout=self.config.spec_debate.timeout_seconds,  # 15 min default for large specs
            )
            cost = result.total_cost_usd
        except ClaudeTimeoutError as e:
            error = f"Claude timed out: {e}"
            self._log("spec_author_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)
        except ClaudeInvocationError as e:
            error = f"Claude invocation failed: {e}"
            self._log("spec_author_error", {"error": error}, level="error")
            return AgentResult.failure_result(error)

        self.checkpoint("llm_complete", cost_usd=cost)

        # Check if Claude already wrote the spec file using the Write tool
        spec_dir = self._get_spec_dir(feature_id)
        spec_path = self._get_spec_draft_path(feature_id)
        spec_content = ""

        try:
            ensure_dir(spec_dir)

            # If Claude wrote the file via Write tool, use that content
            # Otherwise, fall back to result.text
            if file_exists(spec_path):
                existing_content = read_file(spec_path)
                if existing_content and len(existing_content.strip()) > 50:
                    # Claude already wrote meaningful content, use it
                    spec_content = existing_content
                    self._log("spec_author_using_written_file", {
                        "spec_path": str(spec_path),
                        "content_length": len(spec_content),
                    })
                else:
                    # File exists but is empty/too short, use result.text
                    spec_content = result.text
                    if spec_content:
                        safe_write(spec_path, spec_content)
            else:
                # File doesn't exist yet, write result.text
                spec_content = result.text
                if spec_content:
                    safe_write(spec_path, spec_content)

            # Verify we have content
            if not spec_content or len(spec_content.strip()) < 50:
                error = "Generated spec is too short or empty"
                self._log("spec_author_error", {"error": error}, level="error")
                return AgentResult.failure_result(error, cost_usd=cost)

        except Exception as e:
            error = f"Failed to write spec: {e}"
            self._log("spec_author_error", {"error": error}, level="error")
            return AgentResult.failure_result(error, cost_usd=cost)

        self.checkpoint("spec_written", cost_usd=0)

        # Success
        self._log(
            "spec_author_complete",
            {
                "feature_id": feature_id,
                "spec_path": str(spec_path),
                "cost_usd": cost,
            },
        )

        return AgentResult.success_result(
            output={
                "spec_path": str(spec_path),
                "prd_path": str(prd_path),
                "content_preview": spec_content[:500] + "..."
                if len(spec_content) > 500
                else spec_content,
            },
            cost_usd=cost,
        )
