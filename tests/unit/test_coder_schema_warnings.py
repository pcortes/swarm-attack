"""Unit tests for CoderAgent schema warning injection.

TDD Tests for schema drift prevention via memory-based pre-implementation warnings.
These tests are written BEFORE implementation (RED phase).

The schema warning feature:
1. Extracts potential class names from issue body text
2. Queries memory store for prior schema drift conflicts
3. Injects warnings into the coder prompt before task context
4. Handles edge cases gracefully (no warnings, no memory store)

Test file: tests/unit/test_coder_schema_warnings.py
"""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, Mock, patch

from swarm_attack.agents.coder import CoderAgent
from swarm_attack.config import SwarmConfig
from swarm_attack.memory.store import MemoryStore, MemoryEntry


@pytest.fixture
def mock_config(tmp_path: Path) -> MagicMock:
    """Create mock SwarmConfig with tmp_path as repo_root.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Returns:
        SwarmConfig configured for testing.
    """
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.state_path = tmp_path / ".swarm" / "state"
    config.skills_path = tmp_path / ".claude" / "skills"

    # Create necessary directories
    config.specs_path.mkdir(parents=True, exist_ok=True)
    config.state_path.mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def mock_memory_store() -> MagicMock:
    """Create a mock MemoryStore for testing.

    Returns:
        MagicMock configured to behave like MemoryStore.
    """
    store = MagicMock(spec=MemoryStore)
    store.query.return_value = []
    return store


@pytest.fixture
def coder_agent(mock_config: MagicMock) -> CoderAgent:
    """Create a CoderAgent instance for testing without memory store.

    Args:
        mock_config: Mock configuration fixture.

    Returns:
        CoderAgent instance.
    """
    return CoderAgent(mock_config, memory_store=None)


@pytest.fixture
def coder_agent_with_memory(
    mock_config: MagicMock, mock_memory_store: MagicMock
) -> CoderAgent:
    """Create a CoderAgent instance with mock memory store.

    Args:
        mock_config: Mock configuration fixture.
        mock_memory_store: Mock memory store fixture.

    Returns:
        CoderAgent instance with memory store.
    """
    return CoderAgent(mock_config, memory_store=mock_memory_store)


