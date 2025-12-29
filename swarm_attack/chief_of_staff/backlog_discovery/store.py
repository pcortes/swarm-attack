"""BacklogStore for persistent storage of opportunities.

This module provides:
- BacklogStore: Atomic persistence for discovered opportunities
- Similarity search using Jaccard index for duplicate detection
- Status-based queries for workflow management
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from swarm_attack.chief_of_staff.backlog_discovery.candidates import (
    Opportunity,
    OpportunityStatus,
)


class BacklogStore:
    """Persistent storage for backlog discovery opportunities.

    Stores opportunities in .swarm/backlog/candidates.json with atomic writes.
    Provides similarity search for duplicate detection and status-based queries.

    Attributes:
        base_path: Root directory for storage
        backlog_path: Path to backlog subdirectory
        candidates_file: Path to candidates.json file
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize BacklogStore.

        Args:
            base_path: Base directory for storage. Will create backlog/ subdirectory.
        """
        self.base_path = base_path
        self.backlog_path = base_path / "backlog"
        self.candidates_file = self.backlog_path / "candidates.json"

    def _ensure_directories(self) -> None:
        """Ensure backlog directory exists."""
        self.backlog_path.mkdir(parents=True, exist_ok=True)

    def _load_candidates(self) -> dict:
        """Load candidates data from file.

        Returns:
            Dict with 'opportunities' key containing list of opportunity dicts.
        """
        if not self.candidates_file.exists():
            return {"opportunities": []}

        try:
            with open(self.candidates_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"opportunities": []}

    def _save_candidates(self, data: dict) -> None:
        """Save candidates data to file atomically.

        Uses temp file + rename pattern for atomic writes.

        Args:
            data: Dict with 'opportunities' key.
        """
        self._ensure_directories()

        temp_file = self.candidates_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        temp_file.rename(self.candidates_file)

    def save_opportunity(self, opportunity: Opportunity) -> None:
        """Save an opportunity to the store.

        If opportunity with same ID exists, updates it.
        Otherwise adds new opportunity.

        Args:
            opportunity: Opportunity to save.
        """
        data = self._load_candidates()
        opportunities = data["opportunities"]

        # Find existing or add new
        found = False
        for i, opp in enumerate(opportunities):
            if opp.get("opportunity_id") == opportunity.opportunity_id:
                opportunities[i] = opportunity.to_dict()
                found = True
                break

        if not found:
            opportunities.append(opportunity.to_dict())

        data["opportunities"] = opportunities
        self._save_candidates(data)

    def get_opportunity(self, opportunity_id: str) -> Optional[Opportunity]:
        """Get an opportunity by ID.

        Args:
            opportunity_id: Unique identifier of the opportunity.

        Returns:
            Opportunity if found, None otherwise.
        """
        data = self._load_candidates()

        for opp_data in data["opportunities"]:
            if opp_data.get("opportunity_id") == opportunity_id:
                return Opportunity.from_dict(opp_data)

        return None

    def get_all(self) -> list[Opportunity]:
        """Get all opportunities regardless of status.

        Returns:
            List of all Opportunity objects.
        """
        data = self._load_candidates()
        return [Opportunity.from_dict(opp) for opp in data["opportunities"]]

    def get_opportunities_by_status(
        self, status: OpportunityStatus
    ) -> list[Opportunity]:
        """Get opportunities filtered by status.

        Args:
            status: OpportunityStatus to filter by.

        Returns:
            List of Opportunity objects with matching status.
        """
        all_opps = self.get_all()
        return [opp for opp in all_opps if opp.status == status]

    def get_actionable(self) -> list[Opportunity]:
        """Get actionable opportunities sorted by priority.

        Returns opportunities with ACTIONABLE status, sorted by
        priority_rank (lower first, None values last).

        Returns:
            List of actionable Opportunity objects sorted by priority.
        """
        actionable = self.get_opportunities_by_status(OpportunityStatus.ACTIONABLE)

        # Sort by priority_rank (lower first, None last)
        def sort_key(opp: Opportunity) -> tuple:
            if opp.priority_rank is None:
                return (1, 999999)  # Put None values last
            return (0, opp.priority_rank)

        actionable.sort(key=sort_key)
        return actionable

    def mark_accepted(
        self, opportunity_id: str, linked_issue: Optional[int] = None
    ) -> None:
        """Mark an opportunity as accepted.

        Args:
            opportunity_id: ID of opportunity to accept.
            linked_issue: Optional GitHub issue number.
        """
        opp = self.get_opportunity(opportunity_id)
        if opp is None:
            return

        opp.status = OpportunityStatus.ACCEPTED
        if linked_issue is not None:
            opp.linked_issue = linked_issue
        self.save_opportunity(opp)

    def mark_rejected(self, opportunity_id: str) -> None:
        """Mark an opportunity as rejected.

        Args:
            opportunity_id: ID of opportunity to reject.
        """
        opp = self.get_opportunity(opportunity_id)
        if opp is None:
            return

        opp.status = OpportunityStatus.REJECTED
        self.save_opportunity(opp)

    def mark_deferred(self, opportunity_id: str) -> None:
        """Mark an opportunity as deferred.

        Args:
            opportunity_id: ID of opportunity to defer.
        """
        opp = self.get_opportunity(opportunity_id)
        if opp is None:
            return

        opp.status = OpportunityStatus.DEFERRED
        self.save_opportunity(opp)

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase words for similarity matching.

        Args:
            text: Text to tokenize.

        Returns:
            Set of lowercase word tokens.
        """
        words = re.findall(r"\w+", text.lower())
        return set(words)

    def _jaccard_similarity(self, set_a: set[str], set_b: set[str]) -> float:
        """Calculate Jaccard similarity between two sets.

        Args:
            set_a: First set of tokens.
            set_b: Second set of tokens.

        Returns:
            Jaccard similarity coefficient (0.0 to 1.0).
        """
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return 0.0
        return intersection / union

    def _get_opportunity_text(self, opp: Opportunity) -> str:
        """Extract searchable text from an opportunity.

        Combines title, description, and evidence content for similarity matching.

        Args:
            opp: Opportunity to extract text from.

        Returns:
            Combined text string.
        """
        parts = [opp.title, opp.description]
        for ev in opp.evidence:
            parts.append(ev.content)
        return " ".join(parts)

    def find_similar(self, opportunity: Opportunity, k: int = 5) -> list[Opportunity]:
        """Find similar opportunities using Jaccard similarity.

        Compares the given opportunity against all stored opportunities
        using token-based Jaccard similarity on title, description, and evidence.

        Args:
            opportunity: Opportunity to find matches for.
            k: Maximum number of similar opportunities to return.

        Returns:
            List of similar Opportunity objects sorted by similarity (highest first).
        """
        all_opps = self.get_all()
        if not all_opps:
            return []

        query_text = self._get_opportunity_text(opportunity)
        query_tokens = self._tokenize(query_text)

        if not query_tokens:
            return []

        scored: list[tuple[float, Opportunity]] = []
        for opp in all_opps:
            # Don't match against self
            if opp.opportunity_id == opportunity.opportunity_id:
                continue

            opp_text = self._get_opportunity_text(opp)
            opp_tokens = self._tokenize(opp_text)
            similarity = self._jaccard_similarity(query_tokens, opp_tokens)

            if similarity > 0:
                scored.append((similarity, opp))

        # Sort by similarity (highest first)
        scored.sort(key=lambda x: x[0], reverse=True)

        return [opp for _, opp in scored[:k]]
