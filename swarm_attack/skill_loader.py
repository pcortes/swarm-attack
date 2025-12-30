"""
SkillLoader - Load and manage skill definitions with nested subagent support.

This module provides structured skill loading with:
- SkillDefinition dataclass for parsed skill metadata
- SkillLoader for loading skills and subagents from .claude/skills/
- Nested agent discovery ({skill}/agents/{subagent}/SKILL.md)
- YAML frontmatter parsing
- Auto-copy of default skills from package (Bug #4 fix)
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


def ensure_default_skills(repo_root: Path) -> bool:
    """
    Copy default skills from the package to project's .claude/skills/ if missing.

    This function is called automatically when a skill is not found, enabling
    out-of-box functionality after pip install without manual setup.

    Args:
        repo_root: Path to the project root directory.

    Returns:
        True if any skills were copied, False if all skills already exist.

    Note:
        - Only copies skills that don't already exist (preserves customizations)
        - Creates .claude/skills/ directory if it doesn't exist
        - Uses bundled skills from swarm_attack.default_skills package
    """
    from swarm_attack.default_skills import get_default_skills_path

    source = get_default_skills_path()
    target = repo_root / ".claude" / "skills"

    if not source.exists():
        # Can't find bundled skills (shouldn't happen in normal install)
        return False

    # Get list of skills to potentially copy
    skills_to_copy = []
    for skill_dir in source.iterdir():
        if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
            skill_name = skill_dir.name
            target_skill = target / skill_name / "SKILL.md"

            # Only copy if target doesn't exist
            if not target_skill.exists():
                skills_to_copy.append(skill_name)

    if not skills_to_copy:
        # All skills already exist
        return False

    # Ensure target directory exists
    target.mkdir(parents=True, exist_ok=True)

    # Copy each missing skill
    for skill_name in skills_to_copy:
        source_skill = source / skill_name
        target_skill = target / skill_name

        if not target_skill.exists():
            shutil.copytree(source_skill, target_skill)

    return True


class SkillNotFoundError(Exception):
    """Raised when a skill or subagent cannot be found."""

    def __init__(
        self,
        skill_name: str,
        path: Optional[Path] = None,
        is_subagent: bool = False,
    ) -> None:
        self.skill_name = skill_name
        self.path = path
        self.is_subagent = is_subagent

        if is_subagent:
            msg = f"Subagent '{skill_name}' not found"
        else:
            msg = f"Skill '{skill_name}' not found"
        if path:
            msg += f" at {path}"

        super().__init__(msg)


@dataclass
class SkillDefinition:
    """Parsed skill with metadata and nested agent info."""

    name: str  # Skill name (e.g., "coder")
    content: str  # SKILL.md content (frontmatter stripped)
    metadata: dict = field(default_factory=dict)  # Parsed YAML frontmatter
    subagents: list[str] = field(default_factory=list)  # Available nested agents
    path: Optional[Path] = None  # Source file path


class SkillLoader:
    """Loads skills and their nested subagents from .claude/skills/."""

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        repo_root: Optional[Path] = None,
    ) -> None:
        """
        Initialize SkillLoader.

        Args:
            skills_dir: Path to skills directory. Defaults to .claude/skills/
            repo_root: Path to project root. If provided, enables auto-copy of
                       default skills when a skill is not found (Bug #4 fix).
        """
        if skills_dir is not None:
            self.skills_dir = skills_dir
        else:
            # Default to .claude/skills/ relative to current working directory
            self.skills_dir = Path.cwd() / ".claude" / "skills"

        self._repo_root = repo_root

    def load_skill(self, skill_name: str) -> SkillDefinition:
        """
        Load main skill from .claude/skills/{skill_name}/SKILL.md.

        If the skill is not found and repo_root was provided, attempts to
        auto-copy default skills from the package before raising an error.

        Args:
            skill_name: Name of the skill directory.

        Returns:
            SkillDefinition with parsed content, metadata, and subagent list.

        Raises:
            SkillNotFoundError: If skill directory or SKILL.md doesn't exist
                               after attempting auto-copy.
        """
        skill_path = self._get_skill_path(skill_name)

        if not skill_path.exists():
            # Bug #4 fix: Try auto-copy before failing
            if self._repo_root is not None:
                if ensure_default_skills(self._repo_root):
                    # Retry after auto-copy
                    skill_path = self._get_skill_path(skill_name)

            if not skill_path.exists():
                raise SkillNotFoundError(skill_name, skill_path)

        raw_content = skill_path.read_text()
        content, metadata = self._parse_frontmatter(raw_content)

        # Discover subagents
        subagents = self.list_subagents(skill_name)

        return SkillDefinition(
            name=skill_name,
            content=content,
            metadata=metadata,
            subagents=subagents,
            path=skill_path,
        )

    def load_subagent(self, skill_name: str, agent_name: str) -> SkillDefinition:
        """
        Load nested agent from .claude/skills/{skill_name}/agents/{agent_name}/SKILL.md.

        Args:
            skill_name: Parent skill name.
            agent_name: Nested agent name.

        Returns:
            SkillDefinition for the subagent.

        Raises:
            SkillNotFoundError: If subagent doesn't exist.
        """
        subagent_path = self._get_subagent_path(skill_name, agent_name)

        if not subagent_path.exists():
            raise SkillNotFoundError(agent_name, subagent_path, is_subagent=True)

        raw_content = subagent_path.read_text()
        content, metadata = self._parse_frontmatter(raw_content)

        return SkillDefinition(
            name=agent_name,
            content=content,
            metadata=metadata,
            subagents=[],  # Subagents don't have nested agents
            path=subagent_path,
        )

    def list_subagents(self, skill_name: str) -> list[str]:
        """
        List available subagents for a skill.

        Args:
            skill_name: Name of the parent skill.

        Returns:
            List of subagent names. Empty list if no agents/ directory.
        """
        agents_dir = self.skills_dir / skill_name / "agents"

        if not agents_dir.exists() or not agents_dir.is_dir():
            return []

        # Return only directories (not files) that contain SKILL.md
        subagents = []
        for item in agents_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                subagents.append(item.name)

        return subagents

    def has_subagents(self, skill_name: str) -> bool:
        """
        Check if skill has nested agents directory.

        Args:
            skill_name: Name of the skill.

        Returns:
            True if {skill}/agents/ exists and contains subagents.
        """
        return len(self.list_subagents(skill_name)) > 0

    def _parse_frontmatter(self, content: str) -> tuple[str, dict]:
        """
        Parse YAML frontmatter from skill content.

        Args:
            content: Raw SKILL.md content.

        Returns:
            Tuple of (content_without_frontmatter, metadata_dict).
        """
        # Check for YAML frontmatter (starts with ---)
        if not content.startswith("---"):
            return content, {}

        # Find the closing ---
        end_idx = content.find("---", 3)
        if end_idx == -1:
            # Malformed frontmatter - return raw content
            return content, {}

        # Extract and parse frontmatter
        frontmatter_str = content[3:end_idx].strip()
        body = content[end_idx + 3:].lstrip()

        # Handle empty frontmatter
        if not frontmatter_str:
            return body, {}

        # Parse YAML - handle invalid YAML gracefully
        try:
            metadata = yaml.safe_load(frontmatter_str)
            if metadata is None:
                metadata = {}
        except yaml.YAMLError:
            # Invalid YAML - return empty metadata
            metadata = {}

        return body, metadata

    def _get_skill_path(self, skill_name: str) -> Path:
        """Get path to skill's SKILL.md file."""
        return self.skills_dir / skill_name / "SKILL.md"

    def _get_subagent_path(self, skill_name: str, agent_name: str) -> Path:
        """Get path to subagent's SKILL.md file."""
        return self.skills_dir / skill_name / "agents" / agent_name / "SKILL.md"
