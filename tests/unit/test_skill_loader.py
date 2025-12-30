"""Unit tests for SkillLoader.

Tests follow TDD RED phase - all tests should FAIL initially.
"""
import pytest
from pathlib import Path

from swarm_attack.skill_loader import SkillLoader, SkillDefinition, SkillNotFoundError


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create temporary skills directory structure."""
    skills = tmp_path / ".claude" / "skills"
    skills.mkdir(parents=True)
    return skills


@pytest.fixture
def skill_with_subagents(skills_dir: Path) -> Path:
    """Create skill with nested agents."""
    skill_dir = skills_dir / "feature-builder"
    skill_dir.mkdir()

    # Main skill
    (skill_dir / "SKILL.md").write_text('''---
allowed-tools: Read,Glob,Bash
description: Feature builder skill
---
# Feature Builder

You build features.
''')

    # Nested agents
    agents_dir = skill_dir / "agents"
    agents_dir.mkdir()

    research_dir = agents_dir / "research"
    research_dir.mkdir()
    (research_dir / "SKILL.md").write_text('''---
allowed-tools: Read,Glob
---
# Research Agent
''')

    design_dir = agents_dir / "design"
    design_dir.mkdir()
    (design_dir / "SKILL.md").write_text('''---
allowed-tools: Read
---
# Design Agent
''')

    return skill_dir


@pytest.fixture
def skill_without_subagents(skills_dir: Path) -> Path:
    """Create skill without nested agents."""
    skill_dir = skills_dir / "simple-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text('''---
allowed-tools: Read
---
# Simple Skill

No nested agents here.
''')
    return skill_dir


class TestSkillLoaderInit:
    """Tests for SkillLoader initialization."""

    def test_init_with_default_path(self):
        """Should use .claude/skills/ as default."""
        loader = SkillLoader()
        assert loader.skills_dir.name == "skills"

    def test_init_with_custom_path(self, skills_dir):
        """Should accept custom skills directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.skills_dir == skills_dir


