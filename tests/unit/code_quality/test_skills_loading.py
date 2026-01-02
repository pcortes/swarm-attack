"""Tests for code quality skill files."""
import pytest
from pathlib import Path


class TestCodeQualityAnalystSkill:
    """Tests for code-quality-analyst skill."""

    @pytest.fixture
    def skill_path(self):
        return Path(".claude/skills/code-quality-analyst/SKILL.md")

    def test_skill_file_exists(self, skill_path):
        """Skill file must exist."""
        assert skill_path.exists(), f"{skill_path} does not exist"

    def test_skill_has_frontmatter(self, skill_path):
        """Skill file must have YAML frontmatter."""
        content = skill_path.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter start"
        assert "---" in content[3:], "Missing YAML frontmatter end"

    def test_skill_has_name(self, skill_path):
        """Skill must define name."""
        content = skill_path.read_text()
        assert "name: code-quality-analyst" in content

    def test_skill_has_allowed_tools(self, skill_path):
        """Skill must define allowed tools."""
        content = skill_path.read_text()
        assert "allowed-tools:" in content
        assert "Read" in content
        assert "Glob" in content
        assert "Grep" in content

    def test_skill_has_output_format(self, skill_path):
        """Skill must define JSON output format."""
        content = skill_path.read_text()
        assert "Output Format" in content or "output" in content.lower()
        assert "json" in content.lower()


class TestRefactorCriticSkill:
    """Tests for refactor-critic skill."""

    @pytest.fixture
    def skill_path(self):
        return Path(".claude/skills/refactor-critic/SKILL.md")

    def test_skill_file_exists(self, skill_path):
        """Skill file must exist."""
        assert skill_path.exists(), f"{skill_path} does not exist"

    def test_skill_has_frontmatter(self, skill_path):
        """Skill file must have YAML frontmatter."""
        content = skill_path.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter start"
        assert "---" in content[3:], "Missing YAML frontmatter end"

    def test_skill_has_name(self, skill_path):
        """Skill must define name."""
        content = skill_path.read_text()
        assert "name: refactor-critic" in content

    def test_skill_has_allowed_tools(self, skill_path):
        """Skill must define allowed tools."""
        content = skill_path.read_text()
        assert "allowed-tools:" in content

    def test_skill_has_validation_process(self, skill_path):
        """Critic skill must describe validation process."""
        content = skill_path.read_text()
        assert "Review Process" in content or "validate" in content.lower()


class TestRefactorModeratorSkill:
    """Tests for refactor-moderator skill."""

    @pytest.fixture
    def skill_path(self):
        return Path(".claude/skills/refactor-moderator/SKILL.md")

    def test_skill_file_exists(self, skill_path):
        """Skill file must exist."""
        assert skill_path.exists(), f"{skill_path} does not exist"

    def test_skill_has_frontmatter(self, skill_path):
        """Skill file must have YAML frontmatter."""
        content = skill_path.read_text()
        assert content.startswith("---"), "Missing YAML frontmatter start"
        assert "---" in content[3:], "Missing YAML frontmatter end"

    def test_skill_has_name(self, skill_path):
        """Skill must define name."""
        content = skill_path.read_text()
        assert "name: refactor-moderator" in content

    def test_skill_has_allowed_tools(self, skill_path):
        """Skill must define allowed tools."""
        content = skill_path.read_text()
        assert "allowed-tools:" in content

    def test_skill_has_tdd_plan_section(self, skill_path):
        """Moderator skill must describe TDD plan generation."""
        content = skill_path.read_text()
        assert "TDD" in content


class TestAllSkillsConsistency:
    """Cross-skill consistency tests."""

    def test_all_skills_have_description(self):
        """All skills must have description in frontmatter."""
        skills = [
            ".claude/skills/code-quality-analyst/SKILL.md",
            ".claude/skills/refactor-critic/SKILL.md",
            ".claude/skills/refactor-moderator/SKILL.md",
        ]
        for skill_path in skills:
            path = Path(skill_path)
            assert path.exists(), f"{skill_path} missing"
            content = path.read_text()
            assert "description:" in content, f"{skill_path} missing description"
