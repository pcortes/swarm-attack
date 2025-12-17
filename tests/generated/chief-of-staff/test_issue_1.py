"""Tests for Chief of Staff data models."""

import pytest
from datetime import datetime
from typing import Any

from swarm_attack.chief_of_staff.models import (
    GoalStatus,
    CheckpointTrigger,
    DailyGoal,
    Decision,
    WorkLogEntry,
    StandupSession,
    DailySummary,
    DailyLog,
    GitState,
    FeatureSummary,
    BugSummary,
    PRDSummary,
    SpecSummary,
    TestState,
    GitHubState,
    InterruptedSession,
    RepoStateSnapshot,
    Recommendation,
    AttentionItem,
    StandupReport,
    CheckpointEvent,
    AutopilotSession,
)


class TestGoalStatus:
    """Tests for GoalStatus enum."""

    def test_has_pending(self):
        assert GoalStatus.PENDING.value == "pending"

    def test_has_in_progress(self):
        assert GoalStatus.IN_PROGRESS.value == "in_progress"

    def test_has_done(self):
        assert GoalStatus.DONE.value == "done"

    def test_has_partial(self):
        assert GoalStatus.PARTIAL.value == "partial"

    def test_has_skipped(self):
        assert GoalStatus.SKIPPED.value == "skipped"

    def test_has_blocked(self):
        assert GoalStatus.BLOCKED.value == "blocked"


class TestCheckpointTrigger:
    """Tests for CheckpointTrigger enum."""

    def test_has_manual(self):
        assert CheckpointTrigger.MANUAL.value == "manual"

    def test_has_time_based(self):
        assert CheckpointTrigger.TIME_BASED.value == "time_based"

    def test_has_goal_completed(self):
        assert CheckpointTrigger.GOAL_COMPLETED.value == "goal_completed"

    def test_has_error(self):
        assert CheckpointTrigger.ERROR.value == "error"

    def test_has_user_interrupt(self):
        assert CheckpointTrigger.USER_INTERRUPT.value == "user_interrupt"

    def test_has_phase_transition(self):
        assert CheckpointTrigger.PHASE_TRANSITION.value == "phase_transition"


class TestDailyGoal:
    """Tests for DailyGoal dataclass."""

    def test_has_required_fields(self):
        goal = DailyGoal(
            id="goal-1",
            description="Test goal",
            priority=1,
        )
        assert goal.id == "goal-1"
        assert goal.description == "Test goal"
        assert goal.priority == 1

    def test_has_status_default(self):
        goal = DailyGoal(id="goal-1", description="Test", priority=1)
        assert goal.status == GoalStatus.PENDING

    def test_has_feature_id_optional(self):
        goal = DailyGoal(id="goal-1", description="Test", priority=1, feature_id="feat-1")
        assert goal.feature_id == "feat-1"

    def test_has_bug_id_optional(self):
        goal = DailyGoal(id="goal-1", description="Test", priority=1, bug_id="bug-1")
        assert goal.bug_id == "bug-1"

    def test_has_notes_field(self):
        goal = DailyGoal(id="goal-1", description="Test", priority=1, notes="Some notes")
        assert goal.notes == "Some notes"

    def test_to_dict(self):
        goal = DailyGoal(
            id="goal-1",
            description="Test goal",
            priority=1,
            status=GoalStatus.IN_PROGRESS,
            feature_id="feat-1",
        )
        data = goal.to_dict()
        assert data["id"] == "goal-1"
        assert data["description"] == "Test goal"
        assert data["priority"] == 1
        assert data["status"] == "in_progress"
        assert data["feature_id"] == "feat-1"

    def test_from_dict(self):
        data = {
            "id": "goal-2",
            "description": "From dict goal",
            "priority": 2,
            "status": "done",
            "bug_id": "bug-1",
        }
        goal = DailyGoal.from_dict(data)
        assert goal.id == "goal-2"
        assert goal.description == "From dict goal"
        assert goal.priority == 2
        assert goal.status == GoalStatus.DONE
        assert goal.bug_id == "bug-1"

    def test_roundtrip(self):
        original = DailyGoal(
            id="goal-3",
            description="Roundtrip test",
            priority=3,
            status=GoalStatus.BLOCKED,
            feature_id="feat-2",
            notes="Test notes",
        )
        roundtrip = DailyGoal.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.description == original.description
        assert roundtrip.priority == original.priority
        assert roundtrip.status == original.status
        assert roundtrip.feature_id == original.feature_id
        assert roundtrip.notes == original.notes


