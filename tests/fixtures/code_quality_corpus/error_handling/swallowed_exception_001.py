"""Sample with swallowed exception - empty except block."""
import json


def load_config(path: str) -> dict:
    """Load config - swallows exceptions with pass."""
    try:
        with open(path) as f:
            return json.load(f)
    except:
        pass
    return {}
