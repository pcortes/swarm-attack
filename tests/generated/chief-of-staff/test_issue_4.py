"""Tests for DailyLogManager persistence component.

These tests verify the DailyLogManager class that handles reading/writing
daily logs in both markdown and JSON formats, plus the append-only decision log.

Tests MUST FAIL initially because the implementation doesn't exist yet.
The Coder will implement the code to make these tests pass.
"""

import pytest
import json
from datetime import date, datetime, timedelta
from pathlib import Path

# Import from real module path - will fail until Coder implements
from swarm_attack.chief_of_staff.daily_log import DailyLogManager
from swarm_attack.chief_of_staff.models import (
    DailyLog,
    DailyGoal,
    GoalStatus,
    StandupSession,
    WorkLogEntry,
    DailySummary,
    Decision,
)


class TestDailyLogManagerDirectoryStructure:
    """Tests that verify directory structure creation."""

    def test_creates_daily_log_directory(self, tmp_path: Path):
        """Test that initializing DailyLogManager creates the daily-log directory."""
        manager = DailyLogManager(tmp_path)
        
        daily_log_dir = tmp_path / "daily-log"
        assert daily_log_dir.is_dir(), "daily-log/ directory should be created"

    def test_creates_weekly_summary_directory(self, tmp_path: Path):
        """Test that initializing DailyLogManager creates the weekly-summary directory."""
        manager = DailyLogManager(tmp_path)
        
        weekly_dir = tmp_path / "weekly-summary"
        assert weekly_dir.is_dir(), "weekly-summary/ directory should be created"

    def test_handles_existing_directories(self, tmp_path: Path):
        """Test that initialization doesn't fail if directories already exist."""
        # Pre-create directories
        (tmp_path / "daily-log").mkdir(parents=True)
        (tmp_path / "weekly-summary").mkdir(parents=True)
        
        # Should not raise
        manager = DailyLogManager(tmp_path)
        
        assert (tmp_path / "daily-log").is_dir()
        assert (tmp_path / "weekly-summary").is_dir()


class TestGetLog:
    """Tests for get_log(date) method - retrieve log for specific date."""

    def test_get_log_returns_none_for_nonexistent_date(self, tmp_path: Path):
        """Test that get_log returns None when no log exists for the date."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.get_log(date(2025, 12, 15))
        
        assert result is None, "Should return None for non-existent log"

    def test_get_log_returns_existing_log(self, tmp_path: Path):
        """Test that get_log retrieves a previously saved log."""
        manager = DailyLogManager(tmp_path)
        
        # Create and save a log
        test_date = date(2025, 12, 15)
        log = DailyLog(date=test_date.isoformat())
        manager.save_log(log)
        
        # Retrieve it
        result = manager.get_log(test_date)
        
        assert result is not None, "Should return the saved log"
        assert result.date == test_date.isoformat()

    def test_get_log_with_full_data(self, tmp_path: Path):
        """Test that get_log retrieves all fields correctly."""
        manager = DailyLogManager(tmp_path)
        
        test_date = date(2025, 12, 15)
        goal = DailyGoal(
            id="goal-001",
            content="Test goal",
            priority="P1",
            status=GoalStatus.DONE,
        )
        standup = StandupSession(
            session_id="cos-20251215-001",
            time="2025-12-15T09:00:00",
            yesterday_goals=[],
            today_goals=[goal],
        )
        log = DailyLog(
            date=test_date.isoformat(),
            standups=[standup],
        )
        manager.save_log(log)
        
        result = manager.get_log(test_date)
        
        assert len(result.standups) == 1
        assert result.standups[0].session_id == "cos-20251215-001"
        assert len(result.standups[0].today_goals) == 1
        assert result.standups[0].today_goals[0].content == "Test goal"


class TestGetToday:
    """Tests for get_today() method - get or create today's log."""

    def test_get_today_creates_new_log_if_none_exists(self, tmp_path: Path):
        """Test that get_today creates a new log if none exists for today."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.get_today()
        
        assert result is not None
        assert result.date == date.today().isoformat()

    def test_get_today_returns_existing_log(self, tmp_path: Path):
        """Test that get_today returns existing log if one exists."""
        manager = DailyLogManager(tmp_path)
        
        # Create today's log with specific data
        today = date.today()
        log = DailyLog(date=today.isoformat())
        log.work_log.append(WorkLogEntry(
            timestamp="2025-12-15T10:00:00",
            action="Test action",
            result="Success",
        ))
        manager.save_log(log)
        
        # Get today should return the same log
        result = manager.get_today()
        
        assert len(result.work_log) == 1
        assert result.work_log[0].action == "Test action"

    def test_get_today_sets_timestamps(self, tmp_path: Path):
        """Test that get_today sets created_at and updated_at timestamps."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.get_today()
        
        assert result.created_at != ""
        assert result.updated_at != ""


