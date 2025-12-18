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
    """Manages daily goals and reconciliation with repository state."""

    def __init__(self, daily_log_manager: DailyLogManager) -> None:
        """Initialize the GoalTracker.

        Args:
            daily_log_manager: Manager for daily log persistence.
        """
        self.daily_log_manager = daily_log_manager
        self._goals: list[DailyGoal] = []

    def add_goal(self, goal: DailyGoal) -> None:
        """Add a goal to the tracker."""
        self._goals.append(goal)

    def get_goals(self) -> list[DailyGoal]:
        """Get all tracked goals."""
        return self._goals.copy()

    def update_goal_status(self, goal_id: str, status: GoalStatus) -> None:
        """Update the status of a goal."""
        for goal in self._goals:
            if goal.goal_id == goal_id:
                goal.status = status
                break

    def reconcile_with_state(self, state: RepoStateSnapshot) -> list[Recommendation]:
        """Reconcile goals with current repository state.

        Args:
            state: Current repository state snapshot.

        Returns:
            List of recommendations based on state changes.
        """
        recommendations: list[Recommendation] = []

        # Check features
        for feature in state.features:
            if feature.phase in P1_FEATURE_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P1,
                        action=f"Review and approve spec for {feature.feature_id}",
                        reason=f"Feature is in {feature.phase} phase",
                        linked_item=feature.feature_id,
                    )
                )

        # Check bugs
        for bug in state.bugs:
            if bug.phase in P1_BUG_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P1,
                        action=f"Approve fix plan for {bug.bug_id}",
                        reason=f"Bug is in {bug.phase} phase",
                        linked_item=bug.bug_id,
                    )
                )

        return recommendations