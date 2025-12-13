"""
Generated test cases for bug: debate-test-001

These tests verify the fix for the identified bug.
"""

import pytest


# Regression test: verify the exact failing scenario now works - indices 1-3 inclusive returns values [2,3,4]
def test_get_items_inclusive_end_regression():
    """Regression test for off-by-one bug: end index must be inclusive."""
    items = [1, 2, 3, 4, 5]
    result = get_items(items, 1, 3)
    assert result == [2, 3, 4], f"Expected [2, 3, 4], got {result}"
    # Verify length matches expected inclusive range
    assert len(result) == 3, f"Expected 3 items for range 1-3 inclusive"

# Edge case: test boundary conditions including start=end (single element) and full list
def test_get_items_boundary_conditions():
    """Edge case: test boundary conditions for inclusive slicing."""
    items = [0, 1, 2, 3, 4]
    
    # Single element: start == end should return one item
    assert get_items(items, 2, 2) == [2], "Single element case failed"
    
    # First element only
    assert get_items(items, 0, 0) == [0], "First element only case failed"
    
    # Last element only
    assert get_items(items, 4, 4) == [4], "Last element only case failed"
    
    # Full range
    assert get_items(items, 0, 4) == [0, 1, 2, 3, 4], "Full range case failed"

# Edge case: verify adjacent indices return exactly 2 elements
def test_get_items_adjacent_indices():
    """Edge case: adjacent indices should return exactly 2 elements."""
    items = ['a', 'b', 'c', 'd', 'e']
    
    # Indices 1-2 inclusive should return 2 elements
    result = get_items(items, 1, 2)
    assert result == ['b', 'c'], f"Expected ['b', 'c'], got {result}"
    assert len(result) == 2, "Adjacent indices should return exactly 2 elements"

