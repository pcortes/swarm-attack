"""
Unit tests for error classification routing and import error recovery.

Tests the behavior where coder failures are classified by type and routed
to appropriate recovery handlers instead of immediate failure.
"""

import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.agents.base import AgentResult


class TestClassifyCoderError:
    """Tests for _classify_coder_error method."""

    def test_classifies_timeout_error(self):
        """Verify timeout errors are classified as 'timeout'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "Claude timed out: Claude CLI timed out after 300 seconds"
        assert orchestrator._classify_coder_error(error_msg) == "timeout"

    def test_classifies_undefined_name_as_import_error(self):
        """Verify 'undefined name' errors are classified as 'import_error'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "Incomplete implementation: test file(s) import 2 undefined name(s): foo, bar"
        assert orchestrator._classify_coder_error(error_msg) == "import_error"

    def test_classifies_importerror_as_import_error(self):
        """Verify ImportError is classified as 'import_error'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "ImportError: No module named 'nonexistent'"
        assert orchestrator._classify_coder_error(error_msg) == "import_error"

    def test_classifies_modulenotfounderror_as_import_error(self):
        """Verify ModuleNotFoundError is classified as 'import_error'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "ModuleNotFoundError: No module named 'missing'"
        assert orchestrator._classify_coder_error(error_msg) == "import_error"

    def test_classifies_syntax_error(self):
        """Verify SyntaxError is classified as 'syntax_error'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "SyntaxError: invalid syntax at line 42"
        assert orchestrator._classify_coder_error(error_msg) == "syntax_error"

    def test_classifies_indentation_error(self):
        """Verify IndentationError is classified as 'syntax_error'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "IndentationError: unexpected indent"
        assert orchestrator._classify_coder_error(error_msg) == "syntax_error"

    def test_classifies_type_error(self):
        """Verify TypeError is classified as 'type_error'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "TypeError: unsupported operand type(s)"
        assert orchestrator._classify_coder_error(error_msg) == "type_error"

    def test_classifies_unknown_errors(self):
        """Verify unknown errors are classified as 'unknown'."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "Some random error that doesn't match patterns"
        assert orchestrator._classify_coder_error(error_msg) == "unknown"

    def test_classification_is_case_insensitive(self):
        """Verify classification works regardless of case."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        # Mixed case
        assert orchestrator._classify_coder_error("TIMED OUT after 300s") == "timeout"
        assert orchestrator._classify_coder_error("UNDEFINED NAME: foo") == "import_error"


class TestExtractUndefinedNames:
    """Tests for _extract_undefined_names method."""

    def test_extracts_names_from_standard_format(self):
        """Verify extraction from 'path:name' format."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "undefined name(s): typer/testing.py:CliRunner, swarm_attack/cli.py:chief_of_staff"
        names = orchestrator._extract_undefined_names(error_msg)

        assert names == ["CliRunner", "chief_of_staff"]

    def test_extracts_single_name(self):
        """Verify extraction works for single undefined name."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "undefined name(s): pathlib.py:Path"
        names = orchestrator._extract_undefined_names(error_msg)

        assert names == ["Path"]

    def test_returns_empty_list_for_no_match(self):
        """Verify empty list returned when pattern doesn't match."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "Some error without undefined names"
        names = orchestrator._extract_undefined_names(error_msg)

        assert names == []

    def test_extracts_from_full_error_message(self):
        """Verify extraction from full coder error message."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        error_msg = "Incomplete implementation: test file(s) import 2 undefined name(s): module.py:Foo, other.py:Bar"
        names = orchestrator._extract_undefined_names(error_msg)

        assert names == ["Foo", "Bar"]


class TestKnownExternalImports:
    """Tests for known external library import lookup."""

    def test_known_imports_dict_exists(self):
        """Verify KNOWN_EXTERNAL_IMPORTS constant exists."""
        from swarm_attack.orchestrator import KNOWN_EXTERNAL_IMPORTS

        assert isinstance(KNOWN_EXTERNAL_IMPORTS, dict)
        assert len(KNOWN_EXTERNAL_IMPORTS) > 0

    def test_clirunner_in_known_imports(self):
        """Verify CliRunner is in known imports."""
        from swarm_attack.orchestrator import KNOWN_EXTERNAL_IMPORTS

        assert "CliRunner" in KNOWN_EXTERNAL_IMPORTS
        assert "typer.testing" in KNOWN_EXTERNAL_IMPORTS["CliRunner"]

    def test_common_test_imports_known(self):
        """Verify common test imports are known."""
        from swarm_attack.orchestrator import KNOWN_EXTERNAL_IMPORTS

        # These are commonly needed in tests
        expected = ["Mock", "patch", "MagicMock", "pytest"]
        for name in expected:
            assert name in KNOWN_EXTERNAL_IMPORTS, f"{name} should be in KNOWN_EXTERNAL_IMPORTS"


class TestFindCorrectImportPaths:
    """Tests for _find_correct_import_paths method."""

    def test_finds_known_external_imports(self):
        """Verify known external imports are found."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        paths = orchestrator._find_correct_import_paths(["CliRunner"])

        assert "CliRunner" in paths
        assert "typer.testing" in paths["CliRunner"]

    def test_returns_empty_for_unknown_names(self):
        """Verify empty dict for completely unknown names."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        # Mock _search_codebase_for_definition to return None
        orchestrator._search_codebase_for_definition = MagicMock(return_value=None)
        orchestrator._search_for_module = MagicMock(return_value=None)

        paths = orchestrator._find_correct_import_paths(["CompletelyUnknownThing"])

        assert paths == {} or "CompletelyUnknownThing" not in paths


class TestBuildImportRecoveryHint:
    """Tests for _build_import_recovery_hint method."""

    def test_builds_hint_with_suggestions(self):
        """Verify recovery hint includes suggested imports."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        undefined = ["CliRunner", "Path"]
        suggestions = {
            "CliRunner": "from typer.testing import CliRunner",
            "Path": "from pathlib import Path",
        }

        hint = orchestrator._build_import_recovery_hint(undefined, suggestions)

        assert "CliRunner" in hint
        assert "from typer.testing import CliRunner" in hint
        assert "Path" in hint
        assert "from pathlib import Path" in hint

    def test_builds_hint_for_missing_suggestions(self):
        """Verify recovery hint handles names without suggestions."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        undefined = ["CliRunner", "UnknownThing"]
        suggestions = {
            "CliRunner": "from typer.testing import CliRunner",
        }

        hint = orchestrator._build_import_recovery_hint(undefined, suggestions)

        assert "CliRunner" in hint
        assert "UnknownThing" in hint
        # Should indicate no suggestion found
        assert "could not find" in hint.lower() or "unknown" in hint.lower()


class TestHandleImportErrorRecovery:
    """Tests for _handle_import_error_recovery method."""

    def test_returns_none_to_signal_retry(self):
        """Verify None is returned when retry should happen."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_fix_import_errors = True
        orchestrator = Orchestrator(mock_config)

        # Mock session
        mock_session = MagicMock()
        mock_session.recovery_context = None

        error_msg = "undefined name(s): typer/testing.py:CliRunner"
        result = orchestrator._handle_import_error_recovery(
            error_msg=error_msg,
            issue=MagicMock(issue_number=1),
            attempt=1,
            max_retries=3,
            session=mock_session,
        )

        # None means "retry with recovery context"
        assert result is None
        # Session should have recovery context set
        assert mock_session.recovery_context is not None
        assert mock_session.recovery_context["error_type"] == "import_error"

    def test_returns_blocked_after_max_retries(self):
        """Verify blocked status returned after max retries."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_fix_import_errors = True
        orchestrator = Orchestrator(mock_config)

        mock_session = MagicMock()

        error_msg = "undefined name(s): typer/testing.py:CliRunner"
        result = orchestrator._handle_import_error_recovery(
            error_msg=error_msg,
            issue=MagicMock(issue_number=1),
            attempt=3,  # At max
            max_retries=3,
            session=mock_session,
        )

        assert result is not None
        assert result.status == "blocked"
        assert "CliRunner" in result.error

    def test_sets_recovery_context_with_suggestions(self):
        """Verify recovery context includes correct import suggestions."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_fix_import_errors = True
        orchestrator = Orchestrator(mock_config)

        mock_session = MagicMock()
        mock_session.recovery_context = None

        error_msg = "undefined name(s): typer/testing.py:CliRunner"
        orchestrator._handle_import_error_recovery(
            error_msg=error_msg,
            issue=MagicMock(issue_number=1),
            attempt=1,
            max_retries=3,
            session=mock_session,
        )

        ctx = mock_session.recovery_context
        assert "suggested_imports" in ctx
        assert "CliRunner" in ctx["suggested_imports"]