class TestDecision:
    """Tests for Decision dataclass."""

    def test_has_required_fields(self):
        decision = Decision(
            id="dec-1",
            description="Test decision",
            rationale="Because reasons",
            timestamp="2024-01-01T00:00:00",
        )
        assert decision.id == "dec-1"
        assert decision.description == "Test decision"
        assert decision.rationale == "Because reasons"

    def test_has_context_field(self):
        decision = Decision(
            id="dec-1",
            description="Test",
            rationale="Reason",
            timestamp="2024-01-01T00:00:00",
            context={"key": "value"},
        )
        assert decision.context == {"key": "value"}

    def test_to_dict(self):
        decision = Decision(
            id="dec-1",
            description="Test decision",
            rationale="Reason",
            timestamp="2024-01-01T00:00:00",
        )
        data = decision.to_dict()
        assert data["id"] == "dec-1"
        assert data["description"] == "Test decision"
        assert data["rationale"] == "Reason"
        assert data["timestamp"] == "2024-01-01T00:00:00"

    def test_from_dict(self):
        data = {
            "id": "dec-2",
            "description": "From dict",
            "rationale": "Dict reason",
            "timestamp": "2024-01-02T00:00:00",
            "context": {"foo": "bar"},
        }
        decision = Decision.from_dict(data)
        assert decision.id == "dec-2"
        assert decision.description == "From dict"
        assert decision.context == {"foo": "bar"}

    def test_roundtrip(self):
        original = Decision(
            id="dec-3",
            description="Roundtrip",
            rationale="Testing",
            timestamp="2024-01-03T00:00:00",
            context={"test": True},
        )
        roundtrip = Decision.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.description == original.description
        assert roundtrip.rationale == original.rationale
        assert roundtrip.context == original.context


class TestWorkLogEntry:
    """Tests for WorkLogEntry dataclass."""

    def test_has_required_fields(self):
        entry = WorkLogEntry(
            timestamp="2024-01-01T00:00:00",
            action="Test action",
            details="Some details",
        )
        assert entry.timestamp == "2024-01-01T00:00:00"
        assert entry.action == "Test action"
        assert entry.details == "Some details"

    def test_has_goal_id_optional(self):
        entry = WorkLogEntry(
            timestamp="2024-01-01T00:00:00",
            action="Test",
            details="Details",
            goal_id="goal-1",
        )
        assert entry.goal_id == "goal-1"

    def test_to_dict(self):
        entry = WorkLogEntry(
            timestamp="2024-01-01T00:00:00",
            action="Test action",
            details="Details",
            goal_id="goal-1",
        )
        data = entry.to_dict()
        assert data["timestamp"] == "2024-01-01T00:00:00"
        assert data["action"] == "Test action"
        assert data["details"] == "Details"
        assert data["goal_id"] == "goal-1"

    def test_from_dict(self):
        data = {
            "timestamp": "2024-01-02T00:00:00",
            "action": "From dict",
            "details": "Dict details",
        }
        entry = WorkLogEntry.from_dict(data)
        assert entry.timestamp == "2024-01-02T00:00:00"
        assert entry.action == "From dict"
        assert entry.details == "Dict details"

    def test_roundtrip(self):
        original = WorkLogEntry(
            timestamp="2024-01-03T00:00:00",
            action="Roundtrip",
            details="Test",
            goal_id="goal-2",
        )
        roundtrip = WorkLogEntry.from_dict(original.to_dict())
        assert roundtrip.timestamp == original.timestamp
        assert roundtrip.action == original.action
        assert roundtrip.goal_id == original.goal_id


class TestStandupSession:
    """Tests for StandupSession dataclass."""

    def test_has_required_fields(self):
        session = StandupSession(
            date="2024-01-01",
            goals=[],
            decisions=[],
            work_log=[],
        )
        assert session.date == "2024-01-01"
        assert session.goals == []
        assert session.decisions == []
        assert session.work_log == []

    def test_has_summary_field(self):
        session = StandupSession(
            date="2024-01-01",
            goals=[],
            decisions=[],
            work_log=[],
            summary="Day summary",
        )
        assert session.summary == "Day summary"

    def test_to_dict_with_nested(self):
        goal = DailyGoal(id="g1", description="Goal 1", priority=1)
        decision = Decision(id="d1", description="Dec 1", rationale="R", timestamp="2024-01-01T00:00:00")
        entry = WorkLogEntry(timestamp="2024-01-01T00:00:00", action="Act", details="Det")
        session = StandupSession(
            date="2024-01-01",
            goals=[goal],
            decisions=[decision],
            work_log=[entry],
        )
        data = session.to_dict()
        assert data["date"] == "2024-01-01"
        assert len(data["goals"]) == 1
        assert data["goals"][0]["id"] == "g1"
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["id"] == "d1"
        assert len(data["work_log"]) == 1
        assert data["work_log"][0]["action"] == "Act"

    def test_from_dict_with_nested(self):
        data = {
            "date": "2024-01-02",
            "goals": [{"id": "g2", "description": "Goal 2", "priority": 2, "status": "done"}],
            "decisions": [{"id": "d2", "description": "Dec 2", "rationale": "R2", "timestamp": "2024-01-02T00:00:00"}],
            "work_log": [{"timestamp": "2024-01-02T00:00:00", "action": "Act2", "details": "Det2"}],
            "summary": "Summary",
        }
        session = StandupSession.from_dict(data)
        assert session.date == "2024-01-02"
        assert len(session.goals) == 1
        assert isinstance(session.goals[0], DailyGoal)
        assert session.goals[0].status == GoalStatus.DONE
        assert len(session.decisions) == 1
        assert isinstance(session.decisions[0], Decision)
        assert len(session.work_log) == 1
        assert isinstance(session.work_log[0], WorkLogEntry)
        assert session.summary == "Summary"

    def test_roundtrip(self):
        goal = DailyGoal(id="g3", description="Goal 3", priority=3, status=GoalStatus.IN_PROGRESS)
        original = StandupSession(
            date="2024-01-03",
            goals=[goal],
            decisions=[],
            work_log=[],
            summary="Test",
        )
        roundtrip = StandupSession.from_dict(original.to_dict())
        assert roundtrip.date == original.date
        assert len(roundtrip.goals) == 1
        assert roundtrip.goals[0].id == goal.id
        assert roundtrip.goals[0].status == goal.status


