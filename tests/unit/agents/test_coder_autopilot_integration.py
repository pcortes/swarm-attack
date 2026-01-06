"""Tests for CoderAgent autopilot integration with self-healing and learning systems.

This test module follows TDD principles - tests are written first to define
the expected behavior of the autopilot integration.

Test Categories:
1. Feature flag tests - verify feature flags control hook activation
2. Self-healing hook tests - verify hooks are called at correct points
3. Learning integration tests - verify episode logging and strategy optimization
4. Backward compatibility tests - verify everything works when disabled
"""

from __future__ import annotations

import json
import pytest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, patch, Mock

# Import the feature config
from swarm_attack.config.autopilot_features import (
    AutopilotFeaturesConfig,
    SelfHealingConfig,
    LearningConfig,
)


# =============================================================================
# Feature Flag Configuration Tests
# =============================================================================


class TestAutopilotFeaturesConfig:
    """Test AutopilotFeaturesConfig behavior."""

    def test_default_config_has_autopilot_disabled(self):
        """Default configuration should have autopilot disabled."""
        config = AutopilotFeaturesConfig()
        assert config.autopilot_enabled is False

    def test_is_enabled_returns_false_when_autopilot_disabled(self):
        """All features should return False when autopilot is disabled."""
        config = AutopilotFeaturesConfig(autopilot_enabled=False)
        # Even with individual features enabled, master switch wins
        config.self_healing = SelfHealingConfig(enabled=True)
        config.learning = LearningConfig(enabled=True)

        assert config.is_enabled("self_healing") is False
        assert config.is_enabled("learning") is False
        assert config.is_enabled("failure_prediction") is False
        assert config.is_enabled("escalation") is False
        assert config.is_enabled("episode_logging") is False

    def test_is_enabled_returns_true_when_all_enabled(self):
        """Features should return True when autopilot and feature enabled."""
        config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True),
            learning=LearningConfig(enabled=True),
        )

        assert config.is_enabled("self_healing") is True
        assert config.is_enabled("learning") is True

    def test_is_enabled_sub_features_require_parent(self):
        """Sub-features require their parent feature to be enabled."""
        config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=False, failure_prediction_enabled=True),
            learning=LearningConfig(enabled=False, episode_logging_enabled=True),
        )

        # Parent disabled, so sub-features should be False
        assert config.is_enabled("failure_prediction") is False
        assert config.is_enabled("episode_logging") is False

    def test_is_enabled_raises_on_unknown_feature(self):
        """is_enabled should raise ValueError for unknown features."""
        config = AutopilotFeaturesConfig()

        with pytest.raises(ValueError, match="Unknown feature"):
            config.is_enabled("unknown_feature")

    def test_get_self_healing_config_returns_none_when_disabled(self):
        """get_self_healing_config returns None when disabled."""
        config = AutopilotFeaturesConfig(autopilot_enabled=False)
        assert config.get_self_healing_config() is None

    def test_get_self_healing_config_returns_config_when_enabled(self):
        """get_self_healing_config returns config when enabled."""
        config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True),
        )
        result = config.get_self_healing_config()
        assert result is not None
        assert result.enabled is True

    def test_get_learning_config_returns_none_when_disabled(self):
        """get_learning_config returns None when disabled."""
        config = AutopilotFeaturesConfig(autopilot_enabled=False)
        assert config.get_learning_config() is None

    def test_from_dict_creates_config(self):
        """from_dict should create config from dictionary."""
        data = {
            "autopilot_enabled": True,
            "self_healing": {
                "enabled": True,
                "token_threshold": 0.9,
            },
            "learning": {
                "enabled": True,
                "min_confidence": 0.8,
            },
        }
        config = AutopilotFeaturesConfig.from_dict(data)

        assert config.autopilot_enabled is True
        assert config.self_healing.enabled is True
        assert config.self_healing.token_threshold == 0.9
        assert config.learning.enabled is True
        assert config.learning.min_confidence == 0.8

    def test_to_dict_round_trips(self):
        """to_dict followed by from_dict should preserve values."""
        original = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True, token_threshold=0.8),
            learning=LearningConfig(enabled=True, min_confidence=0.6),
        )

        data = original.to_dict()
        restored = AutopilotFeaturesConfig.from_dict(data)

        assert restored.autopilot_enabled == original.autopilot_enabled
        assert restored.self_healing.enabled == original.self_healing.enabled
        assert restored.self_healing.token_threshold == original.self_healing.token_threshold
        assert restored.learning.min_confidence == original.learning.min_confidence


