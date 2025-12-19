"""
Unit tests for timeout-triggered auto-split functionality.

Tests the behavior where a timed-out issue is automatically split
into smaller sub-issues instead of being blocked.
"""

import pytest
from unittest.mock import MagicMock, patch

from swarm_attack.agents.base import AgentResult
from swarm_attack.agents.complexity_gate import ComplexityEstimate


class TestTimeoutDetection:
    """Tests for detecting timeout errors in coder failures."""

    def test_detects_claude_timeout_in_error_message(self):
        """Verify timeout detection works for Claude timeout errors."""
        error_msg = "Claude timed out: Claude CLI timed out after 300 seconds"
        assert "timed out" in error_msg.lower()

    def test_detects_timeout_in_coder_failure_result(self):
        """Verify we can detect timeout from AgentResult."""
        result = AgentResult.failure_result(
            "Claude timed out: Claude CLI timed out after 300 seconds"
        )
        assert result.error is not None
        assert "timed out" in result.error.lower()

    def test_non_timeout_errors_not_detected_as_timeout(self):
        """Verify other errors don't trigger timeout handling."""
        result = AgentResult.failure_result("Test failures: 3 tests failed")
        assert "timed out" not in result.error.lower()


class TestTimeoutAutoSplit:
    """Tests for automatic issue splitting on timeout."""

    def test_should_auto_split_on_timeout_returns_true_for_timeout(self):
        """Verify should_auto_split_on_timeout returns True for timeout errors."""
        from swarm_attack.orchestrator import Orchestrator

        # Create minimal config
        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.claude.timeout_seconds = 300
        mock_config.auto_split_on_timeout = True

        orchestrator = Orchestrator(mock_config)

        # Test with timeout error
        result = AgentResult.failure_result(
            "Claude timed out: Claude CLI timed out after 300 seconds"
        )
        assert orchestrator._should_auto_split_on_timeout(result) is True

    def test_should_auto_split_on_timeout_returns_false_for_other_errors(self):
        """Verify should_auto_split_on_timeout returns False for non-timeout errors."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = True

        orchestrator = Orchestrator(mock_config)

        result = AgentResult.failure_result("Test failures: 3 tests failed")
        assert orchestrator._should_auto_split_on_timeout(result) is False

    def test_should_auto_split_respects_config_flag(self):
        """Verify auto-split can be disabled via config."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = False  # Disabled

        orchestrator = Orchestrator(mock_config)

        result = AgentResult.failure_result(
            "Claude timed out: Claude CLI timed out after 300 seconds"
        )
        assert orchestrator._should_auto_split_on_timeout(result) is False


class TestHandleTimeoutAutoSplit:
    """Tests for _handle_timeout_auto_split method."""

    def test_creates_complexity_estimate_for_split(self):
        """Verify timeout creates synthetic ComplexityEstimate for splitting."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = True

        orchestrator = Orchestrator(mock_config)

        # Mock _auto_split_issue to capture the estimate
        captured_estimate = None
        original_split = orchestrator._auto_split_issue

        def capture_split(feature_id, issue_number, issue_data, gate_estimate):
            nonlocal captured_estimate
            captured_estimate = gate_estimate
            return AgentResult.success_result({
                "sub_issues": [{"title": "Sub 1", "body": "...", "estimated_size": "small"}],
                "count": 1,
            })

        orchestrator._auto_split_issue = capture_split

        # Call timeout handler
        issue_data = {
            "title": "Test Issue",
            "body": "## Acceptance Criteria\n- [ ] Criterion 1",
        }
        orchestrator._handle_timeout_auto_split(
            feature_id="test-feature",
            issue_number=24,
            issue_data=issue_data,
        )

        # Verify estimate was created with needs_split=True
        assert captured_estimate is not None
        assert captured_estimate.needs_split is True
        assert captured_estimate.estimated_turns >= 25
        assert "timeout" in captured_estimate.reasoning.lower()

    def test_returns_success_with_split_action_on_success(self):
        """Verify successful split returns proper result structure."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = True

        orchestrator = Orchestrator(mock_config)

        # Mock successful split
        orchestrator._auto_split_issue = MagicMock(return_value=AgentResult.success_result({
            "sub_issues": [
                {"title": "Sub 1", "body": "...", "estimated_size": "small"},
                {"title": "Sub 2", "body": "...", "estimated_size": "small"},
            ],
            "count": 2,
        }, cost_usd=0.5))

        issue_data = {"title": "Test", "body": "..."}
        success, commit, result, cost = orchestrator._handle_timeout_auto_split(
            feature_id="test",
            issue_number=1,
            issue_data=issue_data,
        )

        assert success is True
        assert result.output["action"] == "split"
        assert result.output["reason"] == "timeout_auto_split"
        assert result.output["count"] == 2

    def test_returns_failure_when_split_fails(self):
        """Verify failed split returns failure result."""
        from swarm_attack.orchestrator import Orchestrator

        mock_config = MagicMock()
        mock_config.repo_root = "/tmp/test"
        mock_config.auto_split_on_timeout = True

        orchestrator = Orchestrator(mock_config)

        # Mock failed split
        orchestrator._auto_split_issue = MagicMock(
            return_value=AgentResult.failure_result("Split failed")
        )

        issue_data = {"title": "Test", "body": "..."}
        success, commit, result, cost = orchestrator._handle_timeout_auto_split(
            feature_id="test",
            issue_number=1,
            issue_data=issue_data,
        )

        assert success is False
        assert "timed out and auto-split failed" in result.error


class TestConfigOption:
    """Tests for auto_split_on_timeout config option."""

    def test_config_has_auto_split_on_timeout_default_true(self):
        """Verify config defaults to auto_split_on_timeout=True."""
        from swarm_attack.config import SwarmConfig

        config = SwarmConfig(repo_root="/tmp/test")
        assert hasattr(config, "auto_split_on_timeout")
        assert config.auto_split_on_timeout is True

    def test_config_can_disable_auto_split_on_timeout(self):
        """Verify auto_split_on_timeout can be set to False."""
        from swarm_attack.config import SwarmConfig

        config = SwarmConfig(repo_root="/tmp/test", auto_split_on_timeout=False)
        assert config.auto_split_on_timeout is False