class TestDailySummary:
    """Tests for DailySummary dataclass."""

    def test_has_required_fields(self):
        summary = DailySummary(
            date="2024-01-01",
            completed_goals=[],
            incomplete_goals=[],
            carryover_goals=[],
            key_decisions=[],
            blockers=[],
        )
        assert summary.date == "2024-01-01"
        assert summary.completed_goals == []
        assert summary.carryover_goals == []

    def test_has_notes_field(self):
        summary = DailySummary(
            date="2024-01-01",
            completed_goals=[],
            incomplete_goals=[],
            carryover_goals=[],
            key_decisions=[],
            blockers=[],
            notes="Daily notes",
        )
        assert summary.notes == "Daily notes"

    def test_to_dict(self):
        summary = DailySummary(
            date="2024-01-01",
            completed_goals=["goal-1"],
            incomplete_goals=["goal-2"],
            carryover_goals=["goal-3"],
            key_decisions=["dec-1"],
            blockers=["blocker-1"],
        )
        data = summary.to_dict()
        assert data["date"] == "2024-01-01"
        assert data["completed_goals"] == ["goal-1"]
        assert data["carryover_goals"] == ["goal-3"]
        assert data["blockers"] == ["blocker-1"]

    def test_from_dict(self):
        data = {
            "date": "2024-01-02",
            "completed_goals": ["g1"],
            "incomplete_goals": ["g2"],
            "carryover_goals": ["g3"],
            "key_decisions": ["d1"],
            "blockers": ["b1"],
            "notes": "Notes",
        }
        summary = DailySummary.from_dict(data)
        assert summary.date == "2024-01-02"
        assert summary.completed_goals == ["g1"]
        assert summary.notes == "Notes"

    def test_roundtrip(self):
        original = DailySummary(
            date="2024-01-03",
            completed_goals=["g1", "g2"],
            incomplete_goals=["g3"],
            carryover_goals=["g4"],
            key_decisions=["d1"],
            blockers=["b1"],
            notes="Test notes",
        )
        roundtrip = DailySummary.from_dict(original.to_dict())
        assert roundtrip.date == original.date
        assert roundtrip.completed_goals == original.completed_goals
        assert roundtrip.carryover_goals == original.carryover_goals
        assert roundtrip.notes == original.notes


class TestDailyLog:
    """Tests for DailyLog dataclass."""

    def test_has_required_fields(self):
        log = DailyLog(
            date="2024-01-01",
            entries=[],
        )
        assert log.date == "2024-01-01"
        assert log.entries == []

    def test_has_timestamp_auto_init(self):
        log = DailyLog(date="2024-01-01", entries=[])
        assert log.created_at is not None
        assert isinstance(log.created_at, str)

    def test_to_dict(self):
        entry = WorkLogEntry(timestamp="2024-01-01T00:00:00", action="Act", details="Det")
        log = DailyLog(date="2024-01-01", entries=[entry])
        data = log.to_dict()
        assert data["date"] == "2024-01-01"
        assert len(data["entries"]) == 1
        assert "created_at" in data

    def test_from_dict(self):
        data = {
            "date": "2024-01-02",
            "entries": [{"timestamp": "2024-01-02T00:00:00", "action": "Act", "details": "Det"}],
            "created_at": "2024-01-02T01:00:00",
        }
        log = DailyLog.from_dict(data)
        assert log.date == "2024-01-02"
        assert len(log.entries) == 1
        assert isinstance(log.entries[0], WorkLogEntry)
        assert log.created_at == "2024-01-02T01:00:00"

    def test_roundtrip(self):
        entry = WorkLogEntry(timestamp="2024-01-03T00:00:00", action="Test", details="Details")
        original = DailyLog(date="2024-01-03", entries=[entry])
        roundtrip = DailyLog.from_dict(original.to_dict())
        assert roundtrip.date == original.date
        assert len(roundtrip.entries) == 1
        assert roundtrip.entries[0].action == entry.action


class TestGitState:
    """Tests for GitState dataclass."""

    def test_has_required_fields(self):
        state = GitState(
            branch="main",
            commit_hash="abc123",
            is_clean=True,
            uncommitted_files=[],
        )
        assert state.branch == "main"
        assert state.commit_hash == "abc123"
        assert state.is_clean is True

    def test_to_dict(self):
        state = GitState(
            branch="feature",
            commit_hash="def456",
            is_clean=False,
            uncommitted_files=["file.py"],
        )
        data = state.to_dict()
        assert data["branch"] == "feature"
        assert data["uncommitted_files"] == ["file.py"]

    def test_from_dict(self):
        data = {
            "branch": "develop",
            "commit_hash": "ghi789",
            "is_clean": True,
            "uncommitted_files": [],
        }
        state = GitState.from_dict(data)
        assert state.branch == "develop"
        assert state.commit_hash == "ghi789"

    def test_roundtrip(self):
        original = GitState(
            branch="test",
            commit_hash="xyz",
            is_clean=False,
            uncommitted_files=["a.py", "b.py"],
        )
        roundtrip = GitState.from_dict(original.to_dict())
        assert roundtrip.branch == original.branch
        assert roundtrip.uncommitted_files == original.uncommitted_files


