"""Tests for centralized input validation."""
import pytest
from pathlib import Path
from swarm_attack.validation import InputValidator, ValidationError


class TestValidateFeatureId:
    """Tests for feature ID validation."""

    def test_valid_simple_id(self):
        """Accept simple lowercase alphanumeric."""
        assert InputValidator.validate_feature_id("myfeature") == "myfeature"

    def test_valid_with_hyphens(self):
        """Accept hyphens in middle."""
        assert InputValidator.validate_feature_id("my-feature-v2") == "my-feature-v2"

    def test_valid_single_char(self):
        """Accept single character."""
        assert InputValidator.validate_feature_id("a") == "a"

    def test_valid_with_numbers(self):
        """Accept numbers."""
        assert InputValidator.validate_feature_id("feature123") == "feature123"
        assert InputValidator.validate_feature_id("123feature") == "123feature"

    def test_reject_empty(self):
        """Reject empty string."""
        result = InputValidator.validate_feature_id("")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_reject_whitespace_only(self):
        """Reject whitespace-only string."""
        result = InputValidator.validate_feature_id("   ")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_reject_path_traversal(self):
        """Reject path traversal attempts."""
        result = InputValidator.validate_feature_id("../../../etc/passwd")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_reject_path_traversal_middle(self):
        """Reject path traversal in the middle."""
        result = InputValidator.validate_feature_id("foo/../bar")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_reject_shell_metachar_dollar(self):
        """Reject shell metacharacters."""
        result = InputValidator.validate_feature_id("$(whoami)")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_reject_shell_metachar_backtick(self):
        """Reject backtick command substitution."""
        result = InputValidator.validate_feature_id("`id`")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_reject_shell_metachar_pipe(self):
        """Reject pipe character."""
        result = InputValidator.validate_feature_id("foo|bar")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_reject_shell_metachar_semicolon(self):
        """Reject semicolon."""
        result = InputValidator.validate_feature_id("foo;rm -rf")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"

    def test_reject_leading_hyphen(self):
        """Reject leading hyphen."""
        result = InputValidator.validate_feature_id("-feature")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_reject_trailing_hyphen(self):
        """Reject trailing hyphen."""
        result = InputValidator.validate_feature_id("feature-")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_reject_uppercase(self):
        """Reject uppercase letters."""
        result = InputValidator.validate_feature_id("MyFeature")
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_FORMAT"

    def test_reject_too_long(self):
        """Reject IDs over 64 characters."""
        result = InputValidator.validate_feature_id("a" * 65)
        assert isinstance(result, ValidationError)
        assert result.code == "ID_TOO_LONG"

    def test_accept_max_length(self):
        """Accept IDs at exactly 64 characters."""
        long_id = "a" * 64
        assert InputValidator.validate_feature_id(long_id) == long_id

    def test_reject_slashes(self):
        """Reject forward and back slashes."""
        for char in ["/", "\\"]:
            result = InputValidator.validate_feature_id(f"my{char}feature")
            assert isinstance(result, ValidationError)
            assert result.code == "PATH_TRAVERSAL"


class TestValidateBugId:
    """Tests for bug ID validation."""

    def test_valid_with_hyphen(self):
        """Accept hyphens."""
        assert InputValidator.validate_bug_id("bug-123") == "bug-123"

    def test_valid_with_underscore(self):
        """Accept underscores (unlike feature IDs)."""
        assert InputValidator.validate_bug_id("bug_fix_auth") == "bug_fix_auth"

    def test_none_is_valid(self):
        """None is a valid input (returns None)."""
        assert InputValidator.validate_bug_id(None) is None

    def test_reject_empty(self):
        """Reject empty string."""
        result = InputValidator.validate_bug_id("")
        assert isinstance(result, ValidationError)
        assert result.code == "EMPTY_ID"

    def test_reject_path_traversal(self):
        """Reject path traversal."""
        result = InputValidator.validate_bug_id("../etc/passwd")
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_TRAVERSAL"

    def test_reject_shell_chars(self):
        """Reject shell metacharacters."""
        result = InputValidator.validate_bug_id("$(whoami)")
        assert isinstance(result, ValidationError)
        assert result.code == "UNSAFE_CHARS"