class TestSelfHealingConfig:
    """Test SelfHealingConfig validation."""

    def test_token_threshold_must_be_between_0_and_1(self):
        """token_threshold must be in valid range."""
        with pytest.raises(ValueError, match="token_threshold must be between"):
            SelfHealingConfig(token_threshold=1.5)

        with pytest.raises(ValueError, match="token_threshold must be between"):
            SelfHealingConfig(token_threshold=-0.1)

    def test_error_threshold_must_be_non_negative(self):
        """error_threshold must be >= 0."""
        with pytest.raises(ValueError, match="error_threshold must be non-negative"):
            SelfHealingConfig(error_threshold=-1)

    def test_valid_config_creation(self):
        """Valid config should be created without errors."""
        config = SelfHealingConfig(
            enabled=True,
            token_threshold=0.85,
            error_threshold=3,
        )
        assert config.enabled is True
        assert config.token_threshold == 0.85


class TestLearningConfig:
    """Test LearningConfig validation."""

    def test_min_confidence_must_be_between_0_and_1(self):
        """min_confidence must be in valid range."""
        with pytest.raises(ValueError, match="min_confidence must be between"):
            LearningConfig(min_confidence=1.5)

    def test_min_episodes_must_be_at_least_1(self):
        """min_episodes_for_patterns must be >= 1."""
        with pytest.raises(ValueError, match="min_episodes_for_patterns must be at least"):
            LearningConfig(min_episodes_for_patterns=0)


# =============================================================================
# CoderAgent Hook Integration Tests
# =============================================================================


