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
    linked_issue: Optional[int] = None
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
            linked_issue=data.get("linked_issue"),
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
            "linked_issue": self.linked_issue,
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

    @property
    def daily_log_manager(self) -> DailyLogManager:
        """Alias for log_manager for compatibility."""
        return self.log_manager

    def add_goal(self, goal: DailyGoal) -> None:
        """Add a goal to track."""
        self._goals.append(goal)

    def get_goals(self) -> list[DailyGoal]:
        """Get all tracked goals."""
        return self._goals.copy()

    def reconcile_with_state(
        self, snapshot: RepoStateSnapshot
    ) -> list[dict[str, Any]]:
        """Reconcile goals with current repo state.

        Updates goal statuses based on linked feature/bug phases.

        Args:
            snapshot: Current state of the repository.

        Returns:
            List of dicts with goal_id and new_status for changed goals.
        """
        changes: list[dict[str, Any]] = []
        today_log = self.log_manager.get_today()

        # Build lookup maps for features and bugs
        feature_phases = {f.feature_id: f.phase for f in snapshot.features}
        bug_phases = {b.bug_id: b.phase for b in snapshot.bugs}

        for goal_data in today_log.goals:
            goal = (
                DailyGoal.from_dict(goal_data)
                if isinstance(goal_data, dict)
                else goal_data
            )

            new_status: Optional[GoalStatus] = None

            # Check if goal is linked to a feature
            if goal.linked_feature and goal.linked_feature in feature_phases:
                phase = feature_phases[goal.linked_feature]
                if phase in FEATURE_PHASE_TO_STATUS:
                    new_status = FEATURE_PHASE_TO_STATUS[phase]

            # Check if goal is linked to a bug
            elif goal.linked_bug and goal.linked_bug in bug_phases:
                phase = bug_phases[goal.linked_bug]
                if phase in BUG_PHASE_TO_STATUS:
                    new_status = BUG_PHASE_TO_STATUS[phase]

            # If status changed, record it
            if new_status is not None and new_status != goal.status:
                changes.append({
                    "goal_id": goal.goal_id,
                    "new_status": new_status,
                    "old_status": goal.status,
                    "reason": f"Linked item phase changed",
                })
                # Update the goal
                goal.status = new_status

        return changes

    def _generate_recommendations_internal(
        self, snapshot: RepoStateSnapshot
    ) -> list[Recommendation]:
        """Generate prioritized recommendations based on repo state.

        This is the original reconcile logic that returns recommendations.

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
                        action=f"Approve spec for {feature.feature_id}",
                        reason="Spec needs approval before implementation",
                        linked_item=feature.feature_id,
                    )
                )
            elif phase in P2_FEATURE_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P2,
                        action=f"Continue {feature.feature_id}",
                        reason=f"Feature is in {phase}",
                        linked_item=feature.feature_id,
                    )
                )
            elif phase in P3_FEATURE_PHASES:
                recommendations.append(
                    Recommendation(
                        priority=RecommendationPriority.P3,
                        action=f"Start {feature.feature_id}",
                        reason=f"Feature is ready ({phase})",
                        linked_item=feature.feature_id,
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

    def get_today_goals(self) -> list[DailyGoal]:
        """Get today's goals from the daily log.

        Returns:
            List of today's goals.
        """
        today_log = self.log_manager.get_today()
        # Always convert to goal_tracker.DailyGoal with proper enums
        # daily_log.DailyGoal uses strings, we need GoalStatus enums
        result = []
        for g in today_log.goals:
            if isinstance(g, dict):
                result.append(DailyGoal.from_dict(g))
            elif hasattr(g, 'to_dict'):
                # It's a daily_log.DailyGoal, convert via dict
                result.append(DailyGoal.from_dict(g.to_dict()))
            else:
                result.append(g)
        return result

    def get_yesterday_goals(self) -> list[DailyGoal]:
        """Get yesterday's goals for comparison.

        Returns:
            List of yesterday's goals, empty list if no log exists.
        """
        yesterday_log = self.log_manager.get_yesterday()
        if yesterday_log is None:
            return []
        # Always convert to goal_tracker.DailyGoal with proper enums
        result = []
        for g in yesterday_log.goals:
            if isinstance(g, dict):
                result.append(DailyGoal.from_dict(g))
            elif hasattr(g, 'to_dict'):
                result.append(DailyGoal.from_dict(g.to_dict()))
            else:
                result.append(g)
        return result

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set today's goals in the daily log.

        Args:
            goals: List of goals to set for today.
        """
        today_log = self.log_manager.get_today()
        # Store the DailyGoal objects directly (not as dicts)
        today_log.goals = goals
        self.log_manager.save_log(today_log)

    def update_goal(
        self,
        goal_id: str,
        status: Optional[GoalStatus] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Update a goal's status and/or notes.

        Args:
            goal_id: ID of the goal to update.
            status: New status (if provided).
            notes: New notes (if provided).

        Raises:
            ValueError: If goal not found.
        """
        today_log = self.log_manager.get_today()

        for i, goal_data in enumerate(today_log.goals):
            goal = DailyGoal.from_dict(goal_data) if isinstance(goal_data, dict) else goal_data
            if goal.goal_id == goal_id:
                if status is not None:
                    goal.status = status
                if notes is not None:
                    goal.notes = notes
                today_log.goals[i] = goal.to_dict() if isinstance(goal_data, dict) else goal
                self.log_manager.save_log(today_log)
                return

        raise ValueError(f"Goal not found: {goal_id}")

    def mark_complete(self, goal_id: str, actual_minutes: Optional[int] = None) -> None:
        """Mark a goal as complete.

        Args:
            goal_id: ID of the goal to mark complete.
            actual_minutes: Actual time spent (optional).

        Raises:
            ValueError: If goal not found.
        """
        today_log = self.log_manager.get_today()

        for i, goal_data in enumerate(today_log.goals):
            goal = DailyGoal.from_dict(goal_data) if isinstance(goal_data, dict) else goal_data
            if goal.goal_id == goal_id:
                goal.status = GoalStatus.COMPLETE
                if actual_minutes is not None:
                    goal.actual_minutes = actual_minutes
                today_log.goals[i] = goal.to_dict() if isinstance(goal_data, dict) else goal
                self.log_manager.save_log(today_log)
                return

        raise ValueError(f"Goal not found: {goal_id}")

    def compare_plan_vs_actual(self) -> dict[str, Any]:
        """Compare yesterday's plan vs actual results.

        Returns:
            Dictionary with:
            - total_planned: Total number of goals planned
            - total_completed: Number of goals completed
            - completion_rate: Float (0-1) completion rate
            - estimated_minutes: Total estimated time
            - actual_minutes: Total actual time spent
            - time_variance: Difference (actual - estimated)
            - incomplete_goals: List of incomplete goal IDs
        """
        yesterday_goals = self.get_yesterday_goals()

        if not yesterday_goals:
            return {
                "total_planned": 0,
                "total_completed": 0,
                "completion_rate": 0.0,
                "estimated_minutes": 0,
                "actual_minutes": 0,
                "time_variance": 0,
                "incomplete_goals": [],
            }

        total_planned = len(yesterday_goals)
        completed_goals = [g for g in yesterday_goals if g.status == GoalStatus.COMPLETE]
        total_completed = len(completed_goals)

        completion_rate = total_completed / total_planned if total_planned > 0 else 0.0

        estimated_minutes = sum(g.estimated_minutes for g in yesterday_goals)
        actual_minutes = sum(g.actual_minutes or 0 for g in completed_goals)
        time_variance = actual_minutes - estimated_minutes

        incomplete_goal_ids = [
            g.goal_id for g in yesterday_goals if g.status != GoalStatus.COMPLETE
        ]

        return {
            "total_planned": total_planned,
            "total_completed": total_completed,
            "completion_rate": completion_rate,
            "estimated_minutes": estimated_minutes,
            "actual_minutes": actual_minutes,
            "time_variance": time_variance,
            "incomplete_goals": incomplete_goal_ids,
        }

    def get_carryover_goals(self) -> list[DailyGoal]:
        """Get incomplete goals that should carry over from yesterday.

        Returns:
            List of goals with status PENDING or IN_PROGRESS.
        """
        yesterday_goals = self.get_yesterday_goals()

        carryover_statuses = {GoalStatus.PENDING, GoalStatus.IN_PROGRESS}
        return [g for g in yesterday_goals if g.status in carryover_statuses]

    def generate_recommendations(self, snapshot: RepoStateSnapshot) -> list[Recommendation]:
        """Generate prioritized recommendations based on repo state.

        Args:
            snapshot: Current repository state.

        Returns:
            List of prioritized recommendations.
        """
        return self._generate_recommendations_internal(snapshot)