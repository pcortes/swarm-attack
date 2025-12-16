"""Tests for buggy_code module."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from buggy_code import divide, calculate_average


class TestDivide:
    def test_divide_basic(self):
        assert divide(10, 2) == 5.0

    def test_divide_by_zero(self):
        """This test exposes the bug - should handle division by zero."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)


class TestCalculateAverage:
    def test_average_basic(self):
        assert calculate_average([1, 2, 3]) == 2.0

    def test_average_empty_list(self):
        """This test exposes the bug - should handle empty list."""
        with pytest.raises(ValueError, match="Cannot calculate average of empty list"):
            calculate_average([])