class TestCoderAgentAutopilotHooks:
    """Test that CoderAgent calls autopilot hooks at correct points.

    These tests verify that when autopilot is enabled, the coder agent
    calls the appropriate hooks at each stage of execution.
    """

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig for testing."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.specs_path = tmp_path / "specs"
        config.skills_path = tmp_path / ".claude" / "skills"
        config.project_instructions_path = tmp_path / "CLAUDE.md"

        # Create required directories
        (tmp_path / "specs" / "test-feature").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "coder").mkdir(parents=True)

        return config

    @pytest.fixture
    def mock_llm_runner(self):
        """Create a mock LLM runner."""
        runner = MagicMock()
        result = MagicMock()
        result.text = """# FILE: src/foo.py
class Foo:
    pass
"""
        result.total_cost_usd = 0.05
        runner.run.return_value = result
        return runner

    @pytest.fixture
    def mock_self_healing_integration(self):
        """Create a mock self-healing integration."""
        integration = MagicMock()
        # Mock pre_execution_hook returns execution state
        mock_state = MagicMock()
        mock_state.session_id = "test-session"
        integration.pre_execution_hook.return_value = mock_state

        # Mock post_action_hook returns prediction
        mock_prediction = MagicMock()
        mock_prediction.failure_predicted = False
        integration.post_action_hook.return_value = mock_prediction

        # Mock on_error_hook returns recovery suggestion
        mock_suggestion = MagicMock()
        mock_suggestion.action = "retry"
        integration.on_error_hook.return_value = mock_suggestion

        return integration

    @pytest.fixture
    def mock_learning_integration(self):
        """Create a mock learning integration."""
        integration = MagicMock()
        return integration

    def test_hooks_not_called_when_autopilot_disabled(
        self, mock_config, mock_llm_runner, mock_self_healing_integration, mock_learning_integration, tmp_path
    ):
        """When autopilot is disabled, no hooks should be called."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        # Create agent with autopilot disabled
        autopilot_config = AutopilotFeaturesConfig(autopilot_enabled=False)

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        # Inject the autopilot config (this is what we're testing)
        agent._autopilot_config = autopilot_config
        agent._self_healing = mock_self_healing_integration
        agent._learning = mock_learning_integration

        # Run the agent
        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Hooks should NOT have been called
        mock_self_healing_integration.pre_execution_hook.assert_not_called()
        mock_self_healing_integration.post_action_hook.assert_not_called()
        mock_learning_integration.wrap_coder_run.assert_not_called()

    def test_pre_execution_hook_called_after_context_loading(
        self, mock_config, mock_llm_runner, mock_self_healing_integration, tmp_path
    ):
        """Pre-execution hook should be called after context is loaded."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        # Create agent with autopilot ENABLED
        autopilot_config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True),
        )

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        # Inject the autopilot config
        agent._autopilot_config = autopilot_config
        agent._self_healing = mock_self_healing_integration

        # Run the agent
        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Pre-execution hook should have been called
        mock_self_healing_integration.pre_execution_hook.assert_called_once()

        # Verify context was passed
        call_args = mock_self_healing_integration.pre_execution_hook.call_args
        assert "feature_id" in call_args[0][0]
        assert call_args[0][0]["feature_id"] == "test-feature"

    def test_post_action_hook_called_after_llm_execution(
        self, mock_config, mock_llm_runner, mock_self_healing_integration, tmp_path
    ):
        """Post-action hook should be called after LLM completes."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        # Create agent with autopilot ENABLED
        autopilot_config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True),
        )

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        agent._autopilot_config = autopilot_config
        agent._self_healing = mock_self_healing_integration

        # Run the agent
        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Post-action hook should have been called
        mock_self_healing_integration.post_action_hook.assert_called()

    def test_on_error_hook_called_on_exception(
        self, mock_config, mock_llm_runner, mock_self_healing_integration, tmp_path
    ):
        """On-error hook should be called when an exception occurs."""
        from swarm_attack.agents.coder import CoderAgent
        from swarm_attack.llm_clients import ClaudeInvocationError

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        # Make LLM throw an exception
        mock_llm_runner.run.side_effect = ClaudeInvocationError("Test error")

        autopilot_config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True),
        )

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        agent._autopilot_config = autopilot_config
        agent._self_healing = mock_self_healing_integration

        # Run the agent (should fail)
        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        assert result.success is False

        # On-error hook should have been called
        mock_self_healing_integration.on_error_hook.assert_called()

    def test_post_execution_hook_called_before_return(
        self, mock_config, mock_llm_runner, mock_self_healing_integration, tmp_path
    ):
        """Post-execution hook should be called before returning result."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        autopilot_config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            self_healing=SelfHealingConfig(enabled=True),
        )

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        agent._autopilot_config = autopilot_config
        agent._self_healing = mock_self_healing_integration

        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Post-execution hook should have been called
        mock_self_healing_integration.post_execution_hook.assert_called_once()


# =============================================================================
# Learning Integration Tests
# =============================================================================


class TestCoderAgentLearningIntegration:
    """Test that CoderAgent integrates with learning system correctly."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig for testing."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.specs_path = tmp_path / "specs"
        config.skills_path = tmp_path / ".claude" / "skills"
        config.project_instructions_path = tmp_path / "CLAUDE.md"

        (tmp_path / "specs" / "test-feature").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "coder").mkdir(parents=True)

        return config

    @pytest.fixture
    def mock_llm_runner(self):
        """Create a mock LLM runner."""
        runner = MagicMock()
        result = MagicMock()
        result.text = """# FILE: src/foo.py
class Foo:
    pass
