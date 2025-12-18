"""
Implementation Summarizer Agent for Feature Swarm.

This agent generates structured summaries of completed issue implementations.
These summaries are used for context handoff to subsequent issues, helping
prevent schema drift by documenting what classes exist and how to use them.

The summaries are:
1. Added to the completed GitHub issue (Implementation Summary section)
2. Propagated to dependent GitHub issues (Context from Dependencies section)
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import AgentResult, BaseAgent, SkillNotFoundError

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.llm_clients import ClaudeCliRunner
    from swarm_attack.logger import SwarmLogger
    from swarm_attack.models import IssueOutput


class SummarizerAgent(BaseAgent):
    """
    Agent that generates implementation summaries after issue completion.

    The summary includes:
    - Files created/modified with their purposes
    - Classes defined with fields, methods, and import statements
    - Usage patterns for common operations
    - Integration notes for downstream issues

    These summaries are injected into GitHub issues to provide context
    for subsequent issues that depend on this one.
    """

    name = "summarizer"

    def __init__(
        self,
        config: SwarmConfig,
        logger: Optional[SwarmLogger] = None,
        llm_runner: Optional[ClaudeCliRunner] = None,
    ) -> None:
        """Initialize the Summarizer agent."""
        super().__init__(config, logger, llm_runner)

    def _get_git_diff(self, commit_hash: Optional[str] = None) -> str:
        """
        Get git diff for recent changes.

        Args:
            commit_hash: Optional specific commit to diff against HEAD~1.
                        If None, diffs staged + unstaged changes.

        Returns:
            Git diff output as string.
        """
        try:
            if commit_hash:
                # Diff the specific commit against its parent
                result = subprocess.run(
                    ["git", "show", commit_hash, "--stat", "--patch"],
                    cwd=str(self.config.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            else:
                # Get diff of staged and unstaged changes
                result = subprocess.run(
                    ["git", "diff", "HEAD"],
                    cwd=str(self.config.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            return result.stdout[:10000]  # Truncate for token limits

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _parse_summary_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse LLM response for structured summary.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Parsed summary dictionary, or error dict if parsing fails.
        """
        # Try to extract JSON from the response
        # Handle cases where LLM wraps JSON in markdown code blocks
        json_match = re.search(
            r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL
        )
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[^{}]*"files_summary"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Try to find any JSON object
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    json_str = response_text[start:end + 1]
                else:
                    json_str = response_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse LLM response as JSON",
                "raw_response": response_text[:1000],
            }

    def _format_summary_for_github(self, summary: dict[str, Any]) -> str:
        """
        Format summary as markdown for GitHub issue comment.

        Args:
            summary: Parsed summary dictionary from LLM.

        Returns:
            Formatted markdown string.
        """
        lines = []

        # Files section
        files_summary = summary.get("files_summary", [])
        if files_summary:
            lines.append("### Files Created/Modified")
            for file_info in files_summary:
                path = file_info.get("path", "unknown")
                purpose = file_info.get("purpose", "")
                lines.append(f"- `{path}`: {purpose}")
            lines.append("")

        # Classes section
        classes_defined = summary.get("classes_defined", {})
        if classes_defined:
            lines.append("### Classes Defined")
            for file_path, classes in classes_defined.items():
                for cls in classes:
                    name = cls.get("name", "Unknown")
                    purpose = cls.get("purpose", "")
                    import_stmt = cls.get("import_statement", "")

                    lines.append(f"**{name}** (`{file_path}`)")
                    if purpose:
                        lines.append(f"> {purpose}")
                    if import_stmt:
                        lines.append(f"> Import: `{import_stmt}`")

                    key_fields = cls.get("key_fields", [])
                    if key_fields:
                        lines.append(f"> Fields: {', '.join(key_fields[:5])}")

                    key_methods = cls.get("key_methods", [])
                    if key_methods:
                        lines.append(f"> Methods: {', '.join(key_methods[:5])}")

                    lines.append("")

        # Usage patterns
        usage_patterns = summary.get("usage_patterns", [])
        if usage_patterns:
            lines.append("### Usage Patterns")
            for pattern in usage_patterns[:5]:
                lines.append(f"- {pattern}")
            lines.append("")

        # Integration notes
        integration_notes = summary.get("integration_notes", [])
        if integration_notes:
            lines.append("### Integration Notes")
            for note in integration_notes[:3]:
                lines.append(f"- {note}")
            lines.append("")

        return "\n".join(lines)

    def _format_context_for_dependent(
        self,
        source_issue: int,
        source_title: str,
        summary: dict[str, Any],
    ) -> str:
        """
        Format summary as compact context for dependent issues.

        This is a more condensed version focused on what dependents need:
        - Import statements
        - Key classes and how to use them

        Args:
            source_issue: Issue number that was completed.
            source_title: Title of the completed issue.
            summary: Parsed summary dictionary.

        Returns:
            Compact markdown context block.
        """
        lines = [
            f"### From Issue #{source_issue}: {source_title}",
            "",
        ]

        # Build import block
        imports = []
        classes_defined = summary.get("classes_defined", {})
        for file_path, classes in classes_defined.items():
            for cls in classes:
                import_stmt = cls.get("import_statement", "")
                if import_stmt:
                    imports.append(import_stmt)

        if imports:
            lines.append("**Imports:**")
            lines.append("```python")
            for imp in imports[:10]:
                lines.append(imp)
            lines.append("```")
            lines.append("")

        # Key classes with brief description
        for file_path, classes in classes_defined.items():
            for cls in classes:
                name = cls.get("name", "Unknown")
                purpose = cls.get("purpose", "")
                key_fields = cls.get("key_fields", [])

                if purpose:
                    lines.append(f"- **{name}**: {purpose}")
                    if key_fields:
                        lines.append(f"  - Fields: {', '.join(key_fields[:5])}")

        # Usage patterns (condensed)
        usage_patterns = summary.get("usage_patterns", [])
        if usage_patterns:
            lines.append("")
            lines.append("**Usage:**")
            for pattern in usage_patterns[:3]:
                lines.append(f"- {pattern}")

        return "\n".join(lines)

    def run(self, context: dict[str, Any]) -> AgentResult:
        """
        Generate implementation summary for a completed issue.

        Args:
            context: Dictionary containing:
                - feature_id: The feature identifier (required)
                - issue_number: The issue that was completed (required)
                - issue_title: Title of the completed issue
                - issue_body: Body/description of the issue
                - commit_hash: Optional commit hash for this implementation
                - files_created: List of files created
                - classes_defined: Dict of file -> [class names]
                - issue_outputs: Optional IssueOutput object

        Returns:
            AgentResult with:
                - success: True if summary was generated
                - output: Dict with:
                    - summary: Parsed summary dict
                    - github_markdown: Formatted markdown for GitHub
                    - context_markdown: Compact context for dependents
                - errors: List of any errors encountered
                - cost_usd: LLM cost
        """
        # Validate context
        feature_id = context.get("feature_id")
        if not feature_id:
            return AgentResult.failure_result("Missing required context: feature_id")

        issue_number = context.get("issue_number")
        if issue_number is None:
            return AgentResult.failure_result("Missing required context: issue_number")

        issue_title = context.get("issue_title", f"Issue #{issue_number}")
        issue_body = context.get("issue_body", "")
        commit_hash = context.get("commit_hash")
        files_created = context.get("files_created", [])
        classes_defined = context.get("classes_defined", {})

        self._log("summarizer_start", {
            "feature_id": feature_id,
            "issue_number": issue_number,
            "files_count": len(files_created),
        })
        self.checkpoint("started")

        # Build prompt for LLM
        try:
            skill_prompt, metadata = self.load_skill_with_metadata("summarizer")
            allowed_tools = self.get_allowed_tools_from_metadata(metadata)
        except SkillNotFoundError:
            # Fall back to inline prompt
            skill_prompt = self._get_fallback_prompt()
            allowed_tools = ["Read", "Glob"]

        # Get diff for context
        diff = self._get_git_diff(commit_hash)

        # Build file list for context
        files_context = "\n".join(f"- {f}" for f in files_created) if files_created else "No files tracked"

        # Build classes context
        classes_context = ""
        if classes_defined:
            for file_path, class_names in classes_defined.items():
                classes_context += f"\n{file_path}: {', '.join(class_names)}"
        else:
            classes_context = "No classes tracked"

        prompt = f"""{skill_prompt}

## Issue Information

**Issue #{issue_number}**: {issue_title}

{issue_body[:2000] if issue_body else "No description provided"}

## Files Created/Modified

{files_context}

## Classes Defined

{classes_context}

## Git Diff (truncated)

```diff
{diff[:5000] if diff else "No diff available"}
```

## Your Task

Generate a structured JSON summary of this implementation following the format in the skill instructions.
Focus on what subsequent issues need to know to USE these classes correctly.
"""

        self._log("summarizer_invoking_llm", {
            "feature_id": feature_id,
            "issue_number": issue_number,
        })

        try:
            result = self.llm.run(
                prompt=prompt,
                allowed_tools=allowed_tools,
            )

            self.checkpoint("llm_complete", cost_usd=result.total_cost_usd)

            # Parse the response
            summary = self._parse_summary_response(result.text)

            if "error" in summary:
                self._log("summarizer_parse_error", {
                    "feature_id": feature_id,
                    "issue_number": issue_number,
                    "error": summary.get("error"),
                }, level="warning")
                # Use fallback summary based on tracked data
                summary = self._build_fallback_summary(
                    files_created, classes_defined
                )

            # Format for GitHub
            github_markdown = self._format_summary_for_github(summary)
            context_markdown = self._format_context_for_dependent(
                issue_number, issue_title, summary
            )

            self._log("summarizer_complete", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "cost_usd": self._total_cost,
            })

            return AgentResult.success_result(
                output={
                    "summary": summary,
                    "github_markdown": github_markdown,
                    "context_markdown": context_markdown,
                    "issue_number": issue_number,
                    "issue_title": issue_title,
                },
                cost_usd=self._total_cost,
            )

        except Exception as e:
            self._log("summarizer_error", {
                "feature_id": feature_id,
                "issue_number": issue_number,
                "error": str(e),
            }, level="error")

            # Return fallback summary on error
            summary = self._build_fallback_summary(files_created, classes_defined)
            github_markdown = self._format_summary_for_github(summary)
            context_markdown = self._format_context_for_dependent(
                issue_number, issue_title, summary
            )

            return AgentResult.success_result(
                output={
                    "summary": summary,
                    "github_markdown": github_markdown,
                    "context_markdown": context_markdown,
                    "issue_number": issue_number,
                    "issue_title": issue_title,
                    "fallback": True,
                },
                cost_usd=self._total_cost,
            )

    def _build_fallback_summary(
        self,
        files_created: list[str],
        classes_defined: dict[str, list[str]],
    ) -> dict[str, Any]:
        """
        Build a basic summary from tracked file/class data without LLM.

        Used when LLM fails or response can't be parsed.

        Args:
            files_created: List of file paths created.
            classes_defined: Dict of file -> [class names].

        Returns:
            Basic summary dictionary.
        """
        files_summary = [
            {"path": f, "purpose": "Implementation file"}
            for f in files_created
        ]

        classes_summary = {}
        for file_path, class_names in classes_defined.items():
            module_path = file_path.replace("/", ".").replace(".py", "")
            classes_summary[file_path] = [
                {
                    "name": cls,
                    "purpose": f"Class defined in {file_path}",
                    "key_fields": [],
                    "key_methods": [],
                    "import_statement": f"from {module_path} import {cls}",
                }
                for cls in class_names
            ]

        return {
            "files_summary": files_summary,
            "classes_defined": classes_summary,
            "usage_patterns": [],
            "integration_notes": ["See source files for usage details"],
        }

    def _get_fallback_prompt(self) -> str:
        """Return inline prompt when skill file not found."""
        return """You are an implementation summarizer. Analyze the completed issue implementation and generate a JSON summary.

Output ONLY valid JSON:

{
  "files_summary": [{"path": "...", "purpose": "..."}],
  "classes_defined": {
    "path/file.py": [
      {
        "name": "ClassName",
        "purpose": "...",
        "key_fields": ["field: type"],
        "key_methods": ["method()"],
        "import_statement": "from module import ClassName"
      }
    ]
  },
  "usage_patterns": ["How to use the classes"],
  "integration_notes": ["Integration guidance"]
}

Be concise. Focus on what other code needs to know to USE these classes."""
