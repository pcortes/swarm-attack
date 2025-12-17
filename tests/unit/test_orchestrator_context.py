"""
Tests for orchestrator context handoff - test_path bug fix.

This tests the fix for the test_path context handoff bug:
- The orchestrator was building coder context without test_path
- The coder would compute its own default path
- If paths didn't match, coder couldn't find tests

The fix: Orchestrator now computes test_path and passes it in context.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from swarm_attack.orchestrator import Orchestrator
from swarm_attack.config import SwarmConfig
from swarm_attack.agents import AgentResult


@pytest.fixture
def mock_config(tmp_path: Path) -> SwarmConfig:
    """Create a mock config with all required attributes."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    # Add required nested attributes for VerifierAgent
    config.tests = MagicMock()
    config.tests.timeout_seconds = 300
    return config


@pytest.fixture
def orchestrator_with_mocks(mock_config: SwarmConfig) -> Orchestrator:
    """Create an orchestrator with injected mock agents."""
    # Create mock agents to inject
    mock_coder = MagicMock()
    mock_coder.run = MagicMock(return_value=AgentResult.success_result())
    mock_coder.reset = MagicMock()

    mock_verifier = MagicMock()
    mock_verifier.run = MagicMock(return_value=AgentResult.success_result())
    mock_verifier.reset = MagicMock()

    # Create orchestrator with injected mocks
    orch = Orchestrator(
        config=mock_config,
        coder=mock_coder,
        verifier=mock_verifier,
    )
    return orch


class TestOrchestratorContextHandoff:
    """Tests for orchestrator context building."""

    def test_context_includes_test_path(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Context dict passed to coder must include test_path."""
        # Setup mock coder to capture the context it receives
        captured_context = {}

        def capture_context(ctx):
            captured_context.update(ctx)
            return AgentResult.success_result()

        orchestrator_with_mocks._coder.run = capture_context
        orchestrator_with_mocks._state_store = None

        # Run implementation cycle
        feature_id = "test-feature"
        issue_number = 42
        session_id = "test-session"

        orchestrator_with_mocks._run_implementation_cycle(
            feature_id=feature_id,
            issue_number=issue_number,
            session_id=session_id,
        )

        # Assert test_path is in context
        assert "test_path" in captured_context
        assert captured_context["test_path"] is not None

    def test_test_path_format_is_correct(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """test_path must match expected format: tests/generated/<feature>/test_issue_<N>.py"""
        captured_context = {}

        def capture_context(ctx):
            captured_context.update(ctx)
            return AgentResult.success_result()

        orchestrator_with_mocks._coder.run = capture_context
        orchestrator_with_mocks._state_store = None

        feature_id = "my-feature"
        issue_number = 7

        orchestrator_with_mocks._run_implementation_cycle(
            feature_id=feature_id,
            issue_number=issue_number,
            session_id="test-session",
        )

        test_path = captured_context.get("test_path")

        # Verify the path format
        assert test_path is not None
        assert "tests/generated/my-feature/test_issue_7.py" in test_path
        assert test_path.endswith("test_issue_7.py")

    def test_context_also_includes_required_fields(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Context must include all required fields for coder."""
        captured_context = {}

        def capture_context(ctx):
            captured_context.update(ctx)
            return AgentResult.success_result()

        orchestrator_with_mocks._coder.run = capture_context
        orchestrator_with_mocks._state_store = None

        orchestrator_with_mocks._run_implementation_cycle(
            feature_id="test-feature",
            issue_number=1,
            session_id="test-session",
        )

        # All these fields must be present
        assert "feature_id" in captured_context
        assert "issue_number" in captured_context
        assert "test_path" in captured_context
        assert "regression_test_files" in captured_context
        assert "retry_number" in captured_context
        assert "test_failures" in captured_context
        assert "module_registry" in captured_context


class TestTestFileExistenceGate:
    """Tests for the test file existence gate on retries."""

    def test_first_run_succeeds_without_test_file(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """First run (retry_number=0) should proceed even if test file doesn't exist.

        In TDD mode, coder creates tests on first run.
        """
        # Don't create the test file - it shouldn't exist
        coder_was_called = {"called": False}

        def track_coder_call(ctx):
            coder_was_called["called"] = True
            return AgentResult.success_result()

        orchestrator_with_mocks._coder.run = track_coder_call
        orchestrator_with_mocks._state_store = None

        success, result, cost = orchestrator_with_mocks._run_implementation_cycle(
            feature_id="test-feature",
            issue_number=1,
            session_id="test-session",
            retry_number=0,  # First run
        )

        # Coder should have been called even though test file doesn't exist
        assert coder_was_called["called"], "Coder should be called on first run without test file"

    def test_retry_fails_without_test_file(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Retry (retry_number > 0) should fail if test file doesn't exist.

        If coder didn't create tests on first run, something is wrong.
        """
        # Don't create the test file
        coder_was_called = {"called": False}

        def track_coder_call(ctx):
            coder_was_called["called"] = True
            return AgentResult.success_result()

        orchestrator_with_mocks._coder.run = track_coder_call
        orchestrator_with_mocks._state_store = None

        success, result, cost = orchestrator_with_mocks._run_implementation_cycle(
            feature_id="test-feature",
            issue_number=1,
            session_id="test-session",
            retry_number=1,  # Retry - should fail
        )

        # Should fail without calling coder
        assert not success
        assert not coder_was_called["called"], "Coder should NOT be called when test file missing on retry"
        assert "not found on retry" in result.errors[0]

    def test_retry_succeeds_with_test_file(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Retry should proceed if test file exists."""
        # Create the test file
        test_dir = tmp_path / "tests" / "generated" / "test-feature"
        test_dir.mkdir(parents=True)
        test_file = test_dir / "test_issue_1.py"
        test_file.write_text("def test_example(): pass")

        coder_was_called = {"called": False}

        def track_coder_call(ctx):
            coder_was_called["called"] = True
            return AgentResult.success_result()

        orchestrator_with_mocks._coder.run = track_coder_call
        orchestrator_with_mocks._state_store = None

        success, result, cost = orchestrator_with_mocks._run_implementation_cycle(
            feature_id="test-feature",
            issue_number=1,
            session_id="test-session",
            retry_number=1,  # Retry with test file present
        )

        # Coder should have been called since test file exists
        assert coder_was_called["called"], "Coder should be called on retry when test file exists"

    def test_gate_uses_correct_test_path(
        self, orchestrator_with_mocks: Orchestrator, mock_config: SwarmConfig, tmp_path: Path
    ):
        """Gate should check for test file at the expected path."""
        # Create test file at the WRONG path - gate should fail
        wrong_dir = tmp_path / "tests" / "wrong" / "test-feature"
        wrong_dir.mkdir(parents=True)
        (wrong_dir / "test_issue_1.py").write_text("def test_example(): pass")

        # Don't create at the correct path
        # Correct path is: tmp_path / "tests" / "generated" / "test-feature" / "test_issue_1.py"

        orchestrator_with_mocks._state_store = None

        success, result, cost = orchestrator_with_mocks._run_implementation_cycle(
            feature_id="test-feature",
            issue_number=1,
            session_id="test-session",
            retry_number=1,
        )

        # Should fail because file is not at the expected path
        assert not success
        assert "not found on retry" in result.errors[0]
