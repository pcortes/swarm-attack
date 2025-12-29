"""StalledWorkDiscoveryAgent for finding stalled features and interrupted sessions.

This module provides:
- StalledWorkDiscoveryAgent: Discovers stalled work without LLM cost
- Detects features stuck in same phase >24 hours
- Detects interrupted/paused sessions
- Detects goals with repeated failures (>2 attempts)
"""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
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
from swarm_attack.chief_of_staff.state_gatherer import (
    FeatureSummary,
    InterruptedSession,
    RepoStateSnapshot,
    StateGatherer,
)
from swarm_attack.chief_of_staff.episodes import Episode, EpisodeStore

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


class StalledWorkDiscoveryAgent(BaseAgent):
    """Discovers stalled features and interrupted sessions.

    No LLM cost - uses StateGatherer data only.

    Detection rules:
    - Feature in same phase >24h -> STALLED_WORK
    - Session state = INTERRUPTED/PAUSED -> STALLED_WORK
    - Same goal failed 3+ times -> STALLED_WORK
    - Issue IN_PROGRESS >4 hours -> STALLED_WORK (future)

    Attributes:
        name: Agent identifier for logs and checkpoints.
        backlog_store: Store for persisting discovered opportunities.
    """

    name: str = "stalled-work-discovery"

    def __init__(
        self,
        config: SwarmConfig,
        backlog_store: Optional[BacklogStore] = None,
        episode_store: Optional[EpisodeStore] = None,
        state_gatherer: Optional[StateGatherer] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize StalledWorkDiscoveryAgent.

        Args:
            config: SwarmConfig with paths and settings.
            backlog_store: Optional BacklogStore for persistence.
            episode_store: Optional EpisodeStore for episode lookup.
            state_gatherer: Optional StateGatherer for gathering state.
            **kwargs: Additional arguments passed to BaseAgent.
        """
        super().__init__(config=config, **kwargs)
        self.backlog_store = backlog_store
        self._episode_store = episode_store
        self._state_gatherer = state_gatherer

    def run(self, context: dict[str, Any]) -> AgentResult:
        """Execute stalled work discovery.

        Discovers:
        1. Features stuck in same phase >24 hours
        2. Interrupted/paused sessions
        3. Goals with repeated failures (>2 attempts)
        4. Issues stuck in IN_PROGRESS

        Args:
            context: Context dict with optional keys:
                - max_opportunities: Limit on opportunities to return (default 10)

        Returns:
            AgentResult with list of Opportunity objects
        """
        max_opportunities = context.get("max_opportunities", 10)
        opportunities: list[Opportunity] = []

        # Get state snapshot
        gatherer = self._get_state_gatherer()
        snapshot = gatherer.gather(include_github=False)

        # 1. Check for stalled features (>24 hours in same phase)
        stalled_features = self._find_stalled_features(snapshot)
        opportunities.extend(stalled_features)

        # 2. Check for interrupted/paused sessions
        interrupted_sessions = self._find_interrupted_sessions(snapshot)
        opportunities.extend(interrupted_sessions)

        # 3. Check for repeated goal failures
        repeated_failures = self._find_repeated_failures()
        opportunities.extend(repeated_failures)

        # Limit results
        opportunities = opportunities[:max_opportunities]

        # Save to store
        if self.backlog_store:
            for opp in opportunities:
                self.backlog_store.save_opportunity(opp)

        self._log("discovery_complete", {
            "stalled_features": len(stalled_features),
            "interrupted_sessions": len(interrupted_sessions),
            "repeated_failures": len(repeated_failures),
            "opportunities_created": len(opportunities),
        })

        return AgentResult.success_result(
            output={"opportunities": opportunities},
            cost_usd=0.0,  # No LLM cost
        )

    def _get_state_gatherer(self) -> StateGatherer:
        """Get or create StateGatherer instance."""
        if self._state_gatherer:
            return self._state_gatherer

        # Create minimal config if needed
        class MinimalConfig:
            pass

        return StateGatherer(MinimalConfig())

    def _find_stalled_features(
        self, snapshot: RepoStateSnapshot
    ) -> list[Opportunity]:
        """Find features stuck in the same phase for >24 hours.

        Args:
            snapshot: Repository state snapshot.

        Returns:
            List of STALLED_WORK opportunities.
        """
        opportunities = []
        stall_threshold = timedelta(hours=24)
        now = datetime.now()

        for feature in snapshot.features:
            # Skip completed features
            if feature.phase in ("COMPLETED", "DONE", "SHIPPED"):
                continue

            # Check last activity time
            last_activity = self._get_feature_last_activity(feature.feature_id)
            if last_activity is None:
                continue

            hours_stalled = (now - last_activity).total_seconds() / 3600

            if hours_stalled > 24:
                opp = self._create_stalled_feature_opportunity(
                    feature=feature,
                    hours_stalled=hours_stalled,
                )
                opportunities.append(opp)

        return opportunities

    def _get_feature_last_activity(
        self, feature_id: str
    ) -> Optional[datetime]:
        """Get the last activity timestamp for a feature.

        Args:
            feature_id: Feature identifier.

        Returns:
            datetime of last activity or None if unknown.
        """
        # Try to read from state file
        try:
            import json
            state_path = Path.cwd() / ".swarm" / "state" / f"{feature_id}.json"
            if state_path.exists():
                data = json.loads(state_path.read_text())
                updated_at = data.get("updated_at")
                if updated_at:
                    return datetime.fromisoformat(updated_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except (json.JSONDecodeError, OSError, ValueError):
            pass

        # Default: assume recent if we can't determine
        return None

    def _find_interrupted_sessions(
        self, snapshot: RepoStateSnapshot
    ) -> list[Opportunity]:
        """Find interrupted or paused sessions.

        Args:
            snapshot: Repository state snapshot.

        Returns:
            List of STALLED_WORK opportunities for interrupted sessions.
        """
        opportunities = []

        for session in snapshot.interrupted_sessions:
            opp = self._create_interrupted_session_opportunity(session)
            opportunities.append(opp)

        return opportunities

    def _find_repeated_failures(self) -> list[Opportunity]:
        """Find goals that have failed 3+ times.

        Returns:
            List of STALLED_WORK opportunities for repeated failures.
        """
        opportunities = []
        episodes = self._get_recent_episodes()

        # Count failures per goal
        failure_counts: Counter[str] = Counter()
        goal_errors: dict[str, str] = {}

        for ep in episodes:
            if not ep.success:
                failure_counts[ep.goal_id] += 1
                goal_errors[ep.goal_id] = ep.error or "Unknown error"

        # Create opportunities for goals with 3+ failures
        for goal_id, count in failure_counts.items():
            if count >= 3:
                opp = self._create_repeated_failure_opportunity(
                    goal_id=goal_id,
                    failure_count=count,
                    last_error=goal_errors.get(goal_id, "Unknown error"),
                )
                opportunities.append(opp)

        return opportunities

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

    def _create_stalled_feature_opportunity(
        self,
        feature: FeatureSummary,
        hours_stalled: float,
    ) -> Opportunity:
        """Create an opportunity for a stalled feature.

        Args:
            feature: The stalled feature summary.
            hours_stalled: Hours since last activity.

        Returns:
            New STALLED_WORK Opportunity.
        """
        opp_id = self._generate_opportunity_id(
            f"stalled-{feature.feature_id}-{feature.phase}"
        )
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Calculate progress
        progress = 0.0
        if feature.issue_count > 0:
            progress = feature.completed_issues / feature.issue_count

        title = f"Resume stalled feature: {feature.feature_id}"
        description = (
            f"Feature '{feature.feature_id}' has been in phase '{feature.phase}' "
            f"for {hours_stalled:.0f} hours without activity. "
            f"Progress: {progress:.0%} ({feature.completed_issues}/{feature.issue_count} issues)."
        )

        evidence = [
            Evidence(
                source="state_gatherer",
                content=f"Feature stalled in {feature.phase} phase for {hours_stalled:.0f}h",
                timestamp=now,
            )
        ]

        actionability = self._calculate_progress_actionability(feature)

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _create_interrupted_session_opportunity(
        self, session: InterruptedSession
    ) -> Opportunity:
        """Create an opportunity for an interrupted session.

        Args:
            session: The interrupted session.

        Returns:
            New STALLED_WORK Opportunity.
        """
        opp_id = self._generate_opportunity_id(
            f"session-{session.session_id}-{session.state}"
        )
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        hours_ago = (datetime.now() - session.timestamp).total_seconds() / 3600

        title = f"Resume {session.state.lower()} session: {session.session_id}"
        description = (
            f"Session '{session.session_id}' for feature '{session.feature_id}' "
            f"is in {session.state} state for {hours_ago:.0f} hours."
        )

        evidence = [
            Evidence(
                source="state_gatherer",
                content=f"Session state: {session.state}",
                timestamp=session.timestamp.isoformat() if session.timestamp else now,
            )
        ]

        actionability = self._calculate_session_actionability(session)

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _create_repeated_failure_opportunity(
        self,
        goal_id: str,
        failure_count: int,
        last_error: str,
    ) -> Opportunity:
        """Create an opportunity for a repeatedly failing goal.

        Args:
            goal_id: The goal identifier.
            failure_count: Number of times the goal has failed.
            last_error: The last error message.

        Returns:
            New STALLED_WORK Opportunity.
        """
        opp_id = self._generate_opportunity_id(f"repeated-{goal_id}-{failure_count}")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        title = f"Fix repeated failure: {goal_id} ({failure_count}x)"
        description = (
            f"Goal '{goal_id}' has failed {failure_count} times. "
            f"Last error: {last_error}"
        )

        evidence = [
            Evidence(
                source="episode_store",
                content=f"Failed {failure_count} times. Last error: {last_error}",
                timestamp=now,
            )
        ]

        # Higher failure count = higher actionability (something is really stuck)
        clarity = min(0.5 + (failure_count - 3) * 0.1, 0.9)

        actionability = ActionabilityScore(
            clarity=clarity,
            evidence=0.8,  # We have good evidence from episode store
            effort="medium",  # Repeated failures usually need investigation
            reversibility="full",
        )

        return Opportunity(
            opportunity_id=opp_id,
            opportunity_type=OpportunityType.STALLED_WORK,
            status=OpportunityStatus.DISCOVERED,
            title=title,
            description=description,
            evidence=evidence,
            actionability=actionability,
            created_at=now,
            updated_at=now,
            discovered_by=self.name,
        )

    def _calculate_progress_actionability(
        self, feature: FeatureSummary
    ) -> ActionabilityScore:
        """Calculate actionability score based on feature progress.

        Args:
            feature: Feature summary with progress info.

        Returns:
            ActionabilityScore based on progress.
        """
        # Calculate progress percentage
        progress = 0.0
        if feature.issue_count > 0:
            progress = feature.completed_issues / feature.issue_count

        # Higher progress = higher clarity (we know more about what's left)
        # 80%+ complete = high clarity, 10% = low clarity
        if progress >= 0.8:
            clarity = 0.9
            effort = "small"  # Almost done
        elif progress >= 0.5:
            clarity = 0.7
            effort = "medium"
        elif progress >= 0.3:
            clarity = 0.5
            effort = "medium"
        else:
            clarity = 0.3
            effort = "large"  # Lots of work remaining

        return ActionabilityScore(
            clarity=clarity,
            evidence=0.8,  # We have state data
            effort=effort,
            reversibility="full",  # Can always continue or pivot
        )

    def _calculate_session_actionability(
        self, session: InterruptedSession
    ) -> ActionabilityScore:
        """Calculate actionability score for an interrupted session.

        Args:
            session: Interrupted session info.

        Returns:
            ActionabilityScore for resuming the session.
        """
        # Interrupted sessions are usually easy to resume
        # PAUSED = intentional, usually clear what to do
        # INTERRUPTED = might need more investigation

        if session.state.upper() == "PAUSED":
            clarity = 0.8
            effort = "small"
        else:  # INTERRUPTED
            clarity = 0.6
            effort = "medium"

        return ActionabilityScore(
            clarity=clarity,
            evidence=0.7,
            effort=effort,
            reversibility="full",
        )

    def _generate_opportunity_id(self, seed: str) -> str:
        """Generate a unique opportunity ID.

        Args:
            seed: Seed string for the hash.

        Returns:
            Unique opportunity ID string.
        """
        hash_suffix = hashlib.md5(seed.encode()).hexdigest()[:8]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"opp-sw-{timestamp}-{hash_suffix}"
