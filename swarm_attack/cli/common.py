"""Common utilities and global state for the CLI.

Contains project directory management, config loading, and path helpers.
This module should NOT import from feature/bug/admin modules to avoid circular imports.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from rich.console import Console

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig

# ============================================================================
# Global State
# ============================================================================

# Global project directory override (set via --project flag)
_project_dir: Optional[str] = None

# Console singleton
_console: Optional[Console] = None


def get_project_dir() -> Optional[str]:
    """Get the project directory override if set."""
    return _project_dir


def set_project_dir(path: str) -> None:
    """Set the project directory override."""
    global _project_dir
    _project_dir = path


def get_console() -> Console:
    """Get or create the console singleton."""
    global _console
    if _console is None:
        _console = Console()
    return _console


# ============================================================================
# Config Helpers
# ============================================================================


def load_config_safe() -> Optional["SwarmConfig"]:
    """
    Load config, returning None if not found (allows running without config).

    For status command, we can work with just the .swarm directory.
    Uses the global --project flag if set.
    """
    from swarm_attack.config import ConfigError, load_config
    import os

    try:
        # Change to project dir if set, to find config.yaml
        project_dir = get_project_dir()
        if project_dir:
            os.chdir(project_dir)
        return load_config()
    except ConfigError:
        # No config file - use defaults
        return None


def get_config_or_default() -> "SwarmConfig":
    """Get config or create a default config for basic operations."""
    config = load_config_safe()
    if config is not None:
        return config

    # Create a minimal default config for basic operations
    from swarm_attack.config import (
        ClaudeConfig,
        GitConfig,
        GitHubConfig,
        SessionConfig,
        SpecDebateConfig,
        SwarmConfig,
        TestRunnerConfig,
    )

    # Return a default SwarmConfig
    return SwarmConfig(
        github=GitHubConfig(repo=""),
        claude=ClaudeConfig(),
        spec_debate=SpecDebateConfig(),
        sessions=SessionConfig(),
        tests=TestRunnerConfig(command="pytest"),
        git=GitConfig(),
    )


def init_swarm_directory(config: "SwarmConfig") -> None:
    """Initialize the .swarm directory structure if it doesn't exist."""
    from swarm_attack.utils.fs import ensure_dir

    ensure_dir(config.swarm_path)
    ensure_dir(config.state_path)
    ensure_dir(config.sessions_path)
    ensure_dir(config.logs_path)


# ============================================================================
# Path Helpers
# ============================================================================


def get_prd_path(config: "SwarmConfig", feature_id: str) -> Path:
    """Get the path to the PRD file for a feature."""
    return Path(config.repo_root) / ".claude" / "prds" / f"{feature_id}.md"


def get_spec_dir(config: "SwarmConfig", feature_id: str) -> Path:
    """Get the spec directory for a feature."""
    return config.specs_path / feature_id
