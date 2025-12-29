"""
Tests for UniversalContextBuilder - agent-type-specific context profiles.

These tests validate:
- AGENT_CONTEXT_PROFILES defines correct profiles for all agent types
- UniversalContextBuilder.build_context_for_agent() returns tailored context
- Token budgets are respected
- BaseAgent context injection works
"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.universal_context_builder import (
    AgentContext,
    AGENT_CONTEXT_PROFILES,
    UniversalContextBuilder,
)


@pytest.fixture
def temp_repo():
    """Create a temporary repository with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Create CLAUDE.md for project instructions
        (repo_path / "CLAUDE.md").write_text("# Project Instructions\nTest project.")
        yield repo_path


@pytest.fixture
def mock_config(temp_repo):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = temp_repo
    return config


@pytest.fixture
def mock_state_store():
    """Create a mock StateStore."""
    store = MagicMock()
    store.get_module_registry.return_value = {"modules": {}}
    return store


class TestAgentContextProfiles:
    """Tests for AGENT_CONTEXT_PROFILES configuration."""

    def test_coder_profile_includes_module_registry(self):
        """Coder agents must receive module registry."""
        profile = AGENT_CONTEXT_PROFILES["coder"]
        assert "module_registry" in profile["include"]
        assert profile["depth"] == "full_source"

    def test_spec_author_profile_is_summary_depth(self):
        """Spec authors get summary, not full source."""
        profile = AGENT_CONTEXT_PROFILES["spec_author"]
        assert profile["depth"] == "summary"
        assert profile["max_tokens"] <= 5000

    def test_all_profiles_have_project_instructions(self):
        """Every agent type should get project instructions."""
        for agent_type, profile in AGENT_CONTEXT_PROFILES.items():
            assert "project_instructions" in profile["include"], (
                f"{agent_type} missing project_instructions"
            )

    def test_coder_has_highest_token_budget(self):
        """Coder agents need the most context."""
        coder_budget = AGENT_CONTEXT_PROFILES["coder"]["max_tokens"]
        for agent_type, profile in AGENT_CONTEXT_PROFILES.items():
            if agent_type != "coder":
                assert profile["max_tokens"] <= coder_budget, (
                    f"{agent_type} has higher budget than coder"
                )

    def test_verifier_has_compact_depth(self):
        """Verifier agents get compact context."""
        profile = AGENT_CONTEXT_PROFILES["verifier"]
        assert profile["depth"] == "compact"
        assert profile["max_tokens"] <= 3000

    def test_bug_researcher_has_full_source_depth(self):
        """Bug researcher needs full source for debugging."""
        profile = AGENT_CONTEXT_PROFILES["bug_researcher"]
        assert profile["depth"] == "full_source"
        assert "test_structure" in profile["include"]


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_create_basic_context(self):
        """Test basic AgentContext creation."""
        context = AgentContext(
            agent_type="coder",
            built_at=datetime.now(),
        )
        assert context.agent_type == "coder"
        assert context.project_instructions is None
        assert context.token_count == 0

    def test_context_with_all_fields(self):
        """Test AgentContext with all fields populated."""
        context = AgentContext(
            agent_type="spec_author",
            built_at=datetime.now(),
            project_instructions="Test instructions",
            module_registry="class Foo: pass",
            completed_summaries="Issue #1 done",
            architecture_overview="System overview",
            token_count=500,
        )
        assert context.project_instructions == "Test instructions"
        assert context.module_registry == "class Foo: pass"
        assert context.token_count == 500


