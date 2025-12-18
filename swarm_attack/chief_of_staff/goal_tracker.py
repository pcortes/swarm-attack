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
        """Initialize the GoalTracker with a DailyLogManager.

        Args:
            daily_log_manager: The manager for daily logs.
        """
        self.daily_log_manager = daily_log_manager

    def get_today_goals(self) -> list[DailyGoal]:
        """Get the current goals for today.

        Returns:
            List of today's goals.
        """
        log = self.daily_log_manager.get_today()
        return log.goals if log else []

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set the goals for today.

        Args:
            goals: List of goals to set.
        """
        log = self.daily_log_manager.get_today()
        log.goals = goals
        self.daily_log_manager.save_log(log)

    def update_goal(
        self,
        goal_id: str,
        status: Optional[GoalStatus] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Update a goal's status and/or notes.

        Args:
            goal_id: The ID of the goal to update.
            status: New status (optional).
            notes: New notes (optional).

        Raises:
            ValueError: If the goal is not found.
        """
        log = self.daily_log_manager.get_today()
        goal = self._find_goal(log.goals, goal_id)

        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        if status is not None:
            goal.status = status
        if notes is not None:
            goal.notes = notes

        self.daily_log_manager.save_log(log)

    def mark_complete(self, goal_id: str, actual_minutes: int) -> None:
        """Mark a goal as complete with actual time spent.

        Args:
            goal_id: The ID of the goal to complete.
            actual_minutes: Actual minutes spent on the goal.

        Raises:
            ValueError: If the goal is not found.
        """
        log = self.daily_log_manager.get_today()
        goal = self._find_goal(log.goals, goal_id)

        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        goal.status = GoalStatus.COMPLETE
        goal.actual_minutes = actual_minutes
        self.daily_log_manager.save_log(log)

    def get_yesterday_goals(self) -> list[DailyGoal]:
        """Get yesterday's goals.

        Returns:
            List of yesterday's goals, or empty list if no log exists.
        """
        log = self.daily_log_manager.get_yesterday()
        if log is None:
            return []
        return log.goals if log.goals else []

    def compare_plan_vs_actual(self) -> dict[str, Any]:
        """Compare yesterday's planned goals versus actual results.

        Returns:
            Dictionary with comparison metrics.
        """
        log = self.daily_log_manager.get_yesterday()
        if log is None or not log.goals:
            return {
                "total_planned": 0,
                "total_completed": 0,
                "completion_rate": 0.0,
                "estimated_minutes": 0,
                "actual_minutes": 0,
                "time_variance": 0,
                "incomplete_goals": [],
            }

        goals = log.goals
        total_planned = len(goals)
        completed = [g for g in goals if g.status == GoalStatus.COMPLETE]
        total_completed = len(completed)

        completion_rate = total_completed / total_planned if total_planned > 0 else 0.0

        estimated_minutes = sum(g.estimated_minutes for g in goals)
        actual_minutes = sum(g.actual_minutes or 0 for g in completed)

        incomplete_goal_ids = [
            g.goal_id for g in goals if g.status != GoalStatus.COMPLETE
        ]

        return {
            "total_planned": total_planned,
            "total_completed": total_completed,
            "completion_rate": completion_rate,
            "estimated_minutes": estimated_minutes,
            "actual_minutes": actual_minutes,
            "time_variance": actual_minutes - estimated_minutes,
            "incomplete_goals": incomplete_goal_ids,
        }

    def get_carryover_goals(self) -> list[DailyGoal]:
        """Get incomplete goals from yesterday that should carry over.

        Returns:
            List of goals to carry over (pending and in_progress only).
        """
        log = self.daily_log_manager.get_yesterday()
        if log is None or not log.goals:
            return []

        # Only carry over pending and in_progress goals
        # Blocked and deferred are excluded
        carryover_statuses = {GoalStatus.PENDING, GoalStatus.IN_PROGRESS}
        return [g for g in log.goals if g.status in carryover_statuses]

    def reconcile_with_state(self, snapshot: RepoStateSnapshot) -> list[dict[str, Any]]:
        """Reconcile goals with the current repository state.

        Args:
            snapshot: Current repository state snapshot.

        Returns:
            List of changes made (goal_id, old_status, new_status).
        """
        log = self.daily_log_manager.get_today()
        if not log.goals:
            return []

        changes: list[dict[str, Any]] = []

        # Build lookup maps
        feature_map = {f.name: f for f in snapshot.features}
        bug_map = {b.bug_id: b for b in snapshot.bugs}

        for goal in log.goals:
            new_status = None

            # Check linked feature
            if goal.linked_feature and goal.linked_feature in feature_map:
                feature = feature_map[goal.linked_feature]
                new_status = FEATURE_PHASE_TO_STATUS.get(feature.phase)

            # Check linked bug
            if goal.linked_bug and goal.linked_bug in bug_map:
                bug = bug_map[goal.linked_bug]
                new_status = BUG_PHASE_TO_STATUS.get(bug.phase)

            # Update if status changed
            if new_status is not None and new_status != goal.status:
                changes.append({
                    "goal_id": goal.goal_id,
                    "old_status": goal.status,
                    "new_status": new_status,
                })
                goal.status = new_status

        if changes:
            self.daily_log_manager.save_log(log)

        return changes

    def generate_recommendations(
        self, snapshot: RepoStateSnapshot
    ) -> list[Recommendation]:
        """Generate prioritized recommendations based on repository state.

        Priority rules (from spec section 13.7):
        - P1: Blockers and approvals needed
        - P2: In-progress work to continue
        - P3: New work to start

        Args:
            snapshot: Current repository state snapshot.

        Returns:
            List of recommendations sorted by priority.
        """
        recommendations: list[Recommendation] = []

        # Process features
        for feature in snapshot.features:
            phase = feature.phase

            if phase in P1_FEATURE_PHASES:
                recommendations.append(Recommendation(
                    priority=RecommendationPriority.P1,
                    action=f"Approve spec for {feature.name}",
                    reason="Blocking implementation progress",
                    linked_item=feature.name,
                ))
            elif phase in P2_FEATURE_PHASES:
                recommendations.append(Recommendation(
                    priority=RecommendationPriority.P2,
                    action=f"Continue implementing {feature.name}",
                    reason="Work in progress",
                    linked_item=feature.name,
                ))
            elif phase in P3_FEATURE_PHASES:
                recommendations.append(Recommendation(
                    priority=RecommendationPriority.P3,
                    action=f"Start implementing {feature.name}",
                    reason="Ready for implementation",
                    linked_item=feature.name,
                ))

        # Process bugs
        for bug in snapshot.bugs:
            phase = bug.phase

            if phase in P1_BUG_PHASES:
                recommendations.append(Recommendation(
                    priority=RecommendationPriority.P1,
                    action=f"Approve fix plan for {bug.bug_id}",
                    reason="Fix plan awaiting approval",
                    linked_item=bug.bug_id,
                ))
            elif phase in P2_BUG_PHASES:
                recommendations.append(Recommendation(
                    priority=RecommendationPriority.P2,
                    action=f"Continue investigating {bug.bug_id}",
                    reason="Bug investigation in progress",
                    linked_item=bug.bug_id,
                ))
            elif phase in P3_BUG_PHASES:
                recommendations.append(Recommendation(
                    priority=RecommendationPriority.P3,
                    action=f"Start working on {bug.bug_id}",
                    reason="Bug ready for investigation",
                    linked_item=bug.bug_id,
                ))

        # Sort by priority (P1 < P2 < P3)
        priority_order = {
            RecommendationPriority.P1: 0,
            RecommendationPriority.P2: 1,
            RecommendationPriority.P3: 2,
        }
        recommendations.sort(key=lambda r: priority_order[r.priority])

        return recommendations

    def _find_goal(
        self, goals: list[DailyGoal], goal_id: str
    ) -> Optional[DailyGoal]:
        """Find a goal by ID in a list of goals.

        Args:
            goals: List of goals to search.
            goal_id: ID of the goal to find.

        Returns:
            The goal if found, None otherwise.
        """
        for goal in goals:
            if goal.goal_id == goal_id:
                return goal
        return None