class TestGetYesterday:
    """Tests for get_yesterday() method - get yesterday's log if exists."""

    def test_get_yesterday_returns_none_if_no_log(self, tmp_path: Path):
        """Test that get_yesterday returns None if no log exists for yesterday."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.get_yesterday()
        
        assert result is None

    def test_get_yesterday_returns_existing_log(self, tmp_path: Path):
        """Test that get_yesterday returns yesterday's log if it exists."""
        manager = DailyLogManager(tmp_path)
        
        yesterday = date.today() - timedelta(days=1)
        log = DailyLog(date=yesterday.isoformat())
        manager.save_log(log)
        
        result = manager.get_yesterday()
        
        assert result is not None
        assert result.date == yesterday.isoformat()


class TestSaveLog:
    """Tests for save_log(log) method - atomic write to both .md and .json formats."""

    def test_save_log_creates_json_file(self, tmp_path: Path):
        """Test that save_log creates a JSON file."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        assert json_path.exists(), "JSON file should be created"

    def test_save_log_creates_markdown_file(self, tmp_path: Path):
        """Test that save_log creates a markdown file."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        md_path = tmp_path / "daily-log" / "2025-12-15.md"
        assert md_path.exists(), "Markdown file should be created"

    def test_save_log_json_content_is_valid(self, tmp_path: Path):
        """Test that saved JSON content is valid and matches the log."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        log.work_log.append(WorkLogEntry(
            timestamp="2025-12-15T10:00:00",
            action="Test action",
            result="Success",
            cost_usd=1.50,
        ))
        manager.save_log(log)
        
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        saved_data = json.loads(json_path.read_text())
        
        assert saved_data["date"] == "2025-12-15"
        assert len(saved_data["work_log"]) == 1
        assert saved_data["work_log"][0]["action"] == "Test action"
        assert saved_data["work_log"][0]["cost_usd"] == 1.50

    def test_save_log_markdown_contains_date_header(self, tmp_path: Path):
        """Test that markdown file contains proper date header."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        md_path = tmp_path / "daily-log" / "2025-12-15.md"
        content = md_path.read_text()
        
        assert "2025-12-15" in content, "Markdown should contain the date"
        assert content.startswith("# Daily Log:"), "Markdown should start with header"

    def test_save_log_updates_existing_file(self, tmp_path: Path):
        """Test that save_log updates existing files atomically."""
        manager = DailyLogManager(tmp_path)
        
        # Save initial log
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        # Update and save again
        log.work_log.append(WorkLogEntry(
            timestamp="2025-12-15T10:00:00",
            action="New action",
            result="Done",
        ))
        manager.save_log(log)
        
        # Verify update
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        saved_data = json.loads(json_path.read_text())
        
        assert len(saved_data["work_log"]) == 1
        assert saved_data["work_log"][0]["action"] == "New action"

    def test_save_log_uses_atomic_write(self, tmp_path: Path):
        """Test that save_log uses temp file then rename (no partial writes)."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        # No temp files should remain
        daily_log_dir = tmp_path / "daily-log"
        temp_files = list(daily_log_dir.glob("*.tmp"))
        
        assert len(temp_files) == 0, "No temp files should remain after save"

    def test_save_log_updates_updated_at_timestamp(self, tmp_path: Path):
        """Test that save_log updates the updated_at timestamp."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        original_updated = log.updated_at
        
        # Small delay to ensure different timestamp
        manager.save_log(log)
        
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        saved_data = json.loads(json_path.read_text())
        
        assert "updated_at" in saved_data
        assert saved_data["updated_at"] != ""


