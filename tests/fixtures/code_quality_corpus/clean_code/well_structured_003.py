"""Clean utility module with focused functions."""
from typing import List, TypeVar

T = TypeVar("T")


def chunk_list(items: List[T], size: int) -> List[List[T]]:
    """Split a list into chunks of specified size.

    Args:
        items: The list to split.
        size: Maximum size of each chunk.

    Returns:
        A list of chunks.

    Raises:
        ValueError: If size is not positive.
    """
    if size <= 0:
        raise ValueError("Chunk size must be positive")

    return [items[i:i + size] for i in range(0, len(items), size)]


def flatten(nested: List[List[T]]) -> List[T]:
    """Flatten a nested list.

    Args:
        nested: A list of lists.

    Returns:
        A single flattened list.
    """
    return [item for sublist in nested for item in sublist]


def deduplicate(items: List[T]) -> List[T]:
    """Remove duplicates while preserving order.

    Args:
        items: The list to deduplicate.

    Returns:
        A list with duplicates removed.
    """
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