class TestFeatureSummary:
    """Tests for FeatureSummary dataclass."""

    def test_has_required_fields(self):
        summary = FeatureSummary(
            id="feat-1",
            name="Test Feature",
            phase="implementing",
            progress=0.5,
        )
        assert summary.id == "feat-1"
        assert summary.name == "Test Feature"
        assert summary.phase == "implementing"
        assert summary.progress == 0.5

    def test_has_issues_field(self):
        summary = FeatureSummary(
            id="feat-1",
            name="Test",
            phase="done",
            progress=1.0,
            total_issues=5,
            completed_issues=5,
        )
        assert summary.total_issues == 5
        assert summary.completed_issues == 5

    def test_to_dict(self):
        summary = FeatureSummary(
            id="feat-1",
            name="Test",
            phase="spec",
            progress=0.25,
        )
        data = summary.to_dict()
        assert data["id"] == "feat-1"
        assert data["progress"] == 0.25

    def test_from_dict(self):
        data = {
            "id": "feat-2",
            "name": "Feature 2",
            "phase": "implementing",
            "progress": 0.75,
            "total_issues": 4,
            "completed_issues": 3,
        }
        summary = FeatureSummary.from_dict(data)
        assert summary.id == "feat-2"
        assert summary.total_issues == 4

    def test_roundtrip(self):
        original = FeatureSummary(
            id="feat-3",
            name="Feature 3",
            phase="done",
            progress=1.0,
            total_issues=10,
            completed_issues=10,
        )
        roundtrip = FeatureSummary.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.progress == original.progress


class TestBugSummary:
    """Tests for BugSummary dataclass."""

    def test_has_required_fields(self):
        summary = BugSummary(
            id="bug-1",
            description="Test bug",
            phase="analyzing",
            severity="high",
        )
        assert summary.id == "bug-1"
        assert summary.description == "Test bug"
        assert summary.phase == "analyzing"
        assert summary.severity == "high"

    def test_to_dict(self):
        summary = BugSummary(
            id="bug-1",
            description="Bug desc",
            phase="fixed",
            severity="low",
        )
        data = summary.to_dict()
        assert data["id"] == "bug-1"
        assert data["severity"] == "low"

    def test_from_dict(self):
        data = {
            "id": "bug-2",
            "description": "Another bug",
            "phase": "planned",
            "severity": "medium",
        }
        summary = BugSummary.from_dict(data)
        assert summary.id == "bug-2"
        assert summary.phase == "planned"

    def test_roundtrip(self):
        original = BugSummary(
            id="bug-3",
            description="Third bug",
            phase="fixing",
            severity="critical",
        )
        roundtrip = BugSummary.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.severity == original.severity


class TestPRDSummary:
    """Tests for PRDSummary dataclass."""

    def test_has_required_fields(self):
        summary = PRDSummary(
            id="prd-1",
            title="Test PRD",
            status="draft",
        )
        assert summary.id == "prd-1"
        assert summary.title == "Test PRD"
        assert summary.status == "draft"

    def test_to_dict(self):
        summary = PRDSummary(id="prd-1", title="PRD", status="approved")
        data = summary.to_dict()
        assert data["id"] == "prd-1"
        assert data["status"] == "approved"

    def test_from_dict(self):
        data = {"id": "prd-2", "title": "PRD 2", "status": "pending"}
        summary = PRDSummary.from_dict(data)
        assert summary.id == "prd-2"
        assert summary.title == "PRD 2"

    def test_roundtrip(self):
        original = PRDSummary(id="prd-3", title="PRD 3", status="done")
        roundtrip = PRDSummary.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.status == original.status


class TestSpecSummary:
    """Tests for SpecSummary dataclass."""

    def test_has_required_fields(self):
        summary = SpecSummary(
            id="spec-1",
            feature_id="feat-1",
            status="approved",
            score=0.9,
        )
        assert summary.id == "spec-1"
        assert summary.feature_id == "feat-1"
        assert summary.status == "approved"
        assert summary.score == 0.9

    def test_to_dict(self):
        summary = SpecSummary(id="spec-1", feature_id="feat-1", status="draft", score=0.5)
        data = summary.to_dict()
        assert data["id"] == "spec-1"
        assert data["score"] == 0.5

    def test_from_dict(self):
        data = {"id": "spec-2", "feature_id": "feat-2", "status": "pending", "score": 0.75}
        summary = SpecSummary.from_dict(data)
        assert summary.id == "spec-2"
        assert summary.score == 0.75

    def test_roundtrip(self):
        original = SpecSummary(id="spec-3", feature_id="feat-3", status="done", score=0.95)
        roundtrip = SpecSummary.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.score == original.score