class TestCoderExtractPotentialClasses:
    """Tests for _extract_potential_classes() method.

    This method extracts class names from issue body text by parsing:
    - Interface Contract sections
    - Acceptance Criteria sections
    - Backtick-enclosed class names (e.g., `ResultParser`)
    - Method call patterns (e.g., `ResultParser.parse()` -> extracts 'ResultParser')
    """

    def test_extracts_single_class_from_backticks(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should extract a single class name from backticks in issue body."""
        issue_body = """
        ## Acceptance Criteria
        - Create `ResultParser` class that handles parsing
        """

        classes = coder_agent._extract_potential_classes(issue_body)

        assert "ResultParser" in classes
        assert len(classes) == 1

    def test_extracts_multiple_classes_from_backticks(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should extract multiple class names from backticks."""
        issue_body = """
        ## Interface Contract
        - `AutopilotSession` - session state management
        - `CheckpointStore` - persistence layer
        - `GoalTracker` - tracks daily goals
        """

        classes = coder_agent._extract_potential_classes(issue_body)

        assert "AutopilotSession" in classes
        assert "CheckpointStore" in classes
        assert "GoalTracker" in classes
        assert len(classes) == 3

    def test_extracts_class_from_method_call_pattern(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should extract class name from method call like `ResultParser.parse()`."""
        issue_body = """
        ## Acceptance Criteria
        - `ResultParser.parse()` must return a valid result
        - `ConfigLoader.load_from_file()` handles file paths
        """

        classes = coder_agent._extract_potential_classes(issue_body)

        assert "ResultParser" in classes
        assert "ConfigLoader" in classes

    def test_deduplicates_class_names(self, coder_agent: CoderAgent) -> None:
        """Should not return duplicate class names."""
        issue_body = """
        ## Interface Contract
        - `AutopilotSession` handles state
        - `AutopilotSession.start()` begins execution
        - Create `AutopilotSession` with proper initialization
        """

        classes = coder_agent._extract_potential_classes(issue_body)

        assert classes.count("AutopilotSession") == 1

    def test_ignores_lowercase_identifiers(self, coder_agent: CoderAgent) -> None:
        """Should only extract identifiers that look like class names (start with uppercase)."""
        issue_body = """
        ## Technical Notes
        - Use `config` module for settings
        - The `logger` instance handles logging
        - `MyClass` is the main entry point
        """

        classes = coder_agent._extract_potential_classes(issue_body)

        assert "MyClass" in classes
        assert "config" not in classes
        assert "logger" not in classes

    def test_handles_empty_issue_body(self, coder_agent: CoderAgent) -> None:
        """Should return empty list for empty issue body."""
        classes = coder_agent._extract_potential_classes("")

        assert classes == []

    def test_handles_none_issue_body(self, coder_agent: CoderAgent) -> None:
        """Should return empty list for None issue body."""
        classes = coder_agent._extract_potential_classes(None)  # type: ignore

        assert classes == []

    def test_handles_issue_body_without_classes(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should return empty list when no class names found."""
        issue_body = """
        ## Description
        This issue fixes a bug in the parsing logic.
        No specific classes mentioned here.
        """

        classes = coder_agent._extract_potential_classes(issue_body)

        assert classes == []


class TestCoderQueryMemoryForSchemaWarnings:
    """Tests for _get_schema_warnings() method.

    This method queries the memory store for schema drift entries
    related to the extracted class names.
    """

    def test_queries_memory_for_each_class(
        self, coder_agent_with_memory: CoderAgent, mock_memory_store: MagicMock
    ) -> None:
        """Should query memory store for each class name."""
        class_names = ["AutopilotSession", "CheckpointStore"]
        mock_memory_store.query.return_value = []

        coder_agent_with_memory._get_schema_warnings(class_names)

        # Should call query once per class
        assert mock_memory_store.query.call_count == 2

    def test_queries_with_correct_category(
        self, coder_agent_with_memory: CoderAgent, mock_memory_store: MagicMock
    ) -> None:
        """Should query with category='schema_drift'."""
        class_names = ["AutopilotSession"]
        mock_memory_store.query.return_value = []

        coder_agent_with_memory._get_schema_warnings(class_names)

        call_kwargs = mock_memory_store.query.call_args
        assert call_kwargs.kwargs.get("category") == "schema_drift"

    def test_queries_with_class_name_tag(
        self, coder_agent_with_memory: CoderAgent, mock_memory_store: MagicMock
    ) -> None:
        """Should query with the class name as a tag."""
        class_names = ["AutopilotSession"]
        mock_memory_store.query.return_value = []

        coder_agent_with_memory._get_schema_warnings(class_names)

        call_kwargs = mock_memory_store.query.call_args
        assert "AutopilotSession" in call_kwargs.kwargs.get("tags", [])

    def test_returns_warnings_from_memory_entries(
        self, coder_agent_with_memory: CoderAgent, mock_memory_store: MagicMock
    ) -> None:
        """Should return warning dicts from memory entries."""
        # Create a mock memory entry
        mock_entry = MagicMock(spec=MemoryEntry)
        mock_entry.content = {
            "existing_file": "swarm_attack/models/session.py",
            "existing_issue": 3,
        }
        mock_memory_store.query.return_value = [mock_entry]

        warnings = coder_agent_with_memory._get_schema_warnings(["AutopilotSession"])

        assert len(warnings) == 1
        assert warnings[0]["class_name"] == "AutopilotSession"
        assert warnings[0]["existing_file"] == "swarm_attack/models/session.py"
        assert warnings[0]["existing_issue"] == 3

    def test_returns_empty_list_when_no_matches(
        self, coder_agent_with_memory: CoderAgent, mock_memory_store: MagicMock
    ) -> None:
        """Should return empty list when no schema drift entries found."""
        mock_memory_store.query.return_value = []

        warnings = coder_agent_with_memory._get_schema_warnings(["NewClass"])

        assert warnings == []

    def test_aggregates_warnings_from_multiple_classes(
        self, coder_agent_with_memory: CoderAgent, mock_memory_store: MagicMock
    ) -> None:
        """Should aggregate warnings from multiple class queries."""
        # Different entries for different classes
        entry1 = MagicMock(spec=MemoryEntry)
        entry1.content = {"existing_file": "models/a.py", "existing_issue": 1}
        entry2 = MagicMock(spec=MemoryEntry)
        entry2.content = {"existing_file": "models/b.py", "existing_issue": 2}

        mock_memory_store.query.side_effect = [[entry1], [entry2]]

        warnings = coder_agent_with_memory._get_schema_warnings(
            ["ClassA", "ClassB"]
        )

        assert len(warnings) == 2


class TestCoderInjectSchemaWarnings:
    """Tests for _format_schema_warnings() method.

    This method formats the schema drift warnings into markdown
    that will be injected into the coder prompt.
    """

    def test_formats_single_warning(self, coder_agent: CoderAgent) -> None:
        """Should format a single warning with class, file, and issue info."""
        warnings = [
            {
                "class_name": "AutopilotSession",
                "existing_file": "swarm_attack/models/session.py",
                "existing_issue": 3,
            }
        ]

        result = coder_agent._format_schema_warnings(warnings)

        assert "AutopilotSession" in result
        assert "swarm_attack/models/session.py" in result
        assert "#3" in result or "Issue #3" in result or "3" in result

    def test_formats_multiple_warnings(self, coder_agent: CoderAgent) -> None:
        """Should format multiple warnings."""
        warnings = [
            {
                "class_name": "ClassA",
                "existing_file": "models/a.py",
                "existing_issue": 1,
            },
            {
                "class_name": "ClassB",
                "existing_file": "models/b.py",
                "existing_issue": 2,
            },
        ]

        result = coder_agent._format_schema_warnings(warnings)

        assert "ClassA" in result
        assert "ClassB" in result
        assert "models/a.py" in result
        assert "models/b.py" in result

    def test_includes_warning_header(self, coder_agent: CoderAgent) -> None:
        """Should include a warning header about schema drift."""
        warnings = [
            {
                "class_name": "MyClass",
                "existing_file": "models/my.py",
                "existing_issue": 1,
            }
        ]

        result = coder_agent._format_schema_warnings(warnings)

        # Should have some warning indicator
        assert (
            "WARNING" in result.upper() or
            "DRIFT" in result.upper() or
            "EXISTING" in result.upper()
        )

    def test_includes_import_guidance(self, coder_agent: CoderAgent) -> None:
        """Should suggest importing instead of recreating."""
        warnings = [
            {
                "class_name": "AutopilotSession",
                "existing_file": "swarm_attack/models/session.py",
                "existing_issue": 3,
            }
        ]

        result = coder_agent._format_schema_warnings(warnings)

        assert (
            "import" in result.lower() or
            "Import" in result or
            "RECREAT" in result.upper()
        )


class TestCoderHandlesNoWarnings:
    """Tests for graceful handling when no warnings exist."""

    def test_format_returns_empty_string_for_no_warnings(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should return empty string when warnings list is empty."""
        result = coder_agent._format_schema_warnings([])

        assert result == ""

    def test_format_returns_empty_string_for_none_warnings(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should return empty string when warnings is None-like."""
        # Test with empty list (None would be a type error)
        result = coder_agent._format_schema_warnings([])

        assert result == ""


class TestCoderHandlesNoMemoryStore:
    """Tests for graceful handling when memory_store is None."""

    def test_get_warnings_returns_empty_when_no_memory_store(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should return empty list when memory_store is None."""
        # coder_agent fixture has no memory_store (None)
        assert coder_agent._memory is None

        warnings = coder_agent._get_schema_warnings(["SomeClass"])

        assert warnings == []

    def test_no_error_when_memory_store_is_none(
        self, coder_agent: CoderAgent
    ) -> None:
        """Should not raise any errors when memory_store is None."""
        assert coder_agent._memory is None

        # Should not raise
        try:
            warnings = coder_agent._get_schema_warnings(["AnyClass", "OtherClass"])
            assert isinstance(warnings, list)
        except AttributeError:
            pytest.fail(
                "_get_schema_warnings raised AttributeError when memory_store is None"
            )
