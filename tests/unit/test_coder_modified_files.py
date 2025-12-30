"""Unit tests for CoderAgent modified file tracking (Fix #2).

Tests for tracking classes in modified files via _extract_outputs(files_modified=...).
This is the RED phase of TDD - tests should FAIL initially because the new methods
don't exist yet in CoderAgent.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock


class TestCoderModifiedFileTracking:
    """Tests for tracking classes in modified files."""

    def test_extract_outputs_tracks_new_file_classes(self, tmp_path):
        """Classes in new files should be tracked (existing behavior)."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create mock config
        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # New files dict (in-memory, not on disk)
        files = {
            "models/user.py": "class User:\n    pass\n\nclass UserFactory:\n    pass"
        }

        # Act: Extract outputs with only new files
        result = coder._extract_outputs(files)

        # Assert: New files should be tracked
        assert "models/user.py" in result.classes_defined
        assert "User" in result.classes_defined["models/user.py"]
        assert "UserFactory" in result.classes_defined["models/user.py"]

    def test_extract_outputs_tracks_modified_file_classes(self, tmp_path):
        """Classes in modified files should be tracked (new behavior)."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create existing file on disk
        existing_file = tmp_path / "models" / "existing.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text('''class ExistingClass:
    pass

class AddedClass:
    """Added by modification"""
    pass
''')

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Extract with modified file (no new files)
        result = coder._extract_outputs(
            files={},
            files_modified=["models/existing.py"],
        )

        # Assert: Modified file classes should be tracked
        assert "models/existing.py" in result.classes_defined
        assert "ExistingClass" in result.classes_defined["models/existing.py"]
        assert "AddedClass" in result.classes_defined["models/existing.py"]

    def test_extract_outputs_merges_new_and_modified(self, tmp_path):
        """Both new and modified files should be tracked together."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create existing file on disk
        existing_file = tmp_path / "models" / "existing.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("class ExistingClass:\n    pass")

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Extract with both new file and modified file
        files = {"models/new.py": "class NewClass:\n    pass"}
        files_modified = ["models/existing.py"]

        result = coder._extract_outputs(files, files_modified=files_modified)

        # Assert: Both new and modified files should be tracked
        assert "models/new.py" in result.classes_defined
        assert "models/existing.py" in result.classes_defined
        assert "NewClass" in result.classes_defined["models/new.py"]
        assert "ExistingClass" in result.classes_defined["models/existing.py"]

    def test_extract_outputs_handles_missing_modified_file(self, tmp_path):
        """Missing modified files should be skipped gracefully."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange
        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Extract with non-existent modified file
        files = {}
        files_modified = ["models/nonexistent.py"]  # Does not exist

        result = coder._extract_outputs(files, files_modified=files_modified)

        # Assert: Should not raise, should have empty classes_defined
        assert result.classes_defined == {}

    def test_extract_outputs_deduplicates_same_file_in_both_lists(self, tmp_path):
        """If same file is in both new files and modified files, merge classes."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create existing file with one class
        existing_file = tmp_path / "models" / "session.py"
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text('''class SessionState:
    pass

class AutopilotSession:
    pass
''')

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Same file appears in both new files (in-memory) and modified files (on disk)
        # This is an edge case but should be handled gracefully
        files = {"models/session.py": "class InMemoryClass:\n    pass"}
        files_modified = ["models/session.py"]

        result = coder._extract_outputs(files, files_modified=files_modified)

        # Assert: Should merge classes from both sources
        assert "models/session.py" in result.classes_defined
        classes = result.classes_defined["models/session.py"]
        # From in-memory new file
        assert "InMemoryClass" in classes
        # From on-disk modified file (merged)
        assert "SessionState" in classes or "AutopilotSession" in classes

    def test_extract_outputs_handles_non_python_modified_files(self, tmp_path):
        """Non-Python modified files should be skipped for class extraction."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create non-Python file
        yaml_file = tmp_path / "config" / "settings.yaml"
        yaml_file.parent.mkdir(parents=True, exist_ok=True)
        yaml_file.write_text("version: 1.0")

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Extract with non-Python modified file
        result = coder._extract_outputs(
            files={},
            files_modified=["config/settings.yaml"],
        )

        # Assert: Should not track classes for non-Python files
        assert "config/settings.yaml" not in result.classes_defined


class TestExtractClassesFromContent:
    """Tests for class extraction helper."""

    def test_extracts_python_classes(self, tmp_path):
        """Should extract Python class definitions."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        content = '''
