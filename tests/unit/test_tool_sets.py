"""Unit tests for ToolSets and agent tool requirements.

TDD RED Phase - All tests should FAIL initially.
"""
import pytest

from swarm_attack.agents.tool_sets import (
    ToolSet,
    AGENT_TOOL_REQUIREMENTS,
    get_tools_for_agent,
)


class TestToolSetEnum:
    """Tests for ToolSet enum."""

    def test_research_only_has_read_glob_grep(self):
        """RESEARCH_ONLY should have Read, Glob, Grep."""
        assert ToolSet.RESEARCH_ONLY.value == ["Read", "Glob", "Grep"]

    def test_research_with_bash_includes_bash(self):
        """RESEARCH_WITH_BASH should include Bash."""
        tools = ToolSet.RESEARCH_WITH_BASH.value
        assert "Bash" in tools
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools

    def test_research_with_write_includes_write(self):
        """RESEARCH_WITH_WRITE should include Write."""
        tools = ToolSet.RESEARCH_WITH_WRITE.value
        assert "Write" in tools
        assert "Read" in tools

    def test_full_has_all_tools(self):
        """FULL should have all tools."""
        tools = ToolSet.FULL.value
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools
        assert "Bash" in tools
        assert "Write" in tools
        assert "Edit" in tools

    def test_none_is_empty_list(self):
        """NONE should be empty list (legacy)."""
        assert ToolSet.NONE.value == []


class TestAgentToolRequirements:
    """Tests for AGENT_TOOL_REQUIREMENTS mapping."""

    def test_coder_agent_has_research_tools(self):
        """CoderAgent should have research tools."""
        assert "CoderAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["CoderAgent"] == ToolSet.RESEARCH_ONLY

    def test_issue_creator_has_research_tools(self):
        """IssueCreatorAgent should have research tools (not NONE!)."""
        assert "IssueCreatorAgent" in AGENT_TOOL_REQUIREMENTS
        # This is the KEY change - was NONE, now RESEARCH_ONLY
        assert AGENT_TOOL_REQUIREMENTS["IssueCreatorAgent"] == ToolSet.RESEARCH_ONLY

    def test_complexity_gate_has_research_tools(self):
        """ComplexityGateAgent should have research tools (not NONE!)."""
        assert "ComplexityGateAgent" in AGENT_TOOL_REQUIREMENTS
        # This is the KEY change - was NONE, now RESEARCH_ONLY
        assert AGENT_TOOL_REQUIREMENTS["ComplexityGateAgent"] == ToolSet.RESEARCH_ONLY

    def test_bug_researcher_has_bash(self):
        """BugResearcherAgent should have Bash for running tests."""
        assert "BugResearcherAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["BugResearcherAgent"] == ToolSet.RESEARCH_WITH_BASH

    def test_verifier_has_research_tools(self):
        """VerifierAgent should have research tools."""
        assert "VerifierAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["VerifierAgent"] == ToolSet.RESEARCH_ONLY

    def test_spec_author_has_write(self):
        """SpecAuthorAgent should have Write for spec files."""
        assert "SpecAuthorAgent" in AGENT_TOOL_REQUIREMENTS
        assert AGENT_TOOL_REQUIREMENTS["SpecAuthorAgent"] == ToolSet.RESEARCH_WITH_WRITE


class TestGetToolsForAgent:
    """Tests for get_tools_for_agent function."""

    def test_returns_correct_tools_for_coder(self):
        """Should return Read, Glob, Grep for CoderAgent."""
        tools = get_tools_for_agent("CoderAgent")
        assert tools == ["Read", "Glob", "Grep"]

    def test_returns_correct_tools_for_issue_creator(self):
        """Should return research tools for IssueCreatorAgent."""
        tools = get_tools_for_agent("IssueCreatorAgent")
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools

    def test_returns_correct_tools_for_complexity_gate(self):
        """Should return research tools for ComplexityGateAgent."""
        tools = get_tools_for_agent("ComplexityGateAgent")
        assert "Read" in tools
        assert "Glob" in tools
        assert "Grep" in tools

    def test_unknown_agent_gets_research_tools(self):
        """Unknown agents should get research tools by default."""
        tools = get_tools_for_agent("UnknownAgent")
        assert tools == ["Read", "Glob", "Grep"]

    def test_returns_list_not_enum(self):
        """Should return list of strings, not ToolSet enum."""
        tools = get_tools_for_agent("CoderAgent")
        assert isinstance(tools, list)
        assert all(isinstance(t, str) for t in tools)