class TestTestState:
    """Tests for TestState dataclass."""

    def test_has_required_fields(self):
        state = TestState(
            total=10,
            passed=8,
            failed=2,
            skipped=0,
            last_run="2024-01-01T00:00:00",
        )
        assert state.total == 10
        assert state.passed == 8
        assert state.failed == 2

    def test_to_dict(self):
        state = TestState(total=5, passed=5, failed=0, skipped=0, last_run="2024-01-01T00:00:00")
        data = state.to_dict()
        assert data["total"] == 5
        assert data["passed"] == 5

    def test_from_dict(self):
        data = {"total": 20, "passed": 18, "failed": 1, "skipped": 1, "last_run": "2024-01-02T00:00:00"}
        state = TestState.from_dict(data)
        assert state.total == 20
        assert state.skipped == 1

    def test_roundtrip(self):
        original = TestState(total=15, passed=10, failed=3, skipped=2, last_run="2024-01-03T00:00:00")
        roundtrip = TestState.from_dict(original.to_dict())
        assert roundtrip.total == original.total
        assert roundtrip.failed == original.failed


class TestGitHubState:
    """Tests for GitHubState dataclass."""

    def test_has_required_fields(self):
        state = GitHubState(
            open_prs=5,
            open_issues=10,
            pending_reviews=[],
        )
        assert state.open_prs == 5
        assert state.open_issues == 10
        assert state.pending_reviews == []

    def test_to_dict(self):
        state = GitHubState(open_prs=3, open_issues=7, pending_reviews=["pr-1"])
        data = state.to_dict()
        assert data["open_prs"] == 3
        assert data["pending_reviews"] == ["pr-1"]

    def test_from_dict(self):
        data = {"open_prs": 2, "open_issues": 5, "pending_reviews": ["pr-1", "pr-2"]}
        state = GitHubState.from_dict(data)
        assert state.open_prs == 2
        assert len(state.pending_reviews) == 2

    def test_roundtrip(self):
        original = GitHubState(open_prs=4, open_issues=8, pending_reviews=["pr-3"])
        roundtrip = GitHubState.from_dict(original.to_dict())
        assert roundtrip.open_prs == original.open_prs
        assert roundtrip.pending_reviews == original.pending_reviews


class TestInterruptedSession:
    """Tests for InterruptedSession dataclass."""

    def test_has_required_fields(self):
        session = InterruptedSession(
            session_id="sess-1",
            feature_id="feat-1",
            phase="implementing",
            interrupted_at="2024-01-01T00:00:00",
            reason="timeout",
        )
        assert session.session_id == "sess-1"
        assert session.feature_id == "feat-1"
        assert session.reason == "timeout"

    def test_has_recovery_data(self):
        session = InterruptedSession(
            session_id="sess-1",
            feature_id="feat-1",
            phase="spec",
            interrupted_at="2024-01-01T00:00:00",
            reason="error",
            recovery_data={"key": "value"},
        )
        assert session.recovery_data == {"key": "value"}

    def test_to_dict(self):
        session = InterruptedSession(
            session_id="sess-1",
            feature_id="feat-1",
            phase="done",
            interrupted_at="2024-01-01T00:00:00",
            reason="manual",
        )
        data = session.to_dict()
        assert data["session_id"] == "sess-1"
        assert data["reason"] == "manual"

    def test_from_dict(self):
        data = {
            "session_id": "sess-2",
            "feature_id": "feat-2",
            "phase": "implementing",
            "interrupted_at": "2024-01-02T00:00:00",
            "reason": "crash",
            "recovery_data": {"state": "partial"},
        }
        session = InterruptedSession.from_dict(data)
        assert session.session_id == "sess-2"
        assert session.recovery_data == {"state": "partial"}

    def test_roundtrip(self):
        original = InterruptedSession(
            session_id="sess-3",
            feature_id="feat-3",
            phase="spec",
            interrupted_at="2024-01-03T00:00:00",
            reason="user",
            recovery_data={"foo": "bar"},
        )
        roundtrip = InterruptedSession.from_dict(original.to_dict())
        assert roundtrip.session_id == original.session_id
        assert roundtrip.recovery_data == original.recovery_data


