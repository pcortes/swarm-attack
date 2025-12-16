"""
Unit tests for Chief of Staff data models.

Tests cover:
- Round-trip serialization (to_dict -> from_dict)
- Enum handling
- Nested object serialization
- Default value handling
- Edge cases
"""

import pytest
from datetime import datetime

from swarm_attack.chief_of_staff.models import (
    # Enums
    GoalStatus,
    CheckpointTrigger,
    # Core models
    DailyGoal,
    Decision,
    WorkLogEntry,
    StandupSession,
    DailySummary,
    DailyLog,
    # State snapshot models
    GitState,
    FeatureSummary,
    BugSummary,
    PRDSummary,
    SpecSummary,
    TestSuiteState,
    GitHubState,
    InterruptedSession,
    RepoStateSnapshot,
    # Recommendation models
    Recommendation,
    AttentionItem,
    StandupReport,
    # Autopilot models
    CheckpointEvent,
    AutopilotSession,
)


# =============================================================================
# Enum Tests
# =============================================================================


class TestGoalStatus:
    """Tests for GoalStatus enum."""

    def test_all_values(self):
        """Test all enum values exist."""
        assert GoalStatus.PENDING.value == "pending"
        assert GoalStatus.IN_PROGRESS.value == "in_progress"
        assert GoalStatus.DONE.value == "done"
        assert GoalStatus.PARTIAL.value == "partial"
        assert GoalStatus.SKIPPED.value == "skipped"
        assert GoalStatus.BLOCKED.value == "blocked"

    def test_from_value(self):
        """Test creating enum from string value."""
        assert GoalStatus("pending") == GoalStatus.PENDING
        assert GoalStatus("in_progress") == GoalStatus.IN_PROGRESS


class TestCheckpointTrigger:
    """Tests for CheckpointTrigger enum."""

    def test_all_values(self):
        """Test all enum values exist."""
        assert CheckpointTrigger.COST_THRESHOLD.value == "cost_threshold_reached"
        assert CheckpointTrigger.TIME_THRESHOLD.value == "time_threshold_reached"
        assert CheckpointTrigger.BLOCKER_DETECTED.value == "blocker_detected"
        assert CheckpointTrigger.APPROVAL_REQUIRED.value == "approval_required"
        assert CheckpointTrigger.HIGH_RISK_ACTION.value == "high_risk_action"
        assert CheckpointTrigger.ERROR_RATE_SPIKE.value == "error_rate_spike"
        assert CheckpointTrigger.END_OF_SESSION.value == "end_of_session"


# =============================================================================
# Core Model Tests
# =============================================================================


class TestDailyGoal:
    """Tests for DailyGoal dataclass."""

    def test_basic_creation(self):
        """Test creating a basic goal."""
        goal = DailyGoal(
            id="goal-001",
            content="Implement feature X",
            priority="P1",
        )
        assert goal.id == "goal-001"
        assert goal.content == "Implement feature X"
        assert goal.priority == "P1"
        assert goal.status == GoalStatus.PENDING

    def test_full_creation(self):
        """Test creating a goal with all fields."""
        goal = DailyGoal(
            id="goal-002",
            content="Fix bug Y",
            priority="P2",
            status=GoalStatus.IN_PROGRESS,
            estimated_minutes=60,
            actual_minutes=45,
            notes="Almost done",
            linked_feature="my-feature",
            linked_bug="bug-123",
            linked_spec="spec-456",
            completed_at="2025-12-16T10:00:00",
        )
        assert goal.status == GoalStatus.IN_PROGRESS
        assert goal.estimated_minutes == 60
        assert goal.linked_feature == "my-feature"

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = DailyGoal(
            id="goal-003",
            content="Test serialization",
            priority="P3",
            status=GoalStatus.DONE,
            estimated_minutes=30,
            actual_minutes=25,
            notes="Completed successfully",
            linked_feature="feature-1",
        )

        data = original.to_dict()
        restored = DailyGoal.from_dict(data)

        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.priority == original.priority
        assert restored.status == original.status
        assert restored.estimated_minutes == original.estimated_minutes
        assert restored.notes == original.notes
        assert restored.linked_feature == original.linked_feature

    def test_status_serializes_as_string(self):
        """Test that status is serialized as string value."""
        goal = DailyGoal(id="g1", content="test", priority="P1", status=GoalStatus.BLOCKED)
        data = goal.to_dict()
        assert data["status"] == "blocked"