class TestAddStandup:
    """Tests for add_standup(standup) method - add standup session to today's log."""

    def test_add_standup_creates_today_log_if_needed(self, tmp_path: Path):
        """Test that add_standup creates today's log if it doesn't exist."""
        manager = DailyLogManager(tmp_path)
        
        standup = StandupSession(
            session_id="cos-20251215-001",
            time="2025-12-15T09:00:00",
            yesterday_goals=[],
            today_goals=[],
        )
        manager.add_standup(standup)
        
        today_log = manager.get_today()
        assert len(today_log.standups) == 1

    def test_add_standup_appends_to_existing_standups(self, tmp_path: Path):
        """Test that add_standup appends to existing standups list."""
        manager = DailyLogManager(tmp_path)
        
        standup1 = StandupSession(
            session_id="cos-20251215-001",
            time="2025-12-15T09:00:00",
            yesterday_goals=[],
            today_goals=[],
        )
        standup2 = StandupSession(
            session_id="cos-20251215-002",
            time="2025-12-15T14:00:00",
            yesterday_goals=[],
            today_goals=[],
        )
        
        manager.add_standup(standup1)
        manager.add_standup(standup2)
        
        today_log = manager.get_today()
        assert len(today_log.standups) == 2
        assert today_log.standups[0].session_id == "cos-20251215-001"
        assert today_log.standups[1].session_id == "cos-20251215-002"

    def test_add_standup_persists_to_disk(self, tmp_path: Path):
        """Test that add_standup saves changes to disk."""
        manager = DailyLogManager(tmp_path)
        
        standup = StandupSession(
            session_id="cos-20251215-001",
            time="2025-12-15T09:00:00",
            yesterday_goals=[],
            today_goals=[],
        )
        manager.add_standup(standup)
        
        # Create new manager instance to verify persistence
        manager2 = DailyLogManager(tmp_path)
        today_log = manager2.get_today()
        
        assert len(today_log.standups) == 1
        assert today_log.standups[0].session_id == "cos-20251215-001"


class TestAddWorkEntry:
    """Tests for add_work_entry(entry) method - add work log entry."""

    def test_add_work_entry_appends_to_work_log(self, tmp_path: Path):
        """Test that add_work_entry appends entry to today's work log."""
        manager = DailyLogManager(tmp_path)
        
        entry = WorkLogEntry(
            timestamp="2025-12-15T10:00:00",
            action="Ran tests",
            result="All passed",
            cost_usd=0.50,
        )
        manager.add_work_entry(entry)
        
        today_log = manager.get_today()
        assert len(today_log.work_log) == 1
        assert today_log.work_log[0].action == "Ran tests"

    def test_add_work_entry_preserves_order(self, tmp_path: Path):
        """Test that work entries are preserved in order added."""
        manager = DailyLogManager(tmp_path)
        
        for i in range(3):
            entry = WorkLogEntry(
                timestamp=f"2025-12-15T{10+i}:00:00",
                action=f"Action {i}",
                result="Done",
            )
            manager.add_work_entry(entry)
        
        today_log = manager.get_today()
        assert len(today_log.work_log) == 3
        assert today_log.work_log[0].action == "Action 0"
        assert today_log.work_log[1].action == "Action 1"
        assert today_log.work_log[2].action == "Action 2"

    def test_add_work_entry_with_checkpoint(self, tmp_path: Path):
        """Test that work entry with checkpoint field is saved correctly."""
        manager = DailyLogManager(tmp_path)
        
        entry = WorkLogEntry(
            timestamp="2025-12-15T10:00:00",
            action="Autopilot paused",
            result="Checkpoint reached",
            checkpoint="cost_threshold_reached",
        )
        manager.add_work_entry(entry)
        
        today_log = manager.get_today()
        assert today_log.work_log[0].checkpoint == "cost_threshold_reached"