class TestLoadSkill:
    """Tests for SkillLoader.load_skill()."""

    def test_load_skill_returns_skill_definition(self, skills_dir, skill_without_subagents):
        """Should return SkillDefinition instance."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert isinstance(result, SkillDefinition)
        assert result.name == "simple-skill"

    def test_load_skill_parses_content(self, skills_dir, skill_without_subagents):
        """Should return content without frontmatter."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert "# Simple Skill" in result.content
        assert "---" not in result.content
        assert "allowed-tools" not in result.content

    def test_load_skill_parses_metadata(self, skills_dir, skill_without_subagents):
        """Should parse YAML frontmatter into metadata dict."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert result.metadata.get("allowed-tools") == "Read"

    def test_load_skill_populates_subagents(self, skills_dir, skill_with_subagents):
        """Should populate subagents list when agents/ exists."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("feature-builder")

        assert "research" in result.subagents
        assert "design" in result.subagents

    def test_load_skill_empty_subagents_when_no_agents_dir(self, skills_dir, skill_without_subagents):
        """Should have empty subagents when no agents/ directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert result.subagents == []

    def test_load_skill_sets_path(self, skills_dir, skill_without_subagents):
        """Should set path to SKILL.md location."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("simple-skill")

        assert result.path == skills_dir / "simple-skill" / "SKILL.md"

    def test_load_skill_raises_for_missing_skill(self, skills_dir):
        """Should raise SkillNotFoundError for missing skill."""
        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load_skill("nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_load_skill_handles_missing_frontmatter(self, skills_dir):
        """Should handle skill without frontmatter."""
        skill_dir = skills_dir / "no-frontmatter"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just Content\n\nNo metadata here.")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_skill("no-frontmatter")

        assert result.metadata == {}
        assert "# Just Content" in result.content


class TestLoadSubagent:
    """Tests for SkillLoader.load_subagent()."""

    def test_load_subagent_returns_definition(self, skills_dir, skill_with_subagents):
        """Should return SkillDefinition for subagent."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_subagent("feature-builder", "research")

        assert isinstance(result, SkillDefinition)
        assert result.name == "research"

    def test_load_subagent_parses_content(self, skills_dir, skill_with_subagents):
        """Should parse subagent content and metadata."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_subagent("feature-builder", "research")

        assert "# Research Agent" in result.content
        assert result.metadata.get("allowed-tools") == "Read,Glob"

    def test_load_subagent_correct_path(self, skills_dir, skill_with_subagents):
        """Should set correct path for subagent."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.load_subagent("feature-builder", "research")

        expected = skills_dir / "feature-builder" / "agents" / "research" / "SKILL.md"
        assert result.path == expected

    def test_load_subagent_raises_for_missing(self, skills_dir, skill_with_subagents):
        """Should raise SkillNotFoundError for missing subagent."""
        loader = SkillLoader(skills_dir=skills_dir)

        with pytest.raises(SkillNotFoundError) as exc_info:
            loader.load_subagent("feature-builder", "nonexistent")

        assert exc_info.value.is_subagent is True


class TestListSubagents:
    """Tests for SkillLoader.list_subagents()."""

    def test_list_subagents_returns_names(self, skills_dir, skill_with_subagents):
        """Should return list of subagent names."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.list_subagents("feature-builder")

        assert set(result) == {"research", "design"}

    def test_list_subagents_empty_when_no_agents(self, skills_dir, skill_without_subagents):
        """Should return empty list when no agents/ directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.list_subagents("simple-skill")

        assert result == []

    def test_list_subagents_ignores_files(self, skills_dir, skill_with_subagents):
        """Should only return directories, not files."""
        # Add a file in agents/ directory
        agents_dir = skills_dir / "feature-builder" / "agents"
        (agents_dir / "README.md").write_text("# Agents")

        loader = SkillLoader(skills_dir=skills_dir)
        result = loader.list_subagents("feature-builder")

        assert "README" not in result
        assert "README.md" not in result


class TestHasSubagents:
    """Tests for SkillLoader.has_subagents()."""

    def test_has_subagents_true(self, skills_dir, skill_with_subagents):
        """Should return True when agents/ exists with subagents."""
        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.has_subagents("feature-builder") is True

    def test_has_subagents_false_no_dir(self, skills_dir, skill_without_subagents):
        """Should return False when no agents/ directory."""
        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.has_subagents("simple-skill") is False

    def test_has_subagents_false_empty_dir(self, skills_dir):
        """Should return False when agents/ is empty."""
        skill_dir = skills_dir / "empty-agents"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Skill")
        (skill_dir / "agents").mkdir()  # Empty agents dir

        loader = SkillLoader(skills_dir=skills_dir)
        assert loader.has_subagents("empty-agents") is False


class TestParseFrontmatter:
    """Tests for frontmatter parsing."""

    def test_parses_yaml_frontmatter(self, skills_dir):
        """Should parse YAML between --- markers."""
        loader = SkillLoader(skills_dir=skills_dir)

        content = '''---
allowed-tools: Read,Glob
description: Test skill
version: 1.0
---
# Content here
'''
        text, metadata = loader._parse_frontmatter(content)

        assert metadata["allowed-tools"] == "Read,Glob"
        assert metadata["description"] == "Test skill"
        assert "# Content here" in text
        assert "---" not in text

    def test_handles_no_frontmatter(self, skills_dir):
        """Should return empty metadata when no frontmatter."""
        loader = SkillLoader(skills_dir=skills_dir)

        content = "# Just content\n\nNo frontmatter here."
        text, metadata = loader._parse_frontmatter(content)

        assert metadata == {}
        assert text == content

    def test_handles_malformed_yaml(self, skills_dir):
        """Should handle malformed YAML gracefully."""
        loader = SkillLoader(skills_dir=skills_dir)

        content = '''---
this is: not: valid: yaml
---
# Content
'''
        # Should not raise, return empty or partial metadata
        text, metadata = loader._parse_frontmatter(content)
        assert "# Content" in text
