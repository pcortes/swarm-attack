"""GoalTracker for managing daily goals with state reconciliation."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid

from swarm_attack.chief_of_staff.daily_log import DailyLogManager
from swarm_attack.chief_of_staff.models import (
    DailyGoal,
    DailyLog,
    GoalStatus,
    Recommendation,
    RepoStateSnapshot,
    StandupSession,
)


class GoalTracker:
    """Tracks daily goals with state reconciliation capabilities."""

    def __init__(self, daily_log_manager: DailyLogManager) -> None:
        """Initialize with a DailyLogManager.
        
        Args:
            daily_log_manager: Manager for daily log persistence
        """
        self._daily_log_manager = daily_log_manager
        self._goals: list[DailyGoal] = []
        
        # Load today's goals from most recent standup
        self._load_today_goals()

    def _load_today_goals(self) -> None:
        """Load today's goals from the most recent standup."""
        log = self._daily_log_manager.get_today()
        if log.standups:
            # Get goals from most recent standup
            latest_standup = log.standups[-1]
            self._goals = list(latest_standup.today_goals)

    def get_today_goals(self) -> list[DailyGoal]:
        """Get a copy of today's goals.
        
        Returns:
            Copy of the current goals list
        """
        return list(self._goals)

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set goals and persist to daily log.
        
        Args:
            goals: List of goals to set for today
        """
        self._goals = list(goals)
        
        # Create a new standup session with these goals
        standup = StandupSession(
            session_id=str(uuid.uuid4()),
            time=datetime.now().isoformat(),
            yesterday_goals=[],
            today_goals=list(goals),
        )
        
        self._daily_log_manager.add_standup(standup)

    def update_goal(
        self,
        goal_id: str,
        status: GoalStatus,
        notes: Optional[str] = None,
    ) -> None:
        """Update a goal's status and optionally notes.
        
        Args:
            goal_id: ID of the goal to update
            status: New status
            notes: Optional notes to add
        """
        for goal in self._goals:
            if goal.id == goal_id:
                goal.status = status
                if notes is not None:
                    goal.notes = notes
                self._persist_goals()
                return

    def mark_complete(
        self,
        goal_id: str,
        actual_minutes: Optional[int] = None,
    ) -> None:
        """Mark a goal as complete.
        
        Args:
            goal_id: ID of the goal to complete
            actual_minutes: Optional actual time spent
        """
        for goal in self._goals:
            if goal.id == goal_id:
                goal.status = GoalStatus.DONE
                goal.completed_at = datetime.now().isoformat()
                if actual_minutes is not None:
                    goal.actual_minutes = actual_minutes
                self._persist_goals()
                return

    def _persist_goals(self) -> None:
        """Persist current goals state to daily log."""
        log = self._daily_log_manager.get_today()
        if log.standups:
            # Update the most recent standup
            log.standups[-1].today_goals = list(self._goals)
            self._daily_log_manager.save_log(log)

    def get_yesterday_goals(self) -> list[DailyGoal]:
        """Get yesterday's goals.
        
        Returns:
            List of yesterday's goals, empty if no yesterday log
        """
        yesterday_log = self._daily_log_manager.get_yesterday()
        if yesterday_log is None or not yesterday_log.standups:
            return []
        
        # Return goals from the most recent standup
        return list(yesterday_log.standups[-1].today_goals)

    def compare_plan_vs_actual(self) -> dict[str, Any]:
        """Compare planned goals vs actual completion from yesterday.
        
        Returns:
            Dictionary with completion_rate, time_accuracy, and goals list
        """
        yesterday_goals = self.get_yesterday_goals()
        
        if not yesterday_goals:
            return {
                "completion_rate": 0.0,
                "time_accuracy": 0.0,
                "goals": [],
            }
        
        completed = sum(1 for g in yesterday_goals if g.status == GoalStatus.DONE)
        completion_rate = completed / len(yesterday_goals) if yesterday_goals else 0.0
        
        # Calculate time accuracy for goals with estimates and actuals
        time_goals = [
            g for g in yesterday_goals
            if g.estimated_minutes and g.actual_minutes
        ]
        if time_goals:
            accuracies = []
            for g in time_goals:
                if g.estimated_minutes and g.actual_minutes:
                    ratio = min(g.estimated_minutes, g.actual_minutes) / max(g.estimated_minutes, g.actual_minutes)
                    accuracies.append(ratio)
            time_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0
        else:
            time_accuracy = 0.0
        
        return {
            "completion_rate": completion_rate,
            "time_accuracy": time_accuracy,
            "goals": [g.to_dict() for g in yesterday_goals],
        }

    def get_carryover_goals(self) -> list[DailyGoal]:
        """Get incomplete goals from yesterday that should carry over.
        
        Returns:
            List of goals that weren't completed yesterday
        """
        yesterday_goals = self.get_yesterday_goals()
        
        carryover = []
        for goal in yesterday_goals:
            if goal.status not in (GoalStatus.DONE, GoalStatus.CARRIED_OVER):
                # Create a copy with carried over status
                carryover_goal = DailyGoal(
                    id=goal.id,
                    content=goal.content,
                    priority=goal.priority,
                    status=GoalStatus.CARRIED_OVER,
                    estimated_minutes=goal.estimated_minutes,
                    notes=goal.notes,
                    linked_feature=goal.linked_feature,
                    linked_bug=goal.linked_bug,
                    linked_spec=goal.linked_spec,
                )
                carryover.append(carryover_goal)
        
        return carryover

    def reconcile_with_state(self, snapshot: RepoStateSnapshot) -> list[dict[str, Any]]:
        """Reconcile goals with current repository state.
        
        Args:
            snapshot: Current state of the repository
            
        Returns:
            List of changes made to goals
        """
        changes = []
        
        # Build lookup maps
        feature_map = {f.feature_id: f for f in snapshot.features}
        bug_map = {b.bug_id: b for b in snapshot.bugs}
        spec_map = {s.feature_id: s for s in snapshot.specs}
        
        for goal in self._goals:
            old_status = goal.status
            new_status = None
            reason = None
            
            # Check linked feature
            if goal.linked_feature and goal.linked_feature in feature_map:
                feature = feature_map[goal.linked_feature]
                if feature.phase == "COMPLETE":
                    new_status = GoalStatus.DONE
                    reason = f"Feature {goal.linked_feature} is COMPLETE"
                elif feature.phase == "BLOCKED":
                    new_status = GoalStatus.BLOCKED
                    reason = f"Feature {goal.linked_feature} is BLOCKED"
            
            # Check linked bug
            if goal.linked_bug and goal.linked_bug in bug_map:
                bug = bug_map[goal.linked_bug]
                if bug.phase == "fixed":
                    new_status = GoalStatus.DONE
                    reason = f"Bug {goal.linked_bug} is fixed"
            
            # Check linked spec
            if goal.linked_spec and goal.linked_spec in spec_map:
                spec = spec_map[goal.linked_spec]
                if spec.has_review:
                    if spec.review_passed:
                        new_status = GoalStatus.DONE
                        reason = f"Spec {goal.linked_spec} review passed"
                    else:
                        new_status = GoalStatus.PARTIAL
                        reason = f"Spec {goal.linked_spec} review failed"
            
            # Apply status change if needed
            if new_status is not None and new_status != old_status:
                goal.status = new_status
                if new_status == GoalStatus.DONE:
                    goal.completed_at = datetime.now().isoformat()
                changes.append({
                    "goal_id": goal.id,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "reason": reason,
                })
        
        # Persist if changes were made
        if changes:
            self._persist_goals()
        
        return changes

    def generate_recommendations(self, snapshot: RepoStateSnapshot) -> list[Recommendation]:
        """Generate task recommendations based on repository state.
        
        Args:
            snapshot: Current state of the repository
            
        Returns:
            List of recommendations sorted by priority
        """
        recommendations = []
        
        # P1: Blocked features need attention
        for feature in snapshot.features:
            if feature.phase == "BLOCKED":
                recommendations.append(Recommendation(
                    task=f"Unblock feature {feature.feature_id}",
                    priority="P1",
                    rationale=f"Feature has {feature.tasks_blocked} blocked tasks",
                    linked_feature=feature.feature_id,
                ))
            elif feature.phase == "SPEC_NEEDS_APPROVAL":
                recommendations.append(Recommendation(
                    task=f"Approve spec for {feature.feature_id}",
                    priority="P1",
                    rationale="Spec is waiting for approval to proceed",
                    linked_feature=feature.feature_id,
                ))
        
        # P1: Failing tests
        if snapshot.tests and snapshot.tests.failing > 0:
            recommendations.append(Recommendation(
                task=f"Fix {snapshot.tests.failing} failing tests",
                priority="P1",
                rationale="Tests must pass before proceeding",
            ))
        
        # P2: In-progress features
        for feature in snapshot.features:
            if feature.phase == "IMPLEMENTING":
                progress = feature.tasks_done / feature.tasks_total if feature.tasks_total > 0 else 0
                recommendations.append(Recommendation(
                    task=f"Continue implementing {feature.feature_id} ({int(progress * 100)}% done)",
                    priority="P2",
                    rationale=f"{feature.tasks_done}/{feature.tasks_total} tasks complete",
                    linked_feature=feature.feature_id,
                ))
        
        # P3: New PRDs ready for spec generation
        for prd in snapshot.prds:
            if prd.phase == "PRD_READY":
                recommendations.append(Recommendation(
                    task=f"Generate spec for {prd.feature_id}",
                    priority="P3",
                    rationale="PRD is ready for spec generation",
                    linked_feature=prd.feature_id,
                ))
        
        # Sort by priority
        priority_order = {"P1": 0, "P2": 1, "P3": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))
        
        return recommendations