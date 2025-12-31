"""
AgentResearchMixin - Adds research capability to any agent.

Provides standardized research phase execution, context discovery,
and result formatting for LLM prompts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TypedDict


class DiscoveredContext(TypedDict):
    """Context discovered during research phase."""
    files_found: list[str]
    patterns_found: dict[str, list[str]]
    modules_read: list[str]
    classes_discovered: dict[str, list[str]]
    functions_discovered: dict[str, list[str]]
    existing_tests: list[str]
    dependencies: list[str]


@dataclass
class ResearchResult:
    """Result of research phase."""
    success: bool
    context: DiscoveredContext
    summary: str
    search_queries: list[str]
    error: Optional[str] = None


class AgentResearchMixin:
    """
    Mixin that adds research capabilities to any agent.

    Provides:
    - Standardized research phase execution
    - Context discovery and caching
    - Research result formatting for prompts
    """

    RESEARCH_TOOLS: list[str] = ["Read", "Glob", "Grep"]

    def __init__(self):
        self._research_cache: dict[str, ResearchResult] = {}

    def get_standard_research_patterns(self, feature_id: str) -> dict:
        """
        Get standard research patterns for a feature.

        Args:
            feature_id: Feature identifier

        Returns:
            Dict with search_patterns, grep_patterns, read_files
        """
        return {
            "search_patterns": [
                "swarm_attack/**/*.py",
                f"tests/**/*{feature_id}*.py" if feature_id else "tests/**/*.py",
                ".claude/skills/**/*.md",
            ],
            "grep_patterns": [
                r"class\s+\w+Agent",
                r"def\s+run\(",
                r"from swarm_attack",
            ],
            "read_files": [
                "CLAUDE.md",
                "swarm_attack/agents/base.py",
            ],
        }

    def format_research_for_prompt(self, result: ResearchResult) -> str:
        """
        Format research results for inclusion in agent prompt.

        Args:
            result: ResearchResult from research phase

        Returns:
            Formatted string suitable for LLM prompt
        """
        if not result.success or not result.context["files_found"]:
            return "## Research Results\n\nNo relevant files found during research."

        lines = ["## Research Results", ""]

        # Files found
        if result.context["files_found"]:
            lines.append("### Files Found")
            for f in result.context["files_found"][:20]:  # Limit to 20
                lines.append(f"- `{f}`")
            lines.append("")

        # Classes discovered
        if result.context["classes_discovered"]:
            lines.append("### Classes Discovered")
            for file, classes in result.context["classes_discovered"].items():
                for cls in classes:
                    lines.append(f"- `{cls}` in `{file}`")
            lines.append("")

        # Modules read
        if result.context["modules_read"]:
            lines.append("### Modules Read")
            for m in result.context["modules_read"]:
                lines.append(f"- `{m}`")
            lines.append("")

        # Summary
        if result.summary:
            lines.append("### Summary")
            lines.append(result.summary)
            lines.append("")

        return "\n".join(lines)

    def build_research_prompt(self, task_context: dict) -> str:
        """
        Build prompt for research phase.

        Args:
            task_context: Context about the task being researched

        Returns:
            Prompt string for research exploration
        """
        feature_id = task_context.get("feature_id", "")
        search_hints = task_context.get("search_hints", [])

        prompt_lines = [
            "# Research Phase",
            "",
            "Before proceeding, explore the codebase to understand existing patterns.",
            "",
            "## Your Task",
            "",
            "1. **Find relevant files** using Glob",
            "2. **Search for patterns** using Grep",
            "3. **Read key modules** to understand interfaces",
            "",
        ]

        if feature_id:
            prompt_lines.extend([
                f"## Feature Context: {feature_id}",
                "",
            ])

        if search_hints:
            prompt_lines.append("## Search Hints")
            for hint in search_hints:
                prompt_lines.append(f"- {hint}")
            prompt_lines.append("")

        prompt_lines.extend([
            "## Required Actions",
            "",
            "1. Glob 'swarm_attack/**/*.py' to find modules",
            "2. Grep for class definitions related to your task",
            "3. Read CLAUDE.md for project conventions",
            "4. Read base classes you'll be extending",
            "",
        ])

        return "\n".join(prompt_lines)
