"""Unit tests for CoderAgent rich context format (Fix #1).

This test file validates the P0 Context Optimization Fix #1:
CoderAgent should use rich context format (with source code) instead of
basic format (just class names) when showing module registry to the LLM.

The rich format includes:
- Import statements
- Full class source code (fields, methods)
- Explicit warnings not to recreate classes

This prevents schema drift by eliminating ambiguity about what exists.
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any

from swarm_attack.agents.coder import CoderAgent
from swarm_attack.config import SwarmConfig
from swarm_attack.state_store import StateStore


@pytest.fixture
def mock_config(tmp_path: Path):
    """Create mock SwarmConfig with tmp_path as repo_root.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        SwarmConfig configured for testing.
    """
    from unittest.mock import MagicMock

    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.state_path = tmp_path / ".swarm" / "state"

    # Create necessary directories
    config.specs_path.mkdir(parents=True, exist_ok=True)
    if hasattr(config, 'state_path'):
        config.state_path.mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def sample_registry(tmp_path: Path) -> dict[str, Any]:
    """Create sample module registry with test files on disk.

    Creates a simple Python module with a dataclass for testing.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        Module registry dict compatible with StateStore.get_module_registry().
    """
    # Create a test file with a dataclass
    test_file = tmp_path / "swarm_attack" / "models" / "session.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text('''from dataclasses import dataclass, field
from typing import Any

@dataclass
class AutopilotSession:
    """Represents an autopilot session."""
    session_id: str
    feature_id: str
    started_at: str
    goals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "feature_id": self.feature_id,
            "started_at": self.started_at,
            "goals": self.goals,
        }

    def add_goal(self, goal: str) -> None:
        """Add a goal to the session."""
        self.goals.append(goal)
''')

    return {
        "modules": {
            "swarm_attack/models/session.py": {
                "created_by_issue": 1,
                "classes": ["AutopilotSession"],
            }
        }
    }


class TestCoderRichContextFormat:
    """Tests for CoderAgent using rich module registry format.

    These tests verify that _format_module_registry() uses the rich format
    from ContextBuilder instead of the basic class-name-only format.
    """

    def test_format_module_registry_shows_source_code(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        sample_registry: dict[str, Any],
    ) -> None:
        """Formatted registry should include class source code.

        The current basic format only shows class names:
        - `swarm_attack/models/session.py` (issue #1): AutopilotSession

        The rich format should show actual source code with fields and methods,
        enabling the coder to understand interfaces without guessing.
        """
        # Update config to use tmp_path
        mock_config.repo_root = str(tmp_path)

        # Create coder agent with StateStore
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Act: Format the registry
        result = coder._format_module_registry(sample_registry)

        # Assert: Should contain source code elements, not just class names
        assert "session_id: str" in result, "Should show field definitions"
        assert "feature_id: str" in result, "Should show all field definitions"
        assert "def to_dict" in result, "Should show method signatures"
        assert "def add_goal" in result, "Should show all methods"

        # Should contain warnings about not recreating
        assert (
            "DO NOT RECREATE" in result or "MUST IMPORT" in result
        ), "Should warn against recreating classes"

    def test_format_module_registry_shows_import_statement(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
    ) -> None:
        """Formatted registry should show how to import the class.

        The rich format must include import statements so the coder knows
        exactly how to use existing classes.
        """
        # Create test file
        test_file = tmp_path / "swarm_attack" / "models" / "user.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('''class User:
    """User model."""

    def __init__(self, username: str):
        self.username = username

    def get_name(self) -> str:
        """Get username."""
        return self.username
''')

        registry = {
            "modules": {
                "swarm_attack/models/user.py": {
                    "created_by_issue": 1,
                    "classes": ["User"],
                }
            }
        }

        mock_config.repo_root = str(tmp_path)
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Act
        result = coder._format_module_registry(registry)

        # Assert: Import statement should be present
        assert "from swarm_attack.models.user import User" in result, (
            "Should show explicit import statement"
        )

    def test_format_module_registry_truncates_large_classes(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
    ) -> None:
        """Large classes should be truncated to stay within token budget.

        The rich format can produce ~500 tokens per class. For very large
        classes (>2000 chars), it should truncate to prevent prompt explosion.
        """
        # Create file with large class (> 2000 chars)
        large_class_code = "@dataclass\nclass LargeClass:\n    " + "\n    ".join(
            f'field{i}: str = "default{i}"' for i in range(100)
        )

        test_file = tmp_path / "swarm_attack" / "models" / "large.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(large_class_code)

        registry = {
            "modules": {
                "swarm_attack/models/large.py": {
                    "created_by_issue": 1,
                    "classes": ["LargeClass"],
                }
            }
        }

        mock_config.repo_root = str(tmp_path)
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Act
        result = coder._format_module_registry(registry)

        # Assert: Should be truncated but still provide useful context
        # The ContextBuilder.format_module_registry_with_source has default
        # max_chars_per_class=3000 but typically uses 2000
        # Entire result should be under a reasonable limit
        assert len(result) < 10000, (
            "Result should be truncated to reasonable size"
        )

        # Should indicate truncation
        assert (
            "truncated" in result.lower() or "..." in result
        ), "Should indicate when content is truncated"

    def test_format_module_registry_empty_returns_message(
        self,
        mock_config: SwarmConfig,
    ) -> None:
        """Empty registry should return informative message.

        When no prior modules exist, should return a clear message
        rather than empty string or error.
        """
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Test with None
        result_none = coder._format_module_registry(None)
        assert "No prior modules" in result_none

        # Test with empty dict
        result_empty = coder._format_module_registry({})
        assert "No prior modules" in result_empty

        # Test with modules key but no modules
        result_no_modules = coder._format_module_registry({"modules": {}})
        assert "No prior modules" in result_no_modules

    def test_format_module_registry_multiple_classes(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
    ) -> None:
        """Registry with multiple classes should format all of them.

        Tests that the rich format correctly handles multiple classes
        from the same file and multiple files.
        """
        # Create file with multiple classes
        test_file = tmp_path / "swarm_attack" / "models" / "multi.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('''from dataclasses import dataclass

@dataclass
class ClassA:
    """First class."""
    field_a: str

@dataclass
class ClassB:
    """Second class."""
    field_b: int

    def process(self) -> int:
        """Process the field."""
        return self.field_b * 2
''')

        registry = {
            "modules": {
                "swarm_attack/models/multi.py": {
                    "created_by_issue": 1,
                    "classes": ["ClassA", "ClassB"],
                }
            }
        }

        mock_config.repo_root = str(tmp_path)
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Act
        result = coder._format_module_registry(registry)

        # Assert: Both classes should be present
        assert "ClassA" in result
        assert "ClassB" in result
        assert "field_a: str" in result
        assert "field_b: int" in result
        assert "def process" in result

        # Should show import for both
        assert "from swarm_attack.models.multi import ClassA, ClassB" in result

    def test_format_module_registry_preserves_decorators(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
    ) -> None:
        """Rich format should preserve decorators in class source.

        Decorators like @dataclass are critical for understanding class behavior.
        They should be included in the source code shown to the coder.
        """
        test_file = tmp_path / "swarm_attack" / "models" / "decorated.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('''from dataclasses import dataclass, field

@dataclass
class DecoratedClass:
    """A dataclass with decorators."""
    name: str
    count: int = 0
    items: list[str] = field(default_factory=list)
''')

        registry = {
            "modules": {
                "swarm_attack/models/decorated.py": {
                    "created_by_issue": 1,
                    "classes": ["DecoratedClass"],
                }
            }
        }

        mock_config.repo_root = str(tmp_path)
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Act
        result = coder._format_module_registry(registry)

        # Assert: Decorator should be visible
        assert "@dataclass" in result, "Should show @dataclass decorator"
        assert "field(default_factory=list)" in result, (
            "Should show field() usage for mutable defaults"
        )

    def test_format_module_registry_handles_missing_files_gracefully(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
    ) -> None:
        """Registry referencing nonexistent files should not crash.

        If a file is deleted or moved after being registered,
        the formatter should handle it gracefully.
        """
        # Registry points to file that doesn't exist
        registry = {
            "modules": {
                "swarm_attack/models/missing.py": {
                    "created_by_issue": 1,
                    "classes": ["MissingClass"],
                }
            }
        }

        mock_config.repo_root = str(tmp_path)
        state_store = StateStore(mock_config)
        coder = CoderAgent(mock_config, state_store=state_store)

        # Act - should not raise
        result = coder._format_module_registry(registry)

        # Assert: Should return something (possibly fallback message or empty)
        assert isinstance(result, str)
        # Should either skip the missing file or show a basic entry
        # The exact behavior depends on implementation, but shouldn't crash