"""
        result.total_cost_usd = 0.05
        runner.run.return_value = result
        return runner

    @pytest.fixture
    def mock_learning_integration(self):
        """Create a mock learning integration."""
        integration = MagicMock()
        # Make wrap_coder_run call the actual function and return result
        def wrap_side_effect(coder_fn, context):
            return coder_fn(context)
        integration.wrap_coder_run.side_effect = wrap_side_effect
        return integration

    def test_learning_wrapper_not_used_when_disabled(
        self, mock_config, mock_llm_runner, mock_learning_integration, tmp_path
    ):
        """Learning wrapper should not be used when learning is disabled."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        autopilot_config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            learning=LearningConfig(enabled=False),
        )

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        agent._autopilot_config = autopilot_config
        agent._learning = mock_learning_integration

        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Learning wrapper should NOT have been used
        mock_learning_integration.wrap_coder_run.assert_not_called()

    def test_learning_wrapper_used_when_enabled(
        self, mock_config, mock_llm_runner, mock_learning_integration, tmp_path
    ):
        """Learning wrapper should wrap execution when used by orchestrator.

        Note: The learning wrapper is designed to be called EXTERNALLY by the
        orchestrator, not internally by CoderAgent. This test verifies the
        intended usage pattern.
        """
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        autopilot_config = AutopilotFeaturesConfig(
            autopilot_enabled=True,
            learning=LearningConfig(enabled=True),
        )

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        agent._autopilot_config = autopilot_config
        agent._learning = mock_learning_integration

        # Simulate orchestrator using the learning wrapper
        context = {
            "feature_id": "test-feature",
            "issue_number": 1,
        }

        # When learning is enabled, orchestrator should use wrap_coder_run
        if agent._is_autopilot_enabled("learning") and agent._learning:
            result = agent._learning.wrap_coder_run(agent.run, context)
        else:
            result = agent.run(context)

        # Learning wrapper should have been called
        mock_learning_integration.wrap_coder_run.assert_called()


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests to ensure everything works identically when autopilot is disabled."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock SwarmConfig for testing."""
        config = MagicMock()
        config.repo_root = str(tmp_path)
        config.specs_path = tmp_path / "specs"
        config.skills_path = tmp_path / ".claude" / "skills"
        config.project_instructions_path = tmp_path / "CLAUDE.md"

        (tmp_path / "specs" / "test-feature").mkdir(parents=True)
        (tmp_path / ".claude" / "skills" / "coder").mkdir(parents=True)

        return config

    @pytest.fixture
    def mock_llm_runner(self):
        """Create a mock LLM runner."""
        runner = MagicMock()
        result = MagicMock()
        result.text = """# FILE: src/foo.py
class Foo:
    pass
"""
        result.total_cost_usd = 0.05
        runner.run.return_value = result
        return runner

    def test_agent_works_without_autopilot_config(
        self, mock_config, mock_llm_runner, tmp_path
    ):
        """Agent should work when no autopilot config is set at all."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        # Create agent WITHOUT setting any autopilot config
        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        # Run should succeed
        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        assert result.success is True

    def test_agent_output_unchanged_with_autopilot_disabled(
        self, mock_config, mock_llm_runner, tmp_path
    ):
        """Output structure should be unchanged when autopilot is disabled."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        autopilot_config = AutopilotFeaturesConfig(autopilot_enabled=False)

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )
        agent._autopilot_config = autopilot_config

        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Standard output fields should be present
        assert result.success is True
        assert "files_created" in result.output or "files_modified" in result.output
        assert "feature_id" in result.output
        assert "issue_number" in result.output

    def test_cost_tracking_unchanged(
        self, mock_config, mock_llm_runner, tmp_path
    ):
        """Cost tracking should work the same with autopilot disabled."""
        from swarm_attack.agents.coder import CoderAgent

        # Create test fixtures
        spec_path = tmp_path / "specs" / "test-feature" / "spec-final.md"
        spec_path.write_text("# Test Spec")

        issues_path = tmp_path / "specs" / "test-feature" / "issues.json"
        issues_path.write_text(json.dumps({
            "issues": [{"order": 1, "title": "Test Issue", "body": "Test body", "labels": []}]
        }))

        skill_path = tmp_path / ".claude" / "skills" / "coder" / "SKILL.md"
        skill_path.write_text("# Coder Skill")

        agent = CoderAgent(
            config=mock_config,
            llm_runner=mock_llm_runner,
        )

        result = agent.run({
            "feature_id": "test-feature",
            "issue_number": 1,
        })

        # Cost should be tracked
        assert result.cost_usd == 0.05


# =============================================================================
# Hook Data Flow Tests
# =============================================================================


