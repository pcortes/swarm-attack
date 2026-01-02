"""Sample with hallucinated import - fake standard library module."""
from typing import Dict
from stdlib_extensions.advanced_json import smart_loads, recursive_merge


def load_config(path: str) -> Dict:
    """Load config using non-existent stdlib extension."""
    with open(path) as f:
        base = smart_loads(f.read())
    return recursive_merge(base, {})
