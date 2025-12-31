"""Default skill definitions bundled with the swarm-attack package.

These skills are automatically copied to a project's .claude/skills/ directory
on first use if they don't already exist.

Skills included:
- coder: TDD implementation agent
- verifier: Test validation agent
- feature-spec-author: Spec generation agent
- feature-spec-critic: Spec review agent
- feature-spec-moderator: Spec improvement agent
- issue-creator: GitHub issue creation agent
- issue-validator: Issue validation agent
- bug-researcher: Bug reproduction agent
- root-cause-analyzer: Root cause analysis agent
- fix-planner: Fix planning agent
- recovery: Session recovery agent
"""
from pathlib import Path


def get_default_skills_path() -> Path:
    """Get the path to bundled default skills."""
    return Path(__file__).parent