class TestValidatePositiveInt:
    """Tests for positive integer validation."""

    def test_valid_positive(self):
        """Accept positive integers."""
        assert InputValidator.validate_positive_int(1, "issue") == 1
        assert InputValidator.validate_positive_int(100, "issue") == 100

    def test_reject_zero(self):
        """Reject zero."""
        result = InputValidator.validate_positive_int(0, "issue")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_negative(self):
        """Reject negative numbers."""
        result = InputValidator.validate_positive_int(-1, "issue")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_too_large(self):
        """Reject numbers over max."""
        result = InputValidator.validate_positive_int(100001, "issue", max_val=100000)
        assert isinstance(result, ValidationError)
        assert result.code == "TOO_LARGE"

    def test_accept_at_max(self):
        """Accept numbers at max value."""
        assert InputValidator.validate_positive_int(100, "issue", max_val=100) == 100


class TestValidatePositiveFloat:
    """Tests for positive float validation."""

    def test_valid_positive(self):
        """Accept positive floats."""
        assert InputValidator.validate_positive_float(0.01, "budget") == 0.01
        assert InputValidator.validate_positive_float(100.0, "budget") == 100.0

    def test_reject_zero(self):
        """Reject zero."""
        result = InputValidator.validate_positive_float(0.0, "budget")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_negative(self):
        """Reject negative numbers."""
        result = InputValidator.validate_positive_float(-10.0, "budget")
        assert isinstance(result, ValidationError)
        assert result.code == "NOT_POSITIVE"

    def test_reject_too_large(self):
        """Reject numbers over max."""
        result = InputValidator.validate_positive_float(1001.0, "budget", max_val=1000.0)
        assert isinstance(result, ValidationError)
        assert result.code == "TOO_LARGE"


class TestValidatePathInProject:
    """Tests for path containment validation."""

    def test_valid_relative_path(self, tmp_path):
        """Accept paths within project."""
        project = tmp_path / "project"
        project.mkdir()
        subdir = project / "src"
        subdir.mkdir()

        result = InputValidator.validate_path_in_project(subdir, project)
        assert result == subdir.resolve()

    def test_reject_path_escape(self, tmp_path):
        """Reject paths that escape project."""
        project = tmp_path / "project"
        project.mkdir()
        escape_path = tmp_path / "outside"

        result = InputValidator.validate_path_in_project(escape_path, project)
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_ESCAPE"

    def test_reject_traversal_escape(self, tmp_path):
        """Reject traversal that escapes project."""
        project = tmp_path / "project"
        project.mkdir()
        traversal = project / ".." / ".." / "etc" / "passwd"

        result = InputValidator.validate_path_in_project(traversal, project)
        assert isinstance(result, ValidationError)
        assert result.code == "PATH_ESCAPE"

    def test_accept_nested_path(self, tmp_path):
        """Accept deeply nested paths."""
        project = tmp_path / "project"
        project.mkdir()
        deep = project / "a" / "b" / "c"
        deep.mkdir(parents=True)

        result = InputValidator.validate_path_in_project(deep, project)
        assert result == deep.resolve()


class TestValidateEnumValue:
    """Tests for enum validation."""

    def test_valid_value(self):
        """Accept valid enum value."""
        result = InputValidator.validate_enum_value(
            "test", ["test", "stalled", "quality"], "discovery_type"
        )
        assert result == "test"

    def test_case_insensitive(self):
        """Accept case-insensitive match, return lowercase."""
        result = InputValidator.validate_enum_value(
            "TEST", ["test", "stalled", "quality"], "discovery_type"
        )
        assert result == "test"

    def test_reject_invalid(self):
        """Reject invalid enum value."""
        result = InputValidator.validate_enum_value(
            "invalid", ["test", "stalled", "quality"], "discovery_type"
        )
        assert isinstance(result, ValidationError)
        assert result.code == "INVALID_ENUM"
        assert "test" in result.expected
        assert "stalled" in result.expected
