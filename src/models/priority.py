"""Priority board data models.

This module contains all the core data models for the priority board system
including panel types, proposals, submissions, and results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PanelType(Enum):
    """Types of expert panels that can participate in prioritization."""

    PRODUCT = "product"
    CEO = "ceo"
    ENGINEERING = "engineering"
    DESIGN = "design"
    OPERATIONS = "operations"


@dataclass
class PanelWeight:
    """Weight assigned to a panel's input in consensus calculation."""

    panel: PanelType
    weight: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "panel": self.panel.value,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PanelWeight":
        """Deserialize from dictionary."""
        return cls(
            panel=PanelType(data["panel"]),
            weight=data["weight"],
        )


@dataclass
class PriorityProposal:
    """A proposed priority item with scoring and metadata."""

    name: str
    why: str
    effort: str = "M"
    scores: list[float] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "why": self.why,
            "effort": self.effort,
            "scores": self.scores,
            "dependencies": self.dependencies,
            "risks": self.risks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriorityProposal":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            why=data["why"],
            effort=data.get("effort", "M"),
            scores=data.get("scores", []),
            dependencies=data.get("dependencies", []),
            risks=data.get("risks", []),
        )


@dataclass
class PanelSubmission:
    """A panel's submission of priorities and research."""

    panel: PanelType
    expert_name: str
    priorities: list[PriorityProposal] = field(default_factory=list)
    research: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "panel": self.panel.value,
            "expert_name": self.expert_name,
            "priorities": [p.to_dict() for p in self.priorities],
            "research": self.research,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PanelSubmission":
        """Deserialize from dictionary."""
        return cls(
            panel=PanelType(data["panel"]),
            expert_name=data["expert_name"],
            priorities=[PriorityProposal.from_dict(p) for p in data.get("priorities", [])],
            research=data.get("research", []),
        )


@dataclass
class PriorityDisposition:
    """Disposition of a priority item after review."""

    priority_name: str
    classification: str  # ACCEPT, REJECT, DEFER, PARTIAL
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "priority_name": self.priority_name,
            "classification": self.classification,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriorityDisposition":
        """Deserialize from dictionary."""
        return cls(
            priority_name=data["priority_name"],
            classification=data["classification"],
            reason=data["reason"],
        )


@dataclass
class ConsensusResult:
    """Result of consensus building between panels."""

    reached: bool
    overlap_count: int
    common_priorities: list[str] = field(default_factory=list)
    forced: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "reached": self.reached,
            "common_priorities": self.common_priorities,
            "overlap_count": self.overlap_count,
            "forced": self.forced,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConsensusResult":
        """Deserialize from dictionary."""
        return cls(
            reached=data["reached"],
            common_priorities=data.get("common_priorities", []),
            overlap_count=data["overlap_count"],
            forced=data.get("forced", False),
        )


@dataclass
class ExternalReviewResult:
    """Result of external review (e.g., CEO review)."""

    outcome: str  # APPROVED, CHALLENGED, REJECTED, PENDING
    feedback: str = ""
    challenged_priorities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "outcome": self.outcome,
            "feedback": self.feedback,
            "challenged_priorities": self.challenged_priorities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExternalReviewResult":
        """Deserialize from dictionary."""
        return cls(
            outcome=data["outcome"],
            feedback=data.get("feedback", ""),
            challenged_priorities=data.get("challenged_priorities", []),
        )


@dataclass
class PrioritizationResult:
    """Final result of a prioritization session."""

    success: bool
    project: str
    priorities: list[PriorityProposal] = field(default_factory=list)
    rounds: int = 0
    cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "project": self.project,
            "priorities": [p.to_dict() for p in self.priorities],
            "rounds": self.rounds,
            "cost": self.cost,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PrioritizationResult":
        """Deserialize from dictionary."""
        return cls(
            success=data["success"],
            project=data["project"],
            priorities=[PriorityProposal.from_dict(p) for p in data.get("priorities", [])],
            rounds=data.get("rounds", 0),
            cost=data.get("cost", 0.0),
        )