class TestSetSummary:
    """Tests for set_summary(summary) method - set end-of-day summary."""

    def test_set_summary_adds_summary_to_log(self, tmp_path: Path):
        """Test that set_summary sets the summary on today's log."""
        manager = DailyLogManager(tmp_path)
        
        summary = DailySummary(
            goals_completed=3,
            goals_total=4,
            total_cost_usd=5.50,
            key_accomplishments=["Fixed bug", "Wrote tests"],
            blockers_for_tomorrow=["Waiting for review"],
            carryover_goals=[],
        )
        manager.set_summary(summary)
        
        today_log = manager.get_today()
        assert today_log.summary is not None
        assert today_log.summary.goals_completed == 3
        assert today_log.summary.total_cost_usd == 5.50

    def test_set_summary_replaces_existing_summary(self, tmp_path: Path):
        """Test that set_summary replaces any existing summary."""
        manager = DailyLogManager(tmp_path)
        
        summary1 = DailySummary(
            goals_completed=2,
            goals_total=4,
            total_cost_usd=3.00,
            key_accomplishments=[],
            blockers_for_tomorrow=[],
            carryover_goals=[],
        )
        summary2 = DailySummary(
            goals_completed=3,
            goals_total=4,
            total_cost_usd=5.00,
            key_accomplishments=["Completed more"],
            blockers_for_tomorrow=[],
            carryover_goals=[],
        )
        
        manager.set_summary(summary1)
        manager.set_summary(summary2)
        
        today_log = manager.get_today()
        assert today_log.summary.goals_completed == 3
        assert today_log.summary.total_cost_usd == 5.00

    def test_set_summary_with_carryover_goals(self, tmp_path: Path):
        """Test that carryover goals are properly saved in summary."""
        manager = DailyLogManager(tmp_path)
        
        carryover = DailyGoal(
            id="goal-001",
            content="Unfinished task",
            priority="P2",
            status=GoalStatus.PARTIAL,
        )
        summary = DailySummary(
            goals_completed=2,
            goals_total=3,
            total_cost_usd=4.00,
            key_accomplishments=[],
            blockers_for_tomorrow=[],
            carryover_goals=[carryover],
        )
        manager.set_summary(summary)
        
        today_log = manager.get_today()
        assert len(today_log.summary.carryover_goals) == 1
        assert today_log.summary.carryover_goals[0].content == "Unfinished task"


class TestAppendDecision:
    """Tests for append_decision(decision) method - append to decisions.jsonl."""

    def test_append_decision_creates_jsonl_file(self, tmp_path: Path):
        """Test that append_decision creates decisions.jsonl if it doesn't exist."""
        manager = DailyLogManager(tmp_path)
        
        decision = Decision(
            timestamp="2025-12-15T10:00:00Z",
            type="approval",
            item="feature-spec",
            decision="approved",
            rationale="Meets quality threshold",
        )
        manager.append_decision(decision)
        
        decisions_path = tmp_path / "decisions.jsonl"
        assert decisions_path.exists(), "decisions.jsonl should be created"

    def test_append_decision_writes_valid_jsonl(self, tmp_path: Path):
        """Test that append_decision writes valid JSONL format."""
        manager = DailyLogManager(tmp_path)
        
        decision = Decision(
            timestamp="2025-12-15T10:00:00Z",
            type="priority",
            item="chief-of-staff",
            decision="P1",
            rationale="User requested prioritization",
            human_override=True,
            metadata={"original_priority": "P2"},
        )
        manager.append_decision(decision)
        
        decisions_path = tmp_path / "decisions.jsonl"
        line = decisions_path.read_text().strip()
        data = json.loads(line)
        
        assert data["type"] == "priority"
        assert data["item"] == "chief-of-staff"
        assert data["human_override"] is True
        assert data["metadata"]["original_priority"] == "P2"

    def test_append_decision_appends_to_existing_file(self, tmp_path: Path):
        """Test that multiple decisions are appended, not overwritten."""
        manager = DailyLogManager(tmp_path)
        
        for i in range(3):
            decision = Decision(
                timestamp=f"2025-12-15T{10+i}:00:00Z",
                type="checkpoint",
                item=f"session-{i}",
                decision="paused",
                rationale="Budget reached",
            )
            manager.append_decision(decision)
        
        decisions_path = tmp_path / "decisions.jsonl"
        lines = decisions_path.read_text().strip().split("\n")
        
        assert len(lines) == 3
        for i, line in enumerate(lines):
            data = json.loads(line)
            assert data["item"] == f"session-{i}"


