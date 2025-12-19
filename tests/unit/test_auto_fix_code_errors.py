"""
Unit tests for auto-fix code errors functionality.

Tests the automatic recovery from common coder errors like import errors.
"""

import pytest
from unittest.mock import MagicMock

from swarm_attack.agents.base import AgentResult


class TestErrorClassification:
    """Tests for _classify_coder_error method."""

    def test_classifies_timeout_error(self):
        """Verify timeout errors are classified correctly."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "Claude timed out: Claude CLI timed out after 300 seconds"
        assert orchestrator._classify_coder_error(error) == "timeout"

    def test_classifies_import_error(self):
        """Verify import errors are classified correctly."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "Incomplete implementation: test file(s) import 4 undefined name(s)"
        assert orchestrator._classify_coder_error(error) == "import_error"

    def test_classifies_module_not_found(self):
        """Verify ModuleNotFoundError is classified as import error."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "ModuleNotFoundError: No module named 'foo'"
        assert orchestrator._classify_coder_error(error) == "import_error"

    def test_classifies_syntax_error(self):
        """Verify syntax errors are classified correctly."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "SyntaxError: invalid syntax"
        assert orchestrator._classify_coder_error(error) == "syntax_error"

    def test_classifies_unknown_error(self):
        """Verify unknown errors return 'unknown'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "Some other random error"
        assert orchestrator._classify_coder_error(error) == "unknown"


class TestExtractUndefinedNames:
    """Tests for extracting undefined names from import errors."""

    def test_extracts_undefined_names_from_error(self):
        """Verify undefined names are extracted from error message."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "undefined name(s): __future__.py:annotations, typer/testing.py:CliRunner"
        names = orchestrator._extract_undefined_names(error)
        assert "annotations" in names
        assert "CliRunner" in names

    def test_handles_single_undefined_name(self):
        """Verify single undefined name is extracted."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "undefined name(s): foo.py:bar"
        names = orchestrator._extract_undefined_names(error)
        assert "bar" in names

    def test_handles_no_undefined_names(self):
        """Verify empty list for no undefined names."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error = "Some other error without undefined names"
        names = orchestrator._extract_undefined_names(error)
        assert names == []