class TestDecision:
    """Tests for Decision dataclass."""

    def test_basic_creation(self):
        """Test creating a basic decision."""
        decision = Decision(
            timestamp="2025-12-16T10:00:00",
            type="approval",
            item="spec-review",
            decision="approve",
            rationale="All criteria met",
        )
        assert decision.type == "approval"
        assert decision.human_override is False

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = Decision(
            timestamp="2025-12-16T10:00:00",
            type="priority",
            item="feature-x",
            decision="escalate",
            rationale="Critical bug",
            human_override=True,
            metadata={"old_priority": "P2", "new_priority": "P1"},
        )

        data = original.to_dict()
        restored = Decision.from_dict(data)

        assert restored.timestamp == original.timestamp
        assert restored.type == original.type
        assert restored.human_override == original.human_override
        assert restored.metadata == original.metadata


class TestWorkLogEntry:
    """Tests for WorkLogEntry dataclass."""

    def test_basic_creation(self):
        """Test creating a basic work log entry."""
        entry = WorkLogEntry(
            timestamp="2025-12-16T10:00:00",
            action="Ran tests",
            result="All passed",
        )
        assert entry.cost_usd == 0.0
        assert entry.duration_seconds == 0

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = WorkLogEntry(
            timestamp="2025-12-16T10:00:00",
            action="Implemented feature",
            result="Success",
            cost_usd=1.50,
            duration_seconds=3600,
            checkpoint="cost_threshold_reached",
        )

        data = original.to_dict()
        restored = WorkLogEntry.from_dict(data)

        assert restored.cost_usd == original.cost_usd
        assert restored.checkpoint == original.checkpoint


class TestStandupSession:
    """Tests for StandupSession dataclass."""

    def test_basic_creation(self):
        """Test creating a basic standup session."""
        session = StandupSession(
            session_id="cos-20251216-001",
            time="2025-12-16T09:00:00",
        )
        assert session.yesterday_goals == []
        assert session.today_goals == []

    def test_with_goals(self):
        """Test standup session with goals."""
        yesterday = [DailyGoal(id="g1", content="Old task", priority="P1")]
        today = [DailyGoal(id="g2", content="New task", priority="P2")]

        session = StandupSession(
            session_id="cos-20251216-001",
            time="2025-12-16T09:00:00",
            yesterday_goals=yesterday,
            today_goals=today,
        )
        assert len(session.yesterday_goals) == 1
        assert len(session.today_goals) == 1

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = StandupSession(
            session_id="cos-20251216-001",
            time="2025-12-16T09:00:00",
            yesterday_goals=[DailyGoal(id="g1", content="Task 1", priority="P1")],
            today_goals=[DailyGoal(id="g2", content="Task 2", priority="P2")],
            philip_notes="Focus on feature X",
            recommendations_accepted=True,
        )

        data = original.to_dict()
        restored = StandupSession.from_dict(data)

        assert restored.session_id == original.session_id
        assert len(restored.yesterday_goals) == 1
        assert len(restored.today_goals) == 1
        assert restored.yesterday_goals[0].content == "Task 1"


class TestDailySummary:
    """Tests for DailySummary dataclass."""

    def test_basic_creation(self):
        """Test creating a basic daily summary."""
        summary = DailySummary(
            goals_completed=3,
            goals_total=5,
            total_cost_usd=4.50,
        )
        assert summary.key_accomplishments == []
        assert summary.blockers_for_tomorrow == []

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        carryover = [DailyGoal(id="g3", content="Unfinished", priority="P1")]
        original = DailySummary(
            goals_completed=4,
            goals_total=5,
            total_cost_usd=8.25,
            key_accomplishments=["Completed feature A", "Fixed bug B"],
            blockers_for_tomorrow=["API rate limit"],
            carryover_goals=carryover,
        )

        data = original.to_dict()
        restored = DailySummary.from_dict(data)

        assert restored.goals_completed == 4
        assert len(restored.carryover_goals) == 1
        assert restored.carryover_goals[0].content == "Unfinished"


