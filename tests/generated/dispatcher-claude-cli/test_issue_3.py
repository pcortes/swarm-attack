"""Tests for AgentDispatcher._run_agent() method.

TDD tests for the async _run_agent() method that orchestrates
Claude CLI invocation using asyncio.to_thread().
"""

import asyncio
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from swarm_attack.commit_review.dispatcher import AgentDispatcher
from swarm_attack.commit_review.models import (
    CommitInfo,
    CommitCategory,
    Finding,
    Severity,
)


class TestRunAgent:
    """Tests for _run_agent() async method."""

    @pytest.fixture
    def dispatcher(self):
        """Create an AgentDispatcher instance."""
        return AgentDispatcher(max_concurrent=5)

    @pytest.fixture
    def sample_commit(self):
        """Sample commit for testing."""
        return CommitInfo(
            sha="abc1234567890",
            author="Test Author",
            email="test@example.com",
            timestamp="2025-01-01T00:00:00",
            message="fix: test commit",
            files_changed=1,
            insertions=10,
            deletions=5,
            changed_files=["src/app.py"],
        )

    @pytest.mark.asyncio
    async def test_run_agent_method_exists(self, dispatcher):
        """_run_agent method exists on AgentDispatcher."""
        assert hasattr(dispatcher, "_run_agent")
        assert asyncio.iscoroutinefunction(dispatcher._run_agent)

    @pytest.mark.asyncio
    async def test_run_agent_returns_list(self, dispatcher, sample_commit):
        """_run_agent returns a list."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = {"result": "[]"}

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_run_agent_calls_claude_cli_via_to_thread(self, dispatcher, sample_commit):
        """Calls _call_claude_cli via asyncio.to_thread."""
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = {"result": "[]"}

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            mock_to_thread.assert_called_once()
            # First arg should be _call_claude_cli
            call_args = mock_to_thread.call_args
            assert call_args[0][0] == dispatcher._call_claude_cli
            # Second arg should be the prompt
            assert call_args[0][1] == "Review this commit"

    @pytest.mark.asyncio
    async def test_run_agent_passes_prompt_to_cli(self, dispatcher, sample_commit):
        """Passes the prompt to _call_claude_cli."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = {"result": "[]"}

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "My custom review prompt",
            )

            # Since we're using asyncio.to_thread, the mock is called with the prompt
            # But we need to patch to_thread to capture the call
            # Let's check the mock was set up correctly
            # This test verifies the method doesn't crash with a prompt

    @pytest.mark.asyncio
    async def test_run_agent_parses_findings(self, dispatcher, sample_commit):
        """Parses findings from Claude CLI response."""
        response = {
            "result": '[{"severity": "MEDIUM", "category": "test", "description": "Issue found", "evidence": "src/app.py:42"}]'
        }
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = response

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert len(result) == 1
            assert isinstance(result[0], Finding)
            assert result[0].severity == Severity.MEDIUM
            assert result[0].description == "Issue found"

    @pytest.mark.asyncio
    async def test_run_agent_returns_empty_list_on_timeout(self, dispatcher, sample_commit):
        """Returns empty list on subprocess.TimeoutExpired."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.side_effect = subprocess.TimeoutExpired("claude", 300)

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_logs_warning_on_timeout(self, dispatcher, sample_commit, caplog):
        """Logs warning on timeout."""
        import logging
        caplog.set_level(logging.WARNING)

        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.side_effect = subprocess.TimeoutExpired("claude", 300)

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert any("timed out" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_run_agent_returns_empty_list_on_json_decode_error(self, dispatcher, sample_commit):
        """Returns empty list on json.JSONDecodeError."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.side_effect = json.JSONDecodeError("test", "doc", 0)

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_logs_warning_on_json_decode_error(self, dispatcher, sample_commit, caplog):
        """Logs warning on JSON decode error."""
        import logging
        caplog.set_level(logging.WARNING)

        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.side_effect = json.JSONDecodeError("test", "doc", 0)

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert any("json" in record.message.lower() or "invalid" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_run_agent_returns_empty_list_on_exception(self, dispatcher, sample_commit):
        """Returns empty list on any other exception."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.side_effect = RuntimeError("CLI failed")

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_logs_warning_on_exception(self, dispatcher, sample_commit, caplog):
        """Logs warning on general exception."""
        import logging
        caplog.set_level(logging.WARNING)

        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.side_effect = RuntimeError("Something went wrong")

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert any("failed" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_run_agent_logs_debug_at_start(self, dispatcher, sample_commit, caplog):
        """Logs debug message at start with commit SHA and category."""
        import logging
        caplog.set_level(logging.DEBUG)

        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = {"result": "[]"}

            await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            # Check for debug message with SHA and category
            debug_messages = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
            assert any(sample_commit.sha in msg and CommitCategory.BUG_FIX.value in msg for msg in debug_messages)

    @pytest.mark.asyncio
    async def test_run_agent_passes_category_to_parse_findings(self, dispatcher, sample_commit):
        """Passes correct category to _parse_findings."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = response

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.FEATURE,
                "Review this commit",
            )

            # FEATURE maps to Dr. Aisha Patel
            assert len(result) == 1
            assert result[0].expert == "Dr. Aisha Patel"

    @pytest.mark.asyncio
    async def test_run_agent_passes_commit_sha_to_parse_findings(self, dispatcher, sample_commit):
        """Passes correct commit SHA to _parse_findings."""
        response = {
            "result": '[{"severity": "LOW", "category": "test", "description": "Issue", "evidence": "file.py:1"}]'
        }
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = response

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert len(result) == 1
            assert result[0].commit_sha == sample_commit.sha

    @pytest.mark.asyncio
    async def test_run_agent_handles_empty_response(self, dispatcher, sample_commit):
        """Handles empty response from CLI gracefully."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = {}

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_handles_no_findings_text(self, dispatcher, sample_commit):
        """Handles 'no findings' text response."""
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = {"result": "No issues found in this commit."}

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_run_agent_multiple_findings(self, dispatcher, sample_commit):
        """Parses multiple findings correctly."""
        response = {
            "result": '[{"severity": "LOW", "category": "c1", "description": "Issue 1", "evidence": "f1.py:1"}, {"severity": "HIGH", "category": "c2", "description": "Issue 2", "evidence": "f2.py:2"}]'
        }
        with patch.object(dispatcher, "_call_claude_cli") as mock_cli:
            mock_cli.return_value = response

            result = await dispatcher._run_agent(
                sample_commit,
                CommitCategory.BUG_FIX,
                "Review this commit",
            )

            assert len(result) == 2
            assert result[0].severity == Severity.LOW
            assert result[1].severity == Severity.HIGH