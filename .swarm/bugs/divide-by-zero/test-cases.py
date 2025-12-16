"""
Generated test cases for bug: divide-by-zero

These tests verify the fix for the identified bug.
"""

import pytest


# Regression test: divide(a, 0) should raise ValueError (not ZeroDivisionError) with correct message
def test_divide_by_zero_raises_value_error():
    """Regression test for bug: division by zero should raise ValueError."""
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)
    # Also verify it's specifically ValueError, not ZeroDivisionError
    with pytest.raises(ValueError):
        divide(-5, 0)

# Edge case: zero as dividend (0/b) should work correctly and return 0.0
def test_divide_zero_dividend():
    """Edge case: zero dividend should return 0.0."""
    assert divide(0, 5) == 0.0
    assert divide(0, -3) == 0.0

# Edge case: negative divisor should work correctly
def test_divide_negative_divisor():
    """Edge case: negative divisor should work correctly."""
    assert divide(10, -2) == -5.0
    assert divide(-10, -2) == 5.0

# Verify normal division operations continue to work as expected after the fix
def test_divide_normal_cases_unchanged():
    """Verify normal division behavior is unchanged."""
    assert divide(10, 2) == 5.0
    assert divide(7, 2) == 3.5
    assert divide(1, 3) == pytest.approx(0.333333, rel=1e-5)