class TestDailyLog:
    """Tests for DailyLog dataclass."""

    def test_basic_creation(self):
        """Test creating a basic daily log."""
        log = DailyLog(date="2025-12-16")
        assert log.date == "2025-12-16"
        assert log.standups == []
        assert log.work_log == []
        assert log.summary is None
        assert log.created_at != ""  # Should be auto-set

    def test_timestamps_auto_set(self):
        """Test that timestamps are auto-set."""
        log = DailyLog(date="2025-12-16")
        assert log.created_at != ""
        assert log.updated_at != ""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = DailyLog(
            date="2025-12-16",
            standups=[StandupSession(session_id="s1", time="2025-12-16T09:00:00")],
            work_log=[WorkLogEntry(timestamp="2025-12-16T10:00:00", action="Test", result="Pass")],
            summary=DailySummary(goals_completed=2, goals_total=3, total_cost_usd=1.0),
            created_at="2025-12-16T08:00:00",
            updated_at="2025-12-16T18:00:00",
        )

        data = original.to_dict()
        restored = DailyLog.from_dict(data)

        assert restored.date == original.date
        assert len(restored.standups) == 1
        assert len(restored.work_log) == 1
        assert restored.summary is not None
        assert restored.summary.goals_completed == 2


# =============================================================================
# State Snapshot Model Tests
# =============================================================================


class TestGitState:
    """Tests for GitState dataclass."""

    def test_basic_creation(self):
        """Test creating git state."""
        state = GitState(branch="main", is_clean=True)
        assert state.uncommitted_files == []
        assert state.ahead_behind == (0, 0)

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = GitState(
            branch="feature/test",
            is_clean=False,
            uncommitted_files=["file1.py", "file2.py"],
            recent_commits=[{"hash": "abc123", "message": "Test commit"}],
            ahead_behind=(2, 1),
        )

        data = original.to_dict()
        restored = GitState.from_dict(data)

        assert restored.branch == "feature/test"
        assert restored.ahead_behind == (2, 1)
        assert len(restored.uncommitted_files) == 2


class TestFeatureSummary:
    """Tests for FeatureSummary dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = FeatureSummary(
            feature_id="my-feature",
            phase="IMPLEMENTING",
            tasks_done=5,
            tasks_total=10,
            tasks_blocked=1,
            cost_usd=15.50,
            updated_at="2025-12-16T10:00:00",
        )

        data = original.to_dict()
        restored = FeatureSummary.from_dict(data)

        assert restored.feature_id == original.feature_id
        assert restored.phase == original.phase
        assert restored.tasks_done == original.tasks_done


class TestBugSummary:
    """Tests for BugSummary dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = BugSummary(
            bug_id="bug-123",
            phase="FIXING",
            cost_usd=2.50,
            updated_at="2025-12-16T10:00:00",
        )

        data = original.to_dict()
        restored = BugSummary.from_dict(data)

        assert restored.bug_id == original.bug_id
        assert restored.phase == original.phase


class TestSpecSummary:
    """Tests for SpecSummary dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = SpecSummary(
            feature_id="my-feature",
            title="My Feature Spec",
            path="specs/my-feature/spec-draft.md",
            has_review=True,
            review_passed=True,
            review_scores={"completeness": 0.9, "clarity": 0.85},
            updated_at="2025-12-16T10:00:00",
        )

        data = original.to_dict()
        restored = SpecSummary.from_dict(data)

        assert restored.feature_id == original.feature_id
        assert restored.has_review is True
        assert restored.review_scores == {"completeness": 0.9, "clarity": 0.85}


class TestTestSuiteState:
    """Tests for TestSuiteState dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = TestSuiteState(
            total_tests=100,
            passing=95,
            failing=3,
            skipped=2,
            last_run_at="2025-12-16T10:00:00",
        )

        data = original.to_dict()
        restored = TestSuiteState.from_dict(data)

        assert restored.total_tests == 100
        assert restored.passing == 95


