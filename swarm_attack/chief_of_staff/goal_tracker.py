"""Goal tracking and reconciliation for Chief of Staff."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from swarm_attack.chief_of_staff.daily_log import DailyLogManager, DailyLog
from swarm_attack.chief_of_staff.state_gatherer import (
    RepoStateSnapshot,
    FeatureSummary,
    BugSummary,
)


class GoalStatus(Enum):
    """Status of a daily goal."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    BLOCKED = "blocked"
    DEFERRED = "deferred"


class GoalPriority(Enum):
    """Priority level for a goal."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationPriority(Enum):
    """Priority level for recommendations."""

    P1 = "P1"  # Blockers, approvals needed
    P2 = "P2"  # In-progress work
    P3 = "P3"  # New work to start


@dataclass
class DailyGoal:
    """A daily goal with tracking information."""

    goal_id: str
    description: str
    priority: GoalPriority
    estimated_minutes: int
    status: GoalStatus = GoalStatus.PENDING
    actual_minutes: Optional[int] = None
    notes: str = ""
    linked_feature: Optional[str] = None
    linked_bug: Optional[str] = None
    linked_spec: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    estimated_cost_usd: Optional[float] = None
    is_unplanned: bool = False
    error_count: int = 0
    is_hiccup: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyGoal":
        """Create a DailyGoal from a dictionary."""
        priority_str = data.get("priority", "medium")
        priority = GoalPriority(priority_str.lower())

        status_str = data.get("status", "pending")
        status = GoalStatus(status_str.lower())

        return cls(
            goal_id=data.get("goal_id", ""),
            description=data.get("description", ""),
            priority=priority,
            estimated_minutes=data.get("estimated_minutes", 0),
            status=status,
            actual_minutes=data.get("actual_minutes"),
            notes=data.get("notes", ""),
            linked_feature=data.get("linked_feature"),
            linked_bug=data.get("linked_bug"),
            linked_spec=data.get("linked_spec"),
            tags=data.get("tags", []),
            estimated_cost_usd=data.get("estimated_cost_usd"),
            is_unplanned=data.get("is_unplanned", False),
            error_count=data.get("error_count", 0),
            is_hiccup=data.get("is_hiccup", False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "priority": self.priority.value,
            "estimated_minutes": self.estimated_minutes,
            "status": self.status.value,
            "actual_minutes": self.actual_minutes,
            "notes": self.notes,
            "linked_feature": self.linked_feature,
            "linked_bug": self.linked_bug,
            "linked_spec": self.linked_spec,
            "tags": self.tags,
            "estimated_cost_usd": self.estimated_cost_usd,
            "is_unplanned": self.is_unplanned,
            "error_count": self.error_count,
            "is_hiccup": self.is_hiccup,
        }


@dataclass
class Recommendation:
    """A prioritized recommendation for action."""

    priority: RecommendationPriority
    action: str
    reason: str
    linked_item: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Recommendation":
        """Create a Recommendation from a dictionary."""
        priority_str = data.get("priority", "P3")
        priority = RecommendationPriority(priority_str.upper())

        return cls(
            priority=priority,
            action=data.get("action", ""),
            reason=data.get("reason", ""),
            linked_item=data.get("linked_item", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "priority": self.priority.value,
            "action": self.action,
            "reason": self.reason,
            "linked_item": self.linked_item,
        }


# Feature phase to goal status mapping
FEATURE_PHASE_TO_STATUS: dict[str, GoalStatus] = {
    "COMPLETE": GoalStatus.COMPLETE,
    "IMPLEMENTING": GoalStatus.IN_PROGRESS,
    "READY_TO_IMPLEMENT": GoalStatus.PENDING,
    "SPEC_APPROVED": GoalStatus.PENDING,
    "SPEC_NEEDS_APPROVAL": GoalStatus.BLOCKED,
    "SPEC_IN_PROGRESS": GoalStatus.IN_PROGRESS,
    "PRD_READY": GoalStatus.PENDING,
    "NO_PRD": GoalStatus.PENDING,
}

# Bug phase to goal status mapping
BUG_PHASE_TO_STATUS: dict[str, GoalStatus] = {
    "FIXED": GoalStatus.COMPLETE,
    "FIXING": GoalStatus.IN_PROGRESS,
    "APPROVED": GoalStatus.PENDING,
    "PLANNED": GoalStatus.BLOCKED,  # Needs approval
    "ANALYZING": GoalStatus.IN_PROGRESS,
    "REPRODUCING": GoalStatus.IN_PROGRESS,
    "CREATED": GoalStatus.PENDING,
}

# Phases that require P1 priority (blockers/approvals)
P1_FEATURE_PHASES = {"SPEC_NEEDS_APPROVAL"}
P1_BUG_PHASES = {"PLANNED"}

# Phases that map to P2 priority (in-progress work)
P2_FEATURE_PHASES = {"IMPLEMENTING", "SPEC_IN_PROGRESS"}
P2_BUG_PHASES = {"FIXING", "ANALYZING", "REPRODUCING"}

# Phases that map to P3 priority (new work)
P3_FEATURE_PHASES = {"READY_TO_IMPLEMENT", "SPEC_APPROVED"}
P3_BUG_PHASES = {"APPROVED", "CREATED"}


class GoalTracker:
    """Manages daily goals and reconciliation with repo state."""

    def __init__(self, log_manager: DailyLogManager) -> None:
        """Initialize GoalTracker.

        Args:
            log_manager: Manager for daily logs.
        """
        self.log_manager = log_manager
        self._goals: list[DailyGoal] = []

    def add_goal(self, goal: DailyGoal) -> None:
        """Add a goal to track."""
        self._goals.append(goal)

    def get_goals(self) -> list[DailyGoal]:
        """Get all tracked goals."""
        return self._goals.copy()

    def reconcile_with_state(self, snapshot: RepoStateSnapshot) -> list[Recommendation]:
        """Reconcile goals with current repo state.

        Args:
            snapshot: Current state of the repository.

        Returns:
            List of prioritized recommendations.
        """
        recommendations: list[Recommendation] = []

        # Check features
        for feature in snapshot.features:
            phase = feature.phase
            if phase in P1_FEATURE_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P1,
                        action=f"Approve spec for {feature.name}",
                        reason="Spec needs approval before implementation",
                        linked_item=feature.name,
                    )
                )
            elif phase in P2_FEATURE_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P2,
                        action=f"Continue {feature.name}",
                        reason=f"Feature is in {phase}",
                        linked_item=feature.name,
                    )
                )
            elif phase in P3_FEATURE_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P3,
                        action=f"Start {feature.name}",
                        reason=f"Feature is ready ({phase})",
                        linked_item=feature.name,
                    )
                )

        # Check bugs
        for bug in snapshot.bugs:
            phase = bug.phase
            if phase in P1_BUG_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P1,
                        action=f"Approve fix for {bug.bug_id}",
                        reason="Fix plan needs approval",
                        linked_item=bug.bug_id,
                    )
                )
            elif phase in P2_BUG_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P2,
                        action=f"Continue {bug.bug_id}",
                        reason=f"Bug is in {phase}",
                        linked_item=bug.bug_id,
                    )
                )
            elif phase in P3_BUG_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P3,
                        action=f"Start {bug.bug_id}",
                        reason=f"Bug is ready ({phase})",
                        linked_item=bug.bug_id,
                    )
                )

        # Sort by priority
        priority_order = {
            RecommendationPriority.P1: 0,
            RecommendationPriority.P2: 1,
            RecommendationPriority.P3: 2,
        }
        recommendations.sort(key=lambda r: priority_order[r.priority])

        return recommendations