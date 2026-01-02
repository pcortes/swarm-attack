"""Sample with hallucinated method - pathlib Path method that doesn't exist."""
from pathlib import Path


def read_yaml_config(path: Path) -> dict:
    """Read YAML using non-existent Path method."""
    # Path has no read_yaml method
    config = path.read_yaml()
    return config
