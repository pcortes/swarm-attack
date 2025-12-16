"""GoalTracker: Manages daily goals, tracks completion, and reconciles with state."""

from datetime import date, datetime, timedelta
from typing import Any, Optional

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
    """Tracks daily goals and their completion with automatic state reconciliation."""

    def __init__(self, daily_log_manager: DailyLogManager) -> None:
        """Initialize with log manager."""
        self._daily_log_manager = daily_log_manager

    def get_today_goals(self) -> list[DailyGoal]:
        """Get current goals for today."""
        today_log = self._daily_log_manager.get_today()
        if not today_log.standups:
            return []
        # Return goals from most recent standup
        return today_log.standups[-1].today_goals

    def set_goals(self, goals: list[DailyGoal]) -> None:
        """Set goals for today."""
        today_log = self._daily_log_manager.get_today()
        
        # Create or update standup session with goals
        standup = StandupSession(
            session_id=f"cos-{date.today().isoformat()}-{len(today_log.standups) + 1:03d}",
            time=datetime.now().isoformat(),
            yesterday_goals=self.get_yesterday_goals(),
            today_goals=goals,
        )
        today_log.standups.append(standup)
        self._daily_log_manager.save_log(today_log)

    def update_goal(self, goal_id: str, status: GoalStatus, notes: str = "") -> None:
        """Update a goal's status."""
        today_log = self._daily_log_manager.get_today()
        if not today_log.standups:
            return
        
        # Find and update the goal in the most recent standup
        for goal in today_log.standups[-1].today_goals:
            if goal.id == goal_id:
                goal.status = status
                if notes:
                    goal.notes = notes
                break
        
        today_log.updated_at = datetime.now().isoformat()
        self._daily_log_manager.save_log(today_log)

    def mark_complete(self, goal_id: str, actual_minutes: Optional[int] = None) -> None:
        """Mark a goal as complete."""
        today_log = self._daily_log_manager.get_today()
        if not today_log.standups:
            return
        
        for goal in today_log.standups[-1].today_goals:
            if goal.id == goal_id:
                goal.status = GoalStatus.DONE
                goal.completed_at = datetime.now().isoformat()
                if actual_minutes is not None:
                    goal.actual_minutes = actual_minutes
                break
        
        today_log.updated_at = datetime.now().isoformat()
        self._daily_log_manager.save_log(today_log)

    def get_yesterday_goals(self) -> list[DailyGoal]:
        """Get yesterday's goals for comparison."""
        yesterday_log = self._daily_log_manager.get_yesterday()
        if not yesterday_log or not yesterday_log.standups:
            return []
        # Return goals from the last standup of yesterday
        return yesterday_log.standups[-1].today_goals

    def compare_plan_vs_actual(self) -> dict[str, Any]:
        """
        Compare yesterday's plan vs actual results.

        Returns:
            Dictionary with:
            - goals: list of {goal, planned, actual, status}
            - completion_rate: float (0-1)
            - time_accuracy: float (planned vs actual time)
        """
        yesterday_goals = self.get_yesterday_goals()
        
        if not yesterday_goals:
            return {
                "goals": [],
                "completion_rate": 0.0,
                "time_accuracy": 0.0,
            }
        
        goal_comparisons = []
        completed_count = 0
        time_ratios = []
        
        for goal in yesterday_goals:
            comparison = {
                "goal": goal.content,
                "planned": goal.estimated_minutes,
                "actual": goal.actual_minutes,
                "status": goal.status.value,
            }
            goal_comparisons.append(comparison)
            
            if goal.status == GoalStatus.DONE:
                completed_count += 1
            
            # Calculate time accuracy if both estimated and actual exist
            if goal.estimated_minutes and goal.actual_minutes:
                min_time = min(goal.estimated_minutes, goal.actual_minutes)
                max_time = max(goal.estimated_minutes, goal.actual_minutes)
                if max_time > 0:
                    time_ratios.append(min_time / max_time)
        
        completion_rate = completed_count / len(yesterday_goals) if yesterday_goals else 0.0
        time_accuracy = sum(time_ratios) / len(time_ratios) if time_ratios else 0.0
        
        return {
            "goals": goal_comparisons,
            "completion_rate": completion_rate,
            "time_accuracy": time_accuracy,
        }

    def get_carryover_goals(self) -> list[DailyGoal]:
        """Get incomplete goals that should carry over."""
        yesterday_goals = self.get_yesterday_goals()
        
        # Carryover: PENDING, PARTIAL, IN_PROGRESS, BLOCKED
        # Don't carryover: DONE, SKIPPED
        carryover_statuses = {
            GoalStatus.PENDING,
            GoalStatus.PARTIAL,
            GoalStatus.IN_PROGRESS,
            GoalStatus.BLOCKED,
        }
        
        carryover = []
        for goal in yesterday_goals:
            if goal.status in carryover_statuses:
                carryover.append(goal)
        
        return carryover

    def reconcile_with_state(self, snapshot: RepoStateSnapshot) -> list[dict[str, Any]]:
        """
        Reconcile goal statuses with actual repository state.

        For goals with linked_feature:
        - If feature phase is COMPLETE -> mark goal DONE
        - If feature phase is BLOCKED -> mark goal BLOCKED
        - If feature phase advanced -> mark goal PARTIAL or IN_PROGRESS

        For goals with linked_bug:
        - If bug phase is "fixed" -> mark goal DONE
        - If bug phase is "blocked" -> mark goal BLOCKED

        For goals with linked_spec:
        - If spec has passing review -> mark goal DONE
        - If spec has failing review -> mark goal PARTIAL

        Args:
            snapshot: Current repository state.

        Returns:
            List of changes made: [{"goal_id": str, "old_status": str, "new_status": str, "reason": str}]
        """
        changes = []
        today_goals = self.get_today_goals()

        # Build lookup maps
        feature_phases = {f.feature_id: f.phase for f in snapshot.features}
        bug_phases = {b.bug_id: b.phase for b in snapshot.bugs}
        spec_reviews = {s.feature_id: s for s in snapshot.specs}

        for goal in today_goals:
            old_status = goal.status
            new_status = old_status
            reason = ""

            # Check linked feature
            if goal.linked_feature and goal.linked_feature in feature_phases:
                phase = feature_phases[goal.linked_feature]
                if phase == "COMPLETE":
                    new_status = GoalStatus.DONE
                    reason = f"Feature {goal.linked_feature} completed"
                elif phase == "BLOCKED":
                    new_status = GoalStatus.BLOCKED
                    reason = f"Feature {goal.linked_feature} is blocked"
                elif phase in ("IMPLEMENTING", "SPEC_IN_PROGRESS"):
                    if old_status == GoalStatus.PENDING:
                        new_status = GoalStatus.IN_PROGRESS
                        reason = f"Feature {goal.linked_feature} now {phase}"

            # Check linked bug
            elif goal.linked_bug and goal.linked_bug in bug_phases:
                phase = bug_phases[goal.linked_bug]
                if phase == "fixed":
                    new_status = GoalStatus.DONE
                    reason = f"Bug {goal.linked_bug} fixed"
                elif phase == "blocked":
                    new_status = GoalStatus.BLOCKED
                    reason = f"Bug {goal.linked_bug} is blocked"

            # Check linked spec
            elif goal.linked_spec and goal.linked_spec in spec_reviews:
                spec = spec_reviews[goal.linked_spec]
                if spec.has_review and spec.review_passed:
                    new_status = GoalStatus.DONE
                    reason = f"Spec {goal.linked_spec} review passed"
                elif spec.has_review and not spec.review_passed:
                    new_status = GoalStatus.PARTIAL
                    reason = f"Spec {goal.linked_spec} needs revision"

            # Apply change if different
            if new_status != old_status:
                self.update_goal(goal.id, new_status, notes=reason)
                changes.append({
                    "goal_id": goal.id,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "reason": reason,
                })

        return changes

    def generate_recommendations(
        self,
        state: RepoStateSnapshot,
    ) -> list[Recommendation]:
        """
        Generate recommended goals based on current state.

        Priority rules:
        1. P1: Blockers, approvals needed, regressions, spec reviews
        2. P2: In-progress work, natural next steps
        3. P3: New features, cleanup, nice-to-haves
        """
        recommendations = []

        # P1: Blockers
        for feature in state.features:
            if feature.phase == "BLOCKED":
                recommendations.append(Recommendation(
                    priority="P1",
                    task=f"Unblock {feature.feature_id}",
                    estimated_cost_usd=0,
                    estimated_minutes=15,
                    rationale=f"Feature {feature.feature_id} is blocked",
                    linked_feature=feature.feature_id,
                    command=f"swarm-attack unblock {feature.feature_id}",
                ))

        # P1: Approvals needed
        for feature in state.features:
            if feature.phase == "SPEC_NEEDS_APPROVAL":
                recommendations.append(Recommendation(
                    priority="P1",
                    task=f"Approve {feature.feature_id} spec",
                    estimated_cost_usd=0,
                    estimated_minutes=5,
                    rationale="Spec ready for review",
                    linked_feature=feature.feature_id,
                    command=f"swarm-attack approve {feature.feature_id}",
                ))

        for bug in state.bugs:
            if bug.phase == "planned":
                recommendations.append(Recommendation(
                    priority="P1",
                    task=f"Review fix plan for {bug.bug_id}",
                    estimated_cost_usd=0,
                    estimated_minutes=10,
                    rationale="Fix plan awaiting approval",
                    linked_bug=bug.bug_id,
                    command=f"swarm-attack bug approve {bug.bug_id}",
                ))

        # P1: Test regressions
        if state.tests.failing > 0:
            recommendations.append(Recommendation(
                priority="P1",
                task=f"Fix {state.tests.failing} failing tests",
                estimated_cost_usd=2.0,
                estimated_minutes=30,
                rationale="Test regressions detected",
            ))

        # P1: Spec reviews needing attention
        for spec in state.specs:
            if spec.has_review and not spec.review_passed:
                avg_score = 0.0
                if spec.review_scores:
                    avg_score = sum(spec.review_scores.values()) / len(spec.review_scores)
                recommendations.append(Recommendation(
                    priority="P1",
                    task=f"Revise {spec.feature_id} spec (avg score: {avg_score:.2f})",
                    estimated_cost_usd=0.50,
                    estimated_minutes=15,
                    rationale="Spec review failed, needs revision",
                    linked_spec=spec.feature_id,
                    command=f"swarm-attack run {spec.feature_id}",
                ))

        # P2: Continue in-progress work
        for feature in state.features:
            if feature.phase in ("SPEC_IN_PROGRESS", "IMPLEMENTING"):
                recommendations.append(Recommendation(
                    priority="P2",
                    task=f"Continue {feature.feature_id}",
                    estimated_cost_usd=5.0,
                    estimated_minutes=60,
                    rationale="Work in progress",
                    linked_feature=feature.feature_id,
                    command=f"swarm-attack run {feature.feature_id}",
                ))

        # P2/P3: PRDs ready for spec
        for prd in state.prds:
            if prd.phase == "PRD_READY":
                # Check if feature exists
                feature_exists = any(f.feature_id == prd.feature_id for f in state.features)
                if not feature_exists:
                    recommendations.append(Recommendation(
                        priority="P2",
                        task=f"Initialize feature {prd.feature_id}",
                        estimated_cost_usd=0,
                        estimated_minutes=1,
                        rationale="PRD ready, feature not initialized",
                        linked_feature=prd.feature_id,
                        command=f"swarm-attack init {prd.feature_id}",
                    ))
                else:
                    recommendations.append(Recommendation(
                        priority="P2",
                        task=f"Generate spec for {prd.feature_id}",
                        estimated_cost_usd=1.0,
                        estimated_minutes=15,
                        rationale="PRD ready for spec generation",
                        linked_feature=prd.feature_id,
                        command=f"swarm-attack run {prd.feature_id}",
                    ))

        # Sort by priority
        priority_order = {"P1": 0, "P2": 1, "P3": 2}
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 99))

        return recommendations