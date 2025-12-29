"""DiscoveryOrchestrator for running discovery agents and merging results.

This module provides:
- DiscoveryOrchestrator: Runs multiple discovery agents
- Merges and deduplicates results
- Triggers debate when threshold exceeded (Phase 3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Opportunity,
    OpportunityStatus,
)
from swarm_attack.chief_of_staff.backlog_discovery.store import BacklogStore

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig
    from swarm_attack.chief_of_staff.backlog_discovery.discovery_agent import (
        TestFailureDiscoveryAgent,
    )
    from swarm_attack.chief_of_staff.backlog_discovery.stalled_work_agent import (
        StalledWorkDiscoveryAgent,
    )
    from swarm_attack.chief_of_staff.backlog_discovery.code_quality_agent import (
        CodeQualityDiscoveryAgent,
    )


@dataclass
class DiscoveryResult:
    """Result of running discovery."""

    opportunities: list[Opportunity]
    total_candidates: int
    cost_usd: float
    debate_triggered: bool
    debate_session_id: Optional[str] = None


class DiscoveryOrchestrator:
    """Runs discovery agents and merges results.

    Triggers debate if >5 opportunities found (Phase 3).

    Attributes:
        agents: Dict of agent name to agent instance.
        backlog_store: Store for persisting opportunities.
    """

    def __init__(
        self,
        config: SwarmConfig,
        backlog_store: BacklogStore,
        test_failure_agent: Optional[Any] = None,
        stalled_work_agent: Optional[Any] = None,
        code_quality_agent: Optional[Any] = None,
        feature_opportunity_agent: Optional[Any] = None,
    ):
        """Initialize DiscoveryOrchestrator.

        Args:
            config: SwarmConfig with paths and settings.
            backlog_store: BacklogStore for persistence.
            test_failure_agent: Optional TestFailureDiscoveryAgent.
            stalled_work_agent: Optional StalledWorkDiscoveryAgent.
            code_quality_agent: Optional CodeQualityDiscoveryAgent.
            feature_opportunity_agent: Optional FeatureOpportunityAgent.
        """
        self.config = config
        self.backlog_store = backlog_store

        # Initialize agents dict
        self.agents: dict[str, Any] = {}

        # Use provided agents or create defaults
        if test_failure_agent is not None:
            self.agents["test"] = test_failure_agent
        else:
            self.agents["test"] = self._create_test_failure_agent()

        if stalled_work_agent is not None:
            self.agents["stalled"] = stalled_work_agent
        else:
            self.agents["stalled"] = self._create_stalled_work_agent()

        if code_quality_agent is not None:
            self.agents["quality"] = code_quality_agent
        else:
            self.agents["quality"] = self._create_code_quality_agent()

        if feature_opportunity_agent is not None:
            self.agents["feature"] = feature_opportunity_agent
        # Feature agent is optional and expensive, so we don't create it by default

    def _create_test_failure_agent(self) -> Any:
        """Create TestFailureDiscoveryAgent."""
        from swarm_attack.chief_of_staff.backlog_discovery.discovery_agent import (
            TestFailureDiscoveryAgent,
        )
        return TestFailureDiscoveryAgent(
            config=self.config,
            backlog_store=self.backlog_store,
        )

    def _create_stalled_work_agent(self) -> Any:
        """Create StalledWorkDiscoveryAgent."""
        from swarm_attack.chief_of_staff.backlog_discovery.stalled_work_agent import (
            StalledWorkDiscoveryAgent,
        )
        return StalledWorkDiscoveryAgent(
            config=self.config,
            backlog_store=self.backlog_store,
        )

    def _create_code_quality_agent(self) -> Any:
        """Create CodeQualityDiscoveryAgent."""
        from swarm_attack.chief_of_staff.backlog_discovery.code_quality_agent import (
            CodeQualityDiscoveryAgent,
        )
        return CodeQualityDiscoveryAgent(
            config=self.config,
            backlog_store=self.backlog_store,
        )

    def discover(
        self,
        types: list[str] | None = None,
        max_candidates: int = 10,
        trigger_debate: bool = True,
        debate_threshold: int = 5,
    ) -> DiscoveryResult:
        """Run discovery agents and merge results.

        Args:
            types: Which agents to run ("test", "stalled", "quality", "feature", "all")
                   Defaults to ["test"] if not specified.
            max_candidates: Maximum opportunities to return.
            trigger_debate: Whether to trigger debate for >threshold.
            debate_threshold: Number of opportunities that triggers debate.

        Returns:
            DiscoveryResult with opportunities and metadata.
        """
        if types is None:
            types = ["test"]

        all_opportunities: list[Opportunity] = []
        total_cost = 0.0

        # Determine which agents to run
        if "all" in types:
            agents_to_run = list(self.agents.values())
        else:
            agents_to_run = [
                self.agents[t] for t in types
                if t in self.agents
            ]

        # Run each agent
        for agent in agents_to_run:
            try:
                result = agent.run(context={})
                opportunities = result.output.get("opportunities", [])
                all_opportunities.extend(opportunities)
                total_cost += result.cost_usd
            except Exception:
                # Continue with other agents if one fails
                continue

        # Deduplicate
        unique = self._deduplicate(all_opportunities)

        # Check if debate should be triggered
        debate_triggered = False
        debate_session_id = None

        if trigger_debate and len(unique) > debate_threshold:
            debate_triggered = True
            # Phase 3: Would run debate here
            # For now, just mark as triggered
            # debate_result = self._run_debate(unique)
            # unique = debate_result.ranked_opportunities
            # total_cost += debate_result.cost_usd
            # debate_session_id = debate_result.session.session_id

        return DiscoveryResult(
            opportunities=unique[:max_candidates],
            total_candidates=len(unique),
            cost_usd=total_cost,
            debate_triggered=debate_triggered,
            debate_session_id=debate_session_id,
        )

    def _deduplicate(
        self, opportunities: list[Opportunity]
    ) -> list[Opportunity]:
        """Remove duplicates using semantic similarity.

        Uses affected_files and title similarity to detect duplicates.

        Args:
            opportunities: List of opportunities to deduplicate.

        Returns:
            Deduplicated list of opportunities.
        """
        if not opportunities:
            return []

        unique: list[Opportunity] = []
        seen_keys: set[str] = set()

        for opp in opportunities:
            # Create a deduplication key
            key = self._get_dedup_key(opp)

            if key not in seen_keys:
                unique.append(opp)
                seen_keys.add(key)

        return unique

    def _get_dedup_key(self, opp: Opportunity) -> str:
        """Get a deduplication key for an opportunity.

        Uses affected_files if available, otherwise title words.

        Args:
            opp: Opportunity to get key for.

        Returns:
            String key for deduplication.
        """
        # Use affected files if available
        if opp.affected_files:
            return "|".join(sorted(opp.affected_files))

        # Otherwise use significant words from title
        words = opp.title.lower().split()
        # Filter out common words
        stop_words = {"fix", "add", "update", "test", "the", "a", "an", "for", "in"}
        significant = [w for w in words if w not in stop_words and len(w) > 2]

        return "|".join(sorted(significant[:3]))

    def _run_debate(self, opportunities: list[Opportunity]) -> Any:
        """Run 3-agent debate to prioritize. See Phase 3.

        Args:
            opportunities: Opportunities to debate.

        Returns:
            DebateResult with ranked opportunities.
        """
        # Phase 3 implementation
        # For now, return opportunities unchanged
        pass
