"""Dataclasses for Backlog Discovery opportunities and evidence.

This module defines the core data structures for the backlog discovery system:
- OpportunityType: Categories of discovered opportunities
- OpportunityStatus: Lifecycle states for opportunities
- Evidence: Supporting data for an opportunity
- ActionabilityScore: Scoring for how actionable an opportunity is
- Opportunity: A discovered work item candidate
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class OpportunityType(Enum):
    """Categories of discovered opportunities."""

    TEST_FAILURE = "test_failure"
    STALLED_WORK = "stalled_work"
    CODE_QUALITY = "code_quality"
    COVERAGE_GAP = "coverage_gap"
    COMPLEXITY = "complexity"
    FEATURE_OPPORTUNITY = "feature_opportunity"  # McKinsey-style strategic features


class OpportunityStatus(Enum):
    """Lifecycle states for opportunities."""

    DISCOVERED = "discovered"      # Newly found
    DEBATING = "debating"          # Under debate for prioritization
    ACTIONABLE = "actionable"      # Ready for human review
    ACCEPTED = "accepted"          # Human approved, will become work
    REJECTED = "rejected"          # Human rejected
    DEFERRED = "deferred"          # Postponed for later


@dataclass
class Evidence:
    """Supporting evidence for an opportunity.

    Captures the source and content of evidence that supports
    the discovery of an opportunity, with optional file location.

    Attributes:
        source: Where the evidence came from (e.g., "test_output", "git_log")
        content: The actual evidence content/message
        file_path: Optional path to the file involved
        line_number: Optional line number in the file
        timestamp: Optional timestamp when evidence was collected
    """

    source: str
    content: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        """Create from dictionary."""
        return cls(
            source=data.get("source", ""),
            content=data.get("content", ""),
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            timestamp=data.get("timestamp"),
        )


@dataclass
class ActionabilityScore:
    """Score for how actionable an opportunity is.

    Provides a structured assessment of an opportunity's viability
    for immediate action, with weighted scoring.

    Attributes:
        clarity: How clear the problem/solution is (0-1)
        evidence: Strength of supporting evidence (0-1)
        effort: Estimated effort ("small", "medium", "large")
        reversibility: How reversible the fix is ("full", "partial", "none")
    """

    clarity: float
    evidence: float
    effort: str   # "small", "medium", "large"
    reversibility: str  # "full", "partial", "none"

    @property
    def overall(self) -> float:
        """Calculate overall actionability score.

        Weighted formula:
        - clarity: 40%
        - evidence: 40%
        - effort bonus: 20% for small, 10% for medium, 0% for large

        Returns:
            Score from 0.0 to 1.0
        """
        effort_bonus = {
            "small": 0.2,
            "medium": 0.1,
            "large": 0.0,
        }.get(self.effort, 0.0)

        return (self.clarity * 0.4) + (self.evidence * 0.4) + effort_bonus

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionabilityScore":
        """Create from dictionary."""
        return cls(
            clarity=data.get("clarity", 0.0),
            evidence=data.get("evidence", 0.0),
            effort=data.get("effort", "medium"),
            reversibility=data.get("reversibility", "partial"),
        )


@dataclass
class Opportunity:
    """A discovered work item candidate.

    Represents an opportunity for improvement discovered by the
    backlog discovery system. Opportunities progress through states
    from DISCOVERED to ACCEPTED/REJECTED.

    Attributes:
        opportunity_id: Unique identifier for this opportunity
        opportunity_type: Category of opportunity
        status: Current lifecycle status
        title: Short description of the opportunity
        description: Detailed description
        evidence: List of supporting evidence
        actionability: Optional actionability scoring
        suggested_fix: Optional LLM-generated fix suggestion
        affected_files: List of files involved
        created_at: ISO timestamp when discovered
        updated_at: ISO timestamp of last update
        discovered_by: Agent that discovered this
        priority_rank: Priority after debate (lower is higher priority)
        debate_session_id: ID of debate session if debated
        linked_issue: GitHub issue number if accepted
    """

    opportunity_id: str
    opportunity_type: OpportunityType
    status: OpportunityStatus
    title: str
    description: str
    evidence: list[Evidence]
    actionability: Optional[ActionabilityScore] = None
    suggested_fix: Optional[str] = None
    affected_files: list[str] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    discovered_by: Optional[str] = None
    priority_rank: Optional[int] = None
    debate_session_id: Optional[str] = None
    linked_issue: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Enums are serialized as their string values for JSON compatibility.
        """
        return {
            "opportunity_id": self.opportunity_id,
            "opportunity_type": self.opportunity_type.value,
            "status": self.status.value,
            "title": self.title,
            "description": self.description,
            "evidence": [e.to_dict() for e in self.evidence],
            "actionability": self.actionability.to_dict() if self.actionability else None,
            "suggested_fix": self.suggested_fix,
            "affected_files": self.affected_files,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "discovered_by": self.discovered_by,
            "priority_rank": self.priority_rank,
            "debate_session_id": self.debate_session_id,
            "linked_issue": self.linked_issue,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Opportunity":
        """Create from dictionary.

        Handles conversion of string enum values back to enums.
        """
        # Convert string to OpportunityType enum
        opp_type = data.get("opportunity_type", "test_failure")
        if isinstance(opp_type, str):
            opp_type = OpportunityType(opp_type)

        # Convert string to OpportunityStatus enum
        status = data.get("status", "discovered")
        if isinstance(status, str):
            status = OpportunityStatus(status)

        # Convert evidence dicts to Evidence objects
        evidence_data = data.get("evidence", [])
        evidence_list = [
            Evidence.from_dict(e) if isinstance(e, dict) else e
            for e in evidence_data
        ]

        # Convert actionability dict to ActionabilityScore object
        actionability_data = data.get("actionability")
        actionability = None
        if actionability_data is not None:
            actionability = ActionabilityScore.from_dict(actionability_data)

        return cls(
            opportunity_id=data.get("opportunity_id", ""),
            opportunity_type=opp_type,
            status=status,
            title=data.get("title", ""),
            description=data.get("description", ""),
            evidence=evidence_list,
            actionability=actionability,
            suggested_fix=data.get("suggested_fix"),
            affected_files=data.get("affected_files", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            discovered_by=data.get("discovered_by"),
            priority_rank=data.get("priority_rank"),
            debate_session_id=data.get("debate_session_id"),
            linked_issue=data.get("linked_issue"),
        )
