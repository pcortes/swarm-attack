"""Tests for agent skip_auth_classification config passthrough (Bug #2).

Verifies that config.preflight.check_codex_auth flows through to
CodexCliRunner.skip_auth_classification in all agents that use Codex.

The relationship is inverted:
- check_codex_auth=True  -> skip_auth_classification=False (perform check)
- check_codex_auth=False -> skip_auth_classification=True (skip check)
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def make_mock_config(check_codex_auth: bool = True):
    """Create a mock SwarmConfig with preflight settings."""
    from swarm_attack.config import SwarmConfig, PreflightConfig

    config = MagicMock(spec=SwarmConfig)
    config.repo_root = "/tmp/test-repo"
    config.specs_path = Path("/tmp/test-repo/specs")

    # Setup preflight config
    preflight = MagicMock(spec=PreflightConfig)
    preflight.check_codex_auth = check_codex_auth
    config.preflight = preflight

    return config


class TestSpecCriticAuthPassthrough:
    """Tests for SpecCriticAgent auth config passthrough."""

    def test_check_codex_auth_true_means_classification_enabled(self):
        """When check_codex_auth=True, skip_auth_classification should be False."""
        from swarm_attack.agents.spec_critic import SpecCriticAgent

        config = make_mock_config(check_codex_auth=True)
        agent = SpecCriticAgent(config=config)

        # Access the lazy-initialized codex runner
        codex = agent.codex

        # Should NOT skip classification (perform the check)
        assert codex.skip_auth_classification is False

    def test_check_codex_auth_false_means_classification_skipped(self):
        """When check_codex_auth=False, skip_auth_classification should be True."""
        from swarm_attack.agents.spec_critic import SpecCriticAgent

        config = make_mock_config(check_codex_auth=False)
        agent = SpecCriticAgent(config=config)

        codex = agent.codex

        # Should skip classification
        assert codex.skip_auth_classification is True


class TestIssueValidatorAuthPassthrough:
    """Tests for IssueValidatorAgent auth config passthrough."""

    def test_check_codex_auth_true_means_classification_enabled(self):
        """When check_codex_auth=True, skip_auth_classification should be False."""
        from swarm_attack.agents.issue_validator import IssueValidatorAgent

        config = make_mock_config(check_codex_auth=True)
        agent = IssueValidatorAgent(config=config)

        codex = agent.codex
        assert codex.skip_auth_classification is False

    def test_check_codex_auth_false_means_classification_skipped(self):
        """When check_codex_auth=False, skip_auth_classification should be True."""
        from swarm_attack.agents.issue_validator import IssueValidatorAgent

        config = make_mock_config(check_codex_auth=False)
        agent = IssueValidatorAgent(config=config)

        codex = agent.codex
        assert codex.skip_auth_classification is True


class TestBugCriticAuthPassthrough:
    """Tests for BugCriticAgent auth config passthrough."""

    def test_check_codex_auth_true_means_classification_enabled(self):
        """When check_codex_auth=True, skip_auth_classification should be False."""
        from swarm_attack.agents.bug_critic import BugCriticAgent

        config = make_mock_config(check_codex_auth=True)
        agent = BugCriticAgent(config=config)

        codex = agent.codex
        assert codex.skip_auth_classification is False

    def test_check_codex_auth_false_means_classification_skipped(self):
        """When check_codex_auth=False, skip_auth_classification should be True."""
        from swarm_attack.agents.bug_critic import BugCriticAgent

        config = make_mock_config(check_codex_auth=False)
        agent = BugCriticAgent(config=config)

        codex = agent.codex
        assert codex.skip_auth_classification is True


class TestDefaultBehavior:
    """Tests for default config behavior."""

    def test_default_config_enables_auth_classification(self):
        """Default PreflightConfig should have check_codex_auth=True."""
        from swarm_attack.config import PreflightConfig

        preflight = PreflightConfig()
        assert preflight.check_codex_auth is True
