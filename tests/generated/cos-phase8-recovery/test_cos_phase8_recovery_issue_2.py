"""Tests for classify_error() function.

Verifies that classify_error() correctly maps LLMErrorType patterns to ErrorCategory.
"""

import pytest
from swarm_attack.chief_of_staff.recovery import classify_error, ErrorCategory
from swarm_attack.errors import LLMError, LLMErrorType


class TestClassifyErrorTransient:
    """Test that transient errors are correctly classified."""

    def test_rate_limit_is_transient(self):
        """RATE_LIMIT errors should classify as TRANSIENT."""
        error = LLMError("Rate limit hit", error_type=LLMErrorType.RATE_LIMIT)
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_rate_limit_timed_is_transient(self):
        """RATE_LIMIT_TIMED errors should classify as TRANSIENT."""
        error = LLMError("Rate limit with timer", error_type=LLMErrorType.RATE_LIMIT_TIMED)
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_server_overloaded_is_transient(self):
        """SERVER_OVERLOADED errors should classify as TRANSIENT."""
        error = LLMError("Server overloaded", error_type=LLMErrorType.SERVER_OVERLOADED)
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_server_error_is_transient(self):
        """SERVER_ERROR errors should classify as TRANSIENT."""
        error = LLMError("Server error", error_type=LLMErrorType.SERVER_ERROR)
        assert classify_error(error) == ErrorCategory.TRANSIENT

    def test_timeout_is_transient(self):
        """TIMEOUT errors should classify as TRANSIENT."""
        error = LLMError("Timeout", error_type=LLMErrorType.TIMEOUT)
        assert classify_error(error) == ErrorCategory.TRANSIENT


class TestClassifyErrorSystematic:
    """Test that systematic errors are correctly classified."""

    def test_cli_crash_is_systematic(self):
        """CLI_CRASH errors should classify as SYSTEMATIC."""
        error = LLMError("CLI crashed", error_type=LLMErrorType.CLI_CRASH)
        assert classify_error(error) == ErrorCategory.SYSTEMATIC

    def test_json_parse_error_is_systematic(self):
        """JSON_PARSE_ERROR errors should classify as SYSTEMATIC."""
        error = LLMError("JSON parse failed", error_type=LLMErrorType.JSON_PARSE_ERROR)
        assert classify_error(error) == ErrorCategory.SYSTEMATIC


class TestClassifyErrorFatal:
    """Test that fatal errors are correctly classified."""

    def test_auth_required_is_fatal(self):
        """AUTH_REQUIRED errors should classify as FATAL."""
        error = LLMError("Auth required", error_type=LLMErrorType.AUTH_REQUIRED)
        assert classify_error(error) == ErrorCategory.FATAL

    def test_auth_expired_is_fatal(self):
        """AUTH_EXPIRED errors should classify as FATAL."""
        error = LLMError("Auth expired", error_type=LLMErrorType.AUTH_EXPIRED)
        assert classify_error(error) == ErrorCategory.FATAL

    def test_cli_not_found_is_fatal(self):
        """CLI_NOT_FOUND errors should classify as FATAL."""
        error = LLMError("CLI not found", error_type=LLMErrorType.CLI_NOT_FOUND)
        assert classify_error(error) == ErrorCategory.FATAL


class TestClassifyErrorUnknown:
    """Test that unknown errors default to FATAL (fail-safe)."""

    def test_unknown_error_type_is_fatal(self):
        """UNKNOWN error type should classify as FATAL (fail-safe)."""
        error = LLMError("Unknown error", error_type=LLMErrorType.UNKNOWN)
        assert classify_error(error) == ErrorCategory.FATAL


class TestClassifyErrorGenericExceptions:
    """Test handling of generic exceptions (non-LLMError)."""

    def test_generic_exception_defaults_to_fatal(self):
        """Generic Exception without error_type should default to FATAL."""
        error = Exception("Some error")
        assert classify_error(error) == ErrorCategory.FATAL

    def test_value_error_defaults_to_fatal(self):
        """ValueError should default to FATAL."""
        error = ValueError("Invalid value")
        assert classify_error(error) == ErrorCategory.FATAL

    def test_runtime_error_defaults_to_fatal(self):
        """RuntimeError should default to FATAL."""
        error = RuntimeError("Runtime failure")
        assert classify_error(error) == ErrorCategory.FATAL

    def test_type_error_defaults_to_fatal(self):
        """TypeError should default to FATAL."""
        error = TypeError("Type mismatch")
        assert classify_error(error) == ErrorCategory.FATAL


class TestClassifyErrorEdgeCases:
    """Test edge cases for classify_error()."""

    def test_handles_llm_error_with_error_type_attribute(self):
        """Should correctly access error_type attribute from LLMError."""
        error = LLMError("Test", error_type=LLMErrorType.TIMEOUT)
        # Verify the function works with the actual LLMError class
        result = classify_error(error)
        assert result == ErrorCategory.TRANSIENT

    def test_handles_exception_without_error_type_attribute(self):
        """Should handle exceptions without error_type attribute gracefully."""
        error = OSError("File not found")
        # Should not raise AttributeError
        result = classify_error(error)
        assert result == ErrorCategory.FATAL

    def test_handles_none_error_type_as_fatal(self):
        """If error_type is somehow None, should treat as FATAL."""
        # Create a mock-like exception with None error_type
        class MockError(Exception):
            error_type = None
        
        error = MockError("Mock error")
        result = classify_error(error)
        assert result == ErrorCategory.FATAL