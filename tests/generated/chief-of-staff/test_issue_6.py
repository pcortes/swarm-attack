"""Tests for GoalTracker - goal management and reconciliation."""

import pytest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Any

from swarm_attack.chief_of_staff.goal_tracker import (
    GoalTracker,
    DailyGoal,
    GoalStatus,
    GoalPriority,
    Recommendation,
    RecommendationPriority,
)
from swarm_attack.chief_of_staff.daily_log import DailyLogManager, DailyLog
from swarm_attack.chief_of_staff.state_gatherer import (
    RepoStateSnapshot,
    FeatureSummary,
    BugSummary,
    GitState,
    TestState,
    GitHubState,
)


class TestDailyGoalModel:
    """Tests for the DailyGoal dataclass."""

    def test_daily_goal_has_required_fields(self):
        goal = DailyGoal(
            goal_id="goal-1",
            description="Implement feature X",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
        )
        assert goal.goal_id == "goal-1"
        assert goal.description == "Implement feature X"
        assert goal.priority == GoalPriority.HIGH
        assert goal.estimated_minutes == 60

    def test_daily_goal_defaults(self):
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
        )
        assert goal.status == GoalStatus.PENDING
        assert goal.actual_minutes is None
        assert goal.notes == ""
        assert goal.linked_feature is None
        assert goal.linked_bug is None
        assert goal.linked_spec is None

    def test_daily_goal_from_dict(self):
        data = {
            "goal_id": "goal-2",
            "description": "Fix bug Y",
            "priority": "high",
            "estimated_minutes": 45,
            "status": "in_progress",
            "actual_minutes": 20,
            "notes": "Working on it",
            "linked_bug": "bug-123",
        }
        goal = DailyGoal.from_dict(data)
        assert goal.goal_id == "goal-2"
        assert goal.description == "Fix bug Y"
        assert goal.priority == GoalPriority.HIGH
        assert goal.status == GoalStatus.IN_PROGRESS
        assert goal.actual_minutes == 20
        assert goal.notes == "Working on it"
        assert goal.linked_bug == "bug-123"

    def test_daily_goal_to_dict(self):
        goal = DailyGoal(
            goal_id="goal-3",
            description="Review spec",
            priority=GoalPriority.LOW,
            estimated_minutes=15,
            status=GoalStatus.COMPLETE,
            actual_minutes=10,
            linked_spec="spec-abc",
        )
        data = goal.to_dict()
        assert data["goal_id"] == "goal-3"
        assert data["description"] == "Review spec"
        assert data["priority"] == "low"
        assert data["status"] == "complete"
        assert data["actual_minutes"] == 10
        assert data["linked_spec"] == "spec-abc"

    def test_daily_goal_roundtrip(self):
        original = DailyGoal(
            goal_id="goal-4",
            description="Test roundtrip",
            priority=GoalPriority.HIGH,
            estimated_minutes=90,
            status=GoalStatus.BLOCKED,
            notes="Waiting on dependency",
            linked_feature="feature-xyz",
        )
        roundtrip = DailyGoal.from_dict(original.to_dict())
        assert roundtrip.goal_id == original.goal_id
        assert roundtrip.description == original.description
        assert roundtrip.priority == original.priority
        assert roundtrip.status == original.status
        assert roundtrip.notes == original.notes
        assert roundtrip.linked_feature == original.linked_feature


class TestGoalStatusEnum:
    """Tests for GoalStatus enum."""

    def test_goal_status_values(self):
        assert GoalStatus.PENDING.value == "pending"
        assert GoalStatus.IN_PROGRESS.value == "in_progress"
        assert GoalStatus.COMPLETE.value == "complete"
        assert GoalStatus.BLOCKED.value == "blocked"
        assert GoalStatus.DEFERRED.value == "deferred"


class TestGoalPriorityEnum:
    """Tests for GoalPriority enum."""

    def test_goal_priority_values(self):
        assert GoalPriority.HIGH.value == "high"
        assert GoalPriority.MEDIUM.value == "medium"
        assert GoalPriority.LOW.value == "low"


