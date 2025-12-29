"""Centralized input validation with security-first approach.

Provides validators for:
- Feature and bug IDs (format, path traversal, shell injection)
- Positive integers and floats (budget, duration, issue numbers)
- Path containment (prevent directory escape)
- Enum values (discovery types, phases)
"""
from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path
import re


@dataclass
class ValidationError:
    """Structured validation error for consistent CLI output."""
    code: str           # e.g., "PATH_TRAVERSAL", "EMPTY_ID", "NOT_POSITIVE"
    message: str        # Human-readable description
    expected: str       # What format was expected
    got: str           # What was actually received
    hint: Optional[str] = None  # How to fix


class InputValidator:
    """Validates all user-facing inputs with security-first approach."""

    # Allowlist pattern for identifiers (lowercase alphanumeric with hyphens)
    IDENTIFIER_PATTERN = re.compile(r'^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$')

    # Bug ID pattern (allows underscores in addition to hyphens)
    BUG_ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]$|^[a-z0-9]$')

    # Characters that could enable shell injection
    UNSAFE_CHARS = re.compile(r'[$`|;&<>(){}[\]!#*?~]')

    # Path traversal indicators
    PATH_TRAVERSAL_PATTERN = re.compile(r'(^|/)\.\.(/|$)|[/\\]')

    @classmethod
    def validate_feature_id(cls, value: str) -> Union[str, ValidationError]:
        """Validate feature ID format and safety.

        Rules:
        - Non-empty
        - Max 64 characters
        - Matches IDENTIFIER_PATTERN
        - No path traversal (.., /, \\)
        - No shell metacharacters

        Args:
            value: The feature ID to validate

        Returns:
            The validated feature ID if valid, or ValidationError if invalid
        """
        # Check empty
        if not value or value.strip() == "":
            return ValidationError(
                code="EMPTY_ID",
                message="Feature ID cannot be empty",
                expected="non-empty lowercase alphanumeric string with hyphens",
                got=repr(value),
                hint="Use a name like 'my-feature' or 'feature-v2'"
            )

        # Check length
        if len(value) > 64:
            return ValidationError(
                code="ID_TOO_LONG",
                message=f"Feature ID too long ({len(value)} chars)",
                expected="maximum 64 characters",
                got=f"{len(value)} characters",
                hint="Use a shorter, descriptive name"
            )

        # Check for path traversal (.. or / or \)
        if '..' in value or '/' in value or '\\' in value:
            return ValidationError(
                code="PATH_TRAVERSAL",
                message="Feature ID contains path traversal characters",
                expected="simple name without path separators",
                got=repr(value),
                hint="Remove '..' and path separators from the ID"
            )

        # Check for shell metacharacters
        if cls.UNSAFE_CHARS.search(value):
            return ValidationError(
                code="UNSAFE_CHARS",
                message="Feature ID contains shell metacharacters",
                expected="alphanumeric characters and hyphens only",
                got=repr(value),
                hint="Remove special characters like $, `, |, ;, &, etc."
            )

        # Check format (lowercase alphanumeric with hyphens)
        if not cls.IDENTIFIER_PATTERN.match(value):
            return ValidationError(
                code="INVALID_FORMAT",
                message="Feature ID has invalid format",
                expected="lowercase alphanumeric, may contain hyphens (not leading/trailing)",
                got=repr(value),
                hint="Use lowercase letters, numbers, and hyphens. Example: 'my-feature-v2'"
            )

        return value

    @classmethod
    def validate_bug_id(cls, value: Optional[str]) -> Union[Optional[str], ValidationError]:
        """Validate bug ID format if provided.

        Same rules as feature_id, but allows None.
        Also allows underscores in addition to hyphens.

        Args:
            value: The bug ID to validate, or None

        Returns:
            The validated bug ID if valid, None if input was None, or ValidationError if invalid
        """
        if value is None:
            return None

        # Check empty
        if not value or value.strip() == "":
            return ValidationError(
                code="EMPTY_ID",
                message="Bug ID cannot be empty",
                expected="non-empty lowercase alphanumeric string with hyphens/underscores",
                got=repr(value),
                hint="Use a name like 'bug-123' or 'auth_failure'"
            )

        # Check length
        if len(value) > 64:
            return ValidationError(
                code="ID_TOO_LONG",
                message=f"Bug ID too long ({len(value)} chars)",
                expected="maximum 64 characters",
                got=f"{len(value)} characters",
                hint="Use a shorter, descriptive name"
            )

        # Check for path traversal
        if '..' in value or '/' in value or '\\' in value:
            return ValidationError(
                code="PATH_TRAVERSAL",
                message="Bug ID contains path traversal characters",
                expected="simple name without path separators",
                got=repr(value),
                hint="Remove '..' and path separators from the ID"
            )

        # Check for shell metacharacters
        if cls.UNSAFE_CHARS.search(value):
            return ValidationError(
                code="UNSAFE_CHARS",
                message="Bug ID contains shell metacharacters",
                expected="alphanumeric characters, hyphens, and underscores only",
                got=repr(value),
                hint="Remove special characters like $, `, |, ;, &, etc."
            )

        # Check format (lowercase alphanumeric with hyphens and underscores)
        if not cls.BUG_ID_PATTERN.match(value):
            return ValidationError(
                code="INVALID_FORMAT",
                message="Bug ID has invalid format",
                expected="lowercase alphanumeric, may contain hyphens/underscores (not leading/trailing)",
                got=repr(value),
                hint="Use lowercase letters, numbers, hyphens, underscores. Example: 'bug-123' or 'auth_fix'"
            )

        return value

    @classmethod
    def validate_positive_int(cls, value: int, name: str, max_val: int = 99999) -> Union[int, ValidationError]:
        """Validate positive integer parameter.

        Rules:
        - Must be >= 1
        - Must be <= max_val

        Args:
            value: The integer to validate
            name: Parameter name for error messages
            max_val: Maximum allowed value (default 99999)

        Returns:
            The validated integer if valid, or ValidationError if invalid
        """
        if value < 1:
            return ValidationError(
                code="NOT_POSITIVE",
                message=f"{name} must be a positive integer",
                expected="integer >= 1",
                got=str(value),
                hint=f"Provide a positive number for {name}"
            )

        if value > max_val:
            return ValidationError(
                code="TOO_LARGE",
                message=f"{name} exceeds maximum allowed value",
                expected=f"integer <= {max_val}",
                got=str(value),
                hint=f"Use a value no larger than {max_val}"
            )

        return value

    @classmethod
    def validate_positive_float(cls, value: float, name: str, max_val: float = 1000.0) -> Union[float, ValidationError]:
        """Validate positive float parameter.

        Rules:
        - Must be > 0
        - Must be <= max_val

        Args:
            value: The float to validate
            name: Parameter name for error messages
            max_val: Maximum allowed value (default 1000.0)

        Returns:
            The validated float if valid, or ValidationError if invalid
        """
        if value <= 0:
            return ValidationError(
                code="NOT_POSITIVE",
                message=f"{name} must be a positive number",
                expected="number > 0",
                got=str(value),
                hint=f"Provide a positive number for {name}"
            )

        if value > max_val:
            return ValidationError(
                code="TOO_LARGE",
                message=f"{name} exceeds maximum allowed value",
                expected=f"number <= {max_val}",
                got=str(value),
                hint=f"Use a value no larger than {max_val}"
            )

        return value

    @classmethod
    def validate_path_in_project(cls, path: Path, project_root: Path) -> Union[Path, ValidationError]:
        """Validate path doesn't escape project directory.

        Rules:
        - Resolve to absolute path
        - Must be within project_root after resolution
        - No symlink escape

        Args:
            path: The path to validate
            project_root: The project root directory

        Returns:
            The resolved absolute path if valid, or ValidationError if invalid
        """
        try:
            # Resolve to absolute, following symlinks
            resolved = path.resolve()
            root_resolved = project_root.resolve()

            # Check if path is within project root
            try:
                resolved.relative_to(root_resolved)
            except ValueError:
                return ValidationError(
                    code="PATH_ESCAPE",
                    message="Path escapes project directory",
                    expected=f"path within {root_resolved}",
                    got=str(resolved),
                    hint="Use a path inside the project directory"
                )

            return resolved

        except (OSError, RuntimeError) as e:
            return ValidationError(
                code="PATH_ERROR",
                message=f"Could not resolve path: {e}",
                expected="valid file system path",
                got=str(path),
                hint="Check that the path is valid"
            )

    @classmethod
    def validate_enum_value(cls, value: str, valid_values: list[str], name: str) -> Union[str, ValidationError]:
        """Validate value is one of allowed enum values.

        Case-insensitive comparison, returns lowercase.

        Args:
            value: The value to validate
            valid_values: List of allowed values (lowercase)
            name: Parameter name for error messages

        Returns:
            The validated value (lowercase) if valid, or ValidationError if invalid
        """
        lower_value = value.lower()

        if lower_value not in [v.lower() for v in valid_values]:
            return ValidationError(
                code="INVALID_ENUM",
                message=f"Invalid {name}: {value}",
                expected=f"one of: {', '.join(valid_values)}",
                got=value,
                hint=f"Choose from: {', '.join(valid_values)}"
            )

        return lower_value
