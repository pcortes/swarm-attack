"""Tests for Issue #5: GoalTracker with state reconciliation."""

import pytest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import shutil

from swarm_attack.chief_of_staff.goal_tracker import GoalTracker
from swarm_attack.chief_of_staff.daily_log import DailyLogManager
from swarm_attack.chief_of_staff.models import (
    DailyGoal,
    DailyLog,
    GoalStatus,
    StandupSession,
    RepoStateSnapshot,
    GitState,
    FeatureSummary,
    BugSummary,
    PRDSummary,
    SpecSummary,
    TestState,
    Recommendation,
)


class TestGoalTrackerInit:
    """Tests for GoalTracker initialization."""

    def test_init_creates_tracker(self, tmp_path):
        """GoalTracker initializes with a DailyLogManager."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        assert tracker is not None

    def test_init_loads_today_goals_from_standup(self, tmp_path):
        """GoalTracker loads today's goals from most recent standup."""
        daily_log_manager = DailyLogManager(tmp_path)

        # Create a log with goals
        log = daily_log_manager.get_today()
        goal = DailyGoal(id="goal-1", content="Test goal", priority="P1")
        standup = StandupSession(
            session_id="s1",
            time=datetime.now().isoformat(),
            yesterday_goals=[],
            today_goals=[goal],
        )
        log.standups.append(standup)
        daily_log_manager.save_log(log)

        # Create new tracker - should load the goals
        tracker = GoalTracker(daily_log_manager)
        goals = tracker.get_today_goals()
        assert len(goals) == 1
        assert goals[0].id == "goal-1"


class TestGetTodayGoals:
    """Tests for get_today_goals method."""

    def test_returns_empty_list_when_no_goals(self, tmp_path):
        """Returns empty list when no goals are set."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        assert tracker.get_today_goals() == []

    def test_returns_copy_of_goals(self, tmp_path):
        """Returns a copy, not the original list."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        goal = DailyGoal(id="g1", content="Test", priority="P1")
        tracker.set_goals([goal])

        goals = tracker.get_today_goals()
        goals.clear()

        # Original should be unchanged
        assert len(tracker.get_today_goals()) == 1


class TestSetGoals:
    """Tests for set_goals method."""

    def test_sets_goals_and_persists(self, tmp_path):
        """Sets goals and persists to daily log."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goals = [
            DailyGoal(id="g1", content="Goal 1", priority="P1"),
            DailyGoal(id="g2", content="Goal 2", priority="P2"),
        ]
        tracker.set_goals(goals)

        # Verify persisted
        log = daily_log_manager.get_today()
        assert len(log.standups) == 1
        assert len(log.standups[0].today_goals) == 2

    def test_replaces_existing_goals(self, tmp_path):
        """Replaces existing goals when set again."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        tracker.set_goals([DailyGoal(id="g1", content="Old", priority="P1")])
        tracker.set_goals([DailyGoal(id="g2", content="New", priority="P2")])

        goals = tracker.get_today_goals()
        assert len(goals) == 1
        assert goals[0].id == "g2"


class TestUpdateGoal:
    """Tests for update_goal method."""

    def test_updates_status(self, tmp_path):
        """Updates goal status."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        tracker.set_goals([DailyGoal(id="g1", content="Test", priority="P1")])

        tracker.update_goal("g1", GoalStatus.IN_PROGRESS)

        goals = tracker.get_today_goals()
        assert goals[0].status == GoalStatus.IN_PROGRESS

    def test_updates_notes(self, tmp_path):
        """Updates goal notes."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        tracker.set_goals([DailyGoal(id="g1", content="Test", priority="P1")])

        tracker.update_goal("g1", GoalStatus.BLOCKED, notes="Blocked by X")

        goals = tracker.get_today_goals()
        assert goals[0].notes == "Blocked by X"

    def test_ignores_unknown_goal_id(self, tmp_path):
        """Silently ignores unknown goal IDs."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        tracker.set_goals([DailyGoal(id="g1", content="Test", priority="P1")])

        # Should not raise
        tracker.update_goal("unknown", GoalStatus.DONE)


class TestMarkComplete:
    """Tests for mark_complete method."""

    def test_marks_goal_done(self, tmp_path):
        """Marks goal as done."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        tracker.set_goals([DailyGoal(id="g1", content="Test", priority="P1")])

        tracker.mark_complete("g1")

        goals = tracker.get_today_goals()
        assert goals[0].status == GoalStatus.DONE
        assert goals[0].completed_at is not None

    def test_sets_actual_minutes(self, tmp_path):
        """Sets actual minutes when provided."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        tracker.set_goals([DailyGoal(id="g1", content="Test", priority="P1")])

        tracker.mark_complete("g1", actual_minutes=30)

        goals = tracker.get_today_goals()
        assert goals[0].actual_minutes == 30


class TestGetYesterdayGoals:
    """Tests for get_yesterday_goals method."""

    def test_returns_empty_when_no_yesterday(self, tmp_path):
        """Returns empty list when no yesterday log."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        assert tracker.get_yesterday_goals() == []