class TestGitHubState:
    """Tests for GitHubState dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = GitHubState(
            open_issues=10,
            closed_issues_today=2,
            open_prs=3,
            pending_reviews=[{"pr": 123, "title": "Fix bug"}],
        )

        data = original.to_dict()
        restored = GitHubState.from_dict(data)

        assert restored.open_issues == 10
        assert len(restored.pending_reviews) == 1


class TestInterruptedSession:
    """Tests for InterruptedSession dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = InterruptedSession(
            session_id="session-001",
            feature_id="my-feature",
            issue_number=5,
            started_at="2025-12-16T10:00:00",
            last_checkpoint="cost_threshold_reached",
        )

        data = original.to_dict()
        restored = InterruptedSession.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.last_checkpoint == original.last_checkpoint


class TestRepoStateSnapshot:
    """Tests for RepoStateSnapshot dataclass."""

    def test_minimal_creation(self):
        """Test creating a minimal snapshot."""
        snapshot = RepoStateSnapshot(
            gathered_at="2025-12-16T10:00:00",
            git=GitState(branch="main", is_clean=True),
        )
        assert snapshot.features == []
        assert snapshot.total_cost_today == 0.0

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = RepoStateSnapshot(
            gathered_at="2025-12-16T10:00:00",
            git=GitState(branch="main", is_clean=True),
            features=[FeatureSummary(
                feature_id="f1", phase="IMPLEMENTING",
                tasks_done=1, tasks_total=5, tasks_blocked=0,
                cost_usd=1.0, updated_at="2025-12-16T09:00:00"
            )],
            bugs=[BugSummary(bug_id="b1", phase="FIXING", cost_usd=0.5, updated_at="2025-12-16T09:00:00")],
            tests=TestSuiteState(total_tests=50, passing=48, failing=2, skipped=0),
            github=GitHubState(open_issues=5, closed_issues_today=1, open_prs=2),
            total_cost_today=5.50,
            total_cost_week=25.00,
        )

        data = original.to_dict()
        restored = RepoStateSnapshot.from_dict(data)

        assert restored.gathered_at == original.gathered_at
        assert len(restored.features) == 1
        assert len(restored.bugs) == 1
        assert restored.tests.total_tests == 50
        assert restored.github.open_issues == 5


# =============================================================================
# Recommendation Model Tests
# =============================================================================


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = Recommendation(
            priority="P1",
            task="Complete feature X",
            estimated_cost_usd=5.00,
            estimated_minutes=60,
            rationale="High priority blocker",
            linked_feature="feature-x",
            command="swarm-attack run feature-x",
        )

        data = original.to_dict()
        restored = Recommendation.from_dict(data)

        assert restored.priority == "P1"
        assert restored.task == original.task
        assert restored.command == original.command