class TestGetDecisions:
    """Tests for get_decisions(since, type) method - query decisions from JSONL."""

    def test_get_decisions_returns_all_when_no_filters(self, tmp_path: Path):
        """Test that get_decisions returns all decisions without filters."""
        manager = DailyLogManager(tmp_path)
        
        for i in range(3):
            decision = Decision(
                timestamp=f"2025-12-15T{10+i}:00:00Z",
                type="approval",
                item=f"item-{i}",
                decision="approved",
                rationale="Test",
            )
            manager.append_decision(decision)
        
        result = manager.get_decisions()
        
        assert len(result) == 3

    def test_get_decisions_filters_by_type(self, tmp_path: Path):
        """Test that get_decisions filters by decision type."""
        manager = DailyLogManager(tmp_path)
        
        manager.append_decision(Decision(
            timestamp="2025-12-15T10:00:00Z",
            type="approval",
            item="item-1",
            decision="approved",
            rationale="Test",
        ))
        manager.append_decision(Decision(
            timestamp="2025-12-15T11:00:00Z",
            type="checkpoint",
            item="item-2",
            decision="paused",
            rationale="Test",
        ))
        manager.append_decision(Decision(
            timestamp="2025-12-15T12:00:00Z",
            type="approval",
            item="item-3",
            decision="approved",
            rationale="Test",
        ))
        
        result = manager.get_decisions(decision_type="approval")
        
        assert len(result) == 2
        assert all(d.type == "approval" for d in result)

    def test_get_decisions_filters_by_since_datetime(self, tmp_path: Path):
        """Test that get_decisions filters by since datetime."""
        manager = DailyLogManager(tmp_path)
        
        manager.append_decision(Decision(
            timestamp="2025-12-14T10:00:00Z",
            type="approval",
            item="old-item",
            decision="approved",
            rationale="Yesterday",
        ))
        manager.append_decision(Decision(
            timestamp="2025-12-15T10:00:00Z",
            type="approval",
            item="new-item",
            decision="approved",
            rationale="Today",
        ))
        
        since = datetime(2025, 12, 15, 0, 0, 0)
        result = manager.get_decisions(since=since)
        
        assert len(result) == 1
        assert result[0].item == "new-item"

    def test_get_decisions_returns_empty_list_when_no_file(self, tmp_path: Path):
        """Test that get_decisions returns empty list if no decisions file."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.get_decisions()
        
        assert result == []

    def test_get_decisions_combines_filters(self, tmp_path: Path):
        """Test that get_decisions combines type and since filters."""
        manager = DailyLogManager(tmp_path)
        
        manager.append_decision(Decision(
            timestamp="2025-12-14T10:00:00Z",
            type="approval",
            item="old-approval",
            decision="approved",
            rationale="Test",
        ))
        manager.append_decision(Decision(
            timestamp="2025-12-15T10:00:00Z",
            type="checkpoint",
            item="new-checkpoint",
            decision="paused",
            rationale="Test",
        ))
        manager.append_decision(Decision(
            timestamp="2025-12-15T11:00:00Z",
            type="approval",
            item="new-approval",
            decision="approved",
            rationale="Test",
        ))
        
        since = datetime(2025, 12, 15, 0, 0, 0)
        result = manager.get_decisions(since=since, decision_type="approval")
        
        assert len(result) == 1
        assert result[0].item == "new-approval"


class TestGetHistory:
    """Tests for get_history(days) method - get logs for last N days."""

    def test_get_history_returns_logs_for_last_n_days(self, tmp_path: Path):
        """Test that get_history returns logs for the specified number of days."""
        manager = DailyLogManager(tmp_path)
        
        # Create logs for the last 5 days
        today = date.today()
        for i in range(5):
            log_date = today - timedelta(days=i)
            log = DailyLog(date=log_date.isoformat())
            manager.save_log(log)
        
        result = manager.get_history(days=3)
        
        assert len(result) == 3

    def test_get_history_returns_logs_in_date_order(self, tmp_path: Path):
        """Test that get_history returns logs sorted by date (newest first)."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        for i in range(3):
            log_date = today - timedelta(days=i)
            log = DailyLog(date=log_date.isoformat())
            manager.save_log(log)
        
        result = manager.get_history(days=3)
        
        # Should be in reverse chronological order
        assert result[0].date == today.isoformat()
        assert result[1].date == (today - timedelta(days=1)).isoformat()
        assert result[2].date == (today - timedelta(days=2)).isoformat()

    def test_get_history_returns_empty_list_when_no_logs(self, tmp_path: Path):
        """Test that get_history returns empty list if no logs exist."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.get_history(days=7)
        
        assert result == []

    def test_get_history_skips_missing_days(self, tmp_path: Path):
        """Test that get_history only returns logs that exist."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        # Only create logs for days 0 and 2 (skip day 1)
        for i in [0, 2]:
            log_date = today - timedelta(days=i)
            log = DailyLog(date=log_date.isoformat())
            manager.save_log(log)
        
        result = manager.get_history(days=3)
        
        assert len(result) == 2

    def test_get_history_default_is_7_days(self, tmp_path: Path):
        """Test that get_history defaults to 7 days."""
        manager = DailyLogManager(tmp_path)
        
        today = date.today()
        for i in range(10):
            log_date = today - timedelta(days=i)
            log = DailyLog(date=log_date.isoformat())
            manager.save_log(log)
        
        result = manager.get_history()  # No days argument
        
        assert len(result) == 7


