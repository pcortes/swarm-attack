"""Tests for GoalTracker with state reconciliation."""

import pytest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Any

from swarm_attack.chief_of_staff.goal_tracker import GoalTracker
from swarm_attack.chief_of_staff.models import (
    DailyGoal,
    GoalStatus,
    RepoStateSnapshot,
    GitState,
    FeatureSummary,
    BugSummary,
    PRDSummary,
    SpecSummary,
    TestState,
    Recommendation,
)
from swarm_attack.chief_of_staff.daily_log import DailyLogManager


class TestGoalTrackerBasicOperations:
    """Test basic goal operations."""

    def test_goal_tracker_init(self, tmp_path: Path) -> None:
        """Test GoalTracker initialization."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)
        assert tracker is not None
        assert tracker._daily_log_manager == log_manager

    def test_get_today_goals_empty(self, tmp_path: Path) -> None:
        """Test getting goals when none exist."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)
        goals = tracker.get_today_goals()
        assert goals == []

    def test_set_goals(self, tmp_path: Path) -> None:
        """Test setting goals for today."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Complete feature X",
                priority="P1",
                estimated_minutes=60,
            ),
            DailyGoal(
                id="goal-002",
                content="Fix bug Y",
                priority="P2",
                estimated_minutes=30,
            ),
        ]

        tracker.set_goals(goals)
        retrieved = tracker.get_today_goals()

        assert len(retrieved) == 2
        assert retrieved[0].id == "goal-001"
        assert retrieved[1].id == "goal-002"

    def test_update_goal_status(self, tmp_path: Path) -> None:
        """Test updating a goal's status."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Complete feature X",
                priority="P1",
            ),
        ]
        tracker.set_goals(goals)

        tracker.update_goal("goal-001", GoalStatus.IN_PROGRESS, notes="Started work")

        retrieved = tracker.get_today_goals()
        assert retrieved[0].status == GoalStatus.IN_PROGRESS
        assert retrieved[0].notes == "Started work"

    def test_update_goal_not_found(self, tmp_path: Path) -> None:
        """Test updating a non-existent goal."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        tracker.set_goals([])
        # Should not raise, just log warning or do nothing
        tracker.update_goal("nonexistent", GoalStatus.DONE)

    def test_mark_complete(self, tmp_path: Path) -> None:
        """Test marking a goal as complete."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Complete feature X",
                priority="P1",
                estimated_minutes=60,
            ),
        ]
        tracker.set_goals(goals)

        tracker.mark_complete("goal-001", actual_minutes=45)

        retrieved = tracker.get_today_goals()
        assert retrieved[0].status == GoalStatus.DONE
        assert retrieved[0].actual_minutes == 45
        assert retrieved[0].completed_at is not None


class TestGoalTrackerYesterdayOperations:
    """Test yesterday goal operations."""

    def test_get_yesterday_goals_none(self, tmp_path: Path) -> None:
        """Test getting yesterday's goals when none exist."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = tracker.get_yesterday_goals()
        assert goals == []

    def test_get_yesterday_goals(self, tmp_path: Path) -> None:
        """Test getting yesterday's goals."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        # Create yesterday's goals
        yesterday = date.today() - timedelta(days=1)
        yesterday_log = log_manager.get_log(yesterday)
        if yesterday_log is None:
            from swarm_attack.chief_of_staff.models import DailyLog
            yesterday_log = DailyLog(date=yesterday.isoformat())

        yesterday_goals = [
            DailyGoal(
                id="yest-001",
                content="Yesterday task",
                priority="P1",
                status=GoalStatus.DONE,
            ),
        ]
        
        # Save yesterday's log with goals
        from swarm_attack.chief_of_staff.models import StandupSession
        standup = StandupSession(
            session_id="test-session",
            time=datetime.now().isoformat(),
            yesterday_goals=[],
            today_goals=yesterday_goals,
        )
        yesterday_log.standups.append(standup)
        log_manager.save_log(yesterday_log)

        retrieved = tracker.get_yesterday_goals()
        assert len(retrieved) == 1
        assert retrieved[0].id == "yest-001"