class SimpleClass:
    pass

class ClassWithBase(BaseClass):
    pass

@dataclass
class DataClass:
    field: str
'''
        result = coder._extract_classes_from_content("test.py", content)

        assert "SimpleClass" in result
        assert "ClassWithBase" in result
        assert "DataClass" in result

    def test_extracts_typescript_classes(self, tmp_path):
        """Should extract TypeScript class definitions."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        content = '''
class SimpleClass {}

export class ExportedClass {}

abstract class AbstractClass {}
'''
        result = coder._extract_classes_from_content("test.ts", content)

        assert "SimpleClass" in result
        assert "ExportedClass" in result
        assert "AbstractClass" in result

    def test_extracts_dart_classes(self, tmp_path):
        """Should extract Dart class definitions."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        content = '''
class DartClass {
  final String name;
}

abstract class AbstractDartClass {}
'''
        result = coder._extract_classes_from_content("test.dart", content)

        assert "DartClass" in result
        assert "AbstractDartClass" in result

    def test_returns_empty_for_unsupported_extension(self, tmp_path):
        """Should return empty list for unsupported file types."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        result = coder._extract_classes_from_content("test.txt", "class Foo {}")

        assert result == []

    def test_handles_empty_content(self, tmp_path):
        """Should return empty list for empty content."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        result = coder._extract_classes_from_content("test.py", "")

        assert result == []

    def test_handles_nested_classes_python(self, tmp_path):
        """Should extract nested class definitions in Python."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        content = '''
class OuterClass:
    class InnerClass:
        pass
'''
        result = coder._extract_classes_from_content("test.py", content)

        # Both outer and inner classes should be extracted
        assert "OuterClass" in result
        assert "InnerClass" in result


class TestParseModifiedFiles:
    """Tests for parsing modified file patterns from LLM response."""

    def test_parse_modified_files_extracts_patterns(self, tmp_path):
        """Should parse various modified file patterns from LLM response."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        response = '''
I'll modify the existing file:
# MODIFIED FILE: models/session.py

And update another:
Modified: `utils/helpers.py`

Updated: config/settings.py
'''

        result = coder._parse_modified_files(response)

        assert "models/session.py" in result
        assert "utils/helpers.py" in result
        assert "config/settings.py" in result

    def test_parse_modified_files_handles_no_markers(self, tmp_path):
        """Should return empty list when no modified file markers found."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        response = '''
I created some new files:
# FILE: models/user.py
class User:
    pass
'''

        result = coder._parse_modified_files(response)

        assert result == []

    def test_parse_modified_files_deduplicates(self, tmp_path):
        """Should deduplicate file paths mentioned multiple times."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        response = '''
# MODIFIED FILE: models/session.py
Modified: models/session.py
Updated: `models/session.py`
'''

        result = coder._parse_modified_files(response)

        # Should only appear once
        assert result.count("models/session.py") == 1

    def test_parse_modified_files_with_whitespace_variations(self, tmp_path):
        """Should handle various whitespace patterns around markers."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        response = '''
