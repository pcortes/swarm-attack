"""Tests for RetryStrategy and ErrorCategory enums."""

import pytest
from swarm_attack.chief_of_staff.recovery import RetryStrategy, ErrorCategory


class TestRetryStrategyEnum:
    """Tests for RetryStrategy enum."""

    def test_retry_strategy_has_same_value(self):
        """RetryStrategy should have SAME member."""
        assert hasattr(RetryStrategy, 'SAME')
        assert RetryStrategy.SAME.value == "same"

    def test_retry_strategy_has_alternative_value(self):
        """RetryStrategy should have ALTERNATIVE member."""
        assert hasattr(RetryStrategy, 'ALTERNATIVE')
        assert RetryStrategy.ALTERNATIVE.value == "alternative"

    def test_retry_strategy_has_clarify_value(self):
        """RetryStrategy should have CLARIFY member."""
        assert hasattr(RetryStrategy, 'CLARIFY')
        assert RetryStrategy.CLARIFY.value == "clarify"

    def test_retry_strategy_has_escalate_value(self):
        """RetryStrategy should have ESCALATE member."""
        assert hasattr(RetryStrategy, 'ESCALATE')
        assert RetryStrategy.ESCALATE.value == "escalate"

    def test_retry_strategy_uses_string_values(self):
        """All RetryStrategy values should be strings for JSON serialization."""
        for strategy in RetryStrategy:
            assert isinstance(strategy.value, str)

    def test_retry_strategy_has_four_members(self):
        """RetryStrategy should have exactly 4 members."""
        assert len(RetryStrategy) == 4

    def test_retry_strategy_membership(self):
        """Test enum membership checks."""
        assert RetryStrategy.SAME in RetryStrategy
        assert RetryStrategy.ALTERNATIVE in RetryStrategy
        assert RetryStrategy.CLARIFY in RetryStrategy
        assert RetryStrategy.ESCALATE in RetryStrategy


class TestErrorCategoryEnum:
    """Tests for ErrorCategory enum."""

    def test_error_category_has_transient_value(self):
        """ErrorCategory should have TRANSIENT member."""
        assert hasattr(ErrorCategory, 'TRANSIENT')
        assert ErrorCategory.TRANSIENT.value == "transient"

    def test_error_category_has_systematic_value(self):
        """ErrorCategory should have SYSTEMATIC member."""
        assert hasattr(ErrorCategory, 'SYSTEMATIC')
        assert ErrorCategory.SYSTEMATIC.value == "systematic"

    def test_error_category_has_fatal_value(self):
        """ErrorCategory should have FATAL member."""
        assert hasattr(ErrorCategory, 'FATAL')
        assert ErrorCategory.FATAL.value == "fatal"

    def test_error_category_uses_string_values(self):
        """All ErrorCategory values should be strings for JSON serialization."""
        for category in ErrorCategory:
            assert isinstance(category.value, str)

    def test_error_category_has_three_members(self):
        """ErrorCategory should have exactly 3 members."""
        assert len(ErrorCategory) == 3

    def test_error_category_membership(self):
        """Test enum membership checks."""
        assert ErrorCategory.TRANSIENT in ErrorCategory
        assert ErrorCategory.SYSTEMATIC in ErrorCategory
        assert ErrorCategory.FATAL in ErrorCategory


class TestEnumDocstrings:
    """Tests verifying enums have docstrings."""

    def test_retry_strategy_has_docstring(self):
        """RetryStrategy should have a docstring."""
        assert RetryStrategy.__doc__ is not None
        assert len(RetryStrategy.__doc__) > 0

    def test_error_category_has_docstring(self):
        """ErrorCategory should have a docstring."""
        assert ErrorCategory.__doc__ is not None
        assert len(ErrorCategory.__doc__) > 0


class TestEnumSerialization:
    """Tests verifying enums work with JSON serialization."""

    def test_retry_strategy_value_roundtrip(self):
        """RetryStrategy values can be used for JSON serialization."""
        import json
        for strategy in RetryStrategy:
            # Value can be serialized to JSON
            serialized = json.dumps(strategy.value)
            # And deserialized back to get the enum
            deserialized = json.loads(serialized)
            assert RetryStrategy(deserialized) == strategy

    def test_error_category_value_roundtrip(self):
        """ErrorCategory values can be used for JSON serialization."""
        import json
        for category in ErrorCategory:
            # Value can be serialized to JSON
            serialized = json.dumps(category.value)
            # And deserialized back to get the enum
            deserialized = json.loads(serialized)
            assert ErrorCategory(deserialized) == category