class TestGoalTrackerComparison:
    """Test plan vs actual comparison."""

    def test_compare_plan_vs_actual_empty(self, tmp_path: Path) -> None:
        """Test comparison when no yesterday data."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        result = tracker.compare_plan_vs_actual()

        assert "goals" in result
        assert "completion_rate" in result
        assert "time_accuracy" in result
        assert result["goals"] == []
        assert result["completion_rate"] == 0.0

    def test_compare_plan_vs_actual_with_data(self, tmp_path: Path) -> None:
        """Test comparison with yesterday's data."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        # Create yesterday's goals
        yesterday = date.today() - timedelta(days=1)
        from swarm_attack.chief_of_staff.models import DailyLog, StandupSession

        yesterday_log = DailyLog(date=yesterday.isoformat())
        yesterday_goals = [
            DailyGoal(
                id="yest-001",
                content="Task 1",
                priority="P1",
                status=GoalStatus.DONE,
                estimated_minutes=60,
                actual_minutes=50,
            ),
            DailyGoal(
                id="yest-002",
                content="Task 2",
                priority="P2",
                status=GoalStatus.PARTIAL,
                estimated_minutes=30,
                actual_minutes=40,
            ),
        ]
        standup = StandupSession(
            session_id="test",
            time=datetime.now().isoformat(),
            yesterday_goals=[],
            today_goals=yesterday_goals,
        )
        yesterday_log.standups.append(standup)
        log_manager.save_log(yesterday_log)

        result = tracker.compare_plan_vs_actual()

        assert len(result["goals"]) == 2
        assert result["completion_rate"] == 0.5  # 1 of 2 done


class TestGoalTrackerCarryover:
    """Test carryover goal operations."""

    def test_get_carryover_goals_empty(self, tmp_path: Path) -> None:
        """Test getting carryover when none exist."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        carryover = tracker.get_carryover_goals()
        assert carryover == []

    def test_get_carryover_goals(self, tmp_path: Path) -> None:
        """Test getting incomplete goals for carryover."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        # Create yesterday's goals with some incomplete
        yesterday = date.today() - timedelta(days=1)
        from swarm_attack.chief_of_staff.models import DailyLog, StandupSession

        yesterday_log = DailyLog(date=yesterday.isoformat())
        yesterday_goals = [
            DailyGoal(id="yest-001", content="Done task", priority="P1", status=GoalStatus.DONE),
            DailyGoal(id="yest-002", content="Pending task", priority="P2", status=GoalStatus.PENDING),
            DailyGoal(id="yest-003", content="Partial task", priority="P1", status=GoalStatus.PARTIAL),
            DailyGoal(id="yest-004", content="Skipped task", priority="P3", status=GoalStatus.SKIPPED),
        ]
        standup = StandupSession(
            session_id="test",
            time=datetime.now().isoformat(),
            yesterday_goals=[],
            today_goals=yesterday_goals,
        )
        yesterday_log.standups.append(standup)
        log_manager.save_log(yesterday_log)

        carryover = tracker.get_carryover_goals()

        # Should include PENDING and PARTIAL, not DONE or SKIPPED
        assert len(carryover) == 2
        ids = [g.id for g in carryover]
        assert "yest-002" in ids
        assert "yest-003" in ids


