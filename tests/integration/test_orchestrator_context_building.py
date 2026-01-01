"""
Integration tests for Orchestrator context building with UniversalContextBuilder.

These tests validate acceptance criteria 4.3 and 4.4:
- 4.3: Orchestrator builds AgentContext before coder.run()
- 4.4: Orchestrator calls coder.with_context(agent_context)

The Orchestrator should use UniversalContextBuilder to create tailored context
for the CoderAgent, including token-budgeted project instructions, module registry,
and completed summaries.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

from swarm_attack.agents.coder import CoderAgent
from swarm_attack.agents.base import AgentResult
from swarm_attack.config import SwarmConfig, TestRunnerConfig, SessionConfig, RetryConfig
from swarm_attack.models import FeaturePhase, TaskRef, TaskStage, RunState
from swarm_attack.orchestrator import Orchestrator
from swarm_attack.state_store import StateStore
from swarm_attack.universal_context_builder import AgentContext, UniversalContextBuilder


@pytest.fixture
def mock_config(tmp_path: Path) -> SwarmConfig:
    """Create mock SwarmConfig with tmp_path as repo_root."""
    config = MagicMock(spec=SwarmConfig)
    config.repo_root = str(tmp_path)
    config.specs_path = tmp_path / "specs"
    config.state_path = tmp_path / ".swarm" / "state"
    config.sessions_path = tmp_path / ".swarm" / "sessions"
    config.tests = TestRunnerConfig(
        command="pytest",
        args=["-v"],
        timeout_seconds=300,
    )
    config.sessions = SessionConfig(
        stale_timeout_minutes=30,
        max_implementation_retries=3,
    )
    config.retry = RetryConfig(
        max_retries=3,
        base_delay_seconds=1.0,
    )

    # Create necessary directories
    config.specs_path.mkdir(parents=True, exist_ok=True)
    config.state_path.mkdir(parents=True, exist_ok=True)
    config.sessions_path.mkdir(parents=True, exist_ok=True)

    return config


@pytest.fixture
def state_store(mock_config: SwarmConfig) -> StateStore:
    """Create StateStore instance for tests."""
    return StateStore(mock_config)


@pytest.fixture
def setup_feature(tmp_path: Path, mock_config: SwarmConfig, state_store: StateStore) -> dict[str, Any]:
    """Set up a feature with spec and issues for testing."""
    feature_id = "test-feature"

    # Create spec directory and files
    spec_dir = mock_config.specs_path / feature_id
    spec_dir.mkdir(parents=True, exist_ok=True)

    # Create spec-final.md
    spec_content = """# Test Feature

## Overview
Test feature for orchestrator context building tests.

