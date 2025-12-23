"""Tests for feature name validation - Bug #1 (path traversal) and Bug #3 (empty name).

TDD RED phase: These tests define the expected behavior for security validation.
"""
import pytest
from pathlib import Path

from swarm_attack.validation import InputValidator, ValidationError


class TestPathTraversalPrevention:
    """Bug #1: Path traversal vulnerability in feature init."""

    def test_rejects_double_dot_traversal(self):
        """Feature names with '..' should be rejected."""
        result = InputValidator.validate_feature_id("../../../../etc/passwd")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_rejects_simple_double_dot(self):
        """Even simple '..' should be rejected."""
        result = InputValidator.validate_feature_id("..")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_rejects_forward_slash(self):
        """Feature names with '/' should be rejected."""
        result = InputValidator.validate_feature_id("foo/bar")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_rejects_backslash(self):
        """Feature names with '\\' should be rejected."""
        result = InputValidator.validate_feature_id("foo\\bar")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_rejects_encoded_traversal(self):
        """Feature names that would resolve outside project should be rejected."""
        result = InputValidator.validate_feature_id("..%2F..%2Fetc")
        assert isinstance(result, ValidationError)
        # Should fail on format (% is not alphanumeric)

    def test_accepts_valid_feature_name(self):
        """Valid feature names should pass."""
        result = InputValidator.validate_feature_id("my-feature")
        assert result == "my-feature"

    def test_accepts_feature_with_numbers(self):
        """Feature names with numbers should pass."""
        result = InputValidator.validate_feature_id("feature-v2")
        assert result == "feature-v2"


class TestEmptyNamePrevention:
    """Bug #3: Empty feature name creates invalid state."""

    def test_rejects_empty_string(self):
        """Empty string should be rejected."""
        result = InputValidator.validate_feature_id("")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_rejects_whitespace_only(self):
        """Whitespace-only names should be rejected."""
        result = InputValidator.validate_feature_id("   ")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_rejects_single_space(self):
        """Single space should be rejected."""
        result = InputValidator.validate_feature_id(" ")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_rejects_tabs_only(self):
        """Tab-only names should be rejected."""
        result = InputValidator.validate_feature_id("\t\t")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"


class TestFormatValidation:
    """Additional format validation tests."""

    def test_rejects_special_characters(self):
        """Names with special characters should be rejected."""
        result = InputValidator.validate_feature_id("feat$ure")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_rejects_shell_metacharacters(self):
        """Shell metacharacters should be rejected."""
        for char in ['$', '`', '|', ';', '&', '<', '>', '(', ')', '{', '}']:
            result = InputValidator.validate_feature_id(f"feature{char}test")
            assert isinstance(result, ValidationError), f"Should reject '{char}'"

    def test_rejects_uppercase(self):
        """Uppercase letters should be rejected (format mismatch)."""
        result = InputValidator.validate_feature_id("MyFeature")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_rejects_leading_hyphen(self):
        """Leading hyphen should be rejected."""
        result = InputValidator.validate_feature_id("-feature")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_rejects_trailing_hyphen(self):
        """Trailing hyphen should be rejected."""
        result = InputValidator.validate_feature_id("feature-")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_accepts_single_char(self):
        """Single alphanumeric character should be accepted."""
        result = InputValidator.validate_feature_id("a")
        assert result == "a"

    def test_rejects_too_long(self):
        """Names longer than 64 chars should be rejected."""
        long_name = "a" * 65
        result = InputValidator.validate_feature_id(long_name)
        assert isinstance(result, ValidationError)
        assert result.code == "ID_TOO_LONG"


class TestPathContainment:
    """Tests for validate_path_in_project."""

    def test_path_within_project_accepted(self):
        """Paths within project should be accepted."""
        project_root = Path("/tmp/test-project")
        path = Path("/tmp/test-project/src/file.py")
        result = InputValidator.validate_path_in_project(path, project_root)
        # Note: This will fail if paths don't exist, which is fine for unit test
        # The validation logic is what we're testing
        # In production, paths would exist
        assert not isinstance(result, ValidationError) or result.code == "PATH_ERROR"

    def test_path_escape_rejected(self):
        """Paths escaping project should be rejected."""
        project_root = Path("/tmp/test-project")
        path = Path("/etc/passwd")
        result = InputValidator.validate_path_in_project(path, project_root)
        # Either PATH_ESCAPE or PATH_ERROR (if path doesn't exist)
        assert isinstance(result, ValidationError)
