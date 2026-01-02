"""Clean module with proper error handling."""
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration loading fails."""

    pass


@dataclass
class Config:
    """Application configuration."""

    name: str
    version: str
    settings: Dict


def load_config(path: Path) -> Config:
    """Load configuration from a JSON file.

    Args:
        path: Path to the configuration file.

    Returns:
        Parsed configuration object.

    Raises:
        ConfigError: If the file cannot be read or parsed.
    """
    try:
        content = path.read_text()
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {path}")
        raise ConfigError(f"Configuration file not found: {path}")
    except PermissionError:
        logger.error(f"Permission denied reading: {path}")
        raise ConfigError(f"Permission denied reading: {path}")

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        raise ConfigError(f"Invalid JSON in configuration file: {e}")

    try:
        return Config(
            name=data["name"],
            version=data["version"],
            settings=data.get("settings", {}),
        )
    except KeyError as e:
        logger.error(f"Missing required field in {path}: {e}")
        raise ConfigError(f"Missing required configuration field: {e}")
