"""
Tests for ContextBuilder source code extraction functionality.

These tests validate the schema drift prevention mechanisms:
- _extract_class_source(): Extract class source code using AST
- _extract_class_schema(): Extract structured schema information
- format_module_registry_with_source(): Format registry with source code
- get_existing_class_names(): Build class name to file mapping
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swarm_attack.context_builder import ContextBuilder


@pytest.fixture
def temp_repo():
    """Create a temporary repository with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_repo):
    """Create a mock SwarmConfig."""
    config = MagicMock()
    config.repo_root = temp_repo
    return config


@pytest.fixture
def context_builder(mock_config):
    """Create a ContextBuilder instance."""
    return ContextBuilder(mock_config)


class TestPathToModule:
    """Tests for _path_to_module conversion."""

    def test_simple_path(self, context_builder):
        """Test simple file path conversion."""
        result = context_builder._path_to_module("swarm_attack/models.py")
        assert result == "swarm_attack.models"

    def test_nested_path(self, context_builder):
        """Test nested file path conversion."""
        result = context_builder._path_to_module("swarm_attack/chief_of_staff/models.py")
        assert result == "swarm_attack.chief_of_staff.models"

    def test_path_without_py(self, context_builder):
        """Test path without .py extension."""
        result = context_builder._path_to_module("swarm_attack/models")
        assert result == "swarm_attack.models"


class TestExtractClassSource:
    """Tests for _extract_class_source AST extraction."""

    def test_extract_simple_class(self, context_builder, temp_repo):
        """Test extracting a simple class definition."""
        test_file = temp_repo / "models.py"
        test_file.write_text('''
class SimpleClass:
    """A simple class."""
    name: str
    value: int

    def get_name(self) -> str:
        return self.name
''')
        source = context_builder._extract_class_source(test_file, "SimpleClass")
        assert "class SimpleClass:" in source
        assert "name: str" in source
        assert "def get_name" in source

    def test_extract_dataclass(self, context_builder, temp_repo):
        """Test extracting a dataclass with fields."""
        test_file = temp_repo / "models.py"
        test_file.write_text('''
from dataclasses import dataclass
from typing import Optional

@dataclass
class AutopilotSession:
    """Session for autopilot runs."""
    id: str
    started_at: str
    goals: list[str]
    ended_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {"id": self.id}
''')
        source = context_builder._extract_class_source(test_file, "AutopilotSession")
        assert "@dataclass" in source
        assert "class AutopilotSession:" in source
        assert "id: str" in source
        assert "goals: list[str]" in source
        assert "ended_at: Optional[str] = None" in source
        assert "def to_dict" in source

    def test_extract_nonexistent_class(self, context_builder, temp_repo):
        """Test extracting a class that doesn't exist."""
        test_file = temp_repo / "models.py"
        test_file.write_text("class OtherClass:\n    pass")
        source = context_builder._extract_class_source(test_file, "NonExistent")
        assert source == ""

    def test_extract_from_missing_file(self, context_builder, temp_repo):
        """Test extracting from a file that doesn't exist."""
        source = context_builder._extract_class_source(
            temp_repo / "nonexistent.py", "SomeClass"
        )
        assert source == ""

    def test_extract_from_invalid_python(self, context_builder, temp_repo):
        """Test extracting from a file with syntax errors."""
        test_file = temp_repo / "invalid.py"
        test_file.write_text("class Broken\n  invalid syntax here")
        source = context_builder._extract_class_source(test_file, "Broken")
        assert source == ""

    def test_extract_multiple_classes(self, context_builder, temp_repo):
        """Test extracting one class from a file with multiple classes."""
        test_file = temp_repo / "models.py"
        test_file.write_text('''
class FirstClass:
    first_field: str

class SecondClass:
    second_field: int

class ThirdClass:
    third_field: bool
''')
        source = context_builder._extract_class_source(test_file, "SecondClass")
        assert "class SecondClass:" in source
        assert "second_field: int" in source
        assert "FirstClass" not in source
        assert "ThirdClass" not in source