## Implementation
- Create TestClass with process() method
"""
    (spec_dir / "spec-final.md").write_text(spec_content)

    # Create issues.json
    issues_data = {
        "feature_id": feature_id,
        "issues": [
            {
                "order": 1,
                "title": "Implement TestClass",
                "body": "Create TestClass with process() method.",
                "labels": ["implementation"],
                "estimated_size": "small",
            }
        ],
    }
    (spec_dir / "issues.json").write_text(json.dumps(issues_data))

    # Create skill file
    skills_dir = tmp_path / ".claude" / "skills" / "coder"
    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "SKILL.md").write_text("# Coder Skill\nImplement code.")

    # Create CLAUDE.md for project instructions
    (tmp_path / "CLAUDE.md").write_text("# Project Instructions\nUse TDD.")

    # Create initial state
    state = RunState(
        feature_id=feature_id,
        phase=FeaturePhase.IMPLEMENTING,
        tasks=[
            TaskRef(
                issue_number=1,
                title="Implement TestClass",
                stage=TaskStage.READY,
                dependencies=[],
            )
        ],
    )
    state_store.save(state)

    return {
        "feature_id": feature_id,
        "spec_dir": spec_dir,
        "issues_data": issues_data,
        "state": state,
    }


class TestOrchestratorBuildsAgentContext:
    """Tests for Orchestrator building AgentContext before coder.run()."""

    def test_orchestrator_builds_context_before_coder_run(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        state_store: StateStore,
        setup_feature: dict[str, Any],
    ) -> None:
        """AC 4.3: Orchestrator should build AgentContext before calling coder.run().

        The Orchestrator should:
        1. Create UniversalContextBuilder
        2. Call build_context_for_agent("coder", ...)
        3. Get an AgentContext back
        4. Use this context when running the coder
        """
        feature_id = setup_feature["feature_id"]

        # Create test file
        test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_example(): pass")

        # Track if context builder was called
        context_builder_called = False
        built_contexts = []

        original_build = UniversalContextBuilder.build_context_for_agent

        def mock_build_context(self, agent_type, feature_id, issue_number=None):
            nonlocal context_builder_called
            context_builder_called = True
            context = AgentContext(
                agent_type=agent_type,
                built_at=datetime.now(),
                project_instructions="# Test Project",
                token_count=100,
            )
            built_contexts.append(context)
            return context

        # Mock the coder to capture context injection
        mock_coder = MagicMock(spec=CoderAgent)
        mock_coder.run.return_value = AgentResult.success_result(
            output={
                "files_created": ["src/test.py"],
                "files_modified": [],
            }
        )
        mock_coder.reset = MagicMock()
        mock_coder.get_total_cost.return_value = 0.01
        mock_coder.get_checkpoints.return_value = []

        with patch.object(UniversalContextBuilder, 'build_context_for_agent', mock_build_context):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=state_store,
                coder=mock_coder,
            )

            # Run implementation cycle (this is what calls coder)
            # We use the internal method to test context building
            result = orchestrator._run_implementation_cycle(
                feature_id=feature_id,
                issue_number=1,
                session_id="test-session",
                retry_number=0,
            )

        # Verify context was built
        assert context_builder_called, "UniversalContextBuilder should be called"
        assert len(built_contexts) > 0, "At least one context should be built"


class TestOrchestratorInjectsContext:
    """Tests for Orchestrator calling coder.with_context()."""

    def test_orchestrator_calls_with_context(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        state_store: StateStore,
        setup_feature: dict[str, Any],
    ) -> None:
        """AC 4.4: Orchestrator should call coder.with_context(agent_context).

        After building the AgentContext, the Orchestrator should inject it
        into the coder via with_context() before calling run().
        """
        feature_id = setup_feature["feature_id"]

        # Create test file
        test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_example(): pass")

        # Track with_context calls
        with_context_calls = []

        mock_coder = MagicMock(spec=CoderAgent)
        mock_coder.run.return_value = AgentResult.success_result(
            output={
                "files_created": ["src/test.py"],
                "files_modified": [],
            }
        )
        mock_coder.reset = MagicMock()
        mock_coder.get_total_cost.return_value = 0.01
        mock_coder.get_checkpoints.return_value = []

        def mock_with_context(ctx):
            with_context_calls.append(ctx)
            return mock_coder

        mock_coder.with_context = mock_with_context

        # Mock context builder to return valid context
        def mock_build_context(self, agent_type, feature_id, issue_number=None):
            return AgentContext(
                agent_type=agent_type,
                built_at=datetime.now(),
                project_instructions="# Test",
                token_count=100,
            )

        with patch.object(UniversalContextBuilder, 'build_context_for_agent', mock_build_context):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=state_store,
                coder=mock_coder,
            )

            orchestrator._run_implementation_cycle(
                feature_id=feature_id,
                issue_number=1,
                session_id="test-session",
                retry_number=0,
            )

        # Verify with_context was called
        assert len(with_context_calls) > 0, "coder.with_context() should be called"
        assert isinstance(with_context_calls[0], AgentContext)

    def test_context_has_coder_agent_type(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        state_store: StateStore,
        setup_feature: dict[str, Any],
    ) -> None:
        """Context built for coder should have agent_type='coder'."""
        feature_id = setup_feature["feature_id"]

        # Create test file
        test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_example(): pass")

        captured_contexts = []

        mock_coder = MagicMock(spec=CoderAgent)
        mock_coder.run.return_value = AgentResult.success_result(
            output={"files_created": [], "files_modified": []}
        )
        mock_coder.reset = MagicMock()
        mock_coder.get_total_cost.return_value = 0.01
        mock_coder.get_checkpoints.return_value = []

        def mock_with_context(ctx):
            captured_contexts.append(ctx)
            return mock_coder

        mock_coder.with_context = mock_with_context

        def mock_build_context(self, agent_type, feature_id, issue_number=None):
            return AgentContext(
                agent_type=agent_type,
                built_at=datetime.now(),
                token_count=100,
            )

        with patch.object(UniversalContextBuilder, 'build_context_for_agent', mock_build_context):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=state_store,
                coder=mock_coder,
            )

            orchestrator._run_implementation_cycle(
                feature_id=feature_id,
                issue_number=1,
                session_id="test-session",
                retry_number=0,
            )

        assert len(captured_contexts) > 0
        assert captured_contexts[0].agent_type == "coder"


class TestOrchestratorContextWithTokenBudget:
    """Tests for token budget enforcement through orchestrator."""

    def test_context_token_count_is_within_budget(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        state_store: StateStore,
        setup_feature: dict[str, Any],
    ) -> None:
        """AC 4.5: Context should be truncated to token budget (15k for coder).

        The UniversalContextBuilder should ensure the context fits within
        the coder's 15k token budget.
        """
        feature_id = setup_feature["feature_id"]

        # Create test file
        test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_example(): pass")

        captured_contexts = []

        mock_coder = MagicMock(spec=CoderAgent)
        mock_coder.run.return_value = AgentResult.success_result(
            output={"files_created": [], "files_modified": []}
        )
        mock_coder.reset = MagicMock()
        mock_coder.get_total_cost.return_value = 0.01
        mock_coder.get_checkpoints.return_value = []

        def mock_with_context(ctx):
            captured_contexts.append(ctx)
            return mock_coder

        mock_coder.with_context = mock_with_context

        # Use real context builder to test budget enforcement
        orchestrator = Orchestrator(
            config=mock_config,
            state_store=state_store,
            coder=mock_coder,
        )

        # Create context builder and verify budget
        context_builder = UniversalContextBuilder(mock_config, state_store)
        context = context_builder.build_context_for_agent(
            agent_type="coder",
            feature_id=feature_id,
            issue_number=1,
        )

        # Token count should be within budget
        assert context.token_count <= 15000, "Context should be within 15k token budget"


class TestOrchestratorBackwardCompatibility:
    """Tests for backward compatibility when context building fails."""

    def test_orchestrator_works_without_context_builder(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        state_store: StateStore,
        setup_feature: dict[str, Any],
    ) -> None:
        """AC 4.6: Orchestrator should work if context builder returns None.

        If UniversalContextBuilder.build_context_for_agent() returns None
        (e.g., missing files), the orchestrator should continue with
        the coder using default context behavior.
        """
        feature_id = setup_feature["feature_id"]

        # Create test file
        test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_example(): pass")

        mock_coder = MagicMock(spec=CoderAgent)
        mock_coder.run.return_value = AgentResult.success_result(
            output={"files_created": [], "files_modified": []}
        )
        mock_coder.reset = MagicMock()
        mock_coder.get_total_cost.return_value = 0.01
        mock_coder.get_checkpoints.return_value = []
        mock_coder.with_context.return_value = mock_coder

        # Make context builder return None
        def mock_build_context_returns_none(self, agent_type, feature_id, issue_number=None):
            return None

        with patch.object(UniversalContextBuilder, 'build_context_for_agent', mock_build_context_returns_none):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=state_store,
                coder=mock_coder,
            )

            # Should not raise even with None context
            result = orchestrator._run_implementation_cycle(
                feature_id=feature_id,
                issue_number=1,
                session_id="test-session",
                retry_number=0,
            )

        # Coder should still be called
        mock_coder.run.assert_called_once()

    def test_orchestrator_handles_context_builder_exception(
        self,
        tmp_path: Path,
        mock_config: SwarmConfig,
        state_store: StateStore,
        setup_feature: dict[str, Any],
    ) -> None:
        """Orchestrator should handle exceptions from context builder gracefully.

        If the context builder raises an exception, the orchestrator should
        log a warning and continue without context injection.
        """
        feature_id = setup_feature["feature_id"]

        # Create test file
        test_file = tmp_path / "tests" / "generated" / feature_id / "test_issue_1.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test_example(): pass")

        mock_coder = MagicMock(spec=CoderAgent)
        mock_coder.run.return_value = AgentResult.success_result(
            output={"files_created": [], "files_modified": []}
        )
        mock_coder.reset = MagicMock()
        mock_coder.get_total_cost.return_value = 0.01
        mock_coder.get_checkpoints.return_value = []
        mock_coder.with_context.return_value = mock_coder

        def mock_build_context_raises(self, agent_type, feature_id, issue_number=None):
            raise RuntimeError("Context builder failed")

        with patch.object(UniversalContextBuilder, 'build_context_for_agent', mock_build_context_raises):
            orchestrator = Orchestrator(
                config=mock_config,
                state_store=state_store,
                coder=mock_coder,
            )

            # Should not raise - should handle gracefully
            result = orchestrator._run_implementation_cycle(
                feature_id=feature_id,
                issue_number=1,
                session_id="test-session",
                retry_number=0,
            )

        # Coder should still be called
        mock_coder.run.assert_called_once()