class TestComparePlanVsActual:
    """Tests for compare_plan_vs_actual method."""

    def test_returns_zeros_when_no_yesterday(self, tmp_path):
        """Returns zero metrics when no yesterday data."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        result = tracker.compare_plan_vs_actual()

        assert result["completion_rate"] == 0.0
        assert result["time_accuracy"] == 0.0
        assert result["goals"] == []


class TestGetCarryoverGoals:
    """Tests for get_carryover_goals method."""

    def test_returns_empty_when_no_yesterday(self, tmp_path):
        """Returns empty list when no yesterday data."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)
        assert tracker.get_carryover_goals() == []


class TestReconcileWithState:
    """Tests for reconcile_with_state method."""

    def test_marks_feature_goal_done_when_complete(self, tmp_path):
        """Marks linked feature goal as DONE when feature is COMPLETE."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goal = DailyGoal(
            id="g1",
            content="Complete feature X",
            priority="P1",
            linked_feature="feature-x",
        )
        tracker.set_goals([goal])

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            features=[
                FeatureSummary(
                    feature_id="feature-x",
                    phase="COMPLETE",
                    tasks_done=5,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=10.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["goal_id"] == "g1"
        assert changes[0]["new_status"] == "done"
        assert tracker.get_today_goals()[0].status == GoalStatus.DONE

    def test_marks_feature_goal_blocked(self, tmp_path):
        """Marks linked feature goal as BLOCKED when feature is BLOCKED."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goal = DailyGoal(
            id="g1",
            content="Work on feature X",
            priority="P1",
            linked_feature="feature-x",
        )
        tracker.set_goals([goal])

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            features=[
                FeatureSummary(
                    feature_id="feature-x",
                    phase="BLOCKED",
                    tasks_done=2,
                    tasks_total=5,
                    tasks_blocked=1,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "blocked"

    def test_marks_bug_goal_done_when_fixed(self, tmp_path):
        """Marks linked bug goal as DONE when bug is fixed."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goal = DailyGoal(
            id="g1",
            content="Fix bug Y",
            priority="P1",
            linked_bug="bug-y",
        )
        tracker.set_goals([goal])

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            bugs=[
                BugSummary(
                    bug_id="bug-y",
                    phase="fixed",
                    cost_usd=3.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "done"

    def test_marks_spec_goal_done_when_review_passed(self, tmp_path):
        """Marks linked spec goal as DONE when review passes."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goal = DailyGoal(
            id="g1",
            content="Complete spec for Z",
            priority="P1",
            linked_spec="spec-z",
        )
        tracker.set_goals([goal])

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            specs=[
                SpecSummary(
                    feature_id="spec-z",
                    title="Spec Z",
                    path="specs/z/spec.md",
                    has_review=True,
                    review_passed=True,
                ),
            ],
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "done"

    def test_marks_spec_goal_partial_when_review_failed(self, tmp_path):
        """Marks linked spec goal as PARTIAL when review fails."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goal = DailyGoal(
            id="g1",
            content="Complete spec for Z",
            priority="P1",
            linked_spec="spec-z",
        )
        tracker.set_goals([goal])

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            specs=[
                SpecSummary(
                    feature_id="spec-z",
                    title="Spec Z",
                    path="specs/z/spec.md",
                    has_review=True,
                    review_passed=False,
                ),
            ],
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "partial"

    def test_no_changes_when_no_linked_items(self, tmp_path):
        """Returns empty changes when goals have no linked items."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        goal = DailyGoal(id="g1", content="Manual task", priority="P1")
        tracker.set_goals([goal])

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert changes == []


class TestGenerateRecommendations:
    """Tests for generate_recommendations method."""

    def test_p1_for_blocked_features(self, tmp_path):
        """Generates P1 recommendation for blocked features."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            features=[
                FeatureSummary(
                    feature_id="blocked-feature",
                    phase="BLOCKED",
                    tasks_done=2,
                    tasks_total=5,
                    tasks_blocked=1,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        recommendations = tracker.generate_recommendations(snapshot)

        assert len(recommendations) >= 1
        p1_recs = [r for r in recommendations if r.priority == "P1"]
        assert any("blocked-feature" in r.task.lower() or r.linked_feature == "blocked-feature" for r in p1_recs)

    def test_p1_for_spec_approval(self, tmp_path):
        """Generates P1 recommendation for specs needing approval."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            features=[
                FeatureSummary(
                    feature_id="needs-approval",
                    phase="SPEC_NEEDS_APPROVAL",
                    tasks_done=0,
                    tasks_total=0,
                    tasks_blocked=0,
                    cost_usd=0.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p1_recs = [r for r in recommendations if r.priority == "P1"]
        assert len(p1_recs) >= 1

    def test_p1_for_failing_tests(self, tmp_path):
        """Generates P1 recommendation for failing tests."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            tests=TestState(
                total_tests=10,
                passing=8,
                failing=2,
                skipped=0,
            ),
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p1_recs = [r for r in recommendations if r.priority == "P1"]
        assert any("failing" in r.task.lower() or "test" in r.task.lower() for r in p1_recs)

    def test_p2_for_in_progress_features(self, tmp_path):
        """Generates P2 recommendation for in-progress features."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            features=[
                FeatureSummary(
                    feature_id="wip-feature",
                    phase="IMPLEMENTING",
                    tasks_done=3,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p2_recs = [r for r in recommendations if r.priority == "P2"]
        assert any(r.linked_feature == "wip-feature" for r in p2_recs)

    def test_p3_for_new_prds(self, tmp_path):
        """Generates P3 recommendation for new PRDs."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            prds=[
                PRDSummary(
                    feature_id="new-prd",
                    title="New Feature PRD",
                    phase="PRD_READY",
                    path=".claude/prds/new-prd.md",
                ),
            ],
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p3_recs = [r for r in recommendations if r.priority == "P3"]
        assert any(r.linked_feature == "new-prd" for r in p3_recs)

    def test_recommendations_sorted_by_priority(self, tmp_path):
        """Recommendations are sorted by priority (P1 first)."""
        daily_log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(daily_log_manager)

        snapshot = RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(branch="main", is_clean=True),
            features=[
                FeatureSummary(
                    feature_id="implementing",
                    phase="IMPLEMENTING",
                    tasks_done=1,
                    tasks_total=2,
                    tasks_blocked=0,
                    cost_usd=1.0,
                    updated_at=datetime.now().isoformat(),
                ),
                FeatureSummary(
                    feature_id="blocked",
                    phase="BLOCKED",
                    tasks_done=0,
                    tasks_total=2,
                    tasks_blocked=1,
                    cost_usd=0.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
            prds=[
                PRDSummary(
                    feature_id="new",
                    title="New",
                    phase="PRD_READY",
                    path=".claude/prds/new.md",
                ),
            ],
        )

        recommendations = tracker.generate_recommendations(snapshot)

        # Verify P1 comes before P2 which comes before P3
        priorities = [r.priority for r in recommendations]
        p1_idx = next((i for i, p in enumerate(priorities) if p == "P1"), len(priorities))
        p2_idx = next((i for i, p in enumerate(priorities) if p == "P2"), len(priorities))
        p3_idx = next((i for i, p in enumerate(priorities) if p == "P3"), len(priorities))

        assert p1_idx <= p2_idx <= p3_idx
