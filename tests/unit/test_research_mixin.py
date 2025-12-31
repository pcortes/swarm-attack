"""Unit tests for AgentResearchMixin.

TDD RED Phase - All tests should FAIL initially.
"""
import pytest
from typing import Optional

from swarm_attack.agents.research_mixin import (
    AgentResearchMixin,
    DiscoveredContext,
    ResearchResult,
)


class TestDiscoveredContext:
    """Tests for DiscoveredContext TypedDict."""

    def test_discovered_context_has_required_fields(self):
        """DiscoveredContext should have all required fields."""
        context: DiscoveredContext = {
            "files_found": ["file1.py"],
            "patterns_found": {"class": ["class Foo"]},
            "modules_read": ["module.py"],
            "classes_discovered": {"file.py": ["MyClass"]},
            "functions_discovered": {"file.py": ["my_func"]},
            "existing_tests": ["test_file.py"],
            "dependencies": ["requests"],
        }

        assert "files_found" in context
        assert "patterns_found" in context
        assert "modules_read" in context
        assert "classes_discovered" in context
        assert "functions_discovered" in context
        assert "existing_tests" in context
        assert "dependencies" in context


class TestResearchResult:
    """Tests for ResearchResult dataclass."""

    def test_research_result_success(self):
        """ResearchResult should capture successful research."""
        context: DiscoveredContext = {
            "files_found": ["file1.py"],
            "patterns_found": {},
            "modules_read": [],
            "classes_discovered": {},
            "functions_discovered": {},
            "existing_tests": [],
            "dependencies": [],
        }

        result = ResearchResult(
            success=True,
            context=context,
            summary="Found 1 file",
            search_queries=["*.py"],
        )

        assert result.success is True
        assert result.error is None
        assert len(result.context["files_found"]) == 1

    def test_research_result_failure(self):
        """ResearchResult should capture failed research."""
        result = ResearchResult(
            success=False,
            context={
                "files_found": [],
                "patterns_found": {},
                "modules_read": [],
                "classes_discovered": {},
                "functions_discovered": {},
                "existing_tests": [],
                "dependencies": [],
            },
            summary="",
            search_queries=["*.py"],
            error="No files found",
        )

        assert result.success is False
        assert result.error == "No files found"


class TestAgentResearchMixin:
    """Tests for AgentResearchMixin class."""

    def test_research_tools_constant(self):
        """RESEARCH_TOOLS should be Read, Glob, Grep."""
        assert AgentResearchMixin.RESEARCH_TOOLS == ["Read", "Glob", "Grep"]

    def test_get_standard_research_patterns(self):
        """Should return sensible default patterns for a feature."""
        mixin = AgentResearchMixin()
        patterns = mixin.get_standard_research_patterns("my-feature")

        assert "search_patterns" in patterns
        assert "grep_patterns" in patterns
        assert "read_files" in patterns

        # Should include python files
        assert any("*.py" in p for p in patterns["search_patterns"])
        # Should include CLAUDE.md
        assert "CLAUDE.md" in patterns["read_files"]

    def test_format_research_for_prompt_includes_files(self):
        """format_research_for_prompt should include found files."""
        mixin = AgentResearchMixin()
        result = ResearchResult(
            success=True,
            context={
                "files_found": ["swarm_attack/agents/base.py"],
                "patterns_found": {"class Agent": ["class BaseAgent"]},
                "modules_read": ["base.py"],
                "classes_discovered": {"base.py": ["BaseAgent"]},
                "functions_discovered": {},
                "existing_tests": [],
                "dependencies": [],
            },
            summary="Found BaseAgent class",
            search_queries=["swarm_attack/**/*.py"],
        )

        formatted = mixin.format_research_for_prompt(result)

        assert "base.py" in formatted
        assert "BaseAgent" in formatted

    def test_format_research_for_prompt_handles_empty(self):
        """format_research_for_prompt should handle empty results."""
        mixin = AgentResearchMixin()
        result = ResearchResult(
            success=True,
            context={
                "files_found": [],
                "patterns_found": {},
                "modules_read": [],
                "classes_discovered": {},
                "functions_discovered": {},
                "existing_tests": [],
                "dependencies": [],
            },
            summary="No results found",
            search_queries=["nonexistent/**/*.py"],
        )

        formatted = mixin.format_research_for_prompt(result)

        # Should not raise, should return something
        assert isinstance(formatted, str)

    def test_build_research_prompt(self):
        """build_research_prompt should create exploration prompt."""
        mixin = AgentResearchMixin()
        task_context = {
            "feature_id": "my-feature",
            "search_hints": ["look for Agent classes"],
        }

        prompt = mixin.build_research_prompt(task_context)

        assert "research" in prompt.lower() or "explore" in prompt.lower()
        assert "my-feature" in prompt or "Agent" in prompt