class TestAttentionItem:
    """Tests for AttentionItem dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = AttentionItem(
            type="approval",
            description="Spec needs review",
            urgency="high",
            action="Review and approve spec",
            command="swarm-attack approve spec",
        )

        data = original.to_dict()
        restored = AttentionItem.from_dict(data)

        assert restored.type == "approval"
        assert restored.urgency == "high"


class TestStandupReport:
    """Tests for StandupReport dataclass."""

    def test_minimal_creation(self):
        """Test creating a minimal standup report."""
        report = StandupReport(date="2025-12-16")
        assert report.attention_items == []
        assert report.recommendations == []

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = StandupReport(
            date="2025-12-16",
            yesterday_comparison={"completed": 3, "total": 5},
            repo_health={"status": "healthy"},
            attention_items=[AttentionItem(
                type="blocker", description="API down",
                urgency="high", action="Investigate"
            )],
            blockers=["External API unavailable"],
            recommendations=[Recommendation(
                priority="P1", task="Fix blocker",
                estimated_cost_usd=2.0, estimated_minutes=30,
                rationale="Critical"
            )],
            state_snapshot=RepoStateSnapshot(
                gathered_at="2025-12-16T09:00:00",
                git=GitState(branch="main", is_clean=True),
            ),
        )

        data = original.to_dict()
        restored = StandupReport.from_dict(data)

        assert restored.date == "2025-12-16"
        assert len(restored.attention_items) == 1
        assert len(restored.recommendations) == 1
        assert restored.state_snapshot is not None


# =============================================================================
# Autopilot Model Tests
# =============================================================================


class TestCheckpointEvent:
    """Tests for CheckpointEvent dataclass."""

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = CheckpointEvent(
            timestamp="2025-12-16T10:00:00",
            trigger=CheckpointTrigger.COST_THRESHOLD,
            context={"cost_usd": 10.50, "budget": 10.0},
            action_taken="paused",
            human_response="continue",
        )

        data = original.to_dict()
        restored = CheckpointEvent.from_dict(data)

        assert restored.trigger == CheckpointTrigger.COST_THRESHOLD
        assert restored.action_taken == "paused"
        assert restored.context["cost_usd"] == 10.50


class TestAutopilotSession:
    """Tests for AutopilotSession dataclass."""

    def test_basic_creation(self):
        """Test creating a basic autopilot session."""
        session = AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
        )
        assert session.goals == []
        assert session.status == "running"
        assert session.cost_spent_usd == 0.0

    def test_round_trip_serialization(self):
        """Test to_dict and from_dict round trip."""
        original = AutopilotSession(
            session_id="ap-20251216-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=7200,
            stop_trigger=CheckpointTrigger.BLOCKER_DETECTED,
            goals=[DailyGoal(id="g1", content="Task 1", priority="P1")],
            current_goal_index=0,
            checkpoints=[CheckpointEvent(
                timestamp="2025-12-16T11:00:00",
                trigger=CheckpointTrigger.APPROVAL_REQUIRED,
                action_taken="paused",
            )],
            cost_spent_usd=5.50,
            duration_seconds=3600,
            status="paused",
            pause_reason="Approval required for spec",
        )

        data = original.to_dict()
        restored = AutopilotSession.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.stop_trigger == CheckpointTrigger.BLOCKER_DETECTED
        assert len(restored.goals) == 1
        assert len(restored.checkpoints) == 1
        assert restored.status == "paused"

    def test_stop_trigger_optional(self):
        """Test that stop_trigger is optional."""
        session = AutopilotSession(
            session_id="ap-001",
            started_at="2025-12-16T10:00:00",
            budget_usd=10.0,
            duration_limit_seconds=3600,
        )
        data = session.to_dict()
        assert data["stop_trigger"] is None

        restored = AutopilotSession.from_dict(data)
        assert restored.stop_trigger is None


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_lists_serialize_correctly(self):
        """Test that empty lists are handled correctly."""
        log = DailyLog(date="2025-12-16")
        data = log.to_dict()
        assert data["standups"] == []
        assert data["work_log"] == []

        restored = DailyLog.from_dict(data)
        assert restored.standups == []

    def test_none_values_serialize_correctly(self):
        """Test that None values are handled correctly."""
        goal = DailyGoal(id="g1", content="test", priority="P1")
        data = goal.to_dict()
        assert data["linked_feature"] is None
        assert data["completed_at"] is None

        restored = DailyGoal.from_dict(data)
        assert restored.linked_feature is None

    def test_deeply_nested_serialization(self):
        """Test deeply nested object serialization."""
        report = StandupReport(
            date="2025-12-16",
            state_snapshot=RepoStateSnapshot(
                gathered_at="2025-12-16T09:00:00",
                git=GitState(branch="main", is_clean=True),
                features=[FeatureSummary(
                    feature_id="f1", phase="COMPLETE",
                    tasks_done=5, tasks_total=5, tasks_blocked=0,
                    cost_usd=10.0, updated_at="2025-12-16T08:00:00"
                )],
            ),
            recommendations=[Recommendation(
                priority="P2", task="Start next feature",
                estimated_cost_usd=8.0, estimated_minutes=120,
                rationale="Previous feature complete"
            )],
        )

        data = report.to_dict()
        restored = StandupReport.from_dict(data)

        assert restored.state_snapshot.features[0].feature_id == "f1"
        assert restored.recommendations[0].priority == "P2"

    def test_metadata_dict_preserved(self):
        """Test that arbitrary metadata dicts are preserved."""
        decision = Decision(
            timestamp="2025-12-16T10:00:00",
            type="custom",
            item="test",
            decision="proceed",
            rationale="Testing",
            metadata={
                "nested": {"key": "value"},
                "list": [1, 2, 3],
                "number": 42.5,
            },
        )

        data = decision.to_dict()
        restored = Decision.from_dict(data)

        assert restored.metadata["nested"]["key"] == "value"
        assert restored.metadata["list"] == [1, 2, 3]
        assert restored.metadata["number"] == 42.5