class TestRecommendationModel:
    """Tests for the Recommendation dataclass."""

    def test_recommendation_has_required_fields(self):
        rec = Recommendation(
            priority=RecommendationPriority.P1,
            action="Approve spec for feature X",
            reason="Blocking implementation",
            linked_item="feature-x",
        )
        assert rec.priority == RecommendationPriority.P1
        assert rec.action == "Approve spec for feature X"
        assert rec.reason == "Blocking implementation"
        assert rec.linked_item == "feature-x"

    def test_recommendation_from_dict(self):
        data = {
            "priority": "P2",
            "action": "Continue implementing",
            "reason": "In progress work",
            "linked_item": "feature-y",
        }
        rec = Recommendation.from_dict(data)
        assert rec.priority == RecommendationPriority.P2
        assert rec.action == "Continue implementing"

    def test_recommendation_to_dict(self):
        rec = Recommendation(
            priority=RecommendationPriority.P3,
            action="Start new feature",
            reason="Available capacity",
            linked_item="feature-z",
        )
        data = rec.to_dict()
        assert data["priority"] == "P3"
        assert data["action"] == "Start new feature"


class TestRecommendationPriorityEnum:
    """Tests for RecommendationPriority enum."""

    def test_recommendation_priority_values(self):
        assert RecommendationPriority.P1.value == "P1"
        assert RecommendationPriority.P2.value == "P2"
        assert RecommendationPriority.P3.value == "P3"


class TestGoalTrackerInit:
    """Tests for GoalTracker initialization."""

    def test_init_with_daily_log_manager(self):
        mock_manager = Mock(spec=DailyLogManager)
        tracker = GoalTracker(mock_manager)
        assert tracker.daily_log_manager is mock_manager

    def test_init_stores_manager_reference(self):
        mock_manager = Mock(spec=DailyLogManager)
        tracker = GoalTracker(mock_manager)
        assert tracker.daily_log_manager == mock_manager