class TestRepoStateSnapshot:
    """Tests for RepoStateSnapshot dataclass."""

    def test_has_required_fields(self):
        snapshot = RepoStateSnapshot(
            timestamp="2024-01-01T00:00:00",
            git=GitState(branch="main", commit_hash="abc", is_clean=True, uncommitted_files=[]),
            features=[],
            bugs=[],
            prds=[],
            specs=[],
            tests=TestState(total=0, passed=0, failed=0, skipped=0, last_run=""),
            github=GitHubState(open_prs=0, open_issues=0, pending_reviews=[]),
            interrupted_sessions=[],
        )
        assert snapshot.timestamp == "2024-01-01T00:00:00"
        assert snapshot.git.branch == "main"

    def test_to_dict_with_nested(self):
        git = GitState(branch="main", commit_hash="abc", is_clean=True, uncommitted_files=[])
        feature = FeatureSummary(id="f1", name="F1", phase="done", progress=1.0)
        tests = TestState(total=10, passed=10, failed=0, skipped=0, last_run="2024-01-01T00:00:00")
        github = GitHubState(open_prs=1, open_issues=2, pending_reviews=[])
        snapshot = RepoStateSnapshot(
            timestamp="2024-01-01T00:00:00",
            git=git,
            features=[feature],
            bugs=[],
            prds=[],
            specs=[],
            tests=tests,
            github=github,
            interrupted_sessions=[],
        )
        data = snapshot.to_dict()
        assert data["timestamp"] == "2024-01-01T00:00:00"
        assert data["git"]["branch"] == "main"
        assert len(data["features"]) == 1
        assert data["features"][0]["id"] == "f1"

    def test_from_dict_with_nested(self):
        data = {
            "timestamp": "2024-01-02T00:00:00",
            "git": {"branch": "develop", "commit_hash": "xyz", "is_clean": False, "uncommitted_files": ["f.py"]},
            "features": [{"id": "f2", "name": "F2", "phase": "implementing", "progress": 0.5}],
            "bugs": [{"id": "b1", "description": "Bug", "phase": "fixing", "severity": "high"}],
            "prds": [],
            "specs": [],
            "tests": {"total": 5, "passed": 4, "failed": 1, "skipped": 0, "last_run": "2024-01-02T00:00:00"},
            "github": {"open_prs": 2, "open_issues": 3, "pending_reviews": []},
            "interrupted_sessions": [],
        }
        snapshot = RepoStateSnapshot.from_dict(data)
        assert snapshot.git.branch == "develop"
        assert len(snapshot.features) == 1
        assert isinstance(snapshot.features[0], FeatureSummary)
        assert len(snapshot.bugs) == 1
        assert isinstance(snapshot.bugs[0], BugSummary)

    def test_roundtrip(self):
        git = GitState(branch="test", commit_hash="123", is_clean=True, uncommitted_files=[])
        tests = TestState(total=20, passed=19, failed=1, skipped=0, last_run="2024-01-03T00:00:00")
        github = GitHubState(open_prs=3, open_issues=5, pending_reviews=["pr-1"])
        original = RepoStateSnapshot(
            timestamp="2024-01-03T00:00:00",
            git=git,
            features=[],
            bugs=[],
            prds=[],
            specs=[],
            tests=tests,
            github=github,
            interrupted_sessions=[],
        )
        roundtrip = RepoStateSnapshot.from_dict(original.to_dict())
        assert roundtrip.timestamp == original.timestamp
        assert roundtrip.git.branch == original.git.branch
        assert roundtrip.tests.total == original.tests.total


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_has_required_fields(self):
        rec = Recommendation(
            id="rec-1",
            action="Do something",
            rationale="Because reasons",
            priority=1,
        )
        assert rec.id == "rec-1"
        assert rec.action == "Do something"
        assert rec.rationale == "Because reasons"
        assert rec.priority == 1

    def test_has_optional_fields(self):
        rec = Recommendation(
            id="rec-1",
            action="Action",
            rationale="Reason",
            priority=2,
            feature_id="feat-1",
            bug_id="bug-1",
        )
        assert rec.feature_id == "feat-1"
        assert rec.bug_id == "bug-1"

    def test_to_dict(self):
        rec = Recommendation(id="rec-1", action="Act", rationale="Rat", priority=1)
        data = rec.to_dict()
        assert data["id"] == "rec-1"
        assert data["priority"] == 1

    def test_from_dict(self):
        data = {"id": "rec-2", "action": "Act2", "rationale": "Rat2", "priority": 2, "feature_id": "f1"}
        rec = Recommendation.from_dict(data)
        assert rec.id == "rec-2"
        assert rec.feature_id == "f1"

    def test_roundtrip(self):
        original = Recommendation(id="rec-3", action="Act3", rationale="Rat3", priority=3, bug_id="b1")
        roundtrip = Recommendation.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.bug_id == original.bug_id


class TestAttentionItem:
    """Tests for AttentionItem dataclass."""

    def test_has_required_fields(self):
        item = AttentionItem(
            id="att-1",
            type="warning",
            message="Something needs attention",
            severity="medium",
        )
        assert item.id == "att-1"
        assert item.type == "warning"
        assert item.message == "Something needs attention"
        assert item.severity == "medium"

    def test_has_optional_context(self):
        item = AttentionItem(
            id="att-1",
            type="error",
            message="Error occurred",
            severity="high",
            context={"file": "test.py"},
        )
        assert item.context == {"file": "test.py"}

    def test_to_dict(self):
        item = AttentionItem(id="att-1", type="info", message="Info", severity="low")
        data = item.to_dict()
        assert data["id"] == "att-1"
        assert data["type"] == "info"

    def test_from_dict(self):
        data = {"id": "att-2", "type": "warning", "message": "Warn", "severity": "medium", "context": {"k": "v"}}
        item = AttentionItem.from_dict(data)
        assert item.id == "att-2"
        assert item.context == {"k": "v"}

    def test_roundtrip(self):
        original = AttentionItem(id="att-3", type="error", message="Err", severity="high", context={"x": 1})
        roundtrip = AttentionItem.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.context == original.context


