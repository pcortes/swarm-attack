"""Parallel agent dispatch for commit review."""

import asyncio
import logging
from typing import Optional

from swarm_attack.commit_review.models import (
    CommitInfo,
    CommitCategory,
    Finding,
    Severity,
)
from swarm_attack.commit_review.prompts import get_prompt_for_category

logger = logging.getLogger(__name__)


class AgentDispatcher:
    """Dispatches review agents in parallel for commits."""

    def __init__(self, max_concurrent: int = 5):
        """Initialize the dispatcher.

        Args:
            max_concurrent: Maximum number of concurrent agent calls
        """
        self.max_concurrent = max_concurrent
        self._semaphore: Optional[asyncio.Semaphore] = None

    async def dispatch(
        self,
        commits: list[CommitInfo],
        categories: list[CommitCategory],
    ) -> list[Finding]:
        """Dispatch review agents for all commits in parallel.

        Args:
            commits: List of commits to review
            categories: Corresponding categories for each commit

        Returns:
            Combined list of findings from all agents
        """
        if not commits:
            return []

        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        tasks = []
        for commit, category in zip(commits, categories):
            prompt = get_prompt_for_category(
                category,
                {
                    "sha": commit.sha,
                    "author": commit.author,
                    "message": commit.message,
                    "files_changed": commit.files_changed,
                    "insertions": commit.insertions,
                    "deletions": commit.deletions,
                    "changed_files": commit.changed_files,
                    "diff": "",  # Diff would be fetched separately
                },
            )
            tasks.append(self._dispatch_with_semaphore(commit, category, prompt))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect findings, handling failures gracefully
        all_findings = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Agent failed: {result}")
                continue
            if result:
                all_findings.extend(result)

        return all_findings

    async def _dispatch_with_semaphore(
        self,
        commit: CommitInfo,
        category: CommitCategory,
        prompt: str,
    ) -> list[Finding]:
        """Dispatch with semaphore for concurrency control."""
        async with self._semaphore:
            return await self._run_agent(commit, category, prompt)

    async def _run_agent(
        self,
        commit: CommitInfo,
        category: CommitCategory,
        prompt: str,
    ) -> list[Finding]:
        """Run a single review agent.

        This is the method that should be mocked in tests.
        In production, this would call the Claude API.

        Args:
            commit: The commit to review
            category: The commit category
            prompt: The formatted review prompt

        Returns:
            List of findings from this agent
        """
        # In production, this would:
        # 1. Call Claude API with the prompt
        # 2. Parse the response into Finding objects
        # 3. Return the findings

        # For now, return empty list - will be mocked in tests
        # and implemented with Claude API in production
        logger.debug(f"Running agent for {commit.sha} ({category.value})")

        # Placeholder - would be replaced with actual Claude call
        return []


async def run_parallel_review(
    commits: list[CommitInfo],
    categories: list[CommitCategory],
    max_concurrent: int = 5,
) -> list[Finding]:
    """Convenience function to run parallel review.

    Args:
        commits: Commits to review
        categories: Categories for each commit
        max_concurrent: Maximum concurrent agents

    Returns:
        Combined findings from all agents
    """
    dispatcher = AgentDispatcher(max_concurrent=max_concurrent)
    return await dispatcher.dispatch(commits, categories)