class TestGoalTrackerReconciliation:
    """Test state reconciliation."""

    def _create_snapshot(
        self,
        features: list[FeatureSummary] | None = None,
        bugs: list[BugSummary] | None = None,
        specs: list[SpecSummary] | None = None,
    ) -> RepoStateSnapshot:
        """Create a test snapshot."""
        return RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(
                branch="main",
                is_clean=True,
                uncommitted_files=[],
                recent_commits=[],
                ahead_behind=(0, 0),
            ),
            features=features or [],
            bugs=bugs or [],
            prds=[],
            specs=specs or [],
            tests=TestState(
                total_tests=10,
                passing=10,
                failing=0,
                skipped=0,
                last_run_at=None,
            ),
            github=None,
            interrupted_sessions=[],
            total_cost_today=0.0,
            total_cost_week=0.0,
        )

    def test_reconcile_feature_complete(self, tmp_path: Path) -> None:
        """Test reconciliation marks goal DONE when feature COMPLETE."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Complete my-feature",
                priority="P1",
                status=GoalStatus.IN_PROGRESS,
                linked_feature="my-feature",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="my-feature",
                    phase="COMPLETE",
                    tasks_done=5,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=10.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["goal_id"] == "goal-001"
        assert changes[0]["old_status"] == "in_progress"
        assert changes[0]["new_status"] == "done"

        retrieved = tracker.get_today_goals()
        assert retrieved[0].status == GoalStatus.DONE

    def test_reconcile_feature_blocked(self, tmp_path: Path) -> None:
        """Test reconciliation marks goal BLOCKED when feature BLOCKED."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Work on blocked-feature",
                priority="P1",
                status=GoalStatus.PENDING,
                linked_feature="blocked-feature",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="blocked-feature",
                    phase="BLOCKED",
                    tasks_done=2,
                    tasks_total=5,
                    tasks_blocked=3,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "blocked"

    def test_reconcile_bug_fixed(self, tmp_path: Path) -> None:
        """Test reconciliation marks goal DONE when bug fixed."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Fix bug-123",
                priority="P1",
                status=GoalStatus.IN_PROGRESS,
                linked_bug="bug-123",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            bugs=[
                BugSummary(
                    bug_id="bug-123",
                    phase="fixed",
                    cost_usd=3.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "done"

    def test_reconcile_bug_blocked(self, tmp_path: Path) -> None:
        """Test reconciliation marks goal BLOCKED when bug blocked."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Fix blocked-bug",
                priority="P1",
                status=GoalStatus.PENDING,
                linked_bug="blocked-bug",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            bugs=[
                BugSummary(
                    bug_id="blocked-bug",
                    phase="blocked",
                    cost_usd=1.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "blocked"

    def test_reconcile_spec_review_passed(self, tmp_path: Path) -> None:
        """Test reconciliation marks goal DONE when spec review passed."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Review my-spec",
                priority="P1",
                status=GoalStatus.IN_PROGRESS,
                linked_spec="my-spec",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            specs=[
                SpecSummary(
                    feature_id="my-spec",
                    title="My Spec",
                    path="specs/my-spec/spec.md",
                    has_review=True,
                    review_passed=True,
                    review_scores={"clarity": 0.9, "coverage": 0.85},
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "done"

    def test_reconcile_spec_review_failed(self, tmp_path: Path) -> None:
        """Test reconciliation marks goal PARTIAL when spec review failed."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Review failing-spec",
                priority="P1",
                status=GoalStatus.IN_PROGRESS,
                linked_spec="failing-spec",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            specs=[
                SpecSummary(
                    feature_id="failing-spec",
                    title="Failing Spec",
                    path="specs/failing-spec/spec.md",
                    has_review=True,
                    review_passed=False,
                    review_scores={"clarity": 0.5, "coverage": 0.4},
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 1
        assert changes[0]["new_status"] == "partial"

    def test_reconcile_returns_changes_list(self, tmp_path: Path) -> None:
        """Test reconciliation returns list of changes made."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Feature 1",
                priority="P1",
                status=GoalStatus.PENDING,
                linked_feature="feat-1",
            ),
            DailyGoal(
                id="goal-002",
                content="Bug 1",
                priority="P2",
                status=GoalStatus.IN_PROGRESS,
                linked_bug="bug-1",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="feat-1",
                    phase="COMPLETE",
                    tasks_done=5,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=10.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
            bugs=[
                BugSummary(
                    bug_id="bug-1",
                    phase="fixed",
                    cost_usd=3.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 2
        for change in changes:
            assert "goal_id" in change
            assert "old_status" in change
            assert "new_status" in change
            assert "reason" in change

    def test_reconcile_no_changes_when_already_correct(self, tmp_path: Path) -> None:
        """Test reconciliation makes no changes when statuses match."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        goals = [
            DailyGoal(
                id="goal-001",
                content="Already done",
                priority="P1",
                status=GoalStatus.DONE,
                linked_feature="done-feature",
            ),
        ]
        tracker.set_goals(goals)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="done-feature",
                    phase="COMPLETE",
                    tasks_done=5,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=10.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        changes = tracker.reconcile_with_state(snapshot)

        assert len(changes) == 0


class TestGoalTrackerRecommendations:
    """Test recommendation generation."""

    def _create_snapshot(
        self,
        features: list[FeatureSummary] | None = None,
        bugs: list[BugSummary] | None = None,
        specs: list[SpecSummary] | None = None,
        prds: list[PRDSummary] | None = None,
        tests: TestState | None = None,
    ) -> RepoStateSnapshot:
        """Create a test snapshot."""
        return RepoStateSnapshot(
            gathered_at=datetime.now().isoformat(),
            git=GitState(
                branch="main",
                is_clean=True,
                uncommitted_files=[],
                recent_commits=[],
                ahead_behind=(0, 0),
            ),
            features=features or [],
            bugs=bugs or [],
            prds=prds or [],
            specs=specs or [],
            tests=tests or TestState(
                total_tests=10,
                passing=10,
                failing=0,
                skipped=0,
                last_run_at=None,
            ),
            github=None,
            interrupted_sessions=[],
            total_cost_today=0.0,
            total_cost_week=0.0,
        )

    def test_generate_recommendations_empty(self, tmp_path: Path) -> None:
        """Test generating recommendations with empty state."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot()
        recommendations = tracker.generate_recommendations(snapshot)

        assert isinstance(recommendations, list)

    def test_generate_recommendations_p1_blockers(self, tmp_path: Path) -> None:
        """Test P1 recommendations for blockers."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="blocked-feature",
                    phase="BLOCKED",
                    tasks_done=2,
                    tasks_total=5,
                    tasks_blocked=3,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p1_recs = [r for r in recommendations if r.priority == "P1"]
        # Should have a recommendation about the blocker
        assert any("blocked" in r.task.lower() or "blocked" in r.rationale.lower() for r in p1_recs)

    def test_generate_recommendations_p1_approvals(self, tmp_path: Path) -> None:
        """Test P1 recommendations for approvals needed."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="needs-approval",
                    phase="SPEC_NEEDS_APPROVAL",
                    tasks_done=0,
                    tasks_total=0,
                    tasks_blocked=0,
                    cost_usd=1.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p1_recs = [r for r in recommendations if r.priority == "P1"]
        assert len(p1_recs) >= 1
        assert any(r.linked_feature == "needs-approval" for r in p1_recs)

    def test_generate_recommendations_p1_regressions(self, tmp_path: Path) -> None:
        """Test P1 recommendations for test regressions."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            tests=TestState(
                total_tests=10,
                passing=7,
                failing=3,
                skipped=0,
                last_run_at=datetime.now().isoformat(),
            )
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p1_recs = [r for r in recommendations if r.priority == "P1"]
        assert any("failing" in r.task.lower() or "test" in r.task.lower() for r in p1_recs)

    def test_generate_recommendations_p1_spec_reviews(self, tmp_path: Path) -> None:
        """Test P1 recommendations for spec reviews."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            specs=[
                SpecSummary(
                    feature_id="needs-revision",
                    title="Failing Spec",
                    path="specs/needs-revision/spec.md",
                    has_review=True,
                    review_passed=False,
                    review_scores={"clarity": 0.5, "coverage": 0.4},
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p1_recs = [r for r in recommendations if r.priority == "P1"]
        assert any(r.linked_spec == "needs-revision" for r in p1_recs)

    def test_generate_recommendations_p2_in_progress(self, tmp_path: Path) -> None:
        """Test P2 recommendations for in-progress work."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="in-progress",
                    phase="IMPLEMENTING",
                    tasks_done=2,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        recommendations = tracker.generate_recommendations(snapshot)

        p2_recs = [r for r in recommendations if r.priority == "P2"]
        assert any(r.linked_feature == "in-progress" for r in p2_recs)

    def test_generate_recommendations_p3_new_features(self, tmp_path: Path) -> None:
        """Test P3 recommendations for new features."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            prds=[
                PRDSummary(
                    feature_id="new-feature",
                    title="New Feature",
                    phase="PRD_READY",
                    path=".claude/prds/new-feature.md",
                ),
            ]
        )

        recommendations = tracker.generate_recommendations(snapshot)

        # Should have recommendation for new feature (P2 or P3)
        assert any(
            "new-feature" in r.task.lower() or r.linked_feature == "new-feature"
            for r in recommendations
        )

    def test_generate_recommendations_priority_order(self, tmp_path: Path) -> None:
        """Test recommendations are sorted by priority."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="needs-approval",
                    phase="SPEC_NEEDS_APPROVAL",
                    tasks_done=0,
                    tasks_total=0,
                    tasks_blocked=0,
                    cost_usd=1.0,
                    updated_at=datetime.now().isoformat(),
                ),
                FeatureSummary(
                    feature_id="in-progress",
                    phase="IMPLEMENTING",
                    tasks_done=2,
                    tasks_total=5,
                    tasks_blocked=0,
                    cost_usd=5.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ],
            tests=TestState(
                total_tests=10,
                passing=8,
                failing=2,
                skipped=0,
                last_run_at=datetime.now().isoformat(),
            ),
        )

        recommendations = tracker.generate_recommendations(snapshot)

        if len(recommendations) >= 2:
            priorities = [r.priority for r in recommendations]
            # P1 should come before P2, P2 before P3
            priority_order = {"P1": 0, "P2": 1, "P3": 2}
            for i in range(len(priorities) - 1):
                assert priority_order[priorities[i]] <= priority_order[priorities[i + 1]]

    def test_recommendation_has_required_fields(self, tmp_path: Path) -> None:
        """Test recommendations have all required fields."""
        log_manager = DailyLogManager(tmp_path)
        tracker = GoalTracker(log_manager)

        snapshot = self._create_snapshot(
            features=[
                FeatureSummary(
                    feature_id="needs-approval",
                    phase="SPEC_NEEDS_APPROVAL",
                    tasks_done=0,
                    tasks_total=0,
                    tasks_blocked=0,
                    cost_usd=1.0,
                    updated_at=datetime.now().isoformat(),
                ),
            ]
        )

        recommendations = tracker.generate_recommendations(snapshot)

        if recommendations:
            rec = recommendations[0]
            assert hasattr(rec, "priority")
            assert hasattr(rec, "task")
            assert hasattr(rec, "estimated_cost_usd")
            assert hasattr(rec, "estimated_minutes")
            assert hasattr(rec, "rationale")