#MODIFIED FILE: no_space.py
# MODIFIED FILE:  extra_space.py
Modified:`backticks.py`
Updated:  spaces.py
'''

        result = coder._parse_modified_files(response)

        assert "no_space.py" in result
        assert "extra_space.py" in result
        assert "backticks.py" in result
        assert "spaces.py" in result

    def test_parse_modified_files_only_matches_python_files(self, tmp_path):
        """Should only match .py files in current implementation."""
        from swarm_attack.agents.coder import CoderAgent

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        response = '''
# MODIFIED FILE: models/session.py
# MODIFIED FILE: config.yaml
Modified: utils/helpers.py
Modified: README.md
'''

        result = coder._parse_modified_files(response)

        # Only .py files should be matched
        assert "models/session.py" in result
        assert "utils/helpers.py" in result
        # Non-Python files should NOT be matched
        assert "config.yaml" not in result
        assert "README.md" not in result


class TestExtractOutputsIntegration:
    """Integration tests for _extract_outputs with both new and modified files."""

    def test_realistic_workflow_new_and_modified_files(self, tmp_path):
        """Test realistic workflow with both new files and modified files."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create existing module with base classes
        base_file = tmp_path / "swarm_attack" / "models" / "base.py"
        base_file.parent.mkdir(parents=True, exist_ok=True)
        base_file.write_text('''class BaseModel:
    """Base model class"""
    pass

class ExtendedModel(BaseModel):
    """Extended by Issue #5"""
    pass
''')

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Create new session.py file AND modify base.py
        new_files = {
            "swarm_attack/models/session.py": '''class AutopilotSession:
    session_id: str

class SessionState:
    active: bool
'''
        }

        modified_files = ["swarm_attack/models/base.py"]

        result = coder._extract_outputs(new_files, files_modified=modified_files)

        # Assert: Should track classes from BOTH sources
        assert "swarm_attack/models/session.py" in result.classes_defined
        assert "AutopilotSession" in result.classes_defined["swarm_attack/models/session.py"]
        assert "SessionState" in result.classes_defined["swarm_attack/models/session.py"]

        assert "swarm_attack/models/base.py" in result.classes_defined
        assert "BaseModel" in result.classes_defined["swarm_attack/models/base.py"]
        assert "ExtendedModel" in result.classes_defined["swarm_attack/models/base.py"]

        # Files created should only include new files
        assert "swarm_attack/models/session.py" in result.files_created
        assert "swarm_attack/models/base.py" not in result.files_created

    def test_typescript_modified_file_tracking(self, tmp_path):
        """Test that TypeScript modified files are tracked correctly."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create existing TypeScript file
        ts_file = tmp_path / "src" / "services" / "api.ts"
        ts_file.parent.mkdir(parents=True, exist_ok=True)
        ts_file.write_text('''export class ApiService {
    baseUrl: string;
}

class InternalHelper {
    process() {}
}
''')

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Track modified TypeScript file
        result = coder._extract_outputs(
            files={},
            files_modified=["src/services/api.ts"],
        )

        # Assert: TypeScript classes should be extracted
        assert "src/services/api.ts" in result.classes_defined
        assert "ApiService" in result.classes_defined["src/services/api.ts"]
        assert "InternalHelper" in result.classes_defined["src/services/api.ts"]

    def test_dart_modified_file_tracking(self, tmp_path):
        """Test that Dart modified files are tracked correctly."""
        from swarm_attack.agents.coder import CoderAgent

        # Arrange: Create existing Dart file
        dart_file = tmp_path / "lib" / "models" / "user.dart"
        dart_file.parent.mkdir(parents=True, exist_ok=True)
        dart_file.write_text('''class User {
  final String id;
  final String name;
}

class UserProfile extends User {
  final String bio;
}
''')

        mock_config = MagicMock()
        mock_config.repo_root = tmp_path
        mock_config.specs_path = tmp_path / "specs"

        coder = CoderAgent(config=mock_config)

        # Act: Track modified Dart file
        result = coder._extract_outputs(
            files={},
            files_modified=["lib/models/user.dart"],
        )

        # Assert: Dart classes should be extracted
        assert "lib/models/user.dart" in result.classes_defined
        assert "User" in result.classes_defined["lib/models/user.dart"]
        assert "UserProfile" in result.classes_defined["lib/models/user.dart"]