class TestHookDataFlow:
    """Test that correct data flows through hooks."""

    def test_pre_execution_hook_receives_full_context(self):
        """Pre-execution hook should receive feature_id, issue_number, etc."""
        from swarm_attack.self_healing.coder_integration import CoderSelfHealingIntegration

        integration = CoderSelfHealingIntegration()

        context = {
            "session_id": "test-session",
            "token_usage": 1000,
            "token_limit": 10000,
            "feature_id": "test-feature",
            "issue_number": 1,
        }

        state = integration.pre_execution_hook(context)

        assert state.session_id == "test-session"
        assert state.token_usage == 1000
        assert state.token_limit == 10000

    def test_post_action_hook_updates_state(self):
        """Post-action hook should update state with action and token delta."""
        from swarm_attack.self_healing.coder_integration import CoderSelfHealingIntegration

        integration = CoderSelfHealingIntegration()

        context = {
            "session_id": "test-session",
            "token_usage": 1000,
            "token_limit": 10000,
        }
        state = integration.pre_execution_hook(context)

        # Record an action
        prediction = integration.post_action_hook(
            state=state,
            action={"type": "llm_call", "prompt_tokens": 500},
            token_delta=500,
        )

        assert state.token_usage == 1500
        assert len(state.actions) == 1
        assert state.actions[0]["type"] == "llm_call"

    def test_on_error_hook_returns_recovery_suggestion(self):
        """On-error hook should return a recovery suggestion."""
        from swarm_attack.self_healing.coder_integration import CoderSelfHealingIntegration

        integration = CoderSelfHealingIntegration()

        context = {
            "session_id": "test-session",
            "token_usage": 1000,
            "token_limit": 10000,
        }
        state = integration.pre_execution_hook(context)

        # Record an error
        suggestion = integration.on_error_hook(
            state=state,
            error={"type": "timeout", "message": "LLM timed out"},
        )

        assert len(state.errors) == 1
        assert suggestion is not None

    def test_post_execution_hook_returns_summary(self):
        """Post-execution hook should return execution summary."""
        from swarm_attack.self_healing.coder_integration import CoderSelfHealingIntegration

        integration = CoderSelfHealingIntegration()

        context = {
            "session_id": "test-session",
            "token_usage": 1000,
            "token_limit": 10000,
        }
        state = integration.pre_execution_hook(context)

        # Simulate some execution
        integration.post_action_hook(state, {"type": "action1"}, token_delta=100)
        integration.post_action_hook(state, {"type": "action2"}, token_delta=200)

        summary = integration.post_execution_hook(state, success=True)

        assert summary["session_id"] == "test-session"
        assert summary["success"] is True
        assert summary["total_actions"] == 2
        assert summary["final_token_usage"] == 1300


# =============================================================================
# Learning Episode Tests
# =============================================================================


class TestLearningEpisodeLogging:
    """Test that learning episodes are logged correctly."""

    def test_episode_created_on_start(self, tmp_path):
        """Episode should be created when coder run starts."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=tmp_path / "episodes")

        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
            task_type="implementation",
        )

        assert episode.feature_id == "test-feature"
        assert episode.issue_number == 1
        assert episode.status == "in_progress"
        assert episode.episode_id.startswith("ep-")

    def test_episode_completed_with_result(self, tmp_path):
        """Episode should be completed with result data."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=tmp_path / "episodes")

        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
        )

        logger.complete_episode(
            episode=episode,
            success=True,
            cost_usd=0.05,
            files_created=["src/foo.py"],
            files_modified=["src/bar.py"],
        )

        assert episode.success is True
        assert episode.status == "completed"
        assert episode.cost_usd == 0.05
        assert "src/foo.py" in episode.files_created

    def test_episode_persisted_to_disk(self, tmp_path):
        """Completed episode should be persisted to disk."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=tmp_path / "episodes")

        episode = logger.start_episode(
            feature_id="test-feature",
            issue_number=1,
        )

        logger.complete_episode(
            episode=episode,
            success=True,
            cost_usd=0.05,
        )

        # Check file was written
        episodes_file = tmp_path / "episodes" / "episodes.jsonl"
        assert episodes_file.exists()

        # Load and verify
        content = episodes_file.read_text()
        assert "test-feature" in content

    def test_episodes_can_be_loaded(self, tmp_path):
        """Persisted episodes should be loadable."""
        from swarm_attack.learning.coder_integration import EpisodeLogger

        logger = EpisodeLogger(base_path=tmp_path / "episodes")

        # Create and complete multiple episodes
        for i in range(3):
            episode = logger.start_episode(
                feature_id=f"feature-{i}",
                issue_number=i,
            )
            logger.complete_episode(episode, success=True)

        # Load recent
        loaded = logger.load_recent(limit=10)

        assert len(loaded) == 3
        # Most recent first
        assert loaded[0].feature_id == "feature-2"
