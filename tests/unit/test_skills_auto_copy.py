"""Tests for skills auto-copy functionality (Bug #4).

Verifies that:
1. Default skills are bundled with the package
2. ensure_default_skills() copies missing skills to project
3. Existing skills are NOT overwritten
4. SkillLoader auto-copies when skill not found
"""
import pytest
import shutil
from pathlib import Path


class TestDefaultSkillsBundled:
    """Tests that default skills are properly bundled with the package."""

    def test_default_skills_package_exists(self):
        """The default_skills package should be importable."""
        from swarm_attack.default_skills import get_default_skills_path

        path = get_default_skills_path()
        assert path.exists()
        assert path.is_dir()

    def test_default_skills_contains_required_skills(self):
        """The bundled skills should include core required skills."""
        from swarm_attack.default_skills import get_default_skills_path

        skills_path = get_default_skills_path()

        required_skills = ["coder", "verifier", "feature-spec-author"]
        for skill in required_skills:
            skill_file = skills_path / skill / "SKILL.md"
            assert skill_file.exists(), f"Missing required skill: {skill}"

    def test_default_skills_contains_all_skills(self):
        """The bundled skills should include all expected skills."""
        from swarm_attack.default_skills import get_default_skills_path

        skills_path = get_default_skills_path()

        expected_skills = [
            "coder",
            "verifier",
            "feature-spec-author",
            "feature-spec-critic",
            "feature-spec-moderator",
            "issue-creator",
            "issue-validator",
            "bug-researcher",
            "root-cause-analyzer",
            "fix-planner",
            "recovery",
        ]

        for skill in expected_skills:
            skill_file = skills_path / skill / "SKILL.md"
            assert skill_file.exists(), f"Missing skill: {skill}"


class TestEnsureDefaultSkills:
    """Tests for ensure_default_skills() function."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        return tmp_path

    def test_copies_skills_to_empty_project(self, temp_project):
        """Skills should be copied to a project without skills dir."""
        from swarm_attack.skill_loader import ensure_default_skills

        result = ensure_default_skills(temp_project)

        assert result is True  # Skills were copied

        # Check that skills exist
        skills_dir = temp_project / ".claude" / "skills"
        assert skills_dir.exists()
        assert (skills_dir / "coder" / "SKILL.md").exists()
        assert (skills_dir / "verifier" / "SKILL.md").exists()

    def test_copies_missing_skills_only(self, temp_project):
        """Only missing skills should be copied, not all skills."""
        from swarm_attack.skill_loader import ensure_default_skills

        # Create a partial skills directory with one skill
        skills_dir = temp_project / ".claude" / "skills" / "coder"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("custom coder skill")

        result = ensure_default_skills(temp_project)

        # Should still return True (copied other skills)
        assert result is True

        # Custom skill should be preserved
        assert (skills_dir / "SKILL.md").read_text() == "custom coder skill"

        # Other skills should be copied
        assert (temp_project / ".claude" / "skills" / "verifier" / "SKILL.md").exists()

    def test_does_not_overwrite_existing_skills(self, temp_project):
        """Existing skills should NOT be overwritten."""
        from swarm_attack.skill_loader import ensure_default_skills

        # Create a custom skill
        skills_dir = temp_project / ".claude" / "skills" / "coder"
        skills_dir.mkdir(parents=True)
        custom_content = "# My Custom Coder Skill\nCustom implementation"
        (skills_dir / "SKILL.md").write_text(custom_content)

        ensure_default_skills(temp_project)

        # Custom content should be preserved
        assert (skills_dir / "SKILL.md").read_text() == custom_content

    def test_returns_false_when_all_skills_exist(self, temp_project):
        """Returns False if all required skills already exist."""
        from swarm_attack.skill_loader import ensure_default_skills
        from swarm_attack.default_skills import get_default_skills_path

        # Copy all skills manually first
        source = get_default_skills_path()
        dest = temp_project / ".claude" / "skills"
        shutil.copytree(source, dest, dirs_exist_ok=True)

        result = ensure_default_skills(temp_project)

        # Should return False (nothing copied)
        assert result is False


class TestSkillLoaderWithAutoCopy:
    """Tests that SkillLoader integrates with auto-copy."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        return tmp_path

    def test_load_skill_after_auto_copy(self, temp_project):
        """SkillLoader.load_skill should work after auto-copy is run."""
        from swarm_attack.skill_loader import SkillLoader, ensure_default_skills

        # First, run auto-copy to populate skills
        ensure_default_skills(temp_project)

        # Now load a skill
        skills_dir = temp_project / ".claude" / "skills"
        loader = SkillLoader(skills_dir)

        # Should succeed because skills were copied
        skill = loader.load_skill("coder")

        assert skill is not None
        assert skill.name == "coder"
        assert len(skill.content) > 0

    def test_skill_loader_with_repo_root_auto_copies(self, temp_project):
        """SkillLoader with repo_root should auto-copy missing skills."""
        from swarm_attack.skill_loader import SkillLoader

        skills_dir = temp_project / ".claude" / "skills"
        loader = SkillLoader(skills_dir, repo_root=temp_project)

        # Should auto-copy and then load the skill
        skill = loader.load_skill("coder")

        assert skill is not None
        assert skill.name == "coder"
