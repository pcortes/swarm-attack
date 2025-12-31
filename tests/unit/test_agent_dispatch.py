"""Tests for agent dispatch functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from swarm_attack.commit_review.dispatcher import AgentDispatcher
from swarm_attack.commit_review.models import (
    CommitInfo,
    CommitCategory,
    Finding,
    Severity,
)


class TestAgentDispatcher:
    """Tests for AgentDispatcher."""

    def _make_commit(
        self,
        sha: str = "abc123",
        category: CommitCategory = CommitCategory.BUG_FIX,
    ) -> CommitInfo:
        """Helper to create a CommitInfo for testing."""
        return CommitInfo(
            sha=sha,
            author="Test User",
            email="test@example.com",
            timestamp="2025-12-31 10:00:00",
            message="fix: some bug",
            files_changed=2,
            insertions=10,
            deletions=5,
            changed_files=["src/main.py", "src/util.py"],
        )

    @pytest.mark.asyncio
    async def test_dispatch_parallel_agents(self):
        """Dispatches multiple agents concurrently for different categories."""
        dispatcher = AgentDispatcher()

        commits = [
            self._make_commit("sha1", CommitCategory.BUG_FIX),
            self._make_commit("sha2", CommitCategory.REFACTOR),
            self._make_commit("sha3", CommitCategory.FEATURE),
        ]
        categories = [CommitCategory.BUG_FIX, CommitCategory.REFACTOR, CommitCategory.FEATURE]

        # Track execution order to verify parallelism
        execution_order = []

        async def mock_agent(commit, category, prompt):
            execution_order.append(f"start_{commit.sha}")
            await asyncio.sleep(0.01)  # Simulate work
            execution_order.append(f"end_{commit.sha}")
            return [Finding(
                commit_sha=commit.sha,
                expert="test",
                severity=Severity.LOW,
                category="test",
                description="Test finding",
                evidence="file.py:10",
            )]

        with patch.object(dispatcher, "_run_agent", side_effect=mock_agent):
            results = await dispatcher.dispatch(commits, categories)

        # All agents should start before any finish (parallel execution)
        # With 3 commits, we should see: start_sha1, start_sha2, start_sha3, then ends
        start_indices = [execution_order.index(f"start_{c.sha}") for c in commits]
        end_indices = [execution_order.index(f"end_{c.sha}") for c in commits]

        # At least 2 starts should happen before the first end
        first_end = min(end_indices)
        starts_before_first_end = sum(1 for s in start_indices if s < first_end)
        assert starts_before_first_end >= 2, "Agents should run in parallel"

    @pytest.mark.asyncio
    async def test_agent_receives_correct_prompt(self):
        """Each agent receives category-specific prompt template."""
        dispatcher = AgentDispatcher()

        commit = self._make_commit()
        category = CommitCategory.BUG_FIX

        captured_prompts = []

        async def mock_agent(commit, cat, prompt):
            captured_prompts.append((cat, prompt))
            return []

        with patch.object(dispatcher, "_run_agent", side_effect=mock_agent):
            await dispatcher.dispatch([commit], [category])

        # Should have received a prompt
        assert len(captured_prompts) == 1
        cat, prompt = captured_prompts[0]

        # Prompt should be category-specific
        assert cat == CommitCategory.BUG_FIX
        assert "bug" in prompt.lower() or "fix" in prompt.lower()

    @pytest.mark.asyncio
    async def test_agent_results_collected(self):
        """All agent results collected before synthesis."""
        dispatcher = AgentDispatcher()

        commits = [
            self._make_commit("sha1"),
            self._make_commit("sha2"),
        ]
        categories = [CommitCategory.BUG_FIX, CommitCategory.BUG_FIX]

        async def mock_agent(commit, cat, prompt):
            return [Finding(
                commit_sha=commit.sha,
                expert="test",
                severity=Severity.MEDIUM,
                category="quality",
                description=f"Finding for {commit.sha}",
                evidence="file.py:10",
            )]

        with patch.object(dispatcher, "_run_agent", side_effect=mock_agent):
            results = await dispatcher.dispatch(commits, categories)

        # Should have findings from both commits
        assert len(results) == 2
        shas = {f.commit_sha for f in results}
        assert shas == {"sha1", "sha2"}

    @pytest.mark.asyncio
    async def test_dispatcher_handles_agent_failure(self):
        """Dispatcher continues if one agent fails."""
        dispatcher = AgentDispatcher()

        commits = [
            self._make_commit("sha1"),
            self._make_commit("sha2"),
        ]
        categories = [CommitCategory.BUG_FIX, CommitCategory.BUG_FIX]

        call_count = 0

        async def mock_agent(commit, cat, prompt):
            nonlocal call_count
            call_count += 1
            if commit.sha == "sha1":
                raise Exception("Agent failed")
            return [Finding(
                commit_sha=commit.sha,
                expert="test",
                severity=Severity.LOW,
                category="test",
                description="Success",
                evidence="file.py:10",
            )]

        with patch.object(dispatcher, "_run_agent", side_effect=mock_agent):
            results = await dispatcher.dispatch(commits, categories)

        # Should still have result from sha2
        assert any(f.commit_sha == "sha2" for f in results)
