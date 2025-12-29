"""
Universal Context Builder for agent-type-specific context profiles.

This module provides a thin wrapper layer that tailors context for each agent type
before execution. It delegates to existing ContextBuilder and QAContextBuilder
infrastructure.

Key components:
- AGENT_CONTEXT_PROFILES: Defines what context each agent type needs
- AgentContext: Dataclass holding tailored context for an agent
- UniversalContextBuilder: Wrapper that dispatches to existing builders
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.context_builder import ContextBuilder

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.state_store import StateStore


# Agent context profiles define what context each agent type needs
AGENT_CONTEXT_PROFILES: dict[str, dict[str, Any]] = {
    # Coding agents need full code context
    "coder": {
        "include": [
            "project_instructions",
            "module_registry",
            "completed_summaries",
            "dependencies",
            "related_tests",
        ],
        "depth": "full_source",
        "max_tokens": 15000,
    },
    # Spec agents need architectural context
    "spec_author": {
        "include": [
            "project_instructions",
            "architecture_overview",
            "existing_modules",
            "conventions",
            "tech_stack",
        ],
        "depth": "summary",
        "max_tokens": 5000,
    },
    "spec_critic": {
        "include": [
            "project_instructions",
            "review_guidelines",
            "past_feedback",
            "quality_standards",
        ],
        "depth": "summary",
        "max_tokens": 3000,
    },
    "spec_moderator": {
        "include": [
            "project_instructions",
            "review_guidelines",
            "quality_standards",
        ],
        "depth": "summary",
        "max_tokens": 3000,
    },
    # Issue agents need backlog context
    "issue_creator": {
        "include": [
            "project_instructions",
            "existing_issues",
            "module_registry",
            "naming_conventions",
        ],
        "depth": "compact",
        "max_tokens": 4000,
    },
    # QA agents need test context
    "bug_researcher": {
        "include": [
            "project_instructions",
            "test_structure",
            "recent_changes",
            "failure_history",
        ],
        "depth": "full_source",
        "max_tokens": 10000,
    },
    "root_cause_analyzer": {
        "include": [
            "project_instructions",
            "test_structure",
            "module_registry",
        ],
        "depth": "full_source",
        "max_tokens": 8000,
    },
    "fix_planner": {
        "include": [
            "project_instructions",
            "module_registry",
            "completed_summaries",
        ],
        "depth": "summary",
        "max_tokens": 5000,
    },
    "verifier": {
        "include": [
            "project_instructions",
            "test_patterns",
            "coverage_gaps",
            "regression_tests",
        ],
        "depth": "compact",
        "max_tokens": 3000,
    },
    # Complexity gate needs minimal context
    "complexity_gate": {
        "include": [
            "project_instructions",
        ],
        "depth": "compact",
        "max_tokens": 2000,
    },
}


@dataclass
class AgentContext:
    """
    Context tailored for a specific agent type.

    Contains all the context an agent needs for execution, with fields
    populated based on the agent's profile requirements.
    """

    agent_type: str
    built_at: datetime
    project_instructions: Optional[str] = None
    module_registry: Optional[str] = None
    completed_summaries: Optional[str] = None
    test_structure: Optional[str] = None
    architecture_overview: Optional[str] = None
    token_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_type": self.agent_type,
            "built_at": self.built_at.isoformat(),
            "project_instructions": self.project_instructions,
            "module_registry": self.module_registry,
            "completed_summaries": self.completed_summaries,
            "test_structure": self.test_structure,
            "architecture_overview": self.architecture_overview,
            "token_count": self.token_count,
        }


class UniversalContextBuilder:
    """
    Wrapper that provides agent-type-specific context.

    Delegates to existing ContextBuilder and QAContextBuilder based on
    the agent type's profile requirements.
    """

    def __init__(
        self,
        config: SwarmConfig,
        state_store: Optional[StateStore] = None,
    ) -> None:
        """
        Initialize the universal context builder.

        Args:
            config: SwarmConfig with repo_root path.
            state_store: Optional StateStore for loading summaries and registry.
        """
        self._config = config
        self._state_store = state_store
        self._context_builder = ContextBuilder(config, state_store)

    def build_context_for_agent(
        self,
        agent_type: str,
        feature_id: str,
        issue_number: Optional[int] = None,
    ) -> AgentContext:
        """
        Build tailored context for a specific agent type.

        This runs BEFORE the agent starts work, gathering all necessary
        context based on the agent's profile.

        Args:
            agent_type: Type of agent (e.g., "coder", "spec_author").
            feature_id: The feature identifier.
            issue_number: Optional issue number for additional context.

        Returns:
            AgentContext populated based on the agent's profile.
        """
        profile = AGENT_CONTEXT_PROFILES.get(agent_type, {})
        include = profile.get("include", ["project_instructions"])
        depth = profile.get("depth", "summary")
        max_tokens = profile.get("max_tokens", 5000)

        context = AgentContext(
            agent_type=agent_type,
            built_at=datetime.now(),
        )

        # Project instructions (most agents need this)
        if "project_instructions" in include:
            context.project_instructions = self._context_builder.get_project_instructions()

        # Module registry (coding and issue agents)
        if "module_registry" in include and self._state_store is not None:
            registry = self._state_store.get_module_registry(feature_id)
            if registry and registry.get("modules"):
                if depth == "full_source":
                    context.module_registry = (
                        self._context_builder.format_module_registry_with_source(registry)
                    )
                else:
                    context.module_registry = (
                        self._context_builder.format_module_registry_compact(registry)
                    )

        # Completed summaries (coding agents)
        if "completed_summaries" in include:
            summaries = self._context_builder.get_completed_summaries(feature_id)
            if summaries:
                context.completed_summaries = (
                    self._context_builder.format_completed_summaries_for_prompt(feature_id)
                )

        # Test structure (QA agents)
        if "test_structure" in include:
            context.test_structure = self._get_test_structure()

        # Architecture overview (spec agents)
        if "architecture_overview" in include:
            context.architecture_overview = self._get_architecture_overview()

        # Truncate to token budget
        context = self._truncate_to_budget(context, max_tokens)

        return context

    def _get_test_structure(self) -> Optional[str]:
        """
        Get test directory structure for QA agents.

        Returns:
            Formatted string describing test structure, or None.
        """
        from pathlib import Path

        tests_dir = Path(self._config.repo_root) / "tests"
        if not tests_dir.exists():
            return None

        lines = ["## Test Structure\n"]

        # List top-level test directories
        for item in sorted(tests_dir.iterdir()):
            if item.is_dir() and not item.name.startswith("__"):
                test_files = list(item.glob("test_*.py"))
                lines.append(f"- **{item.name}/**: {len(test_files)} test files")
            elif item.is_file() and item.name.startswith("test_"):
                lines.append(f"- {item.name}")

        return "\n".join(lines) if len(lines) > 1 else None

    def _get_architecture_overview(self) -> Optional[str]:
        """
        Get high-level architecture overview for spec agents.

        Returns:
            Formatted architecture overview, or None.
        """
        from pathlib import Path

        # Look for architecture documentation
        candidates = [
            "docs/ARCHITECTURE.md",
            "docs/architecture.md",
            "ARCHITECTURE.md",
            "README.md",
        ]

        for candidate in candidates:
            path = Path(self._config.repo_root) / candidate
            if path.exists():
                content = path.read_text()
                # Truncate if too long
                if len(content) > 3000:
                    content = content[:3000] + "\n\n... (truncated)"
                return f"## Architecture Overview (from {candidate})\n\n{content}"

        return None

    def _truncate_to_budget(
        self, context: AgentContext, max_tokens: int
    ) -> AgentContext:
        """
        Truncate context fields to stay within token budget.

        Uses proportional truncation, prioritizing project_instructions.

        Args:
            context: AgentContext to truncate.
            max_tokens: Maximum allowed tokens.

        Returns:
            Truncated AgentContext.
        """
        # Collect all text fields with their priorities (lower = higher priority)
        fields = [
            ("project_instructions", context.project_instructions, 1),
            ("module_registry", context.module_registry, 2),
            ("completed_summaries", context.completed_summaries, 3),
            ("test_structure", context.test_structure, 4),
            ("architecture_overview", context.architecture_overview, 5),
        ]

        # Calculate current total
        total_chars = sum(len(v or "") for _, v, _ in fields)
        context.token_count = total_chars // 4

        if context.token_count <= max_tokens:
            return context

        # Need to truncate - calculate max chars
        max_chars = max_tokens * 4

        # Sort by priority (highest priority first for preservation)
        fields_sorted = sorted(fields, key=lambda x: x[2])

        # Allocate proportionally but preserve high-priority fields
        remaining_chars = max_chars
        allocated: dict[str, str] = {}

        for name, value, priority in fields_sorted:
            if not value:
                allocated[name] = ""
                continue

            # Higher priority fields get more allocation
            if priority <= 2:
                # Project instructions and module registry get up to 40% each
                field_max = int(max_chars * 0.4)
            else:
                # Other fields share remaining space
                field_max = int(max_chars * 0.2)

            # Don't exceed remaining or field max
            field_budget = min(remaining_chars, field_max, len(value))

            if len(value) <= field_budget:
                allocated[name] = value
            else:
                # Truncate at a newline boundary if possible
                truncated = value[:field_budget]
                last_newline = truncated.rfind("\n")
                if last_newline > field_budget // 2:
                    truncated = truncated[:last_newline]
                allocated[name] = truncated + "\n\n... (truncated)"

            remaining_chars -= len(allocated[name])

        # Apply truncated values
        context.project_instructions = allocated.get("project_instructions") or None
        context.module_registry = allocated.get("module_registry") or None
        context.completed_summaries = allocated.get("completed_summaries") or None
        context.test_structure = allocated.get("test_structure") or None
        context.architecture_overview = allocated.get("architecture_overview") or None

        # Recalculate token count
        total_chars = sum(
            len(v or "")
            for v in [
                context.project_instructions,
                context.module_registry,
                context.completed_summaries,
                context.test_structure,
                context.architecture_overview,
            ]
        )
        context.token_count = total_chars // 4

        return context