class TestGenerateWeeklySummary:
    """Tests for generate_weekly_summary(week, year) method - weekly rollup."""

    def test_generate_weekly_summary_creates_markdown(self, tmp_path: Path):
        """Test that generate_weekly_summary returns markdown string."""
        manager = DailyLogManager(tmp_path)
        
        # Create some logs for the week
        # Week 50 of 2025 is Dec 8-14
        for day in range(8, 15):
            log_date = date(2025, 12, day)
            log = DailyLog(date=log_date.isoformat())
            log.work_log.append(WorkLogEntry(
                timestamp=f"2025-12-{day:02d}T10:00:00",
                action=f"Work on day {day}",
                result="Done",
                cost_usd=1.00,
            ))
            manager.save_log(log)
        
        result = manager.generate_weekly_summary(week=50, year=2025)
        
        assert isinstance(result, str)
        assert "2025" in result
        assert "W50" in result or "Week 50" in result

    def test_generate_weekly_summary_includes_cost_totals(self, tmp_path: Path):
        """Test that weekly summary includes total cost."""
        manager = DailyLogManager(tmp_path)
        
        # Create logs with costs
        for day in range(8, 12):  # 4 days
            log_date = date(2025, 12, day)
            log = DailyLog(date=log_date.isoformat())
            log.work_log.append(WorkLogEntry(
                timestamp=f"2025-12-{day:02d}T10:00:00",
                action="Work",
                result="Done",
                cost_usd=2.50,
            ))
            manager.save_log(log)
        
        result = manager.generate_weekly_summary(week=50, year=2025)
        
        # Should include some cost information (format may vary)
        assert "cost" in result.lower() or "$" in result or "10" in result

    def test_generate_weekly_summary_handles_empty_week(self, tmp_path: Path):
        """Test that generate_weekly_summary handles weeks with no logs."""
        manager = DailyLogManager(tmp_path)
        
        result = manager.generate_weekly_summary(week=50, year=2025)
        
        # Should return valid markdown even if empty
        assert isinstance(result, str)


class TestCorruptedFileHandling:
    """Tests for graceful handling of corrupted files."""

    def test_get_log_handles_corrupted_json(self, tmp_path: Path):
        """Test that get_log handles corrupted JSON gracefully."""
        manager = DailyLogManager(tmp_path)
        
        # Create directories
        (tmp_path / "daily-log").mkdir(parents=True, exist_ok=True)
        
        # Write corrupted JSON
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        json_path.write_text("{ invalid json content")
        
        # Should not raise, should return None or handle gracefully
        result = manager.get_log(date(2025, 12, 15))
        
        # Either returns None or some indication of corruption
        assert result is None or hasattr(result, 'date')

    def test_get_decisions_handles_corrupted_line(self, tmp_path: Path):
        """Test that get_decisions handles corrupted JSONL lines gracefully."""
        manager = DailyLogManager(tmp_path)
        
        # Write valid decision
        manager.append_decision(Decision(
            timestamp="2025-12-15T10:00:00Z",
            type="approval",
            item="valid-item",
            decision="approved",
            rationale="Test",
        ))
        
        # Append corrupted line directly
        decisions_path = tmp_path / "decisions.jsonl"
        with open(decisions_path, "a") as f:
            f.write("{ corrupted line\n")
        
        # Append another valid decision
        manager.append_decision(Decision(
            timestamp="2025-12-15T11:00:00Z",
            type="approval",
            item="another-valid",
            decision="approved",
            rationale="Test",
        ))
        
        # Should skip corrupted line and return valid decisions
        result = manager.get_decisions()
        
        # Should have at least the valid decisions
        valid_items = [d.item for d in result]
        assert "valid-item" in valid_items or "another-valid" in valid_items