class TestGetTodayGoals:
    """Tests for get_today_goals method."""

    def test_get_today_goals_empty(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        goals = tracker.get_today_goals()
        
        assert goals == []
        mock_manager.get_today.assert_called_once()

    def test_get_today_goals_returns_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal1 = DailyGoal(
            goal_id="goal-1",
            description="Goal 1",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )
        goal2 = DailyGoal(
            goal_id="goal-2",
            description="Goal 2",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=60,
        )
        mock_log.goals = [goal1, goal2]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        goals = tracker.get_today_goals()
        
        assert len(goals) == 2
        assert goals[0].goal_id == "goal-1"
        assert goals[1].goal_id == "goal-2"


class TestSetGoals:
    """Tests for set_goals method."""

    def test_set_goals_saves_to_log(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        goals = [
            DailyGoal(
                goal_id="goal-1",
                description="New goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=45,
            )
        ]
        tracker.set_goals(goals)
        
        assert mock_log.goals == goals
        mock_manager.save_log.assert_called_once_with(mock_log)

    def test_set_goals_replaces_existing(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        old_goal = DailyGoal(
            goal_id="old-goal",
            description="Old",
            priority=GoalPriority.LOW,
            estimated_minutes=10,
        )
        mock_log.goals = [old_goal]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        new_goals = [
            DailyGoal(
                goal_id="new-goal",
                description="New",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
            )
        ]
        tracker.set_goals(new_goals)
        
        assert mock_log.goals == new_goals
        assert old_goal not in mock_log.goals


class TestUpdateGoal:
    """Tests for update_goal method."""

    def test_update_goal_status(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            status=GoalStatus.PENDING,
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        tracker.update_goal("goal-1", status=GoalStatus.IN_PROGRESS)
        
        assert goal.status == GoalStatus.IN_PROGRESS
        mock_manager.save_log.assert_called()

    def test_update_goal_notes(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        tracker.update_goal("goal-1", notes="Updated notes")
        
        assert goal.notes == "Updated notes"

    def test_update_goal_status_and_notes(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        tracker.update_goal("goal-1", status=GoalStatus.BLOCKED, notes="Waiting on review")
        
        assert goal.status == GoalStatus.BLOCKED
        assert goal.notes == "Waiting on review"

    def test_update_goal_not_found_raises(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        
        with pytest.raises(ValueError, match="Goal not found"):
            tracker.update_goal("nonexistent", status=GoalStatus.COMPLETE)


class TestMarkComplete:
    """Tests for mark_complete method."""

    def test_mark_complete_sets_status_and_time(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="goal-1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            status=GoalStatus.IN_PROGRESS,
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        tracker.mark_complete("goal-1", actual_minutes=25)
        
        assert goal.status == GoalStatus.COMPLETE
        assert goal.actual_minutes == 25
        mock_manager.save_log.assert_called()

    def test_mark_complete_not_found_raises(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        
        with pytest.raises(ValueError, match="Goal not found"):
            tracker.mark_complete("nonexistent", actual_minutes=30)


class TestGetYesterdayGoals:
    """Tests for get_yesterday_goals method."""

    def test_get_yesterday_goals_empty(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        goals = tracker.get_yesterday_goals()
        
        assert goals == []
        mock_manager.get_yesterday.assert_called_once()

    def test_get_yesterday_goals_returns_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="yesterday-goal",
            description="Yesterday's goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            status=GoalStatus.COMPLETE,
            actual_minutes=55,
        )
        mock_log.goals = [goal]
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        goals = tracker.get_yesterday_goals()
        
        assert len(goals) == 1
        assert goals[0].goal_id == "yesterday-goal"

    def test_get_yesterday_goals_none_log(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_manager.get_yesterday.return_value = None
        
        tracker = GoalTracker(mock_manager)
        goals = tracker.get_yesterday_goals()
        
        assert goals == []


class TestComparePlanVsActual:
    """Tests for compare_plan_vs_actual method."""

    def test_compare_empty_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        result = tracker.compare_plan_vs_actual()
        
        assert result["total_planned"] == 0
        assert result["total_completed"] == 0
        assert result["completion_rate"] == 0.0

    def test_compare_all_completed(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                status=GoalStatus.COMPLETE,
                actual_minutes=25,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=60,
                status=GoalStatus.COMPLETE,
                actual_minutes=70,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        result = tracker.compare_plan_vs_actual()
        
        assert result["total_planned"] == 2
        assert result["total_completed"] == 2
        assert result["completion_rate"] == 1.0
        assert result["estimated_minutes"] == 90
        assert result["actual_minutes"] == 95

    def test_compare_partial_completion(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                status=GoalStatus.COMPLETE,
                actual_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Goal 2",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=60,
                status=GoalStatus.PENDING,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        result = tracker.compare_plan_vs_actual()
        
        assert result["total_planned"] == 2
        assert result["total_completed"] == 1
        assert result["completion_rate"] == 0.5
        assert result["incomplete_goals"] == ["g2"]

    def test_compare_includes_time_variance(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                status=GoalStatus.COMPLETE,
                actual_minutes=90,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        result = tracker.compare_plan_vs_actual()
        
        assert result["time_variance"] == 30  # 90 - 60


class TestGetCarryoverGoals:
    """Tests for get_carryover_goals method."""

    def test_carryover_empty_when_all_complete(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Goal 1",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                status=GoalStatus.COMPLETE,
                actual_minutes=30,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        carryover = tracker.get_carryover_goals()
        
        assert carryover == []

    def test_carryover_pending_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Complete goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=30,
                status=GoalStatus.COMPLETE,
                actual_minutes=30,
            ),
            DailyGoal(
                goal_id="g2",
                description="Pending goal",
                priority=GoalPriority.MEDIUM,
                estimated_minutes=60,
                status=GoalStatus.PENDING,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        carryover = tracker.get_carryover_goals()
        
        assert len(carryover) == 1
        assert carryover[0].goal_id == "g2"

    def test_carryover_in_progress_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="In progress goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                status=GoalStatus.IN_PROGRESS,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        carryover = tracker.get_carryover_goals()
        
        assert len(carryover) == 1
        assert carryover[0].goal_id == "g1"

    def test_carryover_excludes_deferred(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Deferred goal",
                priority=GoalPriority.LOW,
                estimated_minutes=30,
                status=GoalStatus.DEFERRED,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        carryover = tracker.get_carryover_goals()
        
        assert carryover == []

    def test_carryover_excludes_blocked(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goals = [
            DailyGoal(
                goal_id="g1",
                description="Blocked goal",
                priority=GoalPriority.HIGH,
                estimated_minutes=60,
                status=GoalStatus.BLOCKED,
            ),
        ]
        mock_log.goals = goals
        mock_manager.get_yesterday.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        carryover = tracker.get_carryover_goals()
        
        # Blocked goals might or might not carry over depending on implementation
        # For now, assume blocked goals do NOT carry over automatically
        assert carryover == []


class TestReconcileWithState:
    """Tests for reconcile_with_state method."""

    def test_reconcile_empty_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        mock_log.goals = []
        mock_manager.get_today.return_value = mock_log
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = []
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert changes == []

    def test_reconcile_feature_complete_updates_goal(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="g1",
            description="Implement feature X",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            status=GoalStatus.IN_PROGRESS,
            linked_feature="feature-x",
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-x"
        feature.phase = "COMPLETE"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert len(changes) == 1
        assert changes[0]["goal_id"] == "g1"
        assert changes[0]["new_status"] == GoalStatus.COMPLETE

    def test_reconcile_feature_implementing_updates_goal(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="g1",
            description="Implement feature X",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            status=GoalStatus.PENDING,
            linked_feature="feature-x",
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-x"
        feature.phase = "IMPLEMENTING"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert len(changes) == 1
        assert changes[0]["goal_id"] == "g1"
        assert changes[0]["new_status"] == GoalStatus.IN_PROGRESS

    def test_reconcile_bug_fixed_updates_goal(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="g1",
            description="Fix bug Y",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            status=GoalStatus.IN_PROGRESS,
            linked_bug="bug-y",
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        bug = Mock(spec=BugSummary)
        bug.bug_id = "bug-y"
        bug.phase = "FIXED"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = []
        snapshot.bugs = [bug]
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert len(changes) == 1
        assert changes[0]["goal_id"] == "g1"
        assert changes[0]["new_status"] == GoalStatus.COMPLETE

    def test_reconcile_multiple_goals(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal1 = DailyGoal(
            goal_id="g1",
            description="Feature X",
            priority=GoalPriority.HIGH,
            estimated_minutes=60,
            status=GoalStatus.PENDING,
            linked_feature="feature-x",
        )
        goal2 = DailyGoal(
            goal_id="g2",
            description="Bug Y",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            status=GoalStatus.PENDING,
            linked_bug="bug-y",
        )
        mock_log.goals = [goal1, goal2]
        mock_manager.get_today.return_value = mock_log
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-x"
        feature.phase = "COMPLETE"
        
        bug = Mock(spec=BugSummary)
        bug.bug_id = "bug-y"
        bug.phase = "ANALYZING"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = [bug]
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert len(changes) == 2

    def test_reconcile_spec_approval_maps_to_blocked(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="g1",
            description="Implement feature needing approval",
            priority=GoalPriority.HIGH,
            estimated_minutes=120,
            status=GoalStatus.PENDING,
            linked_feature="feature-needs-approval",
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-needs-approval"
        feature.phase = "SPEC_NEEDS_APPROVAL"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert len(changes) == 1
        assert changes[0]["new_status"] == GoalStatus.BLOCKED


class TestGenerateRecommendations:
    """Tests for generate_recommendations method."""

    def test_recommendations_empty_state(self):
        mock_manager = Mock(spec=DailyLogManager)
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = []
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        recs = tracker.generate_recommendations(snapshot)
        
        assert recs == []

    def test_recommendations_p1_for_blockers(self):
        mock_manager = Mock(spec=DailyLogManager)
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-blocked"
        feature.phase = "SPEC_NEEDS_APPROVAL"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        recs = tracker.generate_recommendations(snapshot)
        
        assert len(recs) >= 1
        p1_recs = [r for r in recs if r.priority == RecommendationPriority.P1]
        assert len(p1_recs) >= 1
        assert "feature-blocked" in p1_recs[0].linked_item

    def test_recommendations_p1_for_bug_approval(self):
        mock_manager = Mock(spec=DailyLogManager)
        
        bug = Mock(spec=BugSummary)
        bug.bug_id = "bug-needs-approval"
        bug.phase = "PLANNED"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = []
        snapshot.bugs = [bug]
        
        tracker = GoalTracker(mock_manager)
        recs = tracker.generate_recommendations(snapshot)
        
        p1_recs = [r for r in recs if r.priority == RecommendationPriority.P1]
        assert len(p1_recs) >= 1

    def test_recommendations_p2_for_in_progress(self):
        mock_manager = Mock(spec=DailyLogManager)
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-implementing"
        feature.phase = "IMPLEMENTING"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        recs = tracker.generate_recommendations(snapshot)
        
        p2_recs = [r for r in recs if r.priority == RecommendationPriority.P2]
        assert len(p2_recs) >= 1

    def test_recommendations_p3_for_new_work(self):
        mock_manager = Mock(spec=DailyLogManager)
        
        feature = Mock(spec=FeatureSummary)
        feature.feature_id = "feature-ready"
        feature.phase = "READY_TO_IMPLEMENT"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        recs = tracker.generate_recommendations(snapshot)
        
        p3_recs = [r for r in recs if r.priority == RecommendationPriority.P3]
        assert len(p3_recs) >= 1

    def test_recommendations_sorted_by_priority(self):
        mock_manager = Mock(spec=DailyLogManager)
        
        feature1 = Mock(spec=FeatureSummary)
        feature1.feature_id = "feature-ready"
        feature1.phase = "READY_TO_IMPLEMENT"
        
        feature2 = Mock(spec=FeatureSummary)
        feature2.feature_id = "feature-blocked"
        feature2.phase = "SPEC_NEEDS_APPROVAL"
        
        feature3 = Mock(spec=FeatureSummary)
        feature3.feature_id = "feature-implementing"
        feature3.phase = "IMPLEMENTING"
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = [feature1, feature2, feature3]
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        recs = tracker.generate_recommendations(snapshot)
        
        # Verify P1 comes before P2 comes before P3
        priorities = [r.priority for r in recs]
        p1_indices = [i for i, p in enumerate(priorities) if p == RecommendationPriority.P1]
        p2_indices = [i for i, p in enumerate(priorities) if p == RecommendationPriority.P2]
        p3_indices = [i for i, p in enumerate(priorities) if p == RecommendationPriority.P3]
        
        if p1_indices and p2_indices:
            assert max(p1_indices) < min(p2_indices)
        if p2_indices and p3_indices:
            assert max(p2_indices) < min(p3_indices)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_get_yesterday_goals_no_log(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_manager.get_yesterday.return_value = None
        
        tracker = GoalTracker(mock_manager)
        goals = tracker.get_yesterday_goals()
        
        assert goals == []

    def test_compare_plan_vs_actual_no_yesterday_log(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_manager.get_yesterday.return_value = None
        
        tracker = GoalTracker(mock_manager)
        result = tracker.compare_plan_vs_actual()
        
        assert result["total_planned"] == 0
        assert result["completion_rate"] == 0.0

    def test_carryover_goals_no_yesterday_log(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_manager.get_yesterday.return_value = None
        
        tracker = GoalTracker(mock_manager)
        carryover = tracker.get_carryover_goals()
        
        assert carryover == []

    def test_reconcile_unlinked_goal_unchanged(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="g1",
            description="Manual task",
            priority=GoalPriority.MEDIUM,
            estimated_minutes=30,
            status=GoalStatus.PENDING,
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        snapshot = Mock(spec=RepoStateSnapshot)
        snapshot.features = []
        snapshot.bugs = []
        
        tracker = GoalTracker(mock_manager)
        changes = tracker.reconcile_with_state(snapshot)
        
        assert changes == []

    def test_update_goal_with_none_values_unchanged(self):
        mock_manager = Mock(spec=DailyLogManager)
        mock_log = Mock(spec=DailyLog)
        goal = DailyGoal(
            goal_id="g1",
            description="Test goal",
            priority=GoalPriority.HIGH,
            estimated_minutes=30,
            status=GoalStatus.PENDING,
            notes="Original notes",
        )
        mock_log.goals = [goal]
        mock_manager.get_today.return_value = mock_log
        
        tracker = GoalTracker(mock_manager)
        tracker.update_goal("g1", status=None, notes=None)
        
        # Status and notes should remain unchanged
        assert goal.status == GoalStatus.PENDING
        assert goal.notes == "Original notes"