class TestExtractClassSchema:
    """Tests for _extract_class_schema structured extraction."""

    def test_extract_dataclass_schema(self, context_builder, temp_repo):
        """Test extracting schema from a dataclass."""
        test_file = temp_repo / "models.py"
        test_file.write_text('''
from dataclasses import dataclass
from typing import Optional, list

@dataclass
class AutopilotSession:
    id: str
    started_at: str
    goals: list[str]
    ended_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {}

    @classmethod
    def from_dict(cls, data: dict) -> "AutopilotSession":
        return cls(**data)
''')
        schema = context_builder._extract_class_schema(test_file, "AutopilotSession")

        assert schema["is_dataclass"] is True
        assert "to_dict" in schema["methods"]
        assert "from_dict" in schema["methods"]

        field_names = [f["name"] for f in schema["fields"]]
        assert "id" in field_names
        assert "started_at" in field_names
        assert "goals" in field_names
        assert "ended_at" in field_names

        # Check field types
        id_field = next(f for f in schema["fields"] if f["name"] == "id")
        assert id_field["type"] == "str"

        ended_at_field = next(f for f in schema["fields"] if f["name"] == "ended_at")
        assert ended_at_field["default"] == "None"

    def test_extract_regular_class_schema(self, context_builder, temp_repo):
        """Test extracting schema from a regular (non-dataclass) class."""
        test_file = temp_repo / "models.py"
        test_file.write_text('''
class RegularClass:
    name: str
    count: int = 0

    def increment(self):
        self.count += 1
''')
        schema = context_builder._extract_class_schema(test_file, "RegularClass")

        assert schema["is_dataclass"] is False
        assert "increment" in schema["methods"]

        field_names = [f["name"] for f in schema["fields"]]
        assert "name" in field_names
        assert "count" in field_names


class TestFormatModuleRegistryWithSource:
    """Tests for format_module_registry_with_source formatting."""

    def test_empty_registry(self, context_builder):
        """Test formatting an empty registry."""
        result = context_builder.format_module_registry_with_source({})
        assert "No prior modules" in result

    def test_registry_with_no_modules(self, context_builder):
        """Test formatting a registry with empty modules."""
        result = context_builder.format_module_registry_with_source({"modules": {}})
        assert "No prior modules" in result

    def test_registry_with_source(self, context_builder, temp_repo):
        """Test formatting a registry with actual source code."""
        # Create test file
        models_dir = temp_repo / "swarm_attack" / "models"
        models_dir.mkdir(parents=True)
        models_file = models_dir / "session.py"
        models_file.write_text('''
@dataclass
class Session:
    id: str
    status: str = "active"
''')

        registry = {
            "modules": {
                "swarm_attack/models/session.py": {
                    "created_by_issue": 1,
                    "classes": ["Session"],
                }
            }
        }

        result = context_builder.format_module_registry_with_source(registry)

        # Check structure
        assert "## Existing Classes (MUST IMPORT - DO NOT RECREATE)" in result
        assert "CRITICAL" in result
        assert "swarm_attack/models/session.py" in result
        assert "Issue #1" in result
        assert "from swarm_attack.models.session import Session" in result

        # Check source is included
        assert "class Session:" in result
        assert "id: str" in result

        # Check schema evolution guidance
        assert "Schema Evolution Rules" in result
        assert "EXTEND" in result
        assert "COMPOSE" in result
        assert "SEPARATE" in result

    def test_truncation_of_large_classes(self, context_builder, temp_repo):
        """Test that large classes are truncated."""
        # Create a file with a very large class
        test_file = temp_repo / "large.py"
        large_class = "class LargeClass:\n" + "\n".join(
            [f"    field_{i}: str = 'value'" for i in range(500)]
        )
        test_file.write_text(large_class)

        registry = {
            "modules": {
                "large.py": {
                    "created_by_issue": 1,
                    "classes": ["LargeClass"],
                }
            }
        }

        result = context_builder.format_module_registry_with_source(
            registry, max_chars_per_class=1000
        )

        # Should be truncated
        assert "truncated" in result


class TestGetExistingClassNames:
    """Tests for get_existing_class_names mapping."""

    def test_empty_registry(self, context_builder):
        """Test with empty registry."""
        result = context_builder.get_existing_class_names({})
        assert result == {}

    def test_single_class(self, context_builder):
        """Test with a single class."""
        registry = {
            "modules": {
                "models.py": {
                    "classes": ["Session"],
                }
            }
        }
        result = context_builder.get_existing_class_names(registry)
        assert result == {"Session": "models.py"}

    def test_multiple_classes_multiple_files(self, context_builder):
        """Test with multiple classes across multiple files."""
        registry = {
            "modules": {
                "models.py": {
                    "classes": ["Session", "User"],
                },
                "auth.py": {
                    "classes": ["Token", "Permission"],
                },
            }
        }
        result = context_builder.get_existing_class_names(registry)
        assert result == {
            "Session": "models.py",
            "User": "models.py",
            "Token": "auth.py",
            "Permission": "auth.py",
        }