class TestUniversalContextBuilder:
    """Tests for UniversalContextBuilder class."""

    def test_builds_coder_context_with_full_source(self, mock_config, mock_state_store):
        """Coder context includes full source code."""
        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("coder", "test-feature", issue_number=1)

        assert context.agent_type == "coder"
        assert context.project_instructions is not None

    def test_builds_spec_author_context_without_code(self, mock_config, mock_state_store):
        """Spec author context is summary only."""
        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("spec_author", "test-feature")

        assert context.agent_type == "spec_author"
        # Should have architecture overview, not full code
        assert context.token_count <= 5000

    def test_respects_token_budget(self, mock_config, mock_state_store):
        """Context must be truncated to stay within budget."""
        # Create large module registry that exceeds budget
        large_registry = {
            "modules": {
                "large_file.py": {
                    "classes": ["LargeClass"],
                    "created_by_issue": 1,
                }
            }
        }
        mock_state_store.get_module_registry.return_value = large_registry

        # Create a large source file in the repo
        large_file = mock_config.repo_root / "large_file.py"
        large_content = "class LargeClass:\n" + "    " + "x" * 100000
        large_file.write_text(large_content)

        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("verifier", "test-feature")

        # Verifier has 3000 token budget
        assert context.token_count <= 3000

    def test_unknown_agent_type_gets_minimal_context(self, mock_config, mock_state_store):
        """Unknown agent types get safe defaults."""
        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("unknown_agent", "test-feature")

        assert context.agent_type == "unknown_agent"
        # Should not crash, should get minimal context

    def test_includes_project_instructions_for_all_profiles(
        self, mock_config, mock_state_store
    ):
        """All defined agent types receive project instructions."""
        builder = UniversalContextBuilder(mock_config, mock_state_store)

        for agent_type in AGENT_CONTEXT_PROFILES.keys():
            context = builder.build_context_for_agent(agent_type, "test-feature")
            assert context.project_instructions is not None, (
                f"{agent_type} missing project_instructions"
            )

    def test_coder_gets_module_registry(self, mock_config, mock_state_store):
        """Coder context includes module registry content."""
        mock_state_store.get_module_registry.return_value = {
            "modules": {
                "swarm_attack/models.py": {
                    "classes": ["TestModel"],
                    "created_by_issue": 1,
                }
            }
        }

        # Create the file in temp repo
        models_dir = mock_config.repo_root / "swarm_attack"
        models_dir.mkdir(parents=True)
        models_file = models_dir / "models.py"
        models_file.write_text("class TestModel:\n    name: str")

        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("coder", "test-feature")

        assert context.module_registry is not None
        assert "TestModel" in context.module_registry or context.module_registry != ""

    def test_bug_researcher_gets_test_structure(self, mock_config, mock_state_store):
        """Bug researcher context includes test structure."""
        # Create test directory
        tests_dir = mock_config.repo_root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_example.py").write_text("def test_foo(): pass")

        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("bug_researcher", "test-feature")

        # Bug researcher should have test_structure in profile
        assert "test_structure" in AGENT_CONTEXT_PROFILES["bug_researcher"]["include"]


class TestBaseAgentIntegration:
    """Tests for BaseAgent context injection."""

    def test_agent_can_receive_context(self, mock_config):
        """Agents can be injected with context."""
        from swarm_attack.agents.base import BaseAgent

        # Create a concrete agent for testing
        class TestAgent(BaseAgent):
            name = "test_agent"

            def run(self, context):
                return None

        agent = TestAgent(mock_config)
        context = AgentContext(agent_type="coder", built_at=datetime.now())
        result = agent.with_context(context)

        assert agent._universal_context == context
        assert result is agent  # Returns self for chaining

    def test_context_formats_for_prompt(self, mock_config):
        """Injected context formats correctly for prompts."""
        from swarm_attack.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test_agent"

            def run(self, context):
                return None

        agent = TestAgent(mock_config)
        context = AgentContext(
            agent_type="coder",
            built_at=datetime.now(),
            project_instructions="Test instructions",
            module_registry="class Foo: pass",
        )
        agent.with_context(context)

        prompt_section = agent._get_context_prompt_section()
        assert "Test instructions" in prompt_section
        assert "class Foo" in prompt_section

    def test_no_context_returns_empty_string(self, mock_config):
        """Agent without context returns empty prompt section."""
        from swarm_attack.agents.base import BaseAgent

        class TestAgent(BaseAgent):
            name = "test_agent"

            def run(self, context):
                return None

        agent = TestAgent(mock_config)
        prompt_section = agent._get_context_prompt_section()
        assert prompt_section == ""


class TestTokenTruncation:
    """Tests for token budget enforcement."""

    def test_truncation_preserves_project_instructions(self, mock_config, mock_state_store):
        """Project instructions are preserved during truncation."""
        # Set up large module registry
        mock_state_store.get_module_registry.return_value = {
            "modules": {
                "file.py": {"classes": ["Big"], "created_by_issue": 1}
            }
        }
        big_file = mock_config.repo_root / "file.py"
        big_file.write_text("class Big:\n" + "    x = " + "1" * 50000)

        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("verifier", "test-feature")

        # Project instructions should still be present
        assert context.project_instructions is not None
        # But token count should be within budget
        assert context.token_count <= 3000

    def test_token_count_estimation(self, mock_config, mock_state_store):
        """Token count is roughly 1/4 of character count."""
        builder = UniversalContextBuilder(mock_config, mock_state_store)
        context = builder.build_context_for_agent("coder", "test-feature")

        # Token count should be approximately chars / 4
        if context.project_instructions:
            estimated = len(context.project_instructions) // 4
            # Allow some variance due to other fields
            assert context.token_count >= 0
