"""Tests for AutopilotRunner component."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from swarm_attack.chief_of_staff.autopilot import (
    AutopilotRunner,
    AutopilotSession,
    AutopilotSessionStore,
    AutopilotStatus,
    StopTrigger,
    GoalResult,
)


class TestAutopilotSession:
    """Tests for AutopilotSession dataclass."""

    def test_has_from_dict(self):
        assert hasattr(AutopilotSession, 'from_dict')

    def test_has_to_dict(self):
        session = AutopilotSession(
            session_id="test-123",
            goals=[],
            budget_usd=10.0,
            duration_seconds=3600,
        )
        assert hasattr(session, 'to_dict')

    def test_from_dict_creates_instance(self):
        data = {
            "session_id": "test-123",
            "goals": ["goal1", "goal2"],
            "budget_usd": 10.0,
            "duration_seconds": 3600,
            "current_goal_index": 0,
            "status": "running",
            "cost_usd": 0.0,
            "started_at": "2025-01-01T00:00:00",
        }
        session = AutopilotSession.from_dict(data)
        assert isinstance(session, AutopilotSession)
        assert session.session_id == "test-123"
        assert session.goals == ["goal1", "goal2"]
        assert session.budget_usd == 10.0

    def test_to_dict_roundtrip(self):
        original = AutopilotSession(
            session_id="test-456",
            goals=["implement feature", "fix bug"],
            budget_usd=25.0,
            duration_seconds=7200,
            current_goal_index=1,
            status=AutopilotStatus.PAUSED,
            cost_usd=5.5,
        )
        data = original.to_dict()
        roundtrip = AutopilotSession.from_dict(data)
        assert roundtrip.session_id == original.session_id
        assert roundtrip.goals == original.goals
        assert roundtrip.budget_usd == original.budget_usd
        assert roundtrip.current_goal_index == original.current_goal_index

    def test_session_tracks_cost(self):
        session = AutopilotSession(
            session_id="cost-test",
            goals=["goal1"],
            budget_usd=10.0,
            duration_seconds=3600,
            cost_usd=2.5,
        )
        assert session.cost_usd == 2.5

    def test_session_has_stop_trigger(self):
        session = AutopilotSession(
            session_id="trigger-test",
            goals=["goal1"],
            budget_usd=10.0,
            duration_seconds=3600,
            stop_trigger=StopTrigger(until_time="18:00"),
        )
        assert session.stop_trigger is not None
        assert session.stop_trigger.until_time == "18:00"


class TestAutopilotStatus:
    """Tests for AutopilotStatus enum."""

    def test_has_running_status(self):
        assert AutopilotStatus.RUNNING.value == "running"

    def test_has_paused_status(self):
        assert AutopilotStatus.PAUSED.value == "paused"

    def test_has_completed_status(self):
        assert AutopilotStatus.COMPLETED.value == "completed"

    def test_has_aborted_status(self):
        assert AutopilotStatus.ABORTED.value == "aborted"


class TestStopTrigger:
    """Tests for StopTrigger dataclass."""

    def test_has_from_dict(self):
        assert hasattr(StopTrigger, 'from_dict')

    def test_has_to_dict(self):
        trigger = StopTrigger()
        assert hasattr(trigger, 'to_dict')

    def test_until_time_trigger(self):
        trigger = StopTrigger(until_time="17:00")
        assert trigger.until_time == "17:00"

    def test_from_dict_creates_instance(self):
        data = {"until_time": "18:30"}
        trigger = StopTrigger.from_dict(data)
        assert trigger.until_time == "18:30"

    def test_to_dict_roundtrip(self):
        original = StopTrigger(until_time="09:00")
        roundtrip = StopTrigger.from_dict(original.to_dict())
        assert roundtrip.until_time == original.until_time


class TestAutopilotSessionStore:
    """Tests for AutopilotSessionStore persistence."""

    def test_save_and_load_session(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        session = AutopilotSession(
            session_id="persist-test",
            goals=["goal1", "goal2"],
            budget_usd=15.0,
            duration_seconds=1800,
        )
        store.save(session)
        loaded = store.load("persist-test")
        assert loaded is not None
        assert loaded.session_id == "persist-test"
        assert loaded.goals == ["goal1", "goal2"]

    def test_load_nonexistent_returns_none(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        loaded = store.load("does-not-exist")
        assert loaded is None

    def test_list_sessions(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        session1 = AutopilotSession(
            session_id="session-1",
            goals=["goal1"],
            budget_usd=10.0,
            duration_seconds=3600,
        )
        session2 = AutopilotSession(
            session_id="session-2",
            goals=["goal2"],
            budget_usd=20.0,
            duration_seconds=7200,
        )
        store.save(session1)
        store.save(session2)
        sessions = store.list_sessions()
        assert len(sessions) == 2
        assert "session-1" in sessions
        assert "session-2" in sessions


class TestGoalResult:
    """Tests for GoalResult dataclass."""

    def test_has_success_and_cost(self):
        result = GoalResult(success=True, cost_usd=1.5)
        assert result.success is True
        assert result.cost_usd == 1.5

    def test_has_error_field(self):
        result = GoalResult(success=False, cost_usd=0.5, error="Something failed")
        assert result.error == "Something failed"


class TestAutopilotRunner:
    """Tests for AutopilotRunner execution."""

    def test_start_creates_session(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        with patch.object(runner, '_run_session'):
            session = runner.start(
                goals=["implement feature X"],
                budget_usd=50.0,
                duration_seconds=3600,
            )
        
        assert session is not None
        assert session.goals == ["implement feature X"]
        assert session.budget_usd == 50.0
        assert session.status == AutopilotStatus.RUNNING

    def test_start_with_stop_trigger(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        trigger = StopTrigger(until_time="17:00")
        
        with patch.object(runner, '_run_session'):
            session = runner.start(
                goals=["goal1"],
                budget_usd=10.0,
                duration_seconds=3600,
                stop_trigger=trigger,
            )
        
        assert session.stop_trigger is not None
        assert session.stop_trigger.until_time == "17:00"

    def test_resume_loads_session(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        original = AutopilotSession(
            session_id="resume-test",
            goals=["goal1", "goal2"],
            budget_usd=20.0,
            duration_seconds=3600,
            current_goal_index=1,
            status=AutopilotStatus.PAUSED,
        )
        store.save(original)
        
        runner = AutopilotRunner(session_store=store)
        with patch.object(runner, '_run_session'):
            session = runner.resume("resume-test")
        
        assert session is not None
        assert session.current_goal_index == 1
        assert session.status == AutopilotStatus.RUNNING

    def test_resume_nonexistent_raises(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        with pytest.raises(ValueError, match="Session not found"):
            runner.resume("nonexistent-session")

    def test_resume_completed_session_raises(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        completed = AutopilotSession(
            session_id="completed-session",
            goals=["goal1"],
            budget_usd=10.0,
            duration_seconds=3600,
            status=AutopilotStatus.COMPLETED,
        )
        store.save(completed)
        
        runner = AutopilotRunner(session_store=store)
        with pytest.raises(ValueError, match="not resumable"):
            runner.resume("completed-session")

    def test_execute_goal_routes_to_feature_orchestrator(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_orchestrator = Mock()
        mock_orchestrator.run.return_value = Mock(success=True, cost_usd=2.0)
        
        runner = AutopilotRunner(
            session_store=store,
            feature_orchestrator=mock_orchestrator,
        )
        
        result = runner.execute_goal("implement feature:my-feature")
        
        mock_orchestrator.run.assert_called_once()
        assert result.success is True

    def test_execute_goal_routes_to_bug_orchestrator(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_bug_orchestrator = Mock()
        mock_bug_orchestrator.run.return_value = Mock(success=True, cost_usd=1.5)
        
        runner = AutopilotRunner(
            session_store=store,
            bug_orchestrator=mock_bug_orchestrator,
        )
        
        result = runner.execute_goal("fix bug:bug-123")
        
        mock_bug_orchestrator.run.assert_called_once()
        assert result.success is True

    def test_handle_checkpoint_returns_continue(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        session = AutopilotSession(
            session_id="checkpoint-test",
            goals=["goal1", "goal2"],
            budget_usd=100.0,
            duration_seconds=7200,
            cost_usd=10.0,
        )
        
        result = runner.handle_checkpoint(session, trigger=None)
        assert result == "continue"

    def test_handle_checkpoint_returns_pause_on_budget_exceeded(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        session = AutopilotSession(
            session_id="budget-exceeded",
            goals=["goal1"],
            budget_usd=10.0,
            duration_seconds=3600,
            cost_usd=15.0,  # Exceeded budget
        )
        
        result = runner.handle_checkpoint(session, trigger=None)
        assert result == "pause"

    def test_handle_checkpoint_returns_pause_on_time_trigger(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        session = AutopilotSession(
            session_id="time-trigger",
            goals=["goal1"],
            budget_usd=100.0,
            duration_seconds=3600,
            stop_trigger=StopTrigger(until_time="17:00"),
        )
        
        # Mock current time to be past the trigger time
        with patch('swarm_attack.chief_of_staff.autopilot.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 1, 18, 0, 0)
            mock_dt.strptime = datetime.strptime
            result = runner.handle_checkpoint(session, trigger=session.stop_trigger)
        
        assert result == "pause"

    def test_handle_checkpoint_persists_session(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        session = AutopilotSession(
            session_id="persist-checkpoint",
            goals=["goal1"],
            budget_usd=100.0,
            duration_seconds=3600,
            cost_usd=50.0,  # Budget exceeded, will pause
        )
        
        runner.handle_checkpoint(session, trigger=None)
        
        # Verify session was persisted
        loaded = store.load("persist-checkpoint")
        assert loaded is not None

    def test_get_status_returns_session_info(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        session = AutopilotSession(
            session_id="status-test",
            goals=["goal1", "goal2"],
            budget_usd=20.0,
            duration_seconds=3600,
            current_goal_index=1,
            status=AutopilotStatus.RUNNING,
            cost_usd=5.0,
        )
        store.save(session)
        
        runner = AutopilotRunner(session_store=store)
        status = runner.get_status("status-test")
        
        assert status is not None
        assert status["session_id"] == "status-test"
        assert status["status"] == "running"
        assert status["current_goal_index"] == 1
        assert status["cost_usd"] == 5.0

    def test_get_status_nonexistent_returns_none(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        runner = AutopilotRunner(session_store=store)
        
        status = runner.get_status("nonexistent")
        assert status is None

    def test_checks_triggers_before_each_goal(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_orchestrator = Mock()
        mock_orchestrator.run.return_value = Mock(success=True, cost_usd=1.0)
        
        runner = AutopilotRunner(
            session_store=store,
            feature_orchestrator=mock_orchestrator,
        )
        
        session = AutopilotSession(
            session_id="trigger-check",
            goals=["implement feature:f1", "implement feature:f2"],
            budget_usd=1.5,  # Only enough for ~1 goal
            duration_seconds=3600,
        )
        store.save(session)
        
        # Run the session directly
        runner._run_session(session)
        
        # Should have executed first goal but paused before/after second due to budget
        loaded = store.load("trigger-check")
        assert loaded.status in [AutopilotStatus.PAUSED, AutopilotStatus.COMPLETED]

    def test_tracks_cost_throughout_execution(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_orchestrator = Mock()
        mock_orchestrator.run.side_effect = [
            Mock(success=True, cost_usd=2.0),
            Mock(success=True, cost_usd=3.0),
        ]
        
        runner = AutopilotRunner(
            session_store=store,
            feature_orchestrator=mock_orchestrator,
        )
        
        session = AutopilotSession(
            session_id="cost-tracking",
            goals=["implement feature:f1", "implement feature:f2"],
            budget_usd=100.0,
            duration_seconds=3600,
        )
        store.save(session)
        
        runner._run_session(session)
        
        loaded = store.load("cost-tracking")
        assert loaded.cost_usd == 5.0  # 2.0 + 3.0

    def test_persists_session_after_each_goal(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_orchestrator = Mock()
        mock_orchestrator.run.return_value = Mock(success=True, cost_usd=1.0)
        
        runner = AutopilotRunner(
            session_store=store,
            feature_orchestrator=mock_orchestrator,
        )
        
        session = AutopilotSession(
            session_id="persist-after-goal",
            goals=["implement feature:f1", "implement feature:f2"],
            budget_usd=100.0,
            duration_seconds=3600,
        )
        
        with patch.object(store, 'save', wraps=store.save) as mock_save:
            store.save(session)  # Initial save
            runner._run_session(session)
            
            # Should have saved at least once per goal + initial
            assert mock_save.call_count >= 3


class TestAutopilotRunnerIntegration:
    """Integration tests for full execution flow."""

    def test_full_execution_flow_completes_all_goals(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_orchestrator = Mock()
        mock_orchestrator.run.return_value = Mock(success=True, cost_usd=1.0)
        
        runner = AutopilotRunner(
            session_store=store,
            feature_orchestrator=mock_orchestrator,
        )
        
        session = runner.start(
            goals=["implement feature:f1", "implement feature:f2"],
            budget_usd=100.0,
            duration_seconds=3600,
        )
        
        # After synchronous execution, check final state
        loaded = store.load(session.session_id)
        assert loaded.status == AutopilotStatus.COMPLETED
        assert loaded.current_goal_index == 2

    def test_execution_handles_goal_failure(self, tmp_path):
        store = AutopilotSessionStore(base_path=tmp_path)
        mock_orchestrator = Mock()
        mock_orchestrator.run.side_effect = [
            Mock(success=True, cost_usd=1.0),
            Mock(success=False, cost_usd=0.5, error="Implementation failed"),
        ]
        
        runner = AutopilotRunner(
            session_store=store,
            feature_orchestrator=mock_orchestrator,
        )
        
        session = runner.start(
            goals=["implement feature:f1", "implement feature:f2"],
            budget_usd=100.0,
            duration_seconds=3600,
        )
        
        loaded = store.load(session.session_id)
        # Should continue past failures (but track them)
        assert loaded.current_goal_index >= 1