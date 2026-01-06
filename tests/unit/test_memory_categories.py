"""Tests for memory category constants.

TDD tests for swarm_attack.memory.categories module.
"""

import pytest


class TestMemoryCategoryConstants:
    """Test suite for memory category constants."""

    def test_schema_drift_category_is_string(self) -> None:
        """SCHEMA_DRIFT constant should be a string."""
        from swarm_attack.memory.categories import SCHEMA_DRIFT

        assert isinstance(SCHEMA_DRIFT, str)
        assert SCHEMA_DRIFT == "schema_drift"

    def test_test_failure_category_is_string(self) -> None:
        """TEST_FAILURE constant should be a string."""
        from swarm_attack.memory.categories import TEST_FAILURE

        assert isinstance(TEST_FAILURE, str)
        assert TEST_FAILURE == "test_failure"

    def test_recovery_pattern_category_is_string(self) -> None:
        """RECOVERY_PATTERN constant should be a string."""
        from swarm_attack.memory.categories import RECOVERY_PATTERN

        assert isinstance(RECOVERY_PATTERN, str)
        assert RECOVERY_PATTERN == "recovery_pattern"

    def test_implementation_success_category_is_string(self) -> None:
        """IMPLEMENTATION_SUCCESS constant should be a string."""
        from swarm_attack.memory.categories import IMPLEMENTATION_SUCCESS

        assert isinstance(IMPLEMENTATION_SUCCESS, str)
        assert IMPLEMENTATION_SUCCESS == "implementation_success"

    def test_bug_pattern_category_is_string(self) -> None:
        """BUG_PATTERN constant should be a string."""
        from swarm_attack.memory.categories import BUG_PATTERN

        assert isinstance(BUG_PATTERN, str)
        assert BUG_PATTERN == "bug_pattern"

    def test_categories_are_unique(self) -> None:
        """All category constants should have unique values."""
        from swarm_attack.memory.categories import (
            BUG_PATTERN,
            IMPLEMENTATION_SUCCESS,
            RECOVERY_PATTERN,
            SCHEMA_DRIFT,
            TEST_FAILURE,
        )

        categories = [
            SCHEMA_DRIFT,
            TEST_FAILURE,
            RECOVERY_PATTERN,
            IMPLEMENTATION_SUCCESS,
            BUG_PATTERN,
        ]

        # Check that all values are unique
        assert len(categories) == len(set(categories)), "Category constants must have unique values"
