"""Discovery agents for finding backlog opportunities.

This module provides:
- TestFailureDiscoveryAgent: Discovers opportunities from test failures
- Parses pytest output and EpisodeStore for failed tests
- Rule-based actionability scoring (no LLM cost by default)
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.agents.base import BaseAgent, AgentResult
from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    ActionabilityScore,
    Evidence,
    Opportunity,
    OpportunityStatus,
    OpportunityType,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore
from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


class FailureDiscoveryAgent(BaseAgent):
    """Discovers opportunities from test failures.

    MVP implementation that does NOT use LLM for discovery (cost control).
    Uses rule-based actionability scoring instead.

    Attributes:
        name: Agent identifier for logs and checkpoints.
        backlog_store: Store for persisting discovered opportunities.
    """

    name: str = "test-failure-discovery"

    def __init__(
        self,
        config: SwarmConfig,
        backlog_store: Optional[BacklogStore] = None,
        episode_store: Optional[EpisodeStore] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize TestFailureDiscoveryAgent.

        Args:
            config: SwarmConfig with paths and settings.
            backlog_store: Optional BacklogStore for persistence.
            episode_store: Optional EpisodeStore for episode lookup.
            **kwargs: Additional arguments passed to BaseAgent.
        """
        super().__init__(config=config, **kwargs)
        self.backlog_store = backlog_store
        self._episode_store = episode_store

    def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute test failure discovery.

        Args:
            context: Context dict with optional keys:
                - max_opportunities: Limit on opportunities to return (default 10)
                - pytest_output: Pre-captured pytest output (for testing)
                - episodes: Pre-loaded episodes (for testing)

        Returns:
            AgentResult with list of discovered opportunities.
        """
        max_opportunities = context.get("max_opportunities", 10)

        # 1. Run pytest to get current failures
        pytest_output = context.get("pytest_output") or self._run_pytest()
        pytest_failures = self._parse_pytest_output(pytest_output)

        # 2. Get failures from episode store
        episodes = context.get("episodes") or self._get_recent_episodes()
        episode_failures = self._extract_episode_failures(episodes)

        # 3. Merge and deduplicate
        all_failures = self._merge_failures(pytest_failures, episode_failures)

        # 4. Filter out duplicates of rejected opportunities
        if self.backlog_store:
            all_failures = [
                f for f in all_failures
                if not self._is_duplicate_of_rejected(f, self.backlog_store)
            ]

        # 5. Convert to opportunities with actionability scores
        opportunities: list[Opportunity] = []
        for failure in all_failures[:max_opportunities]:
            opp = self._failure_to_opportunity(failure)
            opportunities.append(opp)

            # Save to store
            if self.backlog_store:
                self.backlog_store.save_opportunity(opp)

        self._log("discovery_complete", {
            "pytest_failures": len(pytest_failures),
            "episode_failures": len(episode_failures),
            "opportunities_created": len(opportunities),
        })

        return AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=0.0,  # No LLM cost in MVP
        )

    def _run_pytest(self) -> str:
        """Run pytest and capture output.

        Returns:
            Pytest stdout output.
        """
        try:
            result = subprocess.run(
                ["pytest", "--tb=no", "-v", "--color=no"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=Path(self.config.repo_root),
            )
            return result.stdout + result.stderr
        except (subprocess.SubprocessError, OSError, subprocess.TimeoutExpired) as e:
            self._log("pytest_error", {"error": str(e)}, level="warning")
            return ""

    def _parse_pytest_output(self, output: str) -> list[dict[str, Any]]:
        """Parse pytest output to extract failures.

        Args:
            output: Raw pytest stdout/stderr.

        Returns:
            List of failure dicts with test_file, test_name, error, source.
        """
        if not output:
            return []

        failures = []
        # Pattern: FAILED tests/test_foo.py::test_bar - ErrorType
        pattern = r"FAILED\s+([^:]+)::(\S+)\s*-?\s*(.*)"

        for line in output.split("\n"):
            match = re.search(pattern, line)
            if match:
                test_file = match.group(1).strip()
                test_name = match.group(2).strip()
                error = match.group(3).strip() if match.group(3) else "Unknown error"

                failures.append({
                    "test_file": test_file,
                    "test_name": test_name,
                    "error": error,
                    "source": "pytest",
                })

        return failures

    def _get_recent_episodes(self, limit: int = 100) -> list[Episode]:
        """Get recent episodes from EpisodeStore.

        Args:
            limit: Maximum number of episodes to return.

        Returns:
            List of Episode objects.
        """
        if self._episode_store:
            return self._episode_store.load_recent(limit)

        # Try default location
        try:
            store = EpisodeStore()
            return store.load_recent(limit)
        except Exception:
            return []

    def _extract_episode_failures(
        self, episodes: list[Episode]
    ) -> list[dict[str, Any]]:
        """Extract failed test episodes.

        Args:
            episodes: List of Episode objects.

        Returns:
            List of failure dicts with episode metadata.
        """
        failures = []
        for ep in episodes:
            # Only include failed episodes that look like tests
            if not ep.success and "test" in ep.goal_id.lower():
                failures.append({
                    "episode_id": ep.episode_id,
                    "goal_id": ep.goal_id,
                    "error": ep.error or "Test failed",
                    "timestamp": ep.timestamp,
                    "source": "episode",
                })
        return failures

    def _merge_failures(
        self,
        pytest_failures: list[dict[str, Any]],
        episode_failures: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Merge failures from multiple sources with deduplication.

        Args:
            pytest_failures: Failures from pytest output.
            episode_failures: Failures from EpisodeStore.

        Returns:
            Merged and deduplicated list of failures.
        """
        merged = list(pytest_failures)
        seen_tests = set()

        # Track pytest tests for deduplication
        for f in pytest_failures:
            key = f"{f.get('test_file', '')}::{f.get('test_name', '')}"
            seen_tests.add(key.lower())

        # Add episode failures that aren't duplicates
        for f in episode_failures:
            goal_id = f.get("goal_id", "").lower()
            # Check if this episode matches any pytest test
            is_duplicate = any(
                test_key in goal_id or goal_id in test_key
                for test_key in seen_tests
            )
            if not is_duplicate:
                merged.append(f)

        return merged

    def _failure_to_opportunity(self, failure: dict[str, Any]) -> Opportunity:
        """Convert a failure dict to an Opportunity.

        Args:
            failure: Failure dict from parsing.

        Returns:
            New Opportunity object.
        """
        opp_id = self._generate_opportunity_id(failure)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Build title
        if failure.get("source") == "pytest":
            title = f"Fix {failure.get('test_name', 'unknown test')} failing"
        else:
            goal_id = failure.get("goal_id", "")
            title = f"Fix {goal_id} test failure"

        # Build description
        error = failure.get("error", "Unknown error")
        description = f"Test failure detected: {error}"

        # Build evidence
        evidence = [
            Evidence(
                source="test_output",
                content=error,
                file_path=failure.get("test_file"),
                timestamp=failure.get("timestamp") or now,
            )
        ]

        # Calculate actionability
        actionability = self._calculate_actionability(failure)

        # Determine affected files
        affected_files = []
        if failure.get("test_file"):
            affected_files.append(failure["test_file"])

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.TEST_FAILURE,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            affected_files=affected_files,
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _calculate_actionability(self, failure: dict[str, Any]) -> ActionabilityScore:
        """Calculate actionability score using rules (no LLM).

        Args:
            failure: Failure dict with error info.

        Returns:
            ActionabilityScore based on heuristics.
        """
        error = failure.get("error", "").lower()

        # Clarity scoring - how clear is the error?
        clarity = 0.5  # Default
        if "assert" in error:
            clarity = 0.8  # Assertions are usually clear
        if "expected" in error and "got" in error:
            clarity = 0.9  # Very clear comparison
        if "typeerror" in error or "type" in error:
            clarity = 0.85  # Type errors are usually clear
        if "nameerror" in error or "undefined" in error:
            clarity = 0.8  # Missing name is clear
        if "error occurred" in error or error == "error":
            clarity = 0.2  # Very vague

        # Evidence scoring - how much info do we have?
        evidence_score = 0.5  # Default
        if failure.get("test_file"):
            evidence_score += 0.2
        if len(error) > 50:  # More detail in error
            evidence_score += 0.1
        if "line" in error:  # Has line number
            evidence_score += 0.1
        evidence_score = min(1.0, evidence_score)

        # Effort estimation based on error type
        effort = "medium"  # Default
        if any(kw in error for kw in ["typeerror", "type", "nameerror", "keyerror"]):
            effort = "small"  # Usually quick fixes
        elif any(kw in error for kw in ["timeout", "connection", "database"]):
            effort = "large"  # Usually infrastructure issues
        elif "import" in error:
            effort = "small"  # Usually missing import

        # Reversibility - test fixes are generally fully reversible
        reversibility = "full"

        return ActionabilityScore(
            clarity=clarity,
            evidence=evidence_score,
            effort=effort,
            reversibility=reversibility,
        )

    def _generate_opportunity_id(self, failure: dict[str, Any]) -> str:
        """Generate a unique opportunity ID for a failure.

        Args:
            failure: Failure dict.

        Returns:
            Unique opportunity ID string.
        """
        # Create a hash from failure content
        content = f"{failure.get('test_file', '')}-{failure.get('test_name', '')}-{failure.get('goal_id', '')}"
        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

        return f"opp-tf-{timestamp}-{hash_suffix}"

    def _is_duplicate_of_rejected(
        self, failure: dict[str, Any], store: BacklogStore
    ) -> bool:
        """Check if a failure is similar to a rejected opportunity.

        Args:
            failure: Failure dict to check.
            store: BacklogStore to search for rejected opportunities.

        Returns:
            True if similar rejected opportunity exists.
        """
        # Create a temporary opportunity for similarity search
        temp_opp = self._failure_to_opportunity(failure)

        # Find similar opportunities
        similar = store.find_similar(temp_opp, k=3)

        # Check if any similar are rejected
        for opp in similar:
            if opp.status == OpportunityStatus.REJECTED:
                # Use Jaccard threshold for "same test"
                return True

        return False


# Backwards compatibility alias (avoid pytest collection)
TestFailureDiscoveryAgent = FailureDiscoveryAgent
