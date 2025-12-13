"""Test file with intentional off-by-one bug for debate layer validation."""


def get_items(items, start, end):
    """Get items from start to end (inclusive).

    Args:
        items: List of items to slice
        start: Starting index (0-based)
        end: Ending index (inclusive)

    Returns:
        Sublist from start to end inclusive
    """
    # Fixed: Use end+1 to achieve inclusive end behavior
    return items[start:end+1]


def test_get_items_basic():
    """Test that get_items returns inclusive range."""
    items = [1, 2, 3, 4, 5]
    # Want items at indices 1, 2, 3 which are values 2, 3, 4
    result = get_items(items, 1, 3)
    assert result == [2, 3, 4], f"Expected [2, 3, 4], got {result}"


def test_get_items_full_range():
    """Test getting full range of items."""
    items = ["a", "b", "c", "d", "e"]
    # Want all items from index 0 to 4 inclusive
    result = get_items(items, 0, 4)
    assert result == ["a", "b", "c", "d", "e"], f"Expected full list, got {result}"


def test_get_items_single():
    """Test getting a single item."""
    items = [10, 20, 30, 40, 50]
    # Want just the item at index 2 (value 30)
    result = get_items(items, 2, 2)
    assert result == [30], f"Expected [30], got {result}"
