"""
Standard tool sets for Swarm Attack agents.

Defines consistent tool access across all agents, ensuring every agent
that makes code decisions can research the codebase.
"""
from __future__ import annotations

from enum import Enum
from typing import List


class ToolSet(Enum):
    """Standard tool sets for different agent types."""

    # Minimal research - can read and search
    RESEARCH_ONLY = ["Read", "Glob", "Grep"]

    # Research + can run tests/commands
    RESEARCH_WITH_BASH = ["Read", "Glob", "Grep", "Bash"]

    # Research + can write files
    RESEARCH_WITH_WRITE = ["Read", "Glob", "Grep", "Write"]

    # Full capability
    FULL = ["Read", "Glob", "Grep", "Bash", "Write", "Edit"]

    # No tools (legacy - deprecated)
    NONE = []


# Mapping of agent names to their required tool sets
AGENT_TOOL_REQUIREMENTS: dict[str, ToolSet] = {
    # Implementation agents
    "CoderAgent": ToolSet.RESEARCH_ONLY,
    "VerifierAgent": ToolSet.RESEARCH_ONLY,

    # Planning agents - NOW WITH RESEARCH (was NONE)
    "IssueCreatorAgent": ToolSet.RESEARCH_ONLY,
    "ComplexityGateAgent": ToolSet.RESEARCH_ONLY,

    # Spec agents
    "SpecAuthorAgent": ToolSet.RESEARCH_WITH_WRITE,
    "SpecModeratorAgent": ToolSet.RESEARCH_ONLY,

    # Bug agents
    "BugResearcherAgent": ToolSet.RESEARCH_WITH_BASH,
    "RootCauseAnalyzerAgent": ToolSet.RESEARCH_ONLY,
    "FixPlannerAgent": ToolSet.RESEARCH_ONLY,
    "BugModeratorAgent": ToolSet.RESEARCH_ONLY,

    # Support agents
    "SummarizerAgent": ToolSet.RESEARCH_ONLY,
    "RecoveryAgent": ToolSet.RESEARCH_ONLY,
    "IssueSplitterAgent": ToolSet.RESEARCH_ONLY,
}


def get_tools_for_agent(agent_name: str) -> List[str]:
    """
    Get required tools for an agent.

    Args:
        agent_name: Name of the agent class (e.g., "CoderAgent")

    Returns:
        List of tool names. Defaults to RESEARCH_ONLY if agent not in mapping.
    """
    tool_set = AGENT_TOOL_REQUIREMENTS.get(agent_name, ToolSet.RESEARCH_ONLY)
    return tool_set.value