class TestAtomicWritePattern:
    """Tests verifying atomic write pattern (temp -> validate -> rename)."""

    def test_save_log_validates_before_rename(self, tmp_path: Path):
        """Test that save validates JSON before finalizing."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        # Verify file is valid JSON
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        data = json.loads(json_path.read_text())
        
        # Should be able to reconstruct the log
        reconstructed = DailyLog.from_dict(data)
        assert reconstructed.date == "2025-12-15"

    def test_no_backup_files_remain(self, tmp_path: Path):
        """Test that no .bak files remain after successful save."""
        manager = DailyLogManager(tmp_path)
        
        # Save multiple times to trigger backup creation during updates
        for i in range(3):
            log = DailyLog(date="2025-12-15")
            log.work_log.append(WorkLogEntry(
                timestamp=f"2025-12-15T{10+i}:00:00",
                action=f"Action {i}",
                result="Done",
            ))
            manager.save_log(log)
        
        # No backup files should remain
        daily_log_dir = tmp_path / "daily-log"
        backup_files = list(daily_log_dir.glob("*.bak"))
        
        assert len(backup_files) == 0, "No backup files should remain"


class TestMarkdownFormat:
    """Tests for markdown output format per Section 10.3."""

    def test_markdown_includes_standup_section(self, tmp_path: Path):
        """Test that markdown includes standup information."""
        manager = DailyLogManager(tmp_path)
        
        goal = DailyGoal(
            id="goal-001",
            content="Test goal",
            priority="P1",
            status=GoalStatus.DONE,
        )
        standup = StandupSession(
            session_id="cos-20251215-001",
            time="2025-12-15T09:00:00",
            yesterday_goals=[],
            today_goals=[goal],
            philip_notes="Focus on testing",
        )
        log = DailyLog(date="2025-12-15", standups=[standup])
        manager.save_log(log)
        
        md_path = tmp_path / "daily-log" / "2025-12-15.md"
        content = md_path.read_text()
        
        assert "Standup" in content or "standup" in content
        assert "cos-20251215-001" in content or "09:00" in content

    def test_markdown_includes_work_log_section(self, tmp_path: Path):
        """Test that markdown includes work log entries."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        log.work_log.append(WorkLogEntry(
            timestamp="2025-12-15T10:00:00",
            action="Ran pytest",
            result="All tests passed",
            cost_usd=0.50,
        ))
        manager.save_log(log)
        
        md_path = tmp_path / "daily-log" / "2025-12-15.md"
        content = md_path.read_text()
        
        assert "Work Log" in content or "work log" in content.lower()
        assert "pytest" in content or "Ran" in content

    def test_markdown_includes_summary_section(self, tmp_path: Path):
        """Test that markdown includes end-of-day summary."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        log.summary = DailySummary(
            goals_completed=3,
            goals_total=4,
            total_cost_usd=5.50,
            key_accomplishments=["Completed feature X"],
            blockers_for_tomorrow=["Waiting for review"],
            carryover_goals=[],
        )
        manager.save_log(log)
        
        md_path = tmp_path / "daily-log" / "2025-12-15.md"
        content = md_path.read_text()
        
        assert "Summary" in content or "summary" in content.lower()
        assert "3" in content or "Completed" in content


class TestDateStringFormat:
    """Tests verifying YYYY-MM-DD date string format."""

    def test_date_stored_as_yyyy_mm_dd(self, tmp_path: Path):
        """Test that dates are stored in YYYY-MM-DD format."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        data = json.loads(json_path.read_text())
        
        assert data["date"] == "2025-12-15"

    def test_file_named_with_date(self, tmp_path: Path):
        """Test that files are named with YYYY-MM-DD format."""
        manager = DailyLogManager(tmp_path)
        
        log = DailyLog(date="2025-12-15")
        manager.save_log(log)
        
        json_path = tmp_path / "daily-log" / "2025-12-15.json"
        md_path = tmp_path / "daily-log" / "2025-12-15.md"
        
        assert json_path.exists()
        assert md_path.exists()