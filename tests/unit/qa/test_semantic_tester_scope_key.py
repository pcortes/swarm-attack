"""Unit tests for SemanticTesterAgent scope key compatibility (BUG-AGENT-001).

This test file verifies that the SemanticTesterAgent accepts BOTH 'scope' AND
'test_scope' keys in the context dictionary. This is necessary because:
- Test scenarios use 'scope' key
- SemanticTesterAgent expects 'test_scope' key

The fix should allow both keys to work, with 'scope' taking precedence if both
are provided.
"""
import pytest
from unittest.mock import Mock, patch

from swarm_attack.qa.agents.semantic_tester import (
    SemanticTesterAgent,
    SemanticScope,
)


class TestScopeKeyCompatibility:
    """Test that both 'scope' and 'test_scope' keys are accepted."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create a SemanticTesterAgent with mock config."""
        config = Mock()
        config.repo_root = str(tmp_path)
        return SemanticTesterAgent(config)

    def test_accepts_scope_key(self, agent):
        """Test that 'scope' key is accepted in context."""
        context = {
            "changes": "def foo(): pass",
            "scope": SemanticScope.AFFECTED,  # Using 'scope' key, not 'test_scope'
        }
        prompt = agent._build_test_prompt(context)
        assert "affected" in prompt

    def test_accepts_test_scope_key(self, agent):
        """Test that 'test_scope' key is still accepted in context."""
        context = {
            "changes": "def bar(): pass",
            "test_scope": SemanticScope.FULL_SYSTEM,  # Using 'test_scope' key
        }
        prompt = agent._build_test_prompt(context)
        assert "full_system" in prompt

    def test_scope_takes_precedence_over_test_scope(self, agent):
        """Test that 'scope' key takes precedence when both are provided."""
        context = {
            "changes": "def baz(): pass",
            "scope": SemanticScope.AFFECTED,
            "test_scope": SemanticScope.FULL_SYSTEM,
        }
        prompt = agent._build_test_prompt(context)
        # 'scope' (AFFECTED) should take precedence over 'test_scope' (FULL_SYSTEM)
        assert "affected" in prompt
        assert "full_system" not in prompt

    def test_defaults_to_changes_only_when_neither_provided(self, agent):
        """Test that default scope is CHANGES_ONLY when neither key is provided."""
        context = {
            "changes": "def qux(): pass",
        }
        prompt = agent._build_test_prompt(context)
        assert "changes_only" in prompt

    def test_scope_string_value_accepted(self, agent):
        """Test that string scope values work with 'scope' key."""
        context = {
            "changes": "def quux(): pass",
            "scope": "affected",  # String value instead of enum
        }
        prompt = agent._build_test_prompt(context)
        assert "affected" in prompt

    @patch("subprocess.run")
    def test_run_method_accepts_scope_key(self, mock_run, agent):
        """Test that run() method works with 'scope' key in context."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []}',
            stderr="",
        )

        context = {
            "changes": "def test_func(): pass",
            "scope": SemanticScope.AFFECTED,  # Using 'scope' key
        }

        result = agent.run(context)
        assert result.success is True

    @patch("subprocess.run")
    def test_logging_uses_scope_key(self, mock_run, agent):
        """Test that logging correctly uses 'scope' key value."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout='{"verdict": "PASS", "evidence": [], "issues": [], "recommendations": []}',
            stderr="",
        )

        # Track what gets logged
        logged_data = {}
        def capture_log(event, data, level="info"):
            logged_data[event] = data
        agent._log = capture_log

        context = {
            "changes": "def test_func(): pass",
            "scope": SemanticScope.AFFECTED,
        }

        agent.run(context)

        # Verify logging captured the correct scope
        assert logged_data.get("semantic_test_start", {}).get("scope") == "affected"