class TestAttemptRecoveryWithAgent:
    """Tests for _attempt_recovery_with_agent method using RecoveryAgent."""

    def test_method_exists(self):
        """Verify _attempt_recovery_with_agent method exists."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        orchestrator = Orchestrator(mock_config)

        assert hasattr(orchestrator, "_attempt_recovery_with_agent")

    def test_invokes_recovery_agent(self):
        """Verify RecoveryAgent is invoked with correct context."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.retry = MagicMock()
        mock_config.retry.max_retries = 3
        orchestrator = Orchestrator(mock_config)

        # Mock the recovery agent
        mock_recovery_agent = MagicMock()
        mock_recovery_agent.run.return_value = AgentResult.success_result({
            "recoverable": True,
            "recovery_plan": "Fix the imports",
            "root_cause": "Missing import",
        }, cost_usd=0.5)
        orchestrator._recovery_agent = mock_recovery_agent

        result = orchestrator._attempt_recovery_with_agent(
            feature_id="test-feature",
            issue_number=1,
            error_msg="undefined name(s): foo",
            attempt=1,
        )

        # Verify RecoveryAgent was called
        mock_recovery_agent.run.assert_called_once()
        call_context = mock_recovery_agent.run.call_args[0][0]
        assert call_context["feature_id"] == "test-feature"
        assert call_context["issue_number"] == 1
        assert call_context["failure_type"] == "coder_error"
        assert "undefined name(s): foo" in call_context["error_output"]

    def test_returns_recovery_plan_when_recoverable(self):
        """Verify recovery plan is returned when agent says recoverable."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.retry = MagicMock()
        mock_config.retry.max_retries = 3
        orchestrator = Orchestrator(mock_config)

        mock_recovery_agent = MagicMock()
        mock_recovery_agent.run.return_value = AgentResult.success_result({
            "recoverable": True,
            "recovery_plan": "Add 'from typer.testing import CliRunner'",
            "root_cause": "Missing import for CliRunner",
        }, cost_usd=0.3)
        orchestrator._recovery_agent = mock_recovery_agent

        result = orchestrator._attempt_recovery_with_agent(
            feature_id="test",
            issue_number=1,
            error_msg="undefined name: CliRunner",
            attempt=1,
        )

        assert result["recoverable"] is True
        assert "CliRunner" in result["recovery_plan"]
        assert result["cost_usd"] == 0.3

    def test_returns_not_recoverable_when_agent_says_no(self):
        """Verify not recoverable when agent determines failure is permanent."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.retry = MagicMock()
        mock_config.retry.max_retries = 3
        orchestrator = Orchestrator(mock_config)

        mock_recovery_agent = MagicMock()
        mock_recovery_agent.run.return_value = AgentResult.success_result({
            "recoverable": False,
            "recovery_plan": None,
            "root_cause": "Fundamental architecture mismatch",
            "human_instructions": "Requires manual refactoring",
        }, cost_usd=0.4)
        orchestrator._recovery_agent = mock_recovery_agent

        result = orchestrator._attempt_recovery_with_agent(
            feature_id="test",
            issue_number=1,
            error_msg="Complex error",
            attempt=1,
        )

        assert result["recoverable"] is False
        assert result["human_instructions"] == "Requires manual refactoring"

    def test_handles_agent_failure_gracefully(self):
        """Verify graceful handling when RecoveryAgent itself fails."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.retry = MagicMock()
        mock_config.retry.max_retries = 3
        orchestrator = Orchestrator(mock_config)

        mock_recovery_agent = MagicMock()
        mock_recovery_agent.run.return_value = AgentResult.failure_result(
            "LLM call failed"
        )
        orchestrator._recovery_agent = mock_recovery_agent

        result = orchestrator._attempt_recovery_with_agent(
            feature_id="test",
            issue_number=1,
            error_msg="Some error",
            attempt=1,
        )

        # Should return None or not recoverable when agent fails
        assert result is None or result.get("recoverable") is False


class TestErrorRoutingIntegration:
    """Integration tests for error classification routing in run_issue_session."""

    def test_timeout_still_triggers_auto_split(self):
        """Verify timeout errors still trigger auto-split (unchanged behavior)."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = True
        orchestrator = Orchestrator(mock_config)

        # Timeout should trigger auto-split, not recovery agent
        result = AgentResult.failure_result(
            "Claude timed out: Claude CLI timed out after 300 seconds"
        )

        assert orchestrator._should_auto_split_on_timeout(result) is True
        assert orchestrator._classify_coder_error(result.error) == "timeout"

    def test_recovery_agent_used_for_non_timeout_errors(self):
        """Verify RecoveryAgent is used for non-timeout coder failures."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = True
        orchestrator = Orchestrator(mock_config)

        # Verify method exists for recovery
        assert hasattr(orchestrator, "_attempt_recovery_with_agent")


class TestConfigOption:
    """Tests for auto_fix_import_errors config option."""

    def test_config_has_auto_fix_import_errors_default_true(self):
        """Verify config defaults to auto_fix_import_errors=True."""
        from swarm_attack.config import SwarmConfig

        config = SwarmConfig(repo_root="/tmp/test")
        assert hasattr(config, "auto_fix_import_errors")
        assert config.auto_fix_import_errors is True

    def test_config_can_disable_auto_fix_import_errors(self):
        """Verify auto_fix_import_errors can be set to False."""
        from swarm_attack.config import SwarmConfig

        config = SwarmConfig(repo_root="/tmp/test", auto_fix_import_errors=False)
        assert config.auto_fix_import_errors is False
