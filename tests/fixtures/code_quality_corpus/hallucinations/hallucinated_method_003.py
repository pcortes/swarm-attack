"""Sample with hallucinated method - list method that doesn't exist."""
from typing import List


def filter_items(items: List[str]) -> List[str]:
    """Filter items using non-existent list method."""
    # list has no filter_by method
    filtered = items.filter_by(lambda x: len(x) > 3)
    return filtered