class TestStandupReport:
    """Tests for StandupReport dataclass."""

    def test_has_required_fields(self):
        report = StandupReport(
            timestamp="2024-01-01T00:00:00",
            state_snapshot=RepoStateSnapshot(
                timestamp="2024-01-01T00:00:00",
                git=GitState(branch="main", commit_hash="abc", is_clean=True, uncommitted_files=[]),
                features=[],
                bugs=[],
                prds=[],
                specs=[],
                tests=TestState(total=0, passed=0, failed=0, skipped=0, last_run=""),
                github=GitHubState(open_prs=0, open_issues=0, pending_reviews=[]),
                interrupted_sessions=[],
            ),
            recommendations=[],
            attention_items=[],
            suggested_goals=[],
        )
        assert report.timestamp == "2024-01-01T00:00:00"
        assert report.recommendations == []

    def test_to_dict_with_nested(self):
        git = GitState(branch="main", commit_hash="abc", is_clean=True, uncommitted_files=[])
        tests = TestState(total=0, passed=0, failed=0, skipped=0, last_run="")
        github = GitHubState(open_prs=0, open_issues=0, pending_reviews=[])
        snapshot = RepoStateSnapshot(
            timestamp="2024-01-01T00:00:00",
            git=git,
            features=[],
            bugs=[],
            prds=[],
            specs=[],
            tests=tests,
            github=github,
            interrupted_sessions=[],
        )
        rec = Recommendation(id="r1", action="Act", rationale="Rat", priority=1)
        attention = AttentionItem(id="a1", type="warn", message="Msg", severity="low")
        goal = DailyGoal(id="g1", description="Goal", priority=1)
        report = StandupReport(
            timestamp="2024-01-01T00:00:00",
            state_snapshot=snapshot,
            recommendations=[rec],
            attention_items=[attention],
            suggested_goals=[goal],
        )
        data = report.to_dict()
        assert data["timestamp"] == "2024-01-01T00:00:00"
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["id"] == "r1"
        assert len(data["attention_items"]) == 1
        assert len(data["suggested_goals"]) == 1

    def test_from_dict_with_nested(self):
        data = {
            "timestamp": "2024-01-02T00:00:00",
            "state_snapshot": {
                "timestamp": "2024-01-02T00:00:00",
                "git": {"branch": "main", "commit_hash": "xyz", "is_clean": True, "uncommitted_files": []},
                "features": [],
                "bugs": [],
                "prds": [],
                "specs": [],
                "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "last_run": ""},
                "github": {"open_prs": 0, "open_issues": 0, "pending_reviews": []},
                "interrupted_sessions": [],
            },
            "recommendations": [{"id": "r2", "action": "Act2", "rationale": "Rat2", "priority": 2}],
            "attention_items": [{"id": "a2", "type": "error", "message": "Err", "severity": "high"}],
            "suggested_goals": [{"id": "g2", "description": "Goal2", "priority": 2, "status": "pending"}],
        }
        report = StandupReport.from_dict(data)
        assert report.timestamp == "2024-01-02T00:00:00"
        assert isinstance(report.state_snapshot, RepoStateSnapshot)
        assert len(report.recommendations) == 1
        assert isinstance(report.recommendations[0], Recommendation)
        assert len(report.attention_items) == 1
        assert isinstance(report.attention_items[0], AttentionItem)
        assert len(report.suggested_goals) == 1
        assert isinstance(report.suggested_goals[0], DailyGoal)

    def test_roundtrip(self):
        git = GitState(branch="test", commit_hash="123", is_clean=True, uncommitted_files=[])
        tests = TestState(total=10, passed=10, failed=0, skipped=0, last_run="2024-01-03T00:00:00")
        github = GitHubState(open_prs=1, open_issues=2, pending_reviews=[])
        snapshot = RepoStateSnapshot(
            timestamp="2024-01-03T00:00:00",
            git=git,
            features=[],
            bugs=[],
            prds=[],
            specs=[],
            tests=tests,
            github=github,
            interrupted_sessions=[],
        )
        original = StandupReport(
            timestamp="2024-01-03T00:00:00",
            state_snapshot=snapshot,
            recommendations=[],
            attention_items=[],
            suggested_goals=[],
        )
        roundtrip = StandupReport.from_dict(original.to_dict())
        assert roundtrip.timestamp == original.timestamp
        assert roundtrip.state_snapshot.git.branch == original.state_snapshot.git.branch


