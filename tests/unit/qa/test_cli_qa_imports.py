# tests/unit/qa/test_cli_qa_imports.py
"""Tests for CLI QA imports - comprehensive import validation.

This test verifies that:
1. cli/qa.py correctly imports SemanticScope from semantic_tester.py
   (not the non-existent TestScope)
2. All CLI QA commands can be imported without errors
3. The qa_app is properly configured and registered
4. All QA-related CLI modules have working imports
"""

import pytest
import ast
from pathlib import Path


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


class TestCliQaAppImports:
    """Tests for CLI QA app and command imports."""

    def test_qa_app_import(self):
        """Test that qa_app can be imported from cli/qa.py."""
        from swarm_attack.cli.qa import qa_app

        assert qa_app is not None
        assert qa_app.info.name == "qa"

    def test_qa_commands_app_import(self):
        """Test that app can be imported from cli/qa_commands.py."""
        from swarm_attack.cli.qa_commands import app

        assert app is not None
        assert app.info.name == "qa"

    def test_cli_app_has_qa_subcommand(self):
        """Test that the main CLI app has the QA subcommand registered."""
        from swarm_attack.cli.app import app

        # Check that 'qa' is in the registered sub-apps
        sub_app_names = [cmd.name for cmd in app.registered_groups]
        assert "qa" in sub_app_names, (
            "QA subcommand not registered in main CLI app"
        )

    def test_semantic_scope_cli_enum(self):
        """Test that SemanticScopeCLI enum is properly defined in cli/qa.py."""
        from swarm_attack.cli.qa import SemanticScopeCLI

        # Verify the CLI enum values match the agent enum
        assert SemanticScopeCLI.CHANGES_ONLY.value == "changes_only"
        assert SemanticScopeCLI.AFFECTED.value == "affected"
        assert SemanticScopeCLI.FULL_SYSTEM.value == "full_system"

    def test_cli_enum_matches_agent_enum(self):
        """Test that CLI SemanticScopeCLI matches agent SemanticScope values."""
        from swarm_attack.cli.qa import SemanticScopeCLI
        from swarm_attack.qa.agents.semantic_tester import SemanticScope

        # Values should be identical
        assert SemanticScopeCLI.CHANGES_ONLY.value == SemanticScope.CHANGES_ONLY.value
        assert SemanticScopeCLI.AFFECTED.value == SemanticScope.AFFECTED.value
        assert SemanticScopeCLI.FULL_SYSTEM.value == SemanticScope.FULL_SYSTEM.value


class TestCliQaCommandRegistration:
    """Tests for CLI QA command registration and availability."""

    def test_qa_probe_command_registered(self):
        """Test that the 'probe' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "probe" in command_names

    def test_qa_report_command_registered(self):
        """Test that the 'report' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "report" in command_names

    def test_qa_bugs_command_registered(self):
        """Test that the 'bugs' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "bugs" in command_names

    def test_qa_semantic_test_command_registered(self):
        """Test that the 'semantic-test' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "semantic-test" in command_names

    def test_qa_regression_status_command_registered(self):
        """Test that the 'regression-status' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "regression-status" in command_names

    def test_qa_regression_command_registered(self):
        """Test that the 'regression' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "regression" in command_names

    def test_qa_metrics_command_registered(self):
        """Test that the 'metrics' command is registered."""
        from swarm_attack.cli.qa import qa_app

        command_names = [cmd.name for cmd in qa_app.registered_commands]
        assert "metrics" in command_names


class TestCliQaLazyImports:
    """Tests for lazy import behavior in CLI QA module."""

    def test_semantic_tester_lazy_import(self):
        """Test that SemanticTesterAgent can be lazy imported when needed.

        The cli/qa.py module uses lazy imports inside functions to avoid
        loading heavy modules at import time.
        """
        # First, import should work at the module level
        from swarm_attack.qa.agents.semantic_tester import (
            SemanticTesterAgent,
            SemanticScope,
        )

        assert SemanticTesterAgent is not None
        assert SemanticScope is not None

    def test_regression_detector_import(self):
        """Test that RegressionDetector can be imported."""
        from swarm_attack.qa.regression_detector import RegressionDetector

        assert RegressionDetector is not None

    def test_session_store_import(self):
        """Test that QASessionStore can be imported."""
        from swarm_attack.qa.session_store import QASessionStore

        assert QASessionStore is not None

    def test_display_format_functions_import(self):
        """Test that display formatting functions can be imported."""
        from swarm_attack.cli.display import (
            format_qa_session_table,
            format_qa_bugs_table,
            get_action_suggestion,
        )

        assert format_qa_session_table is not None
        assert format_qa_bugs_table is not None
        assert get_action_suggestion is not None

    def test_metrics_import(self):
        """Test that SemanticQAMetrics can be imported."""
        from swarm_attack.qa.metrics import SemanticQAMetrics

        assert SemanticQAMetrics is not None


class TestCliQaNoRemainingTestScopeReferences:
    """Tests to ensure no remaining TestScope references exist."""

    def test_no_testscope_in_cli_qa_source(self):
        """Scan cli/qa.py source for any TestScope references."""
        import swarm_attack.cli.qa as qa_module
        qa_file = Path(qa_module.__file__)
        source_code = qa_file.read_text()

        # Use AST to parse and find any Name nodes with 'TestScope'
        tree = ast.parse(source_code)

        testscope_refs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "TestScope":
                testscope_refs.append(node.lineno)
            elif isinstance(node, ast.alias) and node.name == "TestScope":
                testscope_refs.append(node.lineno if hasattr(node, 'lineno') else 0)

        assert len(testscope_refs) == 0, (
            f"Found TestScope references at lines: {testscope_refs}. "
            "These should be changed to SemanticScope."
        )

    def test_no_testscope_in_qa_agents_init(self):
        """Ensure qa/agents/__init__.py exports SemanticScope, not TestScope."""
        from swarm_attack.qa.agents import SemanticScope

        import swarm_attack.qa.agents as agents_module

        # SemanticScope should be exported
        assert hasattr(agents_module, "SemanticScope")

        # TestScope should NOT be exported
        assert not hasattr(agents_module, "TestScope"), (
            "qa/agents/__init__.py should not export TestScope"
        )

    def test_no_testscope_in_semantic_tester_exports(self):
        """Ensure semantic_tester.py does not export TestScope."""
        import swarm_attack.qa.agents.semantic_tester as st_module

        # Get all public exports
        public_exports = [name for name in dir(st_module) if not name.startswith('_')]

        assert "TestScope" not in public_exports, (
            "semantic_tester.py should not have TestScope in exports"
        )
        assert "SemanticScope" in public_exports, (
            "semantic_tester.py should export SemanticScope"
        )
