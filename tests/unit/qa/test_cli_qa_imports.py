# tests/unit/qa/test_cli_qa_imports.py
"""Tests for CLI QA imports - BUG-001.

This test verifies that cli/qa.py correctly imports SemanticScope
from semantic_tester.py (not the non-existent TestScope).
"""

import pytest
import ast


class TestCliQaImports:
    """Tests for CLI QA module imports."""

    def test_semantic_scope_import_available(self):
        """Test that SemanticScope can be imported from semantic_tester."""
        from swarm_attack.qa.agents.semantic_tester import SemanticScope

        # Verify the enum values are correct
        assert SemanticScope.CHANGES_ONLY.value == "changes_only"
        assert SemanticScope.AFFECTED.value == "affected"
        assert SemanticScope.FULL_SYSTEM.value == "full_system"

    def test_testscope_does_not_exist(self):
        """Verify that TestScope does NOT exist in semantic_tester.py."""
        import swarm_attack.qa.agents.semantic_tester as st
        
        # TestScope should NOT exist
        assert not hasattr(st, "TestScope"), "TestScope should not exist - use SemanticScope"
        
        # SemanticScope SHOULD exist
        assert hasattr(st, "SemanticScope"), "SemanticScope should exist"

    def test_cli_qa_imports_semantic_scope_not_testscope(self):
        """Test that cli/qa.py imports SemanticScope, not TestScope.
        
        BUG-001: Line 408 imports TestScope but should import SemanticScope.
        This test parses the actual source code to verify the correct import.
        """
        from pathlib import Path
        
        # Find the cli/qa.py file
        import swarm_attack.cli.qa as qa_module
        qa_file = Path(qa_module.__file__)
        
        # Read and parse the source code
        source_code = qa_file.read_text()
        
        # Check that "TestScope" is NOT imported anywhere in the file
        # The buggy line is: from swarm_attack.qa.agents.semantic_tester import SemanticTesterAgent, TestScope
        assert "import" not in source_code or "TestScope" not in source_code, (
            "BUG-001: cli/qa.py imports TestScope but should import SemanticScope. "
            "TestScope does not exist in semantic_tester.py."
        )
        
        # Verify that SemanticScope IS imported (the correct class)
        assert "SemanticScope" in source_code, (
            "cli/qa.py should import SemanticScope from semantic_tester.py"
        )
