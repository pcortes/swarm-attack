"""Parallel agent dispatch for commit review."""

import asyncio
import json
import logging
import subprocess
from typing import Optional

from swarm_attack.commit_review.models import (
    CommitInfo,
    CommitCategory,
    Finding,
    Severity,
)
from swarm_attack.commit_review.prompts import get_prompt_for_category, EXPERTS

logger = logging.getLogger(__name__)


# Mapping from CommitCategory to expert key in EXPERTS dict
CATEGORY_TO_EXPERT_KEY = {
    CommitCategory.BUG_FIX: "production_reliability",
    CommitCategory.FEATURE: "code_quality",
    CommitCategory.REFACTOR: "architecture",
    CommitCategory.TEST_CHANGE: "test_coverage",
    CommitCategory.DOCUMENTATION: "documentation",
    CommitCategory.CHORE: None,  # General reviewer
    CommitCategory.OTHER: None,  # General reviewer
}


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
        In production, this calls Claude CLI (not the API directly).

        Args:
            commit: The commit to review
            category: The commit category
            prompt: The formatted review prompt

        Returns:
            List of findings from this agent
        """
        logger.debug(f"Running agent for {commit.sha} ({category.value})")

        try:
            # Call Claude CLI in a thread to avoid blocking async loop
            response = await asyncio.to_thread(self._call_claude_cli, prompt)
            return self._parse_findings(response, commit.sha, category)
        except Exception as e:
            logger.warning(f"Agent failed for {commit.sha}: {e}")
            return []

    def _call_claude_cli(self, prompt: str) -> dict:
        """Call Claude CLI synchronously.

        This method invokes the Claude CLI via subprocess and returns
        the parsed JSON response. It should be called from a thread
        (via asyncio.to_thread) to avoid blocking the async event loop.

        Args:
            prompt: The review prompt to send to Claude

        Returns:
            Parsed JSON response dict from Claude CLI

        Raises:
            RuntimeError: On non-zero exit code with stderr message
            subprocess.TimeoutExpired: If CLI times out (propagated to caller)
            json.JSONDecodeError: If stdout is not valid JSON (propagated to caller)
        """
        result = subprocess.run(
            ["claude", "--print", "--output-format", "json", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude CLI failed: {result.stderr}")

        return json.loads(result.stdout)

    def _get_expert_for_category(self, category: CommitCategory) -> str:
        """Get the expert name for a commit category.

        Args:
            category: The commit category

        Returns:
            Expert name string
        """
        expert_key = CATEGORY_TO_EXPERT_KEY.get(category)
        if expert_key is None:
            return "General Reviewer"
        expert = EXPERTS.get(expert_key, {})
        return expert.get("name", "General Reviewer")

    def _parse_findings(
        self,
        response: dict,
        commit_sha: str,
        category: CommitCategory,
    ) -> list[Finding]:
        """Parse Claude response into Finding objects.

        Args:
            response: Parsed JSON from Claude CLI
            commit_sha: SHA of the commit being reviewed
            category: Category for expert assignment

        Returns:
            List of Finding objects, empty on parse errors
        """
        findings = []

        # Get result field from response
        result_text = response.get("result", "")
        if not result_text:
            return []

        # Get expert name for this category
        expert = self._get_expert_for_category(category)

        # Try to parse findings from the result
        try:
            findings_data = self._extract_findings_from_result(result_text)
            for finding_dict in findings_data:
                finding = self._create_finding(
                    finding_dict, commit_sha, expert
                )
                if finding is not None:
                    findings.append(finding)
        except Exception as e:
            logger.warning(f"Failed to parse findings for {commit_sha}: {e}")
            return []

        return findings

    def _extract_findings_from_result(self, result_text: str) -> list[dict]:
        """Extract findings data from result text.

        Handles both JSON array and nested dict with 'findings' key.

        Args:
            result_text: The result field text from Claude response

        Returns:
            List of finding dictionaries
        """
        try:
            parsed = json.loads(result_text)
        except json.JSONDecodeError:
            # Not valid JSON, return empty list
            return []

        # If parsed is a list, assume it's the findings array
        if isinstance(parsed, list):
            return parsed

        # If parsed is a dict, look for 'findings' key
        if isinstance(parsed, dict):
            findings = parsed.get("findings", [])
            if isinstance(findings, list):
                return findings

        return []

    def _create_finding(
        self,
        finding_dict: dict,
        commit_sha: str,
        expert: str,
    ) -> Optional[Finding]:
        """Create a Finding object from a dictionary.

        Args:
            finding_dict: Dictionary with finding data
            commit_sha: SHA of the commit
            expert: Expert name to assign

        Returns:
            Finding object or None if creation fails
        """
        try:
            # Get required fields
            severity_str = finding_dict.get("severity", "")
            category = finding_dict.get("category", "")
            description = finding_dict.get("description", "")
            evidence = finding_dict.get("evidence", "")

            # All required fields must be present
            if not all([severity_str, category, description, evidence]):
                return None

            # Parse severity (handle both uppercase and lowercase)
            severity = self._parse_severity(severity_str)
            if severity is None:
                return None

            return Finding(
                commit_sha=commit_sha,
                expert=expert,
                severity=severity,
                category=category,
                description=description,
                evidence=evidence,
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Failed to create finding: {e}")
            return None

    def _parse_severity(self, severity_str: str) -> Optional[Severity]:
        """Parse severity string to Severity enum.

        Args:
            severity_str: Severity string (e.g., "LOW", "low", "MEDIUM")

        Returns:
            Severity enum value or None if invalid
        """
        severity_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        return severity_map.get(severity_str.lower())


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