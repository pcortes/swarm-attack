"""
Unit tests for auto-split trigger conditions.

Tests that various complexity-related errors trigger auto-split.
"""

import pytest
from unittest.mock import MagicMock
from swarm_attack.agents.base import AgentResult


class TestShouldAutoSplitOnTimeout:
    """Tests for _should_auto_split_on_timeout method."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with mocked dependencies."""
        from swarm_attack.orchestrator import Orchestrator as FeatureImplementationOrchestrator
        config = MagicMock()
        config.auto_split_on_timeout = True
        config.repo_root = "/test"
        logger = MagicMock()
        return FeatureImplementationOrchestrator(config, logger)
    
    def test_timeout_triggers_split(self, orchestrator):
        """Standard timeout should trigger split."""
        result = AgentResult.failure_result("Claude timed out after 120 seconds")
        assert orchestrator._should_auto_split_on_timeout(result) is True
    
    def test_error_max_turns_triggers_split(self, orchestrator):
        """error_max_turns should trigger split."""
        result = AgentResult.failure_result(
            "Claude invocation failed: Claude CLI returned error: error_max_turns"
        )
        assert orchestrator._should_auto_split_on_timeout(result) is True
    
    def test_max_turns_triggers_split(self, orchestrator):
        """Generic max_turns error should trigger split."""
        result = AgentResult.failure_result("Exceeded max_turns limit")
        assert orchestrator._should_auto_split_on_timeout(result) is True
    
    def test_context_exhausted_triggers_split(self, orchestrator):
        """Context exhausted error should trigger split."""
        result = AgentResult.failure_result("Context window exhausted")
        assert orchestrator._should_auto_split_on_timeout(result) is True
    
    def test_import_error_does_not_trigger_split(self, orchestrator):
        """Import errors should NOT trigger split."""
        result = AgentResult.failure_result("ImportError: No module named foo")
        assert orchestrator._should_auto_split_on_timeout(result) is False
    
    def test_syntax_error_does_not_trigger_split(self, orchestrator):
        """Syntax errors should NOT trigger split."""
        result = AgentResult.failure_result("SyntaxError: invalid syntax")
        assert orchestrator._should_auto_split_on_timeout(result) is False
    
    def test_disabled_config_prevents_split(self, orchestrator):
        """When auto_split_on_timeout is disabled, no split should occur."""
        orchestrator.config.auto_split_on_timeout = False
        result = AgentResult.failure_result("Claude timed out after 120 seconds")
        assert orchestrator._should_auto_split_on_timeout(result) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