class TestCheckpointEvent:
    """Tests for CheckpointEvent dataclass."""

    def test_has_required_fields(self):
        event = CheckpointEvent(
            id="cp-1",
            timestamp="2024-01-01T00:00:00",
            trigger=CheckpointTrigger.MANUAL,
            summary="Manual checkpoint",
        )
        assert event.id == "cp-1"
        assert event.timestamp == "2024-01-01T00:00:00"
        assert event.trigger == CheckpointTrigger.MANUAL
        assert event.summary == "Manual checkpoint"

    def test_has_optional_fields(self):
        event = CheckpointEvent(
            id="cp-1",
            timestamp="2024-01-01T00:00:00",
            trigger=CheckpointTrigger.ERROR,
            summary="Error checkpoint",
            goal_id="g1",
            error_details="Something failed",
            state_data={"key": "value"},
        )
        assert event.goal_id == "g1"
        assert event.error_details == "Something failed"
        assert event.state_data == {"key": "value"}

    def test_to_dict(self):
        event = CheckpointEvent(
            id="cp-1",
            timestamp="2024-01-01T00:00:00",
            trigger=CheckpointTrigger.GOAL_COMPLETED,
            summary="Goal done",
            goal_id="g1",
        )
        data = event.to_dict()
        assert data["id"] == "cp-1"
        assert data["trigger"] == "goal_completed"
        assert data["goal_id"] == "g1"

    def test_from_dict(self):
        data = {
            "id": "cp-2",
            "timestamp": "2024-01-02T00:00:00",
            "trigger": "time_based",
            "summary": "Time checkpoint",
            "state_data": {"x": 1},
        }
        event = CheckpointEvent.from_dict(data)
        assert event.id == "cp-2"
        assert event.trigger == CheckpointTrigger.TIME_BASED
        assert event.state_data == {"x": 1}

    def test_roundtrip(self):
        original = CheckpointEvent(
            id="cp-3",
            timestamp="2024-01-03T00:00:00",
            trigger=CheckpointTrigger.PHASE_TRANSITION,
            summary="Phase change",
            state_data={"phase": "new"},
        )
        roundtrip = CheckpointEvent.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert roundtrip.trigger == original.trigger
        assert roundtrip.state_data == original.state_data


class TestAutopilotSession:
    """Tests for AutopilotSession dataclass."""

    def test_has_required_fields(self):
        session = AutopilotSession(
            id="auto-1",
            started_at="2024-01-01T00:00:00",
            goals=[],
            checkpoints=[],
            work_log=[],
        )
        assert session.id == "auto-1"
        assert session.started_at == "2024-01-01T00:00:00"
        assert session.goals == []
        assert session.checkpoints == []
        assert session.work_log == []

    def test_has_optional_fields(self):
        session = AutopilotSession(
            id="auto-1",
            started_at="2024-01-01T00:00:00",
            goals=[],
            checkpoints=[],
            work_log=[],
            ended_at="2024-01-01T01:00:00",
            status="completed",
            final_summary="All done",
        )
        assert session.ended_at == "2024-01-01T01:00:00"
        assert session.status == "completed"
        assert session.final_summary == "All done"

    def test_to_dict_with_nested(self):
        goal = DailyGoal(id="g1", description="Goal", priority=1)
        checkpoint = CheckpointEvent(
            id="cp1",
            timestamp="2024-01-01T00:30:00",
            trigger=CheckpointTrigger.MANUAL,
            summary="Check",
        )
        entry = WorkLogEntry(timestamp="2024-01-01T00:15:00", action="Act", details="Det")
        session = AutopilotSession(
            id="auto-1",
            started_at="2024-01-01T00:00:00",
            goals=[goal],
            checkpoints=[checkpoint],
            work_log=[entry],
        )
        data = session.to_dict()
        assert data["id"] == "auto-1"
        assert len(data["goals"]) == 1
        assert data["goals"][0]["id"] == "g1"
        assert len(data["checkpoints"]) == 1
        assert data["checkpoints"][0]["trigger"] == "manual"
        assert len(data["work_log"]) == 1

    def test_from_dict_with_nested(self):
        data = {
            "id": "auto-2",
            "started_at": "2024-01-02T00:00:00",
            "goals": [{"id": "g2", "description": "Goal2", "priority": 2, "status": "done"}],
            "checkpoints": [{"id": "cp2", "timestamp": "2024-01-02T00:30:00", "trigger": "error", "summary": "Err"}],
            "work_log": [{"timestamp": "2024-01-02T00:15:00", "action": "Act2", "details": "Det2"}],
            "ended_at": "2024-01-02T01:00:00",
            "status": "failed",
        }
        session = AutopilotSession.from_dict(data)
        assert session.id == "auto-2"
        assert len(session.goals) == 1
        assert isinstance(session.goals[0], DailyGoal)
        assert session.goals[0].status == GoalStatus.DONE
        assert len(session.checkpoints) == 1
        assert isinstance(session.checkpoints[0], CheckpointEvent)
        assert session.checkpoints[0].trigger == CheckpointTrigger.ERROR
        assert session.status == "failed"

    def test_roundtrip(self):
        goal = DailyGoal(id="g3", description="Goal3", priority=3, status=GoalStatus.IN_PROGRESS)
        checkpoint = CheckpointEvent(
            id="cp3",
            timestamp="2024-01-03T00:30:00",
            trigger=CheckpointTrigger.USER_INTERRUPT,
            summary="User stop",
        )
        original = AutopilotSession(
            id="auto-3",
            started_at="2024-01-03T00:00:00",
            goals=[goal],
            checkpoints=[checkpoint],
            work_log=[],
            status="running",
        )
        roundtrip = AutopilotSession.from_dict(original.to_dict())
        assert roundtrip.id == original.id
        assert len(roundtrip.goals) == 1
        assert roundtrip.goals[0].status == original.goals[0].status
        assert len(roundtrip.checkpoints) == 1
        assert roundtrip.checkpoints[0].trigger == original.checkpoints[0].trigger
        assert roundtrip.status == original.status